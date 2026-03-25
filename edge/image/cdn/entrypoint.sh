#!/usr/bin/env bash
# entrypoint.sh — nginx CDN entrypoint
#
# 1. Substitutes runtime env vars into nginx conf templates.
# 2. Generates per-channel proxy location blocks from mms-channels.json.
# 3. Starts nginx.

set -euo pipefail

# ── Load credentials ─────────────────────────────────────────────────────────
# Priority: 1Password CLI (op) → ~/.collibra/creds → environment variables
#
# ~/.collibra/creds is a simple shell file:
#   export ONETV_TOKEN="..."
#   export COLLIBRA_EDGE_REG_KEY="..."
#   export COLLIBRA_MAVEN_PASS="..."
#
# 1Password items are expected under the vault "Collibra" with fields matching
# the env-var names (e.g. item "CDN Streams" → field "ONETV_TOKEN").

load_creds_from_op() {
  command -v op >/dev/null 2>&1 || return 1
  op whoami >/dev/null 2>&1   || return 1  # not signed in

  local item="CDN Streams"
  for var in ONETV_TOKEN COLLIBRA_EDGE_REG_KEY; do
    val=$(op item get "$item" --fields "$var" 2>/dev/null) || continue
    [ -n "$val" ] && export "$var=$val"
  done
  echo "[entrypoint] credentials loaded from 1Password"
}

load_creds_from_file() {
  local f="${COLLIBRA_CREDS_FILE:-$HOME/.collibra/creds}"
  [ -f "$f" ] || return 1
  # shellcheck source=/dev/null
  . "$f"
  echo "[entrypoint] credentials loaded from $f"
}

load_creds_from_op || load_creds_from_file || echo "[entrypoint] using environment variables for credentials"

# ── Append stream token to channel paths that need it ────────────────────────
# If ONETV_TOKEN is set, the entrypoint injects it into mms-channels.json at
# runtime so the repo copy stays token-free.
ONETV_TOKEN="${ONETV_TOKEN:-}"

# ── Environment defaults ──────────────────────────────────────────────────────
IRIB3_ORIGIN_HOST="${IRIB3_ORIGIN_HOST:-lenz.splus.ir}"
IRIB3_STREAM_PATH="${IRIB3_STREAM_PATH:-/PLTV/88888888/224/3221226868/index.m3u8}"
IRIB3_CDN_HOST="${IRIB3_CDN_HOST:-tv.edge.lutino.io}"
CDN_HOST="${CDN_HOST:-cdn.persiangulf.org}"

export IRIB3_ORIGIN_HOST IRIB3_STREAM_PATH IRIB3_CDN_HOST CDN_HOST

# ── Render .template files (envsubst) ────────────────────────────────────────
SUBST_VARS='${IRIB3_ORIGIN_HOST} ${IRIB3_STREAM_PATH} ${IRIB3_CDN_HOST} ${CDN_HOST}'

for tmpl in /etc/nginx/conf.d/*.template /opt/edge/cdn/irib3/*.template; do
  [ -f "$tmpl" ] || continue
  out="${tmpl%.template}"
  envsubst "$SUBST_VARS" < "$tmpl" > "$out"
  echo "[entrypoint] rendered $(basename $tmpl) → $(basename $out)"
done

echo "[entrypoint] IRIB3_ORIGIN_HOST=${IRIB3_ORIGIN_HOST}"
echo "[entrypoint] IRIB3_STREAM_PATH=${IRIB3_STREAM_PATH}"
echo "[entrypoint] IRIB3_CDN_HOST=${IRIB3_CDN_HOST}"
echo "[entrypoint] CDN_HOST=${CDN_HOST}"

# ── Generate per-channel proxy location blocks ────────────────────────────────
CHANNELS_JSON="/opt/edge/cdn/mms-channels.json"
CHANNELS_CONF="/etc/nginx/conf.d/channels-generated.inc"

if [ -f "$CHANNELS_JSON" ] && command -v python3 >/dev/null 2>&1; then
  python3 - "$CHANNELS_JSON" "$CHANNELS_CONF" <<'PYEOF'
import json, sys

channels_file = sys.argv[1]
out_file      = sys.argv[2]

with open(channels_file) as f:
    channels = json.load(f)

blocks = []
for ch in channels:
    name   = ch['name']
    origin = ch['origin']
    var    = 'ch_' + name.replace('-', '_') + '_origin'
    block  = (
        f"    location /proxy/{name}/ {{\n"
        f"        set ${var} \"https://{origin}\";\n"
        f"        rewrite ^/proxy/{name}/(.*)$ /$1 break;\n"
        f"        proxy_pass ${var};\n"
        f"        proxy_ssl_name {origin};\n"
        f"        proxy_ssl_server_name on;\n"
        f"        proxy_set_header Host {origin};\n"
        f"        proxy_set_header Accept-Encoding \"\";\n"
        f"        proxy_cache cdn_cache;\n"
        f"        proxy_cache_valid 200 10s;\n"
        f"        proxy_cache_key \"$uri$is_args$args\";\n"
        f"        add_header Access-Control-Allow-Origin \"*\";\n"
        f"    }}\n"
    )
    blocks.append(block)

with open(out_file, 'w') as f:
    f.write('\n'.join(blocks) + '\n')

print(f"[entrypoint] generated {out_file} ({len(channels)} channels)")
PYEOF
else
  # No channels JSON or no python3 — write empty conf so nginx include succeeds
  : > "$CHANNELS_CONF"
  echo "[entrypoint] channels-generated.conf: skipped (no JSON or no python3)"
fi

# ── Inject stream tokens into mms-channels.json at runtime ─────────────────
if [ -n "$ONETV_TOKEN" ] && [ -f "$CHANNELS_JSON" ] && command -v python3 >/dev/null 2>&1; then
  python3 - "$CHANNELS_JSON" "$ONETV_TOKEN" <<'PYEOF'
import json, sys, urllib.parse

channels_file = sys.argv[1]
token         = sys.argv[2]

with open(channels_file) as f:
    channels = json.load(f)

# Origins that require the onetv token
ONETV_ORIGINS = {"ca-rt.onetv.app"}

for ch in channels:
    if ch.get("origin") in ONETV_ORIGINS:
        path = ch["path"]
        sep  = "&" if "?" in path else "?"
        if f"token={token}" not in path:
            ch["path"] = f"{path}{sep}token={token}"

with open(channels_file, "w") as f:
    json.dump(channels, f, indent=2)

print(f"[entrypoint] injected stream tokens into {channels_file}")
PYEOF
fi

exec nginx -g "daemon off;"
