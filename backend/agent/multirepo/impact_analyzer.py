"""
ImpactAnalyzer — Blast Radius Intelligence

Cross-repository impact analysis engine that traces downstream effects of changes
and calculates true blast radius across repository boundaries. This enables NAVI
to understand the full scope of change impact and prevent cascading failures.

Key Capabilities:
- Trace dependencies across repository boundaries
- Calculate change blast radius and affected systems
- Identify critical paths and single points of failure
- Analyze downstream consumer impact
- Generate change risk assessments and mitigation strategies
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

from .repo_registry import RepoRegistry, RepoMeta
from .repo_graph_builder import RepoGraphBuilder, RepoGraph
from .dependency_resolver import DependencyResolver
from .contract_analyzer import ContractAnalyzer

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk levels for impact analysis"""

    MINIMAL = "minimal"  # Low risk, isolated change
    LOW = "low"  # Some downstream impact
    MEDIUM = "medium"  # Moderate cross-repo impact
    HIGH = "high"  # Significant system-wide impact
    CRITICAL = "critical"  # Mission-critical system impact


class ChangeType(Enum):
    """Types of changes to analyze"""

    CODE_CHANGE = "code_change"
    DEPENDENCY_UPDATE = "dependency_update"
    API_CHANGE = "api_change"
    SCHEMA_CHANGE = "schema_change"
    CONFIGURATION_CHANGE = "configuration_change"
    INFRASTRUCTURE_CHANGE = "infrastructure_change"
    DATABASE_CHANGE = "database_change"


@dataclass
class AffectedRepository:
    """Represents a repository affected by a change"""

    repo_name: str
    impact_type: str  # "direct", "transitive", "consumer"
    distance: int  # Degrees of separation from origin
    affected_components: List[str] = field(default_factory=list)
    breaking_changes: List[str] = field(default_factory=list)
    migration_required: bool = False
    estimated_effort_hours: int = 0
    risk_factors: List[str] = field(default_factory=list)
    mitigation_strategies: List[str] = field(default_factory=list)


@dataclass
class ImpactPath:
    """Represents a path of impact propagation"""

    origin_repo: str
    target_repo: str
    path_repos: List[str] = field(default_factory=list)
    dependency_chain: List[str] = field(default_factory=list)
    total_distance: int = 0
    is_critical_path: bool = False
    risk_multiplier: float = 1.0


@dataclass
class ImpactAnalysis:
    """Complete impact analysis results"""

    change_description: str
    origin_repository: str
    change_type: ChangeType
    analysis_timestamp: datetime = field(default_factory=datetime.now)

    # Impact scope
    affected_repositories: List[AffectedRepository] = field(default_factory=list)
    impact_paths: List[ImpactPath] = field(default_factory=list)
    blast_radius: int = 0  # Number of affected repos
    max_distance: int = 0  # Maximum degrees of separation

    # Risk assessment
    overall_risk: RiskLevel = RiskLevel.MINIMAL
    risk_score: float = 0.0  # 0.0 - 1.0
    critical_systems_affected: List[str] = field(default_factory=list)
    single_points_of_failure: List[str] = field(default_factory=list)

    # Effort estimation
    total_estimated_effort_hours: int = 0
    teams_affected: List[str] = field(default_factory=list)
    deployment_complexity: str = "simple"  # simple, moderate, complex

    # Recommendations
    recommended_approach: str = ""
    rollback_strategy: str = ""
    testing_recommendations: List[str] = field(default_factory=list)
    monitoring_recommendations: List[str] = field(default_factory=list)


class ImpactAnalyzer:
    """
    Advanced impact analysis engine that traces change effects across
    repository boundaries and calculates comprehensive blast radius.
    """

    def __init__(
        self,
        repo_registry: Optional[RepoRegistry] = None,
        graph_builder: Optional[RepoGraphBuilder] = None,
        dependency_resolver: Optional[DependencyResolver] = None,
        contract_analyzer: Optional[ContractAnalyzer] = None,
    ):
        """Initialize the impact analyzer"""
        self.repo_registry = repo_registry or RepoRegistry()
        self.graph_builder = graph_builder or RepoGraphBuilder(self.repo_registry)
        self.dependency_resolver = dependency_resolver or DependencyResolver()
        self.contract_analyzer = contract_analyzer or ContractAnalyzer()

        # Risk factors and their weights
        self.risk_weights = {
            "breaking_api_change": 0.8,
            "database_schema_change": 0.7,
            "authentication_change": 0.9,
            "external_service_dependency": 0.6,
            "shared_library_change": 0.5,
            "configuration_change": 0.3,
            "documentation_only": 0.1,
        }

        logger.info(
            "ImpactAnalyzer initialized with cross-repository blast radius capabilities"
        )

    async def analyze_change_impact(
        self,
        repo_name: str,
        change_description: str,
        change_type: ChangeType,
        changed_files: Optional[List[str]] = None,
        include_transitive: bool = True,
    ) -> ImpactAnalysis:
        """
        Analyze the impact of a change across the repository ecosystem

        Args:
            repo_name: Name of the repository where change originates
            change_description: Description of the change
            change_type: Type of change being made
            changed_files: List of files being changed
            include_transitive: Whether to include transitive dependencies

        Returns:
            Complete impact analysis
        """
        logger.info(f"Analyzing change impact for {repo_name}: {change_description}")

        # Get repository metadata
        repo = await self.repo_registry.get_repository(repo_name)
        if not repo:
            logger.warning(f"Repository {repo_name} not found in registry")
            return ImpactAnalysis(
                change_description=change_description,
                origin_repository=repo_name,
                change_type=change_type,
            )

        # Build current dependency graph
        # Get all repositories first
        try:
            repos = (
                await self.repo_registry.list_repositories()
                if hasattr(self.repo_registry, "list_repositories")
                else []
            )
        except Exception:
            repos = []

        repo_graph = await self.graph_builder.build_dependency_graph(repos)

        # Initialize analysis
        analysis = ImpactAnalysis(
            change_description=change_description,
            origin_repository=repo_name,
            change_type=change_type,
        )

        # Find direct and transitive dependents
        affected_repos = await self._find_affected_repositories(
            repo_name, repo_graph, changed_files
        )

        # Calculate impact paths
        impact_paths = await self._calculate_impact_paths(
            repo_name, affected_repos, repo_graph
        )

        # Analyze contract changes if applicable
        if change_type in [ChangeType.API_CHANGE, ChangeType.SCHEMA_CHANGE]:
            await self._analyze_contract_impacts(
                repo_name, affected_repos, changed_files
            )

        # Calculate risk assessment
        risk_assessment = await self._calculate_risk_assessment(
            repo_name, affected_repos, change_type, repo_graph
        )

        # Generate recommendations
        recommendations = await self._generate_recommendations(
            affected_repos, risk_assessment, change_type
        )

        # Populate analysis results
        analysis.affected_repositories = affected_repos
        analysis.impact_paths = impact_paths
        analysis.blast_radius = len(affected_repos)
        analysis.max_distance = max((r.distance for r in affected_repos), default=0)
        analysis.overall_risk = risk_assessment["level"]
        analysis.risk_score = risk_assessment["score"]
        analysis.critical_systems_affected = risk_assessment["critical_systems"]
        analysis.single_points_of_failure = risk_assessment["spof"]
        analysis.total_estimated_effort_hours = sum(
            r.estimated_effort_hours for r in affected_repos
        )
        analysis.teams_affected = list(
            set(r.repo_name.split("-")[0] for r in affected_repos)
        )
        analysis.recommended_approach = recommendations["approach"]
        analysis.rollback_strategy = recommendations["rollback"]
        analysis.testing_recommendations = recommendations["testing"]
        analysis.monitoring_recommendations = recommendations["monitoring"]

        logger.info(
            f"Impact analysis complete: {analysis.blast_radius} repositories affected"
        )
        return analysis

    async def _find_affected_repositories(
        self,
        origin_repo: str,
        repo_graph: RepoGraph,
        changed_files: Optional[List[str]] = None,
    ) -> List[AffectedRepository]:
        """Find all repositories affected by the change"""
        affected = []
        visited = set()
        queue = deque([(origin_repo, 0, "origin")])

        while queue:
            current_repo, distance, impact_type = queue.popleft()

            if current_repo in visited:
                continue

            visited.add(current_repo)

            # Skip origin repo in results
            if distance > 0:
                repo_meta = await self.repo_registry.get_repository(current_repo)
                if repo_meta:
                    affected_repo = AffectedRepository(
                        repo_name=current_repo,
                        impact_type=impact_type,
                        distance=distance,
                        estimated_effort_hours=self._estimate_effort_hours(
                            repo_meta, impact_type, distance
                        ),
                    )

                    # Determine affected components
                    affected_repo.affected_components = (
                        await self._identify_affected_components(
                            current_repo, origin_repo, changed_files
                        )
                    )

                    # Assess risk factors
                    affected_repo.risk_factors = await self._assess_repo_risk_factors(
                        repo_meta, impact_type, distance
                    )

                    affected.append(affected_repo)

            # Find dependent repositories (consumers of this repo)
            dependents = repo_graph.get_dependents(current_repo)
            for dependent in dependents:
                if dependent not in visited:
                    queue.append((dependent, distance + 1, "consumer"))

            # For dependency changes, also check transitive dependencies
            if distance < 3:  # Limit depth to prevent explosion
                dependencies = repo_graph.get_dependencies(current_repo)
                for dep in dependencies:
                    if dep not in visited:
                        queue.append((dep, distance + 1, "transitive"))

        return affected

    async def _calculate_impact_paths(
        self,
        origin_repo: str,
        affected_repos: List[AffectedRepository],
        repo_graph: RepoGraph,
    ) -> List[ImpactPath]:
        """Calculate impact propagation paths"""
        paths = []

        for affected in affected_repos:
            # Find shortest path from origin to affected repo
            path_repos = self._find_shortest_path(
                origin_repo, affected.repo_name, repo_graph
            )

            if path_repos:
                impact_path = ImpactPath(
                    origin_repo=origin_repo,
                    target_repo=affected.repo_name,
                    path_repos=path_repos,
                    total_distance=len(path_repos) - 1,
                    is_critical_path=affected.impact_type == "consumer",
                )

                # Calculate risk multiplier based on path characteristics
                impact_path.risk_multiplier = self._calculate_path_risk_multiplier(
                    path_repos, repo_graph
                )

                paths.append(impact_path)

        return paths

    def _find_shortest_path(self, start: str, end: str, graph: RepoGraph) -> List[str]:
        """Find shortest path between two repositories"""
        if start == end:
            return [start]

        queue = deque([(start, [start])])
        visited = {start}

        while queue:
            current, path = queue.popleft()

            # Check both dependencies and dependents
            neighbors = graph.get_dependencies(current) + graph.get_dependents(current)

            for neighbor in neighbors:
                if neighbor == end:
                    return path + [neighbor]

                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return []  # No path found

    def _calculate_path_risk_multiplier(
        self, path_repos: List[str], graph: RepoGraph
    ) -> float:
        """Calculate risk multiplier for an impact path"""
        multiplier = 1.0

        for repo in path_repos:
            # High-traffic repos increase risk
            if "api-gateway" in repo.lower() or "proxy" in repo.lower():
                multiplier *= 1.5

            # Core infrastructure repos increase risk
            if "auth" in repo.lower() or "security" in repo.lower():
                multiplier *= 1.3

            # Shared libraries have moderate impact
            if "lib" in repo.lower() or "common" in repo.lower():
                multiplier *= 1.2

        return min(multiplier, 3.0)  # Cap at 3x

    async def _analyze_contract_impacts(
        self,
        origin_repo: str,
        affected_repos: List[AffectedRepository],
        changed_files: Optional[List[str]] = None,
    ) -> None:
        """Analyze API/schema contract impacts"""
        if not changed_files:
            return

        # Look for contract files in changed files
        contract_files = [
            f
            for f in changed_files
            if any(
                pattern in f.lower()
                for pattern in ["openapi", "swagger", "schema", ".proto", ".graphql"]
            )
        ]

        if not contract_files:
            return

        # Analyze each contract file for breaking changes
        for contract_file in contract_files:
            # This would require comparing with previous version
            # For now, we'll simulate the analysis

            # Mark affected repositories as having potential breaking changes
            for affected in affected_repos:
                if affected.impact_type == "consumer":
                    affected.breaking_changes.append(
                        f"Potential breaking change in {contract_file}"
                    )
                    affected.migration_required = True
                    affected.estimated_effort_hours += 4  # Add migration effort

    async def _calculate_risk_assessment(
        self,
        origin_repo: str,
        affected_repos: List[AffectedRepository],
        change_type: ChangeType,
        repo_graph: RepoGraph,
    ) -> Dict[str, Any]:
        """Calculate comprehensive risk assessment"""
        base_risk = 0.0
        critical_systems = []
        spof = []

        # Base risk by change type
        change_type_risks = {
            ChangeType.API_CHANGE: 0.7,
            ChangeType.SCHEMA_CHANGE: 0.6,
            ChangeType.DATABASE_CHANGE: 0.8,
            ChangeType.INFRASTRUCTURE_CHANGE: 0.5,
            ChangeType.DEPENDENCY_UPDATE: 0.4,
            ChangeType.CONFIGURATION_CHANGE: 0.3,
            ChangeType.CODE_CHANGE: 0.2,
        }

        base_risk = change_type_risks.get(change_type, 0.3)

        # Factor in blast radius
        blast_radius_multiplier = min(len(affected_repos) / 10.0, 2.0)
        risk_score = base_risk * (1 + blast_radius_multiplier)

        # Identify critical systems
        for affected in affected_repos:
            repo_meta = await self.repo_registry.get_repository(affected.repo_name)
            if repo_meta:
                if repo_meta.business_criticality == "critical":
                    critical_systems.append(affected.repo_name)
                    risk_score += 0.2

                # Check if repo is a single point of failure
                dependents_count = len(repo_graph.get_dependents(affected.repo_name))
                if dependents_count > 5:  # Many dependents
                    spof.append(affected.repo_name)
                    risk_score += 0.1

        # Determine risk level
        if risk_score >= 0.8:
            risk_level = RiskLevel.CRITICAL
        elif risk_score >= 0.6:
            risk_level = RiskLevel.HIGH
        elif risk_score >= 0.4:
            risk_level = RiskLevel.MEDIUM
        elif risk_score >= 0.2:
            risk_level = RiskLevel.LOW
        else:
            risk_level = RiskLevel.MINIMAL

        return {
            "level": risk_level,
            "score": min(risk_score, 1.0),
            "critical_systems": critical_systems,
            "spof": spof,
        }

    async def _generate_recommendations(
        self,
        affected_repos: List[AffectedRepository],
        risk_assessment: Dict[str, Any],
        change_type: ChangeType,
    ) -> Dict[str, Any]:
        """Generate deployment and rollback recommendations"""
        recommendations = {
            "approach": "",
            "rollback": "",
            "testing": [],
            "monitoring": [],
        }

        risk_level = risk_assessment["level"]

        # Deployment approach based on risk
        if risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
            recommendations["approach"] = (
                "Staged rollout with extensive testing: "
                "1) Deploy to staging environment first, "
                "2) Comprehensive integration testing, "
                "3) Deploy to subset of production traffic, "
                "4) Monitor closely before full deployment"
            )
        elif risk_level == RiskLevel.MEDIUM:
            recommendations["approach"] = (
                "Careful rollout with monitoring: "
                "1) Deploy during low-traffic period, "
                "2) Monitor key metrics, "
                "3) Have rollback plan ready"
            )
        else:
            recommendations["approach"] = "Standard deployment with basic monitoring"

        # Rollback strategy
        if any(r.migration_required for r in affected_repos):
            recommendations["rollback"] = (
                "Complex rollback required: Prepare database migration rollback scripts "
                "and coordinate with all affected teams"
            )
        else:
            recommendations[
                "rollback"
            ] = "Standard rollback: Use deployment automation to revert to previous version"

        # Risk level ordering for comparisons
        risk_order = {
            RiskLevel.MINIMAL: 0,
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.CRITICAL: 4,
        }

        risk_level_value = risk_order.get(risk_level, 0)
        medium_value = risk_order[RiskLevel.MEDIUM]
        high_value = risk_order[RiskLevel.HIGH]

        # Testing recommendations
        if risk_level_value >= medium_value:
            recommendations["testing"].extend(
                [
                    "End-to-end integration testing across all affected repositories",
                    "Load testing to verify performance impact",
                    "Chaos engineering to test failure scenarios",
                ]
            )

        recommendations["testing"].extend(
            [
                "Unit tests for all changed components",
                "Contract testing for API changes",
                "Smoke tests in production environment",
            ]
        )

        # Monitoring recommendations
        recommendations["monitoring"] = [
            "Monitor error rates in all affected services",
            "Track response times and throughput",
            "Set up alerts for key business metrics",
            "Monitor dependency health and circuit breaker status",
        ]

        if risk_level_value >= high_value:
            recommendations["monitoring"].extend(
                [
                    "Real-time dashboard for deployment progress",
                    "Automated rollback triggers based on error thresholds",
                    "Enhanced logging for troubleshooting",
                ]
            )

        return recommendations

    def _estimate_effort_hours(
        self, repo_meta: RepoMeta, impact_type: str, distance: int
    ) -> int:
        """Estimate effort hours for addressing impact"""
        base_hours = {"origin": 0, "consumer": 4, "transitive": 2}.get(impact_type, 1)

        # Factor in repository complexity
        complexity_multiplier = {
            "microservice": 1.0,
            "api_gateway": 1.5,
            "frontend": 0.8,
            "database": 2.0,
            "infrastructure": 1.2,
        }.get(
            (
                repo_meta.repo_type.value
                if hasattr(repo_meta.repo_type, "value")
                else str(repo_meta.repo_type)
            ),
            1.0,
        )

        # Distance penalty
        distance_penalty = max(0, distance - 1) * 0.5

        return int(base_hours * complexity_multiplier * (1 + distance_penalty))

    async def _identify_affected_components(
        self,
        repo_name: str,
        origin_repo: str,
        changed_files: Optional[List[str]] = None,
    ) -> List[str]:
        """Identify specific components affected in a repository"""
        components = []

        repo_meta = await self.repo_registry.get_repository(repo_name)
        if not repo_meta:
            return components

        # Based on repository type, identify likely affected components
        if repo_meta.repo_type in ["api_gateway", "microservice"]:
            components.extend(["API endpoints", "Request routing", "Authentication"])
        elif repo_meta.repo_type == "frontend":
            components.extend(["UI components", "API clients", "State management"])
        elif repo_meta.repo_type == "database":
            components.extend(["Schema", "Stored procedures", "Migrations"])
        elif repo_meta.repo_type == "shared_library":
            components.extend(["Public interfaces", "Exported functions"])

        return components

    async def _assess_repo_risk_factors(
        self, repo_meta: RepoMeta, impact_type: str, distance: int
    ) -> List[str]:
        """Assess risk factors for an affected repository"""
        risk_factors = []

        if repo_meta.business_criticality == "critical":
            risk_factors.append("Business critical system")

        if repo_meta.repo_type == "api_gateway":
            risk_factors.append("Central API gateway - single point of failure")

        if impact_type == "consumer" and distance == 1:
            risk_factors.append("Direct consumer - immediate impact")

        if repo_meta.repo_type == "database":
            risk_factors.append("Database changes - migration complexity")

        return risk_factors


# Convenience functions
async def analyze_change_impact(
    repo_name: str, change_description: str, change_type: ChangeType
) -> ImpactAnalysis:
    """Convenience function for change impact analysis"""
    analyzer = ImpactAnalyzer()
    return await analyzer.analyze_change_impact(
        repo_name, change_description, change_type
    )
