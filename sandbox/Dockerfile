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

# Copy application package (main.py remains the uvicorn entrypoint)
COPY main.py app_factory.py ./
COPY api ./api
COPY execution ./execution
COPY datasources ./datasources
COPY infrastructure ./infrastructure
COPY security ./security

# Ensure the datasource volume mountpoint exists.
RUN mkdir -p /data/datasources
