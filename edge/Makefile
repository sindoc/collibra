# Makefile — Collibra edge stack
#
# Image build order: base → edge-site, collibra-edge, cdn (all depend on base)
#
# Targets:
#   make setup                → full automated setup + launch (recommended)
#   make build-base           → build CentOS 7 LTS base image
#   make build-collibra-edge  → build Collibra DGC edge image
#   make build-edge-site      → build edge site server image
#   make build-cdn            → build nginx CDN image
#   make build-mock           → build collibra-edge mock (dev)
#   make build                → build all images in order
#   make up                   → docker compose up -d  (production)
#   make dev                  → docker compose -f dev up -d  (mock DGC)
#   make down                 → docker compose down
#   make logs                 → docker compose logs -f
#   make push REGISTRY=…      → tag and push all images
#   make javadoc              → build Javadoc for edge/java/
#   make agent-validate       → run agent smoke-test (no API call)
#   make agent-run TASK=…     → run edge agent with a custom task
#   make clean                → remove local images and agent artefacts

EDGE_DIR    := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
IMAGE_DIR   := $(EDGE_DIR)/image
AGENT_DIR   := $(EDGE_DIR)/agent
COMPOSE       := docker compose -f $(EDGE_DIR)/docker-compose.yml
COMPOSE_DEV   := docker compose -f $(EDGE_DIR)/docker-compose.dev.yml
COMPOSE_CLOUD := docker compose -f $(EDGE_DIR)/docker-compose.cloud.yml

REGISTRY    ?= localhost
TAG         ?= local

BASE_IMAGE          := sindoc-collibra-edge-base
COLLIBRA_EDGE_IMAGE := sindoc-collibra-edge
EDGE_SITE_IMAGE     := sindoc-collibra-edge-site
CDN_IMAGE           := sindoc-collibra-cdn

JAVA_DIR := $(EDGE_DIR)/java

.PHONY: setup build-base build-collibra-edge build-edge-site build-cdn build-mock build \
        build-edge-site-server \
        up dev cloud down logs push \
        edge-install edge-install-dry-run edge-uninstall \
        javadoc \
        agent-validate agent-run \
        clean

# ── One-command setup and launch ─────────────────────────────────────────────

setup:
	bash $(EDGE_DIR)/scripts/setup.sh --tag $(TAG)

dev-setup:
	bash $(EDGE_DIR)/scripts/setup.sh --dev --tag $(TAG)

# ── Images ────────────────────────────────────────────────────────────────────

build-base:
	docker build \
	  -t $(BASE_IMAGE):$(TAG) \
	  $(IMAGE_DIR)/base

build-collibra-edge: build-base
	docker build \
	  --build-arg REGISTRY="" \
	  --build-arg BASE_TAG=$(TAG) \
	  -t $(COLLIBRA_EDGE_IMAGE):$(TAG) \
	  $(IMAGE_DIR)/collibra-edge

build-edge-site: build-base
	docker build \
	  --build-arg REGISTRY="" \
	  --build-arg BASE_TAG=$(TAG) \
	  -t $(EDGE_SITE_IMAGE):$(TAG) \
	  $(IMAGE_DIR)/edge-site

build-cdn: build-base
	docker build \
	  --build-arg REGISTRY="" \
	  --build-arg BASE_TAG=$(TAG) \
	  -t $(CDN_IMAGE):$(TAG) \
	  $(IMAGE_DIR)/cdn

build-mock:
	docker build -t sindoc-collibra-edge-mock:$(TAG) $(IMAGE_DIR)/collibra-edge-mock

build-edge-site-server:
	$(MAKE) -C $(IMAGE_DIR)/edge-site/server install

build: build-base build-collibra-edge build-edge-site build-cdn

# ── Edge Kubernetes install (Docker Desktop K8s + Helm) ──────────────────────

edge-install:
	bash $(EDGE_DIR)/scripts/install-edge-k8s.sh

edge-install-dry-run:
	bash $(EDGE_DIR)/scripts/install-edge-k8s.sh --dry-run

edge-uninstall:
	bash $(EDGE_DIR)/scripts/install-edge-k8s.sh --uninstall

# ── Javadoc ───────────────────────────────────────────────────────────────────

javadoc:
	cd $(JAVA_DIR) && ./gradlew javadoc
	@echo "Javadoc written to $(JAVA_DIR)/build/docs/javadoc/"

# ── Stack ─────────────────────────────────────────────────────────────────────

up:
	$(COMPOSE) up -d

dev:
	$(COMPOSE_DEV) --env-file $(EDGE_DIR)/.env up -d

cloud:
	$(COMPOSE_CLOUD) --env-file $(EDGE_DIR)/.env up -d

down:
	-$(COMPOSE) down 2>/dev/null || true
	-$(COMPOSE_DEV) down 2>/dev/null || true
	-$(COMPOSE_CLOUD) down 2>/dev/null || true

logs:
	$(COMPOSE) logs -f

# ── Registry push ─────────────────────────────────────────────────────────────

push: build
	docker tag $(BASE_IMAGE):$(TAG)          $(REGISTRY)/$(BASE_IMAGE):$(TAG)
	docker tag $(COLLIBRA_EDGE_IMAGE):$(TAG) $(REGISTRY)/$(COLLIBRA_EDGE_IMAGE):$(TAG)
	docker tag $(EDGE_SITE_IMAGE):$(TAG)     $(REGISTRY)/$(EDGE_SITE_IMAGE):$(TAG)
	docker tag $(CDN_IMAGE):$(TAG)           $(REGISTRY)/$(CDN_IMAGE):$(TAG)
	docker push $(REGISTRY)/$(BASE_IMAGE):$(TAG)
	docker push $(REGISTRY)/$(COLLIBRA_EDGE_IMAGE):$(TAG)
	docker push $(REGISTRY)/$(EDGE_SITE_IMAGE):$(TAG)
	docker push $(REGISTRY)/$(CDN_IMAGE):$(TAG)

# ── Agent ─────────────────────────────────────────────────────────────────────

agent-validate:
	$(MAKE) -C $(AGENT_DIR) validate

agent-run:
ifndef TASK
	$(error TASK is not set. Usage: make agent-run TASK="your task description")
endif
	$(MAKE) -C $(AGENT_DIR) run-task TASK="$(TASK)"

# ── Clean ─────────────────────────────────────────────────────────────────────

clean:
	-docker rmi $(BASE_IMAGE):$(TAG) $(COLLIBRA_EDGE_IMAGE):$(TAG) $(EDGE_SITE_IMAGE):$(TAG) $(CDN_IMAGE):$(TAG) 2>/dev/null || true
	$(MAKE) -C $(AGENT_DIR) clean
	@echo "Cleaned images and agent artefacts."
