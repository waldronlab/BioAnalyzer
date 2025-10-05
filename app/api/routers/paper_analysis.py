"""
Paper analysis endpoints for BugSigDB curation analysis.
"""
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from typing import Dict, List, Optional
import json
import asyncio
import logging
from datetime import datetime
import pytz

from app.models.unified_qa import UnifiedQA
from app.services.data_retrieval import PubMedRetriever
from app.utils.text_processing import AdvancedTextProcessor
from app.utils.config import (
    NCBI_API_KEY, 
    GEMINI_API_KEY, 
    DEFAULT_MODEL,
    AVAILABLE_MODELS,
    FRONTEND_TIMEOUT,
    GEMINI_TIMEOUT,
    ANALYSIS_TIMEOUT,
    API_TIMEOUT
)
from app.utils.methods_scorer import MethodsScorer
from app.utils.field_validator import FieldExtractionEnhancer
from app.utils.performance_logger import perf_logger
from app.services.cache_manager import CacheManager
from app.api.models.api_models import Question, PaperAnalysisResult
from app.api.utils.api_utils import (
    extract_taxa,
    create_default_field_structure,
    validate_field_structure,
    create_comprehensive_fallback_analysis,
    generate_curation_summary,
    get_current_timestamp
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Paper Analysis"])

# Initialize services
unified_qa = UnifiedQA(use_gemini=True, gemini_api_key=GEMINI_API_KEY)
pubmed_retriever = PubMedRetriever(api_key=NCBI_API_KEY)
text_processor = AdvancedTextProcessor()
methods_scorer = MethodsScorer()
field_validator = FieldExtractionEnhancer()
cache_manager = CacheManager()


async def process_message(message):
    """Process incoming WebSocket message."""
    content = message.get('content', '')
    current_paper = message.get('currentPaper')
    
    try:
        if current_paper:
            # Analyze the paper first
            analysis_result = await analyze_paper_internal(current_paper)
            
            # Then answer the question
            response = await unified_qa.ask_question(
                question=content,
                context=analysis_result.get('full_text', ''),
                pmid=current_paper
            )
            
            return {
                'type': 'analysis_and_response',
                'analysis': analysis_result,
                'response': response
            }
        else:
            # Just answer the question without paper context
            response = await unified_qa.ask_question(question=content)
            return {
                'type': 'response_only',
                'response': response
            }
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return {
            'type': 'error',
            'error': str(e)
        }


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    **WebSocket endpoint for real-time communication.**
    
    This endpoint allows real-time communication with the AI system for:
    - Asking questions about papers
    - Getting analysis results
    - Interactive paper exploration
    
    **Connection Flow:**
    1. Client connects to `/ws`
    2. Send messages in JSON format: `{"content": "your question", "currentPaper": "PMID"}`
    3. Receive responses in JSON format
    4. Connection remains open for multiple exchanges
    
    **Message Format:**
    ```json
    {
        "content": "What is the host species in this paper?",
        "currentPaper": "12345678"
    }
    ```
    
    **Response Format:**
    ```json
    {
        "type": "analysis_and_response",
        "analysis": {...},
        "response": "The host species is Human..."
    }
    ```
    """
    await websocket.accept()
    logger.info("WebSocket connection established")
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Process message
            result = await process_message(message)
            
            # Send response
            await websocket.send_text(json.dumps(result))
            
    except WebSocketDisconnect:
        logger.info("WebSocket connection closed")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()


@router.post("/ask_question/{pmid}")
async def ask_question(pmid: str, question: Question):
    """
    **Answer questions about a specific paper using AI analysis.**
    
    This endpoint allows you to ask specific questions about a paper after it has been analyzed.
    The AI will use the paper's full text and analysis results to provide accurate answers.
    
    **Parameters:**
    - `pmid`: PubMed ID of the paper to ask about
    - `question`: The question object containing the question text
    
    **Example Request:**
    ```json
    {
        "question": "What is the host species studied in this paper?"
    }
    ```
    
    **Example Response:**
    ```json
    {
        "pmid": "12345678",
        "question": "What is the host species studied in this paper?",
        "answer": "The host species is Human (Homo sapiens).",
        "confidence": 0.95,
        "analysis_timestamp": "2024-01-15T10:30:00Z"
    }
    ```
    """
    try:
        # Get cached analysis or perform new analysis
        analysis_result = await analyze_paper_internal(pmid)
        
        if not analysis_result:
            raise HTTPException(status_code=404, detail=f"Paper {pmid} not found or could not be analyzed")
        
        # Ask the question using the analysis context
        response = await unified_qa.ask_question(
            question=question.question,
            context=analysis_result.get('full_text', ''),
            pmid=pmid
        )
        
        return {
            "pmid": pmid,
            "question": question.question,
            "answer": response.get('answer', 'No answer available'),
            "confidence": response.get('confidence', 0.0),
            "analysis_timestamp": get_current_timestamp()
        }
        
    except Exception as e:
        logger.error(f"Error asking question for PMID {pmid}: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing question: {str(e)}")


@router.get("/")
async def root():
    """Redirect to the frontend application."""
    return RedirectResponse(url="/static/index.html")


@router.get("/analyze/{pmid}")
async def analyze_paper(pmid: str, request: Request):
    """
    **Analyze a single paper for BugSigDB analysis.**
    
    This is the core endpoint that analyzes a paper for the 6 essential BugSigDB curation fields:
    1. Host Species
    2. Body Site  
    3. Condition
    4. Sequencing Type
    5. Taxa Level
    6. Sample Size
    
    **Parameters:**
    - `pmid`: PubMed ID of the paper to analyze
    
    **Response:**
    Returns a comprehensive analysis result with field status, confidence scores, and suggestions.
    """
    try:
        analysis_result = await analyze_paper_internal(pmid)
        
        if not analysis_result:
            raise HTTPException(status_code=404, detail=f"Paper {pmid} not found or could not be analyzed")
        
        # Return minimal payload: pmid + fields only
        return {
            "pmid": pmid,
            "fields": analysis_result.get("fields", {})
        }
        
    except HTTPException as e:
        # Preserve HTTPException (e.g., 404) instead of converting to 500
        raise e
    except Exception as e:
        logger.error(f"Error analyzing paper {pmid}: {e}")
        raise HTTPException(status_code=500, detail=f"Error analyzing paper: {str(e)}")


@router.get("/enhanced_analysis/{pmid}")
async def enhanced_analysis(pmid: str):
    """
    **Enhanced analysis endpoint for BugSigDB curation requirements.**
    
    This endpoint provides a more detailed analysis specifically tailored for BugSigDB curation.
    It includes additional validation, confidence scoring, and curation-specific insights.
    
    **Parameters:**
    - `pmid`: PubMed ID of the paper to analyze
    
    **Response:**
    Returns an enhanced analysis with additional curation-specific information.
    """
    try:
        # Get basic analysis first
        basic_analysis = await analyze_paper_internal(pmid)
        
        if not basic_analysis:
            raise HTTPException(status_code=404, detail=f"Paper {pmid} not found or could not be analyzed")
        
        # Enhance the analysis with additional validation
        enhanced_result = await enhance_analysis_result(basic_analysis, pmid)
        
        # Match frontend expectations: include title and wrap fields under 'enhanced_analysis'
        return {
            "pmid": pmid,
            "title": basic_analysis.get("title", ""),
            "enhanced_analysis": enhanced_result.get("fields", {})
        }
        
    except HTTPException as e:
        # Preserve explicit HTTP errors (like 404)
        raise e
    except Exception as e:
        logger.error(f"Error in enhanced analysis for PMID {pmid}: {e}")
        raise HTTPException(status_code=500, detail=f"Error in enhanced analysis: {str(e)}")


async def analyze_paper_internal(pmid: str) -> Optional[Dict]:
    """Internal method to analyze a paper."""
    try:
        # Check cache first
        cached_result = cache_manager.get_analysis_result(pmid)
        if cached_result:
            logger.info(f"Using cached analysis for PMID {pmid}")
            return cached_result
        
        # Minimal retrieval: abstract + full text (+ optional title)
        texts = await pubmed_retriever.get_texts_for_analysis_async(pmid)
        paper_data = {
            "title": texts.get('title', ''),
            "authors": [],
            "journal": '',
            "publication_date": '',
            "abstract": texts.get('abstract', ''),
            "full_text": texts.get('full_text', '')
        }
        
        # Process the paper
        start_time = datetime.now()
        
        # Extract and process text
        full_text = paper_data.get('full_text', '')
        abstract = paper_data.get('abstract', '')
        
        # Use both abstract and full text for analysis
        text_for_analysis = f"{abstract}\n\n{full_text}" if abstract else full_text
        
        if not text_for_analysis.strip():
            logger.warning(f"No text content available for PMID {pmid}; returning fallback analysis")
            field_analysis = create_comprehensive_fallback_analysis()
            processing_time = (datetime.now() - start_time).total_seconds()
            analysis_result = {
                "pmid": pmid,
                "title": paper_data.get('title', ''),
                "authors": paper_data.get('authors', []),
                "journal": paper_data.get('journal', ''),
                "publication_date": paper_data.get('publication_date', ''),
                "fields": field_analysis,
                "curation_summary": generate_curation_summary(field_analysis, []),
                "analysis_timestamp": get_current_timestamp(),
                "processing_time": processing_time,
                "model_used": DEFAULT_MODEL,
                "full_text": ""
            }
            cache_manager.store_analysis_result(pmid, analysis_result, paper_data)
            return analysis_result
        
        # Process text for analysis
        processed_text = text_processor.process_text(text_for_analysis)
        
        # Perform field analysis with timeout
        try:
            field_analysis = await asyncio.wait_for(
                perform_field_analysis(processed_text, pmid),
                timeout=ANALYSIS_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning(f"Field analysis timed out for PMID {pmid}, using fallback")
            field_analysis = create_comprehensive_fallback_analysis()
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Create analysis result
        analysis_result = {
            "pmid": pmid,
            "title": paper_data.get('title', ''),
            "authors": paper_data.get('authors', []),
            "journal": paper_data.get('journal', ''),
            "publication_date": paper_data.get('publication_date', ''),
            "fields": field_analysis,
            "curation_summary": generate_curation_summary(field_analysis, []),
            "analysis_timestamp": get_current_timestamp(),
            "processing_time": processing_time,
            "model_used": DEFAULT_MODEL,
            "full_text": text_for_analysis[:1000] + "..." if len(text_for_analysis) > 1000 else text_for_analysis
        }
        
        # Cache the result
        cache_manager.store_analysis_result(pmid, analysis_result, paper_data)
        
        return analysis_result
        
    except Exception as e:
        logger.error(f"Error in internal analysis for PMID {pmid}: {e}")
        return None


async def perform_field_analysis(text: str, pmid: str) -> Dict:
    """Perform analysis of the 6 essential fields."""
    try:
        # Use the unified QA system for field extraction
        field_questions = {
            "host_species": "What host species is being studied in this research?",
            "body_site": "What body site or anatomical location was sampled for microbiome analysis?",
            "condition": "What disease, treatment, or condition is being studied?",
            "sequencing_type": "What sequencing method or molecular technique was used?",
            "taxa_level": "What taxonomic level was analyzed (phylum, genus, species, etc.)?",
            "sample_size": "How many samples or participants were included in the study?"
        }
        
        field_results = {}
        
        for field, question in field_questions.items():
            try:
                # Create a prompt combining question and context
                prompt = f"Context: {text[:2000]}\n\nQuestion: {question}\n\nPlease provide a specific answer based on the context."
                
                # Use chat method to ask the question
                response = await unified_qa.chat(prompt)
                
                # Process the response
                field_results[field] = process_field_response(response, field)
                
            except Exception as e:
                logger.warning(f"Error analyzing field {field} for PMID {pmid}: {e}")
                field_results[field] = create_default_field_structure(field)
        
        return field_results
        
    except Exception as e:
        logger.error(f"Error in field analysis for PMID {pmid}: {e}")
        return create_comprehensive_fallback_analysis()


def process_field_response(response: Dict, field_name: str) -> Dict:
    """Process the response from the QA system for a specific field."""
    try:
        answer = response.get('answer', '')
        confidence = response.get('confidence', 0.0)
        
        if not answer or confidence < 0.3:
            return create_default_field_structure(field_name)
        
        # Determine status based on confidence and answer content
        if confidence >= 0.8:
            status = "PRESENT"
        elif confidence >= 0.5:
            status = "PARTIALLY_PRESENT"
        else:
            status = "ABSENT"
        
        return {
            "status": status,
            "value": answer if status != "ABSENT" else None,
            "confidence": confidence,
            "reason_if_missing": None if status != "ABSENT" else f"Low confidence ({confidence:.2f}) in field extraction",
            "suggestions": None if status != "ABSENT" else f"Look for more explicit mentions of {field_name.replace('_', ' ')}"
        }
        
    except Exception as e:
        logger.error(f"Error processing field response for {field_name}: {e}")
        return create_default_field_structure(field_name)


async def enhance_analysis_result(basic_analysis: Dict, pmid: str) -> Dict:
    """Enhance the analysis result with additional validation and insights."""
    try:
        # Add additional validation using the field validator
        enhanced_fields = {}
        
        for field_name, field_data in basic_analysis.get('fields', {}).items():
            # Use the field validator for additional validation
            validation_result = field_validator.validate_field(field_name, field_data)
            
            enhanced_fields[field_name] = {
                **field_data,
                "validation_score": validation_result.get('score', 0.0),
                "validation_notes": validation_result.get('notes', ''),
                "enhanced_confidence": min(field_data.get('confidence', 0.0) + 0.1, 1.0)
            }
        
        # Update the analysis result
        enhanced_analysis = {
            **basic_analysis,
            "fields": enhanced_fields,
            "enhancement_timestamp": get_current_timestamp(),
            "enhancement_version": "1.0"
        }
        
        return enhanced_analysis
        
    except Exception as e:
        logger.error(f"Error enhancing analysis for PMID {pmid}: {e}")
        return basic_analysis
