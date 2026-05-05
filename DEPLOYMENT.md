# Gift Finder Deployment Guide

Quick reference for common deployment tasks.

## Local Development

### Start the stack

```bash
# Copy environment template
cp .env.example .env

# Start services
docker compose up --build

# Run migrations
docker compose exec api alembic upgrade head

# Access services
# Frontend: http://localhost:3000
# API: http://localhost:8000/api/v1/docs
# Flower: http://localhost:5555
```

### Stop the stack

```bash
# Stop all services (keep data)
docker compose down

# Stop and remove all volumes (clean slate)
docker compose down -v
```

## Production Deployment

### GitHub Actions Automated Deploy

Simply merge to `main` branch:

```bash
git checkout -b feature/my-change
# ... make changes ...
git commit -am "Add my feature"
git push origin feature/my-change

# Create PR and merge to main
# GitHub Actions will automatically:
# 1. Run CI tests
# 2. Build and push Docker images to GHCR
# 3. Run database migrations
# 4. Deploy to production
# 5. Run smoke tests
```

Monitor deployment: https://github.com/yourorg/giftfinder/actions

### Manual Deployment (if needed)

```bash
# SSH to production
ssh deploy@your-domain.com
cd /app/giftfinder

# Pull latest code
git fetch origin main && git checkout origin/main

# Update services
docker compose pull
docker compose up -d

# Verify
docker compose ps
curl https://your-domain.com/api/v1/health
```

## Environment Variables

All environment variables are documented in `.env.example`.

Required secrets in `.env` (never commit!):
- `JWT_SECRET` - Generate: `openssl rand -hex 32`
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` - From AWS IAM
- `OPENAI_API_KEY` - From OpenAI dashboard
- `INSTAGRAM_ACCESS_TOKEN` - From Instagram/Facebook Graph API

## Database Migrations

Migrations run automatically when services start.

To manually run:

```bash
docker compose exec api alembic upgrade head
docker compose exec api alembic current  # Check status
docker compose exec api alembic history  # View all migrations
```

## Monitoring

- **Application Logs**: `docker compose logs -f api`
- **Worker Status**: http://localhost:5555
- **Health Check**: `curl http://localhost:8000/api/v1/health | jq`
- **Database**: `docker compose exec postgres psql -U gift -d giftfinder`
- **Redis**: `docker compose exec redis redis-cli info`

## Troubleshooting

See [RUNBOOK.md](RUNBOOK.md) for detailed incident response procedures.

Quick fixes:

```bash
# API not responding
docker compose restart api

# Workers stuck
docker compose restart worker beat

# Database connection issues
docker compose restart postgres

# View detailed logs
docker compose logs --tail=100 api
docker compose logs --tail=100 worker
docker compose logs --tail=100 postgres
```

## Scaling

```bash
# More API servers (behind load balancer)
docker compose up -d --scale api=3 api

# More Celery workers (for background jobs)
docker compose up -d --scale worker=8 worker

# Increase worker concurrency
# Edit docker-compose.yml: --concurrency=8
docker compose up -d worker
```

## Secrets Management

Use `.env` file (never commit to git):

```bash
# Generate secure secrets
openssl rand -hex 32  # JWT_SECRET
openssl rand -hex 16  # FLOWER_PASSWORD

# Add to .env, keep confidential
vi .env

# Add .env to .gitignore (should already be there)
echo ".env" >> .gitignore
```

## Backups

```bash
# Manual database backup
docker compose exec postgres pg_dump -U gift -d giftfinder | gzip > backup.sql.gz

# Restore from backup
docker compose exec -T postgres psql -U gift -d giftfinder < backup.sql.gz

# S3 backup verification (requires AWS CLI)
aws s3 ls s3://giftfinder-images/
```

## Rollback

If deployment fails:

```bash
# Redeploy previous version
git checkout <previous-commit-sha>
docker compose up -d --build

# Or use Docker image tags
docker compose pull  # Gets latest stable
docker compose up -d
```

For database rollback, see RUNBOOK.md section "Database Rollback".

## Useful Commands

```bash
# Check all service status
docker compose ps

# View logs for specific service
docker compose logs -f api          # API server
docker compose logs -f worker       # Celery workers
docker compose logs -f postgres     # Database
docker compose logs -f redis        # Cache

# Execute command in container
docker compose exec api python -c "from app.main import app; print('✓ API loads OK')"

# SSH into container
docker compose exec api bash

# Check database size
docker compose exec postgres du -sh /var/lib/postgresql/data

# Monitor in real-time
watch -n 2 'docker compose ps'
watch -n 2 'docker stats'
```

## CI/CD Status

Current test coverage: 70%+ (enforced by CI)

Check test results: https://github.com/yourorg/giftfinder/actions

Running tests locally:

```bash
# Backend tests
cd backend && pytest tests/ --cov=app --cov-fail-under=70

# Frontend tests
cd frontend && npm run type-check && npm run lint

# Security scanning
cd backend && pip-audit
cd frontend && npm audit
```

---

For detailed operations, see [RUNBOOK.md](RUNBOOK.md).
