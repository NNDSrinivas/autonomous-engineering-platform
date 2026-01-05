"""
Phase 4.9 — Autonomous Planning & Long-Horizon Execution

This module enables NAVI to graduate from 'smart executor' to a **true engineering OS**
with initiative-level autonomy, multi-step plans, pause/resume capabilities, and
org-scale execution.

Key Components:
- InitiativeStore: Durable state management (weeks, not minutes)
- TaskDecomposer: Smart goal → executable steps conversion
- PlanGraph: DAG execution with dependency resolution
- ExecutionScheduler: Orchestrates task execution with human collaboration
- CheckpointEngine: Pause/resume with full state recovery
- AdaptiveReplanner: Intelligent plan adjustment when reality changes
- LongHorizonOrchestrator: End-to-end initiative coordination

This transforms NAVI into: Tech Lead + TPM + Staff Engineer combined.
"""

# Core components for Phase 4.9
from .initiative_store import (
    InitiativeStore,
    Initiative,
    InitiativeStatus,
    InitiativeModel,
)
from .task_decomposer import (
    TaskDecomposer,
    DecomposedTask,
    DecompositionResult,
    TaskPriority,
    TaskType,
)
from .plan_graph import PlanGraph, TaskNode, TaskStatus
from .execution_scheduler import (
    ExecutionScheduler,
    ExecutionContext,
    ExecutionMode,
    TaskExecutor,
    AnalysisTaskExecutor,
    CoordinationTaskExecutor,
)
from .checkpoint_engine import (
    CheckpointEngine,
    CheckpointType,
    CheckpointModel,
    CheckpointMetadata,
)
from .adaptive_replanner import (
    AdaptiveReplanner,
    ReplanTrigger,
    ReplanContext,
    ReplanResult,
    ReplanAnalyzer,
)
from .long_horizon_orchestrator import (
    LongHorizonOrchestrator,
    OrchestrationMode,
    InitiativeConfig,
)

__all__ = [
    # Main orchestrator
    "LongHorizonOrchestrator",
    "OrchestrationMode",
    "InitiativeConfig",
    # Initiative management
    "InitiativeStore",
    "Initiative",
    "InitiativeStatus",
    "InitiativeModel",
    # Task planning
    "TaskDecomposer",
    "DecomposedTask",
    "DecompositionResult",
    "TaskPriority",
    "TaskType",
    # Execution graph
    "PlanGraph",
    "TaskNode",
    "TaskStatus",
    # Execution control
    "ExecutionScheduler",
    "ExecutionContext",
    "ExecutionMode",
    "TaskExecutor",
    "AnalysisTaskExecutor",
    "CoordinationTaskExecutor",
    # State persistence
    "CheckpointEngine",
    "CheckpointType",
    "CheckpointModel",
    "CheckpointMetadata",
    # Adaptive planning
    "AdaptiveReplanner",
    "ReplanTrigger",
    "ReplanContext",
    "ReplanResult",
    "ReplanAnalyzer",
]
