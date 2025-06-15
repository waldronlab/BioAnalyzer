from typing import Dict, List, Optional, Union
import logging
from .openai_qa import OpenAIQA

logger = logging.getLogger(__name__)

class UnifiedQA:
    """Unified QA system that can use OpenAI."""
    
    def __init__(
        self,
        use_openai: bool = True,
        use_gemini: bool = False,  # Disabled Gemini
        openai_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None
    ):
        """Initialize Unified QA system.
        
        Args:
            use_openai: Whether to use OpenAI
            use_gemini: Whether to use Gemini (disabled)
            openai_api_key: API key for OpenAI
            gemini_api_key: API key for Gemini (not used)
        """
        self.models = {}
        
        # Initialize OpenAI
        if use_openai and openai_api_key:
            try:
                self.models['openai'] = OpenAIQA(
                    api_key=openai_api_key,
                    model="gpt-3.5-turbo"
                )
                logger.info("OpenAI model initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI: {str(e)}")
    
    async def analyze_paper(
        self,
        paper_content: Dict[str, str],
        model_name: Optional[str] = None
    ) -> Dict[str, Dict[str, Union[str, float, Dict[str, float]]]]:
        """Analyze a paper using OpenAI.
        
        Args:
            paper_content: Dictionary containing paper content
            model_name: Optional specific model to use (ignored, always uses OpenAI)
            
        Returns:
            Dictionary containing analysis results
        """
        if 'openai' not in self.models:
            return {
                "error": "OpenAI model not available",
                "confidence": 0.0,
                "status": "error",
                "key_findings": ["Error analyzing paper"],
                "suggested_topics": [],
                "found_terms": {},
                "category_scores": {},
                "num_tokens": 0
            }
        
        try:
            return await self.models['openai'].analyze_paper(paper_content)
        except Exception as e:
            logger.error(f"Error with OpenAI model: {str(e)}")
            return {
                "error": str(e),
                "confidence": 0.0,
                "status": "error",
                "key_findings": ["Error analyzing paper"],
                "suggested_topics": [],
                "found_terms": {},
                "category_scores": {},
                "num_tokens": 0
            }
    
    async def get_answer(
        self,
        question: str,
        context: str,
        model_name: Optional[str] = None
    ) -> Dict[str, Union[str, float]]:
        """Get an answer using OpenAI.
        
        Args:
            question: The question to answer
            context: Context information
            model_name: Optional specific model to use (ignored, always uses OpenAI)
            
        Returns:
            Dictionary containing the answer and confidence
        """
        if 'openai' not in self.models:
            return {
                "error": "OpenAI model not available",
                "confidence": 0.0
            }
        
        try:
            return await self.models['openai'].get_answer(question, context)
        except Exception as e:
            logger.error(f"Error with OpenAI model: {str(e)}")
            return {
                "error": str(e),
                "confidence": 0.0
            }
    
    def get_available_models(self) -> List[str]:
        """Get list of available models.
        
        Returns:
            List of model names
        """
        return list(self.models.keys())
    
    def get_model_capabilities(self) -> Dict[str, Dict]:
        """Get capabilities of OpenAI model.
        
        Returns:
            Dictionary of model capabilities
        """
        capabilities = {
            'openai': {
                'strengths': [
                    'Advanced text processing',
                    'Optimized for scientific text',
                    'Fast processing'
                ],
                'limitations': [
                    'Requires API key',
                    'May have usage limits'
                ]
            }
        }
        
        return {k: v for k, v in capabilities.items() 
                if k in self.models} 