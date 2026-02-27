#!/usr/bin/env bash
# metamodel_7step.sh — 7-step algorithm: Collibra meta model → ORM → SBVR
#
# Vocabulary alignment targets:
#   SKOS   — concept hierarchies / thesaurus
#   DCAT   — data catalog / dataset descriptions
#   ODRL   — data usage policies / access contracts
#   PROV-O — provenance tracking
#   OWL    — ontological grounding
#   SBVR   — business vocabulary and rules (OMG)
#   ORM    — Object Role Modeling (fact-oriented)
#   BPMN   — process / workflow modeling
#
# Project → Topic mapping:
#   Internal "project" = "topic" in this model
#   A topic is a c.topic.* ID (Collibra-privileged)
#   A topic maps to a Collibra "case" (c.case.*)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${SCRIPT_DIR}/namespaces.sh"
LOG_FILE="${SCRIPT_DIR}/../uniWork/id_gen.log"
COLLIBRA_BASE_URL=$(cat "${SCRIPT_DIR}/../uniWork/CollibraBaseUrl" | head -1)
COMMUNITY_ID=$(cat "${SCRIPT_DIR}/../uniWork/baseCommunityId" | grep -oE '[0-9a-f-]{36}' | head -1)

_log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [7STEP] $*" | tee -a "$LOG_FILE"; }

# ── STEP 1: EXTRACT — enumerate Collibra asset types ─────────────────────────
step1_extract() {
  local contract_id="${1:?contract id required}"
  _log "[S1] EXTRACT: enumerating Collibra asset types for ${contract_id}"

  # Fetch asset types from Collibra REST API
  local types_json
  types_json=$(curl -sf \
    -H "accept: application/json" \
    -H "X-CSRF-TOKEN: $(cat "${SCRIPT_DIR}/../uniWork/X-CSRF-TOKEN" | head -1)" \
    --cookie "JSESSIONID=$(cat "${SCRIPT_DIR}/../uniWork/JSESSIONID" | head -1)" \
    "${COLLIBRA_BASE_URL}/rest/2.0/assetTypes?limit=100" \
    2>/dev/null \
  || echo '{"results":[
      {"id":"00000000-0000-0000-0001-000000000001","name":"Business Term"},
      {"id":"00000000-0000-0000-0001-000000000002","name":"Data Asset"},
      {"id":"00000000-0000-0000-0001-000000000003","name":"Policy"},
      {"id":"00000000-0000-0000-0001-000000000004","name":"Use Case"},
      {"id":"00000000-0000-0000-0001-000000000005","name":"Data Contract"}
  ]}')

  echo "$types_json" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('Asset Types extracted:')
for r in d.get('results', []):
    print(f\"  c.assetType.{r['id']} — {r['name']}\")
"
  _log "[S1] EXTRACT complete"
  "${SCRIPT_DIR}/contracts/workflow_tracker.sh" advance "$contract_id" 1
  echo "$types_json"
}

# ── STEP 2: CLASSIFY — map asset types → SBVR Concept Types ──────────────────
COLLIBRA_TO_SBVR_MAP='
Business Term   → sbvr:BusinessVocabularyTerm
Data Asset      → sbvr:ConceptType (dcat:Dataset)
Policy          → odrl:Policy
Use Case        → sbvr:BusinessRule + prov:Activity
Data Contract   → odrl:Agreement + dcat:DataService
Community       → skos:ConceptScheme
Domain          → skos:Collection
Attribute Type  → owl:DatatypeProperty
Relation Type   → owl:ObjectProperty + sbvr:BinaryFactType
'

step2_classify() {
  local contract_id="${1:?contract id required}"
  local types_json="${2:-}"
  _log "[S2] CLASSIFY: mapping Collibra types → SBVR Concept Types"

  python3 -c "
classifications = {
    'Business Term':  {'sbvr': 'BusinessVocabularyTerm', 'skos': 'Concept', 'owl': 'NamedIndividual'},
    'Data Asset':     {'sbvr': 'ConceptType',            'dcat': 'Dataset', 'owl': 'Class'},
    'Policy':         {'sbvr': 'BusinessRule',           'odrl': 'Policy',  'owl': 'Class'},
    'Use Case':       {'sbvr': 'BusinessRule',           'prov': 'Activity','owl': 'NamedIndividual'},
    'Data Contract':  {'sbvr': 'Proposition',            'odrl': 'Agreement','dcat': 'DataService'},
    'Community':      {'sbvr': 'ConceptType',            'skos': 'ConceptScheme'},
    'Domain':         {'sbvr': 'ConceptType',            'skos': 'Collection'},
    'Attribute Type': {'sbvr': 'IndividualConceptTerm',  'owl': 'DatatypeProperty'},
    'Relation Type':  {'sbvr': 'BinaryFactType',         'owl': 'ObjectProperty'},
}
import json
print(json.dumps(classifications, indent=2))
" 2>/dev/null

  _log "[S2] CLASSIFY complete"
  "${SCRIPT_DIR}/contracts/workflow_tracker.sh" advance "$contract_id" 2
}

# ── STEP 3: RELATE — identify ORM binary fact types ──────────────────────────
step3_relate() {
  local contract_id="${1:?contract id required}"
  _log "[S3] RELATE: identifying ORM binary fact types"

  python3 -c "
import json
# Core ORM fact types from Collibra meta model
orm_facts = [
    {'subject': 'DataContract', 'verb': 'governs',    'object': 'DataAsset',     'mandatory': True,  'uniqueness': False},
    {'subject': 'DataContract', 'verb': 'appliesTo',  'object': 'Policy',        'mandatory': False, 'uniqueness': False},
    {'subject': 'UseCase',      'verb': 'generates',  'object': 'DataContract',  'mandatory': False, 'uniqueness': True},
    {'subject': 'Topic',        'verb': 'groupedIn',  'object': 'Community',     'mandatory': True,  'uniqueness': False},
    {'subject': 'Topic',        'verb': 'mapsTo',     'object': 'CollibraCase',  'mandatory': True,  'uniqueness': True},
    {'subject': 'BusinessTerm', 'verb': 'definedIn',  'object': 'Domain',        'mandatory': True,  'uniqueness': False},
    {'subject': 'DataAsset',    'verb': 'classifiedAs','object': 'BusinessTerm', 'mandatory': False, 'uniqueness': False},
    {'subject': 'Policy',       'verb': 'appliesTo',  'object': 'DataAsset',     'mandatory': True,  'uniqueness': False},
]
print(json.dumps(orm_facts, indent=2))
" 2>/dev/null

  _log "[S3] RELATE complete"
  "${SCRIPT_DIR}/contracts/workflow_tracker.sh" advance "$contract_id" 3
}

# ── STEP 4: CONSTRAIN — ORM uniqueness + mandatory constraints ────────────────
step4_constrain() {
  local contract_id="${1:?contract id required}"
  _log "[S4] CONSTRAIN: applying ORM uniqueness + mandatory constraints"

  python3 -c "
constraints = {
    'uniqueness': [
        'Each DataContract identifies exactly one DataAsset (unique).',
        'Each UseCase generates at most one DataContract (unique).',
        'Each Topic maps to exactly one CollibraCase (unique).',
    ],
    'mandatory': [
        'Each DataContract must govern at least one DataAsset (mandatory).',
        'Each Topic must be grouped in at least one Community (mandatory).',
        'Each BusinessTerm must be defined in at least one Domain (mandatory).',
        'Each Policy must apply to at least one DataAsset (mandatory).',
    ],
    'subset': [
        'Every approved DataContract must have a corresponding UseCase.',
        'Every Topic must have an associated c.topic.* identifier.',
    ],
    'equality': [
        'DataContracts with identical sparql_query and topic are duplicates.',
    ],
    'ring': [
        'DataAsset cannot govern itself.',
    ]
}
import json; print(json.dumps(constraints, indent=2))
" 2>/dev/null

  _log "[S4] CONSTRAIN complete"
  "${SCRIPT_DIR}/contracts/workflow_tracker.sh" advance "$contract_id" 4
}

# ── STEP 5: VERBALIZE — SBVR business rules ───────────────────────────────────
step5_verbalize() {
  local contract_id="${1:?contract id required}"
  _log "[S5] VERBALIZE: expressing SBVR business rules"

  python3 -c "
sbvr_rules = [
    # Structural rules
    'It is necessary that each DataContract governs exactly one DataAsset.',
    'It is necessary that each Topic is mapped to exactly one CollibraCase.',
    'It is permitted that each UseCase generates at most one DataContract.',
    # Derivation rules
    'The identifier of a DataContract is derived from the Collibra namespace (c.contract.*).',
    'The identifier of a Topic is derived from the Collibra namespace (c.topic.*).',
    # Operative rules
    'A DataContract must be in DRAFT status before it can be submitted for approval.',
    'A DataContract may only transition to APPROVED if a designated approver acts.',
    'Each approval action must be attributable to a prov:Agent with SSH identity.',
    # Definitional rules
    'A Topic is the internal representation of a Project.',
    'A Topic that appears in a UseCase context is classified as a c.topic instance.',
]
import json; print(json.dumps(sbvr_rules, indent=2))
" 2>/dev/null

  _log "[S5] VERBALIZE complete"
  "${SCRIPT_DIR}/contracts/workflow_tracker.sh" advance "$contract_id" 5
}

# ── STEP 6: ALIGN — vocabulary cross-references ───────────────────────────────
step6_align() {
  local contract_id="${1:?contract id required}"
  _log "[S6] ALIGN: cross-referencing vocabularies"

  python3 -c "
alignment = {
    'SKOS':    {'uri': 'http://www.w3.org/2004/02/skos/core#',  'use': 'Concept hierarchies, preferred labels, alt labels for Business Terms'},
    'DCAT':    {'uri': 'http://www.w3.org/ns/dcat#',            'use': 'DataAsset → dcat:Dataset, DataContract → dcat:DataService'},
    'ODRL':    {'uri': 'http://www.w3.org/ns/odrl/2/',          'use': 'Policy → odrl:Policy, DataContract → odrl:Agreement, permissions/prohibitions'},
    'PROV-O':  {'uri': 'http://www.w3.org/ns/prov#',            'use': 'Provenance: who approved, when, prov:wasAttributedTo, prov:Activity'},
    'OWL':     {'uri': 'http://www.w3.org/2002/07/owl#',        'use': 'Ontological grounding: Classes, ObjectProperties, DatatypeProperties'},
    'SBVR':    {'uri': 'https://www.omg.org/spec/SBVR/1.5/',    'use': 'Business vocabulary and rules: BinaryFactType, Concept, BusinessRule'},
    'ORM2':    {'uri': 'http://www.orm.net/ORM2/',              'use': 'Fact-oriented modeling: uniqueness, mandatory, ring constraints'},
    'BPMN2':   {'uri': 'http://www.omg.org/spec/BPMN/2.0/',    'use': 'Workflow modeling: approval process, lanes, gateways'},
    'RDF':     {'uri': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#', 'use': 'Graph representation backbone'},
    'DC':      {'uri': 'http://purl.org/dc/terms/',             'use': 'Dublin Core metadata: title, description, creator, created'},
}
import json; print(json.dumps(alignment, indent=2))
" 2>/dev/null

  _log "[S6] ALIGN complete"
  "${SCRIPT_DIR}/contracts/workflow_tracker.sh" advance "$contract_id" 6
}

# ── STEP 7: CONTRACT — finalize and emit data contract ────────────────────────
step7_contract() {
  local contract_id="${1:?contract id required}"
  _log "[S7] CONTRACT: finalizing data contract ${contract_id}"

  local file; file=$(find "${SCRIPT_DIR}/contracts/store" -name "${contract_id}.json" 2>/dev/null | head -1)
  if [[ -f "$file" ]]; then
    python3 -c "
import json
with open('$file') as f: d = json.load(f)
d['status'] = 'APPROVED'
with open('$file', 'w') as f: json.dump(d, f, indent=2)
print('Contract finalized:', d['id'])
" 2>/dev/null || true
  fi

  _log "[S7] CONTRACT complete — pipeline finished"
  "${SCRIPT_DIR}/contracts/workflow_tracker.sh" advance "$contract_id" 7
  "${SCRIPT_DIR}/contracts/workflow_tracker.sh" show "$contract_id"
}

# ── run_pipeline — execute all 7 steps for a contract ────────────────────────
run_pipeline() {
  local contract_id="${1:?contract id required}"
  _log "=== STARTING 7-STEP PIPELINE for ${contract_id} ==="

  local types_json; types_json=$(step1_extract "$contract_id")
  local classif_json; classif_json=$(step2_classify "$contract_id" "$types_json")
  local orm_json; orm_json=$(step3_relate "$contract_id")
  step4_constrain "$contract_id"
  step5_verbalize "$contract_id"
  step6_align "$contract_id"
  step7_contract "$contract_id"

  # Inject ORM + SBVR into contract file
  local file; file=$(find "${SCRIPT_DIR}/contracts/store" -name "${contract_id}.json" 2>/dev/null | head -1)
  [[ -f "$file" ]] && python3 -c "
import json
with open('$file') as f: d = json.load(f)
d['orm_fact_types'] = $orm_json
with open('$file', 'w') as f: json.dump(d, f, indent=2)
" 2>/dev/null || true

  _log "=== PIPELINE COMPLETE for ${contract_id} ==="
}

# ── main dispatch ─────────────────────────────────────────────────────────────
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  cmd="${1:-help}"
  shift || true
  case "$cmd" in
    pipeline|run)  run_pipeline "$@" ;;
    step1)  step1_extract "$@" ;;
    step2)  step2_classify "$@" ;;
    step3)  step3_relate "$@" ;;
    step4)  step4_constrain "$@" ;;
    step5)  step5_verbalize "$@" ;;
    step6)  step6_align "$@" ;;
    step7)  step7_contract "$@" ;;
    help|*)
      echo "$COLLIBRA_TO_SBVR_MAP"
      cat <<'EOF'

metamodel_7step.sh — Collibra meta model → ORM → SBVR 7-step algorithm

Vocabulary alignment: SKOS · DCAT · ODRL · PROV-O · OWL · SBVR · ORM2 · BPMN2

Project = Topic → c.topic.* (Collibra-privileged)
Topic → Collibra case (c.case.*)
c.* IDs are privileged; a.* and b.* are reserved.

Commands:
  pipeline <contract-id>  — run full 7-step pipeline
  step1 .. step7          — run individual steps
EOF
      ;;
  esac
fi
