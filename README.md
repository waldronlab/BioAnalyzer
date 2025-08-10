# BugSigDB Analyzer

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An automated system for identifying microbial signatures in publications. This tool uses machine learning and natural language processing to screen PubMed papers and predict whether they contain microbial differential abundance signatures for curation.  In summery, This tool is to help in identifying curatable papers from PUBMED. 

** Note that after setting up the project and running, focus should be put on the **BROWSE PAPER** tab

## 🚀 Features

- **Automated Paper Analysis**: Analyze scientific papers for microbial signature content
- **PubMed Integration**: Fetch and analyze papers directly from PubMed using PMIDs or DOIs
- **AI-Powered Analysis**: Uses Google Gemini AI for intelligent paper evaluation
- **Methods Scoring**: Quantitative assessment of experimental and analytical methods quality
- **Web Interface**: Modern, responsive web application with real-time analysis
- **Batch Processing**: Analyze multiple papers simultaneously
- **Curation Readiness**: Determine if papers are ready for BugSigDB curation
- **WebSocket Support**: Real-time communication for interactive analysis
- **Comprehensive API**: RESTful API for programmatic access

## 🏗️ Architecture

The project consists of several key components:

- **Web Application** (`web/`): FastAPI-based web server with HTML/JS frontend
- **Models** (`models/`): AI models and QA systems for paper analysis
- **Data Retrieval** (`retrieve/`): PubMed data fetching and processing
- **Utilities** (`utils/`): Text processing, configuration, and helper functions
- **Processing** (`process/`): Data processing and analysis pipelines
- **Classification** (`classify/`): Machine learning classification models

## 📋 Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Git
- NCBI API key (for PubMed access)
- Google Gemini API key (for AI analysis)

## 🛠️ Installation

### 1. Clone the Repository

```bash
git clone https://github.com/waldronlab/BugsigdbAnalyzer.git
cd BugsigdbAnalyzer
```

### 2. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit the `.env` file with your API keys:

```env
# API Keys
NCBI_API_KEY=your_ncbi_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
EMAIL=your_email_here (Optional since user sessions were removed)

# Model Configuration
DEFAULT_MODEL=gemini (Optional)
```

### 5. Get API Keys

#### NCBI API Key
1. Go to [NCBI Account](https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/)
2. Sign in or create an account
3. Generate an API key

#### Google Gemini API Key
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Create an API key

## 🚀 Running the Application

### Quick Start

```bash
python3 start.py
```

The application will start on `http://127.0.0.1:8000`

### Advanced Options

```bash
# Run with custom host and port
python3 start.py --host 0.0.0.0 --port 8080

# Run with HTTPS (requires SSL certificates)
python3 start.py --https --port 8443
```

### Alternative Startup Methods

```bash
# Using uvicorn directly
uvicorn web.app:app --host 127.0.0.1 --port 8000 --reload

# Using Python module
python -m web.app
```

## 🌐 Web Interface

Once running, open your browser and navigate to:

- **Main Interface**: `http://127.0.0.1:8000`
- **API Documentation**: `http://127.0.0.1:8000/docs`
- **Alternative API Docs**: `http://127.0.0.1:8000/redoc`

### Using the Web Interface

1. **Paper Analysis**: Enter a PMID or DOI to analyze a specific paper and Get detailed assessment of experimental methods
2. **Single & Batch Analysis**: Upload a list of PMIDs for bulk processing or a single PMID to Check if papers are curatable
3. **Interactive Chat**: Ask questions about papers using the AI assistant

## 🔌 API Usage

### Core Endpoints

#### Analyze Paper by PMID
```bash
GET /analyze/{pmid}
```

#### Ask Questions About a Paper
```bash
POST /ask_question/{pmid}
{
  "question": "What are the main findings?"
}
```

#### Batch Analysis
```bash
POST /analyze_batch
{
  "pmids": ["12345", "67890", "11111"],
  "page": 1,
  "page_size": 20
}
```

#### Upload Paper File
```bash
POST /upload_paper
# Multipart form with file and optional username
```

#### Fetch Paper by DOI
```bash
GET /fetch_by_doi?doi=10.1000/example
```

### WebSocket Endpoint

```javascript
// Connect to WebSocket for real-time analysis
const ws = new WebSocket('ws://127.0.0.1:8000/ws');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Analysis result:', data);
};

// Send analysis request
ws.send(JSON.stringify({
    type: 'analyze_paper',
    pmid: '12345'
}));
```

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test file
pytest tests/test_app.py

# Run tests with verbose output
pytest -v
```

## 📁 Project Structure

```
BugsigdbAnalyzer/
├── web/                    # Web application
│   ├── app.py             # FastAPI main application
│   ├── app_test.py        # Test application
│   └── static/            # Frontend assets
│       ├── index.html     # Main interface
│       ├── css/           # Stylesheets
│       └── js/            # JavaScript files
├── models/                 # AI models and QA systems
│   ├── gemini_qa.py       # Google Gemini integration
│   ├── unified_qa.py      # Unified QA system
│   ├── conversation_model.py # Conversational AI model
│   └── config.py          # Model configuration
├── retrieve/               # Data retrieval
│   └── data_retrieval.py  # PubMed data fetching
├── utils/                  # Utilities and helpers
│   ├── config.py          # Configuration management
│   ├── text_processing.py # Text processing utilities
│   ├── methods_scorer.py  # Methods quality scoring
│   └── user_manager.py    # User session management
├── process/                # Data processing pipelines
├── classify/               # Classification models
├── data/                   # Data files and datasets
├── tests/                  # Test suite
├── results/                # Analysis results
├── cache/                  # Cached data
├── requirements.txt        # Python dependencies
├── start.py               # Application launcher
└── README.md              # This file
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `NCBI_API_KEY` | NCBI API key for PubMed access | Yes | - |
| `GEMINI_API_KEY` | Google Gemini API key | Yes | - |
| `EMAIL` | Contact email for API requests | Yes | - |
| `DEFAULT_MODEL` | Default AI model to use | No | `gemini` |

### Model Configuration

The system supports multiple AI models:

- **Gemini**: Google's advanced language model (recommended)
- **Custom Models**: PyTorch-based models for specific tasks

## 📊 Data Sources

- **PubMed**: Primary source for scientific papers
- **BugSigDB**: Reference database for microbial signatures
- **Custom Datasets**: Local data files for testing and development

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt

# Set up pre-commit hooks
pre-commit install

# Run linting
flake8 .
black .
```

## 🐛 Troubleshooting

### Common Issues

#### Import Errors
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

#### API Key Issues
```bash
# Check environment variables
echo $NCBI_API_KEY
echo $GEMINI_API_KEY

# Verify .env file exists and is properly formatted
cat .env
```

#### Port Already in Use
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use a different port
python3 start.py --port 8001
```

### Logs and Debugging

Enable debug logging by setting the log level:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📚 API Documentation

For detailed API documentation, visit:
- **Interactive Docs**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **BugSigDB Team**: For the microbial signatures database
- **NCBI**: For PubMed data access
- **Google**: For Gemini AI capabilities
- **FastAPI**: For the excellent web framework

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/BugsigdbAnalyzer/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/BugsigdbAnalyzer/discussions)
- **Email**: [Your Email]

## 🔄 Changelog

### Version 1.0.0
- Initial release
- Basic paper analysis functionality
- Web interface
- PubMed integration
- AI-powered analysis

---

**Happy analyzing! 🧬🔬**
