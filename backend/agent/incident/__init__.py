"""
Phase 4.6 — Incident-Level Intelligence

Enterprise-grade incident intelligence system that elevates NAVI from a task executor
to a true Autonomous Engineering Intelligence (AEI) with systems thinking, prediction,
and self-healing at scale.

This system enables NAVI to:
- Think in engineering incidents, not single failures
- Predict failures before they occur
- Understand patterns across time, services, and systems
- Make Staff Engineer-level decisions autonomously
"""

from .incident_store import IncidentStore, Incident, IncidentType
from .incident_graph import IncidentGraph, build_incident_graph
from .pattern_analyzer import PatternAnalyzer, RecurringFailure, SystemicIssue
from .flaky_test_detector import FlakyTestDetector, FlakyTest, TestStability
from .regression_predictor import RegressionPredictor, RegressionRisk, PredictionModel
from .blast_radius_analyzer import BlastRadiusAnalyzer, ImpactAnalysis, ChangeRisk
from .incident_orchestrator import IncidentOrchestrator, IncidentDecision, SeverityLevel

__all__ = [
    # Core Data Types
    'Incident',
    'IncidentType', 
    'RecurringFailure',
    'SystemicIssue',
    'FlakyTest',
    'TestStability',
    'RegressionRisk',
    'PredictionModel',
    'ImpactAnalysis',
    'ChangeRisk',
    'IncidentDecision',
    'SeverityLevel',
    
    # Intelligence Engines
    'IncidentStore',
    'IncidentGraph',
    'PatternAnalyzer',
    'FlakyTestDetector', 
    'RegressionPredictor',
    'BlastRadiusAnalyzer',
    'IncidentOrchestrator',
    
    # Utility Functions
    'build_incident_graph'
]