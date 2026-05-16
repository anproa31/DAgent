# Base image
FROM python:3.10-slim

# Set working directory
WORKDIR /usr/src/app

# Copy dependencies and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and related directories
COPY src /usr/src/app/

# EXPOSE 8000 (for documentation, optional)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
