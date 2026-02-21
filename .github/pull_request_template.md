# AEP Pull Request Checklist

## 1. Change Type

- [ ] Backend code change
- [ ] Frontend code change
- [ ] Infrastructure (ECS / ALB / VPC / RDS / Redis)
- [ ] Secrets / IAM
- [ ] Model routing / budget enforcement
- [ ] Database migration
- [ ] Observability / logging
- [ ] Security hardening
- [ ] Production rollout
- [ ] Hotfix

---

## 2. Summary of Change

Describe what this PR does in 3–5 clear sentences:

- What changed?
- Why?
- Risk level (Low / Medium / High)?
- Does it affect runtime traffic?

---

## 3. Staging Verification (REQUIRED)

### Build & Deploy
- [ ] Image built for `linux/amd64`
- [ ] Pushed to correct ECR repo (`navralabs/...`)
- [ ] Task definition revision updated
- [ ] ECS service deployed
- [ ] Old tasks drained cleanly

### Health Checks
- [ ] `/health/live` returns 200
- [ ] `/health/ready` returns 200
- [ ] DB check passes
- [ ] Redis check passes
- [ ] No unexpected 5xx in ALB

### Logs
- [ ] No startup errors in CloudWatch
- [ ] No "transport closed" (Redis)
- [ ] No DB connection leaks
- [ ] No unhandled exceptions

---

## 4. Infrastructure Checklist (if applicable)

### ECS
- [ ] Correct task definition family
- [ ] Correct revision deployed
- [ ] Correct container port
- [ ] Correct security groups
- [ ] No plaintext secrets in task definition

### ALB
- [ ] Routing rules correct
- [ ] `/api/*` → backend
- [ ] `/health/*` → backend
- [ ] Default → frontend
- [ ] HTTP → HTTPS redirect intact

### Secrets
- [ ] Secrets stored in AWS Secrets Manager
- [ ] Task role has least privilege
- [ ] No secrets committed to repo

### Database
- [ ] Alembic migration reviewed
- [ ] Migration tested on staging
- [ ] Rollback plan exists

---

## 5. Model Routing / Budget Enforcement (if applicable)

- [ ] No unapproved models enabled in production
- [ ] Cost metadata correct
- [ ] Tier policy unchanged or reviewed
- [ ] Fail-closed behavior preserved
- [ ] No routing fallback weakens safety

---

## 6. Redis Changes (if applicable)

- [ ] No new `Redis.from_url` instantiations
- [ ] Using centralized `get_redis()` client
- [ ] No module-level singleton clients
- [ ] No client `.close()` outside lifecycle

---

## 7. Security Review

- [ ] No widened security groups
- [ ] No new public exposure
- [ ] CORS restricted appropriately
- [ ] No debug flags enabled
- [ ] No stack traces exposed to clients

---

## 8. Production Rollout Plan (Required for prod-impacting PRs)

If this change goes to production:

### Deployment Strategy
- [ ] Rolling update
- [ ] Blue/green
- [ ] Maintenance window required?

### Rollback Plan
Describe exact rollback steps:

1.
2.
3.

- [ ] Previous task definition revision noted
- [ ] Previous image digest recorded
- [ ] DNS rollback strategy (if applicable)

---

## 9. Observability Impact

- [ ] New metrics added?
- [ ] New logs added?
- [ ] Alerts need updating?
- [ ] Dashboards updated?

---

## 10. Cost Impact

- [ ] No material cost change
- [ ] Expected minor increase (< $X/month)
- [ ] Significant increase — approved

Describe if needed:

---

## 11. Final Validation

Before merge:

- [ ] Reviewer approved
- [ ] Staging green
- [ ] No open critical logs
- [ ] No unhealthy targets
- [ ] Documentation updated (if required)

---

## Reviewer Notes

Reviewer must verify:

- Health endpoints
- ECS service status
- Target group health
- No plaintext secrets
- No regressions in routing

---

**Merge policy:**
- No direct commits to main.
- All infra changes must pass staging validation.
