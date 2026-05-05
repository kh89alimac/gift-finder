# Quick Start Guide

Get Gift Finder running locally in 5 minutes.

## Prerequisites

- Docker and Docker Compose installed
- Git installed
- Port 3000, 5000, 5555, 6379, 8000, 5432 available

## Local Development (5 minutes)

```bash
# 1. Clone or navigate to project
cd /path/to/giftfinder

# 2. Copy environment template
cp .env.example .env

# 3. Start all services
docker compose up --build

# 4. Wait for migrations (check logs)
# Should see: "Upgrade completed"
```

## Access Applications

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | - |
| API Docs | http://localhost:8000/api/v1/docs | - |
| API Redoc | http://localhost:8000/api/v1/redoc | - |
| Flower (Workers) | http://localhost:5555 | admin / changeme |
| Database | localhost:5432 | gift / gift |
| Redis | localhost:6379 | - |

## Common Commands

```bash
# View logs
docker compose logs -f api

# Run tests
cd backend && pytest tests/ --cov=app --cov-fail-under=70

# Connect to database
docker compose exec postgres psql -U gift -d giftfinder

# Scale workers
docker compose up -d --scale worker=8 worker

# Restart a service
docker compose restart api

# Stop everything
docker compose down

# Clean slate
docker compose down -v
```

## Make Commands

We provide a Makefile with helpful shortcuts:

```bash
make help              # Show all available commands
make dev              # Start development environment
make test-all         # Run all tests
make migrate          # Run database migrations
make health           # Check service health
make logs-api         # View API logs
make scale WORKERS=8  # Scale Celery workers
```

## Troubleshooting

### "Address already in use"

Port is occupied. Either:
1. Stop other services: `lsof -i :8000` then `kill <PID>`
2. Change port in docker-compose.yml and .env

### "Database connection refused"

```bash
# Wait longer for database startup
docker compose ps postgres
# Should show "healthy" status

# Or restart postgres
docker compose restart postgres
```

### "Migrations failed"

```bash
# Check migration logs
docker compose logs migration

# Run manually
docker compose exec api alembic upgrade head
```

### Tests fail with "pytest: command not found"

```bash
# Install test dependencies
cd backend
pip install -e ".[dev]"
```

### Node_modules issues in frontend

```bash
cd frontend
rm -rf node_modules package-lock.json
npm ci
```

## Next Steps

1. **Read documentation**:
   - [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment procedures
   - [RUNBOOK.md](RUNBOOK.md) - Operations guide
   - API docs at http://localhost:8000/api/v1/docs

2. **Explore the code**:
   - Frontend: `frontend/src/app/` (Next.js 14)
   - Backend: `backend/app/` (FastAPI)
   - Workers: `backend/app/workers/` (Celery tasks)

3. **Configure external services** (if needed):
   - Update `.env` with OpenAI API key for embeddings
   - Update `.env` with Instagram token for scraping
   - Update `.env` with AWS credentials for S3 storage

4. **Run tests before committing**:
   ```bash
   make test-all
   ```

5. **Deploy to production**:
   - Merge to `main` branch
   - GitHub Actions automatically deploys (see [DEPLOYMENT.md](DEPLOYMENT.md))

## Getting Help

- **API Issues**: Check http://localhost:8000/api/v1/docs for endpoint documentation
- **Database Issues**: See [RUNBOOK.md](RUNBOOK.md) section "Database Issues"
- **Performance Issues**: Use `docker stats` to monitor resource usage
- **Celery Issues**: Check http://localhost:5555 (Flower) for task status

## Resources

- [API Documentation](http://localhost:8000/api/v1/docs)
- [Deployment Guide](DEPLOYMENT.md)
- [Operations Runbook](RUNBOOK.md)
- [Production Checklist](PRODUCTION_CHECKLIST.md)
- [Make Commands](Makefile)

---

**Tips**:
- Use `make help` to see all available commands
- Keep `.env` file private (never commit to git)
- Always run tests before pushing code
- Check logs with `docker compose logs -f <service>` for debugging
