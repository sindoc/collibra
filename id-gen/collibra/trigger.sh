#!/usr/bin/env bash
# trigger.sh — Collibra use-case approval trigger
# Polls Collibra workflow API; when a use-case asset moves to APPROVED,
# fires contract generation and advances the workflow tracker.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${SCRIPT_DIR}/namespaces.sh"

BASE_DIR="${SCRIPT_DIR}/../uniWork"
COLLIBRA_BASE_URL=$(cat "${BASE_DIR}/CollibraBaseUrl" | head -1)
CSRF_TOKEN=$(cat "${BASE_DIR}/X-CSRF-TOKEN" | head -1)
JSESSIONID=$(cat "${BASE_DIR}/JSESSIONID" | head -1)
COMMUNITY_ID=$(cat "${BASE_DIR}/baseCommunityId" | grep -oE '[0-9a-f-]{36}' | head -1)
LOG_FILE="${BASE_DIR}/id_gen.log"

_log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [TRIGGER] $*" | tee -a "$LOG_FILE"; }

_collibra_get() {
  local path="$1"
  curl -sf \
    -H "accept: application/json" \
    -H "X-CSRF-TOKEN: ${CSRF_TOKEN}" \
    --cookie "JSESSIONID=${JSESSIONID}; XSRF-TOKEN=${CSRF_TOKEN}" \
    "${COLLIBRA_BASE_URL}${path}"
}

_collibra_post() {
  local path="$1"
  local body="$2"
  curl -sf -X POST \
    -H "accept: application/json" \
    -H "Content-Type: application/json" \
    -H "X-CSRF-TOKEN: ${CSRF_TOKEN}" \
    --cookie "JSESSIONID=${JSESSIONID}; XSRF-TOKEN=${CSRF_TOKEN}" \
    -d "$body" \
    "${COLLIBRA_BASE_URL}${path}"
}

# ── list_pending_use_cases ────────────────────────────────────────────────────
# Returns Collibra assets of type "Use Case" in PENDING_APPROVAL status
list_pending_use_cases() {
  _collibra_get "/rest/2.0/assets?communityId=${COMMUNITY_ID}&statusId=00000000-0000-0000-0000-000000005009&limit=50" \
    2>/dev/null \
  || echo '{"results":[]}'
}

# ── approve_use_case ──────────────────────────────────────────────────────────
# Trigger Collibra workflow approval action for an asset
approve_use_case() {
  local asset_id="${1:?Collibra asset UUID required}"
  local comment="${2:-Approved by id-gen trigger}"
  _collibra_post "/rest/2.0/workflowInstances/startOnAsset" \
    "{\"assetId\": \"${asset_id}\", \"workflowDefinitionKey\": \"approvalWorkflow\", \"comment\": \"${comment}\"}" \
    2>/dev/null \
  || echo '{"error":"workflow trigger failed"}'
}

# ── on_use_case_approved ──────────────────────────────────────────────────────
# Called when a use-case is approved in Collibra.
# Creates a data contract, imports the Collibra ID, advances to step 1.
on_use_case_approved() {
  local collibra_uuid="${1:?Collibra asset UUID required}"
  local label="${2:-UnnamedUseCase}"
  local ssh_fp="${3:-}"

  _log "USE CASE APPROVED: ${collibra_uuid} — ${label}"

  # Import Collibra UUID → c.case.* namespace
  local case_id; case_id=$(NS_collibra_import "$collibra_uuid" case "$label")
  _log "IMPORTED: ${case_id}"

  # Generate contract from approved use case
  local contract_id
  contract_id=$("${SCRIPT_DIR}/contracts/generate_contract.sh" new \
    "$label" UseCaseContract "" "$ssh_fp" | head -1)
  _log "CONTRACT: ${contract_id}"

  # Inject collibra case ID into contract
  local file; file=$(find "${SCRIPT_DIR}/contracts/store" -name "${contract_id}.json" 2>/dev/null | head -1)
  if [[ -f "$file" ]]; then
    python3 -c "
import json
with open('$file') as f: d = json.load(f)
d['topic']['collibra_case_id'] = '$case_id'
d['topic']['collibra_community_id'] = '$COMMUNITY_ID'
with open('$file', 'w') as f: json.dump(d, f, indent=2)
" 2>/dev/null || true
  fi

  # Advance workflow to step 1 (EXTRACT)
  "${SCRIPT_DIR}/contracts/workflow_tracker.sh" advance "$contract_id" 1

  echo "$contract_id"
}

# ── poll_and_trigger ──────────────────────────────────────────────────────────
# One-shot poll: check for newly approved use cases and fire contracts
poll_and_trigger() {
  local ssh_fp="${1:-}"
  _log "Polling Collibra for approved use cases..."

  local response; response=$(list_pending_use_cases)
  local count
  count=$(echo "$response" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('results',[])))" \
    2>/dev/null || echo "0")

  _log "Found ${count} pending use cases"

  echo "$response" | python3 -c "
import json, sys, subprocess
d = json.load(sys.stdin)
for r in d.get('results', []):
    uid  = r.get('id', '')
    name = r.get('name', 'unnamed')
    stat = r.get('status', {}).get('name', '')
    if stat in ('Approved', 'APPROVED'):
        print(f'TRIGGER: {uid} — {name}')
" 2>/dev/null | while read -r line; do
    local uuid; uuid=$(echo "$line" | grep -oE '[0-9a-f-]{36}' | head -1)
    local label; label=$(echo "$line" | sed 's/TRIGGER: [^ ]* — //')
    [[ -n "$uuid" ]] && on_use_case_approved "$uuid" "$label" "$ssh_fp"
  done
}

# ── main dispatch ─────────────────────────────────────────────────────────────
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  cmd="${1:-help}"
  shift || true
  case "$cmd" in
    poll)     poll_and_trigger "$@" ;;
    approve)  approve_use_case "$@" ;;
    list)     list_pending_use_cases | python3 -m json.tool 2>/dev/null || list_pending_use_cases ;;
    on-approved) on_use_case_approved "$@" ;;
    help|*)
      cat <<'EOF'
trigger.sh — Collibra use-case approval trigger

Commands:
  poll   [ssh-fp]                         — poll & fire contracts for approved cases
  list                                    — list pending use cases from Collibra
  approve <asset-uuid> [comment]          — trigger Collibra approval workflow
  on-approved <uuid> <label> [ssh-fp]     — manually fire contract for an asset
EOF
      ;;
  esac
fi
