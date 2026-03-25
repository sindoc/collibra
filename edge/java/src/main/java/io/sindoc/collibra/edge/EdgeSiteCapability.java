package io.sindoc.collibra.edge;

import java.util.Map;

/**
 * A single capability hosted by a Collibra Edge Site.
 *
 * <p>Each capability encapsulates one feature area that the edge site offers to
 * Collibra DGC.  Implementations are managed by the {@link EdgeSite} lifecycle —
 * they are activated on startup (after registration) and deactivated on shutdown.
 *
 * <p>Capabilities that require DGC connectivity (see
 * {@link EdgeSiteCapabilityType#requiresDgcConnection()}) are suspended automatically
 * when the site transitions to {@link EdgeSiteStatus#DISCONNECTED}.
 *
 * <h2>Implementing a capability</h2>
 * <pre>
 * public class ConnectCapability implements EdgeSiteCapability {
 *
 *     {@literal @}Override
 *     public EdgeSiteCapabilityType getType() { return EdgeSiteCapabilityType.CONNECT; }
 *
 *     {@literal @}Override
 *     public void activate() throws EdgeSiteException {
 *         // open JDBC connection pool, register data source metadata with DGC
 *     }
 *
 *     {@literal @}Override
 *     public InvocationResult invoke(Map&lt;String, Object&gt; parameters) throws EdgeSiteException {
 *         // execute JDBC query or schema discovery requested by DGC
 *     }
 * }
 * </pre>
 *
 * @since 1.0
 */
public interface EdgeSiteCapability {

    /**
     * The result of a capability invocation requested by Collibra DGC.
     *
     * @param success   {@code true} if the invocation completed without error
     * @param payload   the result payload; structure is capability-type-specific
     * @param errorMessage error description when {@code success = false}, or {@code null}
     */
    record InvocationResult(boolean success, Map<String, Object> payload, String errorMessage) {

        /**
         * Convenience constructor for a successful invocation.
         *
         * @param payload the result payload
         */
        public InvocationResult(Map<String, Object> payload) {
            this(true, payload, null);
        }
    }

    /**
     * Returns the type of this capability.
     *
     * @return the capability type
     */
    EdgeSiteCapabilityType getType();

    /**
     * Returns a stable identifier for this capability instance.
     *
     * <p>Typically a combination of site ID and capability type, e.g.
     * {@code "edge-site-brussels-01:connect"}.  This ID is included in DGC
     * registration payloads and in Singine domain event records.
     *
     * @return the capability instance identifier
     */
    String getCapabilityId();

    /**
     * Returns the current status of this capability.
     *
     * @return the capability's lifecycle status
     */
    EdgeSiteStatus getStatus();

    /**
     * Returns the runtime properties of this capability.
     *
     * <p>The map may include connection strings, endpoint URLs, or other
     * operational metadata.  Values containing secrets must not appear here;
     * use the configuration layer for secrets.
     *
     * @return an immutable map of capability properties
     */
    Map<String, String> getProperties();

    /**
     * Activates this capability.
     *
     * <p>Called by the {@link EdgeSite} after DGC registration is complete.
     * Implementations should establish any required connections, register with
     * the DGC capability endpoint, and transition their status to
     * {@link EdgeSiteStatus#READY}.
     *
     * @throws EdgeSiteException if activation fails; the site will transition to
     *         {@link EdgeSiteStatus#DEGRADED} if other capabilities are active,
     *         or to {@link EdgeSiteStatus#ERROR} if no capabilities can activate
     */
    void activate() throws EdgeSiteException;

    /**
     * Deactivates this capability.
     *
     * <p>Called by the {@link EdgeSite} during orderly shutdown or when a
     * {@link EdgeSiteStatus#DISCONNECTED} transition requires capability suspension.
     * Implementations should release resources and deregister from DGC.
     *
     * @throws EdgeSiteException if deactivation fails (non-fatal; logged and ignored
     *         during shutdown)
     */
    void deactivate() throws EdgeSiteException;

    /**
     * Invokes this capability with parameters supplied by Collibra DGC.
     *
     * <p>This is the hot path — called when DGC issues a capability invocation
     * request to the edge site REST API.  Implementations must be thread-safe;
     * DGC may issue concurrent invocations.
     *
     * <p>Parameter and result structures are defined per capability type in the
     * Collibra Edge SDK documentation.
     *
     * @param parameters the invocation parameters from DGC
     * @return the invocation result to be returned to DGC
     * @throws EdgeSiteException if the invocation fails
     */
    InvocationResult invoke(Map<String, Object> parameters) throws EdgeSiteException;

    /**
     * Returns a health snapshot for this capability.
     *
     * <p>Called by {@link EdgeSiteHealth#checkCapabilities()} to build the
     * composite health response.  Implementations should perform only a lightweight
     * probe (e.g. JDBC ping, DGC heartbeat) and return quickly.
     *
     * @return the current health status
     */
    EdgeSiteHealth.HealthStatus health();
}
