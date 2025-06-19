import logging
from typing import Dict, List, Optional, Union
from pathlib import Path
from datetime import datetime
import pytz
import google.generativeai as genai
import os

logger = logging.getLogger(__name__)

class GeminiQA:
    """Enhanced QA system using Gemini's API for biomedical paper analysis."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-pro", results_dir: Optional[Path] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model
        self.results_dir = results_dir or Path("results")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        if not self.api_key:
            logger.warning("No Gemini API key provided. Set GEMINI_API_KEY in your environment.")
        genai.configure(api_key=self.api_key)

    async def analyze_paper(self, paper_content: Dict[str, str]) -> Dict[str, Union[str, float, Dict[str, float]]]:
        """Analyze a paper using Gemini's advanced capabilities."""
        try:
            # Prepare the prompt
            content = f"Title: {paper_content.get('title', '')}\n"
            content += f"Abstract: {paper_content.get('abstract', '')}\n"
            if paper_content.get('full_text'):
                content += f"Full Text: {paper_content['full_text']}\n"

            prompt = (
                "You are a helpful assistant analyzing scientific papers. "
                "Extract key findings, suggested topics, and categorize the content. "
                "Return your answer as a structured summary."
            )

            # Use Gemini API to generate the analysis
            model = genai.GenerativeModel(self.model)
            response = await model.generate_content_async(f"{prompt}\nAnalyze this paper:\n{content}")
            analysis_text = response.text.strip()

            # Save results if directory is specified
            if self.results_dir:
                timestamp = datetime.now(pytz.UTC).strftime("%Y%m%d_%H%M%S")
                paper_title = paper_content.get('title', 'unknown').replace(' ', '_')
                filename = self.results_dir / f"gemini_analysis_{timestamp}_{paper_title[:50]}.txt"
                with open(filename, 'w') as f:
                    f.write(analysis_text)
                logger.info(f"Analysis saved to {filename}")

            # Parse the response (simple split, can be improved)
            key_findings = [line.strip() for line in analysis_text.split('\n') if line.strip()]

            return {
                "key_findings": key_findings,
                "confidence": 0.8,  # Placeholder, Gemini does not return confidence
                "status": "success",
                "suggested_topics": [],
                "found_terms": {},
                "category_scores": {},
                "num_tokens": len(analysis_text.split()),
            }
        except Exception as e:
            error_str = str(e)
            logger.error(f"Gemini API error in paper analysis: {error_str}")
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