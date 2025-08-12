#!/usr/bin/env python3
"""
BugSigDB Analyzer - Main Entry Point
====================================

This is the main entry point for the BugSigDB Analyzer application.
It can be run directly or imported as a module.
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import and run the FastAPI application
from app.api.app import app

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting BugSigDB Analyzer...")
    print("📁 Project root:", project_root)
    print("🌐 Application will be available at: http://127.0.0.1:8000")
    print("📚 API documentation at: http://127.0.0.1:8000/docs")
    print("🔍 Health check at: http://127.0.0.1:8000/health")
    print("📊 Metrics at: http://127.0.0.1:8000/metrics")
    print("\nPress Ctrl+C to stop the server")
    
    uvicorn.run(
        "app.api.app:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True  # Enable auto-reload for development
    ) 