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

    def __init__(self, api_key: Optional[str] = None, model: str = "models/gemini-1.5-pro-latest", results_dir: Optional[Path] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model
        self.results_dir = results_dir or Path("results")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        if not self.api_key:
            logger.warning("No Gemini API key provided. Set GEMINI_API_KEY in your environment.")
        genai.configure(api_key=self.api_key)

    def estimate_confidence(self, key_findings):
        if not key_findings:
            return 0.0
        # Example: more findings = higher confidence, up to 1.0
        return min(1.0, 0.3 + 0.15 * len(key_findings))

    def estimate_category_scores(self, key_findings):
        # Define simple keyword lists for each category
        categories = {
            "microbiome": ["microbiome", "microbial", "bacteria", "microbiota"],
            "methods": ["16s", "metagenomic", "sequencing", "amplicon", "shotgun", "transcriptomic", "qpcr", "fish"],
            "analysis": ["enriched", "depleted", "increased", "decreased", "differential", "higher abundance", "lower abundance"],
            "body_sites": ["gut", "oral", "skin", "lung", "vaginal", "intestinal", "colon", "mouth", "dermal", "epidermis", "airway", "bronchial", "cervical"],
            "diseases": ["ibd", "cancer", "tumor", "carcinoma", "neoplasm", "obesity", "diabetes", "infection", "autoimmune", "arthritis", "lupus", "multiple sclerosis"]
        }
        text = " ".join(key_findings).lower()
        scores = {}
        for cat, keywords in categories.items():
            count = sum(1 for kw in keywords if kw in text)
            # Normalize: 0 if no keywords, up to 1.0 if all present
            scores[cat] = min(1.0, count / max(1, len(keywords)))
        return scores

    def parse_gemini_output(self, key_findings):
        findings = []
        suggested_topics = []
        in_suggested = False
        for line in key_findings:
            if 'Suggested Topics' in line or 'Suggested Topics for Future Research' in line:
                in_suggested = True
                continue
            if in_suggested:
                if line.strip().startswith('*') or line.strip().startswith('-'):
                    suggested_topics.append(line.strip('*- ').strip())
                elif line.strip() == '' or line.strip().startswith('**'):
                    continue
                else:
                    in_suggested = False
            if not in_suggested:
                findings.append(line)
        return findings, suggested_topics

    def extract_found_terms(self, key_findings):
        # Use the same categories as for category_scores
        categories = {
            "microbiome": ["microbiome", "microbial", "bacteria", "microbiota"],
            "methods": ["16s", "metagenomic", "sequencing", "amplicon", "shotgun", "transcriptomic", "qpcr", "fish"],
            "analysis": ["enriched", "depleted", "increased", "decreased", "differential", "higher abundance", "lower abundance"],
            "body_sites": ["gut", "oral", "skin", "lung", "vaginal", "intestinal", "colon", "mouth", "dermal", "epidermis", "airway", "bronchial", "cervical"],
            "diseases": ["ibd", "cancer", "tumor", "carcinoma", "neoplasm", "obesity", "diabetes", "infection", "autoimmune", "arthritis", "lupus", "multiple sclerosis"]
        }
        text = " ".join(key_findings).lower()
        found = {}
        for cat, keywords in categories.items():
            found[cat] = [kw for kw in keywords if kw in text]
        return found

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
            key_findings_raw = [line.strip() for line in analysis_text.split('\n') if line.strip()]
            confidence = self.estimate_confidence(key_findings_raw)
            category_scores = self.estimate_category_scores(key_findings_raw)
            findings, suggested_topics = self.parse_gemini_output(key_findings_raw)
            found_terms = self.extract_found_terms(key_findings_raw)

            return {
                "key_findings": findings,
                "confidence": confidence,
                "status": "success",
                "suggested_topics": suggested_topics,
                "found_terms": found_terms,
                "category_scores": category_scores,
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

    async def chat(self, prompt: str) -> dict:
        """Chat with Gemini using a conversational prompt."""
        try:
            chat_prompt = (
                "You are a helpful scientific assistant. Answer the user's question or message conversationally. "
                "If the user provides a paper context, use it to inform your answer."
            )
            model = genai.GenerativeModel(self.model)
            response = await model.generate_content_async(f"{chat_prompt}\nUser: {prompt}")
            reply = response.text.strip()
            confidence = 1.0 if reply else 0.0
            return {
                "text": reply,
                "confidence": confidence
            }
        except Exception as e:
            logger.error(f"Gemini API error in chat: {str(e)}")
            return {
                "text": f"[Error: {str(e)}]",
                "confidence": 0.0
            } 