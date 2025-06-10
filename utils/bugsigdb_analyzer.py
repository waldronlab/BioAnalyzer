import pandas as pd
import requests
import logging
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path
import json
from datetime import datetime
import re
from functools import lru_cache
from time import sleep

class BugSigDBAnalyzer:
    """Analyzer for identifying and processing microbial signatures in scientific papers."""
    
    # Class-level constants
    BODY_SITES = {
        'gut': ['intestinal', 'gut', 'gastrointestinal', 'gi tract', 'colon', 'intestine'],
        'oral': ['oral', 'mouth', 'dental', 'tongue', 'saliva'],
        'skin': ['skin', 'dermal', 'epidermis'],
        'respiratory': ['lung', 'respiratory', 'airway', 'bronchial'],
        'vaginal': ['vaginal', 'vagina', 'cervical']
    }
    
    DISEASE_CATEGORIES = {
        'IBD': ['inflammatory bowel disease', 'ibd', 'crohn', 'ulcerative colitis'],
        'cancer': ['cancer', 'tumor', 'carcinoma', 'neoplasm'],
        'metabolic': ['obesity', 'diabetes', 'metabolic syndrome'],
        'infectious': ['infection', 'pathogen', 'bacterial infection'],
        'autoimmune': ['autoimmune', 'arthritis', 'lupus', 'multiple sclerosis']
    }
    
    SIGNATURE_KEYWORDS = {
        'general': [
            'microbiome', 'microbial', 'bacteria', 'abundance',
            'differential abundance', 'taxonomic composition',
            'community structure', 'dysbiosis', 'microbiota'
        ],
        'methods': [
            '16s rrna', 'metagenomic', 'sequencing', 'amplicon',
            'shotgun', 'transcriptomic', 'qpcr', 'fish'
        ],
        'analysis': [
            'enriched', 'depleted', 'increased', 'decreased',
            'higher abundance', 'lower abundance', 'differential'
        ]
    }

    def __init__(self, data_path: str = "data/full_dump.csv", cache_dir: str = "cache"):
        """Initialize the BugSigDB analyzer.
        
        Args:
            data_path: Path to full_dump.csv containing existing BugSigDB data
            cache_dir: Directory to store API response caches
        """
        self.data_path = Path(data_path)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('BugSigDBAnalyzer')
        
        self._load_existing_data()
    
    def _load_existing_data(self):
        """Load existing BugSigDB data from full_dump.csv"""
        try:
        if self.data_path.exists():
            self.existing_data = pd.read_csv(self.data_path)
                self.existing_pmids = set(self.existing_data['PMID'].astype(str).unique())
                self.logger.info(f"Loaded {len(self.existing_pmids)} existing PMIDs")
        else:
            self.existing_data = pd.DataFrame()
            self.existing_pmids = set()
                self.logger.warning(f"Data file {self.data_path} not found")
        except Exception as e:
            self.logger.error(f"Error loading data: {str(e)}")
            raise
    
    @lru_cache(maxsize=1000)
    def fetch_paper_metadata(self, pmid: str) -> Dict:
        """Fetch paper metadata from PubMed using E-utilities with caching.
        
        Args:
            pmid: PubMed ID to fetch
            
        Returns:
            Dictionary containing paper metadata
        """
        cache_file = self.cache_dir / f"pmid_{pmid}.json"
        
        # Check cache first
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                self.logger.warning(f"Invalid cache file for PMID {pmid}")
        
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        
        try:
        # Fetch summary
        summary_url = f"{base_url}/esummary.fcgi?db=pubmed&id={pmid}&retmode=json"
        response = requests.get(summary_url)
            response.raise_for_status()
            
            data = response.json()
            if 'result' in data and pmid in data['result']:
                paper_data = data['result'][pmid]
                metadata = {
                    'title': paper_data.get('title', ''),
                    'abstract': paper_data.get('abstract', ''),
                    'pubdate': paper_data.get('pubdate', ''),
                    'journal': paper_data.get('fulljournalname', ''),
                    'mesh_terms': paper_data.get('meshheadinglist', []),
                    'authors': paper_data.get('authors', []),
                    'doi': paper_data.get('elocationid', ''),
                    'fetch_date': datetime.now().isoformat()
                }
                
                # Cache the results
                with open(cache_file, 'w') as f:
                    json.dump(metadata, f)
                
                sleep(0.34)  # Rate limiting for NCBI API
                return metadata
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching metadata for PMID {pmid}: {str(e)}")
        
        return {}
    
    def analyze_paper(self, text: str) -> Dict:
        """Analyze paper text for microbial signatures and metadata.
        
        Args:
            text: Paper text (title, abstract, or full text)
            
        Returns:
            Dict containing analysis results including:
            - has_signatures: Whether paper likely contains microbial signatures
            - sequencing_type: Detected sequencing type
            - confidence: Confidence score of predictions
            - relevant_terms: List of relevant terms found
            - body_sites: Detected body sites
            - disease_categories: Detected disease categories
        """
        text = text.lower()
        
        # Find signature-related terms
        found_terms = {
            category: [term for term in terms if term in text]
            for category, terms in self.SIGNATURE_KEYWORDS.items()
        }
        
        # Calculate signature confidence
        general_weight = len(found_terms['general']) * 0.4
        methods_weight = len(found_terms['methods']) * 0.3
        analysis_weight = len(found_terms['analysis']) * 0.3
        confidence = min(1.0, general_weight + methods_weight + analysis_weight)
        
        # Determine if paper has signatures
        has_signatures = (
            confidence > 0.4 and
            len(found_terms['general']) >= 1 and
            len(found_terms['methods']) >= 1
        )
        
        # Detect sequencing types
        sequencing_patterns = {
            '16S rRNA': r'16s\s*r(?:rna|RNA)',
            'shotgun metagenomics': r'shotgun|whole\s*genome',
            'amplicon sequencing': r'amplicon\s*sequenc',
            'transcriptomics': r'transcriptom|rna[\-\s]*seq',
            'qPCR': r'q(?:uantitative)?\s*pcr'
        }
        
        sequencing_types = [
            seq_type for seq_type, pattern in sequencing_patterns.items()
            if re.search(pattern, text)
        ]
        
        # Detect body sites and diseases
        body_sites = self._detect_categories(text, self.BODY_SITES)
        diseases = self._detect_categories(text, self.DISEASE_CATEGORIES)
        
        return {
            'has_signatures': has_signatures,
            'sequencing_type': sequencing_types,
            'confidence': confidence,
            'relevant_terms': {
                k: list(set(v)) for k, v in found_terms.items()
            },
            'body_sites': body_sites,
            'disease_categories': diseases
        }
    
    def _detect_categories(self, text: str, category_dict: Dict[str, List[str]]) -> List[str]:
        """Helper method to detect categories (body sites, diseases, etc.) in text."""
        return [
            category for category, terms in category_dict.items()
            if any(term in text for term in terms)
        ]
    
    def is_paper_in_bugsigdb(self, pmid: str) -> bool:
        """Check if paper is already in BugSigDB."""
        return str(pmid) in self.existing_pmids
    
    def suggest_papers_for_review(self, pmids: List[str], min_confidence: float = 0.4) -> List[Dict]:
        """Analyze multiple papers and suggest those likely relevant for BugSigDB.
        
        Args:
            pmids: List of PubMed IDs to analyze
            min_confidence: Minimum confidence threshold for suggestions
            
        Returns:
            List of dicts containing analysis results for relevant papers
        """
        suggestions = []
        
        for pmid in pmids:
            if self.is_paper_in_bugsigdb(pmid):
                self.logger.debug(f"Skipping PMID {pmid} - already in BugSigDB")
                continue
                
            try:
            metadata = self.fetch_paper_metadata(pmid)
            if not metadata:
                continue
            
            # Analyze title and abstract
            text_to_analyze = f"{metadata['title']} {metadata['abstract']}"
            analysis = self.analyze_paper(text_to_analyze)
            
                if analysis['has_signatures'] and analysis['confidence'] > min_confidence:
                    suggestion = {
                    'pmid': pmid,
                        'analysis_date': datetime.now().isoformat(),
                    **metadata,
                    **analysis
                    }
                    suggestions.append(suggestion)
                    self.logger.info(f"Found relevant paper: PMID {pmid} (confidence: {analysis['confidence']:.2f})")
            
            except Exception as e:
                self.logger.error(f"Error processing PMID {pmid}: {str(e)}")
                continue
        
        return suggestions 

    def export_suggestions(self, suggestions: List[Dict], output_file: str):
        """Export paper suggestions to a JSON file.
        
        Args:
            suggestions: List of paper suggestions from suggest_papers_for_review
            output_file: Path to save the JSON output
        """
        try:
            with open(output_file, 'w') as f:
                json.dump(suggestions, f, indent=2)
            self.logger.info(f"Exported {len(suggestions)} suggestions to {output_file}")
        except Exception as e:
            self.logger.error(f"Error exporting suggestions: {str(e)}")
            raise 