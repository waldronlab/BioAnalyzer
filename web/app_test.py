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
from utils.text_processing import AdvancedTextProcessor
from utils.data_processor import clean_scientific_text
from starlette.websockets import WebSocketState
from pydantic import validator
import asyncio
from utils.config import (
    NCBI_API_KEY,
    OPENAI_API_KEY,
    DEFAULT_MODEL,
    AVAILABLE_MODELS
)
from fastapi.testclient import TestClient
import pytz
from models.unified_qa import UnifiedQA
from retrieve.data_retrieval import PubMedRetriever
from utils.user_manager import UserManager
import openai
import pytest

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
app = FastAPI(title="BugSigDB Analyzer Test")

# Configure API keys
openai.api_key = OPENAI_API_KEY

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
    use_gemini=False,  # Disabled Gemini
    openai_api_key=OPENAI_API_KEY,
    gemini_api_key=None  # No Gemini API key
)

# Update available models based on successful initialization
AVAILABLE_MODELS = model_config.available_models
DEFAULT_MODEL = model_config.default_model

print(f"Final available models: {AVAILABLE_MODELS}")
print(f"Final default model: {DEFAULT_MODEL}")

# Initialize other components
user_manager = UserManager()
text_processor = AdvancedTextProcessor()
retriever = PubMedRetriever(api_key=NCBI_API_KEY)

# Add endpoints for testing
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
async def analyze_paper(pmid: str):
    metadata = retriever.get_paper_metadata(pmid)
    if not metadata:
        raise HTTPException(status_code=404, detail=f"Paper with PMID {pmid} not found")
    
    return {
        "metadata": metadata,
        "analysis": {
            "key_findings": ["Test finding 1", "Test finding 2"],
            "confidence": 0.8,
            "status": "success",
            "suggested_topics": ["Topic 1", "Topic 2"],
            "found_terms": {},
            "category_scores": {},
            "num_tokens": 100
        }
    }

@app.post("/ask_question/{pmid}")
async def ask_question(pmid: str, question: Question):
    return {
        "answer": "This is a test answer.",
        "confidence": 0.8
    }

@app.get("/model_status")
async def get_model_status():
    return {
        "available_models": model_config.available_models,
        "default_model": model_config.default_model,
        "openai_available": model_config.openai_available
    }

@app.post("/cleanup_session/{name}")
async def cleanup_session(name: str):
    return {"status": "success", "message": f"Session cleaned up for {name}"}

# Test client
client = TestClient(app)

# Test data
TEST_PAPER = {
    "title": "Test Paper Title",
    "abstract": "This is a test abstract about microbial signatures.",
    "full_text": "This is the full text of the test paper."
}

TEST_QUESTION = {
    "question": "What are the main findings of this study?"
}

# Test endpoints
def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "name" in response.json()
    assert "version" in response.json()

def test_start_session():
    response = client.post("/start_session/test_user")
    assert response.status_code == 200
    assert "message" in response.json()
    assert "session" in response.json()

def test_analyze_paper():
    # Mock the retriever's get_paper_metadata method
    retriever.get_paper_metadata = lambda pmid: TEST_PAPER
    
    response = client.get("/analyze/12345")
    assert response.status_code == 200
    assert "metadata" in response.json()
    assert "analysis" in response.json()

def test_ask_question():
    # Mock the retriever's get_paper_metadata method
    retriever.get_paper_metadata = lambda pmid: TEST_PAPER
    
    response = client.post("/ask_question/12345", json=TEST_QUESTION)
    assert response.status_code == 200
    assert "answer" in response.json()
    assert "confidence" in response.json()

def test_model_status():
    response = client.get("/model_status")
    assert response.status_code == 200
    assert "available_models" in response.json()
    assert "default_model" in response.json()
    assert "openai_available" in response.json()

def test_cleanup_session():
    response = client.post("/cleanup_session/test_user")
    assert response.status_code == 200
    assert "status" in response.json()
    assert "message" in response.json()

if __name__ == "__main__":
    pytest.main([__file__])
