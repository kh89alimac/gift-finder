# GitHub Actions Deployment Secrets Setup

This document describes the secrets that must be configured in your GitHub repository for automated deployments.

## Required Secrets

Configure these secrets in GitHub: Settings → Secrets and variables → Actions

### 1. DATABASE_URL

**Purpose**: PostgreSQL connection string for migrations

**Format**: 
```
postgresql+asyncpg://user:password@host:5432/database_name
```

**Example**:
```
postgresql+asyncpg://gift:secure-password@prod-db.us-east-1.rds.amazonaws.com:5432/giftfinder_prod
```

**How to create**:
- If using AWS RDS: Copy endpoint from RDS console
- If using self-hosted: Use your PostgreSQL host and credentials
- Must allow migrations to run (ensure firewall allows GitHub Actions IP)

### 2. DEPLOY_HOST

**Purpose**: Production server hostname or IP

**Format**: 
```
yourdomain.com
```

**Example**:
```
api.yourdomain.com
```

### 3. DEPLOY_USER

**Purpose**: SSH user for deployment

**Format**: Username (e.g., `deploy`, `ubuntu`, `ec2-user`)

**Example**:
```
deploy
```

### 4. DEPLOY_KEY

**Purpose**: SSH private key for deployment server access

**How to create**:

```bash
# Generate new SSH key pair for deployment
ssh-keygen -t rsa -b 4096 -f ~/.ssh/giftfinder-deploy -N ""

# Copy public key to server
ssh-copy-id -i ~/.ssh/giftfinder-deploy.pub deploy@yourdomain.com

# Get private key content (paste into GitHub secret)
cat ~/.ssh/giftfinder-deploy
```

**Security**:
- Use dedicated key for CI/CD (not your personal key)
- Store in encrypted key management (Vault, AWS Secrets Manager)
- Rotate quarterly
- Immediately rotate if compromised

### 5. GITHUB_TOKEN

**Purpose**: Push Docker images to GitHub Container Registry (GHCR)

**Note**: This is automatically provided by GitHub Actions, no configuration needed.

Verify in workflow:
```yaml
- uses: docker/login-action@v3
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}
```

## Setup Instructions

### Step 1: Create secrets in GitHub

Navigate to: https://github.com/yourorg/giftfinder/settings/secrets/actions

Click "New repository secret" for each secret:

| Secret Name | Value |
|-------------|-------|
| DATABASE_URL | postgresql+asyncpg://... |
| DEPLOY_HOST | yourdomain.com |
| DEPLOY_USER | deploy |
| DEPLOY_KEY | (paste private key) |

### Step 2: Verify SSH access

Test that deployment key works:

```bash
# From your local machine, test the key
ssh -i ~/.ssh/giftfinder-deploy deploy@yourdomain.com "echo 'SSH works!'"

# You should see "SSH works!" printed
```

### Step 3: Verify database access

Test that migrations can connect:

```bash
# From your local machine (or GitHub Actions context)
psql "postgresql://user:password@host:5432/database" -c "SELECT version();"

# You should see PostgreSQL version output
```

### Step 4: Set workflow permissions

Navigate to: https://github.com/yourorg/giftfinder/settings/actions

Ensure "Workflow permissions" is set to:
- [x] Read and write permissions
- [x] Allow GitHub Actions to create and approve pull requests

## Usage in Workflows

Secrets are automatically masked in logs. Reference them as:

```yaml
env:
  DATABASE_URL: ${{ secrets.DATABASE_URL }}

steps:
  - uses: appleboy/ssh-action@master
    with:
      host: ${{ secrets.DEPLOY_HOST }}
      username: ${{ secrets.DEPLOY_USER }}
      key: ${{ secrets.DEPLOY_KEY }}
```

## Testing Deployment Without Merging

To test deployment workflow without affecting production:

```bash
# Create feature branch
git checkout -b test/deployment

# Make a change to trigger workflow
echo "# Test deployment" >> README.md

# Commit and push
git commit -am "Test deployment workflow"
git push origin test/deployment

# Create PR (workflow runs on PR but doesn't deploy)
# View workflow run: Actions tab

# After verifying workflow runs correctly, delete branch
git branch -D test/deployment
```

## Troubleshooting

### "SSH: connect to host failed"

- Verify DEPLOY_HOST is correct
- Check firewall allows GitHub Actions IP ranges: https://docs.github.com/en/actions/hosting-your-own-runners/about-self-hosted-runners#communication-between-self-hosted-runners-and-github
- Verify server is running: `ping yourdomain.com`

### "Database connection refused"

- Verify DATABASE_URL is correct
- Check PostgreSQL is running on target server
- Verify firewall allows database connections from GitHub Actions
- Test locally: `psql ${{ secrets.DATABASE_URL }}`

### "Permission denied (publickey)"

- Verify DEPLOY_KEY is correct private key (not public key)
- Verify DEPLOY_USER is correct username
- Check public key is in `~deploy/.ssh/authorized_keys` on server
- Keys must have correct permissions:
  ```bash
  chmod 700 ~/.ssh
  chmod 600 ~/.ssh/authorized_keys
  ```

### "Migration failed"

- Check DATABASE_URL permissions (user must be able to ALTER SCHEMA)
- Verify no other migration is running: `SELECT pg_blocking_pids(pid) FROM pg_stat_activity;`
- Review migration logs: `docker compose logs migration`

## Secrets Rotation

Rotate secrets quarterly or after any personnel changes:

1. **SSH Key**: Generate new key pair, update authorized_keys on server
2. **DATABASE_URL**: Use AWS Secrets Manager or HashiCorp Vault
3. **GITHUB_TOKEN**: Automatically rotated by GitHub

To rotate DATABASE_URL:

```bash
# In GitHub: Settings → Secrets
# 1. Update DATABASE_URL with new connection string
# 2. Run a test deployment to verify
# 3. Delete old database user from PostgreSQL:
#    DROP USER old_deploy_user;
```

## Security Best Practices

- Never log secrets: GitHub automatically masks them
- Use least-privilege: Database user should only have migration permissions
- Separate keys: Deployment key ≠ personal SSH key
- Monitor access: Review GitHub Actions logs regularly
- Audit trail: Enable GitHub audit logging
- Incident response: If key is compromised, rotate immediately

## References

- [GitHub Actions Secrets Documentation](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [SSH in GitHub Actions](https://github.com/appleboy/ssh-action)
- [Docker Registry Authentication](https://docs.docker.com/ci-cd/github-actions/)
