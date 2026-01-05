"""
PolicyInferenceEngine — Automatic Rule Creation

Intelligent policy creation system that automatically infers engineering
standards and governance rules from organizational behavior patterns.
This creates learned behavior policies, not hardcoded rules.

Key Capabilities:
- Automatically infer policies from organizational patterns
- Create evidence-based engineering standards
- Generate contextual governance rules
- Adapt policies based on organizational evolution
- Maintain policy confidence and lifecycle management
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from .knowledge_aggregator import OrgPattern, OrgKnowledge
from .org_memory_store import OrgSignal, SignalType

logger = logging.getLogger(__name__)


class PolicyTrigger(Enum):
    """Types of triggers that can activate policies"""

    MODIFY_HIGH_RISK_FILE = "modify_high_risk_file"
    CREATE_PULL_REQUEST = "create_pull_request"
    DEPLOY_TO_PRODUCTION = "deploy_to_production"
    LARGE_CHANGE_SET = "large_change_set"
    CROSS_TEAM_CHANGE = "cross_team_change"
    CRITICAL_FILE_CHANGE = "critical_file_change"
    FREQUENT_AUTHOR_CHANGE = "frequent_author_change"
    WEEKEND_DEPLOYMENT = "weekend_deployment"
    HOTFIX_DEPLOYMENT = "hotfix_deployment"
    NEW_AUTHOR_CONTRIBUTION = "new_author_contribution"
    DEPENDENCY_CHANGE = "dependency_change"
    SECURITY_RELATED_CHANGE = "security_related_change"


class PolicyAction(Enum):
    """Types of actions a policy can take"""

    REQUIRE_APPROVAL = "require_approval"
    REQUIRE_ADDITIONAL_REVIEW = "require_additional_review"
    REQUIRE_TESTING = "require_testing"
    WARN_USER = "warn_user"
    SUGGEST_ALTERNATIVE = "suggest_alternative"
    BLOCK_ACTION = "block_action"
    REQUEST_DOCUMENTATION = "request_documentation"
    SCHEDULE_REVIEW = "schedule_review"
    NOTIFY_TEAM = "notify_team"
    REQUIRE_SMOKE_TESTS = "require_smoke_tests"
    SUGGEST_STAGING_FIRST = "suggest_staging_first"
    REQUIRE_ROLLBACK_PLAN = "require_rollback_plan"


@dataclass
class PolicyCondition:
    """Condition that must be met for a policy to apply"""

    field: str  # "file_path", "author", "change_size", "team", "time"
    operator: str  # "equals", "contains", "greater_than", "in_list"
    value: Any
    description: str


@dataclass
class Policy:
    """An automatically inferred organizational policy"""

    id: str
    name: str
    description: str
    trigger: PolicyTrigger
    action: PolicyAction
    conditions: List[PolicyCondition] = field(default_factory=list)
    confidence: float = 0.0  # 0.0 - 1.0
    evidence_signals: List[str] = field(
        default_factory=list
    )  # Signal IDs supporting this policy
    created_from_pattern: Optional[str] = None  # Pattern ID that created this policy
    created_at: datetime = field(default_factory=datetime.now)
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0
    effectiveness_score: float = 0.5  # How effective this policy has been
    team_scope: Optional[str] = (
        None  # Team this policy applies to, or None for org-wide
    )
    repo_scope: Optional[str] = (
        None  # Repo this policy applies to, or None for org-wide
    )
    severity_threshold: str = "MEDIUM"  # Minimum severity to trigger
    impact_threshold: str = "TEAM"  # Minimum impact to trigger
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    rationale: List[str] = field(default_factory=list)  # Why this policy was created


class PolicyInferenceEngine:
    """
    System for automatically inferring organizational policies from patterns
    and organizational knowledge. Creates evidence-based governance rules.
    """

    def __init__(self):
        """Initialize the policy inference engine"""
        self.confidence_threshold = 0.7
        self.minimum_evidence = 3
        logger.info(
            "PolicyInferenceEngine initialized - ready to infer organizational policies"
        )

    def infer_policies(self, org_knowledge: OrgKnowledge) -> List[Policy]:
        """
        Infer policies from organizational knowledge

        Args:
            org_knowledge: Comprehensive organizational knowledge

        Returns:
            List of inferred policies
        """
        logger.info(
            f"Inferring policies for {org_knowledge.org_name} from {len(org_knowledge.patterns)} patterns"
        )

        policies = []

        # Infer policies from failure hotspot patterns
        policies.extend(self._infer_from_failure_hotspots(org_knowledge.patterns))

        # Infer policies from author risk patterns
        policies.extend(self._infer_from_author_patterns(org_knowledge.patterns))

        # Infer policies from temporal patterns
        policies.extend(self._infer_from_temporal_patterns(org_knowledge.patterns))

        # Infer policies from team knowledge
        policies.extend(self._infer_from_team_knowledge(org_knowledge.team_knowledge))

        # Infer policies from cross-team patterns
        policies.extend(
            self._infer_from_cross_team_insights(org_knowledge.cross_team_insights)
        )

        # Infer policies from critical insights
        policies.extend(
            self._infer_from_critical_insights(
                org_knowledge.critical_insights, org_knowledge.patterns
            )
        )

        # Filter by confidence threshold
        high_confidence_policies = [
            policy
            for policy in policies
            if policy.confidence >= self.confidence_threshold
        ]

        # Set policy metadata
        for policy in high_confidence_policies:
            policy.metadata["org"] = org_knowledge.org_name
            policy.metadata["inferred_at"] = datetime.now().isoformat()
            policy.metadata["analysis_period"] = [
                org_knowledge.analysis_period[0].isoformat(),
                org_knowledge.analysis_period[1].isoformat(),
            ]

        logger.info(
            f"Inferred {len(high_confidence_policies)} high-confidence policies"
        )
        return high_confidence_policies

    def _infer_from_failure_hotspots(self, patterns: List[OrgPattern]) -> List[Policy]:
        """Infer policies from failure hotspot patterns"""
        policies = []

        failure_hotspots = [p for p in patterns if p.pattern_type == "failure_hotspot"]

        for pattern in failure_hotspots:
            if pattern.confidence >= 0.8 and pattern.frequency >= 5:
                # Create policy for high-risk files
                file_path = (
                    pattern.affected_entities[0]
                    if pattern.affected_entities
                    else "unknown"
                )

                policy = Policy(
                    id=f"hotspot_review_{pattern.pattern_id}",
                    name=f"Extra Review for {file_path}",
                    description=f"Require additional review for changes to {file_path} due to high failure rate",
                    trigger=PolicyTrigger.MODIFY_HIGH_RISK_FILE,
                    action=PolicyAction.REQUIRE_ADDITIONAL_REVIEW,
                    conditions=[
                        PolicyCondition(
                            field="file_path",
                            operator="equals",
                            value=file_path,
                            description=f"File path matches {file_path}",
                        )
                    ],
                    confidence=pattern.confidence,
                    evidence_signals=pattern.evidence,
                    created_from_pattern=pattern.pattern_id,
                    rationale=[
                        f"File {file_path} has failed {pattern.frequency} times",
                        f"Pattern confidence: {pattern.confidence:.2f}",
                        "Additional review can prevent similar failures",
                    ],
                )

                # For critical hotspots, require approval
                if pattern.impact_level == "CRITICAL":
                    policy.action = PolicyAction.REQUIRE_APPROVAL
                    policy.name = f"Approval Required for {file_path}"
                    policy.description = f"Require senior engineer approval for changes to critical file {file_path}"

                policies.append(policy)

        return policies

    def _infer_from_author_patterns(self, patterns: List[OrgPattern]) -> List[Policy]:
        """Infer policies from author risk patterns"""
        policies = []

        author_risk_patterns = [p for p in patterns if p.pattern_type == "author_risk"]

        for pattern in author_risk_patterns:
            if pattern.confidence >= 0.7 and pattern.frequency >= 5:
                author = (
                    pattern.affected_entities[0]
                    if pattern.affected_entities
                    else "unknown"
                )

                policy = Policy(
                    id=f"author_review_{pattern.pattern_id}",
                    name=f"Peer Review for {author}",
                    description=f"Require peer review for {author}'s changes due to elevated failure rate",
                    trigger=PolicyTrigger.CREATE_PULL_REQUEST,
                    action=PolicyAction.REQUIRE_ADDITIONAL_REVIEW,
                    conditions=[
                        PolicyCondition(
                            field="author",
                            operator="equals",
                            value=author,
                            description=f"Author is {author}",
                        )
                    ],
                    confidence=pattern.confidence,
                    evidence_signals=pattern.evidence,
                    created_from_pattern=pattern.pattern_id,
                    rationale=[
                        f"Author {author} has high failure rate ({pattern.frequency} failures)",
                        "Peer review can help catch issues early",
                        "Temporary measure to improve code quality",
                    ],
                )

                policies.append(policy)

        return policies

    def _infer_from_temporal_patterns(self, patterns: List[OrgPattern]) -> List[Policy]:
        """Infer policies from temporal patterns"""
        policies = []

        temporal_patterns = [
            p for p in patterns if p.pattern_type == "temporal_pattern"
        ]

        for pattern in temporal_patterns:
            if (
                "Friday" in pattern.description
                or "weekend" in pattern.description.lower()
            ):
                policy = Policy(
                    id=f"weekend_deployment_{pattern.pattern_id}",
                    name="Weekend Deployment Review",
                    description="Require additional approval for weekend deployments due to higher failure rate",
                    trigger=PolicyTrigger.WEEKEND_DEPLOYMENT,
                    action=PolicyAction.REQUIRE_APPROVAL,
                    conditions=[
                        PolicyCondition(
                            field="time",
                            operator="in_list",
                            value=["Friday", "Saturday", "Sunday"],
                            description="Deployment time is Friday, Saturday, or Sunday",
                        )
                    ],
                    confidence=pattern.confidence,
                    evidence_signals=pattern.evidence,
                    created_from_pattern=pattern.pattern_id,
                    rationale=[
                        "Weekend deployments have higher failure rates",
                        "Reduced support availability increases risk",
                        "Additional approval provides safety net",
                    ],
                )

                policies.append(policy)

        return policies

    def _infer_from_team_knowledge(
        self, team_knowledge: Dict[str, Any]
    ) -> List[Policy]:
        """Infer policies from team-specific knowledge"""
        policies = []

        for team_name, knowledge in team_knowledge.items():
            # Teams with high failure rates need extra oversight
            if knowledge.quality_score < 0.4 and knowledge.activity_level == "HIGH":
                policy = Policy(
                    id=f"team_oversight_{team_name}",
                    name=f"Enhanced Review for {team_name}",
                    description=f"Require enhanced review for {team_name} due to elevated failure rate",
                    trigger=PolicyTrigger.CREATE_PULL_REQUEST,
                    action=PolicyAction.REQUIRE_ADDITIONAL_REVIEW,
                    conditions=[
                        PolicyCondition(
                            field="team",
                            operator="equals",
                            value=team_name,
                            description=f"Author belongs to team {team_name}",
                        )
                    ],
                    confidence=0.8,
                    evidence_signals=[],  # Team knowledge doesn't have direct signals
                    team_scope=team_name,
                    rationale=[
                        f"Team {team_name} has quality score of {knowledge.quality_score:.2f}",
                        "High activity with low quality indicates need for oversight",
                        "Enhanced review can improve team practices",
                    ],
                )

                policies.append(policy)

            # Teams with specific expertise should review related changes
            if len(knowledge.expertise_areas) > 5 and knowledge.quality_score > 0.7:
                for area in knowledge.expertise_areas[:3]:  # Top 3 areas
                    policy = Policy(
                        id=f"expertise_review_{team_name}_{hash(area) % 1000}",
                        name=f"Expert Review: {team_name} for {area}",
                        description=f"Notify {team_name} for changes to {area} (their area of expertise)",
                        trigger=PolicyTrigger.MODIFY_HIGH_RISK_FILE,
                        action=PolicyAction.NOTIFY_TEAM,
                        conditions=[
                            PolicyCondition(
                                field="file_path",
                                operator="contains",
                                value=area,
                                description=f"File path contains {area}",
                            )
                        ],
                        confidence=0.7,
                        evidence_signals=[],
                        team_scope=team_name,
                        rationale=[
                            f"Team {team_name} has expertise in {area}",
                            f"Quality score: {knowledge.quality_score:.2f}",
                            "Expert input can prevent issues",
                        ],
                    )

                    policies.append(policy)

        return policies

    def _infer_from_cross_team_insights(
        self, cross_team_insights: Dict[str, Any]
    ) -> List[Policy]:
        """Infer policies from cross-team patterns"""
        policies = []

        # Shared expertise areas should have cross-team review
        shared_areas = cross_team_insights.get("shared_expertise_areas", {})

        for area, teams in shared_areas.items():
            if len(teams) >= 2:
                policy = Policy(
                    id=f"cross_team_{hash(area) % 10000}",
                    name=f"Cross-Team Review for {area}",
                    description=f"Notify multiple teams for changes to shared area {area}",
                    trigger=PolicyTrigger.CROSS_TEAM_CHANGE,
                    action=PolicyAction.NOTIFY_TEAM,
                    conditions=[
                        PolicyCondition(
                            field="file_path",
                            operator="contains",
                            value=area,
                            description=f"File path contains shared area {area}",
                        )
                    ],
                    confidence=0.8,
                    evidence_signals=[],
                    rationale=[
                        f"Area {area} is shared by teams: {', '.join(teams)}",
                        "Cross-team coordination prevents conflicts",
                        "Shared ownership requires shared awareness",
                    ],
                )

                policies.append(policy)

        return policies

    def _infer_from_critical_insights(
        self, critical_insights: List[str], patterns: List[OrgPattern]
    ) -> List[Policy]:
        """Infer urgent policies from critical insights"""
        policies = []

        for insight in critical_insights:
            if "critical patterns" in insight.lower():
                # Emergency policy for critical patterns
                critical_patterns = [
                    p for p in patterns if p.impact_level == "CRITICAL"
                ]

                if critical_patterns:
                    policy = Policy(
                        id="emergency_review_critical",
                        name="Emergency Review for Critical Changes",
                        description="Require senior engineer approval for any changes affecting critical failure patterns",
                        trigger=PolicyTrigger.MODIFY_HIGH_RISK_FILE,
                        action=PolicyAction.REQUIRE_APPROVAL,
                        conditions=[
                            PolicyCondition(
                                field="impact_level",
                                operator="equals",
                                value="CRITICAL",
                                description="Change affects critical system components",
                            )
                        ],
                        confidence=0.9,
                        evidence_signals=sum(
                            [p.evidence for p in critical_patterns], []
                        ),
                        severity_threshold="HIGH",
                        rationale=[
                            f"{len(critical_patterns)} critical patterns require immediate attention",
                            "Senior oversight prevents cascading failures",
                            "Emergency measure until patterns are resolved",
                        ],
                    )

                    policies.append(policy)

        return policies

    def refine_policy_confidence(
        self, policy: Policy, outcome_signals: List[OrgSignal]
    ) -> Policy:
        """
        Refine policy confidence based on outcomes after policy was applied

        Args:
            policy: The policy to refine
            outcome_signals: Signals after policy was applied

        Returns:
            Policy with updated confidence
        """
        # Count successes and failures after policy application
        policy_applied_time = policy.created_at

        relevant_signals = [
            s for s in outcome_signals if s.timestamp > policy_applied_time
        ]

        if not relevant_signals:
            return policy  # No data to refine with

        # Check if the policy conditions would have triggered
        would_have_triggered = 0
        successful_interventions = 0

        for signal in relevant_signals:
            if self._would_policy_trigger(policy, signal):
                would_have_triggered += 1
                if signal.signal_type in [
                    SignalType.CI_SUCCESS,
                    SignalType.PR_APPROVAL,
                ]:
                    successful_interventions += 1

        if would_have_triggered > 0:
            success_rate = successful_interventions / would_have_triggered

            # Update effectiveness score
            policy.effectiveness_score = (policy.effectiveness_score + success_rate) / 2

            # Adjust confidence based on effectiveness
            if policy.effectiveness_score > 0.8:
                policy.confidence = min(1.0, policy.confidence * 1.1)
            elif policy.effectiveness_score < 0.3:
                policy.confidence = max(0.1, policy.confidence * 0.8)

        return policy

    def _would_policy_trigger(self, policy: Policy, signal: OrgSignal) -> bool:
        """Check if a policy would trigger for a given signal"""
        for condition in policy.conditions:
            if not self._evaluate_condition(condition, signal):
                return False
        return True

    def _evaluate_condition(
        self, condition: PolicyCondition, signal: OrgSignal
    ) -> bool:
        """Evaluate a single policy condition against a signal"""
        if condition.field == "file_path":
            signal_files = signal.files
            if condition.operator == "equals":
                return condition.value in signal_files
            elif condition.operator == "contains":
                return any(condition.value in file_path for file_path in signal_files)

        elif condition.field == "author":
            if condition.operator == "equals":
                return signal.author == condition.value

        elif condition.field == "team":
            if condition.operator == "equals":
                return signal.team == condition.value

        elif condition.field == "time":
            weekday = signal.timestamp.strftime("%A")
            if condition.operator == "in_list":
                return weekday in condition.value

        return False

    def generate_policy_recommendations(
        self, patterns: List[OrgPattern], existing_policies: List[Policy]
    ) -> List[str]:
        """
        Generate recommendations for new policies

        Args:
            patterns: Current organizational patterns
            existing_policies: Existing policies

        Returns:
            List of policy recommendations
        """
        recommendations = []

        # Find patterns not covered by existing policies
        covered_patterns = set()
        for policy in existing_policies:
            if policy.created_from_pattern:
                covered_patterns.add(policy.created_from_pattern)

        uncovered_patterns = [
            p for p in patterns if p.pattern_id not in covered_patterns
        ]

        # High-impact uncovered patterns
        high_impact_uncovered = [
            p
            for p in uncovered_patterns
            if p.impact_level in ["HIGH", "CRITICAL"] and p.confidence > 0.7
        ]

        if high_impact_uncovered:
            recommendations.append(
                f"Create policies for {len(high_impact_uncovered)} high-impact patterns not currently covered"
            )

        # Policies with low effectiveness
        ineffective_policies = [
            p for p in existing_policies if p.effectiveness_score < 0.3
        ]
        if ineffective_policies:
            recommendations.append(
                f"Review or retire {len(ineffective_policies)} policies with low effectiveness"
            )

        return recommendations


# Convenience function
def infer_policies(org_knowledge: OrgKnowledge) -> List[Policy]:
    """Convenience function to infer policies from organizational knowledge"""
    engine = PolicyInferenceEngine()
    return engine.infer_policies(org_knowledge)
