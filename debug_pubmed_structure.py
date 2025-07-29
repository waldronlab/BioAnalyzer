#!/usr/bin/env python3
import sys
import os
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Bio import Entrez
from utils.config import NCBI_API_KEY

def debug_pubmed_structure():
    Entrez.email = "test@example.com"
    if NCBI_API_KEY:
        Entrez.api_key = NCBI_API_KEY
    
    test_pmid = "34647492"
    
    try:
        handle = Entrez.efetch(db="pubmed", id=test_pmid, rettype="medline", retmode="xml")
        result = Entrez.read(handle, validate=False)
        
        if "PubmedArticle" in result:
            article = result["PubmedArticle"][0]
            
            if "PubmedData" in article:
                pubmed_data = article["PubmedData"]
                if "ArticleIdList" in pubmed_data:
                    article_id_list = pubmed_data["ArticleIdList"]
                    print("ArticleIdList content:")
                    for i, item in enumerate(article_id_list):
                        print(f"  [{i}] {item}")
        
        with open("pubmed_debug_output.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
        print("Full structure saved to pubmed_debug_output.json")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    debug_pubmed_structure() 