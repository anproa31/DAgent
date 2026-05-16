# Base image
FROM python:3.11-slim

# Set working directory
WORKDIR /usr/src/app

# Copy dependencies and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .