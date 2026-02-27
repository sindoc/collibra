#!/usr/bin/env bash
# id_gen.sh — Git-tag-based ID generator with merge-conflict resolver
# Wraps git tags to persist contract IDs; decision model for conflict resolution.
# Usage: ./id_gen.sh <command> [args]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/namespaces.sh"

GIT_ROOT=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || echo "$SCRIPT_DIR")
TAG_PREFIX="id-gen"       # git tag prefix  e.g. id-gen/c.contract.<uuid>
LOG_FILE="${SCRIPT_DIR}/../uniWork/id_gen.log"

_log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG_FILE"; }

# ── tag_id  — persist an ID in git as an annotated tag ───────────────────────
tag_id() {
  local id="${1:?id required}"
  local message="${2:-${id}}"
  local tag_name="${TAG_PREFIX}/${id}"

  if git -C "$GIT_ROOT" tag -l "$tag_name" | grep -q .; then
    _log "TAG EXISTS: $tag_name (idempotent)"
    git -C "$GIT_ROOT" tag -v "$tag_name" 2>/dev/null || true
    return 0
  fi

  git -C "$GIT_ROOT" tag -a "$tag_name" -m "$message"
  _log "TAGGED: $tag_name"
  echo "$tag_name"
}

# ── tag_list  — list all id-gen tags ─────────────────────────────────────────
tag_list() {
  git -C "$GIT_ROOT" tag -l "${TAG_PREFIX}/*" | sort
}

# ── tag_push  — push tags to origin ──────────────────────────────────────────
tag_push() {
  local tag="${1:-}"
  if [[ -n "$tag" ]]; then
    git -C "$GIT_ROOT" push origin "$tag"
  else
    git -C "$GIT_ROOT" push origin --tags
  fi
  _log "PUSHED tags to origin"
}

# ── conflict_detect  — check for merge conflicts in contract files ────────────
conflict_detect() {
  local dir="${1:-${GIT_ROOT}}"
  local conflicts
  conflicts=$(grep -rl "<<<<<<" "$dir" --include="*.json" --include="*.sh" \
    --include="*.md" 2>/dev/null || true)
  if [[ -n "$conflicts" ]]; then
    echo "CONFLICTS_FOUND"
    echo "$conflicts"
    return 1
  fi
  echo "NO_CONFLICTS"
}

# ── conflict_resolve  — decision model for merge conflict resolution ──────────
# Strategies: OURS | THEIRS | UNION | MANUAL | ASK
# For contract IDs: always prefer the c.* (Collibra-privileged) ID.
conflict_resolve() {
  local file="${1:?file required}"
  local strategy="${2:-ASK}"

  _log "RESOLVING conflict in $file with strategy=$strategy"

  # extract our version and their version
  local ours;   ours=$(sed  -n '/^<<<<<<</,/^=======/p' "$file" | grep -v '^<\|^=' || true)
  local theirs; theirs=$(sed -n '/^=======/,/^>>>>>>>/p' "$file" | grep -v '^=\|^>' || true)

  # ID precedence rule: c. > b. > a. > raw-uuid
  _decide_id_winner() {
    local a="$1" b="$2"
    for pat in "c\." "b\." "a\."; do
      echo "$a $b" | grep -qE "$pat" && { echo "$a"; return; }
    done
    echo "$a"
  }

  case "$strategy" in
    OURS)
      sed -i '/^<<<<<<</,/^=======/{ /^=======/d; /^<<<<<<</d }' "$file"
      sed -i '/^>>>>>>>/d' "$file"
      _log "RESOLVED(OURS): $file"
      ;;
    THEIRS)
      sed -i '/^<<<<<<</,/^=======/d' "$file"
      sed -i '/^>>>>>>>/d' "$file"
      _log "RESOLVED(THEIRS): $file"
      ;;
    COLLIBRA_WINS)
      # Extract both sides; keep whichever contains c.* IDs
      if echo "$ours" | grep -q '"c\.'; then
        sed -i '/^<<<<<<</,/^=======/{ /^=======/d; /^<<<<<<</d }' "$file"
        sed -i '/^>>>>>>>/d' "$file"
        _log "RESOLVED(COLLIBRA_WINS→OURS): $file"
      elif echo "$theirs" | grep -q '"c\.'; then
        sed -i '/^<<<<<<</,/^=======/d' "$file"
        sed -i '/^>>>>>>>/d' "$file"
        _log "RESOLVED(COLLIBRA_WINS→THEIRS): $file"
      else
        _log "CONFLICT: no c.* ID found — falling back to OURS"
        sed -i '/^<<<<<<</,/^=======/{ /^=======/d; /^<<<<<<</d }' "$file"
        sed -i '/^>>>>>>>/d' "$file"
      fi
      ;;
    ASK)
      echo ""
      echo "=== CONFLICT in: $file ==="
      echo "--- OURS ---"
      echo "$ours"
      echo "--- THEIRS ---"
      echo "$theirs"
      echo ""
      read -rp "Resolve with [o]urs / [t]heirs / [c]ollibra-wins? " choice
      case "$choice" in
        o) conflict_resolve "$file" OURS ;;
        t) conflict_resolve "$file" THEIRS ;;
        c) conflict_resolve "$file" COLLIBRA_WINS ;;
        *) _log "SKIPPED: $file — manual resolution required" ;;
      esac
      ;;
    MANUAL)
      _log "MANUAL: open $file in editor for resolution"
      "${EDITOR:-vi}" "$file"
      ;;
  esac
}

# ── resolve_all  — resolve all detected conflicts ────────────────────────────
resolve_all() {
  local strategy="${1:-COLLIBRA_WINS}"
  local dir="${2:-${GIT_ROOT}}"
  local files
  files=$(grep -rl "<<<<<<" "$dir" --include="*.json" --include="*.sh" \
    --include="*.md" 2>/dev/null || true)
  if [[ -z "$files" ]]; then
    echo "No conflicts found."
    return 0
  fi
  while IFS= read -r f; do
    conflict_resolve "$f" "$strategy"
  done <<< "$files"
}

# ── generate  — mint an ID, tag it, log it ───────────────────────────────────
generate() {
  local ns="${1:-c}"
  local kind="${2:-contract}"
  local label="${3:-}"
  local id; id=$(NS_mint "$ns" "$kind" "$label")
  tag_id "$id" "Auto-generated ${ns}.${kind} — ${label:-unlabeled}"
  _log "GENERATED: $id"
  echo "$id"
}

# ── equation  — solve or plot a contract value equation ──────────────────────
# Lightweight: uses python3 for numeric eval, outputs LaTeX for rendering.
equation() {
  local expr="${1:?expression required}"
  local mode="${2:-solve}"   # solve | plot | latex

  case "$mode" in
    solve)
      python3 -c "import math; result = ${expr}; print(f'Result: {result}')" \
        2>/dev/null || echo "ERROR: invalid expression"
      ;;
    latex)
      python3 -c "
try:
    import sympy
    x = sympy.Symbol('x')
    e = sympy.sympify('${expr}')
    print(sympy.latex(e))
except ImportError:
    print('${expr}')  # fallback: raw expression
" 2>/dev/null || echo "${expr}"
      ;;
    plot)
      python3 -c "
import math, json
vals = []
for i in range(-10, 11):
    x = i
    try:
        v = eval('${expr}')
        vals.append({'x': x, 'y': round(float(v), 4)})
    except: pass
print(json.dumps(vals, indent=2))
" 2>/dev/null || echo "ERROR: cannot plot"
      ;;
  esac
}

# ── main dispatch ─────────────────────────────────────────────────────────────
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  cmd="${1:-help}"
  shift || true
  case "$cmd" in
    generate|gen)      generate "$@" ;;
    tag)               tag_id "$@" ;;
    tag-list|list)     tag_list ;;
    tag-push|push)     tag_push "$@" ;;
    detect-conflicts)  conflict_detect "$@" ;;
    resolve)           conflict_resolve "$@" ;;
    resolve-all)       resolve_all "$@" ;;
    equation|eq)       equation "$@" ;;
    help|*)
      cat <<'EOF'
id_gen.sh — git-tag ID generator with conflict resolver

Commands:
  gen  [ns=c] [kind=contract] [label]   — mint + tag a new ID
  tag  <id> [message]                   — tag an existing ID
  list                                  — list all id-gen git tags
  push [tag]                            — push tags to origin
  detect-conflicts [dir]                — scan for merge conflicts
  resolve <file> [OURS|THEIRS|COLLIBRA_WINS|ASK|MANUAL]
  resolve-all [strategy] [dir]          — resolve all conflicts
  eq  <expr> [solve|latex|plot]         — evaluate/render equation

Namespaces:  c.* = Collibra (privileged)  a.* = reserved  b.* = reserved
EOF
      ;;
  esac
fi
