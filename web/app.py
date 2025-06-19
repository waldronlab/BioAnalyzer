from fastapi import FastAPI, WebSocket, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.websockets import WebSocketDisconnect
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
import json
import torch
from pathlib import Path
from datetime import datetime
import pytz
from models.config import ModelConfig
from models.conversation_model import ConversationalBugSigModel
from models.unified_qa import UnifiedQA
from retrieve.data_retrieval import PubMedRetriever
from utils.text_processing import AdvancedTextProcessor
from utils.config import (
    NCBI_API_KEY, 
    GEMINI_API_KEY, 
    DEFAULT_MODEL,
    AVAILABLE_MODELS
)
import re
import asyncio
import logging
import sys
import os
from bs4 import BeautifulSoup

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BugSigDB Analyzer")

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

# Mount static files after API routes
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

class Message(BaseModel):
    content: str
    role: str = "user"
    model: Optional[str] = None

class Question(BaseModel):
    question: str

async def process_message(message):
    try:
        content = message.get('content', '')
        current_paper = message.get('currentPaper')
        if not content:
            return {"error": "No message content provided"}
        context = ""
        if current_paper:
            try:
                metadata = retriever.get_paper_metadata(current_paper)
                if metadata:
                    context = f"Title: {metadata['title']}\nAbstract: {metadata['abstract']}"
            except Exception as e:
                print(f"Error getting paper metadata: {str(e)}")
        # Use Gemini for chat (simulate with analyze_paper for now)
        if GEMINI_API_KEY:
            try:
                # For chat, we can use the same analyze_paper logic for now
                paper_content = {"title": context, "abstract": content, "full_text": ""}
                response = await qa_system.analyze_paper(paper_content)
                return {"response": "\n".join(response.get("key_findings", []))}
            except Exception as e:
                print(f"Error with Gemini: {str(e)}")
                return {"error": f"Error processing message: {str(e)}"}
        else:
            return {"error": "No AI models available"}
    except Exception as e:
        print(f"Error processing message: {str(e)}")
        return {"error": str(e)}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
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
                            await websocket.send_json(analysis_result)
                        else:
                            await websocket.send_json({"error": "No AI models available for analysis"})
                    except Exception as e:
                        print(f"Error analyzing paper: {str(e)}")
                        await websocket.send_json({"error": f"Error analyzing paper: {str(e)}"})
                else:
                    # Handle chat messages
                    response = await process_message(message)
                    await websocket.send_json(response)
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

@app.post("/ask_question/{pmid}")
async def ask_question(pmid: str, question: Question):
    """Answer questions about a specific paper using available AI models"""
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

@app.post("/upload_paper")
async def upload_paper(file: UploadFile = File(...), username: str = Form(None)):
    """Upload a paper file (PDF or text) and extract information for curation"""
    try:
        # Check file type
        if file.content_type not in ["application/pdf", "text/plain"]:
            raise HTTPException(status_code=400, detail="Only PDF and text files are supported")
        # Read file content
        content = await file.read()
        # Process the file based on type
        if file.content_type == "application/pdf":
            paper_content = {
                "title": "Extracted from PDF",
                "abstract": "Abstract would be extracted from the PDF",
                "full_text": "Full text would be extracted from the PDF"
            }
        else:
            text_content = content.decode("utf-8")
            paper_content = {
                "title": file.filename,
                "abstract": text_content[:500] + "...",
                "full_text": text_content
            }
        # Use QA system to analyze the paper
        results = await qa_system.analyze_paper(paper_content)
        analysis_results = results.get("gemini", {})
        analysis_results["taxa"] = extract_taxa(paper_content["full_text"])
        response = {
            "metadata": {
                "title": paper_content["title"],
                "abstract": paper_content["abstract"],
                "pmid": "",
                "doi": "",
                "publication_date": ""
            },
            "analysis": analysis_results
        }
        return response
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error processing uploaded file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.get("/fetch_by_doi")
async def fetch_by_doi(doi: str, request: Request):
    """Fetch paper by DOI for curation"""
    try:
        # Extract username from request cookies or query params
        username = None
        if "username" in request.cookies:
            username = request.cookies["username"]
        elif "username" in request.query_params:
            username = request.query_params["username"]
        
        # Use PubMed retriever to get paper by DOI
        metadata = retriever.get_paper_by_doi(doi)
        if not metadata:
            raise HTTPException(status_code=404, detail=f"Paper with DOI {doi} not found")
        
        # Get PMID from metadata
        pmid = metadata.get("pmid")
        if not pmid:
            raise HTTPException(status_code=404, detail=f"PMID not found for DOI {doi}")
        
        # Use the analyze_paper function to get full analysis
        return await analyze_paper(pmid, request)
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error fetching paper by DOI: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching paper: {str(e)}")

@app.post("/submit_curation")
async def submit_curation(request: Request):
    """Submit paper curation to BugSigDB"""
    try:
        # Parse request body
        data = await request.json()
        
        # Validate required fields
        required_fields = ["pmid", "title", "host", "body_site", "condition", "sequencing_type"]
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            raise HTTPException(status_code=400, detail=f"Missing required fields: {', '.join(missing_fields)}")
        
        # In a real implementation, this would submit to BugSigDB API
        # For now, just log the submission
        print(f"Curation submitted: {data}")
        
        # Return success response
        return {"status": "success", "message": "Curation submitted successfully"}
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error submitting curation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error submitting curation: {str(e)}")

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

@app.get("/model_status")
async def get_model_status():
    """Get the status of available AI models."""
    try:
        status = {
            "available_models": AVAILABLE_MODELS,
            "default_model": DEFAULT_MODEL,
            "gemini_available": bool(GEMINI_API_KEY),
            "gemini_key_present": bool(GEMINI_API_KEY)
        }
        return status
    except Exception as e:
        print(f"Error getting model status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting model status: {str(e)}")

@app.get("/analyze_by_title")
async def analyze_by_title(title: str, request: Request):
    """Analyze a paper by its title"""
    try:
        # Search PubMed for the paper by title
        search_results = retriever.search_by_title(title)
        if not search_results:
            raise HTTPException(status_code=404, detail=f"No paper found with title: {title}")
        
        # Get the first result's PMID
        pmid = search_results[0].get('pmid')
        if not pmid:
            raise HTTPException(status_code=404, detail="No PMID found for the paper")
        
        # Use the existing analyze_paper endpoint
        return await analyze_paper(pmid, request)
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error analyzing paper by title: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing paper: {str(e)}")

@app.get("/analyze_by_url")
async def analyze_by_url(url: str, request: Request):
    """Analyze a paper by its URL (DOI or PubMed URL)"""
    try:
        # Extract DOI or PMID from URL
        doi = None
        pmid = None
        
        # Check if it's a DOI URL
        if "doi.org" in url:
            doi = url.split("doi.org/")[-1]
        # Check if it's a PubMed URL
        elif "pubmed.ncbi.nlm.nih.gov" in url:
            pmid = url.split("/")[-1]
        else:
            raise HTTPException(status_code=400, detail="Invalid URL format. Please provide a DOI or PubMed URL")
        
        if doi:
            # Use the existing fetch_by_doi endpoint
            return await fetch_by_doi(doi, request)
        elif pmid:
            # Use the existing analyze_paper endpoint
            return await analyze_paper(pmid, request)
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error analyzing paper by URL: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing paper: {str(e)}")

@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

@app.get("/analyze/{pmid}")
async def analyze_paper(pmid: str):
    warning = None
    error = None
    try:
        logger.info(f"=== Starting analysis for PMID: {pmid} ===")
        metadata = retriever.get_paper_metadata(pmid)
        if not metadata:
            return JSONResponse(content={"error": "Paper not found"}, status_code=200)
        logger.info(f"Successfully retrieved metadata: {metadata.get('title', 'No title')}")
        # Try to get full text (optional)
        try:
            logger.info(f"Attempting to fetch full text for PMID: {pmid}")
            full_text = retriever.get_pmc_fulltext(pmid)
            # Robustly handle different types
            if isinstance(full_text, str):
                try:
                    soup = BeautifulSoup(full_text, 'lxml')
                    full_text = retriever._extract_text_from_pmc_xml(soup)
                except Exception as e:
                    logger.warning(f"Failed to parse PMC XML for PMID {pmid}: {str(e)}")
            elif isinstance(full_text, list):
                logger.warning(f"PMC full text result is a list for PMID {pmid}, joining as string.")
                full_text = '\n'.join(str(x) for x in full_text)
            elif full_text is None:
                logger.warning(f"PMC full text result is None for PMID {pmid}.")
            else:
                logger.warning(f"PMC full text result is not a string or list: {type(full_text)}")
                full_text = str(full_text)
        except Exception as e:
            logger.warning(f"Failed to retrieve PMC full text for PMID {pmid}: {str(e)}")
            full_text = None
        paper_content = {
            "title": metadata.get("title", ""),
            "abstract": metadata.get("abstract", ""),
            "full_text": full_text or ""
        }
        # Run analysis using the QA system
        try:
            analysis = await qa_system.analyze_paper(paper_content)
            if analysis.get("error"):
                warning = (
                    "The Gemini API key has IP address restrictions. "
                    "Your current IP address is not authorized to use this API key. "
                    "Please update the API key in your .env file to one without IP restrictions or add your current IP to the allowed list."
                )
                analysis["warning"] = warning
        except Exception as e:
            logger.error(f"Error during analysis: {str(e)}")
            warning = (
                "The Gemini API key has IP address restrictions. "
                "Your current IP address is not authorized to use this API key. "
                "Please update the API key in your .env file to one without IP restrictions or add your current IP to the allowed list."
            )
            analysis = {
                "has_signatures": False,
                "confidence": 0.0,
                "key_findings": [],
                "suggested_topics": [],
                "category_scores": {
                    "microbiome": 0,
                    "methods": 0,
                    "analysis": 0,
                    "body_sites": 0,
                    "diseases": 0
                },
                "found_terms": {
                    "microbiome": [],
                    "methods": [],
                    "analysis": [],
                    "body_sites": [],
                    "diseases": []
                },
                "is_complete": False,
                "num_tokens": 0,
                "status": "error",
                "warning": warning,
                "error": str(e)
            }
            error = str(e)
        # Compose the response for the frontend
        response = {
            "pmid": pmid,
            "metadata": metadata,
            "analysis": analysis,
            "error": error,
            "warning": warning,
            "full_text_type": str(type(full_text)),
        }
        return JSONResponse(content=response)
    except Exception as e:
        logger.error(f"Error analyzing paper {pmid}: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=200)

if __name__ == "__main__":
    import uvicorn
    print("Starting BugSigDB Analyzer API...")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")