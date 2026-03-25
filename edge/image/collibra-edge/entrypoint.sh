#!/bin/sh
# entrypoint.sh — Collibra DGC Edge node container entrypoint
#
# Required environment variables:
#   COLLIBRA_EDGE_HOSTNAME  FQDN of this edge node
#   COLLIBRA_DGC_URL        URL of the central Collibra DGC instance
#
# Optional overrides (all have defaults from the Dockerfile):
#   COLLIBRA_HTTP_PORT      (default 7080)
#   COLLIBRA_HTTPS_PORT     (default 7443)
#   JAVA_OPTS               (default set in Dockerfile)
#   COLLIBRA_EDGE_HOME      (default /opt/edge/collibra)

set -e

EDGE_HOME="${COLLIBRA_EDGE_HOME:-/opt/edge/collibra}"
CONFIG_DIR="${EDGE_HOME}/config"
PROPS_FILE="${CONFIG_DIR}/edge.properties"
TPL_FILE="${CONFIG_DIR}/edge.properties.tpl"
JAR="${EDGE_HOME}/collibra-edge.jar"

# ── Validate required variables ───────────────────────────────────────────────
if [ -z "${COLLIBRA_EDGE_HOSTNAME}" ]; then
  echo "[entrypoint] ERROR: COLLIBRA_EDGE_HOSTNAME is not set" >&2
  exit 1
fi
if [ -z "${COLLIBRA_DGC_URL}" ]; then
  echo "[entrypoint] ERROR: COLLIBRA_DGC_URL is not set" >&2
  exit 1
fi

# ── Render edge.properties from template ─────────────────────────────────────
sed \
  -e "s|{{HOSTNAME}}|${COLLIBRA_EDGE_HOSTNAME}|g" \
  -e "s|{{DGC_URL}}|${COLLIBRA_DGC_URL}|g" \
  -e "s|{{HTTP_PORT}}|${COLLIBRA_HTTP_PORT:-7080}|g" \
  -e "s|{{HTTPS_PORT}}|${COLLIBRA_HTTPS_PORT:-7443}|g" \
  "${TPL_FILE}" > "${PROPS_FILE}"

echo "[entrypoint] edge.properties written to ${PROPS_FILE}"
echo "[entrypoint] hostname=${COLLIBRA_EDGE_HOSTNAME}  dgc=${COLLIBRA_DGC_URL}"

# ── Append runtime JVM flags for Collibra edge ───────────────────────────────
RUNTIME_OPTS="\
  -Dcollibra.edge.hostname=${COLLIBRA_EDGE_HOSTNAME} \
  -Dcollibra.dgc.url=${COLLIBRA_DGC_URL} \
  -Dcollibra.edge.config.dir=${CONFIG_DIR} \
  -Dcollibra.edge.data.dir=${EDGE_HOME}/data \
  -Dcollibra.edge.log.dir=${EDGE_HOME}/logs"

echo "[entrypoint] starting JVM..."
exec "${JAVA_HOME}/bin/java" \
  ${JAVA_OPTS} \
  ${RUNTIME_OPTS} \
  -jar "${JAR}" \
  "$@"
