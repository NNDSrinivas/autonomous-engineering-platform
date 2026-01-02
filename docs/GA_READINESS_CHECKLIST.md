# NAVI GA Readiness Checklist

This checklist maps the vision in `.github/agents/AEP-AEI VISION.agent.md` to implementation status.

Legend:
- [x] Implemented in code and wired end-to-end (not yet production-validated unless stated)
- [ ] Missing / not fully wired

## Completed (Code-Wired End-to-End)

### Core platform capabilities
- [x] Organizational memory graph API (create/search/query nodes) `backend/api/org_brain.py`
- [x] Memory graph storage models `backend/models/memory_graph.py`

### Jira
- [x] Jira connector auth + storage (API token or OAuth) `backend/api/routers/connectors.py`
- [x] Jira live issue retrieval for user (`/api/integrations/jira/my-issues`) `backend/api/routers/jira_integration.py`
- [x] Jira webhook ingestion to DB + memory graph + cache invalidation `backend/api/routers/jira_webhook.py`
- [x] Jira issue cache + context packet hydration `backend/services/jira.py`, `backend/agent/context_packet.py`

### Slack
- [x] Slack OAuth install + connector storage `backend/api/routers/connectors.py`
- [x] Slack channel sync endpoint + VS Code UI action `backend/api/routers/connectors.py`, `extensions/vscode-aep/src/connectorsPanel.ts`
- [x] Slack webhook ingestion into memory graph `backend/api/routers/slack_webhook.py`
- [x] Slack DM sync + file ingestion (sync) `backend/services/slack_ingestor.py`, `backend/api/routers/connectors.py`
- [x] Governance gating for external write actions (Slack/Jira/GitHub) `backend/agent/closedloop/closed_loop_orchestrator.py`

### GitHub
- [x] GitHub OAuth install + repo list + indexing endpoint `backend/api/routers/connectors.py`
- [x] GitHub webhook registration on indexing `backend/api/routers/connectors.py`
- [x] GitHub repo/issue indexing worker `backend/workers/integrations.py`
- [x] GitHub webhook ingestion into DB + memory graph `backend/api/routers/github_webhook.py`
- [x] GitHub write actions (create PR/merge/create issue) `backend/agent/closedloop/execution_controller.py`, `backend/services/github_write.py`

### GitLab
- [ ] GitLab full lifecycle integration (issues/merge requests/webhooks)
  - CI trigger/status API exists (`/api/gitlab/ci`) but no repo/issue ingestion or webhook registration

### Docs
- [x] Docs webhook ingestion into memory graph `backend/api/routers/docs_webhook.py`
- [x] Deployment runbook (Kubernetes standard) `docs/DEPLOYMENT_RUNBOOK.md`

### Meetings
- [x] Meeting capture + summary + action items pipeline `backend/services/meetings.py`, `backend/workers/queue.py`, `backend/api/main.py`

### Confluence
- [x] Confluence OAuth + sync + webhook subscription `backend/api/routers/connectors.py`
- [x] Confluence page ingestion `backend/services/org_ingestor.py`

### Microsoft Teams
- [x] Teams OAuth + Graph subscription creation `backend/api/routers/connectors.py`
- [x] Teams webhook ingestion into conversation store `backend/api/routers/teams_webhook.py`

### Zoom
- [x] Zoom OAuth + sync endpoint `backend/api/routers/connectors.py`
- [x] Zoom webhook ingestion to memory `backend/api/routers/zoom_webhook.py`

### Google Meet
- [x] Google OAuth + Calendar sync/subscribe `backend/api/routers/connectors.py`
- [x] Meet webhook ingestion to memory `backend/api/routers/meet_webhook.py`
- [x] Meet transcript ingestion (Drive export) `backend/services/meet_ingestor.py`

### Connector UX
- [x] Connectors status API + encrypted secrets `backend/services/connectors.py`, `backend/api/routers/connectors.py`
- [x] VS Code connectors panel list + status wiring `extensions/vscode-aep/media/connectorsPanel.js`, `extensions/vscode-aep/src/connectorsPanel.ts`

### Context Packet
- [x] Context packet hydration from NAVI memory (Slack/Teams/Zoom/Meet/Confluence) `backend/agent/context_packet.py`

## Missing / Not Fully Wired (Vision Gaps)

### Universal Platform Integrations (Remaining Gaps)
- [ ] **Slack** richer write actions (reactions, file posts)
- [ ] **Microsoft Teams** DM ingestion + meeting transcript capture
- [ ] **Confluence** attachment ingestion (files/links referenced from pages)
- [ ] **Zoom** webhook registration automation + meeting chat/shared files ingestion

- [ ] **CI/CD** deep integration
  - Normalize CI events across GitHub Actions/GitLab/Jenkins
  - Link builds/tests to Jira issues + memory graph
  - Add context packet hydration for CI status

### Contextual Awareness & Memory
- [ ] Expand context packet hydration to include attachment payloads (Confluence/Zoom/Slack files)

### Autonomous Execution with Approval
- [ ] Enforce governance/approval checks on all write actions
  - Jira transitions, GitHub merges, Slack posts, deployments
  - Add audit trails and rollback hooks

### Performance & Reliability
- [ ] Define SLOs, add load tests, and baseline latency metrics
- [ ] Background queue scaling & retry policies for all ingestors

### Security & Compliance
- [ ] Secrets management integration (KMS/Secrets Manager)
- [ ] Data retention policies + audit export

### QA & Release
- [ ] Full e2e integration tests (Jira/Slack/Teams/Confluence/GitHub/Zoom/Meet)
- [ ] GA runbooks + operational monitoring playbooks
  - Monitoring and on-call playbooks are still missing

## Current GA Blockers
- No end-to-end tests proving cross-platform workflows
- Missing DM ingestion for Teams
- Deferred: Kubernetes standardization + runbook manifests (to revisit after UI E2E validation)

## Next Steps (Proposed Work Order)
1) Slack richer write actions (reactions, file posts)
2) Teams DM ingestion + meeting transcript capture
3) Confluence attachment ingestion + context packet hydration
4) Zoom webhook registration automation + chat/shared files ingestion
5) CI normalization + end-to-end integration test suite + GA runbooks
