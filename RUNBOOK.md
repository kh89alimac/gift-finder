# Gift Finder Deployment & Operations Runbook

This document provides comprehensive procedures for deploying, maintaining, and troubleshooting the Gift Finder application in production environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [First-Time Deployment](#first-time-deployment)
3. [Routine Deployment](#routine-deployment)
4. [Database Migrations](#database-migrations)
5. [Rollback Procedures](#rollback-procedures)
6. [Scaling](#scaling)
7. [Incident Response](#incident-response)
8. [Secrets Rotation](#secrets-rotation)
9. [Monitoring & Alerting](#monitoring--alerting)
10. [Backup & Disaster Recovery](#backup--disaster-recovery)

---

## Prerequisites

### Required Environment Variables

Before deploying, ensure you have configured all required environment variables in `.env`:

```bash
# Copy the template
cp .env.example .env

# Edit and fill in all values
vi .env
```

### External Services Setup

#### AWS S3 Bucket

Create an S3 bucket for image storage:

```bash
aws s3api create-bucket \
  --bucket giftfinder-images \
  --region us-east-1 \
  --acl private

# Enable versioning (optional but recommended)
aws s3api put-bucket-versioning \
  --bucket giftfinder-images \
  --versioning-configuration Status=Enabled

# Set lifecycle policy to delete old image versions after 30 days
aws s3api put-bucket-lifecycle-configuration \
  --bucket giftfinder-images \
  --lifecycle-configuration '{
    "Rules": [{
      "Id": "DeleteOldVersions",
      "Status": "Enabled",
      "NoncurrentVersionExpiration": {"NoncurrentDays": 30}
    }]
  }'
```

Create IAM user for app access:

```bash
# Create user
aws iam create-user --user-name giftfinder-app

# Create access key
aws iam create-access-key --user-name giftfinder-app

# Create inline policy
aws iam put-user-policy --user-name giftfinder-app --policy-name s3-access --policy-document '{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket"
    ],
    "Resource": [
      "arn:aws:s3:::giftfinder-images",
      "arn:aws:s3:::giftfinder-images/*"
    ]
  }]
}'
```

#### Instagram Graph API

Set up Instagram Business Account access:

1. Create/upgrade to Instagram Business Account
2. Create Facebook app: https://developers.facebook.com
3. Configure Instagram Graph API permissions in app settings
4. Generate long-lived access token (valid for ~60 days):
   ```bash
   curl -X GET "https://graph.instagram.com/v18.0/me/accounts?fields=id,username&access_token=YOUR_SHORT_LIVED_TOKEN"
   ```
5. Store `INSTAGRAM_ACCESS_TOKEN` in `.env`

Refresh token before expiry (set reminder for 45 days):

```bash
curl -X GET \
  "https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=YOUR_LONG_LIVED_TOKEN"
```

#### OpenAI API

Generate API key from https://platform.openai.com/api-keys and set `OPENAI_API_KEY` in `.env`.

#### PostgreSQL pgvector Extension

The Docker image `pgvector/pgvector:pg16` includes the extension pre-installed. To use it in your database:

```bash
# Connect to the database
psql postgresql://gift:gift@localhost:5432/giftfinder

# Create extension (done automatically by migrations, but verify)
CREATE EXTENSION IF NOT EXISTS vector;

# Verify
SELECT * FROM pg_extension WHERE extname = 'vector';
```

---

## First-Time Deployment

### Step 1: Prepare the Server

```bash
# SSH to deployment server
ssh deploy@your-server.com

# Create app directory
sudo mkdir -p /app/giftfinder
sudo chown deploy:deploy /app/giftfinder
cd /app/giftfinder

# Install Docker and Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker deploy

# Verify installation
docker --version
docker compose --version
```

### Step 2: Clone Repository & Configure

```bash
cd /app/giftfinder

# Clone repo (or use git pull for updates)
git clone https://github.com/yourorg/giftfinder.git .
git checkout main

# Copy environment template and fill in values
cp .env.example .env
vi .env  # Edit all placeholder values

# Verify critical env vars
echo "Database: $DATABASE_URL"
echo "Redis: $REDIS_URL"
echo "S3 bucket: $S3_BUCKET"
```

### Step 3: Start Services

```bash
# Build images (on first run)
docker compose build

# Bring up all services
docker compose up -d

# Wait for database migrations
sleep 10
docker compose logs migration

# Verify all services are running
docker compose ps

# Check health endpoints
curl http://localhost:8000/api/v1/health
curl http://localhost:3000/
curl http://localhost:5555/  # Flower
```

### Step 4: Verify Application

```bash
# Test backend API
curl -X GET http://localhost:8000/api/v1/docs

# Test frontend
open http://localhost:3000

# Test Celery workers
docker compose logs worker | head -20

# Check Flower monitoring
open http://localhost:5555
# Login with: admin / <FLOWER_PASSWORD>
```

### Step 5: Configure Reverse Proxy (Nginx)

```bash
# Install Nginx
sudo apt-get update && sudo apt-get install -y nginx certbot python3-certbot-nginx

# Create Nginx config
sudo tee /etc/nginx/sites-available/giftfinder > /dev/null <<'EOF'
upstream api {
    server localhost:8000;
}

upstream frontend {
    server localhost:3000;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;
    
    # SSL certificates (configure with certbot)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # API routes
    location /api/ {
        proxy_pass http://api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support for real-time features (if used)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/giftfinder /etc/nginx/sites-enabled/

# Test config
sudo nginx -t

# Get SSL certificate
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Reload Nginx
sudo systemctl reload nginx
```

---

## Routine Deployment

### Zero-Downtime Deployment Process

This procedure ensures the application stays available throughout deployment.

#### Prerequisites

- All tests passing in CI/CD
- Code merged to `main` branch
- GitHub Actions build completed

#### Deployment Steps

```bash
# SSH to production server
ssh deploy@your-server.com
cd /app/giftfinder

# Step 1: Pull latest code
git fetch origin main
git checkout origin/main

# Step 2: Pull new Docker images
docker compose pull api worker beat frontend

# Step 3: Run database migrations (if any)
docker compose up -d migration
sleep 5
docker compose logs migration | tail -20

# Verify migrations succeeded
docker compose logs migration | grep -i "success\|complete\|upgrade"

# Step 4: Start updated services
# This performs a rolling restart:
# - Docker keeps the old container alive while pulling the new one
# - Once new container is ready, old one is stopped
docker compose up -d api worker beat frontend

# Step 5: Verify health
sleep 5
curl http://localhost:8000/api/v1/health | jq .
curl http://localhost:3000/ | head -20

# Step 6: Check logs for errors
docker compose logs --since 1m api worker beat frontend

# Step 7: Verify all services are running
docker compose ps

# Step 8: Test critical endpoints
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test-'"$(date +%s)"'@example.com",
    "password": "TestPassword123!",
    "full_name": "Test User"
  }'
```

#### Rollback (if needed)

If deployment fails, rollback to previous version:

```bash
# Get previous image SHA from docker history
docker compose down
docker compose pull

# Or explicitly specify previous image versions
export BACKEND_IMAGE=ghcr.io/yourorg/giftfinder/backend:previous-sha
docker compose up -d

# Verify
docker compose ps
```

---

## Database Migrations

### Running Migrations

Migrations are applied automatically when services start via the `migration` service in `docker-compose.yml`.

To manually run or verify migrations:

```bash
# View migration status
docker compose exec api alembic current

# View all migrations
docker compose exec api alembic history

# Run forward
docker compose exec api alembic upgrade head

# Run specific migration
docker compose exec api alembic upgrade 002_hnsw_index
```

### HNSW Index Migration

The `002_hnsw_index` migration creates a vector index for faster similarity searches. This migration:

- Uses `CREATE INDEX CONCURRENTLY` to avoid locking the table
- Must run outside a transaction
- Takes time proportional to dataset size

To run safely:

```bash
# Check current migration level
docker compose exec api alembic current

# If not at 002_hnsw_index, run it
docker compose exec api alembic upgrade 002_hnsw_index

# Monitor progress (in another terminal)
docker compose exec postgres psql -U gift -d giftfinder -c "
  SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as uses,
    idx_tup_read as read_tuples,
    idx_tup_fetch as fetched_tuples
  FROM pg_stat_user_indexes
  WHERE indexname LIKE '%hnsw%';
"

# Wait for index creation to complete
docker compose exec postgres psql -U gift -d giftfinder -c "
  SELECT pid, query, state
  FROM pg_stat_activity
  WHERE query LIKE '%CREATE INDEX%';
"
```

### Creating New Migrations

When you need to create a new migration:

```bash
# Connect to the database and make manual schema changes, OR

# Use Alembic to generate migration from models
docker compose exec api alembic revision --autogenerate -m "description of changes"

# Review the generated migration file
cat backend/alembic/versions/xxx_description.py

# Test the migration
docker compose exec api alembic upgrade head
docker compose exec api alembic downgrade -1
docker compose exec api alembic upgrade head
```

---

## Rollback Procedures

### Application Rollback

For rollback of application code:

```bash
# Identify previous version
git log --oneline -5

# Checkout previous version
git checkout <previous-commit-sha>

# Rebuild and deploy
docker compose up -d --build

# Verify
docker compose ps
curl http://localhost:8000/api/v1/health
```

### Database Rollback

**WARNING**: Database rollbacks can cause data loss. Only use when absolutely necessary.

```bash
# View current migration version
docker compose exec api alembic current

# Downgrade one migration
docker compose exec api alembic downgrade -1

# Downgrade to specific version
docker compose exec api alembic downgrade 001_initial_schema

# Verify
docker compose exec api alembic current
```

---

## Scaling

### Horizontal Scaling: Add More API Workers

```bash
# Check current API instances
docker compose ps | grep api

# Scale to 3 instances (behind load balancer)
docker compose up -d --scale api=3 api

# Verify
docker compose ps | grep api
curl http://localhost:8000/api/v1/health

# Note: Configure load balancer (Nginx/AWS ALB) to distribute traffic
```

### Horizontal Scaling: Add More Celery Workers

Celery workers process background jobs (scraping, embeddings, reviews).

```bash
# Check current workers
docker compose ps | grep worker

# Scale to 8 workers
docker compose up -d --scale worker=8 worker

# Verify
docker compose ps | grep worker

# Monitor via Flower
open http://localhost:5555

# Check task queue depth
docker compose exec redis redis-cli LLEN celery
```

### Vertical Scaling: Increase Worker Concurrency

```bash
# Edit docker-compose.yml and change WORKER_CONCURRENCY
vi docker-compose.yml

# Update environment variable
WORKER_CONCURRENCY=8  # was 4

# Restart workers
docker compose up -d worker beat

# Monitor memory and CPU
docker stats worker
```

### Connection Pool Tuning

For PostgreSQL connection pool (important when scaling API):

```bash
# Check current settings
docker compose exec postgres psql -U gift -d giftfinder -c "
  SHOW max_connections;
  SHOW shared_buffers;
"

# Increase max_connections for more API instances
docker compose exec postgres psql -U gift -d giftfinder -c "
  ALTER SYSTEM SET max_connections = 200;
"

docker compose restart postgres
```

For Redis connection pool (automatic, but verify):

```bash
# Check current connections
docker compose exec redis redis-cli INFO clients

# Monitor evictions when load increases
docker compose exec redis redis-cli INFO stats | grep evicted
```

---

## Incident Response

### Incident: Database Connection Pool Exhausted

**Symptoms**: API returns 500 errors with "connection pool timeout" or "too many connections"

**Diagnosis**:

```bash
# Check active connections
docker compose exec postgres psql -U gift -d giftfinder -c "
  SELECT count(*) FROM pg_stat_activity;
  SELECT state, count(*) FROM pg_stat_activity GROUP BY state;
"

# Kill idle connections older than 10 minutes
docker compose exec postgres psql -U gift -d giftfinder -c "
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE state = 'idle'
  AND query_start < now() - interval '10 minutes';
"
```

**Resolution**:

```bash
# Option 1: Scale down API instances temporarily
docker compose down api
docker compose up -d api  # Single instance

# Option 2: Increase max_connections
docker compose exec postgres psql -U gift -d giftfinder -c "
  ALTER SYSTEM SET max_connections = 300;
"
docker compose restart postgres

# Option 3: Increase SQLAlchemy pool size
# Edit .env: DATABASE_URL with pool_size and max_overflow
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db?pool_size=20&max_overflow=10
docker compose up -d api
```

### Incident: Celery Worker Queue Backlog

**Symptoms**: Tasks taking very long to process, scraper jobs piling up

**Diagnosis**:

```bash
# Check queue depth
docker compose exec redis redis-cli LLEN celery

# Check worker status
docker compose logs worker | tail -50

# Check Flower dashboard
open http://localhost:5555

# Identify stuck tasks
docker compose exec redis redis-cli LRANGE celery 0 20
```

**Resolution**:

```bash
# Increase worker concurrency
docker compose up -d --scale worker=8 worker

# Or increase concurrency per worker
vi docker-compose.yml
# Change: --concurrency=4 to --concurrency=8
docker compose up -d worker

# Monitor progress
watch -n 2 'docker compose exec redis redis-cli LLEN celery'

# If tasks are stuck, restart workers
docker compose restart worker
```

### Incident: Instagram API Rate Limit Hit

**Symptoms**: Scraper jobs fail with rate limit errors (429 Too Many Requests)

**Diagnosis**:

```bash
# Check scraper logs
docker compose logs worker | grep -i "rate limit\|429"

# Check remaining API quota (Instagram Graph API)
curl -X GET "https://graph.instagram.com/me?fields=id&access_token=${INSTAGRAM_ACCESS_TOKEN}" \
  -v 2>&1 | grep -i "x-business-use-case-usage\|rate"
```

**Resolution**:

```bash
# Option 1: Reduce scraper concurrency in beat scheduler
vi backend/app/workers/tasks.py
# Reduce SCRAPER_CONCURRENCY from 10 to 2

# Option 2: Implement exponential backoff (should be automatic)
# Verify in backend/app/workers/scraper.py

# Option 3: Request increased rate limit from Instagram
# https://developers.facebook.com/docs/instagram-api/overview#rate-limiting

# Wait for rate limit reset (usually 1 hour)
docker compose logs worker | tail -f
```

### Incident: High API Error Rate

**Symptoms**: API returns 5xx errors, users report service down

**Diagnosis**:

```bash
# Check API logs for errors
docker compose logs api | grep -i "error\|exception\|traceback" | tail -50

# Check database connectivity
docker compose exec api python -c "
from app.core.database import engine
import asyncio
asyncio.run(engine.execute('SELECT 1'))
print('✓ Database OK')
"

# Check Redis connectivity
docker compose exec api python -c "
from app.core.redis import get_redis
import asyncio
r = asyncio.run(get_redis())
print('✓ Redis OK')
"

# Check external service connectivity
curl -v https://api.openai.com/v1/status 2>&1 | grep -i "connect\|timeout"
```

**Resolution**:

```bash
# Restart API with clean state
docker compose restart api

# Or redeploy if restart doesn't help
docker compose up -d --pull=always api

# Check health endpoint
curl http://localhost:8000/api/v1/health

# Monitor logs
docker compose logs --tail=100 -f api
```

### Incident: All Celery Workers Down

**Symptoms**: No background tasks are being processed, Flower shows no workers

**Diagnosis**:

```bash
# Check worker containers
docker compose ps | grep worker

# Check worker logs
docker compose logs worker | tail -100

# Check Redis connection
docker compose exec redis redis-cli ping

# Check if workers can connect to broker
docker compose logs worker | grep -i "redis\|broker\|connection"
```

**Resolution**:

```bash
# Restart Redis first (broker)
docker compose restart redis
sleep 5

# Restart workers
docker compose restart worker beat

# Verify
docker compose ps | grep -E "worker|beat"
docker compose logs worker | head -20
```

### Incident: Disk Space Exhausted

**Symptoms**: Services can't write logs or data, containers stuck in error state

**Diagnosis**:

```bash
# Check disk usage
df -h

# Check which services use most space
docker system df

# Check database size
docker compose exec postgres psql -U gift -d giftfinder -c "
  SELECT
    pg_size_pretty(pg_database_size('giftfinder')) as db_size,
    (SELECT pg_size_pretty(SUM(pg_total_relation_size(schemaname||'.'||tablename))))
    FROM pg_tables WHERE schemaname = 'public';
"
```

**Resolution**:

```bash
# Clean up old Docker images
docker image prune -a -f

# Clean up unused volumes
docker volume prune -f

# Shrink PostgreSQL (remove dead rows)
docker compose exec postgres vacuumdb -U gift -d giftfinder -F

# Remove old logs
docker compose logs --tail=100 > /tmp/logs-backup.txt
docker container prune -f

# Expand volume (cloud-specific)
# AWS EBS: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-modify-volume.html
# DigitalOcean: https://docs.digitalocean.com/products/volumes/how-to/resize/
```

---

## Secrets Rotation

### JWT_SECRET Rotation

Rotating `JWT_SECRET` invalidates all active sessions. Plan for user re-authentication.

#### Procedure

```bash
# Step 1: Generate new secret
NEW_JWT_SECRET=$(openssl rand -hex 32)
echo "New JWT_SECRET: $NEW_JWT_SECRET"

# Step 2: Set environment variable in .env
# Append new secret (keep old one for transition period)
OLD_JWT_SECRET="$JWT_SECRET"
echo "NEW_JWT_SECRET=$NEW_JWT_SECRET" >> .env

# Step 3: Update application to accept both old and new secrets
# (This is optional, but recommended for gradual rollout)

# Step 4: Redeploy API with new secret
JWT_SECRET="$NEW_JWT_SECRET" docker compose up -d api

# Step 5: Notify users (optional)
# Send email: "For security, please log in again"

# Step 6: Monitor for authentication issues
docker compose logs api | grep -i "jwt\|auth\|token" | tail -20

# Step 7: After 1-2 hours, remove old secret from .env
sed -i '/NEW_JWT_SECRET/d' .env
```

### AWS_SECRET_ACCESS_KEY Rotation

Rotate S3 access keys periodically (AWS recommends every 90 days).

```bash
# Step 1: Create new access key in AWS
aws iam create-access-key --user-name giftfinder-app

# Step 2: Update .env with new credentials
NEW_ACCESS_KEY_ID="AKIAIOSFODNN7EXAMPLE"
NEW_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

vi .env  # Update AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY

# Step 3: Restart API
docker compose up -d api

# Step 4: Verify S3 connectivity
docker compose exec api python -c "
import boto3
s3 = boto3.client('s3')
s3.head_bucket(Bucket='giftfinder-images')
print('✓ S3 access OK')
"

# Step 5: Delete old access key in AWS (after verification)
aws iam delete-access-key --user-name giftfinder-app --access-key-id AKIAIOSFODNN7EXAMPLE
```

### INSTAGRAM_ACCESS_TOKEN Rotation

Instagram tokens expire after ~60 days. Refresh before expiry:

```bash
# Check token expiry
curl -X GET \
  "https://graph.instagram.com/v18.0/me?fields=id&access_token=$INSTAGRAM_ACCESS_TOKEN" \
  -v 2>&1 | grep -i "expires"

# Refresh token
NEW_TOKEN=$(curl -X GET \
  "https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=$INSTAGRAM_ACCESS_TOKEN" \
  | jq -r '.access_token')

# Update .env
sed -i "s/INSTAGRAM_ACCESS_TOKEN=.*/INSTAGRAM_ACCESS_TOKEN=$NEW_TOKEN/" .env

# Restart scraper workers
docker compose restart worker beat

# Verify
docker compose exec worker python -c "
import os
from app.workers.scraper import test_instagram_connection
test_instagram_connection()
"
```

---

## Monitoring & Alerting

### Setting Up Prometheus Monitoring

```bash
# Create Prometheus config directory
mkdir -p /app/giftfinder/monitoring

# Copy alerts.yml to monitoring directory
cp monitoring/alerts.yml /app/giftfinder/monitoring/

# Create prometheus.yml
cat > /app/giftfinder/monitoring/prometheus.yml <<'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

rule_files:
  - 'alerts.yml'

scrape_configs:
  - job_name: 'api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:5432']
EOF

# Add Prometheus to docker-compose.yml (optional)
docker compose up -d prometheus
```

### CloudWatch Metrics (AWS)

```bash
# Install CloudWatch agent on EC2
wget https://s3.amazonaws.com/amazoncloudwatch-agent/amazon_linux/amd64/latest/amazon-cloudwatch-agent.rpm
sudo rpm -U ./amazon-cloudwatch-agent.rpm

# Configure CloudWatch agent
sudo tee /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json > /dev/null <<'EOF'
{
  "metrics": {
    "namespace": "GiftFinder",
    "metrics_collected": {
      "cpu": {
        "measurement": [
          {"name": "cpu_usage_idle", "rename": "CPU_IDLE"},
          {"name": "cpu_usage_system", "rename": "CPU_SYSTEM"}
        ]
      },
      "disk": {
        "measurement": [
          {"name": "free", "rename": "DISK_FREE"}
        ],
        "metrics_collection_interval": 60,
        "resources": ["/"]
      },
      "mem": {
        "measurement": [
          {"name": "mem_used_percent", "rename": "MEM_USED_PERCENT"}
        ]
      }
    }
  }
}
EOF

# Start agent
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config \
  -m ec2 \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json \
  -s

# Create alarms
aws cloudwatch put-metric-alarm \
  --alarm-name giftfinder-api-error-rate \
  --alarm-description "Alert when API error rate > 5%" \
  --metric-name HTTPErrors \
  --namespace GiftFinder \
  --statistic Sum \
  --period 300 \
  --threshold 50 \
  --comparison-operator GreaterThanThreshold
```

### DataDog Integration

```bash
# Install DataDog agent
bash -c "$(curl -L https://s3.amazonaws.com/dd-agent/scripts/install_script.sh)"

# Configure
vi /etc/datadog-agent/datadog.yaml

# Enable integrations
cp /etc/datadog-agent/conf.d/docker.d/conf.yaml.default \
   /etc/datadog-agent/conf.d/docker.d/conf.yaml

cp /etc/datadog-agent/conf.d/postgres.d/conf.yaml.default \
   /etc/datadog-agent/conf.d/postgres.d/conf.yaml

# Restart agent
sudo systemctl restart datadog-agent
```

---

## Backup & Disaster Recovery

### Database Backups

#### Automated Daily Backups

```bash
# Create backup script
cat > /app/giftfinder/backup-database.sh <<'EOF'
#!/bin/bash
set -e

BACKUP_DIR="/backups/database"
BACKUP_DATE=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_FILE="${BACKUP_DIR}/giftfinder_${BACKUP_DATE}.sql.gz"

mkdir -p "$BACKUP_DIR"

# Backup database
docker compose exec -T postgres pg_dump \
  -U gift \
  -d giftfinder \
  | gzip > "$BACKUP_FILE"

# Keep only last 30 days of backups
find "$BACKUP_DIR" -mtime +30 -delete

echo "✓ Backup completed: $BACKUP_FILE"
EOF

chmod +x /app/giftfinder/backup-database.sh

# Schedule daily backups via cron
crontab -e
# Add: 0 2 * * * /app/giftfinder/backup-database.sh
```

#### Cloud-Based Backups (AWS RDS)

If using AWS RDS for PostgreSQL:

```bash
# Enable automated backups
aws rds modify-db-instance \
  --db-instance-identifier giftfinder-db \
  --backup-retention-period 30 \
  --preferred-backup-window "02:00-03:00"

# Create manual snapshot before major changes
aws rds create-db-snapshot \
  --db-instance-identifier giftfinder-db \
  --db-snapshot-identifier giftfinder-db-backup-$(date +%Y%m%d)

# List snapshots
aws rds describe-db-snapshots --db-instance-identifier giftfinder-db
```

### Disaster Recovery Plan

#### RTO (Recovery Time Objective): 30 minutes
#### RPO (Recovery Point Objective): 1 hour

**Scenario: Total server failure**

```bash
# Step 1: Provision new server (5 min)
aws ec2 run-instances --image-id ami-0c55b159cbfafe1f0 --instance-type t3.large
aws ec2 describe-instances

# Step 2: Prepare server (10 min)
# (See "First-Time Deployment" > "Step 1: Prepare the Server")

# Step 3: Restore database from backup (10 min)
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier giftfinder-db-restored \
  --db-snapshot-identifier giftfinder-db-backup-20240501

# Step 4: Deploy application (5 min)
cd /app/giftfinder
git clone https://github.com/yourorg/giftfinder.git .
cp .env.example .env  # Update with backup credentials
docker compose up -d

# Step 5: Verify
docker compose ps
curl http://localhost:8000/api/v1/health
```

#### S3 Data Loss Recovery

If objects are accidentally deleted from S3:

```bash
# Check versioning is enabled
aws s3api get-bucket-versioning \
  --bucket giftfinder-images \
  --query 'Status'

# Restore deleted object
aws s3api copy-object \
  --copy-source "giftfinder-images/path/to/file.jpg?versionId=VERSIONID" \
  --bucket giftfinder-images \
  --key "path/to/file.jpg"

# List all versions
aws s3api list-object-versions \
  --bucket giftfinder-images \
  --prefix "path/to/file.jpg"
```

---

## Additional Resources

- **API Documentation**: http://localhost:8000/api/v1/docs (Swagger UI)
- **Flower Monitoring**: http://localhost:5555 (Celery task monitoring)
- **GitHub Actions**: https://github.com/yourorg/giftfinder/actions
- **AWS Console**: https://console.aws.amazon.com/
- **Instagram Graph API**: https://developers.facebook.com/docs/instagram-api/
- **OpenAI API**: https://platform.openai.com/docs/

---

## Escalation & Support

For critical incidents:

1. **Incident Commander**: Page primary on-call engineer
2. **Communication**: Update status page every 15 minutes
3. **Postmortem**: After incident resolution, schedule postmortem within 24 hours

---

**Last Updated**: 2024-05-03
**Maintained by**: DevOps Team
**Contact**: devops@company.com
