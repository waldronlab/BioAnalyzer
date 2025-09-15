# 🚀 BioAnalyzer Beta Testing Setup Guide

This guide will help you set up automated beta releases for easy testing by your US-based team without requiring them to install dependencies.

## 📋 Overview

The beta testing system provides:
- **Automated Docker builds** on every PR
- **One-click deployment** for testers
- **Live preview URLs** for immediate testing
- **Easy sharing** via generated links
- **Comprehensive feedback collection**

## 🛠️ Setup Instructions

### 1. GitHub Repository Setup

#### Enable GitHub Container Registry
1. Go to your repository settings
2. Navigate to "Actions" → "General"
3. Under "Workflow permissions", select "Read and write permissions"
4. Check "Allow GitHub Actions to create and approve pull requests"

#### Update GitHub Actions Workflow
The workflow file is already created at `.github/workflows/beta-release.yml`. You need to:

1. **Update the registry URL** in the workflow:
   ```yaml
   env:
     REGISTRY: ghcr.io
     IMAGE_NAME: ${{ github.repository }}  # This will be your-username/BioAnalyzer
   ```

2. **Update the image references** in the workflow:
   ```yaml
   # Replace "your-username" with your actual GitHub username
   ghcr.io/your-username/bioanalyzer:${imageTag}
   ```

### 2. Docker Registry Configuration

#### Create GitHub Personal Access Token
1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Create a new token with these permissions:
   - `write:packages`
   - `read:packages`
   - `delete:packages`
3. Save the token securely

#### Configure Repository Secrets
Add these secrets to your repository:
- `GITHUB_TOKEN` (automatically available)
- `DOCKER_USERNAME` (your GitHub username)
- `DOCKER_PASSWORD` (your personal access token)

### 3. Update Configuration Files

#### Update Docker Image References
Replace all instances of `your-username` with your actual GitHub username:

```bash
# Find and replace in these files:
grep -r "your-username" . --include="*.yml" --include="*.py" --include="*.md"
```

#### Update API Endpoints
Update the base URLs in:
- `frontend/beta-deploy.html`
- `scripts/generate-beta-link.py`
- `app/api/beta_deployment.py`

### 4. Test the Setup

#### Test Local Beta Deployment
```bash
# Make the script executable
chmod +x scripts/deploy-beta.sh

# Test local deployment
./scripts/deploy-beta.sh --build --port 8080

# Check if it's running
curl http://localhost:8080/health
```

#### Test Beta Link Generation
```bash
# Generate a test link
python3 scripts/generate-beta-link.py \
  --pr 123 \
  --api-key "your_test_key" \
  --ncbi-key "your_ncbi_key" \
  --email "test@example.com" \
  --port 8000
```

## 🎯 How It Works

### For Developers (You)

1. **Create a PR** with your changes
2. **GitHub Actions automatically**:
   - Builds a Docker image
   - Pushes to GitHub Container Registry
   - Creates a comment with deployment info
   - Provides testing URLs and commands

3. **Share the PR** with your US team
4. **They can test immediately** using the provided links

### For Testers (US Team)

1. **Receive PR notification** with beta testing info
2. **Choose testing method**:
   - **Option A**: Use the live preview URL (if configured)
   - **Option B**: Run Docker commands locally
   - **Option C**: Use the web interface

3. **Test the application** and provide feedback
4. **Submit feedback** via GitHub issues

## 📱 Testing Methods

### Method 1: Live Preview URLs (Recommended)
- **Pros**: No installation required, instant access
- **Cons**: Requires additional hosting setup (Vercel, Netlify, etc.)

### Method 2: Docker Commands
- **Pros**: Full control, offline testing
- **Cons**: Requires Docker installation

### Method 3: Web Interface
- **Pros**: User-friendly, guided setup
- **Cons**: Requires local Docker installation

## 🔧 Advanced Configuration

### Custom Docker Registry
If you want to use a different registry:

1. Update `.github/workflows/beta-release.yml`:
   ```yaml
   env:
     REGISTRY: your-registry.com
     IMAGE_NAME: your-org/bioanalyzer
   ```

2. Update authentication in the workflow
3. Update image references in all files

### Custom Deployment URLs
For live preview URLs, you can integrate with:
- **Vercel**: For automatic deployments
- **Netlify**: For static site hosting
- **Railway**: For full-stack applications
- **Render**: For containerized applications

### Notification Setup
Configure notifications for:
- **Slack**: PR notifications
- **Discord**: Beta release alerts
- **Email**: Testing reminders

## 📊 Monitoring and Analytics

### GitHub Actions Monitoring
- View workflow runs in the "Actions" tab
- Monitor build times and success rates
- Debug failed deployments

### Container Registry Management
- View published images in "Packages"
- Monitor storage usage
- Clean up old beta images

### Feedback Collection
- Use GitHub issues for structured feedback
- Track testing progress
- Monitor bug reports and feature requests

## 🚨 Troubleshooting

### Common Issues

#### Docker Build Failures
```bash
# Check Docker daemon
docker info

# Test Docker build locally
docker build -t test-image .

# Check GitHub Actions logs
```

#### Registry Push Failures
```bash
# Verify authentication
docker login ghcr.io

# Check token permissions
# Ensure token has write:packages permission
```

#### Container Runtime Issues
```bash
# Check container logs
docker logs container-name

# Verify environment variables
docker exec container-name env

# Test health endpoint
curl http://localhost:8000/health
```

### Debug Commands

```bash
# Check GitHub Actions status
gh run list

# View workflow logs
gh run view [run-id]

# Test Docker image locally
docker run -it --rm ghcr.io/your-username/bioanalyzer:beta-latest

# Check registry images
gh api /user/packages/container/bioanalyzer/versions
```

## 📈 Best Practices

### For Developers
1. **Test locally** before creating PRs
2. **Use descriptive PR titles** for easy identification
3. **Include testing instructions** in PR descriptions
4. **Monitor feedback** and respond promptly

### For Testers
1. **Test systematically** using the provided checklist
2. **Report issues promptly** with detailed information
3. **Test on multiple browsers/devices** when possible
4. **Provide constructive feedback**

### For Maintenance
1. **Clean up old beta images** regularly
2. **Monitor storage usage** in the registry
3. **Update dependencies** periodically
4. **Review and improve** the testing process

## 🎉 Success Metrics

Track these metrics to measure success:
- **Deployment Success Rate**: % of successful beta deployments
- **Testing Participation**: Number of testers per PR
- **Issue Resolution Time**: Time from report to fix
- **Feedback Quality**: Completeness and usefulness of feedback

## 📞 Support

If you encounter issues:
1. **Check the troubleshooting section** above
2. **Review GitHub Actions logs** for build issues
3. **Create an issue** in the repository
4. **Contact the development team** for urgent issues

---

**Happy Testing! 🧪✨**

This beta testing system will make it much easier for your US-based team to test BioAnalyzer without the hassle of installing dependencies. The automated workflow ensures they always have access to the latest changes for testing.
