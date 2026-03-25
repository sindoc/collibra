# Collibra Edge Local Operations

This repo contains two different Edge paths:

- a custom Docker-based Edge compatibility stack for local experimentation
- the official installer-backed Collibra Edge runtime for real SaaS connectivity

For `https://lutino.collibra.com`, the default operator path is the official
installer-backed runtime on Docker Desktop Kubernetes.

## Quick start

```bash
cd ~/ws/git/github/sindoc/singine
python3 -m singine.command collibra edge site init "sindoc-edge"
```

That command:

- stops local mock stacks when present
- checks `helm`, `kubectl`, `jq`, `yq`, and cluster access
- applies the installer bundle from `installer/`
- upgrades or installs the `collibra-edge` Helm release
- verifies the site with `edge k8s status` and `edge k8s test`

## Local verification

```bash
helm status collibra-edge -n collibra-edge
kubectl get pods -n collibra-edge
python3 -m singine.command edge k8s test
```

## Best practices

- Treat installer credentials and extracted secrets as sensitive operational material.
- Keep public abstractions in git; keep secrets outside commits.
- Prefer the installer-backed runtime for real metadata operations against Collibra SaaS.
- Use the custom Docker compose stack only for mock flows and local edge-site development.

## Known issue now handled

Some older local installs created `collibra-edge-repo-creds` as a Docker
registry secret. `edge-cd` expects an opaque secret with `username` and
`password` files. `scripts/install-edge-k8s.sh` now detects and recreates that
secret correctly.
