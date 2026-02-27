# CLAUDE.md — AI Assistant Guide for the Collibra ID-Gen Repository

This file provides context, conventions, and workflows for AI assistants (Claude Code and similar tools) working in this repository.

---

## Repository Overview

This repository implements a **Bash-based contract ID generation and lifecycle management system** for Collibra data governance. It mints unique, namespace-scoped contract IDs, persists them via Git tags, and drives a 7-step ORM/SBVR semantic transformation pipeline that bridges Collibra assets to formal data contracts.

**Primary working directory:** `id-gen/`
**Supporting utilities:** `uniWork/`

---

## Technology Stack

| Layer | Technology | Notes |
|---|---|---|
| Scripting (primary) | Bash | `set -euo pipefail` throughout |
| Orchestration | GNU Make | `id-gen/Makefile` is the main entry point |
| ID persistence | Git tags | Pattern: `id-gen/<ns>.<kind>.<uuid>` |
| HTTP server | Common Lisp | `id-gen/server/start.lisp` (SBCL / CLISP / ECL / Guile) |
| Frontend | React (JSX) + HTML | `id-gen/ui/` — workflow progress visualisation |
| Data/Config | JSON | Schemas in `id-gen/contracts/`, governance in `id-gen/governance/` |
| Utilities | Python 3 | UUID generation, JSON processing, symbolic math |
| External API | Collibra REST | Cookie + CSRF auth; URL stored in `uniWork/CollibraBaseUrl` |

There is **no package.json** and **no npm**. All orchestration goes through Make.

---

## Repository Structure

```
collibra/
├── CLAUDE.md                        # This file
├── id-gen/                          # Core project
│   ├── Makefile                     # Primary task runner — run `make help`
│   ├── id_gen.sh                    # ID minting + git-tag persistence + conflict resolver
│   ├── namespaces.sh                # Namespace registry (c.*, a.*, b.*)
│   ├── collibra/
│   │   ├── metamodel_7step.sh       # 7-step ORM/SBVR pipeline
│   │   ├── sparql_to_contract.sh    # SPARQL → contract translator
│   │   └── trigger.sh              # Collibra polling
│   ├── contracts/
│   │   ├── generate_contract.sh     # New contract scaffolding
│   │   ├── workflow_tracker.sh      # Step advancement + progress tracking
│   │   ├── contract_schema.json     # JSON Schema (draft-07) for contracts
│   │   └── store/                   # Generated contract JSON files
│   ├── governance/
│   │   ├── reference_data.json      # Enums: kinds, statuses, steps, asset types
│   │   ├── vocab_alignment.json     # SKOS/DCAT/ODRL/PROV/OWL/SBVR mappings
│   │   ├── schema_normalized.json
│   │   └── schema_denormalized.json
│   ├── namespaces/
│   │   ├── c.registry               # Collibra IDs (privileged)
│   │   ├── a.registry               # Reserved namespace A
│   │   └── b.registry               # Reserved namespace B
│   ├── server/
│   │   ├── server.sh                # Startup wrapper (auto-detects Lisp runtime)
│   │   └── start.lisp               # Common Lisp HTTP API
│   └── ui/
│       ├── Progress.jsx             # React progress-bar component
│       ├── progress.html            # Standalone progress tracker
│       └── logseq/logs/             # Logseq markdown logs
└── uniWork/                         # Runtime state and credentials
    ├── CollibraBaseUrl              # Collibra API base URL (plain text)
    ├── JSESSIONID                   # Session cookie
    ├── X-CSRF-TOKEN                 # CSRF token
    ├── baseCommunityId              # Default Collibra community ID
    ├── id_gen.log                   # Unified timestamped log
    └── createTermsAndAcronymsInSameGlossary/
        ├── Makefile
        ├── generate_payload.sh
        ├── RestPath
        └── assets/
```

---

## Development Workflows

All common tasks are driven through `make` from within `id-gen/`. Run `make help` for a full command reference.

### Setup

```bash
cd id-gen
make init        # Create directories and set executable permissions
```

### ID Generation

```bash
make gen [NS=c] [PROJECT=DefaultProject]    # Mint a new contract ID
make gen-topic [PROJECT=...]                 # Mint a topic ID
make import-collibra UUID=<uuid> KIND=...   # Import an existing Collibra UUID
make tags                                    # List all id-gen git tags
make push-tags                               # Push tags to origin
```

### Contract Lifecycle

```bash
make contract [PROJECT=...] [KIND=DataContract]   # Scaffold a new contract
make contract-list                                 # List all contracts
make contract-status CONTRACT_ID=... STATUS=...   # Update contract status
```

### 7-Step Pipeline

```bash
make pipeline [CONTRACT_ID=...]    # Run full pipeline end-to-end
make step1 [CONTRACT_ID=...]       # Run individual step (1–7)
make advance [CONTRACT_ID=...]     # Advance to the next step
make progress [CONTRACT_ID=...]    # Show progress for one contract
make progress-all                  # Show progress for all contracts
```

### Server

```bash
make server-start [PORT=7331] [MODE=net]   # Start dev server (full access)
make server-dmz   [PORT=7331]              # Start in DMZ mode (restricted)
make server-stop                            # Stop server
make server-status                          # Health check
```

Server endpoints: `/health`, `/api/id/gen`, `/api/contracts/list`, `/api/progress`

### SPARQL Integration

```bash
make sparql-translate [QUERY=...] [PROJECT=...]   # Translate SPARQL → contract
make sparql-templates                              # Show template library
```

### Conflict Resolution

```bash
make detect-conflicts                          # Scan for merge conflicts in registries
make resolve-conflicts [STRATEGY=COLLIBRA_WINS]  # Auto-resolve
```

Strategies: `OURS`, `THEIRS`, `COLLIBRA_WINS`, `ASK`, `MANUAL`

### Utilities

```bash
make demo [PROJECT=...]         # Full demonstration workflow
make eq [EXPR="x**2+1"] [MODE=solve|latex|plot]  # Equation solver
make ui                         # Open progress.html in browser
```

---

## Key Conventions

### Shell Scripts

- All scripts use `#!/usr/bin/env bash` and `set -euo pipefail` — **never relax these flags** in new code.
- Private/internal functions are prefixed with `_` (e.g., `_log`, `_uuid`).
- Section breaks use `# ──────────────────────────────────────────` comments.
- Scripts source each other with `source <path>` for modularity.
- Log entries go through `_log()` which prefixes timestamps. Do not use raw `echo` for operational messages.

### ID Namespaces

| Prefix | Owner | Description |
|---|---|---|
| `c.*` | Collibra (privileged) | Production Collibra IDs |
| `a.*` | Reserved | Namespace A |
| `b.*` | Reserved | Namespace B |

ID format: `{namespace}.{kind}.{uuid}` (e.g., `c.contract.f47ac10b-...`)

- **Never** create IDs outside of `id_gen.sh` / `make gen`.
- Registry files (`namespaces/*.registry`) track all minted IDs with timestamps. Do not edit them manually.
- IDs are persisted as annotated git tags (`id-gen/<id>`) — these are the source of truth.

### The 7-Step ORM/SBVR Pipeline

| Step | Label | Status | Progress |
|---|---|---|---|
| 0 | INIT | DRAFT | 0% |
| 1 | EXTRACT | DRAFT | 14% |
| 2 | CLASSIFY | DRAFT | 29% |
| 3 | RELATE | DRAFT | 43% |
| 4 | CONSTRAIN | PENDING_APPROVAL | 57% |
| 5 | VERBALIZE | PENDING_APPROVAL | 71% |
| 6 | ALIGN | PENDING_APPROVAL | 86% |
| 7 | CONTRACT | APPROVED | 100% |

Status lifecycle: `DRAFT` → `PENDING_APPROVAL` → `APPROVED`
Additional statuses: `REJECTED`, `ACTIVE`, `DEPRECATED`

### Contract JSON Schema

All contracts stored in `contracts/store/` must validate against `contracts/contract_schema.json` (JSON Schema draft-07). Required fields: `id`, `kind`, `status`, `created_at`, `project`, `topic_id`. Never write free-form contract JSON — use `make contract` to scaffold.

### Collibra API Authentication

Credentials are stored as plain-text files in `uniWork/`:

| File | Variable | Usage |
|---|---|---|
| `CollibraBaseUrl` | Base URL | All API calls |
| `JSESSIONID` | Cookie | Session auth |
| `X-CSRF-TOKEN` | Header | State-changing requests |
| `baseCommunityId` | ID | Default community |

**Do not hard-code credentials.** Scripts read these files at runtime with `$(cat uniWork/<file>)`.

### Semantic Vocabulary Alignments

`governance/vocab_alignment.json` maps internal concepts to standard ontologies. When modifying contracts or governance data, check this file for the correct external term to use:

- **SKOS** — concept hierarchies / thesaurus
- **DCAT** — data catalog / dataset descriptions
- **ODRL** — data usage policies
- **PROV-O** — provenance
- **OWL** — ontological grounding
- **SBVR** — business vocabulary and rules (OMG standard)

---

## Testing

There is **no formal test framework**. Validation is done through:

1. `make demo PROJECT="TestProject"` — full smoke-test workflow.
2. Manual inspection of `uniWork/id_gen.log`.
3. `make contract-list` and `make progress-all` to verify state.

When adding new shell functionality, at minimum verify the happy path manually with `make demo` and confirm that `set -euo pipefail` exits cleanly on errors.

---

## Linting & Code Style

No automated linting is configured. Follow these conventions when writing shell code:

- `set -euo pipefail` at the top of every script (after the shebang).
- Use `[[ ]]` for conditionals (not `[ ]`).
- Quote all variable expansions: `"${VAR}"`.
- Use `local` for all variables inside functions.
- Prefer `printf` over `echo` for formatted output.
- Use `_log` for any operational log messages.
- Keep functions short and single-purpose.

---

## Git Practices

- Git tags are the **source of truth** for minted IDs. Do not delete or force-overwrite them.
- `git.auto = 0` is set globally in this repo — garbage collection is disabled intentionally.
- When resolving merge conflicts in namespace registries, use `make resolve-conflicts` rather than editing files manually.
- The remote for this repo is `http://local_proxy@127.0.0.1:54221/git/sindoc/collibra`.

### Branch Naming for AI Assistants

Feature branches created by Claude Code use the pattern: `claude/<short-description>-<session-id>` (e.g., `claude/add-claude-documentation-xIyQ1`).

---

## Environment Requirements

| Dependency | Minimum | Notes |
|---|---|---|
| bash | 4.0+ | `#!/usr/bin/env bash` |
| GNU Make | 3.81+ | Primary orchestrator |
| git | 2.0+ | Tag-based ID persistence |
| curl | any | Collibra API calls |
| Python 3 | 3.6+ | UUID, JSON, optional sympy |
| Common Lisp | optional | SBCL / CLISP / ECL / Guile (for server only) |

Python libraries used inline (via `python3 -c`): `uuid`, `json`, `datetime` (stdlib); `sympy` (optional, for `make eq`).

---

## Common Pitfalls

1. **Do not run scripts from the repo root.** Always `cd id-gen` before running make targets — relative paths assume `id-gen/` as the working directory.
2. **Do not create IDs manually.** Always use `make gen` or `make gen-topic` so IDs are registered, tagged, and logged.
3. **Do not edit `*.registry` files by hand.** Use `namespaces.sh` functions or make targets.
4. **Do not skip `make init`** in a fresh clone — scripts will fail without the expected directories.
5. **CSRF tokens expire.** If Collibra API calls return 403, refresh `uniWork/X-CSRF-TOKEN` and `uniWork/JSESSIONID`.
6. **Server mode matters.** DMZ mode restricts which endpoints are accessible — use `net` mode for development and `dmz` only when testing governance restrictions.
7. **`set -euo pipefail` means any unbound variable kills the script.** Always initialise variables before use; use `${VAR:-default}` for optional values.
