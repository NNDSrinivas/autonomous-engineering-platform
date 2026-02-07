# NAVI Production Readiness Plan

This document closes the current production gaps and provides concrete artifacts and checklists. Sections marked `TODO` need real business input, credentials, or customer data.

## 1) ICP (Target Users) and Pain Points

**Confirmed ICP list (from product direction):**
- Individual developers (learning, shipping side projects).
- Startup dev teams.
- Enterprise agencies.
- Fortune 500 companies.

**Pain points NAVI solves (current focus):**
- Slow code review and testing cycles.
- Repetitive fix-and-verify loops.
- Inconsistent project hygiene and command execution.

**Risk:** This ICP list is very broad. For v1 we should select one primary persona to avoid product sprawl.

## 2) Product Positioning

**Current direction:** "Like Codex/Copilot/Claude Code" (broad generalist).

**Recommended v1 positioning (narrow):**
- "Repo-safe engineering agent that runs tests and fixes with verification."
- "A guided autonomous engineer for PRs, tests, and safe command execution."

**Primary differentiation:**
- End‑to‑end workflow (plan → execute → verify → fix).
- Safety approvals + governance.

## 3) Onboarding Flow (First Win in <2 minutes)

**Goal:** First value in a single request, inside the product UI.

**Proposed first-win flow (in-product):**
1. Scan repo (summarize structure, risks, and next steps).
2. Check errors and fix them (safe edits + verification).
3. Run tests or start the app (if requested).

**Status:** Onboarding UI flow added in product (see frontend changes).

## 4) Reliability and Workload Benchmarks

**Benchmarks (already implemented):**
- `scripts/navi_benchmark.py`
- `docs/NAVI_BENCHMARK_SCORECARD.md`

**Next reliability work:**
- Add real workload benchmarks using representative repos and task scripts.
- Track p95 latency per task category.
- Capture duration metrics by task size (small → complex).

**TODO:** Add real workloads + thresholds.

## 5) Security and Compliance

**Artifacts included:**
- Threat model: `docs/THREAT_MODEL.md`
- Pen test plan: `docs/PEN_TEST_PLAN.md`
- SSO guide (OIDC/SAML): `docs/SSO_GUIDE.md`

**Required now: SOC2 + ISO + GDPR; SSO (SAML/OIDC).**

**Audit export:** `/api/audit/export` supports JSON/CSV export for compliance tooling.

**SOC2 readiness checklist (draft):**
- Asset inventory
- Access control policies
- Audit logging review
- Incident response plan
- Vendor risk review

**TODO:** Define compliance owners, vendors, and audit timeline.

## 6) Deployment Proof

**Case study template included:**
- See section "Deployment Case Study Template" below.

**TODO:** Produce at least one real deployment write‑up.

## 7) Pricing and Packaging

**Draft tiers:**
- **Starter:** Limited automation, core tasks.
- **Pro:** Full verification and planning.
- **Team:** Collaboration, governance, usage limits.
- **Enterprise:** SSO, audit exports, on‑prem, SLAs.

**TODO:** Define pricing and usage model.

## 8) Customer Support Loop

**Support playbook:** `docs/SUPPORT_PLAYBOOK.md`

**Draft SLA (placeholder):**
- P1: 4 hours
- P2: 1 business day
- P3: 3 business days

**TODO:** Finalize support tiers.

## 9) Metrics and Dashboards

**Draft KPIs:**
- Activation rate
- Time to first win
- Task success rate
- Error rate per task category
- Benchmark p95 latency

**TODO:** Build dashboards and define thresholds.

## 10) Sales Assets

**Draft assets included:**
- `docs/SALES_ONE_PAGER.md`
- `docs/DEMO_SCRIPT.md`
- `docs/ROI_CALCULATOR.md`

**TODO:** Confirm claims and pricing for the assets.

## 11) Deployment Model (SaaS + Self-Hosted)

**Required:** SaaS and self‑hosted, across AWS, GCP, and Azure.

**Current state:**
- AWS Terraform modules exist in `infra/terraform/aws`.
- Kubernetes manifests in `k8s/`.
- Local docker compose scripts in `scripts/infra/`.
- GCP/Azure infra is not yet implemented (docs will outline required modules).

**Docs:**
- Deployment guide: `docs/DEPLOYMENT_GUIDE.md`
- Staging plan: `docs/STAGING_PLAN.md`

## 12) V1 Scope and Out-of-Scope (Proposed)

**Include in v1:**
- Repo-safe tasks (scan, review, fix, tests, run/start).
- CI-safe operations with audit trail.
- SSO (SAML/OIDC) for enterprise tier.
- SaaS + self-hosted deploy guides.
- Staging + production environment parity.

**Explicitly out of scope for v1:**
- "Any request" generalist autonomy like fully managed app delivery at massive scale.
- Full SOC2/ISO audit completion in <2 days (readiness work only).
- Multi‑cloud infra parity (AWS first, docs for GCP/Azure).

## 13) Timeline Reality Check

**Requested:** First version in 2 days.

**What fits in 2 days:**
- UX cleanup + onboarding UI
- Basic staging environment definition
- Benchmark rerun + scorecard update
- Deployment docs (AWS + k8s + local)

**What does not fit in 2 days:**
- SOC2/ISO certification
- GDPR DPA + legal review
- Full multi-cloud production infra

## 14) Production Hardening Plan (Phased)

**Phase 0 (0–2 days):**
- Onboarding UI in product
- Staging plan + deployment docs
- Benchmarks + nightly CI

**Phase 1 (1–3 weeks):**
- SSO integration (SAML/OIDC)
- Audit log export
- Error budget + SLO dashboards

**Phase 2 (3–6 weeks):**
- SOC2/ISO readiness package
- Multi-cloud parity
- Production case study

---

# Deployment Case Study Template

**Customer:**
**Use case:**
**Repo size:**
**Task:**
**NAVI workflow:**
- Steps taken
- Commands run
- Tests executed

**Outcome:**
- Time saved
- Issues resolved
- Reliability impact

**Quotes:**

---

## Critical Pre-Production Blockers

**Status:** 🔴 **MUST FIX BEFORE PRODUCTION**

The following issues were identified during Copilot code review (PR #64) and must be addressed in the next PR:

### 1. Authentication Context Not Used (CRITICAL)

**Location:** `backend/api/navi.py:7147` - Autonomous task endpoint

**Issue:**
- Endpoint uses `DEV_*` environment variables instead of authenticated request context
- Bypasses authentication layer entirely for user/org context
- Breaks multi-tenancy and org isolation in production
- Security risk: Activity misattribution, unauthorized access

**Impact:**
- ❌ Cannot deploy to production - breaks security model
- ❌ Multi-org deployments will fail
- ❌ Audit trails will be incorrect

**Required Fix:**
- Refactor autonomous task endpoint to pull user/org from auth layer (request.state / dependency injection)
- Only fall back to DEV_* in explicit dev/test mode
- Add validation that authenticated user matches org context
- Update all code paths that derive user_id/org_id from env vars

**Tracking:**
- Issue: To be created in next sprint
- Target: Next PR after PR #64 merge
- Priority: P0 - Blocks production deployment

**Related Code:**
```python
# Current (BROKEN for production):
user_id = os.getenv("DEV_USER_ID", "default_user")
org_id = os.getenv("X_ORG_ID", "default_org")

# Required (production-ready):
user_id = user.user_id  # From authenticated request
org_id = user.org_id    # From authenticated request
```

---

# Go‑Live Checklist (Minimum)

- User onboarding flow complete
- Benchmarks passing nightly
- Security checklist complete
- One real deployment case study
- Pricing published
- Support loop active
- Metrics dashboards live
- ✅ **Critical auth context issue fixed (see above)**
