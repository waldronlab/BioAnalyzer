from typing import Dict, List, Optional, Union
import json
from pathlib import Path
import logging
from datetime import datetime
import google.generativeai as genai
import asyncio
from utils.utils import config

logger = logging.getLogger(__name__)

class GeminiQA:
    """Enhanced QA system using Google's Gemini API for biomedical paper analysis."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-pro",
        cache_results: bool = True
    ):
        """Initialize Gemini QA system.
        
        Args:
            api_key: Gemini API key
            model: Gemini model to use
            cache_results: Whether to cache analysis results
        """
        self.api_key = api_key
        self.model = model
        self.cache_results = cache_results
        self.results_dir = Path("analysis_results")
        self.results_dir.mkdir(exist_ok=True)
        
        # Configure the Gemini API
        genai.configure(api_key=self.api_key)
        
        # Default prompts optimized for Gemini's capabilities
        self.default_prompts = {
            "signature_analysis": {
                "system_prompt": """You are a biomedical research expert analyzing papers for microbial signatures.
                Focus on identifying and explaining:
                1. Differential abundance patterns
                2. Statistical significance
                3. Biological relevance
                4. Methodology validation""",
                "user_template": """Analyze the following paper for microbial signatures:
                Title: {title}
                Abstract: {abstract}
                Full Text: {full_text}
                
                Provide a structured analysis covering:
                1. Key microbial signatures identified
                2. Statistical methods used
                3. Validation approaches
                4. Confidence in findings"""
            },
            "methodology_review": {
                "system_prompt": """You are a bioinformatics expert reviewing methodological approaches.
                Focus on:
                1. Sequencing technologies
                2. Data processing pipelines
                3. Statistical analyses
                4. Quality control measures""",
                "user_template": """Review the methodology of the following paper:
                Title: {title}
                Abstract: {abstract}
                Full Text: {full_text}
                
                Provide a detailed assessment of:
                1. Technical approaches
                2. Data quality measures
                3. Analysis pipelines
                4. Methodological strengths/limitations"""
            }
        }
    
    async def analyze_paper(
        self,
        paper_content: Dict[str, str],
        analysis_types: Optional[List[str]] = None,
        custom_prompts: Optional[Dict[str, Dict[str, str]]] = None
    ) -> Dict[str, Dict[str, Union[str, float, Dict[str, float]]]]:
        """Analyze a paper using Gemini's advanced capabilities.
        
        Args:
            paper_content: Dictionary containing paper content
            analysis_types: Optional list of analysis types to perform
            custom_prompts: Optional custom prompts to use
            
        Returns:
            Dictionary containing analysis results
        """
        results = {}
        
        # Use default or custom prompts
        prompts_to_use = custom_prompts if custom_prompts else self.default_prompts
        
        for analysis_type, prompt_data in prompts_to_use.items():
            if analysis_types and analysis_type not in analysis_types:
                continue
                
            try:
                # Format the user prompt with paper content
                formatted_prompt = prompt_data["user_template"].format(**paper_content)
                
                # Create a Gemini model instance
                generation_config = {
                    "temperature": 0.2,
                    "top_p": 0.8,
                    "top_k": 40,
                    "max_output_tokens": 2048,
                }
                
                safety_settings = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                ]
                
                model = genai.GenerativeModel(
                    model_name=self.model,
                    generation_config=generation_config,
                    safety_settings=safety_settings,
                )
                
                # Run the model in a separate thread to avoid blocking
                loop = asyncio.get_event_loop()
                try:
                    response = await loop.run_in_executor(
                        None, 
                        lambda: model.generate_content([
                            {"role": "system", "parts": [prompt_data["system_prompt"]]},
                            {"role": "user", "parts": [formatted_prompt]}
                        ])
                    )
                    
                    # Process the response
                    response_text = response.text
                    
                    # Extract key findings, confidence, and other metadata
                    key_findings = self._extract_key_findings(response_text)
                    confidence = self._calculate_confidence(response_text)
                    category_scores = self._extract_category_scores(response_text)
                    found_terms = self._extract_found_terms(response_text, paper_content)
                    
                    results[analysis_type] = {
                        "analysis": response_text,
                        "key_findings": key_findings,
                        "confidence": confidence,
                        "category_scores": category_scores,
                        "found_terms": found_terms,
                        "host": self._extract_host(found_terms),
                        "body_site": self._extract_body_site(found_terms),
                        "condition": self._extract_condition(found_terms),
                        "sequencing_type": self._extract_sequencing_type(found_terms),
                        "sample_size": self._extract_sample_size(found_terms, paper_content),
                        "taxa_level": self._extract_taxa_level(found_terms),
                        "statistical_method": self._extract_statistical_method(found_terms, response_text)
                    }
                except Exception as api_error:
                    error_str = str(api_error)
                    logger.error(f"Gemini API error in {analysis_type} analysis: {error_str}")
                    
                    # Check for IP restriction errors
                    if "API_KEY_IP_ADDRESS_BLOCKED" in error_str or "IP address restriction" in error_str:
                        results[analysis_type] = {
                            "error": "IP_RESTRICTED",
                            "analysis": "The Gemini API key has IP address restrictions. Your current IP address is not authorized to use this API key. Please update the API key in your .env file to one without IP restrictions or add your current IP to the allowed list.",
                            "confidence": 0.0
                        }
                    else:
                        results[analysis_type] = {
                            "error": f"API_ERROR: {error_str}",
                            "confidence": 0.0
                        }
            except Exception as e:
                logger.error(f"Error in {analysis_type} analysis: {str(e)}")
                results[analysis_type] = {
                    "error": str(e),
                    "confidence": 0.0
                }
        
        if self.cache_results:
            self._save_results(paper_content.get("title", "untitled"), results)
            
        return results
    
    async def get_answer(self, question: str, context: str) -> Dict[str, Union[str, float]]:
        """Get an answer to a question using Gemini API.
        
        Args:
            question: The question to answer
            context: Context information to help answer the question
            
        Returns:
            Dictionary containing the answer and confidence score
        """
        try:
            logger.info(f"Processing question: {question[:50]}...")
            
            # Create a prompt that includes the context and question
            prompt = f"""Context information:
            {context}
            
            Based on the context information above, please answer the following question:
            {question}
            
            If the answer cannot be determined from the context, please say so.
            """
            
            # Create a Gemini model instance
            generation_config = {
                "temperature": 0.2,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 1024,
            }
            
            model = genai.GenerativeModel(
                model_name=self.model,
                generation_config=generation_config,
            )
            
            # Run the model in a separate thread to avoid blocking
            loop = asyncio.get_event_loop()
            try:
                response = await loop.run_in_executor(
                    None, 
                    lambda: model.generate_content(prompt)
                )
                
                # Process the response
                answer = response.text
                
                # Calculate confidence based on response content
                confidence = self._calculate_answer_confidence(answer, question)
                
                return {
                    "answer": answer,
                    "confidence": confidence
                }
            except Exception as api_error:
                error_str = str(api_error)
                logger.error(f"Gemini API error: {error_str}")
                
                # Check for IP restriction errors
                if "API_KEY_IP_ADDRESS_BLOCKED" in error_str or "IP address restriction" in error_str:
                    return {
                        "error": "IP_RESTRICTED",
                        "answer": "The Gemini API key has IP address restrictions. Your current IP address is not authorized to use this API key. Please update the API key in your .env file to one without IP restrictions or add your current IP to the allowed list.",
                        "confidence": 0.0
                    }
                else:
                    return {
                        "error": "API_ERROR",
                        "answer": f"Error calling Gemini API: {error_str}",
                        "confidence": 0.0
                    }
        except Exception as e:
            logger.error(f"Error in get_answer: {str(e)}")
            return {
                "error": str(e),
                "answer": f"Sorry, I couldn't process your question due to an error: {str(e)}",
                "confidence": 0.0
            }
    
    async def chat_with_context(
        self, 
        message: str, 
        chat_history: Optional[List[Dict]] = None,
        paper_context: Optional[Dict] = None
    ) -> Dict[str, str]:
        """Chat with context using Gemini API.
        
        Args:
            message: User message
            chat_history: Optional chat history as a list of message dictionaries with 'role' and 'content' keys
            paper_context: Optional paper context
            
        Returns:
            Dictionary containing response
        """
        try:
            logger.info(f"Processing chat message: {message[:50]}...")
            
            # Format chat history for Gemini
            gemini_messages = []
            
            # Add system prompt
            system_prompt = "You are a helpful AI assistant for BugSigDB, specialized in microbial signatures in scientific papers."
            
            # Add paper context if available
            if paper_context:
                paper_info = f"""
                I'm currently looking at a scientific paper with:
                PMID: {paper_context.get('pmid', 'Unknown')}
                Title: {paper_context.get('title', 'Unknown')}
                Abstract: {paper_context.get('abstract', 'Not available')}
                
                Please keep this paper in mind when answering my questions.
                """
                system_prompt += "\n\n" + paper_info
            
            gemini_messages.append({"role": "system", "parts": [system_prompt]})
            
            # Add chat history if available
            if chat_history:
                for msg in chat_history:
                    if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                        role = msg['role']
                        content = msg['content']
                        # Map 'user' and 'assistant' roles to Gemini's expected format
                        if role in ['user', 'assistant'] and content:
                            gemini_messages.append({"role": role, "parts": [content]})
            
            # Add current message
            gemini_messages.append({"role": "user", "parts": [message]})
            
            # Create a Gemini model instance
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 1024,
            }
            
            model = genai.GenerativeModel(
                model_name=self.model,
                generation_config=generation_config,
            )
            
            # Run the model in a separate thread to avoid blocking
            loop = asyncio.get_event_loop()
            try:
                response = await loop.run_in_executor(
                    None, 
                    lambda: model.generate_content(gemini_messages)
                )
                
                # Process the response
                response_text = response.text
                
                return {
                    "response": response_text,
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as api_error:
                error_str = str(api_error)
                logger.error(f"Gemini API error: {error_str}")
                
                # Check for IP restriction errors
                if "API_KEY_IP_ADDRESS_BLOCKED" in error_str or "IP address restriction" in error_str:
                    return {
                        "error": "IP_RESTRICTED",
                        "response": "The Gemini API key has IP address restrictions. Your current IP address is not authorized to use this API key. Please update the API key in your .env file to one without IP restrictions or add your current IP to the allowed list.",
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    return {
                        "error": "API_ERROR",
                        "response": f"Error calling Gemini API: {error_str}",
                        "timestamp": datetime.now().isoformat()
                    }
                
        except Exception as e:
            logger.error(f"Error in chat_with_context: {str(e)}")
            return {
                "response": f"I'm sorry, I encountered an error while processing your message. Error details: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
    
    def _save_results(self, paper_title: str, results: Dict) -> None:
        """Save analysis results to disk.
        
        Args:
            paper_title: Title of the analyzed paper
            results: Analysis results to save
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.results_dir / f"gemini_analysis_{timestamp}_{paper_title[:50]}.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
            
        logger.info(f"Results saved to {filename}")
    
    def _extract_key_findings(self, text: str) -> List[str]:
        """Extract key findings from response text."""
        findings = []
        
        # Look for numbered lists, bullet points, or sections labeled "findings"
        lines = text.split('\n')
        in_findings_section = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if we're entering a findings section
            if "key findings" in line.lower() or "main findings" in line.lower():
                in_findings_section = True
                continue
                
            # Check if we're leaving a findings section
            if in_findings_section and (line.lower().startswith("conclusion") or 
                                        line.lower().startswith("discussion") or
                                        line.lower().startswith("summary")):
                in_findings_section = False
                
            # Extract findings from numbered or bullet points
            if in_findings_section or any(marker in line for marker in ["1.", "2.", "3.", "•", "-", "●"]):
                # Remove leading numbers or bullets
                cleaned_line = line
                for prefix in ["1.", "2.", "3.", "4.", "5.", "•", "-", "●"]:
                    if cleaned_line.startswith(prefix):
                        cleaned_line = cleaned_line[len(prefix):].strip()
                        break
                
                if cleaned_line and len(cleaned_line) > 10:
                    findings.append(cleaned_line)
        
        # If no structured findings were found, try to extract sentences with key terms
        if not findings:
            key_terms = ["significant", "increased", "decreased", "associated", "correlation", 
                        "abundance", "enriched", "depleted", "higher", "lower"]
            for line in lines:
                if any(term in line.lower() for term in key_terms) and len(line) > 20:
                    findings.append(line.strip())
                    if len(findings) >= 5:  # Limit to 5 findings
                        break
        
        return findings[:10]  # Limit to 10 findings
    
    def _calculate_confidence(self, text: str) -> float:
        """Calculate confidence score based on response text."""
        confidence_indicators = {
            "high": ["significant", "p<0.01", "strong evidence", "clearly shows", "robust", 
                    "consistent", "well-established", "validated"],
            "medium": ["suggests", "indicates", "may", "could", "potentially", "p<0.05", 
                      "moderate", "trends toward"],
            "low": ["unclear", "limited evidence", "preliminary", "inconclusive", "uncertain", 
                   "mixed results", "contradictory", "needs further research"]
        }
        
        # Count occurrences of each indicator
        counts = {"high": 0, "medium": 0, "low": 0}
        text_lower = text.lower()
        
        for level, indicators in confidence_indicators.items():
            for indicator in indicators:
                counts[level] += text_lower.count(indicator)
        
        # Calculate weighted score
        total_indicators = sum(counts.values())
        if total_indicators == 0:
            return 0.5  # Default confidence
            
        weighted_score = (counts["high"] * 1.0 + counts["medium"] * 0.5 + counts["low"] * 0.2) / total_indicators
        
        # Normalize between 0.1 and 0.9
        normalized_score = 0.1 + (weighted_score * 0.8)
        return min(0.9, max(0.1, normalized_score))
    
    def _extract_category_scores(self, text: str) -> Dict[str, float]:
        """Extract category scores from response text."""
        categories = {
            "methodology_quality": ["methodology", "methods", "protocol", "procedure", "technique"],
            "statistical_rigor": ["statistical", "statistics", "analysis", "p-value", "significance"],
            "sample_size": ["sample size", "participants", "subjects", "cohort", "population"],
            "signature_presence": ["signature", "biomarker", "indicator", "differential abundance"],
            "validation": ["validation", "verified", "confirmed", "replicated", "reproducible"]
        }
        
        scores = {}
        text_lower = text.lower()
        
        for category, keywords in categories.items():
            # Count occurrences of keywords
            keyword_count = sum(text_lower.count(keyword) for keyword in keywords)
            
            # Adjust score based on positive/negative context
            positive_context = sum(text_lower.count(f"{keyword} {pos}") 
                                for keyword in keywords 
                                for pos in ["good", "strong", "robust", "adequate", "appropriate"])
            
            negative_context = sum(text_lower.count(f"{keyword} {neg}") 
                                 for keyword in keywords 
                                 for neg in ["poor", "weak", "inadequate", "limited", "insufficient"])
            
            # Calculate base score from 0-1
            base_score = min(1.0, keyword_count / 10)
            
            # Adjust score based on context
            context_adjustment = (positive_context - negative_context) * 0.1
            final_score = max(0.0, min(1.0, base_score + context_adjustment))
            
            scores[category] = final_score
        
        return scores
    
    def _extract_found_terms(self, text: str, paper_content: Dict[str, str]) -> Dict[str, List[str]]:
        """Extract found terms from response text and paper content."""
        # Categories of terms to extract
        term_categories = {
            "host": ["human", "mouse", "rat", "animal model", "patient", "subject", "participant"],
            "body site": ["gut", "oral", "skin", "vaginal", "intestinal", "stool", "fecal", "saliva"],
            "condition": ["disease", "disorder", "syndrome", "infection", "healthy", "control"],
            "sequencing type": ["16S rRNA", "shotgun", "metagenomics", "metatranscriptomics", "amplicon"],
            "taxa": ["phylum", "class", "order", "family", "genus", "species", "strain"],
            "statistical method": ["PERMANOVA", "ANOVA", "t-test", "Wilcoxon", "LEfSe", "DESeq2", "random forest"]
        }
        
        found_terms = {}
        
        # Combine response text and paper content for searching
        combined_text = text + " " + paper_content.get("title", "") + " " + paper_content.get("abstract", "")
        combined_text = combined_text.lower()
        
        for category, terms in term_categories.items():
            found = []
            for term in terms:
                if term.lower() in combined_text:
                    found.append(term)
            
            if found:
                found_terms[category] = found
        
        return found_terms
    
    def _extract_host(self, found_terms: Dict[str, List[str]]) -> str:
        """Extract host information from found terms."""
        if "host" in found_terms and found_terms["host"]:
            return found_terms["host"][0]
        return ""
    
    def _extract_body_site(self, found_terms: Dict[str, List[str]]) -> str:
        """Extract body site information from found terms."""
        if "body site" in found_terms and found_terms["body site"]:
            return found_terms["body site"][0]
        return ""
    
    def _extract_condition(self, found_terms: Dict[str, List[str]]) -> str:
        """Extract condition information from found terms."""
        if "condition" in found_terms and found_terms["condition"]:
            return found_terms["condition"][0]
        return ""
    
    def _extract_sequencing_type(self, found_terms: Dict[str, List[str]]) -> str:
        """Extract sequencing type information from found terms."""
        if "sequencing type" in found_terms and found_terms["sequencing type"]:
            return found_terms["sequencing type"][0]
        return ""
    
    def _extract_sample_size(self, found_terms: Dict[str, List[str]], paper_content: Dict[str, str]) -> str:
        """Extract sample size information from found terms and paper content."""
        # First check if we have it in found terms
        if "sample size" in found_terms and found_terms["sample size"]:
            return found_terms["sample size"][0]
        
        # Otherwise try to extract from abstract
        import re
        abstract = paper_content.get("abstract", "")
        sample_size_patterns = [
            r'(\d+)\s+(?:subjects|participants|samples|patients)',
            r'cohort\s+of\s+(\d+)',
            r'n\s*=\s*(\d+)',
            r'sample\s+size\s*(?:of|was|:|=)\s*(\d+)'
        ]
        
        for pattern in sample_size_patterns:
            match = re.search(pattern, abstract, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return ""
    
    def _extract_taxa_level(self, found_terms: Dict[str, List[str]]) -> str:
        """Extract taxa level information from found terms."""
        if "taxa" in found_terms and found_terms["taxa"]:
            return found_terms["taxa"][0]
        return ""
    
    def _extract_statistical_method(self, found_terms: Dict[str, List[str]], text: str) -> str:
        """Extract statistical method information from found terms and response text."""
        if "statistical method" in found_terms and found_terms["statistical method"]:
            return found_terms["statistical method"][0]
        
        # Try to find statistical methods in the text
        statistical_methods = ["PERMANOVA", "ANOVA", "t-test", "Wilcoxon", "LEfSe", "DESeq2", "random forest"]
        text_lower = text.lower()
        
        for method in statistical_methods:
            if method.lower() in text_lower:
                return method
        
        return ""
    
    def _calculate_answer_confidence(self, answer: str, question: str) -> float:
        """Calculate confidence score for a question answer."""
        # Check for uncertainty markers
        uncertainty_markers = ["uncertain", "unclear", "not sure", "cannot determine", 
                              "don't know", "unable to", "not enough information"]
        
        if any(marker in answer.lower() for marker in uncertainty_markers):
            return 0.3
        
        # Check for confidence markers
        confidence_markers = ["clearly", "definitely", "certainly", "indeed", 
                             "without doubt", "conclusively"]
        
        if any(marker in answer.lower() for marker in confidence_markers):
            return 0.9
        
        # Default medium confidence
        return 0.6 