#!/usr/bin/env python3

import argparse
import logging
from typing import List
from retrieve.data_retrieval import PubMedRetriever
from models.paper_qa import PaperQA
from utils.utils import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def analyze_papers(pmids: List[str], custom_questions: List[str] = None):
    """Analyze papers using the QA system.
    
    Args:
        pmids: List of PubMed IDs to analyze
        custom_questions: Optional list of custom questions to ask
    """
    # Initialize components
    retriever = PubMedRetriever()
    qa_system = PaperQA()
    
    for pmid in pmids:
        try:
            logger.info(f"Analyzing paper {pmid}...")
            
            # Retrieve paper content
            metadata = retriever.get_paper_metadata(pmid)
            full_text = retriever.get_pmc_fulltext(pmid)
            
            paper_content = {
                "title": metadata["title"],
                "abstract": metadata["abstract"],
                "full_text": full_text if full_text else ""
            }
            
            # Analyze paper
            results = qa_system.analyze_paper(paper_content, questions=custom_questions)
            
            # Print results
            print(f"\nResults for PMID {pmid}:")
            print("-" * 50)
            print(f"Title: {metadata['title']}")
            print("-" * 50)
            
            for question, answer in results.items():
                print(f"\nQ: {question}")
                print(f"A: {answer['answer']}")
                print(f"Confidence: {answer['confidence']:.2f}")
                
        except Exception as e:
            logger.error(f"Error processing PMID {pmid}: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="Analyze papers using LLM-based QA system")
    parser.add_argument(
        "pmids",
        nargs="+",
        help="PubMed IDs to analyze"
    )
    parser.add_argument(
        "--questions",
        nargs="*",
        help="Custom questions to ask about each paper"
    )
    
    args = parser.parse_args()
    analyze_papers(args.pmids, args.questions)

if __name__ == "__main__":
    main() 