.PHONY: help install test lint format clean run-backend run-frontend

help:
	@echo "CodeDNA Development Commands:"
	@echo "  make install        Install backend and frontend dependencies"
	@echo "  make test           Run all tests across backend and frontend"
	@echo "  make lint           Run linters (ruff, mypy, eslint)"
	@echo "  make format         Auto-format codebases"
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

lint:
	cd backend && ruff check . && mypy app
	cd frontend && npm run lint

format:
	cd backend && ruff format .
