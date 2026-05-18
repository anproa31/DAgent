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

# Copy application code
COPY main.py .

# Ensure the datasource volume mountpoint exists.
RUN mkdir -p /data/datasources