# db/Dockerfile
FROM postgis/postgis:16-3.5

# Optional metadata for clarity
LABEL org.opencontainers.image.source="https://github.com/chjch/jaxtwin" \
      org.opencontainers.image.description="PostGIS image with pre-seeded GIS layers"

# Install helpers needed by seed scripts
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       gdal-bin \
       postgis \
       curl \
       gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Google Cloud SDK for gcloud access
RUN curl -sSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee /etc/apt/sources.list.d/google-cloud-sdk.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-cloud-sdk \
    && rm -rf /var/lib/apt/lists/*

ARG YQ_VERSION="v4.47.2"
RUN curl -L "https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_linux_amd64" -o /usr/local/bin/yq \
    && chmod +x /usr/local/bin/yq

# Seed assetss
COPY seed/ /docker-entrypoint-initdb.d/
RUN chown -R postgres:postgres /docker-entrypoint-initdb.d
