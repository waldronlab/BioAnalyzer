@echo off
REM BugSigDB Analyzer Setup Script for Windows
REM This script automates the setup process for Windows users

echo 🚀 BugSigDB Analyzer Setup Script
echo ==================================

REM Check prerequisites
echo [INFO] Checking prerequisites...

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.8+ first.
    pause
    exit /b 1
)
echo [SUCCESS] Python found

REM Check pip
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] pip not found. Please install pip first.
    pause
    exit /b 1
)
echo [SUCCESS] pip found

REM Check git
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] git not found. Please install git first.
    pause
    exit /b 1
)
echo [SUCCESS] git found

echo [INFO] All prerequisites satisfied!

REM Create virtual environment
echo [INFO] Creating virtual environment...
if not exist ".venv" (
    python -m venv .venv
    echo [SUCCESS] Virtual environment created
) else (
    echo [WARNING] Virtual environment already exists
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call .venv\Scripts\activate.bat
echo [SUCCESS] Virtual environment activated

REM Upgrade pip
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo [INFO] Installing dependencies...
pip install -r requirements.txt
echo [SUCCESS] Dependencies installed

REM Create .env file if it doesn't exist
if not exist ".env" (
    echo [INFO] Creating .env file...
    (
        echo # API Keys - Replace with your actual keys
        echo NCBI_API_KEY=your_ncbi_api_key_here
        echo GEMINI_API_KEY=your_gemini_api_key_here
        echo EMAIL=your_email@example.com
        echo.
        echo # Model Configuration
        echo DEFAULT_MODEL=gemini
    ) > .env
    echo [SUCCESS] .env file created
    echo [WARNING] Please edit .env file with your actual API keys before running the application
) else (
    echo [WARNING] .env file already exists
)

REM Create necessary directories
echo [INFO] Creating necessary directories...
if not exist "results" mkdir results
if not exist "cache" mkdir cache
if not exist "data" mkdir data
echo [SUCCESS] Directories created

echo [SUCCESS] Setup completed successfully!
echo.
echo 🎉 Next steps:
echo 1. Edit .env file with your API keys:
echo    notepad .env
echo.
echo 2. Run the application:
echo    python start.py
echo.
echo 3. Open your browser and go to:
echo    http://127.0.0.1:8000
echo.
echo 📚 For more information, see README.md and QUICKSTART.md
echo.
echo 🔑 To get API keys:
echo    - NCBI: https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/
echo    - Gemini: https://makersuite.google.com/app/apikey
echo.
pause 