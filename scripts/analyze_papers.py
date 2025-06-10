#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path
import logging
from typing import List

# Add parent directory to path to import utils
sys.path.append(str(Path(__file__).parent.parent))
from utils.bugsigdb_analyzer import BugSigDBAnalyzer

def read_pmids(pmid_file: str) -> List[str]:
    """Read PMIDs from a file, one per line."""
    with open(pmid_file) as f:
        return [line.strip() for line in f if line.strip()]

def main():
    parser = argparse.ArgumentParser(description='Analyze papers for microbial signatures')
    parser.add_argument('--pmid_list', required=True, help='Path to file containing PMIDs to analyze')
    parser.add_argument('--output', required=True, help='Path for output JSON file')
    parser.add_argument('--min_confidence', type=float, default=0.4, help='Minimum confidence threshold (default: 0.4)')
    parser.add_argument('--cache_dir', default='cache', help='Directory for caching API responses')
    parser.add_argument('--data_path', default='data/full_dump.csv', help='Path to BugSigDB data dump')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('analyze_papers')
    
    try:
        # Initialize analyzer
        analyzer = BugSigDBAnalyzer(
            data_path=args.data_path,
            cache_dir=args.cache_dir
        )
        
        # Read PMIDs
        logger.info(f"Reading PMIDs from {args.pmid_list}")
        pmids = read_pmids(args.pmid_list)
        logger.info(f"Found {len(pmids)} PMIDs to analyze")
        
        # Analyze papers
        logger.info("Starting analysis...")
        suggestions = analyzer.suggest_papers_for_review(
            pmids,
            min_confidence=args.min_confidence
        )
        
        # Export results
        analyzer.export_suggestions(suggestions, args.output)
        logger.info(f"Analysis complete. Found {len(suggestions)} relevant papers.")
        logger.info(f"Results saved to {args.output}")
        
    except Exception as e:
        logger.error(f"Error during analysis: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main() 