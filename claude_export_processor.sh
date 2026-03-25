#!/usr/bin/env bash
# claude_export_processor.sh
# Process Claude conversation exports → Markdown + s.* validation functions.
#
# s.* prefix = high-quality approved check / result / validation series:
#   s.validate   — SBVR rule validation against Collibra reference
#   s.check      — approval check (rule + resource)
#   s.res        — resolution result record
#   s.log        — structured log entry (levels: INFO WARN ERROR AUDIT)
#   s.ref        — Collibra ID cross-reference lookup
#   s.export     — emit conversation as Logseq markdown page
#   s.env        — dump current env config (LOG_LEVEL, COLLIBRA_BASE_URL, …)
#
# Usage:
#   ./claude_export_processor.sh /path/to/extracted_export_folder [options]
#
# Options:
#   --output-dir DIR          Where to write markdown files (default: ./claude_conversations_md)
#   --log-level LEVEL         DEBUG|INFO|WARN|ERROR (default: INFO)
#   --collibra-url URL        Collibra base URL (default: read from ../uniWork/CollibraBaseUrl)
#   --sbvr-strict             Fail on SBVR rule violations (default: warn only)
#   --logseq                  Emit Logseq-compatible page format
#   --id-gen-dir DIR          Path to id-gen dir for namespace integration
#   --source-functions        Only define s.* functions, do not run (for sourcing)
#
# Example (source to get s.* in your shell):
#   source ./claude_export_processor.sh --source-functions
#   s.log INFO "session started"
#   s.validate "Each DataContract must govern at least one DataAsset."

set -euo pipefail

# ── configuration ─────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ID_GEN_DIR="${ID_GEN_DIR:-${SCRIPT_DIR}/id-gen}"

# Defaults — overridable via env or CLI flags
EXPORT_DIR="${1:-./claude_export}"
OUTPUT_DIR="${CLAUDE_OUTPUT_DIR:-./claude_conversations_md}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"
COLLIBRA_BASE_URL="${COLLIBRA_BASE_URL:-}"
SBVR_STRICT="${SBVR_STRICT:-false}"
LOGSEQ_MODE="${LOGSEQ_MODE:-false}"
SOURCE_ONLY="${SOURCE_ONLY:-false}"

# Load Collibra URL from repo if not set
if [[ -z "$COLLIBRA_BASE_URL" ]] && [[ -f "${SCRIPT_DIR}/uniWork/CollibraBaseUrl" ]]; then
  COLLIBRA_BASE_URL=$(head -1 "${SCRIPT_DIR}/uniWork/CollibraBaseUrl")
fi
COLLIBRA_BASE_URL="${COLLIBRA_BASE_URL:-https://api-vlab.collibra.com}"

# ── log levels ─────────────────────────────────────────────────────────────────
declare -A _LOG_NUMERIC=([DEBUG]=0 [INFO]=1 [WARN]=2 [ERROR]=3 [AUDIT]=4)
_CURRENT_LOG_LEVEL="${_LOG_NUMERIC[$LOG_LEVEL]:-1}"

# ═══════════════════════════════════════════════════════════════════════════════
# s.* FUNCTION LIBRARY — source-safe, idempotent
# ═══════════════════════════════════════════════════════════════════════════════

# ── s.log <LEVEL> <message> [context-json] ─────────────────────────────────────
# Structured log entry. Levels: DEBUG INFO WARN ERROR AUDIT
s.log() {
  local level="${1:-INFO}"
  local msg="${2:-}"
  local ctx="${3:-}"
  local numeric="${_LOG_NUMERIC[$level]:-1}"
  [[ $numeric -lt $_CURRENT_LOG_LEVEL ]] && return 0

  local ts; ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  local color=""
  case "$level" in
    DEBUG) color="\033[0;37m" ;;
    INFO)  color="\033[0;32m" ;;
    WARN)  color="\033[0;33m" ;;
    ERROR) color="\033[0;31m" ;;
    AUDIT) color="\033[0;35m" ;;
  esac
  local reset="\033[0m"

  # Structured JSON to stderr
  printf "${color}[%s] [%-5s] %s${reset}\n" "$ts" "$level" "$msg" >&2

  # Append structured JSON log
  local log_file="${SCRIPT_DIR}/uniWork/id_gen.log"
  printf '{"ts":"%s","level":"%s","msg":"%s","ctx":%s}\n' \
    "$ts" "$level" "${msg//\"/\\\"}" "${ctx:-null}" >> "$log_file" 2>/dev/null || true
}

# ── s.env ─────────────────────────────────────────────────────────────────────
# Dump current environment configuration (XML layout-compatible)
s.env() {
  python3 -c "
import json, os
env = {
  'LOG_LEVEL':          os.environ.get('LOG_LEVEL','INFO'),
  'COLLIBRA_BASE_URL':  '${COLLIBRA_BASE_URL}',
  'SBVR_STRICT':        '${SBVR_STRICT}',
  'LOGSEQ_MODE':        '${LOGSEQ_MODE}',
  'ID_GEN_DIR':         '${ID_GEN_DIR}',
  'OUTPUT_DIR':         '${OUTPUT_DIR}',
  'SCRIPT_DIR':         '${SCRIPT_DIR}',
}
print(json.dumps(env, indent=2))
" 2>/dev/null || {
    echo "LOG_LEVEL=${LOG_LEVEL}"
    echo "COLLIBRA_BASE_URL=${COLLIBRA_BASE_URL}"
    echo "ID_GEN_DIR=${ID_GEN_DIR}"
  }
}

# ── s.ref <id-or-label> ───────────────────────────────────────────────────────
# Look up a c.*/a.*/b.* ID or label in the namespace registry.
# Returns JSON: {id, ns, kind, label, ts} or {error}
s.ref() {
  local query="${1:?id or label required}"
  local reg_c="${ID_GEN_DIR}/namespaces/c.registry"
  local reg_a="${ID_GEN_DIR}/namespaces/a.registry"
  local reg_b="${ID_GEN_DIR}/namespaces/b.registry"

  # Search all registries — format: ts|id|label[|source]
  local hit
  hit=$(grep -h "$query" "$reg_c" "$reg_a" "$reg_b" 2>/dev/null | head -1 || true)

  if [[ -z "$hit" ]]; then
    echo '{"error":"not found","query":"'"$query"'"}'
    s.log WARN "s.ref: $query not found in namespace registry"
    return 1
  fi

  python3 -c "
line = '''$hit'''.strip()
parts = line.split('|')
ts    = parts[0] if len(parts) > 0 else ''
id_   = parts[1] if len(parts) > 1 else ''
label = parts[2] if len(parts) > 2 else ''
src   = parts[3] if len(parts) > 3 else 'generated'
ns    = id_.split('.')[0] if '.' in id_ else '?'
kind  = id_.split('.')[1] if id_.count('.') >= 2 else '?'
import json
print(json.dumps({'id': id_, 'ns': ns, 'kind': kind, 'label': label, 'ts': ts, 'source': src}))
" 2>/dev/null || echo '{"raw":"'"$hit"'"}'
}

# ── s.validate <sbvr-rule-text> [contract-id] ────────────────────────────────
# Validate a SBVR rule against the Collibra governance model.
# Returns: PASS | WARN | FAIL  with JSON detail.
s.validate() {
  local rule="${1:?SBVR rule text required}"
  local contract_id="${2:-}"
  local ts; ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  s.log INFO "s.validate: checking rule: ${rule:0:80}…"

  python3 -c "
import re, json, sys

rule = '''$rule'''
result = {'ts': '$ts', 'rule': rule, 'contract_id': '$contract_id', 'checks': []}

# ── structural checks (SBVR vocabulary) ───────────────────────────────────────
checks = [
    ('necessity_or_permission', bool(re.search(r'\b(necessary|permitted|impossible|obligatory|forbidden)\b', rule, re.I)),
     'Rule must express necessity, permission, or impossibility'),
    ('has_concept',      bool(re.search(r'\b[A-Z][a-zA-Z]+\b', rule)),
     'Rule must reference at least one Concept (capitalised noun)'),
    ('has_verb_phrase',  bool(re.search(r'\b(is|has|governs|maps|applies|generates|contains|belongs|references|identifies)\b', rule, re.I)),
     'Rule must contain a verb phrase (ORM fact type)'),
    ('c_id_ref',         bool(re.search(r'\bc\.(contract|topic|case|fact|rule)\b', rule)) or '$contract_id'.startswith('c.'),
     'Rule should reference or be scoped to a c.* ID (Collibra-privileged)'),
    ('no_contradiction', not bool(re.search(r'must.{0,30}must not|is.{0,20}is not', rule, re.I)),
     'Rule must not be self-contradicting'),
]

passed = 0
for name, ok, desc in checks:
    status = 'PASS' if ok else 'WARN'
    result['checks'].append({'check': name, 'status': status, 'desc': desc})
    if ok: passed += 1

pct = round(passed / len(checks) * 100)
result['passed'] = passed
result['total']  = len(checks)
result['score']  = pct
result['verdict'] = 'PASS' if pct == 100 else 'WARN' if pct >= 60 else 'FAIL'

print(json.dumps(result, indent=2))
sys.exit(0 if result['verdict'] != 'FAIL' else 1)
" 2>/dev/null || {
    echo '{"verdict":"ERROR","rule":"'"${rule:0:60}"'...","error":"python3 not available"}'
    return 1
  }

  local verdict; verdict=$(s.validate "$rule" "$contract_id" 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('verdict','?'))" 2>/dev/null || echo "?")
  [[ "$SBVR_STRICT" == "true" && "$verdict" == "FAIL" ]] && {
    s.log ERROR "s.validate: FAIL — SBVR strict mode active"
    return 1
  }
}

# ── s.check <rule-id-or-text> <resource-c-id> ────────────────────────────────
# Approval check: verify a rule is approved and the resource has a c.* ID.
# Used before granting production access.
s.check() {
  local rule="${1:?rule or rule-id required}"
  local resource="${2:?resource c.* ID required}"
  local ts; ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  # Resource must be in c.* namespace
  if ! echo "$resource" | grep -qE '^c\.'; then
    s.log ERROR "s.check: resource '$resource' is not in c.* namespace — access denied"
    echo '{"verdict":"DENY","reason":"resource not in c.* namespace","resource":"'"$resource"'"}'
    return 1
  fi

  # Rule must be resolvable
  local rule_lookup
  rule_lookup=$(s.ref "$rule" 2>/dev/null || echo '{"error":"not found"}')
  local rule_ok; rule_ok=$(echo "$rule_lookup" | python3 -c "import json,sys; d=json.load(sys.stdin); print('true' if 'id' in d else 'false')" 2>/dev/null || echo "false")

  python3 -c "
import json
result = {
  'ts':         '$ts',
  'rule':       '$rule',
  'resource':   '$resource',
  'rule_found': $rule_ok,
  'ns_check':   'PASS',
  'verdict':    'APPROVE' if $rule_ok else 'WARN',
  'note':       'Rule found in registry; c.* namespace verified.' if $rule_ok else
                'Rule not in registry — requires manual approval before production.',
}
print(json.dumps(result, indent=2))
"
  s.log AUDIT "s.check: resource=${resource} rule=${rule} rule_found=${rule_ok}"
}

# ── s.res <code> <message> [json-detail] ──────────────────────────────────────
# Record a resolution result (for policy execution log, approval chains, etc.)
s.res() {
  local code="${1:?result code required}"   # PASS|FAIL|WARN|APPROVE|DENY
  local msg="${2:?message required}"
  local detail="${3:-null}"
  local ts; ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  python3 -c "
import json
r = {'ts':'$ts','code':'$code','msg':'${msg//\'/\\\'}','detail':$detail}
print(json.dumps(r, indent=2))
" 2>/dev/null || echo "{\"ts\":\"$ts\",\"code\":\"$code\",\"msg\":\"$msg\"}"

  s.log "${code//PASS/INFO}" "$msg" "$detail"
}

# ── s.export <conversation-json-string> <output-file> ────────────────────────
# Convert a single Claude conversation JSON object → Logseq markdown page.
s.export() {
  local conv_json="${1:?conversation JSON required}"
  local out_file="${2:?output file required}"
  local ts; ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  python3 -c "
import json, sys, re, os

conv_raw = '''$conv_json'''
try:
    conv = json.loads(conv_raw)
except:
    conv = {}

title   = conv.get('title', conv.get('name', 'untitled'))
cid     = conv.get('uuid', conv.get('id', ''))
created = conv.get('created_at', conv.get('created', '$ts'))
msgs    = conv.get('chat_messages', conv.get('messages', []))

safe = re.sub(r'[^a-zA-Z0-9_\-]', '_', title)[:80]
lines = []

# ── Logseq front matter ────────────────────────────────────────────────────────
if '${LOGSEQ_MODE}' == 'true':
    lines += [
        f'title:: {title}',
        f'claude-conversation-id:: {cid}',
        f'created:: {created}',
        f'tags:: claude-export, conversation',
        '',
    ]
else:
    lines += [
        f'---',
        f'title: \"{title}\"',
        f'claude_id: {cid}',
        f'created: {created}',
        f'tags: [claude-export, conversation]',
        f'---',
        '',
    ]

lines.append(f'# {title}')
lines.append('')

# ── messages ──────────────────────────────────────────────────────────────────
for m in msgs:
    role    = m.get('role', m.get('sender', '?'))
    content = m.get('content', m.get('text', ''))

    # content may be a list (multi-part) or a string
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict):
                parts.append(p.get('text', p.get('content', '')))
            else:
                parts.append(str(p))
        content = '\n'.join(parts)
    content = str(content).strip()

    if role in ('user', 'human'):
        lines.append(f'**Human:** {content}')
    elif role in ('assistant', 'claude'):
        lines.append(f'')
        lines.append(f'**Assistant:** {content}')
    else:
        lines.append(f'**[{role}]:** {content}')
    lines.append('')

out = '\n'.join(lines)
with open('$out_file', 'w') as f:
    f.write(out)
print(f'EXPORTED: $out_file ({len(msgs)} messages)')
" 2>/dev/null || {
    s.log ERROR "s.export: failed to process conversation"
    return 1
  }
  s.log INFO "s.export → $out_file"
}

# ── s.mint-from-conv <conversation-id> <topic-label> ─────────────────────────
# Generate a c.contract.* ID tied to a Claude conversation.
# Useful for linking conversations to data contracts in Collibra.
s.mint-from-conv() {
  local conv_id="${1:?conversation UUID required}"
  local label="${2:-from-claude-export}"

  if [[ -x "${ID_GEN_DIR}/namespaces.sh" ]]; then
    local id
    id=$(source "${ID_GEN_DIR}/namespaces.sh" && NS_collibra_import "$conv_id" "conv" "$label")
    s.log INFO "s.mint-from-conv: $id"
    echo "$id"
  else
    # Fallback: format as c.conv.* without registry
    local id="c.conv.${conv_id}"
    s.log WARN "s.mint-from-conv: id-gen not found — using unregistered ID: $id"
    echo "$id"
  fi
}

# ── s.series <function> [args...] ────────────────────────────────────────────
# Meta-function: list or invoke any s.* function by name.
s.series() {
  local cmd="${1:-list}"
  shift || true
  case "$cmd" in
    list)
      echo "=== s.* function series ==="
      declare -F | awk '{print $3}' | grep '^s\.' | sort | while read -r fn; do
        echo "  $fn"
      done
      ;;
    *)
      if declare -f "s.${cmd}" &>/dev/null; then
        "s.${cmd}" "$@"
      else
        s.log ERROR "s.series: unknown function s.${cmd}"
        return 1
      fi
      ;;
  esac
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN — process Claude export (skip if sourced)
# ═══════════════════════════════════════════════════════════════════════════════

# Parse remaining CLI flags
_parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --output-dir)     OUTPUT_DIR="$2";        shift 2 ;;
      --log-level)      LOG_LEVEL="$2";         shift 2 ;;
      --collibra-url)   COLLIBRA_BASE_URL="$2"; shift 2 ;;
      --sbvr-strict)    SBVR_STRICT="true";     shift ;;
      --logseq)         LOGSEQ_MODE="true";     shift ;;
      --id-gen-dir)     ID_GEN_DIR="$2";        shift 2 ;;
      --source-functions) SOURCE_ONLY="true";   shift ;;
      -*)               s.log WARN "Unknown flag: $1"; shift ;;
      *)                shift ;;
    esac
  done
}

_main() {
  _parse_args "${@:-}"

  [[ "$SOURCE_ONLY" == "true" ]] && return 0

  mkdir -p "$OUTPUT_DIR"
  s.log INFO "Claude export processor starting"
  s.log INFO "Export dir : $EXPORT_DIR"
  s.log INFO "Output dir : $OUTPUT_DIR"
  s.log INFO "Collibra   : $COLLIBRA_BASE_URL"
  s.env >&2

  # Find the main JSON export file
  local MAIN_JSON
  MAIN_JSON=$(find "$EXPORT_DIR" -maxdepth 3 -name "*.json" -not -name ".*" 2>/dev/null \
    | head -1 || true)

  if [[ -z "$MAIN_JSON" ]]; then
    s.log ERROR "No JSON file found in $EXPORT_DIR"
    s.res FAIL "No export JSON found" '{"dir":"'"$EXPORT_DIR"'"}'
    exit 1
  fi

  s.log INFO "Processing: $MAIN_JSON"

  # Detect export shape and extract conversations
  local count=0
  python3 - <<PYEOF
import json, sys, subprocess, os

with open('$MAIN_JSON') as f:
    raw = json.load(f)

# Support multiple export shapes:
# 1. Array of conversations at root
# 2. {"conversations": [...]}
# 3. Single conversation object
if isinstance(raw, list):
    convs = raw
elif isinstance(raw, dict) and 'conversations' in raw:
    convs = raw['conversations']
elif isinstance(raw, dict) and ('uuid' in raw or 'id' in raw):
    convs = [raw]
else:
    # Try to find any list value
    convs = next((v for v in raw.values() if isinstance(v, list)), [raw])

print(f'Found {len(convs)} conversation(s)', file=sys.stderr)

outdir = '$OUTPUT_DIR'
logseq = '${LOGSEQ_MODE}' == 'true'
exported = 0

for conv in convs:
    if not isinstance(conv, dict):
        continue
    title   = conv.get('title', conv.get('name', 'untitled'))
    cid     = conv.get('uuid', conv.get('id', ''))
    created = conv.get('created_at', conv.get('created', ''))
    msgs    = conv.get('chat_messages', conv.get('messages', []))

    import re
    safe = re.sub(r'[^a-zA-Z0-9_\-]', '_', title)[:80]
    out_path = os.path.join(outdir, f'{safe}.md')

    lines = []
    if logseq:
        lines += [
            f'title:: {title}',
            f'claude-conversation-id:: {cid}',
            f'created:: {created}',
            f'tags:: claude-export, conversation',
            '',
        ]
    else:
        lines += [
            '---',
            f'title: "{title}"',
            f'claude_id: {cid}',
            f'created: {created}',
            'tags: [claude-export, conversation]',
            '---',
            '',
        ]

    lines.append(f'# {title}')
    lines.append('')

    for m in msgs:
        role    = m.get('role', m.get('sender', '?'))
        content = m.get('content', m.get('text', ''))
        if isinstance(content, list):
            parts = []
            for p in content:
                if isinstance(p, dict):
                    parts.append(p.get('text', p.get('content', '')))
                else:
                    parts.append(str(p))
            content = '\n'.join(parts)
        content = str(content).strip()

        if role in ('user', 'human'):
            lines.append(f'**Human:** {content}')
        elif role in ('assistant', 'claude'):
            lines.append('')
            lines.append(f'**Assistant:** {content}')
        else:
            lines.append(f'**[{role}]:** {content}')
        lines.append('')

    # Append s.* SBVR annotations block if conversation references contracts
    lines += [
        '',
        '---',
        '## s.* Annotations',
        '',
        '| Key | Value |',
        '|-----|-------|',
        f'| `s.ref` | `c.conv.{cid}` |',
        f'| `s.validate` | See [[SBVR Rules]] |',
        f'| `s.log level` | INFO |',
        f'| Collibra URL | {repr("$COLLIBRA_BASE_URL")} |',
        '',
    ]

    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))

    print(f'  EXPORTED: {out_path} ({len(msgs)} messages)')
    exported += 1

print(f'Done: {exported}/{len(convs)} conversations exported', file=sys.stderr)
sys.exit(0)
PYEOF

  s.log INFO "Export complete → $OUTPUT_DIR"
  s.log AUDIT "s.export run completed"
}

# ─── entry point ─────────────────────────────────────────────────────────────
# If sourced: define functions only.
# If executed: run main.
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
  # Being sourced — just expose s.* functions
  s.log DEBUG "claude_export_processor sourced — s.* functions available"
else
  _main "${@:-}"
fi
