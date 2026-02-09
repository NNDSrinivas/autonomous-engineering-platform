# NAVI On-Call Playbook

**Last Updated:** February 7, 2026
**Version:** 1.0
**On-Call Schedule:** PagerDuty rotation (weekly)

---

## Table of Contents

1. [On-Call Responsibilities](#on-call-responsibilities)
2. [Escalation Procedures](#escalation-procedures)
3. [Alert Response Matrix](#alert-response-matrix)
4. [Common Runbooks](#common-runbooks)
5. [Tools & Access](#tools--access)
6. [Communication Templates](#communication-templates)
7. [Post-Incident Procedures](#post-incident-procedures)

---

## On-Call Responsibilities

### Primary On-Call Engineer

**Responsibilities:**
- Respond to all alerts within SLA (15 minutes for SEV-1, 1 hour for SEV-2)
- Triage and resolve incidents
- Escalate to secondary if needed
- Document all actions in incident ticket
- Conduct post-incident review for SEV-1/SEV-2

**Availability:**
- 24/7 availability during on-call week
- Phone must be charged and with you at all times
- Test PagerDuty at start of shift
- Acknowledge alerts within 5 minutes

### Secondary On-Call Engineer

**Responsibilities:**
- Backup for primary on-call
- Respond if primary doesn't acknowledge within 15 minutes
- Provide second opinion on major decisions
- Assist with complex incidents

### Escalation Contact

**When to Escalate:**
- SEV-1 incident lasting > 30 minutes
- Uncertain about fix approach for critical issue
- Need approval for risky mitigation (e.g., database rollback)
- Customer-facing impact > 1 hour

**Escalation Path:**
1. Engineering Manager
2. VP of Engineering
3. CTO

---

## Escalation Procedures

### Incident Severity Levels

| Severity | Definition | Response Time | Escalation | Examples |
|----------|-----------|---------------|------------|----------|
| **SEV-1** | Service down or critical functionality unavailable | 15 minutes | Page primary + manager | API completely down, database offline, all tasks failing |
| **SEV-2** | Significant degradation, SLO violated | 1 hour | Page primary | P95 latency > 10s, error rate > 5%, task success < 90% |
| **SEV-3** | Minor degradation, SLO at risk | 4 hours | Notify primary (Slack) | P95 latency 5-10s, error rate 1-5%, task success 90-95% |
| **SEV-4** | Cosmetic issue, no user impact | Next business day | Ticket only | Dashboard broken, typo in logs, minor UI glitch |

### SEV-1 Response Procedure

1. **Acknowledge Alert (< 5 minutes)**
   ```bash
   # Acknowledge in PagerDuty
   # Post in Slack #incidents channel
   "SEV-1: [Brief description]. Investigating."
   ```

2. **Initial Assessment (5-10 minutes)**
   - Check Grafana dashboards for scope of impact
   - Review recent deployments (last 2 hours)
   - Check external dependencies (Anthropic API, OpenAI API, database)
   - Determine user impact percentage

3. **Incident Declaration (< 15 minutes)**
   ```bash
   # Create incident ticket
   gh issue create --title "SEV-1: [Description]" \
     --label "incident,sev-1" \
     --body "Impact: [users/features affected]
   Start time: [timestamp]
   Status: Investigating"

   # Update Slack
   "SEV-1: [Description]
   Impact: [X users, Y% traffic]
   ETA for fix: Investigating
   Incident ticket: [link]"
   ```

4. **Escalate if Needed (15-30 minutes)**
   - If no clear fix path → Escalate to manager
   - If database issue → Escalate to DBA
   - If LLM API issue → Check provider status page

5. **Mitigation (ASAP)**
   - Apply immediate mitigation (rollback, failover, circuit breaker)
   - Document all actions in incident ticket
   - Communicate updates every 15 minutes

6. **Resolution & Communication**
   ```bash
   # Slack update
   "SEV-1 RESOLVED: [Description]
   Resolution: [what was done]
   Duration: [X minutes]
   Root cause: [brief explanation]
   Post-mortem: Scheduled for [date]"
   ```

### SEV-2 Response Procedure

1. **Acknowledge** (< 15 minutes)
2. **Assess** (15-30 minutes)
3. **Fix or Escalate** (< 1 hour)
4. **Document** (incident ticket)
5. **Post-Mortem** (if lasted > 30 minutes)

---

## Alert Response Matrix

### Quick Reference

| Alert Name | Severity | First Action | Typical Root Cause |
|------------|----------|-------------|-------------------|
| **HighP95Latency** | SEV-2 | Check LLM API latency | Slow LLM responses, database query |
| **HighErrorRate** | SEV-1 | Check error logs, recent deploys | Code bug, database down, LLM API error |
| **LowTaskSuccessRate** | SEV-2 | Review failed task logs | Prompt issues, tool failures, timeouts |
| **HighLLMCost** | SEV-3 | Check cost breakdown by model | Expensive model usage, runaway tasks |
| **NoMetrics** | SEV-1 | Check if backend is running | Backend crash, metrics endpoint broken |
| **HighLLMLatency** | SEV-2 | Check LLM provider status | Anthropic/OpenAI API slow |
| **HighLLMErrorRate** | SEV-1 | Check LLM provider status | API outage, rate limit, auth failure |
| **LowAvailability** | SEV-1 | Check backend health, deploy history | Deployment issue, resource exhaustion |
| **ErrorBudgetExhausted** | SEV-1 | FEATURE FREEZE - alert leadership | Too many recent incidents |

---

## Common Runbooks

### 1. High Latency (P95 > 5000ms)

**Symptoms:**
- P95 latency alert firing
- Users reporting slow responses
- Grafana showing latency spike

**Investigation:**
1. **Check LLM API latency:**
   ```bash
   # View LLM latency breakdown
   curl http://localhost:8787/metrics | grep aep_llm_latency
   ```

2. **Check database query performance:**
   ```sql
   -- Find slow queries
   SELECT query, mean_exec_time, calls
   FROM pg_stat_statements
   ORDER BY mean_exec_time DESC
   LIMIT 10;
   ```

3. **Check resource usage:**
   ```bash
   # CPU, memory, disk I/O
   top
   free -h
   iostat -x 1
   ```

**Common Fixes:**
- **Slow LLM API:** Switch to faster model (Haiku), reduce prompt size
- **Slow database:** Add indexes, optimize queries
- **High CPU:** Restart backend, scale horizontally

**Rollback Procedure:**
```bash
# If caused by recent deployment
kubectl rollout undo deployment/navi-backend
# Or
git revert HEAD
./deploy.sh
```

---

### 2. High Error Rate (> 1%)

**Symptoms:**
- Error rate alert firing
- 5xx errors in logs
- Users reporting failures

**Investigation:**
1. **Check error logs:**
   ```bash
   # Last 100 errors
   tail -n 100 /var/log/navi/error.log | grep "ERROR"

   # Or from database
   psql -d aep -c "
   SELECT error_type, error_message, COUNT(*)
   FROM error_events
   WHERE created_at > NOW() - INTERVAL '15 minutes'
   GROUP BY error_type, error_message
   ORDER BY COUNT(*) DESC
   LIMIT 10;"
   ```

2. **Check recent deployments:**
   ```bash
   # Last 5 deployments
   kubectl rollout history deployment/navi-backend -n production | tail -5
   ```

3. **Check external dependencies:**
   - Anthropic API status: https://status.anthropic.com
   - OpenAI API status: https://status.openai.com
   - Database connectivity: `psql -h $DB_HOST -U $DB_USER -d aep -c "SELECT 1"`

**Common Fixes:**
- **Code bug:** Rollback to previous version
- **Database down:** Failover to replica, restart database
- **LLM API down:** Switch to backup provider, enable circuit breaker
- **Rate limit:** Reduce request rate, increase quota

**Emergency Mitigation:**
```bash
# Enable circuit breaker for failing endpoint
kubectl set env deployment/navi-backend CIRCUIT_BREAKER_ENABLED=true

# Scale up to handle load
kubectl scale deployment/navi-backend --replicas=10
```

---

### 3. Low Task Success Rate (< 95%)

**Symptoms:**
- Task success rate alert firing
- Users reporting tasks not completing
- Grafana showing increased failures

**Investigation:**
1. **Check failed task logs:**
   ```sql
   SELECT
     task_id,
     error_message,
     iterations_used,
     created_at
   FROM task_metrics
   WHERE success = false
     AND created_at > NOW() - INTERVAL '15 minutes'
   ORDER BY created_at DESC
   LIMIT 20;
   ```

2. **Check common failure patterns:**
   ```bash
   # Group by error message
   psql -d aep -c "
   SELECT
     SUBSTRING(error_message, 1, 100) as error_prefix,
     COUNT(*) as count
   FROM task_metrics
   WHERE success = false
     AND created_at > NOW() - INTERVAL '1 hour'
   GROUP BY error_prefix
   ORDER BY count DESC
   LIMIT 5;"
   ```

3. **Check tool execution failures:**
   ```bash
   # Look for tool errors in logs
   grep "tool_error" /var/log/navi/autonomous_agent.log | tail -20
   ```

**Common Fixes:**
- **Timeout issues:** Increase task timeout, optimize long-running operations
- **Tool failures:** Fix tool implementation, add error handling
- **Prompt issues:** Update prompts to guide model better
- **LLM API errors:** Switch to backup model, reduce complexity

**Hotfix Procedure:**
```bash
# Update prompt to be more explicit
git checkout -b hotfix/improve-prompts
# Edit backend/agent/prompts.py
git commit -m "Fix: Improve task prompts for better success rate"
git push origin hotfix/improve-prompts
# Deploy via CI/CD or manual:
kubectl set image deployment/navi-backend navi-backend=navi:hotfix-prompts
```

---

### 4. High LLM Cost (> $50/hour)

**Symptoms:**
- Cost alert firing
- Grafana showing cost spike
- Finance team reporting high bills

**Investigation:**
1. **Check cost breakdown:**
   ```bash
   # Cost by model (last hour)
   curl http://localhost:8787/metrics | grep aep_llm_cost_usd_total
   ```

2. **Identify expensive tasks:**
   ```sql
   SELECT
     task_id,
     model_name,
     input_tokens + output_tokens as total_tokens,
     cost_usd
   FROM llm_metrics
   WHERE created_at > NOW() - INTERVAL '1 hour'
   ORDER BY cost_usd DESC
   LIMIT 20;
   ```

3. **Check for runaway loops:**
   ```sql
   SELECT
     task_id,
     iterations_used,
     duration_ms
   FROM task_metrics
   WHERE created_at > NOW() - INTERVAL '1 hour'
     AND iterations_used > 20
   ORDER BY iterations_used DESC;
   ```

**Common Fixes:**
- **Expensive model:** Switch to cheaper model (Haiku instead of Opus)
- **Large prompts:** Reduce context size, optimize prompts
- **Runaway tasks:** Add iteration limits, improve termination logic
- **High volume:** Rate limit expensive operations

**Emergency Cost Control:**
```bash
# Switch to cheaper model globally
kubectl set env deployment/navi-backend DEFAULT_MODEL=claude-haiku-4-5

# Reduce max iterations
kubectl set env deployment/navi-backend MAX_ITERATIONS=10

# Enable aggressive rate limiting
kubectl set env deployment/navi-backend RATE_LIMIT_ENABLED=true
```

---

### 5. Database Connection Failures

**Symptoms:**
- Database connection error alerts
- 500 errors mentioning "database"
- Application unable to query/write to database

**Investigation:**
1. **Check database status:**
   ```bash
   # Test connection
   psql -h $DB_HOST -U $DB_USER -d aep -c "SELECT version();"

   # Check connection pool
   psql -h $DB_HOST -U $DB_USER -d aep -c "
   SELECT count(*), state
   FROM pg_stat_activity
   WHERE datname = 'aep'
   GROUP BY state;"
   ```

2. **Check connection pool settings:**
   ```bash
   # Backend connection pool status
   curl http://localhost:8787/health/db
   ```

3. **Check database logs:**
   ```bash
   # On database server
   tail -f /var/log/postgresql/postgresql-15-main.log
   ```

**Common Fixes:**
- **Connection limit exceeded:** Increase `max_connections`, reduce pool size
- **Database down:** Failover to replica, restart database
- **Network issue:** Check firewall rules, DNS resolution
- **Long-running queries:** Kill slow queries, add timeouts

**Failover Procedure:**
```bash
# Promote read replica to primary
aws rds promote-read-replica \
  --db-instance-identifier navi-db-replica-1

# Update backend to point to new primary
kubectl set env deployment/navi-backend \
  DATABASE_URL=postgresql://user:pass@new-primary:5432/aep

# Restart backend
kubectl rollout restart deployment/navi-backend
```

---

### 6. LLM API Outage

**Symptoms:**
- High LLM error rate alerts
- Errors mentioning "Anthropic" or "OpenAI"
- Provider status page showing outage

**Investigation:**
1. **Check provider status:**
   - Anthropic: https://status.anthropic.com
   - OpenAI: https://status.openai.com

2. **Check error messages:**
   ```bash
   grep "LLM_API_ERROR" /var/log/navi/llm_client.log | tail -20
   ```

3. **Check API key validity:**
   ```bash
   # Test API key
   curl https://api.anthropic.com/v1/messages \
     -H "x-api-key: $ANTHROPIC_API_KEY" \
     -H "anthropic-version: 2023-06-01" \
     -H "content-type: application/json" \
     -d '{"model":"claude-3-haiku-20240307","max_tokens":1024,"messages":[{"role":"user","content":"test"}]}'
   ```

**Mitigation:**
- **Partial outage:** Switch to backup provider (Claude ↔ GPT-4)
- **Complete outage:** Enable queue mode, show maintenance message
- **Rate limit:** Reduce request rate, spread across multiple API keys

**Switch to Backup Provider:**
```bash
# Switch to GPT-4 as fallback
kubectl set env deployment/navi-backend \
  FALLBACK_MODEL=gpt-4o \
  FALLBACK_ENABLED=true

# Restart to pick up changes
kubectl rollout restart deployment/navi-backend
```

---

## Tools & Access

### Required Access

**Production Systems:**
- [ ] Kubernetes cluster (kubectl configured)
- [ ] Database (psql access)
- [ ] Grafana (admin or editor role)
- [ ] Prometheus (view access)
- [ ] PagerDuty (on-call schedule configured)
- [ ] Slack (#incidents channel)
- [ ] GitHub (write access for hotfixes)

**Credentials Locations:**
- **Database:** 1Password vault "NAVI Production"
- **API Keys:** AWS Secrets Manager
- **Kubernetes:** `~/.kube/config`
- **SSH:** `~/.ssh/navi-prod.pem`

### Essential Commands

```bash
# Check backend health
curl http://localhost:8787/health

# View logs (last 100 lines)
kubectl logs -n production deployment/navi-backend --tail=100

# Restart backend
kubectl rollout restart deployment/navi-backend -n production

# Scale backend
kubectl scale deployment/navi-backend --replicas=5 -n production

# Check metrics
curl http://localhost:8787/metrics | grep aep_

# Database connection
psql -h $DB_HOST -U $DB_USER -d aep

# View recent deployments
kubectl rollout history deployment/navi-backend -n production

# Rollback deployment
kubectl rollout undo deployment/navi-backend -n production
```

---

## Communication Templates

### SEV-1 Incident Declaration

```
🚨 SEV-1 INCIDENT: [Brief Title]

Impact: [e.g., "API completely down, 100% of users affected"]
Start Time: [2026-02-07 14:35 UTC]
Status: Investigating

Current Actions:
- [Action 1]
- [Action 2]

Next Update: [15 minutes]
Incident Ticket: [GitHub issue link]
On-Call Engineer: @[your-name]
```

### SEV-1 Resolution

```
✅ SEV-1 RESOLVED: [Brief Title]

Duration: [X minutes from start to resolution]
Impact: [users/requests affected]

Root Cause: [Brief explanation]
Resolution: [What was done to fix it]

Post-Mortem: Scheduled for [date/time]
Incident Ticket: [GitHub issue link]
```

### Customer Communication (for public incidents)

```
Subject: [Resolved] NAVI Service Disruption - [Date]

Hello,

We experienced a service disruption today from [start time] to [end time] UTC.

Impact: [Brief description of what didn't work]
Affected Users: [Percentage or number]
Duration: [X minutes]

Root Cause: [Non-technical explanation]
Resolution: [What we did to fix it]
Prevention: [What we're doing to prevent recurrence]

We sincerely apologize for the inconvenience. If you have any questions, please contact support@navi.ai.

Thank you for your patience,
The NAVI Team
```

---

## Post-Incident Procedures

### Post-Mortem Required For

- Any SEV-1 incident
- Any SEV-2 incident lasting > 30 minutes
- Any SLO violation lasting > 5 minutes
- Error budget consumption > 10% in single incident

### Post-Mortem Template

```markdown
# Post-Mortem: [Incident Title]

**Date:** 2026-02-07
**Severity:** SEV-1
**Duration:** 45 minutes
**On-Call:** [Your Name]

## Summary
[2-3 sentence summary of what happened]

## Impact
- Users affected: [number or percentage]
- Requests failed: [number]
- Revenue impact: [$amount if applicable]
- SLO impact: [which SLOs violated]

## Timeline (all times UTC)
- 14:00 - Deployment of v2.3.5
- 14:15 - First error reports
- 14:20 - Alert fired
- 14:22 - On-call acknowledged
- 14:30 - Root cause identified
- 14:40 - Fix deployed
- 14:45 - Service fully restored

## Root Cause
[Detailed explanation using 5 Whys methodology]

## Resolution
[What was done to fix the immediate issue]

## Action Items
1. [ ] [Action 1] - Owner: [Name] - Due: [Date]
2. [ ] [Action 2] - Owner: [Name] - Due: [Date]
3. [ ] [Action 3] - Owner: [Name] - Due: [Date]

## Lessons Learned
- What went well: [e.g., "Fast detection via monitoring"]
- What could be improved: [e.g., "Deploy process needs safety checks"]
- What we'll do differently: [e.g., "Add canary deployments"]

## Prevention
[Long-term changes to prevent recurrence]

## Follow-Up
- Post-mortem review meeting: [Date/Time]
- Attendees: [Names]
- Status: [Open/Closed]
```

---

## On-Call Best Practices

### During Your Shift

1. **Test PagerDuty** at start of shift
2. **Check Grafana** dashboards daily
3. **Review recent deployments** to anticipate issues
4. **Keep laptop charged** and with you
5. **Document everything** in incident tickets
6. **Communicate proactively** with Slack updates

### Handoff Procedure

**At end of your shift:**
1. Slack the next on-call engineer
2. Summarize any ongoing issues
3. Share relevant incident links
4. Note any planned deployments

**At start of your shift:**
1. Read handoff notes
2. Review recent incidents
3. Test PagerDuty
4. Check for upcoming deployments

### Escalation Thresholds

**When to wake up the manager:**
- SEV-1 lasting > 30 minutes
- Database corruption or data loss
- Security incident
- Need approval for risky fix (e.g., database rollback)
- Multiple concurrent SEV-2 incidents

**When NOT to escalate:**
- SEV-3 or SEV-4 incidents
- False alerts
- Issues you can resolve independently

---

## Emergency Contacts

| Role | Name | Phone | Slack | Email |
|------|------|-------|-------|-------|
| **Engineering Manager** | TBD | TBD | TBD | support@Navi.com |
| **VP Engineering** | TBD | TBD | TBD | support@Navi.com |
| **Database Admin** | TBD | TBD | TBD | support@Navi.com |
| **Security Lead** | TBD | TBD | TBD | support@Navi.com |
| **General Support** | NAVI Team | N/A | #navi-support | support@Navi.com |

---

## References

- **SLO Definitions:** [SLO_DEFINITIONS.md](SLO_DEFINITIONS.md)
- **Grafana Dashboards:** [grafana/README.md](../grafana/README.md)
- **Production Readiness:** [NAVI_PROD_READINESS.md](NAVI_PROD_READINESS.md)
- **Prometheus Alerts:** [prometheus/alerts/navi-slos.yaml](../prometheus/alerts/navi-slos.yaml)
- **Deployment Guide:** [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

---

**Document Owner:** Engineering Team
**Last Reviewed:** February 7, 2026
**Next Review:** May 1, 2026
**Version:** 1.0
