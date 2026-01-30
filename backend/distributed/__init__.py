"""
Distributed Agent Execution Module

This module provides multi-agent coordination and parallel execution capabilities:
- DistributedAgentFleet: Manages fleets of agents with parallel execution
- EnterpriseAgentCoordinator: Bridges enterprise projects with agent execution

Usage:
    from backend.distributed import (
        DistributedAgentFleet,
        EnterpriseAgentCoordinator,
        execute_enterprise_project,
    )
"""

from .agent_fleet import (
    DistributedAgentFleet,
    AgentRole,
    TaskPriority,
    TaskStatus,
    Task,
    AgentCapability,
    ConflictResolutionStrategy,
    CommunicationProtocol,
    FleetMetrics,
)

from .enterprise_agent_coordinator import (
    EnterpriseAgentCoordinator,
    ExecutionMode,
    AgentFailureStrategy,
    ParallelExecutionResult,
    TaskExecutionContext,
    CoordinatorState,
    create_coordinator,
    execute_enterprise_project,
)

__all__ = [
    # Agent Fleet
    "DistributedAgentFleet",
    "AgentRole",
    "TaskPriority",
    "TaskStatus",
    "Task",
    "AgentCapability",
    "ConflictResolutionStrategy",
    "CommunicationProtocol",
    "FleetMetrics",
    # Enterprise Coordinator
    "EnterpriseAgentCoordinator",
    "ExecutionMode",
    "AgentFailureStrategy",
    "ParallelExecutionResult",
    "TaskExecutionContext",
    "CoordinatorState",
    "create_coordinator",
    "execute_enterprise_project",
]
