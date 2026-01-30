# NAVI Competitive Plan (Codex/Cline/Copilot/Claude/KiloCode Parity + Beyond)

## Purpose
Deliver a concrete plan to close gaps vs. leading coding assistants and exceed them with enterprise-grade reliability, speed, and end-to-end autonomy.

## North-Star Outcomes
- Consistent end-to-end task completion with approval gating.
- Reliable streaming UX with low latency and clear action tracing.
- Enterprise-ready deployment, security, and auditability.
- Tooling breadth without sacrificing stability or clarity.

## Current Snapshot (As of Jan 28, 2026)
- Strength: Platform scope (policy, approval flow, orchestration, multi-tool).
- Gap: Reliability, infra automation, enterprise ops, and E2E validation.
- Production readiness details: see `docs/NAVI_PROD_READINESS.md`.

## Competitive Gaps (Summary)
1. Reliability: deterministic execution + robust recovery.
2. Latency: faster step updates and predictable response times.
3. UX/Trust: stable, uncluttered execution trace and approvals.
4. Enterprise readiness: auth, audit, retention, compliance posture.
5. Ecosystem depth: CI/CD, PRs, Jira/Slack/Confluence, cloud deploy.

## Phase Plan

### Phase 0: Baseline Quality Bar (2-3 weeks)
Goal: eliminate brittle behavior and establish consistent E2E testing.
- Implement deterministic E2E harness: plan -> approve -> apply -> verify.
- Add minimum validation contract for each plan (lint/test/build).
- Capture telemetry for execution errors, retries, and step timings.

Acceptance criteria:
- 20 consecutive E2E runs with zero flakes.
- Every plan declares required checks; failures trigger remediation loop.

### Phase 1: Reliability + Speed (4-6 weeks)
Goal: match Codex/Cline-level stability and speed in editor.
- Unified streaming for actions, commands, and file edits.
- Retry/rollback policies with clear user-facing status.
- Context caching and faster prefetching for large repos.

Acceptance criteria:
- Median step update < 2s, plan response < 6s.
- No silent tool failures (all failures are surfaced with next action).

### Phase 2: Agent Intelligence Parity (6-8 weeks)
Goal: improve autonomy and root-cause repair.
- Stronger task decomposition for multi-service work.
- Codebase-aware edit strategy (file targeting + minimal diffs).
- Self-healing runbook and failure classification.

Acceptance criteria:
- 80%+ of build failures auto-diagnosed with a concrete fix plan.
- No regressions in existing user flows.

### Phase 3: Enterprise Readiness (8-12 weeks)
Goal: enterprise adoption readiness.
- SSO + JWT rotation + org-level audit logs.
- Policy enforcement and approval gating by default.
- Data retention controls and encryption posture.

Acceptance criteria:
- Security checklist completed (SOC2-ready controls).
- External pilot with at least 2 teams.

### Phase 4: Ecosystem Depth (ongoing)
Goal: match or exceed tool integration breadth.
- CI/CD: pipeline summary, auto-fix integration.
- Jira/Slack/Confluence: task context and decision capture.
- Cloud deploy templates + rollback workflows.

Acceptance criteria:
- Full build/PR flow supported end-to-end for at least one repo.

## E2E "10M Users/Min E-commerce" Scenario Gaps
- No IaC templates for cloud + k8s + local parity.
- No load-test harness or autoscaling validation.
- No automated DB configuration + DR plan.
- No deploy -> verify -> rollback pipeline.

## Execution Checklist (Short-Term)
- Add command output previews in ActivityPanel (done).
- Ensure streaming events update ActivityPanel (done).
- Add extension TS compile check script (done).
- Add V2 approval flow onboarding doc (done).
- Add E2E test harness (done: `scripts/smoke_navi_v2_e2e.py`).

## Owner/Trackers
- Core reliability: Backend + extension execution stream
- UX/streaming: Webview + VS Code extension
- Enterprise readiness: Backend policy/auth + ops
- Ecosystem: Integrations team

## Update Log
- 2026-01-27: Initial plan created.
- 2026-01-27: Extension compile check reported successful after workspace-level install (user confirmation).
- 2026-01-28: Added production readiness assessment in `docs/NAVI_PROD_READINESS.md`.
- 2026-01-27: Added V2 plan -> approve -> apply E2E smoke test and ran it locally (pass).
- 2026-01-27: Documented dev-only CORS quick fix for VS Code webview testing; prod remains strict allowlist + auth.
