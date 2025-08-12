#!/bin/bash

# BugSigDB Analyzer Docker Setup Script
# This script automates the Docker environment setup

set -e  # Exit on any error

echo "🐳 BugSigDB Analyzer Docker Setup Script"
echo "========================================="

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
print_status "Checking Docker status..."
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi
print_success "Docker is running"

# Check if docker compose is available
print_status "Checking Docker Compose..."
if docker compose version > /dev/null 2>&1; then
    print_success "Docker Compose is available"
    DOCKER_COMPOSE_CMD="docker compose"
elif docker-compose --version > /dev/null 2>&1; then
    print_success "Docker Compose (standalone) is available"
    DOCKER_COMPOSE_CMD="docker-compose"
else
    print_error "Docker Compose is not available. Please install Docker Compose first."
    exit 1
fi

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p ../nginx/ssl
mkdir -p ../nginx/error_pages
mkdir -p ../monitoring

# Create .env file if it doesn't exist
if [ ! -f "../../.env" ]; then
    print_status "Creating .env file..."
    cat > ../../.env << EOF
# API Keys - Replace with your actual keys
NCBI_API_KEY=your_ncbi_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
EMAIL=your_email@example.com

# Model Configuration
DEFAULT_MODEL=gemini

# Application Configuration
DEBUG=true
LOG_LEVEL=INFO

# Docker Configuration
COMPOSE_PROJECT_NAME=bugsigdb-analyzer
EOF
    print_success ".env file created"
    print_warning "Please edit .env file with your actual API keys before running the application"
else
    print_warning ".env file already exists"
fi

# Create basic prometheus.yml if it doesn't exist
if [ ! -f "../monitoring/prometheus.yml" ]; then
    print_status "Creating basic Prometheus configuration..."
    cat > ../monitoring/prometheus.yml << EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'bugsigdb-analyzer'
    static_configs:
      - targets: ['app:8000']
    metrics_path: '/metrics'
    scrape_interval: 5s
    scrape_timeout: 10s

  - job_name: 'nginx'
    static_configs:
      - targets: ['nginx:80']
    metrics_path: '/nginx_status'
    scrape_interval: 10s

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']
    scrape_interval: 10s
EOF
    print_success "Prometheus configuration created"
fi

# Build and start development environment
print_status "Building development Docker environment..."
cd ..
$DOCKER_COMPOSE_CMD -f docker/docker-compose.dev.yml build

print_status "Starting development environment..."
$DOCKER_COMPOSE_CMD -f docker/docker-compose.dev.yml up -d

print_success "Docker environment setup completed!"
echo ""
echo "🎉 Your Docker environment is now running!"
echo ""
echo "📊 Services status:"
echo "   - App: http://localhost:8000"
echo "   - Nginx: http://localhost:80"
echo "   - Redis: localhost:6379"
echo "   - Prometheus: http://localhost:9090"
echo ""
echo "🔍 Health check:"
echo "   - App health: http://localhost:8000/health"
echo "   - App metrics: http://localhost:8000/metrics"
echo ""
echo "📚 Useful commands:"
echo "   - View logs: $DOCKER_COMPOSE_CMD -f docker/docker-compose.dev.yml logs -f"
echo "   - Stop services: $DOCKER_COMPOSE_CMD -f docker/docker-compose.dev.yml down"
echo "   - Restart services: $DOCKER_COMPOSE_CMD -f docker/docker-compose.dev.yml restart"
echo ""
echo "🐳 For production deployment, see docs/DOCKER_DEPLOYMENT.md" 