#!/bin/bash

# BioAnalyzer Startup Script
# This script sets up the environment and starts the application

echo "🚀 Starting BioAnalyzer..."

# Create necessary directories
mkdir -p logs
mkdir -p cache
mkdir -p results

# Set up log rotation (if logrotate is available)
if command -v logrotate &> /dev/null; then
    echo "📝 Setting up log rotation..."
    cat > /tmp/bioanalyzer-logs << EOF
$PWD/logs/*.log {
    daily
    rotate 5
    compress
    delaycompress
    missingok
    notifempty
    create 644 $USER $USER
}
EOF
    sudo mv /tmp/bioanalyzer-logs /etc/logrotate.d/bioanalyzer-logs 2>/dev/null || echo "⚠️  Could not set up system log rotation (requires sudo)"
fi

# Set performance environment variables (can be overridden)
export API_TIMEOUT=${API_TIMEOUT:-30}
export ANALYSIS_TIMEOUT=${ANALYSIS_TIMEOUT:-45}
export GEMINI_TIMEOUT=${GEMINI_TIMEOUT:-30}
export FRONTEND_TIMEOUT=${FRONTEND_TIMEOUT:-60}
export CACHE_VALIDITY_HOURS=${CACHE_VALIDITY_HOURS:-24}
export MAX_CACHE_SIZE=${MAX_CACHE_SIZE:-1000}
export NCBI_RATE_LIMIT_DELAY=${NCBI_RATE_LIMIT_DELAY:-0.34}
export MAX_CONCURRENT_REQUESTS=${MAX_CONCURRENT_REQUESTS:-3}
export LOG_LEVEL=${LOG_LEVEL:-INFO}

echo "📁 Created necessary directories"
echo "⚙️  Performance settings:"
echo "   API Timeout: ${API_TIMEOUT}s"
echo "   Analysis Timeout: ${ANALYSIS_TIMEOUT}s"
echo "   Gemini Timeout: ${GEMINI_TIMEOUT}s"
echo "   Cache Validity: ${CACHE_VALIDITY_HOURS}h"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed or not in PATH"
    exit 1
fi

# Check if required packages are installed
echo "🔍 Checking dependencies..."
python3 -c "import fastapi, uvicorn" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 Installing required packages..."
    pip3 install -r config/requirements.txt
fi

# Start the application
echo "🌐 Starting BioAnalyzer server..."
echo "📚 API documentation will be available at: http://127.0.0.1:8000/docs"
echo "🔍 Health check at: http://127.0.0.1:8000/health"
echo "📊 Metrics at: http://127.0.0.1:8000/metrics"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python3 main.py 