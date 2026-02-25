"""
KnowledgeAggregator — Pattern Formation

Pattern recognition system that transforms raw organizational signals into
actionable knowledge and identifies recurring organizational patterns. This
turns individual events into organizational intelligence.

Key Capabilities:
- Transform raw signals into knowledge patterns
- Identify recurring failure patterns across teams
- Discover organizational best practices
- Map team expertise and collaboration patterns
- Generate insights for policy inference
"""

import logging
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any
from .org_memory_store import OrgSignal, SignalType

logger = logging.getLogger(__name__)


@dataclass
class OrgPattern:
    """Represents a pattern discovered in organizational behavior"""

    pattern_id: str
    pattern_type: str  # "failure_hotspot", "success_practice", "team_collaboration", "expertise_area"
    description: str
    confidence: float  # 0.0 - 1.0
    frequency: int  # How often this pattern occurs
    evidence: List[str]  # Signal IDs supporting this pattern
    affected_entities: List[str]  # Files, teams, repos affected
    first_seen: datetime
    last_seen: datetime
    trend: str  # "increasing", "stable", "decreasing"
    impact_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    recommendations: List[str]


@dataclass
class TeamKnowledge:
    """Knowledge about a specific team's patterns"""

    team_name: str
    expertise_areas: List[str]
    common_mistakes: List[str]
    preferred_practices: List[str]
    collaboration_patterns: Dict[str, int]  # Other teams they work with
    risk_indicators: List[str]
    success_factors: List[str]
    knowledge_gaps: List[str]
    activity_level: str  # "LOW", "MEDIUM", "HIGH"
    quality_score: float  # 0.0 - 1.0


@dataclass
class OrgKnowledge:
    """Aggregated organizational knowledge"""

    org_name: str
    analysis_period: Tuple[datetime, datetime]
    total_signals_analyzed: int
    patterns: List[OrgPattern]
    team_knowledge: Dict[str, TeamKnowledge]
    cross_team_insights: Dict[str, Any]
    critical_insights: List[str]
    improvement_opportunities: List[str]
    success_practices: List[str]
    risk_areas: List[str]
    confidence_score: float
    generated_at: datetime = field(default_factory=datetime.now)


class KnowledgeAggregator:
    """
    System for aggregating organizational signals into actionable knowledge
    patterns that can be used for policy inference and decision making.
    """

    def __init__(self):
        """Initialize the knowledge aggregator"""
        self.pattern_cache = {}
        logger.info(
            "KnowledgeAggregator initialized - ready to transform signals into knowledge"
        )

    def aggregate_patterns(
        self,
        signals: List[OrgSignal],
        min_pattern_frequency: int = 3,
        confidence_threshold: float = 0.6,
    ) -> List[OrgPattern]:
        """
        Aggregate signals into organizational patterns

        Args:
            signals: List of organizational signals to analyze
            min_pattern_frequency: Minimum frequency for pattern recognition
            confidence_threshold: Minimum confidence for pattern inclusion

        Returns:
            List of discovered patterns
        """
        logger.info(f"Aggregating {len(signals)} signals into organizational patterns")

        patterns = []

        # Failure hotspot patterns
        patterns.extend(self._identify_failure_hotspots(signals, min_pattern_frequency))

        # Success practice patterns
        patterns.extend(
            self._identify_success_practices(signals, min_pattern_frequency)
        )

        # Author/team patterns
        patterns.extend(self._identify_author_patterns(signals, min_pattern_frequency))

        # Temporal patterns
        patterns.extend(
            self._identify_temporal_patterns(signals, min_pattern_frequency)
        )

        # Cross-repository patterns
        patterns.extend(
            self._identify_cross_repo_patterns(signals, min_pattern_frequency)
        )

        # Filter by confidence
        high_confidence_patterns = [
            pattern
            for pattern in patterns
            if pattern.confidence >= confidence_threshold
        ]

        logger.info(
            f"Identified {len(high_confidence_patterns)} high-confidence patterns"
        )
        return high_confidence_patterns

    def generate_team_knowledge(
        self, signals: List[OrgSignal], team_name: str
    ) -> TeamKnowledge:
        """
        Generate knowledge specific to a team

        Args:
            signals: All organizational signals
            team_name: Name of the team to analyze

        Returns:
            Team-specific knowledge
        """
        team_signals = [s for s in signals if s.team == team_name]

        if not team_signals:
            return TeamKnowledge(
                team_name=team_name,
                expertise_areas=[],
                common_mistakes=[],
                preferred_practices=[],
                collaboration_patterns={},
                risk_indicators=[],
                success_factors=[],
                knowledge_gaps=[],
                activity_level="LOW",
                quality_score=0.5,
            )

        # Analyze expertise areas (files they work on most)
        file_frequency = Counter()
        for signal in team_signals:
            file_frequency.update(signal.files)

        expertise_areas = [file for file, freq in file_frequency.most_common(10)]

        # Identify common mistakes (frequent failures)
        failure_signals = [
            s
            for s in team_signals
            if s.signal_type
            in [
                SignalType.CI_FAILURE,
                SignalType.PR_REJECTION,
                SignalType.ROLLBACK,
                SignalType.INCIDENT,
            ]
        ]

        mistake_causes = Counter()
        for signal in failure_signals:
            if signal.cause:
                # Extract key phrases from causes
                words = signal.cause.lower().split()
                key_phrases = [
                    " ".join(words[i : i + 2]) for i in range(len(words) - 1)
                ]
                mistake_causes.update(key_phrases)

        common_mistakes = [
            phrase for phrase, freq in mistake_causes.most_common(5) if freq >= 2
        ]

        # Identify preferred practices (from successful signals)
        success_signals = [
            s
            for s in team_signals
            if s.signal_type
            in [
                SignalType.CI_SUCCESS,
                SignalType.PR_APPROVAL,
                SignalType.DEPLOYMENT_SUCCESS,
            ]
        ]

        preferred_practices = []
        if len(success_signals) > len(failure_signals):
            preferred_practices.append("High success rate in CI/CD pipeline")
        if any("test" in str(s.tags).lower() for s in success_signals):
            preferred_practices.append("Consistent testing practices")

        # Collaboration patterns (teams they interact with)
        collaboration_patterns = {}
        all_signals = [
            s for s in signals if s.author in [ts.author for ts in team_signals]
        ]
        team_repos = set(s.repo for s in team_signals)

        for signal in all_signals:
            if (
                signal.repo not in team_repos
                and signal.team
                and signal.team != team_name
            ):
                collaboration_patterns[signal.team] = (
                    collaboration_patterns.get(signal.team, 0) + 1
                )

        # Calculate quality score
        total_signals = len(team_signals)
        success_count = len(success_signals)
        quality_score = success_count / total_signals if total_signals > 0 else 0.5

        # Determine activity level
        if total_signals >= 50:
            activity_level = "HIGH"
        elif total_signals >= 20:
            activity_level = "MEDIUM"
        else:
            activity_level = "LOW"

        # Risk indicators
        risk_indicators = []
        if len(failure_signals) > len(success_signals):
            risk_indicators.append("High failure rate")
        if any(s.severity == "CRITICAL" for s in team_signals):
            risk_indicators.append("Critical incidents in history")

        # Success factors
        success_factors = []
        if quality_score > 0.7:
            success_factors.append("High overall success rate")
        if len(collaboration_patterns) > 3:
            success_factors.append("Strong cross-team collaboration")

        return TeamKnowledge(
            team_name=team_name,
            expertise_areas=expertise_areas,
            common_mistakes=common_mistakes,
            preferred_practices=preferred_practices,
            collaboration_patterns=collaboration_patterns,
            risk_indicators=risk_indicators,
            success_factors=success_factors,
            knowledge_gaps=[],  # TODO: Implement gap analysis
            activity_level=activity_level,
            quality_score=quality_score,
        )

    def generate_org_knowledge(
        self, signals: List[OrgSignal], org_name: str
    ) -> OrgKnowledge:
        """
        Generate comprehensive organizational knowledge

        Args:
            signals: All organizational signals
            org_name: Organization name

        Returns:
            Complete organizational knowledge
        """
        logger.info(f"Generating comprehensive knowledge for organization: {org_name}")

        # Filter signals for this org
        org_signals = [s for s in signals if s.org == org_name]

        if not org_signals:
            return OrgKnowledge(
                org_name=org_name,
                analysis_period=(datetime.now() - timedelta(days=30), datetime.now()),
                total_signals_analyzed=0,
                patterns=[],
                team_knowledge={},
                cross_team_insights={},
                critical_insights=[],
                improvement_opportunities=[],
                success_practices=[],
                risk_areas=[],
                confidence_score=0.5,
            )

        # Determine analysis period
        start_date = min(s.timestamp for s in org_signals)
        end_date = max(s.timestamp for s in org_signals)

        # Generate patterns
        patterns = self.aggregate_patterns(org_signals)

        # Generate team knowledge
        teams = set(s.team for s in org_signals if s.team)
        team_knowledge = {}
        for team in teams:
            team_knowledge[team] = self.generate_team_knowledge(org_signals, team)

        # Cross-team insights
        cross_team_insights = self._analyze_cross_team_patterns(
            org_signals, team_knowledge
        )

        # Critical insights
        critical_insights = self._extract_critical_insights(patterns, team_knowledge)

        # Improvement opportunities
        improvement_opportunities = self._identify_improvement_opportunities(
            patterns, team_knowledge
        )

        # Success practices
        success_practices = self._extract_success_practices(patterns, team_knowledge)

        # Risk areas
        risk_areas = self._identify_risk_areas(patterns, team_knowledge)

        # Calculate overall confidence
        confidence_score = self._calculate_knowledge_confidence(
            org_signals, patterns, team_knowledge
        )

        return OrgKnowledge(
            org_name=org_name,
            analysis_period=(start_date, end_date),
            total_signals_analyzed=len(org_signals),
            patterns=patterns,
            team_knowledge=team_knowledge,
            cross_team_insights=cross_team_insights,
            critical_insights=critical_insights,
            improvement_opportunities=improvement_opportunities,
            success_practices=success_practices,
            risk_areas=risk_areas,
            confidence_score=confidence_score,
        )

    def _identify_failure_hotspots(
        self, signals: List[OrgSignal], min_frequency: int
    ) -> List[OrgPattern]:
        """Identify files/areas with frequent failures"""
        failure_signals = [
            s
            for s in signals
            if s.signal_type
            in [
                SignalType.CI_FAILURE,
                SignalType.PR_REJECTION,
                SignalType.ROLLBACK,
                SignalType.INCIDENT,
                SignalType.DEPLOYMENT_FAILURE,
            ]
        ]

        file_failures = defaultdict(list)
        for signal in failure_signals:
            for file_path in signal.files:
                file_failures[file_path].append(signal.id)

        patterns = []
        for file_path, signal_ids in file_failures.items():
            if len(signal_ids) >= min_frequency:
                confidence = min(1.0, len(signal_ids) / (min_frequency * 2))

                # Determine impact level
                signal_severities = []
                for signal in failure_signals:
                    if signal.id in signal_ids:
                        signal_severities.append(signal.severity)

                if "CRITICAL" in signal_severities:
                    impact_level = "CRITICAL"
                elif "HIGH" in signal_severities:
                    impact_level = "HIGH"
                else:
                    impact_level = "MEDIUM"

                pattern = OrgPattern(
                    pattern_id=f"hotspot_{hash(file_path) % 10000}",
                    pattern_type="failure_hotspot",
                    description=f"File {file_path} has frequent failures",
                    confidence=confidence,
                    frequency=len(signal_ids),
                    evidence=signal_ids,
                    affected_entities=[file_path],
                    first_seen=min(
                        s.timestamp for s in failure_signals if s.id in signal_ids
                    ),
                    last_seen=max(
                        s.timestamp for s in failure_signals if s.id in signal_ids
                    ),
                    trend="stable",  # TODO: Calculate actual trend
                    impact_level=impact_level,
                    recommendations=[
                        f"Add comprehensive tests for {file_path}",
                        f"Require additional code review for {file_path}",
                        "Consider refactoring for better maintainability",
                    ],
                )
                patterns.append(pattern)

        return patterns

    def _identify_success_practices(
        self, signals: List[OrgSignal], min_frequency: int
    ) -> List[OrgPattern]:
        """Identify practices that lead to success"""
        success_signals = [
            s
            for s in signals
            if s.signal_type
            in [
                SignalType.CI_SUCCESS,
                SignalType.PR_APPROVAL,
                SignalType.DEPLOYMENT_SUCCESS,
            ]
        ]

        # Look for patterns in successful signals
        tag_success = defaultdict(list)
        for signal in success_signals:
            for tag in signal.tags:
                tag_success[tag].append(signal.id)

        patterns = []
        for tag, signal_ids in tag_success.items():
            if len(signal_ids) >= min_frequency:
                confidence = min(1.0, len(signal_ids) / (min_frequency * 3))

                pattern = OrgPattern(
                    pattern_id=f"success_{hash(tag) % 10000}",
                    pattern_type="success_practice",
                    description=f"Tag '{tag}' correlates with successful outcomes",
                    confidence=confidence,
                    frequency=len(signal_ids),
                    evidence=signal_ids,
                    affected_entities=[tag],
                    first_seen=min(
                        s.timestamp for s in success_signals if s.id in signal_ids
                    ),
                    last_seen=max(
                        s.timestamp for s in success_signals if s.id in signal_ids
                    ),
                    trend="stable",
                    impact_level="MEDIUM",
                    recommendations=[
                        f"Encourage use of '{tag}' practices across teams",
                        f"Document best practices related to '{tag}'",
                    ],
                )
                patterns.append(pattern)

        return patterns

    def _identify_author_patterns(
        self, signals: List[OrgSignal], min_frequency: int
    ) -> List[OrgPattern]:
        """Identify patterns related to specific authors"""
        author_signals = defaultdict(list)
        for signal in signals:
            if signal.author:
                author_signals[signal.author].append(signal)

        patterns = []
        for author, author_sigs in author_signals.items():
            if len(author_sigs) >= min_frequency:
                # Analyze author's success/failure pattern
                failures = len(
                    [
                        s
                        for s in author_sigs
                        if s.signal_type
                        in [
                            SignalType.CI_FAILURE,
                            SignalType.PR_REJECTION,
                            SignalType.ROLLBACK,
                        ]
                    ]
                )
                successes = len(
                    [
                        s
                        for s in author_sigs
                        if s.signal_type
                        in [
                            SignalType.CI_SUCCESS,
                            SignalType.PR_APPROVAL,
                            SignalType.DEPLOYMENT_SUCCESS,
                        ]
                    ]
                )

                if failures > successes * 1.5:  # High failure rate
                    pattern = OrgPattern(
                        pattern_id=f"author_risk_{hash(author) % 10000}",
                        pattern_type="author_risk",
                        description=f"Author {author} has high failure rate",
                        confidence=0.8,
                        frequency=failures,
                        evidence=[s.id for s in author_sigs],
                        affected_entities=[author],
                        first_seen=min(s.timestamp for s in author_sigs),
                        last_seen=max(s.timestamp for s in author_sigs),
                        trend="stable",
                        impact_level="MEDIUM",
                        recommendations=[
                            f"Provide additional training for {author}",
                            f"Require peer review for {author}'s changes",
                            "Consider mentoring program",
                        ],
                    )
                    patterns.append(pattern)

        return patterns

    def _identify_temporal_patterns(
        self, signals: List[OrgSignal], min_frequency: int
    ) -> List[OrgPattern]:
        """Identify time-based patterns"""
        # Group signals by day of week
        weekday_failures = defaultdict(list)

        for signal in signals:
            if signal.signal_type in [
                SignalType.CI_FAILURE,
                SignalType.DEPLOYMENT_FAILURE,
            ]:
                weekday = signal.timestamp.strftime("%A")
                weekday_failures[weekday].append(signal.id)

        patterns = []
        total_failures = sum(len(failures) for failures in weekday_failures.values())

        for weekday, failure_ids in weekday_failures.items():
            if len(failure_ids) >= min_frequency:
                # Check if this day has disproportionately high failures
                expected = total_failures / 7
                if len(failure_ids) > expected * 1.5:
                    pattern = OrgPattern(
                        pattern_id=f"temporal_{weekday.lower()}",
                        pattern_type="temporal_pattern",
                        description=f"{weekday} has unusually high failure rate",
                        confidence=0.7,
                        frequency=len(failure_ids),
                        evidence=failure_ids,
                        affected_entities=[weekday],
                        first_seen=datetime.now() - timedelta(days=30),
                        last_seen=datetime.now(),
                        trend="stable",
                        impact_level="LOW",
                        recommendations=[
                            f"Investigate why {weekday} has more failures",
                            "Consider deployment scheduling adjustments",
                            "Review team workload distribution",
                        ],
                    )
                    patterns.append(pattern)

        return patterns

    def _identify_cross_repo_patterns(
        self, signals: List[OrgSignal], min_frequency: int
    ) -> List[OrgPattern]:
        """Identify patterns across repositories"""
        # Find authors who work across multiple repos
        author_repos = defaultdict(set)
        for signal in signals:
            if signal.author:
                author_repos[signal.author].add(signal.repo)

        patterns = []
        for author, repos in author_repos.items():
            if len(repos) >= 3:  # Author works on multiple repos
                author_signals = [s for s in signals if s.author == author]

                pattern = OrgPattern(
                    pattern_id=f"cross_repo_{hash(author) % 10000}",
                    pattern_type="cross_repo_expertise",
                    description=f"Author {author} has cross-repository expertise",
                    confidence=0.8,
                    frequency=len(author_signals),
                    evidence=[s.id for s in author_signals],
                    affected_entities=[author] + list(repos),
                    first_seen=min(s.timestamp for s in author_signals),
                    last_seen=max(s.timestamp for s in author_signals),
                    trend="stable",
                    impact_level="MEDIUM",
                    recommendations=[
                        f"Leverage {author}'s cross-repo knowledge for architecture decisions",
                        "Consider {author} for cross-team coordination",
                    ],
                )
                patterns.append(pattern)

        return patterns

    def _analyze_cross_team_patterns(
        self, signals: List[OrgSignal], team_knowledge: Dict[str, TeamKnowledge]
    ) -> Dict[str, Any]:
        """Analyze patterns across teams"""
        insights = {
            "team_collaboration_matrix": {},
            "shared_expertise_areas": {},
            "knowledge_transfer_opportunities": [],
            "coordination_bottlenecks": [],
        }

        # Team collaboration matrix
        for team1, knowledge1 in team_knowledge.items():
            insights["team_collaboration_matrix"][team1] = (
                knowledge1.collaboration_patterns
            )

        # Shared expertise areas
        expertise_teams = defaultdict(list)
        for team, knowledge in team_knowledge.items():
            for area in knowledge.expertise_areas:
                expertise_teams[area].append(team)

        insights["shared_expertise_areas"] = {
            area: teams for area, teams in expertise_teams.items() if len(teams) > 1
        }

        return insights

    def _extract_critical_insights(
        self, patterns: List[OrgPattern], team_knowledge: Dict[str, TeamKnowledge]
    ) -> List[str]:
        """Extract critical insights requiring immediate attention"""
        insights = []

        # Critical patterns
        critical_patterns = [p for p in patterns if p.impact_level == "CRITICAL"]
        if critical_patterns:
            insights.append(
                f"CRITICAL: {len(critical_patterns)} critical patterns require immediate action"
            )

        # Teams with high risk
        risky_teams = [
            team
            for team, knowledge in team_knowledge.items()
            if knowledge.quality_score < 0.4 and knowledge.activity_level == "HIGH"
        ]
        if risky_teams:
            insights.append(
                f"HIGH: Teams {risky_teams} have high activity but low quality"
            )

        return insights

    def _identify_improvement_opportunities(
        self, patterns: List[OrgPattern], team_knowledge: Dict[str, TeamKnowledge]
    ) -> List[str]:
        """Identify improvement opportunities"""
        opportunities = []

        # High-frequency failure patterns
        failure_hotspots = [
            p
            for p in patterns
            if p.pattern_type == "failure_hotspot" and p.frequency >= 5
        ]
        if failure_hotspots:
            opportunities.append(
                f"Refactor {len(failure_hotspots)} failure hotspots to improve reliability"
            )

        # Teams with knowledge gaps
        low_activity_teams = [
            team
            for team, knowledge in team_knowledge.items()
            if knowledge.activity_level == "LOW"
        ]
        if low_activity_teams:
            opportunities.append(
                "Increase engagement and knowledge sharing for low-activity teams"
            )

        return opportunities

    def _extract_success_practices(
        self, patterns: List[OrgPattern], team_knowledge: Dict[str, TeamKnowledge]
    ) -> List[str]:
        """Extract successful practices to promote"""
        practices = []

        # Successful patterns
        success_patterns = [p for p in patterns if p.pattern_type == "success_practice"]
        for pattern in success_patterns:
            practices.append(pattern.description)

        # High-quality teams' practices
        high_quality_teams = [
            team
            for team, knowledge in team_knowledge.items()
            if knowledge.quality_score > 0.8
        ]
        if high_quality_teams:
            practices.append(
                f"Adopt practices from high-performing teams: {high_quality_teams}"
            )

        return practices

    def _identify_risk_areas(
        self, patterns: List[OrgPattern], team_knowledge: Dict[str, TeamKnowledge]
    ) -> List[str]:
        """Identify risk areas requiring attention"""
        risks = []

        # Pattern-based risks
        risk_patterns = [p for p in patterns if p.impact_level in ["HIGH", "CRITICAL"]]
        if risk_patterns:
            risks.append(
                f"{len(risk_patterns)} high-impact patterns pose organizational risk"
            )

        # Team-based risks
        teams_with_risks = [
            team
            for team, knowledge in team_knowledge.items()
            if len(knowledge.risk_indicators) > 2
        ]
        if teams_with_risks:
            risks.append(f"Teams with elevated risk: {teams_with_risks}")

        return risks

    def _calculate_knowledge_confidence(
        self,
        signals: List[OrgSignal],
        patterns: List[OrgPattern],
        team_knowledge: Dict[str, TeamKnowledge],
    ) -> float:
        """Calculate confidence in the aggregated knowledge"""
        # Base confidence from data volume
        data_confidence = min(1.0, len(signals) / 100.0)

        # Pattern confidence
        pattern_confidences = [p.confidence for p in patterns]
        pattern_confidence = (
            sum(pattern_confidences) / len(pattern_confidences)
            if pattern_confidences
            else 0.5
        )

        # Team knowledge completeness
        team_confidence = len(team_knowledge) / max(
            1, len(set(s.team for s in signals if s.team))
        )

        return data_confidence * 0.4 + pattern_confidence * 0.4 + team_confidence * 0.2


# Convenience function
def aggregate_patterns(signals: List[OrgSignal]) -> List[OrgPattern]:
    """Convenience function to aggregate patterns from signals"""
    aggregator = KnowledgeAggregator()
    return aggregator.aggregate_patterns(signals)
