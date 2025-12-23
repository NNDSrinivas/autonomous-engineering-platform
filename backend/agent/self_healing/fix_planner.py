"""
Fix Planner for NAVI Phase 3.6

Responsibility:
- Decide whether a failure should be auto-fixed
- Produce constrained, safe fix intents
- Enforce retry limits and confidence thresholds
- Provide explainable decisions for UI transparency

Purpose:
This is the safety gate that prevents runaway autonomous fixes. It uses
conservative rules to determine when NAVI should attempt a fix vs. when
human review is required. The goal is high-confidence, low-risk fixes only.

Decision Matrix:
- Syntax/Lint errors: Auto-fix allowed (high confidence, low risk)
- Test failures: Human review required (complex logic, business rules)
- Dependencies: Conditional (simple missing deps ok, complex issues not)
- Infrastructure: Never auto-fix (environment/deployment concerns)

Flow:
1. Receive FailureCause objects from FailureAnalyzer
2. Apply safety rules and confidence thresholds
3. Generate FixPlan with clear reasoning
4. Provide actionable fix goals for code generation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Set
from enum import Enum

from .failure_analyzer import FailureCause, FailureCategory

logger = logging.getLogger(__name__)


class FixStrategy(Enum):
    """Different strategies for addressing failures."""
    AUTO_FIX = "auto_fix"           # Autonomous fix attempt
    GUIDED_FIX = "guided_fix"       # Fix with human approval
    HUMAN_ONLY = "human_only"       # Requires full human intervention
    RETRY = "retry"                 # Simple retry without changes
    IGNORE = "ignore"               # Known acceptable failure


@dataclass(frozen=True)
class FixPlan:
    """
    Plan for addressing a CI failure.
    
    Contains the decision on whether to fix, how to fix, and why.
    """
    allowed: bool                           # Whether auto-fix is permitted
    strategy: FixStrategy                   # How to address the failure
    reason: str                             # Human-readable explanation
    fix_goal: str                           # Specific goal for code generation
    confidence: float = 0.0                 # Confidence in fix success (0-1)
    estimated_effort: str = "low"           # low | medium | high
    risk_level: str = "low"                 # low | medium | high
    max_attempts: int = 2                   # Maximum fix attempts allowed
    prerequisites: List[str] = None         # Required conditions for fixing
    
    def __post_init__(self):
        if self.prerequisites is None:
            object.__setattr__(self, 'prerequisites', [])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['strategy'] = self.strategy.value  # Convert enum to string
        return result

    def is_safe_for_auto_fix(self) -> bool:
        """Check if this plan is safe for autonomous execution."""
        return (self.allowed and 
                self.strategy == FixStrategy.AUTO_FIX and
                self.confidence >= 0.7 and
                self.risk_level in {"low", "medium"})


class FixPlanningError(Exception):
    """Raised when fix planning encounters an error."""
    pass


class FixPlanner:
    """
    Determines safe auto-fix eligibility and generates fix plans.
    
    This planner uses conservative rules to ensure autonomous fixes are
    only attempted for well-understood, low-risk failure types.
    """

    # Categories that are safe for autonomous fixing
    AUTO_FIXABLE_CATEGORIES = {
        FailureCategory.SYNTAX,
        FailureCategory.LINT
    }
    
    # Categories that might be auto-fixable under certain conditions
    CONDITIONAL_CATEGORIES = {
        FailureCategory.DEPENDENCY
    }
    
    # Categories that require human intervention
    HUMAN_ONLY_CATEGORIES = {
        FailureCategory.TEST,
        FailureCategory.INFRA,
        FailureCategory.UNKNOWN
    }
    
    # Retry-eligible categories (for transient issues)
    RETRY_CATEGORIES = {
        FailureCategory.TIMEOUT
    }

    def __init__(self):
        """Initialize the fix planner."""
        self.planning_stats = {
            'total_planned': 0,
            'by_strategy': {strategy: 0 for strategy in FixStrategy},
            'auto_fix_allowed': 0,
            'human_review_required': 0
        }

    def plan(self, causes: List[FailureCause], context: Dict[str, Any] = None) -> FixPlan:
        """
        Generate a fix plan for the given failure causes.
        
        Args:
            causes: List of FailureCause objects from analysis
            context: Additional context (attempt count, repo info, etc.)
            
        Returns:
            FixPlan with decision and reasoning
        """
        try:
            self.planning_stats['total_planned'] += 1
            
            if not causes:
                return self._create_no_action_plan("No failure causes to address")
            
            # Use the most severe/important cause for planning
            primary_cause = self._select_primary_cause(causes)
            
            # Extract context information
            context = context or {}
            attempt_count = context.get('attempt_count', 0)
            max_total_attempts = context.get('max_attempts', 2)
            repo_context = context.get('repo_context', {})
            
            # Check if we've exceeded attempt limits
            if attempt_count >= max_total_attempts:
                return self._create_blocked_plan(
                    "Maximum fix attempts exceeded",
                    FixStrategy.HUMAN_ONLY
                )
            
            # Generate plan based on failure category
            plan = self._plan_for_category(primary_cause, attempt_count, repo_context)
            
            # Update statistics
            self.planning_stats['by_strategy'][plan.strategy] += 1
            if plan.allowed:
                self.planning_stats['auto_fix_allowed'] += 1
            else:
                self.planning_stats['human_review_required'] += 1
            
            logger.info(f"Generated fix plan: {plan.strategy.value} for {primary_cause.category.value}")
            return plan
            
        except Exception as e:
            logger.exception("Failed to generate fix plan")
            raise FixPlanningError(f"Planning failed: {e}")

    def _select_primary_cause(self, causes: List[FailureCause]) -> FailureCause:
        """
        Select the primary cause to address from multiple causes.
        
        Priority order:
        1. Syntax errors (blocking)
        2. Dependency issues (blocking)
        3. Lint issues (non-blocking but fixable)
        4. Test failures (complex)
        5. Others
        """
        # Sort by priority
        priority_order = [
            FailureCategory.SYNTAX,
            FailureCategory.DEPENDENCY,
            FailureCategory.LINT,
            FailureCategory.TEST,
            FailureCategory.TIMEOUT,
            FailureCategory.INFRA,
            FailureCategory.UNKNOWN
        ]
        
        for category in priority_order:
            for cause in causes:
                if cause.category == category:
                    return cause
        
        # Fallback to first cause
        return causes[0]

    def _plan_for_category(
        self, 
        cause: FailureCause, 
        attempt_count: int, 
        repo_context: Dict[str, Any]
    ) -> FixPlan:
        """Generate a fix plan for a specific failure category."""
        
        if cause.category in self.AUTO_FIXABLE_CATEGORIES:
            return self._plan_auto_fixable(cause, attempt_count)
        
        elif cause.category in self.CONDITIONAL_CATEGORIES:
            return self._plan_conditional(cause, attempt_count, repo_context)
        
        elif cause.category in self.RETRY_CATEGORIES:
            return self._plan_retry(cause, attempt_count)
        
        elif cause.category in self.HUMAN_ONLY_CATEGORIES:
            return self._plan_human_only(cause)
        
        else:
            return self._create_blocked_plan(
                f"Unknown category '{cause.category.value}' - requires human review",
                FixStrategy.HUMAN_ONLY
            )

    def _plan_auto_fixable(self, cause: FailureCause, attempt_count: int) -> FixPlan:
        """Plan for auto-fixable categories (syntax, lint)."""
        
        if cause.category == FailureCategory.SYNTAX:
            return FixPlan(
                allowed=True,
                strategy=FixStrategy.AUTO_FIX,
                reason="Syntax errors are safe to auto-fix with high confidence",
                fix_goal=f"Fix syntax error: {cause.message}",
                confidence=0.85,
                estimated_effort="low",
                risk_level="low",
                max_attempts=2,
                prerequisites=["Clean git working directory", "Valid file path"]
            )
        
        elif cause.category == FailureCategory.LINT:
            # Lint fixes are generally safe but slightly lower confidence
            confidence = 0.8 - (attempt_count * 0.1)  # Reduce confidence on retries
            
            return FixPlan(
                allowed=True,
                strategy=FixStrategy.AUTO_FIX,
                reason="Linting violations are safe to auto-fix",
                fix_goal=f"Fix linting violations: {cause.message}",
                confidence=max(0.6, confidence),
                estimated_effort="low",
                risk_level="low",
                max_attempts=2,
                prerequisites=["Linting rules available", "File accessible"]
            )
        
        else:
            return self._create_blocked_plan(
                f"Unexpected auto-fixable category: {cause.category.value}",
                FixStrategy.HUMAN_ONLY
            )

    def _plan_conditional(
        self, 
        cause: FailureCause, 
        attempt_count: int, 
        repo_context: Dict[str, Any]
    ) -> FixPlan:
        """Plan for conditionally fixable categories (dependencies)."""
        
        if cause.category == FailureCategory.DEPENDENCY:
            # Only auto-fix simple, well-known dependency issues
            if self._is_simple_dependency_issue(cause, repo_context):
                return FixPlan(
                    allowed=True,
                    strategy=FixStrategy.AUTO_FIX,
                    reason="Simple dependency issue detected - safe to auto-fix",
                    fix_goal="Add missing dependency to package configuration",
                    confidence=0.7,
                    estimated_effort="low",
                    risk_level="medium",
                    max_attempts=1,
                    prerequisites=["Package manager available", "Network access"]
                )
            else:
                return FixPlan(
                    allowed=False,
                    strategy=FixStrategy.HUMAN_ONLY,
                    reason="Complex dependency issue requires human review",
                    fix_goal="Review and resolve dependency conflicts",
                    confidence=0.3,
                    estimated_effort="high",
                    risk_level="high"
                )
        
        return self._create_blocked_plan(
            f"Unexpected conditional category: {cause.category.value}",
            FixStrategy.HUMAN_ONLY
        )

    def _plan_retry(self, cause: FailureCause, attempt_count: int) -> FixPlan:
        """Plan for retry-eligible categories (timeouts)."""
        
        if attempt_count == 0:  # First retry allowed
            return FixPlan(
                allowed=True,
                strategy=FixStrategy.RETRY,
                reason="Timeout detected - retry may succeed",
                fix_goal="Retry CI job without changes",
                confidence=0.6,
                estimated_effort="low",
                risk_level="low",
                max_attempts=1
            )
        else:
            return FixPlan(
                allowed=False,
                strategy=FixStrategy.HUMAN_ONLY,
                reason="Multiple timeouts - infrastructure investigation needed",
                fix_goal="Investigate timeout causes and optimize build",
                confidence=0.2,
                estimated_effort="high",
                risk_level="medium"
            )

    def _plan_human_only(self, cause: FailureCause) -> FixPlan:
        """Plan for human-only categories (tests, infrastructure, unknown)."""
        
        reason_map = {
            FailureCategory.TEST: "Test failures require human review of business logic",
            FailureCategory.INFRA: "Infrastructure issues require environment expertise",
            FailureCategory.UNKNOWN: "Unknown failure type requires investigation"
        }
        
        goal_map = {
            FailureCategory.TEST: "Review failing tests and fix implementation logic",
            FailureCategory.INFRA: "Investigate and resolve infrastructure issues",
            FailureCategory.UNKNOWN: "Analyze failure logs and determine root cause"
        }
        
        return FixPlan(
            allowed=False,
            strategy=FixStrategy.HUMAN_ONLY,
            reason=reason_map.get(cause.category, f"Category {cause.category.value} requires human intervention"),
            fix_goal=goal_map.get(cause.category, "Manual investigation and resolution required"),
            confidence=0.0,
            estimated_effort="high",
            risk_level="high"
        )

    def _is_simple_dependency_issue(self, cause: FailureCause, repo_context: Dict[str, Any]) -> bool:
        """
        Determine if a dependency issue is simple enough for auto-fixing.
        
        Simple issues:
        - Single missing package with clear name
        - Standard package managers (npm, pip, etc.)
        - No version conflicts
        """
        # For now, be conservative and don't auto-fix dependencies
        # This can be expanded later with more sophisticated analysis
        return False

    def _create_no_action_plan(self, reason: str) -> FixPlan:
        """Create a plan that requires no action."""
        return FixPlan(
            allowed=False,
            strategy=FixStrategy.IGNORE,
            reason=reason,
            fix_goal="No action required",
            confidence=0.0
        )

    def _create_blocked_plan(self, reason: str, strategy: FixStrategy) -> FixPlan:
        """Create a blocked fix plan."""
        return FixPlan(
            allowed=False,
            strategy=strategy,
            reason=reason,
            fix_goal="Manual intervention required",
            confidence=0.0,
            estimated_effort="high",
            risk_level="high"
        )

    def get_planning_stats(self) -> Dict[str, Any]:
        """Get statistics about fix planning decisions."""
        return {
            'total_planned': self.planning_stats['total_planned'],
            'by_strategy': {
                strategy.value: count 
                for strategy, count in self.planning_stats['by_strategy'].items()
            },
            'auto_fix_allowed': self.planning_stats['auto_fix_allowed'],
            'human_review_required': self.planning_stats['human_review_required'],
            'auto_fix_rate': (
                self.planning_stats['auto_fix_allowed'] / max(1, self.planning_stats['total_planned'])
            )
        }

    def reset_stats(self) -> None:
        """Reset planning statistics."""
        self.planning_stats = {
            'total_planned': 0,
            'by_strategy': {strategy: 0 for strategy in FixStrategy},
            'auto_fix_allowed': 0,
            'human_review_required': 0
        }