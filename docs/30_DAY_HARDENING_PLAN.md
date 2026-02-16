# NAVI 30-Day Hardening Plan

Date window: February 16, 2026 to March 17, 2026
Status: Draft for execution
Primary outcome: move NAVI from late-alpha/early-pilot to controlled enterprise-ready launch candidate

## 1) Mission Alignment

NAVI is not a basic SaaS chat assistant. It is an engineering operating system for:
- Organizations: governed autonomy across repos, tools, and workflows.
- Individuals/startups: high-leverage autonomous execution with safe defaults.

This plan prioritizes controls needed for both missions without compromising speed:
- Safe autonomy by default.
- Observable and debuggable operations.
- Policy-first governance before broad rollout.

## 2) Current Reality (As of February 15, 2026)

Current maturity: late alpha / early pilot.

What is strong:
- Distributed jobs, resume/reattach patterns, and cancellation behavior.
- Broad connector and tool surface.
- Significant backend test coverage and CI foundation.

What blocks broad GA:
- Tool sandbox and policy boundaries are incomplete.
- Security hardening is incomplete (SSO/JWT/token-at-rest concerns).
- Tenant isolation model is not fully formalized and verified.
- Observability and SLO-based operations are not fully wired.
- Frontend/extension quality gates are not consistently enforced.

## 3) Strategy Decision

Recommended path: Enterprise-first hardening with controlled pilot continuation.

Execution policy:
- Continue pilot with limited design partners.
- Block broad go-live until all P0 exit criteria pass.
- Treat governance and safety controls as product features, not infra backlog.

## 4) Workstreams and Exit Criteria

## Workstream 0: Tool Sandbox + Policy Layer (P0)
Owner: Platform Security + Agent Runtime
Dates: February 16 to February 27, 2026

Scope:
- Implement command allowlist and denylist controls for command execution tools.
- Enforce workspace and directory confinement for file/system tools.
- Add per-tool resource limits (CPU, memory, timeout, output size, concurrency).
- Add secrets redaction pipeline for logs, events, traces, and UI payloads.
- Implement policy evaluation before every tool call (read, write, exec, connector actions).
- Add role-based tool permissions (viewer, contributor, maintainer, admin).

Exit criteria:
- Arbitrary destructive command execution is blocked by default.
- Every tool invocation has a policy decision record.
- Redaction tests prove secrets are not emitted in logs/events.
- Security regression tests cover bypass and prompt-injection abuse cases.

## Workstream 1: Core Security Hardening (P0)
Owner: Backend Lead + Security Lead
Dates: February 16 to February 28, 2026

Scope:
- Fix SSO token verification path in `/Users/mounikakapa/dev/autonomous-engineering-platform/backend/api/routers/sso.py`.
- Encrypt integration/provider tokens at rest and rotate existing stored secrets.
- Enforce secure production auth defaults in `/Users/mounikakapa/dev/autonomous-engineering-platform/backend/core/settings.py`.
- Add webhook signature, replay, and auth negative-case tests.
- Update threat model from draft to scored remediation plan.

Exit criteria:
- No known auth bypass path in manual review and automated tests.
- Secrets at rest are encrypted and key-rotation procedure is documented.
- Security suite is mandatory and green in CI on main branch.

## Workstream 2: Tenant Isolation + Data Boundaries (P0)
Owner: Platform Lead + Data Lead
Dates: February 20 to March 3, 2026

Scope:
- Define and implement tenant isolation contract across API, jobs, cache, storage, and memory graph.
- Partition Redis keys and job queues by tenant namespace.
- Enforce tenant-scoped retrieval for memory/context/connectors.
- Validate encryption and access boundaries for audit and event data.
- Add integration tests for cross-tenant access attempts.

Exit criteria:
- Cross-tenant access tests fail closed and pass in CI.
- Queue/cache namespaces are tenant-partitioned and documented.
- Data handling and retention boundaries are explicitly documented.

## Workstream 3: Observability + SLO Operations (P0)
Owner: SRE + Platform Lead
Dates: February 24 to March 7, 2026

Scope:
- Complete telemetry wiring in `/Users/mounikakapa/dev/autonomous-engineering-platform/backend/api/routers/telemetry.py` and related services.
- Define SLOs for API latency, tool success rate, job completion, and policy denial behavior.
- Add dashboards and alerts for queue lag, worker health, error budget burn, and connector failures.
- Run load and soak tests with representative autonomous workloads.

Exit criteria:
- Dashboards and alerts are live and validated with test incidents.
- 7-day staging soak has no unresolved Sev-1/Sev-2 issues.
- On-call runbook is complete and used in at least one drill.

## Workstream 4: Quality Gates + Release Hygiene (P1)
Owner: QA Lead + Frontend Lead + Eng Manager
Dates: March 3 to March 12, 2026

Scope:
- Fix extension linting/tooling gaps and enforce lint/type/test gates.
- Add meaningful frontend and extension tests for critical user paths.
- Remove duplicate artifact files and add checks to prevent reintroduction.
- Reconcile readiness documentation into one source of truth.

Exit criteria:
- CI blocks merges on required checks (backend, frontend, extension, security).
- Release candidate passes E2E gate two consecutive runs.
- Single readiness document is authoritative and current.

## Workstream 5: Competitive Proof Pack (P1)
Owner: Product + Developer Experience
Dates: March 10 to March 17, 2026

Scope:
- Run repeatable benchmark tasks against top alternatives on real engineering workflows.
- Publish measurable outcomes: time-to-merge, autonomous completion rate, governance overhead, failure recovery time.
- Build launch messaging grounded in measured strengths, not model hype.

Exit criteria:
- Benchmark methodology and data are reproducible.
- Claims are mapped to evidence artifacts.
- Sales/demo one-pager reflects actual platform behavior.

## 5) Weekly Cadence and Milestones

Week 1 (February 16 to February 22):
- Start Workstream 0 and Workstream 1.
- Finalize policy model and security test harness.
- Ship first pass of command/file sandbox constraints.

Week 2 (February 23 to March 1):
- Finish Workstream 1.
- Continue Workstream 0 hardening and start Workstream 2.
- Begin telemetry and SLO implementation.

Week 3 (March 2 to March 8):
- Complete Workstream 2.
- Complete Workstream 3 dashboards, alerts, and soak setup.
- Start Workstream 4 CI gate tightening.

Week 4 (March 9 to March 17):
- Complete Workstream 4 and Workstream 5.
- Run final readiness review and go/no-go decision.

## 6) Go/No-Go Gate (March 17, 2026)

Broad rollout is allowed only if all are true:
- Workstream 0 exit criteria are fully complete.
- Workstream 1 exit criteria are fully complete.
- Workstream 2 exit criteria are fully complete.
- Workstream 3 exit criteria are fully complete.
- Required CI gates are enforced on main.
- Rollback and incident drills are completed.

If any P0 exit criterion is incomplete:
- Continue controlled pilot only.
- No broad org onboarding.
- No enterprise SLA commitments.

## 7) Enterprise-Readiness Decision Tree

Use this decision rule at launch review:

1. Is tool policy enforcement mandatory and auditable for every tool call?
- If no: not enterprise ready.

2. Can one tenant access any data, logs, or job outputs of another tenant?
- If yes: not enterprise ready.

3. Are secrets guaranteed to be redacted from logs/events/UI traces?
- If no: not enterprise ready.

4. Are SLOs monitored with active alerts and on-call ownership?
- If no: not enterprise ready.

5. Can the team recover from production incidents using tested runbooks?
- If no: not enterprise ready.

If all five answers pass, proceed with limited enterprise onboarding.

## 8) First 10 Paying Orgs Onboarding Guardrails

Only onboard new paying organizations when:
- Contractual scope excludes regulated workloads until compliance controls are complete.
- Tenant-by-tenant policy templates are pre-configured before first run.
- Pilot success criteria are agreed in writing (workflows, KPIs, acceptance bar).
- Incident communication and rollback contacts are defined for each customer.

## 9) Tracking Template

For each workstream, track daily:
- Planned today
- Done today
- Risks/blockers
- Decision needed
- Exit criteria progress (% and evidence links)

