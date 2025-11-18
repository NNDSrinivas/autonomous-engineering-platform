"""
State Manager - Per-User Conversation State

Tracks what the user is currently doing across messages:
- Active Jira task
- Pending actions (waiting for approval)
- Last shown issues/artifacts
- Conversation intent
- Multi-step plan progress

This is IN-MEMORY for now (can be moved to Redis/DB for persistence).
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# In-memory state store: user_id -> state dict
# In production, this would be Redis or database
_USER_STATES: Dict[str, Dict[str, Any]] = {}


async def get_user_state(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the current state for a user.
    
    Returns None if no state exists (first message or cleared).
    """
    state = _USER_STATES.get(user_id)
    if state:
        logger.info(f"[STATE] Retrieved state for user={user_id}: {list(state.keys())}")
    return state


async def update_user_state(user_id: str, updates: Dict[str, Any]) -> None:
    """
    Update user state with new information.
    
    This merges the updates into existing state (doesn't replace).
    """
    if user_id not in _USER_STATES:
        _USER_STATES[user_id] = {}
    
    _USER_STATES[user_id].update(updates)
    _USER_STATES[user_id]["last_updated"] = datetime.utcnow().isoformat()
    
    logger.info(f"[STATE] Updated state for user={user_id}: {list(updates.keys())}")


def clear_user_state(user_id: str) -> None:
    """
    Clear user state (after completing a conversation flow).
    """
    if user_id in _USER_STATES:
        del _USER_STATES[user_id]
        logger.info(f"[STATE] Cleared state for user={user_id}")


async def set_current_task(user_id: str, task_key: str, task_summary: str = None) -> None:
    """
    Set the user's currently active Jira task.
    """
    await update_user_state(user_id, {
        "current_task": {
            "key": task_key,
            "summary": task_summary,
            "set_at": datetime.utcnow().isoformat()
        }
    })


async def get_current_task(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the user's currently active Jira task.
    """
    state = await get_user_state(user_id)
    return state.get("current_task") if state else None


async def set_last_shown_issues(user_id: str, issues: list) -> None:
    """
    Remember the last list of Jira issues shown to the user.
    
    This enables "the first one", "the second task", etc. references.
    """
    await update_user_state(user_id, {
        "last_shown_issues": [
            {"key": issue.get("key"), "summary": issue.get("summary")}
            for issue in issues
        ]
    })


async def get_last_shown_issues(user_id: str) -> list:
    """
    Get the last list of Jira issues shown to the user.
    """
    state = await get_user_state(user_id)
    return state.get("last_shown_issues", []) if state else []
