#!/usr/bin/env bash
# setup.sh — fully automated edge stack setup and launch
#
# Runs all prerequisites, builds all images, and starts the stack.
# Safe to re-run: steps are skipped if already done.
#
# Usage:
#   bash scripts/setup.sh [--dev] [--no-start]
#
#   --dev       Use mock DGC edge instead of real collibra-edge.jar (default when
#               collibra-edge.jar is absent)
#   --no-start  Build and prepare everything but do not start the stack
#   --tag TAG   Docker image tag  (default: local)

set -euo pipefail

EDGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERTS_DIR="${EDGE_DIR}/certs"
ENV_FILE="${EDGE_DIR}/.env"
SERVER_DIR="${EDGE_DIR}/image/edge-site/server"
EDGE_JAR="${EDGE_DIR}/image/collibra-edge/collibra-edge.jar"

TAG="local"
DEV_MODE=""
NO_START=""

# ── Parse arguments ───────────────────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --dev)      DEV_MODE=1 ;;
    --no-start) NO_START=1 ;;
    --tag)      shift; TAG="$1" ;;
    --tag=*)    TAG="${arg#--tag=}" ;;
  esac
done

# Force dev mode when collibra-edge.jar is absent
if [ ! -f "${EDGE_JAR}" ]; then
  echo "[setup] collibra-edge.jar not found — enabling --dev mode (mock DGC edge)"
  DEV_MODE=1
fi

# ── Colour helpers ────────────────────────────────────────────────────────────
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
blue()  { printf '\033[0;34m%s\033[0m\n' "$*"; }
red()   { printf '\033[0;31m%s\033[0m\n' "$*"; exit 1; }
step()  { blue ""; blue "▶ $*"; }

# ── 1. Prerequisites ──────────────────────────────────────────────────────────
step "Checking prerequisites"

for cmd in docker java openssl; do
  command -v "$cmd" >/dev/null 2>&1 || red "Required tool not found: $cmd"
done

docker info >/dev/null 2>&1 || red "Docker daemon is not running"
green "  docker    $(docker --version | head -1)"
green "  java      $(java -version 2>&1 | head -1)"
green "  openssl   $(openssl version)"

# Detect arm64 → use linux/amd64 for CentOS 7 images
ARCH="$(uname -m)"
if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then
  export DOCKER_DEFAULT_PLATFORM="linux/amd64"
  green "  platform  arm64 detected → DOCKER_DEFAULT_PLATFORM=linux/amd64"
fi

# ── 2. Generate self-signed TLS certificate ───────────────────────────────────
step "TLS certificate"

mkdir -p "${CERTS_DIR}"
if [ -f "${CERTS_DIR}/server.crt" ] && [ -f "${CERTS_DIR}/server.key" ]; then
  green "  already exists — skipping"
else
  openssl req -x509 -nodes -days 3650 \
    -newkey rsa:2048 \
    -keyout "${CERTS_DIR}/server.key" \
    -out    "${CERTS_DIR}/server.crt" \
    -subj   "/C=BE/ST=Brussels/L=Brussels/O=sindoc/OU=edge/CN=edge.local" \
    -addext "subjectAltName=DNS:localhost,DNS:edge.local,IP:127.0.0.1" \
    2>/dev/null
  green "  generated (10-year self-signed): ${CERTS_DIR}/server.crt"
fi

# ── 3. Create .env ────────────────────────────────────────────────────────────
step ".env"

if [ -f "${ENV_FILE}" ]; then
  green "  already exists — skipping (delete to regenerate)"
else
  cat > "${ENV_FILE}" <<'EOF'
COLLIBRA_EDGE_HOSTNAME=edge.local
COLLIBRA_DGC_URL=http://collibra-edge:7080
COLLIBRA_EDGE_SITE_ID=edge-site-local
COLLIBRA_EDGE_SITE_NAME=Local Edge Site
COLLIBRA_EDGE_REG_KEY=dev-placeholder-key
EDGE_SITE_CAPABILITIES=site,connect,catalog
EOF
  green "  created: ${ENV_FILE}"
fi

# ── 4. Build edge-site-server.jar ─────────────────────────────────────────────
step "edge-site-server.jar"

JAR_DEST="${EDGE_DIR}/image/edge-site/edge-site-server.jar"
if [ -f "${JAR_DEST}" ]; then
  green "  already exists — skipping (delete to rebuild)"
else
  make -C "${SERVER_DIR}" install
  green "  built: ${JAR_DEST}"
fi

# ── 5. Build Docker images ────────────────────────────────────────────────────
step "Building Docker images (tag=${TAG})"

if [ -n "$DEV_MODE" ]; then
  echo "[setup] Building: base, edge-site (mock), cdn, collibra-edge-mock"
  docker build --platform linux/amd64 -t sindoc-collibra-edge-base:"${TAG}" "${EDGE_DIR}/image/base"
  docker build \
    --platform linux/amd64 \
    --build-arg REGISTRY="" --build-arg BASE_TAG="${TAG}" \
    -t sindoc-collibra-edge-site:"${TAG}" "${EDGE_DIR}/image/edge-site"
  docker build -t sindoc-collibra-edge-mock:"${TAG}" "${EDGE_DIR}/image/collibra-edge-mock"
  docker build \
    --platform linux/amd64 \
    --build-arg REGISTRY="" --build-arg BASE_TAG="${TAG}" \
    -t sindoc-collibra-cdn:"${TAG}" "${EDGE_DIR}/image/cdn"
else
  echo "[setup] Building all images including real collibra-edge"
  make -C "${EDGE_DIR}" build TAG="${TAG}"
fi

green "  images built"

# ── 6. Compose file selection ─────────────────────────────────────────────────
if [ -n "$DEV_MODE" ]; then
  COMPOSE_FILE="${EDGE_DIR}/docker-compose.dev.yml"
else
  COMPOSE_FILE="${EDGE_DIR}/docker-compose.yml"
fi

# ── 7. Start the stack ────────────────────────────────────────────────────────
if [ -n "$NO_START" ]; then
  step "Skipping stack start (--no-start)"
  green "Run manually with: docker compose -f ${COMPOSE_FILE} up -d"
  exit 0
fi

step "Starting the stack"
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d
green "  stack started"

# ── 8. Wait for health ────────────────────────────────────────────────────────
step "Waiting for services to become healthy"
TIMEOUT=90
ELAPSED=0
while true; do
  UNHEALTHY=$(docker compose -f "${COMPOSE_FILE}" ps --format json 2>/dev/null \
    | python3 -c "
import sys,json
lines=[l for l in sys.stdin.read().splitlines() if l.strip()]
svcs=[]
for l in lines:
    try: svcs.append(json.loads(l))
    except: pass
# support both single object and array per compose version
flat=[]
for s in svcs:
    if isinstance(s,list): flat.extend(s)
    else: flat.append(s)
not_ready=[s.get('Service',s.get('Name','?')) for s in flat
           if s.get('Health','') not in ('healthy','') and s.get('State','') not in ('running','')]
print(len(not_ready))
" 2>/dev/null || echo "0")
  if [ "${UNHEALTHY}" = "0" ]; then
    break
  fi
  if [ "${ELAPSED}" -ge "${TIMEOUT}" ]; then
    echo "[setup] WARNING: some services may not be healthy yet (timeout ${TIMEOUT}s)"
    break
  fi
  printf "."
  sleep 3
  ELAPSED=$((ELAPSED + 3))
done
echo ""

# ── 9. Summary ────────────────────────────────────────────────────────────────
step "Edge stack is up"
echo ""
echo "  HTTPS  → https://localhost/"
echo "         → https://localhost/site/"
echo "         → https://localhost/health"
echo "         → https://localhost/api/edge/v1/status"
echo "         → https://localhost/api/edge/v1/capabilities"
echo ""
echo "  Mode   : $([ -n "$DEV_MODE" ] && echo 'dev (mock DGC)' || echo 'production')"
echo "  Tag    : ${TAG}"
echo ""
echo "  Useful commands:"
echo "    singine edge status"
echo "    singine edge logs --follow"
echo "    singine edge down"
echo ""
echo "  Curl examples:"
echo "    curl -sk https://localhost/health | python3 -m json.tool"
echo "    curl -sk https://localhost/api/edge/v1/status | python3 -m json.tool"
echo ""
if [ -n "$DEV_MODE" ]; then
  echo "  NOTE: Running with mock DGC edge."
  echo "  To use real Collibra edge, place collibra-edge.jar and re-run without --dev."
fi
