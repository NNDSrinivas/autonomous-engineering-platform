"""
Self-Healing Package for NAVI Phase 3.6

This package contains the components for autonomous CI failure recovery:
- FailureAnalyzer: Parse CI failures into structured causes (Phase 3.6.1)
- FixPlanner: Decide safe auto-fix eligibility (Phase 3.6.2)
- SelfHealingEngine: Orchestrate bounded autonomous recovery (Phase 3.6.3)

The self-healing system provides:
- Intelligent failure understanding
- Conservative fix planning with safety bounds
- Transparent progress reporting
- Confidence-based decision making
- Maximum attempt limits to prevent runaway behavior

Integration with existing phases:
- Uses Phase 3.3 ChangePlan system for code generation
- Uses Phase 3.4 validation pipeline for fix validation
- Uses Phase 3.5 PR lifecycle for commit and monitoring
"""

from .failure_analyzer import (
    FailureAnalyzer,
    FailureCause,
    FailureCategory,
    FailureAnalysisError,
)

from .fix_planner import FixPlanner, FixPlan, FixStrategy, FixPlanningError

from .self_healing_engine import (
    SelfHealingEngine,
    HealingSession,
    HealingAttempt,
    HealingStatus,
    SelfHealingError,
)

__all__ = [
    # Failure Analysis (Phase 3.6.1)
    "FailureAnalyzer",
    "FailureCause",
    "FailureCategory",
    "FailureAnalysisError",
    # Fix Planning (Phase 3.6.2)
    "FixPlanner",
    "FixPlan",
    "FixStrategy",
    "FixPlanningError",
    # Self-Healing Engine (Phase 3.6.3)
    "SelfHealingEngine",
    "HealingSession",
    "HealingAttempt",
    "HealingStatus",
    "SelfHealingError",
]
