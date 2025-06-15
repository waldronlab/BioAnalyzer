#!/usr/bin/env python3

import argparse
import logging
import pandas as pd
from typing import Optional, Dict, List
from retrieve.data_retrieval import PubMedRetriever
from models.unified_qa import UnifiedQA
import os
import sys
from pathlib import Path
import json
from datetime import datetime
import asyncio
import pytz

# Add parent directory to path to allow importing utils.config
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.config import NCBI_API_KEY, OPENAI_API_KEY, EMAIL
from utils.data_processor import clean_scientific_text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_bugsigdb_data(filepath: str = "full_dump.csv") -> pd.DataFrame:
    """Load BugSigDB data from CSV.
    
    Args:
        filepath: Path to the BugSigDB dump file
        
    Returns:
        DataFrame containing BugSigDB data
    """
    # Skip the header comment line
    df = pd.read_csv(filepath, skiprows=1)
    # Filter out entries without PMIDs
    df = df[df['PMID'].notna() & (df['PMID'] != 'NA')]
    # Convert PMID to string
    df['PMID'] = df['PMID'].astype(str)
    return df

async def analyze_paper(
    paper_content: dict,
    models_to_use: list = None,
    output_dir: str = None
) -> dict:
    """Analyze a paper using the UnifiedQA system.
    
    Args:
        paper_content: Dictionary containing paper content
        models_to_use: List of models to use (default: all available)
        output_dir: Directory to save results (optional)
        
    Returns:
        Dictionary containing analysis results
    """
    # Initialize UnifiedQA with OpenAI
    qa_system = UnifiedQA(
        use_openai=True,
        use_gemini=False,
        openai_api_key=OPENAI_API_KEY,
        gemini_api_key=None
    )
    
    # Run analysis
    results = await qa_system.analyze_paper(paper_content)
    
    # Save results if output directory is provided
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now(pytz.UTC).strftime("%Y%m%d_%H%M%S")
        paper_title = paper_content.get('title', 'unknown').replace(' ', '_')
        filename = output_path / f"analysis_{timestamp}_{paper_title[:50]}.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {filename}")
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Analyze a paper from BugSigDB")
    parser.add_argument("--title", help="Paper title")
    parser.add_argument("--abstract", help="Paper abstract")
    parser.add_argument("--full_text", help="Paper full text")
    parser.add_argument("--output_dir", help="Directory to save results")
    parser.add_argument("--models", nargs="+", help="Specific models to use (openai)")
    
    args = parser.parse_args()
    
    # Prepare paper content
    paper_content = {
        "title": args.title or "",
        "abstract": args.abstract or "",
        "full_text": args.full_text or ""
    }
    
    # Run analysis
    results = asyncio.run(analyze_paper(
        paper_content=paper_content,
        models_to_use=args.models,
        output_dir=args.output_dir
    ))
    
    # Print results
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main() 