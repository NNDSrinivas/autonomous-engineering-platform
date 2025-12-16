"""
Memory Capture System

Automatically captures and stores memories from various sources:
- User conversations and preferences
- Code patterns and architecture
- Organizational context (Jira, Slack, etc.)
- Task execution history

This is how NAVI learns over time.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from .memory_types import (
    MemoryEntry,
    MemoryCategory,
    ConversationalMemory,
    WorkspaceMemory,
    OrganizationalMemory,
    TaskMemory,
)

logger = logging.getLogger(__name__)


class MemoryCapture:
    """
    Memory capture engine that automatically stores learned information.
    """

    def __init__(self, db_session):
        """
        Initialize memory capture.

        Args:
            db_session: Database session for storage
        """
        self.db = db_session

    async def capture_memory(self, memory: MemoryEntry) -> bool:
        """
        Store a memory in the database.

        Args:
            memory: Memory entry to store

        Returns:
            True if successfully stored
        """
        try:
            # Generate embedding if not provided
            if not memory.embedding and memory.content:
                memory.embedding = await self._generate_embedding(memory.content)

            # Calculate importance
            from .memory_types import calculate_importance

            memory.importance = calculate_importance(memory)

            # Store in database (pseudo-code, actual DB operation depends on schema)
            # await self.db.execute(
            #     "INSERT INTO navi_memory (...) VALUES (...)",
            #     memory.to_dict()
            # )

            logger.info(
                f"Captured {memory.memory_type.value} memory: {memory.content[:50]}..."
            )
            return True

        except Exception as e:
            logger.error(f"Error capturing memory: {e}", exc_info=True)
            return False

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate vector embedding for text."""
        # Placeholder - integrate with OpenAI embeddings
        # from openai import AsyncOpenAI
        # client = AsyncOpenAI()
        # response = await client.embeddings.create(input=text, model="text-embedding-3-small")
        # return response.data[0].embedding
        return [0.0] * 1536  # Placeholder


async def capture_user_preference(
    user_id: str,
    preference_key: str,
    preference_value: str,
    context: str,
    learned_from: str = "explicit",
    db_session=None,
) -> bool:
    """
    Capture a user preference or coding style preference.

    Examples:
        await capture_user_preference(
            user_id="user@example.com",
            preference_key="language_preference",
            preference_value="typescript",
            context="User said: I prefer TypeScript over JavaScript",
            learned_from="explicit"
        )

    Args:
        user_id: User ID
        preference_key: Preference type (e.g., "language_preference")
        preference_value: Preference value (e.g., "typescript")
        context: Full context of how this was learned
        learned_from: "explicit" (user told us) or "implicit" (observed)
        db_session: Database session

    Returns:
        True if captured successfully
    """

    memory = ConversationalMemory(
        user_id=user_id,
        category=MemoryCategory.USER_PREFERENCE,
        content=context,
        preference_key=preference_key,
        preference_value=preference_value,
        learned_from=learned_from,
        source="user",
        confidence=1.0 if learned_from == "explicit" else 0.7,
        tags=[preference_key, "preference"],
    )

    capture = MemoryCapture(db_session)
    return await capture.capture_memory(memory)


async def capture_code_pattern(
    user_id: str,
    pattern_type: str,
    pattern_description: str,
    file_path: Optional[str] = None,
    example_code: Optional[str] = None,
    db_session=None,
) -> bool:
    """
    Capture a code pattern observed in the workspace.

    Examples:
        await capture_code_pattern(
            user_id="user@example.com",
            pattern_type="error_handling",
            pattern_description="Always use try-catch with detailed error logging",
            file_path="backend/api/navi.py",
            example_code="try:\\n    ...\\nexcept Exception as e:\\n    logger.error(...)"
        )

    Args:
        user_id: User ID
        pattern_type: Type of pattern (architecture, convention, etc.)
        pattern_description: Description of the pattern
        file_path: Optional file where pattern was observed
        example_code: Optional code example
        db_session: Database session

    Returns:
        True if captured successfully
    """

    memory = WorkspaceMemory(
        user_id=user_id,
        category=MemoryCategory.CODE_CONVENTION,
        content=pattern_description,
        pattern_type=pattern_type,
        file_path=file_path,
        example_code=example_code,
        source="code",
        confidence=0.8,
        tags=[pattern_type, "pattern", "code"],
        last_seen=datetime.now(timezone.utc),
    )

    capture = MemoryCapture(db_session)
    return await capture.capture_memory(memory)


async def capture_org_context(
    user_id: str,
    org_system: str,
    org_id: str,
    content: str,
    metadata: Dict[str, Any],
    db_session=None,
) -> bool:
    """
    Capture organizational context from Jira, Slack, Confluence, etc.

    Examples:
        await capture_org_context(
            user_id="user@example.com",
            org_system="slack",
            org_id="C123456_1234567890.123456",
            content="Team decided to use React Query for data fetching",
            metadata={
                "channel": "#backend",
                "author": "tech-lead@example.com",
                "timestamp": "2025-11-17T10:30:00Z"
            }
        )

    Args:
        user_id: User ID
        org_system: System name (jira, slack, confluence, zoom, github)
        org_id: ID in that system
        content: Content/summary
        metadata: Additional metadata
        db_session: Database session

    Returns:
        True if captured successfully
    """

    # Determine category based on system
    category_map = {
        "jira": MemoryCategory.JIRA_CONTEXT,
        "slack": MemoryCategory.SLACK_DISCUSSION,
        "confluence": MemoryCategory.CONFLUENCE_DOC,
        "zoom": MemoryCategory.MEETING_NOTES,
        "github": MemoryCategory.PR_REVIEW,
    }

    memory = OrganizationalMemory(
        user_id=user_id,
        category=category_map.get(org_system, MemoryCategory.SLACK_DISCUSSION),
        content=content,
        org_system=org_system,
        org_id=org_id,
        metadata=metadata,
        source=org_system,
        confidence=0.9,
        tags=[org_system, "org"],
        timestamp=datetime.now(timezone.utc),
    )

    capture = MemoryCapture(db_session)
    return await capture.capture_memory(memory)


async def capture_task_execution(
    user_id: str,
    task_id: str,
    step: str,
    action_taken: str,
    result: str,
    user_approved: Optional[bool] = None,
    error: Optional[str] = None,
    resolution: Optional[str] = None,
    files_changed: Optional[List[str]] = None,
    code_diff: Optional[str] = None,
    db_session=None,
) -> bool:
    """
    Capture task execution history for learning.

    Examples:
        await capture_task_execution(
            user_id="user@example.com",
            task_id="SCRUM-123",
            step="apply_diffs",
            action_taken="Applied diff to add null checks",
            result="Success",
            user_approved=True,
            files_changed=["backend/api/navi.py"]
        )

    Args:
        user_id: User ID
        task_id: Jira key or workflow ID
        step: Workflow step
        action_taken: What NAVI did
        result: Outcome
        user_approved: Whether user approved this action
        error: Error if failed
        resolution: How error was resolved
        files_changed: List of modified files
        code_diff: Code diff if applicable
        db_session: Database session

    Returns:
        True if captured successfully
    """

    memory = TaskMemory(
        user_id=user_id,
        category=MemoryCategory.EXECUTION_TRACE,
        content=f"{step}: {action_taken} → {result}",
        task_id=task_id,
        step=step,
        action_taken=action_taken,
        result=result,
        error=error,
        resolution=resolution,
        user_approved=user_approved,
        files_changed=files_changed or [],
        code_diff=code_diff,
        source="workflow",
        confidence=1.0,
        tags=[task_id, step, "execution"],
    )

    capture = MemoryCapture(db_session)
    return await capture.capture_memory(memory)


async def capture_coding_style_observation(
    user_id: str,
    style_aspect: str,
    observed_behavior: str,
    frequency: int = 1,
    db_session=None,
) -> bool:
    """
    Capture observed coding style patterns from user's approvals.

    This is how NAVI learns implicitly from your behavior.

    Examples:
        await capture_coding_style_observation(
            user_id="user@example.com",
            style_aspect="null_checking",
            observed_behavior="User always approves diffs that add explicit null checks",
            frequency=5
        )

    Args:
        user_id: User ID
        style_aspect: Aspect of style (naming, error_handling, etc.)
        observed_behavior: What was observed
        frequency: How many times observed
        db_session: Database session

    Returns:
        True if captured successfully
    """

    memory = ConversationalMemory(
        user_id=user_id,
        category=MemoryCategory.CODING_STYLE,
        content=observed_behavior,
        preference_key=style_aspect,
        learned_from="implicit",
        source="observation",
        confidence=min(
            0.5 + (frequency * 0.1), 0.95
        ),  # Higher frequency = higher confidence
        tags=[style_aspect, "style", "learned"],
        metadata={"frequency": frequency},
    )

    capture = MemoryCapture(db_session)
    return await capture.capture_memory(memory)
