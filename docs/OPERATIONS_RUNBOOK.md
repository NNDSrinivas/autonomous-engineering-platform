# NAVI Operations Runbook (Enterprise)

## Scope
This runbook defines production operational standards for NAVI: SLOs, alerting, incident response, and rollback verification. It complements `docs/DEPLOYMENT_RUNBOOK.md` (deploy mechanics) and the infra scripts in `scripts/infra/`.

## 1) SLOs (Baseline)
### API Availability
- **Objective:** 99.9% monthly availability for core NAVI API routes.
- **Error budget:** 0.1% per month.
- **Signal:** HTTP 5xx rate / request volume.

### Latency (P95)
- **Objective:** P95 < 2.0s for `/api/navi/*` requests.
- **Signal:** request latency histogram.

### E2E Reliability
- **Objective:** 20/20 consecutive runs pass for `make e2e-gate`.
- **Signal:** CI job `e2e-gate` (main/dispatch).

## 2) Monitoring & Alerts
### Required metrics
- **Requests:** total, 4xx, 5xx.
- **Latency:** P50/P95/P99.
- **Rate limiting:** 429 volume by endpoint.
- **Queue depth (if applicable):** rate-limiter queue depth.
- **DB connections:** pool saturation.

### Dashboards (minimum)
- **API Health:** request volume, 4xx/5xx, P95 latency, rate-limit events.
- **Infra Health:** DB connections, Redis availability, CPU/mem.
- **Workflow Health:** E2E gate status + recent failures.

### Alert rules (baseline thresholds)
- **API availability burn:** 5xx > 2% for 5 minutes.
- **Latency SLO burn:** P95 > 2s for 10 minutes.
- **Rate-limit spike:** 429 > 2% for 10 minutes.
- **DB saturation:** pool usage > 90% for 5 minutes.
- **E2E gate failure:** any failure on `e2e-gate`.

### Required alerts
- **High 5xx rate:** >2% for 5 min.
- **Latency SLO burn:** P95 >2s for 10 min.
- **E2E gate fail:** any failure on `e2e-gate`.
- **DB error spike:** error rate >1% for 5 min.

## 3) Incident Response
### Severity
- **SEV1:** Full outage, data loss, auth failure, corruption.
- **SEV2:** Partial outage, severe latency, critical workflow failure.
- **SEV3:** Degraded experience, recoverable error spike.

### First actions (SEV1/SEV2)
1) Announce incident and open incident channel.
2) Confirm scope: auth, DB, compute, or provider.
3) Check recent deploys and rollback readiness.
4) Apply emergency rollback if SLO burn is critical.

### Evidence capture
- Request IDs from Observability logs.
- Trace IDs for upstream dependency tracking.
- Error codes returned to clients.

## 4) Rollback Verification
Use the deploy scripts to verify and rollback:
- Local: `scripts/infra/rollback_local.sh`
- K8s: `scripts/infra/rollback_k8s.sh`
- AWS/Terraform: `scripts/infra/rollback_aws_terraform.sh`

After rollback:
1) Run health checks (`/health`, `/metrics`).
2) Run `make e2e-smoke`.
3) Confirm error rates return to baseline.

## 5) Log & Trace Hygiene
- Use structured JSON logs only (no debug UI output).
- Redact secrets: tokens, API keys, passwords.
- Include `request_id`, `trace_id`, `org_id`, `user_sub` in all logs.

## 6) On-Call Checklist
Daily:
- Check error rate and latency dashboards.
- Review last `e2e-gate` result.
- Review rate-limit spikes or auth failures.

Weekly:
- Review slow endpoints and top error codes.
- Verify data retention and audit purge jobs.
 
## 7) Production Readiness Exit Criteria
- E2E gate consistently green.
- SLO dashboards live with alerts enabled.
- Incident playbook reviewed and on-call rotation defined.
- Rollback verified in each environment.
