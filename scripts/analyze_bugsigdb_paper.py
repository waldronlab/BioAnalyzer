#!/usr/bin/env python3

import argparse
import logging
import pandas as pd
from typing import Optional
from retrieve.data_retrieval import PubMedRetriever
from models.unified_qa import UnifiedQA
import os
import sys

# Add parent directory to path to allow importing utils.config
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.config import NCBI_API_KEY, GEMINI_API_KEY, SUPERSTUDIO_API_KEY, EMAIL

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

async def analyze_bugsigdb_paper(
    pmid: Optional[str] = None,
    random: bool = False,
    custom_questions: Optional[list] = None,
    models: Optional[list] = None
):
    """Analyze a paper from BugSigDB using multiple models.
    
    Args:
        pmid: Specific PMID to analyze
        random: Whether to analyze a random paper
        custom_questions: Optional list of custom questions
        models: Optional list of models to use
    """
    # Load BugSigDB data
    try:
        df = load_bugsigdb_data()
        logger.info(f"Loaded {len(df)} entries from BugSigDB")
    except Exception as e:
        logger.error(f"Error loading BugSigDB data: {str(e)}")
        return
    
    # Select paper
    if pmid:
        paper_data = df[df['PMID'] == pmid]
        if len(paper_data) == 0:
            logger.error(f"PMID {pmid} not found in BugSigDB")
            return
    elif random:
        paper_data = df.sample(n=1)
    else:
        paper_data = df.iloc[0:1]
    
    pmid = str(paper_data['PMID'].iloc[0])
    logger.info(f"Analyzing paper with PMID: {pmid}")
    
    # Initialize components
    retriever = PubMedRetriever(api_key=NCBI_API_KEY)
    qa_system = UnifiedQA(
        use_superstudio=bool(SUPERSTUDIO_API_KEY),
        use_gemini=bool(GEMINI_API_KEY),
        use_biobert=True,
        superstudio_api_key=SUPERSTUDIO_API_KEY,
        gemini_api_key=GEMINI_API_KEY
    )
    
    try:
        # Retrieve paper content
        metadata = retriever.get_paper_metadata(pmid)
        full_text = retriever.get_pmc_fulltext(pmid)
        
        paper_content = {
            "title": metadata["title"],
            "abstract": metadata["abstract"],
            "full_text": full_text if full_text else ""
        }
        
        # Add BugSigDB-specific context
        bugsigdb_context = "\n\nBugSigDB Information:\n"
        for col in paper_data.columns:
            if pd.notna(paper_data[col].iloc[0]) and paper_data[col].iloc[0] != 'NA':
                bugsigdb_context += f"{col}: {paper_data[col].iloc[0]}\n"
        
        paper_content["full_text"] += bugsigdb_context
        
        # Print paper details first
        print("\nPaper Details from BugSigDB:")
        print("-" * 50)
        print(f"Title: {paper_data['Title'].iloc[0]}")
        print(f"Journal: {paper_data['Journal'].iloc[0]}")
        print(f"Year: {paper_data['Year'].iloc[0]}")
        print(f"Study Design: {paper_data['Study design'].iloc[0]}")
        print(f"Body Site: {paper_data['Body site'].iloc[0]}")
        print(f"Sequencing Type: {paper_data['Sequencing type'].iloc[0]}")
        print("-" * 50)
        
        # Get available models
        available_models = qa_system.get_available_models()
        print("\nAvailable Models:", ", ".join(available_models))
        
        # Analyze paper with selected models
        results = await qa_system.analyze_paper(
            paper_content,
            models_to_use=models,
            custom_questions=custom_questions
        )
        
        # Print analysis results by model
        for model_name, model_results in results.items():
            print(f"\nResults from {model_name.upper()}:")
            print("-" * 50)
            
            if "error" in model_results:
                print(f"Error: {model_results['error']}")
                continue
                
            for question, answer in model_results.items():
                print(f"\nQ: {question}")
                if isinstance(answer, dict):
                    if "answer" in answer:
                        print(f"A: {answer['answer']}")
                    if "confidence" in answer:
                        print(f"Confidence: {answer['confidence']:.2f}")
                    if "classification" in answer:
                        print(f"Classification: {answer['classification']}")
                else:
                    print(f"A: {answer}")
            
    except Exception as e:
        logger.error(f"Error analyzing paper: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="Analyze papers from BugSigDB using multiple QA systems")
    parser.add_argument(
        "--pmid",
        help="Specific PMID to analyze"
    )
    parser.add_argument(
        "--random",
        action="store_true",
        help="Analyze a random paper from BugSigDB"
    )
    parser.add_argument(
        "--questions",
        nargs="*",
        help="Custom questions to ask about the paper"
    )
    parser.add_argument(
        "--models",
        nargs="*",
        help="Specific models to use (biobert, superstudio, gemini)"
    )
    
    args = parser.parse_args()
    
    import asyncio
    asyncio.run(analyze_bugsigdb_paper(
        args.pmid,
        args.random,
        args.questions,
        args.models
    ))

if __name__ == "__main__":
    main() 