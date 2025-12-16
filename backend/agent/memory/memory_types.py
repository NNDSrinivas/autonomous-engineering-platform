"""
Memory Types and Schemas

Defines the structure of all memory entries in NAVI's global memory brain.
"""

import logging
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """Types of memories NAVI can store."""

    CONVERSATIONAL = "conversational"  # User preferences, chat history
    WORKSPACE = "workspace"  # Code patterns, architecture
    ORGANIZATIONAL = "organizational"  # Jira, Slack, Confluence, etc.
    TASK = "task"  # Task execution history


class MemoryCategory(Enum):
    """Categories within memory types."""

    # Conversational categories
    USER_PREFERENCE = "user_preference"
    CODING_STYLE = "coding_style"
    COMMUNICATION_STYLE = "communication_style"

    # Workspace categories
    ARCHITECTURE_PATTERN = "architecture_pattern"
    CODE_CONVENTION = "code_convention"
    TEST_PATTERN = "test_pattern"
    FOLDER_STRUCTURE = "folder_structure"

    # Organizational categories
    JIRA_CONTEXT = "jira_context"
    SLACK_DISCUSSION = "slack_discussion"
    CONFLUENCE_DOC = "confluence_doc"
    MEETING_NOTES = "meeting_notes"
    PR_REVIEW = "pr_review"

    # Task categories
    EXECUTION_TRACE = "execution_trace"
    ERROR_RESOLUTION = "error_resolution"
    DECISION_LOG = "decision_log"


@dataclass
class MemoryEntry:
    """
    Base memory entry structure.

    All memories stored by NAVI follow this schema.
    """

    id: Optional[str] = None
    user_id: str = ""
    memory_type: MemoryType = MemoryType.CONVERSATIONAL
    category: MemoryCategory = MemoryCategory.USER_PREFERENCE

    content: str = ""
    embedding: Optional[List[float]] = None

    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = ""  # slack, jira, code, user, etc.

    importance: float = 0.5  # 0.0 to 1.0
    confidence: float = 1.0  # How confident we are in this memory

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    accessed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    access_count: int = 0

    tags: List[str] = field(default_factory=list)
    related_memories: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "memory_type": self.memory_type.value,
            "category": self.category.value,
            "content": self.content,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "source": self.source,
            "importance": self.importance,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "access_count": self.access_count,
            "tags": self.tags,
            "related_memories": self.related_memories,
        }

    def update_access(self):
        """Update access tracking."""
        self.accessed_at = datetime.now(timezone.utc)
        self.access_count += 1


@dataclass
class ConversationalMemory(MemoryEntry):
    """
    Memory from user conversations and preferences.

    Examples:
    - "I prefer TypeScript over JavaScript"
    - "Use kebab-case for file names"
    - "Always add detailed logging"
    - "I like more explanations"
    """

    memory_type: MemoryType = MemoryType.CONVERSATIONAL

    preference_key: Optional[str] = (
        None  # e.g., "language_preference", "naming_convention"
    )
    preference_value: Optional[str] = None

    # How was this learned?
    learned_from: str = "explicit"  # explicit (user told us) or implicit (observed)


@dataclass
class WorkspaceMemory(MemoryEntry):
    """
    Memory about codebase patterns and architecture.

    Examples:
    - "Backend uses NestJS with dependency injection"
    - "Tests follow AAA pattern (Arrange, Act, Assert)"
    - "API responses use DTO pattern"
    - "Services are in src/services/ directory"
    """

    memory_type: MemoryType = MemoryType.WORKSPACE

    file_path: Optional[str] = None
    pattern_type: Optional[str] = None  # "architecture", "convention", "pattern"
    example_code: Optional[str] = None

    # Confidence scores
    usage_frequency: int = 0  # How often this pattern appears
    last_seen: Optional[datetime] = None


@dataclass
class OrganizationalMemory(MemoryEntry):
    """
    Memory from organizational systems (Jira, Slack, Confluence, etc.).

    Examples:
    - Jira ticket discussions
    - Slack thread decisions
    - Confluence architecture docs
    - Zoom meeting notes
    - PR review comments
    """

    memory_type: MemoryType = MemoryType.ORGANIZATIONAL

    org_system: str = ""  # jira, slack, confluence, zoom, github
    org_id: Optional[str] = None  # Issue key, message ID, doc ID, etc.

    participants: List[str] = field(default_factory=list)
    timestamp: Optional[datetime] = None

    # Cross-references
    related_jira: List[str] = field(default_factory=list)
    related_prs: List[str] = field(default_factory=list)
    related_files: List[str] = field(default_factory=list)


@dataclass
class TaskMemory(MemoryEntry):
    """
    Memory from task execution history.

    Examples:
    - How NAVI solved a similar bug
    - What errors occurred and how they were fixed
    - What code changes were made
    - What approvals were given/rejected
    """

    memory_type: MemoryType = MemoryType.TASK

    task_id: str = ""  # Jira key or workflow ID
    step: Optional[str] = None  # Which workflow step

    # Execution details
    action_taken: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    resolution: Optional[str] = None

    # Learning data
    user_approved: Optional[bool] = None
    user_feedback: Optional[str] = None

    files_changed: List[str] = field(default_factory=list)
    code_diff: Optional[str] = None


# ==============================================================================
# MEMORY IMPORTANCE SCORING
# ==============================================================================


def calculate_importance(memory: MemoryEntry) -> float:
    """
    Calculate importance score for a memory.

    Factors:
    - How recently accessed
    - How frequently accessed
    - Memory type (user preferences = high importance)
    - Confidence level
    - Source reliability

    Returns:
        Importance score (0.0 to 1.0)
    """
    score = 0.5  # Base score

    # User preferences are very important
    if memory.memory_type == MemoryType.CONVERSATIONAL:
        score += 0.3

    # Recent access = more important
    days_since_access = (datetime.now(timezone.utc) - memory.accessed_at).days
    if days_since_access < 7:
        score += 0.2
    elif days_since_access < 30:
        score += 0.1

    # Frequent access = more important
    if memory.access_count > 10:
        score += 0.2
    elif memory.access_count > 5:
        score += 0.1

    # High confidence = more important
    score += memory.confidence * 0.1

    # Explicit learning = more important
    if isinstance(memory, ConversationalMemory) and memory.learned_from == "explicit":
        score += 0.1

    return min(score, 1.0)


def should_prune_memory(memory: MemoryEntry) -> bool:
    """
    Decide if a memory should be pruned (deleted).

    Prune if:
    - Very old and never accessed
    - Low importance and low confidence
    - Contradicted by newer memories

    Returns:
        True if should be pruned
    """

    # Never prune user preferences
    if memory.memory_type == MemoryType.CONVERSATIONAL:
        return False

    # Never accessed in 90+ days = prune
    days_since_access = (datetime.now(timezone.utc) - memory.accessed_at).days
    if days_since_access > 90 and memory.access_count == 0:
        return True

    # Low importance + old = prune
    if memory.importance < 0.3 and days_since_access > 60:
        return True

    # Low confidence = prune
    if memory.confidence < 0.3:
        return True

    return False
