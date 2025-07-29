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

    def parse_enhanced_analysis(self, analysis_text: str) -> Dict[str, Union[str, float, List[str]]]:
        """Parse the enhanced analysis text to extract structured curation information."""
        try:
            lines = analysis_text.split('\n')
            curation_analysis = {
                "readiness": "UNKNOWN",
                "explanation": "",
                "microbial_signatures": "Unknown",
                "signature_types": [],
                "data_quality": "Unknown",
                "statistical_significance": "Unknown",
                "required_fields": [],
                "missing_fields": [],
                "data_completeness": "Unknown",
                "specific_reasons": [],
                "confidence": 0.0,
                "examples": []
            }
            
            current_section = ""
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Detect sections
                if "CURATION READINESS ASSESSMENT:" in line:
                    current_section = "readiness"
                    continue
                elif "DETAILED EXPLANATION:" in line:
                    current_section = "explanation"
                    continue
                elif "MICROBIAL SIGNATURE ANALYSIS:" in line:
                    current_section = "signatures"
                    continue
                elif "CURATABLE CONTENT ASSESSMENT:" in line:
                    current_section = "content"
                    continue
                elif "SPECIFIC REASONS" in line:
                    current_section = "reasons"
                    continue
                elif "CONFIDENCE LEVEL:" in line:
                    current_section = "confidence"
                    continue
                elif "EXAMPLES AND EVIDENCE:" in line:
                    current_section = "examples"
                    continue
                
                # Parse content based on current section
                if current_section == "readiness":
                    line_upper = line.upper()
                    if "READY FOR CURATION" in line_upper:
                        curation_analysis["readiness"] = "READY"
                    elif "NOT READY FOR CURATION" in line_upper:
                        curation_analysis["readiness"] = "NOT_READY"
                    elif "READY" in line_upper and "NOT" not in line_upper and "NOT READY" not in line_upper:
                        curation_analysis["readiness"] = "READY"
                    elif "NOT READY" in line_upper:
                        curation_analysis["readiness"] = "NOT_READY"
                    elif "UNKNOWN" in line_upper or "UNCLEAR" in line_upper:
                        curation_analysis["readiness"] = "UNKNOWN"
                    # Also check if the line contains the readiness status directly
                    elif any(status in line_upper for status in ["READY", "NOT READY", "UNKNOWN"]):
                        if "READY" in line_upper and "NOT" not in line_upper:
                            curation_analysis["readiness"] = "READY"
                        elif "NOT READY" in line_upper:
                            curation_analysis["readiness"] = "NOT_READY"
                        elif "UNKNOWN" in line_upper:
                            curation_analysis["readiness"] = "UNKNOWN"
                elif current_section == "explanation":
                    curation_analysis["explanation"] += line + " "
                elif current_section == "signatures":
                    if "Presence of microbial signatures:" in line:
                        if "yes" in line.lower():
                            curation_analysis["microbial_signatures"] = "Present"
                        elif "no" in line.lower():
                            curation_analysis["microbial_signatures"] = "Absent"
                        elif "partial" in line.lower():
                            curation_analysis["microbial_signatures"] = "Partial"
                    elif "Types of signatures found:" in line:
                        # Extract signature types
                        types_text = line.split(":", 1)[1] if ":" in line else ""
                        curation_analysis["signature_types"] = [t.strip() for t in types_text.split(",") if t.strip()]
                    elif "Quality of signature data:" in line:
                        if "high" in line.lower():
                            curation_analysis["data_quality"] = "High"
                        elif "medium" in line.lower():
                            curation_analysis["data_quality"] = "Medium"
                        elif "low" in line.lower():
                            curation_analysis["data_quality"] = "Low"
                    elif "Statistical significance:" in line:
                        if "yes" in line.lower():
                            curation_analysis["statistical_significance"] = "Yes"
                        elif "no" in line.lower():
                            curation_analysis["statistical_significance"] = "No"
                        elif "insufficient" in line.lower():
                            curation_analysis["statistical_significance"] = "Insufficient"
                elif current_section == "content":
                    if "Missing required fields:" in line:
                        # Extract missing fields
                        fields_text = line.split(":", 1)[1] if ":" in line else ""
                        curation_analysis["missing_fields"] = [f.strip() for f in fields_text.split(",") if f.strip()]
                    elif "Data completeness:" in line:
                        if "complete" in line.lower():
                            curation_analysis["data_completeness"] = "Complete"
                        elif "partial" in line.lower():
                            curation_analysis["data_completeness"] = "Partial"
                        elif "insufficient" in line.lower():
                            curation_analysis["data_completeness"] = "Insufficient"
                elif current_section == "reasons":
                    if line.startswith("-") or line.startswith("*"):
                        curation_analysis["specific_reasons"].append(line.lstrip("- *").strip())
                elif current_section == "confidence":
                    # Extract confidence score
                    import re
                    confidence_match = re.search(r'(\d+\.?\d*)', line)
                    if confidence_match:
                        curation_analysis["confidence"] = float(confidence_match.group(1))
                elif current_section == "examples":
                    if line.startswith("-") or line.startswith("*"):
                        curation_analysis["examples"].append(line.lstrip("- *").strip())
            
            # Clean up explanation
            curation_analysis["explanation"] = curation_analysis["explanation"].strip()
            
            return curation_analysis
            
        except Exception as e:
            logger.error(f"Error parsing enhanced analysis: {str(e)}")
            return {
                "readiness": "ERROR",
                "explanation": f"Error parsing analysis: {str(e)}",
                "microbial_signatures": "Unknown",
                "signature_types": [],
                "data_quality": "Unknown",
                "statistical_significance": "Unknown",
                "required_fields": [],
                "missing_fields": [],
                "data_completeness": "Unknown",
                "specific_reasons": [],
                "confidence": 0.0,
                "examples": []
            }

    async def analyze_paper(self, paper_content: Dict[str, str]) -> Dict[str, Union[str, float, Dict[str, float]]]:
        """Analyze a paper using Gemini's advanced capabilities with detailed curation readiness assessment."""
        try:
            # Prepare the prompt
            content = f"Title: {paper_content.get('title', '')}\n"
            content += f"Abstract: {paper_content.get('abstract', '')}\n"
            if paper_content.get('full_text'):
                content += f"Full Text: {paper_content['full_text']}\n"

            # Enhanced prompt for detailed curation analysis
            prompt = """You are an expert scientific curator specializing in microbial signature analysis for BugSigDB. Your task is to analyze this paper and provide a comprehensive assessment of its curation readiness.

Please provide a detailed analysis in the following structured format:

**CURATION READINESS ASSESSMENT:**
[Start with a clear statement: "READY FOR CURATION" or "NOT READY FOR CURATION"]

**DETAILED EXPLANATION:**
[Provide a comprehensive explanation of why the paper is or isn't ready for curation]

**MICROBIAL SIGNATURE ANALYSIS:**
- Presence of microbial signatures: [Yes/No/Partial]
- Types of signatures found: [List specific types]
- Quality of signature data: [High/Medium/Low]
- Statistical significance: [Yes/No/Insufficient]

**CURATABLE CONTENT ASSESSMENT:**
- Required fields present: [List what's available]
- Missing required fields: [List what's missing]
- Data completeness: [Complete/Partial/Insufficient]

**SPECIFIC REASONS FOR READINESS/NON-READINESS:**
[If NOT READY, explain exactly what's missing and provide examples of what would make it curatable]
[If READY, explain what makes it suitable for curation]

**KEY FINDINGS:**
[List the main scientific findings related to microbial signatures]

**SUGGESTED TOPICS FOR FUTURE RESEARCH:**
[List potential follow-up studies or related research directions]

**CONFIDENCE LEVEL:**
[Provide a confidence score (0.0-1.0) with explanation]

**EXAMPLES AND EVIDENCE:**
[Provide specific examples from the text that support your assessment]

Please be thorough and specific in your analysis, especially when explaining why a paper is not ready for curation. Include specific examples and evidence from the text."""

            # Use Gemini API to generate the analysis
            model = genai.GenerativeModel(self.model)
            response = await model.generate_content_async(f"{prompt}\n\nAnalyze this paper:\n{content}")
            analysis_text = response.text.strip()

            # Save results if directory is specified
            if self.results_dir:
                timestamp = datetime.now(pytz.UTC).strftime("%Y%m%d_%H%M%S")
                paper_title = paper_content.get('title', 'unknown').replace(' ', '_')
                filename = self.results_dir / f"gemini_analysis_{timestamp}_{paper_title[:50]}.txt"
                with open(filename, 'w') as f:
                    f.write(analysis_text)
                logger.info(f"Analysis saved to {filename}")

            # Enhanced parsing of the response
            logger.info(f"Raw LLM response for debugging:\n{analysis_text}")
            curation_analysis = self.parse_enhanced_analysis(analysis_text)
            logger.info(f"Parsed curation analysis: {curation_analysis}")
            
            # Parse the response for backward compatibility
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
                "curation_analysis": curation_analysis,  # New detailed curation analysis
                "raw_analysis": analysis_text  # Keep raw text for debugging
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
                "num_tokens": 0,
                "curation_analysis": {
                    "readiness": "ERROR",
                    "explanation": f"Error during analysis: {error_str}",
                    "microbial_signatures": "Unknown",
                    "missing_fields": [],
                    "confidence": 0.0
                }
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