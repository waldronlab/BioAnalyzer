#!/bin/bash

# BioAnalyzer Development Script
# This script sets up the development environment with hot reloading

echo "🚀 BioAnalyzer Development Environment"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Create necessary directories
mkdir -p data cache results logs

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating a template..."
    cat > .env << EOF
# BioAnalyzer Environment Variables
NCBI_API_KEY=your_ncbi_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
DEBUG=true
ENVIRONMENT=development
EOF
    echo "📝 Please edit .env file with your API keys"
fi

# Function to start development environment with build
start_dev_build() {
    echo "🔧 Starting development environment with build..."

    # Stop any existing containers
    docker compose -f docker-compose.dev.yml down

    # Build and start development environment
    docker compose -f docker-compose.dev.yml up -d --build

    echo "⏳ Waiting for services to start..."
    sleep 10

    check_services
}

# Function to start development environment without build
start_dev_no_build() {
    echo "🚀 Starting development environment (no build)..."

    # Just start services (assumes they're already built)
    docker compose -f docker-compose.dev.yml up -d

    echo "⏳ Waiting for services to start..."
    sleep 5

    check_services
}

# Function to check service health
check_services() {
    if docker compose -f docker-compose.dev.yml ps | grep -q "healthy"; then
        echo "✅ Development environment is ready!"
        echo "🌐 Frontend: http://localhost"
        echo "🔌 Backend API: http://localhost:8000"
        echo "📚 API Docs: http://localhost:8000/docs"
        echo ""
        echo "💡 Hot reloading is enabled:"
        echo "   - Backend changes will auto-restart the server"
        echo "   - Frontend changes will be reflected immediately"
        echo "   - Just refresh your browser to see changes!"
        echo ""
        echo "📝 To stop: ./dev.sh stop"
        echo "📝 To view logs: ./dev.sh logs"
        echo "📝 To restart: ./dev.sh restart"
    else
        echo "❌ Some services failed to start. Check logs:"
        docker compose -f docker-compose.dev.yml logs
    fi
}

# Function to stop development environment
stop_dev() {
    echo "🛑 Stopping development environment..."
    docker compose -f docker-compose.dev.yml down
    echo "✅ Development environment stopped"
}

# Function to show logs
show_logs() {
    echo "📋 Showing logs..."
    docker compose -f docker-compose.dev.yml logs -f
}

# Function to restart services
restart_dev() {
    echo "🔄 Restarting services..."
    docker compose -f docker-compose.dev.yml restart
    echo "✅ Services restarted"
}

# Function to show status
show_status() {
    echo "📊 Service Status:"
    docker compose -f docker-compose.dev.yml ps
}

# Main script logic
case "${1:-start}" in
    start)
        echo ""
        echo "Choose startup option:"
        echo "1) Start with build (first time or after dependency changes)"
        echo "2) Start without build (daily development - faster)"
        echo "3) Exit"
        echo ""
        read -p "Enter choice (1-3): " choice

        case $choice in
            1)
                start_dev_build
                ;;
            2)
                start_dev_no_build
                ;;
            3)
                echo "Exiting..."
                exit 0
                ;;
            *)
                echo "Invalid choice. Starting with build..."
                start_dev_build
                ;;
        esac
        ;;
    start-build)
        start_dev_build
        ;;
    start-no-build)
        start_dev_no_build
        ;;
    stop)
        stop_dev
        ;;
    restart)
        restart_dev
        ;;
    logs)
        show_logs
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {start|start-build|start-no-build|stop|restart|logs|status}"
        echo ""
        echo "Commands:"
        echo "  start         - Interactive startup (asks if you want to build)"
        echo "  start-build   - Start with build (first time or dependencies changed)"
        echo "  start-no-build- Start without build (daily development - faster)"
        echo "  stop          - Stop development environment"
        echo "  restart       - Restart services"
        echo "  logs          - Show live logs"
        echo "  status        - Show service status"
        echo ""
        echo "Examples:"
        echo "  ./dev.sh              # Interactive startup"
        echo "  ./dev.sh start-build  # Start with build"
        echo "  ./dev.sh start-no-build # Start without build (fastest)"
        echo "  ./dev.sh logs         # Show logs"
        echo ""
        echo "💡 Daily Development Workflow:"
        echo "  1. First time: ./dev.sh start-build"
        echo "  2. Daily use: ./dev.sh start-no-build"
        echo "  3. Make code changes - they auto-reload!"
        echo "  4. Stop when done: ./dev.sh stop"
        exit 1
        ;;
esac 