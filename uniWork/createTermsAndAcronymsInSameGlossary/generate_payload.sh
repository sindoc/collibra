#!/bin/bash
# generate_payload.sh: Dynamically generate JSON payloads for Collibra assets

TEMPLATE_FILE="template.json"
DOMAIN_ID_FILE="assets/domainId"

# Ensure the domainId file exists
if [[ ! -f $DOMAIN_ID_FILE ]]; then
  echo "Error: domainId file not found at $DOMAIN_ID_FILE"
  exit 1
fi

# Read domainId
DOMAIN_ID=$(<"$DOMAIN_ID_FILE")

# Load the template
if [[ ! -f $TEMPLATE_FILE ]]; then
  echo "Error: Template file not found: $TEMPLATE_FILE"
  exit 1
fi
TEMPLATE=$(<"$TEMPLATE_FILE")

# Function to generate JSON for a single asset
generate_asset_payload() {
  local name="$1"
  local type_id="$2"
  local payload="$TEMPLATE"

  # Replace placeholders with actual values
  payload=${payload//"{{name}}"/"$name"}
  payload=${payload//"{{domainId}}"/"$DOMAIN_ID"}
  payload=${payload//"{{typeId}}"/"$type_id"}

  echo "$payload"
}

# Start JSON array
echo '['
first=true

# Iterate over all *TypeId files
for type_id_file in assets/*TypeId; do
  # Extract the typeId and corresponding asset directory
  type_id=$(<"$type_id_file")
  asset_type=$(basename "$type_id_file" TypeId) # Extract asset type name from the file
  asset_dir="assets/$asset_type"

  # If the directory exists, process its files
  if [[ -d $asset_dir ]]; then
    for asset_file in "$asset_dir"/*; do
      name=$(basename "$asset_file") # Use file name as the asset name

      # Add comma between JSON objects, but not before the first object
      if [[ $first == false ]]; then
        echo ','
      fi
      generate_asset_payload "$name" "$type_id"
      first=false
    done
  fi
done

# End JSON array
echo ']'
