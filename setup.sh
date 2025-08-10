#!/bin/bash

# BugSigDB Analyzer Setup Script
# This script automates the setup process for Linux/Mac users

set -e  # Exit on any error

echo "🚀 BugSigDB Analyzer Setup Script"
echo "=================================="

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

# Check prerequisites
print_status "Checking prerequisites..."

# Check Python version
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    if [[ $(echo "$PYTHON_VERSION >= 3.8" | bc -l) -eq 1 ]]; then
        print_success "Python 3.8+ found: $(python3 --version)"
    else
        print_error "Python 3.8+ required, found: $(python3 --version)"
        exit 1
    fi
else
    print_error "Python 3 not found. Please install Python 3.8+ first."
    exit 1
fi

# Check pip
if command -v pip3 &> /dev/null; then
    print_success "pip3 found"
else
    print_error "pip3 not found. Please install pip3 first."
    exit 1
fi

# Check git
if command -v git &> /dev/null; then
    print_success "git found"
else
    print_error "git not found. Please install git first."
    exit 1
fi

print_status "All prerequisites satisfied!"

# Create virtual environment
print_status "Creating virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    print_success "Virtual environment created"
else
    print_warning "Virtual environment already exists"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source .venv/bin/activate
print_success "Virtual environment activated"

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
print_status "Installing dependencies..."
pip install -r requirements.txt
print_success "Dependencies installed"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    print_status "Creating .env file..."
    cat > .env << EOF
# API Keys - Replace with your actual keys
NCBI_API_KEY=your_ncbi_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
EMAIL=your_email@example.com

# Model Configuration
DEFAULT_MODEL=gemini
EOF
    print_success ".env file created"
    print_warning "Please edit .env file with your actual API keys before running the application"
else
    print_warning ".env file already exists"
fi

# Create results and cache directories
print_status "Creating necessary directories..."
mkdir -p results cache data
print_success "Directories created"

# Make start.py executable
print_status "Making start script executable..."
chmod +x start.py

print_success "Setup completed successfully!"
echo ""
echo "🎉 Next steps:"
echo "1. Edit .env file with your API keys:"
echo "   nano .env"
echo ""
echo "2. Run the application:"
echo "   python3 start.py"
echo ""
echo "3. Open your browser and go to:"
echo "   http://127.0.0.1:8000"
echo ""
echo "📚 For more information, see README.md and QUICKSTART.md"
echo ""
echo "🔑 To get API keys:"
echo "   - NCBI: https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/"
echo "   - Gemini: https://makersuite.google.com/app/apikey" 