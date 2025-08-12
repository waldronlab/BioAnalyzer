# 🧬 BugSigDB Analyzer

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-20.0+-blue.svg)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An automated system for identifying microbial signatures in publications. This tool uses machine learning and natural language processing to screen PubMed papers and predict whether they contain microbial differential abundance signatures for curation.

## 🚀 **Quick Start (Docker - Recommended)**

Your project is already configured and ready to run! Here's how to get started:

### **1. Start the Services**
```bash
docker compose up -d
```

### **2. Access Your Application**
- **🌐 Main App**: http://localhost:8000
- **📖 API Docs**: http://localhost:8000/docs
- **🏥 Health Check**: http://localhost:8000/health
- **🔒 Through Nginx**: http://localhost:80

### **3. Check Service Status**
```bash
docker compose ps
```

### **4. View Logs**
```bash
docker compose logs -f
```

## 🏗️ **Architecture**

The project consists of several key components:

- **FastAPI Backend** (`app/`): RESTful API with AI-powered analysis
- **AI Models** (`models/`): Google Gemini integration and ML models
- **Data Retrieval** (`retrieve/`): PubMed data fetching and processing
- **Frontend** (`frontend/`): Modern web interface
- **Nginx** (`deployment/nginx/`): Reverse proxy and load balancer
- **Redis**: Caching and session management
- **Monitoring**: Health checks and metrics

## 📋 **Prerequisites**

### **For Docker (Recommended)**
- Docker 20.0 or higher
- Docker Compose 2.0 or higher

### **For Local Development**
- Python 3.8 or higher
- pip (Python package installer)
- Git

### **API Keys Required**
- NCBI API key (for PubMed access)
- Google Gemini API key (for AI analysis)

## 🛠️ **Installation & Setup**

### **Option 1: Docker (Recommended)**

#### **Quick Start**
```bash
# Clone the repository
git clone https://github.com/waldronlab/BugsigdbAnalyzer.git
cd BugsigdbAnalyzer

# Start the services
docker compose up -d

# Access the application
# - Main app: http://localhost:8000
# - API docs: http://localhost:8000/docs
# - Through Nginx: http://localhost:80
```

#### **Docker Commands Reference**
```bash
# Start services
docker compose up -d

# Stop services
docker compose down

# Restart services
docker compose restart

# View logs
docker compose logs -f

# Check status
docker compose ps

# Rebuild and restart (after code changes)
docker compose down
docker compose up -d --build
```

### **Option 2: Local Development**

#### **1. Clone and Setup**
```bash
git clone https://github.com/waldronlab/BugsigdbAnalyzer.git
cd BugsigdbAnalyzer

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### **2. Environment Configuration**
Create a `.env` file in the project root:

```env
# API Keys
NCBI_API_KEY=your_ncbi_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here

# Model Configuration
DEFAULT_MODEL=gemini
```

#### **3. Run Locally**
```bash
python3 main.py
```

The application will start on `http://127.0.0.1:8000`

## 🌐 **Web Interface**

Once running, access your application:

- **Main Interface**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### **Features**
1. **Paper Analysis**: Enter a PMID or DOI to analyze a specific paper
2. **Batch Processing**: Upload a list of PMIDs for bulk processing
3. **Interactive Chat**: Ask questions about papers using the AI assistant
4. **Methods Scoring**: Quantitative assessment of experimental quality

## 🔌 **API Usage**

### **Core Endpoints**

#### **Analyze Paper by PMID**
```bash
GET /analyze/{pmid}
```

#### **Ask Questions About a Paper**
```bash
POST /ask_question/{pmid}
{
  "question": "What are the main findings?"
}
```

#### **Batch Analysis**
```bash
POST /analyze_batch
{
  "pmids": ["12345", "67890", "11111"],
  "page": 1,
  "page_size": 20
}
```

#### **Upload Paper File**
```bash
POST /upload_paper
# Multipart form with file and optional username
```

#### **Fetch Paper by DOI**
```bash
GET /fetch_by_doi?doi=10.1000/example
```

## 🧪 **Testing**

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test file
pytest tests/test_app.py

# Run tests in Docker
docker exec -it bugsigdb-analyzer pytest
```

## 📁 **Project Structure**

```
BugsigdbAnalyzer/
├── app/                    # FastAPI application code
├── models/                 # AI models and QA systems
├── retrieve/               # PubMed data fetching
├── utils/                  # Utilities and helpers
├── frontend/               # Static frontend files
├── deployment/             # Docker and Nginx configs
│   ├── docker/            # Docker Compose files
│   ├── nginx/             # Nginx configuration
│   └── scripts/           # Setup and utility scripts
├── config/                 # Configuration files
├── docs/                   # Documentation
├── tests/                  # Test suite
├── data/                   # Data files and datasets
├── cache/                  # Cached data
├── results/                # Analysis results
├── docker-compose.yml      # Main Docker Compose
├── Dockerfile              # Production Docker image
├── main.py                 # Application entry point
└── requirements.txt        # Python dependencies
```

## 🔧 **Configuration**

### **Environment Variables**

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `NCBI_API_KEY` | NCBI API key for PubMed access | Yes | - |
| `GEMINI_API_KEY` | Google Gemini API key | Yes | - |
| `DEFAULT_MODEL` | Default AI model to use | No | `gemini` |

### **Docker Services**

- **analyzer** (FastAPI): Port 8000
- **nginx** (Reverse Proxy): Port 80
- **redis** (Cache): Port 6379

## 🐛 **Troubleshooting**

### **Common Issues**

#### **Port Already in Use**
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use Docker (recommended)
docker compose up -d
```

#### **Docker Issues**
```bash
# Check container logs
docker compose logs

# Restart services
docker compose restart

# Clean up Docker resources
docker system prune -a
```

#### **API Key Issues**
```bash
# Check environment variables
echo $NCBI_API_KEY
echo $GEMINI_API_KEY

# Verify .env file exists
cat .env
```

### **Health Checks**

```bash
# Application health
curl http://localhost:8000/health

# Docker service status
docker compose ps

# View logs
docker compose logs -f
```

## 📚 **Documentation**

- **Quick Start**: [QUICK_START.md](QUICK_START.md)
- **Project Structure**: [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
- **API Documentation**: http://localhost:8000/docs (when running)
- **Detailed Docs**: [docs/README.md](docs/README.md)

## 🤝 **Contributing**

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 **Acknowledgments**

- **BugSigDB Team**: For the microbial signatures database
- **NCBI**: For PubMed data access
- **Google**: For Gemini AI capabilities
- **FastAPI**: For the excellent web framework
- **Docker**: For containerization technology

## 📞 **Support**

- **Issues**: [GitHub Issues](https://github.com/waldronlab/BugsigdbAnalyzer/issues)
- **Discussions**: [GitHub Discussions](https://github.com/waldronlab/BugsigdbAnalyzer/discussions)

---

**Happy analyzing! 🧬🔬**

> **Note**: This project is currently running successfully with Docker. All services are healthy and accessible at the URLs provided above. 