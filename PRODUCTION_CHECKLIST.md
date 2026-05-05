# Production Deployment Checklist

Use this checklist before deploying Gift Finder to production.

## Pre-Deployment (1-2 weeks before)

### Infrastructure Planning
- [ ] Decide deployment platform (AWS EC2, DigitalOcean, Heroku, Kubernetes, etc.)
- [ ] Estimate capacity requirements
  - [ ] CPU cores needed
  - [ ] RAM needed  
  - [ ] Storage capacity (database + S3)
  - [ ] Network bandwidth estimate
- [ ] Design disaster recovery strategy (RTO/RPO targets)
- [ ] Plan backup/restore procedures
- [ ] Define SLAs (availability targets, response times)

### Security Review
- [ ] Audit all dependencies for vulnerabilities (`make audit`)
- [ ] Review GitHub Actions permissions
- [ ] Generate all secrets using secure random generation
  - [ ] `JWT_SECRET = openssl rand -hex 32`
  - [ ] `FLOWER_PASSWORD = openssl rand -hex 16`
  - [ ] Generate AWS IAM access keys for S3
- [ ] Plan secrets rotation schedule
- [ ] Enable HTTPS/TLS certificates
- [ ] Configure firewall rules
- [ ] Set up WAF (Web Application Firewall) rules if applicable
- [ ] Review CORS origins configuration
- [ ] Enable security headers (HSTS, CSP, X-Frame-Options, etc.)

### External Services Setup
- [ ] Create AWS S3 bucket with versioning enabled
- [ ] Create AWS IAM user for application with S3 access
- [ ] Get Instagram access token (request long-lived token)
- [ ] Generate OpenAI API key
- [ ] Set up email SMTP (if needed for notifications)
- [ ] Configure DNS records (A, CNAME, MX if applicable)

### Monitoring & Alerts
- [ ] Set up monitoring system (Prometheus, CloudWatch, DataDog, etc.)
- [ ] Configure alert thresholds
  - [ ] Error rate > 5%
  - [ ] API latency P99 > 2s
  - [ ] Database connection pool > 80%
  - [ ] Disk space < 10%
  - [ ] Memory usage > 85%
- [ ] Set up alerting channels (PagerDuty, Slack, email)
- [ ] Configure log aggregation (CloudWatch, DataDog, etc.)
- [ ] Set up APM (Application Performance Monitoring) if needed

### Testing
- [ ] All tests passing locally (`make test-all`)
- [ ] Code review completed
- [ ] Security scan completed
- [ ] Load testing performed (goal: handle 2x expected traffic)
  - [ ] API endpoints tested
  - [ ] Database query performance verified
  - [ ] Connection pool sizing validated
- [ ] Database migration tested on staging environment
- [ ] Rollback procedure tested
- [ ] SSL/TLS certificate tested
- [ ] CORS configuration tested with real frontend origin

### Documentation
- [ ] RUNBOOK.md reviewed and updated
- [ ] DEPLOYMENT.md reviewed and updated
- [ ] Team trained on incident response procedures
- [ ] On-call rotation established
- [ ] Escalation procedures documented

---

## Deployment Week

### Day Before Deployment

- [ ] Notify all stakeholders (frontend team, mobile team, ops, support)
- [ ] Schedule deployment window (low-traffic time if possible)
- [ ] Verify backup of current production database
- [ ] Verify all external APIs are accessible
- [ ] Test SSH access to production server
- [ ] Verify GitHub Actions secrets are configured
  - [ ] DATABASE_URL
  - [ ] DEPLOY_HOST
  - [ ] DEPLOY_USER
  - [ ] DEPLOY_KEY
- [ ] Run full CI pipeline on main branch (no failures)
- [ ] Prepare rollback plan and test it
- [ ] Communicate expected downtime (if any) to users

### Day of Deployment

#### Pre-Deployment (30 minutes before)
- [ ] Verify current system health
  ```bash
  curl https://yourdomain.com/api/v1/health
  ```
- [ ] Verify database is accessible and healthy
- [ ] Verify Redis is accessible
- [ ] Verify S3 bucket access
- [ ] Open communication channel (Slack, war room, etc.)
- [ ] Start incident tracking

#### During Deployment
- [ ] Monitor GitHub Actions build progress
  - [ ] CI tests passing
  - [ ] Docker images building
  - [ ] Database migrations running
  - [ ] Deployment proceeding
- [ ] Monitor application logs for errors
  ```bash
  ssh deploy@yourdomain.com
  cd /app/giftfinder
  docker compose logs -f api worker
  ```
- [ ] Check health endpoint after deployment
  ```bash
  curl https://yourdomain.com/api/v1/health
  ```
- [ ] Run smoke tests
  - [ ] Create test user
  - [ ] Verify items endpoint
  - [ ] Verify search endpoint
  - [ ] Verify frontend loads
- [ ] Monitor error rates (first 5 minutes)
- [ ] Monitor database connections
- [ ] Monitor API response times

#### Post-Deployment (30 minutes after)
- [ ] Confirm all health checks passing
- [ ] Check error rate (should be < 0.1%)
- [ ] Check response time (P99 should be < 2s)
- [ ] Verify no critical logs from past 30 minutes
- [ ] Close incident tracking
- [ ] Notify stakeholders of successful deployment

---

## Post-Deployment

### Immediate (1-2 hours)
- [ ] Monitor application continuously
- [ ] Check monitoring dashboards for anomalies
- [ ] Review error logs
- [ ] Verify user reports (social media, support channels)
- [ ] Keep on-call engineer on standby

### Short-term (1-2 days)
- [ ] Review deployment metrics
  - [ ] Error rates
  - [ ] Response times
  - [ ] Resource usage
  - [ ] User engagement
- [ ] Verify all features working correctly
- [ ] Check third-party integrations (Instagram, OpenAI, S3)
- [ ] Document any issues encountered
- [ ] Verify backups are working

### Medium-term (1-2 weeks)
- [ ] Collect feedback from users and teams
- [ ] Performance review (compare to baseline)
- [ ] Security review of production environment
- [ ] Update runbook with any lessons learned
- [ ] Review and update monitoring thresholds if needed
- [ ] Plan next deployment

---

## Rollback Scenarios

### Quick Rollback (< 30 minutes to previous version)

```bash
# SSH to production
ssh deploy@yourdomain.com
cd /app/giftfinder

# Identify previous working version
git log --oneline -5

# Checkout previous version
git checkout <previous-sha>

# Redeploy
docker compose up -d --build

# Verify
docker compose ps
curl https://yourdomain.com/api/v1/health
```

### Database Rollback

Only use if data integrity compromised:

```bash
# Check current migration
docker compose exec api alembic current

# Downgrade one migration
docker compose exec api alembic downgrade -1

# Verify
docker compose exec api alembic current
```

### Complete Restore from Backup

For catastrophic failure:

```bash
# Stop application
docker compose down

# Restore database from backup
docker compose exec -T postgres psql -U gift -d giftfinder < backup.sql.gz

# Restart
docker compose up -d
```

---

## Sign-Off

After successful production deployment:

- **Deployed by**: _________________
- **Date/Time**: _________________
- **Version/Commit**: _________________
- **Verified by**: _________________
- **Issues encountered**: _________________
- **Rollback tested**: [ ] Yes [ ] No
- **Monitoring alerts verified**: [ ] Yes [ ] No

---

## Emergency Contact

**On-call engineer**: _________________
**Backup contact**: _________________
**Incident commander (if needed)**: _________________
**External escalation**: _________________

---

## References

- [RUNBOOK.md](RUNBOOK.md) - Detailed operations procedures
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment quick reference
- [GitHub Actions Status](https://github.com/yourorg/giftfinder/actions)
- [Monitoring Dashboard](https://monitoring.yourdomain.com)
- [Incident Tracker](https://jira.yourdomain.com)
