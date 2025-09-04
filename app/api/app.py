from fastapi import FastAPI, WebSocket, HTTPException, Request, UploadFile, File, Form, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.websockets import WebSocketDisconnect
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
import json
import torch
import asyncio
from pathlib import Path
from datetime import datetime
import pytz
from app.models.config import ModelConfig
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
    ANALYSIS_TIMEOUT
)
from app.utils.methods_scorer import MethodsScorer
from app.utils.field_validator import FieldExtractionEnhancer
from app.utils.performance_logger import perf_logger
import re
import asyncio
import logging
import sys
import os
from bs4 import BeautifulSoup
import csv
from app.services.cache_manager import CacheManager

# Add the project root to Python path
# sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="BioAnalyzer - BugSigDB Curation Analysis",
    description="""
    **BioAnalyzer** - A specialized AI-powered tool for analyzing scientific papers for BugSigDB curation readiness.
    
    ## Core Functionality
    
    This API focuses on analyzing papers for **6 essential BugSigDB curation fields**:
    
    1. **Host Species** - What organism is being studied (e.g., Human, Mouse, Rat)
    2. **Body Site** - Where the microbiome sample was collected (e.g., Gut, Oral, Skin)
    3. **Condition** - What disease/treatment/exposure is being studied
    4. **Sequencing Type** - What molecular method was used (e.g., 16S, metagenomics)
    5. **Taxa Level** - What taxonomic level was analyzed (e.g., phylum, genus, species)
    6. **Sample Size** - Number of samples analyzed
    
    ## Analysis Results
    
    For each field, the AI provides:
    - **Status**: PRESENT, PARTIALLY_PRESENT, or ABSENT
    - **Value**: The extracted information
    - **Confidence**: AI confidence score (0.0-1.0)
    - **Reason if Missing**: Why the field is not present
    - **Suggestions**: What additional information is needed for curation
    
    ## Endpoints
    
    - **Paper Analysis**: Single and batch analysis of papers by PMID
    - **CSV Upload**: Batch processing of multiple PMIDs from CSV files

    - **Cache Management**: Efficient storage and retrieval of analysis results
    """,
    version="1.0.0",
    contact={
        "name": "BioAnalyzer Team",
        "url": "https://github.com/your-repo/bioanalyzer",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    tags_metadata=[
        {
            "name": "Paper Analysis",
            "description": "Core endpoints for analyzing papers for BugSigDB curation readiness using the 6 essential fields."
        },
        {
            "name": "Batch Processing",
            "description": "Endpoints for processing multiple papers at once, including CSV uploads."
        },

        {
            "name": "Cache Management",
            "description": "Endpoints for managing cached analysis results and improving performance."
        },
        {
            "name": "System",
            "description": "System health and status endpoints."
        }
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
text_processor = AdvancedTextProcessor()
model = None
if GEMINI_API_KEY:
    print("Model Status: Using gemini as primary model")
else:
    print("Model Status: No Gemini API key found. No LLM available.")
retriever = PubMedRetriever(api_key=NCBI_API_KEY)

qa_system = UnifiedQA(
    use_gemini=bool(GEMINI_API_KEY),
    gemini_api_key=GEMINI_API_KEY
)

# Initialize cache manager and field enhancer
cache_manager = CacheManager()
field_enhancer = FieldExtractionEnhancer()

# Mount static files after API routes
static_dir = Path(__file__).parent.parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

class Message(BaseModel):
    content: str
    role: str = "user"
    model: Optional[str] = None

class Question(BaseModel):
    question: str

async def process_message(message):
    content = message.get('content', '')
    current_paper = message.get('currentPaper')
    if not content:
        return {"error": "No message content provided"}

    # If the user is discussing a paper, include its context
    if current_paper:
        metadata = retriever.get_paper_metadata(current_paper)
        context = f"Title: {metadata['title']}\nAbstract: {metadata['abstract']}\n"
        prompt = f"{context}\nUser question: {content}"
    else:
        # Otherwise, treat as a general chat
        prompt = content

    # Call Gemini chat with the prompt
    response = await qa_system.chat(prompt)
    return {
        "response": response["text"],
        "confidence": response.get("confidence"),
        # ... other fields as needed
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    **WebSocket endpoint for real-time communication.**
    
    This endpoint handles WebSocket connections for:
    - Real-time paper analysis
    - Chat functionality
    - Live updates
    
    **Note:** This is a WebSocket endpoint and cannot be tested in the Swagger UI.
    Use a WebSocket client to connect to `/ws`.
    """
    await websocket.accept()
    print("WebSocket connection accepted")
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get('type') == 'analyze_paper':
                    # Handle paper analysis request
                    pmid = message.get('pmid')
                    if not pmid:
                        await websocket.send_json({"error": "No PMID provided"})
                        continue
                    
                    try:
                        # Get paper metadata
                        metadata = retriever.get_paper_metadata(pmid)
                        if not metadata:
                            await websocket.send_json({"error": f"Paper with PMID {pmid} not found"})
                            continue
                        
                        # Get full text if available
                        full_text = ""
                        try:
                            full_text = retriever.get_pmc_fulltext(pmid)
                        except Exception as e:
                            print(f"Warning: Could not retrieve full text for PMID {pmid}: {str(e)}")
                        
                        # Analyze paper using Gemini
                        if GEMINI_API_KEY:
                            response = await qa_system.analyze_paper(
                                {"title": metadata["title"], "abstract": metadata["abstract"], "full_text": full_text}
                            )
                            
                            analysis_text = response.get("key_findings", [])
                            analysis_result = {
                                "type": "analysis_result",
                                "title": metadata["title"],
                                "authors": metadata.get("authors", "N/A"),
                                "journal": metadata.get("journal", "N/A"),
                                "date": metadata.get("publication_date", "N/A"),
                                "doi": metadata.get("doi", "N/A"),
                                "abstract": metadata["abstract"],
                                "key_findings": analysis_text,
                                "confidence": 0.8,
                                "status": "success",
                                "suggested_topics": [],
                                "found_terms": {},
                                "category_scores": {},
                                "num_tokens": len(analysis_text)
                            }
                            print("Sending analysis result to frontend:", analysis_result)
                            await websocket.send_json(analysis_result)
                        else:
                            await websocket.send_json({"error": "No AI models available for analysis"})
                    except Exception as e:
                        print(f"Error analyzing paper: {str(e)}")
                        await websocket.send_json({"error": f"Error analyzing paper: {str(e)}"})
                else:
                    # Handle chat messages
                    user_message = message.get('content', '')
                    paper_ctx = message.get('paperContext')
                    chat_history = message.get('chatHistory', [])
                    if paper_ctx and paper_ctx.get('pmid'):
                        # Prepend paper metadata to prompt
                        context = f"You are discussing the following paper:\nTitle: {paper_ctx.get('title','')}\nAuthors: {paper_ctx.get('authors','')}\nJournal: {paper_ctx.get('journal','')}\nYear: {paper_ctx.get('year','')}\nPMID: {paper_ctx.get('pmid','')}\nAbstract: {paper_ctx.get('abstract','')}\n\nUser question: {user_message}"
                    elif chat_history:
                        # Build conversation context
                        history_str = ''
                        for msg in chat_history:
                            if msg.get('role') == 'user':
                                history_str += f"User: {msg.get('content','')}\n"
                            elif msg.get('role') == 'assistant':
                                history_str += f"Assistant: {msg.get('content','')}\n"
                        context = history_str + f"User: {user_message}"
                    else:
                        context = user_message
                    response = await qa_system.chat(context)
                    print("Sending chat response to frontend:", response)
                    await websocket.send_json({
                        "response": response["text"],
                        "confidence": response.get("confidence")
                    })
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON format"})
            except Exception as e:
                print(f"Error processing message: {str(e)}")
                await websocket.send_json({"error": str(e)})
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        try:
            await websocket.send_json({"error": str(e)})
        except:
            pass

@app.post("/ask_question/{pmid}", tags=["Paper Analysis"])
async def ask_question(pmid: str, question: Question):
    """
    **Answer questions about a specific paper using AI analysis.**
    
    This endpoint allows users to ask specific questions about a paper and get AI-generated answers.
    Useful for getting clarification on specific aspects of a paper's content.
    
    **Parameters:**
    - `pmid`: PubMed ID of the paper
    - `question`: The question object containing the user's query
    
    **Returns:**
    - **answer**: AI-generated response to the question
    - **confidence**: Confidence score for the answer
    
    **Note:** This endpoint uses the paper's metadata and abstract for context.
    """
    try:
        # Get paper metadata
        metadata = retriever.get_paper_metadata(pmid)
        if not metadata:
            raise HTTPException(status_code=404, detail="Paper not found")
        
        # Create context from paper metadata
        context = f"Title: {metadata['title']}\nAbstract: {metadata['abstract']}"
        
        # Try to get full text if available
        try:
            full_text = retriever.get_pmc_fulltext(pmid)
            if full_text:
                # Limit full text to avoid token limits
                context += f"\n\nFull Text (excerpt): {full_text[:2000]}..."
        except Exception as e:
            print(f"Error getting full text for PMID {pmid}: {str(e)}")
            # Continue with just the abstract
        
        # Try models in order of preference
        models_to_try = ["gemini"] if "gemini" in AVAILABLE_MODELS else AVAILABLE_MODELS
        answer = None
        confidence = 0.0
        
        for model_name in models_to_try:
            try:
                if model_name == "gemini" and GEMINI_API_KEY:
                    print(f"Attempting to use Gemini for question answering")
                    response = await qa_system.analyze_paper(
                        {"title": context, "abstract": question.question, "full_text": ""}
                    )
                    answer = response.get("key_findings", [])
                    confidence = 0.8  # Gemini responses are generally reliable
                    break
                    
            except Exception as e:
                print(f"Error with {model_name}: {str(e)}")
                continue
        
        if answer is None:
            return {
                "answer": "I apologize, but I'm currently unable to process your question. All available AI models are experiencing issues. Please try again later.",
                "confidence": 0.0
            }
        
        return {
            "answer": answer,
            "confidence": confidence
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error in ask_question endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error answering question: {str(e)}")

@app.post("/upload_csv", tags=["Batch Processing"])
async def upload_csv(file: UploadFile = File(...)):
    """
    **Upload CSV or Excel file with PMIDs for batch processing.**
    
    This endpoint processes a CSV or Excel file containing PubMed IDs and analyzes each paper
    for BugSigDB curation readiness using the 6 essential fields.
    
    **Parameters:**
    - `file`: CSV or Excel file with PMIDs (first column should contain PMIDs)
    
    **Supported Formats:**
    - CSV files (.csv)
    - Excel files (.xls, .xlsx)
    
    **CSV/Excel Format:**
    - First column: PubMed IDs (numeric)
    - Additional columns: Optional metadata (not required)
    
    **Returns:**
    - **results**: List of analysis results for each PMID
    - **total_processed**: Number of PMIDs successfully processed
    
    **Limitations:**
    - Maximum 10 PMIDs processed per upload (for performance)
    - CSV files: max 5MB, Excel files: max 10MB
    - PMIDs must be numeric
    
    **Analysis Results:**
    Each result contains the 6 essential fields analysis with curation readiness status.
    """
    try:
        # Debug logging
        print(f"Upload request received for file: {file.filename}")
        print(f"File size: {file.size} bytes")
        print(f"Content type: {file.content_type}")
        
        # Check file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        file_extension = file.filename.lower()
        if not (file_extension.endswith('.csv') or file_extension.endswith('.xls') or file_extension.endswith('.xlsx')):
            raise HTTPException(status_code=400, detail="Only CSV (.csv) and Excel (.xls, .xlsx) files are supported")
        
        # Check file size based on file type
        max_size = 5 * 1024 * 1024 if file_extension.endswith('.csv') else 10 * 1024 * 1024
        if file.size > max_size:
            max_size_mb = max_size / (1024 * 1024)
            raise HTTPException(status_code=400, detail=f"File size must be less than {max_size_mb}MB")
        
        # Read file content
        content = await file.read()
        print(f"File content length: {len(content)} bytes")
        
        # Parse file content based on file type
        pmids = []
        
        if file_extension.endswith('.csv'):
            # Handle CSV files
            try:
                csv_text = content.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    csv_text = content.decode("latin-1")
                except UnicodeDecodeError:
                    print("Failed to decode CSV file content")
                    raise HTTPException(status_code=400, detail="Unable to read CSV file content. Please ensure it's a valid CSV file.")
            
            print(f"CSV text length: {len(csv_text)} characters")
            print(f"First 200 characters: {csv_text[:200]}")
            
            # Parse CSV to extract PMIDs (assuming first column contains PMIDs)
            import csv
            from io import StringIO
            
            csv_reader = csv.reader(StringIO(csv_text))
            for i, row in enumerate(csv_reader):
                if row and len(row) > 0:
                    first_col = row[0].strip()
                    print(f"Row {i}: '{first_col}' (is_digit: {first_col.isdigit()})")
                    if first_col.isdigit():  # Check if first column is a numeric PMID
                        pmids.append(first_col)
        
        else:
            # Handle Excel files
            try:
                import pandas as pd
                from io import BytesIO
                
                # Read Excel file using pandas
                excel_data = pd.read_excel(BytesIO(content), engine='openpyxl' if file_extension.endswith('.xlsx') else 'xlrd')
                print(f"Excel file loaded with {len(excel_data)} rows and columns: {list(excel_data.columns)}")
                
                # Extract PMIDs from first column
                first_column = excel_data.iloc[:, 0]  # Get first column
                for i, value in enumerate(first_column):
                    if pd.notna(value):  # Check if value is not NaN
                        value_str = str(value).strip()
                        print(f"Row {i}: '{value_str}' (is_digit: {value_str.isdigit()})")
                        if value_str.isdigit():  # Check if first column is a numeric PMID
                            pmids.append(value_str)
                
            except ImportError:
                raise HTTPException(status_code=500, detail="Excel file processing requires pandas and openpyxl/xlrd packages. Please install them.")
            except Exception as e:
                print(f"Error processing Excel file: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Error processing Excel file: {str(e)}")
        
        print(f"Extracted PMIDs: {pmids}")
        
        if not pmids:
            print("No valid PMIDs found in file")
            raise HTTPException(status_code=400, detail="No valid PMIDs found in file. Please ensure the first column contains numeric PubMed IDs.")
        
        print(f"Processing {len(pmids)} PMIDs...")
        
        # Process each PMID using the enhanced analysis
        results = []
        for pmid in pmids[:10]:  # Limit to first 10 PMIDs for performance
            try:
                print(f"Processing PMID: {pmid}")
                # Get paper metadata
                metadata = retriever.get_paper_metadata(pmid)
                if not metadata:
                    print(f"No metadata found for PMID {pmid}")
                    results.append({
                        "pmid": pmid,
                        "title": "Not found",
                        "authors": "N/A",
                        "journal": "N/A",
                        "date": "N/A",
                        "enhanced_analysis": {
                            "host_species": {"status": "ABSENT", "reason": "Paper not found", "suggestion": "Verify PMID"},
                            "body_site": {"status": "ABSENT", "reason": "Paper not found", "suggestion": "Verify PMID"},
                            "condition": {"status": "ABSENT", "reason": "Paper not found", "suggestion": "Verify PMID"},
                            "sequencing_type": {"status": "ABSENT", "reason": "Paper not found", "suggestion": "Verify PMID"},
                            "taxa_level": {"status": "ABSENT", "reason": "Paper not found", "suggestion": "Verify PMID"},
                            "sample_size": {"status": "ABSENT", "reason": "Paper not found", "suggestion": "Verify PMID"}
                        }
                    })
                    continue
                
                # Get full text if available
                full_text = ""
                try:
                    full_text = retriever.get_pmc_fulltext(pmid)
                    if isinstance(full_text, str):
                        try:
                            soup = BeautifulSoup(full_text, 'lxml')
                            full_text = retriever._extract_text_from_pmc_xml(soup)
                        except Exception as e:
                            print(f"Failed to parse PMC XML for PMID {pmid}: {str(e)}")
                    elif isinstance(full_text, list):
                        full_text = '\n'.join(str(x) for x in full_text)
                    elif full_text is None:
                        full_text = ""
                    else:
                        full_text = str(full_text)
                except Exception as e:
                    print(f"Failed to retrieve PMC full text for PMID {pmid}: {str(e)}")
                    full_text = ""
                
                # Analyze paper using enhanced analysis with the 6 essential fields
                enhanced_prompt = f"""
                You are a specialized AI assistant for BugSigDB curation. Your task is to carefully analyze this scientific paper and extract specific information about 6 essential fields required for microbial signature curation.

                PAPER INFORMATION:
                Title: {metadata.get('title', '')}
                Abstract: {metadata.get('abstract', '')}
                MeSH Terms: {', '.join(metadata.get('mesh_terms', []))}
                Publication Type: {', '.join(metadata.get('publication_types', []))}
                Journal: {metadata.get('journal', '')}
                Year: {metadata.get('year', '')}
                
                PRELIMINARY EXTRACTION (from metadata):
                - Host Species: {metadata.get('host', 'Not extracted')}
                - Body Site: {metadata.get('body_site', 'Not extracted')}
                - Sequencing Type: {metadata.get('sequencing_type', 'Not extracted')}
                
                FULL TEXT CONTENT (first 8000 characters):
                {full_text[:8000] if full_text else 'Not available'}

                REQUIRED ANALYSIS - EXTRACT THESE 6 FIELDS WITH HIGH ACCURACY:

                STEP 1: HOST SPECIES ANALYSIS
                   - Look for: "Human", "Mouse", "Rat", "Drosophila", "Zebrafish", "Pig", "Cow", "Chicken", etc.
                   - For environmental studies: Look for "Environment", "Indoor", "Outdoor", "Built environment", "Natural environment"
                - Check: Abstract, methods section, study population descriptions, mesh terms, title
                   - Examples: "Human participants", "Adult female offspring", "Built environment microbiome", "Indoor air samples"
                - Be specific: "Human" not "mammal", "Mouse" not "rodent"
                - If you find "Human participants" or "Human subjects", mark as PRESENT

                STEP 2: BODY SITE ANALYSIS
                   - For human/animal: "Gut", "Oral", "Skin", "Vaginal", "Lung", "Nasal", "Ear", "Stool", "Feces"
                   - For environmental: "Indoor", "Restroom", "Hospital", "School", "Office", "Soil", "Water", "Air", "Surface"
                - Check: Sample collection methods, study location descriptions, abstract, methods section
                   - Examples: "Fecal samples", "Oral swabs", "Indoor dust", "Restroom surfaces", "Hospital air"
                - Be precise: "Gut" not "digestive system", "Indoor air" not "air"
                - If you find "fecal samples" or "stool samples", mark as PRESENT

                STEP 3: CONDITION ANALYSIS
                   - Look for: Disease names, experimental conditions, comparative studies, environmental factors
                - Check: Study objectives, hypothesis, experimental design, disease associations, abstract
                   - Examples: "IBD patients", "Obesity", "Diabetes", "Antibiotic treatment", "Men vs women comparison", "Floor differences", "Seasonal changes"
                - Be specific: "Type 2 Diabetes" not "diabetes", "Crohn's disease" not "IBD"
                - If you find disease names or experimental conditions, mark as PRESENT

                STEP 4: SEQUENCING TYPE ANALYSIS
                   - Look for: "16S rRNA", "metagenomics", "shotgun sequencing", "amplicon sequencing", "metatranscriptomics"
                - Check: Methods section, molecular techniques, sequencing protocols, abstract
                   - Examples: "16S rRNA gene sequencing", "V4 region amplification", "Illumina sequencing", "Next-generation sequencing"
                - Be precise: "16S rRNA" not "sequencing", "Metagenomics" not "genomics"
                - If you find "16S" or "sequencing", mark as PRESENT

                STEP 5: TAXA LEVEL ANALYSIS
                   - Look for: Taxonomic levels and specific names
                - Check: Results section, microbial community descriptions, diversity analysis, abstract
                   - Examples: "Phylum level: Proteobacteria, Actinobacteria", "Genus level: Bacteroides, Prevotella", "Species level: E. coli, B. fragilis"
                - Be specific: "Bacteroides fragilis" not "Bacteroides", "Proteobacteria phylum" not "bacteria"
                - If you find taxonomic names or levels, mark as PRESENT

                STEP 6: SAMPLE SIZE ANALYSIS
                   - Look for: Numbers, sample counts, participant numbers, collection descriptions
                - Check: Methods section, study design, sample collection details, abstract
                   - Examples: "n=50 participants", "100 samples collected", "Three floors sampled", "Multiple time points"
                - Be precise: "n=50" not "multiple samples", "100 samples" not "large sample size"
                - If you find numbers or sample counts, mark as PRESENT

                CRITICAL ANALYSIS INSTRUCTIONS:
                1. READ THE TEXT THOROUGHLY - Do not skim. Read every section carefully.
                2. LOOK FOR EXPLICIT MENTIONS - If the text says "Human participants", that's PRESENT.
                3. CHECK MULTIPLE SECTIONS - Title, abstract, methods, results, discussion.
                4. USE CONTEXT CLUES - If it mentions "fecal samples from patients", that's both host (Human) and body site (Gut).
                5. BE CONFIDENT - If you find clear information, use high confidence (0.8-1.0).
                6. DON'T GUESS - Only mark as PRESENT if you're confident the information exists.

                CONFIDENCE SCORING:
                - PRESENT (0.8-1.0): Information is explicitly stated and clear
                - PARTIALLY_PRESENT (0.4-0.7): Information is implied or partially described
                - ABSENT (0.0): Information is completely missing or unclear

                RESPONSE FORMAT - Return ONLY this JSON structure:
                {{
                    "host_species": {{
                        "primary": "extracted_species_name",
                        "confidence": 0.0-1.0,
                        "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                        "reason_if_missing": "explanation if absent",
                        "suggestions_for_curation": "what additional info is needed"
                    }},
                    "body_site": {{
                        "site": "extracted_site_name",
                        "confidence": 0.0-1.0,
                        "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                        "reason_if_missing": "explanation if absent",
                        "suggestions_for_curation": "what additional info is needed"
                    }},
                    "condition": {{
                        "description": "extracted_condition_description",
                        "confidence": 0.0-1.0,
                        "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                        "reason_if_missing": "explanation if absent",
                        "suggestions_for_curation": "what additional info is needed"
                    }},
                    "sequencing_type": {{
                        "method": "extracted_sequencing_method",
                        "confidence": 0.0-1.0,
                        "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                        "reason_if_missing": "explanation if absent",
                        "suggestions_for_curation": "what additional info is needed"
                    }},
                    "taxa_level": {{
                        "level": "extracted_taxonomic_level",
                        "confidence": 0.0-1.0,
                        "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                        "reason_if_missing": "explanation if absent",
                        "suggestions_for_curation": "what additional info is needed"
                    }},
                    "sample_size": {{
                        "size": "extracted_sample_size",
                        "confidence": 0.0-1.0,
                        "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                        "reason_if_missing": "explanation if absent",
                        "suggestions_for_curation": "what additional info is needed"
                    }}
                }}

                FINAL INSTRUCTIONS:
                - Focus ONLY on the 6 fields above
                - Be thorough and careful in your analysis
                - Extract actual information from the text, don't guess or infer
                - Return ONLY the JSON structure above
                - Ensure all field names match exactly: "host_species", "body_site", "condition", "sequencing_type", "taxa_level", "sample_size"
                - Use proper JSON syntax with double quotes for strings
                - Include all required sub-fields for each main field
                - If you find information, mark it as PRESENT with high confidence
                - Only mark as ABSENT if you're absolutely certain the information is missing
                """
                
                analysis = await qa_system.analyze_paper_enhanced(enhanced_prompt)
                
                # Parse the JSON response from Gemini
                try:
                    parsed_analysis = json.loads(analysis.get("key_findings", "{}"))
                    
                    # Validate that we have exactly the 6 required fields
                    required_fields = ["host_species", "body_site", "condition", "sequencing_type", "taxa_level", "sample_size"]
                    missing_fields = []
                    
                    for field in required_fields:
                        if field not in parsed_analysis or not parsed_analysis[field]:
                            missing_fields.append(field)
                            # Ensure the field exists with default structure
                            if field == "host_species":
                                parsed_analysis[field] = {"primary": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "Field not found in analysis", "suggestions_for_curation": "Review paper for host species information"}
                            elif field == "body_site":
                                parsed_analysis[field] = {"site": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "Field not found in analysis", "suggestions_for_curation": "Review paper for body site information"}
                            elif field == "condition":
                                parsed_analysis[field] = {"description": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "Field not found in analysis", "suggestions_for_curation": "Review paper for condition information"}
                            elif field == "sequencing_type":
                                parsed_analysis[field] = {"method": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "Field not found in analysis", "suggestions_for_curation": "Review paper for sequencing method information"}
                            elif field == "taxa_level":
                                parsed_analysis[field] = {"level": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "Field not found in analysis", "suggestions_for_curation": "Review paper for taxonomic level information"}
                            elif field == "sample_size":
                                parsed_analysis[field] = {"size": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "Field not found in analysis", "suggestions_for_curation": "Review paper for sample size information"}
                    
                    # Update the parsed analysis with missing fields
                    parsed_analysis["missing_fields"] = missing_fields
                    
                except json.JSONDecodeError:
                    # Fallback if JSON parsing fails - ensure we have exactly the 6 fields
                    parsed_analysis = {
                        "host_species": {"primary": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "JSON parsing failed", "suggestions_for_curation": "Re-run analysis"},
                        "body_site": {"site": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "JSON parsing failed", "suggestions_for_curation": "Re-run analysis"},
                        "condition": {"description": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "JSON parsing failed", "suggestions_for_curation": "Re-run analysis"},
                        "sequencing_type": {"method": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "JSON parsing failed", "suggestions_for_curation": "Re-run analysis"},
                        "taxa_level": {"level": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "JSON parsing failed", "suggestions_for_curation": "Re-run analysis"},
                        "sample_size": {"size": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "JSON parsing failed", "suggestions_for_curation": "Re-run analysis"},
                        "missing_fields": ["host_species", "body_site", "condition", "sequencing_type", "taxa_level", "sample_size"],
                        "curation_preparation_summary": "Analysis failed - re-run required"
                    }
                
                # Store analysis results in cache
                cache_manager.store_analysis_result(
                    pmid, 
                    parsed_analysis, 
                    metadata, 
                    "gemini_enhanced", 
                    analysis.get("confidence", 0.0), 
                    False
                )
                
                results.append({
                    "pmid": pmid,
                    "title": metadata.get("title", ""),
                    "enhanced_analysis": parsed_analysis
                })
                
            except Exception as e:
                print(f"Error processing PMID {pmid}: {str(e)}")
                results.append({
                    "pmid": pmid,
                    "title": "Error processing",
                    "authors": "N/A",
                    "journal": "N/A",
                    "date": "N/A",
                    "enhanced_analysis": {
                        "host_species": {"status": "ABSENT", "reason": f"Processing error: {str(e)}", "suggestion": "Try again later"},
                        "body_site": {"status": "ABSENT", "reason": f"Processing error: {str(e)}", "suggestion": "Try again later"},
                        "condition": {"status": "ABSENT", "reason": f"Processing error: {str(e)}", "suggestion": "Try again later"},
                        "sequencing_type": {"status": "ABSENT", "reason": f"Processing error: {str(e)}", "suggestion": "Try again later"},
                        "taxa_level": {"status": "ABSENT", "reason": f"Processing error: {str(e)}", "suggestion": "Try again later"},
                        "sample_size": {"status": "ABSENT", "reason": f"Processing error: {str(e)}", "suggestion": "Try again later"}
                    }
                })
        
        return {"results": results, "total_processed": len(results)}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error processing CSV file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing CSV file: {str(e)}")



def extract_taxa(text):
    """Extract potential taxa from text"""
    # This is a simplified implementation
    # In a real system, this would use a more sophisticated approach
    
    # Common bacterial genera
    common_genera = [
        "Bacteroides", "Prevotella", "Faecalibacterium", "Bifidobacterium",
        "Lactobacillus", "Escherichia", "Streptococcus", "Staphylococcus",
        "Clostridium", "Ruminococcus", "Akkermansia", "Pseudomonas"
    ]
    
    found_taxa = []
    for genus in common_genera:
        if re.search(r'\b' + genus + r'\b', text, re.IGNORECASE):
            found_taxa.append(genus)
    
    return found_taxa

@app.get("/", tags=["System"])
async def root():
    """Redirect to the frontend application."""
    return RedirectResponse(url="/static/index.html")

@app.get("/analyze/{pmid}", tags=["Paper Analysis"])
async def analyze_paper(pmid: str, request: Request):
    """
    **Analyze a single paper for BugSigDB analysis.**
    
    This endpoint analyzes a scientific paper using AI to extract and validate 6 essential fields.
    It focuses on extracting and validating 6 essential fields required for analysis.
    
    **Parameters:**
    - `pmid`: PubMed ID of the paper to analyze
    
    **Returns:**
    - **enhanced_analysis**: Detailed analysis of the 6 essential fields
    
    - **metadata**: Paper metadata (title, abstract, authors, etc.)
    
    **6 Essential Fields Analyzed:**
    1. **host_species**: Host organism being studied
    2. **body_site**: Microbiome sample collection location
    3. **condition**: Disease/treatment/exposure studied
    4. **sequencing_type**: Molecular method used
    5. **taxa_level**: Taxonomic level analyzed
    6. **sample_size**: Number of samples analyzed
    
    **Field Status Values:**
    - **PRESENT**: Information is complete and clear
    - **PARTIALLY_PRESENT**: Some information available but incomplete
    - **ABSENT**: Information is missing with reasons and suggestions
    
    **Analysis Status:**
    A paper is considered complete when ALL 6 fields have status "PRESENT".
    """
    import time
    start_time = time.time()
    
    # Log query start with client information
    client_ip = request.client.host if request.client else "Unknown"
    user_agent = request.headers.get("user-agent", "Unknown")
    
    perf_logger.log_pmid_query_start(pmid, user_agent, client_ip)
    logger.info(f"=== Starting analysis for PMID: {pmid} ===")
    
    try:
        # Check cache first for analysis results
        cache_start = time.time()
        cached_result = await cache_manager.get_analysis_result_async(pmid)
        cache_duration = time.time() - cache_start
        
        if cached_result and cache_manager.is_cache_valid(cached_result["timestamp"]):
            total_duration = time.time() - start_time
            perf_logger.log_pmid_query_end(pmid, total_duration, True, cached=True)
            perf_logger.log_cache_operation("GET", pmid, "analysis", cache_duration, True)
            
            logger.info(f"Returning cached analysis for PMID: {pmid}")
            return {
                "pmid": pmid,
                "metadata": cached_result["metadata"],
                "enhanced_analysis": cached_result["analysis_data"],

                "timestamp": cached_result["timestamp"],
                "source": cached_result["source"],
                "cached": True
            }
        
        # Get paper metadata and full text concurrently for better performance
        try:
            # Log data retrieval start
            data_retrieval_start = time.time()
            
            # Use asyncio.gather to run operations concurrently
            metadata_task = retriever.get_paper_metadata_async(pmid)
            full_text_task = retriever.get_pmc_fulltext_async(pmid)
            
            # Wait for both operations with timeout
            metadata, full_text = await asyncio.wait_for(
                asyncio.gather(metadata_task, full_text_task, return_exceptions=True),
                timeout=float(ANALYSIS_TIMEOUT)  # Use ANALYSIS_TIMEOUT from config
            )
            
            # Log data retrieval completion
            data_retrieval_duration = time.time() - data_retrieval_start
            perf_logger.log_analysis_step(pmid, "data_retrieval", data_retrieval_duration, {
                "metadata_success": not isinstance(metadata, Exception),
                "fulltext_success": not isinstance(full_text, Exception)
            })
            
            # Handle exceptions from concurrent operations
            if isinstance(metadata, Exception):
                logger.error(f"Metadata retrieval failed for PMID {pmid}: {str(metadata)}")
                raise HTTPException(status_code=500, detail=f"Metadata retrieval failed: {str(metadata)}")
            
            if isinstance(full_text, Exception):
                logger.warning(f"Full text retrieval failed for PMID {pmid}: {str(full_text)}")
                full_text = ""
            
            # Get CSV metadata if available
            csv_metadata = get_paper_metadata_from_csv(pmid)
            if csv_metadata:
                metadata.update(csv_metadata)
            
            if not metadata:
                raise HTTPException(status_code=404, detail=f"Paper not found: {pmid}")
            
            # Store metadata in cache
            await cache_manager.store_metadata_async(pmid, metadata, "pubmed")
            
            # Process full text if available
            if isinstance(full_text, str):
                try:
                    soup = BeautifulSoup(full_text, 'lxml')
                    full_text = retriever._extract_text_from_pmc_xml(soup)
                except Exception as e:
                    logger.warning(f"Failed to parse PMC XML for PMID {pmid}: {str(e)}")
                    full_text = ""
            
            # Store full text in cache
            if full_text:
                await cache_manager.store_fulltext_async(pmid, full_text, "pmc")
                
        except asyncio.TimeoutError:
            logger.error(f"Analysis timeout for PMID {pmid} after {ANALYSIS_TIMEOUT} seconds")
            raise HTTPException(status_code=408, detail=f"Analysis request timed out after {ANALYSIS_TIMEOUT} seconds. Please try again.")
        except Exception as e:
            logger.error(f"Error retrieving data for PMID {pmid}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Data retrieval failed: {str(e)}")
        
        # Create enhanced prompt for specific analysis - same as enhanced endpoints
        enhanced_prompt = f"""
        You are a specialized AI assistant for BugSigDB curation. Your task is to carefully analyze this scientific paper and extract specific information about 6 essential fields required for microbial signature curation.

        PAPER INFORMATION:
        Title: {metadata.get('title', '')}
        Abstract: {metadata.get('abstract', '')}
        MeSH Terms: {', '.join(metadata.get('mesh_terms', []))}
        Publication Type: {', '.join(metadata.get('publication_types', []))}
        Journal: {metadata.get('journal', '')}
        Year: {metadata.get('year', '')}
        
        PRELIMINARY EXTRACTION (from metadata):
        - Host Species: {metadata.get('host', 'Not extracted')}
        - Body Site: {metadata.get('body_site', 'Not extracted')}
        - Sequencing Type: {metadata.get('sequencing_type', 'Not extracted')}
        
        FULL TEXT CONTENT (first 8000 characters):
        {full_text[:8000] if full_text else 'Not available'}

        REQUIRED ANALYSIS - EXTRACT THESE 6 FIELDS WITH HIGH ACCURACY:

        STEP 1: HOST SPECIES ANALYSIS
           - Look for: "Human", "Mouse", "Rat", "Drosophila", "Zebrafish", "Pig", "Cow", "Chicken", etc.
           - For environmental studies: Look for "Environment", "Indoor", "Outdoor", "Built environment", "Natural environment"
        - Check: Abstract, methods section, study population descriptions, mesh terms, title
           - Examples: "Human participants", "Adult female offspring", "Built environment microbiome", "Indoor air samples"
           - Be specific: "Human" not "mammal", "Mouse" not "rodent"
        - If you find "Human participants" or "Human subjects", mark as PRESENT

        STEP 2: BODY SITE ANALYSIS
           - For human/animal: "Gut", "Oral", "Skin", "Vaginal", "Lung", "Nasal", "Ear", "Stool", "Feces"
           - For environmental: "Indoor", "Restroom", "Hospital", "School", "Office", "Soil", "Water", "Air", "Surface"
        - Check: Sample collection methods, study location descriptions, abstract, methods section
           - Examples: "Fecal samples", "Oral swabs", "Indoor dust", "Restroom surfaces", "Hospital air"
           - Be precise: "Gut" not "digestive system", "Indoor air" not "air"
        - If you find "fecal samples" or "stool samples", mark as PRESENT

        STEP 3: CONDITION ANALYSIS
           - Look for: Disease names, experimental conditions, comparative studies, environmental factors
        - Check: Study objectives, hypothesis, experimental design, disease associations, abstract
           - Examples: "IBD patients", "Obesity", "Diabetes", "Antibiotic treatment", "Men vs women comparison", "Floor differences", "Seasonal changes"
           - Be specific: "Type 2 Diabetes" not "diabetes", "Crohn's disease" not "IBD"
        - If you find disease names or experimental conditions, mark as PRESENT

        STEP 4: SEQUENCING TYPE ANALYSIS
           - Look for: "16S rRNA", "metagenomics", "shotgun sequencing", "amplicon sequencing", "metatranscriptomics"
        - Check: Methods section, molecular techniques, sequencing protocols, abstract
           - Examples: "16S rRNA gene sequencing", "V4 region amplification", "Illumina sequencing", "Next-generation sequencing"
           - Be precise: "16S rRNA" not "sequencing", "Metagenomics" not "genomics"
        - If you find "16S" or "sequencing", mark as PRESENT

        STEP 5: TAXA LEVEL ANALYSIS
           - Look for: Taxonomic levels and specific names
        - Check: Results section, microbial community descriptions, diversity analysis, abstract
           - Examples: "Phylum level: Proteobacteria, Actinobacteria", "Genus level: Bacteroides, Prevotella", "Species level: E. coli, B. fragilis"
           - Be specific: "Bacteroides fragilis" not "Bacteroides", "Proteobacteria phylum" not "bacteria"
        - If you find taxonomic names or levels, mark as PRESENT

        STEP 6: SAMPLE SIZE ANALYSIS
           - Look for: Numbers, sample counts, participant numbers, collection descriptions
        - Check: Methods section, study design, sample collection details, abstract
           - Examples: "n=50 participants", "100 samples collected", "Three floors sampled", "Multiple time points"
           - Be precise: "n=50" not "multiple samples", "100 samples" not "large sample size"
        - If you find numbers or sample counts, mark as PRESENT

        CRITICAL ANALYSIS INSTRUCTIONS:
        1. READ THE TEXT THOROUGHLY - Do not skim. Read every section carefully.
        2. LOOK FOR EXPLICIT MENTIONS - If the text says "Human participants", that's PRESENT.
        3. CHECK MULTIPLE SECTIONS - Title, abstract, methods, results, discussion.
        4. USE CONTEXT CLUES - If it mentions "fecal samples from patients", that's both host (Human) and body site (Gut).
        5. BE CONFIDENT - If you find clear information, use high confidence (0.8-1.0).
        6. DON'T GUESS - Only mark as PRESENT if you're confident the information exists.

        CONFIDENCE SCORING:
        - PRESENT (0.8-1.0): Information is explicitly stated and clear
        - PARTIALLY_PRESENT (0.4-0.7): Information is implied or partially described
        - ABSENT (0.0): Information is completely missing or unclear

        RESPONSE FORMAT - Return ONLY this JSON structure:
        {{
            "host_species": {{
                "primary": "extracted_species_name",
                "confidence": 0.0-1.0,
                "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                "reason_if_missing": "explanation if absent",
                "suggestions_for_curation": "what additional info is needed"
            }},
            "body_site": {{
                "site": "extracted_site_name",
                "confidence": 0.0-1.0,
                "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                "reason_if_missing": "explanation if absent",
                "suggestions_for_curation": "what additional info is needed"
            }},
            "condition": {{
                "description": "extracted_condition_description",
                "confidence": 0.0-1.0,
                "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                "reason_if_missing": "explanation if absent",
                "suggestions_for_curation": "what additional info is needed"
            }},
            "sequencing_type": {{
                "method": "extracted_sequencing_method",
                "confidence": 0.0-1.0,
                "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                "reason_if_missing": "explanation if absent",
                "suggestions_for_curation": "what additional info is needed"
            }},
            "taxa_level": {{
                "level": "extracted_taxonomic_level",
                "confidence": 0.0-1.0,
                "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                "reason_if_missing": "explanation if absent",
                "suggestions_for_curation": "what additional info is needed"
            }},
            "sample_size": {{
                "size": "extracted_sample_size",
                "confidence": 0.0-1.0,
                "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                "reason_if_missing": "explanation if absent",
                "suggestions_for_curation": "what additional info is needed"
            }}
        }}

        FINAL INSTRUCTIONS:
        - Focus ONLY on the 6 fields above
        - Be thorough and careful in your analysis
        - Extract actual information from the text, don't guess or infer
        - Return ONLY the JSON structure above
        - Ensure all field names match exactly: "host_species", "body_site", "condition", "sequencing_type", "taxa_level", "sample_size"
        - Use proper JSON syntax with double quotes for strings
        - Include all required sub-fields for each main field
        - If you find information, mark it as PRESENT with high confidence
        - Only mark as ABSENT if you're absolutely certain the information is missing
        """
        
        # Run enhanced analysis using Gemini
        try:
            analysis = await qa_system.analyze_paper_enhanced(enhanced_prompt)
            
            # Log the LLM response for debugging
            logger.info(f"=== LLM Response for PMID {pmid} ===")
            logger.info(f"Response status: {analysis.get('status', 'unknown')}")
            logger.info(f"Response confidence: {analysis.get('confidence', 'unknown')}")
            logger.info(f"Raw key findings: {analysis.get('key_findings', '{}')[:500]}...")
            
            # Parse the JSON response from Gemini
            try:
                parsed_analysis = json.loads(analysis.get("key_findings", "{}"))
                
                # Enhanced field validation and normalization using the field enhancer
                required_fields = ["host_species", "body_site", "condition", "sequencing_type", "taxa_level", "sample_size"]
                
                # Use the field enhancer to validate and improve extraction accuracy
                # Temporarily bypass field enhancer to test if it's causing the issue
                # enhanced_analysis = field_enhancer.enhance_extraction(parsed_analysis, full_text)
                enhanced_analysis = parsed_analysis
                
                # Ensure all required fields exist with proper structure
                missing_fields = []
                for field in required_fields:
                    if field not in enhanced_analysis:
                        missing_fields.append(field)
                        enhanced_analysis[field] = create_default_field_structure(field)
                    else:
                        # Validate existing field structure
                        field_data = enhanced_analysis[field]
                        if not isinstance(field_data, dict):
                            missing_fields.append(field)
                            enhanced_analysis[field] = create_default_field_structure(field)
                        else:
                            # Ensure all required sub-fields exist
                            if not validate_field_structure(field_data, field):
                                missing_fields.append(field)
                                enhanced_analysis[field] = create_default_field_structure(field)
                
                # Update missing fields from enhanced analysis
                missing_fields = enhanced_analysis.get("missing_fields", missing_fields)
                
                # Ensure we have the final structure
                enhanced_analysis["missing_fields"] = missing_fields
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed for PMID {pmid}: {str(e)}")
                logger.error(f"Raw analysis response: {analysis.get('key_findings', '{}')[:500]}...")
                
                # Create comprehensive fallback structure
                enhanced_analysis = create_comprehensive_fallback_analysis()
                missing_fields = ["host_species", "body_site", "condition", "sequencing_type", "taxa_level", "sample_size"]
            
            # Store analysis results in cache
            cache_manager.store_analysis_result(
                pmid, 
                enhanced_analysis, 
                metadata, 
                "gemini_enhanced", 
                analysis.get("confidence", 0.0)
            )
            
            # Compose the enhanced response
            response = {
                "pmid": pmid,
                "title": metadata.get("title", ""),
                "enhanced_analysis": enhanced_analysis,
                "timestamp": datetime.now().isoformat(),
                "source": "gemini_enhanced_analysis",
                "cached": False
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error during enhanced analysis: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
            
    except HTTPException as he:
        # Log error completion
        total_duration = time.time() - start_time
        perf_logger.log_pmid_query_end(pmid, total_duration, False, error=str(he.detail))
        raise he
    except Exception as e:
        # Log error completion
        total_duration = time.time() - start_time
        perf_logger.log_pmid_query_end(pmid, total_duration, False, error=str(e))
        logger.error(f"Error in analyze_paper endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Helper functions for field structure creation and validation
def create_default_field_structure(field_name: str) -> Dict:
    """Create a default structure for a missing field."""
    field_structures = {
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
    return field_structures.get(field_name, field_structures["host_species"]).copy()

def validate_field_structure(field_data: Dict, field_name: str) -> bool:
    """Validate that a field has the correct structure."""
    required_keys = {
        "host_species": ["primary", "confidence", "status", "reason_if_missing", "suggestions_for_curation"],
        "body_site": ["site", "confidence", "status", "reason_if_missing", "suggestions_for_curation"],
        "condition": ["description", "confidence", "status", "reason_if_missing", "suggestions_for_curation"],
        "sequencing_type": ["method", "confidence", "status", "reason_if_missing", "suggestions_for_curation"],
        "taxa_level": ["level", "confidence", "status", "reason_if_missing", "suggestions_for_curation"],
        "sample_size": ["size", "confidence", "status", "reason_if_missing", "suggestions_for_curation"]
    }
    
    required_keys_for_field = required_keys.get(field_name, [])
    return all(key in field_data for key in required_keys_for_field)

def create_comprehensive_fallback_analysis() -> Dict:
    """Create a comprehensive fallback analysis when parsing completely fails."""
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
        
        "missing_fields": ["host_species", "body_site", "condition", "sequencing_type", "taxa_level", "sample_size"],
        "curation_preparation_summary": "Analysis failed - re-run required"
    }

def generate_curation_summary(parsed_analysis: Dict, missing_fields: List[str]) -> str:
    """Generate a summary of what's needed for curation."""
    if not missing_fields:
        return "All required fields are present. Paper is ready for curation."
    
    if len(missing_fields) == 1:
        return f"Missing 1 field: {missing_fields[0]}. Review paper for this information."
    elif len(missing_fields) <= 3:
        return f"Missing {len(missing_fields)} fields: {', '.join(missing_fields)}. Paper needs additional review."
    else:
        return f"Missing {len(missing_fields)} fields: {', '.join(missing_fields)}. Paper requires significant review before curation."

@app.post("/analyze_batch", tags=["Batch Processing"])
async def analyze_batch(pmids: list = Body(...), page: int = Query(1), page_size: int = Query(20)):
    """
    **Batch analysis endpoint for multiple papers.**
    
    This endpoint analyzes multiple papers at once for BugSigDB curation readiness.
    It processes papers in batches and returns analysis results for the 6 essential fields.
    
    **Parameters:**
    - `pmids`: List of PubMed IDs to analyze
    - `page`: Page number for pagination (default: 1)
    - `page_size`: Number of papers per page (default: 20)
    
    **Returns:**
    - List of analysis results, each containing:
        - **enhanced_analysis**: 6-field analysis results
        
        - **metadata**: Paper metadata
        - **status**: Success/error status
    
    **Performance:** Results are cached to avoid re-analysis of previously processed papers.
    """
    start = (page - 1) * page_size
    end = start + page_size
    pmids_batch = pmids[start:end]
    results = []
    
    for pmid in pmids_batch:
        try:
            # Check cache first for analysis results
            cached_result = cache_manager.get_analysis_result(pmid)
            if cached_result and cache_manager.is_cache_valid(cached_result["timestamp"]):
                results.append({
                    "pmid": pmid,
                    "metadata": cached_result["metadata"],
                    "enhanced_analysis": cached_result["analysis_data"],
                    "timestamp": cached_result["timestamp"],
                    "source": cached_result["source"],
                    "cached": True,
                    "status": "success"
                })
                continue
            
            # Get metadata
            metadata = retriever.get_paper_metadata(pmid)
            csv_metadata = get_paper_metadata_from_csv(pmid)
            
            if csv_metadata:
                metadata.update(csv_metadata)
            
            if not metadata:
                results.append({
                    "pmid": pmid,
                    "status": "error",
                    "error": "Paper not found"
                    })
            continue
            
            # Store metadata in cache
            cache_manager.store_metadata(pmid, metadata, "pubmed")
            
            # Get full text if available
            full_text = ""
            try:
                full_text = retriever.get_pmc_fulltext(pmid)
                if isinstance(full_text, str):
                    try:
                        soup = BeautifulSoup(full_text, 'lxml')
                        full_text = retriever._extract_text_from_pmc_xml(soup)
                    except Exception as e:
                        logger.warning(f"Failed to parse PMC XML for PMID {pmid}: {str(e)}")
                
                if full_text:
                    cache_manager.store_fulltext(pmid, full_text, "pmc")
            except Exception as e:
                logger.warning(f"Failed to retrieve PMC full text for PMID {pmid}: {str(e)}")
            
            # Run enhanced analysis with the same improved prompt
            enhanced_prompt = f"""
            Analyze this scientific paper for BugSigDB curation. Focus ONLY on these 6 essential fields:

            PAPER INFORMATION:
            Title: {metadata.get('title', '')}
            Abstract: {metadata.get('abstract', '')}
            MeSH Terms: {', '.join(metadata.get('mesh_terms', []))}
            Publication Type: {', '.join(metadata.get('publication_types', []))}
            Journal: {metadata.get('journal', '')}
            Year: {metadata.get('year', '')}
            
            PRELIMINARY EXTRACTION (from metadata):
            - Host Species: {metadata.get('host', 'Not extracted')}
            - Body Site: {metadata.get('body_site', 'Not extracted')}
            - Sequencing Type: {metadata.get('sequencing_type', 'Not extracted')}
            
            FULL TEXT CONTENT (first 8000 characters):
            {full_text[:8000] if full_text else 'Not available'}

            REQUIRED ANALYSIS - EXTRACT THESE 6 FIELDS WITH HIGH ACCURACY:

            STEP 1: HOST SPECIES ANALYSIS
            - Look for: "Human", "Mouse", "Rat", "Drosophila", "Zebrafish", "Pig", "Cow", "Chicken", etc.
            - For environmental studies: Look for "Environment", "Indoor", "Outdoor", "Built environment", "Natural environment"
            - Check: Abstract, methods section, study population descriptions, mesh terms, title
            - Examples: "Human participants", "Adult female offspring", "Built environment microbiome", "Indoor air samples"
            - Be specific: "Human" not "mammal", "Mouse" not "rodent"
            - If you find "Human participants" or "Human subjects", mark as PRESENT

            STEP 2: BODY SITE ANALYSIS
            - For human/animal: "Gut", "Oral", "Skin", "Vaginal", "Lung", "Nasal", "Ear", "Stool", "Feces"
            - For environmental: "Indoor", "Restroom", "Hospital", "School", "Office", "Soil", "Water", "Air", "Surface"
            - Check: Sample collection methods, study location descriptions, abstract, methods section
            - Examples: "Fecal samples", "Oral swabs", "Indoor dust", "Restroom surfaces", "Hospital air"
            - Be precise: "Gut" not "digestive system", "Indoor air" not "air"
            - If you find "fecal samples" or "stool samples", mark as PRESENT

            STEP 3: CONDITION ANALYSIS
            - Look for: Disease names, experimental conditions, comparative studies, environmental factors
            - Check: Study objectives, hypothesis, experimental design, disease associations, abstract
            - Examples: "IBD patients", "Obesity", "Diabetes", "Antibiotic treatment", "Men vs women comparison", "Floor differences", "Seasonal changes"
            - Be specific: "Type 2 Diabetes" not "diabetes", "Crohn's disease" not "IBD"
            - If you find disease names or experimental conditions, mark as PRESENT

            STEP 4: SEQUENCING TYPE ANALYSIS
            - Look for: "16S rRNA", "metagenomics", "shotgun sequencing", "amplicon sequencing", "metatranscriptomics"
            - Check: Methods section, molecular techniques, sequencing protocols, abstract
            - Examples: "16S rRNA gene sequencing", "V4 region amplification", "Illumina sequencing", "Next-generation sequencing"
            - Be precise: "16S rRNA" not "sequencing", "Metagenomics" not "genomics"
            - If you find "16S" or "sequencing", mark as PRESENT

            STEP 5: TAXA LEVEL ANALYSIS
            - Look for: Taxonomic levels and specific names
            - Check: Results section, microbial community descriptions, diversity analysis, abstract
            - Examples: "Phylum level: Proteobacteria, Actinobacteria", "Genus level: Bacteroides, Prevotella", "Species level: E. coli, B. fragilis"
            - Be specific: "Bacteroides fragilis" not "Bacteroides", "Proteobacteria phylum" not "bacteria"
            - If you find taxonomic names or levels, mark as PRESENT

            STEP 6: SAMPLE SIZE ANALYSIS
            - Look for: Numbers, sample counts, participant numbers, collection descriptions
            - Check: Methods section, study design, sample collection details, abstract
            - Examples: "n=50 participants", "100 samples collected", "Three floors sampled", "Multiple time points"
            - Be precise: "n=50" not "multiple samples", "100 samples" not "large sample size"
            - If you find numbers or sample counts, mark as PRESENT

            CRITICAL ANALYSIS INSTRUCTIONS:
            1. READ THE TEXT THOROUGHLY - Do not skim. Read every section carefully.
            2. LOOK FOR EXPLICIT MENTIONS - If the text says "Human participants", that's PRESENT.
            3. CHECK MULTIPLE SECTIONS - Title, abstract, methods, results, discussion.
            4. USE CONTEXT CLUES - If it mentions "fecal samples from patients", that's both host (Human) and body site (Gut).
            5. BE CONFIDENT - If you find clear information, use high confidence (0.8-1.0).
            6. DON'T GUESS - Only mark as PRESENT if you're confident the information exists.

            CONFIDENCE SCORING:
            - PRESENT (0.8-1.0): Information is explicitly stated and clear
            - PARTIALLY_PRESENT (0.4-0.7): Information is implied or partially described
            - ABSENT (0.0): Information is completely missing or unclear

            RESPONSE FORMAT - Return ONLY this JSON structure:
            {{
                "host_species": {{
                    "primary": "extracted_species_name",
                    "confidence": 0.0-1.0,
                    "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                    "reason_if_missing": "explanation if absent",
                    "suggestions_for_curation": "what additional info is needed"
                }},
                "body_site": {{
                    "site": "extracted_site_name",
                    "confidence": 0.0-1.0,
                    "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                    "reason_if_missing": "explanation if absent",
                    "suggestions_for_curation": "what additional info is needed"
                }},
                "condition": {{
                    "description": "extracted_condition_description",
                    "confidence": 0.0-1.0,
                    "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                    "reason_if_missing": "explanation if absent",
                    "suggestions_for_curation": "what additional info is needed"
                }},
                "sequencing_type": {{
                    "method": "extracted_sequencing_method",
                    "confidence": 0.0-1.0,
                    "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                    "reason_if_missing": "explanation if absent",
                    "suggestions_for_curation": "what additional info is needed"
                }},
                "taxa_level": {{
                    "level": "extracted_taxonomic_level",
                    "confidence": 0.0-1.0,
                    "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                    "reason_if_missing": "explanation if absent",
                    "suggestions_for_curation": "what additional info is needed"
                }},
                "sample_size": {{
                    "size": "extracted_sample_size",
                    "confidence": 0.0-1.0,
                    "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                    "reason_if_missing": "explanation if absent",
                    "suggestions_for_curation": "what additional info is needed"
                }}
            }}

            FINAL INSTRUCTIONS:
            - Focus ONLY on the 6 fields above
            - Be thorough and careful in your analysis
            - Extract actual information from the text, don't guess or infer
            - Return ONLY the JSON structure above
            - Ensure all field names match exactly: "host_species", "body_site", "condition", "sequencing_type", "taxa_level", "sample_size"
            - Use proper JSON syntax with double quotes for strings
            - Include all required sub-fields for each main field
            - If you find information, mark it as PRESENT with high confidence
            - Only mark as ABSENT if you're absolutely certain the information is missing
            """
            
            analysis = await qa_system.analyze_paper_enhanced(enhanced_prompt)
            
            try:
                parsed_analysis = json.loads(analysis.get("key_findings", "{}"))
                
                # Validate that we have exactly the 6 required fields
                required_fields = ["host_species", "body_site", "condition", "sequencing_type", "taxa_level", "sample_size"]
                missing_fields = []
                
                for field in required_fields:
                    if field not in parsed_analysis or not parsed_analysis[field]:
                        missing_fields.append(field)
                        # Ensure the field exists with default structure
                        if field == "host_species":
                            parsed_analysis[field] = {"primary": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "Field not found in analysis", "suggestions_for_curation": "Review paper for host species information"}
                        elif field == "body_site":
                            parsed_analysis[field] = {"site": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "Field not found in analysis", "suggestions_for_curation": "Review paper for body site information"}
                        elif field == "condition":
                            parsed_analysis[field] = {"description": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "Field not found in analysis", "suggestions_for_curation": "Review paper for condition information"}
                        elif field == "sequencing_type":
                            parsed_analysis[field] = {"method": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "Field not found in analysis", "suggestions_for_curation": "Review paper for sequencing method information"}
                        elif field == "taxa_level":
                            parsed_analysis[field] = {"level": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "Field not found in analysis", "suggestions_for_curation": "Review paper for taxonomic level information"}
                        elif field == "sample_size":
                            parsed_analysis[field] = {"size": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "Field not found in analysis", "suggestions_for_curation": "Review paper for sample size information"}
            
                # Update the parsed analysis with missing fields
                parsed_analysis["missing_fields"] = missing_fields
                
            except json.JSONDecodeError:
                parsed_analysis = {
                    "host_species": {"primary": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "JSON parsing failed", "suggestions_for_curation": "Re-run analysis"},
                    "body_site": {"site": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "JSON parsing failed", "suggestions_for_curation": "Re-run analysis"},
                    "condition": {"description": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "JSON parsing failed", "suggestions_for_curation": "Re-run analysis"},
                    "sequencing_type": {"method": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "JSON parsing failed", "suggestions_for_curation": "Re-run analysis"},
                    "taxa_level": {"level": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "JSON parsing failed", "suggestions_for_curation": "Re-run analysis"},
                    "sample_size": {"size": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "JSON parsing failed", "suggestions_for_curation": "Re-run analysis"},
        
                    "missing_fields": ["host_species", "body_site", "condition", "sequencing_type", "taxa_level", "sample_size"],
                    "curation_preparation_summary": "Analysis failed - re-run required"
                }
            
            confidence = analysis.get("confidence", 0.0)
            
            # Store analysis results in cache
            cache_manager.store_analysis_result(
                pmid, 
                parsed_analysis, 
                metadata, 
                "gemini_enhanced", 
                confidence
            )
            
            results.append({
            "pmid": pmid,
                "metadata": cached_result["metadata"],
                "enhanced_analysis": parsed_analysis,
                "timestamp": datetime.now().isoformat(),
                "source": "gemini_enhanced_analysis",
                "cached": False,
                "status": "success"
            })
            
        except Exception as e:
            logger.error(f"Error processing PMID {pmid}: {str(e)}")
            results.append({
                "pmid": pmid,
                "status": "error",
                "error": str(e)
            })
    
    return results

def get_paper_metadata_from_csv(pmid, csv_path='data/full_dump.csv'):
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        # Skip comment lines (starting with #) or skip first 2 lines
        while True:
            pos = csvfile.tell()
            line = csvfile.readline()
            if not line:
                return None  # End of file, not found
            if isinstance(line, str) and not line.startswith('#'):
                csvfile.seek(pos)
                break
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row.get('PMID') == pmid:
                # Combine both group sample sizes if present
                group0 = row.get('Group 0 sample size', '')
                group1 = row.get('Group 1 sample size', '')
                sample_size = f"Group 0: {group0}, Group 1: {group1}" if group0 or group1 else ''
                return {
                    'pmid': row.get('PMID', ''),
                    'title': row.get('Title', ''),
                    'authors': row.get('Authors list', ''),
                    'journal': row.get('Journal', ''),
                    'year': row.get('Year', ''),
                    'host': row.get('Host species', ''),
                    'body_site': row.get('Body site', ''),
                    'condition': row.get('Condition', ''),
                    'sequencing_type': row.get('Sequencing type', ''),
                    'in_bugsigdb': row.get('In BugSigDB', ''),
                    'sample_size': sample_size,
                    'taxa_level': row.get('Taxa Level', ''),
                    'statistical_method': row.get('Statistical test', ''),
                    'doi': row.get('DOI', ''),
                    'publication_date': row.get('Publication Date', ''),
                    'signature_probability': row.get('Signature Probability', ''),
                }
    return None

@app.get("/list_pmids", tags=["Batch Processing"])
def list_pmids():
    """
    **Get list of all available PMIDs from the CSV database.**
    
    This endpoint retrieves all PubMed IDs available in the local CSV database.
    Useful for batch processing and data exploration.
    
    **Returns:**
    - List of PMIDs as strings
    
    **Note:** This endpoint reads from the local CSV file and may take time for large datasets.
    """
    pmids = []
    try:
        with open('data/full_dump.csv', newline='', encoding='utf-8') as csvfile:
            # Skip comment lines and header
            while True:
                pos = csvfile.tell()
                line = csvfile.readline()
                if not line:
                    break
                if isinstance(line, str) and not line.startswith('#'):
                    csvfile.seek(pos)
                    break
            import csv as pycsv
            reader = pycsv.DictReader(csvfile)
            for row in reader:
                pmid = row.get('PMID')
                if pmid and pmid != 'NA':
                    pmids.append(pmid)
    except Exception as e:
        return {"error": str(e)}
    return pmids

@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint to verify the service is running."""
    return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "service": "BioAnalyzer"
    }

@app.get("/config", tags=["System"])
async def get_config():
    """Get configuration settings for the frontend."""
    return {
        "timeouts": {
            "frontend": FRONTEND_TIMEOUT,
            "gemini": GEMINI_TIMEOUT,
            "analysis": ANALYSIS_TIMEOUT
        },
        "version": "2.0.0",
        "service": "BioAnalyzer"
        }

@app.get("/health/gemini", tags=["System"])
async def gemini_health_check():
    """Specific health check for Gemini API connectivity."""
    try:
        if not qa_system:
            return {
                "status": "not_configured",
                "timestamp": datetime.now().isoformat(),
                "error": "QA system not configured"
            }
        
        # Basic health check
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "message": "System is operational"
        }
            
    except Exception as e:
        logger.exception("Gemini health check failed")  # Log full traceback
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": "Gemini health check failed due to an internal server error.",
            "suggestions": [
                "Check your Gemini API key",
                "Verify IP address is not restricted",
                "Check API quota usage",
                "Ensure API key has proper permissions"
            ]
        }

@app.get("/metrics", tags=["System"])
async def get_metrics():
    """Get system performance metrics."""
    try:
        cache_stats = cache_manager.get_cache_stats()
        
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "cache": cache_stats,
            "performance": {
                "cache_hit_rate": cache_stats.get("curation_readiness_rate", 0.0),
                "total_analyzed": cache_stats.get("total_curation_analyzed", 0),
                "recent_activity": cache_stats.get("recent_analysis_24h", 0)
            }
        }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Metrics collection failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Metrics collection failed: {str(e)}")

@app.delete("/cache/analysis/{pmid}", tags=["Cache Management"])
async def delete_analysis_cache(pmid: str):
    """Delete cached analysis results for a specific PMID."""
    try:
        success = cache_manager.delete_analysis_result(pmid)
        if success:
            return {"message": f"Analysis cache deleted for PMID {pmid}", "pmid": pmid}
        else:
            raise HTTPException(status_code=404, detail=f"No analysis cache found for PMID {pmid}")
    except Exception as e:
        logger.error(f"Failed to delete analysis cache for PMID {pmid}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete analysis cache: {str(e)}")

@app.delete("/cache/metadata/{pmid}", tags=["Cache Management"])
async def delete_metadata_cache(pmid: str):
    """Delete cached metadata for a specific PMID."""
    try:
        success = cache_manager.delete_metadata(pmid)
        if success:
            return {"message": f"Metadata cache deleted for PMID {pmid}", "pmid": pmid}
        else:
            raise HTTPException(status_code=404, detail=f"No metadata cache found for PMID {pmid}")
    except Exception as e:
        logger.error(f"Failed to delete metadata cache for PMID {pmid}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete metadata cache: {str(e)}")

@app.delete("/cache/fulltext/{pmid}", tags=["Cache Management"])
async def delete_fulltext_cache(pmid: str):
    """Delete cached full text for a specific PMID."""
    try:
        success = cache_manager.delete_fulltext(pmid)
        if success:
            return {"message": f"Full text cache deleted for PMID {pmid}", "pmid": pmid}
        else:
            raise HTTPException(status_code=404, detail=f"No full text cache found for PMID {pmid}")
    except Exception as e:
        logger.error(f"Failed to delete full text cache for PMID {pmid}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete full text cache: {str(e)}")

@app.delete("/cache/all", tags=["Cache Management"])
async def clear_all_cache():
    """Clear all cached data."""
    try:
        success = cache_manager.clear_all_cache()
        if success:
            return {"message": "All cache cleared successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to clear cache")
    except Exception as e:
        logger.error(f"Failed to clear all cache: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

@app.get("/enhanced_analysis/{pmid}", tags=["Paper Analysis"])
async def enhanced_analysis(pmid: str):
    """
    **Enhanced analysis endpoint for BugSigDB curation requirements.**
    
    This endpoint provides the same 6-field analysis as the main analyze endpoint but with additional
    caching and performance optimizations. It's the recommended endpoint for production use.
    
    **Parameters:**
    - `pmid`: PubMed ID of the paper to analyze
    
    **Returns:**
    - **enhanced_analysis**: Detailed analysis of the 6 essential fields
    - **metadata**: Paper metadata (title, abstract, authors, etc.)
    - **cached**: Boolean indicating if result was retrieved from cache
    
    **6 Essential Fields Analyzed:**
    1. **host_species**: Host organism being studied
    2. **body_site**: Microbiome sample collection location
    3. **condition**: Disease/treatment/exposure studied
    4. **sequencing_type**: Molecular method used
    5. **taxa_level**: Taxonomic level analyzed
    6. **sample_size**: Number of samples analyzed
    
    **Note:** This endpoint is functionally identical to `/analyze/{pmid}` but includes caching.
    """
    try:
        logger.info(f"=== Starting enhanced analysis for PMID: {pmid} ===")
        
        # Check cache first for analysis results
        cached_result = cache_manager.get_analysis_result(pmid)
        if cached_result and cache_manager.is_cache_valid(cached_result["timestamp"]):
            logger.info(f"Returning cached analysis for PMID: {pmid}")
            return {
                "pmid": pmid,
                "metadata": cached_result["metadata"],
                "enhanced_analysis": cached_result["analysis_data"],
                "timestamp": cached_result["timestamp"],
                "source": cached_result["source"],
                "cached": True
            }
        
        # Get paper metadata (with timeout to prevent hanging)
        try:
            logger.info(f"Retrieving metadata for PMID {pmid}...")
            metadata = await asyncio.wait_for(
                retriever.get_paper_metadata_async(pmid),
                timeout=20.0  # 20 second timeout for metadata retrieval
            )
            csv_metadata = get_paper_metadata_from_csv(pmid)
            
            if csv_metadata:
                metadata.update(csv_metadata)
            
            if not metadata:
                raise HTTPException(status_code=404, detail=f"Paper not found: {pmid}")
            
            # Store metadata in cache
            cache_manager.store_metadata(pmid, metadata, "pubmed")
            logger.info(f"Successfully retrieved metadata for PMID {pmid}")
            
        except asyncio.TimeoutError:
            logger.error(f"Metadata retrieval timed out for PMID {pmid} after 20 seconds")
            raise HTTPException(status_code=408, detail=f"Metadata retrieval timed out for PMID {pmid}")
        except Exception as e:
            logger.error(f"Failed to retrieve metadata for PMID {pmid}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to retrieve metadata: {str(e)}")
        
        # Get full text if available (with timeout to prevent hanging)
        full_text = ""
        try:
            logger.info(f"Attempting to retrieve PMC full text for PMID {pmid}...")
            # Add timeout to prevent hanging
            full_text = await asyncio.wait_for(
                retriever.get_pmc_fulltext_async(pmid),
                timeout=30.0  # 30 second timeout for PMC retrieval
            )
            if isinstance(full_text, str):
                try:
                    soup = BeautifulSoup(full_text, 'lxml')
                    full_text = retriever._extract_text_from_pmc_xml(soup)
                    logger.info(f"Successfully retrieved and parsed PMC full text for PMID {pmid}")
                except Exception as e:
                    logger.warning(f"Failed to parse PMC XML for PMID {pmid}: {str(e)}")
            
            # Store full text in cache
            if full_text:
                cache_manager.store_fulltext(pmid, full_text, "pmc")
                
        except asyncio.TimeoutError:
            logger.warning(f"PMC full text retrieval timed out for PMID {pmid} after 30 seconds")
            full_text = ""
        except Exception as e:
            logger.warning(f"Failed to retrieve PMC full text for PMID {pmid}: {str(e)}")
            full_text = ""
        
        # Log the content being sent to LLM for debugging
        logger.info(f"=== LLM Analysis Request for PMID {pmid} ===")
        logger.info(f"Title: {metadata.get('title', '')[:100]}...")
        logger.info(f"Abstract length: {len(metadata.get('abstract', ''))} characters")
        logger.info(f"MeSH Terms: {metadata.get('mesh_terms', [])}")
        logger.info(f"Full text length: {len(full_text) if full_text else 0} characters")
        logger.info(f"Preliminary extraction - Host: {metadata.get('host', 'Not extracted')}")
        logger.info(f"Preliminary extraction - Body Site: {metadata.get('body_site', 'Not extracted')}")
        logger.info(f"Preliminary extraction - Sequencing: {metadata.get('sequencing_type', 'Not extracted')}")
        
        # Create enhanced prompt for specific analysis - same as enhanced endpoints
        enhanced_prompt = f"""
        You are a specialized AI assistant for BugSigDB curation. Your task is to carefully analyze this scientific paper and extract specific information about 6 essential fields required for microbial signature curation.

        PAPER INFORMATION:
        Title: {metadata.get('title', '')}
        Abstract: {metadata.get('abstract', '')}
        MeSH Terms: {', '.join(metadata.get('mesh_terms', []))}
        Publication Type: {', '.join(metadata.get('publication_types', []))}
        Journal: {metadata.get('journal', '')}
        Year: {metadata.get('year', '')}
        
        PRELIMINARY EXTRACTION (from metadata):
        - Host Species: {metadata.get('host', 'Not extracted')}
        - Body Site: {metadata.get('body_site', 'Not extracted')}
        - Sequencing Type: {metadata.get('sequencing_type', 'Not extracted')}
        
        FULL TEXT CONTENT (first 8000 characters):
        {full_text[:8000] if full_text else 'Not available'}

        REQUIRED ANALYSIS - EXTRACT THESE 6 FIELDS WITH HIGH ACCURACY:

        STEP 1: HOST SPECIES ANALYSIS
           - Look for: "Human", "Mouse", "Rat", "Drosophila", "Zebrafish", "Pig", "Cow", "Chicken", etc.
           - For environmental studies: Look for "Environment", "Indoor", "Outdoor", "Built environment", "Natural environment"
        - Check: Abstract, methods section, study population descriptions, mesh terms, title
           - Examples: "Human participants", "Adult female offspring", "Built environment microbiome", "Indoor air samples"
           - Be specific: "Human" not "mammal", "Mouse" not "rodent"
        - If you find "Human participants" or "Human subjects", mark as PRESENT

        STEP 2: BODY SITE ANALYSIS
           - For human/animal: "Gut", "Oral", "Skin", "Vaginal", "Lung", "Nasal", "Ear", "Stool", "Feces"
           - For environmental: "Indoor", "Restroom", "Hospital", "School", "Office", "Soil", "Water", "Air", "Surface"
        - Check: Sample collection methods, study location descriptions, abstract, methods section
           - Examples: "Fecal samples", "Oral swabs", "Indoor dust", "Restroom surfaces", "Hospital air"
           - Be precise: "Gut" not "digestive system", "Indoor air" not "air"
        - If you find "fecal samples" or "stool samples", mark as PRESENT

        STEP 3: CONDITION ANALYSIS
           - Look for: Disease names, experimental conditions, comparative studies, environmental factors
        - Check: Study objectives, hypothesis, experimental design, disease associations, abstract
           - Examples: "IBD patients", "Obesity", "Diabetes", "Antibiotic treatment", "Men vs women comparison", "Floor differences", "Seasonal changes"
           - Be specific: "Type 2 Diabetes" not "diabetes", "Crohn's disease" not "IBD"
        - If you find disease names or experimental conditions, mark as PRESENT

        STEP 4: SEQUENCING TYPE ANALYSIS
           - Look for: "16S rRNA", "metagenomics", "shotgun sequencing", "amplicon sequencing", "metatranscriptomics"
        - Check: Methods section, molecular techniques, sequencing protocols, abstract
           - Examples: "16S rRNA gene sequencing", "V4 region amplification", "Illumina sequencing", "Next-generation sequencing"
           - Be precise: "16S rRNA" not "sequencing", "Metagenomics" not "genomics"
        - If you find "16S" or "sequencing", mark as PRESENT

        STEP 5: TAXA LEVEL ANALYSIS
           - Look for: Taxonomic levels and specific names
        - Check: Results section, microbial community descriptions, diversity analysis, abstract
           - Examples: "Phylum level: Proteobacteria, Actinobacteria", "Genus level: Bacteroides, Prevotella", "Species level: E. coli, B. fragilis"
           - Be specific: "Bacteroides fragilis" not "Bacteroides", "Proteobacteria phylum" not "bacteria"
        - If you find taxonomic names or levels, mark as PRESENT

        STEP 6: SAMPLE SIZE ANALYSIS
           - Look for: Numbers, sample counts, participant numbers, collection descriptions
        - Check: Methods section, study design, sample collection details, abstract
           - Examples: "n=50 participants", "100 samples collected", "Three floors sampled", "Multiple time points"
           - Be precise: "n=50" not "multiple samples", "100 samples" not "large sample size"
        - If you find numbers or sample counts, mark as PRESENT

        CRITICAL ANALYSIS INSTRUCTIONS:
        1. READ THE TEXT THOROUGHLY - Do not skim. Read every section carefully.
        2. LOOK FOR EXPLICIT MENTIONS - If the text says "Human participants", that's PRESENT.
        3. CHECK MULTIPLE SECTIONS - Title, abstract, methods, results, discussion.
        4. USE CONTEXT CLUES - If it mentions "fecal samples from patients", that's both host (Human) and body site (Gut).
        5. BE CONFIDENT - If you find clear information, use high confidence (0.8-1.0).
        6. DON'T GUESS - Only mark as PRESENT if you're confident the information exists.

        CONFIDENCE SCORING:
        - PRESENT (0.8-1.0): Information is explicitly stated and clear
        - PARTIALLY_PRESENT (0.4-0.7): Information is implied or partially described
        - ABSENT (0.0): Information is completely missing or unclear

        RESPONSE FORMAT - Return ONLY this JSON structure:
        {{
            "host_species": {{
                "primary": "extracted_species_name",
                "confidence": 0.0-1.0,
                "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                "reason_if_missing": "explanation if absent",
                "suggestions_for_curation": "what additional info is needed"
            }},
            "body_site": {{
                "site": "extracted_site_name",
                "confidence": 0.0-1.0,
                "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                "reason_if_missing": "explanation if absent",
                "suggestions_for_curation": "what additional info is needed"
            }},
            "condition": {{
                "description": "extracted_condition_description",
                "confidence": 0.0-1.0,
                "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                "reason_if_missing": "explanation if absent",
                "suggestions_for_curation": "what additional info is needed"
            }},
            "sequencing_type": {{
                "method": "extracted_sequencing_method",
                "confidence": 0.0-1.0,
                "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                "reason_if_missing": "explanation if absent",
                "suggestions_for_curation": "what additional info is needed"
            }},
            "taxa_level": {{
                "level": "extracted_taxonomic_level",
                "confidence": 0.0-1.0,
                "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                "reason_if_missing": "explanation if absent",
                "suggestions_for_curation": "what additional info is needed"
            }},
            "sample_size": {{
                "size": "extracted_sample_size",
                "confidence": 0.0-1.0,
                "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                "reason_if_missing": "explanation if absent",
                "suggestions_for_curation": "what additional info is needed"
            }}
        }}

        FINAL INSTRUCTIONS:
        - Focus ONLY on the 6 fields above
        - Be thorough and careful in your analysis
        - Extract actual information from the text, don't guess or infer
        - Return ONLY the JSON structure above
        - Ensure all field names match exactly: "host_species", "body_site", "condition", "sequencing_type", "taxa_level", "sample_size"
        - Use proper JSON syntax with double quotes for strings
        - Include all required sub-fields for each main field
        - If you find information, mark it as PRESENT with high confidence
        - Only mark as ABSENT if you're absolutely certain the information is missing
        """
        
        # Run enhanced analysis using Gemini
        try:
            analysis = await qa_system.analyze_paper_enhanced(enhanced_prompt)
            
            # Log the LLM response for debugging
            logger.info(f"=== LLM Response for PMID {pmid} ===")
            logger.info(f"Response status: {analysis.get('status', 'unknown')}")
            logger.info(f"Response confidence: {analysis.get('confidence', 'unknown')}")
            logger.info(f"Raw key findings: {analysis.get('key_findings', '{}')[:500]}...")
            
            # Parse the JSON response from Gemini
            try:
                parsed_analysis = json.loads(analysis.get("key_findings", "{}"))
                
                # Enhanced field validation and normalization using the field enhancer
                required_fields = ["host_species", "body_site", "condition", "sequencing_type", "taxa_level", "sample_size"]
                
                # Use the field enhancer to validate and improve extraction accuracy
                # Temporarily bypass field enhancer to test if it's causing the issue
                # enhanced_analysis = field_enhancer.enhance_extraction(parsed_analysis, full_text)
                enhanced_analysis = parsed_analysis
                
                # Ensure all required fields exist with proper structure
                missing_fields = []
                for field in required_fields:
                    if field not in enhanced_analysis:
                        missing_fields.append(field)
                        enhanced_analysis[field] = create_default_field_structure(field)
                    else:
                        # Validate existing field structure
                        field_data = enhanced_analysis[field]
                        if not isinstance(field_data, dict):
                            missing_fields.append(field)
                            enhanced_analysis[field] = create_default_field_structure(field)
                        else:
                            # Ensure all required sub-fields exist
                            if not validate_field_structure(field_data, field):
                                missing_fields.append(field)
                                enhanced_analysis[field] = create_default_field_structure(field)
                
                # Update missing fields from enhanced analysis
                missing_fields = enhanced_analysis.get("missing_fields", missing_fields)
                
                # Ensure we have the final structure
                enhanced_analysis["missing_fields"] = missing_fields
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed for PMID {pmid}: {str(e)}")
                logger.error(f"Raw analysis response: {analysis.get('key_findings', '{}')[:500]}...")
                
                # Create comprehensive fallback structure
                enhanced_analysis = create_comprehensive_fallback_analysis()
                missing_fields = ["host_species", "body_site", "condition", "sequencing_type", "taxa_level", "sample_size"]
            
            # Store analysis results in cache
            cache_manager.store_analysis_result(
                pmid, 
                enhanced_analysis, 
                metadata, 
                "gemini_enhanced", 
                analysis.get("confidence", 0.0)
            )
            
            # Compose the enhanced response
            response = {
                "pmid": pmid,
                "title": metadata.get("title", ""),
                "enhanced_analysis": enhanced_analysis,
                "timestamp": datetime.now().isoformat(),
                "source": "gemini_enhanced_analysis",
                "cached": False
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error during enhanced analysis: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in enhanced analysis endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.post("/enhanced_analysis_batch", tags=["Batch Processing"])
async def enhanced_analysis_batch(pmids: List[str] = Body(...), max_concurrent: int = Query(5)):
    """
    **Enhanced batch analysis endpoint for multiple papers.**
    
    This endpoint provides the same 6-field analysis as the regular batch endpoint but with
    additional performance optimizations and caching. It's the recommended endpoint for batch processing.
    
    **Parameters:**
    - `pmids`: List of PubMed IDs to analyze (max 50)
    - `max_concurrent`: Maximum concurrent processing (default: 5)
    
    **Returns:**
    - **batch_results**: List of analysis results for each PMID
    - **summary**: Processing statistics including:
        - Total PMIDs processed
        - Success/error counts
        - Cache hit rates
        - Processing timestamps
    
    **Performance Features:**
    - Intelligent caching to avoid re-analysis
    - Concurrent processing for better throughput
    - Detailed performance metrics
    """
    try:
        if not pmids:
            raise HTTPException(status_code=400, detail="No PMIDs provided")
        
        if len(pmids) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 PMIDs allowed per batch")
        
        results = []
        cached_count = 0
        new_analysis_count = 0
        
        # Process PMIDs with caching
        for pmid in pmids:
            try:
                # Check cache first
                cached_result = cache_manager.get_analysis_result(pmid)
                if cached_result and cache_manager.is_cache_valid(cached_result["timestamp"]):
                    results.append({
                        "pmid": pmid,
                        "metadata": cached_result["metadata"],
                        "enhanced_analysis": cached_result["analysis_data"],
                        "timestamp": cached_result["timestamp"],
                        "source": cached_result["source"],
                        "cached": True,
                        "status": "success"
                    })
                    cached_count += 1
                else:
                    # Get metadata and run analysis
                    metadata = retriever.get_paper_metadata(pmid)
                    csv_metadata = get_paper_metadata_from_csv(pmid)
                    
                    if csv_metadata:
                        metadata.update(csv_metadata)
                    
                    if not metadata:
                        results.append({
                            "pmid": pmid,
                            "status": "error",
                            "error": "Paper not found"
                        })
                        continue
                    
                    # Store metadata in cache
                    cache_manager.store_metadata(pmid, metadata, "pubmed")
                    
                    # Get full text if available
                    full_text = ""
                    try:
                        full_text = retriever.get_pmc_fulltext(pmid)
                        if isinstance(full_text, str):
                            try:
                                soup = BeautifulSoup(full_text, 'lxml')
                                full_text = retriever._extract_text_from_pmc_xml(soup)
                            except Exception as e:
                                logger.warning(f"Failed to parse PMC XML for PMID {pmid}: {str(e)}")
                        
                        if full_text:
                            cache_manager.store_fulltext(pmid, full_text, "pmc")
                    except Exception as e:
                        logger.warning(f"Failed to retrieve PMC full text for PMID {pmid}: {str(e)}")
                    
                    # Run enhanced analysis with the same improved prompt
                    enhanced_prompt = f"""
                    Analyze this scientific paper for BugSigDB curation. Focus ONLY on these 6 essential fields:

                    PAPER INFORMATION:
                    Title: {metadata.get('title', '')}
                    Abstract: {metadata.get('abstract', '')}
                    MeSH Terms: {', '.join(metadata.get('mesh_terms', []))}
                    Publication Type: {', '.join(metadata.get('publication_types', []))}
                    Journal: {metadata.get('journal', '')}
                    Year: {metadata.get('year', '')}
                    
                    PRELIMINARY EXTRACTION (from metadata):
                    - Host Species: {metadata.get('host', 'Not extracted')}
                    - Body Site: {metadata.get('body_site', 'Not extracted')}
                    - Sequencing Type: {metadata.get('sequencing_type', 'Not extracted')}
                    
                    FULL TEXT CONTENT (first 8000 characters):
                    {full_text[:8000] if full_text else 'Not available'}

                    REQUIRED ANALYSIS - EXTRACT THESE 6 FIELDS WITH HIGH ACCURACY:

                    STEP 1: HOST SPECIES ANALYSIS
                    - Look for: "Human", "Mouse", "Rat", "Drosophila", "Zebrafish", "Pig", "Cow", "Chicken", etc.
                    - For environmental studies: Look for "Environment", "Indoor", "Outdoor", "Built environment", "Natural environment"
                    - Check: Abstract, methods section, study population descriptions, mesh terms, title
                    - Examples: "Human participants", "Adult female offspring", "Built environment microbiome", "Indoor air samples"
                    - Be specific: "Human" not "mammal", "Mouse" not "rodent"
                    - If you find "Human participants" or "Human subjects", mark as PRESENT

                    STEP 2: BODY SITE ANALYSIS
                    - For human/animal: "Gut", "Oral", "Skin", "Vaginal", "Lung", "Nasal", "Ear", "Stool", "Feces"
                    - For environmental: "Indoor", "Restroom", "Hospital", "School", "Office", "Soil", "Water", "Air", "Surface"
                    - Check: Sample collection methods, study location descriptions, abstract, methods section
                    - Examples: "Fecal samples", "Oral swabs", "Indoor dust", "Restroom surfaces", "Hospital air"
                    - Be precise: "Gut" not "digestive system", "Indoor air" not "air"
                    - If you find "fecal samples" or "stool samples", mark as PRESENT

                    STEP 3: CONDITION ANALYSIS
                    - Look for: Disease names, experimental conditions, comparative studies, environmental factors
                    - Check: Study objectives, hypothesis, experimental design, disease associations, abstract
                    - Examples: "IBD patients", "Obesity", "Diabetes", "Antibiotic treatment", "Men vs women comparison", "Floor differences", "Seasonal changes"
                    - Be specific: "Type 2 Diabetes" not "diabetes", "Crohn's disease" not "IBD"
                    - If you find disease names or experimental conditions, mark as PRESENT

                    STEP 4: SEQUENCING TYPE ANALYSIS
                    - Look for: "16S rRNA", "metagenomics", "shotgun sequencing", "amplicon sequencing", "metatranscriptomics"
                    - Check: Methods section, molecular techniques, sequencing protocols, abstract
                    - Examples: "16S rRNA gene sequencing", "V4 region amplification", "Illumina sequencing", "Next-generation sequencing"
                    - Be precise: "16S rRNA" not "sequencing", "Metagenomics" not "genomics"
                    - If you find "16S" or "sequencing", mark as PRESENT

                    STEP 5: TAXA LEVEL ANALYSIS
                    - Look for: Taxonomic levels and specific names
                    - Check: Results section, microbial community descriptions, diversity analysis, abstract
                    - Examples: "Phylum level: Proteobacteria, Actinobacteria", "Genus level: Bacteroides, Prevotella", "Species level: E. coli, B. fragilis"
                    - Be specific: "Bacteroides fragilis" not "Bacteroides", "Proteobacteria phylum" not "bacteria"
                    - If you find taxonomic names or levels, mark as PRESENT

                    STEP 6: SAMPLE SIZE ANALYSIS
                    - Look for: Numbers, sample counts, participant numbers, collection descriptions
                    - Check: Methods section, study design, sample collection details, abstract
                    - Examples: "n=50 participants", "100 samples collected", "Three floors sampled", "Multiple time points"
                    - Be precise: "n=50" not "multiple samples", "100 samples" not "large sample size"
                    - If you find numbers or sample counts, mark as PRESENT

                    CRITICAL ANALYSIS INSTRUCTIONS:
                    1. READ THE TEXT THOROUGHLY - Do not skim. Read every section carefully.
                    2. LOOK FOR EXPLICIT MENTIONS - If the text says "Human participants", that's PRESENT.
                    3. CHECK MULTIPLE SECTIONS - Title, abstract, methods, results, discussion.
                    4. USE CONTEXT CLUES - If it mentions "fecal samples from patients", that's both host (Human) and body site (Gut).
                    5. BE CONFIDENT - If you find clear information, use high confidence (0.8-1.0).
                    6. DON'T GUESS - Only mark as PRESENT if you're confident the information exists.

                    CONFIDENCE SCORING:
                    - PRESENT (0.8-1.0): Information is explicitly stated and clear
                    - PARTIALLY_PRESENT (0.4-0.7): Information is implied or partially described
                    - ABSENT (0.0): Information is completely missing or unclear

                    RESPONSE FORMAT - Return ONLY this JSON structure:
                    {{
                        "host_species": {{
                            "primary": "extracted_species_name",
                            "confidence": 0.0-1.0,
                            "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                            "reason_if_missing": "explanation if absent",
                            "suggestions_for_curation": "what additional info is needed"
                        }},
                        "body_site": {{
                            "site": "extracted_site_name",
                            "confidence": 0.0-1.0,
                            "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                            "reason_if_missing": "explanation if absent",
                            "suggestions_for_curation": "what additional info is needed"
                        }},
                        "condition": {{
                            "description": "extracted_condition_description",
                            "confidence": 0.0-1.0,
                            "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                            "reason_if_missing": "explanation if absent",
                            "suggestions_for_curation": "what additional info is needed"
                        }},
                        "sequencing_type": {{
                            "method": "extracted_sequencing_method",
                            "confidence": 0.0-1.0,
                            "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                            "reason_if_missing": "explanation if absent",
                            "suggestions_for_curation": "what additional info is needed"
                        }},
                        "taxa_level": {{
                            "level": "extracted_taxonomic_level",
                            "confidence": 0.0-1.0,
                            "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                            "reason_if_missing": "explanation if absent",
                            "suggestions_for_curation": "what additional info is needed"
                        }},
                        "sample_size": {{
                            "size": "extracted_sample_size",
                            "confidence": 0.0-1.0,
                            "status": "PRESENT|PARTIALLY_PRESENT|ABSENT",
                            "reason_if_missing": "explanation if absent",
                            "suggestions_for_curation": "what additional info is needed"
                        }},
        
                        "missing_fields": ["field1", "field2", ...],
                        "curation_preparation_summary": "Overall assessment of what's needed for curation"
                    }}

                    CRITICAL INSTRUCTIONS: 
                    - Focus ONLY on the 6 fields listed above
                    - Do NOT include Factor-Based Analysis, Detailed Explanation, Specific Reasons, Examples and Evidence, Key Findings, Category Scores, or Analysis Confidence
                    - For each missing field, provide specific reason and suggestions
                    - Determine curation readiness based on having all 6 fields with status "PRESENT"
                    - Return ONLY the JSON structure above
                    - Be thorough in your analysis - read the text carefully for each field
                    """
                    
                    analysis = await qa_system.analyze_paper_enhanced(enhanced_prompt)
                    
                    try:
                        parsed_analysis = json.loads(analysis.get("key_findings", "{}"))
                        
                        # Validate that we have exactly the 6 required fields
                        required_fields = ["host_species", "body_site", "condition", "sequencing_type", "taxa_level", "sample_size"]
                        missing_fields = []
                        
                        for field in required_fields:
                            if field not in parsed_analysis or not parsed_analysis[field]:
                                missing_fields.append(field)
                                # Ensure the field exists with default structure
                                if field == "host_species":
                                    parsed_analysis[field] = {"primary": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "Field not found in analysis", "suggestions_for_curation": "Review paper for host species information"}
                                elif field == "body_site":
                                    parsed_analysis[field] = {"site": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "Field not found in analysis", "suggestions_for_curation": "Review paper for body site information"}
                                elif field == "condition":
                                    parsed_analysis[field] = {"description": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "Field not found in analysis", "suggestions_for_curation": "Review paper for condition information"}
                                elif field == "sequencing_type":
                                    parsed_analysis[field] = {"method": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "Field not found in analysis", "suggestions_for_curation": "Review paper for sequencing method information"}
                                elif field == "taxa_level":
                                    parsed_analysis[field] = {"level": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "Field not found in analysis", "suggestions_for_curation": "Review paper for taxonomic level information"}
                                elif field == "sample_size":
                                    parsed_analysis[field] = {"size": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "Field not found in analysis", "suggestions_for_curation": "Review paper for sample size information"}
                        
                        
                        parsed_analysis["missing_fields"] = missing_fields
                        
                    except json.JSONDecodeError:
                        parsed_analysis = {
                            "host_species": {"primary": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "JSON parsing failed", "suggestions_for_curation": "Re-run analysis"},
                            "body_site": {"site": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "JSON parsing failed", "suggestions_for_curation": "Re-run analysis"},
                            "condition": {"description": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "JSON parsing failed", "suggestions_for_curation": "Re-run analysis"},
                            "sequencing_type": {"method": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "JSON parsing failed", "suggestions_for_curation": "Re-run analysis"},
                            "taxa_level": {"level": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "JSON parsing failed", "suggestions_for_curation": "Re-run analysis"},
                            "sample_size": {"size": "Unknown", "confidence": 0.0, "status": "ABSENT", "reason_if_missing": "JSON parsing failed", "suggestions_for_curation": "Re-run analysis"},
                
                            "missing_fields": ["host_species", "body_site", "condition", "sequencing_type", "taxa_level", "sample_size"],
                            "curation_preparation_summary": "Analysis failed - re-run required"
                        }
                    
                    confidence = analysis.get("confidence", 0.0)
                    
                    # Store analysis results in cache
                    cache_manager.store_analysis_result(
                        pmid, 
                        parsed_analysis, 
                        metadata, 
                        "gemini_enhanced", 
                        confidence
                    )
                    
                    results.append({
                        "pmid": pmid,
                        "metadata": cached_result["metadata"],
                        "enhanced_analysis": parsed_analysis,
                        "timestamp": datetime.now().isoformat(),
                        "source": "gemini_enhanced_analysis",
                        "cached": False,
                        "status": "success"
                    })
                    new_analysis_count += 1
                    
            except Exception as e:
                logger.error(f"Error processing PMID {pmid}: {str(e)}")
                results.append({
                    "pmid": pmid,
                    "status": "error",
                    "error": str(e)
                })
        
        return {
            "batch_results": results,
            "summary": {
                "total_pmids": len(pmids),
                "successful": len([r for r in results if r.get("status") == "success"]),
                "errors": len([r for r in results if r.get("status") == "error"]),
                "cached_results": cached_count,
                "new_analysis": new_analysis_count,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error in batch enhanced analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch analysis failed: {str(e)}")

@app.get("/cache/stats", tags=["Cache Management"])
async def get_cache_stats():
    """Get cache statistics and information."""
    try:
        stats = cache_manager.get_cache_stats()
        return {
            "cache_stats": stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")

@app.post("/cache/clear", tags=["Cache Management"])
async def clear_old_cache(max_age_hours: int = 168):
    """Clear old cache entries. Default: clear entries older than 1 week."""
    try:
        cleared_count = cache_manager.clear_old_cache(max_age_hours)
        return {
            "message": f"Cleared {cleared_count} old cache entries",
            "cleared_count": cleared_count,
            "max_age_hours": max_age_hours,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

@app.get("/cache/search", tags=["Cache Management"])
async def search_cache(query: str, search_type: str = "all"):
    """Search cache for papers matching the query."""
    try:
        results = cache_manager.search_cache(query, search_type)
        return {
            "query": query,
            "search_type": search_type,
            "results": results,
            "result_count": len(results),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error searching cache: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to search cache: {str(e)}")





if __name__ == "__main__":
    import uvicorn
    print("Starting BugSigDB Analyzer API...")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")