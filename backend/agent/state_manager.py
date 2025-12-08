"""
State Manager - Per-User Conversation State

Tracks what the user is currently doing across messages:
- Active Jira task / current_jira
- Pending actions (waiting for approval)
- Last shown issues/artifacts
- Last action taken
- Conversation intent
- Multi-step plan progress
- Active workspace file

This enables NAVI to understand continuations like:
- "yes" (approve pending action)
- "continue" (next step in plan)
- "this task" (refers to current_jira)

This is IN-MEMORY for now (can be moved to Redis/DB for persistence).
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# In-memory state store: user_id -> state dict
# In production, this would be Redis or database
_USER_STATES: Dict[str, Dict[str, Any]] = {}


async def get_user_state(user_id: str) -> Dict[str, Any]:
    """
    Get the current state for a user.

    Returns empty dict if no state exists (first message or cleared).
    """
    state = _USER_STATES.get(user_id, {})
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


async def set_current_task(
    user_id: str, task_key: str, task_summary: Optional[str] = None
) -> None:
    """
    Set the user's currently active Jira task.
    """
    await update_user_state(
        user_id,
        {
            "current_task": {
                "key": task_key,
                "summary": task_summary,
                "set_at": datetime.utcnow().isoformat(),
            }
        },
    )


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
    await update_user_state(
        user_id,
        {
            "last_shown_issues": [
                {"key": issue.get("key"), "summary": issue.get("summary")}
                for issue in issues
            ]
        },
    )


async def get_last_shown_issues(user_id: str) -> list:
    """
    Get the last list of Jira issues shown to the user.
    """
    state = await get_user_state(user_id)
    return state.get("last_shown_issues", [])


async def set_pending_action(
    user_id: str,
    action_type: str,
    action_data: Dict[str, Any],
    description: Optional[str] = None,
) -> None:
    """
    Set a pending action waiting for user approval.

    Examples:
    - "Create file X" → user can say "yes" to approve
    - "Apply diff to file Y" → user can say "go ahead"
    - "Run command Z" → user can say "do it"

    Args:
        user_id: User ID
        action_type: Type of action (create_file, apply_diff, run_command, etc.)
        action_data: Action parameters
        description: Human-readable description of the action
    """
    await update_user_state(
        user_id,
        {
            "pending_action": {
                "type": action_type,
                "data": action_data,
                "description": description,
                "created_at": datetime.utcnow().isoformat(),
            }
        },
    )
    logger.info(f"[STATE] Set pending action for user={user_id}: {action_type}")


async def get_pending_action(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the pending action waiting for user approval.
    """
    state = await get_user_state(user_id)
    return state.get("pending_action")


async def clear_pending_action(user_id: str) -> None:
    """
    Clear the pending action after execution or cancellation.
    """
    state = await get_user_state(user_id)
    if "pending_action" in state:
        del state["pending_action"]
        logger.info(f"[STATE] Cleared pending action for user={user_id}")


async def set_last_action(user_id: str, action_type: str, result: str) -> None:
    """
    Record the last action taken by NAVI.

    This enables better continuity and debugging.
    """
    await update_user_state(
        user_id,
        {
            "last_action": {
                "type": action_type,
                "result": result,
                "timestamp": datetime.utcnow().isoformat(),
            }
        },
    )


async def set_current_jira(user_id: str, jira_key: str) -> None:
    """
    Set the current Jira issue being discussed/worked on.

    This enables "this Jira", "that issue" references.
    """
    await update_user_state(
        user_id,
        {
            "current_jira": jira_key,
            "current_jira_set_at": datetime.utcnow().isoformat(),
        },
    )


async def get_current_jira(user_id: str) -> Optional[str]:
    """
    Get the current Jira issue being discussed/worked on.
    """
    state = await get_user_state(user_id)
    return state.get("current_jira")


async def set_active_file(user_id: str, file_path: str) -> None:
    """
    Set the currently active file in workspace.

    This enables "this file", "the current file" references.
    """
    await update_user_state(
        user_id,
        {"active_file": file_path, "active_file_set_at": datetime.utcnow().isoformat()},
    )


async def get_active_file(user_id: str) -> Optional[str]:
    """
    Get the currently active file in workspace.
    """
    state = await get_user_state(user_id)
    return state.get("active_file")
