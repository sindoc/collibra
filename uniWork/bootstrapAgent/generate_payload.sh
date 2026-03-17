#!/bin/bash
# generate_payload.sh — Bulk asset payload generator for investment maturity levels
# Mirrors the pattern from createTermsAndAcronymsInSameGlossary/generate_payload.sh
# but targets the EdgeCap Investment Maturity asset type.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOMAIN_ID_FILE="$SCRIPT_DIR/assets/domainId"
ASSETS_DIR="$SCRIPT_DIR/assets"

TEMPLATE='{"name":"{{name}}","domainId":"{{domainId}}","typeId":"{{typeId}}"}'

if [[ ! -f "$DOMAIN_ID_FILE" ]]; then
  echo "Error: domainId not found at $DOMAIN_ID_FILE" >&2
  exit 1
fi
DOMAIN_ID="$(<"$DOMAIN_ID_FILE")"

generate_asset_payload() {
  local name="$1" type_id="$2"
  local payload="$TEMPLATE"
  payload="${payload//\{\{name\}\}/$name}"
  payload="${payload//\{\{domainId\}\}/$DOMAIN_ID}"
  payload="${payload//\{\{typeId\}\}/$type_id}"
  echo "$payload"
}

echo '['
first=true

for type_id_file in "$ASSETS_DIR"/*TypeId; do
  type_id="$(<"$type_id_file")"
  asset_type="$(basename "$type_id_file" TypeId)"
  asset_dir="$ASSETS_DIR/$asset_type"

  if [[ -d "$asset_dir" ]]; then
    for asset_file in "$asset_dir"/*; do
      name="$(basename "$asset_file")"
      if [[ "$first" == false ]]; then echo ','; fi
      generate_asset_payload "$name" "$type_id"
      first=false
    done
  fi
done

echo ']'
