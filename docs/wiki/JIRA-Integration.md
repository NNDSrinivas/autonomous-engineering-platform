# JIRA Integration Guide

## Overview

The AEP JIRA integration provides seamless connectivity between your conversational AI assistant and Atlassian JIRA, enabling intelligent task management, priority awareness, and team coordination directly through the chat interface.

## Features

### Core Capabilities
- **Task Retrieval**: Fetch assigned tasks with priority and status
- **Smart Filtering**: Automatic priority-based task organization
- **Real-time Updates**: Sync with JIRA for current task states
- **Context Integration**: Deep task context for better responses
- **Team Coordination**: Cross-reference team member assignments

### Conversational Intelligence
- **Natural Queries**: "Show my tasks", "What's high priority?"
- **Context-Aware Responses**: Task-specific guidance and suggestions
- **Proactive Insights**: Deadline alerts and dependency notifications
- **Planning Integration**: Generate implementation plans from JIRA requirements

## Setup and Configuration

### 1. JIRA Prerequisites

#### Required Permissions
Your JIRA account needs these permissions:
- **Browse Projects**: View project details and issues
- **View Issues**: Access issue details and comments
- **Search Issues**: Query issues with JQL
- **View Development Tools**: Access git integration data

#### Supported JIRA Versions
- **JIRA Cloud**: Fully supported (recommended)
- **JIRA Server**: Version 8.0+ supported
- **JIRA Data Center**: Version 8.0+ supported

### 2. API Token Creation

#### For JIRA Cloud
1. Visit [Atlassian Account Settings](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click "Create API token"
3. Provide a descriptive label (e.g., "AEP Integration")
4. Copy the generated token **immediately** (it won't be shown again)

#### For JIRA Server/Data Center
1. Go to JIRA Settings → System → Personal Access Tokens
2. Create new token with appropriate permissions
3. Copy token for configuration

### 3. Backend Configuration

#### Environment Variables
```bash
# JIRA Connection Settings
JIRA_SERVER_URL=https://your-company.atlassian.net
JIRA_USERNAME=your-email@company.com
JIRA_API_TOKEN=your-api-token-here

# Optional: Custom settings
JIRA_MAX_RESULTS=50
JIRA_CACHE_TTL=300
JIRA_TIMEOUT=30
JIRA_PROJECT_FILTER=AEP,DEV,PROD
```

#### Configuration File
```python
# backend/core/settings.py
JIRA_SETTINGS = {
    "server": os.getenv("JIRA_SERVER_URL"),
    "username": os.getenv("JIRA_USERNAME"),
    "token": os.getenv("JIRA_API_TOKEN"),
    "enabled": True,
    "max_results": int(os.getenv("JIRA_MAX_RESULTS", "50")),
    "cache_ttl": int(os.getenv("JIRA_CACHE_TTL", "300")),
    "timeout": int(os.getenv("JIRA_TIMEOUT", "30")),
    "project_filter": os.getenv("JIRA_PROJECT_FILTER", "").split(","),
    "custom_fields": {
        "story_points": "customfield_10001",
        "epic_link": "customfield_10002",
        "sprint": "customfield_10003"
    }
}
```

### 4. Verification

#### Test Connection
```bash
# Using curl
curl -X GET "http://localhost:8002/api/jira/test-connection"

# Expected response
{
  "status": "connected",
  "server": "https://your-company.atlassian.net",
  "user": "your-email@company.com",
  "permissions": ["browse_projects", "view_issues", "search_issues"],
  "projects": ["AEP", "DEV", "PROD"]
}
```

#### Test Task Retrieval
```bash
curl -X GET "http://localhost:8002/api/jira/tasks"
```

## Usage Examples

### Basic Task Queries

#### "Show my tasks"
```
User: Show my tasks
AEP: You have 5 assigned tasks.

🔴 High Priority:
• AEP-123: Implement enhanced chat interface
• AEP-124: Add team intelligence features

🟡 Medium Priority:
• AEP-125: Update documentation
• AEP-126: Code review improvements

🟢 Low Priority:
• AEP-127: Optimize performance metrics

Suggestions: [Work on AEP-123] [Generate plan] [Check dependencies]
```

#### "What's my highest priority task?"
```
User: What's my highest priority task?
AEP: Your highest priority task is **AEP-123: Implement enhanced chat interface**.

**Details:**
- Status: In Progress
- Priority: High
- Reporter: Product Manager
- Due Date: January 20, 2024
- Story Points: 8

**Description:**
Transform the basic greeting system into a comprehensive conversational experience...

Suggestions: [Generate implementation plan] [Check related work] [Start working]
```

### Advanced Queries

#### "Show tasks due this week"
```
User: Show tasks due this week
AEP: You have 3 tasks due this week:

📅 **Due January 18, 2024:**
• AEP-123: Implement enhanced chat interface (High Priority)

📅 **Due January 20, 2024:**
• AEP-125: Update documentation (Medium Priority)
• AEP-126: Code review improvements (Medium Priority)

🚨 **Attention:** AEP-123 is due in 3 days and is high priority!

Suggestions: [Focus on AEP-123] [Plan weekly schedule] [Check blockers]
```

#### "Are there any blockers for my current work?"
```
User: Are there any blockers for my current work?
AEP: I found potential blockers for your current tasks:

🚫 **AEP-123 (Current Task):**
- Dependency: AEP-120 (Database schema update) - Still in review
- Resource: Design mockups needed from UX team

⚠️ **Recommendations:**
- Contact Sarah about AEP-120 review status
- Follow up with Design team for mockups
- Consider working on documentation (AEP-125) while waiting

Suggestions: [Contact Sarah] [Ping UX team] [Work on docs] [Find alternative tasks]
```

### Team Coordination

#### "Who's working on related tasks?"
```
User: Who's working on related tasks?
AEP: Found teammates working on related areas:

👥 **Related Work:**
• **John Smith** - AEP-120: Database schema update (Blocks your work)
• **Sarah Johnson** - AEP-124: Team intelligence features (Similar scope)
• **Mike Wilson** - AEP-130: Frontend components (Complementary)

💡 **Coordination Opportunities:**
- Sync with John on database changes affecting your chat interface
- Collaborate with Sarah on shared team intelligence components
- Share frontend patterns with Mike for consistency

Suggestions: [Schedule sync with John] [Collaborate with Sarah] [Share with Mike]
```

## Advanced Features

### Custom JQL Queries

#### Configuration
```python
# Custom JQL templates for specific queries
CUSTOM_JQL_QUERIES = {
    "my_overdue": "assignee = currentUser() AND duedate < now() AND status != Done",
    "my_this_week": "assignee = currentUser() AND duedate >= startOfWeek() AND duedate <= endOfWeek()",
    "my_sprint": "assignee = currentUser() AND sprint in openSprints()",
    "team_blockers": "project = {project} AND status = 'Blocked' AND assignee in membersOf('{team}')"
}
```

#### Usage in Chat
```
User: Show my overdue tasks
AEP: [Uses custom JQL: "my_overdue"]

User: What's in our current sprint?
AEP: [Uses custom JQL: "my_sprint"]
```

### Custom Fields Integration

#### Configuration
```python
# Map JIRA custom fields to readable names
CUSTOM_FIELD_MAPPING = {
    "customfield_10001": "story_points",
    "customfield_10002": "epic_link",
    "customfield_10003": "sprint",
    "customfield_10004": "team",
    "customfield_10005": "business_value"
}
```

#### Enhanced Responses
```
User: Show task details for AEP-123
AEP: **AEP-123: Implement enhanced chat interface**

**Core Details:**
- Status: In Progress
- Priority: High
- Story Points: 8
- Sprint: Sprint 23
- Epic: Enhanced UI Experience
- Team: Frontend Development
- Business Value: High

**Progress:**
- 60% complete based on subtasks
- 3 of 5 acceptance criteria met
- No blockers currently identified
```

### Webhooks Integration (Advanced)

#### Setup Webhook Endpoint
```python
# backend/api/jira_webhooks.py
from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/webhooks/jira")

@router.post("/issue-updated")
async def handle_issue_update(request: Request):
    data = await request.json()
    issue_key = data["issue"]["key"]
    
    # Update cache and notify relevant users
    await invalidate_task_cache(issue_key)
    await notify_task_update(issue_key, data)
    
    return {"status": "processed"}
```

#### Real-time Updates
```
# When JIRA task updates via webhook
AEP: 🔔 **Task Update:** AEP-123 status changed to "Code Review"

The task you're working on has been updated:
- Previous status: In Progress
- New status: Code Review
- Updated by: John Smith
- Comment: "Ready for review, please check the implementation"

Suggestions: [View changes] [Request review] [Update status]
```

## Troubleshooting

### Common Issues

#### Connection Failed
**Error:** `JIRA_CONNECTION_FAILED`
**Causes:**
1. Incorrect server URL
2. Invalid credentials
3. Network connectivity issues
4. JIRA server temporarily unavailable

**Solutions:**
```bash
# Test URL accessibility
curl -I https://your-company.atlassian.net

# Verify credentials
curl -u "email:token" https://your-company.atlassian.net/rest/api/3/myself

# Check backend logs
tail -f logs/backend.log | grep -i jira
```

#### Authentication Errors
**Error:** `JIRA_AUTH_FAILED`
**Causes:**
1. Expired API token
2. Account permissions changed
3. Username/email mismatch

**Solutions:**
1. Regenerate API token in Atlassian settings
2. Verify account has required permissions
3. Check username matches JIRA account email

#### Rate Limiting
**Error:** `JIRA_RATE_LIMITED`
**Causes:**
1. Too many API calls in short time
2. JIRA instance rate limits

**Solutions:**
```python
# Increase cache TTL to reduce API calls
JIRA_CACHE_TTL = 600  # 10 minutes

# Implement request batching
JIRA_BATCH_REQUESTS = True
JIRA_MAX_CONCURRENT = 5
```

#### Slow Response Times
**Causes:**
1. Large number of assigned tasks
2. Complex JQL queries
3. Network latency

**Solutions:**
```python
# Optimize query parameters
JIRA_SETTINGS = {
    "max_results": 25,  # Reduce from default 50
    "fields": "key,summary,status,priority,assignee",  # Limit fields
    "timeout": 15,  # Reduce timeout
    "use_pagination": True
}
```

### Debug Mode

#### Enable JIRA Debug Logging
```python
# backend/core/logging.py
import logging

logging.getLogger("jira").setLevel(logging.DEBUG)
logging.getLogger("requests").setLevel(logging.DEBUG)
```

#### Verbose API Calls
```python
# In JIRA service configuration
JIRA_DEBUG = {
    "log_requests": True,
    "log_responses": True,
    "log_performance": True,
    "mask_credentials": True
}
```

### Performance Optimization

#### Caching Strategy
```python
# Multi-level caching for better performance
JIRA_CACHE_CONFIG = {
    "task_list": {"ttl": 300, "max_size": 100},
    "task_details": {"ttl": 600, "max_size": 500},
    "user_info": {"ttl": 3600, "max_size": 50},
    "project_info": {"ttl": 86400, "max_size": 20}
}
```

#### Query Optimization
```python
# Optimized JQL for common queries
OPTIMIZED_JQL = {
    "my_tasks": (
        "assignee = currentUser() "
        "AND status NOT IN (Done, Closed, Resolved) "
        "ORDER BY priority DESC, duedate ASC"
    ),
    "high_priority": (
        "assignee = currentUser() "
        "AND priority IN (High, Highest) "
        "AND status NOT IN (Done, Closed)"
    )
}
```

## Security Considerations

### API Token Security
- Store tokens in environment variables, never in code
- Use different tokens for different environments
- Regularly rotate API tokens
- Monitor token usage for unusual activity

### Network Security
```python
# SSL/TLS configuration
JIRA_SSL_CONFIG = {
    "verify_ssl": True,
    "ssl_cert_path": "/path/to/cert.pem",
    "ssl_key_path": "/path/to/key.pem",
    "ca_bundle_path": "/path/to/ca-bundle.crt"
}
```

### Data Privacy
- Limit task data exposure in logs
- Implement data retention policies
- Respect JIRA instance privacy settings
- Comply with organizational data policies

## Best Practices

### Query Patterns
1. **Use specific JQL**: Avoid broad queries that return too many results
2. **Leverage caching**: Repeated queries should use cached results
3. **Batch requests**: Group related API calls when possible
4. **Monitor quotas**: Track API usage against JIRA limits

### Error Handling
```python
# Graceful degradation when JIRA is unavailable
def get_tasks_with_fallback():
    try:
        return jira_service.get_user_tasks()
    except JIRAConnectionError:
        # Return cached data or empty state with helpful message
        return {
            "tasks": get_cached_tasks(),
            "message": "JIRA temporarily unavailable, showing cached data"
        }
```

### User Experience
1. **Clear error messages**: Help users understand and resolve issues
2. **Progressive disclosure**: Show basic info first, details on request
3. **Contextual suggestions**: Offer relevant actions based on task state
4. **Performance feedback**: Show loading states for slow operations