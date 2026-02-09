# NAVI Service Level Objectives (SLOs)

**Last Updated:** February 7, 2026
**Version:** 1.0
**Review Cycle:** Quarterly

---

## Overview

This document defines Service Level Objectives (SLOs) for NAVI's production deployment. SLOs are target values for service level indicators (SLIs) that define the expected performance and reliability of the system.

**SLO Framework:**
- **SLI (Service Level Indicator):** The actual metric being measured
- **SLO (Service Level Objective):** Target value or range for the SLI
- **SLA (Service Level Agreement):** Customer-facing commitment (typically lower than SLO)
- **Error Budget:** Allowed failure rate (100% - SLO%)

---

## SLO Summary Table

| Category | SLI | SLO Target | Error Budget | Measurement Window | Alert Threshold |
|----------|-----|------------|--------------|-----------------------|-----------------|
| **Availability** | Uptime % | 99.5% | 0.5% | 30 days | < 99.5% for 5m |
| **Latency** | P95 Response Time | < 5000ms | N/A | 5 minutes | > 5000ms for 2m |
| **Latency** | P99 Response Time | < 10000ms | N/A | 5 minutes | > 10000ms for 2m |
| **Error Rate** | Failed Requests | < 1% | 1% | 5 minutes | > 1% for 5m |
| **Task Success** | Successful Tasks | ≥ 95% | 5% | 5 minutes | < 95% for 10m |
| **LLM Latency** | P95 LLM Call | < 5000ms | N/A | 5 minutes | > 5000ms for 2m |
| **LLM Error Rate** | Failed LLM Calls | < 1% | 1% | 5 minutes | > 1% for 5m |
| **Cost** | Hourly LLM Spend | < $50/hour | N/A | 1 hour | > $50/hour for 10m |

---

## Detailed SLO Definitions

### 1. Availability SLO

**Objective:** System is available and responding to requests 99.5% of the time

**SLI Definition:**
```promql
# Successful requests / Total requests (excluding 5xx errors caused by client)
sum(rate(http_requests_total{status!~"5.."}[30d]))
/
sum(rate(http_requests_total[30d]))
```

**SLO Target:** ≥ 99.5%

**Error Budget:**
- 0.5% downtime allowed = ~3.6 hours per month
- ~50 minutes per week
- ~7 minutes per day

**Alert Conditions:**
- **Warning:** Availability < 99.7% for 5 minutes
- **Critical:** Availability < 99.5% for 5 minutes

**Exclusions:**
- Planned maintenance (with advance notice)
- Client-side errors (4xx status codes)
- DDoS attacks or external service failures

**Measurement:**
- Window: 30-day rolling window
- Frequency: Continuous (5-minute evaluation)

**Consequences of SLO Violation:**
- **Minor (99.0-99.5%):** Post-mortem required, no feature launches until resolved
- **Major (95-99%):** Executive notification, immediate incident response
- **Severe (<95%):** Customer notification, root cause analysis, prevention plan

---

### 2. Latency SLO (P95)

**Objective:** 95% of requests complete within 5 seconds

**SLI Definition:**
```promql
# P95 latency across all HTTP requests
histogram_quantile(0.95,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
)
```

**SLO Target:** < 5000ms (5 seconds)

**Measurement:**
- Window: 5-minute rolling window
- Frequency: Continuous

**Alert Conditions:**
- **Warning:** P95 latency > 5000ms for 2 minutes
- **Critical:** P95 latency > 10000ms for 2 minutes

**Breakdown by Endpoint:**
| Endpoint | P95 Target | Justification |
|----------|-----------|---------------|
| `/api/navi/chat/autonomous` | < 5000ms | Primary user-facing endpoint |
| `/api/navi/chat/streaming` | < 3000ms | Real-time streaming requires lower latency |
| `/api/feedback/submit` | < 500ms | Simple POST operation |
| `/api/memory/recent` | < 1000ms | Database read operation |
| `/metrics` | < 100ms | Monitoring endpoint should be fast |

**Exclusions:**
- Long-running tasks explicitly marked as async (> 30s expected duration)
- Enterprise mode tasks with unlimited iterations

**Actions on Violation:**
- Identify slow queries in database
- Review LLM API latency
- Check for resource constraints (CPU, memory, I/O)
- Optimize hot paths in code

---

### 3. Latency SLO (P99)

**Objective:** 99% of requests complete within 10 seconds

**SLI Definition:**
```promql
# P99 latency across all HTTP requests
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
)
```

**SLO Target:** < 10000ms (10 seconds)

**Measurement:**
- Window: 5-minute rolling window
- Frequency: Continuous

**Alert Conditions:**
- **Warning:** P99 latency > 10000ms for 2 minutes
- **Critical:** P99 latency > 20000ms for 2 minutes

**Purpose:**
- Ensure tail latency doesn't degrade user experience
- Catch edge cases and outliers
- Prevent worst-case scenarios from affecting users

---

### 4. Error Rate SLO

**Objective:** Less than 1% of requests result in errors

**SLI Definition:**
```promql
# 5xx errors / Total requests
sum(rate(http_requests_total{status=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))
```

**SLO Target:** < 1% error rate

**Error Budget:**
- 1% of requests can fail = ~720 errors per month (at 100K requests/month)
- ~24 errors per day

**Alert Conditions:**
- **Warning:** Error rate > 1% for 5 minutes
- **Critical:** Error rate > 5% for 5 minutes

**Error Classification:**
- **Counted toward SLO:** 500, 502, 503, 504 (server errors)
- **Not counted:** 400, 401, 403, 404, 429 (client errors, rate limits)

**Error Budget Consumption:**
- Track daily error budget consumption
- If budget exhausted: freeze feature launches, focus on reliability

---

### 5. Task Success Rate SLO

**Objective:** 95% of autonomous tasks complete successfully

**SLI Definition:**
```promql
# Successful tasks / Total tasks
sum(rate(aep_task_success_rate[5m]))
```

**SLO Target:** ≥ 95%

**Error Budget:**
- 5% of tasks can fail = ~360 failed tasks per month (at 7200 tasks/month)
- ~12 failed tasks per day

**Alert Conditions:**
- **Warning:** Success rate < 95% for 10 minutes
- **Critical:** Success rate < 90% for 10 minutes

**Breakdown by Complexity:**
| Complexity | Success Rate Target | Justification |
|------------|---------------------|---------------|
| Simple | ≥ 99% | Single-step operations should rarely fail |
| Medium | ≥ 97% | Multi-step tasks have higher failure risk |
| Complex | ≥ 95% | Complex tasks may require multiple attempts |
| Enterprise | ≥ 90% | Very long-running tasks have higher variability |

**Exclusions:**
- User-initiated cancellations
- Tasks that hit human checkpoint gates (not failures)
- Tasks blocked by external service outages (LLM API down)

**Actions on Violation:**
- Review failed task logs
- Identify common failure patterns
- Improve error handling and retry logic
- Update prompts for better LLM guidance

---

### 6. LLM Latency SLO

**Objective:** 95% of LLM API calls complete within 5 seconds

**SLI Definition:**
```promql
# P95 latency for LLM API calls
histogram_quantile(0.95,
  sum(rate(aep_llm_latency_ms_bucket[5m])) by (le)
)
```

**SLO Target:** < 5000ms

**Measurement:**
- Window: 5-minute rolling window
- Frequency: Continuous

**Alert Conditions:**
- **Warning:** P95 LLM latency > 5000ms for 2 minutes
- **Critical:** P95 LLM latency > 10000ms for 2 minutes

**Breakdown by Model:**
| Model | P95 Target | Typical Latency |
|-------|-----------|-----------------|
| Claude Sonnet 4 | < 3000ms | ~1500ms |
| Claude Opus 4 | < 5000ms | ~2500ms |
| Claude Haiku 4 | < 1500ms | ~800ms |
| GPT-4o | < 3000ms | ~1800ms |

**Dependencies:**
- Anthropic API availability and performance
- OpenAI API availability and performance
- Network latency to API endpoints

**Actions on Violation:**
- Switch to faster model tier (Haiku instead of Sonnet)
- Reduce prompt size to decrease processing time
- Implement caching for repeated queries
- Contact LLM provider about performance issues

---

### 7. LLM Error Rate SLO

**Objective:** Less than 1% of LLM API calls fail

**SLI Definition:**
```promql
# Failed LLM calls / Total LLM calls
sum(rate(aep_llm_calls_total{status="error"}[5m]))
/
sum(rate(aep_llm_calls_total[5m]))
```

**SLO Target:** < 1% error rate

**Alert Conditions:**
- **Warning:** LLM error rate > 1% for 5 minutes
- **Critical:** LLM error rate > 5% for 5 minutes

**Error Classification:**
- **Counted:** Network errors, 5xx errors, timeouts
- **Not counted:** Rate limits (429), quota exceeded (402), invalid requests (400)

**Common Error Scenarios:**
- Anthropic/OpenAI API outages
- Network connectivity issues
- Invalid prompts or malformed requests
- Token limit exceeded

**Mitigation Strategies:**
- Implement exponential backoff retry logic
- Fallback to secondary LLM provider
- Cache successful responses
- Circuit breaker pattern for failing endpoints

---

### 8. Cost SLO

**Objective:** LLM costs remain under $50 per hour

**SLI Definition:**
```promql
# Hourly LLM cost
sum(rate(aep_llm_cost_usd_total[1h])) * 3600
```

**SLO Target:** < $50/hour

**Budget:**
- $50/hour = $1,200/day = $36,000/month
- Cost per request: ~$0.50 (at 100 requests/hour)

**Alert Conditions:**
- **Warning:** Hourly cost > $50 for 10 minutes
- **Critical:** Hourly cost > $100 for 10 minutes

**Cost Breakdown (Estimated):**
| Model | Cost per 1K Tokens (Input) | Cost per 1K Tokens (Output) | Avg Cost per Call |
|-------|----------------------------|-----------------------------|--------------------|
| Claude Sonnet 4 | $0.003 | $0.015 | $0.30 |
| Claude Opus 4 | $0.015 | $0.075 | $1.50 |
| Claude Haiku 4 | $0.00025 | $0.00125 | $0.05 |
| GPT-4o | $0.005 | $0.015 | $0.40 |

**Cost Optimization Actions:**
- Switch to cheaper models (Haiku) for simple tasks
- Reduce prompt size (fewer tokens = lower cost)
- Implement aggressive caching
- Rate limit expensive operations
- Review and optimize prompts monthly

---

## SLO Monitoring & Reporting

### Daily Monitoring

**Actions:**
- Check Grafana dashboards for SLO compliance
- Review overnight alerts and incidents
- Identify trends in SLI metrics

**Dashboards:**
- LLM Metrics Dashboard → Latency, Error Rate, Cost
- Task Metrics Dashboard → Success Rate
- Error Tracking Dashboard → Error trends

### Weekly Reporting

**Metrics to Report:**
- SLO compliance percentage for each SLO
- Error budget consumption (% used)
- Number of SLO violations
- Root cause analysis for violations

**Report Template:**
```markdown
# NAVI SLO Report - Week of [Date]

## Summary
- All SLOs Met: Yes/No
- Critical Incidents: 0
- Error Budget Remaining: 85%

## SLO Compliance
| SLO | Target | Actual | Status | Error Budget Used |
|-----|--------|--------|--------|-------------------|
| Availability | 99.5% | 99.8% | ✅ Met | 15% |
| P95 Latency | <5s | 3.2s | ✅ Met | N/A |
| Error Rate | <1% | 0.3% | ✅ Met | 30% |
| Task Success | ≥95% | 97% | ✅ Met | 60% |

## Incidents
- [Date] - P95 latency spike to 7s (2 minutes) - Cause: LLM API slow response

## Actions Taken
- Implemented prompt caching to reduce LLM latency
- Increased timeout for long-running tasks

## Recommendations
- Consider increasing error budget for task success (currently tight)
```

### Monthly Review

**Agenda:**
- Review SLO definitions (are they still appropriate?)
- Analyze long-term trends
- Discuss error budget consumption
- Plan improvements for next month

**Attendees:**
- Engineering team
- Product team
- On-call engineers

**Decisions:**
- Adjust SLO targets if needed
- Allocate engineering resources for reliability improvements
- Plan feature launches based on error budget availability

---

## Error Budget Policy

### What is Error Budget?

Error budget is the amount of unreliability you're willing to tolerate, calculated as:

```
Error Budget = 100% - SLO Target
```

**Example:**
- Availability SLO: 99.5%
- Error Budget: 0.5% = ~3.6 hours downtime per month

### Error Budget Consumption

**Tracking:**
```promql
# Availability error budget consumed (%)
(1 - sum(rate(http_requests_total{status!~"5.."}[30d])) / sum(rate(http_requests_total[30d]))) / 0.005 * 100

# Error rate budget consumed (%)
(sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))) / 0.01 * 100
```

### Error Budget Policies

| Error Budget Remaining | Actions Required |
|------------------------|------------------|
| **> 75%** | Normal operations, proceed with feature launches |
| **50-75%** | Caution - monitor closely, consider slowing feature velocity |
| **25-50%** | Warning - prioritize reliability, slow down feature launches |
| **< 25%** | **Freeze features** - focus 100% on reliability improvements |
| **0%** | **Complete freeze** - no changes except reliability fixes |

### Error Budget Reset

- Error budgets reset **monthly** (30-day rolling window)
- Partial resets allowed after post-mortem completion
- Exceptional circumstances may warrant early reset (executive approval)

---

## SLO Review & Update Process

### Quarterly Review

**Schedule:** First week of each quarter (January, April, July, October)

**Review Checklist:**
- [ ] Are current SLOs being met consistently?
- [ ] Are SLOs too loose (always met with >90% error budget remaining)?
- [ ] Are SLOs too tight (never met or error budget always exhausted)?
- [ ] Have user expectations changed?
- [ ] Have new features impacted SLO feasibility?
- [ ] Do we have enough monitoring coverage?

### SLO Update Approval

**Process:**
1. Engineering proposes SLO changes with justification
2. Product review for customer impact
3. Executive approval for customer-facing changes
4. Update this document and Prometheus alert rules
5. Communicate changes to team and stakeholders

**Change Log:**
- 2026-02-07: Initial SLO definitions v1.0

---

## Incident Response & SLO Violations

### Incident Severity

| Severity | SLO Impact | Response Time | Escalation |
|----------|-----------|---------------|------------|
| **SEV-1 (Critical)** | Multiple SLOs violated, customer impact | 15 minutes | Page on-call + manager |
| **SEV-2 (High)** | Single SLO violated, degraded performance | 1 hour | Page on-call |
| **SEV-3 (Medium)** | SLO at risk, trending toward violation | 4 hours | Notify on-call |
| **SEV-4 (Low)** | Minor issue, no SLO impact | Next business day | Create ticket |

### Post-Incident Review

**Required for:**
- Any SEV-1 or SEV-2 incident
- Any SLO violation lasting > 5 minutes
- Error budget consumption > 10% in single incident

**Post-Mortem Template:**
- Incident timeline
- Root cause analysis (5 Whys)
- Impact assessment (users affected, SLO impact)
- Lessons learned
- Action items to prevent recurrence

---

## SLO Calculation Examples

### Example 1: Availability SLO

**Scenario:** 99.6% uptime over 30 days

**Calculation:**
- Uptime: 99.6%
- Target: 99.5%
- **Result:** ✅ SLO MET (99.6% > 99.5%)
- Error budget used: (0.5% - 0.4%) / 0.5% = 20%
- Error budget remaining: 80%

### Example 2: Latency SLO

**Scenario:** P95 latency = 6200ms

**Calculation:**
- P95: 6200ms
- Target: < 5000ms
- **Result:** ❌ SLO VIOLATED (6200ms > 5000ms)
- Violation duration: 3 minutes
- Action: Critical alert fired, on-call paged

### Example 3: Task Success Rate

**Scenario:** 94.2% task success rate

**Calculation:**
- Success rate: 94.2%
- Target: ≥ 95%
- **Result:** ❌ SLO VIOLATED (94.2% < 95%)
- Error budget used: (5% - 5.8%) / 5% = **116%** (over budget!)
- Action: Freeze features, investigate failures

---

## References

- **Google SRE Book - SLO Chapter:** https://sre.google/sre-book/service-level-objectives/
- **Prometheus Alerting:** https://prometheus.io/docs/alerting/latest/overview/
- **Grafana Dashboards:** [grafana/README.md](../grafana/README.md)
- **NAVI Production Readiness:** [NAVI_PROD_READINESS.md](NAVI_PROD_READINESS.md)
- **On-Call Playbook:** [ONCALL_PLAYBOOK.md](ONCALL_PLAYBOOK.md)

---

**Document Owner:** Engineering Team
**Last Reviewed:** February 7, 2026
**Next Review:** May 1, 2026
**Version:** 1.0
