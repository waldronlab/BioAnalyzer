import argparse
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd
from tqdm import tqdm
from Bio import Entrez
import sys
import os

# Add parent directory to path to allow importing utils.config
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.config import NCBI_API_KEY, GEMINI_API_KEY, EMAIL

from retrieve.data_retrieval import PubMedRetriever
from utils.text_processing import AdvancedTextProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PubMedDataCollector:
    """Collect and preprocess PubMed data for training."""
    
    def __init__(self, api_key: Optional[str] = None, output_dir: str = "data", max_papers: int = 1000):
        """Initialize the data collector.
        
        Args:
            api_key: NCBI API key
            output_dir: Directory to save processed data
            max_papers: Maximum number of papers to collect
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_papers = max_papers
        self.text_processor = AdvancedTextProcessor()
        
        # Use provided API key or fall back to environment variable
        self.api_key = api_key or NCBI_API_KEY
        self.retriever = PubMedRetriever(api_key=self.api_key)
        
        # Set up Entrez
        Entrez.email = EMAIL
        
        logger.info(f"Initialized PubMedDataCollector with output_dir={output_dir}, max_papers={max_papers}")
        
    def search_relevant_papers(self, query: str, max_results: int = 100) -> List[str]:
        """Search for relevant papers using a query.
        
        Args:
            query: PubMed search query
            max_results: Maximum number of results to return
            
        Returns:
            List of PMIDs
        """
        logger.info(f"Searching PubMed with query: {query}")
        
        try:
            # Search for papers
            handle = Entrez.esearch(
                db="pubmed",
                term=query,
                retmax=max_results,
                sort="relevance"
            )
            results = Entrez.read(handle)
            handle.close()
            
            pmids = results.get("IdList", [])
            logger.info(f"Found {len(pmids)} papers matching the query")
            return pmids
            
        except Exception as e:
            logger.error(f"Error searching PubMed: {str(e)}")
            return []
    
    def collect_paper_data(self, pmids: List[str]) -> List[Dict]:
        """Collect metadata and full text for a list of papers.
        
        Args:
            pmids: List of PubMed IDs
            
        Returns:
            List of paper data dictionaries
        """
        papers = []
        
        for pmid in tqdm(pmids, desc="Collecting paper data"):
            try:
                # Get metadata
                metadata = self.retriever.get_paper_metadata(pmid)
                
                # Try to get full text
                full_text = self.retriever.get_pmc_fulltext(pmid)
                
                paper_data = {
                    "pmid": pmid,
                    "title": metadata.get("title", ""),
                    "abstract": metadata.get("abstract", ""),
                    "journal": metadata.get("journal", ""),
                    "year": metadata.get("year", ""),
                    "mesh_terms": metadata.get("mesh_terms", []),
                    "full_text": full_text if full_text else ""
                }
                
                papers.append(paper_data)
                
                # Rate limiting
                time.sleep(0.1)  # 10 requests per second with API key
                
            except Exception as e:
                logger.warning(f"Error processing PMID {pmid}: {str(e)}")
        
        logger.info(f"Collected data for {len(papers)} papers")
        return papers
    
    def generate_training_conversations(self, papers: List[Dict]) -> List[Dict]:
        """Generate training conversations from paper data.
        
        Args:
            papers: List of paper data dictionaries
            
        Returns:
            List of conversation dictionaries
        """
        conversations = []
        
        # Define question templates
        question_templates = [
            "What is the main finding of this paper?",
            "What methods were used in this study?",
            "What are the key microbiome signatures identified in this paper?",
            "What body sites were studied in this research?",
            "What diseases or conditions are associated with the microbial signatures in this paper?",
            "What sequencing technologies were used in this study?",
            "What statistical analyses were performed in this paper?",
            "What are the limitations of this study?",
            "How does this paper contribute to microbiome research?",
            "What future research directions are suggested by this paper?"
        ]
        
        # Generate conversations for each paper
        for paper in tqdm(papers, desc="Generating conversations"):
            # Combine title, abstract, and full text
            context = f"Title: {paper['title']}\n\nAbstract: {paper['abstract']}"
            if paper.get("full_text"):
                context += f"\n\nFull Text: {paper['full_text'][:5000]}..."  # Limit full text length
            
            # Use each question template
            for template in question_templates:
                conversations.append({
                    "query": template,
                    "context": context,
                    "response": "",  # Empty response to be filled by Gemini API
                    "pmid": paper["pmid"]
                })
        
        logger.info(f"Generated {len(conversations)} conversation templates")
        return conversations
    
    def fill_responses_with_gemini(self, conversations: List[Dict]) -> List[Dict]:
        """Fill conversation responses using Gemini API.
        
        Args:
            conversations: List of conversation dictionaries
            
        Returns:
            List of completed conversation dictionaries
        """
        # Import here to avoid circular imports
        from models.gemini_qa import GeminiQA
        import asyncio
        
        logger.info("Filling responses with Gemini API")
        
        # Initialize Gemini QA with API key from environment
        gemini = GeminiQA(api_key=GEMINI_API_KEY)
        
        async def process_conversations():
            completed = []
            
            for conv in tqdm(conversations, desc="Processing with Gemini"):
                try:
                    # Skip if already has a response
                    if conv.get("response"):
                        completed.append(conv)
                        continue
                    
                    # Get answer from Gemini
                    result = await gemini.get_answer(conv["query"], conv["context"])
                    
                    # Add response to conversation
                    conv["response"] = result["answer"]
                    completed.append(conv)
                    
                    # Rate limiting
                    await asyncio.sleep(1)  # 1 request per second
                    
                except Exception as e:
                    logger.warning(f"Error processing conversation: {str(e)}")
            
            return completed
        
        # Run async processing
        completed_conversations = asyncio.run(process_conversations())
        
        # Filter out conversations without responses
        completed_conversations = [c for c in completed_conversations if c.get("response")]
        
        logger.info(f"Completed {len(completed_conversations)} conversations")
        return completed_conversations
    
    def save_training_data(self, conversations: List[Dict], filename: str = "pubmed_training_conversations.json"):
        """Save training conversations to a file.
        
        Args:
            conversations: List of conversation dictionaries
            filename: Output filename
        """
        output_path = self.output_dir / filename
        
        # Format for training
        training_data = {
            "conversations": [
                {
                    "query": conv["query"],
                    "response": conv["response"],
                    "context": conv.get("context", "")
                }
                for conv in conversations
            ]
        }
        
        with open(output_path, 'w') as f:
            json.dump(training_data, f, indent=2)
        
        logger.info(f"Saved {len(training_data['conversations'])} conversations to {output_path}")
    
    def run_collection(self, queries: List[str]):
        """Run the full data collection process.
        
        Args:
            queries: List of PubMed search queries
        """
        all_pmids = []
        
        # Search for papers using each query
        for query in queries:
            pmids = self.search_relevant_papers(query, max_results=min(100, self.max_papers // len(queries)))
            all_pmids.extend(pmids)
        
        # Remove duplicates and limit to max_papers
        all_pmids = list(set(all_pmids))[:self.max_papers]
        
        # Collect paper data
        papers = self.collect_paper_data(all_pmids)
        
        # Generate training conversations
        conversations = self.generate_training_conversations(papers)
        
        # Fill responses with Gemini
        completed_conversations = self.fill_responses_with_gemini(conversations)
        
        # Save training data
        self.save_training_data(completed_conversations)
        
        # Also save raw paper data
        papers_df = pd.DataFrame(papers)
        papers_df.to_csv(self.output_dir / "pubmed_papers.csv", index=False)
        
        logger.info("Data collection complete")

def main():
    parser = argparse.ArgumentParser(description="Collect PubMed data for training")
    parser.add_argument("--api-key", help="NCBI API key (optional, will use environment variable if not provided)")
    parser.add_argument("--output-dir", default="data", help="Output directory")
    parser.add_argument("--max-papers", type=int, default=1000, help="Maximum number of papers to collect")
    args = parser.parse_args()
    
    # Define search queries
    queries = [
        "microbiome[Title/Abstract] AND signature[Title/Abstract]",
        "microbiota[Title/Abstract] AND (disease[Title/Abstract] OR health[Title/Abstract])",
        "16S rRNA sequencing[Title/Abstract] AND microbiome[Title/Abstract]",
        "metagenomics[Title/Abstract] AND microbiome[Title/Abstract]",
        "gut microbiome[Title/Abstract] AND (dysbiosis[Title/Abstract] OR diversity[Title/Abstract])"
    ]
    
    collector = PubMedDataCollector(
        api_key=args.api_key,  # Will use environment variable if None
        output_dir=args.output_dir,
        max_papers=args.max_papers
    )
    
    collector.run_collection(queries)

if __name__ == "__main__":
    main() 