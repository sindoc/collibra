#!/usr/bin/env bash
# sparql_to_contract.sh — SPARQL semantic query → data contract translation
# Parses agreed SPARQL queries, extracts c.* IDs and fact types,
# and generates a structured data contract with ORM/SBVR annotations.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${SCRIPT_DIR}/namespaces.sh"
LOG_FILE="${SCRIPT_DIR}/../uniWork/id_gen.log"

_log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [SPARQL] $*" | tee -a "$LOG_FILE"; }

# ── SPARQL template library ───────────────────────────────────────────────────
# Templates are stored as heredocs; variables are substituted at runtime.
# Prefix: c: = Collibra, a: = reserved-A, b: = reserved-B

SPARQL_PREFIX='
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX odrl: <http://www.w3.org/ns/odrl/2/>
PREFIX c:    <https://api-vlab.collibra.com/ontology/>
PREFIX sbvr: <https://www.omg.org/spec/SBVR/1.5/>
'

# Template: fetch all contracts for a topic/project
sparql_contracts_for_topic() {
  local topic_label="${1:?topic label required}"
  cat <<EOF
${SPARQL_PREFIX}
SELECT ?contract ?contractId ?status ?step
WHERE {
  ?contract rdf:type       c:DataContract ;
            c:id           ?contractId ;
            c:status       ?status ;
            c:workflowStep ?step ;
            c:topic        ?topic .
  ?topic    skos:prefLabel "${topic_label}"@en .
}
ORDER BY DESC(?step)
EOF
}

# Template: fetch use-case approval decisions
sparql_use_case_approvals() {
  cat <<EOF
${SPARQL_PREFIX}
SELECT ?useCase ?id ?decision ?approvedBy ?timestamp
WHERE {
  ?useCase rdf:type      c:UseCase ;
           c:id          ?id ;
           c:decision    ?decision ;
           prov:wasAttributedTo ?approvedBy ;
           prov:generatedAtTime ?timestamp .
  FILTER(?decision = "APPROVED")
}
ORDER BY DESC(?timestamp)
LIMIT 100
EOF
}

# Template: ORM fact types from Collibra meta model
sparql_orm_fact_types() {
  local community_id="${1:-}"
  cat <<EOF
${SPARQL_PREFIX}
SELECT ?subject ?verb ?object ?mandatory ?unique
WHERE {
  ?rel    rdf:type        c:Relation ;
          c:sourceType    ?subject ;
          c:targetType    ?object ;
          c:relationType  ?verb .
  OPTIONAL { ?rel c:mandatory ?mandatory }
  OPTIONAL { ?rel c:unique    ?unique }
  ${community_id:+FILTER(?community = <https://api-vlab.collibra.com/community/${community_id}>)}
}
ORDER BY ?subject ?verb
EOF
}

# Template: SBVR vocabulary alignment query
sparql_vocab_alignment() {
  cat <<EOF
${SPARQL_PREFIX}
SELECT ?concept ?skosMatch ?sbvrType ?dcatClass
WHERE {
  ?concept    rdf:type           c:AssetType ;
              skos:exactMatch    ?skosMatch .
  OPTIONAL { ?concept sbvr:conceptType ?sbvrType }
  OPTIONAL { ?concept skos:broadMatch  ?dcatClass .
             FILTER(STRSTARTS(STR(?dcatClass), "http://www.w3.org/ns/dcat#")) }
}
EOF
}

# ── sparql_to_orm ─────────────────────────────────────────────────────────────
# Parse SPARQL SELECT result bindings → ORM fact type array (JSON)
sparql_to_orm() {
  local sparql_result_json="${1:?SPARQL JSON result required}"
  python3 -c "
import json, sys
data = json.loads('''$sparql_result_json''')
facts = []
for row in data.get('results', {}).get('bindings', []):
    subj = row.get('subject', {}).get('value', '').split('/')[-1]
    verb = row.get('verb',    {}).get('value', '').split('/')[-1]
    obj  = row.get('object',  {}).get('value', '').split('/')[-1]
    mand = row.get('mandatory', {}).get('value', 'false') == 'true'
    uniq = row.get('unique',    {}).get('value', 'false') == 'true'
    if subj and verb and obj:
        facts.append({'subject': subj, 'verb': verb, 'object': obj,
                      'mandatory': mand, 'uniqueness': uniq})
print(json.dumps(facts, indent=2))
" 2>/dev/null || echo "[]"
}

# ── sparql_to_sbvr_rules ──────────────────────────────────────────────────────
# Convert ORM fact types → SBVR verbalized business rules
sparql_to_sbvr_rules() {
  local orm_json="${1:?ORM JSON required}"
  python3 -c "
import json
facts = json.loads('''$orm_json''')
rules = []
for f in facts:
    subj, verb, obj = f['subject'], f['verb'], f['object']
    rule = f'Each {subj} {verb} at most one {obj}.'
    if f.get('mandatory'):
        rule = f'Each {subj} must {verb} at least one {obj}.'
    if f.get('uniqueness') and f.get('mandatory'):
        rule = f'Each {subj} must {verb} exactly one {obj}.'
    rules.append(rule)
print(json.dumps(rules, indent=2))
" 2>/dev/null || echo "[]"
}

# ── translate ─────────────────────────────────────────────────────────────────
# Full pipeline: SPARQL query string → complete data contract JSON
translate() {
  local project="${1:?project/topic label required}"
  local sparql_query="${2:-}"
  local ssh_fp="${3:-}"

  # 1. Generate contract with embedded SPARQL
  _log "Translating SPARQL → contract for project: ${project}"
  local contract_id
  contract_id=$("${SCRIPT_DIR}/contracts/generate_contract.sh" new \
    "$project" DataContract "$sparql_query" "$ssh_fp" | head -1)

  # 2. Derive mock ORM fact types from the SPARQL query structure
  local orm_json
  orm_json=$(python3 -c "
import re, json
q = '''$sparql_query'''
# extract triple patterns: ?s ?p ?o
triples = re.findall(r'\?(\w+)\s+(\w+:\w+)\s+\?(\w+)', q)
facts = []
for s,p,o in triples:
    facts.append({'subject': s, 'verb': p.split(':')[-1], 'object': o,
                  'mandatory': True, 'uniqueness': False})
print(json.dumps(facts, indent=2))
" 2>/dev/null || echo "[]")

  # 3. Generate SBVR rules
  local sbvr_json; sbvr_json=$(sparql_to_sbvr_rules "$orm_json")

  # 4. Inject ORM + SBVR into contract file
  local file; file=$(find "${SCRIPT_DIR}/contracts/store" -name "${contract_id}.json" 2>/dev/null | head -1)
  if [[ -f "$file" ]]; then
    python3 -c "
import json
with open('$file') as f: d = json.load(f)
d['orm_fact_types'] = $orm_json
d['sbvr_rules']     = $sbvr_json
d['sparql_query']   = '''$sparql_query'''
with open('$file', 'w') as f: json.dump(d, f, indent=2)
" 2>/dev/null || true
    _log "ORM + SBVR injected into ${contract_id}"
  fi

  # 5. Advance workflow: EXTRACT(1) → CLASSIFY(2) → RELATE(3)
  "${SCRIPT_DIR}/contracts/workflow_tracker.sh" advance "$contract_id" 1
  "${SCRIPT_DIR}/contracts/workflow_tracker.sh" advance "$contract_id" 2
  "${SCRIPT_DIR}/contracts/workflow_tracker.sh" advance "$contract_id" 3

  echo "$contract_id"
}

# ── show_templates ────────────────────────────────────────────────────────────
show_templates() {
  echo "=== SPARQL Template Library ==="
  echo ""
  echo "1. contracts_for_topic <topic-label>"
  sparql_contracts_for_topic "ExampleTopic"
  echo ""
  echo "2. use_case_approvals"
  sparql_use_case_approvals
  echo ""
  echo "3. orm_fact_types [community-id]"
  sparql_orm_fact_types
  echo ""
  echo "4. vocab_alignment"
  sparql_vocab_alignment
}

# ── main dispatch ─────────────────────────────────────────────────────────────
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  cmd="${1:-help}"
  shift || true
  case "$cmd" in
    translate)        translate "$@" ;;
    template)
      t="${1:-help}"; shift || true
      case "$t" in
        contracts)    sparql_contracts_for_topic "$@" ;;
        approvals)    sparql_use_case_approvals ;;
        orm)          sparql_orm_fact_types "$@" ;;
        vocab)        sparql_vocab_alignment ;;
        all)          show_templates ;;
        *)            show_templates ;;
      esac ;;
    orm)              sparql_to_orm "$@" ;;
    sbvr)             sparql_to_sbvr_rules "$@" ;;
    help|*)
      cat <<'EOF'
sparql_to_contract.sh — SPARQL → data contract translator

Commands:
  translate <project> [sparql-query] [ssh-fp]  — full pipeline → contract
  template  contracts <topic>                  — SPARQL for contracts by topic
  template  approvals                          — SPARQL for approval decisions
  template  orm [community-id]                 — SPARQL for ORM fact types
  template  vocab                              — SPARQL for vocab alignment
  template  all                                — show all templates
  orm  <sparql-result-json>                    — parse → ORM fact type JSON
  sbvr <orm-json>                              — ORM → SBVR rules
EOF
      ;;
  esac
fi
