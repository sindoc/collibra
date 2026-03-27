# Collibra IO Commands

This document publishes the `singine collibra io` command family as a stable interaction surface for governed Collibra I/O operations.

The implementation lives in [io.py](/Users/skh/ws/git/github/sindoc/collibra/singine-collibra/python/singine_collibra/io.py), while the canonical XML publication source remains [singine-collibra-commands.xml](/Users/skh/ws/git/github/sindoc/collibra/docs/xml/singine-collibra-commands.xml). The OpenAPI artifact is generated from that XML by [generate_collibra_io_openapi.py](/Users/skh/ws/git/github/sindoc/collibra/scripts/generate_collibra_io_openapi.py).

## Goal

Define one command set that can be consumed from:

- terminal CLI
- XML publication
- OpenAPI / Swagger tooling
- Postman collections
- `curl` and `wget` request generation
- SinLisp planning and test harnesses

## Command family

```bash
singine collibra io <subject> <action> [options]
```

## Covered commands

### Create

```bash
singine collibra io create community --name "Data Governance" --json
singine collibra io create template --name glossary-import --asset-type "Business Term" --output /tmp/glossary-import.json
```

### Metamodel

```bash
singine collibra io metamodel status
singine collibra io metamodel visualize --asset-type "Data Notebook" --format mermaid
singine collibra io metamodel export --format opmodel --asset-type "Business Term" --output /tmp/business-term-opmodel.json
```

### CHIP

```bash
singine collibra io chip status --json
singine collibra io chip configure all --json
singine collibra io chip tools list --json
```

### Edge

```bash
singine collibra io edge connection probe-postgres --json
singine collibra io edge datasource diagnose --id DATASOURCE-UUID --json
```

## Companion artifacts

- XML source: `docs/xml/singine-collibra-commands.xml`
- OpenAPI: `schema/singine-collibra-io-api.json`
- SinLisp: `runtime/sinlisp/collibra_io.sinlisp`

## Interaction pattern

The CLI remains the executable surface. The OpenAPI document provides a request/response contract for service adapters and HTTP tooling. The SinLisp file records the same command inventory in a form that can drive tests, workflow planning, and higher-level protocol generation.

## Verification

```bash
cd /Users/skh/ws/git/github/sindoc/collibra
python3 scripts/generate_collibra_io_openapi.py
python3 -m unittest singine-collibra/python/tests/test_collibra_io_docs_surface.py -v
python3 -m json.tool schema/singine-collibra-io-api.json >/tmp/collibra-io-api.pretty.json
```
