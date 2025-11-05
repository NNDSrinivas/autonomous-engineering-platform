# API Reference - Phase 1 Enhanced Conversational UI

## Overview

The AEP Chat API provides intelligent conversational capabilities with team intelligence integration. This RESTful API handles chat interactions, intent analysis, and context-aware response generation.

## Base URL
```
http://localhost:8002/api/chat
```

## Authentication

Currently, the API uses basic authentication for JIRA integration. Future versions will implement JWT-based authentication.

```http
Authorization: Bearer <jwt-token>
```

## Core Endpoints

### POST /respond

Generate context-aware chat response using team intelligence.

#### Request

```http
POST /api/chat/respond
Content-Type: application/json
```

```json
{
  "message": "string",
  "conversationHistory": [
    {
      "id": "string",
      "type": "user|assistant|system|suggestion",
      "content": "string",
      "timestamp": "2024-01-15T10:30:00Z",
      "context": {
        "taskKey": "string",
        "files": ["string"],
        "suggestions": ["string"]
      }
    }
  ],
  "currentTask": "string",
  "teamContext": {
    "activeProjects": ["string"],
    "recentActivity": ["object"]
  }
}
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `message` | string | Yes | User's chat message |
| `conversationHistory` | array | No | Previous chat messages (last 5 recommended) |
| `currentTask` | string | No | Current JIRA task key (e.g., "AEP-123") |
| `teamContext` | object | No | Additional team context data |

#### Response

```json
{
  "content": "string",
  "context": {
    "taskKey": "string",
    "action": "string",
    "metadata": "object"
  },
  "suggestions": [
    "string"
  ]
}
```

#### Example

**Request:**
```json
{
  "message": "Show my tasks",
  "conversationHistory": [],
  "currentTask": null,
  "teamContext": {}
}
```

**Response:**
```json
{
  "content": "You have 3 assigned tasks.\n\n🔴 **High Priority:**\n• **AEP-123**: Implement enhanced chat interface\n• **AEP-124**: Add team intelligence features\n\n📋 **All Tasks:**\n🔴 AEP-123: Implement enhanced chat interface\n🟡 AEP-125: Update documentation\n🟢 AEP-126: Code review improvements",
  "context": {
    "taskKey": null,
    "action": "task_list",
    "metadata": {
      "totalTasks": 3,
      "highPriorityCount": 2
    }
  },
  "suggestions": [
    "Work on AEP-123",
    "Generate plan for highest priority task",
    "Show task dependencies",
    "Check what teammates are working on"
  ]
}
```

### POST /suggestions/proactive

Generate proactive suggestions based on current context.

#### Request

```http
POST /api/chat/suggestions/proactive
Content-Type: application/json
```

```json
{
  "context": {
    "recentChanges": ["string"],
    "currentFiles": ["string"],
    "activeTask": "string",
    "teamActivity": ["object"]
  }
}
```

#### Response

```json
{
  "items": [
    "string"
  ]
}
```

#### Example

**Request:**
```json
{
  "context": {
    "recentChanges": ["src/components/ChatPanel.tsx", "backend/api/chat.py"],
    "currentFiles": ["extensions/vscode/src/panels/ChatPanel.ts"],
    "activeTask": "AEP-123",
    "teamActivity": []
  }
}
```

**Response:**
```json
{
  "items": [
    "I notice recent changes in multiple files. Would you like me to check for conflicts?",
    "The current files look like they might need testing. Want me to help with that?",
    "Your current task might overlap with team work. Want to check?"
  ]
}
```

## Intent Classification

The API automatically classifies user messages into the following intent types:

### Task Query
- **Keywords**: task, jira, ticket, assigned, priority
- **Response**: Task list, priorities, assignments
- **Example**: "Show my tasks", "What's my highest priority?"

### Team Query
- **Keywords**: team, colleague, teammate, working on, activity
- **Response**: Team activity, collaboration opportunities
- **Example**: "What is my team working on?", "Who's working on related tasks?"

### Plan Request
- **Keywords**: plan, how, implement, steps, approach
- **Response**: Implementation plans, step-by-step guides
- **Example**: "How should I implement this?", "Generate a plan for AEP-123"

### Code Help
- **Keywords**: code, bug, error, fix, debug, review
- **Response**: Code assistance, debugging help, reviews
- **Example**: "Help me debug this", "Review my changes"

### General Query
- **Default**: General assistance and platform information
- **Response**: Platform overview, general guidance
- **Example**: "Hello", "What can you help me with?"

## Context Enhancement

### Conversation History
- Maintains last 5 messages for context
- Preserves message metadata and suggestions
- Enables contextual follow-up responses

### Task Context Integration
Automatically fetches task details when `currentTask` is provided:

```http
GET /api/context/task/{taskKey}
```

Includes:
- Task summary and description
- Priority and status
- Assignee and reporter
- Comments and updates

### Team Activity Integration
Fetches recent team activity:

```http
GET /api/activity/recent
```

Returns:
- Recent commits and changes
- Task assignments and updates
- Collaboration opportunities
- Team coordination insights

## Response Patterns

### Task-Focused Responses
```json
{
  "content": "Task information with priority indicators",
  "suggestions": [
    "Work on specific task",
    "Generate implementation plan",
    "Check dependencies"
  ]
}
```

### Team-Oriented Responses
```json
{
  "content": "Team activity and collaboration insights",
  "suggestions": [
    "Show detailed team status",
    "Find related work",
    "Check coordination opportunities"
  ]
}
```

### Implementation-Focused Responses
```json
{
  "content": "Technical guidance and code assistance",
  "suggestions": [
    "Generate detailed plan",
    "Show code examples",
    "Create tests"
  ]
}
```

## Error Handling

### Standard Error Response
```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": "object"
  }
}
```

### Common Error Codes

| Code | Status | Description |
|------|--------|-------------|
| `INVALID_REQUEST` | 400 | Malformed request body |
| `MISSING_MESSAGE` | 400 | Message field is required |
| `CONTEXT_ERROR` | 500 | Failed to fetch task/team context |
| `JIRA_UNAVAILABLE` | 503 | JIRA integration temporarily unavailable |
| `RATE_LIMITED` | 429 | Too many requests |

### Error Examples

**Missing Message:**
```json
{
  "error": {
    "code": "MISSING_MESSAGE",
    "message": "Message field is required",
    "details": {
      "field": "message",
      "received": null
    }
  }
}
```

**JIRA Unavailable:**
```json
{
  "error": {
    "code": "JIRA_UNAVAILABLE",
    "message": "JIRA integration temporarily unavailable",
    "details": {
      "service": "jira",
      "status": "offline",
      "fallback_enabled": true
    }
  }
}
```

## Rate Limiting

### Current Limits
- **Chat Responses**: 60 requests per minute per user
- **Proactive Suggestions**: 20 requests per minute per user
- **Context Fetching**: 100 requests per minute per user

### Rate Limit Headers
```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1642248000
```

### Rate Limit Exceeded
```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded",
    "details": {
      "limit": 60,
      "window": "1 minute",
      "reset_time": "2024-01-15T10:31:00Z"
    }
  }
}
```

## Integration APIs

### JIRA Integration

#### GET /api/jira/tasks
Fetch user's assigned JIRA tasks.

```json
{
  "items": [
    {
      "key": "AEP-123",
      "summary": "Implement enhanced chat interface",
      "priority": "High",
      "status": "In Progress",
      "assignee": "john.doe@company.com",
      "created": "2024-01-10T09:00:00Z",
      "updated": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 3
}
```

#### GET /api/jira/test-connection
Test JIRA integration connectivity.

```json
{
  "status": "connected",
  "server": "https://company.atlassian.net",
  "user": "john.doe@company.com",
  "permissions": ["browse_projects", "view_issues"]
}
```

### Team Activity Integration

#### GET /api/activity/recent
Fetch recent team activity.

```json
{
  "items": [
    {
      "author": "jane.smith",
      "action": "committed changes to",
      "target": "authentication module",
      "timestamp": "2024-01-15T08:30:00Z",
      "type": "git_commit"
    },
    {
      "author": "mike.wilson",
      "action": "opened PR for",
      "target": "dashboard updates",
      "timestamp": "2024-01-15T06:15:00Z",
      "type": "pull_request"
    }
  ],
  "total": 15
}
```

## WebSocket Support (Future)

Real-time chat updates will be available via WebSocket:

```javascript
const ws = new WebSocket('ws://localhost:8002/api/chat/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Handle real-time updates
};
```

## SDK Examples

### JavaScript/TypeScript
```typescript
interface ChatRequest {
  message: string;
  conversationHistory?: ChatMessage[];
  currentTask?: string;
  teamContext?: any;
}

class AEPChatClient {
  constructor(private baseUrl: string) {}

  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    const response = await fetch(`${this.baseUrl}/api/chat/respond`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    });
    return response.json();
  }

  async getProactiveSuggestions(context: any): Promise<string[]> {
    const response = await fetch(`${this.baseUrl}/api/chat/suggestions/proactive`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ context })
    });
    const data = await response.json();
    return data.items;
  }
}
```

### Python
```python
import requests
from typing import List, Dict, Any, Optional

class AEPChatClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def send_message(
        self,
        message: str,
        conversation_history: Optional[List[Dict]] = None,
        current_task: Optional[str] = None,
        team_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/api/chat/respond"
        data = {
            "message": message,
            "conversationHistory": conversation_history or [],
            "currentTask": current_task,
            "teamContext": team_context or {}
        }
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()

    def get_proactive_suggestions(self, context: Dict[str, Any]) -> List[str]:
        url = f"{self.base_url}/api/chat/suggestions/proactive"
        data = {"context": context}
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()["items"]
```

## Performance Considerations

### Caching
- Task context cached for 5 minutes
- Team activity cached for 2 minutes
- Intent analysis results cached for 1 hour

### Optimization Tips
1. **Limit conversation history** to last 5 messages
2. **Use currentTask** parameter for better context
3. **Batch proactive suggestions** requests
4. **Implement client-side caching** for repeated queries

### Monitoring
Available metrics:
- Response time percentiles
- Error rates by endpoint
- Cache hit rates
- JIRA integration health