import logging
from typing import Dict, List, Optional, Union
from .gemini_qa import GeminiQA

logger = logging.getLogger(__name__)

class UnifiedQA:
    """Unified QA system that wraps GeminiQA for conversational interactions."""
    
    def __init__(self, use_gemini: bool = True, gemini_api_key: Optional[str] = None):
        """Initialize the unified QA system.
        
        Args:
            use_gemini: Whether to use Gemini API
            gemini_api_key: API key for Gemini
        """
        self.use_gemini = use_gemini
        if use_gemini and gemini_api_key:
            self.qa_system = GeminiQA(api_key=gemini_api_key)
        else:
            self.qa_system = None
            logger.warning("No Gemini API key provided. Chat functionality will be limited.")
    
    async def chat(self, prompt: str) -> dict:
        """Chat with the QA system.
        
        Args:
            prompt: User's message
            
        Returns:
            Dictionary with response text and confidence
        """
        if not self.qa_system:
            return {
                "text": "Sorry, I'm not available right now. Please check your API configuration.",
                "confidence": 0.0
            }
        
        try:
            return await self.qa_system.chat(prompt)
        except Exception as e:
            logger.error(f"Error in chat: {str(e)}")
            return {
                "text": f"Sorry, I encountered an error: {str(e)}",
                "confidence": 0.0
            }
    
    async def analyze_paper(self, paper_content: Dict[str, str]) -> dict:
        """Analyze a paper using the QA system.
        
        Args:
            paper_content: Dictionary containing paper information
            
        Returns:
            Dictionary with analysis results
        """
        if not self.qa_system:
            return {
                "error": "QA system not available",
                "confidence": 0.0,
                "status": "error"
            }
        
        try:
            return await self.qa_system.analyze_paper(paper_content)
        except Exception as e:
            logger.error(f"Error analyzing paper: {str(e)}")
            return {
                "error": str(e),
                "confidence": 0.0,
                "status": "error"
            } 

    async def analyze_paper_enhanced(self, prompt: str) -> Dict[str, Union[str, float, List[str]]]:
        """
        Enhanced analysis method for BugSigDB curation requirements.
        """
        if self.use_gemini and self.qa_system:
            return await self.qa_system.analyze_paper_enhanced(prompt)
        else:
            return {
                "error": "No enhanced analysis available",
                "key_findings": "{}",
                "confidence": 0.0
            } 