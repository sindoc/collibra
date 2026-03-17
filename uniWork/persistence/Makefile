# Makefile — Singine persistence layer
# Orchestrates: schema migrations · Rust engine · Python tools · Clojure JVM
#
# Quick start (dev):
#   make migrate          Apply SQL migrations to singine.db
#   make analyze          Analyze HEAD commit (raw → base → master)
#   make path src=A dst=B Compute shortest path between two gen_ids
#   make status           Show DB + layer health

SHELL    := /bin/bash
PYTHON   := python3
LEIN     := $(shell command -v lein 2>/dev/null || echo $(HOME)/.local/bin/lein)
RUST_BIN := rust/target/release/persistence
SQLITE   := singine.db
SCHEMA   := schema
LOGS     := logs

.PHONY: all migrate analyze path status semantic ldap rust-build clojure-run \
        ipad-url help clean

all: migrate

# ── Schema migrations ─────────────────────────────────────────────────────────
migrate: | $(LOGS)
	@echo "=== Phase 2: Schema migration (raw → base) ==="
	$(PYTHON) python/migrate.py \
	  --db "$(SQLITE)" \
	  --migrations "$(SCHEMA)" \
	  --env dev

# ── Commit analysis ───────────────────────────────────────────────────────────
analyze: migrate | $(LOGS)
	@echo "=== Phase 3: Commit analysis (base → master) ==="
	$(PYTHON) logseq/analyze_commit.py \
	  --db     "$(SQLITE)" \
	  --commit "$$(git rev-parse HEAD)" \
	  --branch "$$(git rev-parse --abbrev-ref HEAD)" \
	  --author "$$(git log -1 --format='%aN')" \
	  --repo   "sindoc/collibra"

# ── Rust shortest-path ────────────────────────────────────────────────────────
rust-build:
	cargo build --release --manifest-path rust/Cargo.toml

path: rust-build
	@echo "=== Phase 4: Shortest path $(src) → $(dst) ==="
	./$(RUST_BIN) --db "$(SQLITE)" --mode shortest-path \
	  --src "$(src)" --dst "$(dst)"

gen-id:
	./$(RUST_BIN) --db "$(SQLITE)" --mode gen-id --namespace "$(ns)"

# ── Clojure categories + similarity ──────────────────────────────────────────
clojure-run: | $(LOGS)
	@echo "=== Phase 5: Clojure categories + similarity ==="
	(cd clojure && SINGINE_DB="../$(SQLITE)" $(LEIN) run --mode categorise)
	(cd clojure && SINGINE_DB="../$(SQLITE)" $(LEIN) run --mode similarity)

# ── Semantic web (FOAF/DOAP/RSS) ─────────────────────────────────────────────
semantic: migrate
	$(PYTHON) python/foaf_doap.py \
	  --db     "$(SQLITE)" \
	  --commit "$$(git rev-parse HEAD)" \
	  --branch "$$(git rev-parse --abbrev-ref HEAD)" \
	  --output "semantic-web"
	@echo "Outputs in semantic-web/: project.ttl · feed.rss · commit.jsonld"

# ── LDAP tree ─────────────────────────────────────────────────────────────────
ldap:
	$(PYTHON) python/ldap_tree.py --db "$(SQLITE)" --json

# ── Status ────────────────────────────────────────────────────────────────────
status:
	@echo "=== DB tables ==="
	@sqlite3 "$(SQLITE)" ".tables" 2>/dev/null || echo "(DB not yet initialised — run make migrate)"
	@echo "=== Schema versions ==="
	@sqlite3 "$(SQLITE)" \
	  "SELECT version,description,applied_at FROM schema_migrations ORDER BY version;" \
	  2>/dev/null || true
	@echo "=== Lineage count ==="
	@sqlite3 "$(SQLITE)" "SELECT phase,COUNT(*) FROM lineage GROUP BY phase;" 2>/dev/null || true

# ── iPad URL ──────────────────────────────────────────────────────────────────
ipad-url:
	@IP=$$(hostname -I 2>/dev/null | awk '{print $$1}' || \
	       ipconfig getifaddr en0 2>/dev/null || echo "<machine-ip>"); \
	echo ""; \
	echo "  ╔══════════════════════════════════════════╗"; \
	echo "  ║  Open on iPad Safari:                    ║"; \
	echo "  ║  http://$$IP:8080                        ║"; \
	echo "  ╚══════════════════════════════════════════╝"; \
	echo ""; \
	echo "  (Ensure smtpAgent is running: make -C ../smtpAgent start)"

# ── Full pipeline ─────────────────────────────────────────────────────────────
pipeline: migrate analyze semantic ldap
	@echo "=== Full Singine pipeline complete ==="

# ── Clean ─────────────────────────────────────────────────────────────────────
clean:
	rm -f "$(SQLITE)"
	rm -rf semantic-web/ clojure/target rust/target
	@echo "Clean."

$(LOGS):
	mkdir -p $@

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo "Singine persistence layer"
	@echo ""
	@echo "  make migrate             Apply SQL migrations to $(SQLITE)"
	@echo "  make analyze             Analyze HEAD commit (raw→base→master)"
	@echo "  make path src=X dst=Y   Shortest path between gen_ids (Rust)"
	@echo "  make gen-id ns=<ns>     Generate inode-style ID for namespace"
	@echo "  make clojure-run         Categories + similarity (JVM)"
	@echo "  make semantic            FOAF/DOAP/RSS output"
	@echo "  make ldap                Print LDAP entity tree"
	@echo "  make status              DB health + schema versions"
	@echo "  make pipeline            Full pipeline (migrate+analyze+semantic+ldap)"
	@echo "  make ipad-url            Show iPad browser URL for smtpAgent UI"
	@echo ""
	@echo "GitHub Action: .github/workflows/chain_of_command.yml"
	@echo "triggers on: push to claude/**, main, master"
