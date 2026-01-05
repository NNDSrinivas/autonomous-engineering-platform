"""
Phase 4.7 — Org-Wide Learning & Policy Engine

This module transforms NAVI from technically capable to organizationally intelligent.
It learns from every engineering decision across the organization and automatically
infers engineering standards, governance policies, and best practices.

Key Capabilities:
- Organizational memory across all teams and repositories
- Automatic policy inference from organizational behavior
- Evidence-based, contextual policy enforcement
- Continuous learning and adaptation
- Explainable AI for all organizational decisions

This is where NAVI becomes impossible to replicate without years of org data.
"""

from .org_memory_store import OrgMemoryStore, OrgSignal, SignalType
from .learning_collector import (
    LearningCollector,
    collect_from_pr,
    collect_from_ci_failure,
)
from .knowledge_aggregator import KnowledgeAggregator, OrgKnowledge, aggregate_patterns
from .policy_inference_engine import (
    PolicyInferenceEngine,
    Policy,
    PolicyTrigger,
    infer_policies,
)
from .policy_registry import PolicyRegistry, register_policy, get_active_policies
from .policy_enforcer import PolicyEnforcer, PolicyAction, enforce_policies
from .org_insights_service import (
    OrgInsightsService,
    PolicyExplanation,
    explain_policy_decision,
)

__all__ = [
    # Core storage
    "OrgMemoryStore",
    "OrgSignal",
    "SignalType",
    # Learning system
    "LearningCollector",
    "collect_from_pr",
    "collect_from_ci_failure",
    # Knowledge aggregation
    "KnowledgeAggregator",
    "OrgKnowledge",
    "aggregate_patterns",
    # Policy system
    "PolicyInferenceEngine",
    "Policy",
    "PolicyTrigger",
    "infer_policies",
    "PolicyRegistry",
    "register_policy",
    "get_active_policies",
    "PolicyEnforcer",
    "PolicyAction",
    "enforce_policies",
    # Insights and explanations
    "OrgInsightsService",
    "PolicyExplanation",
    "explain_policy_decision",
]
