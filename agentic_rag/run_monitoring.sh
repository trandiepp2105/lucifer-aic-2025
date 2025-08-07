#!/bin/bash

# Start Agent Monitoring Dashboard
# Usage: ./run_monitoring.sh

echo "🤖 Starting Agent Monitoring Dashboard..."

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "❌ Streamlit is not installed. Please install it with: pip install streamlit"
    exit 1
fi

# Check if the monitoring file exists
if [ ! -f "streamlit_monitoring.py" ]; then
    echo "❌ streamlit_monitoring.py not found. Please make sure you're in the correct directory."
    exit 1
fi

# Set environment variables if .env exists
if [ -f ".env" ]; then
    echo "📝 Loading environment variables from .env"
    export $(cat .env | xargs)
fi

# Start the Streamlit app
echo "🚀 Starting dashboard on http://localhost:8501"
echo "🔍 Use this dashboard to monitor agent reasoning steps, view frames, and analyze performance."
echo ""
echo "📊 Available features:"
echo "   - Sessions Overview: View all agent reasoning sessions"
echo "   - Session Details: Deep dive into specific sessions"
echo "   - Live Monitoring: Real-time monitoring of active sessions"
echo "   - Tools Reference: Information about available tools"
echo ""
echo "🌐 Language support: English / Tiếng Việt"
echo ""

streamlit run streamlit_monitoring.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false
