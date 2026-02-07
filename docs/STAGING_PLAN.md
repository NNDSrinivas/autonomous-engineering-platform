# NAVI Staging Environment Plan

Goal: provide a production-like environment that validates reliability, performance, and security before release.

## 1) Environment Topology

- `dev`: local + ephemeral testing.
- `staging`: production-like, smaller scale.
- `prod`: full scale.

Data separation:
- Separate databases and Redis instances per environment.
- No production data in staging unless masked.

## 2) Staging Infra Baseline

- Deploy via `k8s/` or `infra/terraform/aws`.
- Same container images as prod.
- Same feature flags and configs as prod (except scale and secrets).

**Required Secrets for Staging:**
- `DATABASE_URL` - PostgreSQL connection string
- `AUDIT_ENCRYPTION_KEY` - **MANDATORY** for audit log encryption (32-byte base64 key)
- `JWT_SECRET` - JWT token signing key
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` - LLM provider API key

## 3) CI/CD Flow

1. Build image on every commit.
2. Deploy to staging automatically.
3. Run smoke tests + benchmark suite.
4. Manual approval gate for prod.
5. Deploy to prod with rollback ready.

Workflow references:
- Staging deploy: `.github/workflows/deploy-staging.yml`
- Production deploy: `.github/workflows/deploy.yml` (manual + benchmark freshness gate)

## 4) Staging Validation Checklist

- [ ] Health endpoints up (`/health`, `/health/live`, `/health/ready`)
- [ ] **Audit encryption configured** (`AUDIT_ENCRYPTION_KEY` set) ⚠️ MANDATORY
- [ ] Backend starts without encryption key errors
- [ ] Core agent flows succeed
- [ ] Run/start detection works on real repos
- [ ] Audit events emitted and exportable
- [ ] Latency within target p95 (<5s p95)

## 5) Release Process

- Release candidate tag created after staging pass.
- Verify changelog + risk summary.
- Rollback plan confirmed (previous image + DB rollback).

## 6) Multi-Cloud Considerations

- AWS staging first (existing Terraform).
- GCP/Azure parity added once AWS staging is stable.
