package io.sindoc.collibra.edge;

import java.time.Instant;
import java.util.Map;

/**
 * Health reporting interface for a Collibra Edge Site.
 *
 * <p>The {@link #checkHealth()} result is served by the embedded HTTP server at
 * {@code GET /health}.  Collibra DGC polls this endpoint as a liveness probe.
 * The CDN also uses it for upstream health-checking.
 *
 * <p>All check methods are synchronous.  Implementations should enforce a short
 * internal timeout (≤ 5 seconds) to prevent slow DGC or JDBC checks from blocking
 * the HTTP server thread.
 *
 * @since 1.0
 */
public interface EdgeSiteHealth {

    /**
     * Represents the health of a single check.
     *
     * @param healthy  {@code true} if the check passed
     * @param message  human-readable description; reason for failure if unhealthy
     * @param details  additional key-value pairs for structured logging
     * @param checkedAt the instant at which the check was performed
     */
    record HealthStatus(
            boolean healthy,
            String message,
            Map<String, Object> details,
            Instant checkedAt) {

        /**
         * Convenience constructor without extra details.
         *
         * @param healthy {@code true} if the check passed
         * @param message human-readable description
         */
        public HealthStatus(boolean healthy, String message) {
            this(healthy, message, Map.of(), Instant.now());
        }
    }

    /**
     * Performs the composite liveness check for the edge site.
     *
     * <p>The composite result is {@code healthy = true} only when all sub-checks pass.
     * In {@link EdgeSiteStatus#DEGRADED} state the composite is unhealthy even though
     * the site continues to serve requests.
     *
     * <p>This result is serialised to JSON and returned by {@code GET /health}.
     * Collibra DGC interprets any non-2xx HTTP response as an unhealthy site.
     *
     * @return the composite health status
     */
    HealthStatus checkHealth();

    /**
     * Checks connectivity to the Collibra DGC instance.
     *
     * <p>Performs a lightweight HTTP probe against the DGC {@code /health} or
     * {@code /rest/2.0/ping} endpoint.  Returns unhealthy if the probe times out
     * or returns a non-2xx status.
     *
     * @return connectivity health status
     */
    HealthStatus checkDgcConnectivity();

    /**
     * Returns per-capability health statuses.
     *
     * <p>The map contains an entry for every capability in
     * {@link EdgeSiteConfig#getEnabledCapabilities()}.  Capabilities that are
     * {@link EdgeSiteStatus#INITIALIZING} are reported as unhealthy with the message
     * {@code "activating"}.
     *
     * @return an immutable map from capability type to its current health status
     */
    Map<EdgeSiteCapabilityType, HealthStatus> checkCapabilities();

    /**
     * Returns the current site status as a summary health object.
     *
     * <p>Convenience method combining {@link #checkHealth()},
     * {@link #checkDgcConnectivity()}, and {@link #checkCapabilities()} into a
     * single structured response suitable for the {@code GET /api/edge/v1/status}
     * endpoint.
     *
     * @return a status summary keyed by check name
     */
    Map<String, HealthStatus> summarise();
}
