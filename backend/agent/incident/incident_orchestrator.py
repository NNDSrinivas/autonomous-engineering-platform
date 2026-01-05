"""
IncidentOrchestrator — Decision Brain

The central intelligence coordinator that orchestrates all incident analysis
components and makes Staff Engineer-level decisions. This is the "brain" of
the incident intelligence system that synthesizes insights from all analyzers
and provides autonomous engineering intelligence.

Key Capabilities:
- Coordinate all incident intelligence components
- Make autonomous decisions about incident response
- Generate Staff Engineer-level recommendations
- Prioritize actions based on business impact
- Escalate appropriately with evidence
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from .incident_store import IncidentStore, Incident, IncidentType
from .incident_graph import IncidentGraph, build_incident_graph
from .pattern_analyzer import PatternAnalyzer, AnalysisResult
from .flaky_test_detector import FlakyTestDetector, FlakyTest, TestSuiteHealth
from .regression_predictor import RegressionPredictor, RegressionRisk
from .blast_radius_analyzer import BlastRadiusAnalyzer, ImpactAnalysis

logger = logging.getLogger(__name__)


class SeverityLevel:
    """Severity levels for incident intelligence decisions"""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


@dataclass
class IncidentDecision:
    """Autonomous decision made by the incident orchestrator"""

    decision_type: str  # "auto_fix", "escalate", "quarantine", "investigate", "monitor"
    severity: str
    confidence: float  # 0.0 - 1.0
    reasoning: List[str]  # Human-readable reasoning
    recommended_actions: List[str]
    escalation_path: Optional[str]  # Who to escalate to
    timeline: str  # "immediate", "within_1h", "within_1d", "next_sprint"
    business_impact: str
    evidence: Dict[str, Any]  # Supporting evidence for the decision
    monitoring_requirements: List[str]


@dataclass
class IntelligenceSummary:
    """Comprehensive intelligence summary"""

    repo: str
    analysis_timestamp: datetime
    total_incidents: int
    critical_issues: List[str]
    systemic_problems: List[str]
    immediate_actions: List[str]
    preventive_measures: List[str]
    confidence_score: float
    next_review_date: datetime


class IncidentOrchestrator:
    """
    Central decision brain that coordinates all incident intelligence components
    and makes autonomous Staff Engineer-level decisions about incident response,
    prevention, and escalation.
    """

    def __init__(self, incident_store: IncidentStore):
        """Initialize the incident orchestrator with required components"""
        self.incident_store = incident_store
        self.pattern_analyzer = PatternAnalyzer()
        self.flaky_test_detector = FlakyTestDetector()
        self.regression_predictor = RegressionPredictor()
        self.blast_radius_analyzer = BlastRadiusAnalyzer()

        # Decision thresholds
        self.auto_fix_confidence_threshold = 0.8
        self.escalation_confidence_threshold = 0.6
        self.critical_impact_threshold = 0.7

        logger.info(
            "IncidentOrchestrator initialized - Autonomous Engineering Intelligence ready"
        )

    def analyze_repository_health(
        self, repo: str, lookback_days: int = 30
    ) -> IntelligenceSummary:
        """
        Perform comprehensive repository health analysis

        Args:
            repo: Repository to analyze
            lookback_days: Days of history to consider

        Returns:
            Complete intelligence summary with autonomous recommendations
        """
        logger.info(f"Performing comprehensive analysis for repository: {repo}")

        # Get incident data
        incidents = self.incident_store.get_recent_incidents(repo, limit=100)

        if not incidents:
            return self._generate_healthy_repo_summary(repo)

        # Build incident graph for relationship analysis
        incident_graph = build_incident_graph(incidents)

        # Run all analysis components
        pattern_analysis = self.pattern_analyzer.analyze_incidents(
            incidents, incident_graph
        )
        flaky_tests, test_health = self.flaky_test_detector.analyze_test_stability(
            incidents
        )

        # Synthesize intelligence
        critical_issues = self._identify_critical_issues(
            pattern_analysis, flaky_tests, test_health
        )
        systemic_problems = self._identify_systemic_problems(
            pattern_analysis, incident_graph
        )
        immediate_actions = self._prioritize_immediate_actions(
            critical_issues, systemic_problems
        )
        preventive_measures = self._generate_preventive_measures(
            pattern_analysis, flaky_tests
        )

        # Calculate overall confidence
        confidence_score = self._calculate_intelligence_confidence(
            pattern_analysis, len(flaky_tests), len(incidents)
        )

        return IntelligenceSummary(
            repo=repo,
            analysis_timestamp=datetime.now(),
            total_incidents=len(incidents),
            critical_issues=critical_issues,
            systemic_problems=systemic_problems,
            immediate_actions=immediate_actions,
            preventive_measures=preventive_measures,
            confidence_score=confidence_score,
            next_review_date=self._calculate_next_review_date(
                critical_issues, systemic_problems
            ),
        )

    def make_incident_decision(
        self, incident: Incident, context_incidents: Optional[List[Incident]] = None
    ) -> IncidentDecision:
        """
        Make autonomous decision about how to handle an incident

        Args:
            incident: The incident to make a decision about
            context_incidents: Related historical incidents for context

        Returns:
            Autonomous decision with reasoning and recommended actions
        """
        logger.info(f"Making autonomous decision for incident: {incident.id}")

        if context_incidents is None:
            context_incidents = self.incident_store.get_recent_incidents(
                incident.repo, limit=50
            )

        # Analyze incident in context
        incident_graph = build_incident_graph([incident] + context_incidents)
        pattern_analysis = self.pattern_analyzer.analyze_incidents(
            [incident] + context_incidents, incident_graph
        )

        # Check if this is part of a recurring pattern
        is_recurring = self._is_recurring_incident(incident, pattern_analysis)

        # Assess impact and severity
        severity = self._assess_incident_severity(incident, context_incidents)
        impact_analysis = self.blast_radius_analyzer.analyze_change_impact(
            incident.files, context_incidents
        )

        # Make decision based on analysis
        decision = self._determine_incident_action(
            incident, is_recurring, severity, impact_analysis
        )

        # Add supporting evidence
        decision.evidence = {
            "incident_id": incident.id,
            "recurring_pattern": is_recurring,
            "impact_analysis": {
                "blast_radius": impact_analysis.blast_radius,
                "risk_score": impact_analysis.risk_score,
                "affected_services": len(impact_analysis.directly_affected_services),
            },
            "similar_incidents": len(
                [
                    inc
                    for inc in context_incidents
                    if inc.failure_type == incident.failure_type
                ]
            ),
        }

        return decision

    def predict_and_prevent(
        self, changed_files: List[str], repo: str, author: Optional[str] = None
    ) -> RegressionRisk:
        """
        Predict regression risk and provide prevention recommendations

        Args:
            changed_files: Files being changed
            repo: Repository name
            author: Author making changes

        Returns:
            Regression risk with prevention recommendations
        """
        logger.info(
            f"Predicting regression risk for {len(changed_files)} files in {repo}"
        )

        # Get historical data
        incidents = self.incident_store.get_recent_incidents(repo, limit=100)

        # Predict regression risk
        risk = self.regression_predictor.predict_regression_risk(
            changed_files, incidents, author=author
        )

        # Enhance with blast radius analysis
        impact_analysis = self.blast_radius_analyzer.analyze_change_impact(
            changed_files, incidents
        )

        # Augment recommendations with system-level thinking
        enhanced_recommendations = (
            risk.recommendations + impact_analysis.recommendations
        )
        risk.recommendations = list(dict.fromkeys(enhanced_recommendations))[
            :8
        ]  # Remove duplicates, limit

        # Add preventive measures if high risk
        if risk.risk_level in ["HIGH", "CRITICAL"]:
            preventive_measures = self._generate_preventive_measures_for_changes(
                risk, impact_analysis, incidents
            )
            risk.recommendations.extend(preventive_measures)

        return risk

    def handle_ci_failure(self, ci_event: Dict[str, Any]) -> IncidentDecision:
        """
        Handle CI failure with incident-level intelligence

        Args:
            ci_event: CI failure event data

        Returns:
            Autonomous decision about how to handle the CI failure
        """
        logger.info("Handling CI failure with incident intelligence")

        # Create incident from CI event
        incident = self._create_incident_from_ci_event(ci_event)

        # Record the incident
        self.incident_store.record_incident(incident)

        # Get context
        context_incidents = self.incident_store.get_recent_incidents(
            incident.repo, limit=50
        )

        # Check for flaky test patterns
        if incident.incident_type == IncidentType.TEST_FAILURE:
            flaky_tests, _ = self.flaky_test_detector.analyze_test_stability(
                context_incidents + [incident]
            )

            # If this looks like a flaky test, handle differently
            for flaky_test in flaky_tests:
                if any(
                    file_path in flaky_test.test_path for file_path in incident.files
                ):
                    return self._handle_flaky_test_failure(incident, flaky_test)

        # Make standard incident decision
        return self.make_incident_decision(incident, context_incidents)

    def _identify_critical_issues(
        self,
        pattern_analysis: AnalysisResult,
        flaky_tests: List[FlakyTest],
        test_health: TestSuiteHealth,
    ) -> List[str]:
        """Identify critical issues requiring immediate attention"""
        issues = []

        # Critical systemic issues
        critical_systemic = [
            si for si in pattern_analysis.systemic_issues if si.severity == "CRITICAL"
        ]
        if critical_systemic:
            issues.append(
                f"CRITICAL: {len(critical_systemic)} systemic issues requiring immediate action"
            )

        # Critical flaky tests
        critical_flaky = [ft for ft in flaky_tests if ft.impact_level == "CRITICAL"]
        if critical_flaky:
            issues.append(
                f"CRITICAL: {len(critical_flaky)} critical flaky tests blocking pipeline"
            )

        # High-frequency recurring failures
        high_freq_failures = [
            rf for rf in pattern_analysis.recurring_failures if rf.failure_rate > 1.0
        ]
        if high_freq_failures:
            issues.append(
                f"HIGH: {len(high_freq_failures)} files failing daily or more"
            )

        # Test suite health
        if test_health.overall_stability < 0.5:
            issues.append(
                "CRITICAL: Test suite stability below 50% - pipeline unreliable"
            )

        return issues

    def _identify_systemic_problems(
        self, pattern_analysis: AnalysisResult, incident_graph: IncidentGraph
    ) -> List[str]:
        """Identify systemic problems affecting multiple components"""
        problems = []

        # Architectural issues
        arch_issues = [
            si
            for si in pattern_analysis.systemic_issues
            if si.issue_type == "architecture"
        ]
        if arch_issues:
            problems.append("Architecture: Cascading failures indicate tight coupling")

        # Process issues
        process_issues = [
            si for si in pattern_analysis.systemic_issues if si.issue_type == "process"
        ]
        if process_issues:
            problems.append("Process: High deployment/build failure rate")

        # Hotspots from graph analysis
        hotspots = incident_graph.get_patterns_by_type("hotspot")
        if len(hotspots) >= 3:
            problems.append(
                f"Quality: {len(hotspots)} failure hotspots need refactoring"
            )

        # Author patterns (knowledge issues)
        author_patterns = incident_graph.get_patterns_by_type("author_pattern")
        if len(author_patterns) >= 2:
            problems.append("Knowledge: Multiple authors with repeated incidents")

        return problems

    def _prioritize_immediate_actions(
        self, critical_issues: List[str], systemic_problems: List[str]
    ) -> List[str]:
        """Prioritize actions that need immediate attention"""
        actions = []

        # Handle critical issues first
        if any("CRITICAL" in issue for issue in critical_issues):
            actions.append("🚨 Form incident response team immediately")
            actions.append(
                "🔒 Consider deployment freeze until critical issues resolved"
            )

        # Address test suite issues
        if any("Test suite" in issue for issue in critical_issues):
            actions.append("🧪 Quarantine flaky tests and stabilize test suite")

        # Address hotspots
        if any("hotspots" in problem for problem in systemic_problems):
            actions.append("🔥 Refactor failure hotspots with highest business impact")

        # Address architectural issues
        if any("Architecture" in problem for problem in systemic_problems):
            actions.append("🏗️ Architecture review - add circuit breakers and bulkheads")

        # Address process issues
        if any("Process" in problem for problem in systemic_problems):
            actions.append("⚙️ CI/CD pipeline reliability review and hardening")

        return actions[:5]  # Top 5 priorities

    def _generate_preventive_measures(
        self, pattern_analysis: AnalysisResult, flaky_tests: List[FlakyTest]
    ) -> List[str]:
        """Generate preventive measures to avoid future incidents"""
        measures = []

        # Based on recurring failures
        if pattern_analysis.recurring_failures:
            measures.append(
                "Implement pre-commit hooks for files with high failure rates"
            )

        # Based on flaky tests
        if len(flaky_tests) > 5:
            measures.append("Implement flaky test quarantine system")
            measures.append("Set up automated test stability monitoring")

        # Based on systemic issues
        for issue in pattern_analysis.systemic_issues:
            if issue.issue_type == "architecture":
                measures.append("Implement service mesh for better fault isolation")
            elif issue.issue_type == "process":
                measures.append("Add deployment smoke tests and rollback automation")
            elif issue.issue_type == "knowledge":
                measures.append("Implement mandatory peer review for high-risk files")

        return measures[:6]

    def _is_recurring_incident(
        self, incident: Incident, analysis: AnalysisResult
    ) -> bool:
        """Check if incident is part of a recurring pattern"""
        for recurring_failure in analysis.recurring_failures:
            if any(
                file_path in incident.files for file_path in [recurring_failure.entity]
            ):
                return True
        return False

    def _assess_incident_severity(
        self, incident: Incident, context: List[Incident]
    ) -> str:
        """Assess incident severity based on context"""
        # Start with incident's stated severity
        base_severity = getattr(incident, "severity", "MEDIUM")

        # Escalate based on frequency
        similar_recent = [
            inc
            for inc in context
            if (
                inc.failure_type == incident.failure_type
                and (incident.timestamp - inc.timestamp).days <= 7
            )
        ]

        if len(similar_recent) >= 5:
            return SeverityLevel.CRITICAL
        elif len(similar_recent) >= 3:
            return SeverityLevel.HIGH
        elif incident.incident_type == IncidentType.SECURITY_INCIDENT:
            return SeverityLevel.CRITICAL
        else:
            return base_severity

    def _determine_incident_action(
        self,
        incident: Incident,
        is_recurring: bool,
        severity: str,
        impact: ImpactAnalysis,
    ) -> IncidentDecision:
        """Determine the appropriate action for an incident"""

        reasoning = []
        recommended_actions = []

        # Determine decision type based on analysis
        if severity == SeverityLevel.CRITICAL or impact.blast_radius == "SYSTEM_WIDE":
            decision_type = "escalate"
            escalation_path = "senior_engineer"
            timeline = "immediate"
            reasoning.append("Critical severity or system-wide impact")

        elif is_recurring and impact.risk_score > 0.5:
            decision_type = "investigate"
            escalation_path = "team_lead"
            timeline = "within_1h"
            reasoning.append("Recurring pattern with moderate risk")

        elif incident.incident_type == IncidentType.FLAKY_TEST:
            decision_type = "quarantine"
            escalation_path = None
            timeline = "within_1d"
            reasoning.append("Flaky test should be quarantined")

        else:
            decision_type = "auto_fix"
            escalation_path = None
            timeline = "immediate"
            reasoning.append("Standard incident suitable for auto-repair")

        # Generate specific recommendations
        if decision_type == "escalate":
            recommended_actions = [
                "Notify on-call engineer immediately",
                "Create incident channel",
                "Prepare rollback plan",
            ]
        elif decision_type == "quarantine":
            recommended_actions = [
                "Quarantine flaky test",
                "Create stabilization task",
                "Notify test owners",
            ]
        else:
            recommended_actions = [
                "Apply automated fix",
                "Monitor for resolution",
                "Update incident tracking",
            ]

        confidence = 0.8 if decision_type in ["escalate", "quarantine"] else 0.6
        business_impact = self._assess_business_impact(severity, impact)

        return IncidentDecision(
            decision_type=decision_type,
            severity=severity,
            confidence=confidence,
            reasoning=reasoning,
            recommended_actions=recommended_actions,
            escalation_path=escalation_path,
            timeline=timeline,
            business_impact=business_impact,
            evidence={},  # Will be filled by caller
            monitoring_requirements=self._generate_monitoring_requirements(
                incident, impact
            ),
        )

    def _assess_business_impact(self, severity: str, impact: ImpactAnalysis) -> str:
        """Assess business impact of an incident"""
        if severity == SeverityLevel.CRITICAL:
            return "Service disruption affecting customers"
        elif impact.blast_radius == "SYSTEM_WIDE":
            return "Multiple services affected, potential customer impact"
        elif len(impact.directly_affected_services) > 1:
            return "Limited service impact, internal systems affected"
        else:
            return "Minimal impact, development workflow affected"

    def _generate_monitoring_requirements(
        self, incident: Incident, impact: ImpactAnalysis
    ) -> List[str]:
        """Generate monitoring requirements for incident resolution"""
        requirements = []

        if impact.directly_affected_services:
            requirements.append(
                f"Monitor health of: {', '.join(impact.directly_affected_services)}"
            )

        if incident.incident_type in [
            IncidentType.PERFORMANCE_REGRESSION,
            IncidentType.RUNTIME_ERROR,
        ]:
            requirements.append("Monitor application performance metrics")

        if impact.blast_radius in ["CROSS_SERVICE", "SYSTEM_WIDE"]:
            requirements.append("Monitor inter-service communication")

        return requirements

    def _calculate_intelligence_confidence(
        self, analysis: AnalysisResult, flaky_test_count: int, incident_count: int
    ) -> float:
        """Calculate overall confidence in intelligence analysis"""
        # Base confidence from pattern analysis
        base_confidence = analysis.confidence_score

        # Data quality factor
        data_quality = min(1.0, incident_count / 20.0)  # More data = higher confidence

        # Analysis completeness factor
        completeness = 0.5  # Base
        if analysis.recurring_failures:
            completeness += 0.2
        if analysis.systemic_issues:
            completeness += 0.2
        if flaky_test_count > 0:
            completeness += 0.1

        return min(1.0, base_confidence * 0.5 + data_quality * 0.3 + completeness * 0.2)

    def _calculate_next_review_date(
        self, critical_issues: List[str], systemic_problems: List[str]
    ) -> datetime:
        """Calculate when next review should happen"""
        from datetime import timedelta

        if critical_issues:
            return datetime.now() + timedelta(
                days=1
            )  # Daily review for critical issues
        elif systemic_problems:
            return datetime.now() + timedelta(days=7)  # Weekly for systemic problems
        else:
            return datetime.now() + timedelta(days=30)  # Monthly for stable repos

    def _generate_healthy_repo_summary(self, repo: str) -> IntelligenceSummary:
        """Generate summary for repositories with no incidents"""
        return IntelligenceSummary(
            repo=repo,
            analysis_timestamp=datetime.now(),
            total_incidents=0,
            critical_issues=[],
            systemic_problems=[],
            immediate_actions=["Continue monitoring for patterns"],
            preventive_measures=[
                "Maintain current development practices",
                "Consider implementing proactive monitoring",
            ],
            confidence_score=0.9,
            next_review_date=datetime.now() + timedelta(days=90),
        )
