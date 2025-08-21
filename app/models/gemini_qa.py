import logging
from typing import Dict, List, Optional, Union
from pathlib import Path
from datetime import datetime
import pytz
import google.generativeai as genai
import os
import json

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
                "examples": [],
                # New factor-based analysis fields
                "general_factors_present": [],
                "human_animal_factors_present": [],
                "environmental_factors_present": [],
                "missing_critical_factors": [],
                "factor_based_score": 0.0
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
                elif "FACTOR-BASED ANALYSIS:" in line:
                    current_section = "factor_analysis"
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
                elif current_section == "factor_analysis":
                    if "General Factors Present:" in line:
                        factors_text = line.split(":", 1)[1] if ":" in line else ""
                        curation_analysis["general_factors_present"] = [f.strip() for f in factors_text.split(",") if f.strip()]
                    elif "Human/Animal Factors Present:" in line:
                        factors_text = line.split(":", 1)[1] if ":" in line else ""
                        curation_analysis["human_animal_factors_present"] = [f.strip() for f in factors_text.split(",") if f.strip()]
                    elif "Environmental Factors Present:" in line:
                        factors_text = line.split(":", 1)[1] if ":" in line else ""
                        curation_analysis["environmental_factors_present"] = [f.strip() for f in factors_text.split(",") if f.strip()]
                    elif "Missing Critical Factors:" in line:
                        factors_text = line.split(":", 1)[1] if ":" in line else ""
                        curation_analysis["missing_critical_factors"] = [f.strip() for f in factors_text.split(",") if f.strip()]
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
            
            # Calculate factor-based score
            total_factors = len(curation_analysis["general_factors_present"]) + \
                           len(curation_analysis["human_animal_factors_present"]) + \
                           len(curation_analysis["environmental_factors_present"])
            max_factors = 16  # 6 general + 5 human/animal + 5 environmental
            curation_analysis["factor_based_score"] = min(1.0, total_factors / max_factors)
            
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
                "examples": [],
                "general_factors_present": [],
                "human_animal_factors_present": [],
                "environmental_factors_present": [],
                "missing_critical_factors": [],
                "factor_based_score": 0.0
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
            prompt = """You are an expert scientific curator specializing in microbial signature analysis. Your task is to analyze this paper and provide a comprehensive assessment of its curation readiness based on the methods and experimental design.

## COMPREHENSIVE CURATION READINESS CRITERIA

### GENERAL FACTORS (Applicable to ALL Study Types)
A paper is READY FOR CURATION if it contains ALL of the following fundamental factors:

1. **Specific Microbial Taxa Identification**
   - Explicit mentions of microbial names (e.g., Nocardiaceae, Bacteroides, phyla, genera, species)
   - Prioritize the most granular level provided

2. **Differential Abundance/Compositional Changes**
   - Statements indicating significant increases, decreases, enrichment, depletion
   - Differences in overall community structure between groups/conditions

3. **Proper Experimental Design**
   - Clear description of study setup, experimental groups, control groups, and replication
   - Appropriate sample sizes and statistical power
   - Randomization and blinding where applicable

4. **Microbiota Characterization Methodology**
   - Details on how the microbial community was analyzed (e.g., 16S rRNA gene sequencing, metagenomics, metatranscriptomics)
   - Specific sequencing platforms and protocols
   - Bioinformatics pipeline details

5. **Quantitative Data/Statistical Significance**
   - P-values, fold-changes, relative abundances, diversity metrics, effect sizes, or other numerical data
   - Appropriate statistical tests for the experimental design
   - Multiple testing corrections where applicable

6. **Data Availability/Repository Information**
   - Mention of raw data deposited in public repositories (e.g., SRA, ENA) with accession numbers
   - Code availability and reproducibility information

### METHODS-SPECIFIC ASSESSMENT CRITERIA

7. **Sequencing and Molecular Methods**
   - DNA/RNA extraction protocols
   - Library preparation methods
   - Sequencing platform and parameters
   - Quality control measures
   - Bioinformatics analysis pipeline

8. **Statistical and Analytical Methods**
   - Diversity analysis (alpha/beta diversity metrics)
   - Differential abundance analysis tools
   - Ordination methods (PCA, PCoA, NMDS)
   - Machine learning approaches
   - Functional prediction methods

9. **Sample Collection and Processing**
   - Sample collection protocols
   - Storage and preservation methods
   - Sample size calculations
   - Replication and technical controls

10. **Experimental Design Quality**
    - Clear hypothesis and objectives
    - Appropriate control groups
    - Randomization and blinding
    - Longitudinal vs cross-sectional design
    - Intervention details (if applicable)

### SPECIFIC FACTORS FOR HUMAN/ANIMAL STUDIES
Additional criteria for host-associated studies:

11. **Host Health Outcome/Phenotype Associations**
    - Clear links between microbial changes and specific health conditions, diseases, physiological states
    - Examples: Hypertension, increased body weight, altered metabolic markers, inflammatory responses

12. **Host/Study Population Characteristics**
    - Detailed descriptors of host organisms or human participants
    - Examples: "Adult female offspring," "pregnant dams," "women with PCOS"

13. **Intervention/Exposure Details** (if applicable)
    - Specifics of experimental manipulation, treatment, or exposure
    - Examples: Dose, duration, route of administration

14. **Sample Type from Host**
    - Where the microbial sample was collected from the host
    - Examples: Fecal microbiota, gut microbiota, skin, oral, vaginal

15. **Proposed Molecular Mechanisms/Pathways**
    - Specific host or microbial molecules, genes, or metabolic pathways implicated
    - Examples: Short chain fatty acids (SCFAs), adipokines, specific enzymes

### SPECIFIC FACTORS FOR ENVIRONMENTAL STUDIES
Additional criteria for environmental studies:

16. **Environmental Context/Associated Factors**
    - Specific environmental factors or properties linked to microbial communities
    - Examples: Location/spatial data, physical/chemical parameters, source/material, anthropogenic influence

17. **Sample Type from Environment**
    - Specific matrix or material from which sample was collected
    - Examples: Dust, surface swab, soil core, water column, air filter

18. **Geospatial Data** (Highly Valued)
    - Exact locations, GPS coordinates, altitude, latitude/longitude if provided

19. **Study Duration/Seasonality**
    - If study spanned specific time period, multiple seasons, or before/after environmental event

20. **Associated Chemical/Physical Measurements**
    - Environmental parameters measured alongside microbial samples
    - Examples: Soil texture, water chemistry, air quality indices

### ENVIRONMENTAL STUDIES CRITERIA (Simplified Check)
A paper is READY FOR CURATION if it contains ANY of the following:
1. Indoor environment microbiome studies with human health implications
2. Built environment studies (hospitals, schools, transportation, public spaces)
3. Agricultural/food safety studies with microbial analysis
4. Industrial environment studies with health implications
5. Environmental studies with clear microbial signatures and health relevance

### NOT READY FOR CURATION Criteria
A paper is NOT READY FOR CURATION only if:
- It's purely a review article with no original research
- It contains NO microbial data or sequencing results
- It only mentions "microbiome" in passing without specific findings
- It lacks any quantitative or qualitative microbial data
- It's purely ecological without health implications
- It contains no quantitative microbial analysis

Please provide a detailed analysis in the following structured format:

**CURATION READINESS ASSESSMENT:**
[Start with a clear statement: "READY FOR CURATION" or "NOT READY FOR CURATION"]

**DETAILED EXPLANATION:**
[Provide a comprehensive explanation of why the paper is or isn't ready for curation, focusing on methods and experimental design]

**METHODS ASSESSMENT:**
- Sequencing Methods: [List specific sequencing methods used]
- Analytical Methods: [List statistical and bioinformatics methods]
- Experimental Design: [Assess quality of experimental design]
- Sample Processing: [Describe sample collection and processing methods]
- Data Quality: [Assess data quality and reproducibility]

**FACTOR-BASED ANALYSIS:**
- General Factors Present: [List which of the 6 general factors are present]
- Methods Factors Present: [List which of the 4 methods-specific factors are present]
- Human/Animal Factors Present: [List which of the 5 human/animal factors are present, if applicable]
- Environmental Factors Present: [List which of the 5 environmental factors are present, if applicable]
- Missing Critical Factors: [List any missing factors that prevent curation readiness]

**MICROBIAL SIGNATURE ANALYSIS:**
- Presence of microbial signatures: [Yes/No/Partial]
- Types of signatures found: [List specific types like "differential abundance", "community composition", "taxonomic identification"]
- Quality of signature data: [High/Medium/Low]
- Statistical significance: [Yes/No/Insufficient]

**CURATABLE CONTENT ASSESSMENT:**
- Required fields present: [List what's available - host, body site, condition, sequencing type, sample size]
- Missing required fields: [List what's missing, if any]
- Data completeness: [Complete/Partial/Insufficient]

**SPECIFIC REASONS FOR READINESS/NON-READINESS:**
[If NOT READY, explain exactly what's missing and provide examples of what would make it curatable]
[If READY, explain what makes it suitable for curation - be specific about the microbial signatures found]

**KEY FINDINGS:**
[List the main scientific findings related to microbial signatures]

**SUGGESTED TOPICS FOR FUTURE RESEARCH:**
[List potential follow-up studies or related research directions]

**CONFIDENCE LEVEL:**
[Provide a confidence score (0.0-1.0) with explanation]

**EXAMPLES AND EVIDENCE:**
[Provide specific examples from the text that support your assessment]

CRITICAL: If the paper contains ANY specific microbial taxa identification, abundance data, or microbial community analysis, it should be marked as READY FOR CURATION. This includes environmental studies with health implications. Only mark as NOT READY if the paper completely lacks microbial data or is purely a review article."""

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

    async def analyze_paper_enhanced(self, prompt: str) -> Dict[str, Union[str, float, List[str]]]:
        """
        Enhanced analysis method specifically for BugSigDB curation requirements.
        Focuses on structured extraction of key information with improved accuracy.
        """
        try:
            if not self.api_key:
                return {
                    "error": "No Gemini API key available",
                    "key_findings": "{}",
                    "confidence": 0.0
                }
            
            # Configure the model for structured output
            model = genai.GenerativeModel('gemini-1.5-pro-latest')
            
            # Enhanced structured prompt for better field extraction accuracy
            enhanced_structured_prompt = f"""
            You are a specialized AI assistant for BugSigDB curation with expertise in microbial signature analysis. Your task is to analyze scientific papers and extract specific information in a structured JSON format with high accuracy.

            {prompt}

            CRITICAL EXTRACTION GUIDELINES FOR ACCURACY:

            1. HOST SPECIES EXTRACTION:
               - Look for explicit mentions: "Human participants", "Mouse model", "Rat study", "Environmental samples"
               - Check study population descriptions, methods section, and abstract
               - For environmental studies, identify: "Built environment", "Indoor air", "Soil samples", "Water samples"
               - Be specific: "Human" not "mammal", "Mouse" not "rodent"

            2. BODY SITE EXTRACTION:
               - Human/Animal: Look for "fecal", "oral swab", "skin sample", "vaginal swab", "nasal swab"
               - Environmental: Look for "indoor surface", "restroom", "hospital room", "classroom", "office"
               - Check sample collection methods and study location descriptions
               - Be precise: "Gut" not "digestive system", "Indoor air" not "air"

            3. CONDITION EXTRACTION:
               - Look for disease names: "IBD", "Obesity", "Diabetes", "Cancer"
               - Check experimental conditions: "Antibiotic treatment", "Diet intervention", "Seasonal changes"
               - Identify comparative studies: "Men vs women", "Healthy vs diseased", "Before vs after"
               - Be specific: "Type 2 Diabetes" not "diabetes", "Crohn's disease" not "IBD"

            4. SEQUENCING TYPE EXTRACTION:
               - Look for specific methods: "16S rRNA gene sequencing", "V4 region amplification"
               - Check for platforms: "Illumina MiSeq", "Next-generation sequencing"
               - Identify techniques: "Shotgun metagenomics", "Amplicon sequencing"
               - Be precise: "16S rRNA" not "sequencing", "Metagenomics" not "genomics"

            5. TAXA LEVEL EXTRACTION:
               - Look for taxonomic classifications: "Phylum Proteobacteria", "Genus Bacteroides"
               - Check for specific names: "E. coli", "B. fragilis", "Lactobacillus spp."
               - Identify analysis levels: "Phylum level", "Genus level", "Species level"
               - Be specific: "Bacteroides fragilis" not "Bacteroides", "Proteobacteria phylum" not "bacteria"

            6. SAMPLE SIZE EXTRACTION:
               - Look for numbers: "n=50 participants", "100 samples", "Three time points"
               - Check study design: "Multiple floors sampled", "Longitudinal study with 6 visits"
               - Identify sample counts: "48 fecal samples", "24 oral swabs"
               - Be precise: "n=50" not "multiple samples", "100 samples" not "large sample size"

            CONFIDENCE SCORING GUIDELINES:
            - PRESENT (0.8-1.0): Information is explicitly stated and clear
            - PARTIALLY_PRESENT (0.4-0.7): Information is implied or partially described
            - ABSENT (0.0): Information is completely missing or unclear

            JSON RESPONSE REQUIREMENTS:
            - Return ONLY valid JSON without any explanatory text
            - Ensure all field names match exactly: "host_species", "body_site", "condition", "sequencing_type", "taxa_level", "sample_size"
            - Each field must have the exact structure specified in the prompt
            - Use proper JSON syntax with double quotes for strings
            - Include all required sub-fields for each main field

            IMPORTANT: You must respond with ONLY valid JSON. Do not include any explanatory text before or after the JSON. The response should be parseable by json.loads().

            Focus on accuracy and provide confidence scores based on how clearly the information is stated in the text.
            """
            
            # Generate response with enhanced prompt
            response = model.generate_content(enhanced_structured_prompt)
            
            if not response or not response.text:
                return {
                    "error": "No response generated",
                    "key_findings": "{}",
                    "confidence": 0.0
                }
            
            # Clean the response text to extract just the JSON
            response_text = response.text.strip()
            
            # Try to find JSON in the response with improved extraction
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
            else:
                json_text = response_text
            
            # Validate and clean JSON structure
            try:
                # First attempt to parse the JSON
                parsed_json = json.loads(json_text)
                
                # Validate and normalize the structure
                validated_json = self._validate_and_normalize_json(parsed_json)
                
                # Calculate enhanced confidence
                confidence = self._calculate_enhanced_confidence(validated_json)
                
                return {
                    "key_findings": json.dumps(validated_json, indent=2),
                    "confidence": confidence,
                    "status": "success"
                }
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON response: {e}")
                logger.warning(f"Raw response: {response_text[:500]}...")
                
                # Return a structured fallback with proper field structure
                fallback_json = self._create_fallback_json()
                
                return {
                    "key_findings": json.dumps(fallback_json, indent=2),
                    "confidence": 0.0,
                    "status": "fallback",
                    "error": f"JSON parsing failed: {str(e)}"
                }
                
        except Exception as e:
            logger.error(f"Error in enhanced analysis: {str(e)}")
            return {
                "error": str(e),
                "key_findings": "{}",
                "confidence": 0.0,
                "status": "error"
            }

    def _validate_and_normalize_json(self, parsed_json: Dict) -> Dict:
        """
        Validate and normalize the JSON structure to ensure all required fields are present.
        """
        # Define the required field structure
        required_fields = {
            "host_species": {
                "primary": "Unknown",
                "confidence": 0.0,
                "status": "ABSENT",
                "reason_if_missing": "Field not found in analysis",
                "suggestions_for_curation": "Review paper for host species information"
            },
            "body_site": {
                "site": "Unknown",
                "confidence": 0.0,
                "status": "ABSENT",
                "reason_if_missing": "Field not found in analysis",
                "suggestions_for_curation": "Review paper for body site information"
            },
            "condition": {
                "description": "Unknown",
                "confidence": 0.0,
                "status": "ABSENT",
                "reason_if_missing": "Field not found in analysis",
                "suggestions_for_curation": "Review paper for condition information"
            },
            "sequencing_type": {
                "method": "Unknown",
                "confidence": 0.0,
                "status": "ABSENT",
                "reason_if_missing": "Field not found in analysis",
                "suggestions_for_curation": "Review paper for sequencing method information"
            },
            "taxa_level": {
                "level": "Unknown",
                "confidence": 0.0,
                "status": "ABSENT",
                "reason_if_missing": "Field not found in analysis",
                "suggestions_for_curation": "Review paper for taxonomic level information"
            },
            "sample_size": {
                "size": "Unknown",
                "confidence": 0.0,
                "status": "ABSENT",
                "reason_if_missing": "Field not found in analysis",
                "suggestions_for_curation": "Review paper for sample size information"
            }
        }
        
        # Ensure all required fields exist with proper structure
        for field_name, default_structure in required_fields.items():
            if field_name not in parsed_json:
                parsed_json[field_name] = default_structure.copy()
            else:
                # Ensure the field has the required structure
                field_data = parsed_json[field_name]
                if not isinstance(field_data, dict):
                    parsed_json[field_name] = default_structure.copy()
                else:
                    # Merge with default structure to ensure all required keys exist
                    for key, default_value in default_structure.items():
                        if key not in field_data:
                            field_data[key] = default_value
        
        # Add curation readiness assessment
        curation_ready = all(
            parsed_json.get(field, {}).get("status") == "PRESENT" 
            for field in required_fields.keys()
        )
        
        # Add missing fields list
        missing_fields = [
            field for field in required_fields.keys()
            if parsed_json.get(field, {}).get("status") != "PRESENT"
        ]
        
        # Add summary fields
        parsed_json["curation_ready"] = curation_ready
        parsed_json["missing_fields"] = missing_fields
        parsed_json["curation_preparation_summary"] = self._generate_curation_summary(parsed_json, missing_fields)
        
        return parsed_json

    def _create_fallback_json(self) -> Dict:
        """
        Create a properly structured fallback JSON when parsing fails.
        """
        return {
            "host_species": {
                "primary": "Unknown",
                "confidence": 0.0,
                "status": "ABSENT",
                "reason_if_missing": "Analysis failed - re-run required",
                "suggestions_for_curation": "Re-run analysis with corrected prompt"
            },
            "body_site": {
                "site": "Unknown",
                "confidence": 0.0,
                "status": "ABSENT",
                "reason_if_missing": "Analysis failed - re-run required",
                "suggestions_for_curation": "Re-run analysis with corrected prompt"
            },
            "condition": {
                "description": "Unknown",
                "confidence": 0.0,
                "status": "ABSENT",
                "reason_if_missing": "Analysis failed - re-run required",
                "suggestions_for_curation": "Re-run analysis with corrected prompt"
            },
            "sequencing_type": {
                "method": "Unknown",
                "confidence": 0.0,
                "status": "ABSENT",
                "reason_if_missing": "Analysis failed - re-run required",
                "suggestions_for_curation": "Re-run analysis with corrected prompt"
            },
            "taxa_level": {
                "level": "Unknown",
                "confidence": 0.0,
                "status": "ABSENT",
                "reason_if_missing": "Analysis failed - re-run required",
                "suggestions_for_curation": "Re-run analysis with corrected prompt"
            },
            "sample_size": {
                "size": "Unknown",
                "confidence": 0.0,
                "status": "ABSENT",
                "reason_if_missing": "Analysis failed - re-run required",
                "suggestions_for_curation": "Re-run analysis with corrected prompt"
            },
            "curation_ready": False,
            "missing_fields": ["host_species", "body_site", "condition", "sequencing_type", "taxa_level", "sample_size"],
            "curation_preparation_summary": "Analysis failed - re-run required"
        }

    def _calculate_enhanced_confidence(self, validated_json: Dict) -> float:
        """
        Calculate enhanced confidence based on the quality of extracted information.
        """
        try:
            confidence_scores = []
            
            # Check each field for quality indicators
            for field_name, field_data in validated_json.items():
                if field_name in ["curation_ready", "missing_fields", "curation_preparation_summary"]:
                    continue
                    
                if not isinstance(field_data, dict):
                    continue
                
                # Get field status and confidence
                status = field_data.get("status", "ABSENT")
                field_confidence = field_data.get("confidence", 0.0)
                
                # Score based on status
                if status == "PRESENT":
                    # Boost confidence if the field has meaningful content
                    content_key = self._get_content_key_for_field(field_name)
                    content_value = field_data.get(content_key, "")
                    
                    if content_value and content_value.lower() not in ["unknown", "not specified", ""]:
                        confidence_scores.append(min(1.0, field_confidence + 0.1))
                    else:
                        confidence_scores.append(field_confidence)
                        
                elif status == "PARTIALLY_PRESENT":
                    confidence_scores.append(field_confidence)
                else:  # ABSENT
                    confidence_scores.append(0.0)
            
            if not confidence_scores:
                return 0.0
            
            # Calculate weighted average (give more weight to PRESENT fields)
            weighted_scores = []
            for score in confidence_scores:
                if score >= 0.8:  # PRESENT fields
                    weighted_scores.append(score * 1.2)
                else:
                    weighted_scores.append(score)
            
            final_confidence = sum(weighted_scores) / len(weighted_scores)
            return min(1.0, final_confidence)
            
        except Exception as e:
            logger.warning(f"Error calculating enhanced confidence: {str(e)}")
            return 0.5

    def _get_content_key_for_field(self, field_name: str) -> str:
        """
        Get the appropriate content key for a given field.
        """
        content_keys = {
            "host_species": "primary",
            "body_site": "site",
            "condition": "description",
            "sequencing_type": "method",
            "taxa_level": "level",
            "sample_size": "size"
        }
        return content_keys.get(field_name, "value")

    def _generate_curation_summary(self, parsed_json: Dict, missing_fields: List[str]) -> str:
        """
        Generate a summary of what's needed for curation.
        """
        if not missing_fields:
            return "All required fields are present. Paper is ready for curation."
        
        if len(missing_fields) == 1:
            return f"Missing 1 field: {missing_fields[0]}. Review paper for this information."
        elif len(missing_fields) <= 3:
            return f"Missing {len(missing_fields)} fields: {', '.join(missing_fields)}. Paper needs additional review."
        else:
            return f"Missing {len(missing_fields)} fields: {', '.join(missing_fields)}. Paper requires significant review before curation."

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