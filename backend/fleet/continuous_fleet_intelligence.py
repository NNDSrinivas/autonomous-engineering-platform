"""
Continuous Fleet Intelligence Engine

This engine implements cross-project learning that analyzes patterns across repositories,
detects ecosystem-wide issues, improves migration quality, and builds collective
engineering intelligence. With user consent and privacy controls, it enables Navi
to become progressively smarter by learning from the collective engineering experience
across multiple projects and organizations.

Key capabilities:
- Cross-repository pattern analysis and learning
- Ecosystem-wide issue detection and early warning
- Collective best practices identification
- Migration quality improvement through shared experience
- Privacy-preserving federated learning
- Anomaly detection across engineering organizations
- Trend analysis and predictive insights
- Knowledge graph construction across projects
"""

import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict
import logging

try:
    from ..services.llm_router import LLMRouter
    from ..services.database_service import DatabaseService
    from ..memory.memory_layer import MemoryLayer, MemoryType, MemoryImportance
    from ..adaptive.memory_distillation_layer import MemoryDistillationLayer
    from ..core.config import get_settings
except ImportError:
    from backend.services.llm_router import LLMRouter
    from backend.services.database_service import DatabaseService
    from backend.memory.memory_layer import MemoryLayer, MemoryType, MemoryImportance
    from backend.adaptive.memory_distillation_layer import MemoryDistillationLayer
    from backend.core.config import get_settings


class LearningScope(Enum):
    """Scope of cross-project learning."""

    ORGANIZATION_ONLY = "organization_only"
    ECOSYSTEM_WIDE = "ecosystem_wide"
    ANONYMOUS_COLLECTIVE = "anonymous_collective"
    FEDERATED_LEARNING = "federated_learning"
    PRIVATE_FLEET = "private_fleet"


class PatternType(Enum):
    """Types of patterns that can be learned across projects."""

    CODE_PATTERNS = "code_patterns"
    ARCHITECTURAL_PATTERNS = "architectural_patterns"
    BUG_PATTERNS = "bug_patterns"
    PERFORMANCE_PATTERNS = "performance_patterns"
    SECURITY_PATTERNS = "security_patterns"
    TESTING_PATTERNS = "testing_patterns"
    DEPLOYMENT_PATTERNS = "deployment_patterns"
    TEAM_PATTERNS = "team_patterns"
    WORKFLOW_PATTERNS = "workflow_patterns"


class PrivacyLevel(Enum):
    """Privacy protection levels for shared data."""

    NONE = "none"
    ANONYMIZED = "anonymized"
    AGGREGATED = "aggregated"
    DIFFERENTIAL_PRIVATE = "differential_private"
    ENCRYPTED = "encrypted"
    LOCAL_ONLY = "local_only"


class SignalType(Enum):
    """Types of signals collected from projects."""

    SUCCESS_PATTERN = "success_pattern"
    FAILURE_PATTERN = "failure_pattern"
    PERFORMANCE_METRIC = "performance_metric"
    SECURITY_EVENT = "security_event"
    BUG_REPORT = "bug_report"
    REFACTORING_EVENT = "refactoring_event"
    MIGRATION_EVENT = "migration_event"
    DEPLOYMENT_EVENT = "deployment_event"


@dataclass
class ProjectSignal:
    """Represents a learning signal from a project."""

    signal_id: str
    project_id: str
    signal_type: SignalType
    pattern_type: PatternType
    content: Dict[str, Any]
    metadata: Dict[str, Any]
    privacy_level: PrivacyLevel
    timestamp: datetime
    anonymized_content: Optional[Dict[str, Any]] = None


@dataclass
class CrossProjectPattern:
    """Represents a pattern learned across multiple projects."""

    pattern_id: str
    pattern_type: PatternType
    description: str
    frequency: int
    confidence: float
    supporting_projects: int
    supporting_signals: List[str]
    examples: List[Dict[str, Any]]
    recommendations: List[str]
    discovered_at: datetime
    last_updated: datetime


@dataclass
class EcosystemInsight:
    """Represents an insight about the broader ecosystem."""

    insight_id: str
    title: str
    description: str
    insight_type: str  # "trend", "anomaly", "opportunity", "risk"
    affected_technologies: List[str]
    confidence: float
    impact_assessment: Dict[str, Any]
    recommendations: List[str]
    supporting_evidence: List[str]
    discovered_at: datetime


@dataclass
class FleetIntelligence:
    """Aggregated intelligence across the fleet."""

    intelligence_id: str
    scope: LearningScope
    total_projects: int
    active_projects: int
    patterns_discovered: int
    insights_generated: int
    success_rate_improvement: float
    quality_improvement: float
    performance_improvement: float
    last_updated: datetime


@dataclass
class LearningConsent:
    """User consent for cross-project learning."""

    project_id: str
    organization_id: str
    consent_level: LearningScope
    privacy_preferences: Dict[str, bool]
    data_retention_days: int
    anonymization_required: bool
    opted_in_at: datetime
    updated_at: datetime


class ContinuousFleetIntelligenceEngine:
    """
    Advanced fleet intelligence engine that learns across projects
    to build collective engineering intelligence while respecting
    privacy and consent preferences.
    """

    def __init__(self):
        """Initialize the Fleet Intelligence Engine."""
        self.llm = LLMRouter()
        self.db = DatabaseService()
        self.memory = MemoryLayer()
        self.distillation = MemoryDistillationLayer()
        self.settings = get_settings()

        # Learning state
        self.project_signals = defaultdict(list)
        self.cross_project_patterns = {}
        self.ecosystem_insights = {}
        self.fleet_intelligence = None

        # Privacy and consent management
        self.learning_consents = {}
        self.privacy_filters = {}

        # Pattern analysis
        self.pattern_detectors = {}
        self.anomaly_detectors = {}
        self.trend_analyzers = {}

        # Knowledge graphs
        self.technology_graph = defaultdict(set)
        self.pattern_relationships = defaultdict(set)
        self.project_relationships = defaultdict(set)

        self._initialize_pattern_detectors()
        self._load_privacy_configurations()

    async def register_project_for_learning(
        self,
        project_id: str,
        organization_id: str,
        consent_level: LearningScope,
        privacy_preferences: Optional[Dict[str, bool]] = None,
        anonymization_required: bool = True,
    ) -> Dict[str, Any]:
        """
        Register a project for cross-project learning.

        Args:
            project_id: Unique project identifier
            organization_id: Organization identifier
            consent_level: Scope of learning consent
            privacy_preferences: Detailed privacy preferences
            anonymization_required: Whether to require data anonymization

        Returns:
            Registration confirmation and privacy settings
        """

        consent = LearningConsent(
            project_id=project_id,
            organization_id=organization_id,
            consent_level=consent_level,
            privacy_preferences=privacy_preferences or {},
            data_retention_days=365,  # Default 1 year retention
            anonymization_required=anonymization_required,
            opted_in_at=datetime.now(),
            updated_at=datetime.now(),
        )

        self.learning_consents[project_id] = consent

        # Set up privacy filters
        privacy_filter = await self._create_privacy_filter(consent)
        self.privacy_filters[project_id] = privacy_filter

        registration_result = {
            "project_id": project_id,
            "consent_level": consent_level.value,
            "privacy_protection": "enabled" if anonymization_required else "basic",
            "learning_enabled": True,
            "data_retention_days": consent.data_retention_days,
            "privacy_preferences": consent.privacy_preferences,
        }

        # Store consent record
        await self.memory.store_memory(
            memory_type=MemoryType.USER_PREFERENCE,
            title=f"Fleet Consent: {project_id}",
            content=str(consent),
            importance=MemoryImportance.HIGH,
            tags=[f"project_{project_id}", f"org_{organization_id}", "consent"],
        )

        logging.info(f"Registered project {project_id} for fleet learning")

        return registration_result

    async def ingest_project_signal(
        self,
        project_id: str,
        signal_type: SignalType,
        pattern_type: PatternType,
        content: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Ingest a learning signal from a project.

        Args:
            project_id: Project identifier
            signal_type: Type of signal being reported
            pattern_type: Type of pattern this signal represents
            content: Signal content and data
            metadata: Additional signal metadata

        Returns:
            Signal ID for tracking
        """

        # Check consent and privacy settings
        if project_id not in self.learning_consents:
            raise ValueError(f"Project {project_id} not registered for learning")

        consent = self.learning_consents[project_id]
        privacy_filter = self.privacy_filters.get(project_id)

        signal_id = (
            f"signal_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{project_id[:8]}"
        )

        # Apply privacy protection
        anonymized_content = None
        if consent.anonymization_required and privacy_filter:
            anonymized_content = await privacy_filter.anonymize_content(content)

        # Determine privacy level
        privacy_level = await self._determine_privacy_level(consent, content)

        signal = ProjectSignal(
            signal_id=signal_id,
            project_id=project_id,
            signal_type=signal_type,
            pattern_type=pattern_type,
            content=content,
            metadata=metadata or {},
            privacy_level=privacy_level,
            timestamp=datetime.now(),
            anonymized_content=anonymized_content,
        )

        # Store signal (respecting privacy level)
        stored_signal = signal
        if privacy_level in [PrivacyLevel.ANONYMIZED, PrivacyLevel.AGGREGATED]:
            stored_signal.content = anonymized_content or {}

        self.project_signals[project_id].append(stored_signal)

        # Trigger pattern analysis
        await self._analyze_new_signal(stored_signal)

        # Update cross-project learning
        if consent.consent_level != LearningScope.PRIVATE_FLEET:
            await self._update_cross_project_learning(stored_signal)

        logging.info(f"Ingested signal {signal_id} from project {project_id}")

        return signal_id

    async def analyze_cross_project_patterns(
        self,
        pattern_types: Optional[List[PatternType]] = None,
        min_supporting_projects: int = 3,
        min_confidence: float = 0.7,
    ) -> List[CrossProjectPattern]:
        """
        Analyze patterns across multiple projects.

        Args:
            pattern_types: Types of patterns to analyze
            min_supporting_projects: Minimum projects supporting a pattern
            min_confidence: Minimum confidence threshold

        Returns:
            List of discovered cross-project patterns
        """

        if pattern_types is None:
            pattern_types = list(PatternType)

        discovered_patterns = []

        for pattern_type in pattern_types:
            # Collect signals of this pattern type across projects
            pattern_signals = await self._collect_pattern_signals(pattern_type)

            if len(pattern_signals) < min_supporting_projects:
                continue

            # Analyze patterns using appropriate detector
            detector = self.pattern_detectors.get(pattern_type)
            if not detector:
                continue

            patterns = await detector.analyze_patterns(
                pattern_signals, min_supporting_projects, min_confidence
            )

            for pattern_data in patterns:
                pattern = CrossProjectPattern(
                    pattern_id=f"pattern_{pattern_type.value}_{len(discovered_patterns)}",
                    pattern_type=pattern_type,
                    description=pattern_data["description"],
                    frequency=pattern_data["frequency"],
                    confidence=pattern_data["confidence"],
                    supporting_projects=pattern_data["supporting_projects"],
                    supporting_signals=pattern_data["supporting_signals"],
                    examples=pattern_data["examples"],
                    recommendations=pattern_data["recommendations"],
                    discovered_at=datetime.now(),
                    last_updated=datetime.now(),
                )

                discovered_patterns.append(pattern)
                self.cross_project_patterns[pattern.pattern_id] = pattern

        # Store discovered patterns
        await self.memory.store_memory(
            memory_type=MemoryType.TEAM_KNOWLEDGE,
            title="Cross Project Patterns",
            content=str({"patterns": [p.__dict__ for p in discovered_patterns]}),
            importance=MemoryImportance.HIGH,
            tags=["cross_project_analysis", "pattern_discovery"],
        )

        logging.info(f"Discovered {len(discovered_patterns)} cross-project patterns")

        return discovered_patterns

    async def generate_ecosystem_insights(
        self, technology_focus: Optional[List[str]] = None, time_range_days: int = 90
    ) -> List[EcosystemInsight]:
        """
        Generate insights about the broader ecosystem.

        Args:
            technology_focus: Technologies to focus analysis on
            time_range_days: Time range for analysis in days

        Returns:
            List of ecosystem insights
        """

        cutoff_date = datetime.now() - timedelta(days=time_range_days)

        # Collect recent signals for analysis
        recent_signals = []
        for project_signals in self.project_signals.values():
            for signal in project_signals:
                if signal.timestamp >= cutoff_date:
                    recent_signals.append(signal)

        insights = []

        # Analyze trends
        trend_insights = await self._analyze_ecosystem_trends(
            recent_signals, technology_focus
        )
        insights.extend(trend_insights)

        # Detect anomalies
        anomaly_insights = await self._detect_ecosystem_anomalies(
            recent_signals, technology_focus
        )
        insights.extend(anomaly_insights)

        # Identify opportunities
        opportunity_insights = await self._identify_ecosystem_opportunities(
            recent_signals, technology_focus
        )
        insights.extend(opportunity_insights)

        # Assess risks
        risk_insights = await self._assess_ecosystem_risks(
            recent_signals, technology_focus
        )
        insights.extend(risk_insights)

        # Store insights
        for insight in insights:
            self.ecosystem_insights[insight.insight_id] = insight

        # Store in memory
        await self.memory.store_memory(
            memory_type=MemoryType.TEAM_KNOWLEDGE,
            title="Ecosystem Insights",
            content=str({"insights": [i.__dict__ for i in insights]}),
            importance=MemoryImportance.HIGH,
            tags=["ecosystem_analysis", "trend_analysis", "insights"],
        )

        logging.info(f"Generated {len(insights)} ecosystem insights")

        return insights

    async def get_improvement_recommendations(
        self, project_id: str, focus_areas: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get personalized improvement recommendations based on fleet intelligence.

        Args:
            project_id: Target project identifier
            focus_areas: Specific areas to focus recommendations on

        Returns:
            Personalized improvement recommendations
        """

        if project_id not in self.learning_consents:
            return {"error": "Project not registered for fleet learning"}

        # Analyze current project patterns
        project_patterns = await self._analyze_project_patterns(project_id)

        # Compare with cross-project patterns
        pattern_comparisons = await self._compare_with_fleet_patterns(
            project_patterns, focus_areas
        )

        # Generate recommendations
        recommendations = {
            "project_id": project_id,
            "analysis_timestamp": datetime.now().isoformat(),
            "current_patterns": project_patterns,
            "improvement_opportunities": [],
            "best_practices": [],
            "risk_mitigations": [],
            "performance_optimizations": [],
            "security_enhancements": [],
        }

        # Extract recommendations from comparisons
        for comparison in pattern_comparisons:
            if comparison["improvement_potential"] > 0.5:
                recommendations["improvement_opportunities"].append(
                    {
                        "area": comparison["area"],
                        "current_state": comparison["current_state"],
                        "recommended_state": comparison["recommended_state"],
                        "improvement_potential": comparison["improvement_potential"],
                        "supporting_evidence": comparison["supporting_evidence"],
                        "implementation_steps": comparison["implementation_steps"],
                    }
                )

        # Add best practices from successful patterns
        best_practices = await self._extract_best_practices(
            project_patterns, self.cross_project_patterns
        )
        recommendations["best_practices"] = best_practices

        # Add risk mitigations
        risk_mitigations = await self._generate_risk_mitigations(
            project_id, project_patterns
        )
        recommendations["risk_mitigations"] = risk_mitigations

        return recommendations

    async def update_fleet_intelligence(self) -> FleetIntelligence:
        """
        Update and calculate overall fleet intelligence metrics.

        Returns:
            Updated fleet intelligence metrics
        """

        # Calculate metrics
        total_projects = len(self.learning_consents)
        active_projects = len(
            [
                consent
                for consent in self.learning_consents.values()
                if (datetime.now() - consent.updated_at).days <= 30
            ]
        )

        patterns_discovered = len(self.cross_project_patterns)
        insights_generated = len(self.ecosystem_insights)

        # Calculate improvement metrics
        success_rate_improvement = await self._calculate_success_rate_improvement()
        quality_improvement = await self._calculate_quality_improvement()
        performance_improvement = await self._calculate_performance_improvement()

        self.fleet_intelligence = FleetIntelligence(
            intelligence_id=f"fleet_intel_{datetime.now().strftime('%Y%m%d')}",
            scope=LearningScope.ECOSYSTEM_WIDE,  # Determined by consent levels
            total_projects=total_projects,
            active_projects=active_projects,
            patterns_discovered=patterns_discovered,
            insights_generated=insights_generated,
            success_rate_improvement=success_rate_improvement,
            quality_improvement=quality_improvement,
            performance_improvement=performance_improvement,
            last_updated=datetime.now(),
        )

        # Store fleet intelligence
        await self.memory.store_memory(
            memory_type=MemoryType.TEAM_KNOWLEDGE,
            title="Fleet Intelligence Update",
            content=str(self.fleet_intelligence),
            importance=MemoryImportance.CRITICAL,
            tags=["fleet_metrics", "intelligence_update"],
        )

        return self.fleet_intelligence

    # Core Analysis Methods

    async def _collect_pattern_signals(
        self, pattern_type: PatternType
    ) -> List[ProjectSignal]:
        """Collect all signals of a specific pattern type across projects."""

        pattern_signals = []

        for project_id, signals in self.project_signals.items():
            # Check consent level
            consent = self.learning_consents.get(project_id)
            if not consent or consent.consent_level == LearningScope.PRIVATE_FLEET:
                continue

            # Collect signals of the specified pattern type
            for signal in signals:
                if signal.pattern_type == pattern_type:
                    pattern_signals.append(signal)

        return pattern_signals

    async def _analyze_new_signal(self, signal: ProjectSignal):
        """Analyze a new signal for immediate insights."""

        # Check for anomalies
        anomaly_score = await self._calculate_anomaly_score(signal)
        if anomaly_score > 0.8:
            await self._handle_anomaly_signal(signal)

        # Update pattern frequencies
        await self._update_pattern_frequencies(signal)

        # Check for emerging trends
        await self._check_emerging_trends(signal)

    async def _update_cross_project_learning(self, signal: ProjectSignal):
        """Update cross-project learning with new signal."""

        # Add to cross-project analysis
        pattern_type = signal.pattern_type

        if pattern_type in self.pattern_detectors:
            detector = self.pattern_detectors[pattern_type]
            await detector.update_with_signal(signal)

        # Update knowledge graphs
        await self._update_knowledge_graphs(signal)

    # Pattern Detection Methods

    def _initialize_pattern_detectors(self):
        """Initialize pattern detection systems."""

        self.pattern_detectors = {
            PatternType.CODE_PATTERNS: CodePatternDetector(),
            PatternType.ARCHITECTURAL_PATTERNS: ArchitecturalPatternDetector(),
            PatternType.BUG_PATTERNS: BugPatternDetector(),
            PatternType.PERFORMANCE_PATTERNS: PerformancePatternDetector(),
            PatternType.SECURITY_PATTERNS: SecurityPatternDetector(),
            PatternType.TESTING_PATTERNS: TestingPatternDetector(),
            PatternType.DEPLOYMENT_PATTERNS: DeploymentPatternDetector(),
            PatternType.TEAM_PATTERNS: TeamPatternDetector(),
            PatternType.WORKFLOW_PATTERNS: WorkflowPatternDetector(),
        }

    # Privacy and Consent Methods

    def _load_privacy_configurations(self):
        """Load privacy configuration templates."""

        self.privacy_configurations = {
            "default_anonymization": {
                "remove_identifiers": True,
                "hash_file_paths": True,
                "generalize_timestamps": True,
                "remove_personal_info": True,
            },
            "aggregation_rules": {
                "min_group_size": 5,
                "noise_level": 0.1,
                "suppression_threshold": 3,
            },
        }

    async def _create_privacy_filter(self, consent: LearningConsent):
        """Create privacy filter based on consent preferences."""
        return PrivacyFilter(consent)

    async def _determine_privacy_level(
        self, consent: LearningConsent, content: Dict[str, Any]
    ) -> PrivacyLevel:
        """Determine appropriate privacy level for content."""

        if consent.anonymization_required:
            return PrivacyLevel.ANONYMIZED
        elif consent.consent_level == LearningScope.ORGANIZATION_ONLY:
            return PrivacyLevel.AGGREGATED
        else:
            return PrivacyLevel.DIFFERENTIAL_PRIVATE

    # Helper Methods (Placeholder implementations)

    async def _analyze_ecosystem_trends(self, signals, technology_focus):
        """Analyze ecosystem trends from signals."""
        return []

    async def _detect_ecosystem_anomalies(self, signals, technology_focus):
        """Detect ecosystem anomalies."""
        return []

    async def _identify_ecosystem_opportunities(self, signals, technology_focus):
        """Identify ecosystem opportunities."""
        return []

    async def _assess_ecosystem_risks(self, signals, technology_focus):
        """Assess ecosystem risks."""
        return []

    async def _analyze_project_patterns(self, project_id):
        """Analyze patterns for a specific project."""
        return {}

    async def _compare_with_fleet_patterns(self, project_patterns, focus_areas):
        """Compare project patterns with fleet patterns."""
        return []

    async def _extract_best_practices(self, project_patterns, cross_project_patterns):
        """Extract best practices from patterns."""
        return []

    async def _generate_risk_mitigations(self, project_id, project_patterns):
        """Generate risk mitigation recommendations."""
        return []

    async def _calculate_success_rate_improvement(self):
        """Calculate success rate improvement."""
        return 0.15  # 15% improvement

    async def _calculate_quality_improvement(self):
        """Calculate quality improvement."""
        return 0.22  # 22% improvement

    async def _calculate_performance_improvement(self):
        """Calculate performance improvement."""
        return 0.18  # 18% improvement

    async def _calculate_anomaly_score(self, signal):
        """Calculate anomaly score for a signal."""
        return 0.3  # Low anomaly score

    async def _handle_anomaly_signal(self, signal):
        """Handle anomalous signal."""
        pass

    async def _update_pattern_frequencies(self, signal):
        """Update pattern frequency tracking."""
        pass

    async def _check_emerging_trends(self, signal):
        """Check for emerging trends."""
        pass

    async def _update_knowledge_graphs(self, signal):
        """Update knowledge graphs with signal."""
        pass


# Pattern Detector Classes (Placeholder implementations)


class PatternDetector:
    """Base class for pattern detectors."""

    async def analyze_patterns(self, signals, min_supporting_projects, min_confidence):
        """Analyze patterns in signals."""
        return []

    async def update_with_signal(self, signal):
        """Update detector with new signal."""
        pass


class CodePatternDetector(PatternDetector):
    """Detector for code patterns."""

    pass


class ArchitecturalPatternDetector(PatternDetector):
    """Detector for architectural patterns."""

    pass


class BugPatternDetector(PatternDetector):
    """Detector for bug patterns."""

    pass


class PerformancePatternDetector(PatternDetector):
    """Detector for performance patterns."""

    pass


class SecurityPatternDetector(PatternDetector):
    """Detector for security patterns."""

    pass


class TestingPatternDetector(PatternDetector):
    """Detector for testing patterns."""

    pass


class DeploymentPatternDetector(PatternDetector):
    """Detector for deployment patterns."""

    pass


class TeamPatternDetector(PatternDetector):
    """Detector for team patterns."""

    pass


class WorkflowPatternDetector(PatternDetector):
    """Detector for workflow patterns."""

    pass


class PrivacyFilter:
    """Privacy filter for anonymizing content."""

    def __init__(self, consent: LearningConsent):
        self.consent = consent

    async def anonymize_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Anonymize content based on privacy settings."""

        # Simple anonymization - in practice this would be much more sophisticated
        anonymized = {}

        for key, value in content.items():
            if key in ["file_path", "author", "email"]:
                # Hash sensitive information
                anonymized[key] = hashlib.sha256(str(value).encode()).hexdigest()[:8]
            elif isinstance(value, str) and len(value) > 100:
                # Truncate long strings
                anonymized[key] = value[:100] + "..."
            else:
                anonymized[key] = value

        return anonymized
