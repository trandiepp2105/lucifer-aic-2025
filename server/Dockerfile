FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    CUDA_HOME=/usr/local/cuda

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    wget \
    curl \
    git \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# Download Meilisearch binary
RUN wget https://github.com/meilisearch/meilisearch/releases/latest/download/meilisearch-linux-amd64 -O /usr/local/bin/meilisearch && \
    chmod +x /usr/local/bin/meilisearch

# Copy application code
COPY . .

# Create directories for data and outputs
RUN mkdir -p /app/data /app/outputs /app/indexes

# Expose ports
# 8000 for FastAPI
# 7700 for Meilisearch
EXPOSE 8000 7700

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command to start both Meilisearch and FastAPI
CMD ["sh", "-c", "meilisearch --http-addr 0.0.0.0:7700 & python3 main.py"]
