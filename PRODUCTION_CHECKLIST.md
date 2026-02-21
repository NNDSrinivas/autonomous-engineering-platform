# AEP Production Go-Live Checklist

Last updated: 2026-02-21
Purpose: One-page verification checklist before DNS cutover to production

---

## Pre-Launch Phase (T-7 days)

### Infrastructure Readiness

- [ ] Production AWS account provisioned (ID: _____________)
- [ ] IAM deployer user/role created with least privilege
- [ ] AWS CLI profile `navra-prod` configured and tested
- [ ] Budget alerts configured (monthly cap, 80% warning)
- [ ] VPC created (NOT default VPC)
  - [ ] 2-3 AZs
  - [ ] Public subnets (ALB only)
  - [ ] Private subnets (ECS tasks)
  - [ ] NAT gateway(s) provisioned
  - [ ] VPC endpoints configured (ECR, CloudWatch, S3, Secrets Manager)

### Networking & Security

- [ ] Security groups created:
  - [ ] ALB SG: 80/443 from `0.0.0.0/0`
  - [ ] Frontend SG: 80 from ALB SG only
  - [ ] Backend SG: 8787 from ALB SG only
  - [ ] RDS SG: 5432 from backend SG only
  - [ ] Redis SG: 6379 from backend SG only
- [ ] ACM certificate requested for production domain
  - [ ] Domain: `app.navralabs.com` (or `navralabs.com`)
  - [ ] DNS validation records added to Route53
  - [ ] Certificate status: **Issued**
- [ ] ALB created (internet-facing, in public subnets)
  - [ ] Listener 443 configured (forward to frontend TG)
  - [ ] Listener 80 configured (redirect to 443)
  - [ ] Routing rules:
    - [ ] `/api/*` → backend TG
    - [ ] `/health/*` → backend TG
    - [ ] Default → frontend TG
- [ ] Target groups created:
  - [ ] `aep-prod-tg-frontend` (HTTP 80, health path `/`)
  - [ ] `aep-prod-tg-backend` (HTTP 8787, health path `/health/live`)

### Data Layer

- [ ] RDS database provisioned
  - [ ] Instance type: _____________ (e.g., db.t4g.micro)
  - [ ] Multi-AZ: Yes / No (document risk if No)
  - [ ] Automated backups: **Enabled** (retention: _____ days)
  - [ ] Public accessibility: **NO**
  - [ ] Security group attached
  - [ ] Master password stored in Secrets Manager
- [ ] Redis provisioned
  - [ ] ElastiCache Redis OR managed provider: _____________
  - [ ] Multi-AZ: Yes / No
  - [ ] Auth token enabled: Yes
  - [ ] Security group attached
  - [ ] Connection string stored in Secrets Manager

### Secrets

- [ ] All production secrets created in AWS Secrets Manager:
  - [ ] `aep/prod/AUDIT_ENCRYPTION_KEY`
  - [ ] `aep/prod/OPENAI_API_KEY`
  - [ ] `aep/prod/ANTHROPIC_API_KEY`
  - [ ] `aep/prod/DATABASE_URL`
  - [ ] `aep/prod/REDIS_URL`
- [ ] Task execution role has `secretsmanager:GetSecretValue` for prod secrets only
- [ ] Secrets **never** in plaintext in task definitions

---

## Launch Phase (T-1 day)

### ECR & Images

- [ ] ECR repositories created:
  - [ ] `navralabs/aep-backend` (tag: `prod` or separate `navralabs/aep-backend-prod`)
  - [ ] `navralabs/aep-frontend` (tag: `prod` or separate `navralabs/aep-frontend-prod`)
- [ ] Images built for `linux/amd64`
- [ ] Images pushed to ECR
- [ ] Image digests recorded (for rollback):
  - Backend: `sha256:_____________`
  - Frontend: `sha256:_____________`
- [ ] Image scanning enabled and passed

### ECS Cluster & Tasks

- [ ] ECS cluster created: `aep-prod`
- [ ] Backend task definition registered:
  - [ ] Family: `aep-backend-prod`
  - [ ] Revision: `:1`
  - [ ] Container port: `8787`
  - [ ] Environment variables:
    - [ ] `APP_ENV=production`
    - [ ] `BUDGET_ENFORCEMENT_MODE=strict`
    - [ ] `CORS_ORIGINS=https://app.navralabs.com`
  - [ ] Secrets: **All** from Secrets Manager (no plaintext)
  - [ ] CPU: _____ (e.g., 512)
  - [ ] Memory: _____ (e.g., 1024)
  - [ ] Logs: CloudWatch log group `/ecs/aep-backend-prod`
- [ ] Frontend task definition registered:
  - [ ] Family: `aep-frontend-prod`
  - [ ] Revision: `:1`
  - [ ] Container port: `80`
  - [ ] CPU: _____ (e.g., 256)
  - [ ] Memory: _____ (e.g., 512)
  - [ ] Logs: CloudWatch log group `/ecs/aep-frontend-prod`

### ECS Services

- [ ] Backend service created: `aep-backend-prod-svc`
  - [ ] Desired count: _____ (minimum 1, recommend 2 for HA)
  - [ ] Launch type: Fargate
  - [ ] Subnets: **Private subnets only**
  - [ ] Public IP: **NO**
  - [ ] Security group: backend SG
  - [ ] Target group: backend TG
  - [ ] Health check grace period: 300s
- [ ] Frontend service created: `aep-frontend-prod-svc`
  - [ ] Desired count: _____ (minimum 1, recommend 2 for HA)
  - [ ] Subnets: **Private subnets only**
  - [ ] Public IP: **NO**
  - [ ] Security group: frontend SG
  - [ ] Target group: frontend TG

### Database Migrations

- [ ] Alembic migrations executed on production database:
  ```bash
  alembic upgrade head
  ```
- [ ] Migration verified:
  ```sql
  SELECT version_num FROM alembic_version;
  ```
- [ ] Expected table count: _____ (e.g., 30+ tables)

---

## Go-Live Verification (T-0, Pre-Cutover)

### Health Checks (Critical — Do NOT proceed if failing)

- [ ] Backend liveness endpoint:
  ```bash
  curl http://<alb-dns>/health/live
  # Expected: 200 OK
  ```
- [ ] Backend readiness endpoint:
  ```bash
  curl http://<alb-dns>/health/ready
  # Expected: {"ok": true, "checks": [{"name": "self", "ok": true}, {"name": "db", "ok": true}, {"name": "redis", "ok": true}]}
  ```
- [ ] Frontend loads:
  ```bash
  curl http://<alb-dns>/
  # Expected: 200 OK, HTML
  ```

### ECS Service Status

- [ ] Backend service stable:
  ```bash
  aws ecs describe-services --cluster aep-prod --services aep-backend-prod-svc
  # deployments[0].runningCount == desiredCount
  ```
- [ ] Frontend service stable:
  ```bash
  aws ecs describe-services --cluster aep-prod --services aep-frontend-prod-svc
  # deployments[0].runningCount == desiredCount
  ```

### ALB Target Health

- [ ] Backend targets healthy:
  ```bash
  aws elbv2 describe-target-health --target-group-arn <backend-tg-arn>
  # All targets: State = healthy
  ```
- [ ] Frontend targets healthy:
  ```bash
  aws elbv2 describe-target-health --target-group-arn <frontend-tg-arn>
  # All targets: State = healthy
  ```

### Smoke Tests

Run against ALB DNS (before DNS cutover):

- [ ] API test:
  ```bash
  curl http://<alb-dns>/api/health/ready
  # Expected: 200, JSON
  ```
- [ ] Model routing test (if applicable):
  ```bash
  curl -X POST http://<alb-dns>/api/v1/chat \
    -H "Authorization: Bearer <test-token>" \
    -H "Content-Type: application/json" \
    -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "test"}]}'
  # Expected: 200 or 401 (auth required)
  ```
- [ ] Budget enforcement test:
  - [ ] Verify tier limits are respected
  - [ ] Verify overage returns 429

### Logs Check

- [ ] Backend logs clean:
  ```bash
  aws logs tail /ecs/aep-backend-prod --since 10m
  # No errors, no "transport closed", no DB failures
  ```
- [ ] Frontend logs clean:
  ```bash
  aws logs tail /ecs/aep-frontend-prod --since 10m
  # No errors
  ```

### Observability

- [ ] CloudWatch dashboards created (optional but recommended):
  - [ ] ALB 2xx/4xx/5xx
  - [ ] Target health count
  - [ ] ECS CPU/memory
  - [ ] Request latency
- [ ] CloudWatch alarms configured:
  - [ ] Unhealthy target count > 0
  - [ ] 5xx rate > 5%
  - [ ] ECS running tasks < desired count
- [ ] ALB access logs enabled (recommended):
  - [ ] S3 bucket created: `aep-prod-alb-logs`
  - [ ] ALB logging enabled

---

## DNS Cutover (T=0, Go-Live)

### Pre-Cutover

- [ ] Lower TTL on existing DNS record (if applicable):
  ```bash
  # Set TTL to 60 seconds 24 hours before cutover
  aws route53 change-resource-record-sets ...
  ```
- [ ] Record current DNS target (for rollback):
  ```bash
  dig app.navralabs.com
  # Current target: _____________
  ```

### Cutover

- [ ] Create Route53 alias record:
  ```bash
  # Domain: app.navralabs.com
  # Type: A (Alias)
  # Target: ALB DNS name (aep-prod-alb-xxxx.us-east-1.elb.amazonaws.com)
  ```
- [ ] Verify DNS propagation:
  ```bash
  dig app.navralabs.com
  nslookup app.navralabs.com
  # Expected: ALB IP addresses
  ```

### Post-Cutover Monitoring (First 30 minutes)

- [ ] Health checks green:
  ```bash
  curl https://app.navralabs.com/health/ready
  # Expected: {"ok": true, ...}
  ```
- [ ] Frontend loads:
  ```bash
  curl https://app.navralabs.com/
  # Expected: 200, HTML
  ```
- [ ] API responds:
  ```bash
  curl https://app.navralabs.com/health/ready
  # Expected: 200, JSON
  ```
- [ ] HTTPS enforced:
  ```bash
  curl http://app.navralabs.com/
  # Expected: 301 redirect to https://
  ```
- [ ] CloudWatch metrics (watch for 30 min):
  - [ ] 5xx rate < 1%
  - [ ] Target health stable
  - [ ] Request count increasing (traffic shifting)
  - [ ] No unhealthy targets

### User Acceptance Testing

- [ ] Manual test: Load frontend in browser
- [ ] Manual test: Login/auth flow (if applicable)
- [ ] Manual test: Key user journey (e.g., create chat, send message)
- [ ] Manual test: Budget enforcement (test tier limits)

---

## Rollback Plan (If Needed)

If health checks fail, errors spike, or critical issue discovered:

### Immediate Rollback (DNS)

- [ ] Revert Route53 record to previous target:
  ```bash
  aws route53 change-resource-record-sets ...
  # Point app.navralabs.com back to staging or previous prod ALB
  ```
- [ ] Verify rollback:
  ```bash
  dig app.navralabs.com
  # Expected: Previous target IP
  ```

### ECS Rollback (If Issue is in Code)

- [ ] Rollback backend:
  ```bash
  aws ecs update-service \
    --cluster aep-prod \
    --service aep-backend-prod-svc \
    --task-definition aep-backend-prod:0  # previous revision
  ```
- [ ] Rollback frontend:
  ```bash
  aws ecs update-service \
    --cluster aep-prod \
    --service aep-frontend-prod-svc \
    --task-definition aep-frontend-prod:0  # previous revision
  ```

### Database Rollback (DANGEROUS — Avoid if possible)

Only if migration broke production:

```bash
cd backend
alembic downgrade -1  # or specific revision
```

**WARNING**: Test on staging first. Data loss risk.

---

## Post-Launch (T+24 hours)

- [ ] Monitor CloudWatch metrics for 24 hours
- [ ] Review logs for any errors or warnings
- [ ] Confirm no user-reported issues
- [ ] Restore DNS TTL to normal (e.g., 300s or 3600s)
- [ ] Document any issues encountered
- [ ] Celebrate 🎉

---

## Success Criteria

Production is considered successfully launched when:

- [ ] DNS points to production ALB
- [ ] HTTPS enforced (HTTP → 301)
- [ ] `/health/ready` returns 200 (db + redis healthy)
- [ ] Frontend loads correctly
- [ ] API responds to requests
- [ ] No 5xx errors (< 0.1% acceptable)
- [ ] All ALB targets healthy
- [ ] Budget enforcement active (`BUDGET_ENFORCEMENT_MODE=strict`)
- [ ] Logs clean (no critical errors)
- [ ] No secrets in plaintext
- [ ] ECS tasks in private subnets (no public IPs)
- [ ] CloudWatch alarms configured
- [ ] User acceptance tests passed
- [ ] 24-hour stability confirmed

---

## Production Risk Log (Document Accepted Risks)

If any best practices are skipped for cost/time, document here:

| Risk | Accepted? | Mitigation Plan |
|------|-----------|-----------------|
| Single-AZ RDS (no Multi-AZ) | Yes / No | Accept downtime risk OR upgrade to Multi-AZ by [date] |
| Single task per service (no HA) | Yes / No | Accept downtime risk OR scale to 2 tasks by [date] |
| No WAF enabled | Yes / No | Add WAF before public launch OR monitor for abuse |
| No autoscaling | Yes / No | Manual scaling acceptable OR add autoscaling by [date] |
| Single NAT gateway | Yes / No | Accept AZ failure risk OR add second NAT by [date] |

---

## Emergency Contacts

| Role | Name | Contact |
|------|------|---------|
| On-call Engineer | _______ | Slack: _______ |
| Engineering Lead | _______ | Email: _______ |
| AWS Account Owner | _______ | Email: _______ |
| Domain/DNS Admin | _______ | Email: _______ |

---

## Final Sign-Off

- [ ] Infrastructure Lead: _______________ Date: _____
- [ ] Engineering Lead: _______________ Date: _____
- [ ] Security Review: _______________ Date: _____
- [ ] Go/No-Go Decision: **GO** / **NO-GO**

---

**Once all checkboxes are complete and sign-off obtained, proceed with DNS cutover.**

**Good luck. You've built something real.**
