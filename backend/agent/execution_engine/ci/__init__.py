"""
Phase 4.5.2 — CI Failure Auto-Repair Loop

Enterprise-grade autonomous CI healing system that detects failures,
analyzes root causes, applies targeted fixes, and re-runs pipelines.

This system enables NAVI to handle CI failures autonomously with
professional-level incident response capabilities.
"""

from .ci_types import (
    CIEvent,
    FailureType,
    FailureContext,
    RepairResult,
    CIProvider,
    CIIntegrationContext,
)
from .ci_log_fetcher import CILogFetcher
from .failure_classifier import FailureClassifier
from .failure_mapper import FailureMapper
from .ci_retry_engine import CIRetryEngine
from .ci_repair_orchestrator import CIRepairOrchestrator, RepairConfiguration

__all__ = [
    "CIEvent",
    "FailureType",
    "FailureContext",
    "RepairResult",
    "CIProvider",
    "CIIntegrationContext",
    "CILogFetcher",
    "FailureClassifier",
    "FailureMapper",
    "CIRetryEngine",
    "CIRepairOrchestrator",
    "RepairConfiguration",
]
