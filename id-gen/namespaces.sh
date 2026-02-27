#!/usr/bin/env bash
# namespaces.sh — ID namespace registry
# c.ids  : Collibra IDs (privileged — sourced from or registered in Collibra)
# a.ids  : reserved namespace A
# b.ids  : reserved namespace B
# Usage : source namespaces.sh ; NS_mint c topic

set -euo pipefail

NAMESPACE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/namespaces" && pwd)"

# ── registry files ─────────────────────────────────────────────────────────────
NS_REGISTRY_C="${NAMESPACE_DIR}/c.registry"
NS_REGISTRY_A="${NAMESPACE_DIR}/a.registry"
NS_REGISTRY_B="${NAMESPACE_DIR}/b.registry"
COLLIBRA_BASE_URL_FILE="$(dirname "${BASH_SOURCE[0]}")/../uniWork/CollibraBaseUrl"

mkdir -p "$NAMESPACE_DIR"
touch "$NS_REGISTRY_C" "$NS_REGISTRY_A" "$NS_REGISTRY_B"

# ── internal helpers ───────────────────────────────────────────────────────────
_uuid() { python3 -c "import uuid; print(uuid.uuid4())" 2>/dev/null \
    || cat /proc/sys/kernel/random/uuid 2>/dev/null \
    || uuidgen 2>/dev/null \
    || od -x /dev/urandom | head -1 | awk '{print $2$3"-"$4"-"$5"-"$6"-"$7$8$9}'; }

_collibra_base_url() {
  [[ -f "$COLLIBRA_BASE_URL_FILE" ]] && cat "$COLLIBRA_BASE_URL_FILE" | head -1 \
    || echo "https://api-vlab.collibra.com"
}

# ── NS_mint  <namespace> <kind> [human-label] ─────────────────────────────────
# Mint a new ID: namespace = c | a | b   kind = topic | case | contract | ...
# Prints the full ID string and appends to the registry file.
NS_mint() {
  local ns="${1:?namespace required: c|a|b}"
  local kind="${2:?kind required e.g. topic|case|contract}"
  local label="${3:-}"
  local uuid; uuid=$(_uuid)
  local id="${ns}.${kind}.${uuid}"
  local ts; ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  case "$ns" in
    c) echo "${ts}|${id}|${label}" >> "$NS_REGISTRY_C" ;;
    a) echo "${ts}|${id}|${label}" >> "$NS_REGISTRY_A" ;;
    b) echo "${ts}|${id}|${label}" >> "$NS_REGISTRY_B" ;;
    *) echo "ERROR: unknown namespace '${ns}'. Use c, a, or b." >&2; return 1 ;;
  esac

  echo "$id"
}

# ── NS_lookup  <id> ───────────────────────────────────────────────────────────
NS_lookup() {
  local id="${1:?id required}"
  grep -h "^[^|]*|${id}|" "$NS_REGISTRY_C" "$NS_REGISTRY_A" "$NS_REGISTRY_B" \
    2>/dev/null || echo "NOT_FOUND"
}

# ── NS_list  [namespace] ──────────────────────────────────────────────────────
NS_list() {
  local ns="${1:-all}"
  case "$ns" in
    c)   cat "$NS_REGISTRY_C" ;;
    a)   cat "$NS_REGISTRY_A" ;;
    b)   cat "$NS_REGISTRY_B" ;;
    all) cat "$NS_REGISTRY_C" "$NS_REGISTRY_A" "$NS_REGISTRY_B" ;;
  esac
}

# ── NS_topic_from_project  <project-name> ─────────────────────────────────────
# Project = Topic in internal model; maps to a c.topic.* ID (Collibra-privileged)
NS_topic_from_project() {
  local project="${1:?project name required}"
  local existing
  existing=$(grep -h "|c\.topic\." "$NS_REGISTRY_C" 2>/dev/null \
    | grep "|${project}$" | head -1 | cut -d'|' -f2 || true)
  if [[ -n "$existing" ]]; then
    echo "$existing"
  else
    NS_mint c topic "$project"
  fi
}

# ── NS_collibra_import  <collibra-uuid> <kind> <label> ───────────────────────
# Register an ID that already exists in Collibra; prefix with c.
NS_collibra_import() {
  local cuuid="${1:?collibra UUID required}"
  local kind="${2:?kind required}"
  local label="${3:-}"
  local id="c.${kind}.${cuuid}"
  local ts; ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  echo "${ts}|${id}|${label}|collibra-import" >> "$NS_REGISTRY_C"
  echo "$id"
}

# ── standalone execution ──────────────────────────────────────────────────────
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  cmd="${1:-help}"
  shift || true
  case "$cmd" in
    mint)    NS_mint "$@" ;;
    lookup)  NS_lookup "$@" ;;
    list)    NS_list "$@" ;;
    topic)   NS_topic_from_project "$@" ;;
    import)  NS_collibra_import "$@" ;;
    help|*)
      cat <<'EOF'
namespaces.sh — ID namespace registry
  c.* = Collibra (privileged)   a.* = reserved-A   b.* = reserved-B

Commands:
  mint   <ns> <kind> [label]   — generate a new namespaced ID
  lookup <id>                  — find registry entry for an ID
  list   [ns|all]              — list all IDs in namespace
  topic  <project-name>        — get or create c.topic ID for project
  import <collibra-uuid> <kind> [label]  — import existing Collibra ID
EOF
      ;;
  esac
fi
