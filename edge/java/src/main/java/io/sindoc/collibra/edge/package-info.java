/**
 * Collibra Edge Site — Java interface layer.
 *
 * <p>This package defines the contract for a self-contained edge server that is:
 * <ol>
 *   <li><strong>Collibra-compatible</strong> — implements the REST API surface expected by
 *       Collibra Data Intelligence Cloud (CDIC) for Edge Site registration, capability
 *       activation, and health reporting.</li>
 *   <li><strong>Site-hosting capable</strong> — serves static and dynamic web content at the
 *       edge, fronted by the CDN reverse proxy.</li>
 *   <li><strong>Governance-traceable</strong> — every deployed instance carries a Collibra
 *       asset identity ({@code collibraId}) and records lifecycle events in the Singine
 *       domain event log.</li>
 * </ol>
 *
 * <h2>Architecture overview</h2>
 * <pre>
 *   ┌───────────────────────────────────────────────────┐
 *   │  CDN (nginx, TLS termination)                     │
 *   │    :443 → edge-site :8080  (site + Edge Site API) │
 *   │    :443 → collibra-edge :7080  (DGC Edge JAR)     │
 *   └───────────────────────────────────────────────────┘
 *              │                          │
 *   ┌──────────▼──────────┐   ┌───────────▼───────────────┐
 *   │  EdgeSiteServer     │   │  Collibra DGC Edge JAR     │
 *   │  (this module)      │   │  (collibra-edge image)     │
 *   │                     │   │                            │
 *   │  /health            │   │  /rest/2.0/…               │
 *   │  /api/edge/v1/…     │   │  /graphql/…                │
 *   │  /site/…            │   │  port 7080 / 7443          │
 *   └─────────────────────┘   └────────────────────────────┘
 *              │
 *   ┌──────────▼──────────────┐
 *   │  Collibra DGC Cloud     │
 *   │  (registration target)  │
 *   └─────────────────────────┘
 * </pre>
 *
 * <h2>Core interfaces</h2>
 * <ul>
 *   <li>{@link io.sindoc.collibra.edge.EdgeSite} — top-level lifecycle facade</li>
 *   <li>{@link io.sindoc.collibra.edge.EdgeSiteConfig} — immutable configuration</li>
 *   <li>{@link io.sindoc.collibra.edge.EdgeSiteRegistry} — DGC registration/deregistration</li>
 *   <li>{@link io.sindoc.collibra.edge.EdgeSiteServer} — embedded HTTP server</li>
 *   <li>{@link io.sindoc.collibra.edge.EdgeSiteCapability} — a single hosted capability</li>
 *   <li>{@link io.sindoc.collibra.edge.EdgeSiteHealth} — health reporting</li>
 *   <li>{@link io.sindoc.collibra.edge.CollibraEdgeSiteApi} — Collibra REST API contract</li>
 * </ul>
 *
 * <h2>Collibra Edge Site compatibility</h2>
 * <p>The {@link io.sindoc.collibra.edge.CollibraEdgeSiteApi} interface mirrors the REST
 * surface expected by Collibra CDIC when polling or invoking an on-premises edge site:
 * <ul>
 *   <li>{@code GET /health} — liveness probe</li>
 *   <li>{@code GET /api/edge/v1/status} — site registration and capability status</li>
 *   <li>{@code POST /api/edge/v1/register} — initiate DGC registration handshake</li>
 *   <li>{@code GET /api/edge/v1/capabilities} — enumerate active capabilities</li>
 *   <li>{@code POST /api/edge/v1/capabilities/{type}/invoke} — invoke a capability</li>
 * </ul>
 *
 * @since 1.0
 */
package io.sindoc.collibra.edge;
