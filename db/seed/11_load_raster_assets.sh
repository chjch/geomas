#!/usr/bin/env bash
set -euo pipefail

# Path to the raster manifest embedded in the image
MANIFEST_PATH="/docker-entrypoint-initdb.d/21_manifest_raster.yaml"

# NOTE: If using signed URLs (e.g., Google Cloud Storage signed URLs), remember to:
# - Regenerate signed URLs when they expire (typically 7 days)
# - Update the URI in manifest_raster.yaml with the new signed URL
# - Signed URLs contain x-goog-expires parameter indicating expiration time
#
# To regenerate: gcloud storage signurls create <gs://path> --duration=7d --private-key-file=<key.json>

PSQL_TARGET=(psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB")
RASTER_SCHEMA=${RASTER_SCHEMA:-raster}

# Skip quietly if no manifest is provided
if [ ! -f "$MANIFEST_PATH" ]; then
  echo "No raster manifest found at $MANIFEST_PATH; skipping raster load."
  exit 0
fi

# Ensure required tooling is present inside the container
for tool in yq curl raster2pgsql psql; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Required tool '$tool' is missing; aborting raster load." >&2
    exit 1
  fi
done

# Ensure the target schema exists before loading tables
"${PSQL_TARGET[@]}" -c "CREATE SCHEMA IF NOT EXISTS \"$RASTER_SCHEMA\";"

# Remember whether gsutil is available for gs:// downloads
GSUTIL_BIN=""
if command -v gsutil >/dev/null 2>&1; then
  GSUTIL_BIN=$(command -v gsutil)
fi

# Parse manifest rows into tab-separated lines we can iterate over
mapfile -t RASTER_ENTRIES < <(
  yq -r '.rasters[]? | [
      .name,
      .uri,
      (.srid // 4326),
      (.schema // "raster"),
      (.table // .name),
      (.tile_size // "256x256"),
      ((.raster2pgsql_options // []) | join(" "))
    ] | @tsv' "$MANIFEST_PATH"
)

# Exit if nothing was defined
if [ ${#RASTER_ENTRIES[@]} -eq 0 ]; then
  echo "Manifest did not define any rasters; nothing to do."
  exit 0
fi

for entry in "${RASTER_ENTRIES[@]}"; do
  IFS=$'\t' read -r name uri srid schema table tile_size extra_opts <<< "$entry"

  printf 'Downloading raster "%s" from %s\n' "$name" "$uri"
  tmp_raster=$(mktemp --suffix=.tif)

  # Fetch the raster. HTTPS (including signed URLs) works out of the box.
  # IMPORTANT: If download fails, the signed URL may have expired. Regenerate it and update manifest.yaml
  if [[ "$uri" == gs://* ]]; then
    if [[ -z "$GSUTIL_BIN" ]]; then
      echo "gs:// URI '$uri' requires gsutil; provide an https URL or install gsutil." >&2
      rm -f "$tmp_raster"
      exit 1
    fi
    if ! "$GSUTIL_BIN" cp "$uri" "$tmp_raster"; then
      echo "ERROR: Failed to download raster '$name' from gs:// URI" >&2
      echo "If using a signed URL, it may have expired. Regenerate and update manifest_raster.yaml" >&2
      rm -f "$tmp_raster"
      exit 1
    fi
  else
    if ! curl -sSL -f "$uri" -o "$tmp_raster"; then
      echo "ERROR: Failed to download raster '$name' from $uri" >&2
      echo "If using a signed URL (contains 'x-goog-signature'), it may have expired." >&2
      echo "Regenerate the signed URL and update the URI in manifest_raster.yaml" >&2
      echo "Command: gcloud storage signurls create <gs://path> --duration=7d --private-key-file=<key.json>" >&2
      rm -f "$tmp_raster"
      exit 1
    fi
  fi

  printf 'Loading raster "%s" into %s.%s (SRID %s)\n' "$name" "$schema" "$table" "$srid"
  # Build raster2pgsql command with optional tile size and extra flags
  raster_cmd=(raster2pgsql -I -C -s "$srid")
  [[ -n "$tile_size" ]] && raster_cmd+=(-t "$tile_size")
  if [[ -n "$extra_opts" ]]; then
    # shellcheck disable=SC2206
    raster_cmd+=($extra_opts)
  fi
  raster_cmd+=("$tmp_raster" "$schema.$table")

  # Pipe loader output directly into psql
  "${raster_cmd[@]}" | "${PSQL_TARGET[@]}" --quiet --set ON_ERROR_STOP=1 >/dev/null
  printf 'Loaded raster "%s" successfully.\n' "$name"

  rm -f "$tmp_raster"
done
