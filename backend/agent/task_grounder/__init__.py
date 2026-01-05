"""
Task Grounding System

Deterministic task grounding that converts user intents into structured,
executable tasks without LLM guessing or validation errors.

This system eliminates the "validation error" problem by providing clean,
structured inputs to the planner.
"""

from .types import GroundingResult, GroundedTask, Diagnostic, Clarification
from .fixProblemsGrounder import ground_fix_problems
from .deployGrounder import ground_deploy

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def ground_task(intent: Any, context: Dict[str, Any]) -> GroundingResult:
    """
    Main entry point for task grounding.

    Takes a classified intent and workspace context, returns a grounded task
    ready for planner execution or requests clarification/rejection.

    Args:
        intent: Classified intent object from intent classifier
        context: Workspace context with diagnostics, files, etc.

    Returns:
        GroundingResult with ready task, clarification, or rejection
    """
    # Extract intent information
    intent_family = getattr(intent, "family", None)
    intent_kind = getattr(intent, "kind", None)

    # Convert to string for routing
    family_str = intent_family.value if intent_family else str(intent_family)
    kind_str = intent_kind.value if intent_kind else str(intent_kind)

    logger.info(f"Grounding task for intent: {family_str}/{kind_str}")

    # Determine intent type from classification
    intent_type = _determine_intent_type(family_str, kind_str, context)

    # Route to specific grounder based on intent type
    if intent_type == "FIX_PROBLEMS":
        return await ground_fix_problems(context)
    elif intent_type == "DEPLOY":
        return ground_deploy(intent, context)

    # Future intents will be added here:
    # elif intent_type == "RUN_TESTS":
    #     return ground_run_tests(context)

    else:
        logger.warning(
            f"No grounding logic available for intent: {family_str}/{kind_str}"
        )
        return GroundingResult(
            type="rejected",
            reason=f"Intent '{family_str}/{kind_str}' is not yet supported by the task grounding system.",
        )


def _determine_intent_type(family: str, kind: str, context: Dict[str, Any]) -> str:
    """
    Determine the intent type for grounding routing.

    Maps classified intents to grounding modules.
    """
    message = context.get("message", "").lower()

    # FIX_PROBLEMS detection
    if family == "ENGINEERING" and "fix" in kind.lower():
        return "FIX_PROBLEMS"

    # Message-based FIX_PROBLEMS detection
    fix_keywords = [
        "fix",
        "solve",
        "resolve",
        "debug",
        "error",
        "problem",
        "issue",
        "diagnostic",
    ]
    if any(keyword in message for keyword in fix_keywords):
        # Validate we have diagnostics to fix
        if context.get("diagnostics_count", 0) > 0:
            return "FIX_PROBLEMS"

    # DEPLOY detection
    if "deploy" in kind.lower() or family == "DEPLOYMENT":
        return "DEPLOY"

    # Message-based DEPLOY detection
    deploy_keywords = ["deploy", "deployment", "publish", "release", "ship", "launch"]
    if any(keyword in message for keyword in deploy_keywords):
        return "DEPLOY"

    # Default: unknown intent
    return "UNKNOWN"


__all__ = [
    "ground_task",
    "GroundingResult",
    "GroundedTask",
    "Diagnostic",
    "Clarification",
]
