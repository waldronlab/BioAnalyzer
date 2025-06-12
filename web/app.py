from fastapi import FastAPI, WebSocket, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.websockets import WebSocketDisconnect
from pydantic import BaseModel
from typing import Dict, List, Optional
import json
import torch
from pathlib import Path
from datetime import datetime
import pytz
from models.config import ModelConfig
from models.conversation_model import ConversationalBugSigModel
from models.intent_classifier import IntentClassifier  # New import
from models.unified_qa import UnifiedQA
from retrieve.data_retrieval import PubMedRetriever
from utils.text_processing import AdvancedTextProcessor
from utils.user_manager import UserManager
from utils.config import NCBI_API_KEY, GEMINI_API_KEY, SUPERSTUDIO_API_KEY, SUPERSTUDIO_URL
import re

app = FastAPI(title="BugSigDB Analyzer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

user_manager = UserManager()
text_processor = AdvancedTextProcessor()

# Load models
# model_path = Path("models/conversation_model/best_model.pt")
# if model_path.exists():
#     # Add ModelConfig to safe globals for PyTorch 2.6+ compatibility
#     torch.serialization.add_safe_globals([ModelConfig])
#     checkpoint = torch.load(model_path, weights_only=False)
#     config = checkpoint['config']
#     model = ConversationalBugSigModel.load_from_pretrained(checkpoint)
#     model.eval()
# else:
#     print("Warning: Model checkpoint not found. Running in limited functionality mode.")
#     model = None

# Skip local model entirely and use Gemini exclusively
model = None
print("Info: Using Gemini API exclusively (local model disabled)")

intent_classifier = IntentClassifier()
if Path("models/intent_classifier/model.pt").exists():
    intent_classifier.model.load_state_dict(torch.load("models/intent_classifier/model.pt"))
intent_classifier.eval()

# Initialize PubMedRetriever with NCBI API key
retriever = PubMedRetriever(api_key=NCBI_API_KEY)

# Initialize UnifiedQA with SuperStudio API key
qa_system = UnifiedQA(
    use_biobert=True, 
    use_superstudio=True,
    use_gemini=True,
    superstudio_api_key=SUPERSTUDIO_API_KEY,
    gemini_api_key=GEMINI_API_KEY
)

# Initialize Gemini for chat using SuperStudio
from models.gemini_qa import GeminiQA
gemini_chat = GeminiQA(
    api_key=GEMINI_API_KEY,
    model="gemini-pro"
)

class Message(BaseModel):
    content: str
    role: str = "user"

class Question(BaseModel):
    question: str

@app.get("/")
async def root():
    return {
        "name": "BugSigDB Analyzer API",
        "version": "1.0.0",
        "description": "API for analyzing papers for microbial signatures"
    }

@app.post("/start_session/{name}")
async def start_session(name: str):
    session = user_manager.start_session(name)
    return {"message": f"Welcome {name}!", "session": session.to_dict()}

@app.get("/analyze/{pmid}")
async def analyze_paper(pmid: str, request: Request):
    try:
        # Extract username from request cookies or query params
        username = None
        if "username" in request.cookies:
            username = request.cookies["username"]
        elif "username" in request.query_params:
            username = request.query_params["username"]
        
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
        
        # Use Gemini for analysis if available
        try:
            results = await qa_system.analyze_paper(paper_content)
        except Exception as e:
            print(f"Error in paper analysis: {str(e)}")
            # Return a partial result with error information
            return {
                "metadata": metadata,
                "analysis": {
                    "error": str(e),
                    "confidence": 0.0,
                    "status": "error",
                    "key_findings": ["Error analyzing paper"],
                    "suggested_topics": [],
                    "found_terms": {},
                    "category_scores": {},
                    "num_tokens": 0
                }
            }
        
        # Prefer Gemini results if available, otherwise use biobert
        analysis_results = results.get("gemini", results.get("biobert", {}))
        
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
        
        # If we have a valid username, update the user session
        if username:
            try:
                session = user_manager.get_session(username)
                if session:
                    session.set_current_paper(pmid)
                    user_manager.save_session(username)
                    print(f"Set current paper for {username} to {pmid}")
                else:
                    # Create a new session if needed
                    session = user_manager.start_session(username)
                    session.set_current_paper(pmid)
                    user_manager.save_session(username)
                    print(f"Created new session for {username} and set paper to {pmid}")
            except Exception as e:
                print(f"Error updating user session for {username}: {str(e)}")
                # Continue without updating the session
        
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

@app.websocket("/ws/{name}")
async def websocket_endpoint(websocket: WebSocket, name: str):
    await websocket.accept()
    print(f"WebSocket connection accepted for {name}")
    
    session = user_manager.get_session(name)
    if not session:
        print(f"Session not found for {name}, creating new session")
        session = user_manager.start_session(name)
    
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Received message from {name}: {data[:100]}...")
            
            try:
                message = json.loads(data)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from {name}: {str(e)}")
                await websocket.send_text(json.dumps({
                    "error": "Invalid message format. Please send valid JSON."
                }))
                continue
            
            # Check if message contains current paper info
            if "currentPaper" in message:
                pmid = message["currentPaper"]
                session.set_current_paper(pmid)
                user_manager.save_session(name)
                print(f"Updated current paper for {name} to {pmid} from chat message")
            
            # Get chat history for context
            chat_history = []
            if hasattr(session, "memory") and hasattr(session.memory, "messages"):
                chat_history = session.memory.messages[-5:] if len(session.memory.messages) > 5 else session.memory.messages
            
            # Get current paper context if available
            paper_context = None
            current_paper = message.get("currentPaper") or (hasattr(session, "current_paper") and session.current_paper)
            
            if current_paper:
                try:
                    pmid = current_paper
                    metadata = retriever.get_paper_metadata(pmid)
                    paper_context = {
                        "pmid": pmid,
                        "title": metadata.get("title", ""),
                        "abstract": metadata.get("abstract", "")
                    }
                    print(f"Using paper context for PMID: {pmid}")
                except Exception as e:
                    print(f"Error getting paper context: {str(e)}")
                    # Continue without paper context
                    paper_context = {
                        "pmid": pmid,
                        "title": "Unknown paper",
                        "abstract": "Unable to retrieve paper abstract"
                    }
            
            try:
                print(f"Calling Gemini chat_with_context for {name}")
                # Try using Gemini API with the new method
                result = await gemini_chat.chat_with_context(
                    message=message["content"],
                    chat_history=chat_history,
                    paper_context=paper_context
                )
                
                response_text = result["response"]
                print(f"Generated response: {response_text[:100]}...")
                
            except Exception as e:
                print(f"Gemini API error: {str(e)}. Falling back to local model.")
                # Fall back to the local model if Gemini fails
                if model is None:
                    response_text = f"Sorry, the model is not available. Running in limited functionality mode. Error: {str(e)}"
                else:
                    # Classify intent
                    intent = intent_classifier.classify(message['content'])
                    
                    if intent == "greeting":
                        eat_tz = pytz.timezone('Africa/Nairobi')
                        current_hour = datetime.now(eat_tz).hour
                        if "morning" in message['content'].lower() and current_hour < 12:
                            response_text = "Good morning! How can I help you today?"
                        elif current_hour < 17:
                            response_text = "Good afternoon! How can I assist you?"
                        else:
                            response_text = "Good evening! What's on your mind?"
                    else:
                        query_ids = text_processor.encode_text(message['content'])
                        response = model.generate_response(
                            query_ids=query_ids,
                            temperature=0.7,
                            max_length=100
                        )
                        response_text = text_processor.decode_tokens(response['response_ids'])
            
            await websocket.send_text(json.dumps({
                "response": response_text,
                "timestamp": datetime.now().isoformat()
            }))
            
            session.memory.add_message(role="user", content=message['content'])
            session.memory.add_message(role="assistant", content=response_text)
            print(f"Response sent to {name}")
            
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for {name}")
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        try:
            await websocket.send_text(json.dumps({"error": str(e)}))
        except:
            print(f"Failed to send error message to {name}")
    finally:
        user_manager.save_session(name)
        try:
            await websocket.close()
        except:
            pass

@app.post("/ask_question/{pmid}")
async def ask_question(pmid: str, question: Question):
    """Answer questions about a specific paper using Gemini"""
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
        
        # Use Gemini to answer the question
        try:
            answer = await gemini_chat.get_answer(question.question, context)
        except Exception as e:
            print(f"Error from Gemini API: {str(e)}")
            # Return a graceful error message
            return {
                "answer": f"I'm sorry, I encountered an error while processing your question. Please try again later. Error: {str(e)}",
                "confidence": 0.1
            }
        
        return {
            "answer": answer["answer"],
            "confidence": answer["confidence"]
        }
    except HTTPException as he:
        # Re-raise HTTP exceptions
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
        
        # Prefer Gemini results if available, otherwise use biobert
        analysis_results = results.get("gemini", results.get("biobert", {}))
        
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

if __name__ == "__main__":
    import uvicorn
    print("Starting BugSigDB Analyzer API...")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")