#!/usr/bin/env bash
# deploy/db/db.sh — SQLite database layer for id-gen
#
# Three logical databases (one SQLite file each, per "db db db" pattern):
#   db/contracts.db  — data contracts, workflow state, ORM facts, SBVR rules
#   db/namespaces.db — ID namespace registry (mirrors namespaces/*.registry)
#   db/catalog.db    — service/resource catalog + vocab namespace lookup
#
# Usage:
#   ./db.sh init                          — create all schemas
#   ./db.sh insert-contract <id> ...      — insert a new contract
#   ./db.sh upsert-from-file <file.json>  — upsert from contract JSON file
#   ./db.sh advance <id> <step>           — advance workflow step
#   ./db.sh query <sql>                   — raw SQL on contracts.db
#   ./db.sh query-ns <sql>                — raw SQL on namespaces.db
#   ./db.sh query-cat <sql>               — raw SQL on catalog.db
#   ./db.sh export-md <contract-id>       — export contract as Logseq markdown
#   ./db.sh resolve <uri-or-prefix>       — catalog namespace resolution

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${SCRIPT_DIR}/../../uniWork/id_gen.log"

DB_CONTRACTS="${SCRIPT_DIR}/contracts.db"
DB_NAMESPACES="${SCRIPT_DIR}/namespaces.db"
DB_CATALOG="${SCRIPT_DIR}/catalog.db"

_log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [DB] $*" | tee -a "$LOG_FILE"; }

# ── sqlite3 shim: CLI preferred, python3 sqlite3 module as fallback ───────────
_SQLITE3_BIN=$(command -v sqlite3 2>/dev/null || true)

_sqlite3() {
  local db="$1"; shift
  local json_mode=false; local sql=""
  while [[ $# -gt 0 ]]; do
    case "$1" in -json) json_mode=true; shift ;; -column|-header) shift ;; *) sql="$*"; break ;; esac
  done
  if [[ -n "$_SQLITE3_BIN" ]]; then
    $json_mode && sqlite3 -json "$db" "$sql" || sqlite3 "$db" "$sql"
  else
    python3 - "$db" "$sql" "$json_mode" <<'PYEOF'
import sqlite3, sys, json
db_path, sql, as_json = sys.argv[1], sys.argv[2], sys.argv[3]=='True'
if not sql.strip(): sys.exit(0)
con = sqlite3.connect(db_path); con.row_factory = sqlite3.Row
try:
    stmts = [s.strip() for s in sql.split(';') if s.strip()]
    rows = []
    for st in stmts:
        cur = con.execute(st)
        if cur.description: rows = cur.fetchall()
    if as_json: print(json.dumps([dict(r) for r in rows], indent=2))
    else:
        for r in rows: print('|'.join('' if v is None else str(v) for v in r))
    con.commit()
except Exception as e: print(f'ERROR: {e}', file=sys.stderr); sys.exit(1)
finally: con.close()
PYEOF
  fi
}

_sq()   { _sqlite3 "$DB_CONTRACTS"  -json "$@"; }
_sqn()  { _sqlite3 "$DB_NAMESPACES" -json "$@"; }
_sqc()  { _sqlite3 "$DB_CATALOG"    -json "$@"; }
_sq_()  { _sqlite3 "$DB_CONTRACTS"  "$@"; }
_sqn_() { _sqlite3 "$DB_NAMESPACES" "$@"; }
_sqc_() { _sqlite3 "$DB_CATALOG"    "$@"; }

# ── db init — create all three schemas (python3 sqlite3 used for portability) ─
db_init() {
  local ts; ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  _log "Initialising all databases via python3 sqlite3"
  python3 - "$DB_CONTRACTS" "$DB_NAMESPACES" "$DB_CATALOG" "$ts" <<'PYEOF'
import sqlite3, sys
db_c, db_n, db_cat, ts = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

# ── contracts.db ──────────────────────────────────────────────────────────────
con = sqlite3.connect(db_c)
con.executescript("""
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS contracts (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL DEFAULT 'DataContract',
  status TEXT NOT NULL DEFAULT 'DRAFT', workflow_step INTEGER NOT NULL DEFAULT 0,
  workflow_progress INTEGER NOT NULL DEFAULT 0, git_tag TEXT,
  sparql_query TEXT, ssh_identity TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS topics (
  id TEXT PRIMARY KEY, label TEXT NOT NULL,
  collibra_case_id TEXT, collibra_community TEXT);
CREATE TABLE IF NOT EXISTS contract_topics (
  contract_id TEXT REFERENCES contracts(id),
  topic_id TEXT REFERENCES topics(id),
  PRIMARY KEY (contract_id, topic_id));
CREATE TABLE IF NOT EXISTS orm_fact_types (
  id TEXT PRIMARY KEY, contract_id TEXT REFERENCES contracts(id),
  subject TEXT NOT NULL, verb TEXT NOT NULL, object TEXT NOT NULL,
  mandatory INTEGER NOT NULL DEFAULT 0, uniqueness INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS sbvr_rules (
  id TEXT PRIMARY KEY, contract_id TEXT REFERENCES contracts(id),
  rule_text TEXT NOT NULL, rule_type TEXT DEFAULT 'structural');
CREATE TABLE IF NOT EXISTS workflow_log (
  id TEXT PRIMARY KEY, contract_id TEXT REFERENCES contracts(id),
  step INTEGER NOT NULL, step_key TEXT NOT NULL, ts TEXT NOT NULL, message TEXT);
CREATE TABLE IF NOT EXISTS docs (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, content TEXT, ts TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status);
CREATE INDEX IF NOT EXISTS idx_contracts_step ON contracts(workflow_step);
CREATE INDEX IF NOT EXISTS idx_orm_contract ON orm_fact_types(contract_id);
CREATE INDEX IF NOT EXISTS idx_sbvr_contract ON sbvr_rules(contract_id);
""")
con.close(); print(f'contracts.db OK')

# ── namespaces.db ─────────────────────────────────────────────────────────────
con = sqlite3.connect(db_n)
con.executescript("""
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS registry (
  id TEXT PRIMARY KEY, ns TEXT NOT NULL, kind TEXT NOT NULL,
  label TEXT, source TEXT DEFAULT 'generated', created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_registry_ns    ON registry(ns);
CREATE INDEX IF NOT EXISTS idx_registry_kind  ON registry(kind);
CREATE INDEX IF NOT EXISTS idx_registry_label ON registry(label);
""")
con.close(); print(f'namespaces.db OK')

# ── catalog.db ────────────────────────────────────────────────────────────────
con = sqlite3.connect(db_cat)
con.executescript("""
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS namespace_catalog (
  prefix TEXT PRIMARY KEY, uri TEXT NOT NULL,
  local_path TEXT, description TEXT, vocab_type TEXT);
CREATE TABLE IF NOT EXISTS service_catalog (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
  endpoint TEXT, auth TEXT DEFAULT 'ssh-key', mode TEXT DEFAULT 'net',
  description TEXT, registered_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cert_store (
  fingerprint TEXT PRIMARY KEY, subject TEXT, key_type TEXT,
  purpose TEXT, file_path TEXT, registered_at TEXT NOT NULL, expires_at TEXT);
CREATE INDEX IF NOT EXISTS idx_svc_kind ON service_catalog(kind);
CREATE INDEX IF NOT EXISTS idx_svc_mode ON service_catalog(mode);
""")
vocabs = [
  ('rdf','http://www.w3.org/1999/02/22-rdf-syntax-ns#',None,'RDF core','owl'),
  ('rdfs','http://www.w3.org/2000/01/rdf-schema#',None,'RDF Schema','owl'),
  ('owl','http://www.w3.org/2002/07/owl#',None,'Web Ontology Language','owl'),
  ('skos','http://www.w3.org/2004/02/skos/core#',None,'Simple KOS','skos'),
  ('dcat','http://www.w3.org/ns/dcat#',None,'Data Catalog','owl'),
  ('odrl','http://www.w3.org/ns/odrl/2/',None,'Open DRM Language','owl'),
  ('prov','http://www.w3.org/ns/prov#',None,'Provenance Ontology','owl'),
  ('dc','http://purl.org/dc/terms/',None,'Dublin Core Terms','owl'),
  ('sbvr','https://www.omg.org/spec/SBVR/1.5/',None,'SBVR 1.5','sbvr'),
  ('orm','http://www.orm.net/ORM2/',None,'ORM2','orm'),
  ('bpmn','http://www.omg.org/spec/BPMN/2.0/',None,'BPMN 2.0','owl'),
  ('xsd','http://www.w3.org/2001/XMLSchema#',None,'XML Schema','xsd'),
  ('c','https://api-vlab.collibra.com/ontology/',None,'Collibra ontology','owl'),
  ('shacl','http://www.w3.org/ns/shacl#',None,'SHACL','shacl'),
]
con.executemany('INSERT OR IGNORE INTO namespace_catalog VALUES(?,?,?,?,?)', vocabs)
svcs = [
  ('svc.collibra.api','Collibra REST API','collibra','https://api-vlab.collibra.com','session-cookie','prod','Main Collibra API',ts),
  ('svc.id-gen.api','id-gen HTTP server','api','http://localhost:7331','ssh-key','net','id-gen contract API',ts),
  ('svc.id-gen.webdav','id-gen WebDAV inbox','webdav','http://localhost:8080/webdav/','anonymous','net','WebDAV drop-zone',ts),
  ('svc.sparql.collibra','Collibra SPARQL','sparql','https://api-vlab.collibra.com/rest/2.0/graphQL','session-cookie','prod','Collibra SPARQL',ts),
  ('svc.markupware','markupware.com','web','https://markupware.com','public','prod','Linked site',ts),
  ('svc.khakbaz','khakbaz.com','web','https://khakbaz.com','public','prod','Controlled server',ts),
  ('svc.guiti','guiti.be','web','https://guiti.be','public','prod','Controlled server',ts),
  ('svc.lutinio','lutinio.io','web','https://lutinio.io','public','prod','Controlled server',ts),
]
con.executemany('INSERT OR IGNORE INTO service_catalog VALUES(?,?,?,?,?,?,?,?)', svcs)
con.commit(); con.close(); print('catalog.db OK')
PYEOF
  _log "All three databases initialised"
  echo "contracts.db  → $DB_CONTRACTS"
  echo "namespaces.db → $DB_NAMESPACES"
  echo "catalog.db    → $DB_CATALOG"
}

# ── insert-contract ───────────────────────────────────────────────────────────
insert_contract() {
  local id="${1:?id required}"
  local label="${2:-unlabeled}"
  local kind="${3:-DataContract}"
  local status="${4:-DRAFT}"
  local sparql="${5:-}"
  local ssh_fp="${6:-}"
  local ts; ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  # Insert into contracts.db
  _sqlite3 "$DB_CONTRACTS" \
    "INSERT OR REPLACE INTO contracts(id,kind,status,workflow_step,workflow_progress,sparql_query,ssh_identity,created_at,updated_at)
     VALUES('${id//\'/\'\'}','$kind','$status',0,0,'${sparql//\'/\'\'}','$ssh_fp','$ts','$ts');"

  # Mirror into namespaces.db
  local ns; ns=$(echo "$id" | cut -d. -f1)
  local k;  k=$(echo  "$id" | cut -d. -f2)
  _sqlite3 "$DB_NAMESPACES" \
    "INSERT OR IGNORE INTO registry(id,ns,kind,label,created_at)
     VALUES('$id','$ns','$k','${label//\'/\'\'}','$ts');"

  _log "DB INSERT: $id ($kind / $status)"
}

# ── upsert-from-file ──────────────────────────────────────────────────────────
upsert_from_file() {
  local file="${1:?JSON file required}"
  python3 -c "
import json, subprocess, sys

with open('$file') as f: d = json.load(f)

id_     = d.get('id','')
kind    = d.get('kind','DataContract')
status  = d.get('status','DRAFT')
step    = d.get('workflow_step',0)
pct     = d.get('workflow_progress',0)
sparql  = d.get('sparql_query','').replace(\"'\",\"''\")
ssh_fp  = d.get('ssh_identity','')
topic   = d.get('topic',{})
tid     = topic.get('id','')
tlabel  = topic.get('label','').replace(\"'\",\"''\")
tcase   = topic.get('collibra_case_id','')
tcomm   = topic.get('collibra_community_id','')

import sqlite3, datetime
ts = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

# contracts.db
con = sqlite3.connect('$DB_CONTRACTS')
con.execute('''INSERT OR REPLACE INTO contracts
  (id,kind,status,workflow_step,workflow_progress,sparql_query,ssh_identity,created_at,updated_at)
  VALUES(?,?,?,?,?,?,?,?,?)''',
  (id_,kind,status,step,pct,sparql,ssh_fp,ts,ts))

if tid:
    con.execute('INSERT OR IGNORE INTO topics(id,label,collibra_case_id,collibra_community) VALUES(?,?,?,?)',
                (tid,tlabel,tcase,tcomm))
    con.execute('INSERT OR IGNORE INTO contract_topics VALUES(?,?)',(id_,tid))

for ft in d.get('orm_fact_types',[]):
    import uuid
    fid = 'c.fact.' + str(uuid.uuid4())
    con.execute('INSERT OR IGNORE INTO orm_fact_types(id,contract_id,subject,verb,object,mandatory,uniqueness) VALUES(?,?,?,?,?,?,?)',
      (fid,id_,ft.get('subject',''),ft.get('verb',''),ft.get('object',''),
       int(ft.get('mandatory',False)), int(ft.get('uniqueness',False))))

for rule in d.get('sbvr_rules',[]):
    rid = 'c.rule.' + str(uuid.uuid4())
    con.execute('INSERT OR IGNORE INTO sbvr_rules(id,contract_id,rule_text) VALUES(?,?,?)',
      (rid,id_,rule))

con.commit(); con.close()

# namespaces.db
ns_ = id_.split('.')[0] if '.' in id_ else 'c'
k_  = id_.split('.')[1] if id_.count('.') >= 2 else 'contract'
nsdb = sqlite3.connect('$DB_NAMESPACES')
nsdb.execute('INSERT OR IGNORE INTO registry(id,ns,kind,label,created_at) VALUES(?,?,?,?,?)',
             (id_,ns_,k_,tlabel,ts))
nsdb.commit(); nsdb.close()

print(f'UPSERTED: {id_}')
" && _log "UPSERT: $file"
}

# ── advance step ──────────────────────────────────────────────────────────────
db_advance() {
  local id="${1:?contract id required}"
  local step="${2:?step required}"
  local pct=$(( step * 100 / 7 ))
  local status
  case $step in
    0|1|2|3) status="DRAFT" ;;
    4|5|6)   status="PENDING_APPROVAL" ;;
    7)       status="APPROVED" ;;
    *)       status="DRAFT" ;;
  esac
  local ts; ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  _sqlite3 "$DB_CONTRACTS" \
    "UPDATE contracts SET workflow_step=$step, workflow_progress=$pct,
     status='$status', updated_at='$ts' WHERE id='$id';"
  _log "ADVANCE: $id → step $step ($pct%) $status"
}

# ── catalog resolve ───────────────────────────────────────────────────────────
db_resolve() {
  local query="${1:?prefix or URI required}"
  # Try prefix match first, then URI substring
  local result
  result=$(_sqlite3 "$DB_CATALOG" -json \
    "SELECT prefix, uri, local_path, description, vocab_type
     FROM namespace_catalog
     WHERE prefix = '${query//\'/\'\'}' OR uri LIKE '%${query//\'/\'\'}%'
     LIMIT 5;" 2>/dev/null || echo "[]")
  echo "$result"

  # Also check service catalog
  local svc
  svc=$(_sqlite3 "$DB_CATALOG" -json \
    "SELECT id, name, kind, endpoint, mode, description
     FROM service_catalog
     WHERE name LIKE '%${query//\'/\'\'}%' OR endpoint LIKE '%${query//\'/\'\'}%'
     LIMIT 5;" 2>/dev/null || echo "[]")
  [[ "$svc" != "[]" ]] && echo "$svc"
}

# ── insert-doc ────────────────────────────────────────────────────────────────
db_insert_doc() {
  local name="${1:?name required}"
  local content="${2:-}"
  local ts; ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  local id; id="doc.$(python3 -c "import uuid; print(uuid.uuid4())")"
  _sqlite3 "$DB_CONTRACTS" \
    "INSERT INTO docs(id,name,content,ts) VALUES('$id','${name//\'/\'\'}','${content:0:4000}','$ts');"
  _log "DOC INSERT: $name → $id"
  echo "$id"
}

# ── export markdown ───────────────────────────────────────────────────────────
db_export_md() {
  local id="${1:?contract id required}"
  python3 -c "
import sqlite3, json, sys

con = sqlite3.connect('$DB_CONTRACTS')
con.row_factory = sqlite3.Row

row = con.execute('SELECT * FROM contracts WHERE id=?', ('$id',)).fetchone()
if not row:
    print('NOT FOUND: $id', file=sys.stderr); sys.exit(1)

topic = con.execute(
  'SELECT t.* FROM topics t JOIN contract_topics ct ON ct.topic_id=t.id WHERE ct.contract_id=?',
  ('$id',)).fetchone()

facts = con.execute('SELECT * FROM orm_fact_types WHERE contract_id=?', ('$id',)).fetchall()
rules = con.execute('SELECT * FROM sbvr_rules WHERE contract_id=?',     ('$id',)).fetchall()
logs  = con.execute('SELECT * FROM workflow_log WHERE contract_id=? ORDER BY step', ('$id',)).fetchall()

steps = ['INIT','EXTRACT','CLASSIFY','RELATE','CONSTRAIN','VERBALIZE','ALIGN','CONTRACT']
step  = row['workflow_step']
pct   = row['workflow_progress']
bar   = '█' * int(pct // 10) + '░' * (10 - int(pct // 10))

md = []
md += [
  f'---',
  f'title: \"Contract: {row[\"id\"]}\"',
  f'tags: [data-contract, c-namespace, step-{step}]',
  f'---',
  f'',
  f'# Contract: \`{row[\"id\"]}\`',
  f'',
  f'| Field | Value |',
  f'|-------|-------|',
  f'| **Status** | {row[\"status\"]} |',
  f'| **Kind** | {row[\"kind\"]} |',
  f'| **Step** | {step}/7 — {steps[step]} |',
  f'| **Progress** | [{bar}] {pct}% |',
  f'| **Topic** | {topic[\"label\"] if topic else \"—\"} |',
  f'| **Created** | {row[\"created_at\"]} |',
  f'',
  f'## SBVR Rules',
  f'',
]
for r in rules:
    md.append(f'- {r[\"rule_text\"]}')
md += ['', '## ORM Fact Types', '', '| Subject | Verb | Object | Mandatory | Unique |', '|---------|------|--------|-----------|--------|']
for f in facts:
    md.append(f'| {f[\"subject\"]} | {f[\"verb\"]} | {f[\"object\"]} | {bool(f[\"mandatory\"])} | {bool(f[\"uniqueness\"])} |')
md += ['', '## Workflow Log', '']
for l in logs:
    md.append(f'- \`{l[\"ts\"]}\` Step {l[\"step\"]}/7 — {l[\"step_key\"]}: {l[\"message\"]}')

print('\n'.join(md))
con.close()
" 2>/dev/null
}

# ── list ─────────────────────────────────────────────────────────────────────
db_list() {
  echo "=== Contracts ==="
  _sqlite3 "$DB_CONTRACTS" \
    "SELECT id, status, workflow_step||'/7' AS step, kind FROM contracts ORDER BY created_at DESC;" \
    2>/dev/null || echo "(no contracts yet)"

  echo ""
  echo "=== Namespace Registry (top 10) ==="
  _sqlite3 "$DB_NAMESPACES" \
    "SELECT id, ns, kind, label FROM registry ORDER BY created_at DESC LIMIT 10;" \
    2>/dev/null || echo "(no entries yet)"

  echo ""
  echo "=== Services ==="
  _sqlite3 "$DB_CATALOG" \
    "SELECT id, name, kind, mode, endpoint FROM service_catalog;" \
    2>/dev/null || echo "(no services yet)"
}

# ── sync from flat files → DB ─────────────────────────────────────────────────
db_sync() {
  local id_gen="${SCRIPT_DIR}/../.."
  _log "Syncing flat files → DB"

  # Contracts store
  for f in "${id_gen}/id-gen/contracts/store"/*.json; do
    [[ -f "$f" ]] || continue
    upsert_from_file "$f"
  done

  # Namespace registries
  for reg in "${id_gen}/id-gen/namespaces"/*.registry; do
    [[ -f "$reg" ]] || continue
    local ns; ns=$(basename "$reg" .registry)
    while IFS='|' read -r ts id label source; do
      [[ -z "$id" ]] && continue
      local kind; kind=$(echo "$id" | cut -d. -f2)
      _sqlite3 "$DB_NAMESPACES" \
        "INSERT OR IGNORE INTO registry(id,ns,kind,label,source,created_at)
         VALUES('${id//\'/\'\'}','$ns','$kind','${label//\'/\'\'}','${source:-generated}','${ts:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}');" \
        2>/dev/null || true
    done < "$reg"
  done

  _log "Sync complete"
}

# ── main dispatch ─────────────────────────────────────────────────────────────
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  cmd="${1:-help}"; shift || true
  case "$cmd" in
    init)             db_init ;;
    insert-contract)  insert_contract "$@" ;;
    upsert-from-file) upsert_from_file "$@" ;;
    advance)          db_advance "$@" ;;
    resolve)          db_resolve "$@" ;;
    insert-doc)       db_insert_doc "$@" ;;
    export-md)        db_export_md "$@" ;;
    list)             db_list ;;
    sync)             db_sync ;;
    query)            _sq_ "$@" ;;
    query-ns)         _sqn_ "$@" ;;
    query-cat)        _sqc_ "$@" ;;
    help|*)
      cat <<'EOF'
db.sh — three-database layer (contracts · namespaces · catalog)

Databases:
  contracts.db   contracts, topics, orm_fact_types, sbvr_rules, workflow_log, docs
  namespaces.db  ID registry (c.* a.* b.*)
  catalog.db     vocab namespace catalog + service catalog + cert store

Commands:
  init                          Create all schemas + seed catalog
  insert-contract <id> <label> <kind> <status> [sparql] [ssh-fp]
  upsert-from-file <file.json>  Import contract JSON file
  advance <id> <step>           Update workflow step (0–7)
  resolve <prefix-or-uri>       Resolve namespace / service catalog entry
  insert-doc <name> <content>   Store a document
  export-md <contract-id>       Export contract as Logseq markdown
  list                          Show all contracts + services
  sync                          Sync flat files → databases
  query     <sql>               Raw SQL on contracts.db
  query-ns  <sql>               Raw SQL on namespaces.db
  query-cat <sql>               Raw SQL on catalog.db
EOF
    ;;
  esac
fi
