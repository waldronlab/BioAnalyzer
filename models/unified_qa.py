from typing import Dict, List, Optional, Union
import logging
from .gemini_qa import GeminiQA

logger = logging.getLogger(__name__)

class UnifiedQA:
    """Unified QA system that can use Gemini."""
    
    def __init__(
        self,
        use_gemini: bool = True,
        gemini_api_key: Optional[str] = None
    ):
        """Initialize Unified QA system.
        
        Args:
            use_gemini: Whether to use Gemini
            gemini_api_key: API key for Gemini
        """
        self.models = {}
        
        # Initialize Gemini
        if use_gemini and gemini_api_key:
            try:
                self.models['gemini'] = GeminiQA(
                    api_key=gemini_api_key,
                    model="models/gemini-1.5-pro-latest"
                )
                logger.info("Gemini model initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini: {str(e)}")

    async def analyze_paper(
        self,
        paper_content: Dict[str, str],
        model_name: Optional[str] = None
    ) -> Dict[str, Dict[str, Union[str, float, Dict[str, float]]]]:
        """Analyze a paper using Gemini.
        
        Args:
            paper_content: Dictionary containing paper content
            model_name: Optional specific model to use (ignored, always uses Gemini)
            
        Returns:
            Dictionary containing analysis results
        """
        if 'gemini' not in self.models:
            return {
                "error": "Gemini model not available",
                "confidence": 0.0,
                "status": "error",
                "key_findings": ["Error analyzing paper"],
                "suggested_topics": [],
                "found_terms": {},
                "category_scores": {},
                "num_tokens": 0
            }
        try:
            return await self.models['gemini'].analyze_paper(paper_content)
        except Exception as e:
            logger.error(f"Error with Gemini model: {str(e)}")
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

    async def chat(self, prompt: str) -> dict:
        """Chat with Gemini (conversational, not paper analysis)."""
        if 'gemini' not in self.models:
            return {
                "text": "[Error: Gemini model not available]",
                "confidence": 0.0
            }
        try:
            return await self.models['gemini'].chat(prompt)
        except Exception as e:
            logger.error(f"Error with Gemini chat: {str(e)}")
            return {
                "text": f"[Error: {str(e)}]",
                "confidence": 0.0
            }

    def get_available_models(self) -> List[str]:
        """Get list of available models.
        
        Returns:
            List of model names
        """
        return list(self.models.keys())
    
    def get_model_capabilities(self) -> Dict[str, Dict]:
        """Get capabilities of Gemini model.
        
        Returns:
            Dictionary of model capabilities
        """
        capabilities = {
            'gemini': {
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