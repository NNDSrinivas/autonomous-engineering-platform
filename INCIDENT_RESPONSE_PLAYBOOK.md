# AEP Incident Response Playbook

Last updated: 2026-02-20
Applies to: Staging + Production ECS Fargate environments

---

## Incident Severity Levels

| Level | Definition | Response Time | Examples |
|-------|------------|---------------|----------|
| **P0** | Site down, data loss, security breach | Immediate | All requests 5xx, DB deleted, API keys leaked |
| **P1** | Degraded service, major feature broken | < 15 min | 50% requests slow, auth broken, budget enforcement failing |
| **P2** | Minor degradation, workaround exists | < 1 hour | Single endpoint slow, non-critical cache miss |
| **P3** | Cosmetic issue, no user impact | < 1 day | Typo, non-critical log noise |

---

## General Incident Response Flow

```
Detect → Triage → Mitigate → Root Cause → Resolve → Postmortem
```

1. **Detect**: Alert fires or user report
2. **Triage**: Determine severity (P0-P3)
3. **Mitigate**: Stop the bleeding (rollback, disable feature, scale up)
4. **Root Cause**: Investigate logs, metrics, traces
5. **Resolve**: Permanent fix deployed
6. **Postmortem**: Document what happened, why, and how to prevent recurrence

---

## Incident 1: High 5xx Error Rate

### Symptoms
- ALB 5xx metrics spiking (> 5% of requests)
- Users seeing "Internal Server Error"
- `/health/ready` may or may not be failing

### Decision Tree

```
Is /health/ready failing?
├─ YES → Go to "Unhealthy Targets" section
└─ NO → Continue below
```

### Immediate Actions (< 5 min)

1. **Check recent deployments**:
   ```bash
   aws ecs describe-services \
     --cluster aep-staging \
     --services aep-backend-staging-svc \
     --query 'services[0].deployments'
   ```
   - If deployment in last 30 min → **ROLLBACK** (see DEPLOY_RUNBOOK.md Section 6)

2. **Check backend logs**:
   ```bash
   aws logs tail /ecs/aep-backend-staging --follow --since 10m
   ```
   Look for:
   - Unhandled exceptions
   - "transport closed" (Redis)
   - "connection refused" (DB)
   - "timeout" (external API)

3. **Check ALB access logs** (if enabled):
   - Identify which endpoint is failing
   - Check request pattern (bot attack? spike in traffic?)

### Root Cause Investigation

| Error Pattern | Likely Cause | Fix |
|---------------|--------------|-----|
| `RuntimeError: transport closed` | Redis connection closed | Restart backend tasks to reset Redis pool |
| `sqlalchemy.exc.TimeoutError` | DB connection pool exhausted | Scale up tasks OR investigate slow queries |
| `openai.error.RateLimitError` | OpenAI API rate limit hit | Enable budget enforcement or rate limiting |
| `KeyError` / `AttributeError` | Code bug in new deployment | Rollback immediately |
| Random 502/504 | ALB → task timeout | Check task CPU/memory, scale up if needed |

### Mitigation Options

**Option A: Rollback** (P0/P1, safest)
```bash
aws ecs update-service \
  --cluster aep-staging \
  --service aep-backend-staging-svc \
  --task-definition aep-backend-staging:10  # previous revision
```

**Option B: Restart Tasks** (Redis transport closed)
```bash
aws ecs update-service \
  --cluster aep-staging \
  --service aep-backend-staging-svc \
  --force-new-deployment
```

**Option C: Scale Up** (Resource exhaustion)
```bash
aws ecs update-service \
  --cluster aep-staging \
  --service aep-backend-staging-svc \
  --desired-count 2
```

**Option D: Disable Feature** (New feature causing errors)
- Set feature flag or env var
- Force new deployment to pick up change

---

## Incident 2: Unhealthy Targets (ALB)

### Symptoms
- ALB target health check failing
- No healthy targets available
- All requests return 503 Service Unavailable

### Immediate Actions (< 2 min)

1. **Check target health**:
   ```bash
   aws elbv2 describe-target-health \
     --target-group-arn <backend-tg-arn>
   ```
   - Note: `Reason` field (e.g., "Target.FailedHealthChecks")

2. **Check health endpoint directly**:
   ```bash
   # Get task private IP
   aws ecs list-tasks --cluster aep-staging --service-name aep-backend-staging-svc
   aws ecs describe-tasks --cluster aep-staging --tasks <task-arn>

   # Curl health endpoint from bastion/local (if routable)
   curl http://<task-ip>:8787/health/live
   curl http://<task-ip>:8787/health/ready
   ```

3. **Check task logs**:
   ```bash
   aws logs tail /ecs/aep-backend-staging --follow --since 5m
   ```

### Root Cause Investigation

| Health Check Failure | Likely Cause | Fix |
|----------------------|--------------|-----|
| `/health/live` returns 404 | Wrong health check path in target group | Update target group health check path to `/health/live` |
| `/health/ready` returns 503 | DB or Redis connection failing | Check DB connectivity, Redis connectivity |
| Connection timeout | Security group blocking ALB → task traffic | Verify security group allows ALB SG on port 8787 |
| Task not starting | Image pull error, missing secrets, OOM | Check task logs, verify secrets, check task memory |

### Mitigation Options

**Option A: Fix Health Check Path**
```bash
aws elbv2 modify-target-group \
  --target-group-arn <arn> \
  --health-check-path /health/live
```

**Option B: Restart Tasks** (Stuck Redis/DB connection)
```bash
aws ecs update-service \
  --cluster aep-staging \
  --service aep-backend-staging-svc \
  --force-new-deployment
```

**Option C: Rollback** (New deployment broke health)
- See DEPLOY_RUNBOOK.md Section 6

---

## Incident 3: Redis "Transport Closed" Error

### Symptoms
- `/health/ready` returns 503 with `redis: false`
- Logs show: `RuntimeError: transport closed`
- Intermittent or persistent

### Root Cause

Redis client connection pool closed, tasks trying to reuse dead connections.

### Immediate Fix (< 2 min)

**Option A: Restart Backend Tasks** (Phase 1 fix should self-heal)
```bash
aws ecs update-service \
  --cluster aep-staging \
  --service aep-backend-staging-svc \
  --force-new-deployment
```

**Option B: Verify Redis Lifecycle**

Check that centralized Redis client is being used:
```bash
# Search for non-centralized Redis instantiations
cd backend
grep -r "Redis.from_url" --exclude-dir=services
grep -r "redis.from_url" --exclude-dir=services
```

If found, these are Phase 2 migration candidates (see REDIS_PHASE_2_MIGRATION.md).

### Long-Term Fix

Complete Redis Phase 2 migration:
- All Redis usage through `get_redis()` from `services/redis_client.py`
- No module-level singletons
- Proper lifecycle (init on startup, close on shutdown)

---

## Incident 4: Database Connection Pool Exhausted

### Symptoms
- Requests timeout or return 5xx
- Logs show: `sqlalchemy.exc.TimeoutError: QueuePool limit exceeded`
- `/health/ready` may pass (uses separate connection)

### Immediate Actions (< 5 min)

1. **Check active connections**:
   ```sql
   -- From DB client
   SELECT count(*) FROM pg_stat_activity WHERE datname = 'aep';
   SELECT state, count(*) FROM pg_stat_activity WHERE datname = 'aep' GROUP BY state;
   ```

2. **Check for long-running queries**:
   ```sql
   SELECT pid, now() - query_start AS duration, state, query
   FROM pg_stat_activity
   WHERE state != 'idle'
   ORDER BY duration DESC
   LIMIT 10;
   ```

3. **Check backend pool config**:
   - Look for `pool_size` and `max_overflow` in DB connection string
   - Default: 5 connections per task

### Root Cause Investigation

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Active connections = pool_size × task_count | Normal operation at limit | Scale up tasks OR increase pool_size |
| Many "idle in transaction" | Transactions not committed/rolled back | Fix code to close transactions properly |
| Long-running queries (> 30s) | Slow query or missing index | Optimize query, add index |
| Connections leak (grow over time) | Connection not returned to pool | Fix code to use `with session:` pattern |

### Mitigation Options

**Option A: Scale Up Tasks** (Quick relief)
```bash
aws ecs update-service \
  --cluster aep-staging \
  --service aep-backend-staging-svc \
  --desired-count 2
```

**Option B: Increase Pool Size** (Requires redeploy)

Update `DATABASE_URL` to include pool settings:
```
postgresql://user:pass@host/db?pool_size=10&max_overflow=5
```

Or set in backend code.

**Option C: Kill Long-Running Queries** (Emergency)
```sql
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid = <pid>;
```

---

## Incident 5: Budget Enforcement Failing

### Symptoms
- Users bypassing spend limits
- OpenAI/Anthropic API costs spiking
- Budget warnings not triggering

### Immediate Actions (< 5 min)

1. **Check budget enforcement mode**:
   ```bash
   aws ecs describe-task-definition \
     --task-definition aep-backend-staging:latest \
     --query 'taskDefinition.containerDefinitions[0].environment'

   # Look for BUDGET_ENFORCEMENT_MODE=strict
   ```

2. **Check backend logs for budget rejections**:
   ```bash
   aws logs tail /ecs/aep-backend-staging --follow | grep -i budget
   ```

3. **Check model routing config**:
   - Verify tier limits are correct
   - Verify cost metadata is accurate

### Root Cause Investigation

| Issue | Likely Cause | Fix |
|-------|--------------|-----|
| No budget rejections in logs | Enforcement disabled or bypassed | Verify `BUDGET_ENFORCEMENT_MODE=strict`, check code for bypass logic |
| Rejections logged but requests succeed | Enforcement logic not failing requests | Fix code to return 429 on budget exceeded |
| Wrong tier limits applied | Tier config error | Update tier config, redeploy |
| Costs miscalculated | Wrong model cost metadata | Update cost metadata in model registry |

### Mitigation Options

**Option A: Emergency Rate Limit** (Stop the bleeding)

Add WAF rate limiting rule to ALB:
```bash
# Create rate-limit rule (100 req/5min per IP)
aws wafv2 create-rule-group ...
```

**Option B: Disable Expensive Models** (Temporary)

Update model registry to mark expensive models as unavailable.

**Option C: Enable Strict Enforcement** (If disabled)

Set env var `BUDGET_ENFORCEMENT_MODE=strict` and redeploy.

---

## Incident 6: Complete Site Outage (P0)

### Symptoms
- All requests failing (frontend + backend)
- `/health/live` and `/health/ready` both down

### Immediate Actions (< 1 min)

1. **Check ECS service status**:
   ```bash
   aws ecs describe-services \
     --cluster aep-staging \
     --services aep-backend-staging-svc aep-frontend-staging-svc
   ```

2. **Check ALB status**:
   ```bash
   aws elbv2 describe-load-balancers --names aep-staging-alb
   ```

3. **Check DNS**:
   ```bash
   dig staging.navralabs.com
   nslookup staging.navralabs.com
   ```

### Root Cause Investigation

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| ECS desired count = 0 | Accidental scale-down | Scale up immediately |
| All tasks stopped | OOM, bad deploy, missing secrets | Rollback to previous task definition |
| ALB offline | AWS outage, deleted by accident | Restore from backup or rebuild |
| DNS not resolving | Route53 misconfiguration | Fix Route53 record |
| Security group changed | Accidentally removed ALB ingress | Restore security group rules |

### Mitigation (FASTEST PATH)

**Option A: Rollback** (Most common)
```bash
aws ecs update-service \
  --cluster aep-staging \
  --service aep-backend-staging-svc \
  --task-definition aep-backend-staging:10 \
  --desired-count 1

aws ecs update-service \
  --cluster aep-staging \
  --service aep-frontend-staging-svc \
  --task-definition aep-frontend-staging:1 \
  --desired-count 1
```

**Option B: Force Restart**
```bash
aws ecs update-service \
  --cluster aep-staging \
  --service aep-backend-staging-svc \
  --force-new-deployment \
  --desired-count 1
```

**Option C: Emergency Maintenance Page**

Update ALB default action to return 503 with maintenance message while investigating.

---

## Incident 7: Security Incident (P0)

### Symptoms
- API keys leaked
- Unauthorized access detected
- Data exfiltration suspected

### Immediate Actions (< 5 min)

1. **Rotate all secrets immediately**:
   ```bash
   # Rotate each secret (use file to avoid shell history)
   SECRET_FILE="$(mktemp)"
   chmod 600 "$SECRET_FILE"
   echo -n "new-key" > "$SECRET_FILE"

   aws secretsmanager update-secret \
     --secret-id aep/staging/OPENAI_API_KEY \
     --secret-string "file://$SECRET_FILE"

   rm -f "$SECRET_FILE"

   # Force tasks to restart and pick up new secrets
   aws ecs update-service \
     --cluster aep-staging \
     --service aep-backend-staging-svc \
     --force-new-deployment
   ```

2. **Review recent ALB access logs** (if enabled):
   - Identify suspicious IPs
   - Check for unusual request patterns

3. **Lock down security groups** (if needed):
   ```bash
   # Remove public access temporarily
   aws ec2 revoke-security-group-ingress \
     --group-id <alb-sg> \
     --ip-permissions ...
   ```

4. **Check for unauthorized IAM activity**:
   ```bash
   aws cloudtrail lookup-events \
     --lookup-attributes AttributeKey=Username,AttributeValue=<user> \
     --max-results 50
   ```

### Containment

- Rotate all API keys (OpenAI, Anthropic, DB passwords)
- Review IAM policies for overly permissive access
- Enable CloudTrail if not already enabled
- Enable ALB access logs if not already enabled
- Consider enabling WAF with IP allowlist temporarily

---

## Postmortem Template

After every P0/P1 incident:

```markdown
# Incident Postmortem: [Title]

**Date**: YYYY-MM-DD
**Severity**: P0 / P1
**Duration**: X minutes
**Affected**: Staging / Production

## What Happened

[1-2 paragraph summary]

## Timeline

- HH:MM - Incident detected
- HH:MM - Triage started
- HH:MM - Mitigation deployed
- HH:MM - Service restored
- HH:MM - Root cause identified
- HH:MM - Permanent fix deployed

## Root Cause

[Technical explanation]

## Impact

- Requests affected: X
- Users affected: Y
- Revenue impact: $Z (if applicable)

## What Went Well

- [Detection was fast]
- [Rollback worked]

## What Went Wrong

- [Health checks didn't catch this]
- [Took too long to identify root cause]

## Action Items

- [ ] [Fix X] - Owner: @name - Due: YYYY-MM-DD
- [ ] [Improve monitoring for Y] - Owner: @name - Due: YYYY-MM-DD
- [ ] [Update runbook] - Owner: @name - Due: YYYY-MM-DD
```

---

## Incident Response Contacts

| Role | Contact | Escalation Path |
|------|---------|----------------|
| On-call Engineer | Slack: #oncall | → Engineering Lead |
| Engineering Lead | @lead | → CTO |
| AWS Account Owner | @owner | → AWS Support (Enterprise) |
| Security | @security | → CISO |

---

## Tools Quick Reference

```bash
# ECS service status
aws ecs describe-services --cluster aep-staging --services aep-backend-staging-svc

# Force restart
aws ecs update-service --cluster aep-staging --service aep-backend-staging-svc --force-new-deployment

# Rollback
aws ecs update-service --cluster aep-staging --service aep-backend-staging-svc --task-definition aep-backend-staging:10

# Scale up
aws ecs update-service --cluster aep-staging --service aep-backend-staging-svc --desired-count 2

# Logs
aws logs tail /ecs/aep-backend-staging --follow

# Target health
aws elbv2 describe-target-health --target-group-arn <arn>

# Health check
curl https://staging.navralabs.com/health/ready
```
