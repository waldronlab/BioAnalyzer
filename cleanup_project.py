#!/usr/bin/env python3
"""
Project cleanup script to remove unnecessary files and reduce project weight.
"""

import os
import shutil
from pathlib import Path

def cleanup_project():
    """Remove unnecessary files to reduce project weight."""
    
    # Files to remove
    files_to_remove = [
        # Redundant documentation
        "PAGE_BASED_DETAILS.md",
        "PAGE_BASED_PAPER_DETAILS.md", 
        "POPUP_RESPONSIVENESS_IMPROVEMENTS.md",
        "ENHANCED_POPUP_FEATURES.md",
        "TAB_ENHANCEMENTS.md",
        "CURATION_ENHANCEMENTS.md",
        "ENHANCED_CURATION_ANALYSIS.md",
        
        # Test files (empty/placeholder)
        "tests/test_bugsigdb_classifier.py",
        "tests/test_data_retrieval.py", 
        "tests/test_model.py",
        "tests/test_preprocessing.py",
        "tests/test_utils.py",
        "test_enhanced_curation.py",
        "test_doi_extraction.py",
        "debug_pubmed_structure.py",
        
        # Unused model files
        "models/superstudio_qa.py",
        "models/trainer.py",
        "models/attention_model.py",
        "models/conversation_model.py",
        "models/paper_qa.py",
        "models/unified_qa.py",
        
        # Unused scripts
        "scripts/train_conversation_model.py",
        "scripts/analyze_bugsigdb_paper.py",
        "scripts/analyze_paper.py",
        "scripts/analyze_papers.py",
        "scripts/check_env.py",
        
        # Debug and temporary files
        "pubmed_debug_output.json",
        ".coverage",
        "check_columns.py",
        "commands",
        "data/training_conversations.json"
    ]
    
    # Directories to remove
    dirs_to_remove = [
        "cache",
        "user_sessions", 
        "analysis_results",
        ".vscode",
        ".pytest_cache",
        "venv",
        "bugsigdb_miner.egg-info",
        "__pycache__",
        "web/__pycache__",
        "models/__pycache__",
        "utils/__pycache__",
        "scripts/__pycache__",
        "tests/__pycache__",
        "retrieve/__pycache__",
        "classify/__pycache__",
        "process/__pycache__"
    ]
    
    print("Starting project cleanup...")
    print("=" * 50)
    
    # Remove files
    removed_files = 0
    for file_path in files_to_remove:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"✓ Removed file: {file_path}")
                removed_files += 1
            except Exception as e:
                print(f"✗ Error removing {file_path}: {e}")
        else:
            print(f"- File not found: {file_path}")
    
    # Remove directories
    removed_dirs = 0
    for dir_path in dirs_to_remove:
        if os.path.exists(dir_path):
            try:
                shutil.rmtree(dir_path)
                print(f"✓ Removed directory: {dir_path}")
                removed_dirs += 1
            except Exception as e:
                print(f"✗ Error removing {dir_path}: {e}")
        else:
            print(f"- Directory not found: {dir_path}")
    
    print("=" * 50)
    print(f"Cleanup completed!")
    print(f"Removed {removed_files} files")
    print(f"Removed {removed_dirs} directories")
    print("\nEssential files kept:")
    print("- web/app.py (main application)")
    print("- web/static/ (UI files)")
    print("- models/gemini_qa.py (active LLM)")
    print("- utils/ (core utilities)")
    print("- data/full_dump.csv (main data)")
    print("- requirements.txt (dependencies)")
    print("- README.md (documentation)")

if __name__ == "__main__":
    cleanup_project() 