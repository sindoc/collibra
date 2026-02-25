# Makefile — Bootstrap Agent: Edge Cap Investment Maturity Model
# Orchestrates handshake validation, asset creation, and metrics capture
# for the investment maturity migration path in Collibra.

BASE_DIR             := ..
CSRF_TOKEN_FILE      := $(BASE_DIR)/X-CSRF-TOKEN
JSESSIONID_FILE      := $(BASE_DIR)/JSESSIONID
COLLIBRA_BASE_URL_FILE := $(BASE_DIR)/CollibraBaseUrl
REST_PATH_FILE       := ./RestPath

CSRF_TOKEN           := $(shell head -1 $(CSRF_TOKEN_FILE))
JSESSIONID           := $(shell head -1 $(JSESSIONID_FILE))
COLLIBRA_BASE_URL    := $(shell cat $(COLLIBRA_BASE_URL_FILE))
REST_PATH            := $(shell cat $(REST_PATH_FILE))
FULL_URL             := $(COLLIBRA_BASE_URL)$(REST_PATH)

JSON_PAYLOAD         := $(shell ./generate_payload.sh)

.PHONY: bootstrap createInvestmentMaturityAssets validateHandshake \
        showConfig showMetrics showLineage help

# ── Primary entry point ────────────────────────────────────────────────────────
bootstrap:
	@chmod +x bootstrap.sh handshake/validate.sh handshake/log_entry.sh \
	           edgeCap/snapshots/generate_snapshot.sh generate_payload.sh
	@bash bootstrap.sh

# ── Asset creation ─────────────────────────────────────────────────────────────
createInvestmentMaturityAssets:
	curl -X 'POST' \
	  '$(FULL_URL)' \
	  -H 'accept: application/json' \
	  -H 'Content-Type: application/json' \
	  -H 'X-CSRF-TOKEN: $(CSRF_TOKEN)' \
	  --cookie 'JSESSIONID=$(JSESSIONID); XSRF-TOKEN=$(CSRF_TOKEN)' \
	  -d '$(JSON_PAYLOAD)'

# ── Handshake only ─────────────────────────────────────────────────────────────
validateHandshake:
	@chmod +x handshake/validate.sh
	@bash handshake/validate.sh "manual-run" "/dev/stderr"

# ── Inspection targets ─────────────────────────────────────────────────────────
showConfig:
	@echo "Collibra URL : $(COLLIBRA_BASE_URL)"
	@echo "REST Path    : $(REST_PATH)"
	@echo "Full URL     : $(FULL_URL)"

showMetrics:
	@echo "=== Baseline ===" && cat metrics/baseline.json
	@echo "=== Targets  ===" && cat metrics/targets.json

showLineage:
	@echo "=== Migration Path ===" && cat lineage/migration_path.json
	@echo "=== Control Imperatives ===" && cat lineage/control_imperatives.json

showEdgeCap:
	@cat edgeCap/model.json

# ── Help ───────────────────────────────────────────────────────────────────────
help:
	@echo "Bootstrap Agent — Edge Cap Investment Maturity"
	@echo ""
	@echo "Targets:"
	@echo "  bootstrap                    Run full bootstrap (handshake → assets → snapshot)"
	@echo "  createInvestmentMaturityAssets  POST maturity level assets to Collibra"
	@echo "  validateHandshake            Validate connection to Collibra endpoint"
	@echo "  showConfig                   Print resolved URL config"
	@echo "  showMetrics                  Print baseline and target metrics"
	@echo "  showLineage                  Print migration path and control imperatives"
	@echo "  showEdgeCap                  Print edge cap model"
