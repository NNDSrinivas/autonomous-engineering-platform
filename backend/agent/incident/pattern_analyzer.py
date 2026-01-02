"""
PatternAnalyzer — Root Cause Analysis at Scale

Advanced pattern detection engine that identifies systemic issues across 
incidents to enable Staff Engineer-level reasoning. This system analyzes
recurring failures, problematic files, temporal patterns, and cross-system
relationships to understand the "why" behind failures.

Key Capabilities:
- Detect recurring failures across time and systems
- Identify systemic vs. transient issues  
- Find root causes beyond individual incidents
- Generate actionable insights for prevention
"""

import logging
from collections import defaultdict, Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Set, Tuple, Optional
from .incident_store import Incident, IncidentType
from .incident_graph import IncidentGraph

logger = logging.getLogger(__name__)

@dataclass
class RecurringFailure:
    """Represents a pattern of recurring failures"""
    entity: str  # file, service, test, etc.
    entity_type: str
    failure_count: int
    incident_ids: List[str]
    first_occurrence: datetime
    last_occurrence: datetime
    failure_rate: float  # failures per day
    confidence: float
    root_cause_hypothesis: str
    suggested_remediation: str

@dataclass
class SystemicIssue:
    """Represents a systemic issue affecting multiple components"""
    issue_type: str  # "architecture", "process", "tooling", "knowledge"
    affected_entities: List[str]
    incident_count: int
    incident_ids: List[str] 
    severity: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    confidence: float
    description: str
    business_impact: str
    recommended_actions: List[str]
    estimated_effort: str  # "LOW", "MEDIUM", "HIGH"

@dataclass
class TemporalPattern:
    """Represents a time-based pattern in incidents"""
    pattern_type: str  # "spike", "trend", "cyclical", "cascade"
    time_range: Tuple[datetime, datetime]
    incident_ids: List[str]
    frequency: float  # incidents per unit time
    description: str
    trigger_hypothesis: str

@dataclass
class AnalysisResult:
    """Complete pattern analysis result"""
    total_incidents: int
    recurring_failures: List[RecurringFailure]
    systemic_issues: List[SystemicIssue]
    temporal_patterns: List[TemporalPattern]
    recommendations: List[str]
    confidence_score: float
    analysis_timestamp: datetime

class PatternAnalyzer:
    """
    Advanced pattern analyzer that identifies systemic issues and root causes
    from incident data, enabling Staff Engineer-level reasoning and decision making.
    """
    
    def __init__(self, min_recurrence_threshold: int = 3, min_confidence: float = 0.6):
        """
        Initialize the pattern analyzer
        
        Args:
            min_recurrence_threshold: Minimum incidents to consider a recurring failure
            min_confidence: Minimum confidence score for pattern inclusion
        """
        self.min_recurrence_threshold = min_recurrence_threshold
        self.min_confidence = min_confidence
        logger.info("PatternAnalyzer initialized for systemic issue detection")
    
    def analyze_incidents(self, incidents: List[Incident], incident_graph: Optional[IncidentGraph] = None) -> AnalysisResult:
        """
        Perform comprehensive pattern analysis on incidents
        
        Args:
            incidents: List of incidents to analyze
            incident_graph: Optional pre-built incident graph for enhanced analysis
            
        Returns:
            Complete analysis result with patterns and recommendations
        """
        logger.info(f"Analyzing {len(incidents)} incidents for systemic patterns")
        
        # Build or use provided incident graph
        if incident_graph is None:
            from .incident_graph import build_incident_graph
            incident_graph = build_incident_graph(incidents)
        
        # Analyze different pattern types
        recurring_failures = self._analyze_recurring_failures(incidents)
        systemic_issues = self._analyze_systemic_issues(incidents, incident_graph)
        temporal_patterns = self._analyze_temporal_patterns(incidents)
        
        # Generate high-level recommendations
        recommendations = self._generate_recommendations(recurring_failures, systemic_issues, temporal_patterns)
        
        # Calculate overall confidence
        confidence_score = self._calculate_confidence_score(recurring_failures, systemic_issues)
        
        return AnalysisResult(
            total_incidents=len(incidents),
            recurring_failures=recurring_failures,
            systemic_issues=systemic_issues,
            temporal_patterns=temporal_patterns,
            recommendations=recommendations,
            confidence_score=confidence_score,
            analysis_timestamp=datetime.now()
        )
    
    def _analyze_recurring_failures(self, incidents: List[Incident]) -> List[RecurringFailure]:
        """Identify recurring failures in files, tests, and services"""
        recurring_failures = []
        
        # Analyze file-based recurring failures
        file_failures = self._analyze_file_recurrence(incidents)
        recurring_failures.extend(file_failures)
        
        # Analyze test-based recurring failures
        test_failures = self._analyze_test_recurrence(incidents)
        recurring_failures.extend(test_failures)
        
        # Analyze service-based recurring failures
        service_failures = self._analyze_service_recurrence(incidents)
        recurring_failures.extend(service_failures)
        
        # Filter by confidence and threshold
        filtered_failures = [
            rf for rf in recurring_failures 
            if rf.failure_count >= self.min_recurrence_threshold and rf.confidence >= self.min_confidence
        ]
        
        logger.info(f"Identified {len(filtered_failures)} recurring failure patterns")
        return sorted(filtered_failures, key=lambda x: x.confidence, reverse=True)
    
    def _analyze_file_recurrence(self, incidents: List[Incident]) -> List[RecurringFailure]:
        """Analyze recurring failures at the file level"""
        file_incidents = defaultdict(list)
        
        # Group incidents by file
        for incident in incidents:
            for file_path in incident.files:
                file_incidents[file_path].append(incident)
        
        recurring_failures = []
        for file_path, file_incident_list in file_incidents.items():
            if len(file_incident_list) >= self.min_recurrence_threshold:
                # Calculate failure characteristics
                timestamps = [inc.timestamp for inc in file_incident_list]
                time_span = max(timestamps) - min(timestamps)
                failure_rate = len(file_incident_list) / max(1, time_span.days)
                
                # Determine root cause hypothesis
                failure_types = [inc.failure_type for inc in file_incident_list]
                most_common_failure = Counter(failure_types).most_common(1)[0][0]
                
                # Calculate confidence based on consistency and frequency
                confidence = self._calculate_recurrence_confidence(file_incident_list)
                
                recurring_failures.append(RecurringFailure(
                    entity=file_path,
                    entity_type="file",
                    failure_count=len(file_incident_list),
                    incident_ids=[inc.id for inc in file_incident_list],
                    first_occurrence=min(timestamps),
                    last_occurrence=max(timestamps),
                    failure_rate=failure_rate,
                    confidence=confidence,
                    root_cause_hypothesis=f"Recurring {most_common_failure} in {file_path}",
                    suggested_remediation=self._suggest_file_remediation(file_path, failure_types)
                ))
        
        return recurring_failures
    
    def _analyze_test_recurrence(self, incidents: List[Incident]) -> List[RecurringFailure]:
        """Analyze recurring test failures (flaky tests)"""
        test_incidents = defaultdict(list)
        
        # Find test-related incidents
        for incident in incidents:
            if incident.incident_type in [IncidentType.TEST_FAILURE, IncidentType.FLAKY_TEST]:
                for file_path in incident.files:
                    if self._is_test_file(file_path):
                        test_incidents[file_path].append(incident)
        
        recurring_failures = []
        for test_path, test_incident_list in test_incidents.items():
            if len(test_incident_list) >= 2:  # Lower threshold for tests
                timestamps = [inc.timestamp for inc in test_incident_list]
                time_span = max(timestamps) - min(timestamps)
                
                # Tests that fail over multiple days are likely flaky
                if time_span.days >= 1:
                    confidence = min(1.0, len(test_incident_list) / 5.0)
                    failure_rate = len(test_incident_list) / max(1, time_span.days)
                    
                    recurring_failures.append(RecurringFailure(
                        entity=test_path,
                        entity_type="test",
                        failure_count=len(test_incident_list),
                        incident_ids=[inc.id for inc in test_incident_list],
                        first_occurrence=min(timestamps),
                        last_occurrence=max(timestamps),
                        failure_rate=failure_rate,
                        confidence=confidence,
                        root_cause_hypothesis="Flaky test with non-deterministic behavior",
                        suggested_remediation="Stabilize test conditions or quarantine until fixed"
                    ))
        
        return recurring_failures
    
    def _analyze_service_recurrence(self, incidents: List[Incident]) -> List[RecurringFailure]:
        """Analyze recurring failures at the service level"""
        # This is a simplified implementation - in practice, you'd use service topology
        service_incidents = defaultdict(list)
        
        for incident in incidents:
            services = self._infer_services(incident.files)
            for service in services:
                service_incidents[service].append(incident)
        
        recurring_failures = []
        for service, service_incident_list in service_incidents.items():
            if len(service_incident_list) >= self.min_recurrence_threshold:
                timestamps = [inc.timestamp for inc in service_incident_list]
                confidence = self._calculate_recurrence_confidence(service_incident_list)
                
                if confidence >= self.min_confidence:
                    time_span = max(timestamps) - min(timestamps)
                    failure_rate = len(service_incident_list) / max(1, time_span.days)
                    
                    recurring_failures.append(RecurringFailure(
                        entity=service,
                        entity_type="service",
                        failure_count=len(service_incident_list),
                        incident_ids=[inc.id for inc in service_incident_list],
                        first_occurrence=min(timestamps),
                        last_occurrence=max(timestamps),
                        failure_rate=failure_rate,
                        confidence=confidence,
                        root_cause_hypothesis=f"Recurring issues in {service} service",
                        suggested_remediation=self._suggest_service_remediation(service, service_incident_list)
                    ))
        
        return recurring_failures
    
    def _analyze_systemic_issues(self, incidents: List[Incident], incident_graph: IncidentGraph) -> List[SystemicIssue]:
        """Identify systemic issues affecting multiple components"""
        systemic_issues = []
        
        # Analyze architectural issues
        arch_issues = self._analyze_architectural_issues(incidents, incident_graph)
        systemic_issues.extend(arch_issues)
        
        # Analyze process issues
        process_issues = self._analyze_process_issues(incidents)
        systemic_issues.extend(process_issues)
        
        # Analyze tooling issues
        tooling_issues = self._analyze_tooling_issues(incidents)
        systemic_issues.extend(tooling_issues)
        
        # Analyze knowledge/training issues
        knowledge_issues = self._analyze_knowledge_issues(incidents, incident_graph)
        systemic_issues.extend(knowledge_issues)
        
        logger.info(f"Identified {len(systemic_issues)} systemic issues")
        return sorted(systemic_issues, key=lambda x: x.confidence, reverse=True)
    
    def _analyze_architectural_issues(self, incidents: List[Incident], incident_graph: IncidentGraph) -> List[SystemicIssue]:
        """Identify architectural issues from cascade patterns"""
        issues = []
        
        # Look for cascade patterns in the incident graph
        cascade_patterns = incident_graph.get_patterns_by_type("cascade")
        
        if cascade_patterns:
            for pattern in cascade_patterns:
                if pattern.confidence >= self.min_confidence:
                    issues.append(SystemicIssue(
                        issue_type="architecture",
                        affected_entities=pattern.entities,
                        incident_count=len(pattern.incidents),
                        incident_ids=pattern.incidents,
                        severity=self._calculate_severity(len(pattern.incidents), pattern.confidence),
                        confidence=pattern.confidence,
                        description="Cascading failures indicate tight coupling between components",
                        business_impact="Service disruptions affect multiple systems",
                        recommended_actions=[
                            "Implement circuit breakers",
                            "Add bulkheads between services",
                            "Review service dependencies",
                            "Implement graceful degradation"
                        ],
                        estimated_effort="HIGH"
                    ))
        
        return issues
    
    def _analyze_process_issues(self, incidents: List[Incident]) -> List[SystemicIssue]:
        """Identify process-related issues from incident patterns"""
        issues = []
        
        # Look for patterns indicating process problems
        deployment_failures = [inc for inc in incidents if inc.incident_type == IncidentType.DEPLOYMENT_FAILURE]
        
        if len(deployment_failures) >= 5:  # Many deployment failures suggest process issues
            confidence = min(1.0, len(deployment_failures) / 10.0)
            
            if confidence >= self.min_confidence:
                issues.append(SystemicIssue(
                    issue_type="process",
                    affected_entities=list(set(inc.repo for inc in deployment_failures)),
                    incident_count=len(deployment_failures),
                    incident_ids=[inc.id for inc in deployment_failures],
                    severity=self._calculate_severity(len(deployment_failures), confidence),
                    confidence=confidence,
                    description="High deployment failure rate indicates process issues",
                    business_impact="Delayed releases and reduced confidence in deployments",
                    recommended_actions=[
                        "Improve CI/CD pipeline reliability",
                        "Add deployment smoke tests",
                        "Implement blue-green deployments",
                        "Review deployment procedures"
                    ],
                    estimated_effort="MEDIUM"
                ))
        
        return issues
    
    def _analyze_tooling_issues(self, incidents: List[Incident]) -> List[SystemicIssue]:
        """Identify tooling-related issues"""
        issues = []
        
        # Look for build system issues
        build_failures = [inc for inc in incidents if inc.incident_type == IncidentType.BUILD_FAILURE]
        
        if len(build_failures) >= 3:
            # Analyze error messages for tooling patterns
            error_patterns = Counter(inc.failure_type for inc in build_failures)
            most_common = error_patterns.most_common(1)[0] if error_patterns else None
            
            if most_common and most_common[1] >= 2:  # Same error type appears multiple times
                confidence = min(1.0, most_common[1] / 5.0)
                
                if confidence >= self.min_confidence:
                    issues.append(SystemicIssue(
                        issue_type="tooling",
                        affected_entities=list(set(inc.repo for inc in build_failures)),
                        incident_count=len(build_failures),
                        incident_ids=[inc.id for inc in build_failures],
                        severity=self._calculate_severity(len(build_failures), confidence),
                        confidence=confidence,
                        description=f"Recurring build issues: {most_common[0]}",
                        business_impact="Development velocity reduced by build instability",
                        recommended_actions=[
                            "Upgrade build tools",
                            "Standardize build environment",
                            "Implement build caching",
                            "Review build dependencies"
                        ],
                        estimated_effort="MEDIUM"
                    ))
        
        return issues
    
    def _analyze_knowledge_issues(self, incidents: List[Incident], incident_graph: IncidentGraph) -> List[SystemicIssue]:
        """Identify knowledge/training issues from author patterns"""
        issues = []
        
        # Look for author patterns in the incident graph
        author_patterns = incident_graph.get_patterns_by_type("author_pattern")
        
        if len(author_patterns) >= 2:  # Multiple authors with patterns
            all_incidents = []
            affected_authors = []
            
            for pattern in author_patterns:
                if pattern.confidence >= self.min_confidence:
                    all_incidents.extend(pattern.incidents)
                    affected_authors.extend(pattern.entities)
            
            if len(set(all_incidents)) >= 5:  # Significant incident count
                confidence = min(1.0, len(author_patterns) / 5.0)
                
                issues.append(SystemicIssue(
                    issue_type="knowledge",
                    affected_entities=list(set(affected_authors)),
                    incident_count=len(set(all_incidents)),
                    incident_ids=list(set(all_incidents)),
                    severity=self._calculate_severity(len(set(all_incidents)), confidence),
                    confidence=confidence,
                    description="Multiple authors involved in repeated incidents",
                    business_impact="Knowledge gaps leading to recurring issues",
                    recommended_actions=[
                        "Implement code review standards",
                        "Provide targeted training",
                        "Create architectural guidelines",
                        "Set up pair programming",
                        "Document common pitfalls"
                    ],
                    estimated_effort="MEDIUM"
                ))
        
        return issues
    
    def _analyze_temporal_patterns(self, incidents: List[Incident]) -> List[TemporalPattern]:
        """Identify time-based patterns in incidents"""
        patterns = []
        
        if not incidents:
            return patterns
        
        # Sort incidents by timestamp
        sorted_incidents = sorted(incidents, key=lambda x: x.timestamp)
        
        # Look for incident spikes
        spike_patterns = self._find_incident_spikes(sorted_incidents)
        patterns.extend(spike_patterns)
        
        # Look for trends
        trend_patterns = self._find_incident_trends(sorted_incidents)
        patterns.extend(trend_patterns)
        
        return patterns
    
    def _find_incident_spikes(self, sorted_incidents: List[Incident]) -> List[TemporalPattern]:
        """Find incident spikes (many incidents in short time)"""
        patterns = []
        
        if len(sorted_incidents) < 5:
            return patterns
        
        # Use sliding window to find spikes
        window_size = timedelta(hours=2)
        
        for i in range(len(sorted_incidents) - 2):
            window_start = sorted_incidents[i].timestamp
            window_end = window_start + window_size
            
            # Count incidents in window
            window_incidents = []
            for j in range(i, len(sorted_incidents)):
                if sorted_incidents[j].timestamp <= window_end:
                    window_incidents.append(sorted_incidents[j])
                else:
                    break
            
            # If we have 3+ incidents in 2 hours, it's a spike
            if len(window_incidents) >= 3:
                patterns.append(TemporalPattern(
                    pattern_type="spike",
                    time_range=(window_start, window_end),
                    incident_ids=[inc.id for inc in window_incidents],
                    frequency=len(window_incidents) / 2.0,  # incidents per hour
                    description=f"Incident spike: {len(window_incidents)} incidents in 2 hours",
                    trigger_hypothesis="Possible deployment or external trigger"
                ))
                
                # Skip overlapping windows
                i += len(window_incidents) - 1
        
        return patterns
    
    def _find_incident_trends(self, sorted_incidents: List[Incident]) -> List[TemporalPattern]:
        """Find incident trends (increasing/decreasing over time)"""
        patterns = []
        
        if len(sorted_incidents) < 10:  # Need sufficient data for trend analysis
            return patterns
        
        # Analyze last 30 days if available
        latest = sorted_incidents[-1].timestamp
        earliest_for_trend = latest - timedelta(days=30)
        
        recent_incidents = [inc for inc in sorted_incidents if inc.timestamp >= earliest_for_trend]
        
        if len(recent_incidents) >= 10:
            # Simple trend analysis: compare first half vs second half
            mid_point = len(recent_incidents) // 2
            first_half_rate = mid_point / max(1, (recent_incidents[mid_point].timestamp - recent_incidents[0].timestamp).days)
            second_half_rate = (len(recent_incidents) - mid_point) / max(1, (recent_incidents[-1].timestamp - recent_incidents[mid_point].timestamp).days)
            
            if second_half_rate > first_half_rate * 1.5:  # 50% increase
                patterns.append(TemporalPattern(
                    pattern_type="trend",
                    time_range=(recent_incidents[0].timestamp, recent_incidents[-1].timestamp),
                    incident_ids=[inc.id for inc in recent_incidents],
                    frequency=second_half_rate,
                    description="Increasing incident trend detected",
                    trigger_hypothesis="Possible system degradation or increased load"
                ))
        
        return patterns
    
    def _generate_recommendations(self, recurring_failures: List[RecurringFailure], 
                                 systemic_issues: List[SystemicIssue], 
                                 temporal_patterns: List[TemporalPattern]) -> List[str]:
        """Generate high-level recommendations based on analysis"""
        recommendations = []
        
        # Recommendations based on recurring failures
        if len(recurring_failures) >= 3:
            recommendations.append("🔥 URGENT: Address recurring failure hotspots - multiple files/tests failing repeatedly")
            
            file_failures = [rf for rf in recurring_failures if rf.entity_type == "file"]
            if len(file_failures) >= 2:
                recommendations.append("📁 Focus on file-level stability - consider refactoring high-failure files")
            
            test_failures = [rf for rf in recurring_failures if rf.entity_type == "test"]
            if len(test_failures) >= 2:
                recommendations.append("🧪 Test suite needs attention - stabilize or quarantine flaky tests")
        
        # Recommendations based on systemic issues
        high_severity_issues = [si for si in systemic_issues if si.severity in ["HIGH", "CRITICAL"]]
        if high_severity_issues:
            recommendations.append("⚠️ CRITICAL: Systemic issues detected requiring architectural attention")
            
            arch_issues = [si for si in systemic_issues if si.issue_type == "architecture"]
            if arch_issues:
                recommendations.append("🏗️ Architecture review needed - cascading failures indicate tight coupling")
            
            process_issues = [si for si in systemic_issues if si.issue_type == "process"]
            if process_issues:
                recommendations.append("⚙️ Process improvements needed - deployment/build pipeline instability")
        
        # Recommendations based on temporal patterns
        spike_patterns = [tp for tp in temporal_patterns if tp.pattern_type == "spike"]
        if spike_patterns:
            recommendations.append("📈 Investigate incident spikes - possible external triggers or deployments")
        
        trend_patterns = [tp for tp in temporal_patterns if tp.pattern_type == "trend"]
        if trend_patterns:
            recommendations.append("📊 Monitor incident trends - system may be degrading over time")
        
        # Overall recommendations
        if len(recurring_failures) + len(systemic_issues) >= 5:
            recommendations.append("🎯 Recommend immediate incident response team formation")
            recommendations.append("📋 Create action plan with priority ordering based on business impact")
        
        return recommendations
    
    def _calculate_recurrence_confidence(self, incidents: List[Incident]) -> float:
        """Calculate confidence score for recurring failure pattern"""
        if not incidents:
            return 0.0
        
        # Factors affecting confidence:
        # 1. Number of incidents (more = higher confidence)
        # 2. Consistency of failure types
        # 3. Time distribution (spread out = more concerning)
        
        count_factor = min(1.0, len(incidents) / 5.0)  # Max at 5 incidents
        
        # Consistency factor
        failure_types = [inc.failure_type for inc in incidents]
        most_common_count = Counter(failure_types).most_common(1)[0][1]
        consistency_factor = most_common_count / len(incidents)
        
        # Time distribution factor
        timestamps = [inc.timestamp for inc in incidents]
        time_span = max(timestamps) - min(timestamps)
        distribution_factor = min(1.0, time_span.days / 30.0)  # More concerning if spread over time
        
        confidence = (count_factor * 0.4 + consistency_factor * 0.3 + distribution_factor * 0.3)
        return min(1.0, confidence)
    
    def _calculate_confidence_score(self, recurring_failures: List[RecurringFailure], 
                                   systemic_issues: List[SystemicIssue]) -> float:
        """Calculate overall analysis confidence score"""
        if not recurring_failures and not systemic_issues:
            return 0.0
        
        # Weight by pattern confidence and severity
        total_weight = 0.0
        weighted_confidence = 0.0
        
        for rf in recurring_failures:
            weight = rf.failure_count
            total_weight += weight
            weighted_confidence += rf.confidence * weight
        
        for si in systemic_issues:
            weight = si.incident_count * (2 if si.severity in ["HIGH", "CRITICAL"] else 1)
            total_weight += weight  
            weighted_confidence += si.confidence * weight
        
        return weighted_confidence / total_weight if total_weight > 0 else 0.0
    
    def _calculate_severity(self, incident_count: int, confidence: float) -> str:
        """Calculate severity level based on incident count and confidence"""
        score = incident_count * confidence
        
        if score >= 8:
            return "CRITICAL"
        elif score >= 5:
            return "HIGH"
        elif score >= 3:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _is_test_file(self, file_path: str) -> bool:
        """Determine if a file is a test file"""
        test_indicators = ["test", "spec", "__test__", ".test.", ".spec."]
        return any(indicator in file_path.lower() for indicator in test_indicators)
    
    def _infer_services(self, files: List[str]) -> Set[str]:
        """Infer service names from file paths"""
        services = set()
        
        for file_path in files:
            parts = file_path.split('/')
            
            # Common patterns
            if 'services' in parts:
                idx = parts.index('services')
                if idx + 1 < len(parts):
                    services.add(parts[idx + 1])
            elif 'src' in parts and len(parts) > parts.index('src') + 1:
                idx = parts.index('src')
                services.add(parts[idx + 1])
            elif parts and not parts[0].startswith('.'):
                services.add(parts[0])
        
        return services
    
    def _suggest_file_remediation(self, file_path: str, failure_types: List[str]) -> str:
        """Suggest remediation for recurring file failures"""
        most_common = Counter(failure_types).most_common(1)[0][0]
        
        if "syntax" in most_common.lower():
            return "Add linting and pre-commit hooks"
        elif "type" in most_common.lower():
            return "Improve type annotations and static analysis"
        elif "test" in most_common.lower():
            return "Review and stabilize test logic"
        elif "import" in most_common.lower():
            return "Review dependency management and module structure"
        else:
            return "Refactor for reliability and add defensive programming"
    
    def _suggest_service_remediation(self, service: str, incidents: List[Incident]) -> str:
        """Suggest remediation for recurring service failures"""
        incident_types = [inc.incident_type for inc in incidents]
        most_common = Counter(incident_types).most_common(1)[0][0]
        
        if most_common == IncidentType.DEPLOYMENT_FAILURE:
            return "Improve deployment pipeline and add smoke tests"
        elif most_common == IncidentType.RUNTIME_ERROR:
            return "Add monitoring, logging, and error handling"
        elif most_common == IncidentType.PERFORMANCE_REGRESSION:
            return "Performance profiling and optimization"
        else:
            return "Comprehensive service health review and hardening"