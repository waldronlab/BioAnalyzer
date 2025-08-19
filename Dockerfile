FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV WATCHFILES_FORCE_POLLING=true

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements and install Python dependencies with retry logic
COPY config/requirements.txt .
RUN pip install --no-cache-dir --timeout 300 --retries 5 -r requirements.txt || \
    (echo "First attempt failed, retrying..." && \
     pip install --no-cache-dir --timeout 600 --retries 10 -r requirements.txt) || \
    (echo "Second attempt failed, retrying with different index..." && \
     pip install --no-cache-dir --timeout 600 --retries 10 --index-url https://pypi.org/simple/ -r requirements.txt)

# Install development dependencies for auto-reload
RUN pip install --no-cache-dir watchfiles[watchdog] uvicorn[standard]

# Copy application code
COPY app/ ./app/
COPY config/ ./config/
COPY frontend/ ./frontend/
COPY main.py .

# Create necessary directories
RUN mkdir -p data cache results

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the application with auto-reload
CMD ["python", "main.py"] 