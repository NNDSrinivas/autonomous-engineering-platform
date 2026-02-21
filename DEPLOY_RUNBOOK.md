# AEP Deployment Runbook

Last updated: 2026-02-21
Applies to: Staging + Production ECS Fargate deployments

---

## 1) Pre-Deploy Checklist

Before starting any deployment:

- [ ] Health check passing on current deployment (`/health/ready` → 200)
- [ ] No active incidents
- [ ] Change approved (PR merged or emergency approved)
- [ ] Rollback plan documented
- [ ] AWS CLI profile set: `export AWS_PROFILE=navra-staging` (or `navra-prod`)

---

## 2) Standard Backend Deployment (ECS)

### Step 2.1 — Build & Push Image

```bash
# Navigate to repo root
cd /path/to/autonomous-engineering-platform

# Set environment
export ENV=staging  # or prod
export AWS_ACCOUNT_ID=625847798833  # staging account
export AWS_REGION=us-east-1
export ECR_REPO=navralabs/aep-backend

# Build for linux/amd64
docker buildx build \
  --platform linux/amd64 \
  -t ${ECR_REPO}:${ENV} \
  -f ./Dockerfile \
  .

# Login to ECR
aws ecr get-login-password --region ${AWS_REGION} \
  | docker login --username AWS --password-stdin \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Tag and push
docker tag ${ECR_REPO}:${ENV} \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${ENV}

docker push \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${ENV}
```

**Record the image digest** (needed for rollback):
```bash
aws ecr describe-images \
  --repository-name ${ECR_REPO} \
  --image-ids imageTag=${ENV} \
  --query 'imageDetails[0].imageDigest' \
  --output text
```

### Step 2.2 — Update Task Definition

**Option A: AWS Console (Staging)**
1. Navigate to ECS → Task Definitions → `aep-backend-staging`
2. Create new revision (JSON)
3. Update image URI to new digest or `:staging` tag
4. **Verify no plaintext secrets** (all should be `valueFrom` Secrets Manager ARNs)
5. Save and note the new revision number (e.g., `:11`)

**Option B: CLI (Production-recommended)**
```bash
# Get current task definition
aws ecs describe-task-definition \
  --task-definition aep-backend-staging \
  --query 'taskDefinition' > task-def.json

# Edit task-def.json: update image URI
# Remove fields: taskDefinitionArn, revision, status, requiresAttributes, compatibilities, registeredAt, registeredBy

# Register new revision
aws ecs register-task-definition \
  --cli-input-json file://task-def.json
```

### Step 2.3 — Deploy to ECS Service

```bash
export CLUSTER=aep-staging
export SERVICE=aep-backend-staging-svc
export TASK_FAMILY=aep-backend-staging
export NEW_REVISION=11  # from step 2.2

# Update service
aws ecs update-service \
  --cluster ${CLUSTER} \
  --service ${SERVICE} \
  --task-definition ${TASK_FAMILY}:${NEW_REVISION} \
  --force-new-deployment

# Wait for deployment to stabilize (max 10 min)
aws ecs wait services-stable \
  --cluster ${CLUSTER} \
  --services ${SERVICE}
```

**Expected output**: Service is stable.

### Step 2.4 — Verify Deployment

```bash
# Check service status
aws ecs describe-services \
  --cluster ${CLUSTER} \
  --services ${SERVICE} \
  --query 'services[0].deployments'

# Expected: 1 deployment with desiredCount = runningCount
```

**Health checks**:
```bash
# Liveness
curl https://staging.navralabs.com/health/live

# Readiness (critical)
curl https://staging.navralabs.com/health/ready

# Expected:
# {
#   "ok": true,
#   "checks": [
#     {"name": "self", "ok": true, "latency_ms": 0, "detail": "ok"},
#     {"name": "db", "ok": true, "latency_ms": 1, "detail": "ok"},
#     {"name": "redis", "ok": true, "latency_ms": 2, "detail": "ok"}
#   ]
# }
```

**ALB Target Health**:
```bash
# Get target group ARN
aws elbv2 describe-target-groups \
  --names aep-staging-tg-backend \
  --query 'TargetGroups[0].TargetGroupArn' \
  --output text

# Check target health
aws elbv2 describe-target-health \
  --target-group-arn <ARN>

# Expected: State = healthy
```

**Logs check**:
```bash
# Get log stream
aws logs tail /ecs/aep-backend-staging --follow

# Watch for:
# ✅ "Application startup complete"
# ✅ No exceptions
# ❌ "transport closed" (Redis issue)
# ❌ "Connection pool exhausted" (DB issue)
```

---

## 3) Standard Frontend Deployment (ECS)

Same process, substitute:
- Repo: `navralabs/aep-frontend`
- Task family: `aep-frontend-staging`
- Service: `aep-frontend-staging-svc`
- Dockerfile: `frontend/Dockerfile`
- Health check: `curl https://staging.navralabs.com/` (expect 200, HTML)

---

## 4) Database Migration Deployment

**Critical**: Migrations must run **before** deploying code that depends on schema changes.

### Step 4.1 — Pre-Migration

```bash
# Backup current schema (production only)
# (Add pg_dump command if available)

# Test migration on staging first (always)
cd backend
alembic upgrade head
```

### Step 4.2 — Deploy Migration to ECS

**Option A: One-off ECS Task** (recommended for prod)
1. Create one-off task using backend task definition
2. Override command: `["alembic", "upgrade", "head"]`
3. Wait for task to complete
4. Check logs for success

**Option B: SSH/Bastion** (if available)
```bash
# From bastion or local with DB access
cd backend
alembic upgrade head
```

### Step 4.3 — Verify Migration

```bash
# Check alembic version
# (requires DB access)
psql $DATABASE_URL -c "SELECT version_num FROM alembic_version;"
```

### Step 4.4 — Deploy Code

Proceed with standard backend deployment (Section 2).

---

## 5) Secrets Rotation Deployment

When rotating secrets (API keys, encryption keys, DB passwords):

### Step 5.1 — Update Secrets Manager

```bash
# Store the new secret in a secure temporary file (avoids shell history)
SECRET_FILE="$(mktemp)"
chmod 600 "$SECRET_FILE"

# Read the new secret securely (not echoed, not stored in shell history)
printf 'Enter new secret value: ' >&2
IFS= read -r -s NEW_SECRET
printf '\n' >&2
printf '%s' "$NEW_SECRET" > "$SECRET_FILE"
unset NEW_SECRET

# Update the secret from the file
aws secretsmanager update-secret \
  --secret-id aep/staging/OPENAI_API_KEY \
  --secret-string "file://$SECRET_FILE"

# Clean up
rm -f "$SECRET_FILE"
```

### Step 5.2 — Force New Deployment

ECS tasks cache secrets. Force restart:

```bash
aws ecs update-service \
  --cluster ${CLUSTER} \
  --service ${SERVICE} \
  --force-new-deployment
```

Tasks will drain and restart with new secrets.

---

## 6) Rollback Procedures

### Rollback Trigger Conditions

Rollback immediately if:
- `/health/ready` returns 503 for > 2 minutes
- 5xx rate > 5% for > 1 minute
- Unhealthy targets > 0 for > 3 minutes
- Critical feature broken (confirmed by smoke test)

### Step 6.1 — Rollback to Previous Task Revision

```bash
# Identify previous working revision (you recorded this, right?)
export PREVIOUS_REVISION=10

# Rollback
aws ecs update-service \
  --cluster ${CLUSTER} \
  --service ${SERVICE} \
  --task-definition ${TASK_FAMILY}:${PREVIOUS_REVISION}

# Wait for stability
aws ecs wait services-stable \
  --cluster ${CLUSTER} \
  --services ${SERVICE}
```

### Step 6.2 — Verify Rollback

```bash
# Health check
curl https://staging.navralabs.com/health/ready

# Check ALB targets
aws elbv2 describe-target-health --target-group-arn <ARN>
```

### Step 6.3 — Rollback Database Migration (Emergency Only)

```bash
# Downgrade by 1 revision
cd backend
alembic downgrade -1

# Or specific revision
alembic downgrade <revision_id>
```

**Warning**: Only rollback migrations if new code is incompatible. Test on staging first.

---

## 7) Production-Specific Considerations

### Blue/Green Deployment (Future)

When CodeDeploy blue/green is enabled:
- Use CodeDeploy console to monitor traffic shift
- Rollback via CodeDeploy (automatic or manual)
- Do NOT use `update-service` during blue/green deploy

### Multi-Region Failover (Future)

If multi-region is configured:
- Update Route53 health checks first
- Deploy to secondary region
- Verify health before promoting
- Shift traffic via Route53 weighted routing

---

## 8) Emergency Procedures

### Emergency Hotfix (No PR)

Only for P0 incidents (site down, data leak, security breach):

1. Make minimal fix locally
2. Build and push image with tag `hotfix-YYYYMMDD-HHMM`
3. Update task definition to hotfix image
4. Deploy via `update-service`
5. Verify fix
6. **Create PR immediately after** to capture change

### Manual Task Stop (Stuck Deployment)

```bash
# List running tasks
aws ecs list-tasks --cluster ${CLUSTER} --service-name ${SERVICE}

# Stop stuck task (forces new task to start)
aws ecs stop-task --cluster ${CLUSTER} --task <task-arn>
```

---

## 9) Deployment Notification Template

Post to Slack/email after every deployment:

```
🚀 Deployment: aep-backend-staging
Revision: :10 → :11
Change: [PR #123] Fix Redis transport closed error
Health: ✅ /health/ready green
Targets: ✅ 1/1 healthy
Rollback: Revision :10 (digest sha256:abc123...)
Deployed by: @username
```

---

## 10) Common Issues & Fixes

### Issue: "Service update blocked" (AWS Console)

**Cause**: Previous deployment still in progress.

**Fix**: Wait for `aws ecs wait services-stable` or stop old tasks manually.

### Issue: "Task failed to start" (CrashLoopBackoff)

**Cause**: Bad image, missing secrets, or port conflict.

**Fix**:
1. Check logs: `aws logs tail /ecs/aep-backend-staging`
2. Verify secrets ARNs in task definition
3. Verify security group allows ALB → task port
4. Rollback to previous revision

### Issue: "Unhealthy targets" (ALB)

**Cause**: Health check endpoint failing or wrong path.

**Fix**:
1. Verify health check path in target group config (should be `/health/live`)
2. Check backend logs for exceptions
3. Verify task has connectivity to DB + Redis

### Issue: "Old tasks not draining"

**Cause**: Long-running requests or sticky sessions.

**Fix**:
1. Wait for deregistration delay (default 300s)
2. If critical, manually stop old tasks
3. Consider reducing deregistration delay for faster deploys

---

## Exit Criteria (Deployment Complete)

- [ ] New task revision running
- [ ] Old tasks drained (0 running)
- [ ] Health checks green (`/health/live` + `/health/ready`)
- [ ] ALB targets healthy (1/1 or N/N)
- [ ] No 5xx errors in ALB metrics (past 5 min)
- [ ] Logs clean (no exceptions)
- [ ] Smoke test passed (key feature works)
- [ ] Deployment notification sent
- [ ] Rollback plan documented in case of regression
