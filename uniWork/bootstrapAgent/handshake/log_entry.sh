#!/bin/bash
# handshake/log_entry.sh — Structured activity log entry writer
# Appends a JSON lineage record to the session activity log.
# Usage: log_entry.sh --session <id> --phase <phase> --log <file> [--meta <json>]

set -euo pipefail

SESSION_ID=""
PHASE=""
LOG_FILE="/dev/stderr"
META="{}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --session) SESSION_ID="$2"; shift 2 ;;
    --phase)   PHASE="$2";      shift 2 ;;
    --log)     LOG_FILE="$2";   shift 2 ;;
    --meta)    META="$2";       shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OPERATOR="${USER:-unknown}"
HOST="$(hostname)"

ENTRY="$(cat <<JSON
{
  "sessionId":  "${SESSION_ID}",
  "timestamp":  "${TIMESTAMP}",
  "phase":      "${PHASE}",
  "operator":   "${OPERATOR}",
  "host":       "${HOST}",
  "lineage": {
    "source":    "bootstrap-agent",
    "branch":    "claude/bootstrap-agent-edge-cap-2f2SM",
    "repo":      "sindoc/collibra"
  },
  "meta": ${META}
}
JSON
)"

echo "$ENTRY" | tee -a "$LOG_FILE"
