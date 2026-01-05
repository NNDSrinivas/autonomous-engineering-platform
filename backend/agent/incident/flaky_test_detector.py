"""
FlakyTestDetector — SRE-Grade Capability

Advanced flaky test detection system that identifies non-deterministic test
failures using statistical analysis, temporal patterns, and success/failure
distributions. This enables NAVI to make SRE-level decisions about test
stability and recommend stabilization or quarantine strategies.

Key Capabilities:
- Detect flaky tests with high confidence
- Analyze flakiness patterns and root causes
- Recommend stabilization strategies
- Quarantine management for unstable tests
- Impact analysis on CI pipeline reliability
"""

import logging
import statistics
from collections import defaultdict, Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple
from .incident_store import Incident, IncidentType

logger = logging.getLogger(__name__)


@dataclass
class TestStability:
    """Represents the stability characteristics of a test"""

    test_path: str
    total_runs: int
    failures: int
    successes: int
    failure_rate: float
    flakiness_score: float  # 0.0 = stable, 1.0 = maximally flaky
    first_failure: datetime
    last_failure: datetime
    failure_pattern: str  # "intermittent", "trending", "burst", "random"
    confidence: float


@dataclass
class FlakyTest:
    """Represents a confirmed flaky test with analysis and recommendations"""

    test_path: str
    stability: TestStability
    root_cause_hypothesis: str
    impact_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    affected_branches: List[str]
    affected_authors: List[str]
    failure_incidents: List[str]
    recommended_action: str  # "STABILIZE", "QUARANTINE", "INVESTIGATE", "DISABLE"
    stabilization_priority: int  # 1-10, higher = more urgent
    estimated_fix_effort: str  # "LOW", "MEDIUM", "HIGH"


@dataclass
class TestSuiteHealth:
    """Overall health assessment of the test suite"""

    total_tests: int
    stable_tests: int
    flaky_tests: int
    quarantined_tests: int
    overall_stability: float  # 0.0-1.0
    pipeline_impact: str
    recommendations: List[str]


class FlakyTestDetector:
    """
    SRE-grade flaky test detector that uses statistical analysis and
    temporal patterns to identify non-deterministic test failures with
    high confidence and provide actionable recommendations.
    """

    def __init__(
        self,
        min_runs_threshold: int = 5,
        flakiness_threshold: float = 0.3,
        confidence_threshold: float = 0.7,
    ):
        """
        Initialize the flaky test detector

        Args:
            min_runs_threshold: Minimum test runs to consider for analysis
            flakiness_threshold: Minimum flakiness score to classify as flaky
            confidence_threshold: Minimum confidence to report as flaky
        """
        self.min_runs_threshold = min_runs_threshold
        self.flakiness_threshold = flakiness_threshold
        self.confidence_threshold = confidence_threshold
        logger.info("FlakyTestDetector initialized with SRE-grade capabilities")

    def analyze_test_stability(
        self, incidents: List[Incident]
    ) -> Tuple[List[FlakyTest], TestSuiteHealth]:
        """
        Analyze test stability from incident data

        Args:
            incidents: List of incidents to analyze

        Returns:
            Tuple of (flaky tests, overall test suite health)
        """
        logger.info(f"Analyzing test stability from {len(incidents)} incidents")

        # Extract test-related incidents
        test_incidents = self._filter_test_incidents(incidents)
        logger.info(f"Found {len(test_incidents)} test-related incidents")

        # Analyze each test's stability
        test_stability_map = self._analyze_individual_tests(test_incidents)

        # Identify flaky tests
        flaky_tests = self._identify_flaky_tests(test_stability_map, test_incidents)

        # Assess overall test suite health
        suite_health = self._assess_suite_health(test_stability_map, flaky_tests)

        logger.info(f"Detected {len(flaky_tests)} flaky tests")
        return flaky_tests, suite_health

    def _filter_test_incidents(self, incidents: List[Incident]) -> List[Incident]:
        """Filter incidents to only test-related ones"""
        test_incidents = []

        for incident in incidents:
            # Include explicit test incident types
            if incident.incident_type in [
                IncidentType.TEST_FAILURE,
                IncidentType.FLAKY_TEST,
            ]:
                test_incidents.append(incident)
                continue

            # Include CI failures that involve test files
            if incident.incident_type == IncidentType.CI_FAILURE:
                test_files = [f for f in incident.files if self._is_test_file(f)]
                if test_files:
                    test_incidents.append(incident)
                    continue

            # Include incidents where error message suggests test failure
            if incident.error_message and self._error_suggests_test_failure(
                incident.error_message
            ):
                test_incidents.append(incident)

        return test_incidents

    def _analyze_individual_tests(
        self, test_incidents: List[Incident]
    ) -> Dict[str, TestStability]:
        """Analyze stability for each individual test"""
        test_data = defaultdict(list)

        # Group incidents by test file
        for incident in test_incidents:
            for file_path in incident.files:
                if self._is_test_file(file_path):
                    test_data[file_path].append(incident)

        stability_map = {}

        for test_path, incidents in test_data.items():
            if len(incidents) >= self.min_runs_threshold:
                stability = self._calculate_test_stability(test_path, incidents)
                if stability.confidence >= self.confidence_threshold:
                    stability_map[test_path] = stability

        return stability_map

    def _calculate_test_stability(
        self, test_path: str, incidents: List[Incident]
    ) -> TestStability:
        """Calculate stability metrics for a test"""
        # Sort incidents by timestamp
        sorted_incidents = sorted(incidents, key=lambda x: x.timestamp)

        # Count failures vs total runs (approximated from incidents)
        failures = len(incidents)

        # Estimate total runs based on time span and typical CI frequency
        if len(incidents) >= 2:
            time_span = sorted_incidents[-1].timestamp - sorted_incidents[0].timestamp
            # Rough estimate: assume CI runs multiple times per day
            estimated_runs = max(
                failures, int(time_span.total_seconds() / (6 * 3600))
            )  # Every 6 hours
        else:
            estimated_runs = failures + 1  # Conservative estimate

        successes = max(0, estimated_runs - failures)
        failure_rate = failures / estimated_runs if estimated_runs > 0 else 0.0

        # Calculate flakiness score based on temporal distribution
        flakiness_score = self._calculate_flakiness_score(
            sorted_incidents, failure_rate
        )

        # Determine failure pattern
        failure_pattern = self._determine_failure_pattern(sorted_incidents)

        # Calculate confidence based on data quality and consistency
        confidence = self._calculate_stability_confidence(incidents, failure_rate)

        return TestStability(
            test_path=test_path,
            total_runs=estimated_runs,
            failures=failures,
            successes=successes,
            failure_rate=failure_rate,
            flakiness_score=flakiness_score,
            first_failure=sorted_incidents[0].timestamp,
            last_failure=sorted_incidents[-1].timestamp,
            failure_pattern=failure_pattern,
            confidence=confidence,
        )

    def _calculate_flakiness_score(
        self, sorted_incidents: List[Incident], failure_rate: float
    ) -> float:
        """
        Calculate flakiness score based on temporal distribution and failure rate

        A truly flaky test will have:
        - Intermittent failures over time (not clustered)
        - Moderate failure rate (not 0% or 100%)
        - Inconsistent error messages
        """
        if len(sorted_incidents) < 2:
            return 0.0

        # Factor 1: Temporal distribution (0.0 = clustered, 1.0 = well distributed)
        time_span = sorted_incidents[-1].timestamp - sorted_incidents[0].timestamp
        if time_span.total_seconds() == 0:
            temporal_factor = 0.0
        else:
            # Calculate coefficient of variation for time intervals
            time_intervals = []
            for i in range(1, len(sorted_incidents)):
                interval = (
                    sorted_incidents[i].timestamp - sorted_incidents[i - 1].timestamp
                ).total_seconds()
                time_intervals.append(interval)

            if len(time_intervals) >= 2:
                mean_interval = statistics.mean(time_intervals)
                std_interval = (
                    statistics.stdev(time_intervals) if len(time_intervals) > 1 else 0
                )
                temporal_factor = (
                    min(1.0, std_interval / mean_interval) if mean_interval > 0 else 0.0
                )
            else:
                temporal_factor = 0.5

        # Factor 2: Failure rate optimum (most flaky around 50%)
        rate_factor = (
            1.0 - abs(failure_rate - 0.5) * 2
        )  # Peak at 0.5, drops to 0 at 0.0 and 1.0

        # Factor 3: Error message diversity (flaky tests often have varying errors)
        error_messages = [
            inc.error_message for inc in sorted_incidents if inc.error_message
        ]
        if error_messages:
            unique_errors = len(set(error_messages))
            error_diversity = min(1.0, unique_errors / len(error_messages))
        else:
            error_diversity = 0.0

        # Combine factors with weights
        flakiness_score = (
            temporal_factor * 0.4 + rate_factor * 0.4 + error_diversity * 0.2
        )

        return min(1.0, flakiness_score)

    def _determine_failure_pattern(self, sorted_incidents: List[Incident]) -> str:
        """Determine the pattern of failures"""
        if len(sorted_incidents) < 3:
            return "insufficient_data"

        # Calculate time intervals between failures
        intervals = []
        for i in range(1, len(sorted_incidents)):
            interval = (
                sorted_incidents[i].timestamp - sorted_incidents[i - 1].timestamp
            ).total_seconds()
            intervals.append(interval)

        # Analyze interval patterns
        mean_interval = statistics.mean(intervals)
        std_interval = statistics.stdev(intervals) if len(intervals) > 1 else 0

        coefficient_of_variation = (
            std_interval / mean_interval if mean_interval > 0 else 0
        )

        # Classify pattern based on interval analysis
        if coefficient_of_variation < 0.3:
            return "periodic"  # Regular intervals
        elif coefficient_of_variation > 1.0:
            return "burst"  # Clustered failures
        elif all(interval < 3600 for interval in intervals):  # All within 1 hour
            return "cascade"  # Quick succession
        else:
            return "intermittent"  # Irregular but distributed

    def _calculate_stability_confidence(
        self, incidents: List[Incident], failure_rate: float
    ) -> float:
        """Calculate confidence in the stability assessment"""
        # More incidents = higher confidence
        sample_factor = min(1.0, len(incidents) / 10.0)

        # Time span factor (longer observation = higher confidence)
        if len(incidents) >= 2:
            time_span = incidents[-1].timestamp - incidents[0].timestamp
            time_factor = min(1.0, time_span.days / 30.0)  # Max confidence at 30+ days
        else:
            time_factor = 0.1

        # Consistency factor (consistent error types = higher confidence)
        error_types = [inc.failure_type for inc in incidents if inc.failure_type]
        if error_types:
            most_common_count = Counter(error_types).most_common(1)[0][1]
            consistency_factor = most_common_count / len(error_types)
        else:
            consistency_factor = 0.5

        confidence = sample_factor * 0.4 + time_factor * 0.4 + consistency_factor * 0.2
        return min(1.0, confidence)

    def _identify_flaky_tests(
        self, stability_map: Dict[str, TestStability], incidents: List[Incident]
    ) -> List[FlakyTest]:
        """Identify tests that are confirmed flaky"""
        flaky_tests = []

        for test_path, stability in stability_map.items():
            if stability.flakiness_score >= self.flakiness_threshold:
                # Get incidents for this test
                test_incidents = [inc for inc in incidents if test_path in inc.files]

                # Analyze impact and generate recommendations
                flaky_test = self._analyze_flaky_test(
                    test_path, stability, test_incidents
                )
                flaky_tests.append(flaky_test)

        # Sort by priority (highest first)
        return sorted(flaky_tests, key=lambda x: x.stabilization_priority, reverse=True)

    def _analyze_flaky_test(
        self, test_path: str, stability: TestStability, incidents: List[Incident]
    ) -> FlakyTest:
        """Analyze a flaky test and generate recommendations"""
        # Determine root cause hypothesis
        root_cause = self._hypothesize_root_cause(stability, incidents)

        # Calculate impact level
        impact_level = self._calculate_impact_level(stability, incidents)

        # Get affected branches and authors
        affected_branches = list(set(inc.branch for inc in incidents if inc.branch))
        affected_authors = list(set(inc.author for inc in incidents if inc.author))

        # Determine recommended action
        recommended_action = self._determine_recommended_action(stability, impact_level)

        # Calculate stabilization priority
        priority = self._calculate_stabilization_priority(
            stability, impact_level, len(incidents)
        )

        # Estimate fix effort
        fix_effort = self._estimate_fix_effort(stability, root_cause)

        return FlakyTest(
            test_path=test_path,
            stability=stability,
            root_cause_hypothesis=root_cause,
            impact_level=impact_level,
            affected_branches=affected_branches,
            affected_authors=affected_authors,
            failure_incidents=[inc.id for inc in incidents],
            recommended_action=recommended_action,
            stabilization_priority=priority,
            estimated_fix_effort=fix_effort,
        )

    def _hypothesize_root_cause(
        self, stability: TestStability, incidents: List[Incident]
    ) -> str:
        """Generate hypothesis for the root cause of flakiness"""
        # Analyze error patterns
        error_messages = [inc.error_message for inc in incidents if inc.error_message]

        if not error_messages:
            return "Unknown - no error messages available"

        # Look for common flaky test patterns
        error_text = " ".join(error_messages).lower()

        if any(
            keyword in error_text for keyword in ["timeout", "connection", "network"]
        ):
            return "Network/timeout issues - likely external dependency"
        elif any(keyword in error_text for keyword in ["race", "concurrent", "async"]):
            return "Race condition - concurrent execution issues"
        elif any(keyword in error_text for keyword in ["random", "uuid", "timestamp"]):
            return "Non-deterministic data - time or random values"
        elif any(keyword in error_text for keyword in ["file", "resource", "cleanup"]):
            return "Resource cleanup issues - test isolation problems"
        elif any(
            keyword in error_text for keyword in ["order", "sequence", "dependency"]
        ):
            return "Test order dependency - tests affecting each other"
        elif stability.failure_pattern == "periodic":
            return "Environmental issue - periodic system condition"
        elif stability.failure_pattern == "burst":
            return "System load issue - fails under specific conditions"
        else:
            return f"Pattern-based hypothesis - {stability.failure_pattern} failures"

    def _calculate_impact_level(
        self, stability: TestStability, incidents: List[Incident]
    ) -> str:
        """Calculate the impact level of the flaky test"""
        # Consider failure rate, frequency, and affected scope
        impact_score = 0

        # Failure rate impact
        if stability.failure_rate > 0.5:
            impact_score += 3
        elif stability.failure_rate > 0.3:
            impact_score += 2
        else:
            impact_score += 1

        # Frequency impact (how often it runs)
        if len(incidents) > 10:
            impact_score += 2
        elif len(incidents) > 5:
            impact_score += 1

        # Time span impact (longer = more disruptive)
        time_span = stability.last_failure - stability.first_failure
        if time_span.days > 30:
            impact_score += 2
        elif time_span.days > 7:
            impact_score += 1

        # Affected branches (main/master = higher impact)
        branches = set(inc.branch for inc in incidents if inc.branch)
        if any(branch in ["main", "master", "develop"] for branch in branches):
            impact_score += 2

        if impact_score >= 7:
            return "CRITICAL"
        elif impact_score >= 5:
            return "HIGH"
        elif impact_score >= 3:
            return "MEDIUM"
        else:
            return "LOW"

    def _determine_recommended_action(
        self, stability: TestStability, impact_level: str
    ) -> str:
        """Determine the recommended action for a flaky test"""
        # High-impact or high-flakiness tests should be prioritized
        if impact_level == "CRITICAL" or stability.flakiness_score > 0.8:
            if stability.failure_rate > 0.7:
                return "DISABLE"  # Too unreliable
            else:
                return "QUARANTINE"  # Isolate while fixing
        elif impact_level == "HIGH":
            return "STABILIZE"  # Fix immediately
        elif stability.flakiness_score > 0.6:
            return "INVESTIGATE"  # Needs attention
        else:
            return "MONITOR"  # Watch for changes

    def _calculate_stabilization_priority(
        self, stability: TestStability, impact_level: str, incident_count: int
    ) -> int:
        """Calculate priority for stabilization (1-10)"""
        priority = 0

        # Impact level contribution
        impact_scores = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        priority += impact_scores.get(impact_level, 1)

        # Flakiness score contribution
        priority += int(stability.flakiness_score * 3)

        # Incident frequency contribution
        if incident_count >= 10:
            priority += 2
        elif incident_count >= 5:
            priority += 1

        # Recent activity boost
        days_since_last = (datetime.now() - stability.last_failure).days
        if days_since_last <= 1:
            priority += 1

        return min(10, max(1, priority))

    def _estimate_fix_effort(self, stability: TestStability, root_cause: str) -> str:
        """Estimate effort required to fix the flaky test"""
        # Base estimation on root cause type
        if "network" in root_cause.lower() or "timeout" in root_cause.lower():
            return "MEDIUM"  # Requires mocking or retry logic
        elif "race" in root_cause.lower() or "concurrent" in root_cause.lower():
            return "HIGH"  # Complex synchronization issues
        elif "cleanup" in root_cause.lower() or "isolation" in root_cause.lower():
            return "LOW"  # Usually straightforward cleanup
        elif "dependency" in root_cause.lower():
            return "MEDIUM"  # Requires test restructuring
        elif "environmental" in root_cause.lower():
            return "HIGH"  # May require infrastructure changes
        else:
            # Use flakiness score as proxy
            if stability.flakiness_score > 0.8:
                return "HIGH"
            elif stability.flakiness_score > 0.5:
                return "MEDIUM"
            else:
                return "LOW"

    def _assess_suite_health(
        self, stability_map: Dict[str, TestStability], flaky_tests: List[FlakyTest]
    ) -> TestSuiteHealth:
        """Assess overall test suite health"""
        total_tests = len(stability_map)
        flaky_count = len(flaky_tests)
        stable_count = total_tests - flaky_count

        # Calculate overall stability
        if total_tests > 0:
            overall_stability = stable_count / total_tests
        else:
            overall_stability = 1.0

        # Assess pipeline impact
        critical_flaky = len(
            [ft for ft in flaky_tests if ft.impact_level == "CRITICAL"]
        )
        high_flaky = len([ft for ft in flaky_tests if ft.impact_level == "HIGH"])

        if critical_flaky > 0:
            pipeline_impact = "SEVERE - Critical flaky tests blocking pipeline"
        elif high_flaky > 3:
            pipeline_impact = "HIGH - Multiple high-impact flaky tests"
        elif flaky_count > total_tests * 0.2:  # >20% flaky
            pipeline_impact = "MEDIUM - High flakiness rate affecting reliability"
        else:
            pipeline_impact = "LOW - Manageable flakiness levels"

        # Generate recommendations
        recommendations = self._generate_suite_recommendations(
            flaky_tests, overall_stability
        )

        return TestSuiteHealth(
            total_tests=total_tests,
            stable_tests=stable_count,
            flaky_tests=flaky_count,
            quarantined_tests=0,  # Would be tracked separately
            overall_stability=overall_stability,
            pipeline_impact=pipeline_impact,
            recommendations=recommendations,
        )

    def _generate_suite_recommendations(
        self, flaky_tests: List[FlakyTest], overall_stability: float
    ) -> List[str]:
        """Generate recommendations for test suite health"""
        recommendations = []

        if overall_stability < 0.8:
            recommendations.append(
                "🚨 URGENT: Test suite stability below 80% - immediate attention required"
            )

        critical_tests = [ft for ft in flaky_tests if ft.impact_level == "CRITICAL"]
        if critical_tests:
            recommendations.append(
                f"⛔ Disable/quarantine {len(critical_tests)} critical flaky tests immediately"
            )

        high_impact_tests = [ft for ft in flaky_tests if ft.impact_level == "HIGH"]
        if len(high_impact_tests) > 2:
            recommendations.append(
                f"🔥 Prioritize fixing {len(high_impact_tests)} high-impact flaky tests"
            )

        # Pattern-based recommendations
        race_condition_tests = [
            ft for ft in flaky_tests if "race" in ft.root_cause_hypothesis.lower()
        ]
        if len(race_condition_tests) >= 2:
            recommendations.append(
                "🏃 Multiple race condition tests detected - review test parallelization"
            )

        timeout_tests = [
            ft for ft in flaky_tests if "timeout" in ft.root_cause_hypothesis.lower()
        ]
        if len(timeout_tests) >= 2:
            recommendations.append(
                "⏱️ Multiple timeout-related flaky tests - review external dependencies"
            )

        if len(flaky_tests) > 5:
            recommendations.append(
                "🛠️ Consider implementing flaky test quarantine system"
            )
            recommendations.append("📊 Set up flaky test monitoring dashboard")

        return recommendations

    def _is_test_file(self, file_path: str) -> bool:
        """Determine if a file is a test file"""
        test_indicators = [
            "test",
            "spec",
            "__test__",
            ".test.",
            ".spec.",
            "_test.py",
            "_spec.py",
            "test_",
            "spec_",
        ]
        return any(indicator in file_path.lower() for indicator in test_indicators)

    def _error_suggests_test_failure(self, error_message: str) -> bool:
        """Determine if error message suggests test failure"""
        test_keywords = [
            "test failed",
            "assertion",
            "assert",
            "expect",
            "junit",
            "pytest",
            "test case",
            "test suite",
        ]
        return any(keyword in error_message.lower() for keyword in test_keywords)
