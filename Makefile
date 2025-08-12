.PHONY: help build run start stop logs clean

help: ## Show this help message
	@echo "🚀 BugSigDB Analyzer - Available Commands"
	@echo "=========================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

build: ## Build the analyzer Docker image
	docker build -t bugsigdb-analyzer .

run: ## Run the analyzer (builds if needed)
	docker compose up --build -d

start: ## Start all services
	docker compose up -d

stop: ## Stop all services
	docker compose down

logs: ## View analyzer logs
	docker compose logs -f analyzer

status: ## Show service status
	docker compose ps

health: ## Check application health
	curl -f http://localhost:8000/health || echo "Service not healthy"

clean: ## Remove all containers and images
	docker compose down -v --rmi all
	docker rmi bugsigdb-analyzer 2>/dev/null || true

restart: ## Restart all services
	docker compose restart

shell: ## Open shell in analyzer container
	docker compose exec analyzer bash

# Quick start - builds and runs everything
all: build run ## Build and run everything (recommended for first time) 