"""
NAVI Multi-Repository Intelligence Integration

This module integrates Phase 4.8 multi-repository intelligence with NAVI's core
reasoning engine, enabling system-wide autonomous engineering capabilities.

Key Integration Points:
- Cross-repository impact analysis for all NAVI operations
- System-wide architectural decision making
- Coordinated multi-repository changes
- Principal Engineer-level strategic thinking

This transforms NAVI from repository-aware to organization-system-aware.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from .multirepo.orchestrator import MultiRepoOrchestrator, DecisionType
from .multirepo.repo_registry import RepoRegistry
from .multirepo.repo_graph_builder import RepoGraphBuilder
from .multirepo.dependency_resolver import DependencyResolver
from .multirepo.contract_analyzer import ContractAnalyzer
from .multirepo.impact_analyzer import ImpactAnalyzer, ChangeType
from .multirepo.change_coordinator import ChangeCoordinator, ChangeRequest

logger = logging.getLogger(__name__)


@dataclass
class SystemContext:
    """System-wide context for NAVI reasoning"""

    workspace_root: str
    current_repository: str
    organization_repos: List[str] = field(default_factory=list)
    system_health_score: float = 1.0
    last_health_check: Optional[datetime] = None


class NaviMultiRepoIntegration:
    """
    Integration layer that enhances NAVI's core reasoning with multi-repository
    intelligence, enabling Principal Engineer-level system thinking.
    """

    def __init__(self, workspace_root: str):
        """Initialize multi-repo integration"""
        self.workspace_root = workspace_root

        # Initialize multi-repo intelligence components
        self.repo_registry = RepoRegistry()
        self.graph_builder = RepoGraphBuilder(self.repo_registry)
        self.dependency_resolver = DependencyResolver()
        self.contract_analyzer = ContractAnalyzer()

        self.impact_analyzer = ImpactAnalyzer(
            repo_registry=self.repo_registry,
            graph_builder=self.graph_builder,
            dependency_resolver=self.dependency_resolver,
            contract_analyzer=self.contract_analyzer,
        )

        self.change_coordinator = ChangeCoordinator(
            repo_registry=self.repo_registry,
            graph_builder=self.graph_builder,
            impact_analyzer=self.impact_analyzer,
        )

        # Master orchestrator for Principal Engineer decisions
        self.multi_repo_orchestrator = MultiRepoOrchestrator(
            repo_registry=self.repo_registry,
            graph_builder=self.graph_builder,
            dependency_resolver=self.dependency_resolver,
            contract_analyzer=self.contract_analyzer,
            impact_analyzer=self.impact_analyzer,
            change_coordinator=self.change_coordinator,
        )

        # System context cache
        self._system_context = None
        self._context_ttl = 300  # 5 minutes
        self._last_context_update = None

        logger.info(
            f"NaviMultiRepoIntegration initialized for workspace: {workspace_root}"
        )

    async def get_system_context(self, force_refresh: bool = False) -> SystemContext:
        """Get or refresh system-wide context"""
        now = datetime.now()

        if (
            not force_refresh
            and self._system_context
            and self._last_context_update
            and (now - self._last_context_update).seconds < self._context_ttl
        ):
            return self._system_context

        logger.info("Refreshing system context...")

        try:
            # Discover current repository
            current_repo = await self._discover_current_repository()

            # Get organization repositories
            org_repos = await self.repo_registry.list_repositories()
            org_repo_names = [repo.name for repo in org_repos]

            # Get system health score
            health_report = await self.multi_repo_orchestrator.analyze_system_health()

            self._system_context = SystemContext(
                workspace_root=self.workspace_root,
                current_repository=current_repo,
                organization_repos=org_repo_names,
                system_health_score=health_report.overall_health_score,
                last_health_check=health_report.generated_at,
            )

            self._last_context_update = now

            logger.info(
                f"System context refreshed: {len(org_repo_names)} repos, health: {health_report.overall_health_score:.2f}"
            )

        except Exception as e:
            logger.error(f"Failed to refresh system context: {e}")
            # Return minimal context
            self._system_context = SystemContext(
                workspace_root=self.workspace_root, current_repository="unknown"
            )

        return self._system_context

    async def enhance_intent_with_system_context(
        self, intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enhance NAVI intent classification with system-wide context.
        This adds organization-level intelligence to every NAVI operation.
        """
        try:
            system_context = await self.get_system_context()

            # Add system context to intent
            intent["system_context"] = {
                "current_repository": system_context.current_repository,
                "total_repositories": len(system_context.organization_repos),
                "system_health_score": system_context.system_health_score,
                "multi_repo_enabled": True,
            }

            # Enhance intent classification based on system context
            if intent.get("kind") == "implement_feature":
                # Check if this might affect multiple repositories
                feature_description = intent.get("raw_text", "")
                if any(
                    keyword in feature_description.lower()
                    for keyword in [
                        "api",
                        "database",
                        "auth",
                        "shared",
                        "common",
                        "library",
                    ]
                ):
                    intent["system_context"]["potential_cross_repo_impact"] = True
                    intent["system_context"][
                        "recommendation"
                    ] = "Consider cross-repository impact analysis"

            elif intent.get("kind") == "fix_bug":
                # For bug fixes, consider system-wide debugging
                bug_description = intent.get("raw_text", "")
                if any(
                    keyword in bug_description.lower()
                    for keyword in [
                        "production",
                        "outage",
                        "critical",
                        "urgent",
                        "system",
                    ]
                ):
                    intent["system_context"]["system_wide_analysis"] = True
                    intent["system_context"][
                        "recommendation"
                    ] = "Perform system health analysis"

            logger.debug(
                f"Enhanced intent with system context for {system_context.current_repository}"
            )

        except Exception as e:
            logger.error(f"Failed to enhance intent with system context: {e}")

        return intent

    async def analyze_change_impact(
        self,
        change_description: str,
        changed_files: Optional[List[str]] = None,
        change_type: str = "code_change",
    ) -> Dict[str, Any]:
        """
        Analyze the system-wide impact of a proposed change.
        This is called by NAVI before making any significant changes.
        """
        try:
            system_context = await self.get_system_context()
            current_repo = system_context.current_repository

            if current_repo == "unknown":
                return {
                    "analysis_available": False,
                    "reason": "Current repository not identified",
                }

            # Convert change type to enum
            change_type_enum = ChangeType.CODE_CHANGE
            try:
                change_type_enum = ChangeType(change_type.lower())
            except ValueError:
                logger.warning(f"Unknown change type: {change_type}, using CODE_CHANGE")

            logger.info(f"Analyzing system-wide impact for change in {current_repo}")

            # Perform impact analysis
            impact_analysis = await self.impact_analyzer.analyze_change_impact(
                repo_name=current_repo,
                change_description=change_description,
                change_type=change_type_enum,
                changed_files=changed_files or [],
            )

            return {
                "analysis_available": True,
                "blast_radius": impact_analysis.blast_radius,
                "affected_repositories": [
                    r.repo_name for r in impact_analysis.affected_repositories
                ],
                "risk_level": impact_analysis.overall_risk.value,
                "risk_score": impact_analysis.risk_score,
                "critical_systems": impact_analysis.critical_systems_affected,
                "estimated_effort_hours": impact_analysis.total_estimated_effort_hours,
                "recommended_approach": impact_analysis.recommended_approach,
                "rollback_strategy": impact_analysis.rollback_strategy,
                "testing_recommendations": impact_analysis.testing_recommendations,
                "requires_coordination": impact_analysis.blast_radius > 1,
                "confidence": "high" if impact_analysis.risk_score > 0.7 else "medium",
            }

        except Exception as e:
            logger.error(f"Impact analysis failed: {e}")
            return {"analysis_available": False, "error": str(e)}

    async def should_coordinate_change(self, impact_analysis: Dict[str, Any]) -> bool:
        """
        Determine if a change should be coordinated across multiple repositories.
        This helps NAVI decide between single-repo and multi-repo workflows.
        """
        if not impact_analysis.get("analysis_available", False):
            return False

        # Coordinate if multiple repositories are affected
        if impact_analysis.get("blast_radius", 0) > 1:
            return True

        # Coordinate if high risk even in single repo
        if impact_analysis.get("risk_level") in ["high", "critical"]:
            return True

        # Coordinate if critical systems are affected
        if impact_analysis.get("critical_systems", []):
            return True

        return False

    async def plan_coordinated_change(
        self, title: str, description: str, impact_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Plan a coordinated change across multiple repositories.
        This generates the execution plan for system-wide changes.
        """
        try:
            affected_repos = impact_analysis.get("affected_repositories", [])

            if not affected_repos:
                return {
                    "plan_available": False,
                    "reason": "No affected repositories identified",
                }

            logger.info(
                f"Planning coordinated change across {len(affected_repos)} repositories"
            )

            # Generate change requests for each affected repository
            change_requests = []
            for repo_name in affected_repos:
                change_request = {
                    "repo_name": repo_name,
                    "branch_name": f"navi-coordinated-{int(datetime.now().timestamp())}",
                    "commit_message": f"{title} - coordinated change",
                    "pr_title": f"[Coordinated] {title}",
                    "pr_description": f"Part of coordinated change: {description}\n\nThis change affects {len(affected_repos)} repositories total.",
                    "file_changes": {},  # Will be populated by NAVI's code generation
                }
                change_requests.append(change_request)

            # Create coordinated change plan
            change_id = await self.change_coordinator.create_coordinated_change(
                title=title,
                description=description,
                change_requests=[ChangeRequest(**cr) for cr in change_requests],
                created_by="navi",
            )

            # Get change status and details
            change_status = self.change_coordinator.get_change_status(change_id)

            return {
                "plan_available": True,
                "change_id": change_id,
                "affected_repositories": affected_repos,
                "change_requests": change_requests,
                "deployment_order": (change_status or {}).get(
                    "deployment_order", affected_repos
                ),
                "requires_approval": (change_status or {}).get(
                    "requires_approval", True
                ),
                "estimated_duration": f"{impact_analysis.get('estimated_effort_hours', 4)} hours",
                "rollback_strategy": impact_analysis.get(
                    "rollback_strategy", "Standard rollback"
                ),
                "coordination_complexity": (
                    "high" if len(affected_repos) > 3 else "medium"
                ),
            }

        except Exception as e:
            logger.error(f"Coordinated change planning failed: {e}")
            return {"plan_available": False, "error": str(e)}

    async def get_architectural_guidance(
        self, problem_description: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get Principal Engineer-level architectural guidance for complex problems.
        This elevates NAVI's reasoning to system architecture level.
        """
        try:
            logger.info(
                f"Requesting architectural guidance: {problem_description[:100]}..."
            )

            # Determine decision type based on problem description
            decision_type = DecisionType.REFACTORING_STRATEGY  # Default

            problem_lower = problem_description.lower()
            if "technology" in problem_lower or "framework" in problem_lower:
                decision_type = DecisionType.TECHNOLOGY_ADOPTION
            elif "dependency" in problem_lower or "package" in problem_lower:
                decision_type = DecisionType.DEPENDENCY_MANAGEMENT
            elif "performance" in problem_lower or "scaling" in problem_lower:
                decision_type = DecisionType.PERFORMANCE_OPTIMIZATION
            elif "security" in problem_lower or "compliance" in problem_lower:
                decision_type = DecisionType.SECURITY_COMPLIANCE
            elif "migration" in problem_lower or "upgrade" in problem_lower:
                decision_type = DecisionType.MIGRATION_PLANNING
            elif "standard" in problem_lower or "consistency" in problem_lower:
                decision_type = DecisionType.STANDARDIZATION

            # Make architectural decision
            decision = await self.multi_repo_orchestrator.make_architectural_decision(
                decision_type=decision_type,
                context=context or {"problem": problem_description},
                business_priority="medium",
            )

            return {
                "guidance_available": True,
                "decision_id": decision.decision_id,
                "title": decision.title,
                "recommended_action": decision.recommended_action,
                "technical_rationale": decision.technical_rationale,
                "business_justification": decision.business_justification,
                "confidence_level": decision.confidence_level.value,
                "risk_assessment": decision.risk_assessment.value,
                "implementation_plan": decision.implementation_plan,
                "estimated_effort_weeks": decision.estimated_effort_weeks,
                "alternatives_considered": decision.alternatives_considered,
                "trade_offs": decision.trade_offs,
                "principal_engineer_recommendation": True,
            }

        except Exception as e:
            logger.error(f"Architectural guidance failed: {e}")
            return {"guidance_available": False, "error": str(e)}

    async def get_system_health_insights(self) -> Dict[str, Any]:
        """
        Get system health insights for proactive engineering decisions.
        This provides system-wide visibility for NAVI's operations.
        """
        try:
            logger.info("Generating system health insights")

            health_report = await self.multi_repo_orchestrator.analyze_system_health()

            return {
                "insights_available": True,
                "overall_health_score": health_report.overall_health_score,
                "system_status": (
                    "healthy"
                    if health_report.overall_health_score > 0.8
                    else (
                        "concerning"
                        if health_report.overall_health_score > 0.6
                        else "critical"
                    )
                ),
                "repository_summary": {
                    "total": health_report.total_repositories,
                    "active": health_report.active_repositories,
                    "deprecated": health_report.deprecated_repositories,
                },
                "dependency_summary": {
                    "total": health_report.total_dependencies,
                    "outdated": health_report.outdated_dependencies,
                    "vulnerable": health_report.vulnerable_dependencies,
                    "conflicts": health_report.dependency_conflicts,
                },
                "technology_stack": {
                    "languages": health_report.language_distribution,
                    "frameworks": health_report.framework_usage,
                    "fragmentation": len(health_report.version_fragmentation),
                },
                "immediate_actions": health_report.immediate_actions,
                "strategic_improvements": health_report.strategic_improvements,
                "single_points_of_failure": health_report.single_points_of_failure,
                "generated_at": health_report.generated_at.isoformat(),
                "recommendations_count": len(health_report.immediate_actions)
                + len(health_report.strategic_improvements),
            }

        except Exception as e:
            logger.error(f"System health insights failed: {e}")
            return {"insights_available": False, "error": str(e)}

    async def _discover_current_repository(self) -> str:
        """Discover the current repository name from workspace"""
        try:
            from pathlib import Path

            workspace_path = Path(self.workspace_root)

            # Try to get repo name from .git/config if it exists
            git_config = workspace_path / ".git" / "config"
            if git_config.exists():
                with open(git_config) as f:
                    content = f.read()
                    # Extract repo name from remote URL
                    for line in content.split("\n"):
                        if "url =" in line:
                            url = line.split("url =")[-1].strip()
                            if url.endswith(".git"):
                                repo_name = url.split("/")[-1][:-4]  # Remove .git
                                return repo_name
                            else:
                                repo_name = url.split("/")[-1]
                                return repo_name

            # Fallback to directory name
            return workspace_path.name

        except Exception as e:
            logger.warning(f"Could not discover current repository: {e}")
            return "unknown"


# Global integration instance (initialized per workspace)
_integration_instances: Dict[str, NaviMultiRepoIntegration] = {}


def get_multi_repo_integration(workspace_root: str) -> NaviMultiRepoIntegration:
    """Get or create multi-repo integration instance for workspace"""
    if workspace_root not in _integration_instances:
        _integration_instances[workspace_root] = NaviMultiRepoIntegration(
            workspace_root
        )
    return _integration_instances[workspace_root]


# Convenience functions for NAVI orchestrator integration
async def enhance_navi_intent_with_system_context(
    intent: Dict[str, Any], workspace_root: str
) -> Dict[str, Any]:
    """Enhance NAVI intent with system-wide context"""
    integration = get_multi_repo_integration(workspace_root)
    return await integration.enhance_intent_with_system_context(intent)


async def analyze_navi_change_impact(
    change_description: str,
    workspace_root: str,
    changed_files: Optional[List[str]] = None,
    change_type: str = "code_change",
) -> Dict[str, Any]:
    """Analyze system-wide impact of NAVI changes"""
    integration = get_multi_repo_integration(workspace_root)
    return await integration.analyze_change_impact(
        change_description, changed_files or [], change_type
    )


async def get_navi_architectural_guidance(
    problem_description: str,
    workspace_root: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Get Principal Engineer-level guidance for NAVI"""
    integration = get_multi_repo_integration(workspace_root)
    return await integration.get_architectural_guidance(
        problem_description, context or {}
    )


async def get_navi_system_health(workspace_root: str) -> Dict[str, Any]:
    """Get system health insights for NAVI operations"""
    integration = get_multi_repo_integration(workspace_root)
    return await integration.get_system_health_insights()
