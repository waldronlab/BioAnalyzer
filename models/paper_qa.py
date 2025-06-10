from typing import Dict, List, Optional, Union
import json
from pathlib import Path
import torch
from transformers import AutoModelForQuestionAnswering, AutoTokenizer, AutoModelForSequenceClassification
from utils.utils import config
import logging
import pandas as pd
from datetime import datetime
import time
from transformers.utils import WEIGHTS_NAME, CONFIG_NAME

logger = logging.getLogger(__name__)

class PaperQA:
    """Enhanced class for answering questions about papers using LLM."""
    
    def __init__(
        self,
        qa_model_name: str = "dmis-lab/biobert-v1.1",
        classifier_model_name: str = "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract",
        max_retries: int = 3,
        retry_delay: int = 5
    ):
        """Initialize the QA system with improved error handling.
        
        Args:
            qa_model_name: Name of the pretrained model for QA
            classifier_model_name: Name of the pretrained model for classification
            max_retries: Maximum number of download attempts
            retry_delay: Delay between retries in seconds
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Create model cache directory
        cache_dir = config.CACHE_DIR / "models"
        cache_dir.mkdir(exist_ok=True)
        
        # Load QA model with retries
        for attempt in range(max_retries):
            try:
                logger.info(f"Loading QA model {qa_model_name} (attempt {attempt + 1}/{max_retries})")
                self.qa_tokenizer = AutoTokenizer.from_pretrained(
                    qa_model_name,
                    cache_dir=cache_dir,
                    local_files_only=False
                )
                self.qa_model = AutoModelForQuestionAnswering.from_pretrained(
                    qa_model_name,
                    cache_dir=cache_dir,
                    local_files_only=False
                )
                self.qa_model = self.qa_model.to(self.device)
                break
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise RuntimeError(f"Failed to load QA model after {max_retries} attempts")
        
        # Load classifier model with retries
        for attempt in range(max_retries):
            try:
                logger.info(f"Loading classifier model {classifier_model_name} (attempt {attempt + 1}/{max_retries})")
                self.clf_tokenizer = AutoTokenizer.from_pretrained(
                    classifier_model_name,
                    cache_dir=cache_dir,
                    local_files_only=False
                )
                self.clf_model = AutoModelForSequenceClassification.from_pretrained(
                    classifier_model_name,
                    cache_dir=cache_dir,
                    local_files_only=False,
                    num_labels=2
                )
                self.clf_model = self.clf_model.to(self.device)
                break
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise RuntimeError(f"Failed to load classifier model after {max_retries} attempts")
        
        # Default BugSigDB-specific questions
        self.default_questions = {
            "signature_presence": "Does this paper contain microbial differential abundance signatures?",
            "sequencing": "What sequencing technology or method was used in this study?",
            "body_sites": "What body sites or anatomical locations were studied?",
            "organisms": "What microorganisms were found to be differentially abundant?",
            "statistical_methods": "What statistical methods were used for differential abundance analysis?",
            "study_design": "What was the study design and what conditions were compared?",
            "sample_size": "What was the sample size and how were samples collected?",
            "metadata": "What metadata or clinical data was collected about the samples?",
            "validation": "Were the findings validated using any additional methods or cohorts?"
        }
        
        # Initialize results storage
        self.results_dir = Path("analysis_results")
        self.results_dir.mkdir(exist_ok=True)
        
    def _classify_text(self, question: str, context: str) -> Dict[str, float]:
        """Classify text for yes/no questions.
        
        Args:
            question: Question to answer
            context: Text context
            
        Returns:
            Dictionary with classification probabilities
        """
        inputs = self.clf_tokenizer(
            question,
            context,
            max_length=512,
            truncation=True,
            padding=True,
            return_tensors="pt"
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        outputs = self.clf_model(**inputs)
        probs = torch.softmax(outputs.logits, dim=1)
        
        return {
            "yes_probability": probs[0][1].item(),
            "no_probability": probs[0][0].item()
        }
        
    def answer_question(
        self,
        question: str,
        paper_content: Dict[str, str],
        max_length: int = 512
    ) -> Dict[str, Union[str, float, Dict[str, float]]]:
        """Enhanced answer generation with classification support.
        
        Args:
            question: Question to answer
            paper_content: Dictionary containing paper content
            max_length: Maximum sequence length
            
        Returns:
            Dictionary containing answer, confidence scores, and classifications
        """
        # Combine paper content into context
        context = f"Title: {paper_content['title']}\n\n"
        context += f"Abstract: {paper_content['abstract']}\n\n"
        if paper_content.get('full_text'):
            context += f"Full Text: {paper_content['full_text']}"
            
        # Get classification probabilities for yes/no questions
        classification = self._classify_text(question, context)
        
        # Get detailed answer using QA model
        inputs = self.qa_tokenizer(
            question,
            context,
            max_length=max_length,
            truncation=True,
            padding=True,
            return_tensors="pt"
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        outputs = self.qa_model(**inputs)
        
        # Extract answer span
        answer_start = torch.argmax(outputs.start_logits)
        answer_end = torch.argmax(outputs.end_logits) + 1
        
        answer = self.qa_tokenizer.decode(
            inputs["input_ids"][0][answer_start:answer_end],
            skip_special_tokens=True
        )
        
        # Calculate confidence score
        confidence = torch.softmax(outputs.start_logits, dim=1).max().item() * \
                    torch.softmax(outputs.end_logits, dim=1).max().item()
        
        return {
            "answer": answer,
            "confidence": confidence,
            "classification": classification
        }
        
    def analyze_paper(
        self,
        paper_content: Dict[str, str],
        questions: Optional[List[str]] = None,
        save_results: bool = True
    ) -> Dict[str, Dict[str, Union[str, float, Dict[str, float]]]]:
        """Analyze a paper with enhanced question set and result storage.
        
        Args:
            paper_content: Dictionary containing paper content
            questions: Optional list of custom questions
            save_results: Whether to save results to disk
            
        Returns:
            Dictionary of question-answer pairs with detailed analysis
        """
        if questions is None:
            questions = list(self.default_questions.values())
            
        results = {}
        for question in questions:
            try:
                answer = self.answer_question(question, paper_content)
                results[question] = answer
            except Exception as e:
                logger.error(f"Error answering question '{question}': {str(e)}")
                results[question] = {
                    "answer": "Error processing this question",
                    "confidence": 0.0,
                    "classification": {"yes_probability": 0.0, "no_probability": 0.0}
                }
        
        if save_results:
            self._save_results(paper_content["title"], results)
            
        return results
        
    def _save_results(self, paper_title: str, results: Dict) -> None:
        """Save analysis results to disk.
        
        Args:
            paper_title: Title of the analyzed paper
            results: Analysis results to save
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.results_dir / f"analysis_{timestamp}_{paper_title[:50]}.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
            
        logger.info(f"Results saved to {filename}")
        
    def get_analysis_history(self) -> pd.DataFrame:
        """Retrieve analysis history from saved results.
        
        Returns:
            DataFrame containing analysis history
        """
        results = []
        for file in self.results_dir.glob("analysis_*.json"):
            with open(file, 'r') as f:
                data = json.load(f)
                results.append({
                    "timestamp": file.stem.split("_")[1],
                    "paper_title": "_".join(file.stem.split("_")[2:]),
                    "results": data
                })
                
        return pd.DataFrame(results)