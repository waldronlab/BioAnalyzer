# BioAnalyzer

A scientific paper analysis tool focused on microbiome research and BugSigDB curation readiness.

## Features

- **Browse Papers**: Search papers by PMID and analyze them for BugSigDB curation readiness
- **Chat Assistant**: Interactive AI-powered assistance for analysis questions

## Key BugSigDB Curation Fields

The system analyzes papers for the following 6 essential fields that determine curation readiness:

1. **Host Species**: Primary organism being studied
2. **Body Site**: Microbiome sample collection location  
3. **Condition**: Disease/treatment/exposure being studied
4. **Sequencing Type**: Molecular method used (16S, metagenomics, etc.)
5. **Taxa Level**: Taxonomic level analyzed (phylum, genus, species, etc.)
6. **Sample Size**: Number of samples analyzed

**Curation Readiness**: A paper is considered ready for curation when all 6 fields are present and well-documented.

## Architecture

- **FastAPI Backend**: Python-based API server with AI-powered analysis
- **AI Models**: Integration with Google Gemini for intelligent paper analysis
- **Frontend**: Modern web interface built with Bootstrap and vanilla JavaScript
- **Core Functionality**: Automated extraction and assessment of curation fields from scientific papers

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- API Keys:
  - NCBI API key for PubMed access
  - Google Gemini API key for AI analysis

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd BioAnalyzer
```

2. Create environment file:
```bash
cp .env.example .env
# Edit .env with your API keys
```

3. Start the development environment:
```bash
./dev.sh start-build
```

## Development

The development environment includes hot reloading:

```bash
# Start with build (first time)
./dev.sh start-build

# Start without build (daily development)
./dev.sh start-no-build

# Stop services
./dev.sh stop

# View logs
./dev.sh logs

# Check status
./dev.sh status
```

## API Usage

### Enhanced Analysis

#### Single Paper Analysis
```bash
POST /enhanced_analysis/{pmid}
```
Analyze a single paper for BugSigDB curation readiness.

#### Batch Analysis
```bash
POST /enhanced_analysis_batch
```
Analyze multiple papers for BugSigDB curation readiness.

#### Curation Statistics
```bash
GET /curation/statistics
```
Get statistics about how well the 6 essential curation fields are being identified across all analyzed papers.

## License

[Your License Here] 
