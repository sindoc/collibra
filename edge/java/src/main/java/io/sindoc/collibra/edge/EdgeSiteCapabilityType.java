package io.sindoc.collibra.edge;

/**
 * The set of capabilities that a Collibra-compatible edge site can host.
 *
 * <p>Each capability type maps to a specific Collibra Edge feature set.  An edge site
 * declares its supported capabilities during the DGC registration handshake.  Collibra
 * DGC then routes capability invocations to the registered site.
 *
 * <p>Capability types align with the Collibra product capability surface as of the
 * 2024.x DGC release series.  Not all capability types require a live DGC connection
 * to function — see {@link #requiresDgcConnection()}.
 *
 * @since 1.0
 */
public enum EdgeSiteCapabilityType {

    /**
     * JDBC data source connectivity.
     *
     * <p>Enables Collibra to reach data sources that are accessible from the edge
     * network but not from the Collibra cloud.  Used for data sampling, row-count
     * profiling, and schema discovery on on-premises databases.
     *
     * <p>Collibra DGC API path prefix: {@code /api/edge/v1/capabilities/connect}
     */
    CONNECT("connect", true, "JDBC data source connectivity for on-premises data sampling"),

    /**
     * Catalog asset synchronisation.
     *
     * <p>Allows the edge site to push asset metadata (tables, columns, data elements)
     * to the central Collibra catalog without requiring the catalog to reach the
     * on-premises network directly.
     *
     * <p>Collibra DGC API path prefix: {@code /api/edge/v1/capabilities/catalog}
     */
    CATALOG("catalog", true, "Asset metadata push to the central Collibra catalog"),

    /**
     * Data lineage collection.
     *
     * <p>Captures technical lineage from on-premises ETL tools, databases, and
     * pipelines and forwards it to the Collibra Lineage Harvester.
     *
     * <p>Collibra DGC API path prefix: {@code /api/edge/v1/capabilities/lineage}
     */
    LINEAGE("lineage", true, "Technical lineage collection from on-premises pipelines"),

    /**
     * Data profiling and classification.
     *
     * <p>Runs profiling jobs against on-premises data sources and sends summary
     * statistics and classification results to the Collibra catalog.  This
     * capability requires an active CONNECT capability as a dependency.
     *
     * <p>Collibra DGC API path prefix: {@code /api/edge/v1/capabilities/profiling}
     */
    PROFILING("profiling", true, "On-premises data profiling and automatic classification"),

    /**
     * Static and dynamic web site hosting.
     *
     * <p>Serves an edge-hosted web application through the CDN layer.  This
     * capability does not require a Collibra DGC connection and remains available
     * even when the site is in {@link EdgeSiteStatus#DISCONNECTED} state.
     *
     * <p>Collibra DGC API path prefix: {@code /api/edge/v1/capabilities/site}
     */
    SITE("site", false, "Edge-hosted web site served through the CDN layer"),

    /**
     * Workflow invocation.
     *
     * <p>Executes Collibra workflow steps that require access to on-premises
     * resources (e.g., sending notifications to an on-premises SMTP relay,
     * triggering on-premises ETL jobs as part of a governance workflow).
     *
     * <p>Collibra DGC API path prefix: {@code /api/edge/v1/capabilities/workflow}
     */
    WORKFLOW("workflow", true, "On-premises workflow step execution triggered by Collibra DGC");

    private final String apiKey;
    private final boolean requiresDgcConnection;
    private final String description;

    EdgeSiteCapabilityType(String apiKey, boolean requiresDgcConnection, String description) {
        this.apiKey = apiKey;
        this.requiresDgcConnection = requiresDgcConnection;
        this.description = description;
    }

    /**
     * Returns the lowercase API key used in Collibra REST path segments.
     * For example, {@link #CONNECT} returns {@code "connect"}, giving the path
     * {@code /api/edge/v1/capabilities/connect}.
     *
     * @return the API path key for this capability type
     */
    public String getApiKey() {
        return apiKey;
    }

    /**
     * Returns {@code true} if this capability requires an active connection to
     * Collibra DGC to function.  Capabilities that return {@code false} (e.g.
     * {@link #SITE}) continue to operate when the site is
     * {@link EdgeSiteStatus#DISCONNECTED}.
     *
     * @return {@code true} if DGC connectivity is a hard dependency
     */
    public boolean requiresDgcConnection() {
        return requiresDgcConnection;
    }

    /**
     * Returns a human-readable description of this capability type.
     *
     * @return capability description
     */
    public String getDescription() {
        return description;
    }

    /**
     * Looks up a capability type by its API key (case-insensitive).
     *
     * @param apiKey the API path key (e.g. {@code "connect"})
     * @return the matching type
     * @throws IllegalArgumentException if no match is found
     */
    public static EdgeSiteCapabilityType fromApiKey(String apiKey) {
        for (EdgeSiteCapabilityType t : values()) {
            if (t.apiKey.equalsIgnoreCase(apiKey)) {
                return t;
            }
        }
        throw new IllegalArgumentException("Unknown edge site capability API key: " + apiKey);
    }
}
