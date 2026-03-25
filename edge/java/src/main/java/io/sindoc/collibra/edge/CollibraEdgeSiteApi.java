package io.sindoc.collibra.edge;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * The REST API contract that a Collibra-compatible Edge Site must implement.
 *
 * <p>Collibra DGC communicates with on-premises edge sites through this API surface.
 * Implementations of this interface are exposed by the {@link EdgeSiteServer} under
 * the path prefix {@code /api/edge/v1/}.
 *
 * <h2>Endpoint summary</h2>
 * <pre>
 *   GET  /health                                  → {@link #health()}
 *   GET  /api/edge/v1/status                      → {@link #status()}
 *   POST /api/edge/v1/register                    → {@link #register(RegistrationRequest)}
 *   GET  /api/edge/v1/capabilities                → {@link #listCapabilities()}
 *   POST /api/edge/v1/capabilities/{type}/invoke  → {@link #invokeCapability(String, InvocationRequest)}
 * </pre>
 *
 * <p>All responses are serialised as JSON.  Error responses use the standard
 * Collibra error envelope:
 * <pre>
 *   { "errorCode": "...", "errorMessage": "...", "errorType": "...", "context": {} }
 * </pre>
 *
 * @since 1.0
 */
public interface CollibraEdgeSiteApi {

    // ── Response types ────────────────────────────────────────────────────────

    /**
     * Response for {@code GET /health}.
     *
     * <p>HTTP status {@code 200} when healthy, {@code 503} when unhealthy.
     *
     * @param status   {@code "UP"} or {@code "DOWN"}
     * @param siteId   the stable site identifier
     * @param checkedAt the instant of the health check
     * @param details  per-check detail map
     */
    record HealthResponse(
            String status,
            String siteId,
            Instant checkedAt,
            Map<String, Object> details) {}

    /**
     * Response for {@code GET /api/edge/v1/status}.
     *
     * @param siteId         the stable site identifier
     * @param siteName       the display name
     * @param status         the current {@link EdgeSiteStatus} as a string
     * @param registrationState the DGC registration state as a string
     * @param capabilities   per-capability status entries
     * @param reportedAt     the instant at which the status was sampled
     */
    record SiteStatusResponse(
            String siteId,
            String siteName,
            String status,
            String registrationState,
            List<CapabilityStatusEntry> capabilities,
            Instant reportedAt) {}

    /**
     * A single capability entry within a {@link SiteStatusResponse}.
     *
     * @param type    the capability type API key (e.g. {@code "connect"})
     * @param status  the capability's lifecycle status as a string
     * @param healthy {@code true} if the capability's health check passed
     * @param message additional detail, or empty string
     */
    record CapabilityStatusEntry(
            String type,
            String status,
            boolean healthy,
            String message) {}

    /**
     * Request body for {@code POST /api/edge/v1/register}.
     *
     * @param registrationKey the DGC-issued key from {@link EdgeSiteConfig#getRegistrationKey()}
     * @param siteId          the stable site identifier
     * @param hostname        the reachable FQDN of this edge node
     * @param httpPort        the HTTP port
     * @param capabilities    the capability API keys being declared
     */
    record RegistrationRequest(
            String registrationKey,
            String siteId,
            String hostname,
            int httpPort,
            List<String> capabilities) {}

    /**
     * Response body for {@code POST /api/edge/v1/register}.
     *
     * @param siteId            the site identifier confirmed by DGC
     * @param registrationToken the bearer token for subsequent API calls
     * @param dgcEdgeApiBase    the DGC-side edge API base URL for this site
     * @param tokenExpiresAt    the expiry instant for the registration token
     */
    record RegistrationResponse(
            String siteId,
            String registrationToken,
            String dgcEdgeApiBase,
            Instant tokenExpiresAt) {}

    /**
     * Metadata describing an active capability.
     *
     * @param type        the capability type API key
     * @param capabilityId the stable capability instance identifier
     * @param status      the lifecycle status as a string
     * @param properties  capability runtime properties
     */
    record CapabilityInfo(
            String type,
            String capabilityId,
            String status,
            Map<String, String> properties) {}

    /**
     * Request body for {@code POST /api/edge/v1/capabilities/{type}/invoke}.
     *
     * @param invocationId a DGC-issued identifier for this invocation (for idempotency)
     * @param parameters   capability-type-specific invocation parameters
     */
    record InvocationRequest(
            String invocationId,
            Map<String, Object> parameters) {}

    /**
     * Response body for {@code POST /api/edge/v1/capabilities/{type}/invoke}.
     *
     * @param invocationId the DGC-issued identifier echoed back
     * @param success      {@code true} if the invocation completed without error
     * @param payload      the result payload; structure is capability-type-specific
     * @param errorMessage error description when {@code success = false}, or {@code null}
     */
    record InvocationResponse(
            String invocationId,
            boolean success,
            Map<String, Object> payload,
            String errorMessage) {}

    // ── API methods ───────────────────────────────────────────────────────────

    /**
     * Liveness probe.
     *
     * <p>Mapped to {@code GET /health}.
     * Returns HTTP {@code 200} when the site is {@link EdgeSiteStatus#isOperational()},
     * {@code 503} otherwise.
     *
     * @return the health response
     */
    HealthResponse health();

    /**
     * Returns the current registration and capability status.
     *
     * <p>Mapped to {@code GET /api/edge/v1/status}.
     *
     * @return the site status response
     */
    SiteStatusResponse status();

    /**
     * Initiates or refreshes DGC registration.
     *
     * <p>Mapped to {@code POST /api/edge/v1/register}.
     * On success, the returned token is stored and used for all subsequent DGC API calls.
     *
     * @param request the registration request
     * @return the DGC registration response
     * @throws EdgeSiteException if registration is rejected
     */
    RegistrationResponse register(RegistrationRequest request) throws EdgeSiteException;

    /**
     * Returns metadata for all active capabilities.
     *
     * <p>Mapped to {@code GET /api/edge/v1/capabilities}.
     *
     * @return an immutable list of active capability descriptors
     */
    List<CapabilityInfo> listCapabilities();

    /**
     * Invokes a capability on behalf of Collibra DGC.
     *
     * <p>Mapped to {@code POST /api/edge/v1/capabilities/{type}/invoke}.
     * The {@code type} path parameter is the capability's API key (e.g. {@code "connect"}).
     *
     * @param type    the capability API key from the request path
     * @param request the invocation request from DGC
     * @return the invocation result to be returned to DGC
     * @throws EdgeSiteException if the capability is not active or the invocation fails
     */
    InvocationResponse invokeCapability(String type, InvocationRequest request) throws EdgeSiteException;
}
