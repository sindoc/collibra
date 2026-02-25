# Makefile — Singine smtpAgent
# Multi-layer SMTP agent: C (TCP) + Clojure/JVM (SMTP) + Python (Web UI)
#
# Quickstart:
#   make bootstrap        # install deps, build everything
#   export SMTP_USER=you@gmail.com SMTP_PASS=your-app-password
#   make start            # launch all three layers
#
# Individual layers:
#   make start-c          # C TCP acceptor on :8025
#   make start-clojure    # Clojure SMTP service on :8026
#   make start-python     # Python web UI on :8080
#
# Browser (iPad):  http://<machine-ip>:8080

SHELL := /bin/bash
.DEFAULT_GOAL := help

LEIN     := $(shell command -v lein 2>/dev/null || echo $(HOME)/.local/bin/lein)
PYTHON   := python3
PID_DIR  := .pids
LOG_DIR  := logs

# ── Bootstrap ─────────────────────────────────────────────────────────────────
.PHONY: bootstrap
bootstrap:
	@bash meta/bootstrap.sh

# ── Build ─────────────────────────────────────────────────────────────────────
.PHONY: build build-c build-clojure build-python
build: build-c build-clojure

build-c:
	@$(MAKE) -C c all

build-clojure:
	@(cd clojure && $(LEIN) uberjar)

build-python:
	@$(PYTHON) -m pip install --quiet -r python/requirements.txt
	@echo "Python packages ready."

# ── Start all layers ──────────────────────────────────────────────────────────
.PHONY: start
start: start-clojure start-python start-c
	@echo ""
	@echo "=== Singine smtpAgent running ==="
	@echo "  Web UI (iPad browser): http://0.0.0.0:8080"
	@echo "  SMTP service (loopback): http://127.0.0.1:8026"
	@echo "  C TCP relay (loopback):  127.0.0.1:8025"
	@echo ""
	@echo "Logs: $(LOG_DIR)/"

# ── Individual layer starts (background) ─────────────────────────────────────
.PHONY: start-c
start-c: build-c | $(PID_DIR) $(LOG_DIR)
	@if [[ -f $(PID_DIR)/accept_tcp.pid ]]; then \
	  echo "C TCP acceptor already running (PID $$(cat $(PID_DIR)/accept_tcp.pid))"; \
	else \
	  ./c/bin/accept_tcp 127.0.0.1 8025 >>$(LOG_DIR)/tcp_accept.log 2>&1 & \
	  echo $$! > $(PID_DIR)/accept_tcp.pid; \
	  echo "C TCP acceptor started (PID $$!)"; \
	fi

.PHONY: start-clojure
start-clojure: | $(PID_DIR) $(LOG_DIR)
	@if [[ -f $(PID_DIR)/clojure.pid ]]; then \
	  echo "Clojure SMTP service already running (PID $$(cat $(PID_DIR)/clojure.pid))"; \
	else \
	  SINGINE_META_CONFIG=../meta/config.edn \
	  (cd clojure && $(LEIN) run) >>$(LOG_DIR)/smtp.log 2>&1 & \
	  echo $$! > $(PID_DIR)/clojure.pid; \
	  echo "Clojure SMTP service started (PID $$!)"; \
	fi

.PHONY: start-python
start-python: | $(PID_DIR) $(LOG_DIR)
	@if [[ -f $(PID_DIR)/python.pid ]]; then \
	  echo "Python web server already running (PID $$(cat $(PID_DIR)/python.pid))"; \
	else \
	  (cd python && $(PYTHON) server.py) >>$(LOG_DIR)/web.log 2>&1 & \
	  echo $$! > $(PID_DIR)/python.pid; \
	  echo "Python web UI started (PID $$!) → http://0.0.0.0:8080"; \
	fi

# ── Stop all layers ───────────────────────────────────────────────────────────
.PHONY: stop
stop:
	@for pid_file in $(PID_DIR)/*.pid; do \
	  [[ -f "$$pid_file" ]] || continue; \
	  pid=$$(cat "$$pid_file"); \
	  name=$$(basename "$$pid_file" .pid); \
	  if kill -0 "$$pid" 2>/dev/null; then \
	    kill "$$pid" && echo "Stopped $$name (PID $$pid)"; \
	  fi; \
	  rm -f "$$pid_file"; \
	done

# ── Status ────────────────────────────────────────────────────────────────────
.PHONY: status
status:
	@echo "=== Layer status ==="
	@for pid_file in $(PID_DIR)/*.pid; do \
	  [[ -f "$$pid_file" ]] || continue; \
	  pid=$$(cat "$$pid_file"); \
	  name=$$(basename "$$pid_file" .pid); \
	  if kill -0 "$$pid" 2>/dev/null; then \
	    echo "  ✓ $$name  (PID $$pid)"; \
	  else \
	    echo "  ✗ $$name  (dead — stale PID $$pid)"; \
	  fi; \
	done
	@echo "=== HTTP probes ==="
	@curl -sf http://127.0.0.1:8026/ping && echo " Clojure :8026 OK" || echo " Clojure :8026 OFFLINE"
	@curl -sf http://127.0.0.1:8080/ping && echo " Python  :8080 OK" || echo " Python  :8080 OFFLINE"

# ── Logs ──────────────────────────────────────────────────────────────────────
.PHONY: logs
logs:
	@tail -f $(LOG_DIR)/*.log

# ── Clean ─────────────────────────────────────────────────────────────────────
.PHONY: clean
clean: stop
	@$(MAKE) -C c clean
	@rm -rf clojure/target
	@echo "Clean complete."

# ── Helpers ───────────────────────────────────────────────────────────────────
$(PID_DIR) $(LOG_DIR):
	mkdir -p $@

.PHONY: help
help:
	@echo "Singine smtpAgent — multi-layer SMTP via C + Clojure/JVM + Python"
	@echo ""
	@echo "Setup:"
	@echo "  make bootstrap          Install lein, pip packages, build C binary"
	@echo "  export SMTP_USER=...    Gmail/SMTP address"
	@echo "  export SMTP_PASS=...    App password (not your Google password)"
	@echo ""
	@echo "Run:"
	@echo "  make start              Launch all three layers"
	@echo "  make start-python       Web UI only (iPad browser → :8080)"
	@echo "  make start-clojure      SMTP service only (:8026)"
	@echo "  make start-c            TCP relay only (:8025)"
	@echo "  make stop               Stop all layers"
	@echo "  make status             Show layer + HTTP health"
	@echo "  make logs               Tail all log files"
	@echo ""
	@echo "Browser (iPad):  http://<this-machine-ip>:8080"
	@echo "SMTP config:     meta/config.edn"
