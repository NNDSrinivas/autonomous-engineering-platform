# Production Rollout Plan (AEP on AWS)

Last updated: 2026-02-20
Goal: replicate staging architecture into Production account with production-grade networking, security, and deployment controls.

## 0) Principles

- Prod should be **private by default**: tasks in private subnets, no public IPs.
- Secrets never in task definitions (Secrets Manager only).
- Prefer least privilege IAM + separation of duties.
- Repeatable infrastructure (IaC recommended; if manual, document every console action).
- Staging remains the proving ground; prod changes are promoted.

---

## 1) Account & Access Setup (Production account)

1. Create Production AWS account (management or member per org structure).
2. Create IAM roles:
   - `Deployer` role/user with scoped permissions (ECS/ECR/ALB/ACM/Route53/Secrets).
   - Break-glass admin (MFA, no access keys unless strictly needed).
3. Configure AWS CLI profile `navra-prod`.
4. Budgets:
   - Account budget (monthly)
   - Service-level guardrails (optional) + alerts to email/Slack.

**Exit criteria:** `aws sts get-caller-identity --profile navra-prod` returns prod account id.

---

## 2) Networking (Prod VPC)

Create a dedicated VPC (do NOT use default VPC):
- 2–3 AZs
- Public subnets (ALB only)
- Private subnets (ECS tasks)
- NAT gateways (1 per AZ if strict HA; can start with 1 to reduce cost)
- VPC endpoints (recommended for cost/security):
  - ECR (api + dkr)
  - CloudWatch Logs
  - S3 (gateway)
  - Secrets Manager (optional but recommended)

**Exit criteria:** ECS tasks can pull ECR images and write logs without public IP.

---

## 3) ECR (Prod Repositories + Promotion Model)

Option A (Recommended): Separate repos per env
- `navralabs/aep-backend:prod`
- `navralabs/aep-frontend:prod`

Option B: Same repo, separate tags
- `:staging` and `:prod`

Promotion strategy:
- Promote by **immutable digest** (preferred)
- Or promote by retagging a tested digest from `staging` to `prod`

Enable:
- Scan on push
- Lifecycle policies (retain last N images)

---

## 4) Secrets Manager (Prod)

Create prod secrets (names mirror staging):
- `aep/prod/AUDIT_ENCRYPTION_KEY`
- `aep/prod/OPENAI_API_KEY`
- `aep/prod/ANTHROPIC_API_KEY`
- `aep/prod/DATABASE_URL`
- `aep/prod/REDIS_URL`

Rotate strategy:
- Start manual rotation
- Add automatic rotation later (DB especially)

---

## 5) Data (RDS + Redis)

RDS:
- Multi-AZ recommended (or start single AZ for cost, plan upgrade)
- Automated backups + retention policy
- Parameter group tuned for workload later

Redis:
- ElastiCache Redis (recommended) OR managed Redis provider
- Multi-AZ / cluster mode depends on needs
- Ensure security group allows only backend tasks

Migration:
- Run Alembic migrations in prod via CI job or one-off ECS task.

---

## 6) ALB + TLS + DNS

- ACM cert for:
  - `navralabs.com`
  - `app.navralabs.com` (or `aep.navralabs.com`)
  - optional: `api.navralabs.com` if you later split hostnames
- ALB (internet-facing) in public subnets
- Listeners:
  - 443 forward to frontend TG
  - 80 redirect to 443
- Rules:
  - `/api/*` → backend TG
  - `/health/*` → backend TG
  - default → frontend TG

Route53:
- `app.navralabs.com` → ALB alias
- Consider `api.navralabs.com` later if you want clean separation.

---

## 7) ECS (Prod Cluster, Task Definitions, Services)

Cluster:
- `aep-prod`

Tasks:
- `aep-backend-prod` (port 8787)
- `aep-frontend-prod` (port 80)

Services:
- Desired count:
  - Backend: start at 2 (HA) if budget allows; otherwise 1 (accept downtime risk)
  - Frontend: 2 if budget allows; otherwise 1
- Networking:
  - private subnets
  - public IP OFF
- SGs:
  - ALB SG: 80/443 from internet
  - Frontend SG: 80 from ALB SG only
  - Backend SG: 8787 from ALB SG only

Deployment:
- Rolling update initially
- Add blue/green (CodeDeploy) later if needed

---

## 8) Observability & Alerting (Prod Baseline)

Minimum:
- ALB access logs to S3
- CloudWatch alarms:
  - Unhealthy host count > 0
  - 5xx spikes
  - ECS service running < desired
  - CPU/memory high
  - Budget enforcement rejection rate (app metric) if available
- Dashboard:
  - ALB 2xx/4xx/5xx
  - Target health
  - ECS CPU/memory
  - Latency

---

## 9) Security Hardening (Prod)

- WAF (optional early, recommended before public launch)
  - Managed rules: CommonRuleSet
  - Rate limiting on `/api/*`
- Strict CORS:
  - `https://app.navralabs.com` only
- TLS policy modern
- Secrets access:
  - Task role least privilege to only required secrets
- Container hardening:
  - non-root user where feasible
  - read-only root fs where possible
  - drop capabilities (later)

---

## 10) Cutover Plan (Staging → Prod)

1. Deploy prod stack in parallel (no DNS cutover yet).
2. Verify health endpoints:
   - `/health/live` 200
   - `/health/ready` 200 (db + redis)
3. Smoke tests:
   - Frontend loads
   - `/api/*` returns expected responses
   - Auth flows if present
4. Data migrations: execute and validate.
5. DNS cutover:
   - set low TTL ahead of time (e.g., 60s)
   - point `app.navralabs.com` to prod ALB alias
6. Post-cutover monitoring:
   - watch 5xx, latency, unhealthy targets, DB connections
7. Rollback:
   - revert Route53 alias to staging ALB or prior prod ALB
   - keep last known good task definition revision handy

---

## 11) Cost-Control Starter Profile (Prod)

To keep costs minimal initially:
- 2 AZs instead of 3
- 1 NAT gateway (accept AZ failure risk)
- 1 task per service (accept downtime risk)
- Single-AZ RDS (upgrade later)
- No WAF initially (add before scaling / exposure)

Document which risks are accepted.

---

## Exit Criteria (Prod "Go Live")

- HTTPS on real prod domain
- `/health/ready` green (db + redis)
- Secrets in Secrets Manager only
- Tasks in private subnets, no public IP
- Observability alarms configured
- Rollback procedure tested
