"""
NAVI Agent Core - Autonomous Engineering Assistant Architecture

This package implements NAVI's agent loop with:
- Dynamic reasoning (not scripted responses)
- Memory-driven context awareness
- Tool-use capabilities
- Multi-step planning
- Intent classification
- RAG-based artifact retrieval
"""

from .agent_loop import run_agent_loop
from .state_manager import (
    get_user_state,
    update_user_state,
    clear_user_state,
    set_current_task,
    get_current_task,
    set_pending_action,
    get_pending_action,
    clear_pending_action,
    set_current_jira,
    get_current_jira,
    set_active_file,
    get_active_file,
)
from .context_builder import build_context
from .intent_classifier import classify_intent
from .planner_v3 import SimplePlanner
from .tool_executor import execute_tool, get_available_tools, is_write_operation
from .rag import retrieve_rag_context, format_rag_context_for_llm
from .memory_retriever import retrieve_memories, retrieve_recent_memories
from .org_retriever import retrieve_org_context
from .workspace_retriever import retrieve_workspace_context


def generate_plan(intent, context):
    """Backwards-compatible function wrapper."""
    planner = SimplePlanner()
    return planner.plan(intent, context)


__all__ = [
    "run_agent_loop",
    "get_user_state",
    "update_user_state",
    "clear_user_state",
    "set_current_task",
    "get_current_task",
    "set_pending_action",
    "get_pending_action",
    "clear_pending_action",
    "set_current_jira",
    "get_current_jira",
    "set_active_file",
    "get_active_file",
    "build_context",
    "classify_intent",
    "generate_plan",
    "execute_tool",
    "get_available_tools",
    "is_write_operation",
    "retrieve_rag_context",
    "format_rag_context_for_llm",
    "retrieve_memories",
    "retrieve_recent_memories",
    "retrieve_org_context",
    "retrieve_workspace_context",
    # Tools
    "read_file",
    "create_file",
    "edit_file",
    "apply_diff",
    "search_repo",
    "run_command",
    "list_assigned_issues_for_user",
    "github_create_branch",
    "github_create_pr",
]
