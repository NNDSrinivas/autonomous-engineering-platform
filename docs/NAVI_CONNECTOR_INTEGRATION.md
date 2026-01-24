# NAVI Connector Integration Guide

This document explains how NAVI integrates with third-party applications and connectors, enabling intelligent context-aware responses across your entire development ecosystem.

## Overview

When users connect third-party apps to NAVI, the platform establishes secure OAuth connections and begins ingesting data into a unified memory system. This allows NAVI to:

1. **Understand Context** - Pull relevant information from connected services when answering questions
2. **Perform Actions** - Execute operations across connected platforms with user approval
3. **Stay Updated** - Receive real-time updates via webhooks from connected services
4. **Build Intelligence** - Learn from patterns across all connected data sources

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        NAVI Connector Architecture                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                 │
│   │   GitHub     │    │    Jira      │    │   Slack      │                 │
│   │   GitLab     │    │   Linear     │    │   Teams      │                 │
│   │   Bitbucket  │    │   Asana      │    │   Discord    │   ... 250+     │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                 │
│          │                   │                   │                          │
│          ▼                   ▼                   ▼                          │
│   ┌─────────────────────────────────────────────────────────────────┐      │
│   │                    OAuth Connection Layer                        │      │
│   │   • Secure token storage (encrypted)                            │      │
│   │   • Token refresh handling                                       │      │
│   │   • Scoped permissions per connector                             │      │
│   └─────────────────────────────────────────────────────────────────┘      │
│                                    │                                        │
│                                    ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────┐      │
│   │                     Data Ingestion Layer                         │      │
│   │   • Initial sync on connection                                   │      │
│   │   • Webhook listeners for real-time updates                      │      │
│   │   • Incremental sync for large datasets                          │      │
│   └─────────────────────────────────────────────────────────────────┘      │
│                                    │                                        │
│                                    ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────┐      │
│   │                   Unified Memory System                          │      │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │      │
│   │   │  navi_      │  │  memory_    │  │ conversation│            │      │
│   │   │  memory     │  │  node       │  │ _message    │            │      │
│   │   └─────────────┘  └─────────────┘  └─────────────┘            │      │
│   └─────────────────────────────────────────────────────────────────┘      │
│                                    │                                        │
│                                    ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────┐      │
│   │                    Context Packet Builder                        │      │
│   │   • Aggregates data from all connected sources                   │      │
│   │   • Scopes by user/org permissions                               │      │
│   │   • Provides source citations for all context                    │      │
│   └─────────────────────────────────────────────────────────────────┘      │
│                                    │                                        │
│                                    ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────┐      │
│   │                      NAVI Intelligence                           │      │
│   │   • Contextual responses with source links                       │      │
│   │   • Cross-platform action execution                              │      │
│   │   • Approval-gated operations                                    │      │
│   └─────────────────────────────────────────────────────────────────┘      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Connection Flow

### 1. User Initiates Connection

When a user clicks "Connect" on a connector in the VSCode extension:

```
User clicks "Connect GitHub"
        │
        ▼
┌─────────────────────────────────┐
│  VSCode Extension calls:         │
│  GET /api/connectors/github/     │
│      oauth/start                 │
└─────────────────┬───────────────┘
                  │
                  ▼
┌─────────────────────────────────┐
│  Backend generates OAuth URL     │
│  with secure state token         │
│  Returns: { auth_url: "..." }    │
└─────────────────┬───────────────┘
                  │
                  ▼
┌─────────────────────────────────┐
│  Browser opens OAuth consent     │
│  User authorizes access          │
└─────────────────┬───────────────┘
                  │
                  ▼
┌─────────────────────────────────┐
│  OAuth callback with code        │
│  Backend exchanges for tokens    │
│  Tokens encrypted and stored     │
└─────────────────────────────────┘
```

### 2. Token Storage

Tokens are securely stored with encryption:

```python
# backend/services/connectors.py
def upsert_connector(
    db, user_id, provider, name, config, secrets, workspace_root
):
    # Encrypt sensitive tokens
    encrypted_secrets = {}
    for k, v in secrets.items():
        encrypted_secrets[k] = encrypt_token(str(v))

    # Store in database with org/user scoping
    connector = Connector(
        user_id=user_id,
        provider=provider,
        config_json=json.dumps(config),
        secret_json=json.dumps(encrypted_secrets).encode(),
    )
    db.add(connector)
```

### 3. Data Ingestion

After connection, NAVI begins ingesting data:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Initial Sync Process                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  GitHub:                                                         │
│    • List repositories                                           │
│    • Index issues, PRs, commits                                  │
│    • Register webhooks for updates                               │
│                                                                  │
│  Jira:                                                           │
│    • Fetch assigned issues                                       │
│    • Index issue descriptions, comments                          │
│    • Register webhooks for transitions                           │
│                                                                  │
│  Slack/Teams:                                                    │
│    • List accessible channels                                    │
│    • Index recent messages mentioning user                       │
│    • Subscribe to channel updates                                │
│                                                                  │
│  Confluence/Docs:                                                │
│    • List accessible spaces                                      │
│    • Index page content                                          │
│    • Register webhooks for page updates                          │
│                                                                  │
│  Zoom/Meet:                                                      │
│    • List recent meetings                                        │
│    • Fetch transcripts (if available)                            │
│    • Register calendar watches                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Context Packet System

When NAVI responds to a query, it builds a **Context Packet** containing all relevant information from connected services:

### Context Packet Structure

```python
@dataclass
class ContextPacket:
    task_key: str           # e.g., "PROJ-123"
    summary: str            # Task summary
    status: str             # Current status

    # Data from connected services
    jira: Dict              # Jira issue details
    prs: List               # Related pull requests
    builds: List            # CI/CD build statuses
    tests: List             # Test results
    conversations: List     # Slack/Teams messages
    meetings: List          # Meeting transcripts
    docs: List              # Documentation links
    code_refs: List         # Code references

    # Metadata
    owners: List            # Assignees, reviewers
    decisions: List         # Recorded decisions
    actions: List           # Action items
    sources: List[SourceRef] # Clickable source links
```

### How NAVI Uses Context

```
User asks: "What's blocking PROJ-123?"
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Context Packet Builder                           │
│                                                                  │
│  1. Query Jira for PROJ-123 details                             │
│     → Status: "In Review", Assignee: "john@example.com"         │
│                                                                  │
│  2. Search Slack messages mentioning PROJ-123                   │
│     → Found: "Waiting on API team review" in #engineering       │
│                                                                  │
│  3. Check GitHub PRs linked to PROJ-123                         │
│     → PR #456: 2 pending reviews, 1 failing check               │
│                                                                  │
│  4. Look up recent CI builds                                    │
│     → Build #789: Failed - "test_auth.py::test_login"          │
│                                                                  │
│  5. Search meeting transcripts                                  │
│     → Standup (Jan 15): "John mentioned API dependency"         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    NAVI Response                                 │
│                                                                  │
│  "PROJ-123 is blocked by several issues:                        │
│                                                                  │
│   1. **PR Review Pending**: PR #456 needs 2 more reviews        │
│      [View PR](https://github.com/org/repo/pull/456)            │
│                                                                  │
│   2. **CI Failure**: test_auth.py is failing                    │
│      [View Build](https://ci.example.com/build/789)             │
│                                                                  │
│   3. **API Dependency**: Waiting on API team per today's        │
│      standup discussion                                         │
│      [View Slack](https://slack.com/archives/C123/p456)         │
│                                                                  │
│  Would you like me to:                                          │
│   • Request reviews on the PR?                                  │
│   • Investigate the test failure?                               │
│   • Ping the API team in Slack?"                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Webhook Integration

NAVI stays updated through webhooks from connected services:

### Supported Webhook Events

| Connector   | Events                                              |
|-------------|-----------------------------------------------------|
| GitHub      | issues, issue_comment, pull_request, status, review |
| Jira        | issue_created, issue_updated, comment_added         |
| Slack       | message, reaction_added, channel_archive            |
| Teams       | message, mention, channel_created                   |
| Confluence  | page_created, page_updated                          |
| Zoom        | meeting_ended, recording_completed                  |
| Meet        | calendar_updated (via Google Calendar watch)        |
| Jenkins/CI  | build_started, build_completed, build_failed        |

### Webhook Processing

```
Webhook received: GitHub issue_comment on #123
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Webhook Router                                  │
│  POST /api/webhooks/github                                       │
│                                                                  │
│  1. Verify signature (GITHUB_WEBHOOK_SECRET)                    │
│  2. Parse event type and payload                                │
│  3. Extract relevant data                                       │
└─────────────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Memory Node Creation                            │
│                                                                  │
│  INSERT INTO memory_node (                                       │
│    org_id, node_type, title, text, meta_json                    │
│  ) VALUES (                                                      │
│    'org-123',                                                    │
│    'github_comment',                                             │
│    'Comment on issue #123',                                      │
│    'Looks good, just fix the typo on line 42',                  │
│    '{"repo": "org/repo", "issue": 123, "user": "jane"}'         │
│  )                                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Cache Invalidation                              │
│                                                                  │
│  invalidate_context_packet_cache(                               │
│    task_key="PROJ-123",                                         │
│    org_id="org-123"                                             │
│  )                                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Action Execution

NAVI can perform actions across connected services with user approval:

### Approval-Gated Operations

```
User: "Comment on PROJ-123 that the fix is ready"
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    NAVI Action Planning                          │
│                                                                  │
│  Plan: Add comment to Jira issue PROJ-123                       │
│  Text: "The fix is ready for review."                           │
│                                                                  │
│  ⚠️  This action requires approval                               │
│                                                                  │
│  [Approve] [Edit] [Cancel]                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                │
        User clicks [Approve]
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Action Execution                              │
│                                                                  │
│  POST /rest/api/3/issue/PROJ-123/comment                        │
│  Body: { "body": "The fix is ready for review." }               │
│                                                                  │
│  ✓ Comment added successfully                                    │
│  Source: https://jira.example.com/browse/PROJ-123               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Supported Actions by Connector

| Connector   | Read Actions                    | Write Actions (Approval Required)      |
|-------------|--------------------------------|----------------------------------------|
| GitHub      | List repos, issues, PRs        | Create issue, comment, review          |
| Jira        | View issues, search            | Transition, comment, assign            |
| Slack       | List channels, search          | Post message, react                    |
| Teams       | List teams, channels           | Post message                           |
| Confluence  | View pages, search             | Create/edit pages (future)             |

## Connector Categories

NAVI supports 250+ connectors across these categories:

### Development & Version Control (30+)
GitHub, GitLab, Bitbucket, Azure DevOps, Perforce, SVN, etc.

### Project Management (35+)
Jira, Linear, Asana, Trello, Notion, Monday, ClickUp, Basecamp, etc.

### Communication (20+)
Slack, Discord, Teams, Zoom, Google Meet, Webex, etc.

### CI/CD & DevOps (35+)
Jenkins, CircleCI, Vercel, GitHub Actions, Docker, Kubernetes, etc.

### Cloud Platforms (20+)
AWS, GCP, Azure, DigitalOcean, Cloudflare, etc.

### Monitoring & Observability (25+)
Datadog, Grafana, Sentry, New Relic, PagerDuty, etc.

### Documentation (15+)
Confluence, GitBook, Notion, ReadMe, Docusaurus, etc.

### Databases (20+)
PostgreSQL, MySQL, MongoDB, Redis, Elasticsearch, etc.

### Security (20+)
Snyk, SonarQube, Veracode, Auth0, Okta, etc.

### And more...
Analytics, CRM, Payments, E-commerce, HR, Testing, AI/ML

## API Reference

### Connection Management

```
GET  /api/connectors/status           # List all connector statuses
GET  /api/connectors                  # List user's connected connectors
POST /api/connectors/save             # Save connector config
DEL  /api/connectors/{id}            # Remove connector

# OAuth flows
GET  /api/connectors/{provider}/oauth/start     # Start OAuth
GET  /api/connectors/{provider}/oauth/callback  # OAuth callback
```

### Sync Operations

```
POST /api/connectors/slack/sync       # Sync Slack channels
POST /api/connectors/confluence/sync  # Sync Confluence pages
POST /api/connectors/github/index     # Index GitHub repo
POST /api/connectors/zoom/sync        # Sync Zoom recordings
POST /api/connectors/meet/sync        # Sync Google Meet events
```

### Webhook Endpoints

```
POST /api/webhooks/github      # GitHub events
POST /api/webhooks/jira        # Jira events
POST /api/webhooks/slack       # Slack events
POST /api/webhooks/teams       # Teams events
POST /api/webhooks/docs        # Confluence events
POST /api/webhooks/ci          # CI/CD events
POST /api/webhooks/meet        # Google Calendar events
```

## Security Considerations

### Token Security
- All tokens encrypted at rest using AES-256
- Tokens never logged or exposed in API responses
- Automatic token refresh for OAuth 2.0 connectors

### Permission Scoping
- Connectors only request minimum required scopes
- User/org isolation enforced at query level
- Admin approval required for org-wide connections

### Webhook Verification
- All webhooks verified using provider signatures
- Configurable secrets per webhook type
- Request replay protection via timestamps

## Troubleshooting

### Common Issues

**Connection fails with "OAuth not configured"**
- Ensure OAuth client credentials are set in `.env` or org config
- Check that redirect URI matches configured callback URL

**Webhook events not received**
- Verify webhook URL is publicly accessible
- Check webhook secret matches configuration
- Ensure firewall allows incoming webhooks

**Context not including connector data**
- Verify connector shows as "connected" in status
- Check that initial sync completed successfully
- Look for sync errors in backend logs

### Debug Endpoints

```
GET /api/connectors/status         # Check connection status
GET /api/health                    # Overall system health
GET /api/advanced/mcp/health       # MCP tools health
```

## Future Enhancements

- **Bi-directional Sync**: Real-time sync of changes back to source systems
- **Custom Connectors**: User-defined connector configurations
- **Connector Marketplace**: Browse and install community connectors
- **Advanced Permissions**: Fine-grained access control per connector
- **Audit Logging**: Comprehensive logging of all connector actions
