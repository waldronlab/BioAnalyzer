from fastapi import FastAPI, WebSocket, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.websockets import WebSocketDisconnect
from fastapi.responses import RedirectResponse
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

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

text_processor = AdvancedTextProcessor()

# Skip local model
model = None
print(f"Model Status: Using {DEFAULT_MODEL} as primary model")

# Initialize PubMedRetriever with NCBI API key
retriever = PubMedRetriever(api_key=NCBI_API_KEY)

class Message(BaseModel):
    content: str
    role: str = "user"
    model: Optional[str] = None

class Question(BaseModel):
    question: str

@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

@app.get("/analyze/{pmid}")
async def analyze_paper(pmid: str, request: Request):
    try:
        # Get metadata and full text
        try:
            metadata = retriever.get_paper_metadata(pmid)
            if not metadata:
                raise HTTPException(status_code=404, detail=f"Paper with PMID {pmid} not found")
        except Exception as e:
            print(f"Error retrieving metadata for PMID {pmid}: {str(e)}")
            raise HTTPException(status_code=404, detail=f"Error retrieving paper metadata: {str(e)}")
        
        # Try to get full text, but continue if not available
        full_text = ""
        try:
            full_text = retriever.get_pmc_fulltext(pmid)
        except Exception as e:
            print(f"Warning: Could not retrieve full text for PMID {pmid}: {str(e)}")
            # Continue with just the abstract
        
        paper_content = {
            "title": metadata["title"],
            "abstract": metadata["abstract"],
            "full_text": full_text if full_text else ""
        }
        
        # Try models in order of preference
        models_to_try = ["openai"] if model_config.openai_available else []
        
        results = {}
        error_message = None
        
        for model_name in models_to_try:
            try:
                if model_name == "openai" and model_config.openai_available:
                    print(f"Attempting to use OpenAI for paper analysis")
                    # Use OpenAI for analysis
                    response = await client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant analyzing scientific papers. Extract key findings, suggested topics, and categorize the content."},
                            {"role": "user", "content": f"Analyze this paper:\nTitle: {paper_content['title']}\nAbstract: {paper_content['abstract']}\nFull Text: {paper_content['full_text']}"}
                        ],
                        temperature=0.7,
                        max_tokens=1000
                    )
                    
                    # Parse OpenAI response into analysis format
                    analysis_text = response.choices[0].message.content
                    results["openai"] = {
                        "key_findings": [line.strip() for line in analysis_text.split('\n') if line.strip()],
                        "confidence": 0.8,
                        "status": "success",
                        "suggested_topics": [],
                        "found_terms": {},
                        "category_scores": {},
                        "num_tokens": len(analysis_text.split())
                    }
                    break
                    
            except Exception as e:
                error_str = str(e)
                print(f"Error with {model_name}: {error_str}")
                if "insufficient_quota" in error_str:
                    error_message = "OpenAI API quota exceeded. Please check your billing details or try again later."
                else:
                    error_message = str(e)
                continue
        
        if not results:
            # Return a partial result with error information
            return {
                "metadata": metadata,
                "analysis": {
                    "error": error_message or "All AI models are currently unavailable",
                    "confidence": 0.0,
                    "status": "error",
                    "key_findings": ["Unable to analyze paper at this time. Please try again later or contact support if the issue persists."],
                    "suggested_topics": [],
                    "found_terms": {},
                    "category_scores": {},
                    "num_tokens": 0
                }
            }
        
        # Prefer OpenAI results if available
        analysis_results = results.get("openai", {})
        
        # Add additional fields for the paper analysis details table
        # Extract these from the analysis if possible, or set defaults
        found_terms = analysis_results.get("found_terms", {})
        
        # Add host information
        if "host" not in analysis_results and "host" in found_terms and found_terms["host"]:
            analysis_results["host"] = found_terms["host"][0]
            
        # Add body site information
        if "body_site" not in analysis_results and "body site" in found_terms and found_terms["body site"]:
            analysis_results["body_site"] = found_terms["body site"][0]
            
        # Add condition information
        if "condition" not in analysis_results and "condition" in found_terms and found_terms["condition"]:
            analysis_results["condition"] = found_terms["condition"][0]
            
        # Add sequencing type information
        if "sequencing_type" not in analysis_results and "sequencing type" in found_terms and found_terms["sequencing type"]:
            analysis_results["sequencing_type"] = found_terms["sequencing type"][0]
        
        # Add sample size information
        if "sample_size" not in analysis_results:
            # Try to extract from found terms
            if "sample size" in found_terms and found_terms["sample size"]:
                analysis_results["sample_size"] = found_terms["sample size"][0]
            else:
                # Try to extract from key findings or abstract
                sample_size_pattern = r'(\d+)\s+(?:subjects|participants|samples|patients)'
                key_findings = analysis_results.get("key_findings", [])
                for finding in key_findings:
                    if isinstance(finding, str):
                        match = re.search(sample_size_pattern, finding, re.IGNORECASE)
                        if match:
                            analysis_results["sample_size"] = match.group(1)
                            break
                
                # If not found in key findings, try abstract
                if "sample_size" not in analysis_results and "abstract" in paper_content:
                    match = re.search(sample_size_pattern, paper_content["abstract"], re.IGNORECASE)
                    if match:
                        analysis_results["sample_size"] = match.group(1)
        
        # Add taxa level information
        if "taxa_level" not in analysis_results:
            # Try to extract from found terms
            for term_key in ["taxa level", "taxonomic level"]:
                if term_key in found_terms and found_terms[term_key]:
                    analysis_results["taxa_level"] = found_terms[term_key][0]
                    break
            
            # If not found in found terms, look for common taxonomic levels
            if "taxa_level" not in analysis_results:
                taxa_levels = ["phylum", "class", "order", "family", "genus", "species", "strain"]
                for level in taxa_levels:
                    if level in found_terms and found_terms[level]:
                        analysis_results["taxa_level"] = level
                        break
        
        # Add statistical method information
        if "statistical_method" not in analysis_results:
            # Try to extract from found terms
            for term_key in ["statistical method", "statistics", "analysis method"]:
                if term_key in found_terms and found_terms[term_key]:
                    analysis_results["statistical_method"] = found_terms[term_key][0]
                    break
            
            # If not found, look for common statistical methods
            if "statistical_method" not in analysis_results:
                stat_methods = ["PERMANOVA", "ANOVA", "t-test", "Wilcoxon", "LEfSe", "DESeq2", "random forest"]
                for method in stat_methods:
                    method_pattern = re.compile(r'\b' + re.escape(method) + r'\b', re.IGNORECASE)
                    if "abstract" in paper_content and method_pattern.search(paper_content["abstract"]):
                        analysis_results["statistical_method"] = method
                        break
        
        # Check if paper is in BugSigDB (this would need actual integration with BugSigDB)
        if "in_bugsigdb" not in analysis_results:
            # This is a placeholder - in a real implementation, you would check against the BugSigDB database
            analysis_results["in_bugsigdb"] = "No"
            
        # Calculate signature probability if not already present
        if "signature_probability" not in analysis_results:
            # Use confidence as a proxy if available, or calculate based on other metrics
            confidence = analysis_results.get("confidence", 0)
            category_scores = analysis_results.get("category_scores", {})
            signature_score = category_scores.get("signature_presence", 0)
            
            # Use the higher of confidence or signature_score
            signature_probability = max(confidence, signature_score)
            analysis_results["signature_probability"] = f"{signature_probability * 100:.1f}%"
        
        return {
            "metadata": metadata,
            "analysis": analysis_results
        }
    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise he
    except Exception as e:
        print(f"Unexpected error in analyze_paper endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing paper: {str(e)}")

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
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                response = await process_message(message)
                await websocket.send_json(response)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON format"})
            except Exception as e:
                await websocket.send_json({"error": str(e)})
    except WebSocketDisconnect:
        print("WebSocket disconnected")

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

if __name__ == "__main__":
    import uvicorn
    print("Starting BugSigDB Analyzer API...")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")