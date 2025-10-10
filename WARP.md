# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

Project summary
- BioAnalyzer is a FastAPI-based web app with a static frontend that analyzes PubMed papers for BugSigDB curation readiness across six key fields: host_species, body_site, condition, sequencing_type, taxa_level, and sample_size.
- Primary entrypoint: main.py (runs FastAPI app and serves frontend under /static).

Common commands
- Local (no Docker)
  ```bash path=null start=null
  # Setup once
  ./setup.sh
  # or ensure deps and run directly
  ./start.sh
  # start server (hot-reload)
  python3 main.py
  ```

- Containers (Docker/Compose)
  ```bash path=null start=null
  # Build image and run services (analyzer, optional nginx, optional redis)
  make build
  make start

  # Stop/clean
  make stop
  make clean

  # Logs and status
  make logs
  make status
  make shell   # open bash in analyzer container

  # One-shot health
  make health
  ```

- Development helper (interactive; only if docker-compose.dev.yml exists)
  ```bash path=null start=null
  ./dev.sh start-build      # first run or after dependency changes
  ./dev.sh start-no-build   # faster subsequent runs
  ./dev.sh logs
  ./dev.sh stop
  ```
  Note: If docker-compose.dev.yml is not present, prefer the Makefile targets above.

- Testing (pytest is referenced in docs and config/pytest.ini)
  ```bash path=null start=null
  # Run all tests
  pytest

  # Run with coverage
  pytest --cov=.

  # Run a single file or test
  pytest tests/test_app.py
  pytest -k "test_name_substring" -q
  ```

- Lint/format (from docs/README.md; install tools if needed)
  ```bash path=null start=null
  flake8 .
  black .
  ```

- Curl smoke checks (when running locally)
  ```bash path=null start=null
  curl -f http://127.0.0.1:8000/health
  curl -f http://127.0.0.1:8000/api/v1/config
  curl -f http://127.0.0.1:8000/api/v1/version
  ```

Environment and configuration
- Environment variables are loaded via app/utils/config.py. Create a .env in the repo root (scripts will help generate it) with at least:
  - NCBI_API_KEY
  - GEMINI_API_KEY
  - Optional: EMAIL, DEFAULT_MODEL, DEBUG, LOG_LEVEL, timeouts (API_TIMEOUT, ANALYSIS_TIMEOUT, GEMINI_TIMEOUT, FRONTEND_TIMEOUT)
- Directories created/used: data, cache, results, logs.
- Cache is a local sqlite database at cache/analysis_cache.db (safe to delete to reset cache).

High-level architecture
- Backend (FastAPI)
  - app/api/app.py defines the application and mounts:
    - Routers under prefix /api/v1:
      - Paper analysis: app/api/routers/paper_analysis.py
      - Batch processing: app/api/routers/batch_processing.py
      - Cache management: app/api/routers/cache_management.py
      - System/health/metrics: app/api/routers/system.py
    - Static frontend mounted at /static from frontend/.
  - Entry process main.py runs uvicorn on 0.0.0.0:8000 with reload for development.

- Core services and utilities
  - Retrieval: app/services/data_retrieval.py (PubMedRetriever)
    - Uses NCBI E-Utilities (efetch/esummary/esearch) with rate limiting and timeouts.
  - Caching: app/services/cache_manager.py
    - sqlite3-backed caches: analysis_cache, metadata_cache, fulltext_cache with indexes; async wrappers for throughput.
  - Text processing: app/utils/text_processing.py (tokenization via tiktoken with fallbacks) and AdvancedTextProcessor used in analysis.
  - Field/score helpers: app/utils/field_validator.py, app/utils/methods_scorer.py, app/api/utils/api_utils.py for standardized field structures and summaries.
  - Unified QA/LLM: app/models/unified_qa.py wraps app/models/gemini_qa.py when GEMINI_API_KEY is configured; falls back gracefully if absent.
  - Configuration and logging: app/utils/config.py loads .env from several locations, sets timeouts and logging with rotation.

- Frontend
  - Served from frontend/ via /static. Key files: index.html, js/app.js, js/curation-analysis.js.
  - Calls backend endpoints including:
    - GET /api/v1/enhanced_analysis/{pmid}
    - POST /api/v1/enhanced_analysis_batch (body: JSON array of PMIDs)
    - POST /api/v1/upload_csv (multipart)
    - GET /api/v1/config, /api/v1/health, /api/v1/metrics
    - WebSocket /ws for interactive Q&A

- Data flow (big picture)
  1) Client requests analysis (single or batch) → paper_analysis/batch_processing routers
  2) PubMedRetriever fetches abstract/full text (parallel, timeout-bounded)
  3) AdvancedTextProcessor prepares text; UnifiedQA queries model (if configured) to extract the six curation fields
  4) Results normalized into a consistent field structure; summaries generated
  5) CacheManager persists analysis/metadata/fulltext; responses returned to client

Deployment notes
- Dockerfile builds a Python 3.11-slim image, installs deps from config/requirements.txt, and runs main.py.
- docker-compose.yml defines:
  - analyzer (the FastAPI app on 8000 with volume mounts for live reload)
  - nginx (reverse proxy) and redis (optional); verify referenced nginx config paths under deployment/nginx/ and deployment/docker/nginx.Dockerfile exist before enabling.
- Health checks are exposed at /health and /api/v1/health.

Useful repository references
- Root README.md: feature overview, endpoints, and dev entrypoints (./dev.sh and ./start.sh).
- docs/QUICKSTART.md and docs/DOCKER_DEPLOYMENT.md: additional setup/deploy guidance. Prefer the Makefile for a consistent local experience.

Troubleshooting quick tips
- If the analyzer starts but nginx fails in Compose, run only the analyzer service (make start) or comment out nginx; ensure referenced nginx files exist.
- If GEMINI_API_KEY is unset, analysis falls back with limited functionality; health endpoints will report status accordingly.
- To reset state: stop services and remove cache/analysis_cache.db and the data/cache/results directories as needed.
