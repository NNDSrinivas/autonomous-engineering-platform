"""
Intent Classifier - Understand What the User Wants

Uses LLM to classify user intent from their message.

Intent categories:
- jira.list: List Jira tasks
- jira.deep_dive: Get details on specific task
- jira.work.start: Start working on a task
- jira.create: Create new Jira issue
- jira.update: Update existing issue
- code.explain: Explain code
- code.refactor: Refactor code
- code.fix: Fix a bug
- code.generate: Generate new code
- search.codebase: Search codebase
- search.org: Search org artifacts
- chat: General conversation
- ambiguous: Unclear intent
"""

import logging
from typing import Dict, Any, Optional
import re

logger = logging.getLogger(__name__)


async def classify_intent(
    message: str,
    context: Dict[str, Any],
    previous_state: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Classify the user's intent.
    
    Args:
        message: User's message
        context: Full context from context_builder
        previous_state: Previous user state
    
    Returns:
        {
            "type": str,              # Intent category
            "confidence": float,      # 0.0 to 1.0
            "targets": List[str],     # Specific artifacts (Jira keys, files, etc.)
            "question": str           # Clarifying question if ambiguous
        }
    """
    
    message_lower = message.lower()
    
    logger.info(f"[INTENT] Classifying: '{message[:50]}...'")
    
    # ---------------------------------------------------------
    # Pattern 1: Jira issue mentioned explicitly
    # ---------------------------------------------------------
    jira_keys = _extract_jira_keys(message)
    if jira_keys:
        logger.info(f"[INTENT] Found Jira keys: {jira_keys}")
        
        # Check if user wants details or to work on it
        if any(word in message_lower for word in ["details", "info", "about", "explain", "tell me"]):
            return {
                "type": "jira.deep_dive",
                "confidence": 0.95,
                "targets": jira_keys,
                "question": None
            }
        elif any(word in message_lower for word in ["work on", "start", "implement", "fix", "code"]):
            return {
                "type": "jira.work.start",
                "confidence": 0.9,
                "targets": jira_keys,
                "question": None
            }
        else:
            # Default to deep dive
            return {
                "type": "jira.deep_dive",
                "confidence": 0.8,
                "targets": jira_keys,
                "question": None
            }
    
    # ---------------------------------------------------------
    # Pattern 2: List Jira tasks
    # ---------------------------------------------------------
    if any(phrase in message_lower for phrase in [
        "my tasks", "my tickets", "my issues",
        "jira tasks", "assigned to me",
        "what should i work on", "what's on my plate",
        "show me my", "list my"
    ]):
        logger.info("[INTENT] Detected jira.list")
        return {
            "type": "jira.list",
            "confidence": 0.95,
            "targets": [],
            "question": None
        }
    
    # ---------------------------------------------------------
    # Pattern 3: Reference to "this task" / "that task"
    # ---------------------------------------------------------
    if any(phrase in message_lower for phrase in [
        "this task", "that task", "this one", "that one",
        "this ticket", "that ticket", "this jira", "this issue"
    ]):
        # Check if we have a current task in state
        current_task = context.get("state", {}).get("current_task")
        last_shown = context.get("state", {}).get("last_shown_issues", [])
        
        if current_task:
            logger.info(f"[INTENT] Reference to current task: {current_task.get('key')}")
            return {
                "type": "jira.deep_dive",
                "confidence": 0.9,
                "targets": [current_task.get("key")],
                "question": None
            }
        elif last_shown:
            # Assume first in list
            logger.info(f"[INTENT] Reference to first shown task: {last_shown[0].get('key')}")
            return {
                "type": "jira.deep_dive",
                "confidence": 0.7,
                "targets": [last_shown[0].get("key")],
                "question": f"Just to confirm, are you asking about {last_shown[0].get('key')}?"
            }
        else:
            logger.info("[INTENT] Ambiguous reference to 'this task'")
            return {
                "type": "ambiguous",
                "confidence": 0.0,
                "targets": [],
                "question": "Which task are you referring to? Could you mention the Jira key (like SCRUM-1)?"
            }
    
    # ---------------------------------------------------------
    # Pattern 4: Code-related intents
    # ---------------------------------------------------------
    if any(word in message_lower for word in ["explain this code", "what does this do", "refactor this"]):
        logger.info("[INTENT] Detected code intent")
        return {
            "type": "code.explain",
            "confidence": 0.85,
            "targets": [],
            "question": None
        }
    
    # ---------------------------------------------------------
    # Pattern 5: Create Jira issue
    # ---------------------------------------------------------
    if any(phrase in message_lower for phrase in [
        "create a ticket", "create a task", "create an issue",
        "file a bug", "log a bug", "new jira"
    ]):
        logger.info("[INTENT] Detected jira.create")
        return {
            "type": "jira.create",
            "confidence": 0.9,
            "targets": [],
            "question": None
        }
    
    # ---------------------------------------------------------
    # Default: General chat
    # ---------------------------------------------------------
    logger.info("[INTENT] Defaulting to chat")
    return {
        "type": "chat",
        "confidence": 0.6,
        "targets": [],
        "question": None
    }


def _extract_jira_keys(text: str) -> list:
    """Extract Jira issue keys like SCRUM-1, ENG-102, etc."""
    pattern = r'\b([A-Z][A-Z0-9]+-\d+)\b'
    matches = re.findall(pattern, text)
    return list(set(matches))
