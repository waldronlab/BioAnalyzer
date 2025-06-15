import os
from pathlib import Path
from dotenv import load_dotenv
import openai
import google.generativeai as genai
import logging

# Load environment variables from .env file
env_path = Path(__file__).parents[1] / '.env'
load_dotenv(dotenv_path=env_path)

# API Keys
NCBI_API_KEY = os.getenv('NCBI_API_KEY', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
# GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')  # Commented out Gemini
EMAIL = os.getenv('EMAIL', '')

# Model Configuration
DEFAULT_MODEL = os.getenv('DEFAULT_MODEL', 'openai')  # Only OpenAI now
AVAILABLE_MODELS = []

# Initialize available models
if OPENAI_API_KEY:
    AVAILABLE_MODELS.append('openai')

# Commented out Gemini validation
# def validate_gemini_key():
#     """Validate Gemini API key by configuring the client."""
#     if not GEMINI_API_KEY:
#         return False
#     try:
#         genai.configure(api_key=GEMINI_API_KEY)
#         return True
#     except Exception as e:
#         print(f"Gemini API key validation failed: {str(e)}")
#         return False

# Commented out Gemini model addition
# if validate_gemini_key():
#     AVAILABLE_MODELS.append('gemini')

def validate_openai_key():
    """Validate OpenAI API key by making a test request."""
    if not OPENAI_API_KEY:
        return False
    try:
        openai.api_key = OPENAI_API_KEY
        # Make a minimal test request
        openai.models.list()
        return True
    except Exception as e:
        print(f"OpenAI API key validation failed: {str(e)}")
        return False

def validate_env_vars():
    """Validate that required environment variables are set."""
    missing_vars = []
    
    if not NCBI_API_KEY:
        missing_vars.append('NCBI_API_KEY')
    if not EMAIL:
        missing_vars.append('EMAIL')
    if not OPENAI_API_KEY:  # Only check for OpenAI now
        missing_vars.append('OPENAI_API_KEY')
    
    # Check if at least one AI model is available
    if not AVAILABLE_MODELS:
        missing_vars.append('OPENAI_API_KEY')
    
    if missing_vars:
        print(f"Warning: The following environment variables are missing: {', '.join(missing_vars)}")
        print("Please set them in your .env file or environment.")
    
    return len(missing_vars) == 0

# Call validation when module is imported
validate_env_vars() 

def check_required_vars():
    """Check if all required environment variables are set."""
    missing_vars = []
    
    if not NCBI_API_KEY:
        missing_vars.append('NCBI_API_KEY')
    if not EMAIL:
        missing_vars.append('EMAIL')
    if not OPENAI_API_KEY:  # Only check for OpenAI now
        missing_vars.append('OPENAI_API_KEY')
    
    if missing_vars:
        print("Missing required environment variables:")
        for var in missing_vars:
            print(f"- {var}")
        return False
    
    return True 