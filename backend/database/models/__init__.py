"""
Database models package.

Exports all SQLAlchemy models for the NAVI platform.
"""

# RBAC models
from backend.database.models.rbac import (
    DBRole,
    DBUser,
    Organization,
    UserRole,
)

# Memory Graph models
from backend.database.models.memory_graph import (
    EdgeRelation,
    MemoryEdge,
    MemoryNode,
    NodeKind,
)

# Memory System models
from backend.database.models.memory import (
    CodebaseIndex,
    CodePattern,
    CodeSymbol,
    Conversation,
    ConversationSummary,
    Message,
    OrgContext,
    OrgKnowledge,
    OrgStandard,
    UserActivity,
    UserFeedback,
    UserPattern,
    UserPreferences,
)

__all__ = [
    # RBAC
    "Organization",
    "DBUser",
    "DBRole",
    "UserRole",
    # Memory Graph
    "NodeKind",
    "EdgeRelation",
    "MemoryNode",
    "MemoryEdge",
    # Memory System - User
    "UserPreferences",
    "UserActivity",
    "UserPattern",
    "UserFeedback",
    # Memory System - Organization
    "OrgKnowledge",
    "OrgStandard",
    "OrgContext",
    # Memory System - Conversation
    "Conversation",
    "Message",
    "ConversationSummary",
    # Memory System - Codebase
    "CodebaseIndex",
    "CodeSymbol",
    "CodePattern",
]
