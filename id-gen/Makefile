# id-gen Makefile — Collibra contract ID generator + ORM/SBVR pipeline
# Usage: make help

SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

# ── paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR  := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
ID_GEN      := $(SCRIPT_DIR)/id_gen.sh
NAMESPACES  := $(SCRIPT_DIR)/namespaces.sh
CONTRACT    := $(SCRIPT_DIR)/contracts/generate_contract.sh
TRACKER     := $(SCRIPT_DIR)/contracts/workflow_tracker.sh
TRIGGER     := $(SCRIPT_DIR)/collibra/trigger.sh
SPARQL      := $(SCRIPT_DIR)/collibra/sparql_to_contract.sh
METAMODEL   := $(SCRIPT_DIR)/collibra/metamodel_7step.sh
SERVER      := $(SCRIPT_DIR)/server/server.sh
STORE       := $(SCRIPT_DIR)/contracts/store

# ── config (overridable) ──────────────────────────────────────────────────────
PROJECT     ?= DefaultProject
KIND        ?= DataContract
MODE        ?= net
PORT        ?= 7331
NS          ?= c
STRATEGY    ?= COLLIBRA_WINS

# Pre-registered SSH identity: sina@neille.mac.collibra.com
SSH_KEY     ?= $(shell cat $(SCRIPT_DIR)/server/.server.ssh_key 2>/dev/null | head -1)

# ── init ──────────────────────────────────────────────────────────────────────
.PHONY: init
init:
	@chmod +x $(ID_GEN) $(NAMESPACES) $(CONTRACT) $(TRACKER) \
	           $(TRIGGER) $(SPARQL) $(METAMODEL) $(SERVER) \
	           $(SCRIPT_DIR)/server/server.sh
	@mkdir -p $(STORE) $(SCRIPT_DIR)/ui/logseq/logs $(SCRIPT_DIR)/namespaces
	@echo "id-gen initialized."

# ── ID generation ─────────────────────────────────────────────────────────────
.PHONY: gen
gen: init
	@$(ID_GEN) gen $(NS) contract "$(PROJECT)"

.PHONY: gen-topic
gen-topic: init
	@$(NAMESPACES) topic "$(PROJECT)"

.PHONY: import-collibra
import-collibra: init
	@$(NAMESPACES) import "$(UUID)" "$(KIND)" "$(PROJECT)"

.PHONY: ns-list
ns-list:
	@$(NAMESPACES) list all

# ── contract generation ───────────────────────────────────────────────────────
.PHONY: contract
contract: init
	@$(CONTRACT) new "$(PROJECT)" $(KIND) "" "$(SSH_KEY)"

.PHONY: contract-list
contract-list:
	@$(CONTRACT) list

.PHONY: contract-status
contract-status:
	@$(CONTRACT) status "$(CONTRACT_ID)" "$(STATUS)"

# ── workflow tracker ──────────────────────────────────────────────────────────
.PHONY: advance
advance:
	@$(TRACKER) advance "$(CONTRACT_ID)"

.PHONY: progress
progress:
	@$(TRACKER) show "$(CONTRACT_ID)"

.PHONY: progress-all
progress-all:
	@$(TRACKER) all

.PHONY: progress-json
progress-json:
	@$(TRACKER) json "$(CONTRACT_ID)"

# ── 7-step pipeline ───────────────────────────────────────────────────────────
.PHONY: pipeline
pipeline: init contract
	@echo "Running 7-step pipeline for last created contract..."
	@LAST=$$(ls -t $(STORE)/*.json 2>/dev/null | head -1 | xargs basename .json 2>/dev/null | sed 's/\.json//'); \
	 $(METAMODEL) pipeline "$$LAST"

.PHONY: step1 step2 step3 step4 step5 step6 step7
step1: ; @$(METAMODEL) step1 "$(CONTRACT_ID)"
step2: ; @$(METAMODEL) step2 "$(CONTRACT_ID)"
step3: ; @$(METAMODEL) step3 "$(CONTRACT_ID)"
step4: ; @$(METAMODEL) step4 "$(CONTRACT_ID)"
step5: ; @$(METAMODEL) step5 "$(CONTRACT_ID)"
step6: ; @$(METAMODEL) step6 "$(CONTRACT_ID)"
step7: ; @$(METAMODEL) step7 "$(CONTRACT_ID)"

# ── SPARQL → contract ─────────────────────────────────────────────────────────
.PHONY: sparql-translate
sparql-translate: init
	@$(SPARQL) translate "$(PROJECT)" "$(QUERY)" "$(SSH_KEY)"

.PHONY: sparql-templates
sparql-templates:
	@$(SPARQL) template all

# ── Collibra trigger ──────────────────────────────────────────────────────────
.PHONY: poll
poll: init
	@$(TRIGGER) poll "$(SSH_KEY)"

.PHONY: trigger-list
trigger-list:
	@$(TRIGGER) list

# ── git tag operations ────────────────────────────────────────────────────────
.PHONY: tags
tags:
	@$(ID_GEN) list

.PHONY: push-tags
push-tags:
	@$(ID_GEN) push

.PHONY: detect-conflicts
detect-conflicts:
	@$(ID_GEN) detect-conflicts

.PHONY: resolve-conflicts
resolve-conflicts:
	@$(ID_GEN) resolve-all $(STRATEGY)

# ── equation ──────────────────────────────────────────────────────────────────
.PHONY: eq
eq:
	@$(ID_GEN) eq "$(EXPR)" $(or $(MODE_EQ), solve)

# ── server ────────────────────────────────────────────────────────────────────
.PHONY: server-start
server-start: init
	@$(SERVER) start --port $(PORT) --mode $(MODE) \
	  $$([ -n "$(SSH_KEY)" ] && echo "--ssh-key '$(SSH_KEY)'" || true)

.PHONY: server-stop
server-stop:
	@$(SERVER) stop

.PHONY: server-status
server-status:
	@$(SERVER) status

.PHONY: server-dmz
server-dmz: init
	@$(SERVER) start --port $(PORT) --mode dmz \
	  $$([ -n "$(SSH_KEY)" ] && echo "--ssh-key '$(SSH_KEY)'" || true)

# ── UI ────────────────────────────────────────────────────────────────────────
.PHONY: ui
ui:
	@echo "Open ui/progress.html in a browser:"
	@echo "  file://$(SCRIPT_DIR)/ui/progress.html"
	@command -v xdg-open &>/dev/null && xdg-open $(SCRIPT_DIR)/ui/progress.html || true

# ── full demo workflow ────────────────────────────────────────────────────────
.PHONY: demo
demo: init
	@echo "=== id-gen demo: $(PROJECT) ==="
	@ID=$$($(CONTRACT) new "$(PROJECT)" DataContract "" "" | head -1); \
	 echo "Contract: $$ID"; \
	 $(METAMODEL) pipeline "$$ID"; \
	 $(TRACKER) show "$$ID"

# ── help ─────────────────────────────────────────────────────────────────────
.PHONY: help
help:
	@cat <<'HELP'
id-gen — Collibra contract ID generator + ORM/SBVR pipeline

Variables (override with make VAR=value):
  PROJECT=<name>         Topic/project label (default: DefaultProject)
  KIND=DataContract      Contract kind
  CONTRACT_ID=<id>       c.contract.* ID for step operations
  NS=c                   ID namespace: c | a | b
  PORT=7331              Server port
  MODE=net               Server mode: net | dmz
  SSH_KEY=<pubkey>       SSH public key (default: registered sina@neille.mac.collibra.com)
  STRATEGY=COLLIBRA_WINS Conflict resolution strategy
  EXPR=<math-expr>       Expression for equation solver

ID generation:
  make gen               Mint c.contract.* ID + git tag
  make gen-topic         Mint c.topic.* ID for PROJECT
  make import-collibra   Import existing Collibra UUID (UUID=<uuid> KIND=<kind>)
  make ns-list           List all registered IDs

Contracts:
  make contract          Generate new data contract
  make contract-list     List all contracts
  make contract-status   Update status (CONTRACT_ID=... STATUS=...)

7-step pipeline:
  make pipeline          Run full pipeline on latest contract
  make step1..step7      Run individual step (CONTRACT_ID=...)
  make advance           Advance to next step (CONTRACT_ID=...)
  make progress          Show progress bar (CONTRACT_ID=...)
  make progress-all      Show all contract bars
  make progress-json     Export progress as JSON (CONTRACT_ID=...)

SPARQL:
  make sparql-translate  QUERY="..." PROJECT=... → contract
  make sparql-templates  Show SPARQL template library

Collibra:
  make poll              Poll Collibra for approved use cases → contracts
  make trigger-list      List pending use cases

Git:
  make tags              List all id-gen git tags
  make push-tags         Push tags to origin
  make detect-conflicts  Scan for merge conflicts
  make resolve-conflicts Resolve all (STRATEGY=COLLIBRA_WINS|OURS|THEIRS)

Server:
  make server-start      Start in net mode (full API)
  make server-dmz        Start in DMZ mode (restricted)
  make server-stop       Stop server
  make server-status     Server health check

Misc:
  make eq EXPR="x**2+1"  Solve equation
  make ui                Open progress.html in browser
  make demo              Full demo workflow
HELP
