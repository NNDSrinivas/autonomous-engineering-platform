"""
MultiRepoOrchestrator — Principal Engineer AI

Master orchestrator that makes Principal Engineer and Platform Architect level
decisions across repository boundaries. This is the brain that coordinates all
multi-repository intelligence components to provide system-wide reasoning.

Key Capabilities:
- System-wide architectural decision making
- Cross-repository change planning and execution
- Technology stack standardization recommendations
- Platform evolution strategy
- Risk-based decision making with business context
- Automated governance and compliance enforcement
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple

from .repo_registry import RepoRegistry, RepoMeta
from .repo_graph_builder import RepoGraphBuilder, RepoGraph
from .dependency_resolver import DependencyResolver
from .contract_analyzer import ContractAnalyzer
from .impact_analyzer import ImpactAnalyzer, RiskLevel
from .change_coordinator import ChangeCoordinator, ChangeRequest

logger = logging.getLogger(__name__)


class DecisionType(Enum):
    """Types of architectural decisions"""

    TECHNOLOGY_ADOPTION = "technology_adoption"
    REFACTORING_STRATEGY = "refactoring_strategy"
    DEPENDENCY_MANAGEMENT = "dependency_management"
    SECURITY_COMPLIANCE = "security_compliance"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    SCALING_STRATEGY = "scaling_strategy"
    MIGRATION_PLANNING = "migration_planning"
    STANDARDIZATION = "standardization"


class ConfidenceLevel(Enum):
    """Confidence levels for decisions"""

    LOW = "low"  # < 60% confidence
    MEDIUM = "medium"  # 60-80% confidence
    HIGH = "high"  # 80-95% confidence
    VERY_HIGH = "very_high"  # > 95% confidence


@dataclass
class ArchitecturalDecision:
    """Represents a major architectural decision"""

    decision_id: str
    decision_type: DecisionType
    title: str
    description: str

    # Decision context
    affected_repositories: List[str] = field(default_factory=list)
    business_justification: str = ""
    technical_rationale: str = ""

    # Decision details
    recommended_action: str = ""
    alternatives_considered: List[str] = field(default_factory=list)
    trade_offs: Dict[str, str] = field(default_factory=dict)

    # Confidence and risk
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    risk_assessment: RiskLevel = RiskLevel.MEDIUM

    # Implementation
    implementation_plan: List[str] = field(default_factory=list)
    estimated_effort_weeks: int = 0
    required_approvals: List[str] = field(default_factory=list)

    # Tracking
    created_at: datetime = field(default_factory=datetime.now)
    status: str = "proposed"  # proposed, approved, implementing, completed
    decision_maker: str = "navi-orchestrator"


@dataclass
class SystemHealthReport:
    """Comprehensive system health analysis"""

    report_id: str
    generated_at: datetime = field(default_factory=datetime.now)

    # System overview
    total_repositories: int = 0
    active_repositories: int = 0
    deprecated_repositories: int = 0

    # Dependency analysis
    total_dependencies: int = 0
    outdated_dependencies: int = 0
    vulnerable_dependencies: int = 0
    dependency_conflicts: int = 0

    # Technology stack
    language_distribution: Dict[str, int] = field(default_factory=dict)
    framework_usage: Dict[str, int] = field(default_factory=dict)
    version_fragmentation: Dict[str, List[str]] = field(default_factory=dict)

    # Architecture quality
    circular_dependencies: List[str] = field(default_factory=list)
    single_points_of_failure: List[str] = field(default_factory=list)
    highly_coupled_systems: List[Tuple[str, str]] = field(default_factory=list)

    # Risk factors
    high_risk_repositories: List[str] = field(default_factory=list)
    compliance_issues: List[str] = field(default_factory=list)
    performance_concerns: List[str] = field(default_factory=list)

    # Recommendations
    immediate_actions: List[str] = field(default_factory=list)
    strategic_improvements: List[str] = field(default_factory=list)
    overall_health_score: float = 0.5  # 0.0 - 1.0


class MultiRepoOrchestrator:
    """
    Master orchestrator that provides Principal Engineer and Platform Architect
    level intelligence across the entire repository ecosystem.
    """

    def __init__(
        self,
        repo_registry: Optional[RepoRegistry] = None,
        graph_builder: Optional[RepoGraphBuilder] = None,
        dependency_resolver: Optional[DependencyResolver] = None,
        contract_analyzer: Optional[ContractAnalyzer] = None,
        impact_analyzer: Optional[ImpactAnalyzer] = None,
        change_coordinator: Optional[ChangeCoordinator] = None,
    ):
        """Initialize the multi-repo orchestrator"""
        self.repo_registry = repo_registry or RepoRegistry()
        self.graph_builder = graph_builder or RepoGraphBuilder(self.repo_registry)
        self.dependency_resolver = dependency_resolver or DependencyResolver()
        self.contract_analyzer = contract_analyzer or ContractAnalyzer()
        self.impact_analyzer = impact_analyzer or ImpactAnalyzer(
            repo_registry=self.repo_registry,
            graph_builder=self.graph_builder,
            dependency_resolver=self.dependency_resolver,
            contract_analyzer=self.contract_analyzer,
        )
        self.change_coordinator = change_coordinator or ChangeCoordinator(
            repo_registry=self.repo_registry,
            graph_builder=self.graph_builder,
            impact_analyzer=self.impact_analyzer,
        )

        # Decision tracking
        self.architectural_decisions: Dict[str, ArchitecturalDecision] = {}

        # System monitoring
        self.last_health_report: Optional[SystemHealthReport] = None
        self.health_report_interval = timedelta(hours=24)

        logger.info(
            "MultiRepoOrchestrator initialized for Principal Engineer-level decisions"
        )

    async def analyze_system_health(self) -> SystemHealthReport:
        """
        Perform comprehensive system health analysis

        Returns:
            Complete system health report
        """
        logger.info("Performing comprehensive system health analysis")

        report_id = f"health-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        report = SystemHealthReport(report_id=report_id)

        # Get all repositories
        all_repos = await self.repo_registry.list_repositories()
        report.total_repositories = len(all_repos)
        report.active_repositories = len([r for r in all_repos if r.is_active])
        report.deprecated_repositories = len([r for r in all_repos if not r.is_active])

        # Build comprehensive dependency graph
        repo_graph = await self.graph_builder.build_dependency_graph(
            include_external=True, include_transitive=True
        )

        # Analyze dependencies across all repositories
        dependency_analysis = await self._analyze_system_dependencies(all_repos)
        report.total_dependencies = dependency_analysis["total"]
        report.outdated_dependencies = dependency_analysis["outdated"]
        report.vulnerable_dependencies = dependency_analysis["vulnerable"]
        report.dependency_conflicts = dependency_analysis["conflicts"]

        # Technology stack analysis
        tech_analysis = await self._analyze_technology_stack(all_repos)
        report.language_distribution = tech_analysis["languages"]
        report.framework_usage = tech_analysis["frameworks"]
        report.version_fragmentation = tech_analysis["version_fragmentation"]

        # Architecture quality analysis
        arch_analysis = await self._analyze_architecture_quality(repo_graph)
        report.circular_dependencies = arch_analysis["circular_deps"]
        report.single_points_of_failure = arch_analysis["spof"]
        report.highly_coupled_systems = arch_analysis["high_coupling"]

        # Risk assessment
        risk_analysis = await self._assess_system_risks(all_repos, repo_graph)
        report.high_risk_repositories = risk_analysis["high_risk_repos"]
        report.compliance_issues = risk_analysis["compliance_issues"]
        report.performance_concerns = risk_analysis["performance_concerns"]

        # Generate recommendations
        recommendations = await self._generate_system_recommendations(report)
        report.immediate_actions = recommendations["immediate"]
        report.strategic_improvements = recommendations["strategic"]

        # Calculate overall health score
        report.overall_health_score = self._calculate_system_health_score(report)

        self.last_health_report = report

        logger.info(
            f"System health analysis complete. Overall score: {report.overall_health_score:.2f}"
        )
        return report

    async def make_architectural_decision(
        self,
        decision_type: DecisionType,
        context: Dict[str, Any],
        business_priority: str = "medium",
    ) -> ArchitecturalDecision:
        """
        Make a data-driven architectural decision

        Args:
            decision_type: Type of architectural decision
            context: Context and parameters for the decision
            business_priority: Business priority level

        Returns:
            Architectural decision with rationale
        """
        logger.info(f"Making architectural decision: {decision_type.value}")

        decision_id = f"decision-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        # Gather system intelligence
        if not self.last_health_report or (
            datetime.now() - self.last_health_report.generated_at
            > self.health_report_interval
        ):
            await self.analyze_system_health()

        # Make decision based on type
        if decision_type == DecisionType.TECHNOLOGY_ADOPTION:
            decision = await self._decide_technology_adoption(decision_id, context)
        elif decision_type == DecisionType.DEPENDENCY_MANAGEMENT:
            decision = await self._decide_dependency_strategy(decision_id, context)
        elif decision_type == DecisionType.REFACTORING_STRATEGY:
            decision = await self._decide_refactoring_strategy(decision_id, context)
        elif decision_type == DecisionType.MIGRATION_PLANNING:
            decision = await self._decide_migration_strategy(decision_id, context)
        elif decision_type == DecisionType.STANDARDIZATION:
            decision = await self._decide_standardization_strategy(decision_id, context)
        else:
            # Generic decision framework
            decision = await self._make_generic_decision(
                decision_id, decision_type, context
            )

        self.architectural_decisions[decision_id] = decision

        logger.info(f"Architectural decision made: {decision.title}")
        return decision

    async def plan_system_evolution(
        self, target_state: Dict[str, Any], timeline_months: int = 12
    ) -> Dict[str, Any]:
        """
        Plan the evolution of the system toward a target state

        Args:
            target_state: Desired system characteristics
            timeline_months: Timeline for evolution

        Returns:
            Comprehensive evolution plan
        """
        logger.info(f"Planning system evolution over {timeline_months} months")

        # Analyze current state
        current_health = await self.analyze_system_health()

        # Identify gaps between current and target state
        gaps = await self._identify_evolution_gaps(current_health, target_state)

        # Create evolution roadmap
        roadmap = await self._create_evolution_roadmap(gaps, timeline_months)

        # Estimate effort and resources
        resource_plan = await self._estimate_evolution_resources(roadmap)

        evolution_plan = {
            "current_state": {
                "health_score": current_health.overall_health_score,
                "key_metrics": self._extract_key_metrics(current_health),
            },
            "target_state": target_state,
            "identified_gaps": gaps,
            "evolution_roadmap": roadmap,
            "resource_requirements": resource_plan,
            "timeline_months": timeline_months,
            "success_criteria": self._define_success_criteria(target_state),
            "risk_mitigation": await self._plan_evolution_risk_mitigation(roadmap),
        }

        logger.info("System evolution plan created")
        return evolution_plan

    async def recommend_coordinated_changes(
        self, problem_description: str, max_repositories: int = 10
    ) -> List[ChangeRequest]:
        """
        Recommend coordinated changes across repositories to solve a problem

        Args:
            problem_description: Description of the problem to solve
            max_repositories: Maximum number of repositories to modify

        Returns:
            List of recommended changes
        """
        logger.info(f"Analyzing problem for coordinated changes: {problem_description}")

        # Analyze the problem and identify affected systems
        affected_systems = await self._identify_affected_systems(problem_description)

        # Determine optimal solution approach
        solution_strategy = await self._determine_solution_strategy(
            problem_description, affected_systems
        )

        # Generate specific change requests
        change_requests = await self._generate_change_requests(
            solution_strategy, affected_systems, max_repositories
        )

        # Optimize change order and dependencies
        optimized_changes = await self._optimize_change_dependencies(change_requests)

        logger.info(f"Generated {len(optimized_changes)} coordinated change requests")
        return optimized_changes

    async def _analyze_system_dependencies(
        self, repositories: List[RepoMeta]
    ) -> Dict[str, int]:
        """Analyze dependencies across all repositories"""
        total_deps = 0
        outdated_deps = 0
        vulnerable_deps = 0
        conflicts = 0

        dependency_graphs = []

        # Analyze each repository's dependencies
        for repo in repositories[:20]:  # Limit to prevent timeout
            try:
                dep_graph = self.dependency_resolver.resolve_dependencies(
                    repo.path, repo.name
                )
                dependency_graphs.append(dep_graph)

                total_deps += dep_graph.total_dependencies
                vulnerable_deps += len(dep_graph.vulnerabilities)

                # Simple heuristic for outdated dependencies
                outdated_deps += len(
                    [
                        d
                        for d in dep_graph.dependencies
                        if "old" in d.version or d.version.startswith("0.")
                    ]
                )

            except Exception as e:
                logger.warning(f"Failed to analyze dependencies for {repo.name}: {e}")

        # Find version conflicts across repositories
        conflicts = len(
            self.dependency_resolver.find_version_conflicts(dependency_graphs)
        )

        return {
            "total": total_deps,
            "outdated": outdated_deps,
            "vulnerable": vulnerable_deps,
            "conflicts": conflicts,
        }

    async def _analyze_technology_stack(
        self, repositories: List[RepoMeta]
    ) -> Dict[str, Any]:
        """Analyze technology stack distribution"""
        languages = defaultdict(int)
        frameworks = defaultdict(int)
        version_fragmentation = defaultdict(list)

        for repo in repositories:
            # Count primary languages
            if repo.primary_language:
                languages[repo.primary_language] += 1

            # Analyze frameworks (would need more sophisticated detection)
            for tech in repo.technologies:
                if "framework" in tech.lower() or "lib" in tech.lower():
                    frameworks[tech] += 1

                # Track version fragmentation
                if ":" in tech:  # Format like "react:18.2.0"
                    tech_name, version = tech.split(":", 1)
                    version_fragmentation[tech_name].append(version)

        return {
            "languages": dict(languages),
            "frameworks": dict(frameworks),
            "version_fragmentation": {
                k: list(set(v)) for k, v in version_fragmentation.items()
            },
        }

    async def _analyze_architecture_quality(
        self, repo_graph: RepoGraph
    ) -> Dict[str, Any]:
        """Analyze architecture quality metrics"""
        # Find circular dependencies
        circular_deps = repo_graph.find_circular_dependencies()

        # Identify single points of failure (high-dependency nodes)
        all_repos = repo_graph.repositories
        spof = []
        high_coupling = []

        for repo in all_repos:
            dependents = repo_graph.get_dependents(repo)
            if len(dependents) > 10:  # High number of dependents
                spof.append(repo)

            # Find highly coupled pairs (both depend on each other's dependencies)
            dependencies = set(repo_graph.get_dependencies(repo))
            for other_repo in all_repos:
                if repo != other_repo:
                    other_deps = set(repo_graph.get_dependencies(other_repo))
                    if len(dependencies & other_deps) > 5:  # Many shared dependencies
                        if (other_repo, repo) not in high_coupling:
                            high_coupling.append((repo, other_repo))

        return {
            "circular_deps": circular_deps,
            "spof": spof,
            "high_coupling": high_coupling,
        }

    async def _assess_system_risks(
        self, repositories: List[RepoMeta], repo_graph: RepoGraph
    ) -> Dict[str, List[str]]:
        """Assess system-wide risks"""
        high_risk_repos = []
        compliance_issues = []
        performance_concerns = []

        for repo in repositories:
            # High risk factors
            risk_factors = 0

            if repo.business_criticality == "critical":
                risk_factors += 1

            if not repo.is_active:
                risk_factors += 2
                compliance_issues.append(
                    f"Deprecated repository still in use: {repo.name}"
                )

            if len(repo_graph.get_dependents(repo.name)) > 10:
                risk_factors += 1
                performance_concerns.append(f"High-dependency repository: {repo.name}")

            if risk_factors >= 2:
                high_risk_repos.append(repo.name)

            # Compliance checks
            if not repo.has_documentation:
                compliance_issues.append(f"Missing documentation: {repo.name}")

            if not repo.technologies:  # No technology metadata
                compliance_issues.append(f"Missing technology metadata: {repo.name}")

        return {
            "high_risk_repos": high_risk_repos,
            "compliance_issues": compliance_issues,
            "performance_concerns": performance_concerns,
        }

    async def _generate_system_recommendations(
        self, report: SystemHealthReport
    ) -> Dict[str, List[str]]:
        """Generate system improvement recommendations"""
        immediate = []
        strategic = []

        # Immediate actions based on critical issues
        if report.vulnerable_dependencies > 0:
            immediate.append(
                f"Update {report.vulnerable_dependencies} vulnerable dependencies"
            )

        if report.circular_dependencies:
            immediate.append(
                f"Resolve {len(report.circular_dependencies)} circular dependencies"
            )

        if report.compliance_issues:
            immediate.append(
                f"Address {len(report.compliance_issues)} compliance issues"
            )

        # Strategic improvements
        if report.version_fragmentation:
            strategic.append("Implement technology standardization program")

        if report.overall_health_score < 0.7:
            strategic.append("Develop comprehensive technical debt reduction plan")

        if len(report.single_points_of_failure) > 3:
            strategic.append("Implement system resilience improvements")

        return {"immediate": immediate, "strategic": strategic}

    def _calculate_system_health_score(self, report: SystemHealthReport) -> float:
        """Calculate overall system health score"""
        score = 1.0

        # Penalize for issues
        if report.total_dependencies > 0:
            vulnerable_ratio = (
                report.vulnerable_dependencies / report.total_dependencies
            )
            score -= vulnerable_ratio * 0.3

            outdated_ratio = report.outdated_dependencies / report.total_dependencies
            score -= outdated_ratio * 0.2

        # Penalize for architecture issues
        score -= min(len(report.circular_dependencies) * 0.1, 0.2)
        score -= min(len(report.single_points_of_failure) * 0.05, 0.1)

        # Penalize for compliance issues
        score -= min(len(report.compliance_issues) * 0.02, 0.1)

        return max(0.0, min(score, 1.0))

    # Placeholder implementations for decision-making methods
    async def _decide_technology_adoption(
        self, decision_id: str, context: Dict[str, Any]
    ) -> ArchitecturalDecision:
        """Make technology adoption decision"""
        return ArchitecturalDecision(
            decision_id=decision_id,
            decision_type=DecisionType.TECHNOLOGY_ADOPTION,
            title="Technology Adoption Analysis",
            description="Analysis of new technology adoption",
            recommended_action="Evaluate technology in pilot project first",
            confidence_level=ConfidenceLevel.MEDIUM,
        )

    async def _decide_dependency_strategy(
        self, decision_id: str, context: Dict[str, Any]
    ) -> ArchitecturalDecision:
        """Make dependency management decision"""
        return ArchitecturalDecision(
            decision_id=decision_id,
            decision_type=DecisionType.DEPENDENCY_MANAGEMENT,
            title="Dependency Management Strategy",
            description="Standardization of dependency management approach",
            recommended_action="Implement organization-wide dependency update policy",
            confidence_level=ConfidenceLevel.HIGH,
        )

    async def _decide_refactoring_strategy(
        self, decision_id: str, context: Dict[str, Any]
    ) -> ArchitecturalDecision:
        """Make refactoring strategy decision"""
        return ArchitecturalDecision(
            decision_id=decision_id,
            decision_type=DecisionType.REFACTORING_STRATEGY,
            title="System Refactoring Strategy",
            description="Strategic approach to system refactoring",
            recommended_action="Implement incremental refactoring with feature flags",
            confidence_level=ConfidenceLevel.MEDIUM,
        )

    async def _decide_migration_strategy(
        self, decision_id: str, context: Dict[str, Any]
    ) -> ArchitecturalDecision:
        """Make migration strategy decision"""
        return ArchitecturalDecision(
            decision_id=decision_id,
            decision_type=DecisionType.MIGRATION_PLANNING,
            title="System Migration Strategy",
            description="Plan for migrating to new architecture",
            recommended_action="Implement strangler fig pattern for gradual migration",
            confidence_level=ConfidenceLevel.HIGH,
        )

    async def _decide_standardization_strategy(
        self, decision_id: str, context: Dict[str, Any]
    ) -> ArchitecturalDecision:
        """Make standardization strategy decision"""
        return ArchitecturalDecision(
            decision_id=decision_id,
            decision_type=DecisionType.STANDARDIZATION,
            title="Technology Standardization Strategy",
            description="Approach to standardizing technology stack",
            recommended_action="Create technology radar and adoption guidelines",
            confidence_level=ConfidenceLevel.HIGH,
        )

    async def _make_generic_decision(
        self, decision_id: str, decision_type: DecisionType, context: Dict[str, Any]
    ) -> ArchitecturalDecision:
        """Make generic architectural decision"""
        return ArchitecturalDecision(
            decision_id=decision_id,
            decision_type=decision_type,
            title=f"Generic {decision_type.value.replace('_', ' ').title()} Decision",
            description=f"Analysis and recommendation for {decision_type.value}",
            recommended_action="Further analysis required for specific recommendation",
            confidence_level=ConfidenceLevel.LOW,
        )

    # Additional placeholder methods for evolution planning
    async def _identify_evolution_gaps(
        self, current: SystemHealthReport, target: Dict[str, Any]
    ) -> List[str]:
        return ["Gap analysis not yet implemented"]

    async def _create_evolution_roadmap(
        self, gaps: List[str], timeline_months: int
    ) -> List[Dict[str, Any]]:
        return [{"phase": "Planning", "duration_months": timeline_months}]

    async def _estimate_evolution_resources(
        self, roadmap: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        return {"estimated_effort_months": len(roadmap)}

    def _extract_key_metrics(self, health_report: SystemHealthReport) -> Dict[str, Any]:
        return {
            "total_repositories": health_report.total_repositories,
            "health_score": health_report.overall_health_score,
        }

    def _define_success_criteria(self, target_state: Dict[str, Any]) -> List[str]:
        return ["Success criteria definition not yet implemented"]

    async def _plan_evolution_risk_mitigation(
        self, roadmap: List[Dict[str, Any]]
    ) -> List[str]:
        return ["Risk mitigation planning not yet implemented"]

    async def _identify_affected_systems(self, problem_description: str) -> List[str]:
        return ["System identification not yet implemented"]

    async def _determine_solution_strategy(
        self, problem: str, systems: List[str]
    ) -> Dict[str, Any]:
        return {"strategy": "placeholder"}

    async def _generate_change_requests(
        self, strategy: Dict[str, Any], systems: List[str], max_repos: int
    ) -> List[ChangeRequest]:
        return []

    async def _optimize_change_dependencies(
        self, changes: List[ChangeRequest]
    ) -> List[ChangeRequest]:
        return changes


# Convenience function
async def create_orchestrator() -> MultiRepoOrchestrator:
    """Create a fully configured multi-repo orchestrator"""
    return MultiRepoOrchestrator()
