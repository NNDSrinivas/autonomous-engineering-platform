"""
NAVI Global Memory Brain

The unified memory system that makes NAVI learn, adapt, and personalize over time.

This is what makes NAVI better than Devin/Cursor/Cline - true long-term
memory that remembers:
- User preferences and coding style
- Workspace patterns and architecture
- Organizational context and decisions
- Task history and execution patterns

NAVI becomes a real teammate that gets smarter with every interaction.
"""

from .memory_types import (
    MemoryType,
    MemoryEntry,
    ConversationalMemory,
    WorkspaceMemory,
    OrganizationalMemory,
    TaskMemory
)
from .memory_capture import (
    MemoryCapture,
    capture_user_preference,
    capture_code_pattern,
    capture_org_context,
    capture_task_execution
)
from .memory_retrieval import (
    MemoryRetrieval,
    retrieve_user_memories,
    retrieve_workspace_memories,
    retrieve_org_memories,
    retrieve_task_memories,
    retrieve_relevant_context
)
from .learning_engine import (
    LearningEngine,
    learn_from_approval,
    learn_from_code_change,
    learn_coding_style,
    detect_patterns
)
from .memory_manager import (
    MemoryManager,
    prune_old_memories,
    merge_similar_memories,
    optimize_memory_store
)

__all__ = [
    "MemoryType",
    "MemoryEntry",
    "ConversationalMemory",
    "WorkspaceMemory",
    "OrganizationalMemory",
    "TaskMemory",
    "MemoryCapture",
    "capture_user_preference",
    "capture_code_pattern",
    "capture_org_context",
    "capture_task_execution",
    "MemoryRetrieval",
    "retrieve_user_memories",
    "retrieve_workspace_memories",
    "retrieve_org_memories",
    "retrieve_task_memories",
    "retrieve_relevant_context",
    "LearningEngine",
    "learn_from_approval",
    "learn_from_code_change",
    "learn_coding_style",
    "detect_patterns",
    "MemoryManager",
    "prune_old_memories",
    "merge_similar_memories",
    "optimize_memory_store",
]
