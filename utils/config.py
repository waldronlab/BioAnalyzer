import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parents[1] / '.env'
load_dotenv(dotenv_path=env_path)

# API Keys
NCBI_API_KEY = os.getenv('NCBI_API_KEY', '')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
SUPERSTUDIO_API_KEY = os.getenv('SUPERSTUDIO_API_KEY', '')
SUPERSTUDIO_URL = os.getenv('SUPERSTUDIO_URL', 'https://superstudio.ngrok.io')
EMAIL = os.getenv('EMAIL', '')

# Validate required environment variables
def validate_env_vars():
    """Validate that required environment variables are set."""
    missing_vars = []
    
    if not NCBI_API_KEY:
        missing_vars.append('NCBI_API_KEY')
    if not GEMINI_API_KEY:
        missing_vars.append('GEMINI_API_KEY')
    if not EMAIL:
        missing_vars.append('EMAIL')
    
    if missing_vars:
        print(f"Warning: The following environment variables are missing: {', '.join(missing_vars)}")
        print("Please set them in your .env file or environment.")
    
    return len(missing_vars) == 0

# Call validation when module is imported
validate_env_vars() 