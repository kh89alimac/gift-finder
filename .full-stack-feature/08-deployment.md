# Deployment & Infrastructure: Gift Finder App

## Files Created (14 new files, 3 modified)

### Docker & Containerization
- `frontend/Dockerfile` — Multi-stage Next.js build (deps → builder → standalone runner, non-root `nextjs` user)
- `docker-compose.yml` — Updated: frontend service, migration job, health checks, networks, resource limits, env_file
- `docker-compose.override.yml.example` — Local development overrides
- `docker-compose.prod.yml.example` — Production HA configuration

### CI/CD (`.github/workflows/`)
- `ci.yml` — PR pipeline: backend pytest (70% coverage), frontend type-check + lint, pip-audit + npm audit security scans, Docker build validation
- `deploy.yml` — Push-to-main: build+push to GHCR, run Alembic migrations, deploy API+frontend via SSH+docker-compose, smoke tests

### Backend
- `backend/app/api/v1/health.py` — `/api/v1/health` endpoint: checks DB (`SELECT 1`) + Redis (`PING`), returns `{status, checks}` 
- `backend/app/api/v1/router.py` — Updated to register health router

### Config & Secrets
- `.env.example` — All required env vars documented (APP_ENV, JWT_SECRET, DATABASE_URL, REDIS_URL, AWS, OPENAI_API_KEY, INSTAGRAM_ACCESS_TOKEN, FLOWER auth)
- `.github/DEPLOYMENT_SECRETS.md` — GitHub Actions secrets setup guide

### Monitoring
- `monitoring/alerts.yml` — 25+ Prometheus alerting rules: HTTP error rate > 5%, scraper job backlog > 50, review queue > 200 pending, embedding task lag > 60s, DB connection pool, Redis memory, etc.

### Documentation
- `RUNBOOK.md` — Complete ops manual: prerequisites, first-time deploy, routine deploy, Alembic migration procedure (including HNSW migration outside transaction), rollback, scaling, incident response, secrets rotation
- `QUICKSTART.md` — 5-minute local setup
- `DEPLOYMENT.md` — Quick deployment reference
- `PRODUCTION_CHECKLIST.md` — Pre-flight verification checklist
- `Makefile` — 30+ commands (make dev, make test, make migrate, make deploy, make logs, etc.)

## CI/CD Pipeline

```
PR opened → ci.yml
  ├── backend-test (pytest, coverage)
  ├── frontend-test (tsc, lint)
  ├── security-scan (pip-audit, npm audit)
  └── docker-build (validate images)

Push to main → deploy.yml
  ├── build-and-push (GHCR: SHA + latest tags)
  ├── migrate (alembic upgrade head, needs postgres)
  ├── deploy-backend (SSH → docker compose up -d, health check)
  ├── deploy-frontend (same)
  └── smoke-test (register → list items → cleanup)
```

## Key deployment decisions

- **Zero-downtime**: Rolling update via docker-compose pull + up -d; health check gate before marking deploy complete
- **Migration safety**: Migration job runs as a one-shot container before API deploy; HNSW migration (`002`) uses `CREATE INDEX CONCURRENTLY` — must run outside Alembic transaction (documented in RUNBOOK.md)
- **Secrets**: No secrets in docker-compose.yml; all from `.env` file or GitHub Secrets
- **Flower auth**: `FLOWER_BASIC_AUTH=${FLOWER_USER}:${FLOWER_PASSWORD}` — not exposed without credentials
- **Rollback**: `docker compose up -d --scale api=0 && docker compose up -d backend:previous-sha` + `alembic downgrade -1`
