package io.sindoc.collibra.edge;

import java.util.function.BiConsumer;

/**
 * The embedded HTTP server that serves the Collibra Edge Site API and hosted web content.
 *
 * <p>The server exposes two path trees:
 * <ul>
 *   <li><strong>{@code /api/edge/v1/}</strong> — Collibra Edge Site REST API (see
 *       {@link CollibraEdgeSiteApi}).  All paths under this prefix implement the
 *       protocol expected by Collibra DGC.</li>
 *   <li><strong>{@code /site/}</strong> — Edge-hosted web content served from the
 *       directory configured in {@link EdgeSiteConfig#getSiteContentRoot()}.  Only
 *       active when the {@link EdgeSiteCapabilityType#SITE} capability is enabled.</li>
 *   <li><strong>{@code /health}</strong> — Liveness probe endpoint; returns
 *       {@code 200 OK} with a JSON health object when the site is operational.</li>
 * </ul>
 *
 * <p>The server runs on the port defined by {@link EdgeSiteConfig#getHttpPort()}.
 * TLS termination is expected to be handled by the CDN (nginx) layer; the server
 * itself speaks plain HTTP on the internal container network.
 *
 * @since 1.0
 */
public interface EdgeSiteServer {

    /**
     * A handler for capability-specific HTTP requests routed from the API layer.
     *
     * <p>The handler receives the parsed capability type and a request context,
     * and is responsible for invoking the capability and writing the response.
     *
     * @param <R> the request context type (framework-specific)
     */
    @FunctionalInterface
    interface CapabilityHandler<R> {
        /**
         * Handles a capability invocation request.
         *
         * @param type    the capability being invoked
         * @param context the framework-specific request/response context
         * @throws EdgeSiteException if the invocation fails
         */
        void handle(EdgeSiteCapabilityType type, R context) throws EdgeSiteException;
    }

    /**
     * Starts the HTTP server and begins accepting connections.
     *
     * <p>This method blocks until the server is ready to accept connections.
     * The server binds to {@code 0.0.0.0} on the configured HTTP port.
     *
     * @throws EdgeSiteException with code {@link EdgeSiteException.Code#SERVER_START_FAILED}
     *         if the port is already in use or the server fails to initialise
     */
    void start() throws EdgeSiteException;

    /**
     * Stops the HTTP server gracefully.
     *
     * <p>Waits for in-flight requests to complete up to a configured drain timeout
     * before forcibly closing connections.
     *
     * @throws EdgeSiteException if the server cannot be stopped cleanly
     */
    void stop() throws EdgeSiteException;

    /**
     * Returns {@code true} if the server is currently accepting connections.
     *
     * @return {@code true} when the server is running
     */
    boolean isRunning();

    /**
     * Returns the HTTP port on which the server is (or will be) listening.
     *
     * @return the HTTP listen port
     */
    int getHttpPort();

    /**
     * Returns the HTTPS port configured for direct TLS (if applicable).
     *
     * @return the HTTPS port, or {@code -1} if TLS is not handled by this server
     */
    int getHttpsPort();

    /**
     * Registers a handler for invocations of the given capability type.
     *
     * <p>Must be called before {@link #start()}.  Each capability type may have at
     * most one handler; registering a second handler for the same type replaces the
     * first.
     *
     * @param type    the capability type to handle
     * @param handler the handler implementation
     */
    void registerCapabilityHandler(EdgeSiteCapabilityType type, CapabilityHandler<?> handler);

    /**
     * Registers an error handler that is called when an unhandled exception escapes
     * from a request handler.
     *
     * <p>The handler receives the exception and a string identifying the request path.
     * Useful for structured error logging and alerting.
     *
     * @param handler the error handler
     */
    void registerErrorHandler(BiConsumer<Throwable, String> handler);

    /**
     * Returns the base URL at which the server is accessible from the container
     * network.
     *
     * <p>Example: {@code http://edge-site:8080}.  Used by the CDN to configure its
     * upstream and by the Collibra edge agent to reference the local server.
     *
     * @return the internal base URL of this server
     */
    String getInternalBaseUrl();
}
