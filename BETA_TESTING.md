# 🧪 BioAnalyzer Beta Testing Guide

Welcome to BioAnalyzer beta testing! This guide will help you test new features and changes without installing any dependencies.

## 🚀 Quick Start (Recommended)

### Option 1: One-Click Docker Deployment
```bash
# Download and run the beta testing script
curl -sSL https://raw.githubusercontent.com/your-username/BioAnalyzer/main/scripts/deploy-beta.sh | bash
```

### Option 2: Manual Docker Deployment
```bash
# 1. Pull the latest beta image
docker pull ghcr.io/your-username/bioanalyzer:beta-latest

# 2. Run the application
docker run -d \
  --name bioanalyzer-beta \
  -p 8000:8000 \
  -e GEMINI_API_KEY=your_api_key \
  -e NCBI_API_KEY=your_ncbi_key \
  -e EMAIL=your_email \
  ghcr.io/your-username/bioanalyzer:beta-latest

# 3. Access the application
open http://localhost:8000
```

## 🌐 Live Beta URLs

When a PR is created, you'll get a live URL like:
- **Frontend**: `https://bioanalyzer-beta-123.vercel.app`
- **API**: `https://bioanalyzer-beta-123.vercel.app/api`
- **Documentation**: `https://bioanalyzer-beta-123.vercel.app/docs`

## 📋 Testing Checklist

### ✅ Basic Functionality
- [ ] Application loads without errors
- [ ] All navigation links work
- [ ] API endpoints respond correctly
- [ ] Health check passes

### ✅ Paper Analysis Testing
- [ ] Single PMID analysis works
- [ ] Batch CSV upload works
- [ ] Results display correctly
- [ ] Export functionality works
- [ ] Error handling is appropriate

### ✅ UI/UX Testing
- [ ] Interface is responsive on different screen sizes
- [ ] Loading states are clear
- [ ] Error messages are helpful
- [ ] Navigation is intuitive

### ✅ Performance Testing
- [ ] Page load times are reasonable
- [ ] Analysis completes within expected time
- [ ] No memory leaks during extended use

## 🐛 Reporting Issues

When you find an issue, please include:

1. **Description**: What went wrong?
2. **Steps to Reproduce**: How can we recreate it?
3. **Expected Behavior**: What should have happened?
4. **Actual Behavior**: What actually happened?
5. **Screenshots**: If applicable
6. **Environment**: Browser, OS, etc.

### Issue Template
```markdown
## Bug Report

**Description:**
[Brief description of the issue]

**Steps to Reproduce:**
1. Go to '...'
2. Click on '...'
3. Scroll down to '...'
4. See error

**Expected Behavior:**
[What you expected to happen]

**Actual Behavior:**
[What actually happened]

**Screenshots:**
[If applicable, add screenshots]

**Environment:**
- OS: [e.g., Windows 10, macOS 12, Ubuntu 20.04]
- Browser: [e.g., Chrome 91, Firefox 89, Safari 14]
- Beta Version: [e.g., beta-20241215-143022]
```

## 🔧 Advanced Testing

### Testing Specific Features
```bash
# Test with specific environment variables
docker run -d \
  --name bioanalyzer-beta \
  -p 8000:8000 \
  -e GEMINI_API_KEY=your_key \
  -e NCBI_API_KEY=your_key \
  -e EMAIL=your_email \
  -e DEBUG=true \
  -e LOG_LEVEL=DEBUG \
  ghcr.io/your-username/bioanalyzer:beta-latest

# View detailed logs
docker logs -f bioanalyzer-beta
```

### Testing Different Configurations
```bash
# Test with custom timeouts
docker run -d \
  --name bioanalyzer-beta \
  -p 8000:8000 \
  -e API_TIMEOUT=60 \
  -e ANALYSIS_TIMEOUT=120 \
  -e GEMINI_TIMEOUT=30 \
  ghcr.io/your-username/bioanalyzer:beta-latest
```

## 📊 Performance Monitoring

### Check Application Health
```bash
# Health check
curl http://localhost:8000/health

# Detailed metrics
curl http://localhost:8000/metrics

# API status
curl http://localhost:8000/api/status
```

### Monitor Resource Usage
```bash
# Check container stats
docker stats bioanalyzer-beta

# Check logs for errors
docker logs bioanalyzer-beta | grep ERROR

# Check logs for performance
docker logs bioanalyzer-beta | grep "duration\|timeout"
```

## 🧹 Cleanup

### Stop Beta Testing
```bash
# Stop and remove container
docker stop bioanalyzer-beta
docker rm bioanalyzer-beta

# Remove beta images (optional)
docker rmi ghcr.io/your-username/bioanalyzer:beta-latest
```

### Using the Deploy Script
```bash
# Stop beta container
./scripts/deploy-beta.sh --stop

# View logs
./scripts/deploy-beta.sh --logs

# Restart with different settings
./scripts/deploy-beta.sh --tag beta-custom --port 8080
```

## 🆘 Troubleshooting

### Common Issues

**Container won't start:**
```bash
# Check logs
docker logs bioanalyzer-beta

# Check if port is already in use
netstat -tlnp | grep :8000
```

**API errors:**
```bash
# Check environment variables
docker exec bioanalyzer-beta env | grep -E "(GEMINI|NCBI|EMAIL)"

# Test API directly
curl -X GET http://localhost:8000/health
```

**Frontend not loading:**
```bash
# Check if container is running
docker ps | grep bioanalyzer-beta

# Check port mapping
docker port bioanalyzer-beta
```

## 📞 Support

- **GitHub Issues**: [Create an issue](https://github.com/your-username/BioAnalyzer/issues)
- **Discord**: [Join our Discord](https://discord.gg/your-discord)
- **Email**: [Contact us](mailto:support@bioanalyzer.com)

## 🎉 Thank You!

Your testing helps make BioAnalyzer better for everyone. We appreciate your time and feedback!

---

*This beta testing system is designed to make it easy for anyone to test BioAnalyzer without installing dependencies. If you have suggestions for improving this process, please let us know!*
