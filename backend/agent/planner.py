"""
Planner - Generate Multi-Step Plans

Based on the classified intent, generates an execution plan.

Plans can be:
- pure_chat: Just respond with text (no tools needed)
- execute_tool: Run a tool immediately
- multi_step: Multiple steps requiring approval

Each plan specifies what tools to use and what approval is needed.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


async def generate_plan(
    intent: Dict[str, Any],
    context: Dict[str, Any],
    previous_state: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate an execution plan based on intent.
    
    Args:
        intent: Classified intent from intent_classifier
        context: Full context
        previous_state: Previous user state
    
    Returns:
        {
            "type": str,                    # pure_chat | execute_tool | multi_step
            "requires_user_approval": bool,  # Whether to wait for confirmation
            "tool": Dict,                    # Tool to execute (if any)
            "explanation": str,              # Explain what will happen
            "steps": List[Dict]              # For multi-step plans
        }
    """
    
    intent_type = intent.get("type")
    logger.info(f"[PLANNER] Generating plan for intent: {intent_type}")
    
    # ---------------------------------------------------------
    # Jira: List tasks
    # ---------------------------------------------------------
    if intent_type == "jira.list":
        return {
            "type": "pure_chat",
            "requires_user_approval": False,
            "tool": None,
            "explanation": None,
            "steps": []
        }
    
    # ---------------------------------------------------------
    # Jira: Deep dive on specific task
    # ---------------------------------------------------------
    if intent_type == "jira.deep_dive":
        targets = intent.get("targets", [])
        if targets:
            return {
                "type": "pure_chat",
                "requires_user_approval": False,
                "tool": None,
                "explanation": None,
                "steps": []
            }
        else:
            return {
                "type": "pure_chat",
                "requires_user_approval": False,
                "tool": None,
                "explanation": None,
                "steps": []
            }
    
    # ---------------------------------------------------------
    # Jira: Start working on task
    # ---------------------------------------------------------
    if intent_type == "jira.work.start":
        targets = intent.get("targets", [])
        if targets:
            task_key = targets[0]
            return {
                "type": "execute_tool",
                "requires_user_approval": True,
                "tool": {
                    "name": "create_branch",
                    "args": {
                        "branch_name": f"feature/{task_key.lower()}"
                    }
                },
                "explanation": f"I'll help you work on {task_key}. Should I create a feature branch `feature/{task_key.lower()}`?",
                "steps": [
                    {"action": "create_branch", "status": "pending"},
                    {"action": "analyze_requirements", "status": "pending"},
                    {"action": "propose_implementation", "status": "pending"}
                ]
            }
        else:
            return _chat_plan("Sure! Which task would you like to work on?")
    
    # ---------------------------------------------------------
    # Jira: Create new issue
    # ---------------------------------------------------------
    if intent_type == "jira.create":
        return {
            "type": "pure_chat",
            "requires_user_approval": False,
            "tool": None,
            "explanation": "I'll help you create a Jira issue. What type? (bug, task, story, epic)",
            "steps": []
        }
    
    # ---------------------------------------------------------
    # Code: Explain
    # ---------------------------------------------------------
    if intent_type == "code.explain":
        return {
            "type": "pure_chat",
            "requires_user_approval": False,
            "tool": None,
            "explanation": None,
            "steps": []
        }
    
    # ---------------------------------------------------------
    # Default: General chat
    # ---------------------------------------------------------
    return _chat_plan()


def _chat_plan(explanation: str = None) -> Dict[str, Any]:
    """Helper to create a pure chat plan."""
    return {
        "type": "pure_chat",
        "requires_user_approval": False,
        "tool": None,
        "explanation": explanation,
        "steps": []
    }
