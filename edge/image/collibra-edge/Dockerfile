# collibra-edge/Dockerfile — Collibra DGC Edge node
#
# Runs the Collibra Data Governance Center edge process.
# The DGC edge JAR is not public; it must be placed at:
#   collibra-edge/collibra-edge.jar
# before building, or provided via a build ARG / mounted volume.
#
# Default ports:
#   7080  HTTP
#   7443  HTTPS

ARG REGISTRY=localhost
ARG BASE_TAG=latest
FROM sindoc-collibra-edge-base:${BASE_TAG}

LABEL org.opencontainers.image.title="sindoc-collibra-edge" \
      org.opencontainers.image.description="Collibra DGC Edge node on CentOS 7 LTS base" \
      collibra.edge.component="dgc-edge"

# ── Build arguments ───────────────────────────────────────────────────────────
ARG COLLIBRA_EDGE_JAR=collibra-edge.jar
ARG HTTP_PORT=7080
ARG HTTPS_PORT=7443
ARG JAVA_HEAP_GB=4

# ── Runtime environment ───────────────────────────────────────────────────────
ENV COLLIBRA_EDGE_HOME=/opt/edge/collibra \
    COLLIBRA_HTTP_PORT=${HTTP_PORT} \
    COLLIBRA_HTTPS_PORT=${HTTPS_PORT} \
    JAVA_OPTS="-Xms${JAVA_HEAP_GB}g -Xmx${JAVA_HEAP_GB}g \
               -XX:+UseG1GC -XX:MaxGCPauseMillis=200 \
               -Djava.awt.headless=true \
               -Dfile.encoding=UTF-8"

# Switch to root for directory setup, then drop back
USER root
RUN mkdir -p /opt/edge/collibra/config \
             /opt/edge/collibra/data \
             /opt/edge/collibra/logs && \
    chown -R edge:edge /opt/edge/collibra
USER edge

WORKDIR /opt/edge/collibra

# ── Application JAR ───────────────────────────────────────────────────────────
# Copy the Collibra edge JAR into the image.
# Obtain from: https://productresources.collibra.com
# Place the downloaded JAR at collibra-edge/collibra-edge.jar before building.
COPY --chown=edge:edge ${COLLIBRA_EDGE_JAR} /opt/edge/collibra/collibra-edge.jar

# ── Edge properties template ──────────────────────────────────────────────────
# Runtime values (hostname, dgc.url) are injected via environment variables
# by the entrypoint script.
COPY --chown=edge:edge edge.properties.tpl /opt/edge/collibra/config/edge.properties.tpl

# ── Entrypoint ────────────────────────────────────────────────────────────────
COPY --chown=edge:edge entrypoint.sh /opt/edge/collibra/entrypoint.sh
RUN chmod +x /opt/edge/collibra/entrypoint.sh

EXPOSE ${HTTP_PORT} ${HTTPS_PORT}

HEALTHCHECK --interval=30s --timeout=15s --start-period=120s --retries=5 \
    CMD curl -sf http://localhost:${COLLIBRA_HTTP_PORT}/rest/2.0/ping || exit 1

ENTRYPOINT ["/opt/edge/collibra/entrypoint.sh"]
