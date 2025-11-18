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
    get_active_file
)
from .context_builder import build_context
from .intent_classifier import classify_intent, extract_jira_keys, extract_file_references
from .planner import generate_plan, is_read_only_plan, requires_user_approval, format_plan_for_approval
from .tool_executor import execute_tool
from .rag import retrieve_rag_context, format_rag_context_for_llm
from .memory_retriever import retrieve_memories, retrieve_recent_memories
from .org_retriever import retrieve_org_context
from .workspace_retriever import retrieve_workspace_context

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
    "extract_jira_keys",
    "extract_file_references",
    "generate_plan",
    "is_read_only_plan",
    "requires_user_approval",
    "format_plan_for_approval",
    "execute_tool",
    "retrieve_rag_context",
    "format_rag_context_for_llm",
    "retrieve_memories",
    "retrieve_recent_memories",
    "retrieve_org_context",
    "retrieve_workspace_context",
]

