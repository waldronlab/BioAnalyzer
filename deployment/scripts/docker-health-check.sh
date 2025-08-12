#!/bin/bash

# BugSigDB Analyzer Docker Health Check Script
# This script performs comprehensive health checks on all Docker services

set -e

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

echo "🏥 BugSigDB Analyzer Docker Health Check"
echo "========================================"

# Check if Docker is running
if ! docker info &> /dev/null; then
    print_error "Docker daemon is not running"
    exit 1
fi

# Check if containers are running
print_status "Checking container status..."

# Check app container
if docker ps --format "table {{.Names}}\t{{.Status}}" | grep -q "bugsigdb-analyzer-app"; then
    APP_STATUS=$(docker ps --format "table {{.Names}}\t{{.Status}}" | grep "bugsigdb-analyzer-app")
    print_success "App container: $APP_STATUS"
else
    print_error "App container is not running"
fi

# Check nginx container
if docker ps --format "table {{.Names}}\t{{.Status}}" | grep -q "bugsigdb-analyzer-nginx"; then
    NGINX_STATUS=$(docker ps --format "table {{.Names}}\t{{.Status}}" | grep "bugsigdb-analyzer-nginx")
    print_success "Nginx container: $NGINX_STATUS"
else
    print_error "Nginx container is not running"
fi

# Check redis container
if docker ps --format "table {{.Names}}\t{{.Status}}" | grep -q "bugsigdb-analyzer-redis"; then
    REDIS_STATUS=$(docker ps --format "table {{.Names}}\t{{.Status}}" | grep "bugsigdb-analyzer-redis")
    print_success "Redis container: $REDIS_STATUS"
else
    print_warning "Redis container is not running (optional)"
fi

# Check prometheus container (if running)
if docker ps --format "table {{.Names}}\t{{.Status}}" | grep -q "bugsigdb-analyzer-prometheus"; then
    PROMETHEUS_STATUS=$(docker ps --format "table {{.Names}}\t{{.Status}}" | grep "bugsigdb-analyzer-prometheus")
    print_success "Prometheus container: $PROMETHEUS_STATUS"
fi

echo ""
print_status "Checking service health..."

# Check app health endpoint
if curl -f http://localhost:8000/health &> /dev/null; then
    print_success "App health check: OK"
else
    print_error "App health check: FAILED"
fi

# Check nginx health endpoint
if curl -f http://localhost/health &> /dev/null; then
    print_success "Nginx health check: OK"
else
    print_error "Nginx health check: FAILED"
fi

# Check Redis connectivity
if docker exec bugsigdb-analyzer-redis redis-cli ping &> /dev/null; then
    print_success "Redis connectivity: OK"
else
    print_warning "Redis connectivity: FAILED (optional)"
fi

echo ""
print_status "Checking resource usage..."

# Check container resource usage
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

echo ""
print_status "Checking logs for errors..."

# Check recent logs for errors
echo "Recent app logs (last 10 lines):"
docker logs --tail 10 bugsigdb-analyzer-app 2>&1 | grep -i "error\|exception\|fail" || echo "No errors found in recent logs"

echo ""
echo "Recent nginx logs (last 10 lines):"
docker logs --tail 10 bugsigdb-analyzer-nginx 2>&1 | grep -i "error\|exception\|fail" || echo "No errors found in recent logs"

echo ""
print_status "Health check completed!"

# Summary
echo ""
echo "📊 Summary:"
echo "==========="
if docker ps --format "table {{.Names}}\t{{.Status}}" | grep -q "bugsigdb-analyzer-app.*Up"; then
    echo "✅ App: Running"
else
    echo "❌ App: Not running"
fi

if docker ps --format "table {{.Names}}\t{{.Status}}" | grep -q "bugsigdb-analyzer-nginx.*Up"; then
    echo "✅ Nginx: Running"
else
    echo "❌ Nginx: Not running"
fi

if docker ps --format "table {{.Names}}\t{{.Status}}" | grep -q "bugsigdb-analyzer-redis.*Up"; then
    echo "✅ Redis: Running"
else
    echo "⚠️  Redis: Not running (optional)"
fi

echo ""
echo "🌐 Access URLs:"
echo "==============="
echo "App (direct): http://localhost:8000"
echo "App (via Nginx): http://localhost"
echo "API docs: http://localhost:8000/docs"
echo "Health check: http://localhost:8000/health"
echo "Metrics: http://localhost:8000/metrics" 