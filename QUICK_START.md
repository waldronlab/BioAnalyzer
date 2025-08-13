# 🚀 BugSigDB Analyzer - Quick Start Guide

Welcome to the  BugSigDB Analyzer! This guide will help you get started quickly with the project.

## 📁 **What Changed?**

The project is organised to improve maintainability:

- **`app/`** - All the application code
- **`deployment/`** - All Docker, Nginx, and deployment files
- **`frontend/`** - All static frontend files
- **`config/`** - All configuration files
- **`docs/` - All documentation

## ⚡ **Quick Start Options**

### **Option 1: Local Development (Recommended for developers)**
```bash
# 1. Setup local environment
./setup.sh

# 2. Run the application
python3 main.py

# 3. Open in browser
# http://127.0.0.1:8000
```

### **Option 2: Docker Development (Recommended for DevOps)**
```bash
# 1. Setup Docker environment
./deployment/scripts/docker-setup.sh

# 2. View running services
docker compose -f deployment/docker/docker-compose.dev.yml ps

# 3. Access services
# App: http://localhost:8000
# Nginx: http://localhost:8080
# Redis: localhost:6379
```

### **Option 3: Production Docker**
```bash
# 1. Deploy production stack
docker compose -f deployment/docker/docker-compose.prod.yml up -d

# 2. Monitor health
./deployment/scripts/docker-health-check.sh

# 3. Access production
# App: http://localhost:8000
# Nginx: http://localhost:80
# Prometheus: http://localhost:9090
```

## 🔧 **Key Commands**

### **Development**
```bash
# Run locally
python3 main.py

# Run tests
python3 -m pytest

# Format code
python3 -m black app/
```

### **Docker**
```bash
# Development
docker compose -f deployment/docker/docker-compose.dev.yml up -d
docker compose -f deployment/docker/docker-compose.dev.yml down

# Production
docker compose -f deployment/docker/docker-compose.prod.yml up -d
docker compose -f deployment/docker/docker-compose.prod.yml down

# View logs
docker compose -f deployment/docker/docker-compose.dev.yml logs -f app
```

### **Health Checks**
```bash
# Application health
curl http://localhost:8000/health

# Application metrics
curl http://localhost:8000/metrics

# Docker health check
./deployment/scripts/docker-health-check.sh
```

## 📁 **Where to Find Things**

### **🔍 Looking for code?**
- **API endpoints**: `app/api/app.py`
- **Business logic**: `app/services/`
- **Data models**: `app/models/`
- **Utilities**: `app/utils/`

### **🐳 Looking for Docker?**
- **Dockerfiles**: `deployment/docker/`
- **Compose files**: `deployment/docker/`
- **Setup scripts**: `deployment/scripts/`

### **🌐 Looking for Nginx?**
- **Configs**: `deployment/nginx/`
- **SSL certs**: `deployment/nginx/ssl/`

### **📊 Looking for monitoring?**
- **Prometheus**: `deployment/monitoring/`
- **Health checks**: `deployment/scripts/docker-health-check.sh`

### **📚 Looking for docs?**
- **Main docs**: `docs/README.md`
- **Docker guide**: `docs/DOCKER_DEPLOYMENT.md`
- **Project structure**: `PROJECT_STRUCTURE.md`


### **Docker Contexts **
All Docker builds  use the project root as context, so paths in Dockerfiles are relative to the root.

## 🆘 **Need Help?**

### **Common Issues**

1. **"Module not found" errors**
   - Update import paths to use `app.` prefix
   - See import examples above

2. **Docker build failures**
   - Make sure you're running from project root
   - Check that all files are in correct locations

3. **Nginx configuration errors**
   - Verify paths in `deployment/nginx/`
   - Check Docker volume mounts

### **Getting Support**

- **Documentation**: Check `docs/` directory
- **Project Structure**: See `PROJECT_STRUCTURE.md`
- **Docker Issues**: See `docs/DOCKER_DEPLOYMENT.md`

## 🎯 **Next Steps**

1. **Choose your setup method** (Local vs Docker)
2. **Run the setup script** for your chosen method
3. **Test the application** to ensure everything works
4. **Explore the structure** to get familiar with it

---

**🎉 Congratulations!** You're now ready to work with BugSigDB Analyzer.
