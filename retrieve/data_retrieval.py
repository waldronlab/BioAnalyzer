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
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
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
        
        # Extract DOI from article identifiers
        doi = self._extract_doi(article)
        
        # Extract authors
        authors = self._extract_authors(article)
        
        # Extract basic metadata
        title = article["MedlineCitation"]["Article"]["ArticleTitle"]
        abstract = article["MedlineCitation"]["Article"].get("Abstract", {}).get("AbstractText", [""])[0]
        mesh_terms = self._extract_mesh_terms(article)
        
        # Extract BugSigDB-specific fields using text analysis
        host = self._extract_host(title, abstract, mesh_terms)
        body_site = self._extract_body_site(title, abstract, mesh_terms)
        sequencing_type = self._extract_sequencing_type(title, abstract, mesh_terms)
        
        metadata = {
            "pmid": pmid,
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "mesh_terms": mesh_terms,
            "publication_types": self._extract_publication_types(article),
            "journal": article["MedlineCitation"]["Article"]["Journal"]["Title"],
            "year": article["MedlineCitation"]["Article"]["Journal"]["JournalIssue"]["PubDate"].get("Year", ""),
            "doi": doi,
            "host": host,
            "body_site": body_site,
            "sequencing_type": sequencing_type
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
        
    def _extract_authors(self, article: Dict) -> str:
        """Extract authors from article metadata.
        
        Args:
            article: PubMed article dictionary
            
        Returns:
            Comma-separated string of author names
        """
        author_list = article["MedlineCitation"]["Article"].get("AuthorList", [])
        if not author_list:
            return ""
        
        authors = []
        for author in author_list:
            last_name = author.get("LastName", "")
            first_name = author.get("ForeName", "")
            initials = author.get("Initials", "")
            
            if last_name:
                if first_name:
                    authors.append(f"{last_name} {first_name}")
                elif initials:
                    authors.append(f"{last_name} {initials}")
                else:
                    authors.append(last_name)
        
        return ", ".join(authors)
        
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

    def _extract_doi(self, article: Dict) -> str:
        """Extract DOI from article metadata.
        
        Args:
            article: PubMed article dictionary
            
        Returns:
            DOI string or empty string if not found
        """
        try:
            logger.info(f"Extracting DOI from article structure...")
            
            # Method 1: Check for DOI in ArticleIdList (most common location)
            if "PubmedData" in article and "ArticleIdList" in article["PubmedData"]:
                logger.info("Checking ArticleIdList for DOI...")
                for article_id in article["PubmedData"]["ArticleIdList"]:
                    if isinstance(article_id, dict):
                        if article_id.get("IdType") == "doi":
                            doi = article_id.get("Id", "")
                            logger.info(f"Found DOI in ArticleIdList: {doi}")
                            return doi
                    elif isinstance(article_id, str) and article_id.startswith("10."):
                        logger.info(f"Found DOI string in ArticleIdList: {article_id}")
                        return article_id
            
            # Method 2: Check for DOI in ELocationID
            if "MedlineCitation" in article and "Article" in article["MedlineCitation"]:
                article_data = article["MedlineCitation"]["Article"]
                if "ELocationID" in article_data:
                    logger.info("Checking ELocationID for DOI...")
                    for elocation in article_data["ELocationID"]:
                        if isinstance(elocation, dict) and elocation.get("EIdType") == "doi":
                            doi = elocation.get("EId", "")
                            logger.info(f"Found DOI in ELocationID: {doi}")
                            return doi
            
            logger.warning("No DOI found in any expected location")
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting DOI: {str(e)}")
            return "" 

    def _extract_host(self, title: str, abstract: str, mesh_terms: List[str]) -> str:
        """Extract host species from title, abstract, and MeSH terms.
        
        Args:
            title: Paper title
            abstract: Paper abstract
            mesh_terms: List of MeSH terms
            
        Returns:
            Host species or empty string if not found
        """
        text = f"{title} {abstract} {' '.join(mesh_terms)}".lower()
        
        logger.info(f"Extracting host from text: {text[:200]}...")
        
        # Human-related terms
        human_terms = ['human', 'humans', 'patient', 'patients', 'subject', 'subjects', 'volunteer', 'volunteers']
        if any(term in text for term in human_terms):
            logger.info(f"Found human host in text")
            return "Human"
        
        # Mouse-related terms
        mouse_terms = ['mouse', 'mice', 'murine', 'c57bl', 'balb/c']
        if any(term in text for term in mouse_terms):
            logger.info(f"Found mouse host in text")
            return "Mouse"
        
        # Rat-related terms
        rat_terms = ['rat', 'rats', 'rattus']
        if any(term in text for term in rat_terms):
            logger.info(f"Found rat host in text")
            return "Rat"
        
        # Environmental terms
        env_terms = ['environmental', 'environment', 'soil', 'water', 'air', 'indoor', 'outdoor', 'building', 'restroom', 'bathroom', 'toilet', 'facility', 'public building', 'university', 'office', 'hospital', 'school']
        if any(term in text for term in env_terms):
            logger.info(f"Found environmental host in text")
            return "Environmental"
        
        # Mixed terms (human + environmental)
        if any(term in text for term in human_terms) and any(term in text for term in env_terms):
            logger.info(f"Found mixed human+environmental host in text")
            return "Mixed (Human + Environmental)"
        
        logger.warning(f"No host found in text")
        return ""

    def _extract_body_site(self, title: str, abstract: str, mesh_terms: List[str]) -> str:
        """Extract body site from title, abstract, and MeSH terms.
        
        Args:
            title: Paper title
            abstract: Paper abstract
            mesh_terms: List of MeSH terms
            
        Returns:
            Body site or empty string if not found
        """
        text = f"{title} {abstract} {' '.join(mesh_terms)}".lower()
        
        logger.info(f"Extracting body site from text: {text[:200]}...")
        
        # Gut-related terms
        gut_terms = ['gut', 'intestine', 'intestinal', 'stomach', 'colon', 'fecal', 'feces', 'stool']
        if any(term in text for term in gut_terms):
            logger.info(f"Found gut body site in text")
            return "Gut"
        
        # Oral-related terms
        oral_terms = ['oral', 'mouth', 'saliva', 'dental', 'tooth', 'teeth', 'tongue']
        if any(term in text for term in oral_terms):
            logger.info(f"Found oral body site in text")
            return "Oral"
        
        # Skin-related terms
        skin_terms = ['skin', 'cutaneous', 'dermal', 'epidermal']
        if any(term in text for term in skin_terms):
            logger.info(f"Found skin body site in text")
            return "Skin"
        
        # Vaginal-related terms
        vaginal_terms = ['vaginal', 'vagina', 'cervical', 'cervix']
        if any(term in text for term in vaginal_terms):
            logger.info(f"Found vaginal body site in text")
            return "Vaginal"
        
        # Environmental sites
        env_sites = {
            'indoor': ['indoor', 'building', 'room', 'office', 'home', 'house', 'restroom', 'bathroom', 'toilet', 'facility', 'public building', 'university', 'hospital', 'school', 'classroom', 'hall', 'corridor'],
            'outdoor': ['outdoor', 'soil', 'air', 'water'],
            'built-environment': ['built', 'infrastructure', 'facility'],
            'agricultural': ['agricultural', 'farm', 'crop', 'soil'],
            'industrial': ['industrial', 'factory', 'manufacturing'],
            'water-systems': ['water', 'aquatic', 'marine', 'freshwater'],
            'soil': ['soil', 'terrestrial', 'ground']
        }
        
        for site, terms in env_sites.items():
            if any(term in text for term in terms):
                logger.info(f"Found {site} body site in text")
                return site.title()
        
        logger.warning(f"No body site found in text")
        return ""

    def _extract_sequencing_type(self, title: str, abstract: str, mesh_terms: List[str]) -> str:
        """Extract sequencing type from title, abstract, and MeSH terms.
        
        Args:
            title: Paper title
            abstract: Paper abstract
            mesh_terms: List of MeSH terms
            
        Returns:
            Sequencing type or empty string if not found
        """
        text = f"{title} {abstract} {' '.join(mesh_terms)}".lower()
        
        logger.info(f"Extracting sequencing type from text: {text[:200]}...")
        
        # 16S rRNA sequencing
        if '16s' in text or '16s rrna' in text or '16s ribosomal' in text:
            logger.info(f"Found 16S rRNA sequencing in text")
            return "16S rRNA"
        
        # Shotgun metagenomics
        shotgun_terms = ['shotgun', 'metagenomic', 'metagenomics', 'whole genome', 'wgs']
        if any(term in text for term in shotgun_terms):
            logger.info(f"Found shotgun metagenomics in text")
            return "Shotgun Metagenomics"
        
        # Metatranscriptomics
        transcript_terms = ['metatranscriptomic', 'metatranscriptomics', 'rna-seq', 'transcriptome']
        if any(term in text for term in transcript_terms):
            logger.info(f"Found metatranscriptomics in text")
            return "Metatranscriptomics"
        
        # Other sequencing types
        other_terms = ['sequencing', 'next-generation', 'ngs', 'illumina', 'pacbio']
        if any(term in text for term in other_terms):
            logger.info(f"Found other sequencing type in text")
            return "Other"
        
        logger.warning(f"No sequencing type found in text")
        return ""