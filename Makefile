.PHONY: help install test lint format clean run-backend run-frontend verify evaluate build

help:
	@echo "CodeDNA Development & Verification Commands:"
	@echo "  make install        Install backend and frontend dependencies"
	@echo "  make test           Run all tests across backend and frontend"
	@echo "  make verify         Run mandatory 9-step connection verification"
	@echo "  make evaluate       Run 3-scenario memory evaluation benchmark"
	@echo "  make lint           Run linters (ruff, mypy, eslint)"
	@echo "  make format         Auto-format codebases"
	@echo "  make build          Build Next.js production frontend"
	@echo "  make run-backend    Start FastAPI backend server"
	@echo "  make run-frontend   Start Next.js frontend dev server"

install:
	cd backend && pip install -r requirements.txt -r requirements-dev.txt
	cd frontend && npm install

test-backend:
	cd backend && pytest -v

test-frontend:
	cd frontend && npm run typecheck

test: test-backend test-frontend

verify:
	python scripts/verify_connections.py

evaluate:
	python scripts/run_memory_evaluation.py

lint:
	cd backend && ruff check app tests && mypy app
	cd frontend && npm run lint

format:
	cd backend && ruff format app tests

build:
	cd frontend && npm run build

run-backend:
	cd backend && uvicorn app.main:app --reload --port 8000

run-frontend:
	cd frontend && npm run dev
