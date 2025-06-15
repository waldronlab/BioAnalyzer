import logging
import openai
from typing import Dict, List, Optional, Union
from pathlib import Path
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

class OpenAIQA:
    """Enhanced QA system using OpenAI's API for biomedical paper analysis."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-3.5-turbo",
        results_dir: Optional[Path] = None
    ):
        """Initialize OpenAI QA system.
        
        Args:
            api_key: OpenAI API key
            model: OpenAI model to use
            results_dir: Directory to save analysis results
        """
        # Configure the OpenAI API
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.results_dir = results_dir or Path("results")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Default prompts optimized for OpenAI's capabilities
        self.prompts = {
            "key_findings": "Extract the key findings and main conclusions from this paper. Focus on microbial signatures, host-microbiome interactions, and any significant associations found.",
            "suggested_topics": "What are the main topics and themes discussed in this paper? Focus on microbial signatures, host-microbiome interactions, and related concepts.",
            "found_terms": "Identify important terms related to microbial signatures, host-microbiome interactions, and related concepts in this paper.",
            "category_scores": "Analyze this paper and provide scores for different categories: microbial signature presence, host-microbiome interaction, statistical significance, and methodological quality."
        }
    
    async def analyze_paper(
        self,
        paper_content: Dict[str, str]
    ) -> Dict[str, Union[str, float, Dict[str, float]]]:
        """Analyze a paper using OpenAI's advanced capabilities.
        
        Args:
            paper_content: Dictionary containing paper content (title, abstract, full_text)
            
        Returns:
            Dictionary containing analysis results
        """
        try:
            # Prepare the paper content
            content = f"Title: {paper_content.get('title', '')}\n"
            content += f"Abstract: {paper_content.get('abstract', '')}\n"
            if paper_content.get('full_text'):
                content += f"Full Text: {paper_content['full_text']}\n"
            
            # Get analysis from OpenAI
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant analyzing scientific papers. Extract key findings, suggested topics, and categorize the content."},
                    {"role": "user", "content": f"Analyze this paper:\n{content}"}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            # Parse the response
            analysis_text = response.choices[0].message.content
            
            # Save results if directory is specified
            if self.results_dir:
                timestamp = datetime.now(pytz.UTC).strftime("%Y%m%d_%H%M%S")
                paper_title = paper_content.get('title', 'unknown').replace(' ', '_')
                filename = self.results_dir / f"openai_analysis_{timestamp}_{paper_title[:50]}.json"
                
                with open(filename, 'w') as f:
                    f.write(analysis_text)
                logger.info(f"Analysis saved to {filename}")
            
            return {
                "key_findings": [line.strip() for line in analysis_text.split('\n') if line.strip()],
                "confidence": 0.8,
                "status": "success",
                "suggested_topics": [],
                "found_terms": {},
                "category_scores": {},
                "num_tokens": len(analysis_text.split())
            }
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"OpenAI API error in paper analysis: {error_str}")
            return {
                "error": error_str,
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
        context: str
    ) -> Dict[str, Union[str, float]]:
        """Get an answer to a question using OpenAI API.
        
        Args:
            question: The question to answer
            context: Context information
            
        Returns:
            Dictionary containing the answer and confidence
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"You are a helpful assistant analyzing a scientific paper. Here is the context:\n\n{context}"},
                    {"role": "user", "content": question}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            return {
                "answer": response.choices[0].message.content,
                "confidence": 0.8
            }
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"OpenAI API error: {error_str}")
            return {
                "error": error_str,
                "confidence": 0.0
            }
    
    async def chat_with_context(
        self,
        message: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        paper_context: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Chat with context using OpenAI API.
        
        Args:
            message: The user's message
            chat_history: Optional list of previous messages
            paper_context: Optional paper context
            
        Returns:
            Dictionary containing the response
        """
        try:
            # Prepare messages
            messages = []
            
            # Add system message with paper context if available
            if paper_context:
                system_prompt = f"You are a helpful assistant analyzing a scientific paper. Paper title: {paper_context.get('title', '')}\nAbstract: {paper_context.get('abstract', '')}"
                messages.append({"role": "system", "content": system_prompt})
            
            # Add chat history
            if chat_history:
                for msg in chat_history:
                    messages.append({"role": msg["role"], "content": msg["content"]})
            
            # Add current message
            messages.append({"role": "user", "content": message})
            
            # Get response from OpenAI
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            return {
                "response": response.choices[0].message.content
            }
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"OpenAI API error: {error_str}")
            return {
                "error": error_str
            } 