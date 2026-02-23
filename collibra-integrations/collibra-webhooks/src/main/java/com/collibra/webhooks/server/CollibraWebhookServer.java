package com.collibra.webhooks.server;

import com.collibra.webhooks.config.WebhookServerConfig;
import com.collibra.webhooks.handler.WebhookHandler;
import com.collibra.webhooks.handler.WebhookHandlerException;
import com.collibra.webhooks.model.WebhookEvent;
import com.collibra.webhooks.security.HmacVerifier;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.eclipse.jetty.server.Server;
import org.eclipse.jetty.server.ServerConnector;
import org.eclipse.jetty.servlet.ServletContextHandler;
import org.eclipse.jetty.servlet.ServletHolder;
import org.eclipse.jetty.util.thread.QueuedThreadPool;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Embedded Jetty HTTP server that receives and dispatches Collibra webhook events.
 *
 * <h2>Usage</h2>
 * <pre>
 *   WebhookServerConfig config = WebhookServerConfig.builder()
 *       .port(8080)
 *       .path("/collibra/events")
 *       .sharedSecret("super-secret")
 *       .requireSignatureVerification(true)
 *       .build();
 *
 *   CollibraWebhookServer server = new CollibraWebhookServer(config);
 *   server.registerHandler(EventType.ASSET_CREATED, event -> {
 *       System.out.println("New asset: " + event.getResourceName());
 *   });
 *   server.registerHandler(EventType.WORKFLOW_STATE_CHANGED, new MyWorkflowHandler());
 *   server.start();
 *   // ... application runs ...
 *   server.stop();
 * </pre>
 */
public class CollibraWebhookServer {

    private static final Logger log = LoggerFactory.getLogger(CollibraWebhookServer.class);
    private static final String SIG_HEADER = "X-Collibra-Signature";

    private final WebhookServerConfig config;
    private final ObjectMapper        mapper;
    private final HmacVerifier        hmacVerifier;

    /** eventType → ordered list of handlers */
    private final Map<String, List<WebhookHandler>> handlers = new HashMap<>();
    /** Catch-all handlers invoked for every event regardless of type */
    private final List<WebhookHandler> globalHandlers = new ArrayList<>();

    private Server jettyServer;

    public CollibraWebhookServer(WebhookServerConfig config) {
        this.config = config;
        this.mapper = new ObjectMapper().registerModule(new JavaTimeModule());
        this.hmacVerifier = config.getSharedSecret() != null
                ? new HmacVerifier(config.getSharedSecret())
                : null;
    }

    // ------------------------------------------------------------------
    // Registration API
    // ------------------------------------------------------------------

    /**
     * Registers a handler for a specific Collibra event type string.
     *
     * @param eventType one of the constants in {@link com.collibra.webhooks.model.EventType}
     * @param handler   the handler implementation
     */
    public synchronized void registerHandler(String eventType, WebhookHandler handler) {
        handlers.computeIfAbsent(eventType, k -> new ArrayList<>()).add(handler);
        log.info("Registered handler {} for eventType='{}'", handler.getClass().getSimpleName(), eventType);
    }

    /**
     * Registers a catch-all handler that receives every event regardless of type.
     */
    public synchronized void registerGlobalHandler(WebhookHandler handler) {
        globalHandlers.add(handler);
        log.info("Registered global handler {}", handler.getClass().getSimpleName());
    }

    // ------------------------------------------------------------------
    // Lifecycle
    // ------------------------------------------------------------------

    public void start() throws Exception {
        QueuedThreadPool pool = new QueuedThreadPool(config.getMaxThreads(), 2);
        jettyServer = new Server(pool);

        ServerConnector connector = new ServerConnector(jettyServer);
        connector.setPort(config.getPort());
        jettyServer.addConnector(connector);

        ServletContextHandler ctx = new ServletContextHandler();
        ctx.setContextPath("/");
        ctx.addServlet(new ServletHolder(new WebhookServlet()), config.getPath());
        jettyServer.setHandler(ctx);

        jettyServer.start();
        log.info("Collibra webhook server listening on port {} at path {}", config.getPort(), config.getPath());
    }

    public void stop() throws Exception {
        if (jettyServer != null) {
            jettyServer.stop();
            log.info("Collibra webhook server stopped");
        }
    }

    // ------------------------------------------------------------------
    // Internal servlet
    // ------------------------------------------------------------------

    private class WebhookServlet extends HttpServlet {

        @Override
        protected void doPost(HttpServletRequest req, HttpServletResponse resp) throws IOException {
            byte[] body = req.getInputStream().readAllBytes();

            // Signature verification
            if (config.isRequireSignatureVerification()) {
                String sig = req.getHeader(SIG_HEADER);
                if (hmacVerifier == null || !hmacVerifier.verify(body, sig)) {
                    log.warn("Rejected webhook delivery — invalid or missing signature");
                    resp.sendError(HttpServletResponse.SC_UNAUTHORIZED, "Invalid signature");
                    return;
                }
            }

            WebhookEvent event;
            try {
                event = mapper.readValue(body, WebhookEvent.class);
            } catch (Exception e) {
                log.error("Failed to deserialize webhook payload", e);
                resp.sendError(HttpServletResponse.SC_BAD_REQUEST, "Malformed JSON payload");
                return;
            }

            log.debug("Dispatching event: {}", event);
            dispatch(event);

            resp.setStatus(HttpServletResponse.SC_OK);
            resp.getWriter().write("{\"status\":\"accepted\"}");
        }
    }

    private void dispatch(WebhookEvent event) {
        List<WebhookHandler> targeted = handlers.getOrDefault(event.getEventType(), Collections.emptyList());
        List<WebhookHandler> all = new ArrayList<>(globalHandlers);
        all.addAll(targeted);

        for (WebhookHandler h : all) {
            try {
                h.handle(event);
            } catch (WebhookHandlerException e) {
                log.error("Handler {} threw an exception for event {}: {}",
                        h.getClass().getSimpleName(), event.getEventId(), e.getMessage(), e);
            } catch (Exception e) {
                log.error("Unexpected error in handler {} for event {}",
                        h.getClass().getSimpleName(), event.getEventId(), e);
            }
        }
    }
}
