# AEP Agent – VS Code Extension (Preview)

This is the MVP IDE agent for AEP. It provides:
- Agent sidebar (greeting + assigned Jira issues)
- Plan & Act approvals with patch preview
- Device-code sign-in against your AEP backend

## Quick start
1. `cd extensions/vscode-aep && npm i`
2. Set VS Code settings:
   - `aep.baseUrl`: `http://localhost:8000`
   - `aep.orgId`: `org-dev`
3. Press F5 to run the extension in a new VS Code window.
4. Run **AEP: Sign In**, then **AEP: Start Agent Session**.

## Backend endpoints expected
- `POST /oauth/device/start` → `{ device_code, user_code, verification_uri, verification_uri_complete?, interval }`
- `POST /oauth/device/poll`  → `{ access_token, expires_in }`
- `GET  /api/integrations/jira/my-issues` → `JiraIssue[]`
- `POST /api/agent/propose` (body: `{ issue_key }`) → `ProposedStep[]`
- `POST /api/ai/apply-patch` (body: `{ diff, dry_run }`) → `{ applied, output }`

You can stub these in dev if not ready.