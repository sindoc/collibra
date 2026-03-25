package io.sindoc.collibra.edge;

import java.time.Instant;
import java.util.List;

/**
 * Manages the registration lifecycle of an edge site with Collibra DGC.
 *
 * <p>Registration is the handshake through which an edge site declares its identity,
 * capabilities, and network endpoint to the central Collibra DGC instance.  Once
 * registered, DGC can route capability invocations to the site and the site can push
 * catalog updates to DGC.
 *
 * <p>Implementations must handle token refresh and re-registration transparently.
 * The registration token obtained from DGC has a finite lifetime and must be renewed
 * before expiry to avoid service interruption.
 *
 * @since 1.0
 */
public interface EdgeSiteRegistry {

    /**
     * The result of a successful registration handshake with Collibra DGC.
     *
     * @param siteId            the stable site identifier confirmed by DGC
     * @param registrationToken the bearer token issued by DGC for subsequent API calls
     * @param dgcEdgeApiBase    the DGC-side API base URL for this edge site
     * @param registeredAt      the instant at which registration completed
     * @param tokenExpiresAt    the instant at which the registration token expires
     * @param capabilities      the capabilities accepted by DGC
     */
    record RegistrationResult(
            String siteId,
            String registrationToken,
            String dgcEdgeApiBase,
            Instant registeredAt,
            Instant tokenExpiresAt,
            List<EdgeSiteCapabilityType> capabilities) {}

    /**
     * The current registration state of an edge site as reported by DGC.
     */
    enum RegistrationState {
        /** The site has completed registration and is known to DGC. */
        REGISTERED,
        /** The site has never registered or has been explicitly deregistered. */
        UNREGISTERED,
        /** A registration or token-renewal request is in flight. */
        PENDING,
        /** The site is registered but its token has expired. */
        TOKEN_EXPIRED
    }

    /**
     * Registers this edge site with Collibra DGC.
     *
     * <p>Sends the site configuration (identity, hostname, port, capabilities) to the
     * DGC registration endpoint using the registration key from
     * {@link EdgeSiteConfig#getRegistrationKey()}.  On success, DGC returns a bearer
     * token and an API base URL for the registered site.
     *
     * <p>This method is idempotent — calling it on an already-registered site
     * refreshes the registration record and renews the token.
     *
     * @param config the edge site configuration to register
     * @return the DGC-issued registration result
     * @throws EdgeSiteException with code {@link EdgeSiteException.Code#REGISTRATION_FAILED}
     *         if DGC rejects the registration request
     * @throws EdgeSiteException with code {@link EdgeSiteException.Code#INVALID_REGISTRATION_KEY}
     *         if the registration key is invalid or expired
     * @throws EdgeSiteException with code {@link EdgeSiteException.Code#DGC_UNREACHABLE}
     *         if the DGC endpoint cannot be reached
     */
    RegistrationResult register(EdgeSiteConfig config) throws EdgeSiteException;

    /**
     * Deregisters this edge site from Collibra DGC.
     *
     * <p>Signals to DGC that the site is being permanently removed.  All capability
     * registrations associated with the site are withdrawn.  This is a destructive
     * operation — the site will need to re-register (with a new registration key) to
     * reconnect to DGC.
     *
     * @param siteId the stable site identifier to deregister
     * @throws EdgeSiteException if the deregistration request fails
     */
    void deregister(String siteId) throws EdgeSiteException;

    /**
     * Queries the current registration state of a site.
     *
     * <p>Performs a lightweight API call to DGC to retrieve the current registration
     * status.  Does not modify any state.
     *
     * @param siteId the stable site identifier to query
     * @return the current registration state
     * @throws EdgeSiteException if the DGC query fails
     */
    RegistrationState getRegistrationState(String siteId) throws EdgeSiteException;

    /**
     * Renews the DGC bearer token before it expires.
     *
     * <p>Should be called by a background thread when the current token is within
     * a configurable refresh window of its expiry time (typically 10% of total lifetime
     * remaining).
     *
     * @param currentResult the current registration result whose token should be renewed
     * @return an updated registration result with a fresh token and expiry
     * @throws EdgeSiteException if token renewal fails
     */
    RegistrationResult renewToken(RegistrationResult currentResult) throws EdgeSiteException;
}
