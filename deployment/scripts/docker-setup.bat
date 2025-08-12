@echo off
REM BugSigDB Analyzer Docker Setup Script for Windows
REM This script sets up the Docker environment for the project

echo 🐳 BugSigDB Analyzer Docker Setup Script
echo =========================================

REM Check prerequisites
echo [INFO] Checking Docker prerequisites...

REM Check Docker
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker not found. Please install Docker first.
    echo Visit: https://docs.docker.com/get-docker/
    pause
    exit /b 1
)

REM Check Docker Compose
docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker Compose not found. Please install Docker Compose first.
    echo Visit: https://docs.docker.com/compose/install/
    pause
    exit /b 1
)

REM Check Docker daemon
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker daemon is not running. Please start Docker first.
    pause
    exit /b 1
)

echo [SUCCESS] Docker prerequisites satisfied!

REM Create necessary directories
echo [INFO] Creating necessary directories...
if not exist "nginx\ssl" mkdir nginx\ssl
if not exist "nginx\error_pages" mkdir nginx\error_pages
if not exist "monitoring" mkdir monitoring
if not exist "results" mkdir results
if not exist "cache" mkdir cache
if not exist "data" mkdir data
echo [SUCCESS] Directories created

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
        echo.
        echo # Redis Configuration
        echo REDIS_PASSWORD=changeme
        echo.
        echo # Environment
        echo ENVIRONMENT=development
    ) > .env
    echo [SUCCESS] .env file created
    echo [WARNING] Please edit .env file with your actual API keys before running the application
) else (
    echo [WARNING] .env file already exists
)

REM Create basic monitoring configuration
if not exist "monitoring\prometheus.yml" (
    echo [INFO] Creating Prometheus configuration...
    (
        echo global:
        echo   scrape_interval: 15s
        echo   evaluation_interval: 15s
        echo.
        echo rule_files:
        echo   # "first_rules.yml"
        echo   # "second_rules.yml"
        echo.
        echo scrape_configs:
        echo   - job_name: 'prometheus'
        echo     static_configs:
        echo       - targets: ['localhost:9090']
        echo.
        echo   - job_name: 'bugsigdb-analyzer'
        echo     static_configs:
        echo       - targets: ['app:8000']
        echo     metrics_path: '/metrics'
        echo     scrape_interval: 5s
    ) > monitoring\prometheus.yml
    echo [SUCCESS] Prometheus configuration created
)

REM Create basic error pages
echo [INFO] Creating basic error pages...
(
    echo ^<!DOCTYPE html^>
    echo ^<html^>
    echo ^<head^>
    echo     ^<title^>404 - Page Not Found^</title^>
    echo     ^<style^>
    echo         body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
    echo         .error { color: #666; font-size: 72px; margin-bottom: 20px; }
    echo         .message { color: #999; font-size: 18px; }
    echo     ^</style^>
    echo ^</head^>
    echo ^<body^>
    echo     ^<div class="error"^>404^</div^>
    echo     ^<div class="message"^>Page Not Found^</div^>
    echo     ^<p^>The page you're looking for doesn't exist.^</p^>
    echo     ^<a href="/"^>Go Home^</a^>
    echo ^</body^>
    echo ^</html^>
) > nginx\error_pages\404.html

(
    echo ^<!DOCTYPE html^>
    echo ^<html^>
    echo ^<head^>
    echo     ^<title^>Server Error^</title^>
    echo     ^<style^>
    echo         body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
    echo         .error { color: #d32f2f; font-size: 72px; margin-bottom: 20px; }
    echo         .message { color: #999; font-size: 18px; }
    echo     ^</style^>
    echo ^</head^>
    echo ^<body^>
    echo     ^<div class="error"^>500^</div^>
    echo     ^<div class="message"^>Internal Server Error^</div^>
    echo     ^<p^>Something went wrong on our end. Please try again later.^</p^>
    echo     ^<a href="/"^>Go Home^</a^>
    echo ^</body^>
    echo ^</html^>
) > nginx\error_pages\50x.html
echo [SUCCESS] Error pages created

REM Build and start development environment
echo [INFO] Building and starting development environment...
docker-compose -f docker-compose.dev.yml build

echo [SUCCESS] Docker setup completed successfully!
echo.
echo 🎉 Next steps:
echo 1. Edit .env file with your API keys:
echo    notepad .env
echo.
echo 2. Start the development environment:
echo    docker-compose -f docker-compose.dev.yml up -d
echo.
echo 3. View logs:
echo    docker-compose -f docker-compose.dev.yml logs -f
echo.
echo 4. Access the application:
echo    - Direct app: http://localhost:8000
echo    - Through Nginx: http://localhost:8080
echo    - API docs: http://localhost:8000/docs
echo.
echo 5. Stop the environment:
echo    docker-compose -f docker-compose.dev.yml down
echo.
echo 📚 For production deployment:
echo    docker-compose -f docker-compose.prod.yml up -d
echo.
echo 🔑 To get API keys:
echo    - NCBI: https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/
echo    - Gemini: https://makersuite.google.com/app/apikey
echo.
pause 