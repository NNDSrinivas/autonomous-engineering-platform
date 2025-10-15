#!/usr/bin/env bash
set -euo pipefail

# ===== CONFIG =====
OWNER="NNDSrinivas"
PROJECT_NUMBER=2
REPO="${REPO:-NNDSrinivas/autonomous-engineering-platform}"  # Can override via environment variable

# Project field names must match exactly what you shared:
FIELD_STATUS="Status"            # ProjectV2SingleSelectField
FIELD_PRIORITY="Priority"        # ProjectV2SingleSelectField
FIELD_ITERATION="Iteration"      # ProjectV2IterationField (optional)

# Desired values (must exist in your project)
STATUS_BACKLOG="Backlog"
STATUS_READY="Ready"
STATUS_INPROGRESS="In progress"
STATUS_INREVIEW="In review"
STATUS_DONE="Done"

PRIORITY_P0="P0"
PRIORITY_P1="P1"

# Iteration to apply (optional). If not present, script will skip setting it.
ITERATION_NAME="Current iteration"

# Set to "echo" for dry-run preview (no changes applied).
DRY=""

# ===== HELPERS =====

need() { command -v "$1" >/dev/null 2>&1 || { echo "❌ Missing $1. Please install it."; exit 1; }; }
need gh
need jq

# Verify we can access the project
echo "🔎 Checking project fields for $OWNER/$PROJECT_NUMBER ..."
gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" >/dev/null

# Try to detect iteration availability
ITERATION_AVAILABLE="false"
iteration_list_output=$(gh project iteration-list "$PROJECT_NUMBER" --owner "$OWNER" 2>/dev/null || true)
if [[ -n "$iteration_list_output" ]]; then
  if echo "$iteration_list_output" | grep -q "^$ITERATION_NAME$"; then
    ITERATION_AVAILABLE="true"
    echo "🗓️  Iteration '$ITERATION_NAME' detected; will assign it."
  else
    echo "ℹ️ Iteration '$ITERATION_NAME' not found; skipping iteration assignment."
  fi
else
  echo "ℹ️ Iterations not enabled on this project; skipping iteration assignment."
fi

create_and_add () {
  local title="$1"
  local body="$2"
  local labels_csv="$3"
  local status="$4"
  local priority="$5"

  # 1) Create GitHub Issue
  local out
  out=$($DRY gh issue create -R "$REPO" -t "$title" -b "$body" -l "$labels_csv" --json url,number)
  local url number
  url=$(echo "$out" | jq -r '.url')
  number=$(echo "$out" | jq -r '.number')

  echo "• #$number created: $title"

  # 2) Add to Project
  $DRY gh project item-add --owner "$OWNER" --number "$PROJECT_NUMBER" --url "$url" >/dev/null
  echo "  ↳ added to project #$PROJECT_NUMBER"

  # 3) Set Status & Priority fields
  $DRY gh project item-edit --owner "$OWNER" --number "$PROJECT_NUMBER" --url "$url" --field "${FIELD_STATUS}=${status}" >/dev/null || \
    echo "  ! could not set ${FIELD_STATUS}='${status}' (check field option names)"
  $DRY gh project item-edit --owner "$OWNER" --number "$PROJECT_NUMBER" --url "$url" --field "${FIELD_PRIORITY}=${priority}" >/dev/null || \
    echo "  ! could not set ${FIELD_PRIORITY}='${priority}' (check field option names)"

  # 4) Optional: set Iteration (if available)
  if [[ "$ITERATION_AVAILABLE" == "true" ]]; then
    $DRY gh project item-edit --owner "$OWNER" --number "$PROJECT_NUMBER" --url "$url" --field "${FIELD_ITERATION}=${ITERATION_NAME}" >/dev/null || \
      echo "  ! could not set ${FIELD_ITERATION}='${ITERATION_NAME}' (check iteration name)"
  fi
}

echo "🚀 Creating issues in $REPO and organizing them on Project $OWNER/$PROJECT_NUMBER ..."

# ===== SPRINT 1 (Ready / P0) =====
create_and_add \
  "A1: OIDC SSO (Okta/Azure AD) with JWT rotation" \
  "Implement OIDC login with Okta or Azure AD. Map claims→roles. Mint/rotate JWT; add auth middleware and protect /api/* (toggle public dev routes via env). Include logout and token invalidation." \
  "epic,security,P0,backend" \
  "$STATUS_READY" "$PRIORITY_P0"

create_and_add \
  "A2: RBAC + org_id scoping middleware" \
  "Add org/project/role model (owner/admin/member/auditor). Enforce org_id scoping in a central DB access layer. Add unit tests proving cross-tenant isolation." \
  "epic,security,P0,backend" \
  "$STATUS_READY" "$PRIORITY_P0"

create_and_add \
  "B1: JIRA OAuth 3LO + refresh" \
  "Replace raw token input with proper JIRA 3LO OAuth. Persist encrypted refresh token; auto-refresh access tokens. Update /connect to show connection state and scopes." \
  "epic,integration,P0,backend" \
  "$STATUS_READY" "$PRIORITY_P0"

create_and_add \
  "B2: GitHub OAuth/App install (least-privilege)" \
  "Support GitHub OAuth or App installation with minimal scopes. Persist installation id and token rotation. Update /connect and /index flows; add health checks." \
  "epic,integration,P0,backend" \
  "$STATUS_READY" "$PRIORITY_P0"

create_and_add \
  "C1: Answer Coach v2 — retrieval reranker" \
  "Implement hybrid BM25+embeddings reranker over meetings/JIRA/GitHub. Keep context ≤2k tokens; return ranked bundle with reason codes for transparency." \
  "epic,P0,backend" \
  "$STATUS_READY" "$PRIORITY_P0"

create_and_add \
  "C2: Answer Coach v2 — small LLM draft + JSON schema validation" \
  "Use a fast LLM to draft ≤2-sentence answers. Enforce JSON schema {answer, citations[], confidence}. Reject unverifiable claims; require citation per claim." \
  "epic,P0,backend" \
  "$STATUS_READY" "$PRIORITY_P0"

# ===== SPRINT 2 (Backlog / P1) =====
create_and_add \
  "C3: Hallucination guardrails + citation validator" \
  "Add a validator to check each claim is backed by a citation (meeting/JIRA/GitHub). On failure, fall back to a conservative, caveated response." \
  "epic,P1,backend" \
  "$STATUS_BACKLOG" "$PRIORITY_P1"

create_and_add \
  "C4: Latency budget + graceful fallbacks" \
  "Enforce ≤3s P95 end-to-end. Add fast-path (meeting-only) answers if retrieval is slow. Emit confidence and reason codes in payload." \
  "epic,P1,backend" \
  "$STATUS_BACKLOG" "$PRIORITY_P1"

create_and_add \
  "D1: Web app shell (Next.js) + auth handoff" \
  "Next.js app with OIDC login, session, and base layout. Org switcher, nav to Meetings/JIRA/GitHub/Answer Coach. Wire to APIs." \
  "epic,ui,P1" \
  "$STATUS_BACKLOG" "$PRIORITY_P1"

create_and_add \
  "D2: Meetings UI — list/detail + actions" \
  "UI for meeting list and detail pages showing summary/decisions/risks/actions and transcript timeline. Connect to /api endpoints." \
  "epic,ui,P1" \
  "$STATUS_BACKLOG" "$PRIORITY_P1"

create_and_add \
  "H1: Dockerfiles per service + multi-stage builds" \
  "Add Dockerfiles for core, realtime, workers with slim Python base, non-root user, multi-stage build, healthcheck. Compose profiles for local/prod." \
  "epic,platform,P1" \
  "$STATUS_BACKLOG" "$PRIORITY_P1"

create_and_add \
  "H3: CI hardening (matrix, CodeQL, Trivy)" \
  "Expand CI to Python 3.11/3.12/3.13 matrix. Add GitHub CodeQL scan and Trivy container scan; block on critical findings." \
  "epic,platform,P1" \
  "$STATUS_BACKLOG" "$PRIORITY_P1"

echo "✅ Done. Review your board at: https://github.com/users/${OWNER}/projects/${PROJECT_NUMBER}"
