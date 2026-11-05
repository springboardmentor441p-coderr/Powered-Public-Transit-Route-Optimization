# AI MetroFlow - Makefile
# Common development commands

.PHONY: help dev build test clean migrate init-data

# Default target
help:
	@echo "AI MetroFlow - Development Commands"
	@echo ""
	@echo "Usage:"
	@echo "  make dev          Start development environment (Docker)"
	@echo "  make dev-local    Start development environment (local)"
	@echo "  make build        Build Docker images"
	@echo "  make test         Run all tests"
	@echo "  make test-backend Run backend tests"
	@echo "  make test-frontend Run frontend tests"
	@echo "  make migrate      Run database migrations"
	@echo "  make init-data    Initialize default data"
	@echo "  make clean        Clean up containers and volumes"
	@echo "  make logs         View Docker logs"
	@echo "  make shell-backend Get backend shell"
	@echo "  make shell-frontend Get frontend shell"
	@echo "  make format       Format code (black, isort, prettier)"

# Development with Docker
dev:
	docker-compose up -d
	@echo "Services started:"
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend API: http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/docs"

# Development locally (requires Python, Node.js, PostgreSQL, MongoDB, Redis)
dev-local:
	@echo "Starting backend..."
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
	@echo "Starting frontend..."
	cd frontend && npm run dev

# Build Docker images
build:
	docker-compose build

# Run tests
test: test-backend test-frontend

test-backend:
	cd backend && pytest -v

test-frontend:
	cd frontend && npm test

# Database migrations
migrate:
	docker-compose exec backend alembic upgrade head

migrate-create:
	@read -p "Enter migration message: " msg; \
	docker-compose exec backend alembic revision --autogenerate -m "$$msg"

# Initialize default data
init-data:
	docker-compose exec backend python -c "import asyncio; from app.main import init_default_data; asyncio.run(init_default_data())"

# Clean up
clean:
	docker-compose down -v
	docker system prune -f

# View logs
logs:
	docker-compose logs -f

logs-backend:
	docker-compose logs -f backend

logs-frontend:
	docker-compose logs -f frontend

# Get shell access
shell-backend:
	docker-compose exec backend bash

shell-frontend:
	docker-compose exec frontend sh

shell-db:
	docker-compose exec postgres psql -U metroflow -d metroflow

# Format code
format: format-backend format-frontend

format-backend:
	cd backend && black . && isort .

format-frontend:
	cd frontend && npm run lint -- --fix

# Lint code
lint: lint-backend lint-frontend

lint-backend:
	cd backend && black --check . && isort --check-only . && mypy app

lint-frontend:
	cd frontend && npm run lint

# Check types
type-check:
	cd backend && mypy app

# Generate requirements
requirements:
	cd backend && pip freeze > requirements.txt

# Update dependencies
update-deps:
	cd backend && pip install --upgrade -r requirements.txt
	cd frontend && npm update

# GTFS data loading
load-gtfs:
	@read -p "Enter GTFS directory path: " path; \
	docker-compose exec backend python scripts/load_gtfs_data.py "$$path"

# Backup database
backup-db:
	docker-compose exec postgres pg_dump -U metroflow metroflow > backup_$$(date +%Y%m%d_%H%M%S).sql

# Restore database
restore-db:
	@read -p "Enter backup file path: " file; \
	docker-compose exec -T postgres psql -U metroflow -d metroflow < "$$file"

# Reset everything
reset: clean dev

# Production deployment
prod-build:
	docker-compose -f docker-compose.prod.yml build

prod-up:
	docker-compose -f docker-compose.prod.yml up -d

prod-down:
	docker-compose -f docker-compose.prod.yml down

# Health check
health:
	curl -f http://localhost:8000/health || exit 1
	curl -f http://localhost:3000/ || exit 1

# Check status
status:
	docker-compose ps