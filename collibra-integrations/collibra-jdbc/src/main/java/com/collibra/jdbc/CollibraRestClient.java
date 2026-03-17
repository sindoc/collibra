package com.collibra.jdbc;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.apache.hc.client5.http.classic.methods.HttpGet;
import org.apache.hc.client5.http.classic.methods.HttpPost;
import org.apache.hc.client5.http.impl.classic.CloseableHttpClient;
import org.apache.hc.client5.http.impl.classic.HttpClients;
import org.apache.hc.core5.http.ContentType;
import org.apache.hc.core5.http.io.entity.StringEntity;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Thin HTTP client that wraps Collibra REST API v2 calls used by the JDBC driver.
 *
 * <p>Authentication flow:
 * <ol>
 *   <li>POST {@code /rest/2.0/auth/sessions} with username + password</li>
 *   <li>Store the {@code JSESSIONID} cookie and {@code X-CSRF-TOKEN} header value</li>
 *   <li>Include both on every subsequent request</li>
 * </ol>
 */
public class CollibraRestClient implements AutoCloseable {

    private static final Logger log = LoggerFactory.getLogger(CollibraRestClient.class);

    private final CollibraConnectionConfig config;
    private final CloseableHttpClient      http;
    private final ObjectMapper             mapper;

    private volatile String jsessionId;
    private volatile String csrfToken;
    private volatile boolean authenticated = false;

    CollibraRestClient(CollibraConnectionConfig config) {
        this.config = config;
        this.http   = HttpClients.createDefault();
        this.mapper = new ObjectMapper().registerModule(new JavaTimeModule());
    }

    // ------------------------------------------------------------------
    // Authentication
    // ------------------------------------------------------------------

    public synchronized void authenticate() throws SQLException {
        if (authenticated) return;
        String url = config.getBaseUrl() + "/rest/2.0/auth/sessions";
        String body = String.format(
                "{\"username\":\"%s\",\"password\":\"%s\"}",
                escape(config.getUser()), escape(config.getPassword()));

        HttpPost post = new HttpPost(url);
        post.setEntity(new StringEntity(body, ContentType.APPLICATION_JSON));
        post.setHeader("Accept", "application/json");

        try {
            http.execute(post, response -> {
                int status = response.getCode();
                if (status != 200) {
                    throw new IOException("Authentication failed: HTTP " + status);
                }
                // Extract CSRF token from response header
                var csrfHeader = response.getFirstHeader("X-CSRF-TOKEN");
                if (csrfHeader != null) csrfToken = csrfHeader.getValue();

                // Extract session cookie (simplified — production should use cookie store)
                var cookieHeader = response.getFirstHeader("Set-Cookie");
                if (cookieHeader != null) {
                    String cookie = cookieHeader.getValue();
                    if (cookie.contains("JSESSIONID=")) {
                        jsessionId = cookie.split("JSESSIONID=")[1].split(";")[0];
                    }
                }
                authenticated = true;
                log.info("Authenticated with Collibra at {}", config.getBaseUrl());
                return null;
            });
        } catch (IOException e) {
            throw new SQLException("Failed to authenticate with Collibra: " + e.getMessage(), e);
        }
    }

    // ------------------------------------------------------------------
    // Query helpers (used by CollibraStatement / CollibraResultSet)
    // ------------------------------------------------------------------

    /**
     * Fetches a paginated list of assets with optional REST filter parameters.
     *
     * @param filterParams URL query params forwarded to /rest/2.0/assets, e.g. "name=Customer&typeId=..."
     * @param offset       pagination offset
     * @param limit        page size
     * @return list of row maps (column name → value)
     */
    public List<Map<String, Object>> queryAssets(String filterParams, int offset, int limit)
            throws SQLException {
        ensureAuthenticated();
        String url = config.getBaseUrl() + "/rest/2.0/assets?offset=" + offset +
                     "&limit=" + limit +
                     (filterParams.isBlank() ? "" : "&" + filterParams);
        JsonNode root = get(url);
        return parseResults(root, "results");
    }

    public List<Map<String, Object>> queryDomains(String filterParams, int offset, int limit)
            throws SQLException {
        ensureAuthenticated();
        String url = config.getBaseUrl() + "/rest/2.0/domains?offset=" + offset +
                     "&limit=" + limit +
                     (filterParams.isBlank() ? "" : "&" + filterParams);
        JsonNode root = get(url);
        return parseResults(root, "results");
    }

    public List<Map<String, Object>> queryCommunities(String filterParams, int offset, int limit)
            throws SQLException {
        ensureAuthenticated();
        String url = config.getBaseUrl() + "/rest/2.0/communities?offset=" + offset +
                     "&limit=" + limit +
                     (filterParams.isBlank() ? "" : "&" + filterParams);
        JsonNode root = get(url);
        return parseResults(root, "results");
    }

    /** Health-check — returns true if the Collibra instance is reachable. */
    public boolean ping() {
        try {
            HttpGet req = new HttpGet(config.getBaseUrl() + "/rest/2.0/ping");
            addAuthHeaders(req);
            return http.execute(req, r -> r.getCode() == 200);
        } catch (Exception e) {
            return false;
        }
    }

    @Override
    public void close() {
        try { http.close(); } catch (IOException ignored) {}
    }

    // ------------------------------------------------------------------
    // Internal helpers
    // ------------------------------------------------------------------

    private void ensureAuthenticated() throws SQLException {
        if (!authenticated) authenticate();
    }

    private JsonNode get(String url) throws SQLException {
        HttpGet req = new HttpGet(url);
        req.setHeader("Accept", "application/json");
        addAuthHeaders(req);

        try {
            return http.execute(req, response -> {
                int status = response.getCode();
                if (status == 401) throw new IOException("Session expired — re-authenticate");
                if (status != 200) throw new IOException("REST call failed: HTTP " + status + " for " + url);
                byte[] body = response.getEntity().getContent().readAllBytes();
                return mapper.readTree(body);
            });
        } catch (IOException e) {
            throw new SQLException("REST GET failed for " + url + ": " + e.getMessage(), e);
        }
    }

    private void addAuthHeaders(org.apache.hc.core5.http.HttpRequest req) {
        if (jsessionId != null) req.setHeader("Cookie", "JSESSIONID=" + jsessionId);
        if (csrfToken  != null) req.setHeader("X-CSRF-TOKEN", csrfToken);
    }

    private List<Map<String, Object>> parseResults(JsonNode root, String arrayField) {
        List<Map<String, Object>> rows = new ArrayList<>();
        JsonNode arr = root.has(arrayField) ? root.get(arrayField) : root;
        if (arr == null || !arr.isArray()) return rows;

        for (JsonNode item : arr) {
            Map<String, Object> row = new LinkedHashMap<>();
            item.fields().forEachRemaining(e -> row.put(e.getKey(), nodeToObject(e.getValue())));
            rows.add(row);
        }
        return rows;
    }

    private Object nodeToObject(JsonNode node) {
        if (node.isNull())    return null;
        if (node.isBoolean()) return node.booleanValue();
        if (node.isLong())    return node.longValue();
        if (node.isInt())     return node.intValue();
        if (node.isDouble())  return node.doubleValue();
        if (node.isTextual()) return node.textValue();
        return node.toString();
    }

    private static String escape(String s) {
        return s == null ? "" : s.replace("\"", "\\\"");
    }
}
