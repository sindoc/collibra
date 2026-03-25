# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build Commands

### Java server (edge-site-server.jar)
```bash
# Build and install JAR into Dockerfile context
make -C image/edge-site/server install

# Or just build the JAR locally
make -C image/edge-site/server
```
The server is compiled with `javac -source 11 -target 11` — no external dependencies, JDK 11 standard library only.

### Docker images
```bash
make build            # all four images (base → edge-site, collibra-edge, cdn)
make build-base       # CentOS 7 LTS base only
make build-edge-site  # edge-site image (depends on base)
make build-cdn        # nginx CDN image (depends on base)
make build-mock       # Python mock for dev (arm64-native, no base dependency)
```
Image tag defaults to `local`. Override with `TAG=v1.0.0`.

### Java interface layer (Gradle)
```bash
cd java
./gradlew jar         # compile + package
./gradlew javadoc     # HTML Javadoc → build/docs/javadoc/
./gradlew build       # compile + test + all docs
# XML Javadoc requires Java ≤ 12:
JAVA_HOME=/path/to/jdk-11 ./gradlew xmldoc
```
Collibra Maven repo credentials: `COLLIBRA_MAVEN_USER` / `COLLIBRA_MAVEN_PASS` env vars (only needed if consuming Collibra SDK artifacts).

### One-command setup
```bash
make setup            # prerequisites → certs → .env → JAR → images → up
make dev-setup        # same but forces mock DGC (no collibra-edge.jar needed)
```
`setup.sh` is idempotent: steps are skipped when already done.

### Preferred production bootstrap
```bash
cd ~/ws/git/github/sindoc/singine
python3 -m singine.command collibra edge site init "sindoc-edge"
```

Use this installer-backed path for the real Collibra-managed Edge runtime on
Docker Desktop Kubernetes. It verifies prerequisites, installs or upgrades the
Helm release from `installer/`, reconciles stale repo-credential secrets, and
runs post-install verification.

## Stack Lifecycle

```bash
make dev              # start dev stack (mock DGC, docker-compose.dev.yml)
make cloud            # start cloud stack (points to lutino.collibra.com)
make up               # start production stack (real collibra-edge.jar required)
make down             # stop all compose variants
make logs             # tail production logs
```

Manual compose:
```bash
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.cloud.yml --env-file .env up -d
```

## Testing the Running Stack

All traffic enters through the CDN on ports 80/443. Port 8080 (edge-site) and 7080 (collibra-edge) are internal-only. HTTP redirects to HTTPS; use `-k` with the self-signed cert.

```bash
curl -sk https://localhost/health | python3 -m json.tool
curl -sk https://localhost/api/edge/v1/status | python3 -m json.tool
curl -sk https://localhost/api/edge/v1/capabilities | python3 -m json.tool
curl -sk -X POST https://localhost/api/edge/v1/capabilities/catalog/invoke \
     -H "Content-Type: application/json" -d '{"action":"ping","params":{}}' \
     | python3 -m json.tool
```

## Agent (Claude API)

```bash
make agent-validate             # smoke-test tools, no API call
make agent-run TASK="Generate a Collibra edge Deployment for RHEL 7.9"
```
Requires `ANTHROPIC_API_KEY`. Uses `claude-opus-4-6` with adaptive thinking. Writes artifacts to `agent/output/`.

## Architecture

The stack is three services behind an nginx CDN:

```
Internet → CDN (nginx :443) ─┬→ edge-site (:8080)       EdgeSiteServerMain.java
                              └→ collibra-edge (:7080)   Real DGC edge JAR / Python mock
```

**CDN routing** (`image/cdn/conf.d/collibra-upstream.conf`):
- `/api/edge/*` → edge-site (no cache)
- `/site/*` → edge-site (30m cache)
- `/rest/*`, `/graphql/*` → collibra-edge (no cache)
- `/` default → edge-site (10m cache)
- `/health`, `/healthz` → edge-site (uncached health probes)

**EdgeSiteServerMain.java** is a zero-dependency JDK 11 HTTP server (`com.sun.net.httpserver`). It owns all `/api/edge/v1/*` endpoints and serves static content from `/opt/edge/site/www`. On startup it spawns `DgcRegistrar` (daemon thread) which POSTs to `${DGC_URL}/rest/2.0/edgeSites/${SITE_ID}/connectionRequests` — skipped when `COLLIBRA_EDGE_REG_KEY` is blank or starts with `dev-placeholder`.

**java/** is a pure-interface Gradle module (`io.sindoc.collibra.edge`). It defines the contract (`EdgeSiteServer`, `EdgeSiteConfig`, `EdgeSiteCapabilityType`, `EdgeSiteRegistry`, `EdgeSiteInstaller`, etc.) that `EdgeSiteServerMain` implements. No implementation code lives here.

**Three deploy modes:**
| Mode | Compose file | DGC backend | Use when |
|------|-------------|-------------|----------|
| dev | `docker-compose.dev.yml` | Python mock (`:7080`) | No `collibra-edge.jar` |
| cloud | `docker-compose.cloud.yml` | `https://lutino.collibra.com` | Connecting to SaaS |
| production | `docker-compose.yml` | Real `collibra-edge.jar` (`:7080/7443`) | On-prem DGC edge |
| installer-backed | `installer/` + Docker Desktop Kubernetes | `https://lutino.collibra.com` | Real official Edge runtime on this workstation |

**Registration state machine:** `UNREGISTERED → REGISTERING → REGISTERED` (or stays `UNREGISTERED` in dev/cloud with no key). Tracked in-memory only; resets on container restart.

## Environment Variables

`.env` drives all three compose files. Key variables:

| Variable | Required | Notes |
|----------|----------|-------|
| `COLLIBRA_EDGE_HOSTNAME` | yes | FQDN for DGC callbacks |
| `COLLIBRA_DGC_URL` | yes | `https://lutino.collibra.com` for cloud mode |
| `COLLIBRA_EDGE_SITE_ID` | yes | Stable UUID from Collibra DGC Settings → Edge → Sites |
| `COLLIBRA_EDGE_REG_KEY` | no | Blank = skip registration |
| `EDGE_SITE_CAPABILITIES` | no | Comma-separated: `site,connect,catalog,lineage,profiling,workflow` |

TLS certs live in `certs/` (gitignored). `setup.sh` generates a 10-year self-signed cert with SANs for `localhost`, `edge.local`, `127.0.0.1`.

## Platform Notes

- All CentOS 7 images require `--platform linux/amd64`. `setup.sh` sets `DOCKER_DEFAULT_PLATFORM=linux/amd64` automatically on arm64 hosts.
- `collibra-edge.jar` is not in this repo (obtained from Collibra). Its absence forces dev mode in `setup.sh`.
- The `installer/` directory (K8s Helm bundle) is gitignored; generated by `scripts/install-edge-k8s.sh`.
- XML Javadoc (`xmldoclet`) requires Java ≤ 12 due to removal of the legacy `com.sun.javadoc` API.
- Do not commit generated `.env` files, extracted secrets, copied installer credentials, or other proprietary Collibra payloads.
