#!/usr/bin/env bash
# workflow_tracker.sh — 7-step workflow progression tracker
# Tracks each step of the Collibra→ORM→SBVR mapping algorithm.
# Outputs progress as percentage for UI bar, JSON, and Logseq log entries.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${SCRIPT_DIR}/../uniWork/id_gen.log"
CONTRACTS_DIR="${SCRIPT_DIR}/contracts/store"
LOGSEQ_LOG_DIR="${SCRIPT_DIR}/ui/logseq/logs"

mkdir -p "$LOGSEQ_LOG_DIR"

_log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG_FILE"; }

# 7-step labels (Collibra metamodel → ORM → SBVR algorithm)
declare -A STEP_LABELS=(
  [0]="INIT: Contract created"
  [1]="EXTRACT: Collibra asset types enumerated"
  [2]="CLASSIFY: Asset types mapped to SBVR Concept Types"
  [3]="RELATE: ORM binary fact types identified"
  [4]="CONSTRAIN: ORM uniqueness + mandatory constraints applied"
  [5]="VERBALIZE: SBVR business rules expressed"
  [6]="ALIGN: Vocabulary cross-references applied (SKOS/DCAT/ODRL/PROV)"
  [7]="CONTRACT: Data contract finalized, IDs tracked, workflow complete"
)

declare -A STEP_STATUS=(
  [0]="DRAFT"
  [1]="DRAFT"
  [2]="DRAFT"
  [3]="DRAFT"
  [4]="PENDING_APPROVAL"
  [5]="PENDING_APPROVAL"
  [6]="PENDING_APPROVAL"
  [7]="APPROVED"
)

# ── progress_percent ──────────────────────────────────────────────────────────
progress_percent() {
  local step="${1:-0}"
  echo $(( step * 100 / 7 ))
}

# ── advance_step ──────────────────────────────────────────────────────────────
advance_step() {
  local contract_id="${1:?contract id required}"
  local target_step="${2:-}"   # if blank, increment by 1
  local file; file=$(find "$CONTRACTS_DIR" -name "${contract_id}.json" 2>/dev/null | head -1)
  [[ -f "$file" ]] || { echo "ERROR: contract $contract_id not found"; return 1; }

  local current_step
  current_step=$(python3 -c "import json; d=json.load(open('$file')); print(d['workflow_step'])" \
    2>/dev/null || grep -o '"workflow_step": [0-9]*' "$file" | grep -o '[0-9]*')

  local next_step
  if [[ -n "$target_step" ]]; then
    next_step="$target_step"
  else
    next_step=$(( current_step + 1 ))
  fi
  [[ $next_step -gt 7 ]] && next_step=7

  local pct; pct=$(progress_percent "$next_step")
  local status="${STEP_STATUS[$next_step]}"
  local label="${STEP_LABELS[$next_step]}"
  local ts; ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  python3 -c "
import json
with open('$file') as f: d = json.load(f)
d['workflow_step'] = $next_step
d['workflow_progress'] = $pct
d['status'] = '$status'
d['updated_at'] = '$ts'
with open('$file', 'w') as f: json.dump(d, f, indent=2)
" 2>/dev/null || {
    sed -i "s/\"workflow_step\": [0-9]*/\"workflow_step\": ${next_step}/" "$file"
    sed -i "s/\"workflow_progress\": [0-9]*/\"workflow_progress\": ${pct}/" "$file"
  }

  # Logseq log entry (markdown)
  local logfile="${LOGSEQ_LOG_DIR}/${contract_id}.md"
  cat >> "$logfile" <<EOF
- **[${ts}]** Step ${next_step}/7 — ${pct}% — \`${status}\`
  - ${label}
  - Contract: \`${contract_id}\`
EOF

  _log "STEP ${next_step}/7 (${pct}%): ${contract_id} — ${label}"
  echo "step=${next_step} progress=${pct}% status=${status}"
  echo "$label"
}

# ── show_progress ─────────────────────────────────────────────────────────────
show_progress() {
  local contract_id="${1:?contract id required}"
  local file; file=$(find "$CONTRACTS_DIR" -name "${contract_id}.json" 2>/dev/null | head -1)
  [[ -f "$file" ]] || { echo "ERROR: contract $contract_id not found"; return 1; }

  python3 -c "
import json
with open('$file') as f: d = json.load(f)
step = d.get('workflow_step', 0)
pct  = d.get('workflow_progress', 0)
status = d.get('status', '?')
topic  = d.get('topic', {}).get('label', '?')
print(f'Contract : {d[\"id\"]}')
print(f'Topic    : {topic}')
print(f'Status   : {status}')
print(f'Step     : {step}/7  ({pct}%)')
bar = '█' * int(pct // 10) + '░' * (10 - int(pct // 10))
print(f'Progress : [{bar}] {pct}%')
" 2>/dev/null || grep -E '"id"|"status"|"workflow"' "$file"
}

# ── export_progress_json ──────────────────────────────────────────────────────
export_progress_json() {
  local contract_id="${1:?contract id required}"
  local file; file=$(find "$CONTRACTS_DIR" -name "${contract_id}.json" 2>/dev/null | head -1)
  [[ -f "$file" ]] || { echo "{}"; return 1; }
  python3 -c "
import json
with open('$file') as f: d = json.load(f)
out = {
  'id': d['id'],
  'step': d.get('workflow_step', 0),
  'progress': d.get('workflow_progress', 0),
  'status': d.get('status', 'DRAFT'),
  'topic': d.get('topic', {}).get('label', ''),
  'steps': {str(k): v for k, v in {
    0:'INIT',1:'EXTRACT',2:'CLASSIFY',3:'RELATE',
    4:'CONSTRAIN',5:'VERBALIZE',6:'ALIGN',7:'CONTRACT'
  }.items()}
}
print(json.dumps(out, indent=2))
" 2>/dev/null || cat "$file"
}

# ── print_all_bars ────────────────────────────────────────────────────────────
print_all_bars() {
  echo "=== Workflow Progress ==="
  for f in "${CONTRACTS_DIR}"/*.json; do
    [[ -f "$f" ]] || continue
    cid=$(python3 -c "import json; print(json.load(open('$f'))['id'])" 2>/dev/null || basename "$f" .json)
    show_progress "$cid" 2>/dev/null
    echo "---"
  done
}

# ── main dispatch ─────────────────────────────────────────────────────────────
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  cmd="${1:-help}"
  shift || true
  case "$cmd" in
    advance)  advance_step "$@" ;;
    show)     show_progress "$@" ;;
    json)     export_progress_json "$@" ;;
    all)      print_all_bars ;;
    pct)      progress_percent "$@" ;;
    help|*)
      cat <<'EOF'
workflow_tracker.sh — 7-step ORM/SBVR workflow tracker

7-step algorithm:
  0  INIT       Contract created
  1  EXTRACT    Collibra asset types enumerated
  2  CLASSIFY   Asset types → SBVR Concept Types
  3  RELATE     ORM binary fact types identified
  4  CONSTRAIN  ORM uniqueness + mandatory constraints
  5  VERBALIZE  SBVR business rules expressed
  6  ALIGN      Vocab cross-references (SKOS/DCAT/ODRL/PROV)
  7  CONTRACT   Finalized, IDs tracked

Commands:
  advance <contract-id> [step]  — advance workflow step
  show    <contract-id>         — show progress bar (terminal)
  json    <contract-id>         — export progress as JSON
  all                           — show all contract bars
  pct     <step>                — calculate progress percent
EOF
      ;;
  esac
fi
