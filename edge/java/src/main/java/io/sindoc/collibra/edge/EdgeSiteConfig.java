package io.sindoc.collibra.edge;

import java.util.Optional;
import java.util.Set;

/**
 * Immutable configuration for a Collibra Edge Site instance.
 *
 * <p>Implementations are expected to be thread-safe value objects.  All configuration
 * is fixed at construction time; a site must be shut down and restarted to apply
 * configuration changes.
 *
 * <h2>Minimum required configuration</h2>
 * <ul>
 *   <li>{@link #getSiteId()} — stable identity, persisted across restarts</li>
 *   <li>{@link #getDgcUrl()} — base URL of the Collibra DGC instance</li>
 *   <li>{@link #getRegistrationKey()} — issued by Collibra DGC during site setup</li>
 * </ul>
 *
 * <h2>Environment variable mapping</h2>
 * <pre>
 *   COLLIBRA_EDGE_HOSTNAME    → {@link #getHostname()}
 *   COLLIBRA_DGC_URL          → {@link #getDgcUrl()}
 *   COLLIBRA_EDGE_SITE_ID     → {@link #getSiteId()}
 *   COLLIBRA_EDGE_REG_KEY     → {@link #getRegistrationKey()}
 *   COLLIBRA_EDGE_HTTP_PORT   → {@link #getHttpPort()}
 *   COLLIBRA_EDGE_HTTPS_PORT  → {@link #getHttpsPort()}
 * </pre>
 *
 * @since 1.0
 */
public interface EdgeSiteConfig {

    /**
     * The stable, unique identifier of this edge site.
     *
     * <p>This value is used as the primary key in Collibra DGC and in the Singine
     * domain event log.  It must remain constant across container restarts.
     * Recommended format: a lowercase slug, e.g. {@code "edge-site-brussels-01"}.
     *
     * @return the stable site identifier
     */
    String getSiteId();

    /**
     * A human-readable display name for this edge site.
     *
     * <p>Shown in the Collibra DGC administration console and in status output.
     *
     * @return the display name
     */
    String getSiteName();

    /**
     * The fully qualified domain name of this edge node.
     *
     * <p>Used in Collibra DGC registration and in the CDN virtual host configuration.
     * Must be reachable from the Collibra DGC instance if DGC-initiated invocations
     * are required.
     *
     * @return the FQDN of this edge node
     */
    String getHostname();

    /**
     * The HTTP port on which the edge site server listens.
     *
     * <p>Default: {@code 8080}.  The CDN proxy forwards external HTTPS to this port.
     *
     * @return the HTTP listen port
     */
    int getHttpPort();

    /**
     * The HTTPS port on which the edge site server listens, when TLS is terminated
     * at the edge site itself rather than at the CDN.
     *
     * <p>Default: {@code 8443}.  When the CDN handles TLS termination (the standard
     * deployment), this port is not exposed externally.
     *
     * @return the HTTPS listen port
     */
    int getHttpsPort();

    /**
     * The base URL of the central Collibra Data Intelligence Cloud (DGC) instance.
     *
     * <p>Example: {@code https://myorg.collibra.com}.  Used for registration,
     * heartbeat, and capability result reporting.
     *
     * @return the DGC base URL, without trailing slash
     */
    String getDgcUrl();

    /**
     * The registration key issued by Collibra DGC for this edge site.
     *
     * <p>Obtained from the Collibra DGC administration console under
     * <em>Settings → Edge → Sites → Add Site</em>.  Treated as a secret —
     * never log or expose this value.
     *
     * @return the DGC-issued registration key
     */
    String getRegistrationKey();

    /**
     * The set of capabilities that this edge site should activate on startup.
     *
     * <p>Only declared capabilities are registered with Collibra DGC.  Capabilities
     * not in this set are ignored even if an implementation is present on the classpath.
     *
     * @return an immutable set of enabled capability types
     */
    Set<EdgeSiteCapabilityType> getEnabledCapabilities();

    /**
     * The Collibra asset ID for this edge site in the Collibra catalog.
     *
     * <p>Populated once the site has been registered and its catalog entry created.
     * Empty until first successful registration.
     *
     * @return an {@link Optional} containing the Collibra asset UUID, or empty
     */
    Optional<String> getCollibraId();

    /**
     * The path on disk where static web site content is served from.
     *
     * <p>Used only when the {@link EdgeSiteCapabilityType#SITE} capability is enabled.
     * Content at this path is served by the edge site server under the {@code /site/}
     * path prefix.
     *
     * <p>Default: {@code /opt/edge/site/www}
     *
     * @return the absolute path to the static web content root
     */
    String getSiteContentRoot();
}
