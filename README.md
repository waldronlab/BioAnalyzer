# MicrobeSig Miner

An automated system for identifying microbial signatures in publications. This tool uses machine learning and natural language processing to screen PubMed papers and predict whether they contain microbial differential abundance signatures for inclusion in the BugSigDB database.

## Features

- Automated screening of PubMed papers for microbial signatures
- Advanced text analysis for detecting:
  - Sequencing methods (16S rRNA, shotgun metagenomics, etc.)
  - Body sites (gut, oral, skin, etc.)
  - Disease categories (IBD, cancer, metabolic disorders, etc.)
- Intelligent confidence scoring based on multiple criteria
- Caching system for efficient API usage
- Comprehensive logging
- Export functionality for analysis results
- Integration with BugSigDB data

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/microbesig-miner.git
cd microbesig-miner
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
   - Copy the example environment file: `cp .env.example .env`
   - Edit the `.env` file and add your API keys:
     ```
     EMAIL=your_email@example.com
     NCBI_API_KEY=your_ncbi_api_key_here
     GEMINI_API_KEY=your_gemini_api_key_here
     SUPERSTUDIO_API_KEY=your_superstudio_api_key_here
     ```

## API Keys

This project requires the following API keys:

1. **NCBI API Key**: For accessing PubMed and PMC data
   - Register at: https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/

2. **Gemini API Key**: For Google's Gemini AI model
   - Get API key at: https://ai.google.dev/

3. **SuperStudio API Key** (optional): For additional AI capabilities

These keys should be stored in your `.env` file, not hardcoded in the source code.

## Project Structure

```
.
├── classify/           # Classification models and logic
├── data/              # Data storage directory
│   └── full_dump.csv  # BugSigDB data dump
├── models/            # Trained model storage
├── process/           # Data processing utilities
├── retrieve/          # Data retrieval modules
├── scripts/           # Utility scripts
├── tests/            # Test suite
├── utils/            # Utility functions
│   └── bugsigdb_analyzer.py  # Main analyzer class
│   └── config.py     # Configuration and environment variables
└── web/              # Web interface components
```

## Usage

### Basic Usage

```python
from utils.bugsigdb_analyzer import BugSigDBAnalyzer

# Initialize analyzer
analyzer = BugSigDBAnalyzer()

# Analyze a single paper
pmid = "12345678"
metadata = analyzer.fetch_paper_metadata(pmid)
analysis = analyzer.analyze_paper(f"{metadata['title']} {metadata['abstract']}")

# Batch analysis
pmids = ["12345678", "23456789", "34567890"]
suggestions = analyzer.suggest_papers_for_review(pmids)
analyzer.export_suggestions(suggestions, "output.json")
```

### Command Line Interface

```bash
python scripts/analyze_papers.py --pmid_list pmids.txt --output results.json --min_confidence 0.4
```

### Parameters

- `--pmid_list`: Path to text file containing PMIDs to analyze
- `--output`: Path for output JSON file
- `--min_confidence`: Minimum confidence threshold (default: 0.4)
- `--cache_dir`: Directory for caching API responses (default: "cache")

## Output Format

The tool generates a JSON file with detailed analysis for each paper:

```json
{
  "pmid": "12345678",
  "title": "Paper Title",
  "abstract": "Paper Abstract",
  "has_signatures": true,
  "confidence": 0.85,
  "sequencing_type": ["16S rRNA", "shotgun metagenomics"],
  "body_sites": ["gut"],
  "disease_categories": ["IBD"],
  "relevant_terms": {
    "general": ["microbiome", "abundance"],
    "methods": ["16s rrna", "shotgun"],
    "analysis": ["differential", "enriched"]
  },
  "analysis_date": "2024-03-14T12:00:00",
  "authors": ["Author 1", "Author 2"],
  "journal": "Journal Name",
  "pubdate": "2024-01"
}
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

### Development Setup

1. Fork the repository
2. Create a development branch
3. Install development dependencies:
```bash
pip install -r requirements.txt
```
4. Run tests:
```bash
pytest
```

## License

This project is licensed under the Creative Commons Attribution 4.0 and Open Data Commons Attribution License.

## Attribution

This tool integrates with BugSigDB (https://bugsigdb.org/). When using this tool, please cite:

[BugSigDB citation information]

## Acknowledgments

- BugSigDB team for providing the database and support
- NCBI for providing the E-utilities API
- Contributors and maintainers of the project 