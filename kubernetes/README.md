# Kubernetes Deployment Manifests for NAVI

This directory contains Kubernetes manifests for deploying NAVI to staging and production environments.

## Directory Structure

```
kubernetes/
├── secrets/
│   ├── database-staging.yaml        # Database credentials for staging
│   ├── database-production.yaml     # Database credentials for production
│   └── README.md                    # Secrets management guide
├── deployments/
│   ├── backend-staging.yaml         # Backend deployment (staging)
│   └── backend-production.yaml      # Backend deployment (production)
├── cronjobs/
│   └── feedback-analyzer.yaml       # Periodic learning system analyzer
└── README.md                        # This file
```

## Prerequisites

1. **Kubernetes Cluster**: v1.24+ with kubectl configured
2. **PostgreSQL Database**: Managed service (AWS RDS, GCP Cloud SQL, Azure Database)
3. **Container Registry**: Docker images pushed to registry
4. **Secrets Management**: Database credentials configured

## Quick Start

### 1. Set Up Database

See [docs/DEPLOYMENT_GUIDE.md](../docs/DEPLOYMENT_GUIDE.md#2-database-setup) for detailed database setup instructions.

**TL;DR:**

```bash
# Create staging namespace
kubectl create namespace navi-staging

# Create database secret (replace ${STAGING_DB_PASSWORD})
kubectl create secret generic navi-database-staging \
  --from-literal=DATABASE_URL='postgresql+psycopg2://navi_staging:${STAGING_DB_PASSWORD}@staging-db-host:5432/navi_staging' \
  --namespace navi-staging

# Or apply from file
kubectl apply -f secrets/database-staging.yaml
```

### 2. Deploy Application

```bash
# Deploy backend (includes init container for migrations)
kubectl apply -f deployments/backend-staging.yaml

# Verify deployment
kubectl get pods -n navi-staging
kubectl logs -n navi-staging deployment/navi-backend -c db-migrate  # Check migration logs
kubectl logs -n navi-staging deployment/navi-backend -c backend     # Check app logs
```

### 3. Verify Health

```bash
# Port-forward to test locally
kubectl port-forward -n navi-staging service/navi-backend 8787:8787 &

# Check health endpoints
curl http://localhost:8787/health
curl http://localhost:8787/health/ready
curl http://localhost:8787/api/telemetry/health
```

## Database Migrations

### Automatic Migrations (Staging Only)

The staging deployment includes an init container that runs `alembic upgrade head` automatically before the app starts.

```yaml
initContainers:
  - name: db-migrate
    image: your-registry/navi-backend:staging
    command:
      - /bin/sh
      - -c
      - "alembic upgrade head"
```

### Manual Migrations (Production)

⚠️ **Production migrations must be reviewed and approved manually!**

```bash
# 1. Review migration SQL first
alembic upgrade head --sql > migration-$(date +%Y%m%d).sql
cat migration-$(date +%Y%m%d).sql  # Review changes

# 2. Create backup
kubectl exec -n navi-production deployment/navi-backend -- \
  pg_dump $DATABASE_URL > backup-$(date +%Y%m%d-%H%M%S).sql

# 3. Run migration during maintenance window
kubectl exec -n navi-production deployment/navi-backend -c backend -- \
  alembic upgrade head

# 4. Verify
kubectl exec -n navi-production deployment/navi-backend -c backend -- \
  alembic current
```

## Secrets Management

### Development/Staging

For staging, it's acceptable to use Kubernetes Secrets directly:

```bash
kubectl create secret generic navi-database-staging \
  --from-literal=DATABASE_URL='postgresql+psycopg2://...' \
  --namespace navi-staging
```

### Production

For production, **ALWAYS** use external secrets management:

**Option 1: AWS Secrets Manager + External Secrets Operator**

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: navi-database-production
  namespace: navi-production
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: navi-database-production
  data:
    - secretKey: DATABASE_URL
      remoteRef:
        key: navi/prod/database-url
```

**Option 2: HashiCorp Vault**

```yaml
apiVersion: secrets.hashicorp.com/v1beta1
kind: VaultStaticSecret
metadata:
  name: navi-database-production
  namespace: navi-production
spec:
  vaultAuthRef: navi-prod
  mount: secret
  path: navi/database
  refreshAfter: 1h
```

**Option 3: Sealed Secrets**

```bash
# Encrypt secret with sealed-secrets
kubectl create secret generic navi-database-production \
  --from-literal=DATABASE_URL='...' \
  --dry-run=client -o yaml | \
  kubeseal -o yaml > sealed-secret-database-production.yaml

# Apply sealed secret (safe to commit)
kubectl apply -f sealed-secret-database-production.yaml
```

## Environment Variables

### Database Environment Variables

Set via `navi-database-staging` / `navi-database-production` secret:

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg2://user:pass@host:5432/db` |
| `DB_HOST` | Database host | `postgres-staging.navi.svc.cluster.local` |
| `DB_PORT` | Database port | `5432` |
| `DB_NAME` | Database name | `navi_staging` |
| `DB_USER` | Database username | `navi_staging` |
| `DB_PASSWORD` | Database password | `***` |
| `DB_SSLMODE` | SSL mode | `require` |

### Database Connection Pool Settings

Set via `navi-database-config-staging` ConfigMap:

| Variable | Staging | Production |
|----------|---------|------------|
| `DB_POOL_SIZE` | 20 | 50 |
| `DB_MAX_OVERFLOW` | 40 | 100 |
| `DB_POOL_TIMEOUT` | 30 | 30 |
| `DB_POOL_RECYCLE` | 3600 | 1800 |
| `ALEMBIC_AUTO_UPGRADE` | true | **false** |

## Monitoring

### Health Checks

All deployments include startup, readiness, and liveness probes:

```yaml
startupProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 10
  periodSeconds: 5
  failureThreshold: 30

readinessProbe:
  httpGet:
    path: /health/ready
    port: http
  periodSeconds: 10

livenessProbe:
  httpGet:
    path: /health/live
    port: http
  periodSeconds: 20
```

### Database Monitoring

Check database connection health:

```bash
# Check database connections from app
kubectl exec -n navi-staging deployment/navi-backend -c backend -- \
  psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'navi_staging';"

# Check slow queries
kubectl exec -n navi-staging deployment/navi-backend -c backend -- \
  psql $DATABASE_URL -c "SELECT pid, now() - query_start AS duration, query FROM pg_stat_activity WHERE state = 'active' AND now() - query_start > interval '5 seconds';"
```

## Auto-Scaling

Backend deployments include HorizontalPodAutoscaler:

```yaml
spec:
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          averageUtilization: 70
```

Monitor scaling:

```bash
kubectl get hpa -n navi-staging
kubectl describe hpa navi-backend -n navi-staging
```

## Troubleshooting

### Database Connection Issues

```bash
# Check if DATABASE_URL is set correctly
kubectl exec -n navi-staging deployment/navi-backend -c backend -- \
  env | grep DATABASE

# Test database connectivity
kubectl exec -n navi-staging deployment/navi-backend -c backend -- \
  psql $DATABASE_URL -c "SELECT version();"

# Check database logs
kubectl logs -n navi-staging deployment/navi-backend -c backend | grep -i database
```

### Migration Failures

```bash
# Check init container logs
kubectl logs -n navi-staging deployment/navi-backend -c db-migrate

# Manually run migrations
kubectl exec -it -n navi-staging deployment/navi-backend -c backend -- \
  alembic upgrade head

# Check current migration version
kubectl exec -n navi-staging deployment/navi-backend -c backend -- \
  alembic current

# Rollback one version (if needed)
kubectl exec -n navi-staging deployment/navi-backend -c backend -- \
  alembic downgrade -1
```

### Pod Startup Issues

```bash
# Describe pod for events
kubectl describe pod -n navi-staging -l app=navi,component=backend

# Check all container logs
kubectl logs -n navi-staging deployment/navi-backend --all-containers

# Interactive debugging
kubectl exec -it -n navi-staging deployment/navi-backend -c backend -- /bin/sh
```

## Security Best Practices

1. ✅ **Never commit secrets** - Use external secrets management
2. ✅ **Enable SSL/TLS** - Set `DB_SSLMODE=require`
3. ✅ **Rotate credentials** - Quarterly rotation minimum
4. ✅ **Principle of least privilege** - Use dedicated database user with minimal permissions
5. ✅ **Network policies** - Restrict pod-to-pod communication
6. ✅ **Security contexts** - Run as non-root, drop capabilities
7. ✅ **Resource limits** - Prevent resource exhaustion attacks
8. ✅ **Pod disruption budgets** - Maintain availability during updates

## CI/CD Integration

GitHub Actions workflow example:

```yaml
- name: Deploy to Staging
  run: |
    kubectl apply -f kubernetes/secrets/database-staging.yaml
    kubectl apply -f kubernetes/deployments/backend-staging.yaml
    kubectl rollout status deployment/navi-backend -n navi-staging --timeout=5m

- name: Verify Deployment
  run: |
    kubectl get pods -n navi-staging
    kubectl exec -n navi-staging deployment/navi-backend -c backend -- \
      curl -f http://localhost:8787/health || exit 1
```

## Related Documentation

- [Deployment Guide](../docs/DEPLOYMENT_GUIDE.md) - Complete deployment instructions
- [Production Readiness](../docs/NAVI_PROD_READINESS.md) - Production checklist
- [Database Migration Guide](../alembic/README.md) - Alembic migration details
- [Secrets Guide](../docs/PRODUCTION_SECRETS_GUIDE.md) - Secrets management

## Support

For deployment issues, see:
- GitHub Issues: https://github.com/your-org/autonomous-engineering-platform/issues
- Internal Docs: Confluence/Wiki
- On-call: PagerDuty rotation
