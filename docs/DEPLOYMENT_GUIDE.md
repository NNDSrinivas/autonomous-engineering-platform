# NAVI Deployment Guide

This guide covers local, Kubernetes, and AWS deployments. GCP/Azure sections outline required work to reach parity.

## 1) Prerequisites

- Docker and docker-compose (local).
- Kubernetes cluster + `kubectl` (k8s).
- Terraform (AWS).
- Python 3.11, Node 18+.
- PostgreSQL 15+ (local/managed).
- Secrets configured per `PRODUCTION_SECRETS_GUIDE.md`.

## 2) Database Setup

NAVI requires PostgreSQL 15+ with pgvector extension for vector embeddings.

### 2.1) Local Development Database

**Option A: Docker (Recommended)**

```bash
# Start PostgreSQL with pgvector
docker run -d \
  --name navi-postgres \
  -e POSTGRES_DB=mentor \
  -e POSTGRES_USER=mentor \
  -e POSTGRES_PASSWORD=mentor \
  -p 5432:5432 \
  pgvector/pgvector:pg15

# Wait for database to be ready
sleep 3 && docker exec navi-postgres pg_isready -U mentor
```

**Option B: Local PostgreSQL Installation**

```bash
# macOS
brew install postgresql@15 pgvector
brew services start postgresql@15

# Linux (Ubuntu/Debian)
sudo apt-get install postgresql-15 postgresql-15-pgvector

# Create database
createdb -U postgres mentor
psql -U postgres -d mentor -c "CREATE USER mentor WITH PASSWORD 'mentor';"
psql -U postgres -d mentor -c "GRANT ALL PRIVILEGES ON DATABASE mentor TO mentor;"
psql -U postgres -d mentor -c "CREATE EXTENSION vector;"
```

**Apply Database Migrations**

```bash
# Set DATABASE_URL
export DATABASE_URL="postgresql+psycopg2://mentor:mentor@localhost:5432/mentor"

# Run migrations
alembic upgrade head

# Verify tables were created
docker exec navi-postgres psql -U mentor -d mentor -c "\dt" | grep -E "(llm_metrics|learning_suggestions|telemetry_events)"
```

Expected output: 9 new v1 tables (llm_metrics, rag_metrics, task_metrics, learning_suggestions, learning_insights, learning_patterns, telemetry_events, performance_metrics, error_events) plus existing tables.

### 2.2) Staging Environment Database

**PostgreSQL Managed Service** (Recommended)
- AWS RDS PostgreSQL 15+ with Multi-AZ
- GCP Cloud SQL PostgreSQL 15+
- Azure Database for PostgreSQL 15+

**Configuration:**

1. **Create Database Secret**:
```bash
# Replace ${STAGING_DB_PASSWORD} with actual password
kubectl create secret generic navi-database-staging \
  --from-literal=DATABASE_URL='postgresql+psycopg2://navi_staging:${STAGING_DB_PASSWORD}@staging-db-host:5432/navi_staging' \
  --namespace navi-staging

# Or apply from file
kubectl apply -f kubernetes/secrets/database-staging.yaml
```

2. **Run Migrations**:
```bash
# Port-forward to staging pod
kubectl port-forward -n navi-staging deployment/navi-backend 8080:8000 &

# Run migration via pod
kubectl exec -n navi-staging deployment/navi-backend -- \
  alembic upgrade head

# Or run from CI/CD as init container (see kubernetes/deployments/backend-staging.yaml)
```

3. **Verify Deployment**:
```bash
./scripts/infra/verify_k8s.sh staging
```

### 2.3) Production Environment Database

**⚠️ CRITICAL: Production Database Checklist**

- [ ] Multi-AZ/High Availability enabled
- [ ] Automated backups configured (daily, 30-day retention)
- [ ] Point-in-time recovery (PITR) enabled
- [ ] SSL/TLS encryption enforced
- [ ] Read replica for analytics queries
- [ ] Connection pooling (PgBouncer recommended)
- [ ] Monitoring and alerting configured
- [ ] Database credentials rotated quarterly
- [ ] Access restricted to VPC/private subnet

**PostgreSQL Production Configuration:**

```sql
-- Recommended PostgreSQL settings for production
ALTER SYSTEM SET max_connections = 200;
ALTER SYSTEM SET shared_buffers = '4GB';
ALTER SYSTEM SET effective_cache_size = '12GB';
ALTER SYSTEM SET work_mem = '16MB';
ALTER SYSTEM SET maintenance_work_mem = '512MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;  -- For SSD storage
ALTER SYSTEM SET effective_io_concurrency = 200;
SELECT pg_reload_conf();
```

**Create Production Database Secret:**

```bash
# Use external secrets management in production!
# AWS Secrets Manager example:
kubectl create secret generic navi-database-production \
  --from-literal=DATABASE_URL="$(aws secretsmanager get-secret-value --secret-id navi/prod/database-url --query SecretString --output text)" \
  --namespace navi-production

# Or apply from external-secrets operator
kubectl apply -f kubernetes/external-secrets/database-production.yaml
```

**Run Production Migrations** (Manual approval required):

```bash
# NEVER auto-upgrade in production!
# Always review and test migrations in staging first

# 1. Create backup before migration
kubectl exec -n navi-production deployment/navi-backend -- \
  pg_dump $DATABASE_URL > backup-pre-migration-$(date +%Y%m%d).sql

# 2. Review migration SQL
alembic upgrade head --sql > migration.sql
cat migration.sql  # Review changes

# 3. Apply migration during maintenance window
kubectl exec -n navi-production deployment/navi-backend -- \
  alembic upgrade head

# 4. Verify migration
kubectl exec -n navi-production deployment/navi-backend -- \
  alembic current

# 5. Verify application health
./scripts/infra/verify_k8s.sh production
```

### 2.4) Database Maintenance

**Regular Maintenance Tasks:**

```bash
# Analyze tables for query optimization (weekly)
psql $DATABASE_URL -c "ANALYZE;"

# Vacuum to reclaim storage (weekly)
psql $DATABASE_URL -c "VACUUM ANALYZE;"

# Reindex for performance (monthly)
psql $DATABASE_URL -c "REINDEX DATABASE mentor;"

# Check database size
psql $DATABASE_URL -c "SELECT pg_size_pretty(pg_database_size('mentor'));"

# Check table sizes
psql $DATABASE_URL -c "
  SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
  FROM pg_tables
  WHERE schemaname = 'public'
  ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
  LIMIT 20;
"
```

**Monitoring Queries:**

```sql
-- Active connections
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';

-- Long-running queries
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active' AND now() - query_start > interval '5 minutes';

-- Database locks
SELECT blocked_locks.pid AS blocked_pid,
       blocking_locks.pid AS blocking_pid,
       blocked_activity.usename AS blocked_user,
       blocking_activity.usename AS blocking_user,
       blocked_activity.query AS blocked_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
  AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
  AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

## 3) Local (Docker Compose)

- Deploy: `./scripts/infra/deploy_local.sh`
- Verify: `./scripts/infra/verify_local.sh http://localhost:8000/health`
- Rollback: `./scripts/infra/rollback_local.sh`

## 3) Kubernetes

- Deploy: `./scripts/infra/deploy_k8s.sh`
- Verify: `./scripts/infra/verify_k8s.sh`
- Rollback: `./scripts/infra/rollback_k8s.sh`

Notes:
- Manifests live in `k8s/`.
- Provide secrets via your cluster secret manager or sealed secrets.

## 4) AWS (Terraform + ECS Fargate)

- Terraform: `infra/terraform/aws`
- Deploy: `./scripts/infra/deploy_aws_terraform.sh`
- Verify: `./scripts/infra/verify_aws.sh`
- Rollback: `./scripts/infra/rollback_aws_terraform.sh`

Notes:
- RDS/Redis are optional Terraform toggles (`enable_rds`, `enable_redis`).
- For production, use private subnets and restrict public access.

Staging workflow:
- `.github/workflows/deploy-staging.yml` uses container image in this order:
  - `STAGING_CONTAINER_IMAGE` → `ECR_IMAGE` → `GHCR_IMAGE` → `DOCKERHUB_IMAGE`

## 5) GCP (Planned)

Required modules to reach parity:
- Cloud Run or GKE deployment
- Cloud SQL (Postgres) + Memorystore (Redis)
- VPC + private services
- Secret Manager + IAM

Suggested structure:
- `infra/terraform/gcp` with:
  - `network.tf`, `iam.tf`, `cloudrun.tf` or `gke.tf`, `cloudsql.tf`, `memorystore.tf`

## 6) Azure (Planned)

Required modules to reach parity:
- Azure Container Apps or AKS
- Azure Database for PostgreSQL
- Azure Cache for Redis
- VNet + private endpoints
- Key Vault + managed identities

Suggested structure:
- `infra/terraform/azure` with:
  - `network.tf`, `identity.tf`, `aca.tf` or `aks.tf`, `postgres.tf`, `redis.tf`

## 7) Self-Hosted (Enterprise)

- Use Kubernetes manifests in `k8s/` or local docker compose as a starting point.
- Provide your own Postgres and Redis endpoints via env vars.
- Enable SSO (SAML/OIDC) at the edge (IdP + reverse proxy).

## 8) Audit Encryption (REQUIRED for Production/Staging)

**⚠️ CRITICAL: Audit encryption is MANDATORY for production and staging environments.**

NAVI enforces encryption of audit logs at rest to protect sensitive data. The backend will **fail to start** in production/staging without a valid encryption key.

### 8.1) Generate Encryption Key

```bash
# Generate a secure 32-byte encryption key
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

### 8.2) Configure Environment Variable

**Staging:**
```bash
# Kubernetes secret
kubectl create secret generic navi-audit-encryption-staging \
  --from-literal=AUDIT_ENCRYPTION_KEY='<generated-key-from-above>' \
  --namespace navi-staging

# Verify secret
kubectl get secret navi-audit-encryption-staging -n navi-staging
```

**Production:**
```bash
# Use external secrets management (AWS Secrets Manager, HashiCorp Vault, etc.)
aws secretsmanager create-secret \
  --name navi/prod/audit-encryption-key \
  --secret-string '<generated-key-from-above>'

# Apply external secret to Kubernetes
kubectl apply -f kubernetes/external-secrets/audit-encryption-production.yaml
```

**Local Development:**
```bash
# Add to .env file (not required for development, but recommended for testing)
echo "AUDIT_ENCRYPTION_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" >> .env
```

### 8.3) Verify Configuration

```bash
# Check if backend starts successfully
kubectl logs -n navi-staging deployment/navi-backend | grep -i audit

# Expected output: No errors about missing AUDIT_ENCRYPTION_KEY
# If missing, you'll see: "AUDIT_ENCRYPTION_KEY is REQUIRED when APP_ENV=staging and audit logging is enabled"
```

**Key Management Best Practices:**
- ✅ Store keys in external secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.)
- ✅ Rotate keys quarterly with zero-downtime key rotation support
- ✅ Never commit keys to source control
- ✅ Use different keys for staging and production
- ❌ Never reuse keys across environments
- ❌ Never share production keys in Slack/email

## 9) Deployment Checklist

- [ ] Secrets configured and validated
- [ ] **AUDIT_ENCRYPTION_KEY set for production/staging** ⚠️ MANDATORY
- [ ] Database migrations run
- [ ] Health endpoints verified
- [ ] Observability dashboards connected
- [ ] Rollback path tested
