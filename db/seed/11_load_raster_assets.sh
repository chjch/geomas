#!/usr/bin/env bash
set -euo pipefail

# Path to the raster manifest embedded in the image
MANIFEST_PATH="/docker-entrypoint-initdb.d/21_manifest_raster.yaml"

PSQL_TARGET=(psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB")
RASTER_SCHEMA=${RASTER_SCHEMA:-raster}
GCP_SA_KEY=${GCP_SA_KEY:-/run/secrets/gcp_sa_key}

# Skip quietly if no manifest is provided
if [ ! -f "$MANIFEST_PATH" ]; then
  echo "No raster manifest found at $MANIFEST_PATH; skipping raster load."
  exit 0
fi

# Ensure required tooling is present inside the container
for tool in yq raster2pgsql psql; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Required tool '$tool' is missing; aborting raster load." >&2
    exit 1
  fi
done

# Check for gcloud
if ! command -v gcloud >/dev/null 2>&1; then
  echo "ERROR: gcloud not found. Install Google Cloud SDK." >&2
  exit 1
fi

# Authenticate with service account key if available
if [ -f "$GCP_SA_KEY" ]; then
  export GOOGLE_APPLICATION_CREDENTIALS="$GCP_SA_KEY"
  gcloud auth activate-service-account --key-file="$GCP_SA_KEY" --quiet
else
  echo "WARNING: Service account key not found at $GCP_SA_KEY" >&2
  echo "Assuming Application Default Credentials are configured" >&2
fi

# Ensure the target schema exists before loading tables
"${PSQL_TARGET[@]}" -c "CREATE SCHEMA IF NOT EXISTS \"$RASTER_SCHEMA\";"

# Parse manifest rows into tab-separated lines we can iterate over
mapfile -t RASTER_ENTRIES < <(
  yq -r '.rasters[]? | [
      .name,
      .gs_path,
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
  IFS=$'\t' read -r name gs_path srid schema table tile_size extra_opts <<< "$entry"

  printf 'Downloading raster "%s" from %s\n' "$name" "$gs_path"
  tmp_raster=$(mktemp --suffix=.tif)

  # Download using gcloud storage cp with service account authentication
  if ! gcloud storage cp "$gs_path" "$tmp_raster"; then
    echo "ERROR: Failed to download raster '$name' from $gs_path" >&2
    echo "Check that the file exists and service account has storage.objectViewer role" >&2
    rm -f "$tmp_raster"
    exit 1
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
