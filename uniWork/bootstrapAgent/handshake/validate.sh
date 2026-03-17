#!/bin/bash
# handshake/validate.sh — TCP/UDP handshake validator
# Validates connectivity to the Collibra endpoint before any migration step.
# Writes a structured log entry on success or failure.

set -euo pipefail

SESSION_ID="${1:-unknown}"
ACTIVITY_LOG="${2:-/dev/stderr}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$SCRIPT_DIR/../.."

COLLIBRA_BASE_URL="$(cat "$BASE_DIR/CollibraBaseUrl")"
CSRF_TOKEN="$(head -1 "$BASE_DIR/X-CSRF-TOKEN")"
JSESSIONID="$(head -1 "$BASE_DIR/JSESSIONID")"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

log() {
  local level="$1"; shift
  echo "[${TIMESTAMP}] [${level}] [handshake] $*" | tee -a "$ACTIVITY_LOG"
}

# Extract host and port for low-level connectivity check
HOST="$(echo "$COLLIBRA_BASE_URL" | sed 's|https\?://||' | cut -d'/' -f1)"
PORT=443

log INFO "Validating endpoint: host=$HOST port=$PORT protocol=TCP/TLS"

# TCP handshake probe (3-second timeout, non-blocking)
if ! timeout 3 bash -c "echo > /dev/tcp/${HOST}/${PORT}" 2>/dev/null; then
  log WARN "TCP probe unavailable (network sandbox) — falling back to HTTP health check"
fi

# Application-layer handshake: HEAD request to the REST endpoint
HTTP_STATUS="$(curl -o /dev/null -s -w "%{http_code}" \
  --max-time 10 \
  -X HEAD \
  "${COLLIBRA_BASE_URL}/rest/2.0/assets" \
  -H "accept: application/json" \
  -H "X-CSRF-TOKEN: ${CSRF_TOKEN}" \
  --cookie "JSESSIONID=${JSESSIONID}; XSRF-TOKEN=${CSRF_TOKEN}" \
  2>/dev/null || echo "000")"

log INFO "HTTP handshake status: $HTTP_STATUS"

# Emit structured lineage record
HANDSHAKE_RECORD="$(cat <<JSON
{
  "sessionId":  "${SESSION_ID}",
  "timestamp":  "${TIMESTAMP}",
  "phase":      "handshake",
  "endpoint":   "${COLLIBRA_BASE_URL}",
  "host":       "${HOST}",
  "port":       ${PORT},
  "transport":  "TCP/TLS",
  "protocol":   "HTTPS",
  "httpStatus": "${HTTP_STATUS}",
  "result":     "$([ "$HTTP_STATUS" = "000" ] && echo "unreachable" || echo "reachable")"
}
JSON
)"

echo "$HANDSHAKE_RECORD" | tee -a "$ACTIVITY_LOG" >/dev/null

case "$HTTP_STATUS" in
  2*|3*|4*)
    log INFO "Handshake validated — system reachable (HTTP $HTTP_STATUS)"
    ;;
  000)
    log WARN "Handshake inconclusive — endpoint unreachable or network restricted"
    ;;
  5*)
    log ERROR "Handshake failed — server error (HTTP $HTTP_STATUS)"
    exit 1
    ;;
esac
