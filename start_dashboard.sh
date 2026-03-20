#!/bin/bash

# Test Report Analyzer - Dashboard Quick Start Script

set -e

echo "=========================================="
echo "  Test Report Analyzer Dashboard"
echo "=========================================="
echo ""

# Check if running from project root
if [ ! -f "dashboard/app.py" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found. Creating one..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies if needed
if ! python -c "import streamlit" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
    echo "✅ Dependencies installed"
fi

# Check if API is running
API_URL="${TEST_ANALYZER_API_URL:-http://localhost:8000}"
echo ""
echo "🔍 Checking API status at $API_URL..."
if curl -s -f -m 2 "$API_URL/health" > /dev/null 2>&1; then
    echo "✅ API is running"
else
    echo "⚠️  Warning: API is not responding at $API_URL"
    echo "   Start the API first with:"
    echo "   uvicorn api.main:app --host 0.0.0.0 --port 8000"
    echo ""
    echo "   Or use Docker Compose to start everything:"
    echo "   docker-compose up -d"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Start dashboard
echo ""
echo "=========================================="
echo "🚀 Starting Streamlit Dashboard..."
echo "=========================================="
echo ""
echo "📊 Dashboard will be available at: http://localhost:8501"
echo "🌐 API endpoint: $API_URL"
echo ""
echo "Press Ctrl+C to stop the dashboard"
echo ""

# Run Streamlit
streamlit run dashboard/app.py \
    --server.port=8501 \
    --server.address=localhost \
    --server.headless=false
