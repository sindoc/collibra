# Makefile — Edge Server Agent
#
# Lifecycle targets for the Claude API edge-agent application.
# All targets are invokable directly or via:
#   singine runtime exec-external make -C ~/ws/git/github/sindoc/collibra/edge/agent [TARGET]
#
#   make prepare      → create venv, install Python dependencies
#   make install      → install dependencies + register governance decision
#   make run          → run agent with default task (set TASK= to override)
#   make run-task     → run agent with TASK= argument (required)
#   make validate     → run tool smoke-test without API call
#   make clean        → remove venv and output artefacts
#   make status       → show venv and package status

AGENT_DIR   := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
VENV        := $(AGENT_DIR)/.venv
PYTHON      := $(VENV)/bin/python3
PIP         := $(VENV)/bin/pip
AGENT       := $(AGENT_DIR)/edge_agent.py
OUTPUT_DIR  := $(AGENT_DIR)/output

DEFAULT_TASK := Generate a complete Collibra edge server stack for RHEL 7.9: \
  Kubernetes Deployment and Service for collibra-edge, \
  OpenShift Route with TLS edge termination, \
  firewalld zone XML for required ports, \
  and a systemd unit for the Collibra DGC edge service.

.PHONY: all prepare install run run-task validate clean status

all: prepare

# ── Prepare ───────────────────────────────────────────────────────────────────
prepare: $(VENV)/bin/python3

$(VENV)/bin/python3:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip --quiet
	$(PIP) install -r $(AGENT_DIR)/requirements.txt --quiet
	@echo ""
	@echo "Virtualenv ready: $(VENV)"
	@echo "Packages installed from requirements.txt"

# ── Install (prepare + governance registration) ───────────────────────────────
install: prepare
	@echo ""
	@echo "Registering governance decision for edge-agent ..."
	singine decide edge-agent \
	  --decision approve \
	  --reason "Edge agent installed and ready: Kubernetes/OpenShift/RHEL7/Collibra edge" \
	  --json 2>/dev/null \
	  || python3 -c "\
import json, datetime, os; \
ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'); \
uid = 'edge-agent'; \
rec = {'ok': True, 'urn': f'urn:singine:decision:{uid}:{ts}', \
       'id': uid, 'decision': 'approve', 'ts': ts, 'source': 'local-fallback'}; \
os.makedirs(os.path.expanduser('~/.singine/decisions'), exist_ok=True); \
open(os.path.expanduser(f'~/.singine/decisions/{uid}.json'), 'w').write(json.dumps(rec, indent=2)); \
print(rec['urn'])"
	@echo ""
	@echo "edge-agent installed."

# ── Run (default task) ────────────────────────────────────────────────────────
run: prepare
	@mkdir -p $(OUTPUT_DIR)
	$(PYTHON) $(AGENT) \
	  --task "$(DEFAULT_TASK)" \
	  --output-dir $(OUTPUT_DIR)

# ── Run (custom task via TASK= variable) ──────────────────────────────────────
run-task: prepare
ifndef TASK
	$(error TASK is not set. Usage: make run-task TASK="your task description")
endif
	@mkdir -p $(OUTPUT_DIR)
	$(PYTHON) $(AGENT) \
	  --task "$(TASK)" \
	  --output-dir $(OUTPUT_DIR)

# ── Validate (tool smoke-test, no API call) ───────────────────────────────────
validate: prepare
	$(PYTHON) -c "\
import sys, json, pathlib; \
sys.path.insert(0, '$(AGENT_DIR)'); \
import tools as t; \
t.set_output_dir(pathlib.Path('/tmp/edge-agent-validate')); \
import edge_agent as ea; \
schemas = ea._collect_raw_schemas(); \
assert len(schemas) == 6, f'Expected 6 tool schemas, got {len(schemas)}'; \
r = t.generate_kubernetes_manifest(component='test', image='test:1', resource_kind='Deployment'); \
assert 'manifest' in r; \
r = t.validate_rhel_compatibility(rhel_version='7.9', packages=json.dumps(['yum'])); \
assert r['ok'] is True; \
r = t.generate_collibra_edge_config(hostname='h', dgc_url='https://dgc'); \
assert 'systemd_unit' in r; \
print('All tool smoke-tests passed. tools.py and edge_agent.py are healthy.')"

# ── Status ────────────────────────────────────────────────────────────────────
status:
	@echo "=== edge-agent status ==="
	@echo "Agent dir   : $(AGENT_DIR)"
	@echo "Venv        : $(VENV)"
	@if [ -f $(PYTHON) ]; then \
	  echo "Python      : $$($(PYTHON) --version)"; \
	  echo "anthropic   : $$($(PIP) show anthropic 2>/dev/null | grep Version || echo 'not installed')"; \
	else \
	  echo "Python      : venv not created (run: make prepare)"; \
	fi
	@echo "Output dir  : $(OUTPUT_DIR)"
	@if [ -d $(OUTPUT_DIR) ]; then \
	  echo "Artifacts   : $$(ls $(OUTPUT_DIR) | wc -l | tr -d ' ') file(s)"; \
	else \
	  echo "Artifacts   : (none — output dir does not exist)"; \
	fi
	@python3 -c \
	  "import json,os; f=os.path.expanduser('~/.singine/decisions/edge-agent.json'); \
	   d=json.load(open(f)) if os.path.exists(f) else {}; \
	   print('Decision    :', d.get('urn','(not registered)'))"

# ── Clean ─────────────────────────────────────────────────────────────────────
clean:
	rm -rf $(VENV) $(OUTPUT_DIR) $(AGENT_DIR)/__pycache__
	@echo "Cleaned venv and output artefacts."
