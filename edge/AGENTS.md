# AGENTS.md

Codex guidance for this repository.

## Primary goal

Keep the public abstractions for running and verifying Collibra Edge healthy
without committing Collibra proprietary runtime content or secrets.

## Preferred operator path

```bash
cd ~/ws/git/github/sindoc/singine
python3 -m singine.command collibra edge site init "sindoc-edge"
```

This is the supported local bootstrap for `lutino.collibra.com` on Docker
Desktop Kubernetes.

## Safe change surface

- `Makefile`
- `scripts/`
- `docker-compose*.yml`
- custom Java code under `image/edge-site/server/`
- docs such as `README.md`, `CLAUDE.md`, `AGENTS.md`

## Never commit

- generated `.env` files
- raw secrets or copied credential values
- proprietary JARs or vendor payloads
- copied installer artifacts beyond the repo's existing public abstractions

## Known operational pitfall

If `edge-cd` crashes with:

```text
open /opt/edge-cd/secret/repo/username: no such file or directory
```

the live `collibra-edge-repo-creds` secret likely has the wrong type. The
installer script in `scripts/install-edge-k8s.sh` now reconciles that secret
automatically.
