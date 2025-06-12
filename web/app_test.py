from fastapi import FastAPI, WebSocket, HTTPException, WebSocketDisconnect, File, UploadFile, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional, Union
import requests
import json
import time
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET
import io
import random
import re
import torch
from torch import serialization
from models.conversation_model import ConversationalBugSigModel
from models.config import ModelConfig
from models.gemini_qa import GeminiQA  # Import GeminiQA
from utils.text_processing import AdvancedTextProcessor
from utils.data_processor import clean_scientific_text
from starlette.websockets import WebSocketState
from pydantic import validator
import asyncio  # Import asyncio for async/await support
from utils.config import NCBI_API_KEY, GEMINI_API_KEY, SUPERSTUDIO_API_KEY, SUPERSTUDIO_URL

class Message(BaseModel):
    content: str
    role: str = "user"

class CodeRequest(BaseModel):
    language: str
    code_type: str
    description: str

class Question(BaseModel):
    question: str

# Pydantic models for type validation
class PaperMetadata(BaseModel):
    title: str = Field(default="No title available")
    authors: Union[List[str], str] = Field(default_factory=list)
    journal: str = Field(default="No journal available")
    publication_date: str = Field(default="No date available")
    doi: Optional[str] = None
    abstract: str = Field(default="No abstract available")
    error: Optional[str] = None

class Analysis(BaseModel):
    has_signatures: bool = False
    confidence: float = 0.0
    key_findings: List[str] = Field(default_factory=list)
    suggested_topics: List[str] = Field(default_factory=list)
    category_scores: Dict[str, float] = Field(
        default_factory=lambda: {
            "microbiome": 0.0,
            "methods": 0.0,
            "analysis": 0.0,
            "body_sites": 0.0,
            "diseases": 0.0
        }
    )
    found_terms: Dict[str, List[str]] = Field(default_factory=dict)
    is_complete: bool = False
    num_tokens: int = 0
    status: str = "success"
    warning: Optional[str] = None
    error: Optional[str] = None

    @validator('category_scores')
    def validate_category_scores(cls, v):
        """Ensure all required categories are present with valid scores."""
        required_categories = {"microbiome", "methods", "analysis", "body_sites", "diseases"}
        
        # Add missing categories with default score
        for category in required_categories:
            if category not in v:
                v[category] = 0.0
        
        # Validate score values
        for category, score in v.items():
            if not isinstance(score, (int, float)):
                raise ValueError(f"Invalid score type for {category}: {type(score)}")
            if not 0 <= score <= 1:
                raise ValueError(f"Score for {category} must be between 0 and 1")
        
        return v

    @validator('found_terms')
    def validate_found_terms(cls, v):
        """Ensure found_terms has valid structure."""
        if not isinstance(v, dict):
            raise ValueError("found_terms must be a dictionary")
        
        for category, terms in v.items():
            if not isinstance(terms, list):
                raise ValueError(f"Terms for {category} must be a list")
            if not all(isinstance(term, str) for term in terms):
                raise ValueError(f"All terms in {category} must be strings")
        
        return v

class AnalysisResponse(BaseModel):
    pmid: str
    metadata: PaperMetadata
    analysis: Analysis
    error: Optional[str] = None
    warning: Optional[str] = None

# Initialize FastAPI app
app = FastAPI(title="BugSigDB Analyzer")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Store active sessions
active_sessions: Dict[str, Dict] = {}

# Initialize text processor and model
text_processor = AdvancedTextProcessor()

# Comment out the local model loading and always use Gemini instead
# Load the trained model
# model_path = Path("models/conversation_model/best_model.pt")
# if model_path.exists():
#     # Add ModelConfig to safe globals
#     serialization.add_safe_globals([ModelConfig])
#     # Load the model with weights_only=False
#     checkpoint = torch.load(model_path, weights_only=False)
#     config = checkpoint['config']
#     model = ConversationalBugSigModel.load_from_pretrained(checkpoint)
#     model.eval()
#     device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
#     model = model.to(device)
# else:
#     print("Warning: Model checkpoint not found. Please train the model first.")
#     model = None

# Skip local model entirely and use Gemini exclusively
model = None
print("Info: Using Gemini API exclusively (local model disabled)")

# Initialize Gemini for chat
from models.gemini_qa import GeminiQA
gemini_chat = GeminiQA(
    api_key=GEMINI_API_KEY,
    model="gemini-pro"
)

class ModelBasedChatHandler:
    def __init__(self, model: ConversationalBugSigModel, text_processor: AdvancedTextProcessor):
        self.model = model
        self.text_processor = text_processor
        self.device = next(model.parameters()).device if model else None
        self.max_seq_length = 256  # Reduced for faster processing
        
        # Cache for storing processed inputs
        self.input_cache = {}
        self.cache_size = 100
    
    def _prepare_input(self, message: str, context: Optional[str] = None) -> Dict[str, torch.Tensor]:
        """Prepare model inputs with caching"""
        try:
            # Check cache first
            cache_key = f"{message}_{context}"
            if cache_key in self.input_cache:
                return self.input_cache[cache_key]
            
            # Clean and process the message
            message_clean = clean_scientific_text(message)
            message_encoded = self.text_processor.encode_text(message_clean)
            
            # Ensure message_encoded is 2D tensor [batch_size=1, sequence_length]
            if len(message_encoded.shape) == 1:
                message_encoded = message_encoded.unsqueeze(0)
            
            # Truncate if needed
            if message_encoded.size(1) > self.max_seq_length:
                message_encoded = message_encoded[:, :self.max_seq_length]
            
            # Process context if available
            context_encoded = None
            if context:
                context_clean = clean_scientific_text(context)
                context_encoded = self.text_processor.encode_text(context_clean)
                
                if len(context_encoded.shape) == 1:
                    context_encoded = context_encoded.unsqueeze(0)
                
                if context_encoded.size(1) > self.max_seq_length:
                    context_encoded = context_encoded[:, :self.max_seq_length]
            
            # Move to device
            inputs = {
                'query_ids': message_encoded.to(self.device),
                'context_ids': context_encoded.to(self.device) if context_encoded is not None else None
            }
            
            # Cache the result
            if len(self.input_cache) >= self.cache_size:
                # Remove oldest entry
                oldest_key = next(iter(self.input_cache))
                del self.input_cache[oldest_key]
            self.input_cache[cache_key] = inputs
            
            return inputs
            
        except Exception as e:
            print(f"Error in _prepare_input: {str(e)}")
            raise
    
    def get_response(self, message: str, context: Dict) -> str:
        """Generate model response with optimizations"""
        if not self.model:
            return "I apologize, but the conversation model is not loaded. Please ensure the model is trained and loaded properly."
        
        try:
            # Prepare model inputs
            inputs = self._prepare_input(
                message=message,
                context=context.get('conversation_history', '')
            )
            
            # Generate response with optimized settings
            with torch.no_grad():
                outputs = self.model.generate_response(
                    query_ids=inputs['query_ids'],
                    context_ids=inputs['context_ids'],
                    max_length=100,  # Reduced for speed
                    temperature=0.7,
                    top_p=0.9,
                    top_k=20,  # Reduced for speed
                    max_time=30.0,  # Increased timeout from 10.0 to 30.0
                    min_length=20,
                    repetition_penalty=1.2
                )
                
                if 'error' in outputs:
                    print(f"Error in response generation: {outputs['error']}")
                    return "I apologize, but I encountered an error. Please try a shorter or simpler message."
                
                # Decode response
                response_text = self.text_processor.decode_tokens(outputs['response_ids'])
                
                return response_text
            
        except Exception as e:
            print(f"Error generating response: {str(e)}")
            return "I apologize, but I encountered an error. Please try again with a different message."

@app.get("/analyze/{pmid}", response_model=AnalysisResponse)
async def analyze_paper(pmid: str) -> AnalysisResponse:
    """Analyze a paper by PMID with proper type validation"""
    try:
        print(f"Starting analysis for PMID: {pmid}")
        
        # Fetch paper metadata
        metadata = fetch_paper_metadata(pmid)
        
        if metadata.get('error'):
            return AnalysisResponse(
                pmid=pmid,
                metadata=PaperMetadata(**metadata),
                analysis=Analysis(**get_default_analysis_result(metadata['error'])),
                error=metadata['error']
            )
        
        # Combine title and abstract for analysis
        text = f"{metadata['title']}\n\n{metadata['abstract']}"
        
        # Analyze the text
        print(f"Analyzing text for PMID {pmid}")
        analysis_dict = await analyze_text(text)
        
        # Ensure key_findings is always a list
        if not isinstance(analysis_dict.get('key_findings', []), list):
            analysis_dict['key_findings'] = []
            
        # Create the response
        response = AnalysisResponse(
            pmid=pmid,
            metadata=PaperMetadata(**metadata),
            analysis=Analysis(**analysis_dict),
            error=analysis_dict.get('error'),
            warning=analysis_dict.get('warning')
        )
        
        return response
        
    except Exception as e:
        print(f"Error in analyze_paper: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return error response
        return AnalysisResponse(
            pmid=pmid,
            metadata=PaperMetadata(
                title="Error",
                abstract=f"An error occurred while analyzing the paper: {str(e)}",
                error=str(e)
            ),
            analysis=Analysis(**get_default_analysis_result(str(e))),
            error=str(e)
        )

# Initialize chat handler with model
chat_handler = ModelBasedChatHandler(model, text_processor) if model else None

def fetch_paper_metadata(pmid: str) -> Dict[str, Any]:
    """Fetch paper metadata from PubMed using the E-utilities API."""
    import time
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    from urllib3.util.timeout import Timeout
    
    try:
        # Create a session with retry strategy
        session = requests.Session()
        retries = Retry(
            total=5,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount('https://', adapter)
        
        # Configure longer timeouts
        timeout = Timeout(connect=30, read=30)
        
        # Use the API key from environment variables
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        api_key = NCBI_API_KEY
        
        # First fetch the summary
        esummary_url = f"{base_url}/esummary.fcgi?db=pubmed&id={pmid}&retmode=json&api_key={api_key}"
        print(f"Fetching summary from: {esummary_url}")
        summary_response = session.get(esummary_url, timeout=timeout)
        summary_response.raise_for_status()
        summary_data = summary_response.json()
        
        # Add delay to comply with NCBI's rate limits (with API key, we can do 10 requests per second)
        time.sleep(0.1)
        
        # Then fetch the abstract using efetch
        efetch_url = f"{base_url}/efetch.fcgi?db=pubmed&id={pmid}&retmode=xml&api_key={api_key}"
        print(f"Fetching abstract from: {efetch_url}")
        abstract_response = session.get(efetch_url, timeout=timeout)
        abstract_response.raise_for_status()
        
        # Parse XML response for abstract
        root = ET.fromstring(abstract_response.content)
        abstract_text = ""
        abstract_elements = root.findall(".//Abstract/AbstractText")
        if abstract_elements:
            abstract_text = " ".join(elem.text for elem in abstract_elements if elem.text)
        
        # Extract metadata from summary response
        result = summary_data['result'][pmid]
        metadata = {
            'title': result.get('title', ''),
            'abstract': abstract_text,
            'authors': [author['name'] for author in result.get('authors', [])],
            'journal': result.get('fulljournalname', ''),
            'publication_date': result.get('pubdate', ''),
            'doi': result.get('elocationid', '').replace('doi: ', '') if result.get('elocationid') else None
        }
        
        print(f"Successfully fetched metadata for PMID {pmid}")
        return metadata
        
    except requests.exceptions.Timeout as e:
        print(f"Timeout error fetching metadata for PMID {pmid}: {str(e)}")
        return {
            'title': 'Error: Request Timeout',
            'abstract': 'Could not fetch paper details due to timeout. Please try again later.',
            'authors': [],
            'journal': '',
            'publication_date': '',
            'doi': None,
            'error': f"Request timed out: {str(e)}"
        }
    except requests.exceptions.RequestException as e:
        print(f"Network error fetching metadata for PMID {pmid}: {str(e)}")
        return {
            'title': 'Error: Network Issue',
            'abstract': f'Could not fetch paper details due to network error: {str(e)}',
            'authors': [],
            'journal': '',
            'publication_date': '',
            'doi': None,
            'error': str(e)
        }
    except Exception as e:
        print(f"Error fetching metadata for PMID {pmid}: {str(e)}")
        return {
            'title': 'Error',
            'abstract': f'An error occurred while fetching paper details: {str(e)}',
            'authors': [],
            'journal': '',
            'publication_date': '',
            'doi': None,
            'error': str(e)
        }

async def analyze_text(text: str, timeout: int = 30) -> Dict[str, Any]:
    """Analyze the text content using the trained model and Gemini API."""
    try:
        print("Starting text analysis...")
        start_time = time.time()
        
        if not text:
            print("Error: Empty text provided")
            return get_default_analysis_result("Empty text provided")
            
        print("Cleaning and processing text...")
        # Clean and process the text
        cleaned_text = clean_scientific_text(text)
        
        # Extract key terms and concepts
        microbiome_terms = ["microbiota", "microbiome", "bacterial", "bacteria", "16S rRNA", "sequencing"]
        method_terms = ["sequencing", "PCR", "amplification", "culture", "analysis", "pyrosequencing"]
        analysis_terms = ["abundance", "diversity", "richness", "significant", "differential", "analysis"]
        body_site_terms = ["gut", "oral", "saliva", "skin", "respiratory", "vaginal"]
        disease_terms = ["infection", "disease", "syndrome", "disorder", "condition"]
        
        # Calculate category scores based on term presence
        def calculate_score(terms):
            return sum(1 for term in terms if term.lower() in cleaned_text.lower()) / len(terms)
        
        category_scores = {
            "microbiome": calculate_score(microbiome_terms),
            "methods": calculate_score(method_terms),
            "analysis": calculate_score(analysis_terms),
            "body_sites": calculate_score(body_site_terms),
            "diseases": calculate_score(disease_terms)
        }
        
        # Find terms present in text
        found_terms = {
            "microbiome": [term for term in microbiome_terms if term.lower() in cleaned_text.lower()],
            "methods": [term for term in method_terms if term.lower() in cleaned_text.lower()],
            "analysis": [term for term in analysis_terms if term.lower() in cleaned_text.lower()],
            "body_sites": [term for term in body_site_terms if term.lower() in cleaned_text.lower()],
            "diseases": [term for term in disease_terms if term.lower() in cleaned_text.lower()]
        }
        
        # Extract key findings - first try Gemini API, fall back to local extraction if API fails
        key_findings = []
        warning = None
        
        try:
            # Try using Gemini API first
            print("Attempting to use Gemini API for key findings extraction...")
            gemini_response = await gemini_chat.get_answer(
                question="What are the key findings of this paper?",
                context=cleaned_text[:4000]  # Limit context length
            )
            
            if "error" in gemini_response:
                # Special handling for IP restriction errors
                if gemini_response.get('error') == "IP_RESTRICTED":
                    warning = "The Gemini API key has IP address restrictions. Your current IP address is not authorized to use this API key. Please update the API key in your .env file to one without IP restrictions or add your current IP to the allowed list."
                    print(warning)
                    print("Falling back to local extraction method")
                    key_findings = extract_key_findings_from_text(cleaned_text)
                else:
                    warning = f"Gemini API error: {gemini_response.get('error')}"
                    print(warning)
                    print("Falling back to local extraction method")
                    key_findings = extract_key_findings_from_text(cleaned_text)
            else:
                # Process Gemini's response
                response_text = gemini_response.get("answer", "")
                if response_text:
                    # Split the response into sentences or bullet points
                    findings = re.split(r'[\n\r]+|(?<=[.!?]) +', response_text)
                    # Clean up the findings
                    key_findings = [
                        finding.strip().rstrip('.') 
                        for finding in findings 
                        if finding.strip() and len(finding.strip()) > 10
                    ][:3]  # Take up to 3 findings
                
                # If no valid findings from Gemini, fall back to local extraction
                if not key_findings:
                    print("No valid findings from Gemini, using fallback method")
                    key_findings = extract_key_findings_from_text(cleaned_text)
        except Exception as e:
            warning = f"Error generating key findings: {str(e)}"
            print(warning)
            print("Using local extraction method due to error")
            key_findings = extract_key_findings_from_text(cleaned_text)
            
        # If we still don't have key findings, extract from the abstract directly
        if not key_findings:
            print("No key findings extracted, using direct extraction from abstract")
            sentences = re.split(r'[.!?]+', cleaned_text)
            # Look for sentences with important keywords
            important_keywords = ["significant", "found", "observed", "showed", "demonstrated", "revealed", "identified", "concluded"]
            for sentence in sentences:
                sentence = sentence.strip()
                if (len(sentence) > 20 and 
                    any(keyword in sentence.lower() for keyword in important_keywords)):
                    key_findings.append(sentence)
                    if len(key_findings) >= 3:
                        break
        
        print("Processing analysis results...")
        result = {
            "has_signatures": any(score > 0.3 for score in category_scores.values()),
            "confidence": max(0.4, sum(category_scores.values()) / len(category_scores)),
            "key_findings": key_findings,
            "suggested_topics": [
                "Microbiome Analysis" if found_terms["microbiome"] else None,
                "Methodology" if found_terms["methods"] else None,
                "Statistical Analysis" if found_terms["analysis"] else None,
                "Anatomical Sites" if found_terms["body_sites"] else None,
                "Clinical Relevance" if found_terms["diseases"] else None
            ],
            "category_scores": category_scores,
            "found_terms": found_terms,
            "is_complete": True,
            "num_tokens": len(cleaned_text.split()),
            "status": "success",
            "warning": warning
        }
        
        # Filter out None values from suggested_topics
        result["suggested_topics"] = [topic for topic in result["suggested_topics"] if topic]
        
        elapsed_time = time.time() - start_time
        print(f"Analysis completed in {elapsed_time:.2f} seconds")
        return result
        
    except Exception as e:
        print(f"Error analyzing text: {str(e)}")
        import traceback
        traceback.print_exc()
        return get_default_analysis_result(str(e))

def extract_key_findings_from_text(text: str, max_findings: int = 3) -> List[str]:
    """Extract key findings from text as a fallback method."""
    # Split into sentences
    sentences = re.split(r'[.!?]+', text)
    # Filter and clean sentences
    findings = []
    for s in sentences:
        s = s.strip()
        # Only include sentences that:
        # 1. Are long enough (>10 chars)
        # 2. Have enough words (>3)
        # 3. Don't start with common filler phrases
        if (len(s) > 10 and 
            len(s.split()) > 3 and 
            not any(s.lower().startswith(x) for x in ['this study', 'these results', 'in this paper'])):
            findings.append(s)
    return findings[:max_findings]

def get_default_analysis_result(error_message: str = None) -> Dict[str, Any]:
    """Return a default analysis result structure with zeros/empty values"""
    return {
        "error": error_message,
        "has_signatures": False,
        "confidence": 0.0,
        "key_findings": [],
        "suggested_topics": [],
        "category_scores": {
            "microbiome": 0.0,
            "methods": 0.0,
            "analysis": 0.0,
            "body_sites": 0.0,
            "diseases": 0.0
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
        "status": "error" if error_message else "success",
        "warning": None
    }

@app.get("/")
async def root():
    """Serve the main HTML page"""
    return FileResponse(static_dir / "index.html")

@app.post("/start_session/{name}")
async def start_session(name: str):
    """Start a new chat session."""
    if name in active_sessions:
        # Reset existing session
        active_sessions[name] = {
            "messages": [],
            "last_activity": datetime.now().isoformat()
        }
    else:
        # Create new session
        active_sessions[name] = {
            "messages": [],
            "last_activity": datetime.now().isoformat()
        }
    
    print(f"Creating new session for {name}")
    return {"status": "success", "name": name}

@app.post("/chat/{name}")
async def chat(name: str, message: Message):
    """Chat with the Gemini API with fallback."""
    try:
        if name not in active_sessions:
            return {"error": "Session not found. Please start a new session."}
        
        # Get session context
        session = active_sessions[name]
        
        # Add message to history
        session["messages"].append({
            "role": message.role,
            "content": message.content
        })
        
        # Limit history to last 10 messages to avoid context length issues
        if len(session["messages"]) > 10:
            session["messages"] = session["messages"][-10:]
        
        # Build context from message history
        conversation_history = "\n".join([
            f"{msg['role']}: {msg['content']}" 
            for msg in session["messages"][-10:]
        ])
        
        # Try using Gemini API first
        try:
            print(f"Attempting to chat using Gemini API: {message.content[:50]}...")
            response = await gemini_chat.chat_with_context(
                message=message.content,
                chat_history=session["messages"]
            )
            
            if "error" in response:
                print(f"Gemini API error: {response.get('error')}")
                
                # Special handling for IP restriction errors
                if response.get('error') == "IP_RESTRICTED":
                    answer = "⚠️ API Key Error: The Gemini API key has IP address restrictions. Your current IP address is not authorized to use this API key. Please update the API key in your .env file to one without IP restrictions or add your current IP to the allowed list."
                    
                    # Add error response to history
                    session["messages"].append({
                        "role": "assistant",
                        "content": answer
                    })
                    
                    return {
                        "response": answer,
                        "name": name,
                        "note": "API Key IP restriction error"
                    }
                else:
                    # Fall back to local method for other errors
                    answer = generate_fallback_chat_response(message.content, session["messages"])
                    
                    # Add fallback response to history
                    session["messages"].append({
                        "role": "assistant",
                        "content": answer
                    })
                    
                    return {
                        "response": answer,
                        "name": name,
                        "note": "Generated using fallback method due to API unavailability"
                    }
            
            # Add assistant response to history
            assistant_response = response.get("response", "Sorry, I couldn't generate a response.")
            session["messages"].append({
                "role": "assistant",
                "content": assistant_response
            })
            
            return {
                "response": assistant_response,
                "name": name
            }
            
        except Exception as e:
            print(f"Error using Gemini API: {str(e)}")
            # Fall back to local method
            answer = generate_fallback_chat_response(message.content, session["messages"])
            
            # Add fallback response to history
            session["messages"].append({
                "role": "assistant",
                "content": answer
            })
            
            return {
                "response": answer,
                "name": name,
                "note": "Generated using fallback method due to API error"
            }
        
    except Exception as e:
        print(f"Error in chat: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": f"Error processing message: {str(e)}"}

@app.websocket("/ws/{name}")
async def websocket_endpoint(websocket: WebSocket, name: str):
    """WebSocket endpoint for real-time chat with Gemini API and fallback."""
    print(f"New WebSocket connection request from {name}")
    await websocket.accept()
    print(f"WebSocket connection accepted for {name}")
    
    # Initialize or get session
    if name not in active_sessions:
        active_sessions[name] = {
            "messages": [],
            "last_activity": datetime.now().isoformat()
        }
        print(f"Creating new session for {name}")
    
    print(f"Starting message loop for {name}")
    print("INFO: connection open")
    
    try:
        while True:
            # Wait for message from client
            print(f"Waiting for message from {name}...")
            data = await websocket.receive_text()
            print(f"Received raw data from {name}: {data[:100]}...")
            
            try:
                # Parse message data
                message_data = json.loads(data)
                print(f"Parsed JSON data: {message_data}")
                user_message = message_data.get("content", "")
                
                if not user_message or not isinstance(user_message, str) or not user_message.strip():
                    print(f"Empty or invalid message received: {message_data}")
                    await websocket.send_json({
                        "error": "Empty or invalid message received"
                    })
                    continue
                
                print(f"Received message from {name}: {user_message[:50]}...")
                
                # Add message to history
                active_sessions[name]["messages"].append({
                    "role": "user",
                    "content": user_message
                })
                
                # Limit history to last 10 messages
                if len(active_sessions[name]["messages"]) > 10:
                    active_sessions[name]["messages"] = active_sessions[name]["messages"][-10:]
                
                # Build conversation history
                conversation_history = "\n".join([
                    f"{msg['role']}: {msg['content']}" 
                    for msg in active_sessions[name]["messages"][-10:]
                ])
                
                # Try using Gemini API first
                try:
                    print(f"Attempting to chat using Gemini API via WebSocket: {user_message[:50]}...")
                    response = await gemini_chat.chat_with_context(
                        message=user_message,
                        chat_history=active_sessions[name]["messages"]
                    )
                    
                    if "error" in response:
                        print(f"Gemini API error: {response.get('error')}")
                        
                        # Special handling for IP restriction errors
                        if response.get('error') == "IP_RESTRICTED":
                            assistant_message = "⚠️ API Key Error: The Gemini API key has IP address restrictions. Your current IP address is not authorized to use this API key. Please update the API key in your .env file to one without IP restrictions or add your current IP to the allowed list."
                        else:
                            # Fall back to local method for other errors
                            assistant_message = generate_fallback_chat_response(
                                user_message, 
                                active_sessions[name]["messages"]
                            )
                            
                            # Add note about fallback
                            note = "Note: Generated using fallback method due to API unavailability"
                            assistant_message = f"{assistant_message}\n\n{note}"
                    else:
                        # Get the response text - use 'response' key instead of 'answer'
                        assistant_message = response.get("response", "Sorry, I couldn't generate a response.")
                        
                except Exception as e:
                    print(f"Error using Gemini API via WebSocket: {str(e)}")
                    # Fall back to local method
                    assistant_message = generate_fallback_chat_response(
                        user_message, 
                        active_sessions[name]["messages"]
                    )
                    
                    # Add note about fallback
                    note = "Note: Generated using fallback method due to API error"
                    assistant_message = f"{assistant_message}\n\n{note}"
                
                # Add response to history
                active_sessions[name]["messages"].append({
                    "role": "assistant",
                    "content": assistant_message
                })
                
                # Update last activity timestamp
                active_sessions[name]["last_activity"] = datetime.now().isoformat()
                
                # Send response to client
                await websocket.send_json({
                    "response": assistant_message,
                    "name": name
                })
                
            except json.JSONDecodeError:
                await websocket.send_json({
                    "error": "Invalid JSON format"
                })
            except Exception as e:
                print(f"Error processing message: {str(e)}")
                await websocket.send_json({
                    "error": f"Error processing message: {str(e)}"
                })
    
    except WebSocketDisconnect:
        print(f"WebSocket connection closed for {name}")
    except Exception as e:
        print(f"WebSocket error for {name}: {str(e)}")
        try:
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close()
        except:
            pass

def generate_fallback_chat_response(message: str, history: List[Dict]) -> str:
    """Generate a simple chat response when the API is unavailable."""
    message_lower = message.lower()
    
    # Check for common greeting patterns
    greetings = ["hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening"]
    if any(greeting in message_lower for greeting in greetings):
        return "Hello! I'm a fallback assistant. The Gemini API is currently unavailable, but I can try to help with basic questions about papers and research."
    
    # Check for questions about the system
    if "what can you do" in message_lower or "help me" in message_lower or "your capabilities" in message_lower:
        return "I'm currently running in fallback mode because the Gemini API is unavailable. I can help with basic paper analysis and simple questions, but my capabilities are limited in this mode."
    
    # Check for questions about papers
    paper_related = ["paper", "research", "study", "article", "publication", "findings", "results", "conclusion"]
    if any(term in message_lower for term in paper_related):
        return "To analyze a paper, please enter a valid PMID in the Paper Analysis tab. I can then try to extract key information from the paper."
    
    # Default responses based on message length
    if len(message) < 20:
        return "I'm operating in fallback mode due to API unavailability. Could you please provide more details about what you're looking for?"
    else:
        return "I understand you're asking about something detailed, but I'm currently operating in fallback mode with limited capabilities. Please try analyzing a specific paper using the Paper Analysis tab, or try again later when the API might be available."

@app.post("/ask_question/{pmid}")
async def ask_question(pmid: str, question: Question):
    """Ask a question about a specific paper using Gemini API with fallback."""
    try:
        # Fetch paper metadata
        metadata = fetch_paper_metadata(pmid)
        
        if metadata.get('error'):
            return {"error": f"Error fetching paper: {metadata.get('error')}"}
        
        # Combine title and abstract for context
        paper_text = f"Title: {metadata['title']}\n\nAbstract: {metadata['abstract']}"
        
        # Try using Gemini API first
        try:
            print(f"Attempting to answer question using Gemini API: {question.question}")
            response = await gemini_chat.get_answer(
                question=question.question,
                context=paper_text
            )
            
            if "error" in response:
                print(f"Gemini API error: {response.get('error')}")
                
                # Special handling for IP restriction errors
                if response.get('error') == "IP_RESTRICTED":
                    return {
                        "answer": "⚠️ API Key Error: The Gemini API key has IP address restrictions. Your current IP address is not authorized to use this API key. Please update the API key in your .env file to one without IP restrictions or add your current IP to the allowed list.",
                        "pmid": pmid,
                        "question": question.question,
                        "note": "API Key IP restriction error"
                    }
                else:
                    # Fall back to local method for other errors
                    answer = generate_fallback_answer(question.question, paper_text)
                    return {
                        "answer": answer,
                        "pmid": pmid,
                        "question": question.question,
                        "note": "Generated using fallback method due to API unavailability"
                    }
            
            return {
                "answer": response.get("answer", "Sorry, I couldn't generate an answer."),
                "pmid": pmid,
                "question": question.question
            }
            
        except Exception as e:
            print(f"Error using Gemini API: {str(e)}")
            # Fall back to local method
            answer = generate_fallback_answer(question.question, paper_text)
            return {
                "answer": answer,
                "pmid": pmid,
                "question": question.question,
                "note": "Generated using fallback method due to API error"
            }
        
    except Exception as e:
        print(f"Error in ask_question: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": f"Error processing question: {str(e)}"}

def generate_fallback_answer(question: str, context: str) -> str:
    """Generate a simple answer to a question using keyword matching when API is unavailable."""
    question_lower = question.lower()
    context_lower = context.lower()
    
    # Extract relevant sentences based on keyword matching
    sentences = re.split(r'[.!?]+', context)
    relevant_sentences = []
    
    # Extract keywords from the question
    question_words = set(re.findall(r'\b\w+\b', question_lower))
    important_words = [w for w in question_words if len(w) > 3 and w not in 
                      {'what', 'when', 'where', 'which', 'who', 'whom', 'whose', 'why', 'how',
                       'does', 'did', 'do', 'is', 'are', 'was', 'were', 'will', 'would', 'should',
                       'could', 'can', 'this', 'that', 'these', 'those', 'there', 'here', 'have',
                       'has', 'had', 'been', 'being', 'about', 'paper', 'study', 'research'}]
    
    # Find sentences containing important question words
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 10:
            continue
            
        sentence_lower = sentence.lower()
        matches = sum(1 for word in important_words if word in sentence_lower)
        
        if matches > 0:
            relevant_sentences.append((sentence, matches))
    
    # Sort by relevance (number of matching keywords)
    relevant_sentences.sort(key=lambda x: x[1], reverse=True)
    
    # Generate answer based on question type
    if "what" in question_lower and "conclusion" in question_lower:
        # Looking for conclusions
        for sentence, _ in relevant_sentences:
            if any(word in sentence.lower() for word in ["conclude", "conclusion", "suggest", "demonstrate", "show", "reveal", "indicate"]):
                return f"Based on the paper: {sentence}"
    
    elif "what" in question_lower and any(word in question_lower for word in ["method", "technique", "approach"]):
        # Looking for methods
        for sentence, _ in relevant_sentences:
            if any(word in sentence.lower() for word in ["method", "technique", "approach", "procedure", "protocol", "analysis", "measure"]):
                return f"The paper describes this method: {sentence}"
    
    elif "what" in question_lower and "finding" in question_lower:
        # Looking for findings
        for sentence, _ in relevant_sentences:
            if any(word in sentence.lower() for word in ["found", "observed", "showed", "demonstrated", "revealed", "identified"]):
                return f"Key finding from the paper: {sentence}"
    
    # If we have relevant sentences, return the most relevant one
    if relevant_sentences:
        return f"Based on the paper: {relevant_sentences[0][0]}"
    
    # Default response
    return "I'm sorry, I don't have enough information to answer that question based on this paper."

@app.post("/upload_paper")
async def upload_paper(file: UploadFile = File(...), username: str = Form(None)):
    """Upload a paper file (PDF or text) and extract information for curation"""
    try:
        # Check file type
        if file.content_type not in ["application/pdf", "text/plain"]:
            return {"error": "Only PDF and text files are supported"}
        
        # Read file content
        content = await file.read()
        
        # Process the file based on type
        if file.content_type == "application/pdf":
            # For PDF files, extract text using PyPDF2
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
                text_content = ""
                for page in pdf_reader.pages:
                    text_content += page.extract_text() + "\n"
                
                paper_content = {
                    "title": file.filename,
                    "abstract": text_content[:500] + "..." if len(text_content) > 500 else text_content,
                    "full_text": text_content
                }
            except Exception as e:
                print(f"Error extracting text from PDF: {str(e)}")
                return {"error": f"Error extracting text from PDF: {str(e)}"}
        else:
            # For text files, use the content directly
            text_content = content.decode("utf-8")
            paper_content = {
                "title": file.filename,
                "abstract": text_content[:500] + "..." if len(text_content) > 500 else text_content,
                "full_text": text_content
            }
        
        # Use Gemini to analyze the paper
        try:
            print(f"Analyzing uploaded paper with Gemini...")
            results = await gemini_chat.analyze_paper(paper_content)
            
            # Extract analysis results
            analysis_results = results.get("signature_analysis", {})
            
            # Add additional fields for curation
            if "found_terms" in analysis_results:
                # Extract potential taxa from found terms or full text
                taxa = []
                if "taxa" in analysis_results["found_terms"]:
                    taxa = analysis_results["found_terms"]["taxa"]
                elif "microbiome" in analysis_results["found_terms"]:
                    taxa = analysis_results["found_terms"]["microbiome"]
                
                analysis_results["taxa"] = taxa
            
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
            
            # If username is provided, update session
            if username and username in active_sessions:
                active_sessions[username]["current_paper"] = file.filename
            
            return response
            
        except Exception as e:
            print(f"Error analyzing paper with Gemini: {str(e)}")
            # Return basic info without analysis
            return {
                "metadata": {
                    "title": paper_content["title"],
                    "abstract": paper_content["abstract"],
                },
                "analysis": {
                    "error": f"Error analyzing paper: {str(e)}",
                    "key_findings": ["Unable to analyze paper automatically"],
                    "confidence": 0.1
                }
            }
            
    except Exception as e:
        print(f"Error processing uploaded file: {str(e)}")
        return {"error": f"Error processing file: {str(e)}"}

@app.get("/fetch_by_doi")
async def fetch_by_doi(doi: str):
    """Fetch paper by DOI for curation"""
    try:
        # Use NCBI API to convert DOI to PMID
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={doi}[doi]&retmode=json"
        response = requests.get(url)
        data = response.json()
        
        # Check if we got a PMID
        id_list = data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return {"error": f"No PMID found for DOI {doi}"}
        
        pmid = id_list[0]
        
        # Use the analyze_paper function to get full analysis
        return await analyze_paper(pmid)
    except Exception as e:
        print(f"Error fetching paper by DOI: {str(e)}")
        return {"error": f"Error fetching paper: {str(e)}"}

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
            return {"error": f"Missing required fields: {', '.join(missing_fields)}"}
        
        # In a real implementation, this would submit to BugSigDB API
        # For now, just log the submission
        print(f"Curation submitted: {data}")
        
        # Return success response
        return {"status": "success", "message": "Curation submitted successfully"}
    except Exception as e:
        print(f"Error submitting curation: {str(e)}")
        return {"error": f"Error submitting curation: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    import ssl
    import os
    import argparse
    from pathlib import Path
    
    parser = argparse.ArgumentParser(description="Run BugSigDB Analyzer")
    parser.add_argument("--https", action="store_true", help="Run with HTTPS")
    parser.add_argument("--port", type=int, default=None, help="Port to run on (default: 8443 for HTTPS, 8000 for HTTP)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to run on (default: 127.0.0.1)")
    
    args = parser.parse_args()
    
    print("Starting BugSigDB Analyzer API...")
    
    if args.https:
        # Set default HTTPS port if not specified
        port = args.port or 8443
        
        # Check if SSL certificates exist, if not, create self-signed certificates
        cert_dir = Path("./certs")
        cert_file = cert_dir / "cert.pem"
        key_file = cert_dir / "key.pem"
        
        if not cert_dir.exists():
            cert_dir.mkdir(exist_ok=True)
        
        if not cert_file.exists() or not key_file.exists():
            print("Generating self-signed SSL certificates...")
            os.system(f'openssl req -x509 -newkey rsa:4096 -nodes -out {cert_file} -keyout {key_file} -days 365 -subj "/CN=localhost"')
        
        print(f"Running with HTTPS on {args.host}:{port}")
        uvicorn.run(app, host=args.host, port=port, ssl_certfile=str(cert_file), ssl_keyfile=str(key_file), log_level="info")
    else:
        # Set default HTTP port if not specified
        port = args.port or 8000
        print(f"Running with HTTP on {args.host}:{port}")
        uvicorn.run(app, host=args.host, port=port, log_level="info")
