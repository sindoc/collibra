#!/usr/bin/env bash
# server.sh — id-gen dev platform startup wrapper
# Starts the Lisp server with SSH public key identity.
# Supports net mode (full API) and DMZ mode (governance-restricted).
#
# Usage:
#   ./server.sh start [--port 7331] [--mode net|dmz] [--ssh-key "ssh-rsa ..."]
#   ./server.sh start --ssh-key-file ~/.ssh/id_rsa.pub
#   ./server.sh stop
#   ./server.sh status

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${SCRIPT_DIR}/../../uniWork/id_gen.log"
PID_FILE="${SCRIPT_DIR}/.server.pid"
SSH_KEY_FILE="${SCRIPT_DIR}/.server.ssh_key"

# ── registered SSH identity (sina@neille.mac.collibra.com) ───────────────────
DEFAULT_SSH_KEY="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDBcqBuMbbDlQTcZe3af41ftbm8dQJ1o5d/W0Wdrgj8ncdeEHA6He9gAuE5JQqbye+WsG2O950CetxwxnbzHvptr8TLAWvKWARv2WuM3r11Ypsgau5TDuQZw7K7wlFZy6xV9mhUnlUbu7/5rDroII1vHYiC2Kgs76qC1oNIgDss0DV0Jnq3TGqtsaTiZM5rpGxEDYtqVdkvNjqZTiIEQxhANqFOLLwsK7HZ15vfCfZ37HKG33fJgdihn/tVuo+XiiUbaMbEB5mQbtkIQAc86SCoYTo6XWGNe569Y3sg2r5zGsucMv3iGGbOuVJK/7A7JN7vflUR1GkDsG/Hsy84Ont9 sina@neille.mac.collibra.com"

DEFAULT_PORT=7331
DEFAULT_MODE="net"

_log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [SERVER] $*" | tee -a "$LOG_FILE"; }

_fingerprint() {
  local key="$1"
  # Try ssh-keygen; fall back to manual extraction
  if echo "$key" > /tmp/_id_gen_key.pub && ssh-keygen -lf /tmp/_id_gen_key.pub 2>/dev/null; then
    rm -f /tmp/_id_gen_key.pub
    return
  fi
  rm -f /tmp/_id_gen_key.pub
  # Fallback: show key type + comment
  echo "$key" | awk '{print $1 " ... " $NF}'
}

_find_lisp() {
  for bin in sbcl ros clisp ecl guile; do
    command -v "$bin" &>/dev/null && echo "$bin" && return
  done
  echo ""
}

# ── start ─────────────────────────────────────────────────────────────────────
start_server() {
  local port="$DEFAULT_PORT"
  local mode="$DEFAULT_MODE"
  local ssh_key="$DEFAULT_SSH_KEY"
  local ssh_key_file=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --port)         port="$2";        shift 2 ;;
      --mode)         mode="$2";        shift 2 ;;
      --ssh-key)      ssh_key="$2";     shift 2 ;;
      --ssh-key-file) ssh_key_file="$2";shift 2 ;;
      *) shift ;;
    esac
  done

  # Read SSH key from file if specified
  [[ -n "$ssh_key_file" && -f "$ssh_key_file" ]] && ssh_key=$(cat "$ssh_key_file")

  # Persist key for status checks
  echo "$ssh_key" > "$SSH_KEY_FILE"

  echo ""
  echo "╔══════════════════════════════════════════════════╗"
  echo "║  id-gen dev platform — starting                  ║"
  echo "╚══════════════════════════════════════════════════╝"
  echo "  SSH identity : $(_fingerprint "$ssh_key")"
  echo "  Port         : ${port}"
  echo "  Mode         : ${mode}"
  echo "  Namespaces   : c.* (Collibra/privileged) | a.* | b.* (reserved)"
  echo ""

  _log "Starting server: port=${port} mode=${mode}"

  local lisp; lisp=$(_find_lisp)

  if [[ -z "$lisp" ]]; then
    _log "No Lisp runtime found. Starting fallback HTTP server (Python)."
    _start_python_fallback "$port" "$mode" "$ssh_key"
    return
  fi

  _log "Using Lisp runtime: ${lisp}"
  echo "$ssh_key" | \
  case "$lisp" in
    sbcl)
      nohup sbcl --script "${SCRIPT_DIR}/start.lisp" -- "$ssh_key" "$port" "$mode" \
        >> "$LOG_FILE" 2>&1 &
      ;;
    clisp)
      nohup clisp "${SCRIPT_DIR}/start.lisp" -- "$ssh_key" "$port" "$mode" \
        >> "$LOG_FILE" 2>&1 &
      ;;
    ecl)
      nohup ecl --load "${SCRIPT_DIR}/start.lisp" -- "$ssh_key" "$port" "$mode" \
        >> "$LOG_FILE" 2>&1 &
      ;;
    *)
      _log "Unsupported Lisp: ${lisp}. Falling back to Python."
      _start_python_fallback "$port" "$mode" "$ssh_key"
      return ;;
  esac

  echo $! > "$PID_FILE"
  _log "Server started (PID $!)"
  echo "Server running. PID: $! — http://localhost:${port}/"
}

# ── Python fallback server ────────────────────────────────────────────────────
_start_python_fallback() {
  local port="$1" mode="$2" ssh_key="$3"
  local fp; fp=$(echo "$ssh_key" | awk '{print $1 "..." $NF}')

  _log "Python fallback HTTP server on port ${port}"

  nohup python3 -c "
import http.server, json, urllib.parse, os, threading

PORT = ${port}
MODE = '${mode}'
SSH_FP = '${fp}'
CONTRACTS = []

ALLOWED_DMZ = {'/health', '/api/id/gen', '/api/contracts/list', '/api/progress'}

def gen_uuid():
    return open('/proc/sys/kernel/random/uuid').read().strip()

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass
    def send_json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type','application/json')
        self.send_header('Access-Control-Allow-Origin','*')
        self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if MODE == 'dmz' and p not in ALLOWED_DMZ:
            return self.send_json(403, {'error': f'DMZ mode: {p} not allowed'})
        if p == '/health':
            self.send_json(200, {'status':'ok','mode':MODE,'port':PORT,'ssh_fp':SSH_FP})
        elif p == '/api/contracts/list':
            self.send_json(200, CONTRACTS)
        elif p == '/api/progress':
            self.send_json(200, {'steps':['INIT','EXTRACT','CLASSIFY','RELATE','CONSTRAIN','VERBALIZE','ALIGN','CONTRACT'],'total':7})
        elif p == '/api/namespaces':
            self.send_json(200, {'c':{'description':'Collibra-privileged'},'a':{'description':'Reserved-A'},'b':{'description':'Reserved-B'}})
        elif p == '/api/identity':
            self.send_json(200, {'ssh_fp':SSH_FP,'mode':MODE})
        else:
            self.send_json(404, {'error':'not found','path':p})
    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        if p == '/api/id/gen':
            uid = gen_uuid()
            cid = f'c.contract.{uid}'
            tag = f'id-gen/{cid}'
            CONTRACTS.append({'id':cid,'tag':tag,'ssh_fp':SSH_FP})
            self.send_json(200, {'id':cid,'tag':tag,'namespace':'c','kind':'contract'})
        else:
            self.send_json(404, {'error':'not found'})
    def do_OPTIONS(self):
        self.send_response(200); self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS')
        self.end_headers()

print(f'[id-gen] Python fallback — port {PORT} mode {MODE} fp {SSH_FP}')
with http.server.HTTPServer(('0.0.0.0', PORT), Handler) as srv:
    srv.serve_forever()
" >> "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  _log "Python fallback running (PID $!)"
  echo "Python fallback running. PID: $! — http://localhost:${port}/"
}

# ── stop ──────────────────────────────────────────────────────────────────────
stop_server() {
  if [[ -f "$PID_FILE" ]]; then
    local pid; pid=$(cat "$PID_FILE")
    kill "$pid" 2>/dev/null && _log "Stopped PID ${pid}" || _log "PID ${pid} already stopped"
    rm -f "$PID_FILE"
  else
    echo "No PID file found. Is the server running?"
  fi
}

# ── status ────────────────────────────────────────────────────────────────────
server_status() {
  local port="$DEFAULT_PORT"
  if [[ -f "$PID_FILE" ]]; then
    local pid; pid=$(cat "$PID_FILE")
    if kill -0 "$pid" 2>/dev/null; then
      echo "RUNNING (PID ${pid})"
      [[ -f "$SSH_KEY_FILE" ]] && echo "SSH: $(cat "$SSH_KEY_FILE" | awk '{print $1 "..." $NF}')"
      curl -sf "http://localhost:${port}/health" 2>/dev/null | python3 -m json.tool 2>/dev/null \
        || curl -sf "http://localhost:${port}/health" 2>/dev/null || echo "(could not reach health endpoint)"
    else
      echo "STOPPED (stale PID file)"
      rm -f "$PID_FILE"
    fi
  else
    echo "NOT RUNNING (no PID file)"
  fi
}

# ── main dispatch ─────────────────────────────────────────────────────────────
cmd="${1:-help}"
shift || true
case "$cmd" in
  start)  start_server "$@" ;;
  stop)   stop_server ;;
  status) server_status ;;
  restart) stop_server; sleep 1; start_server "$@" ;;
  help|*)
    cat <<'EOF'
server.sh — id-gen dev platform server

Commands:
  start [--port N] [--mode net|dmz] [--ssh-key "..."] [--ssh-key-file path]
  stop
  status
  restart [same args as start]

Modes:
  net  — full API (default)
  dmz  — restricted; only: /health /api/id/gen /api/contracts/list /api/progress

Default identity: sina@neille.mac.collibra.com (pre-registered SSH key)

API endpoints:
  GET  /health                — server health + identity
  POST /api/id/gen            — generate c.contract.* ID
  GET  /api/contracts/list    — list generated contracts
  GET  /api/progress          — 7-step workflow metadata
  GET  /api/namespaces        — namespace registry info
  GET  /api/identity          — SSH fingerprint + mode
EOF
    ;;
esac
