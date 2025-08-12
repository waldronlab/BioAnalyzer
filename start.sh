#!/bin/bash

# BugSigDB Analyzer Docker Startup Script
# This script builds and starts the entire application stack

set -e  # Exit on any error

echo "🚀 BugSigDB Analyzer Docker Startup"
echo "===================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is running
print_status "Checking Docker..."
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi
print_success "Docker is running"

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_warning ".env file not found. Creating default .env file..."
    cat > .env << EOF
# API Keys - Replace with your actual keys
NCBI_API_KEY=your_ncbi_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
EMAIL=your_email@example.com

# Model Configuration
DEFAULT_MODEL=gemini

# Application Configuration
DEBUG=true
LOG_LEVEL=INFO
EOF
    print_warning "Please edit .env file with your actual API keys before running the application"
fi

# Build and start the application
print_status "Building and starting BugSigDB Analyzer..."
docker compose up --build -d

# Wait for services to be healthy
print_status "Waiting for services to be healthy..."
sleep 10

# Check service status
print_status "Checking service status..."
docker compose ps

# Show access information
echo ""
print_success "🎉 BugSigDB Analyzer is now running!"
echo ""
echo "📱 Access your application:"
echo "   • Main App: http://localhost:8000"
echo "   • Nginx: http://localhost:80"
echo "   • Redis: localhost:6379"
echo ""
echo "📚 Useful commands:"
echo "   • View logs: docker compose logs -f analyzer"
echo "   • Stop services: docker compose down"
echo "   • Restart: docker compose restart"
echo "   • Health check: curl http://localhost:8000/health"
echo ""
echo "🔑 Don't forget to update your .env file with real API keys!" 