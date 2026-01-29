# NAVI Production Readiness Status (As of Jan 28, 2026)

## Executive Summary
NAVI is not yet production-ready for enterprise adoption or a formal "prod release." The product has strong scope and UX momentum, but it still lacks the reliability, security controls, and operational maturity required for enterprise deployment and funding due diligence.

## Readiness Rating
- Enterprise production: **Not ready**
- Pilot readiness (friendly teams): **Partial**
- Investor readiness (pre-seed/seed): **Possible with a clear roadmap and traction**

## Top Blockers (Must Fix)
1) Reliability and E2E validation: frequent runtime errors and incomplete end-to-end success criteria.
2) Security posture: missing SSO/JWT rotation, audit logs, and data retention controls.
3) Operational readiness: no SLOs, incident runbooks, or rollback assurances.
4) Deployment consistency: no validated end-to-end infrastructure templates for local/k8s/cloud.

## Release Criteria (Minimum for Production)
- Reliability:
  - 20+ consecutive E2E runs with zero flakes.
  - Deterministic recovery from failed steps.
- Security:
  - SSO/JWT, access isolation, audit logs, retention policies.
  - Documented encryption and data handling posture.
  - Ops note: to enable audit encryption, set `AUDIT_ENCRYPTION_KEY` (Fernet key) and optionally `AUDIT_ENCRYPTION_KEY_ID`.
  - Ops note: to rotate JWT secrets, set `JWT_SECRET` to the new key and `JWT_SECRET_PREVIOUS` to the old one (comma-separated).
- Operations:
  - Monitoring, alerting, SLO dashboards, rollback + incident playbook.
- UX:
  - No debug output; only user-facing features in UI.
  - Clear status and error recovery messaging.

## Current Status by Area
- Reliability: **In progress**
- Security/compliance: **Not ready**
- Ops/observability: **Not ready**
- UI/UX polish: **Improving**
- E2E autonomy: **Not validated**

## Immediate Next Steps (4-8 weeks)
1) Ship a deterministic E2E harness (plan → approve → execute → verify → rollback).
2) Add auth/audit/data retention baseline.
3) Define SLOs + monitoring + incident runbooks.
4) Verify deployments across local/k8s/cloud with IaC templates.

## E2E Harness Commands
- Single run: `make e2e-smoke`
- Gate (20 runs): `make e2e-gate`

## Audit Retention Automation
- Manual purge: `make audit-purge`
- Example cron (daily at 02:15):
  - `15 2 * * * cd /path/to/autonomous-engineering-platform && make audit-purge >> /var/log/aep/audit-purge.log 2>&1`
- Example systemd timer (enterprise-friendly):
  - `/etc/systemd/system/aep-audit-purge.service`
    - `ExecStart=/bin/bash -lc "cd /path/to/autonomous-engineering-platform && make audit-purge"`
  - `/etc/systemd/system/aep-audit-purge.timer`
    - `OnCalendar=*-*-* 02:15:00`
    - `Persistent=true`
  - Enable with:
    - `sudo systemctl daemon-reload`
    - `sudo systemctl enable --now aep-audit-purge.timer`

## SSO/JWT Rotation Runbook (Enterprise)
1) **Prepare rotation**
   - Issue new signing key in IdP/JWT issuer.
   - Set `JWT_SECRET` to the new key.
   - Set `JWT_SECRET_PREVIOUS` to the old key (comma-separated if multiple).
2) **Deploy**
   - Roll out backend with both secrets configured.
   - Keep both secrets active for at least one token TTL window.
3) **Validate**
   - Verify new tokens authenticate.
   - Verify old tokens still authenticate during grace period.
4) **Cutover**
   - Remove old key from `JWT_SECRET_PREVIOUS`.
   - Confirm only new key validates.

## Validation Runs (Latest)
- 2026-01-29: `RUN_INTEGRATION_TESTS=1 NAVI_TEST_URL=http://127.0.0.1:8000 pytest -q tests -m integration` **passed** (97 passed, 335 deselected; warnings only).
  - Backend started with `APP_ENV=test` to enable test auth bypass.
- 2026-01-29: CI integration job updated with 3 test shards, per-shard retry, and a 20-minute timeout guard.
- 2026-01-29: CI now split into lint/unit/integration jobs; added E2E smoke job (`make e2e-smoke`).
- 2026-01-29: E2E smoke job now depends on lint + unit + integration jobs (runs last).
- 2026-01-29: `pytest -q backend/tests` **passed** (116 passed, 2 skipped; warnings only).
- 2026-01-29: `pytest -q tests` **passed** (308 passed, 124 skipped; warnings only).
- 2026-01-29: Prior suite failures have been resolved; `pytest -q tests` now green.
- Prior full-suite timeout/issues have been resolved; current validation runs are green.
- `make e2e-gate` **passed** (20/20).
- `npm run -s build` **passed**.
- `./scripts/check_extension_compile.sh` **passed**.

## Funding Readiness Guidance
- Pre-seed/seed: feasible with a tight story + demos + roadmap.
- Enterprise pilots: only after security + reliability baselines are met.

## UI Production Policy
The production UI must not expose debug or placeholder logs. Only user-facing, purposeful UI is allowed.

## Update Log
- 2026-01-29: Added infra automation scripts (local/k8s/aws) and AWS Terraform templates for deploy/verify/rollback parity.
- 2026-01-29: Added admin security console (JWT rotation, SSO, encryption-at-rest, retention status) at `/admin/security`.
- 2026-01-29: Added `/api/admin/security/status` for security posture snapshot (admin-only).
- 2026-01-29: Added CI E2E smoke job (single-run end-to-end check).
- 2026-01-29: Split CI pipeline into lint + unit + integration jobs to avoid full-suite timeouts.
- 2026-01-29: CI integration job now shards integration tests (3 shards), retries once on failure, and enforces a 20-minute timeout.
- 2026-01-29: UX readiness: inline command cards now point to Activity panel for output; Activity panel keeps “View in chat” links; highlight duration extended for easier cross-panel navigation.
- 2026-01-29: Observability: request context is now injected into structured logs; structlog configured for JSON with redaction.
- 2026-01-29: Added CI E2E gate job (20-run) for main/dispatch flows.
- 2026-01-29: Added enterprise operations runbook with SLOs, alerting, incident response, and rollback verification (`docs/OPERATIONS_RUNBOOK.md`).
- 2026-01-29: Timeline windowing now anchors to root node timestamp (stable timelines for fixtures) and depth increased to 2 hops.
- 2026-01-29: Added deterministic narrative fallback (citations + causality keywords) when LLM is unavailable.
- 2026-01-29: Auto-enable VS Code auth bypass for `APP_ENV=test|ci` unless explicitly configured (integration tests).
- 2026-01-29: Added SaaS router to main API to unblock `/saas/*` endpoints.
- 2026-01-29: Added admin-only audit console in web app (role-gated via `VITE_USER_ROLE` or `aep_user_role` during dev).
- 2026-01-29: Added admin payload endpoint with optional decrypt and retention purge endpoint.
- 2026-01-29: Documented audit encryption config (`AUDIT_ENCRYPTION_KEY`/`AUDIT_ENCRYPTION_KEY_ID`) and JWT rotation (`JWT_SECRET_PREVIOUS`).
- 2026-01-29: Admin audit console now uses JWT access token for role gating + API auth headers.
- 2026-01-29: Decrypt access now supports optional reason + logs an `audit.decrypt` event.
- 2026-01-29: Added scheduled audit purge script at `backend/scripts/purge_audit_logs.py`.
- 2026-01-29: Added `make audit-purge` target + cron example for retention automation.
- 2026-01-29: Added systemd timer example for audit retention automation.
- 2026-01-29: Added README pointer to production readiness/retention guidance.
- 2026-01-29: Admin console now reads role from JWT (via stored access token) and sends Authorization header to audit APIs.
- 2026-01-29: Fixed audit crypto logger import to unblock backend tests.
- 2026-01-29: Validation runs recorded (pytest timeout, e2e-gate pass, frontend build pass, extension compile pass).
- 2026-01-29: Security hardening: removed wildcard CORS headers from streaming endpoints to enforce allowlist-only CORS.
- 2026-01-29: Removed DEBUG-FLOW prints from NAVI chat flow; logging is now structured and debug-level only.
- 2026-01-29: OAuth device flow now supports Redis-backed persistence with TTLs for device codes and access tokens.
- 2026-01-29: Rate limiting hardened: Redis backend required when fallback disabled; 503 returned when backend unavailable.
- 2026-01-29: JWT rotation supported via `JWT_SECRET_PREVIOUS` (comma-separated).
- 2026-01-29: Audit payload encryption + admin decrypt endpoint (`POST /api/audit/{id}/decrypt`) added.
- 2026-01-29: Added deterministic E2E harness runners (`scripts/e2e_smoke.py`, `scripts/e2e_gate.py`) and Makefile targets.
