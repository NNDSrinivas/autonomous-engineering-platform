"""
Phase 3.3 - AEI-Grade Code Generation Engine

This module provides production-ready code generation capabilities
for autonomous engineering intelligence.

Key Components:
- types: Core data structures for change planning
- change_plan_generator: Generates detailed change plans from user requests
- context_assembler: Builds rich context for code generation
- diff_generator: Creates precise code diffs
- patch_validator: Validates changes before application

Integration Point:
This engine integrates with existing planner_v3.py without replacement,
acting as a specialized sub-planner for code generation tasks.
"""

from .types import (
    ChangeType,
    ChangeIntent,
    ValidationLevel,
    CodeChange,
    PlannedFileChange,
    ChangePlan,
    ChangeResult,
    PlanExecutionResult,
)

from .change_plan_generator import ChangePlanGenerator
from .context_assembler import ContextAssembler, FileContext, ContextAssemblyError
from .diff_generator import DiffGenerator, DiffSynthesisBackend, DiffGenerationError

__all__ = [
    "ChangeType",
    "ChangeIntent",
    "ValidationLevel",
    "CodeChange",
    "PlannedFileChange",
    "ChangePlan",
    "ChangeResult",
    "PlanExecutionResult",
    "ChangePlanGenerator",
    "ContextAssembler",
    "FileContext",
    "ContextAssemblyError",
    "DiffGenerator",
    "DiffSynthesisBackend",
    "DiffGenerationError",
]
