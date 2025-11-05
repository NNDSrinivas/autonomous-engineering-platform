"""
Enhanced Chat API for conversational interface
Provides context-aware responses with team intelligence
"""

from fastapi import APIRouter, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timezone
import logging
import threading
import httpx  # Use async httpx instead of sync requests
from sqlalchemy.orm import Session
from urllib.parse import urlparse

from backend.core.db import get_db
from backend.core.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


# Shared async client instance with proper lifecycle management
_async_client: Optional[httpx.AsyncClient] = None
_client_lock = threading.Lock()


def get_http_client() -> httpx.AsyncClient:
    """Get shared httpx client instance (thread-safe initialization)"""
    global _async_client
    if _async_client is None:
        with _client_lock:
            # Double-check locking pattern
            if _async_client is None:
                _async_client = httpx.AsyncClient(
                    timeout=httpx.Timeout(10.0),
                    limits=httpx.Limits(
                        max_keepalive_connections=5, max_connections=10
                    ),
                )
    return _async_client


async def close_http_client():
    """Close shared httpx client (for use in app lifespan)"""
    global _async_client
    if _async_client is not None:
        await _async_client.aclose()
        _async_client = None


# Configuration helper for API base URL with validation
def get_api_base_url() -> str:
    """Get the API base URL from settings or environment with validation"""
    url = getattr(settings, "API_BASE_URL", "http://localhost:8002")

    # Basic URL validation
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            logger.warning(f"Invalid API_BASE_URL: {url}, using default")
            return "http://localhost:8002"
        return url
    except Exception as e:
        logger.error(f"Error parsing API_BASE_URL {url}: {e}")
        return "http://localhost:8002"


class ChatMessage(BaseModel):
    id: str
    type: str  # 'user', 'assistant', 'system', 'suggestion'
    content: str
    timestamp: datetime
    context: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    message: str
    conversationHistory: List[ChatMessage] = []
    currentTask: Optional[str] = None
    teamContext: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    content: str
    context: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None


class ProactiveSuggestionsRequest(BaseModel):
    context: Dict[str, Any]


@router.post("/respond", response_model=ChatResponse)
async def generate_chat_response(
    request: ChatRequest, db: Session = Depends(get_db)
) -> ChatResponse:
    """
    Generate context-aware chat response using team intelligence
    """
    try:
        # Analyze user intent
        intent = await _analyze_user_intent(request.message)

        # Build enhanced context
        enhanced_context = await _build_enhanced_context(request, intent)

        # Generate response based on intent
        if intent["type"] == "task_query":
            response = await _handle_task_query(intent, enhanced_context)
        elif intent["type"] == "team_query":
            response = await _handle_team_query(intent, enhanced_context)
        elif intent["type"] == "plan_request":
            response = await _handle_plan_request(intent, enhanced_context)
        elif intent["type"] == "code_help":
            response = await _handle_code_help(intent, enhanced_context)
        else:
            response = await _handle_general_query(intent, enhanced_context)

        return response

    except Exception as e:
        logger.error(f"Chat response error: {e}")
        return ChatResponse(
            content=f"I encountered an error: {str(e)}. Let me try a different approach.",
            suggestions=["Show my tasks", "Help with current work", "Generate a plan"],
        )


@router.post("/suggestions/proactive")
async def generate_proactive_suggestions(
    request: ProactiveSuggestionsRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Generate proactive suggestions based on current context
    """
    try:
        # Analyze current context for suggestions
        suggestions = []

        # Check for potential blockers
        if request.context.get("recentChanges"):
            suggestions.extend(
                [
                    "I notice recent changes in multiple files. Would you like me to check for conflicts?",
                    "There might be merge conflicts brewing. Should I check dependencies?",
                ]
            )

        # Check for incomplete work patterns
        if request.context.get("currentFiles"):
            suggestions.extend(
                [
                    "The current files look like they might need testing. Want me to help with that?",
                    "I see some work in progress. Need help finishing up?",
                ]
            )

        # Check team coordination opportunities
        if request.context.get("activeTask"):
            suggestions.extend(
                [
                    "Your current task might overlap with team work. Want to check?",
                    "There could be related work happening. Want to see team activity?",
                ]
            )

        return {"items": suggestions[:3]}  # Limit to top 3 suggestions

    except Exception as e:
        logger.error(f"Proactive suggestions error: {e}")
        return {"items": []}


async def _analyze_user_intent(message: str) -> Dict[str, Any]:
    """Analyze user message to determine intent"""
    message_lower = message.lower()

    # Task-related queries
    if any(
        keyword in message_lower
        for keyword in ["task", "jira", "ticket", "assigned", "priority"]
    ):
        return {
            "type": "task_query",
            "keywords": ["task", "jira", "priority"],
            "confidence": 0.9,
        }

    # Team-related queries
    if any(
        keyword in message_lower
        for keyword in ["team", "colleague", "teammate", "working on", "activity"]
    ):
        return {
            "type": "team_query",
            "keywords": ["team", "activity", "collaboration"],
            "confidence": 0.8,
        }

    # Plan generation requests
    if any(
        keyword in message_lower
        for keyword in ["plan", "how", "implement", "steps", "approach"]
    ):
        return {
            "type": "plan_request",
            "keywords": ["plan", "implementation", "steps"],
            "confidence": 0.85,
        }

    # Code help requests
    if any(
        keyword in message_lower
        for keyword in ["code", "bug", "error", "fix", "debug", "review"]
    ):
        return {
            "type": "code_help",
            "keywords": ["code", "debug", "review"],
            "confidence": 0.8,
        }

    return {"type": "general_query", "keywords": [], "confidence": 0.5}


async def _build_enhanced_context(
    request: ChatRequest, intent: Dict[str, Any]
) -> Dict[str, Any]:
    """Build enhanced context for response generation"""

    enhanced_context = {
        "intent": intent,
        "conversation_history": request.conversationHistory[-5:],  # Last 5 messages
        "current_task": request.currentTask,
        "team_context": request.teamContext or {},
    }

    # Try to add task context if current task is set
    if request.currentTask:
        try:
            # Make async request to existing context API
            api_base = get_api_base_url()
            client = get_http_client()
            response = await client.get(
                f"{api_base}/api/context/task/{request.currentTask}"
            )
            if response.status_code == 200:
                enhanced_context["task_context"] = response.json()
        except Exception as e:
            logger.warning(f"Could not fetch task context: {e}")

    return enhanced_context


async def _handle_task_query(
    intent: Dict[str, Any], context: Dict[str, Any]
) -> ChatResponse:
    """Handle task-related queries"""
    try:
        # Try to get tasks from JIRA API
        try:
            api_base = get_api_base_url()
            client = get_http_client()
            response = await client.get(f"{api_base}/api/jira/tasks")
            if response.status_code == 200:
                data = response.json()
                tasks = data.get("items", [])
            else:
                tasks = []
        except Exception:
            tasks = []

        if not tasks:
            return ChatResponse(
                content="You don't have any assigned tasks right now. Would you like me to help you find work to do?",
                suggestions=[
                    "Show available tasks",
                    "Check team priorities",
                    "Find tasks I can help with",
                ],
            )

        # Sort by priority and format response
        high_priority_tasks = [
            t for t in tasks if t.get("priority") in ["High", "Highest"]
        ]

        content = f"You have {len(tasks)} assigned tasks.\n\n"

        if high_priority_tasks:
            content += "🔴 **High Priority:**\n"
            for task in high_priority_tasks[:2]:
                content += f"• **{task['key']}**: {task['summary']}\n"
            content += "\n"

        content += "📋 **All Tasks:**\n"
        for task in tasks[:5]:
            priority_emoji = (
                "🔴"
                if task.get("priority") in ["High", "Highest"]
                else "🟡" if task.get("priority") == "Medium" else "🟢"
            )
            content += f"{priority_emoji} **{task['key']}**: {task['summary']}\n"

        suggestions = [
            (
                f"Work on {high_priority_tasks[0]['key']}"
                if high_priority_tasks
                else f"Work on {tasks[0]['key']}"
            ),
            "Generate plan for highest priority task",
            "Show task dependencies",
            "Check what teammates are working on",
        ]

        return ChatResponse(content=content, suggestions=suggestions)

    except Exception:
        return ChatResponse(
            content="I had trouble fetching your tasks. Let me try a different approach.",
            suggestions=[
                "Refresh task list",
                "Check JIRA connection",
                "Show cached tasks",
            ],
        )


async def _handle_team_query(
    intent: Dict[str, Any], context: Dict[str, Any]
) -> ChatResponse:
    """Handle team-related queries"""
    try:
        # Try to get team activity
        team_activity = []
        try:
            api_base = get_api_base_url()
            client = get_http_client()
            response = await client.get(f"{api_base}/api/activity/recent")
            if response.status_code == 200:
                data = response.json()
                team_activity = data.get("items", [])
        except Exception as e:
            logger.warning(f"Failed to fetch team activity: {e}")

        if not team_activity:
            return ChatResponse(
                content="I don't have recent team activity data. Let me help you connect with your team.",
                suggestions=[
                    "Check Slack for updates",
                    "Review recent commits",
                    "Show team calendar",
                ],
            )

        content = "🔄 **Recent Team Activity:**\n\n"

        for activity in team_activity[:5]:
            time_ago = _format_time_ago(activity.get("timestamp"))
            content += f"• **{activity.get('author')}** {activity.get('action')} on **{activity.get('target')}** ({time_ago})\n"

        # Add coordination insights
        if context.get("current_task"):
            content += "\n💡 **Tip:** I can help you coordinate with teammates working on related tasks."

        suggestions = [
            "Show detailed team status",
            "Find teammates working on related tasks",
            "Check for coordination opportunities",
            "View team dependencies",
        ]

        return ChatResponse(content=content, suggestions=suggestions)

    except Exception:
        return ChatResponse(
            content="I had trouble getting team information. Let me help you in other ways.",
            suggestions=[
                "Check team chat",
                "Review recent changes",
                "Show project status",
            ],
        )


async def _handle_plan_request(
    intent: Dict[str, Any], context: Dict[str, Any]
) -> ChatResponse:
    """Handle plan generation requests"""
    try:
        current_task = context.get("current_task") or context.get(
            "task_context", {}
        ).get("key")

        if not current_task:
            return ChatResponse(
                content="I'd love to help you create a plan! Which task would you like me to plan for?",
                suggestions=[
                    "Plan for my highest priority task",
                    "Create a general work plan",
                    "Help me break down a complex task",
                ],
            )

        # Get task context for plan generation
        task_context = context.get("task_context", {})

        content = f"I'll create a detailed plan for **{current_task}**.\n\n"
        content += (
            f"**Task**: {task_context.get('summary', 'Task details loading...')}\n\n"
        )

        if task_context.get("description"):
            content += f"**Description**: {task_context['description'][:200]}...\n\n"

        content += (
            "Let me analyze the requirements and generate an implementation plan."
        )

        suggestions = [
            "Generate detailed implementation plan",
            "Show task dependencies first",
            "Break into smaller subtasks",
            "Include testing strategy",
        ]

        return ChatResponse(
            content=content,
            suggestions=suggestions,
            context={"taskKey": current_task, "action": "plan_generation"},
        )

    except Exception:
        return ChatResponse(
            content="I had trouble analyzing the task for planning. Let me help you get started anyway.",
            suggestions=[
                "Tell me about the task manually",
                "Show existing plans",
                "Create simple task breakdown",
            ],
        )


async def _handle_code_help(
    intent: Dict[str, Any], context: Dict[str, Any]
) -> ChatResponse:
    """Handle code-related help requests"""
    try:
        content = "I'm here to help with your code! 👨‍💻\n\n"
        content += "I can assist with:\n"
        content += "• **Code review** - Analyze your changes and suggest improvements\n"
        content += "• **Debugging** - Help identify and fix issues\n"
        content += "• **Implementation** - Guide you through coding tasks\n"
        content += "• **Testing** - Create tests and validate your code\n\n"

        # Add context-specific suggestions
        suggestions = [
            "Review my current changes",
            "Help debug an issue",
            "Generate tests for my code",
            "Suggest code improvements",
            "Check for potential bugs",
        ]

        # If there's a current task, offer task-specific help
        if context.get("current_task"):
            content += f"I can also provide specific help for your current task: **{context['current_task']}**"
            suggestions.insert(0, f"Help implement {context['current_task']}")

        return ChatResponse(content=content, suggestions=suggestions)

    except Exception:
        return ChatResponse(
            content="I'm ready to help with your code! What specific challenge are you facing?",
            suggestions=[
                "Review code",
                "Debug issue",
                "Generate tests",
                "Code suggestions",
            ],
        )


async def _handle_general_query(
    intent: Dict[str, Any], context: Dict[str, Any]
) -> ChatResponse:
    """Handle general queries with contextual awareness"""
    try:
        content = "I'm your autonomous engineering assistant! 🤖\n\n"
        content += "I can help you with:\n"
        content += "• **Task Management** - Show your JIRA tasks and priorities\n"
        content += "• **Team Coordination** - Keep you updated on team activity\n"
        content += (
            "• **Implementation Planning** - Generate detailed plans for your work\n"
        )
        content += "• **Code Assistance** - Review, debug, and improve your code\n"
        content += (
            "• **Context Intelligence** - Connect related work across your team\n\n"
        )

        # Add personalized suggestions based on context
        suggestions = []

        if context.get("current_task"):
            suggestions.extend(
                [
                    f"Continue work on {context['current_task']}",
                    "Generate plan for current task",
                ]
            )

        suggestions.extend(
            [
                "Show my tasks",
                "What is my team working on?",
                "Help me with current work",
                "Review recent changes",
            ]
        )

        return ChatResponse(content=content, suggestions=suggestions)

    except Exception:
        return ChatResponse(
            content="I'm here to help with your engineering work! How can I assist you today?",
            suggestions=["Show tasks", "Team status", "Generate plan", "Code help"],
        )


def _format_time_ago(timestamp: str) -> str:
    """Format timestamp as time ago"""
    if not timestamp:
        return "unknown time"

    try:
        now = datetime.now(timezone.utc)

        # Handle different timestamp formats
        if isinstance(timestamp, str):
            try:
                # Try ISO format first
                ts_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                try:
                    # Try UNIX timestamp (seconds)
                    ts_dt = datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
                except (ValueError, TypeError):
                    return "unknown time"
        elif isinstance(timestamp, datetime):
            ts_dt = timestamp
            if ts_dt.tzinfo is None:
                ts_dt = ts_dt.replace(tzinfo=timezone.utc)
        else:
            return "unknown time"

        # Calculate time difference
        diff = now - ts_dt
        seconds = int(diff.total_seconds())

        if seconds < 0:
            return "in the future"
        elif seconds < 60:
            return f"{seconds} second{'s' if seconds != 1 else ''} ago"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 604800:  # 7 days
            days = seconds // 86400
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif seconds < 2592000:  # 30 days
            weeks = seconds // 604800
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        elif seconds < 31536000:  # 365 days
            months = (
                seconds // 2592000
            )  # 30 days for more accurate monthly calculations
            return f"{months} month{'s' if months != 1 else ''} ago"
        else:
            years = seconds // 31536000
            return f"{years} year{'s' if years != 1 else ''} ago"

    except Exception as e:
        logger.warning(f"Error formatting timestamp {timestamp}: {e}")
        return "recently"
