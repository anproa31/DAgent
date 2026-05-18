# Base image
FROM python:3.11-slim

# Build deps for pandas/duckdb wheels
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /usr/src/app

# Copy dependencies and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Optional local entrypoint (``python run.py``); primary CMD still uses uvicorn directly.
COPY run.py ./

# Copy application code (mounted as a volume in compose so live-reload works)
COPY src /usr/src/app/src

# Ensure the datasource volume mountpoint exists even before the volume is mounted.
RUN mkdir -p /data/datasources

# EXPOSE 8000 (for documentation, optional)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
