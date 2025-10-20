#!/bin/bash

# Startup script for Lucifer AIC 2025 Search Engine

set -e

echo "🚀 Starting Lucifer AIC 2025 Search Engine..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "✅ Please edit .env file with your configurations before running again."
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

echo "📋 Configuration loaded"
echo "   - Meilisearch: ${MEILISEARCH_HOST}:${MEILISEARCH_PORT}"
echo "   - API: ${API_HOST}:${API_PORT}"
echo "   - GPU: ${USE_GPU}"

# Check if Meilisearch is running
echo "🔍 Checking Meilisearch..."
if ! curl -s http://${MEILISEARCH_HOST}:${MEILISEARCH_PORT}/health > /dev/null 2>&1; then
    echo "⚠️  Meilisearch is not running. Starting Meilisearch..."
    
    # Check if meilisearch binary exists
    if [ ! -f ./meilisearch ]; then
        echo "📥 Downloading Meilisearch..."
        wget https://github.com/meilisearch/meilisearch/releases/latest/download/meilisearch-linux-amd64 -O meilisearch
        chmod +x meilisearch
    fi
    
    # Start Meilisearch in background
    export MEILI_MASTER_KEY=${MEILISEARCH_API_KEY}
    ./meilisearch --http-addr ${MEILISEARCH_HOST}:${MEILISEARCH_PORT} > meilisearch.log 2>&1 &
    MEILI_PID=$!
    echo "✅ Meilisearch started (PID: $MEILI_PID)"
    
    # Wait for Meilisearch to be ready
    echo "⏳ Waiting for Meilisearch to be ready..."
    for i in {1..30}; do
        if curl -s http://${MEILISEARCH_HOST}:${MEILISEARCH_PORT}/health > /dev/null 2>&1; then
            echo "✅ Meilisearch is ready"
            break
        fi
        sleep 1
    done
else
    echo "✅ Meilisearch is already running"
fi

# Check Python version
echo "🐍 Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "   Python version: $PYTHON_VERSION"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Check GPU availability
if [ "${USE_GPU}" = "true" ]; then
    echo "🎮 Checking GPU..."
    python3 -c "import torch; print(f'   CUDA available: {torch.cuda.is_available()}'); print(f'   GPU count: {torch.cuda.device_count()}')"
fi

# Start FastAPI application
echo "🚀 Starting FastAPI application..."
echo "   Access API at: http://${API_HOST}:${API_PORT}"
echo "   API Docs at: http://${API_HOST}:${API_PORT}/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python3 main.py
