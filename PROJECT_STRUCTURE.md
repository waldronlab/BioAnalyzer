# 🏗️ BugSigDB Analyzer - Project Structure

This document provides a comprehensive overview of the reorganized project structure for the BugSigDB Analyzer.

## 📁 **Root Directory Structure**

```
BugsigdbAnalyzer/
├── 📁 app/                    # Main application code
├── 📁 deployment/             # All deployment-related files
├── 📁 frontend/               # Frontend static files
├── 📁 tests/                  # Test files
├── 📁 docs/                   # Documentation
├── 📁 data/                   # Data files
├── 📁 cache/                  # Cache files
├── 📁 results/                # Output results
├── 📁 config/                 # Configuration files
├── 📁 .venv/                  # Python virtual environment
├── 📄 main.py                 # Main entry point
├── 📄 .env                    # Environment variables
├── 📄 .gitignore              # Git ignore rules
└── 📄 PROJECT_STRUCTURE.md    # This file
```

## 🚀 **Application Code (`app/`)**

### **`app/api/`** - API Layer
- **`app.py`** - Main FastAPI application with all endpoints
- **`app_test.py`** - API testing utilities

### **`app/core/`** - Core Business Logic
- Core application logic and business rules
- Configuration management
- Application settings

### **`app/models/`** - Data Models
- **`config.py`** - Model configuration classes
- **`unified_qa.py`** - Unified QA system implementation
- **`gemini_qa.py`** - Gemini AI integration

### **`app/services/`** - Business Services
- **`data_retrieval.py`** - PubMed data retrieval service
- **`methods_scorer.py`** - Methods scoring service
- **`classify/`** - Classification services
- **`process/`** - Data processing services

### **`app/utils/`** - Utility Functions
- **`text_processing.py`** - Text processing utilities
- **`config.py`** - Configuration utilities
- **`methods_scorer.py`** - Methods scoring utilities

## 🐳 **Deployment (`deployment/`)**

### **`deployment/docker/`** - Docker Configuration
- **`Dockerfile`** - Production Docker image
- **`Dockerfile.dev`** - Development Docker image
- **`nginx.Dockerfile`** - Custom Nginx Docker image
- **`docker-compose.yml`** - Base Docker Compose configuration
- **`docker-compose.dev.yml`** - Development environment
- **`docker-compose.prod.yml`** - Production environment
- **`.dockerignore`** - Docker build exclusions

### **`deployment/nginx/`** - Nginx Configuration
- **`nginx.conf`** - Production Nginx configuration
- **`nginx.dev.conf`** - Development Nginx configuration
- **`ssl/`** - SSL certificates (for HTTPS)
- **`error_pages/`** - Custom error pages

### **`deployment/monitoring/`** - Monitoring & Metrics
- **`prometheus.yml`** - Prometheus configuration
- **`grafana/`** - Grafana dashboards (future)

### **`deployment/scripts/`** - Setup & Maintenance
- **`docker-setup.sh`** - Docker environment setup
- **`docker-setup.bat`** - Windows Docker setup
- **`docker-health-check.sh`** - Docker health monitoring
- **`setup.sh`** - Local development setup
- **`setup.bat`** - Windows development setup

## 🎨 **Frontend (`frontend/`)**
- **`index.html`** - Main application page
- **`css/`** - Stylesheets
- **`js/`** - JavaScript files
- **`images/`** - Images and icons

## 📚 **Documentation (`docs/`)**
- **`README.md`** - Main project documentation
- **`QUICKSTART.md`** - Quick start guide
- **`DOCKER_DEPLOYMENT.md`** - Docker deployment guide

## ⚙️ **Configuration (`config/`)**
- **`requirements.txt`** - Python dependencies
- **`pytest.ini`** - Test configuration
- **`setup.py`** - Package setup
- **`run.py`** - Alternative entry point
- **`start.py`** - Legacy entry point

## 🔧 **Key Benefits of New Structure**

### **1. Clear Separation of Concerns**
- **Application Logic**: All business logic is in `app/`
- **Deployment**: All deployment files are in `deployment/`
- **Configuration**: All config files are in `config/`

### **2. Easy Navigation**
- **Developers**: Focus on `app/` for code changes
- **DevOps**: Focus on `deployment/` for infrastructure
- **Users**: Focus on `docs/` for documentation

### **3. Scalable Architecture**
- **Modular Design**: Easy to add new services
- **Clear Dependencies**: Well-defined import paths
- **Environment Separation**: Development vs Production

### **4. Docker Integration**
- **Optimized Builds**: Better layer caching
- **Clear Contexts**: Proper build paths
- **Health Checks**: Comprehensive monitoring

## 🚀 **Getting Started**

### **Local Development**
```bash
# Setup local environment
./setup.sh

# Run the application
python3 main.py
```

### **Docker Development**
```bash
# Setup Docker environment
./deployment/scripts/docker-setup.sh

# View running services
docker compose -f deployment/docker/docker-compose.dev.yml ps
```

### **Production Deployment**
```bash
# Deploy production stack
docker compose -f deployment/docker/docker-compose.prod.yml up -d

# Monitor services
./deployment/scripts/docker-health-check.sh
```

