# Backlog — sindoc/collibra

> Upsert target: Claude Code backlog · branch `claude/add-documentation-docs1`
> Last updated: 2026-03-26

---

## Epics

| ID | Epic | Status |
|----|------|--------|
| E1 | chip MCP query surface | in progress |
| E2 | Quantum catalog & symbolic chain | in progress |
| E3 | gRPC-HTTP persistence bridge | open |
| E4 | JProfiler JVM attach (Groovy + Clojure) | open |
| E5 | Code tables + Shiva base layer | open |
| E6 | BubbleLeader builder chain | open |
| E7 | Cosine similarity → Collibra resolution | open |

---

## E1 · chip MCP Query Surface

### CHIP-001 · MCP query DSL — `chip_queries.py`

**Status:** done
**Branch:** `claude/add-documentation-docs1`
**File:** `singine-collibra/python/singine_collibra/chip_queries.py`

Implements the full `~ws(self, ...+ ++ +++ ++++ +++++)/codeLookup().lambda_().exec().try_catch_claude()` chain.

**Acceptance criteria:**
- [x] `WorkspaceDepth` enum: SELF(0) → FULL(5), symbols `self + ++ +++ ++++ +++++`
- [x] `WorkspaceContext(depth)` constructs root traversal context
- [x] `CodeLookupQuery._build_request()` emits valid JSON-RPC 2.0 `tools/call` to chip
- [x] `.lambda_(transform)` wraps in deferred `LambdaExec`
- [x] `.exec()` runs chip session; catches all exceptions
- [x] `.try_catch_claude()` returns result or MCP error envelope (`code: -32000`)
- [x] `.type_retrieval()` returns typed `TypeRetrieval` with `TypeRef`
- [x] `discover_jvm_targets()` uses `jps -l` to find Groovy + Clojure PIDs

**Depends on:** `chip.py` (ChipSession, ChipRequest, ChipPaths)

---

### CHIP-002 · XML grammar — `chip-queries.xml`

**Status:** done
**File:** `docs/xml/chip-queries.xml`

System-of-design for the full query surface. Go `lang=XML.g()` entry point.

**Acceptance criteria:**
- [x] `<workspace-depths>` — 6 levels (self, +, ++, +++, ++++, +++++)
- [x] `<query-types>` — `code-lookup`, `type-retrieval`, `lambda-exec`
- [x] `<grpc-http-bindings>` — 6 RPC bindings for `singine.persistence.v1`
- [x] `<jprofiler-targets>` — `groovy-process`, `clojure-process` with pattern matchers
- [x] `<go-codegen>` — declares output path and generated types

---

### CHIP-003 · HTTP-compatible gRPC bridge

**Status:** done (Python layer); **open** (Go server + proto codegen)
**File:** `singine-collibra/python/singine_collibra/chip_queries.py` → `grpc_http_call()`

**Acceptance criteria:**
- [x] `GrpcHttpRequest` dataclass: `rpc`, `body`, `base_url`, `use_http`
- [x] `_RPC_HTTP_MAP` covers all 6 `persistence.proto` RPCs
- [x] HTTP transcoding: POST/GET with `X-Singine-Rpc` header
- [ ] Go `grpc-gateway` annotations in `persistence.proto`
- [ ] Generated `persistence.pb.gw.go` for native HTTP/2 + JSON transcoding
- [ ] Integration test: Python HTTP call → Go grpc-gateway → Clojure handler

---

## E2 · Quantum Catalog & Symbolic Chain

### QCAT-001 · Quantum catalog Python module

**Status:** done
**File:** `singine-collibra/python/singine_collibra/quantum_catalog.py`

**Acceptance criteria:**
- [x] `dirac(x, x0, eps)` — Gaussian δ approximation
- [x] `einstein()` — field equations + data-gravity analog + ultimate metric
- [x] `knuth()` — O/Ω/Θ + up-arrow notation
- [x] `tex()` — TeX badness formula string
- [x] `latex(expr)` — renders any expr to LaTeX string
- [x] `jd(Y, M, D)` — Julian Day Number for temporal lineage keys
- [x] `QuantumStack` — `push()` (â†), `pop()` (â), `number_expectation()` (⟨N̂⟩), `ket()` string
- [x] `QuantumQueue` — `enqueue()`, `dequeue()` (Tr₁), `purity()` (Tr[ρ²])
- [x] `cosine_similarity_complex(u, v)` — Re(⟨u,v⟩)/(|u|·|v|) in ℂⁿ
- [x] `CosineChain` — full 7-step fluent chain to `collibra()`
- [x] `BubbleLeaderChain` — 13-layer monad bind to `paulGraham()`

---

### QCAT-002 · LaTeX document

**Status:** done
**File:** `docs/quantum/chip-quantum-catalog.tex`

Compile: `pdflatex chip-quantum-catalog.tex` (requires `physics`, `tikz`, `pgfplots`)

**Acceptance criteria:**
- [x] TikZ unit circle diagram — θ, cos θ, sin θ, vectors **u** and **v**
- [x] Quantum stack: â†|n⟩=√(n+1)|n+1⟩; [â,â†]=**1**; uncertainty ΔN·Δφ≥½
- [x] Quantum queue: ρ=Σpᵢ|ψᵢ⟩⟨ψᵢ|; enqueue U_enq; dequeue Tr₁
- [x] Einstein field equation + data-gravity analog
- [x] BubbleLeader chain table (13 layers) + Gödel formula + Y-combinator
- [x] Code table AAAA…FFFFF with SBVR/DCAT/Collibra columns
- [x] MathML fragments for Euler identity and cosine similarity
- [ ] CI: `make docs` compiles `.tex` → `.pdf` in `docs/quantum/`

---

### QCAT-003 · SVG complex plane

**Status:** done
**File:** `docs/quantum/complex-plane.svg`

**Acceptance criteria:**
- [x] Unit circle, axes, origin dot
- [x] Vectors **u** (22°) and **v** (58°), angle θ arc
- [x] cos θ and sin θ dashed projections
- [x] Euler identity box: `e^{iθ} = cos θ + i sin θ`
- [x] Dirac/quantum row: `|ψ⟩ = Σαₖ|k⟩ · â†|n⟩ = √(n+1)|n+1⟩`
- [x] Code table strip: `AAAA·BBBB·CCCC·DDDD·EEEE·FFFFF`
- [x] Ξ chain label: `bubbleLeader…paulGraham`
- [ ] Export `.png` at 2× for README embed

---

### QCAT-004 · XML catalog with embedded MathML

**Status:** done
**File:** `docs/quantum/quantum-catalog.xml`

**Acceptance criteria:**
- [x] `<code-tables>` — AAAA…FFFFF with inline MathML per entry
- [x] `<quantum-stack>` — operator elements with MathML â† formula
- [x] `<quantum-queue>` — Grover O(√n) and quantum bubble-sort O(n^{3/2})
- [x] `<cosine-similarity-chain>` — MathML formula + 7 chain steps
- [x] `<bubble-leader-chain>` — 13 `<layer>` elements, monad bind, Gödel, Escher
- [x] DCAT / SKOS / SBVR / PROV-O / OWL namespace declarations
- [ ] Validate against `docs/xml/quantum-catalog.xsd` (schema to be created)
- [ ] Wire `collibra-id` attributes once `collibra().init()` is run

---

## E3 · gRPC-HTTP Persistence Bridge

### GRPC-001 · grpc-gateway annotations in `persistence.proto`

**Status:** open
**File:** `uniWork/persistence/proto/persistence.proto`

**Acceptance criteria:**
- [ ] Add `google/api/annotations.proto` import
- [ ] Annotate all 6 RPCs with `option (google.api.http)` matching `chip-queries.xml` bindings
- [ ] Regenerate `persistence.pb.go` and `persistence.pb.gw.go`
- [ ] Gateway listens on `:9090`; gRPC on `:50051`

---

### GRPC-002 · Go gateway server

**Status:** open
**File:** `uniWork/persistence/go/` (new: `gateway.go`)

**Acceptance criteria:**
- [ ] `go run gateway.go` starts grpc-gateway reverse proxy on `:9090`
- [ ] Routes HTTP JSON to gRPC handlers (Clojure JVM or Rust)
- [ ] `Content-Type: application/json` + `X-Singine-Rpc` header
- [ ] Health endpoint `GET /healthz`

---

### GRPC-003 · Go chip_queries entry point

**Status:** done (XML parse + JVM discovery)
**File:** `uniWork/persistence/go/chip_queries.go`

**Acceptance criteria:**
- [x] Parses `docs/xml/chip-queries.xml` via `encoding/xml`
- [x] `WorkspaceDepth`, `CodeLookupRequest`, `TypeRetrieval`, `GrpcHttpRequest`, `JProfilerTarget` types
- [x] `discoverJVMTargets()` via `jps -l` with pattern matching from grammar
- [x] CLI commands: `status`, `jprofiler-targets`, `grpc-bindings`
- [ ] `go mod init github.com/sindoc/collibra/persistence` + `go.mod`
- [ ] `make go-build` target in `uniWork/persistence/Makefile`

---

## E4 · JProfiler JVM Attach

### JPRO-001 · Groovy attach script

**Status:** done
**File:** `uniWork/persistence/groovy/JProfilerAttach.groovy`

**Acceptance criteria:**
- [x] `status` — reflects `Controller.isAgentActive()` via reflection; graceful if agent absent
- [x] `start` — `Controller.startCPURecording(true)`
- [x] `stop [dir]` — `Controller.stopCPURecording()` + `saveSnapshot(file)`
- [x] JSON output on stdout
- [ ] `groovy JProfilerAttach.groovy status` integration test (CI)
- [ ] `make jprofiler-groovy-status` target

---

### JPRO-002 · Clojure attach namespace

**Status:** done
**File:** `uniWork/persistence/clojure/src/persistence/jprofiler.clj`

**Acceptance criteria:**
- [x] `(status)` — reflection on `com.jprofiler.api.agent.Controller`; fallback map if absent
- [x] `(start-cpu-recording label)` — `Controller/startCPURecording`
- [x] `(stop-and-snapshot dir)` — stop + `saveSnapshot`
- [x] `-main` — `status | start | stop` dispatch
- [ ] Add `com.jprofiler/jprofiler-api` to `project.clj` as `provided` scope
- [ ] `lein run -m persistence.jprofiler status` smoke test

---

### JPRO-003 · JVM agent startup flags

**Status:** open

**Acceptance criteria:**
- [ ] Document `-agentpath` flags in `uniWork/persistence/groovy/README.md`
- [ ] Add `JPROFILER_AGENT` env var to `uniWork/persistence/Makefile`
- [ ] Groovy and Clojure `make` targets honour `JPROFILER_AGENT` if set

---

## E5 · Code Tables + Shiva Base Layer

### SHIV-001 · `loadCodeTableFromBaseFromShiva()` — domain layer integration

**Status:** done (in-memory); **open** (SQLite persistence)
**File:** `singine-collibra/python/singine_collibra/quantum_catalog.py`

**Acceptance criteria:**
- [x] In-memory: AAAA / BBBB / CCCC / DDDD / EEEE / FFFFF entries
- [ ] Persist to `singine domain master add` (humble-idp.db) via `singine domain refdata add`
- [ ] CLI: `singine collibra refdata load-shiva --db $SINGINE_DOMAIN_DB`
- [ ] `collibra().init()` calls `loadCodeTableFromBaseFromShiva()` and registers assets

---

### SHIV-002 · Register AAAA…FFFFF in Collibra

**Status:** open
**Depends on:** SHIV-001, Collibra instance running

**Acceptance criteria:**
- [ ] POST each `CodeEntry` to `/rest/2.0/assets` as Business Term / Reference Data
- [ ] Populate `collibra_id` in `quantum-catalog.xml`
- [ ] `singine collibra id gen --ns c --project QuantumCatalog` for each entry
- [ ] Governance decision: `singine decide quantum-catalog --decision approved`

---

## E6 · BubbleLeader Builder Chain

### BUBL-001 · Full 13-layer chain — Python

**Status:** done
**File:** `singine-collibra/python/singine_collibra/quantum_catalog.py`

**Acceptance criteria:**
- [x] `bubbleLeader(items)` — bubble-sort, float max to top
- [x] `.builder()` GoF factory accumulation
- [x] `.piotr()` coordination
- [x] `.groovy()` / `.clojure()` / `.c()` language layer tags
- [x] `.f()` F-algebra / fixed-point functor
- [x] `.math()` CAS symbolic flag
- [x] `.godel()` Gödel number: `∏ pⱼ^aⱼ`
- [x] `.escher()` Y-combinator fixed point
- [x] `.pg()` × 2 (PostgreSQL, then Paul Graham)
- [x] `.paulGraham()` LISP primitives terminal eval
- [x] `.build()` returns `{chain: [...], result: {...}}`

---

### BUBL-002 · Groovy + Clojure implementations of chain layers

**Status:** open

**Acceptance criteria:**
- [ ] Groovy: `BubbleLeaderChain.groovy` — mirror `.groovy()` and `.clojure()` layer behaviour
- [ ] Clojure: `(ns persistence.bubble-leader)` — pure functional chain using `->>`
- [ ] Both emit JSON trace compatible with `chip_queries.py` `LambdaExec.try_catch_claude()`

---

## E7 · Cosine Similarity → Collibra

### COS-001 · `CosineChain` — full 7-step fluent chain

**Status:** done
**File:** `singine-collibra/python/singine_collibra/quantum_catalog.py`

**Acceptance criteria:**
- [x] `.similarity()` — Re(⟨u,v⟩)/(|u||v|) in ℂⁿ
- [x] `.complex()` — compute arg(z) = phase of similarity
- [x] `.resolve()` — angle → code table → IRI `urn:singine:quantum:<domain>:<CODE>`
- [x] `.xml()` — serialize as `<cosine-similarity iri=... re=... im=... angle_rad=... cos_theta=.../>`
- [x] `.catalog()` — DCAT `dcat:Dataset` entry dict
- [x] `.collibra()` — final envelope with `mcp_tool: "collibra/code_lookup"`
- [ ] Wire into `chip_queries.py` `CodeLookupQuery.type_retrieval()` as post-processor

---

### COS-002 · Quantum-cosine similarity in SPARQL bridge

**Status:** open
**Depends on:** `singine bridge sparql`

**Acceptance criteria:**
- [ ] `singine bridge sparql` accepts complex vector literals
- [ ] `SELECT ?s WHERE { ?s singine:cosSim ?v FILTER(singine:cosTheta(?s,?v) > 0.85) }`
- [ ] Backed by `cosine_similarity_complex()` from `quantum_catalog.py`

---

## Tech Debt

| ID | Item | Priority |
|----|------|----------|
| TD-001 | `go.mod` for `uniWork/persistence/go/` | medium |
| TD-002 | XSD schema for `quantum-catalog.xml` | low |
| TD-003 | `pdflatex` CI step for `chip-quantum-catalog.tex` | low |
| TD-004 | `.png` export of `complex-plane.svg` for README | low |
| TD-005 | Integration test: Python `grpc_http_call` → Go gateway → Clojure | high |
| TD-006 | `make jprofiler-*` targets in persistence `Makefile` | medium |

---

## File Index (this session)

| File | Epic | Status |
|------|------|--------|
| `docs/xml/chip-queries.xml` | E1 | done |
| `singine-collibra/python/singine_collibra/chip_queries.py` | E1 | done |
| `uniWork/persistence/go/chip_queries.go` | E3 | done |
| `uniWork/persistence/groovy/JProfilerAttach.groovy` | E4 | done |
| `uniWork/persistence/clojure/src/persistence/jprofiler.clj` | E4 | done |
| `singine-collibra/python/singine_collibra/quantum_catalog.py` | E2 | done |
| `docs/quantum/chip-quantum-catalog.tex` | E2 | done |
| `docs/quantum/complex-plane.svg` | E2 | done |
| `docs/quantum/quantum-catalog.xml` | E2 | done |
