# Database Seed Assets

This folder contains the build context for the pre-seeded PostGIS image. The
layout keeps executable seed scripts in the top level and data assets grouped
by type underneath.

## Folder Structure

```plaintext
db/
├─ Dockerfile
├─ README.md
├─ docker-compose.yaml
├─ seed/
│  ├─ 01_extensions.sql
│  ├─ 10_load_vector_assets.sh
│  ├─ 11_load_raster_assets.sh
│  ├─ raster_assets/
│  │  └─ manifest.yaml
│  └─ vector_assets/
│     ├─ integrated_decision_units/
│     │  ├─ integrated_decision_units.dbf
│     │  ├─ integrated_decision_units.prj
│     │  ├─ integrated_decision_units.shp
│     │  ├─ integrated_decision_units.shx
│     │  └─ ...
└─ ...
```

## Naming Conventions

- **Script order**: files in `seed/` execute alphabetically during the first
  database start (via the Postgres entrypoint). Use numeric prefixes to control
  order (`01_extensions.sql`, `10_load_vectors.sh`, etc.).
- **Vector assets**: each layer lives in `vector_assets/<layer_name>/`. The
  shapefile base name should match the folder (`<layer_name>.shp` with companion
  files `.shx`, `.dbf`, `.prj`, etc.).
- **Raster assets**: mirror the vector layout under `raster_assets/`.

## Loader Expectations

- `10_load_vector_assets.sh` looks for shapefiles under `vector_assets/*/`. For every
  folder it finds, it expects a single `.shp` file whose base name matches the
  folder name. The script loads that shapefile into Postgres using EPSG:4326 and
  creates a table named after the folder inside the schema defined by
  `VECTOR_SCHEMA` (defaults to `vector`).
- `11_load_raster_assets.sh` reads `raster_assets/manifest.yaml`, downloads the
  listed rasters (HTTP(S) URLs using `curl`), and
  loads them with `raster2pgsql`. It expects the `yq` and `curl` CLI tools that are
  installed in the Dockerfile.

Update the scripts if your projection differs or if you need to target a
different schema.

## Environment Variables

Loader scripts rely on the following variables, provided by the Postgres
entrypoint or Compose:

- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `POSTGRES_PORT` (defaults to 5432)
- `VECTOR_SCHEMA`
- `RASTER_SCHEMA`

Ensure they are set in the root folder's `secrets/db/postgres.env` before invoking
the scripts manually.

## GCP commands

1. Create a new bucket for the US multi-region:
   ```bash
   gcloud storage buckets create gs://jaxtwin-gis-assets-us/ --location=US
   ```
2. Copy a local folder with vector datasets to the bucket (`-r` for recursive):
   ```bash
   gcloud storage cp -r db/seed/vector_assets/ gs://jaxtwin-gis-assets-us/vectors/
   ```
3. Copy a raster dataset from one bucket to the new bucket:
   ```bash
   gcloud storage cp -r "gs://jaxtwin-gis-cog-us/rasters/*" gs://jaxtwin-gis-assets-us/rasters/
   ```
4. Remove a bucket:
   ```bash
   gcloud storage rm -r gs://jaxtwin-gis-cog-us/
   ```
5. Authentication for GCP:
   ```bash
   gcloud auth list  # list active accounts
   gcloud auth activate-service-account --key-file=secrets/gcp/jaxtwin-svc-key.json
   gcloud auth list  # check again to see the new account
   ```

## Adding New Layers

1. For vectors:
   - create a folder under `vector_assets/` (or `raster_assets/`) with
   the layer name.
   - drop the dataset files into that folder, keeping the shapefile base name in
   sync.
   - set `VECTOR_SCHEMA` in `secrets/db/postgres.env` if you need a
   schema other than the default `vector`.
2. For rasters, add an entry to `raster_assets/manifest.yaml`:

   ```yaml
   rasters:
     - name: impervious_2022
       uri: <signed-url>
       srid: 32119          # replace with the raster's actual CRS/EPSG code
       schema: raster       # defaults to public when omitted
       table: impervious_2022
       tile_size: 256x256
       raster2pgsql_options:
         - -Y               # optional extra loader flags
         - -e
   ```

   The loader accepts HTTP(S) URLs (signed URLs work).
3. Rebuild the image (`docker compose -f db/docker-compose.yaml build db`) to bake
   the new data.
4. Start a fresh container (remember to drop the old volume with
   `docker compose -f db/docker-compose.yaml down -v`) and verify the layer loads
   (e.g., using `psql` or
   `SELECT COUNT(*)`).

## Generating Signed URLs for Raster Sources

Private rasters stored in **Google Cloud Storage** can be referenced in
`raster_assets/manifest.yaml` via signed HTTPS URLs. Generate them from your
workstation with the Cloud SDK:

1. Create or download a service-account key that can sign URLs
   (needs `roles/iam.serviceAccountTokenCreator` on the target account):

   - Console: go to **IAM & Admin → Service Accounts**, pick the intended
     account, open the **Keys** tab, and choose
     **Add key → Create new key → JSON**. Save it outside of version
     control—for example `secrets/gcp/jaxtwin-svc-key.json`.
   - CLI (optional):

     ```bash
     gcloud iam service-accounts keys create secrets/gcp/jaxtwin-svc-key.json \
       --iam-account <service-account-email>
     ```

   - Limit the key’s usage to signing and rotate or delete it according to
     your security policy.

2. Install the compatible cryptography stack (Cloud SDK currently expects
   `pyOpenSSL` 23.2.0 and `cryptography` 41.0.7):

   ```bash
   python3 -m pip uninstall pyopenssl cryptography -y
   python3 -m pip install --user "pyopenssl==23.2.0" "cryptography==41.0.7"
   export CLOUDSDK_PYTHON_SITEPACKAGES=1
   ```

3. Create the signed URL (example: 7-day read access):

   ```bash
   gcloud storage sign-url gs://jaxtwin-gis-assets/rasters/impervious/duval_2022_ccap_v2_hires_impervious_20231226_cog.tif --duration=7d --private-key-file=secrets\gcp\jaxtwin-svc-key.json
   ```

   Copy the `https://storage.googleapis.com/...` link into `manifest.yaml`.

4. Replace the URL when it expires or when a new raster version is uploaded.
   Because the database container downloads via HTTPS, the service-account JSON
   file does **not** need to be mounted inside the PostGIS image once the signed
   URL is in place.

## Testing

After building `db/Dockerfile`, run the container and verify:

```bash
psql -U postgres -d "$POSTGRES_DB" -c "SELECT PostGIS_Full_Version();"
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT COUNT(*) FROM public.<layer_name>;"
```

This confirms PostGIS extensions and seeded tables are available.
