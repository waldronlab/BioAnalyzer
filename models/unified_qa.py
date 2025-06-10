from typing import Dict, List, Optional, Union
import logging
from pathlib import Path
from .paper_qa import PaperQA
from .superstudio_qa import SuperstudioQA
from .gemini_qa import GeminiQA

logger = logging.getLogger(__name__)

class UnifiedQA:
    """Unified interface for multiple QA systems."""
    
    def __init__(
        self,
        use_superstudio: bool = True,
        use_gemini: bool = True,
        use_biobert: bool = True,
        superstudio_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        cache_results: bool = True
    ):
        """Initialize unified QA system.
        
        Args:
            use_superstudio: Whether to use Superstudio
            use_gemini: Whether to use Gemini
            use_biobert: Whether to use BioBERT
            superstudio_api_key: API key for Superstudio
            gemini_api_key: API key for Gemini
            cache_results: Whether to cache results
        """
        self.models = {}
        
        if use_biobert:
            try:
                self.models['biobert'] = PaperQA()
                logger.info("BioBERT model initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize BioBERT: {str(e)}")
        
        if use_superstudio and superstudio_api_key:
            try:
                self.models['superstudio'] = SuperstudioQA(api_key=superstudio_api_key)
                logger.info("Superstudio model initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Superstudio: {str(e)}")
        
        if use_gemini and gemini_api_key:
            try:
                self.models['gemini'] = GeminiQA(api_key=gemini_api_key)
                logger.info("Gemini model initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini: {str(e)}")
    
    async def analyze_paper(
        self,
        paper_content: Dict[str, str],
        models_to_use: Optional[List[str]] = None,
        custom_questions: Optional[Dict] = None
    ) -> Dict[str, Dict]:
        """Analyze a paper using specified models.
        
        Args:
            paper_content: Dictionary containing paper content
            models_to_use: List of model names to use
            custom_questions: Custom questions/prompts for analysis
            
        Returns:
            Dictionary containing results from each model
        """
        results = {}
        models = {k: v for k, v in self.models.items() 
                 if not models_to_use or k in models_to_use}
        
        for model_name, model in models.items():
            try:
                if model_name == 'biobert':
                    results[model_name] = await model.analyze_paper(
                        paper_content,
                        questions=custom_questions
                    )
                elif model_name == 'superstudio':
                    results[model_name] = await model.analyze_paper(
                        paper_content,
                        questions=custom_questions
                    )
                elif model_name == 'gemini':
                    results[model_name] = await model.analyze_paper(
                        paper_content,
                        custom_prompts=custom_questions
                    )
            except Exception as e:
                logger.error(f"Error in {model_name} analysis: {str(e)}")
                results[model_name] = {"error": str(e)}
        
        return results
    
    def get_available_models(self) -> List[str]:
        """Get list of available models.
        
        Returns:
            List of model names
        """
        return list(self.models.keys())
    
    def get_model_capabilities(self) -> Dict[str, Dict]:
        """Get capabilities of each model.
        
        Returns:
            Dictionary of model capabilities
        """
        capabilities = {
            'biobert': {
                'strengths': [
                    'Specialized in biomedical text',
                    'Good for specific QA tasks',
                    'No API key required'
                ],
                'limitations': [
                    'Limited context window',
                    'May be slower than API-based models'
                ]
            },
            'superstudio': {
                'strengths': [
                    'Advanced text processing',
                    'Optimized for scientific text',
                    'Fast processing'
                ],
                'limitations': [
                    'Requires API key',
                    'May have usage limits'
                ]
            },
            'gemini': {
                'strengths': [
                    'State-of-the-art language model',
                    'Good at complex reasoning',
                    'Large context window'
                ],
                'limitations': [
                    'Requires API key',
                    'May be more expensive'
                ]
            }
        }
        
        return {k: v for k, v in capabilities.items() 
                if k in self.models} 