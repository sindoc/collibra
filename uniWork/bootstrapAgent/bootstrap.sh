#!/bin/bash
# bootstrap.sh — Bootstrap agent entry point
# Edge cap model from maturity to back-snap on investments
# Orchestrates: handshake validation → lineage setup → asset creation → metrics baseline

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$SCRIPT_DIR/.."
LOG_DIR="$SCRIPT_DIR/logs"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SESSION_ID="$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid)"

mkdir -p "$LOG_DIR"
ACTIVITY_LOG="$LOG_DIR/activity_${TIMESTAMP}.log"

log() {
  local level="$1"; shift
  echo "[${TIMESTAMP}] [${level}] $*" | tee -a "$ACTIVITY_LOG"
}

log INFO "=== Bootstrap Agent — Edge Cap Maturity Model ==="
log INFO "Session : $SESSION_ID"
log INFO "Operator: ${USER:-unknown}"
log INFO "Host    : $(hostname)"

# ── 1. Handshake validation ────────────────────────────────────────────────────
log INFO "Phase 1: Connection handshake validation"
"$SCRIPT_DIR/handshake/validate.sh" "$SESSION_ID" "$ACTIVITY_LOG"

# ── 2. Lineage registration ────────────────────────────────────────────────────
log INFO "Phase 2: Registering migration lineage"
"$SCRIPT_DIR/handshake/log_entry.sh" \
  --session "$SESSION_ID" \
  --phase   "lineage-registration" \
  --log     "$ACTIVITY_LOG"

# ── 3. Edge cap maturity asset creation ───────────────────────────────────────
log INFO "Phase 3: Creating edge cap investment maturity assets"
(cd "$SCRIPT_DIR" && make createInvestmentMaturityAssets) 2>&1 | tee -a "$ACTIVITY_LOG"

# ── 4. Metrics baseline snapshot ──────────────────────────────────────────────
log INFO "Phase 4: Recording baseline metrics snapshot"
"$SCRIPT_DIR/edgeCap/snapshots/generate_snapshot.sh" \
  --session "$SESSION_ID" \
  --log     "$ACTIVITY_LOG"

log INFO "=== Bootstrap complete — session $SESSION_ID ==="
log INFO "Full activity log: $ACTIVITY_LOG"
