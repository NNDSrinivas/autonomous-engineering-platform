"""
Multi-Agent Collaboration Framework Module - Part 14

This module enables multiple specialized agents to work together as a virtual
engineering team with communication, coordination, and collaborative reasoning.
"""

from .collaboration_engine import (
    CollaborationEngine,
    MultiAgentOrchestrator,
    BaseCollaborativeAgent,
    AgentMessage,
    CollaborationContext,
    TaskDelegation,
    MessageType,
    AgentRole,
    Priority,
)

__all__ = [
    "CollaborationEngine",
    "MultiAgentOrchestrator",
    "BaseCollaborativeAgent",
    "AgentMessage",
    "CollaborationContext",
    "TaskDelegation",
    "MessageType",
    "AgentRole",
    "Priority",
]
