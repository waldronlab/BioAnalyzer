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
    OPENAI_API_KEY, 
    DEFAULT_MODEL,
    AVAILABLE_MODELS
)
import re
import openai
import asyncio
import logging
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BugSigDB Analyzer")

# Configure API keys
openai.api_key = OPENAI_API_KEY
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Model configuration
class ModelConfig:
    def __init__(self):
        self.openai_available = bool(OPENAI_API_KEY)
        self.available_models = []
        self.default_model = None
        self.initialize_models()

    def initialize_models(self):
        # Initialize OpenAI
        if self.openai_available:
            self.available_models.append("openai")
            self.default_model = "openai"
            print("OpenAI model initialized successfully")

        print(f"Available models: {self.available_models}")
        print(f"Default model: {self.default_model}")

    def get_model(self, preferred_model: Optional[str] = None) -> str:
        """Get the model to use, considering preferences and availability"""
        if preferred_model and preferred_model in self.available_models:
            return preferred_model
        return self.default_model

    def is_model_available(self, model_name: str) -> bool:
        """Check if a specific model is available"""
        return model_name in self.available_models

# Initialize model configuration
model_config = ModelConfig()

# Initialize UnifiedQA with OpenAI only
qa_system = UnifiedQA(
    use_openai=model_config.openai_available,
    use_gemini=False,
    openai_api_key=OPENAI_API_KEY,
    gemini_api_key=None
)

# Update available models based on successful initialization
AVAILABLE_MODELS = model_config.available_models
DEFAULT_MODEL = model_config.default_model

print(f"Final available models: {AVAILABLE_MODELS}")
print(f"Final default model: {DEFAULT_MODEL}")

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
print(f"Model Status: Using {DEFAULT_MODEL} as primary model")
retriever = PubMedRetriever(api_key=NCBI_API_KEY)

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
    """Process incoming WebSocket messages"""
    try:
        content = message.get('content', '')
        current_paper = message.get('currentPaper')
        
        if not content:
            return {"error": "No message content provided"}
            
        # Create context from current paper if available
        context = ""
        if current_paper:
            try:
                metadata = retriever.get_paper_metadata(current_paper)
                if metadata:
                    context = f"Title: {metadata['title']}\nAbstract: {metadata['abstract']}"
            except Exception as e:
                print(f"Error getting paper metadata: {str(e)}")
        
        # Use OpenAI for chat
        if model_config.openai_available:
            try:
                response = await client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant analyzing scientific papers. " + 
                         ("Here is the current paper context:\n" + context if context else "")},
                        {"role": "user", "content": content}
                    ],
                    temperature=0.7,
                    max_tokens=500
                )
                return {"response": response.choices[0].message.content}
            except Exception as e:
                print(f"Error with OpenAI: {str(e)}")
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
                        
                        # Analyze paper using OpenAI
                        if model_config.openai_available:
                            response = await client.chat.completions.create(
                                model="gpt-3.5-turbo",
                                messages=[
                                    {"role": "system", "content": "You are a helpful assistant analyzing scientific papers. Extract key findings, suggested topics, and categorize the content."},
                                    {"role": "user", "content": f"Analyze this paper:\nTitle: {metadata['title']}\nAbstract: {metadata['abstract']}\nFull Text: {full_text}"}
                                ],
                                temperature=0.7,
                                max_tokens=1000
                            )
                            
                            analysis_text = response.choices[0].message.content
                            analysis_result = {
                                "type": "analysis_result",
                                "title": metadata["title"],
                                "authors": metadata.get("authors", "N/A"),
                                "journal": metadata.get("journal", "N/A"),
                                "date": metadata.get("publication_date", "N/A"),
                                "doi": metadata.get("doi", "N/A"),
                                "abstract": metadata.get("abstract", "N/A"),
                                "key_findings": [line.strip() for line in analysis_text.split('\n') if line.strip()],
                                "confidence": 0.8,
                                "status": "success",
                                "suggested_topics": [],
                                "found_terms": {},
                                "category_scores": {},
                                "num_tokens": len(analysis_text.split())
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
        models_to_try = ["openai"] if "openai" in AVAILABLE_MODELS else AVAILABLE_MODELS
        answer = None
        confidence = 0.0
        
        for model_name in models_to_try:
            try:
                if model_name == "openai" and model_config.openai_available:
                    print(f"Attempting to use OpenAI for question answering")
                    response = await client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": f"You are a helpful assistant analyzing a scientific paper. Here is the paper content:\n\n{context}"},
                            {"role": "user", "content": question.question}
                        ],
                        temperature=0.7,
                        max_tokens=500
                    )
                    answer = response.choices[0].message.content
                    confidence = 0.8  # OpenAI responses are generally reliable
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
            # For PDF files, we would use a PDF parser here
            # This is a placeholder for actual PDF parsing
            paper_content = {
                "title": "Extracted from PDF",
                "abstract": "Abstract would be extracted from the PDF",
                "full_text": "Full text would be extracted from the PDF"
            }
        else:
            # For text files, use the content directly
            text_content = content.decode("utf-8")
            paper_content = {
                "title": file.filename,
                "abstract": text_content[:500] + "...",  # Use first 500 chars as abstract
                "full_text": text_content
            }
        
        # Use QA system to analyze the paper
        results = await qa_system.analyze_paper(paper_content)
        
        # Prefer OpenAI results if available
        analysis_results = results.get("openai", {})
        
        # Add additional fields for curation
        analysis_results["taxa"] = extract_taxa(paper_content["full_text"])
        
        # Create response with metadata and analysis
        response = {
            "metadata": {
                "title": paper_content["title"],
                "abstract": paper_content["abstract"],
                "pmid": "",  # No PMID for uploaded files
                "doi": "",   # No DOI for uploaded files
                "publication_date": ""  # No date for uploaded files
            },
            "analysis": analysis_results
        }
        
        # If username is provided, update user session
        if username:
            try:
                session = user_manager.get_session(username)
                if not session:
                    session = user_manager.start_session(username)
                session.set_current_paper(file.filename)  # Use filename as identifier
                user_manager.save_session(username)
            except Exception as e:
                print(f"Error updating user session for {username}: {str(e)}")
        
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
            "available_models": model_config.available_models,
            "default_model": model_config.default_model,
            "openai_available": model_config.openai_available,
            "gemini_available": False,  # Commented out Gemini
            "openai_key_present": bool(OPENAI_API_KEY),
            "gemini_key_present": False  # Commented out Gemini
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
    return {"message": "BugSigDB Analyzer API is running"}

@app.get("/analyze/{pmid}")
async def analyze_paper(pmid: str, request: Request):
    try:
        logger.info(f"=== Starting analysis for PMID: {pmid} ===")
        
        # Get paper metadata
        logger.info(f"Fetching metadata for PMID: {pmid}")
        metadata = retriever.get_paper_metadata(pmid)
        
        if not metadata:
            raise HTTPException(status_code=404, detail="Paper not found")
            
        logger.info(f"Successfully retrieved metadata: {metadata.get('title', 'No title')}")
        
        # Try to get full text (optional)
        try:
            logger.info(f"Attempting to fetch full text for PMID: {pmid}")
            full_text = retriever.get_pmc_fulltext(pmid)
        except Exception as e:
            logger.warning(f"Failed to retrieve PMC full text for PMID {pmid}: {str(e)}")
            full_text = None
            
        # Prepare response
        response = {
            "metadata": metadata,
            "analysis": {
                "status": "success",
                "confidence": 0.85,  # Example confidence score
                "category_scores": {
                    "relevance": 0.9,
                    "methodology": 0.8,
                    "significance": 0.75
                },
                "key_findings": [
                    "Finding 1",
                    "Finding 2",
                    "Finding 3"
                ],
                "suggested_topics": [
                    "Topic 1",
                    "Topic 2",
                    "Topic 3"
                ]
            }
        }
        
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Error analyzing paper {pmid}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("Starting BugSigDB Analyzer API...")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")