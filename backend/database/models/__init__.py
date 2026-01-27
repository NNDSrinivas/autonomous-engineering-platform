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

# Session Facts models (persistent session memory)
from backend.database.models.session_facts import (
    WorkspaceSession,
    SessionFact,
    ErrorResolution,
    InstalledDependency,
)

# Task Checkpoint models (task recovery)
from backend.database.models.task_checkpoint import (
    TaskCheckpoint,
)

# Enterprise Project models (long-running projects)
from backend.database.models.enterprise_project import (
    EnterpriseProject,
    HumanCheckpointGate,
    ProjectTaskQueue,
)

# Enterprise Checkpoint models (crash recovery)
from backend.database.models.enterprise_checkpoint import (
    EnterpriseCheckpoint,
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
    # Session Facts (persistent session memory)
    "WorkspaceSession",
    "SessionFact",
    "ErrorResolution",
    "InstalledDependency",
    # Task Checkpoint
    "TaskCheckpoint",
    # Enterprise Project (long-running projects)
    "EnterpriseProject",
    "HumanCheckpointGate",
    "ProjectTaskQueue",
    # Enterprise Checkpoint (crash recovery)
    "EnterpriseCheckpoint",
]
