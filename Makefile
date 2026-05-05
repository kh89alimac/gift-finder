.PHONY: help install dev logs clean test migrate deploy rollback ps health scale

help:
	@echo "Gift Finder Project Commands"
	@echo ""
	@echo "Development:"
	@echo "  make install        Install all dependencies"
	@echo "  make dev            Start development environment"
	@echo "  make logs           Tail all service logs"
	@echo "  make clean          Stop and remove containers"
	@echo ""
	@echo "Testing:"
	@echo "  make test-backend   Run backend unit tests"
	@echo "  make test-frontend  Run frontend type-check and lint"
	@echo "  make test-all       Run all tests"
	@echo ""
	@echo "Database:"
	@echo "  make migrate        Run Alembic migrations"
	@echo "  make migrate-down   Downgrade last migration"
	@echo "  make db-shell       Connect to database shell"
	@echo ""
	@echo "Operations:"
	@echo "  make ps             Show running containers"
	@echo "  make health         Check health endpoints"
	@echo "  make scale          Scale workers (WORKERS=8 make scale)"
	@echo "  make logs-api       Tail API logs"
	@echo "  make logs-worker    Tail worker logs"
	@echo "  make logs-db        Tail database logs"
	@echo ""

# Development commands
install:
	@echo "Installing dependencies..."
	cd backend && pip install -e ".[dev]"
	cd frontend && npm ci

dev:
	@echo "Starting development environment..."
	docker compose up --build

logs:
	docker compose logs -f

clean:
	@echo "Stopping and removing containers..."
	docker compose down
	@echo "✓ Environment cleaned"

# Testing commands
test-backend:
	@echo "Running backend tests..."
	cd backend && pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=70

test-frontend:
	@echo "Running frontend tests..."
	cd frontend && npm run type-check && npm run lint && npm run build

test-all: test-backend test-frontend
	@echo "✓ All tests passed"

# Database commands
migrate:
	@echo "Running Alembic migrations..."
	docker compose exec api alembic upgrade head
	docker compose exec api alembic upgrade 002_hnsw_index || echo "ℹ HNSW migration not available"
	@echo "✓ Migrations complete"

migrate-down:
	@echo "Downgrading last migration..."
	docker compose exec api alembic downgrade -1
	@echo "✓ Downgrade complete"

db-shell:
	@echo "Connecting to database..."
	docker compose exec postgres psql -U gift -d giftfinder

db-backup:
	@echo "Backing up database..."
	docker compose exec -T postgres pg_dump -U gift -d giftfinder | gzip > backup-$$(date +%Y%m%d_%H%M%S).sql.gz
	@echo "✓ Backup complete"

# Operational commands
ps:
	docker compose ps

health:
	@echo "Checking health endpoints..."
	@echo ""
	@echo "API:"
	@curl -s http://localhost:8000/api/v1/health | jq . || echo "❌ API unhealthy"
	@echo ""
	@echo "Frontend:"
	@curl -s http://localhost:3000/ | head -1 || echo "❌ Frontend unhealthy"
	@echo ""
	@echo "Flower (Celery):"
	@curl -s http://localhost:5555/ | head -1 || echo "❌ Flower unhealthy"

scale:
	@echo "Scaling workers to $(WORKERS) instances..."
	docker compose up -d --scale worker=$(WORKERS) worker
	@sleep 2
	docker compose ps | grep worker

# Log commands
logs-api:
	docker compose logs -f api

logs-worker:
	docker compose logs -f worker

logs-beat:
	docker compose logs -f beat

logs-frontend:
	docker compose logs -f frontend

logs-db:
	docker compose logs -f postgres

logs-redis:
	docker compose logs -f redis

# Production-like environment
prod-env:
	@echo "Creating production-like environment..."
	@echo "1. Copy .env.example to .env"
	cp .env.example .env
	@echo "2. Edit .env with production values"
	@echo "3. Run: docker compose -f docker-compose.yml up -d"
	@echo ""
	@echo "Note: Production deployments use GitHub Actions"
	@echo "See DEPLOYMENT.md for automated deployment procedures"

# Utility commands
shell-api:
	docker compose exec api bash

shell-worker:
	docker compose exec worker bash

shell-postgres:
	docker compose exec postgres bash

shell-redis:
	docker compose exec redis sh

# Build commands
build:
	docker compose build

build-api:
	docker compose build api

build-worker:
	docker compose build worker

build-frontend:
	docker compose build frontend

# Docker commands
docker-clean:
	@echo "Cleaning up Docker resources..."
	docker image prune -af
	docker volume prune -f
	@echo "✓ Docker cleanup complete"

# Security commands
audit-backend:
	@echo "Auditing backend dependencies..."
	cd backend && pip-audit

audit-frontend:
	@echo "Auditing frontend dependencies..."
	cd frontend && npm audit

audit: audit-backend audit-frontend
	@echo "✓ Security audit complete"

# Monitoring commands
monitor:
	watch -n 2 'docker compose ps'

monitor-stats:
	docker stats --no-stream

# Deployment helpers
deploy-help:
	@echo "Production deployment is automated via GitHub Actions"
	@echo ""
	@echo "To deploy:"
	@echo "  1. Create feature branch: git checkout -b feature/xxx"
	@echo "  2. Make changes and test locally: make test-all"
	@echo "  3. Commit and push: git push origin feature/xxx"
	@echo "  4. Create PR on GitHub"
	@echo "  5. Merge to main (GitHub Actions runs automatically)"
	@echo ""
	@echo "Monitor deployment:"
	@echo "  https://github.com/yourorg/giftfinder/actions"
	@echo ""
	@echo "For manual deployment, see RUNBOOK.md"

# Default target
.DEFAULT_GOAL := help
