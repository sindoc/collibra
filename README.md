# collibra

Collibra governance tooling — edge stack deployment, contract ID generation,
data contract lifecycle, ORM/SBVR semantic pipeline, and API server.

All features are exposed through the `singine collibra` CLI family.

This repository is the system of record for all Collibra-specific
implementations. Singine may expose and document those capabilities, but the
code that knows about Collibra APIs, SDKs, CLI conventions, Edge, datasource
capabilities, and tenant-specific behaviors belongs here.

---

## Architecture

```
singine collibra <component> <command> [subcommand] [options]
```

### Repository Boundary

The architecture follows three hard boundaries:

| Concern | System of record | Notes |
|---|---|---|
| Collibra-specific code | `collibra/` | REST API clients, SDK adapters, `collibractl` wrappers, Edge workflows, datasource/capability logic, Collibra runbooks |
| Secure execution engine | `singine/` | authentication, authorisation, identity/provider routing, JVM orchestration, manpages/docbook publication, CLI runtime |
| Payload/document transformation | `silkpage/` | XML, XSLT, XPath, RDF, TTL, SPARQL, SQL, GraphQL and adjacent transformation flows |

Operational rule:

- If the implementation depends on Collibra semantics, endpoints, SDK classes,
  Edge behavior, or official Collibra CLI conventions, it belongs in this repo.
- Singine should call into this repo through `COLLIBRA_DIR` discovery and thin
  parser/invocation hooks.
- SilkPage should be the preferred home for cross-format transformation logic,
  especially where James Clark, Tim Bray, and Norman Walsh style XML-first
  workflows are a better fit than ad hoc Python.

### Hooking Model

The preferred integration path is:

```text
singine CLI/runtime -> dynamic import from collibra/singine-collibra/python/singine_collibra -> Collibra implementation
                                                         \
                                                          -> silkpage for XML/RDF/XSLT/XPath transforms
```

That keeps Collibra behavior versioned here while still letting Singine provide
the secure execution shell, docs toolchain, and operator ergonomics.

### Reuse First

Before adding new Collibra-specific code, check these existing assets:

- `singine-collibra/` for Singine-facing Collibra implementation hooks
- `collibra-integrations/` for JVM-oriented integration modules
- `edge/` for Edge runtime, installer, and operator workflows
- sibling `silkpage/` for transformation-heavy XML/RDF/XSLT/XPath work
- sibling `tools-nested/collibra-fs/` for Collibra CLI and filesystem-oriented utilities

The Collibra metamodel and its four-letter codes are treated as a canonical
integration contract across `collibra`, `singine`, `silkpage`, and Edge-facing
components.

The first published command-contract set for HTTP and protocol tooling starts
with `singine collibra io`:

- XML source: `docs/xml/singine-collibra-commands.xml`
- Markdown guide: `docs/collibra-io-commands.md`
- OpenAPI: `schema/singine-collibra-io-api.json`
- SinLisp: `runtime/sinlisp/collibra_io.sinlisp`

```
┌──────────────────────────────────────────────────────────────────┐
│                    singine collibra CLI                          │
├──────────────┬───────────────┬─────────────────┬────────────────┤
│    edge      │      id       │    contract     │    server      │
├──────────────┼───────────────┼─────────────────┼────────────────┤
│ Docker stack │ id-gen/       │ id-gen/         │ id-gen/        │
│ Java server  │ id_gen.sh     │ contracts/      │ server/        │
│ nginx CDN    │ namespaces.sh │ metamodel_7step │ server.sh      │
│ mock DGC     │               │ .sh             │                │
└──────────────┴───────────────┴─────────────────┴────────────────┘
         │               │               │
         ▼               ▼               ▼
  edge/ (Docker)   id-gen/ (Bash)   singine-collibra/ (Python package home)
```

### Component map

| Component | Command | Source |
|-----------|---------|--------|
| Edge stack | `singine collibra edge` | `edge/` |
| ID generation | `singine collibra id` | `id-gen/id_gen.sh`, `id-gen/namespaces.sh` |
| Contracts | `singine collibra contract` | `id-gen/contracts/` |
| ORM/SBVR pipeline | `singine collibra contract pipeline` | `id-gen/collibra/metamodel_7step.sh` |
| API server | `singine collibra server` | `id-gen/server/server.sh` |
| Mock DGC | `singine collibra edge` (dev mode) | `edge/image/collibra-edge-mock/mock_dgc.py` |
| Python glue | imported by singine | `singine-collibra/python/singine_collibra/` |

---

## Quick Start

### Prerequisites

- [singine](https://github.com/sindoc/singine) installed (`singine --version`)
- Docker Desktop (for edge commands)
- Bash 4+, GNU Make, git

### One-liner setup

```bash
# Start the edge stack in dev mode (no Collibra license required)
singine collibra edge setup --dev
singine collibra edge up --detach
singine collibra edge status --json

# Mint a contract ID
singine collibra id gen --ns c --project MyProject

# Create a data contract and run the pipeline
singine collibra contract new --project MyProject
singine collibra contract pipeline
singine collibra contract progress --all
```

---

## Edge Stack (`singine collibra edge`)

The edge stack is a three-service Docker Compose setup:

```
Internet → CDN (nginx :443) ─┬→ edge-site (:8080)     EdgeSiteServerMain.java
                              └→ collibra-edge (:7080)  DGC JAR / Python mock
```

### Deploy modes

| Mode | Command | DGC backend |
|------|---------|-------------|
| Dev (mock) | `singine collibra edge setup --dev` | Python mock |
| Cloud | `singine collibra edge cloud` | `https://lutino.collibra.com` |
| Production | `singine collibra edge deploy` | Real `collibra-edge.jar` |
| Kubernetes | `singine collibra edge site init <name>` | Helm + installer/ |

### Commands

```bash
singine collibra edge build [--target base|collibra-edge|cdn|all] [--tag TAG]
singine collibra edge push  --registry REGISTRY [--target TARGET] [--tag TAG]
singine collibra edge setup [--dev] [--no-start] [--tag TAG]
singine collibra edge up    [--detach]
singine collibra edge down
singine collibra edge logs  [--service edge-site|collibra-edge|cdn] [--follow]
singine collibra edge status [--json]
singine collibra edge install [--tag TAG]
singine collibra edge deploy  [--tag TAG]
singine collibra edge cloud
singine collibra edge test  [--url URL] [--k8s]
singine collibra edge javadoc

# Kubernetes
singine collibra edge site init NAME [--edge-dir DIR] [--namespace NS] [--dry-run]
singine collibra edge k8s prereqs
singine collibra edge k8s install [--dry-run]
singine collibra edge k8s uninstall
singine collibra edge k8s status [--namespace NS]
singine collibra edge k8s logs COMPONENT [--follow] [--tail N]
singine collibra edge k8s test

# Claude API agent
singine collibra edge agent validate
singine collibra edge agent install
singine collibra edge agent status
singine collibra edge agent run --task "DESCRIPTION" [--output-dir DIR]
```

### Edge API endpoints (running stack)

```bash
# All traffic via CDN on :443
curl -sk https://localhost/health
curl -sk https://localhost/api/edge/v1/status
curl -sk https://localhost/api/edge/v1/capabilities
curl -sk https://localhost/rest/2.0/ping       # proxied to collibra-edge
curl -sk https://localhost/rest/2.0/communities
```

### Mock DGC

The Python mock (`edge/image/collibra-edge-mock/mock_dgc.py`) implements the
minimum DGC REST surface for local development without a Collibra license:

| Endpoint | Response |
|----------|----------|
| `GET /rest/2.0/ping` | `{"status":"ok","mock":true}` |
| `GET /rest/2.0/communities` | 3 sample communities |
| `GET /rest/2.0/assets[?typeNames=X]` | 11 sample assets (filterable) |
| `POST,GET /graphql/2.0` | empty stub |

---

## Contract ID Generation (`singine collibra id`)

IDs are minted as annotated git tags using the format `id-gen/<ns>.<kind>.<uuid>`.

### Namespace registry

| Prefix | Owner | Use |
|--------|-------|-----|
| `c.*` | Collibra (privileged) | Production Collibra IDs |
| `a.*` | Reserved | Namespace A |
| `b.*` | Reserved | Namespace B |

### Commands

```bash
# Mint IDs
singine collibra id gen [--ns c|a|b] [--project PROJECT] [--kind KIND]
singine collibra id gen-topic [--project PROJECT]
singine collibra id import --uuid UUID --kind KIND [--project PROJECT]

# Registry operations
singine collibra id tags
singine collibra id push-tags

# Conflict resolution
singine collibra id detect-conflicts
singine collibra id resolve-conflicts [--strategy OURS|THEIRS|COLLIBRA_WINS|ASK|MANUAL]
```

**Priority rule for conflict resolution:** `c.*` > `b.*` > `a.*` > raw UUID.
`COLLIBRA_WINS` (default) always prefers `c.*` namespaced IDs.

---

## Data Contracts (`singine collibra contract`)

### 7-step ORM/SBVR pipeline

| Step | Label | Status | Progress |
|------|-------|--------|----------|
| 0 | INIT | DRAFT | 0% |
| 1 | EXTRACT | DRAFT | 14% |
| 2 | CLASSIFY | DRAFT | 29% |
| 3 | RELATE | DRAFT | 43% |
| 4 | CONSTRAIN | PENDING_APPROVAL | 57% |
| 5 | VERBALIZE | PENDING_APPROVAL | 71% |
| 6 | ALIGN | PENDING_APPROVAL | 86% |
| 7 | CONTRACT | APPROVED | 100% |

### Contract statuses

`DRAFT` → `PENDING_APPROVAL` → `APPROVED`
Additional: `REJECTED`, `ACTIVE`, `DEPRECATED`

### Commands

```bash
# Scaffold and list
singine collibra contract new  [--project PROJECT] [--kind DataContract|UseCaseContract|ServiceContract|GovernanceContract]
singine collibra contract list

# Status management
singine collibra contract status CONTRACT_ID DRAFT|PENDING_APPROVAL|APPROVED|REJECTED|ACTIVE|DEPRECATED

# Pipeline
singine collibra contract pipeline [--id CONTRACT_ID]
singine collibra contract step N   [--id CONTRACT_ID]   # N = 1–7
singine collibra contract advance  [--id CONTRACT_ID]
singine collibra contract progress [--id CONTRACT_ID] [--all] [--json]
```

---

## API Server (`singine collibra server`)

The id-gen HTTP server exposes contract and ID operations over REST.

### Endpoints

| Endpoint | Mode | Description |
|----------|------|-------------|
| `GET /health` | net + dmz | Liveness probe |
| `GET /api/id/gen` | net + dmz | Mint a new ID |
| `GET /api/contracts/list` | net + dmz | List all contracts |
| `GET /api/progress` | net + dmz | All contract progress |
| (all other endpoints) | net only | Full API access |

### Commands

```bash
singine collibra server start [--port 7331] [--mode net|dmz]
singine collibra server dmz   [--port 7331]    # start in restricted mode
singine collibra server status
singine collibra server stop
```

---

## Python Package (`singine-collibra/python/singine_collibra/`)

The `singine_collibra` package is the core Python implementation for the
`singine collibra id`, `singine collibra contract`, and `singine collibra server`
subcommands. It is dynamically imported by the singine CLI from the
`singine-collibra/python/` path.

### Direct use

```bash
export PYTHONPATH=$PYTHONPATH:~/ws/git/github/sindoc/collibra/singine-collibra/python
```

```python
from singine_collibra import idgen, contract, server

# Mint an ID
idgen.gen(ns="c", project="MyProject")

# Create and advance a contract
contract.new(project="MyProject", kind="DataContract")
contract.advance()
contract.progress(all_contracts=True)

# Start the API server
server.start(port=7331, mode="net")
```

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `COLLIBRA_DIR` | `~/ws/git/github/sindoc/collibra` | Collibra repo root |
| `COLLIBRA_EDGE_DIR` | `$COLLIBRA_DIR/edge` | Edge stack root (singine) |

### Metamodel Contract

The Collibra metamodel and its four-letter codes are a canonical integration
contract across `collibra`, `singine`, `silkpage`, and Edge-facing workflows.

---

## Repository Layout

```
collibra/
├── README.md                        ← this file
├── CLAUDE.md                        ← AI assistant guide
├── .gitignore
│
├── edge/                            ← Docker edge stack
│   ├── docker-compose.yml           ← production (real DGC JAR)
│   ├── docker-compose.dev.yml       ← dev (Python mock)
│   ├── docker-compose.cloud.yml     ← cloud (lutino.collibra.com)
│   ├── image/
│   │   ├── base/                    ← CentOS 7 LTS base image
│   │   ├── edge-site/               ← EdgeSiteServerMain.java
│   │   ├── cdn/                     ← nginx reverse proxy + TLS
│   │   ├── collibra-edge/           ← DGC edge JAR runner
│   │   └── collibra-edge-mock/      ← Python mock DGC (mock_dgc.py)
│   ├── java/                        ← Pure-interface Gradle module
│   ├── agent/                       ← Claude API artifact generator
│   ├── scripts/
│   │   ├── setup.sh                 ← one-command idempotent setup
│   │   └── install-edge-k8s.sh     ← Kubernetes Helm deployment
│   └── CLAUDE.md
│
├── id-gen/                          ← Bash contract lifecycle
│   ├── Makefile                     ← make help for all targets
│   ├── id_gen.sh                    ← ID minting + conflict resolution
│   ├── namespaces.sh                ← namespace registry (c.*, a.*, b.*)
│   ├── collibra/
│   │   ├── metamodel_7step.sh       ← 7-step ORM/SBVR pipeline
│   │   ├── sparql_to_contract.sh   ← SPARQL → contract translation
│   │   └── trigger.sh              ← Collibra polling agent
│   ├── contracts/
│   │   ├── generate_contract.sh    ← contract scaffolding
│   │   ├── workflow_tracker.sh     ← step advancement + progress
│   │   ├── contract_schema.json    ← JSON Schema draft-07
│   │   └── store/                  ← generated contract JSON files
│   ├── governance/
│   │   ├── reference_data.json     ← enums, SBVR/SKOS/DCAT/ODRL mappings
│   │   ├── vocab_alignment.json    ← cross-ontology mappings
│   │   └── schema_*.json           ← normalised/denormalised schemas
│   ├── namespaces/
│   │   ├── c.registry              ← Collibra IDs (privileged)
│   │   ├── a.registry              ← namespace A
│   │   └── b.registry              ← namespace B
│   ├── server/
│   │   ├── server.sh               ← HTTP API server (net/dmz)
│   │   └── start.lisp              ← Common Lisp HTTP API
│   └── ui/
│       ├── progress.html           ← standalone progress tracker
│       └── Progress.jsx            ← React component
│
├── collibra-integrations/           ← Java/Maven integrations
│   ├── collibra-edge/               ← SQL pushdown + device registry
│   ├── collibra-jdbc/               ← JDBC Type 4 driver
│   ├── collibra-webhooks/           ← webhook event processor
│   └── collibra-storage/
│
├── singine-collibra/                ← Singine-facing Collibra implementation home
│   ├── README.md
│   └── python/
│       └── singine_collibra/        ← importable Python package
│           ├── __init__.py
│           ├── paths.py             ← COLLIBRA_DIR, IDGEN_DIR, EDGE_DIR
│           ├── idgen.py             ← make wrappers for id-gen
│           ├── contract.py          ← make wrappers for contracts
│           ├── server.py            ← bash wrappers for server.sh
│           └── command.py           ← argparse registration
│
└── uniWork/                         ← runtime state + credentials
    ├── CollibraBaseUrl
    ├── JSESSIONID
    ├── X-CSRF-TOKEN
    └── baseCommunityId
```

---

## Development

### Running the test suite

```bash
# Full workflow smoke-test
cd id-gen && make demo PROJECT="TestProject"

# Edge stack test suite
singine collibra edge setup --dev
singine collibra edge test
```

### Linting shell scripts

All scripts use `set -euo pipefail`. Verify with:

```bash
bash -n id-gen/id_gen.sh
bash -n id-gen/namespaces.sh
bash -n id-gen/collibra/metamodel_7step.sh
```

### Building Java components

```bash
# Edge site server JAR
make -C edge/image/edge-site/server install

# Java interface layer (Gradle)
cd edge/java && ./gradlew build
cd edge/java && ./gradlew javadoc
```

---

## Java Integrations (`collibra-integrations/`)

| Module | Purpose |
|--------|---------|
| `collibra-edge` | SQL pushdown query engine, edge device registry |
| `collibra-jdbc` | JDBC Type 4 driver — query Collibra assets as SQL tables |
| `collibra-webhooks` | Webhook server for real-time Collibra event processing |
| `collibra-storage` | Data persistence layer |

---

## Governance Vocabulary

Contract objects are aligned to standard ontologies via
`id-gen/governance/vocab_alignment.json`:

| Ontology | Use |
|----------|-----|
| SKOS | Concept hierarchies, thesaurus |
| DCAT | Data catalog / dataset descriptions |
| ODRL | Data usage policies |
| PROV-O | Provenance |
| OWL | Ontological grounding |
| SBVR | Business vocabulary and rules (OMG) |

---

## Related

- [singine](https://github.com/sindoc/singine) — platform CLI (provides `singine collibra`)
- Collibra DGC — enterprise data governance platform
