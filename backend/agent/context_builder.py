"""
Context Builder - Aggregate All Context Sources (STEP C Enhanced)

Combines context from:
- Workspace (files, code, project)
- Organization (Jira, Slack, Confluence, GitHub, Zoom)
- Memory (user profile, past interactions, tasks)
- State (current task, pending actions)
- RAG (ranked and compressed context)

Produces a unified context dictionary for the LLM with intelligent compression.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def build_context(
    workspace_ctx: Dict[str, Any],
    org_ctx: Dict[str, Any],
    memory_ctx: Dict[str, Any],
    state: Optional[Dict[str, Any]],
    current_message: str,
    rag_results: Optional[list] = None
) -> Dict[str, Any]:
    """
    Build unified context for the LLM.
    
    Args:
        workspace_ctx: Workspace context from workspace_retriever
        org_ctx: Org context from org_retriever
        memory_ctx: Memory context from memory_retriever
        state: User state from state_manager
        current_message: Current user message
        rag_results: Optional pre-computed RAG results
    
    Returns:
        Unified context dictionary with all relevant information
    """
    
    logger.info("[CONTEXT] Building unified context")
    
    context = {
        "workspace": workspace_ctx,
        "organization": org_ctx,
        "memory": memory_ctx,
        "state": state or {},
        "current_message": current_message,
        "rag_results": rag_results or []
    }
    
    # Build a combined text summary for LLM prompt injection
    context["combined"] = _build_combined_text(context)
    
    # Build RAG-formatted context if available
    if rag_results:
        from backend.agent.rag import format_rag_context_for_llm
        context["rag_formatted"] = format_rag_context_for_llm(rag_results)
    else:
        context["rag_formatted"] = ""
    
    logger.info(f"[CONTEXT] Built context with {len(context['combined'])} chars, "
               f"{len(rag_results) if rag_results else 0} RAG chunks")
    return context


def _build_combined_text(context: Dict[str, Any]) -> str:
    """
    Build a human-readable text summary of all context.
    
    This gets injected into the LLM prompt.
    Prioritizes most important context to fit in token limits.
    """
    
    parts = []
    
    # ---------------------------------------------------------
    # Priority 1: User state / current task
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
    # Priority 2: RAG results (if available)
    # ---------------------------------------------------------
    rag_formatted = context.get("rag_formatted", "")
    if rag_formatted:
        parts.append(rag_formatted)
        parts.append("\n")
    else:
        # Fallback: manual context aggregation
        
        # Jira issues
        jira_issues = context.get("organization", {}).get("jira_issues", [])
        if jira_issues:
            parts.append("## Relevant Jira Issues\n\n")
            for issue in jira_issues[:5]:  # Top 5
                parts.append(f"- **{issue.get('key')}**: {issue.get('summary')}\n")
                if issue.get("content"):
                    content = issue.get("content", "")[:200]
                    parts.append(f"  {content}...\n")
            parts.append("\n")
        
        # Slack threads
        slack_threads = context.get("organization", {}).get("slack_threads", [])
        if slack_threads:
            parts.append("## Related Slack Discussions\n\n")
            for thread in slack_threads[:3]:
                parts.append(f"- **{thread.get('channel')}**: {thread.get('content', '')[:150]}...\n")
            parts.append("\n")
        
        # Confluence pages
        conf_pages = context.get("organization", {}).get("confluence_pages", [])
        if conf_pages:
            parts.append("## Related Documentation\n\n")
            for page in conf_pages[:2]:
                parts.append(f"- **{page.get('title')}**: {page.get('content', '')[:150]}...\n")
            parts.append("\n")
        
        # Task memories
        task_memories = context.get("memory", {}).get("tasks", [])
        if task_memories:
            parts.append("## Relevant Task History\n\n")
            for mem in task_memories[:3]:  # Top 3
                parts.append(f"- {mem.get('title')}: {mem.get('content', '')[:150]}...\n")
            parts.append("\n")
    
    # ---------------------------------------------------------
    # Priority 3: User profile / preferences
    # ---------------------------------------------------------
    profile = context.get("memory", {}).get("user_profile", [])
    if profile:
        parts.append("## User Preferences\n\n")
        for pref in profile[:2]:  # Top 2
            parts.append(f"- {pref.get('title')}: {pref.get('content')}\n")
        parts.append("\n")
    
    # ---------------------------------------------------------
    # Priority 4: Workspace info (if relevant)
    # ---------------------------------------------------------
    workspace = context.get("workspace", {})
    
    # New: filesystem tree snapshot for project overview questions
    if workspace.get("tree") and workspace.get("kind") == "filesystem":
        parts.append("## Project Structure\n\n")
        parts.append(f"Repository: {workspace.get('repo_root', 'Unknown')}\n\n")
        parts.append("```\n")
        parts.append(workspace["tree"])
        parts.append("\n```\n\n")
        
        # Include README content if available
        readme = workspace.get("readme", "")
        if readme.strip():
            parts.append("## Project README\n\n")
            parts.append(readme)
            parts.append("\n\n")
    
    if workspace.get("active_file"):
        parts.append(f"## Active File\n\n{workspace['active_file']}\n\n")
    
    if workspace.get("selected_text"):
        selected = workspace['selected_text']
        if len(selected) > 500:
            selected = selected[:500] + "..."
        parts.append(f"## Selected Code\n\n```\n{selected}\n```\n\n")
    
    if workspace.get("git_branch"):
        parts.append(f"## Git Branch\n\n{workspace['git_branch']}\n\n")
    
    return "".join(parts)
