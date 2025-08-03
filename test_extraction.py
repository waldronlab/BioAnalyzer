#!/usr/bin/env python3
"""
Test script to verify that the PubMed data extraction works correctly
for the specific paper mentioned: PMID 29127623
"""

import sys
import os
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from retrieve.data_retrieval import PubMedRetriever
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_paper_extraction():
    """Test the extraction for the specific paper mentioned."""
    
    # Initialize the retriever
    retriever = PubMedRetriever()
    
    # Test with the specific paper mentioned
    pmid = "29127623"
    
    print(f"Testing extraction for PMID: {pmid}")
    print("=" * 50)
    
    try:
        # Use the cached data we know exists
        cache_file = f"cache/metadata_{pmid}.json"
        if os.path.exists(cache_file):
            print("Using cached data...")
            with open(cache_file, 'r') as f:
                metadata = json.load(f)
        else:
            print("Fetching metadata from PubMed...")
            metadata = retriever.get_paper_metadata(pmid)
        
        print(f"Title: {metadata.get('title', 'N/A')}")
        print(f"Authors: {metadata.get('authors', 'N/A')}")
        print(f"Journal: {metadata.get('journal', 'N/A')}")
        print(f"Year: {metadata.get('year', 'N/A')}")
        print(f"DOI: {metadata.get('doi', 'N/A')}")
        print()
        
        # Check the extracted fields
        print("Extracted BugSigDB fields:")
        print(f"Host: {metadata.get('host', 'N/A')}")
        print(f"Body Site: {metadata.get('body_site', 'N/A')}")
        print(f"Sequencing Type: {metadata.get('sequencing_type', 'N/A')}")
        print()
        
        # Show abstract preview
        abstract = metadata.get('abstract', '')
        if abstract:
            print(f"Abstract preview: {abstract[:200]}...")
        print()
        
        # Show MeSH terms
        mesh_terms = metadata.get('mesh_terms', [])
        if mesh_terms:
            print(f"MeSH terms: {', '.join(mesh_terms[:10])}")
            if len(mesh_terms) > 10:
                print(f"... and {len(mesh_terms) - 10} more")
        print()
        
        # Test extraction methods directly
        print("Testing extraction methods directly...")
        title = metadata.get('title', '')
        abstract = metadata.get('abstract', '')
        mesh_terms = metadata.get('mesh_terms', [])
        
        print(f"Testing host extraction...")
        host = retriever._extract_host(title, abstract, mesh_terms)
        print(f"Direct host extraction result: {host}")
        
        print(f"Testing body site extraction...")
        body_site = retriever._extract_body_site(title, abstract, mesh_terms)
        print(f"Direct body site extraction result: {body_site}")
        
        print(f"Testing sequencing type extraction...")
        sequencing_type = retriever._extract_sequencing_type(title, abstract, mesh_terms)
        print(f"Direct sequencing type extraction result: {sequencing_type}")
        print()
        
        # Expected values based on the paper description
        print("Expected values based on paper description:")
        print("Host: Environmental (indoor microbiome research)")
        print("Body Site: Indoor (restrooms and common areas)")
        print("Sequencing Type: 16S rRNA (mentioned in abstract)")
        print()
        
        # Check if extraction worked
        success = True
        if not metadata.get('host'):
            print("❌ Host extraction failed")
            success = False
        else:
            print(f"✅ Host extracted: {metadata.get('host')}")
            
        if not metadata.get('body_site'):
            print("❌ Body site extraction failed")
            success = False
        else:
            print(f"✅ Body site extracted: {metadata.get('body_site')}")
            
        if not metadata.get('sequencing_type'):
            print("❌ Sequencing type extraction failed")
            success = False
        else:
            print(f"✅ Sequencing type extracted: {metadata.get('sequencing_type')}")
        
        if success:
            print("\n🎉 All extractions successful!")
        else:
            print("\n⚠️  Some extractions failed")
            
        # Update the cache file with the new fields
        print("\nUpdating cache file with extracted fields...")
        metadata['host'] = host
        metadata['body_site'] = body_site
        metadata['sequencing_type'] = sequencing_type
        
        with open(cache_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        print("✅ Cache file updated!")
        
        # Test with another paper to verify the changes work
        print("\n" + "=" * 50)
        print("Testing with another paper (PMID: 24489843)...")
        pmid2 = "24489843"
        cache_file2 = f"cache/metadata_{pmid2}.json"
        
        if os.path.exists(cache_file2):
            with open(cache_file2, 'r') as f:
                metadata2 = json.load(f)
            
            print(f"Title: {metadata2.get('title', 'N/A')}")
            print(f"Host: {metadata2.get('host', 'N/A')}")
            print(f"Body Site: {metadata2.get('body_site', 'N/A')}")
            print(f"Sequencing Type: {metadata2.get('sequencing_type', 'N/A')}")
            
            # Extract fields for this paper too
            title2 = metadata2.get('title', '')
            abstract2 = metadata2.get('abstract', '')
            mesh_terms2 = metadata2.get('mesh_terms', [])
            
            host2 = retriever._extract_host(title2, abstract2, mesh_terms2)
            body_site2 = retriever._extract_body_site(title2, abstract2, mesh_terms2)
            sequencing_type2 = retriever._extract_sequencing_type(title2, abstract2, mesh_terms2)
            
            print(f"Extracted Host: {host2}")
            print(f"Extracted Body Site: {body_site2}")
            print(f"Extracted Sequencing Type: {sequencing_type2}")
            
            # Update cache file
            metadata2['host'] = host2
            metadata2['body_site'] = body_site2
            metadata2['sequencing_type'] = sequencing_type2
            
            with open(cache_file2, 'w') as f:
                json.dump(metadata2, f, indent=2)
            print("✅ Second cache file updated!")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        logger.exception("Error during extraction")

if __name__ == "__main__":
    test_paper_extraction() 