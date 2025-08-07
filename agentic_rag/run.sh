#!/bin/bash

# run.sh - Script to run the Agentic RAG application

echo "🚀 Starting Agentic RAG Video Retrieval System..."

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Copying template..."
    cp .env.template .env
    echo "📝 Please edit .env file with your actual API keys and endpoints."
    echo "   Required: GOOGLE_API_KEY, SEARCH_API_URL, MEDIA_API_URL"
    exit 1
fi

# Run the application
echo "🌟 Starting FastAPI server..."
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
