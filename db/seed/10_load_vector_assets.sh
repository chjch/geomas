#!/usr/bin/env bash
set -euo pipefail

SHAPE_LOADER=$(command -v shp2pgsql || true)
if [ -z "$SHAPE_LOADER" ]; then
  echo "shp2pgsql tool not found on PATH" >&2
  exit 1
fi

PSQL_CMD=(psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB")
MANIFEST_PATH="/docker-entrypoint-initdb.d/20_manifest_vector.yaml"
VECTOR_SRID=${VECTOR_SRID:-4326}
VECTOR_SCHEMA=${VECTOR_SCHEMA:-vector}
GCP_SA_KEY=${GCP_SA_KEY:-/run/secrets/gcp_sa_key}

# Ensure the target schema exists before loading tables
"${PSQL_CMD[@]}" -c "CREATE SCHEMA IF NOT EXISTS \"$VECTOR_SCHEMA\";"

# Check if manifest exists (GCS-based loading)
if [ -f "$MANIFEST_PATH" ]; then
  echo "Loading vectors from manifest: $MANIFEST_PATH"
  
  # Ensure required tools are present
  for tool in yq shp2pgsql psql; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      echo "Required tool '$tool' is missing; aborting vector load." >&2
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
  
  # Parse manifest entries
  mapfile -t VECTOR_ENTRIES < <(
    yq -r '.vectors[]? | [
      .name,
      .gs_path,
      (.srid // 4326),
      (.schema // "vector"),
      (.table // .name)
    ] | @tsv' "$MANIFEST_PATH"
  )
  
  if [ ${#VECTOR_ENTRIES[@]} -eq 0 ]; then
    echo "Manifest did not define any vectors; nothing to do."
    exit 0
  fi
  
  # Required shapefile extensions
  SHAPEFILE_EXTS=(".shp" ".shx" ".dbf")
  OPTIONAL_EXTS=(".prj" ".cpg" ".sbn" ".sbx" ".xml" ".shp.xml")
  
  for entry in "${VECTOR_ENTRIES[@]}"; do
    IFS=$'\t' read -r name gs_path srid schema table <<< "$entry"
    
    echo "Downloading vector layer '$name' from $gs_path"
    tmp_dir=$(mktemp -d)
    
    # Download all shapefile components
    base_name=$(basename "$gs_path")
    echo "Base name: $base_name"
    download_failed=false
    
    # Download required shapefile components
    for ext in "${SHAPEFILE_EXTS[@]}"; do
      gs_file="${gs_path}${ext}"
      
      echo "  Downloading ${ext} from $gs_file ..."
      # gcloud storage cp copies FROM gs://path TO local directory
      # When destination is a directory, it preserves the original filename
      if ! gcloud storage cp "$gs_file" "$tmp_dir/"; then
        echo "ERROR: Failed to download ${ext} for '$name' from $gs_file" >&2
        download_failed=true
        break
      fi
    done
    
    if [ "$download_failed" = true ]; then
      echo "ERROR: Failed to download required components for '$name'" >&2
      rm -rf "$tmp_dir"
      continue
    fi
    
    # Download optional shapefile components (fail silently if missing)
    for ext in "${OPTIONAL_EXTS[@]}"; do
      gs_file="${gs_path}${ext}"
      
      echo "  Downloading optional ${ext} from $gs_file ..."
      # Download to directory - gcloud preserves the filename
      if ! gcloud storage cp "$gs_file" "$tmp_dir/" 2>/dev/null; then
        echo "  Optional ${ext} not found, skipping" >&2
      fi
    done
    
    echo "Loading vector layer '$name' into $schema.$table (SRID $srid)"
    target_table="$schema.$table"
    shp_file="${tmp_dir}/${base_name}.shp"
    
    if "$SHAPE_LOADER" -I -s "$srid" "$shp_file" "$target_table" | "${PSQL_CMD[@]}" --quiet --set ON_ERROR_STOP=1 >/dev/null; then
      echo "Loaded '$name' successfully"
    else
      echo "ERROR: Failed to load '$name' into database" >&2
    fi
    
    rm -rf "$tmp_dir"
  done
  
  exit 0
fi

# No manifest found
echo "No vector manifest found at $MANIFEST_PATH; skipping vector load."
exit 0
