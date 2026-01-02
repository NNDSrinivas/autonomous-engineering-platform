# NAVI Deployment Runbook (Kubernetes Standard)

This runbook standardizes production deployments on Kubernetes (EKS/GKE/AKS). Docker Compose is supported for local dev only.

## Standard Platform
- Kubernetes for production workloads
- Managed Postgres and Redis (RDS/Cloud SQL + ElastiCache/Memorystore)
- External Secrets or Sealed Secrets for credential injection

## Required Inputs
Minimum required environment variables:
- DATABASE_URL
- REDIS_URL
- BACKEND_PUBLIC_URL
- OPENAI_API_KEY

Common production settings:
- JWT_ENABLED, JWT_ISSUER, JWT_AUDIENCE, JWT_SECRET
- TOKEN_ENCRYPTION_KEY_ID (KMS key id for token encryption)
- <PROVIDER>_CLIENT_ID / <PROVIDER>_CLIENT_SECRET for OAuth connectors

See `.env.example` for the full list.

## Kubernetes Artifacts
- k8s/namespace.yaml
- k8s/configmap.example.yaml
- k8s/secret.example.yaml
- k8s/deployment.yaml
- k8s/worker-deployment.yaml
- k8s/service.yaml
- k8s/ingress.yaml
- k8s/migration-job.yaml

## Deployment Steps
1) Build and push the container image.
2) Apply the namespace.
3) Create secrets (External Secrets recommended).
4) Apply configmap, deployment, worker, service, and ingress.
5) Run migrations before traffic is routed.
6) Verify health endpoints.

## Commands (Example)
```bash
# 1) Namespace
kubectl apply -f k8s/namespace.yaml

# 2) Secrets and config (use External Secrets in production)
kubectl apply -f k8s/secret.example.yaml
kubectl apply -f k8s/configmap.example.yaml

# 3) Deploy API + workers
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/worker-deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# 4) Migrations
kubectl apply -f k8s/migration-job.yaml
kubectl wait --for=condition=complete job/navi-migrate --timeout=300s

# 5) Verify
kubectl get pods -n navi-prod
kubectl logs deploy/navi-backend -n navi-prod --tail=100
```

## Migration Runbook
- Run `alembic upgrade heads` on each deploy.
- The provided job manifest runs migrations using the same image and env.
- Do not route traffic until the migration job completes successfully.

## Rollback
```bash
kubectl rollout undo deployment/navi-backend -n navi-prod
kubectl rollout undo deployment/navi-worker -n navi-prod
```

## OAuth Callback URL
`BACKEND_PUBLIC_URL` must match the public API ingress host, for example:
- https://api.navi.example.com

OAuth redirects should return users to:
- https://<org-domain>/settings/connectors?provider=<provider>&status=success

## Notes
- Keep secrets out of git. Use External Secrets or Sealed Secrets.
- Validate readiness at `/health/ready` before enabling traffic.
