package io.sindoc.collibra.edge;

import java.util.Collection;
import java.util.Optional;

/**
 * Top-level lifecycle facade for a Collibra Edge Site.
 *
 * <p>{@code EdgeSite} is the central object owned by the container process.  It
 * coordinates startup, capability activation, server binding, DGC registration, and
 * orderly shutdown.  All other interfaces in this package are reachable through it.
 *
 * <h2>Startup sequence</h2>
 * <ol>
 *   <li>Load and validate {@link EdgeSiteConfig}.</li>
 *   <li>Start the {@link EdgeSiteServer} on the configured port.</li>
 *   <li>Register with Collibra DGC via {@link EdgeSiteRegistry} using the
 *       registration key.</li>
 *   <li>Activate each {@link EdgeSiteCapability} declared in
 *       {@link EdgeSiteConfig#getEnabledCapabilities()}.</li>
 *   <li>Transition status to {@link EdgeSiteStatus#READY} (or
 *       {@link EdgeSiteStatus#DEGRADED} if some capabilities failed to activate).</li>
 * </ol>
 *
 * <h2>Shutdown sequence</h2>
 * <ol>
 *   <li>Drain in-flight capability invocations.</li>
 *   <li>Deactivate all capabilities.</li>
 *   <li>Stop the HTTP server.</li>
 *   <li>Optionally deregister from DGC.</li>
 * </ol>
 *
 * <h2>Usage example</h2>
 * <pre>
 * EdgeSiteConfig config = ...; // load from environment / properties file
 * EdgeSite site = EdgeSiteFactory.create(config);
 * site.initialize();
 *
 * Runtime.getRuntime().addShutdownHook(new Thread(() -> {
 *     try { site.shutdown(); } catch (EdgeSiteException e) { log.error(e); }
 * }));
 * </pre>
 *
 * @since 1.0
 */
public interface EdgeSite {

    /**
     * Returns the immutable configuration for this edge site.
     *
     * @return the site configuration
     */
    EdgeSiteConfig getConfig();

    /**
     * Returns the current lifecycle status of this edge site.
     *
     * @return the current status
     */
    EdgeSiteStatus getStatus();

    /**
     * Returns the registry that manages DGC registration for this site.
     *
     * @return the site registry
     */
    EdgeSiteRegistry getRegistry();

    /**
     * Returns the embedded HTTP server.
     *
     * @return the site server
     */
    EdgeSiteServer getServer();

    /**
     * Returns the health reporter for this site.
     *
     * @return the health interface
     */
    EdgeSiteHealth getHealth();

    /**
     * Returns all capabilities registered with this site.
     *
     * <p>Includes capabilities in any lifecycle state, including those that failed
     * to activate.
     *
     * @return an immutable collection of all registered capabilities
     */
    Collection<EdgeSiteCapability> getCapabilities();

    /**
     * Looks up a specific capability by type.
     *
     * @param type the capability type to look up
     * @return an {@link Optional} containing the capability, or empty if the type
     *         is not enabled for this site
     */
    Optional<EdgeSiteCapability> getCapability(EdgeSiteCapabilityType type);

    /**
     * Initialises and starts the edge site.
     *
     * <p>Executes the full startup sequence: validate config, start server, register
     * with DGC, activate capabilities.  Returns only after the site has reached
     * {@link EdgeSiteStatus#READY} or {@link EdgeSiteStatus#DEGRADED}.
     *
     * <p>This method is idempotent — calling it on an already-running site has no
     * effect.
     *
     * @throws EdgeSiteException if a fatal startup failure occurs (e.g. invalid config,
     *         DGC unreachable, server port already in use)
     */
    void initialize() throws EdgeSiteException;

    /**
     * Shuts down the edge site gracefully.
     *
     * <p>Executes the shutdown sequence: drain invocations, deactivate capabilities,
     * stop server.  Blocks until shutdown is complete.
     *
     * <p>This method is idempotent — calling it on an already-stopped site has no effect.
     *
     * @throws EdgeSiteException if shutdown cannot be completed cleanly (non-fatal in
     *         practice — callers should log and proceed with process exit)
     */
    void shutdown() throws EdgeSiteException;

    /**
     * Returns the Collibra Edge Site REST API handler.
     *
     * <p>The returned object is the implementation of {@link CollibraEdgeSiteApi} that
     * is wired into the HTTP server.  It can be used directly for testing or for
     * programmatic invocation without going through HTTP.
     *
     * @return the Collibra Edge Site API implementation
     */
    CollibraEdgeSiteApi getApi();
}
