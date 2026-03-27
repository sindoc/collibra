# Makefile — repository-level generated artefacts and documentation helpers

SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

REPO_ROOT := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
PYTHON    ?= python3

AGENT_XML      := $(REPO_ROOT)/docs/xml/singine-agent-contract.xml
AGENT_GEN      := $(REPO_ROOT)/scripts/generate_agent_docs.py
AGENT_DOCS     := $(REPO_ROOT)/CODEX.md $(REPO_ROOT)/CLAUDE.md $(REPO_ROOT)/AGENTS.md
WATCH_INPUTS   := $(AGENT_XML) $(AGENT_GEN)

.PHONY: help agent-docs agent-docs-force agent-docs-check agent-docs-watch

$(REPO_ROOT)/CODEX.md $(REPO_ROOT)/CLAUDE.md $(REPO_ROOT)/AGENTS.md: $(AGENT_XML) $(AGENT_GEN)
	@cd $(REPO_ROOT) && $(PYTHON) $(AGENT_GEN)

agent-docs: $(AGENT_DOCS)
	@echo "Agent markdown files are aligned with $(AGENT_XML)."

agent-docs-force:
	@cd $(REPO_ROOT) && $(PYTHON) $(AGENT_GEN)

agent-docs-check:
	@tmp_dir="$$(mktemp -d)"; \
	cp $(AGENT_DOCS) "$$tmp_dir"/; \
	cd $(REPO_ROOT) && $(PYTHON) $(AGENT_GEN) >/dev/null; \
	if diff -q $(REPO_ROOT)/CODEX.md "$$tmp_dir"/CODEX.md >/dev/null \
	  && diff -q $(REPO_ROOT)/CLAUDE.md "$$tmp_dir"/CLAUDE.md >/dev/null \
	  && diff -q $(REPO_ROOT)/AGENTS.md "$$tmp_dir"/AGENTS.md >/dev/null; then \
	  echo "Agent markdown files are up to date."; \
	  rm -rf "$$tmp_dir"; \
	else \
	  echo "Agent markdown files are out of date. Run: make agent-docs"; \
	  rm -rf "$$tmp_dir"; \
	  exit 1; \
	fi

agent-docs-watch:
	@if command -v fswatch >/dev/null 2>&1; then \
	  printf "%s\n" $(WATCH_INPUTS) | fswatch -0 --event Updated --event Created --event Removed | \
	  while IFS= read -r -d '' _; do \
	    $(MAKE) agent-docs-force; \
	  done; \
	elif command -v entr >/dev/null 2>&1; then \
	  printf "%s\n" $(WATCH_INPUTS) | entr -r $(MAKE) agent-docs-force; \
	else \
	  echo "Install fswatch or entr to use agent-docs-watch."; \
	  exit 1; \
	fi

help:
	@printf '%s\n' \
	  'Repository-level targets' \
	  '' \
	  '  make agent-docs        Regenerate CODEX.md, CLAUDE.md, and AGENTS.md from docs/xml/singine-agent-contract.xml' \
	  '  make agent-docs-force  Regenerate regardless of timestamps' \
	  '  make agent-docs-check  Fail if generated agent markdown files are stale' \
	  '  make agent-docs-watch  Watch the XML contract and generator, then regenerate on change'
