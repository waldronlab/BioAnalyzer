import time
import logging
from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path
import requests
from Bio import Entrez
from bs4 import BeautifulSoup
from utils.utils import config, create_cache_key, save_json, load_json

logger = logging.getLogger(__name__)

class PubMedRetriever:
    """Class for retrieving data from PubMed and PMC."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the retriever with API credentials."""
        Entrez.email = config.EMAIL
        self.api_key = api_key or config.NCBI_API_KEY
        Entrez.api_key = self.api_key
        self.cache_dir = config.CACHE_DIR
        
    def _handle_api_call(self, func, *args, **kwargs) -> Dict:
        """Handle API calls with retries and rate limiting.
        
        Args:
            func: Entrez function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            API response dictionary
        """
        # Add API key to kwargs if not already present
        if self.api_key and "api_key" not in kwargs:
            kwargs["api_key"] = self.api_key
            
        for attempt in range(config.MAX_RETRIES):
            try:
                handle = func(*args, **kwargs)
                return Entrez.read(handle, validate=False)
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < config.MAX_RETRIES - 1:
                    time.sleep(config.RETRY_DELAY * (attempt + 1))
                else:
                    raise
                    
    def get_paper_metadata(self, pmid: str) -> Dict:
        """Retrieve metadata for a paper from PubMed.
        
        Args:
            pmid: PubMed ID
            
        Returns:
            Dictionary containing paper metadata
        """
        cache_key = create_cache_key("metadata", pmid)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if cache_file.exists():
            return load_json(cache_file)
            
        result = self._handle_api_call(
            Entrez.efetch,
            db="pubmed",
            id=pmid,
            rettype="medline",
            retmode="xml"
        )
        
        if not result or "PubmedArticle" not in result:
            raise ValueError(f"No metadata found for PMID: {pmid}")
            
        article = result["PubmedArticle"][0]
        metadata = {
            "pmid": pmid,
            "title": article["MedlineCitation"]["Article"]["ArticleTitle"],
            "abstract": article["MedlineCitation"]["Article"].get("Abstract", {}).get("AbstractText", [""])[0],
            "mesh_terms": self._extract_mesh_terms(article),
            "publication_types": self._extract_publication_types(article),
            "journal": article["MedlineCitation"]["Article"]["Journal"]["Title"],
            "year": article["MedlineCitation"]["Article"]["Journal"]["JournalIssue"]["PubDate"].get("Year", "")
        }
        
        save_json(metadata, cache_file)
        return metadata
        
    def _extract_mesh_terms(self, article: Dict) -> List[str]:
        """Extract MeSH terms from article metadata.
        
        Args:
            article: PubMed article dictionary
            
        Returns:
            List of MeSH terms
        """
        mesh_list = article["MedlineCitation"].get("MeshHeadingList", [])
        return [mesh["DescriptorName"] for mesh in mesh_list]
        
    def _extract_publication_types(self, article: Dict) -> List[str]:
        """Extract publication types from article metadata.
        
        Args:
            article: PubMed article dictionary
            
        Returns:
            List of publication types
        """
        pub_types = article["MedlineCitation"]["Article"].get("PublicationTypeList", [])
        return [pt for pt in pub_types]
        
    def get_pmc_fulltext(self, pmid: str) -> Optional[str]:
        """Retrieve full text from PMC if available.
        
        Args:
            pmid: PubMed ID
            
        Returns:
            Full text string if available, None otherwise
        """
        cache_key = create_cache_key("fulltext", pmid)
        cache_file = self.cache_dir / f"{cache_key}.txt"
        
        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                return f.read()
                
        # First, get the PMCID
        result = self._handle_api_call(
            Entrez.elink,
            dbfrom="pubmed",
            db="pmc",
            id=pmid
        )
        
        if not result or not result[0]["LinkSetDb"]:
            logger.info(f"No PMC full text available for PMID: {pmid}")
            return None
            
        pmcid = result[0]["LinkSetDb"][0]["Link"][0]["Id"]
        
        # Then fetch the full text
        try:
            result = self._handle_api_call(
                Entrez.efetch,
                db="pmc",
                id=pmcid,
                rettype="full",
                retmode="xml"
            )
            
            # Parse XML and extract text
            soup = BeautifulSoup(result, 'lxml')
            full_text = self._extract_text_from_pmc_xml(soup)
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                f.write(full_text)
                
            return full_text
            
        except Exception as e:
            logger.warning(f"Failed to retrieve PMC full text for PMID {pmid}: {str(e)}")
            return None
            
    def _extract_text_from_pmc_xml(self, soup: BeautifulSoup) -> str:
        """Extract text content from PMC XML.
        
        Args:
            soup: BeautifulSoup object of PMC XML
            
        Returns:
            Extracted text content
        """
        # Extract text from different sections
        sections = []
        
        # Title
        title = soup.find('article-title')
        if title:
            sections.append(title.get_text())
            
        # Abstract
        abstract = soup.find('abstract')
        if abstract:
            sections.append(abstract.get_text())
            
        # Body text
        body = soup.find('body')
        if body:
            for p in body.find_all('p'):
                sections.append(p.get_text())
                
        return "\n\n".join(sections)
        
    def get_bugsigdb_pmids(self) -> List[str]:
        """Retrieve PMIDs of papers already in BugSigDB.
        
        Returns:
            List of PMIDs
        """
        # This would normally query the BugSigDB API
        # For now, return a placeholder list
        return ["12345", "67890"]
        
    def get_paper_by_doi(self, doi: str) -> Dict:
        """Retrieve paper metadata using DOI.
        
        Args:
            doi: Digital Object Identifier
            
        Returns:
            Dictionary containing paper metadata
        """
        cache_key = create_cache_key("doi", doi)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if cache_file.exists():
            return load_json(cache_file)
            
        # Search for the DOI in PubMed
        result = self._handle_api_call(
            Entrez.esearch,
            db="pubmed",
            term=f"{doi}[DOI]",
            retmax=1
        )
        
        if not result or not result.get("IdList"):
            raise ValueError(f"No paper found with DOI: {doi}")
            
        # Get the PMID from the search result
        pmid = result["IdList"][0]
        
        # Get the full metadata using the PMID
        metadata = self.get_paper_metadata(pmid)
        
        # Add the DOI to the metadata
        metadata["doi"] = doi
        
        save_json(metadata, cache_file)
        return metadata
        
    def get_negative_examples(self, n: int = 1000) -> List[str]:
        """Retrieve PMIDs for papers unlikely to contain microbial signatures.
        
        Args:
            n: Number of negative examples to retrieve
            
        Returns:
            List of PMIDs
        """
        query = "biology[MeSH Terms] NOT microbiome[All Fields] NOT microbiota[All Fields]"
        
        result = self._handle_api_call(
            Entrez.esearch,
            db="pubmed",
            term=query,
            retmax=n
        )
        
        return result.get("IdList", []) 