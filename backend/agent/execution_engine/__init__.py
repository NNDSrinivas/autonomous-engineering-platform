"""
Execution Engine - Phase 4.3

The core autonomous execution system that transforms GroundedTasks into
concrete engineering actions with approval-based execution.

This module provides the foundational execution loop that will scale to
all future NAVI autonomous capabilities:
- FIX_PROBLEMS (Phase 4.3)
- DEPLOY (Phase 4.4+)
- REFACTOR (Future)
- FEATURE_IMPLEMENTATION (Future)
- CI_FAILURE_RESOLUTION (Future)

Architecture:
    GroundedTask → Analyze → Plan → Propose → Approve → Apply → Verify → Report
"""

from .core import ExecutionEngine, Executor, ExecutionResult
from .fix_problems import FixProblemsExecutor
from .types import (
    AnalysisResult,
    FixPlan,
    DiffProposal,
    VerificationResult,
    ExecutionStatus
)

__all__ = [
    "ExecutionEngine",
    "Executor", 
    "ExecutionResult",
    "FixProblemsExecutor",
    "AnalysisResult",
    "FixPlan", 
    "DiffProposal",
    "VerificationResult",
    "ExecutionStatus"
]