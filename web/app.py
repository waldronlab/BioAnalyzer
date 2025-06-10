from fastapi import FastAPI, WebSocket, HTTPException, Request
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
model_path = Path("models/conversation_model/best_model.pt")
if model_path.exists():
    # Add ModelConfig to safe globals for PyTorch 2.6+ compatibility
    torch.serialization.add_safe_globals([ModelConfig])
    checkpoint = torch.load(model_path, weights_only=False)
    config = checkpoint['config']
    model = ConversationalBugSigModel.load_from_pretrained(checkpoint)
    model.eval()
else:
    print("Warning: Model checkpoint not found. Running in limited functionality mode.")
    model = None

intent_classifier = IntentClassifier()
if Path("models/intent_classifier/model.pt").exists():
    intent_classifier.model.load_state_dict(torch.load("models/intent_classifier/model.pt"))
intent_classifier.eval()

# Initialize PubMedRetriever with NCBI API key
retriever = PubMedRetriever(api_key="30f325dac249c6e73498c0225d818105e008")

# Initialize UnifiedQA with SuperStudio API key
qa_system = UnifiedQA(
    use_biobert=True, 
    use_superstudio=True,
    use_gemini=False,
    superstudio_api_key="AIzaSyD-B2XQrXgsn-YZarxZcz5jHCTI-g3nugI"
)

# Initialize Gemini for chat using SuperStudio
from models.gemini_qa import GeminiQA
gemini_chat = GeminiQA(
    api_key="AIzaSyD-B2XQrXgsn-YZarxZcz5jHCTI-g3nugI",
    model="gemini-pro",
    base_url="https://generativelanguage.googleapis.com/v1beta",
    use_superstudio=True,
    superstudio_url="https://superstudio.ngrok.io"
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
                # Call Gemini API with the new method
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

if __name__ == "__main__":
    import uvicorn
    print("Starting BugSigDB Analyzer API...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")