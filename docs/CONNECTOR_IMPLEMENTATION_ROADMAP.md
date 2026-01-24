# NAVI Connector Implementation Roadmap

## Current State (January 2025)

### Fully Implemented Connectors (27 total)

All connectors below have complete end-to-end integration:
- **Service Layer**: `backend/services/{provider}_service.py`
- **Tools Layer**: `backend/agent/tools/{provider}_tools.py`
- **Tool Executor**: Dispatchers in `backend/agent/tool_executor.py`
- **Intent Detection**: Keywords in `backend/agent/intent_classifier.py`
- **Provider Capabilities**: Defined in `backend/services/connector_base.py`

| Category | Connector | Tools | Read Ops | Write Ops | Status |
|----------|-----------|-------|----------|-----------|--------|
| **Issue Tracking** | Jira | 6 | Query issues, get details, list comments | Create issues, add comments, transition | ✅ Complete |
| | Linear | 6 | Query issues, search, list projects | Create issues, add comments | ✅ Complete |
| | Asana | 5 | List tasks, search, list projects | Create tasks, complete tasks | ✅ Complete |
| | Trello | 5 | List boards, list cards, get card | Create cards, move cards | ✅ Complete |
| | Monday.com | 5 | List boards, list items, get details | Create items | ✅ Complete |
| | ClickUp | 5 | List tasks, list spaces, get task | Create tasks, update tasks | ✅ Complete |
| **Code & VCS** | GitHub | 9 | Query PRs, issues, list repos, PR details | Create issues, comment, labels, PRs | ✅ Complete |
| | GitLab | 6 | Query MRs, issues, pipeline status | Create MRs, add comments | ✅ Complete |
| | Bitbucket | 4 | List PRs, repos, PR details | Create pull requests | ✅ Complete |
| **CI/CD** | GitHub Actions | 4 | List workflows, runs, get status | Trigger workflows | ✅ Complete |
| | CircleCI | 4 | List pipelines, status, job status | Trigger pipelines | ✅ Complete |
| | Vercel | 4 | List projects, deployments, status | Redeploy | ✅ Complete |
| **Communication** | Slack | 3 | Search messages, list channel messages | Send messages | ✅ Complete |
| | Discord | 3 | List channels, get messages | Send messages | ✅ Complete |
| **Documentation** | Notion | 5 | Search pages, get content, list recent | Create pages | ✅ Complete |
| | Confluence | 3 | Search pages, get content, list in space | - | ✅ Complete |
| | Google Drive | 3 | List files, search, get content | - | ✅ Complete |
| **Meetings** | Zoom | 3 | List recordings, get transcript, search | - | ✅ Complete |
| | Google Calendar | 3 | List events, today's events, get event | - | ✅ Complete |
| | Loom | 3 | List videos, search, get details | - | ✅ Complete |
| **Monitoring** | Datadog | 5 | List monitors, alerting, incidents, dashboards | Mute monitors | ✅ Complete |
| | Sentry | 4 | List issues, get details, list projects | Resolve issues | ✅ Complete |
| | PagerDuty | 5 | List incidents, get on-call, services | Acknowledge, resolve | ✅ Complete |
| **Security** | Snyk | 4 | List vulnerabilities, projects, summary | - | ✅ Complete |
| | SonarQube | 4 | List projects, issues, quality gate | - | ✅ Complete |
| **Design** | Figma | 5 | List files, get details, comments | Add comments | ✅ Complete |

**Total: 127 tools across 27 connectors**

---

## Architecture Overview

### How Connectors Work End-to-End

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER REQUEST                                       │
│                    "show my datadog monitors"                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      INTENT CLASSIFIER                                       │
│  backend/agent/intent_classifier.py                                         │
│  ├─ _detect_provider("datadog") → Provider.DATADOG                         │
│  ├─ _infer_family() → IntentFamily.PROJECT_MANAGEMENT                      │
│  └─ _infer_kind() → IntentKind.LIST_MY_ITEMS                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PLANNER V3                                          │
│  backend/agent/planner_v3.py                                                │
│  ├─ Selects tool: "datadog.list_monitors"                                  │
│  └─ Returns action plan with tool call                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       TOOL EXECUTOR                                         │
│  backend/agent/tool_executor.py                                             │
│  ├─ execute_tool("datadog.list_monitors", args)                            │
│  ├─ Routes to _dispatch_datadog_tool()                                      │
│  └─ Calls DATADOG_TOOLS["datadog.list_monitors"]                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TOOL FUNCTION                                        │
│  backend/agent/tools/datadog_tools.py                                       │
│  ├─ list_datadog_monitors(context, ...)                                    │
│  ├─ Gets user connection from DB                                            │
│  └─ Calls DatadogService.list_monitors()                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SERVICE LAYER                                         │
│  backend/services/datadog_service.py                                        │
│  ├─ Extracts credentials from connection                                    │
│  ├─ Calls DatadogClient (API wrapper)                                       │
│  └─ Returns formatted data                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        API CLIENT                                            │
│  backend/integrations/datadog_client.py                                     │
│  ├─ Makes authenticated HTTP requests                                       │
│  ├─ Handles pagination, rate limits                                         │
│  └─ Returns raw API response                                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TOOL RESULT                                          │
│  ToolResult(output="Found 5 monitors...", sources=[{url, name}])           │
│  → Rendered in UI with clickable links                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## File Structure Per Connector

Each connector consists of these files:

```
backend/
├── integrations/
│   └── {provider}_client.py       # HTTP API client (already existed)
├── services/
│   └── {provider}_service.py      # Service layer with sync/write/query methods
├── agent/tools/
│   └── {provider}_tools.py        # Tool functions for NAVI agent
└── api/routers/
    └── connectors.py              # OAuth endpoints (shared file)
```

### Service Layer Pattern

```python
class {Provider}Service(ConnectorServiceBase):
    PROVIDER = "{provider}"
    SUPPORTED_ITEM_TYPES = ["item1", "item2"]
    WRITE_OPERATIONS = ["create_item", "update_item"]

    @classmethod
    async def sync_items(cls, db, connection, item_types, **kwargs):
        """Fetch from API and store in local DB."""

    @classmethod
    async def write_item(cls, db, connection, operation, **kwargs):
        """Create/update/delete items via API."""

    @classmethod
    async def list_{items}(cls, db, connection, **kwargs):
        """Query items from API (live, not cached)."""
```

### Tools Layer Pattern

```python
async def list_{provider}_{items}(context: Dict[str, Any], **kwargs) -> ToolResult:
    """List {items} from {Provider}."""
    user_id = context.get("user_id")
    connection = get_connector(db, user_id, "{provider}")

    items = await {Provider}Service.list_{items}(db, connection, **kwargs)

    # Format output with clickable sources
    return ToolResult(output=formatted_text, sources=source_links)

{PROVIDER}_TOOLS = {
    "{provider}.list_{items}": list_{provider}_{items},
    "{provider}.get_{item}": get_{provider}_{item},
    # ...
}
```

---

## Authentication Methods

| Connector | Auth Type | Credentials Storage |
|-----------|-----------|---------------------|
| **Jira** | OAuth 2.0 / API Token | User's token in DB |
| **GitHub** | OAuth 2.0 | User's token in DB |
| **Slack** | OAuth 2.0 | User's token in DB |
| **Datadog** | API Key + App Key | User enters in UI |
| **SonarQube** | Token (Basic Auth) | User enters in UI |
| **Snyk** | API Token | User enters in UI |
| **Google (Drive/Calendar)** | OAuth 2.0 | User's token in DB |
| **Figma** | OAuth 2.0 | User's token in DB |
| **PagerDuty** | API Token | User enters in UI |

### OAuth Flow (Admin Setup Required)

Admins must set these environment variables:

```bash
# Core OAuth Credentials (set once per deployment)
GITHUB_CLIENT_ID=xxx
GITHUB_CLIENT_SECRET=xxx

SLACK_CLIENT_ID=xxx
SLACK_CLIENT_SECRET=xxx

GOOGLE_CLIENT_ID=xxx          # Shared by Drive, Calendar, Docs
GOOGLE_CLIENT_SECRET=xxx

FIGMA_CLIENT_ID=xxx
FIGMA_CLIENT_SECRET=xxx

TRELLO_API_KEY=xxx
TRELLO_API_SECRET=xxx

MONDAY_CLIENT_ID=xxx
MONDAY_CLIENT_SECRET=xxx

# Token-based (users enter their own)
# No admin setup needed - users add tokens in connection settings
```

---

## Tool Reference

### Project Management Tools

```
jira.list_my_issues          - List Jira issues assigned to user
jira.get_issue               - Get issue details
jira.create_issue            - Create new issue
jira.add_comment             - Add comment to issue
jira.transition_issue        - Change issue status
jira.search_issues           - Search with JQL

linear.list_my_issues        - List Linear issues assigned to user
linear.search_issues         - Search issues
linear.create_issue          - Create new issue

asana.list_my_tasks          - List tasks assigned to user
asana.create_task            - Create new task
asana.complete_task          - Mark task complete

trello.list_boards           - List all boards
trello.list_my_cards         - List cards assigned to user
trello.create_card           - Create new card
trello.move_card             - Move card to different list

monday.list_boards           - List Monday.com boards
monday.list_items            - List items in a board
monday.get_my_items          - Get items assigned to user
monday.create_item           - Create new item

clickup.list_my_tasks        - List tasks assigned to user
clickup.list_spaces          - List workspaces
clickup.create_task          - Create new task
```

### Code & CI/CD Tools

```
github.list_my_prs           - List PRs by user
github.list_my_issues        - List issues assigned to user
github.get_pr_details        - Get PR with files, reviews
github.create_issue          - Create new issue
github.add_comment           - Add PR/issue comment

gitlab.list_my_mrs           - List merge requests by user
gitlab.get_pipeline_status   - Get CI pipeline status

bitbucket.list_my_prs        - List pull requests
bitbucket.list_repos         - List repositories
bitbucket.create_pull_request - Create new PR

github_actions.list_workflows - List workflow definitions
github_actions.list_runs      - List recent workflow runs
github_actions.trigger_workflow - Trigger a workflow

circleci.list_pipelines      - List pipelines
circleci.trigger_pipeline    - Trigger new pipeline

vercel.list_deployments      - List deployments
vercel.get_deployment_status - Get deployment details
vercel.redeploy              - Trigger redeployment
```

### Communication Tools

```
slack.search_messages        - Search Slack messages
slack.list_channel_messages  - Get recent channel messages
slack.send_message           - Send message to channel

discord.list_channels        - List server channels
discord.get_messages         - Get channel messages
discord.send_message         - Send message
```

### Documentation Tools

```
notion.search_pages          - Search Notion workspace
notion.get_page_content      - Get page content
notion.list_recent_pages     - List recently edited pages
notion.create_page           - Create new page

confluence.search_pages      - Search Confluence
confluence.get_page          - Get page content
confluence.list_pages_in_space - List pages in a space

gdrive.list_files            - List Drive files
gdrive.search                - Search files
gdrive.get_content           - Get file content
```

### Monitoring & Security Tools

```
datadog.list_monitors        - List all monitors
datadog.alerting_monitors    - Get monitors in alert state
datadog.list_incidents       - List incidents
datadog.mute_monitor         - Mute a monitor

sentry.list_issues           - List error issues
sentry.get_issue             - Get issue details
sentry.resolve_issue         - Resolve an issue

pagerduty.list_incidents     - List incidents
pagerduty.get_oncall         - Get on-call schedule
pagerduty.acknowledge_incident - Acknowledge incident
pagerduty.resolve_incident   - Resolve incident

snyk.list_vulnerabilities    - List security vulnerabilities
snyk.list_projects           - List projects
snyk.get_security_summary    - Get security overview

sonarqube.list_issues        - List code quality issues
sonarqube.get_quality_gate   - Get quality gate status
sonarqube.get_metrics        - Get project metrics
```

### Design & Meeting Tools

```
figma.list_files             - List design files
figma.get_file               - Get file details
figma.get_comments           - Get design comments
figma.add_comment            - Add comment to design

zoom.list_recordings         - List meeting recordings
zoom.get_transcript          - Get meeting transcript
zoom.search_recordings       - Search recordings

gcalendar.list_events        - List upcoming events
gcalendar.todays_events      - Get today's schedule
gcalendar.get_event          - Get event details

loom.list_videos             - List Loom videos
loom.search_videos           - Search videos
loom.get_video               - Get video details
```

---

## Write Operations (Require Approval)

These tools mutate external systems and require user approval:

```python
WRITE_OPERATION_TOOLS = {
    # Issue Tracking
    "jira.create_issue",
    "jira.add_comment",
    "jira.transition_issue",
    "linear.create_issue",
    "linear.add_comment",
    "asana.create_task",
    "asana.complete_task",
    "trello.create_card",
    "trello.move_card",
    "clickup.create_task",
    "clickup.update_task",
    "monday.create_item",

    # Code
    "github.create_issue",
    "github.add_comment",
    "github.create_pr",
    "gitlab.create_mr",
    "gitlab.add_comment",
    "bitbucket.create_pull_request",

    # CI/CD
    "github_actions.trigger_workflow",
    "circleci.trigger_pipeline",
    "vercel.redeploy",

    # Communication
    "slack.send_message",
    "discord.send_message",

    # Monitoring
    "datadog.mute_monitor",
    "sentry.resolve_issue",
    "pagerduty.acknowledge_incident",
    "pagerduty.resolve_incident",

    # Design
    "figma.add_comment",

    # Documentation
    "notion.create_page",
    "confluence.create_page",
}
```

---

## Provider Capabilities Matrix

Defined in `backend/services/connector_base.py`:

```python
PROVIDER_CAPABILITIES = {
    "jira": {
        "name": "Jira",
        "category": "work_tracking",
        "read_capabilities": ["query issues", "get issue details", "list comments"],
        "write_capabilities": ["create issues", "add comments", "transition status"],
    },
    "datadog": {
        "name": "Datadog",
        "category": "monitoring",
        "read_capabilities": ["list monitors", "get alerting monitors", "list incidents"],
        "write_capabilities": ["mute monitors"],
    },
    # ... 25 more providers
}
```

This matrix is used to:
1. Build NAVI's system prompt dynamically based on connected services
2. Validate tool calls before execution
3. Show users what capabilities are available

---

## Intent Detection Keywords

The intent classifier detects providers from natural language:

| Provider | Trigger Keywords |
|----------|------------------|
| Jira | "jira", "jira ticket", "jira issue", "jira sprint" |
| Linear | "linear", "lin-", "linear issue" |
| GitHub | "github", "gh pr", "pull request", "pr " |
| GitLab | "gitlab", "merge request", "mr ", "gitlab pipeline" |
| Slack | "slack", "slack channel", "slack message" |
| Datadog | "datadog", "dd monitor", "datadog incident" |
| Sentry | "sentry", "sentry issue", "sentry error" |
| PagerDuty | "pagerduty", "oncall", "on-call" |
| Figma | "figma", "figma file", "figma design" |
| Zoom | "zoom", "zoom recording", "zoom transcript" |
| Google Calendar | "google calendar", "gcal", "calendar event" |

---

## Testing Connectors

### Verify Tool Import

```bash
python3 -c "
from backend.agent.tools.datadog_tools import DATADOG_TOOLS
print(f'Datadog tools: {list(DATADOG_TOOLS.keys())}')
"
```

### Verify Tool Executor

```bash
python3 -c "
from backend.agent.tool_executor import get_available_tools
tools = get_available_tools()
print(f'Total tools: {len(tools)}')
"
```

### Test Provider Detection

```bash
python3 -c "
from backend.agent.intent_classifier import _detect_provider
print(_detect_provider('show my datadog monitors'))  # Provider.DATADOG
print(_detect_provider('list sentry issues'))        # Provider.SENTRY
"
```

---

## Future Connectors (Not Yet Implemented)

| Connector | Priority | Notes |
|-----------|----------|-------|
| Microsoft Teams | High | Needs async wrapper for MSAL |
| Google Docs | Medium | Shares OAuth with Drive |
| AWS CloudWatch | Medium | Complex IAM setup |
| Jenkins | Medium | Many deployment variations |
| Opsgenie | Low | Alternative to PagerDuty |
| New Relic | Low | Alternative to Datadog |

---

## Troubleshooting

### "Connector not connected"
- User hasn't completed OAuth flow
- Check `connector_connections` table for user's connection

### "Tool not implemented"
- Tool name doesn't match registry key
- Check `{PROVIDER}_TOOLS` dict in tools file

### "Rate limited"
- API rate limits exceeded
- Implement backoff in client layer

### "Token expired"
- OAuth token needs refresh
- Implement token refresh in service layer
