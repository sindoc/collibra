#!/bin/bash
# edgeCap/snapshots/generate_snapshot.sh — Back-snap generator
# Captures the current state of all asset files, config, and metrics into a
# timestamped snapshot directory for rollback / lineage audit.

set -euo pipefail

SESSION_ID=""
LOG_FILE="/dev/stderr"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --session) SESSION_ID="$2"; shift 2 ;;
    --log)     LOG_FILE="$2";   shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$SCRIPT_DIR/../.."
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SNAP_DIR="$SCRIPT_DIR/${TIMESTAMP}_${SESSION_ID}"

log() {
  echo "[${TIMESTAMP}] [INFO] [snapshot] $*" | tee -a "$LOG_FILE"
}

log "Generating back-snap: $SNAP_DIR"
mkdir -p "$SNAP_DIR"

# Snapshot all tracked assets and config
cp -r "$AGENT_DIR/assets"  "$SNAP_DIR/assets"
cp -r "$AGENT_DIR/metrics" "$SNAP_DIR/metrics"
cp -r "$AGENT_DIR/lineage" "$SNAP_DIR/lineage"
cp    "$AGENT_DIR/edgeCap/model.json" "$SNAP_DIR/model.json"

# Manifest
MANIFEST="$SNAP_DIR/manifest.json"
cat >"$MANIFEST" <<JSON
{
  "sessionId":   "${SESSION_ID}",
  "timestamp":   "${TIMESTAMP}",
  "snapshotDir": "${SNAP_DIR}",
  "capturedPaths": [
    "assets",
    "metrics",
    "lineage",
    "edgeCap/model.json"
  ],
  "purpose": "back-snap for edge cap investment maturity rollback"
}
JSON

log "Snapshot manifest written: $MANIFEST"
log "Back-snap complete — session $SESSION_ID"
