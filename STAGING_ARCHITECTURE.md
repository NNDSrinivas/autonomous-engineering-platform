# AEP Staging Architecture (AWS)

Last updated: 2026-02-20
Account: Staging (625847798833)
Region: us-east-1
Primary URL: https://staging.navralabs.com

## 1) High-level Overview

AEP staging is deployed as two ECS Fargate services behind a single internet-facing ALB:

- **Frontend**: nginx + React SPA (HTTP 80)
- **Backend**: FastAPI (HTTP 8787)
- **ALB** routes:
  - `/api/*` → backend target group
  - `/health/*` → backend target group
  - `/*` → frontend target group

The environment is HTTPS-first with HTTP→HTTPS redirects and secrets pulled from AWS Secrets Manager.

## 2) DNS + TLS

- Route53 Hosted Zone: `navralabs.com`
- Record: `staging.navralabs.com` (A Alias → ALB)
- ACM Certificate: `staging.navralabs.com` (DNS validated, in us-east-1)
- ALB listeners:
  - 443 HTTPS (default action → frontend TG)
  - 80 HTTP (301 redirect → HTTPS)

## 3) Networking

VPC:
- Using **default VPC** in us-east-1 (vpc-0652a6de1c9efdc2f)

Subnets:
- 3 public subnets across AZs (us-east-1a, 1b, 1c)
- ECS tasks currently run with **Public IP = ON** (staging convenience)

Security Groups:
- `aep-staging-alb-sg` (sg-08200836125a8f3af)
  - Inbound: 80/443 from 0.0.0.0/0
  - Outbound: all
- `aep-staging-ecs-frontend-sg` (sg-052b6de52177c40be)
  - Inbound: 80 **from ALB SG only**
  - Outbound: all
- `aep-staging-ecs-backend-sg` (sg-024e491e60830af98)
  - Inbound: 8787 **from ALB SG only**
  - Outbound: all

## 4) Compute (ECS Fargate)

ECS Cluster:
- `aep-staging`

Task Definitions:
- Backend:
  - Family: `aep-backend-staging`
  - Current revision: `:10`
  - Container port: `8787`
- Frontend:
  - Family: `aep-frontend-staging`
  - Current revision: `:1`
  - Container port: `80`

Services:
- `aep-backend-staging-svc`
  - Desired count: 1
  - Attached to backend target group
- `aep-frontend-staging-svc`
  - Desired count: 1
  - Attached to frontend target group

## 5) Load Balancing (ALB)

ALB:
- Name: `aep-staging-alb`
- Scheme: Internet-facing
- Listener rules (HTTPS 443):
  1. `/api/*` → `aep-staging-tg-backend`
  2. `/health/*` → `aep-staging-tg-backend`
  3. Default → `aep-staging-tg-frontend`

Target Groups (type = IP):
- `aep-staging-tg-frontend` (HTTP 80, health path `/`)
- `aep-staging-tg-backend` (HTTP 8787, health path `/health/live`)

## 6) Secrets + Configuration

Secrets Manager (staging):
- `aep/staging/AUDIT_ENCRYPTION_KEY`
- `aep/staging/OPENAI_API_KEY`
- `aep/staging/ANTHROPIC_API_KEY`
- `aep/staging/DATABASE_URL`
- `aep/staging/REDIS_URL`

Non-sensitive env vars (plaintext in task def):
- `APP_ENV=staging`
- `BUDGET_ENFORCEMENT_MODE=strict` (or equivalent)
- `CORS_ORIGINS=https://staging.navralabs.com`

## 7) Health Endpoints

Backend:
- `/health/live` → liveness (process alive)
- `/health/ready` → readiness (self + db + redis)

ALB must route `/health/*` to backend TG to avoid frontend intercepting health probes.

## 8) Data Layer

- RDS is provisioned for staging
- Alembic migrations executed successfully (30+ tables created)
- DB connectivity is verified by readiness health check

## 9) Redis

Redis is configured via `REDIS_URL` from Secrets Manager.

Known implementation details:
- Phase 1 fix introduced centralized Redis lifecycle used by readiness health check to prevent "transport closed" failures.
- Other parts of the codebase may still instantiate Redis independently (Phase 2 planned migration).

## 10) Logging & Observability

- CloudWatch log groups exist for backend and frontend
- ECS tasks stream logs via awslogs driver

Recommended additions (future hardening):
- ALB access logs to S3
- Metrics dashboards (ALB target health, ECS CPU/mem, 4xx/5xx)
- Alerts (unhealthy targets, 5xx spikes, budget enforcement rejections)

## 11) Staging Tradeoffs (Intentional)

Current staging choices (acceptable for staging, change for prod):
- Default VPC + public subnets + Public IP ON for tasks
- Single desired task per service
- No WAF
- No autoscaling
- No blue/green deployment controller
