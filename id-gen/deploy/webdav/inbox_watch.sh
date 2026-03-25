#!/usr/bin/env bash
# deploy/webdav/inbox_watch.sh — WebDAV inbox watcher
#
# Architecture:
#   iPad / client  ──WebDAV PUT──►  /inbox/{sparql,contract,conv}/
#                                        │
#                                   inotifywait / poll
#                                        │
#                              process_inbox_file()
#                                        │
#                         ┌─────────────┼──────────────┐
#                      .sparql       .json           .md/.txt
#                    sparql→contract  contract        claude-export
#                         │              │                │
#                      db.sh          db.sh           db.sh
#                         └─────────────┴────────────────┘
#                                   SQLite DB
#
# WebDAV server options (choose one):
#   A) wsgidav (Python):  pip3 install wsgidav cheroot
#   B) Apache mod_dav:    see deploy/webdav/apache.conf
#   C) Caddy with WebDAV: see deploy/webdav/Caddyfile
#   D) rclone serve webdav: rclone serve webdav ./inbox --addr :8080
#
# Usage:
#   ./inbox_watch.sh start [--inbox-dir /path/to/webdav/inbox] [--poll]
#   ./inbox_watch.sh stop
#   ./inbox_watch.sh process <file>   # manually process one file

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_FILE="${SCRIPT_DIR}/uniWork/id_gen.log"
PID_FILE="${SCRIPT_DIR}/deploy/webdav/.inbox_watch.pid"

# Inbox sub-directories (created by WebDAV server or this script)
INBOX_ROOT="${INBOX_DIR:-${SCRIPT_DIR}/deploy/inbox}"
INBOX_SPARQL="${INBOX_ROOT}/sparql"      # .sparql files → contracts
INBOX_CONTRACT="${INBOX_ROOT}/contract"  # .json files → import contracts
INBOX_CONV="${INBOX_ROOT}/conv"          # .json/.md → claude export
INBOX_CERT="${INBOX_ROOT}/certs"         # .pem/.pub → key/cert store
INBOX_DONE="${INBOX_ROOT}/.done"         # processed files archive
INBOX_FAIL="${INBOX_ROOT}/.fail"         # failed files for inspection

POLL_INTERVAL="${POLL_INTERVAL:-5}"  # seconds between polls (fallback)

_log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [INBOX] $*" | tee -a "$LOG_FILE"; }

_init_dirs() {
  mkdir -p "$INBOX_SPARQL" "$INBOX_CONTRACT" "$INBOX_CONV" \
           "$INBOX_CERT" "$INBOX_DONE" "$INBOX_FAIL"
  mkdir -p "${SCRIPT_DIR}/deploy/db"
}

# ── process one inbox file ────────────────────────────────────────────────────
process_inbox_file() {
  local file="${1:?file path required}"
  local ext="${file##*.}"
  local base; base=$(basename "$file")
  local ts; ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  _log "Processing: $base (ext=$ext)"

  local ok=false

  case "$ext" in
    sparql|rq)
      # SPARQL file → generate data contract
      local query; query=$(cat "$file")
      local project; project=$(basename "$file" ".$ext" | tr '_' ' ')
      _log "SPARQL→contract: project='$project'"
      local cid
      cid=$(bash "${SCRIPT_DIR}/id-gen/collibra/sparql_to_contract.sh" \
              translate "$project" "$query" "" 2>>"$LOG_FILE" \
            | grep '^c\.contract\.' | head -1 || true)
      if [[ -n "$cid" ]]; then
        _log "CONTRACT CREATED: $cid"
        # Persist to DB
        bash "${SCRIPT_DIR}/deploy/db/db.sh" insert-contract "$cid" \
          "$project" "DataContract" "DRAFT" "$query" 2>>"$LOG_FILE" || true
        ok=true
      fi
      ;;

    json)
      local kind
      kind=$(python3 -c "import json; d=json.load(open('$file')); print(d.get('kind','?'))" \
             2>/dev/null || echo "?")
      if [[ "$kind" =~ Contract ]]; then
        # Pre-formed contract JSON → import directly
        local cid
        cid=$(python3 -c "import json; print(json.load(open('$file')).get('id',''))" 2>/dev/null || true)
        _log "CONTRACT IMPORT: $cid"
        bash "${SCRIPT_DIR}/deploy/db/db.sh" upsert-from-file "$file" 2>>"$LOG_FILE" || true
        ok=true
      else
        # Assume Claude conversation export
        _log "CONV EXPORT: $base"
        local out_dir="${SCRIPT_DIR}/claude_conversations_md"
        mkdir -p "$out_dir"
        bash "${SCRIPT_DIR}/claude_export_processor.sh" "$INBOX_CONV" \
          --output-dir "$out_dir" --logseq 2>>"$LOG_FILE" || true
        ok=true
      fi
      ;;

    md|txt)
      # Markdown → treat as Logseq page drop; index in DB
      _log "MARKDOWN DROP: $base"
      bash "${SCRIPT_DIR}/deploy/db/db.sh" insert-doc \
        "$(basename "$file")" "$(cat "$file")" 2>>"$LOG_FILE" || true
      ok=true
      ;;

    pem|pub|crt|key)
      # Certificate / public key → cert store
      _log "CERT/KEY: $base"
      local dest="${SCRIPT_DIR}/deploy/db/certs/${base}"
      mkdir -p "${SCRIPT_DIR}/deploy/db/certs"
      cp "$file" "$dest"
      chmod 600 "$dest"
      _log "STORED: $dest"
      ok=true
      ;;

    *)
      _log "UNKNOWN ext=$ext — skipping $base"
      cp "$file" "$INBOX_FAIL/"
      return 0
      ;;
  esac

  if $ok; then
    mv "$file" "${INBOX_DONE}/${ts}_${base}"
    _log "DONE: archived → ${INBOX_DONE}/${ts}_${base}"
  else
    mv "$file" "$INBOX_FAIL/"
    _log "FAIL: moved to $INBOX_FAIL"
  fi
}

# ── poll loop (fallback when inotify not available) ───────────────────────────
_poll_loop() {
  _log "Poll mode: checking every ${POLL_INTERVAL}s"
  while true; do
    for dir in "$INBOX_SPARQL" "$INBOX_CONTRACT" "$INBOX_CONV" "$INBOX_CERT"; do
      while IFS= read -r -d '' f; do
        [[ -f "$f" ]] || continue
        # skip hidden/partial files (WebDAV temp files start with .)
        [[ "$(basename "$f")" == .* ]] && continue
        process_inbox_file "$f"
      done < <(find "$dir" -maxdepth 1 -type f -print0 2>/dev/null)
    done
    sleep "$POLL_INTERVAL"
  done
}

# ── inotify loop (preferred — Linux) ─────────────────────────────────────────
_inotify_loop() {
  _log "inotify mode: watching ${INBOX_ROOT}"
  inotifywait -m -r -e close_write,moved_to \
    "$INBOX_SPARQL" "$INBOX_CONTRACT" "$INBOX_CONV" "$INBOX_CERT" \
    --format '%w%f' 2>/dev/null \
  | while IFS= read -r file; do
      [[ -f "$file" ]] || continue
      [[ "$(basename "$file")" == .* ]] && continue
      process_inbox_file "$file"
    done
}

# ── wsgidav launcher (Python WebDAV server) ───────────────────────────────────
start_webdav_server() {
  local port="${WEBDAV_PORT:-8080}"
  local host="${WEBDAV_HOST:-0.0.0.0}"

  if command -v wsgidav &>/dev/null; then
    _log "Starting wsgidav on ${host}:${port} → root: ${INBOX_ROOT}"
    nohup wsgidav \
      --host="$host" \
      --port="$port" \
      --root="$INBOX_ROOT" \
      --auth=anonymous \
      >> "$LOG_FILE" 2>&1 &
    echo $! > "${SCRIPT_DIR}/deploy/webdav/.wsgidav.pid"
    _log "wsgidav PID $!"
  else
    _log "wsgidav not found — starting rclone WebDAV fallback"
    if command -v rclone &>/dev/null; then
      nohup rclone serve webdav "$INBOX_ROOT" \
        --addr "${host}:${port}" \
        >> "$LOG_FILE" 2>&1 &
      echo $! > "${SCRIPT_DIR}/deploy/webdav/.wsgidav.pid"
      _log "rclone WebDAV PID $!"
    else
      _log "WARNING: No WebDAV server found (install wsgidav or rclone)"
      _log "Inbox watching only — clients must write files directly to: $INBOX_ROOT"
    fi
  fi
}

# ── start ─────────────────────────────────────────────────────────────────────
start_watch() {
  local poll_only="${1:-}"
  _init_dirs

  # Start WebDAV server
  start_webdav_server

  _log "Inbox directories:"
  _log "  sparql   : $INBOX_SPARQL   (drop .sparql/.rq files)"
  _log "  contract : $INBOX_CONTRACT (drop contract .json files)"
  _log "  conv     : $INBOX_CONV     (drop Claude export .json)"
  _log "  certs    : $INBOX_CERT     (drop .pem/.pub/.crt/.key)"

  # Watch for new files
  if [[ "$poll_only" == "--poll" ]] || ! command -v inotifywait &>/dev/null; then
    _poll_loop &
  else
    _inotify_loop &
  fi

  echo $! > "$PID_FILE"
  _log "Watcher started (PID $!)"
  echo "WebDAV inbox watching. PID: $! — Drop files into:"
  echo "  $INBOX_ROOT/{sparql,contract,conv,certs}/"
}

# ── stop ──────────────────────────────────────────────────────────────────────
stop_watch() {
  for f in "$PID_FILE" "${SCRIPT_DIR}/deploy/webdav/.wsgidav.pid"; do
    [[ -f "$f" ]] || continue
    local pid; pid=$(cat "$f")
    kill "$pid" 2>/dev/null && _log "Stopped PID $pid" || true
    rm -f "$f"
  done
}

# ── main ─────────────────────────────────────────────────────────────────────
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  cmd="${1:-help}"; shift || true
  case "$cmd" in
    start)   start_watch "$@" ;;
    stop)    stop_watch ;;
    process) process_inbox_file "$@" ;;
    help|*)
      cat <<'EOF'
inbox_watch.sh — WebDAV inbox watcher

Commands:
  start [--poll]        Start watcher (inotify if available, else poll)
  stop                  Stop watcher + WebDAV server
  process <file>        Manually process one inbox file

Inbox layout (WebDAV root = deploy/inbox/):
  sparql/     .sparql/.rq  → SPARQL→contract pipeline
  contract/   .json        → direct contract import
  conv/       .json        → Claude export processor
  certs/      .pem/.pub    → cert/key store

WebDAV server (auto-detected):
  wsgidav     pip3 install wsgidav cheroot
  rclone      rclone serve webdav ./inbox --addr :8080
  Apache      see deploy/webdav/apache.conf
  Caddy       see deploy/webdav/Caddyfile

Env vars:
  WEBDAV_PORT=8080   WEBDAV_HOST=0.0.0.0
  INBOX_DIR=...      POLL_INTERVAL=5
EOF
    ;;
  esac
fi
