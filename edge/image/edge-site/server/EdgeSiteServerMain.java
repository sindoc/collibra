import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;

import java.io.*;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Duration;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.Executors;
import java.util.logging.*;

/**
 * Minimal Collibra Edge Site server.
 *
 * Implements the Collibra Edge Site REST API contract (io.sindoc.collibra.edge):
 *   GET  /health
 *   GET  /api/edge/v1/status
 *   POST /api/edge/v1/register
 *   GET  /api/edge/v1/capabilities
 *   POST /api/edge/v1/capabilities/{type}/invoke
 *   GET  /site/*           (static content from SITE_CONTENT_ROOT)
 *   GET  /                 (serves /site/index.html)
 *
 * On startup, DgcRegistrar attempts outbound registration with Collibra DGC cloud
 * (POST ${DGC_URL}/rest/2.0/edgeSites/${SITE_ID}/connectionRequests).
 * Registration is skipped in dev mode (empty or placeholder REG_KEY).
 *
 * Configuration via system properties (set by entrypoint.sh):
 *   collibra.edge.site.id
 *   collibra.edge.site.name
 *   collibra.edge.hostname
 *   collibra.dgc.url
 *   collibra.edge.registration.key
 *   collibra.edge.http.port
 *   collibra.edge.capabilities   (comma-separated)
 *   collibra.edge.site.content.root
 *
 * No external dependencies — uses only JDK 11 standard library.
 */
public class EdgeSiteServerMain {

    private static final Logger LOG = Logger.getLogger("edge-site");

    // ── Configuration ─────────────────────────────────────────────────────────

    static final String SITE_ID   = prop("collibra.edge.site.id",           "edge-site-local");
    static final String SITE_NAME = prop("collibra.edge.site.name",         SITE_ID);
    static final String HOSTNAME  = prop("collibra.edge.hostname",          "localhost");
    static final String DGC_URL   = prop("collibra.dgc.url",                "https://dgc.example.com");
    static final String REG_KEY   = prop("collibra.edge.registration.key",  "");
    static final int    HTTP_PORT = Integer.parseInt(prop("collibra.edge.http.port", "8080"));
    static final String CAPS_CSV  = prop("collibra.edge.capabilities",      "site");
    static final String CONTENT   = prop("collibra.edge.site.content.root", "/opt/edge/site/www");

    static final List<String> CAPABILITIES = Arrays.asList(CAPS_CSV.split(","));

    // Registration state (in-memory for this session)
    static volatile String  registrationState = "UNREGISTERED";
    static volatile String  registrationToken = null;
    static volatile Instant registeredAt      = null;

    // Pulse state
    static volatile Instant lastPulseAt       = null;
    static volatile String  pulseState        = "IDLE";    // IDLE | PULSING | FAILED
    static final long       PULSE_INTERVAL_MS = 60_000;    // 60 s

    // ── Main ──────────────────────────────────────────────────────────────────

    public static void main(String[] args) throws Exception {
        configureLogging();

        HttpServer server = HttpServer.create(new InetSocketAddress(HTTP_PORT), 0);
        server.createContext("/health",                    new HealthHandler());
        server.createContext("/api/edge/v1/status",       new StatusHandler());
        server.createContext("/api/edge/v1/register",     new RegisterHandler());
        server.createContext("/api/edge/v1/capabilities", new CapabilitiesHandler());
        server.createContext("/api/edge/v1/pulse",        new PulseHandler());
        server.createContext("/site",                      new StaticHandler(CONTENT));
        server.createContext("/",                          new RootHandler());
        server.setExecutor(Executors.newFixedThreadPool(8));
        server.start();

        LOG.info("Edge Site server started on :" + HTTP_PORT);
        LOG.info("  site-id    : " + SITE_ID);
        LOG.info("  site-name  : " + SITE_NAME);
        LOG.info("  hostname   : " + HOSTNAME);
        LOG.info("  dgc-url    : " + DGC_URL);
        LOG.info("  capabilities: " + CAPABILITIES);
        LOG.info("  content    : " + CONTENT);

        // Outbound registration with Collibra DGC cloud (non-blocking)
        Thread regThread = new Thread(new DgcRegistrar(), "dgc-registrar");
        regThread.setDaemon(true);
        regThread.start();

        // Pulse heartbeat — starts after registration
        Thread pulseThread = new Thread(new DgcPulse(), "dgc-pulse");
        pulseThread.setDaemon(true);
        pulseThread.start();
    }

    // ── DGC Registrar ─────────────────────────────────────────────────────────

    /**
     * Attempts to register this edge site with Collibra DGC cloud on startup.
     *
     * Calls:
     *   POST ${DGC_URL}/rest/2.0/edgeSites/${SITE_ID}/connectionRequests
     *
     * Body:
     *   {"registrationKey":"<key>","callbackUrl":"http://<hostname>:8080",
     *    "capabilities":["site","connect","catalog"]}
     *
     * Skipped when REG_KEY is blank or starts with "dev-placeholder".
     * Retries up to MAX_ATTEMPTS times with RETRY_DELAY between attempts.
     */
    static class DgcRegistrar implements Runnable {

        private static final int  MAX_ATTEMPTS = 5;
        private static final long RETRY_DELAY_MS = 15_000;

        @Override
        public void run() {
            if (REG_KEY == null || REG_KEY.isEmpty() || REG_KEY.startsWith("dev-placeholder")) {
                LOG.info("[registrar] No registration key — skipping DGC registration (dev/mock mode)");
                return;
            }

            String url      = DGC_URL + "/rest/2.0/edgeSites/" + SITE_ID + "/connectionRequests";
            String callback = "http://" + HOSTNAME + ":" + HTTP_PORT;

            // Build capabilities JSON array
            StringBuilder capsArr = new StringBuilder("[");
            for (int i = 0; i < CAPABILITIES.size(); i++) {
                if (i > 0) capsArr.append(",");
                capsArr.append("\"").append(CAPABILITIES.get(i).trim()).append("\"");
            }
            capsArr.append("]");

            String body = "{"
                + "\"registrationKey\":\"" + REG_KEY + "\","
                + "\"callbackUrl\":\"" + callback + "\","
                + "\"capabilities\":" + capsArr
                + "}";

            HttpClient client = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(10))
                .build();

            LOG.info("[registrar] Registering with Collibra DGC: " + url);

            for (int attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
                try {
                    HttpRequest req = HttpRequest.newBuilder()
                        .uri(URI.create(url))
                        .header("Content-Type", "application/json")
                        .header("Accept", "application/json")
                        .timeout(Duration.ofSeconds(30))
                        .POST(HttpRequest.BodyPublishers.ofString(body))
                        .build();

                    HttpResponse<String> resp =
                        client.send(req, HttpResponse.BodyHandlers.ofString());

                    int status = resp.statusCode();

                    if (status == 200 || status == 201) {
                        registrationState = "REGISTERED";
                        registeredAt      = Instant.now();
                        registrationToken = extractJson(resp.body(), "token",
                                            extractJson(resp.body(), "registrationToken", "cloud-token"));
                        LOG.info("[registrar] Registered with Collibra DGC — HTTP " + status);
                        return;

                    } else if (status == 409) {
                        // Already registered — treat as success
                        registrationState = "REGISTERED";
                        registeredAt      = Instant.now();
                        LOG.info("[registrar] Edge site already registered with DGC (HTTP 409)");
                        return;

                    } else if (status == 401 || status == 403) {
                        LOG.warning("[registrar] Registration rejected — invalid or expired key"
                            + " (HTTP " + status + "). Check COLLIBRA_EDGE_REG_KEY.");
                        return;   // No point retrying auth failures

                    } else {
                        LOG.warning("[registrar] Attempt " + attempt + "/" + MAX_ATTEMPTS
                            + " failed: HTTP " + status + " — " + resp.body());
                    }

                } catch (Exception e) {
                    LOG.warning("[registrar] Attempt " + attempt + "/" + MAX_ATTEMPTS
                        + " error: " + e.getMessage());
                }

                if (attempt < MAX_ATTEMPTS) {
                    try {
                        Thread.sleep(RETRY_DELAY_MS);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        return;
                    }
                }
            }

            LOG.warning("[registrar] DGC registration failed after " + MAX_ATTEMPTS
                + " attempts — running UNREGISTERED. Verify COLLIBRA_EDGE_REG_KEY and network.");
        }
    }

    // ── DGC Pulse ─────────────────────────────────────────────────────────────

    /**
     * Sends periodic heartbeat pulses to Collibra DGC once the site is registered.
     *
     * Calls:
     *   POST ${DGC_URL}/rest/2.0/edgeSites/${SITE_ID}/pulse
     *
     * Body:
     *   {"siteId":"<id>","status":"READY","capabilities":["site","connect",...]}
     *
     * Without regular pulses the DGC marks the edge site as offline/disconnected.
     * Interval: PULSE_INTERVAL_MS (60 s). Waits for REGISTERED state before starting.
     * Backs off to FAILED state on consecutive errors; recovers automatically.
     */
    static class DgcPulse implements Runnable {

        private static final int  MAX_ERRORS = 3;

        @Override
        public void run() {
            // Wait until registered (or skip entirely if no key)
            if (REG_KEY == null || REG_KEY.isEmpty() || REG_KEY.startsWith("dev-placeholder")) {
                LOG.info("[pulse] No registration key — pulse disabled (dev/mock mode)");
                return;
            }

            // Poll until registration completes (up to 5 minutes)
            int waitSeconds = 0;
            while (!"REGISTERED".equals(registrationState) && waitSeconds < 300) {
                try { Thread.sleep(5_000); } catch (InterruptedException e) { return; }
                waitSeconds += 5;
            }
            if (!"REGISTERED".equals(registrationState)) {
                LOG.warning("[pulse] Registration never completed — pulse not started");
                return;
            }

            String url = DGC_URL + "/rest/2.0/edgeSites/" + SITE_ID + "/pulse";

            // Build capabilities JSON array
            StringBuilder capsArr = new StringBuilder("[");
            for (int i = 0; i < CAPABILITIES.size(); i++) {
                if (i > 0) capsArr.append(",");
                capsArr.append("\"").append(CAPABILITIES.get(i).trim()).append("\"");
            }
            capsArr.append("]");

            HttpClient client = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(10))
                .build();

            LOG.info("[pulse] Starting heartbeat loop → " + url + " (every " + (PULSE_INTERVAL_MS / 1000) + "s)");
            pulseState = "PULSING";

            int errors = 0;

            while (!Thread.currentThread().isInterrupted()) {
                try {
                    Thread.sleep(PULSE_INTERVAL_MS);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    return;
                }

                String body = "{"
                    + "\"siteId\":\"" + SITE_ID + "\","
                    + "\"status\":\"READY\","
                    + "\"capabilities\":" + capsArr
                    + "}";

                try {
                    HttpRequest req = HttpRequest.newBuilder()
                        .uri(URI.create(url))
                        .header("Content-Type", "application/json")
                        .header("Accept", "application/json")
                        .header("Authorization", "Bearer " + (registrationToken != null ? registrationToken : ""))
                        .timeout(Duration.ofSeconds(20))
                        .POST(HttpRequest.BodyPublishers.ofString(body))
                        .build();

                    HttpResponse<String> resp =
                        client.send(req, HttpResponse.BodyHandlers.ofString());

                    int status = resp.statusCode();

                    if (status == 200 || status == 204) {
                        lastPulseAt = Instant.now();
                        pulseState  = "PULSING";
                        errors      = 0;
                        LOG.info("[pulse] Heartbeat OK — HTTP " + status);

                    } else if (status == 401 || status == 403) {
                        LOG.warning("[pulse] Pulse rejected (HTTP " + status + ") — token may have expired");
                        pulseState = "FAILED";
                        return;   // Stop; registrar must re-register

                    } else {
                        errors++;
                        LOG.warning("[pulse] Pulse HTTP " + status + " (error " + errors + "/" + MAX_ERRORS + ")");
                        if (errors >= MAX_ERRORS) {
                            pulseState = "FAILED";
                            LOG.warning("[pulse] Too many errors — pulse suspended. Check DGC connectivity.");
                            return;
                        }
                    }

                } catch (Exception e) {
                    errors++;
                    LOG.warning("[pulse] Pulse error (" + errors + "/" + MAX_ERRORS + "): " + e.getMessage());
                    if (errors >= MAX_ERRORS) {
                        pulseState = "FAILED";
                        LOG.warning("[pulse] Too many errors — pulse suspended.");
                        return;
                    }
                }
            }
        }
    }

    // ── Handlers ──────────────────────────────────────────────────────────────

    static class HealthHandler implements HttpHandler {
        @Override public void handle(HttpExchange ex) throws IOException {
            String body = json(
                "\"status\":\"UP\"",
                "\"siteId\":\"" + SITE_ID + "\"",
                "\"registrationState\":\"" + registrationState + "\"",
                "\"pulseState\":\"" + pulseState + "\"",
                "\"lastPulseAt\":" + (lastPulseAt != null ? "\"" + lastPulseAt + "\"" : "null"),
                "\"checkedAt\":\"" + Instant.now() + "\""
            );
            respond(ex, 200, body);
        }
    }

    static class PulseHandler implements HttpHandler {
        @Override public void handle(HttpExchange ex) throws IOException {
            if ("POST".equals(ex.getRequestMethod())) {
                // Manual pulse trigger (for testing / DGC-initiated probes)
                lastPulseAt = Instant.now();
                pulseState  = "PULSING";
                String body = json(
                    "\"siteId\":\"" + SITE_ID + "\"",
                    "\"pulseState\":\"" + pulseState + "\"",
                    "\"lastPulseAt\":\"" + lastPulseAt + "\"",
                    "\"triggeredAt\":\"" + Instant.now() + "\""
                );
                LOG.info("[pulse] Manual pulse triggered via POST /api/edge/v1/pulse");
                respond(ex, 200, body);
            } else {
                String body = json(
                    "\"siteId\":\"" + SITE_ID + "\"",
                    "\"pulseState\":\"" + pulseState + "\"",
                    "\"lastPulseAt\":" + (lastPulseAt != null ? "\"" + lastPulseAt + "\"" : "null"),
                    "\"intervalMs\":" + PULSE_INTERVAL_MS,
                    "\"registrationState\":\"" + registrationState + "\""
                );
                respond(ex, 200, body);
            }
        }
    }

    static class StatusHandler implements HttpHandler {
        @Override public void handle(HttpExchange ex) throws IOException {
            StringBuilder caps = new StringBuilder("[");
            for (int i = 0; i < CAPABILITIES.size(); i++) {
                String c = CAPABILITIES.get(i).trim();
                if (i > 0) caps.append(",");
                caps.append("{\"type\":\"").append(c)
                    .append("\",\"status\":\"READY\",\"healthy\":true,\"message\":\"\"}");
            }
            caps.append("]");
            String body = "{"
                + "\"siteId\":\"" + SITE_ID + "\","
                + "\"siteName\":\"" + SITE_NAME + "\","
                + "\"dgcUrl\":\"" + DGC_URL + "\","
                + "\"status\":\"READY\","
                + "\"registrationState\":\"" + registrationState + "\","
                + "\"pulseState\":\"" + pulseState + "\","
                + "\"lastPulseAt\":" + (lastPulseAt != null ? "\"" + lastPulseAt + "\"" : "null") + ","
                + "\"capabilities\":" + caps + ","
                + "\"reportedAt\":\"" + Instant.now() + "\""
                + "}";
            respond(ex, 200, body);
        }
    }

    static class RegisterHandler implements HttpHandler {
        @Override public void handle(HttpExchange ex) throws IOException {
            if (!"POST".equals(ex.getRequestMethod())) {
                respond(ex, 405, "{\"errorCode\":\"METHOD_NOT_ALLOWED\"}");
                return;
            }
            String reqBody = new String(ex.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
            registrationToken = "token-" + UUID.randomUUID();
            registrationState = "REGISTERED";
            registeredAt      = Instant.now();
            Instant expires   = registeredAt.plusSeconds(3600 * 24);
            String body = "{"
                + "\"siteId\":\"" + SITE_ID + "\","
                + "\"registrationToken\":\"" + registrationToken + "\","
                + "\"dgcEdgeApiBase\":\"" + DGC_URL + "/api/edge/sites/" + SITE_ID + "\","
                + "\"tokenExpiresAt\":\"" + expires + "\""
                + "}";
            LOG.info("Registered edge site via local /register endpoint: " + SITE_ID);
            respond(ex, 200, body);
        }
    }

    static class CapabilitiesHandler implements HttpHandler {
        @Override public void handle(HttpExchange ex) throws IOException {
            String path = ex.getRequestURI().getPath();

            // POST /api/edge/v1/capabilities/{type}/invoke
            if ("POST".equals(ex.getRequestMethod()) && path.contains("/invoke")) {
                String type = path.replaceAll(".*/capabilities/([^/]+)/invoke.*", "$1");
                String reqBody = new String(ex.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
                String invocationId = extractJson(reqBody, "invocationId", "inv-" + UUID.randomUUID());
                if (!CAPABILITIES.contains(type)) {
                    respond(ex, 404, "{\"errorCode\":\"CAPABILITY_NOT_FOUND\",\"type\":\"" + type + "\"}");
                    return;
                }
                String body = "{"
                    + "\"invocationId\":\"" + invocationId + "\","
                    + "\"success\":true,"
                    + "\"payload\":{\"type\":\"" + type + "\",\"status\":\"invoked\"},"
                    + "\"errorMessage\":null"
                    + "}";
                LOG.info("Capability invoked: " + type + " invocationId=" + invocationId);
                respond(ex, 200, body);
                return;
            }

            // GET /api/edge/v1/capabilities
            StringBuilder sb = new StringBuilder("[");
            for (int i = 0; i < CAPABILITIES.size(); i++) {
                String c = CAPABILITIES.get(i).trim();
                if (i > 0) sb.append(",");
                sb.append("{\"type\":\"").append(c).append("\",")
                  .append("\"capabilityId\":\"").append(SITE_ID).append(":").append(c).append("\",")
                  .append("\"status\":\"READY\",")
                  .append("\"properties\":{\"siteId\":\"").append(SITE_ID).append("\"}}");
            }
            sb.append("]");
            respond(ex, 200, sb.toString());
        }
    }

    static class StaticHandler implements HttpHandler {
        private final Path root;
        StaticHandler(String contentRoot) { this.root = Paths.get(contentRoot); }

        @Override public void handle(HttpExchange ex) throws IOException {
            String reqPath = ex.getRequestURI().getPath().replaceFirst("^/site", "");
            if (reqPath.isEmpty() || reqPath.equals("/")) reqPath = "/index.html";
            Path target = root.resolve(reqPath.substring(1)).normalize();
            if (!target.startsWith(root) || !Files.isRegularFile(target)) {
                respond(ex, 404, "{\"error\":\"not found\"}");
                return;
            }
            byte[] bytes = Files.readAllBytes(target);
            String ct = contentType(target.getFileName().toString());
            ex.getResponseHeaders().set("Content-Type", ct);
            ex.sendResponseHeaders(200, bytes.length);
            try (OutputStream os = ex.getResponseBody()) { os.write(bytes); }
        }
    }

    static class RootHandler implements HttpHandler {
        @Override public void handle(HttpExchange ex) throws IOException {
            ex.getResponseHeaders().set("Location", "/site/");
            ex.sendResponseHeaders(302, -1);
            ex.close();
        }
    }

    // ── Utilities ─────────────────────────────────────────────────────────────

    static void respond(HttpExchange ex, int status, String body) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        ex.getResponseHeaders().set("X-Edge-Site-Id", SITE_ID);
        ex.sendResponseHeaders(status, bytes.length);
        try (OutputStream os = ex.getResponseBody()) { os.write(bytes); }
    }

    static String json(String... pairs) {
        StringBuilder sb = new StringBuilder("{");
        for (int i = 0; i < pairs.length; i++) {
            if (i > 0) sb.append(",");
            sb.append(pairs[i]);
        }
        return sb.append("}").toString();
    }

    static String extractJson(String body, String key, String defaultVal) {
        String search = "\"" + key + "\":\"";
        int start = body.indexOf(search);
        if (start < 0) return defaultVal;
        start += search.length();
        int end = body.indexOf('"', start);
        return end < 0 ? defaultVal : body.substring(start, end);
    }

    static String contentType(String name) {
        if (name.endsWith(".html") || name.endsWith(".htm")) return "text/html; charset=utf-8";
        if (name.endsWith(".css"))  return "text/css; charset=utf-8";
        if (name.endsWith(".js"))   return "application/javascript; charset=utf-8";
        if (name.endsWith(".json")) return "application/json; charset=utf-8";
        if (name.endsWith(".png"))  return "image/png";
        if (name.endsWith(".svg"))  return "image/svg+xml";
        return "application/octet-stream";
    }

    static String prop(String key, String def) {
        String v = System.getProperty(key);
        return (v != null && !v.isEmpty()) ? v : def;
    }

    static void configureLogging() {
        Logger root = Logger.getLogger("");
        for (Handler h : root.getHandlers()) h.setFormatter(new SimpleFormatter() {
            @Override public String format(LogRecord r) {
                return String.format("[edge-site] %s %s%n",
                    r.getLevel(), r.getMessage());
            }
        });
    }
}
