"""
Adaptive Learning Engine

Learns from user behavior and code patterns to personalize NAVI.
This is what makes NAVI get smarter every day.
"""

import logging
from typing import Dict, Any, List
from collections import Counter

from .memory_capture import (
    capture_user_preference,
    capture_code_pattern,
    capture_coding_style_observation
)
from .memory_retrieval import retrieve_user_memories, retrieve_task_memories

logger = logging.getLogger(__name__)


class LearningEngine:
    """
    Adaptive learning engine that learns from user interactions.
    """
    
    def __init__(self, db_session):
        """
        Initialize learning engine.
        
        Args:
            db_session: Database session
        """
        self.db = db_session
        self.observation_cache = {}  # Track recurring patterns
    
    async def process_learning(
        self,
        user_id: str,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> bool:
        """
        Process a learning event.
        
        Args:
            user_id: User ID
            event_type: Type of event (approval, rejection, code_change, etc.)
            event_data: Event details
            
        Returns:
            True if learning occurred
        """
        
        if event_type == "approval":
            return await learn_from_approval(user_id, event_data, self.db)
        elif event_type == "rejection":
            return await learn_from_rejection(user_id, event_data, self.db)
        elif event_type == "code_change":
            return await learn_from_code_change(user_id, event_data, self.db)
        elif event_type == "explicit_preference":
            return await learn_explicit_preference(user_id, event_data, self.db)
        else:
            logger.warning(f"Unknown learning event type: {event_type}")
            return False


async def learn_from_approval(
    user_id: str,
    approval_data: Dict[str, Any],
    db_session = None
) -> bool:
    """
    Learn from user approving a change.
    
    When user approves a diff, NAVI learns:
    - Code patterns they prefer
    - Coding style preferences
    - Error handling approaches
    - Testing patterns
    
    Examples:
        await learn_from_approval(
            user_id="user@example.com",
            approval_data={
                "task_id": "SCRUM-123",
                "files_changed": ["backend/api/navi.py"],
                "diff": "...added null checks...",
                "pattern_detected": "null_checking"
            }
        )
    
    Args:
        user_id: User ID
        approval_data: Data about what was approved
        db_session: Database session
        
    Returns:
        True if learning occurred
    """
    
    try:
        # Extract patterns from the approved change
        patterns = _extract_code_patterns(approval_data.get("diff", ""))
        
        for pattern in patterns:
            # Check if we've seen this pattern before
            cache_key = f"{user_id}_{pattern['type']}"
            frequency = approval_data.get("_observation_cache", {}).get(cache_key, 0) + 1
            
            # After seeing pattern 3+ times, capture as preference
            if frequency >= 3:
                await capture_coding_style_observation(
                    user_id=user_id,
                    style_aspect=pattern["type"],
                    observed_behavior=pattern["description"],
                    frequency=frequency,
                    db_session=db_session
                )
                
                logger.info(f"Learned coding preference for {user_id}: {pattern['type']}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error learning from approval: {e}", exc_info=True)
        return False


async def learn_from_rejection(
    user_id: str,
    rejection_data: Dict[str, Any],
    db_session = None
) -> bool:
    """
    Learn from user rejecting a change.
    
    When user rejects a diff, NAVI learns what NOT to do.
    
    Examples:
        await learn_from_rejection(
            user_id="user@example.com",
            rejection_data={
                "task_id": "SCRUM-123",
                "reason": "Don't use any keyword, prefer explicit imports",
                "pattern_rejected": "wildcard_imports"
            }
        )
    
    Args:
        user_id: User ID
        rejection_data: Data about what was rejected
        db_session: Database session
        
    Returns:
        True if learning occurred
    """
    
    try:
        reason = rejection_data.get("reason", "")
        pattern = rejection_data.get("pattern_rejected", "")
        
        if reason or pattern:
            # Capture as negative preference
            await capture_user_preference(
                user_id=user_id,
                preference_key=f"avoid_{pattern}" if pattern else "rejection",
                preference_value="false",
                context=f"User rejected: {reason}",
                learned_from="explicit",
                db_session=db_session
            )
            
            logger.info(f"Learned negative preference for {user_id}: avoid {pattern}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error learning from rejection: {e}", exc_info=True)
        return False


async def learn_from_code_change(
    user_id: str,
    change_data: Dict[str, Any],
    db_session = None
) -> bool:
    """
    Learn from observing code changes in the workspace.
    
    NAVI observes patterns in how user writes code.
    
    Examples:
        await learn_from_code_change(
            user_id="user@example.com",
            change_data={
                "file_path": "backend/api/navi.py",
                "change_type": "function_added",
                "patterns": ["async_await", "type_hints", "docstrings"]
            }
        )
    
    Args:
        user_id: User ID
        change_data: Data about the code change
        db_session: Database session
        
    Returns:
        True if learning occurred
    """
    
    try:
        patterns = change_data.get("patterns", [])
        file_path = change_data.get("file_path", "")
        
        for pattern in patterns:
            # Capture workspace pattern
            await capture_code_pattern(
                user_id=user_id,
                pattern_type=pattern,
                pattern_description=f"User uses {pattern} in {file_path}",
                file_path=file_path,
                db_session=db_session
            )
        
        return True
        
    except Exception as e:
        logger.error(f"Error learning from code change: {e}", exc_info=True)
        return False


async def learn_explicit_preference(
    user_id: str,
    preference_data: Dict[str, Any],
    db_session = None
) -> bool:
    """
    Learn from user explicitly stating a preference.
    
    Examples:
        User says: "I prefer TypeScript over JavaScript"
        User says: "Always add null checks"
        User says: "Use async/await instead of .then()"
    
    Args:
        user_id: User ID
        preference_data: Preference details
        db_session: Database session
        
    Returns:
        True if learning occurred
    """
    
    try:
        preference_key = preference_data.get("key", "")
        preference_value = preference_data.get("value", "")
        context = preference_data.get("context", "")
        
        await capture_user_preference(
            user_id=user_id,
            preference_key=preference_key,
            preference_value=preference_value,
            context=context,
            learned_from="explicit",
            db_session=db_session
        )
        
        logger.info(f"Learned explicit preference for {user_id}: {preference_key} = {preference_value}")
        return True
        
    except Exception as e:
        logger.error(f"Error learning explicit preference: {e}", exc_info=True)
        return False


async def learn_coding_style(
    user_id: str,
    db_session = None
) -> Dict[str, Any]:
    """
    Analyze past approvals to extract coding style preferences.
    
    This runs periodically to detect patterns across all approvals.
    
    Examples:
        style = await learn_coding_style(user_id="user@example.com")
        # Returns:
        # {
        #   "prefers_async_await": True,
        #   "uses_type_hints": True,
        #   "null_check_style": "explicit",
        #   "error_handling": "try_catch_with_logging"
        # }
    
    Args:
        user_id: User ID
        db_session: Database session
        
    Returns:
        Dictionary of detected style preferences
    """
    
    try:
        # Retrieve all approved task memories
        approved_tasks = await retrieve_task_memories(
            user_id=user_id,
            approved_only=True,
            limit=50,
            db_session=db_session
        )
        
        # Analyze patterns
        patterns = Counter()
        for task in approved_tasks:
            if task.code_diff:
                detected = _extract_code_patterns(task.code_diff)
                for pattern in detected:
                    patterns[pattern["type"]] += 1
        
        # Convert to style guide
        style_guide = {}
        for pattern_type, count in patterns.most_common(10):
            if count >= 3:  # Must appear 3+ times
                style_guide[pattern_type] = True
        
        logger.info(f"Detected {len(style_guide)} style preferences for {user_id}")
        return style_guide
        
    except Exception as e:
        logger.error(f"Error learning coding style: {e}", exc_info=True)
        return {}


async def detect_patterns(
    user_id: str,
    context: str,
    db_session = None
) -> List[str]:
    """
    Detect which learned patterns apply to the current context.
    
    This is used to apply learned preferences to new tasks.
    
    Examples:
        patterns = await detect_patterns(
            user_id="user@example.com",
            context="implementing authentication endpoint"
        )
        # Returns: ["add_type_hints", "use_async_await", "add_null_checks"]
    
    Args:
        user_id: User ID
        context: Current context/task description
        db_session: Database session
        
    Returns:
        List of applicable pattern names
    """
    
    try:
        # Retrieve relevant memories
        memories = await retrieve_user_memories(
            user_id=user_id,
            query=context,
            limit=20,
            db_session=db_session
        )
        
        # Extract pattern recommendations
        patterns = []
        for memory in memories:
            if hasattr(memory, 'preference_key'):
                # Check if this preference applies
                if memory.confidence > 0.7:
                    patterns.append(memory.preference_key)
        
        logger.info(f"Detected {len(patterns)} applicable patterns for context")
        return patterns
        
    except Exception as e:
        logger.error(f"Error detecting patterns: {e}", exc_info=True)
        return []


def _extract_code_patterns(code_diff: str) -> List[Dict[str, str]]:
    """
    Extract code patterns from a diff.
    
    Looks for:
    - async/await usage
    - Type hints
    - Null checks
    - Error handling patterns
    - Import styles
    - Function structure
    
    Args:
        code_diff: Code diff string
        
    Returns:
        List of detected patterns
    """
    
    patterns = []
    
    # Async/await detection
    if "async def" in code_diff or "await " in code_diff:
        patterns.append({
            "type": "async_await",
            "description": "Uses async/await for asynchronous code"
        })
    
    # Type hints
    if "->" in code_diff or ": str" in code_diff or ": int" in code_diff:
        patterns.append({
            "type": "type_hints",
            "description": "Adds explicit type hints"
        })
    
    # Null/None checks
    if "if not" in code_diff or "is None" in code_diff or "is not None" in code_diff:
        patterns.append({
            "type": "null_checking",
            "description": "Adds explicit null/None checks"
        })
    
    # Try-catch error handling
    if "try:" in code_diff and "except" in code_diff:
        patterns.append({
            "type": "try_catch",
            "description": "Uses try-catch for error handling"
        })
    
    # Logging
    if "logger." in code_diff:
        patterns.append({
            "type": "logging",
            "description": "Adds logging statements"
        })
    
    # Docstrings
    if '"""' in code_diff or "'''" in code_diff:
        patterns.append({
            "type": "docstrings",
            "description": "Includes docstrings"
        })
    
    return patterns
