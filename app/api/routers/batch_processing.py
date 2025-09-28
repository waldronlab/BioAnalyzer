"""
Batch processing endpoints for multiple paper analysis.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Body
from typing import Dict, List, Optional
import csv
import asyncio
import logging
from datetime import datetime
import pytz
from pathlib import Path

from app.models.unified_qa import UnifiedQA
from app.services.data_retrieval import PubMedRetriever
from app.utils.text_processing import AdvancedTextProcessor
from app.utils.config import NCBI_API_KEY, DEFAULT_MODEL
from app.utils.performance_logger import perf_logger
from app.services.cache_manager import CacheManager
from app.api.models.api_models import BatchAnalysisRequest, EnhancedBatchAnalysisRequest
from app.api.utils.api_utils import get_current_timestamp

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Batch Processing"])

# Initialize services
unified_qa = UnifiedQA()
pubmed_retriever = PubMedRetriever(api_key=NCBI_API_KEY)
text_processor = AdvancedTextProcessor()
cache_manager = CacheManager()


@router.post("/upload_csv")
async def upload_csv(file: UploadFile = File(...)):
    """
    **Upload CSV or Excel file with PMIDs for batch processing.**
    
    This endpoint accepts CSV or Excel files containing PMIDs and processes them in batch.
    The file should have a column named 'pmid' or 'PMID' containing the PubMed IDs.
    
    **Supported formats:**
    - CSV files (.csv)
    - Excel files (.xlsx, .xls)
    
    **File format:**
    ```csv
    pmid,title,notes
    12345678,Paper Title 1,Additional notes
    87654321,Paper Title 2,Additional notes
    ```
    
    **Response:**
    Returns a summary of the upload and processing status.
    """
    try:
        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in ['.csv', '.xlsx', '.xls']:
            raise HTTPException(
                status_code=400, 
                detail="Unsupported file format. Please upload CSV or Excel files."
            )
        
        # Read file content
        content = await file.read()
        
        # Parse file based on extension
        pmids = []
        if file_extension == '.csv':
            pmids = parse_csv_content(content)
        else:
            pmids = parse_excel_content(content)
        
        if not pmids:
            raise HTTPException(status_code=400, detail="No valid PMIDs found in the file")
        
        # Store the file for batch processing
        file_path = f"data/uploads/{file.filename}"
        Path("data/uploads").mkdir(parents=True, exist_ok=True)
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Return upload summary
        return {
            "filename": file.filename,
            "pmids_found": len(pmids),
            "pmids": pmids[:10],  # Return first 10 for preview
            "file_path": file_path,
            "upload_timestamp": get_current_timestamp(),
            "status": "uploaded_successfully"
        }
        
    except Exception as e:
        logger.error(f"Error uploading CSV file: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@router.post("/analyze_batch")
async def analyze_batch(
    pmids: list = Body(...), 
    page: int = Query(1), 
    page_size: int = Query(20)
):
    """
    **Batch analysis endpoint for multiple papers.**
    
    This endpoint processes multiple papers in batch for BugSigDB curation analysis.
    It supports pagination to handle large batches efficiently.
    
    **Parameters:**
    - `pmids`: List of PubMed IDs to analyze
    - `page`: Page number for pagination (default: 1)
    - `page_size`: Number of papers per page (default: 20)
    
    **Example Request:**
    ```json
    {
        "pmids": ["12345678", "87654321", "11223344"]
    }
    ```
    
    **Response:**
    Returns paginated results with analysis status for each paper.
    """
    try:
        if not pmids:
            raise HTTPException(status_code=400, detail="No PMIDs provided")
        
        # Validate page parameters
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20
        
        # Calculate pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_pmids = pmids[start_idx:end_idx]
        
        # Process papers in parallel
        results = []
        errors = []
        
        # Use semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(5)
        
        async def analyze_single_paper(pmid: str):
            async with semaphore:
                try:
                    # Check cache first
                    cached_result = cache_manager.get_analysis(pmid)
                    if cached_result:
                        return {
                            "pmid": pmid,
                            "status": "success",
                            "cached": True,
                            "analysis": cached_result
                        }
                    
                    # Perform analysis
                    analysis_result = await analyze_paper_internal(pmid)
                    
                    if analysis_result:
                        # Cache the result
                        cache_manager.cache_analysis(pmid, analysis_result)
                        return {
                            "pmid": pmid,
                            "status": "success",
                            "cached": False,
                            "analysis": analysis_result
                        }
                    else:
                        return {
                            "pmid": pmid,
                            "status": "error",
                            "error": "Analysis failed"
                        }
                        
                except Exception as e:
                    logger.error(f"Error analyzing PMID {pmid}: {e}")
                    return {
                        "pmid": pmid,
                        "status": "error",
                        "error": str(e)
                    }
        
        # Process all papers
        tasks = [analyze_single_paper(pmid) for pmid in page_pmids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Separate successful and failed results
        successful_results = [r for r in results if isinstance(r, dict) and r.get("status") == "success"]
        failed_results = [r for r in results if isinstance(r, dict) and r.get("status") == "error"]
        
        # Calculate pagination info
        total_pages = (len(pmids) + page_size - 1) // page_size
        
        return {
            "total_pmids": len(pmids),
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "successful_analyses": len(successful_results),
            "failed_analyses": len(failed_results),
            "results": successful_results,
            "errors": failed_results,
            "processing_timestamp": get_current_timestamp()
        }
        
    except Exception as e:
        logger.error(f"Error in batch analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Error in batch analysis: {str(e)}")


@router.get("/list_pmids")
def list_pmids():
    """
    **Get list of all available PMIDs from the CSV database.**
    
    This endpoint returns a list of all PMIDs available in the local CSV database.
    This is useful for batch processing and validation.
    
    **Response:**
    Returns a list of PMIDs with optional metadata.
    """
    try:
        csv_path = 'data/full_dump.csv'
        if not Path(csv_path).exists():
            return {
                "pmids": [],
                "total_count": 0,
                "message": "CSV database not found"
            }
        
        pmids = []
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                pmid = row.get('pmid', '').strip()
                if pmid and pmid.isdigit():
                    pmids.append({
                        "pmid": pmid,
                        "title": row.get('title', ''),
                        "authors": row.get('authors', ''),
                        "journal": row.get('journal', ''),
                        "publication_date": row.get('publication_date', '')
                    })
        
        return {
            "pmids": pmids,
            "total_count": len(pmids),
            "database_path": csv_path,
            "last_updated": get_current_timestamp()
        }
        
    except Exception as e:
        logger.error(f"Error listing PMIDs: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing PMIDs: {str(e)}")


@router.post("/enhanced_analysis_batch")
async def enhanced_analysis_batch(
    pmids: List[str] = Body(...), 
    max_concurrent: int = Query(5)
):
    """
    **Enhanced batch analysis endpoint for multiple papers.**
    
    This endpoint provides enhanced batch analysis with additional validation
    and curation-specific insights for BugSigDB requirements.
    
    **Parameters:**
    - `pmids`: List of PubMed IDs to analyze
    - `max_concurrent`: Maximum number of concurrent analyses (default: 5)
    
    **Example Request:**
    ```json
    {
        "pmids": ["12345678", "87654321", "11223344"]
    }
    ```
    
    **Response:**
    Returns enhanced analysis results with additional validation and insights.
    """
    try:
        if not pmids:
            raise HTTPException(status_code=400, detail="No PMIDs provided")
        
        if max_concurrent < 1 or max_concurrent > 20:
            max_concurrent = 5
        
        # Process papers with enhanced analysis
        results = []
        errors = []
        
        # Use semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def enhanced_analyze_paper(pmid: str):
            async with semaphore:
                try:
                    # Check cache first
                    cached_result = cache_manager.get_analysis(pmid)
                    if cached_result:
                        # Enhance cached result
                        enhanced_result = await enhance_analysis_result(cached_result, pmid)
                        return {
                            "pmid": pmid,
                            "status": "success",
                            "cached": True,
                            "analysis": enhanced_result
                        }
                    
                    # Perform enhanced analysis
                    analysis_result = await analyze_paper_internal(pmid)
                    if analysis_result:
                        enhanced_result = await enhance_analysis_result(analysis_result, pmid)
                        # Cache the enhanced result
                        cache_manager.cache_analysis(pmid, enhanced_result)
                        return {
                            "pmid": pmid,
                            "status": "success",
                            "cached": False,
                            "analysis": enhanced_result
                        }
                    else:
                        return {
                            "pmid": pmid,
                            "status": "error",
                            "error": "Enhanced analysis failed"
                        }
                        
                except Exception as e:
                    logger.error(f"Error in enhanced analysis for PMID {pmid}: {e}")
                    return {
                        "pmid": pmid,
                        "status": "error",
                        "error": str(e)
                    }
        
        # Process all papers
        tasks = [enhanced_analyze_paper(pmid) for pmid in pmids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Separate successful and failed results
        successful_results = [r for r in results if isinstance(r, dict) and r.get("status") == "success"]
        failed_results = [r for r in results if isinstance(r, dict) and r.get("status") == "error"]
        
        return {
            "total_pmids": len(pmids),
            "successful_analyses": len(successful_results),
            "failed_analyses": len(failed_results),
            "max_concurrent": max_concurrent,
            "results": successful_results,
            "errors": failed_results,
            "processing_timestamp": get_current_timestamp(),
            "analysis_type": "enhanced"
        }
        
    except Exception as e:
        logger.error(f"Error in enhanced batch analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Error in enhanced batch analysis: {str(e)}")


def parse_csv_content(content: bytes) -> List[str]:
    """Parse CSV content and extract PMIDs."""
    try:
        import io
        text_content = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(text_content))
        
        pmids = []
        for row in csv_reader:
            pmid = row.get('pmid', '').strip() or row.get('PMID', '').strip()
            if pmid and pmid.isdigit():
                pmids.append(pmid)
        
        return pmids
        
    except Exception as e:
        logger.error(f"Error parsing CSV content: {e}")
        return []


def parse_excel_content(content: bytes) -> List[str]:
    """Parse Excel content and extract PMIDs."""
    try:
        import pandas as pd
        import io
        
        # Read Excel file
        df = pd.read_excel(io.BytesIO(content))
        
        # Look for PMID column
        pmid_columns = ['pmid', 'PMID', 'pmid_id', 'pubmed_id']
        pmid_column = None
        
        for col in pmid_columns:
            if col in df.columns:
                pmid_column = col
                break
        
        if not pmid_column:
            logger.warning("No PMID column found in Excel file")
            return []
        
        # Extract PMIDs
        pmids = []
        for pmid in df[pmid_column].dropna():
            pmid_str = str(pmid).strip()
            if pmid_str.isdigit():
                pmids.append(pmid_str)
        
        return pmids
        
    except Exception as e:
        logger.error(f"Error parsing Excel content: {e}")
        return []


async def analyze_paper_internal(pmid: str) -> Optional[Dict]:
    """Internal method to analyze a single paper."""
    try:
        # Retrieve paper data
        paper_data = await pubmed_retriever.get_paper_data(pmid)
        if not paper_data:
            return None
        
        # Process the paper
        start_time = datetime.now()
        
        # Extract and process text
        full_text = paper_data.get('full_text', '')
        if not full_text:
            return None
        
        # Process text for analysis
        processed_text = text_processor.process_text(full_text)
        
        # Perform field analysis
        field_analysis = await perform_field_analysis(processed_text, pmid)
        
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
            "model_used": DEFAULT_MODEL
        }
        
        return analysis_result
        
    except Exception as e:
        logger.error(f"Error in internal analysis for PMID {pmid}: {e}")
        return None


async def perform_field_analysis(text: str, pmid: str) -> Dict:
    """Perform analysis of the 6 essential fields."""
    try:
        from app.api.utils.api_utils import create_default_field_structure, generate_curation_summary
        
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
                response = await unified_qa.ask_question(
                    question=question,
                    context=text,
                    pmid=pmid
                )
                
                field_results[field] = process_field_response(response, field)
                
            except Exception as e:
                logger.warning(f"Error analyzing field {field} for PMID {pmid}: {e}")
                field_results[field] = create_default_field_structure(field)
        
        return field_results
        
    except Exception as e:
        logger.error(f"Error in field analysis for PMID {pmid}: {e}")
        from app.api.utils.api_utils import create_comprehensive_fallback_analysis
        return create_comprehensive_fallback_analysis()


def process_field_response(response: Dict, field_name: str) -> Dict:
    """Process the response from the QA system for a specific field."""
    try:
        from app.api.utils.api_utils import create_default_field_structure
        
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
        from app.api.utils.api_utils import create_default_field_structure
        return create_default_field_structure(field_name)


async def enhance_analysis_result(basic_analysis: Dict, pmid: str) -> Dict:
    """Enhance the analysis result with additional validation and insights."""
    try:
        from app.utils.field_validator import FieldExtractionEnhancer
        field_validator = FieldExtractionEnhancer()
        
        enhanced_fields = {}
        
        for field_name, field_data in basic_analysis.get('fields', {}).items():
            validation_result = field_validator.validate_field(field_name, field_data)
            
            enhanced_fields[field_name] = {
                **field_data,
                "validation_score": validation_result.get('score', 0.0),
                "validation_notes": validation_result.get('notes', ''),
                "enhanced_confidence": min(field_data.get('confidence', 0.0) + 0.1, 1.0)
            }
        
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
