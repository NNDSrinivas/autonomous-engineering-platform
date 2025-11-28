# NAVI Context Packet and Planner Loop (v0.1)

Goal: every NAVI answer and action comes from live, stitched context (no hardcoded text), with explicit approvals for writes.

## Context Packet Shape
- `task`: key, title/summary, status, type, epic/sprint linkage, acceptance criteria.
- `owners`: assignee, reporters, reviewers, code owners; includes contact handles.
- `jira`: issue fields + latest comments/transitions + canonical URL.
- `prs`: open/merged PRs, review state, blockers, links.
- `builds/tests`: CI runs, failing tests, logs, coverage, rerun URLs.
- `conversations`: Slack/Teams/Chats threads where task/people are mentioned with message links.
- `meetings`: transcript summaries, decisions, action items, timestamps, recording links.
- `docs`: design/ADR/Confluence/Notion sections with anchors.
- `code_refs`: key files/functions, blame info, recent edits, repo/branch.
- `decisions/risks/actions`: structured decision log and open actions.
- `approvals`: what is required for NAVI to act (comment, transition, PR update, CI rerun).
- `sources`: clickable links for every item above (type + connector + URL + metadata).

## API Surface (to implement incrementally)
- Builder: `backend.agent.context_packet.build_context_packet(task_key, user_id, org_id, db, include_related=True)` → normalized packet + sources.
- REST (future): `GET /api/context/packet/{task_key}` with org/user auth; returns packet for IDE/agent.
- Tool usage: agent tools consume packets and always cite `sources`; approval checks gate any write.

## Retrieval Rules
- Prefer webhook/ingested data; fall back to on-demand API calls when missing.
- Enforce org/user scoping on every connector.
- Always include canonical URLs and timestamps; keep small payload + optional “hydrated” flag for verbose content.
- Cache hot entities; invalidate on webhook events (issue updated, PR comment, new build, Slack thread update).

## Planner/Executor Loop Expectations
- Planner reads a packet and outputs a plan: files/functions to touch, tests to run, external updates (Jira comment/transition, Slack update, PR comment).
- Executor steps are approval-gated; every write logs sources + plan step reference.
- Critic/self-check runs after each code/test/action step and feeds updated packet to the loop.

## Next Steps
1) Land the context packet builder skeleton (this doc + code) and wire into agent tools.
2) Hook Jira read/write + webhook intake; add Slack/Teams/Meet/Docs connectors with message/section links.
3) Expose `GET /api/context/packet/{task_key}` with auth + org scoping.
4) Update planner/executor to require a packet for decisions and to surface approvals inline.
5) Add observability/tests: packet assembly latency, missing-source alerts, connector regression tests.
