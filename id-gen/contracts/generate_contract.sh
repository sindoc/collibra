#!/usr/bin/env bash
# generate_contract.sh — Generate a data contract from a SPARQL query / topic
# Usage: ./generate_contract.sh <project-label> [kind] [sparql-query-string]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${SCRIPT_DIR}/namespaces.sh"

GIT_ROOT=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || echo "$SCRIPT_DIR")
CONTRACTS_DIR="${SCRIPT_DIR}/contracts/store"
LOG_FILE="${SCRIPT_DIR}/../uniWork/id_gen.log"

mkdir -p "$CONTRACTS_DIR"

_log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG_FILE"; }
_uuid() { python3 -c "import uuid; print(uuid.uuid4())" 2>/dev/null \
    || cat /proc/sys/kernel/random/uuid 2>/dev/null \
    || uuidgen 2>/dev/null \
    || od -x /dev/urandom | head -1 | awk '{OFS="-"; print $2$3,$4,$5,$6,$7$8$9}'; }

# ── new_contract ──────────────────────────────────────────────────────────────
new_contract() {
  local project="${1:?project/topic label required}"
  local kind="${2:-DataContract}"
  local sparql="${3:-}"
  local ssh_fp="${4:-}"   # SSH key fingerprint of initiating principal

  # Mint IDs — c.* namespace (Collibra-privileged)
  local topic_id; topic_id=$(NS_topic_from_project "$project")
  local contract_id; contract_id=$(NS_mint c contract "$project")
  local ts; ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  local git_tag="id-gen/${contract_id}"

  # Write contract JSON
  local file="${CONTRACTS_DIR}/${contract_id}.json"
  cat > "$file" <<EOF
{
  "id": "${contract_id}",
  "kind": "${kind}",
  "status": "DRAFT",
  "workflow_step": 0,
  "workflow_progress": 0,
  "topic": {
    "id": "${topic_id}",
    "label": "${project}",
    "collibra_community_id": "$(cat "${SCRIPT_DIR}/../uniWork/baseCommunityId" 2>/dev/null | grep -oE '[0-9a-f-]{36}' | head -1 || echo '')"
  },
  "sparql_query": $(echo "$sparql" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))" 2>/dev/null || echo "\"${sparql}\""),
  "sbvr_rules": [],
  "orm_fact_types": [],
  "schema": {
    "normalized": {},
    "denormalized": {}
  },
  "git_tag": "${git_tag}",
  "created_at": "${ts}",
  "updated_at": "${ts}",
  "ssh_identity": "${ssh_fp}",
  "a_ids": [],
  "b_ids": [],
  "vocab_alignment": {
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "dcat": "http://www.w3.org/ns/dcat#",
    "odrl": "http://www.w3.org/ns/odrl/2/",
    "prov": "http://www.w3.org/ns/prov#",
    "owl":  "http://www.w3.org/2002/07/owl#",
    "sbvr": "https://www.omg.org/spec/SBVR/1.5/"
  }
}
EOF

  # Tag in git
  "${SCRIPT_DIR}/id_gen.sh" tag "$contract_id" \
    "DataContract: ${project} | ${kind} | ${ts}" 2>/dev/null || true

  _log "CONTRACT CREATED: ${contract_id} → ${file}"
  echo "$contract_id"
  echo "FILE: $file"
}

# ── update_status ─────────────────────────────────────────────────────────────
update_status() {
  local contract_id="${1:?contract id required}"
  local new_status="${2:?status required}"
  local file; file=$(find "$CONTRACTS_DIR" -name "${contract_id}.json" 2>/dev/null | head -1)
  [[ -f "$file" ]] || { echo "ERROR: contract $contract_id not found"; return 1; }

  local ts; ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  python3 -c "
import json, sys
with open('$file') as f: d = json.load(f)
d['status'] = '$new_status'
d['updated_at'] = '$ts'
with open('$file', 'w') as f: json.dump(d, f, indent=2)
print('STATUS UPDATED:', '$new_status')
" 2>/dev/null || {
    # python fallback: sed
    sed -i "s/\"status\": \"[^\"]*\"/\"status\": \"${new_status}\"/" "$file"
    echo "STATUS UPDATED: ${new_status}"
  }
  _log "STATUS: ${contract_id} → ${new_status}"
}

# ── list_contracts ────────────────────────────────────────────────────────────
list_contracts() {
  echo "=== Data Contracts ==="
  for f in "${CONTRACTS_DIR}"/*.json; do
    [[ -f "$f" ]] || continue
    python3 -c "
import json
with open('$f') as fh: d = json.load(fh)
print(f\"  {d['id']}  [{d['status']}]  step={d['workflow_step']}/7  {d['topic']['label']}\")
" 2>/dev/null || grep -o '"id"[^,]*\|"status"[^,]*' "$f" | tr '\n' '  '
    echo
  done
}

# ── main dispatch ─────────────────────────────────────────────────────────────
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  cmd="${1:-help}"
  shift || true
  case "$cmd" in
    new)    new_contract "$@" ;;
    status) update_status "$@" ;;
    list)   list_contracts ;;
    help|*)
      cat <<'EOF'
generate_contract.sh — data contract generator

Commands:
  new    <project> [kind] [sparql] [ssh-fp]  — create contract + git tag
  status <contract-id> <STATUS>              — update contract status
  list                                       — list all contracts
EOF
      ;;
  esac
fi
