# VS Code Extension MVP - Production Ready

This VS Code extension provides Cline-like capabilities with enterprise intelligence integration.

## Features

### Core UX (Cline Parity)
- **Chat Panel**: Rich conversational interface with message history
- **Plan & Act UI**: Step-by-step approval workflow with visual progress
- **Context Sidebar**: File explorer integration with smart suggestions
- **Terminal Integration**: Execute commands with user approval
- **Git Operations**: Safe commit/push with review gates

### Enterprise Intelligence (AEP Differentiator)
- **Morning Brief**: "Good morning" with Jira tasks and context
- **Task-Centric Flow**: Pick Jira ticket → compile context → explain → code
- **Cross-Source Memory**: Answers with citations from Jira/Confluence/Slack
- **Team Awareness**: Real-time view of teammate activity and availability
- **Predictive Insights**: Sprint velocity, bug likelihood, technical debt

### Security & Governance
- **OAuth Device Flow**: Secure authentication without secrets in extension
- **Permission Gates**: Explicit approval for every action
- **Audit Trail**: Complete history of all autonomous actions
- **Role-Based Access**: Org-level permissions and tenant isolation

## Architecture

```
┌─ VS Code Extension ─────────────────────────┐
│  ┌─ Agent Panel ──────┐  ┌─ Chat Panel ──┐  │
│  │ • Morning Brief    │  │ • Conversation │  │
│  │ • Jira Tasks       │  │ • Message Hist │  │
│  │ • Context Summary  │  │ • Suggestions  │  │
│  │ • Quick Actions    │  │ • File Preview │  │
│  └────────────────────┘  └───────────────┘  │
│  ┌─ Plan & Act Tree ──────────────────────┐  │
│  │ • Step-by-step workflow               │  │
│  │ • Approval checkboxes                 │  │
│  │ • Progress indicators                 │  │
│  │ • Error handling & retry              │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
                     │
                     ▼
            ┌─ AEP Backend APIs ─┐
            │ • /api/ai/chat     │
            │ • /api/auth/oauth  │
            │ • /api/jira/tasks  │
            │ • /api/memory/search │
            │ • /api/plan/execute │
            └───────────────────┘
```

## Development

```bash
# Install dependencies
cd extensions/vscode
npm install

# Build
npm run compile

# Test
npm run test

# Package
vsce package
```

## Configuration

```json
{
  "aep.coreApi": "https://your-aep-backend.com",
  "aep.authFlow": "oauth-device",
  "aep.autoGreeting": true,
  "aep.jiraIntegration": true,
  "aep.confluenceIntegration": true,
  "aep.slackIntegration": true
}
```