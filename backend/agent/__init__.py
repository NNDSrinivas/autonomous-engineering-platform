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
    get_current_task
)
from .context_builder import build_context
from .intent_classifier import classify_intent
from .planner import generate_plan
from .tool_executor import execute_tool

__all__ = [
    "run_agent_loop",
    "get_user_state",
    "update_user_state",
    "clear_user_state",
    "set_current_task",
    "get_current_task",
    "build_context",
    "classify_intent",
    "generate_plan",
    "execute_tool",
]

