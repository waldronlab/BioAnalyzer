#!/bin/bash

# BioAnalyzer Beta Deployment Script
# This script helps deploy beta versions for testing

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGISTRY="ghcr.io"
IMAGE_NAME="bioanalyzer"
BETA_TAG="beta-$(date +%Y%m%d-%H%M%S)"
CONTAINER_NAME="bioanalyzer-beta-test"

echo -e "${BLUE}🚀 BioAnalyzer Beta Deployment Script${NC}"
echo "=================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Creating a template...${NC}"
    cat > .env << EOF
EMAIL=your_email@example.com
NCBI_API_KEY=your_ncbi_api_key
GEMINI_API_KEY=your_gemini_api_key

# Optional: Override default settings
API_TIMEOUT=30
ANALYSIS_TIMEOUT=25
GEMINI_TIMEOUT=8
FRONTEND_TIMEOUT=30
EOF
    echo -e "${YELLOW}📝 Please edit .env file with your actual API keys before running again.${NC}"
    exit 1
fi

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -t, --tag TAG        Custom tag for the beta image (default: beta-YYYYMMDD-HHMMSS)"
    echo "  -p, --port PORT      Port to expose the application (default: 8000)"
    echo "  -n, --name NAME      Container name (default: bioanalyzer-beta-test)"
    echo "  -b, --build          Build the image locally instead of pulling"
    echo "  -s, --stop           Stop and remove existing beta container"
    echo "  -l, --logs           Show logs from running beta container"
    echo "  -h, --help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --build                    # Build and run locally"
    echo "  $0 --tag my-beta --port 8080  # Use custom tag and port"
    echo "  $0 --stop                     # Stop existing beta container"
    echo "  $0 --logs                     # View logs"
}

# Parse command line arguments
BUILD_LOCAL=false
PORT=8000
STOP_CONTAINER=false
SHOW_LOGS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--tag)
            BETA_TAG="$2"
            shift 2
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -n|--name)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        -b|--build)
            BUILD_LOCAL=true
            shift
            ;;
        -s|--stop)
            STOP_CONTAINER=true
            shift
            ;;
        -l|--logs)
            SHOW_LOGS=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            show_usage
            exit 1
            ;;
    esac
done

# Handle stop command
if [ "$STOP_CONTAINER" = true ]; then
    echo -e "${YELLOW}🛑 Stopping beta container...${NC}"
    if docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
        docker stop $CONTAINER_NAME
        docker rm $CONTAINER_NAME
        echo -e "${GREEN}✅ Beta container stopped and removed${NC}"
    else
        echo -e "${YELLOW}⚠️  No running beta container found${NC}"
    fi
    exit 0
fi

# Handle logs command
if [ "$SHOW_LOGS" = true ]; then
    echo -e "${BLUE}📋 Showing logs for beta container...${NC}"
    if docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
        docker logs -f $CONTAINER_NAME
    else
        echo -e "${YELLOW}⚠️  Beta container is not running${NC}"
    fi
    exit 0
fi

# Stop existing container if running
if docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
    echo -e "${YELLOW}🛑 Stopping existing beta container...${NC}"
    docker stop $CONTAINER_NAME
    docker rm $CONTAINER_NAME
fi

# Build or pull image
if [ "$BUILD_LOCAL" = true ]; then
    echo -e "${BLUE}🔨 Building beta image locally...${NC}"
    docker build -t $REGISTRY/$IMAGE_NAME:$BETA_TAG .
    echo -e "${GREEN}✅ Image built successfully${NC}"
else
    echo -e "${BLUE}📥 Pulling beta image...${NC}"
    # For now, we'll build locally since we don't have a registry set up yet
    echo -e "${YELLOW}⚠️  Building locally (registry not configured yet)${NC}"
    docker build -t $REGISTRY/$IMAGE_NAME:$BETA_TAG .
fi

# Run the container
echo -e "${BLUE}🚀 Starting beta container...${NC}"
docker run -d \
    --name $CONTAINER_NAME \
    -p $PORT:8000 \
    --env-file .env \
    -v $(pwd)/data:/app/data \
    -v $(pwd)/cache:/app/cache \
    -v $(pwd)/results:/app/results \
    $REGISTRY/$IMAGE_NAME:$BETA_TAG

# Wait for container to start
echo -e "${YELLOW}⏳ Waiting for application to start...${NC}"
sleep 10

# Check if container is running
if docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
    echo -e "${GREEN}✅ Beta deployment successful!${NC}"
    echo ""
    echo -e "${BLUE}🌐 Application URLs:${NC}"
    echo "   Frontend: http://localhost:$PORT"
    echo "   API: http://localhost:$PORT/api"
    echo "   Health: http://localhost:$PORT/health"
    echo "   Docs: http://localhost:$PORT/docs"
    echo ""
    echo -e "${BLUE}📋 Container Info:${NC}"
    echo "   Name: $CONTAINER_NAME"
    echo "   Image: $REGISTRY/$IMAGE_NAME:$BETA_TAG"
    echo "   Port: $PORT"
    echo ""
    echo -e "${BLUE}🔧 Management Commands:${NC}"
    echo "   View logs: $0 --logs"
    echo "   Stop: $0 --stop"
    echo "   Restart: $0 --tag $BETA_TAG --port $PORT"
    echo ""
    echo -e "${GREEN}🎉 Ready for testing!${NC}"
else
    echo -e "${RED}❌ Failed to start beta container${NC}"
    echo -e "${YELLOW}📋 Container logs:${NC}"
    docker logs $CONTAINER_NAME
    exit 1
fi
