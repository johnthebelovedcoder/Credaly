# Credaly — Predictive Behavioral Credit & Insurance Platform
# Makefile for local development.

.PHONY: help install dev test lint migrate sandbox docker-up docker-down clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Setup ────────────────────────────────────────────────────────────

install: ## Install all dependencies (Python + Node.js)
install: install-python install-node

install-python: ## Install Python dependencies
	cd services/scoring-api && pip install -r requirements.txt
	cd services/scoring-api && pip install pytest pytest-asyncio httpx

install-node: ## Install Node.js dependencies
	npm install
	cd services/admin-api && npm install

# ── Development ──────────────────────────────────────────────────────

dev: ## Start both services in watch mode
	npm run dev

dev-python: ## Start scoring API only
	cd services/scoring-api && uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

dev-admin: ## Start admin API only
	npm run dev:admin

# ── Testing ──────────────────────────────────────────────────────────

test: ## Run all tests
test: test-python test-admin

test-python: ## Run Python tests
	cd services/scoring-api && pytest -v --tb=short

test-admin: ## Run TypeScript tests
	npm run test:admin

# ── Linting ──────────────────────────────────────────────────────────

lint: ## Run linters
	cd services/scoring-api && python -m flake8 src/ --max-line-length=120 || true
	npm run lint:admin || true

# ── Database ─────────────────────────────────────────────────────────

migrate: ## Run database migrations
	cd services/scoring-api && alembic upgrade head

migrate-gen: ## Generate a new migration
	@echo "Usage: make migrate-gen MSG='your message'"
	cd services/scoring-api && alembic revision --autogenerate -m "$(MSG)"

# ── Sandbox ──────────────────────────────────────────────────────────

sandbox: ## Generate 100 synthetic sandbox borrowers
	cd services/scoring-api && python -m scripts.generate_sandbox_data

# ── Docker ───────────────────────────────────────────────────────────

docker-up: ## Start all services via Docker Compose
	docker compose up --build

docker-down: ## Stop all Docker services
	docker compose down

docker-clean: ## Stop and remove all Docker resources
	docker compose down -v --remove-orphans

# ── Cleanup ──────────────────────────────────────────────────────────

clean: ## Remove generated files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf services/scoring-api/.pytest_cache 2>/dev/null || true
	rm -rf services/scoring-api/htmlcov 2>/dev/null || true
	rm -rf services/scoring-api/coverage.xml 2>/dev/null || true
	rm -f services/scoring-api/credaly.db 2>/dev/null || true
	rm -rf services/admin-api/dist 2>/dev/null || true
	rm -rf services/admin-api/coverage 2>/dev/null || true
	rm -rf services/admin-api/node_modules 2>/dev/null || true
