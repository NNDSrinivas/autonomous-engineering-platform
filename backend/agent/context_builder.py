"""
Context Builder - Aggregate All Context Sources

Combines context from:
- Workspace (files, code, project)
- Organization (Jira, Slack, Confluence, GitHub, Zoom)
- Memory (user profile, past interactions, tasks)
- State (current task, pending actions)

Produces a unified context dictionary for the LLM.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def build_context(
    workspace_ctx: Dict[str, Any],
    org_ctx: Dict[str, Any],
    memory_ctx: Dict[str, Any],
    state: Optional[Dict[str, Any]],
    current_message: str
) -> Dict[str, Any]:
    """
    Build unified context for the LLM.
    
    Args:
        workspace_ctx: Workspace context from workspace_retriever
        org_ctx: Org context from org_retriever
        memory_ctx: Memory context from memory_retriever
        state: User state from state_manager
        current_message: Current user message
    
    Returns:
        Unified context dictionary with all relevant information
    """
    
    logger.info("[CONTEXT] Building unified context")
    
    context = {
        "workspace": workspace_ctx,
        "organization": org_ctx,
        "memory": memory_ctx,
        "state": state or {},
        "current_message": current_message
    }
    
    # Build a combined text summary for LLM prompt injection
    context["combined"] = _build_combined_text(context)
    
    logger.info(f"[CONTEXT] Built context with {len(context['combined'])} chars")
    return context


def _build_combined_text(context: Dict[str, Any]) -> str:
    """
    Build a human-readable text summary of all context.
    
    This gets injected into the LLM prompt.
    """
    
    parts = []
    
    # ---------------------------------------------------------
    # User state / current task
    # ---------------------------------------------------------
    state = context.get("state", {})
    if state.get("current_task"):
        task = state["current_task"]
        parts.append(f"## Current Task\n\n{task.get('key')}: {task.get('summary')}\n")
    
    if state.get("last_shown_issues"):
        issues = state["last_shown_issues"]
        parts.append("## Recently Shown Jira Tasks\n\n")
        for i, issue in enumerate(issues, 1):
            parts.append(f"{i}. {issue.get('key')}: {issue.get('summary')}\n")
        parts.append("\n")
    
    # ---------------------------------------------------------
    # Jira issues
    # ---------------------------------------------------------
    jira_issues = context.get("organization", {}).get("jira_issues", [])
    if jira_issues:
        parts.append("## Relevant Jira Issues\n\n")
        for issue in jira_issues[:5]:  # Top 5
            parts.append(f"- **{issue.get('key')}**: {issue.get('summary')}\n")
            if issue.get("content"):
                # Truncate long content
                content = issue.get("content", "")[:200]
                parts.append(f"  {content}...\n")
        parts.append("\n")
    
    # ---------------------------------------------------------
    # Task memories
    # ---------------------------------------------------------
    task_memories = context.get("memory", {}).get("tasks", [])
    if task_memories:
        parts.append("## Relevant Task History\n\n")
        for mem in task_memories[:3]:  # Top 3
            parts.append(f"- {mem.get('title')}: {mem.get('content', '')[:150]}...\n")
        parts.append("\n")
    
    # ---------------------------------------------------------
    # User profile / preferences
    # ---------------------------------------------------------
    profile = context.get("memory", {}).get("user_profile", [])
    if profile:
        parts.append("## User Preferences\n\n")
        for pref in profile:
            parts.append(f"- {pref.get('title')}: {pref.get('content')}\n")
        parts.append("\n")
    
    # ---------------------------------------------------------
    # Workspace info
    # ---------------------------------------------------------
    workspace = context.get("workspace", {})
    if workspace.get("active_file"):
        parts.append(f"## Active File\n\n{workspace['active_file']}\n\n")
    
    if workspace.get("selected_text"):
        parts.append(f"## Selected Code\n\n```\n{workspace['selected_text'][:500]}\n```\n\n")
    
    return "".join(parts)
