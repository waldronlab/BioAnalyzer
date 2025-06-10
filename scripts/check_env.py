#!/usr/bin/env python3

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from utils.config import NCBI_API_KEY, GEMINI_API_KEY, SUPERSTUDIO_API_KEY, EMAIL, validate_env_vars
    
    print("Environment Variable Check")
    print("=========================")
    
    # Check if .env file exists
    env_path = Path(__file__).parents[1] / '.env'
    if env_path.exists():
        print(f"✓ .env file found at {env_path}")
    else:
        print(f"✗ .env file not found. Please create one based on .env.example")
    
    # Check individual variables
    print("\nRequired Variables:")
    print(f"EMAIL: {'✓ Set' if EMAIL else '✗ Missing'}")
    print(f"NCBI_API_KEY: {'✓ Set' if NCBI_API_KEY else '✗ Missing'}")
    
    print("\nOptional Variables:")
    print(f"GEMINI_API_KEY: {'✓ Set' if GEMINI_API_KEY else '✗ Missing'}")
    print(f"SUPERSTUDIO_API_KEY: {'✓ Set' if SUPERSTUDIO_API_KEY else '✗ Missing'}")
    
    # Overall status
    if validate_env_vars():
        print("\n✓ All required environment variables are set.")
    else:
        print("\n✗ Some required environment variables are missing.")
        print("  Please check your .env file and ensure all required variables are set.")
    
except ImportError as e:
    print(f"Error importing configuration: {e}")
    print("Make sure you've created the utils/config.py file.")
except Exception as e:
    print(f"Error checking environment variables: {e}")

if __name__ == "__main__":
    # The script has already run
    pass 