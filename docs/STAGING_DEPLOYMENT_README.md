# NAVI Staging Deployment Guide

Complete guide for deploying NAVI to the staging environment.

## Prerequisites

Before deploying to staging, ensure you have:

- [x] Kubernetes cluster configured and accessible
- [x] `kubectl` installed and configured
- [x] Docker registry access for NAVI images
- [x] Database (PostgreSQL 15+ with pgvector) provisioned
- [x] Redis instance provisioned (optional but recommended)
- [x] Required secrets generated

## Quick Start

```bash
# 1. Generate required secrets
python -c 'import secrets; print("AUDIT_ENCRYPTION_KEY:", secrets.token_urlsafe(32))'
python -c 'import secrets; print("JWT_SECRET:", secrets.token_urlsafe(32))'

# 2. Create Kubernetes secrets
kubectl create secret generic navi-backend-secrets \
  --from-literal=AUDIT_ENCRYPTION_KEY='<generated-key>' \
  --from-literal=JWT_SECRET='<jwt-secret>' \
  --from-literal=OPENAI_API_KEY='<openai-key>' \
  --namespace navi-staging

kubectl create secret generic navi-database-staging \
  --from-literal=DATABASE_URL='postgresql+psycopg2://user:password@host:5432/dbname' \
  --namespace navi-staging

# 3. Deploy to staging
./scripts/deploy_staging.sh
```

## Detailed Setup

### Step 1: Generate Encryption Keys

NAVI requires a secure encryption key for audit logs. This is **MANDATORY** for staging and production.

```bash
# Generate audit encryption key (32-byte base64)
python -c 'import secrets; print(secrets.token_urlsafe(32))'

# Generate JWT secret
openssl rand -hex 32
```

**Save these keys securely!** You'll need them for the secret creation step.

### Step 2: Configure Database

#### Option A: AWS RDS (Recommended)

```bash
# Create RDS PostgreSQL instance (via AWS Console or Terraform)
# - Engine: PostgreSQL 15.x
# - Instance class: db.t3.medium (staging) or larger
# - Multi-AZ: Enabled
# - Storage: 100 GB SSD
# - Backup retention: 7 days

# Get database endpoint
DB_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier navi-staging \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text)

# Construct DATABASE_URL
DATABASE_URL="postgresql+psycopg2://navi_staging:${DB_PASSWORD}@${DB_ENDPOINT}:5432/navi_staging"
```

#### Option B: GCP Cloud SQL

```bash
# Create Cloud SQL instance
gcloud sql instances create navi-staging \
  --database-version=POSTGRES_15 \
  --tier=db-custom-2-7680 \
  --region=us-central1

# Get connection name
gcloud sql instances describe navi-staging --format='value(connectionName)'
```

#### Option C: Existing PostgreSQL

If you have an existing PostgreSQL server:

```bash
# Create database and user
psql -h your-postgres-host -U postgres <<EOF
CREATE DATABASE navi_staging;
CREATE USER navi_staging WITH PASSWORD 'secure-password';
GRANT ALL PRIVILEGES ON DATABASE navi_staging TO navi_staging;
\c navi_staging
CREATE EXTENSION vector;
EOF
```

### Step 3: Create Kubernetes Secrets

#### Using kubectl (Quick Method)

```bash
# Create backend secrets (includes AUDIT_ENCRYPTION_KEY)
kubectl create secret generic navi-backend-secrets \
  --from-literal=AUDIT_ENCRYPTION_KEY='<your-generated-key>' \
  --from-literal=AUDIT_ENCRYPTION_KEY_ID='staging-v1' \
  --from-literal=JWT_SECRET='<your-jwt-secret>' \
  --from-literal=OPENAI_API_KEY='<your-openai-key>' \
  --namespace navi-staging

# Create database secrets
kubectl create secret generic navi-database-staging \
  --from-literal=DATABASE_URL='postgresql+psycopg2://navi_staging:password@host:5432/navi_staging' \
  --namespace navi-staging

# Verify secrets were created
kubectl get secrets -n navi-staging
```

#### Using YAML Templates (Recommended)

1. **Edit the secret templates:**

```bash
# Copy templates
cp kubernetes/secrets/backend-secrets-staging.yaml /tmp/backend-secrets-staging.yaml
cp kubernetes/secrets/database-staging.yaml /tmp/database-staging.yaml

# Edit with your actual values
nano /tmp/backend-secrets-staging.yaml
nano /tmp/database-staging.yaml
```

2. **Apply the secrets:**

```bash
kubectl apply -f /tmp/backend-secrets-staging.yaml
kubectl apply -f /tmp/database-staging.yaml
```

3. **Clean up temporary files:**

```bash
rm /tmp/backend-secrets-staging.yaml /tmp/database-staging.yaml
```

#### Using AWS Secrets Manager (Best Practice)

For production-grade deployments, use external secrets management:

```bash
# 1. Store secrets in AWS Secrets Manager
aws secretsmanager create-secret \
  --name navi/staging/audit-encryption-key \
  --secret-string '<your-generated-key>'

aws secretsmanager create-secret \
  --name navi/staging/jwt-secret \
  --secret-string '<your-jwt-secret>'

aws secretsmanager create-secret \
  --name navi/staging/openai-api-key \
  --secret-string '<your-openai-key>'

# 2. Install External Secrets Operator
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets \
  --namespace external-secrets-system \
  --create-namespace

# 3. Create ExternalSecret resource (see kubernetes/external-secrets/)
kubectl apply -f kubernetes/external-secrets/backend-secrets-staging.yaml
```

### Step 4: Validate Secrets

Before deploying, verify all required secrets are present:

```bash
# Check if secrets exist
kubectl get secret navi-backend-secrets -n navi-staging
kubectl get secret navi-database-staging -n navi-staging

# Verify AUDIT_ENCRYPTION_KEY is set
kubectl get secret navi-backend-secrets -n navi-staging \
  -o jsonpath='{.data.AUDIT_ENCRYPTION_KEY}' | base64 -d | wc -c

# Should output: 43 (32 bytes base64-encoded)
```

### Step 5: Deploy to Staging

#### Automated Deployment (Recommended)

```bash
# Deploy using the automated script
./scripts/deploy_staging.sh

# The script will:
# 1. Validate prerequisites
# 2. Check for required secrets
# 3. Validate AUDIT_ENCRYPTION_KEY
# 4. Apply ConfigMaps
# 5. Deploy backend
# 6. Wait for rollout
# 7. Run health checks
```

#### Manual Deployment

If you prefer manual control:

```bash
# 1. Create namespace
kubectl create namespace navi-staging
kubectl label namespace navi-staging environment=staging

# 2. Apply ConfigMaps and Secrets
kubectl apply -f kubernetes/secrets/database-staging.yaml
kubectl apply -f kubernetes/secrets/backend-secrets-staging.yaml

# 3. Deploy backend
kubectl apply -f kubernetes/deployments/backend-staging.yaml

# 4. Wait for deployment
kubectl rollout status deployment/navi-backend -n navi-staging --timeout=300s

# 5. Verify pods are running
kubectl get pods -n navi-staging -l app=navi,component=backend
```

### Step 6: Post-Deployment Validation

After deployment, run these validation checks:

```bash
# 1. Check pod status
kubectl get pods -n navi-staging -l app=navi,component=backend

# Expected output: 2 pods in Running state

# 2. Check logs for errors
kubectl logs -n navi-staging -l app=navi,component=backend --tail=100

# Look for:
# ✅ No "AUDIT_ENCRYPTION_KEY is REQUIRED" errors
# ✅ Database migrations completed
# ✅ Server started successfully

# 3. Check health endpoints
kubectl port-forward -n navi-staging deployment/navi-backend 8787:8787 &

curl http://localhost:8787/health
# Expected: {"status":"ok","service":"core"}

curl http://localhost:8787/health/ready
# Expected: {"status":"healthy","checks":{...}}

curl http://localhost:8787/health/live
# Expected: {"status":"healthy"}

# 4. Verify database migrations
kubectl exec -n navi-staging deployment/navi-backend -- alembic current
# Expected: Shows current migration version

# 5. Test NAVI endpoint
curl -X POST http://localhost:8787/api/navi/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "What is 2+2?",
    "mode": "agent",
    "workspace_root": "/tmp"
  }'

# Expected: Streaming SSE response with answer

# 6. Verify audit encryption
kubectl exec -n navi-staging deployment/navi-backend -- \
  python -c 'import os; print("AUDIT_ENCRYPTION_KEY:", "SET ✓" if os.getenv("AUDIT_ENCRYPTION_KEY") else "MISSING ✗")'

# Expected: "AUDIT_ENCRYPTION_KEY: SET ✓"
```

### Step 7: Run Performance Tests

Once deployed, run the real LLM test suite against staging:

```bash
# Set staging URL
export NAVI_BASE_URL="http://staging.navi.example.com"

# Run tests
./run_tests_now.sh

# Expected results:
# - 98% success rate
# - p50 latency: 5-6 seconds
# - No timeout errors
```

## Troubleshooting

### Issue: Pod fails with "AUDIT_ENCRYPTION_KEY is REQUIRED"

**Cause:** Missing or empty `AUDIT_ENCRYPTION_KEY` in staging environment.

**Solution:**

```bash
# 1. Check if secret exists
kubectl get secret navi-backend-secrets -n navi-staging \
  -o jsonpath='{.data.AUDIT_ENCRYPTION_KEY}' | base64 -d

# 2. If empty or missing, update secret
AUDIT_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')
kubectl patch secret navi-backend-secrets -n navi-staging \
  --type='json' \
  -p='[{"op":"add","path":"/data/AUDIT_ENCRYPTION_KEY","value":"'"$(echo -n $AUDIT_KEY | base64)"'"}]'

# 3. Restart pods
kubectl rollout restart deployment/navi-backend -n navi-staging
```

### Issue: Database migration fails

**Cause:** Database connection issues or permission problems.

**Solution:**

```bash
# 1. Check database connectivity
kubectl exec -n navi-staging deployment/navi-backend -- \
  psql $DATABASE_URL -c 'SELECT version();'

# 2. Check database permissions
kubectl exec -n navi-staging deployment/navi-backend -- \
  psql $DATABASE_URL -c '\du navi_staging'

# 3. Manually run migrations
kubectl exec -n navi-staging deployment/navi-backend -- \
  alembic upgrade head
```

### Issue: Pods stuck in CrashLoopBackOff

**Cause:** Application startup failure.

**Solution:**

```bash
# 1. Check pod logs
kubectl logs -n navi-staging -l app=navi,component=backend --tail=200

# 2. Check pod events
kubectl describe pod -n navi-staging -l app=navi,component=backend

# 3. Check resource limits
kubectl top pods -n navi-staging -l app=navi,component=backend
```

### Issue: Health checks failing

**Cause:** Application not starting correctly or taking too long to start.

**Solution:**

```bash
# 1. Increase startup probe timeout
kubectl patch deployment navi-backend -n navi-staging \
  --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/startupProbe/failureThreshold","value":60}]'

# 2. Check application logs
kubectl logs -n navi-staging deployment/navi-backend --tail=200
```

## Rollback

If deployment fails or has issues:

```bash
# 1. Rollback to previous version
kubectl rollout undo deployment/navi-backend -n navi-staging

# 2. Check rollout status
kubectl rollout status deployment/navi-backend -n navi-staging

# 3. Verify rollback
kubectl rollout history deployment/navi-backend -n navi-staging
```

## Monitoring

After deployment, monitor the following:

### Metrics

```bash
# View Prometheus metrics
kubectl port-forward -n navi-staging deployment/navi-backend 8787:8787
curl http://localhost:8787/metrics

# Key metrics to watch:
# - http_requests_total
# - http_request_duration_seconds
# - navi_agent_latency_seconds
# - database_connection_pool_size
```

### Logs

```bash
# Tail logs from all pods
kubectl logs -n navi-staging -l app=navi,component=backend -f

# Search for errors
kubectl logs -n navi-staging -l app=navi,component=backend --tail=1000 | grep -i error

# Search for slow queries
kubectl logs -n navi-staging -l app=navi,component=backend --tail=1000 | grep -i "slow\|timeout"
```

### Alerts

Set up alerts for:

- Pod restart count > 3 in 10 minutes
- Memory usage > 80%
- CPU usage > 70%
- Request latency p95 > 10 seconds
- Error rate > 5%
- Database connection pool exhaustion

## Security Checklist

Before allowing traffic to staging:

- [ ] AUDIT_ENCRYPTION_KEY is set and unique to staging
- [ ] JWT_SECRET is set and different from production
- [ ] Database credentials are stored in Kubernetes secrets (not hardcoded)
- [ ] Network policies restrict pod-to-pod communication
- [ ] TLS/SSL enabled for database connections
- [ ] Secrets rotation policy in place (quarterly)
- [ ] CORS origins restricted to staging frontend only
- [ ] Rate limiting enabled
- [ ] Pod security policies enforced

## Next Steps

After successful staging deployment:

1. **Load Testing**: Run 100+ concurrent user tests
2. **Security Scan**: Run penetration testing
3. **Performance Validation**: Verify latency targets
4. **Integration Testing**: Test all integrations (Jira, GitHub, Slack)
5. **Monitoring Setup**: Configure Grafana dashboards and alerts
6. **Incident Response**: Test rollback procedures

Once staging is stable for 48 hours with no issues, proceed with production deployment.

## References

- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Staging Plan](STAGING_PLAN.md)
- [Production Readiness](NAVI_PROD_READINESS.md)
- [Performance Benchmarks](OPTIMIZED_TEST_RESULTS_FEB6.md)
