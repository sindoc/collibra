# edge-site/Dockerfile — Collibra-compatible Edge Site server
#
# Implements the Collibra Edge Site REST API:
#   GET  /health
#   GET  /api/edge/v1/status
#   POST /api/edge/v1/register
#   GET  /api/edge/v1/capabilities
#   POST /api/edge/v1/capabilities/{type}/invoke
#
# Also hosts static web content under /site/ (EdgeSiteCapabilityType.SITE).
#
# The edge-site-server.jar must be built from the Java module at:
#   edge/java/  (io.sindoc.collibra.edge)
# and placed at edge-site/edge-site-server.jar before building.
#
# Default port: 8080 (HTTP; TLS is terminated at the CDN)
#
# Required environment variables at runtime:
#   COLLIBRA_EDGE_HOSTNAME    FQDN of this edge node
#   COLLIBRA_DGC_URL          Base URL of the Collibra DGC instance
#   COLLIBRA_EDGE_SITE_ID     Stable site identifier
#   COLLIBRA_EDGE_REG_KEY     Registration key from Collibra DGC admin console

ARG REGISTRY=
ARG BASE_TAG=latest
FROM sindoc-collibra-edge-base:${BASE_TAG}

LABEL org.opencontainers.image.title="sindoc-collibra-edge-site" \
      org.opencontainers.image.description="Collibra Edge Site server — REST API + web content hosting on CentOS 7 LTS" \
      collibra.edge.component="edge-site"

# ── Build arguments ───────────────────────────────────────────────────────────
ARG HTTP_PORT=8080
ARG HTTPS_PORT=8443

# ── Runtime environment ───────────────────────────────────────────────────────
ENV EDGE_SITE_HOME=/opt/edge/site \
    EDGE_SITE_HTTP_PORT=${HTTP_PORT} \
    EDGE_SITE_HTTPS_PORT=${HTTPS_PORT} \
    JAVA_OPTS="-Xms512m -Xmx1g \
               -XX:+UseG1GC \
               -XX:MaxGCPauseMillis=100 \
               -Djava.awt.headless=true \
               -Dfile.encoding=UTF-8"

# ── Directory setup ───────────────────────────────────────────────────────────
USER root
RUN mkdir -p /opt/edge/site/config \
             /opt/edge/site/logs \
             /opt/edge/site/www && \
    chown -R edge:edge /opt/edge/site
USER edge

WORKDIR /opt/edge/site

# ── Application JAR ───────────────────────────────────────────────────────────
# Build the JAR from edge/java/ with:
#   cd edge/java && ./gradlew jar
# then copy the output:
#   cp edge/java/build/libs/edge-site-api-1.0.0.jar \
#      edge/image/edge-site/edge-site-server.jar
COPY --chown=edge:edge edge-site-server.jar /opt/edge/site/edge-site-server.jar

# ── Default web content (index page placeholder) ─────────────────────────────
COPY --chown=edge:edge www/ /opt/edge/site/www/

# ── Entrypoint ────────────────────────────────────────────────────────────────
COPY --chown=edge:edge entrypoint.sh /opt/edge/site/entrypoint.sh
RUN chmod +x /opt/edge/site/entrypoint.sh

EXPOSE ${HTTP_PORT}

HEALTHCHECK --interval=20s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:${EDGE_SITE_HTTP_PORT}/health || exit 1

ENTRYPOINT ["/opt/edge/site/entrypoint.sh"]
