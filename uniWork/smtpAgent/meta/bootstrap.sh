#!/bin/bash
# meta/bootstrap.sh — Singine package-management bootstrap
# Installs: Leiningen (JVM/Clojure), pip packages (Python), builds C binary.
# Safe to re-run; each step is idempotent.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$SCRIPT_DIR/.."
LOG="$ROOT/logs/bootstrap.log"
mkdir -p "$ROOT/logs"

log() { echo "[$(date -u +%Y%m%dT%H%M%SZ)] $*" | tee -a "$LOG"; }

log "=== Singine smtpAgent Bootstrap ==="

# ── 1. Leiningen (Clojure package manager) ────────────────────────────────────
LEIN_BIN="$HOME/.local/bin/lein"
if command -v lein &>/dev/null; then
  log "lein already on PATH: $(command -v lein)"
elif [[ -x "$LEIN_BIN" ]]; then
  log "lein found at $LEIN_BIN"
  export PATH="$HOME/.local/bin:$PATH"
else
  log "Installing Leiningen..."
  mkdir -p "$HOME/.local/bin"
  curl -fsSL https://raw.githubusercontent.com/technomancy/leiningen/stable/bin/lein \
    -o "$LEIN_BIN"
  chmod +x "$LEIN_BIN"
  export PATH="$HOME/.local/bin:$PATH"
  log "Running lein self-install..."
  "$LEIN_BIN" version
fi
log "Leiningen: $(lein version 2>/dev/null || echo 'version check deferred')"

# ── 2. Python pip packages ────────────────────────────────────────────────────
log "Installing Python packages..."
python3 -m pip install --quiet --ignore-installed -r "$ROOT/python/requirements.txt" 2>/dev/null \
  || python3 -m pip install --quiet --ignore-installed --break-system-packages \
       -r "$ROOT/python/requirements.txt"
log "Python packages installed."

# ── 3. Build C TCP acceptor ───────────────────────────────────────────────────
log "Building C TCP acceptor..."
make -C "$ROOT/c" all
log "C binary built: $ROOT/c/bin/accept_tcp"

# ── 4. Clojure dependencies ───────────────────────────────────────────────────
log "Fetching Clojure dependencies (lein deps)..."
(cd "$ROOT/clojure" && lein deps)
log "Clojure dependencies resolved."

log "=== Bootstrap complete. Run 'make -C $ROOT start' to launch all layers. ==="
