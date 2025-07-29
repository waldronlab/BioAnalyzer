#!/usr/bin/env python3
"""
Test script to verify DOI extraction from PubMed
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from retrieve.data_retrieval import PubMedRetriever
from utils.config import NCBI_API_KEY
import shutil

def test_doi_extraction():
    """Test DOI extraction with the specific PMID provided by the user"""
    
    # Clear cache first
    cache_dir = "cache"
    if os.path.exists(cache_dir):
        print("Clearing cache...")
        shutil.rmtree(cache_dir)
    
    # Initialize the retriever
    retriever = PubMedRetriever(api_key=NCBI_API_KEY)
    
    # Test with the specific PMID from the user's example
    test_pmid = "34647492"  # The PMID from the user's example
    expected_doi = "10.1080/07853890.2021.1990392"  # The DOI from the user's example
    
    print(f"Testing DOI extraction for PMID: {test_pmid}")
    print(f"Expected DOI: {expected_doi}")
    print("-" * 50)
    
    try:
        # Get metadata
        metadata = retriever.get_paper_metadata(test_pmid)
        
        print(f"Title: {metadata.get('title', 'Not found')}")
        print(f"Journal: {metadata.get('journal', 'Not found')}")
        print(f"Year: {metadata.get('year', 'Not found')}")
        print(f"Extracted DOI: {metadata.get('doi', 'Not found')}")
        
        # Check if DOI matches expected
        if metadata.get('doi') == expected_doi:
            print("✅ SUCCESS: DOI extraction works correctly!")
        elif metadata.get('doi'):
            print(f"⚠️  WARNING: DOI found but doesn't match expected: {metadata.get('doi')}")
        else:
            print("❌ FAILURE: No DOI extracted")
            
        # Print all metadata keys for debugging
        print("\nAll metadata keys:")
        for key in metadata.keys():
            print(f"  - {key}: {metadata[key]}")
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")

if __name__ == "__main__":
    test_doi_extraction() 