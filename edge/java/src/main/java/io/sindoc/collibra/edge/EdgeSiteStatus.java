package io.sindoc.collibra.edge;

/**
 * Lifecycle status of a Collibra Edge Site.
 *
 * <p>Status transitions follow the linear path:
 * <pre>
 *   INITIALIZING → REGISTERING → REGISTERED → READY
 *                                           ↘ DEGRADED
 *                       ← DISCONNECTED ←───────┘
 *                       → ERROR  (terminal — restart required)
 * </pre>
 *
 * <p>Only {@code READY} and {@code DEGRADED} are visible to the CDN and to Collibra DGC
 * as operational states.  All others indicate transitional or failure conditions.
 *
 * @since 1.0
 */
public enum EdgeSiteStatus {

    /**
     * The edge site is starting up.  Configuration is being loaded and validated.
     * No network connections have been established yet.
     */
    INITIALIZING,

    /**
     * The site is performing the registration handshake with Collibra DGC.
     * The registration key is being exchanged and capabilities are being declared.
     */
    REGISTERING,

    /**
     * DGC registration is complete.  The site identity and registration token have
     * been obtained.  Capabilities are activating.
     */
    REGISTERED,

    /**
     * All configured capabilities are active and healthy.  The site is fully
     * operational and ready to serve requests from Collibra DGC and the CDN.
     */
    READY,

    /**
     * One or more capabilities have failed but the site remains partially operational.
     * DGC will receive a degraded health response.  Alerting should be triggered.
     */
    DEGRADED,

    /**
     * The site has lost its connection to Collibra DGC.  Capabilities that require
     * DGC connectivity are suspended.  Local capabilities (e.g. static site serving)
     * continue to function.  Automatic reconnection is attempted.
     */
    DISCONNECTED,

    /**
     * A fatal error has occurred from which the site cannot recover automatically.
     * Operator intervention is required.  The HTTP {@code /health} endpoint returns
     * {@code 503} in this state.
     */
    ERROR;

    /**
     * Returns {@code true} if the site can serve requests from the CDN.
     * {@code READY} and {@code DEGRADED} are both considered operational.
     *
     * @return {@code true} when the site is in an operational state
     */
    public boolean isOperational() {
        return this == READY || this == DEGRADED;
    }

    /**
     * Returns {@code true} if the site is in a transitional state and has not yet
     * reached a stable operational or terminal status.
     *
     * @return {@code true} when the site is still starting up or registering
     */
    public boolean isTransitional() {
        return this == INITIALIZING || this == REGISTERING;
    }
}
