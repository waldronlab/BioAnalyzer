#!/usr/bin/env python3

import os
import sys
from pathlib import Path

# Add the project root directory to the Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from utils.config import (
    NCBI_API_KEY,
    OPENAI_API_KEY,
    EMAIL,
    validate_openai_key,
    check_required_vars
)

def main():
    """Check environment configuration."""
    print("\nChecking environment configuration...")
    
    # Check required environment variables
    print("\nRequired Environment Variables:")
    print(f"NCBI_API_KEY: {'✓ Set' if NCBI_API_KEY else '✗ Missing'}")
    print(f"OPENAI_API_KEY: {'✓ Set' if OPENAI_API_KEY else '✗ Missing'}")
    print(f"EMAIL: {'✓ Set' if EMAIL else '✗ Missing'}")
    
    # Validate API keys
    print("\nAPI Key Validation:")
    print(f"OpenAI API: {'✓ Valid' if validate_openai_key() else '✗ Invalid'}")
    
    # Check if all required variables are set
    if check_required_vars():
        print("\n✓ All required environment variables are set and valid.")
    else:
        print("\n✗ Some required environment variables are missing or invalid.")
        print("\nNote: OpenAI API key is required.")

if __name__ == "__main__":
    main() 