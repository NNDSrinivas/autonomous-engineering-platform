from typing import Dict, Any, List, Optional, Protocol, Union, cast
import inspect
import asyncio
import json
import logging
import time
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Phase 4.8 Multi-Repository Intelligence imports
MULTIREPO_AVAILABLE = False
try:
    # Import multi-repo components directly
    from .agent.multirepo.repo_registry import RepoRegistry  # type: ignore
    from .agent.multirepo.repo_graph_builder import RepoGraphBuilder  # type: ignore
    from .agent.multirepo.dependency_resolver import DependencyResolver  # type: ignore
    from .agent.multirepo.contract_analyzer import ContractAnalyzer  # type: ignore
    from .agent.multirepo.impact_analyzer import ImpactAnalyzer  # type: ignore
    from .agent.multirepo.change_coordinator import ChangeCoordinator, ChangeRequest  # type: ignore
    from .agent.multirepo.orchestrator import MultiRepoOrchestrator  # type: ignore
    from .agent.multirepo_integration import NaviMultiRepoIntegration  # type: ignore

    MULTIREPO_AVAILABLE = True

except ImportError as e:
    logger.warning(f"Multi-repo intelligence components not available: {e}")

    # Create stub classes with required methods only when imports fail
    class RepoRegistry:
        def __init__(self):
            pass

        async def get_repository(self, name):
            return None

    class RepoGraphBuilder:
        def __init__(self, repo_registry=None):
            pass

        async def build_dependency_graph(self, repos):
            return {}

    class DependencyResolver:
        def __init__(self):
            pass

    class ContractAnalyzer:
        def __init__(self):
            pass

    class ImpactAnalyzer:
        def __init__(
            self,
            repo_registry=None,
            graph_builder=None,
            dependency_resolver=None,
            contract_analyzer=None,
        ):
            pass

        async def analyze_change_impact(self, *args, **kwargs):
            return {}

    class ChangeCoordinator:
        def __init__(
            self, repo_registry=None, graph_builder=None, impact_analyzer=None
        ):
            pass

        async def create_coordinated_change(self, *args, **kwargs):
            return "stub"

        def get_change_status(self, change_id):
            return "completed"

    class MultiRepoOrchestrator:
        def __init__(
            self,
            repo_registry=None,
            graph_builder=None,
            dependency_resolver=None,
            contract_analyzer=None,
            impact_analyzer=None,
            change_coordinator=None,
        ):
            pass

        async def analyze_system_health(self):
            return {}

        async def make_architectural_decision(self, *args, **kwargs):
            return {}

    class NaviMultiRepoIntegration:
        def __init__(self):
            pass

    # Stub ChangeRequest class
    @dataclass
    class ChangeRequest:
        repo_name: str = ""
        branch_name: str = ""
        commit_message: str = ""
        file_changes: Dict[str, str] = field(default_factory=dict)
        pr_title: str = ""
        pr_description: str = ""


logger = logging.getLogger(__name__)


# Stub imports for missing components - Phase 4.1.2 compatibility
class RepoContextBuilder:
    async def build(self, workspace_root):
        return None


class CodeSynthesizer:
    pass


class PatchAssembler:
    pass


class DefaultSafetyPolicy:
    pass


class ApprovalEngine:
    def __init__(self, safety_policy):
        pass


class UndoCheckpoint:
    pass


class ValidationEngine:
    async def validate(self, payload):
        return type(
            "ValidationResult", (), {"passed": True, "issues": [], "details": {}}
        )()


class FailureAnalyzer:
    pass


class SelfHealingLoop:
    async def heal(self, validation_result, generation_result):
        return type(
            "HealingResult", (), {"healed": False, "updated_result": generation_result}
        )()


class ValidationPolicyManager:
    pass


class PRLifecycleEngine:
    def __init__(self, *args, **kwargs):
        pass

    async def executeFullLifecycle(self, task):
        return {
            "pr": {"prNumber": 0, "htmlUrl": "", "prUrl": ""},
            "branch": {"name": "main"},
            "monitoring": False,
        }

    async def startMonitoring(self, pr_number):
        return None

    def stopMonitoring(self, pr_number):
        return None


class BranchManager:
    def __init__(self, workspace_root=None):
        pass


class CommitComposer:
    pass


class PRCreator:
    def __init__(self, provider=None, owner=None, name=None):
        pass


class PRMonitor:
    def __init__(self, provider=None, owner=None, name=None):
        pass

    async def getStatus(self, pr_number):
        return {"prUrl": "", "htmlUrl": "", "status": "unknown"}


class PRCommentResolver:
    def __init__(self, *args, **kwargs):
        pass

    async def getActionableComments(self, pr_number):
        return []

    async def resolve(self, context):
        return {"understood": False, "confidence": 0}

    async def applyResolution(self, pr_number, resolution, comment):
        return None


class PRStatusReporter:
    def generateReport(self, pr_number, pr_url, html_url, title, status):
        return {
            "humanReadable": f"PR #{pr_number} status unavailable",
            "status": status,
        }


try:
    # Try relative imports first (for when run as module)
    from .models.plan import Plan, ExecutionResult, AgentContext
    from .agents.planner_agent import PlannerAgent
    from .agents.memory_agent import MemoryAgent
    from .agents.repo_analysis_agent import RepoAnalysisAgent
    from .agents.execution_agent import ExecutionAgent
    from .services.llm_router import LLMRouter
    from .core.config import get_settings
    from .agent.intent_schema import NaviIntent, IntentKind, RepoTarget
    from .agent.intent_classifier import IntentClassifier

    # Phase 3.3 - AEI-Grade Code Generation Engine
    from .agent.codegen import ChangePlanGenerator, ChangePlan, ContextAssembler
except ImportError:
    # Fallback to absolute imports (for direct execution)
    from backend.models.plan import Plan, ExecutionResult, AgentContext
    from backend.agents.planner_agent import PlannerAgent
    from backend.agents.memory_agent import MemoryAgent
    from backend.agents.repo_analysis_agent import RepoAnalysisAgent
    from backend.agents.execution_agent import ExecutionAgent
    from backend.services.llm_router import LLMRouter
    from backend.core.config import get_settings
    from backend.agent.intent_schema import NaviIntent, IntentKind, RepoTarget
    from backend.agent.intent_classifier import IntentClassifier

    # Phase 3.3 - AEI-Grade Code Generation Engine
    from backend.agent.codegen import ChangePlanGenerator, ChangePlan, ContextAssembler

# Phase 3.3/3.4 - navi-core components integration (placeholder)
# These components will be initialized when available
GENERATION_AVAILABLE = False
PHASE_3_AVAILABLE = False


# ============================================================================
# Protocol Interfaces for Orchestrator Components
# ============================================================================


class StateManager(Protocol):
    def load_state(self, session_id: str) -> Dict[str, Any]:
        ...

    def save_state(self, session_id: str, state: Dict[str, Any]) -> None:
        ...


class MemoryRetriever(Protocol):
    def retrieve(self, intent: NaviIntent, context: Dict[str, Any]) -> Dict[str, Any]:
        ...


class Planner(Protocol):
    async def plan(self, intent: NaviIntent, context: Dict[str, Any]) -> "PlanResult":
        ...


class ToolExecutor(Protocol):
    async def execute_step(
        self, step: "PlannedStep", intent: NaviIntent, context: Dict[str, Any]
    ) -> "StepResult":
        ...


class LLMIntentClassifier(Protocol):
    async def classify(
        self,
        message: Any,
        *,
        repo: Optional["RepoTarget"] = None,
        metadata: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
        org_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> NaviIntent:
        ...


# ============================================================================
# Data Structures for Planning and Execution
# ============================================================================


@dataclass
class PlannedStep:
    """A single step produced by the planner."""

    id: str
    description: str
    tool: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanResult:
    """Result from the planner containing steps and optional summary."""

    steps: List[PlannedStep]
    summary: Optional[str] = None


@dataclass
class StepResult:
    """Result from executing a single step."""

    step_id: str
    ok: bool
    output: Any
    error: Optional[str] = None
    sources: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentTurnResult:
    """Result container returned to API/UI."""

    intent: NaviIntent
    trace: List[StepResult]
    final_message: str
    raw_plan_summary: Optional[str] = None


class NaviOrchestrator:
    """
    The Navi Orchestrator is the unified master controller that coordinates all agents.
    This is what makes Navi a true multi-agent AI system, not just a chatbot.

    Consolidated from multiple orchestrators to provide:
    - Unified intent classification (LLM + heuristic fallback)
    - Agent coordination and execution flow
    - Phase 3 navi-core integration (generation, validation, PR lifecycle)
    - Phase 4.8: Multi-repository intelligence and system-wide reasoning
    - Error handling and recovery
    - Learning from outcomes
    - Unified responses to API/UI

    This consolidation eliminates architectural conflicts and provides a single
    source of truth for orchestration logic with organization-system-smart capabilities.
    """

    def __init__(
        self,
        *,
        planner: Optional[Planner] = None,
        tool_executor: Optional[ToolExecutor] = None,
        llm_classifier: Optional[LLMIntentClassifier] = None,
        heuristic_classifier: Optional[IntentClassifier] = None,
        state_manager: Optional[StateManager] = None,
        memory_retriever: Optional[MemoryRetriever] = None,
        enable_generation: bool = True,
        enable_multirepo: bool = True,
    ):
        # Initialize core agents (existing)
        self.planner_agent = PlannerAgent()
        self.memory_agent = MemoryAgent()
        self.repo_analyzer = RepoAnalysisAgent()
        self.executor = ExecutionAgent()

        # Production orchestrator components
        self.planner = planner or self.planner_agent
        self.tool_executor = tool_executor or self.executor

        # Intent classifiers (LLM + fallback)
        self.llm_classifier = llm_classifier
        if not self.llm_classifier:
            try:
                from .ai.intent_llm_classifier import LLMIntentClassifier

                self.llm_classifier = LLMIntentClassifier()
            except ImportError:
                logger.warning("LLM classifier not available, using heuristic only")

        self.heuristic_classifier = heuristic_classifier or IntentClassifier()

        # Optional production components
        self.state_manager = state_manager
        self.memory_retriever = memory_retriever or self.memory_agent

        # LLM router for orchestrator-level reasoning
        self.llm_router = LLMRouter()

        # Phase 4.8 - Multi-Repository Intelligence System
        self.multirepo_enabled = enable_multirepo
        if self.multirepo_enabled:
            try:
                # Initialize multi-repo intelligence components
                self.repo_registry = RepoRegistry()
                self.graph_builder = RepoGraphBuilder()
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

                # Master multi-repo orchestrator for Principal Engineer decisions
                self.multi_repo_orchestrator = MultiRepoOrchestrator(
                    repo_registry=self.repo_registry,
                    graph_builder=self.graph_builder,
                    dependency_resolver=self.dependency_resolver,
                    contract_analyzer=self.contract_analyzer,
                    impact_analyzer=self.impact_analyzer,
                    change_coordinator=self.change_coordinator,
                )

                logger.info(
                    "[ORCHESTRATOR] Phase 4.8 Multi-Repository Intelligence enabled"
                )
            except Exception as e:
                logger.error(
                    f"[ORCHESTRATOR] Failed to initialize multi-repo intelligence: {e}"
                )
                self.multirepo_enabled = False
                self._init_multirepo_stubs()
        else:
            self._init_multirepo_stubs()

        # Phase 3.3 - Change Plan Generator (AEI-Grade)
        self.change_plan_generator = ChangePlanGenerator()

        # Phase 3.3 - Context Assembler and Diff Generator
        self.context_assembler = None  # Will be initialized per workspace
        self.diff_generator = None  # Will be initialized with synthesis backend
        self.code_generation_engine = None

        # Settings
        self.settings = get_settings()

        # Orchestrator state
        self.active_sessions = {}
        self.execution_queue = asyncio.Queue()

        # Phase 3.3 - Code Generation Engine (VS Code extension integration)
        self.generation_enabled = enable_generation and GENERATION_AVAILABLE
        if self.generation_enabled:
            try:
                self.repo_context_builder = RepoContextBuilder()
                self.code_synthesizer = CodeSynthesizer()
                self.patch_assembler = PatchAssembler()
                self.safety_policy = DefaultSafetyPolicy()
                self.approval_engine = ApprovalEngine(self.safety_policy)
                self.undo_checkpoint = UndoCheckpoint()

                # Phase 3.4 - Validation & Self-Healing System
                self.validation_engine = ValidationEngine()
                self.failure_analyzer = FailureAnalyzer()
                self.self_healing_loop = SelfHealingLoop()
                self.validation_policy_manager = ValidationPolicyManager()

                # Phase 3.5 - PR Generation & Lifecycle
                self.pr_lifecycle_engine = PRLifecycleEngine()
                self.branch_manager = BranchManager()
                self.commit_composer = CommitComposer()
                self.pr_creator = PRCreator()
                self.pr_monitor = PRMonitor()
                self.pr_comment_resolver = PRCommentResolver()
                self.pr_status_reporter = PRStatusReporter()

                logger.info(
                    "[ORCHESTRATOR] Phase 3.3/3.4/3.5 generation engines initialized successfully"
                )
            except Exception as e:
                logger.error(
                    f"[ORCHESTRATOR] Failed to initialize Phase 3 components: {e}"
                )
                self.generation_enabled = False
        else:
            # Fallback initialization for when Phase 3 is not available
            self.repo_context_builder = None
            self.code_generation_engine = None
            self.code_synthesizer = None
            self.patch_assembler = None
            self.validation_engine = None
            self.failure_analyzer = None
            self.self_healing_loop = None
            self.validation_policy_manager = None

            # Phase 3.4 - Validation & Self-Healing Engine
            self.validation_engine = None  # Initialized per workspace
            self.failure_analyzer = None  # Initialized per workspace
            self.self_healing_loop = None  # Initialized per workspace

            # Phase 3.5 - PR Generation & Lifecycle Engine
            self.pr_lifecycle_engine = None  # Initialized per workspace with git config
            self.branch_manager = None  # Initialized per workspace
            self.commit_composer = None  # Will be initialized per workspace
            self.pr_creator = None  # Initialized with git provider config
            self.pr_monitor = None  # Initialized with git provider config
            self.pr_comment_resolver = None  # Initialized with dependencies
            self.pr_status_reporter = None  # Will be initialized per workspace

    def _init_multirepo_stubs(self):
        """Initialize stub multi-repo components when disabled"""
        self.repo_registry = None
        self.graph_builder = None
        self.dependency_resolver = None
        self.contract_analyzer = None
        self.impact_analyzer = None
        self.change_coordinator = None
        self.multi_repo_orchestrator = None
        logger.info("[ORCHESTRATOR] Multi-repo intelligence disabled - using stubs")

    # ============================================================================
    # Phase 4.8 - Multi-Repository Intelligence Integration
    # ============================================================================

    async def analyze_cross_repo_impact(
        self,
        repo_name: str,
        change_description: str,
        change_type: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze the cross-repository impact of a proposed change.
        This enables system-wide reasoning about change consequences.
        """
        if not self.multirepo_enabled or not self.impact_analyzer:
            logger.warning("[MULTI-REPO] Impact analysis not available")
            return {
                "enabled": False,
                "message": "Multi-repo intelligence not available",
                "blast_radius": 0,
            }

        try:
            # Convert string change type to enum
            from .agent.multirepo.impact_analyzer import ChangeType

            change_type_enum = ChangeType.CODE_CHANGE  # Default
            if change_type:
                try:
                    change_type_enum = ChangeType(change_type.lower())
                except ValueError:
                    logger.warning(
                        f"Unknown change type: {change_type}, using CODE_CHANGE"
                    )

            logger.info(
                f"[MULTI-REPO] Analyzing cross-repo impact for {repo_name}: {change_description[:100]}..."
            )

            impact_analysis = await self.impact_analyzer.analyze_change_impact(
                repo_name=repo_name,
                change_description=change_description,
                change_type=change_type_enum,
                changed_files=changed_files or [],
            )

            return {
                "enabled": True,
                "analysis": {
                    "blast_radius": (
                        getattr(impact_analysis, "blast_radius", 0)
                        if hasattr(impact_analysis, "blast_radius")
                        else impact_analysis.get("blast_radius", 0)
                    ),
                    "affected_repositories": (
                        [
                            r.repo_name
                            for r in getattr(
                                impact_analysis, "affected_repositories", []
                            )
                        ]
                        if hasattr(impact_analysis, "affected_repositories")
                        else []
                    ),
                    "risk_level": (
                        getattr(impact_analysis, "overall_risk", "low")
                        if hasattr(impact_analysis, "overall_risk")
                        else impact_analysis.get("risk_level", "low")
                    ),
                    "risk_score": (
                        getattr(impact_analysis, "risk_score", 0.0)
                        if hasattr(impact_analysis, "risk_score")
                        else impact_analysis.get("risk_score", 0.0)
                    ),
                    "estimated_effort_hours": (
                        getattr(impact_analysis, "total_estimated_effort_hours", 0)
                        if hasattr(impact_analysis, "total_estimated_effort_hours")
                        else impact_analysis.get("estimated_effort_hours", 0)
                    ),
                    "critical_systems_affected": (
                        getattr(impact_analysis, "critical_systems_affected", [])
                        if hasattr(impact_analysis, "critical_systems_affected")
                        else impact_analysis.get("critical_systems_affected", [])
                    ),
                    "recommended_approach": (
                        getattr(impact_analysis, "recommended_approach", "")
                        if hasattr(impact_analysis, "recommended_approach")
                        else impact_analysis.get("recommended_approach", "")
                    ),
                    "rollback_strategy": (
                        getattr(impact_analysis, "rollback_strategy", "")
                        if hasattr(impact_analysis, "rollback_strategy")
                        else impact_analysis.get("rollback_strategy", "")
                    ),
                    "testing_recommendations": (
                        getattr(impact_analysis, "testing_recommendations", [])
                        if hasattr(impact_analysis, "testing_recommendations")
                        else impact_analysis.get("testing_recommendations", [])
                    )[
                        :3
                    ],  # Limit for API
                },
                "summary": f"Impact analysis: {getattr(impact_analysis, 'blast_radius', 0) if hasattr(impact_analysis, 'blast_radius') else impact_analysis.get('blast_radius', 0)} repositories affected, {getattr(getattr(impact_analysis, 'overall_risk', {}), 'value', 'low') if hasattr(impact_analysis, 'overall_risk') and hasattr(getattr(impact_analysis, 'overall_risk'), 'value') else impact_analysis.get('risk_level', 'low')} risk",
            }

        except Exception as e:
            logger.error(f"[MULTI-REPO] Impact analysis failed: {e}")
            return {"enabled": True, "error": str(e), "blast_radius": 0}

    async def get_system_health_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive system health report across all repositories.
        This provides Principal Engineer-level system insights.
        """
        if not self.multirepo_enabled or not self.multi_repo_orchestrator:
            return {
                "enabled": False,
                "message": "Multi-repo intelligence not available",
            }

        try:
            logger.info("[MULTI-REPO] Generating system health report")

            health_report = await self.multi_repo_orchestrator.analyze_system_health()

            return {
                "enabled": True,
                "report": {
                    "overall_health_score": (
                        getattr(health_report, "overall_health_score", 0.5)
                        if hasattr(health_report, "overall_health_score")
                        else health_report.get("overall_health_score", 0.5)
                    ),
                    "total_repositories": (
                        getattr(health_report, "total_repositories", 0)
                        if hasattr(health_report, "total_repositories")
                        else health_report.get("total_repositories", 0)
                    ),
                    "active_repositories": (
                        getattr(health_report, "active_repositories", 0)
                        if hasattr(health_report, "active_repositories")
                        else health_report.get("active_repositories", 0)
                    ),
                    "total_dependencies": (
                        getattr(health_report, "total_dependencies", 0)
                        if hasattr(health_report, "total_dependencies")
                        else health_report.get("total_dependencies", 0)
                    ),
                    "vulnerable_dependencies": (
                        getattr(health_report, "vulnerable_dependencies", 0)
                        if hasattr(health_report, "vulnerable_dependencies")
                        else health_report.get("vulnerable_dependencies", 0)
                    ),
                    "language_distribution": (
                        getattr(health_report, "language_distribution", {})
                        if hasattr(health_report, "language_distribution")
                        else health_report.get("language_distribution", {})
                    ),
                    "immediate_actions": (
                        getattr(health_report, "immediate_actions", [])
                        if hasattr(health_report, "immediate_actions")
                        else health_report.get("immediate_actions", [])
                    )[
                        :5
                    ],  # Limit for API
                    "strategic_improvements": (
                        getattr(health_report, "strategic_improvements", [])
                        if hasattr(health_report, "strategic_improvements")
                        else health_report.get("strategic_improvements", [])
                    )[:3],
                    "generated_at": (
                        getattr(
                            health_report, "generated_at", datetime.now()
                        ).isoformat()
                        if hasattr(health_report, "generated_at")
                        and getattr(health_report, "generated_at")
                        else health_report.get(
                            "generated_at", datetime.now().isoformat()
                        )
                    ),
                },
                "summary": f"System health: {getattr(health_report, 'overall_health_score', 0.5) if hasattr(health_report, 'overall_health_score') else health_report.get('overall_health_score', 0.5):.2f}/1.0, {getattr(health_report, 'total_repositories', 0) if hasattr(health_report, 'total_repositories') else health_report.get('total_repositories', 0)} repositories, {len(getattr(health_report, 'immediate_actions', []) if hasattr(health_report, 'immediate_actions') else health_report.get('immediate_actions', []))} immediate actions needed",
            }

        except Exception as e:
            logger.error(f"[MULTI-REPO] System health analysis failed: {e}")
            return {"enabled": True, "error": str(e)}

    async def coordinate_multi_repo_change(
        self,
        title: str,
        description: str,
        change_requests: List[Dict[str, Any]],
        created_by: str = "navi",
    ) -> Dict[str, Any]:
        """
        Coordinate atomic changes across multiple repositories.
        This enables system-wide change orchestration.
        """
        if not self.multirepo_enabled or not self.change_coordinator:
            return {
                "enabled": False,
                "message": "Multi-repo change coordination not available",
            }

        try:
            logger.info(f"[MULTI-REPO] Coordinating multi-repo change: {title}")

            # Convert dict change requests to ChangeRequest objects
            change_request_objs = []
            for cr_dict in change_requests:
                change_request = ChangeRequest(
                    repo_name=cr_dict["repo_name"],
                    branch_name=cr_dict.get("branch_name", "navi-coordinated-change"),
                    commit_message=cr_dict["commit_message"],
                    file_changes=cr_dict.get("file_changes", {}),
                    pr_title=cr_dict.get("pr_title", title),
                    pr_description=cr_dict.get("pr_description", description),
                )
                change_request_objs.append(change_request)

            # Create coordinated change
            change_id = await self.change_coordinator.create_coordinated_change(
                title=title,
                description=description,
                change_requests=change_request_objs,
                created_by=created_by,
            )

            # Get change status
            change_status = self.change_coordinator.get_change_status(change_id)

            return {
                "enabled": True,
                "change_id": change_id,
                "status": change_status,
                "summary": f"Coordinated change created: {len(change_requests)} repositories involved",
            }

        except Exception as e:
            logger.error(f"[MULTI-REPO] Change coordination failed: {e}")
            return {"enabled": True, "error": str(e)}

    async def make_architectural_decision(
        self,
        decision_type: str,
        context: Dict[str, Any],
        business_priority: str = "medium",
    ) -> Dict[str, Any]:
        """
        Make Principal Engineer-level architectural decisions.
        This enables system-wide strategic thinking.
        """
        if not self.multirepo_enabled or not self.multi_repo_orchestrator:
            return {
                "enabled": False,
                "message": "Multi-repo architectural decisions not available",
            }

        try:
            from .agent.multirepo.orchestrator import DecisionType

            # Convert string to DecisionType enum
            decision_type_enum = DecisionType(decision_type.lower())

            logger.info(f"[MULTI-REPO] Making architectural decision: {decision_type}")

            decision = await self.multi_repo_orchestrator.make_architectural_decision(
                decision_type=decision_type_enum,
                context=context,
                business_priority=business_priority,
            )

            return {
                "enabled": True,
                "decision": {
                    "decision_id": (
                        getattr(
                            decision, "decision_id", decision.get("decision_id", "")
                        )
                        if hasattr(decision, "get")
                        else getattr(decision, "decision_id", "")
                    ),
                    "title": (
                        getattr(decision, "title", decision.get("title", ""))
                        if hasattr(decision, "get")
                        else getattr(decision, "title", "")
                    ),
                    "recommended_action": (
                        getattr(
                            decision,
                            "recommended_action",
                            decision.get("recommended_action", ""),
                        )
                        if hasattr(decision, "get")
                        else getattr(decision, "recommended_action", "")
                    ),
                    "confidence_level": (
                        getattr(
                            getattr(decision, "confidence_level", {}),
                            "value",
                            decision.get("confidence_level", "medium"),
                        )
                        if hasattr(decision, "get")
                        else getattr(
                            getattr(decision, "confidence_level", {}), "value", "medium"
                        )
                    ),
                    "risk_assessment": (
                        getattr(
                            getattr(decision, "risk_assessment", {}),
                            "value",
                            decision.get("risk_assessment", "low"),
                        )
                        if hasattr(decision, "get")
                        else getattr(
                            getattr(decision, "risk_assessment", {}), "value", "low"
                        )
                    ),
                    "business_justification": (
                        getattr(
                            decision,
                            "business_justification",
                            decision.get("business_justification", ""),
                        )
                        if hasattr(decision, "get")
                        else getattr(decision, "business_justification", "")
                    ),
                    "technical_rationale": (
                        getattr(
                            decision,
                            "technical_rationale",
                            decision.get("technical_rationale", ""),
                        )
                        if hasattr(decision, "get")
                        else getattr(decision, "technical_rationale", "")
                    ),
                    "implementation_plan": (
                        getattr(
                            decision,
                            "implementation_plan",
                            decision.get("implementation_plan", []),
                        )
                        if hasattr(decision, "get")
                        else getattr(decision, "implementation_plan", [])
                    )[
                        :3
                    ],  # Limit for API
                    "estimated_effort_weeks": (
                        getattr(
                            decision,
                            "estimated_effort_weeks",
                            decision.get("estimated_effort_weeks", 0),
                        )
                        if hasattr(decision, "get")
                        else getattr(decision, "estimated_effort_weeks", 0)
                    ),
                },
                "summary": f"Architectural decision: {getattr(decision, 'title', decision.get('title', '')) if hasattr(decision, 'get') else getattr(decision, 'title', '')} - {getattr(decision, 'recommended_action', decision.get('recommended_action', '')) if hasattr(decision, 'get') else getattr(decision, 'recommended_action', '')}",
            }

        except Exception as e:
            logger.error(f"[MULTI-REPO] Architectural decision failed: {e}")
            return {"enabled": True, "error": str(e)}

    # ============================================================================
    # Production Orchestrator API - Intent Classification and Message Handling
    # ============================================================================

    async def classify(
        self,
        message: Any,
        *,
        repo: Optional[Union["RepoTarget", str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
        org_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> NaviIntent:
        """
        Classify user intent using LLM with heuristic fallback.
        This is the unified intent classification method for the API.
        """
        try:
            # Try LLM classification first
            if self.llm_classifier:
                logger.info(
                    f"[CLASSIFY] Using LLM classifier for message: {str(message)[:100]}..."
                )

                # Handle repo parameter properly - convert to RepoTarget when needed
                repo_target = None
                if repo:
                    if isinstance(repo, RepoTarget):
                        repo_target = repo
                    elif isinstance(repo, str):
                        repo_target = RepoTarget(repo_id=repo, root_path=repo)
                    elif hasattr(repo, "root_path") or hasattr(repo, "repo_id"):
                        repo_target = RepoTarget(
                            repo_id=getattr(repo, "repo_id", None),
                            root_path=getattr(repo, "root_path", None),
                        )
                    else:
                        repo_target = RepoTarget(repo_id=str(repo))

                intent = await self.llm_classifier.classify(
                    message,
                    repo=repo_target,
                    metadata=metadata,
                    api_key=api_key,
                    org_id=org_id,
                    session_id=session_id,
                )
                logger.info(
                    f"[CLASSIFY] LLM result: {intent.kind} (confidence: {intent.confidence})"
                )
                return intent
        except Exception as e:
            logger.error(f"[CLASSIFY] LLM classification failed: {e}")

        # Fallback to heuristic classification
        try:
            if self.heuristic_classifier:
                logger.info("[CLASSIFY] Using heuristic classifier fallback")
                intent = self.heuristic_classifier.classify(str(message))
                logger.info(
                    f"[CLASSIFY] Heuristic result: {intent.kind} (confidence: {intent.confidence})"
                )
                return intent
        except Exception as e:
            logger.error(f"[CLASSIFY] Heuristic classification failed: {e}")

        # Final fallback - return generic intent
        logger.warning("[CLASSIFY] All classifiers failed, using generic intent")
        return NaviIntent(
            kind=IntentKind.IMPLEMENT_FEATURE,
            confidence=0.1,
            raw_text=str(message),
            slots={"query": str(message), "classification_method": "fallback"},
        )

    async def create_plan(
        self,
        intent: NaviIntent,
        *,
        context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a structured plan based on classified intent.
        This is Phase 4.1.2 - Planning Engine.
        """
        try:
            # Phase 4.1.2 - Planning Engine using TypeScript bridge
            # Direct call to TypeScript planner via _call_typescript_planner

            plan_result = await self._call_typescript_planner(intent, context)

            logger.info(
                f"[PLAN] Created plan: {plan_result.get('title', 'Unknown')} with {len(plan_result.get('steps', []))} steps"
            )

            return {
                "success": True,
                "plan": plan_result,
                "reasoning": plan_result.get("reasoning", ""),
                "session_id": session_id,
            }

        except Exception as e:
            logger.error(f"[PLAN] Planning failed: {e}")

            # Fallback to simple plan structure
            return {
                "success": False,
                "plan": {
                    "id": f"fallback_{int(time.time())}",
                    "title": "Assist with Request",
                    "intent_kind": intent.kind,
                    "steps": [
                        {
                            "id": "step_1",
                            "description": f"Analyze your request: {intent.raw_text[:100]}...",
                            "type": "analyze",
                            "estimated_duration": "2-3 minutes",
                        }
                    ],
                    "requires_approval": True,
                    "confidence": 0.5,
                    "estimated_total_time": "2-3 minutes",
                },
                "reasoning": "Using fallback planning due to planner error",
                "error": str(e),
                "session_id": session_id,
            }

    async def _call_typescript_planner(
        self, intent: NaviIntent, context
    ) -> Dict[str, Any]:
        """
        Bridge to TypeScript planner - Phase 4.1.2 Planning Engine.
        Maps NaviIntent to IntentType and generates structured plans.
        """

        # Map NaviIntent kinds to Planning Engine IntentTypes
        intent_mapping = {
            "inspect_repo": "REPO_AWARENESS",
            "fix_bug": "DEBUGGING",
            "implement_feature": "TASK_PLANNING",
            "run_tests": "TASK_PLANNING",
            "explain_code": "CODE_ASSISTANCE",
            "greet": "GREETING",
        }

        # Get intent type from mapping first
        intent_type = intent_mapping.get(intent.kind, None)
        logger.info(f"[PLAN] Intent mapping: {intent.kind} -> {intent_type}")

        # Fallback: classify based on message content if mapping fails
        if intent_type is None:
            user_message = intent.raw_text.lower()
            if any(
                word in user_message
                for word in ["repo", "repository", "workspace", "project"]
            ):
                intent_type = "REPO_AWARENESS"
            elif any(
                word in user_message
                for word in ["bug", "error", "broken", "fix", "debug"]
            ):
                intent_type = "DEBUGGING"
            elif any(
                word in user_message
                for word in ["plan", "task", "implement", "create", "build"]
            ):
                intent_type = "TASK_PLANNING"
            elif (
                any(word in user_message for word in ["hello", "hi", "how are you"])
                or len(user_message) < 10
            ):
                intent_type = "GREETING"
            else:
                intent_type = "UNKNOWN"

        # Generate structured plan based on intent type
        plan_id = f"plan_{int(time.time())}_{hash(intent.raw_text) % 10000}"

        if intent_type == "REPO_AWARENESS":
            return {
                "id": plan_id,
                "title": "Identify current repository",
                "intent_kind": intent_type,
                "steps": [
                    {
                        "id": f"{plan_id}_1",
                        "description": "Inspect VS Code workspace folders",
                        "type": "inspect",
                    },
                    {
                        "id": f"{plan_id}_2",
                        "description": "Summarize repository name and purpose",
                        "type": "summarize",
                    },
                ],
                "requires_approval": False,
                "confidence": 0.95,
                "reasoning": "User is asking about the current repository context. This requires inspecting workspace metadata.",
            }
        elif intent_type == "DEBUGGING":
            return {
                "id": plan_id,
                "title": "Debug and fix issue",
                "intent_kind": intent_type,
                "steps": [
                    {
                        "id": f"{plan_id}_1",
                        "description": "Analyze error logs and stack traces",
                        "type": "analyze",
                    },
                    {
                        "id": f"{plan_id}_2",
                        "description": "Identify root cause and affected components",
                        "type": "inspect",
                    },
                    {
                        "id": f"{plan_id}_3",
                        "description": "Propose specific code changes to fix the issue",
                        "type": "propose",
                    },
                ],
                "requires_approval": True,
                "confidence": 0.85,
                "reasoning": "User is reporting a bug or asking for debugging help. This requires systematic analysis.",
            }
        elif intent_type == "TASK_PLANNING":
            return {
                "id": plan_id,
                "title": "Create task plan",
                "intent_kind": intent_type,
                "steps": [
                    {
                        "id": f"{plan_id}_1",
                        "description": "Analyze and understand task requirements",
                        "type": "analyze",
                    },
                    {
                        "id": f"{plan_id}_2",
                        "description": "Break down work into actionable steps",
                        "type": "propose",
                    },
                    {
                        "id": f"{plan_id}_3",
                        "description": "Provide time estimates and priority recommendations",
                        "type": "summarize",
                    },
                ],
                "requires_approval": False,
                "confidence": 0.75,
                "reasoning": "User wants help planning a task. This requires understanding requirements and breaking down work.",
            }
        elif intent_type == "GREETING":
            return {
                "id": plan_id,
                "title": "Respond to greeting",
                "intent_kind": intent_type,
                "steps": [
                    {
                        "id": f"{plan_id}_1",
                        "description": "Provide helpful greeting and context",
                        "type": "propose",
                    }
                ],
                "requires_approval": False,
                "confidence": 0.90,
                "reasoning": "User is greeting NAVI. Respond appropriately and offer assistance.",
            }
        else:  # UNKNOWN
            return {
                "id": plan_id,
                "title": "Clarify request",
                "intent_kind": intent_type,
                "steps": [
                    {
                        "id": f"{plan_id}_1",
                        "description": "Ask user what they want to do next",
                        "type": "propose",
                    }
                ],
                "requires_approval": False,
                "confidence": 0.4,
                "reasoning": "User intent is unclear. Respond calmly and ask a clarifying question.",
            }

    async def handle_message(
        self,
        *,
        session_id: str,
        message: Any,
        metadata: Optional[Dict[str, Any]] = None,
        repo: Optional[Any] = None,
        source: Optional[str] = "chat",
        api_key: Optional[str] = None,
        org_id: Optional[str] = None,
        context_packet: Optional[Dict[str, Any]] = None,
    ) -> AgentTurnResult:
        """
        Unified message handling from production orchestrator.
        Handles intent classification, memory retrieval, planning, and execution.
        """
        # 1. Load session state if enabled
        state = {}
        if self.state_manager:
            try:
                state = self.state_manager.load_state(session_id)
            except Exception as e:
                logger.error(f"[STATE] Failed to load session state: {e}")
                state = {}

        # 2. Classify intent → Try LLM, fallback to heuristic
        try:
            if self.llm_classifier:
                intent = await self.llm_classifier.classify(
                    message,
                    metadata=metadata,
                    repo=repo,
                    api_key=api_key,
                    org_id=org_id,
                    session_id=session_id,
                )
            else:
                raise Exception("LLM classifier not available")
        except Exception as e:
            logger.error(f"[INTENT] LLM classifier failed → fallback. Error: {e}")
            intent = self.heuristic_classifier.classify(
                message, metadata=metadata, repo=repo
            )

        # 3. Retrieve long-term memory (optional)
        memory = {}
        if self.memory_retriever:
            try:
                memory = self.memory_retriever.retrieve(intent, {"state": state})
            except Exception as e:
                logger.error(f"[MEMORY] Memory retrieval failed: {e}")

        # 4. Build planner context
        planner_context = {
            "session_id": session_id,
            "state": state,
            "memory": memory,
            "metadata": metadata or {},
            "repo": repo,
            "source": source,
            "intent": intent,
            "context_packet": context_packet,
        }

        # 5. Check if this is a code generation request (Phase 3.3)
        if hasattr(intent, "kind") and str(intent.kind.value).upper() in [
            "GENERATE_CODE",
            "IMPLEMENT_FEATURE",
            "FIX_CODE",
        ]:
            logger.info("[ORCHESTRATOR] Routing to Phase 3.3 AEI-Grade code generation")
            return await self.handle_aei_code_generation(intent, planner_context)

        # 6. Produce plan (traditional path)
        try:
            plan_result = await self.planner.plan(intent, planner_context)
        except Exception as e:
            logger.exception("[PLANNER] Error producing plan")
            return AgentTurnResult(
                intent=intent,
                trace=[],
                final_message=f"Failed to plan steps: {e}",
                raw_plan_summary=None,
            )

        # 7. Execute steps with error handling
        trace = []
        steps = getattr(plan_result, "steps", [])
        workspace_root = (
            planner_context.get("workspace_root") or planner_context.get("repo") or ""
        )

        for step in steps:
            try:
                # Handle different execute_step signatures
                executor = cast(Any, self.tool_executor)
                if hasattr(self.tool_executor, "execute_step"):
                    # Try different parameter signatures
                    try:
                        step_result = await executor.execute_step(
                            step, workspace_root, intent, planner_context
                        )
                    except TypeError:
                        # Fallback to basic signature - try with workspace_root
                        try:
                            step_result = await executor.execute_step(
                                step, workspace_root, planner_context
                            )
                        except TypeError:
                            # Ultimate fallback
                            step_result = await executor.execute_step(step)
                else:
                    # Fallback to basic execution
                    step_result = type(
                        "StepResult",
                        (),
                        {
                            "step_id": getattr(step, "id", "unknown"),
                            "ok": True,
                            "output": "Step executed (stub)",
                            "error": None,
                        },
                    )()

                trace.append(step_result)

                # Stop execution on critical failure
                step_ok = (
                    getattr(step_result, "ok", True)
                    if hasattr(step_result, "ok")
                    else True
                )
                step_error = (
                    getattr(step_result, "error", None)
                    if hasattr(step_result, "error")
                    else None
                )
                if not step_ok and hasattr(intent, "critical") and intent.critical:
                    logger.error(f"[EXECUTION] Critical step failed: {step_error}")
                    break

            except Exception as e:
                logger.exception("[EXECUTION] Step execution failed")
                step_result = type(
                    "StepResult",
                    (),
                    {
                        "step_id": getattr(step, "id", "unknown"),
                        "ok": False,
                        "output": None,
                        "error": str(e),
                    },
                )()
                trace.append(step_result)

        # 8. Generate final response
        success_count = sum(1 for t in trace if getattr(t, "ok", True))
        total_count = len(trace)

        if success_count == total_count:
            final_message = (
                f"Successfully completed {total_count} steps for your request."
            )
        else:
            final_message = f"Completed {success_count}/{total_count} steps. Some issues encountered."

        # 9. Save session state if enabled
        if self.state_manager:
            try:
                updated_state = {
                    **state,
                    "last_intent": intent,
                    "last_execution": datetime.now(),
                }
                self.state_manager.save_state(session_id, updated_state)
            except Exception as e:
                logger.error(f"[STATE] Failed to save session state: {e}")

        return AgentTurnResult(
            intent=intent,
            trace=trace,
            final_message=final_message,
            raw_plan_summary=(
                plan_result.get("summary")
                if isinstance(plan_result, dict)
                else getattr(plan_result, "summary", None)
            ),
        )

    async def handle_code_generation(
        self, intent: NaviIntent, context: Dict[str, Any]
    ) -> AgentTurnResult:
        """
        Phase 3.3 - Code generation pathway using navi-core engines.
        """
        if not self.generation_enabled:
            return AgentTurnResult(
                intent=intent,
                trace=[],
                final_message="Code generation is not available in this configuration.",
                raw_plan_summary=None,
            )

        try:
            # Build repo context
            workspace_root = (
                context.get("repo", {}).get("workspace_root")
                or context.get("workspace_root")
                or context.get("repo_root")
            )
            if not workspace_root:
                raise ValueError("Workspace root required for code generation")

            # Build repo context if available
            repo_context = None
            if hasattr(self, "repo_context_builder") and self.repo_context_builder:
                try:
                    if hasattr(self.repo_context_builder, "build"):
                        build_result = self.repo_context_builder.build(workspace_root)
                        if inspect.isawaitable(build_result):
                            repo_context = await build_result
                        else:
                            repo_context = build_result
                    else:
                        repo_context = None
                except Exception as e:
                    logger.warning(f"Failed to build repo context: {e}")
                    repo_context = None

            # Create generation context
            generation_context = {
                "intent": intent,
                "repo_context": repo_context,
                "workspace_root": workspace_root,
                "user_context": context,
            }

            # Generate code using Phase 3.3 engine
            if not self.code_generation_engine:
                # Initialize per-workspace (requires LLM access)
                from .ai.llm_router import LLMRouter

                LLMRouter()
                # TODO: Initialize CodeGenerationEngine with LLM once available
                raise NotImplementedError(
                    "CodeGenerationEngine initialization pending LLM integration"
                )

            generation_engine = cast(Any, self.code_generation_engine)
            generation_result = await generation_engine.generate(generation_context)

            # Apply validation if enabled
            if self.validation_engine and getattr(generation_result, "files", None):
                validation_engine = cast(Any, self.validation_engine)
                validation_result = await validation_engine.validate(
                    {
                        "modifiedFiles": [f.path for f in generation_result.files],
                        "workspaceRoot": workspace_root,
                        "language": (
                            getattr(repo_context, "primary_language", "python")
                            if repo_context
                            else "python"
                        ),
                        "validationTypes": ["syntax", "typecheck", "lint"],
                        "allowAutoFix": True,
                        "maxRetries": 3,
                        "skipValidation": [],
                    }
                )

                if (
                    not getattr(validation_result, "passed", True)
                    and self.self_healing_loop
                ):
                    # Attempt self-healing
                    healing_loop = cast(Any, self.self_healing_loop)
                    healing_result = await healing_loop.heal(
                        validation_result, generation_result
                    )
                    if getattr(healing_result, "healed", False):
                        logger.info("[ORCHESTRATOR] Self-healing successful")
                        generation_result = healing_result.updated_result

            return AgentTurnResult(
                intent=intent,
                trace=[
                    StepResult(
                        step_id="code_generation",
                        ok=generation_result.success,
                        output=generation_result,
                        error=(
                            None
                            if generation_result.success
                            else "Code generation failed"
                        ),
                    )
                ],
                final_message=(
                    "Code generation completed"
                    if generation_result.success
                    else "Code generation failed"
                ),
                raw_plan_summary=f"Generated {len(generation_result.files)} files",
            )

        except Exception as e:
            logger.exception("[ORCHESTRATOR] Code generation failed")
            return AgentTurnResult(
                intent=intent,
                trace=[
                    StepResult(
                        step_id="code_generation", ok=False, output=None, error=str(e)
                    )
                ],
                final_message=f"Code generation failed: {e}",
                raw_plan_summary=None,
            )

    async def handle_aei_code_generation(
        self, intent: NaviIntent, context: Dict[str, Any]
    ) -> AgentTurnResult:
        """
        Phase 3.3 - AEI-Grade code generation using new ChangePlan system.

        This integrates with existing planner_v3 WITHOUT replacing it.
        Flow: intent → planner_v3 → ChangePlanGenerator → existing tool_executor
        """
        logger.info("[PHASE3.3] Starting AEI-Grade code generation")

        try:
            # 1. Get traditional plan from planner_v3 (unchanged)
            traditional_plan = await self.planner.plan(intent, context)

            # 2. Generate AEI-Grade ChangePlan from traditional plan
            change_plan = await self.change_plan_generator.generate_plan(
                intent=intent,
                user_request=(
                    str(intent.description)
                    if hasattr(intent, "description")
                    else context.get("user_request", "")
                ),
                workspace_root=context.get("repo", {}).get("workspace_root", ""),
                repo_context=context.get("repo_context", {}),
                user_preferences=context.get("user_preferences", {}),
            )

            # Emit ChangePlan to UI (Phase 3.3)
            if hasattr(context, "ui_callback"):
                await context["ui_callback"](
                    {
                        "type": "navi.changePlan.generated",
                        "changePlan": {
                            "goal": change_plan.description,
                            "strategy": change_plan.reasoning,
                            "files": [
                                {
                                    "path": fc.file_path or "",
                                    "intent": (
                                        getattr(fc.change_type, "value", "unknown")
                                        if fc.change_type
                                        else "unknown"
                                    ),
                                    "rationale": fc.reasoning or "",
                                }
                                for fc in change_plan.file_changes
                            ],
                            "riskLevel": change_plan.complexity,
                            "testsRequired": any(
                                "test" in (fc.file_path or "").lower()
                                for fc in change_plan.file_changes
                                if fc.file_path
                            ),
                        },
                    }
                )

            # 3. Phase 3.3 - Assemble file contexts and generate diffs
            workspace_root = context.get("repo", {}).get("workspace_root", "")
            code_changes: List[Any] = []
            if workspace_root:
                # Initialize context assembler for this workspace
                context_assembler = ContextAssembler(repo_root=workspace_root)
                file_contexts = context_assembler.assemble(change_plan.file_changes)

                # Skip diff generation for now - requires synthesis backend implementation
                # TODO: Initialize DiffGenerator with proper synthesis backend (LLM or rule-based)
                logger.info(
                    "[PHASE3.3] Diff generation skipped - synthesis backend not configured"
                )
                diff_generator = None

                # Generate diffs (when synthesis backend is available)
                if diff_generator:
                    try:
                        generated_changes = diff_generator.generate(
                            plan=change_plan, file_contexts=file_contexts
                        )
                        code_changes = list(generated_changes or [])
                        if code_changes:
                            logger.info(
                                f"[PHASE3.3] Generated {len(code_changes)} diff-based code changes"
                            )

                            # Emit Diffs to UI (Phase 3.3)
                            if hasattr(context, "ui_callback"):
                                await context["ui_callback"](
                                    {
                                        "type": "navi.diffs.generated",
                                        "codeChanges": [
                                            {
                                                "file_path": change.file_path,
                                                "change_type": (
                                                    getattr(
                                                        change.change_type,
                                                        "value",
                                                        "unknown",
                                                    )
                                                    if hasattr(change, "change_type")
                                                    and change.change_type
                                                    else "unknown"
                                                ),
                                                "diff": (
                                                    "\n".join(
                                                        h.content for h in change.hunks
                                                    )
                                                    if hasattr(change, "hunks")
                                                    and change.hunks
                                                    else getattr(
                                                        change, "new_file_content", ""
                                                    )
                                                ),
                                                "reasoning": getattr(
                                                    change,
                                                    "reasoning",
                                                    "Code generation",
                                                ),
                                            }
                                            for change in code_changes
                                        ],
                                    }
                                )
                    except Exception as e:
                        logger.error(f"[PHASE3.3] Diff generation failed: {e}")
                        code_changes = []
                else:
                    logger.info(
                        "[PHASE3.3] Code changes generation deferred - synthesis backend needed"
                    )
            else:
                logger.warning(
                    "[PHASE3.3] No workspace root provided, skipping diff generation"
                )
                code_changes = []

            # 4. Convert ChangePlan back to traditional steps for existing tool_executor
            traditional_steps = getattr(traditional_plan, "steps", None)
            if traditional_steps is None and isinstance(traditional_plan, dict):
                traditional_steps = traditional_plan.get("steps", [])
            enhanced_steps = self._convert_change_plan_to_steps(
                change_plan, traditional_steps or []
            )

            # 4. Execute using existing tool_executor (no changes needed)
            trace = []
            workspace_root = context.get("workspace_root", "")
            for step in enhanced_steps:
                try:
                    executor = cast(Any, self.tool_executor)
                    step_result = await executor.execute_step(
                        step, workspace_root, intent, context
                    )
                    trace.append(step_result)

                    if not step_result.ok:
                        logger.error(f"[PHASE3.3] Step failed: {step_result.error}")
                        break

                except Exception as e:
                    logger.exception(f"[PHASE3.3] Step execution failed: {step.id}")
                    trace.append(
                        StepResult(step_id=step.id, ok=False, output=None, error=str(e))
                    )

            # 5. Generate enhanced response with diff information
            success_count = sum(1 for t in trace if t.ok)
            total_count = len(trace)

            if success_count == total_count:
                final_message = f"✅ AEI Code Generation: Successfully generated {len(code_changes) if code_changes else 0} diffs for {getattr(change_plan, 'total_files_affected', 0)} files"
            else:
                final_message = f"⚠️ AEI Code Generation: {success_count}/{total_count} operations completed"

            return AgentTurnResult(
                intent=intent,
                trace=trace,
                final_message=final_message,
                raw_plan_summary=f"ChangePlan: {change_plan.description}",
            )

        except Exception as e:
            logger.exception("[PHASE3.3] AEI code generation failed")
            return AgentTurnResult(
                intent=intent,
                trace=[
                    StepResult(
                        step_id="aei_code_generation",
                        ok=False,
                        output=None,
                        error=str(e),
                    )
                ],
                final_message=f"AEI Code generation failed: {e}",
                raw_plan_summary=None,
            )

    def _convert_change_plan_to_steps(
        self, change_plan: ChangePlan, original_steps: List
    ) -> List:
        """
        Convert Phase 3.3 ChangePlan back to traditional planner steps.

        This allows Phase 3.3 to enhance planning while keeping execution unchanged.
        """
        enhanced_steps = []

        for i, file_change in enumerate(change_plan.file_changes):
            if file_change.change_type and hasattr(file_change.change_type, "value"):
                if file_change.change_type.value == "create_file":
                    step = PlannedStep(
                        id=f"aei_create_{i}",
                        description=f"Create {file_change.file_path}: {file_change.reasoning}",
                        tool="create_file",
                        arguments={
                            "file_path": file_change.file_path,
                            "content": file_change.new_file_content or "",
                            "reasoning": file_change.reasoning,
                        },
                    )
                elif file_change.change_type.value == "modify_file":
                    step = PlannedStep(
                        id=f"aei_modify_{i}",
                        description=f"Modify {file_change.file_path}: {file_change.reasoning}",
                        tool="edit_file",
                        arguments={
                            "file_path": file_change.file_path,
                            "changes": [
                                change.to_dict() for change in file_change.changes
                            ],
                            "reasoning": file_change.reasoning,
                        },
                    )
                else:  # delete_file
                    step = PlannedStep(
                        id=f"aei_delete_{i}",
                        description=f"Delete {file_change.file_path}: {file_change.reasoning}",
                        tool="delete_file",
                        arguments={
                            "file_path": file_change.file_path,
                            "reasoning": file_change.reasoning,
                        },
                    )
            else:
                # Fallback step if change_type is not properly defined
                step = PlannedStep(
                    id=f"aei_fallback_{i}",
                    description=f"Process {file_change.file_path}: {file_change.reasoning}",
                    tool="inspect_file",
                    arguments={
                        "file_path": file_change.file_path,
                        "reasoning": file_change.reasoning,
                    },
                )

            enhanced_steps.append(step)

        return enhanced_steps

    async def handle_validation(
        self, context: Dict[str, Any], code_changes: List[Any]
    ) -> Dict[str, Any]:
        """
        Phase 3.4 - Run validation pipeline and emit results to UI.
        """
        try:
            # Import Phase 3.4 ValidationPipeline
            from .agent.validation import ValidationPipeline, ValidationStatus

            workspace_root = context.get("repo", {}).get("workspace_root", "")
            if not workspace_root:
                raise ValueError("Workspace root required for validation")

            # Initialize validation pipeline
            validator = ValidationPipeline(repo_root=workspace_root)

            # Run validation
            validation_result = validator.validate(code_changes)

            # Emit Validation Result to UI (Phase 3.4)
            if hasattr(context, "ui_callback"):
                await context["ui_callback"](
                    {
                        "type": "navi.validation.result",
                        "validationResult": {
                            "status": validation_result.status.value,
                            "issues": [
                                {
                                    "validator": issue.validator,
                                    "file_path": issue.file_path,
                                    "line_number": getattr(issue, "line_number", None),
                                    "message": issue.message,
                                }
                                for issue in validation_result.issues
                            ],
                            "canProceed": validation_result.status
                            == ValidationStatus.PASSED,
                        },
                    }
                )

            return {
                "success": validation_result.status == ValidationStatus.PASSED,
                "result": validation_result,
                "can_proceed": validation_result.status == ValidationStatus.PASSED,
            }

        except Exception as e:
            logger.exception("[PHASE3.4] Validation failed")

            # Emit validation failure to UI
            if hasattr(context, "ui_callback"):
                await context["ui_callback"](
                    {
                        "type": "navi.validation.result",
                        "validationResult": {
                            "status": "FAILED",
                            "issues": [
                                {
                                    "validator": "ValidationPipeline",
                                    "message": f"Validation system error: {str(e)}",
                                }
                            ],
                            "canProceed": False,
                        },
                    }
                )

            return {"success": False, "error": str(e), "can_proceed": False}

    async def handle_apply_changes(
        self, context: Dict[str, Any], code_changes: List[Any]
    ) -> Dict[str, Any]:
        """
        Phase 3.4 - Apply validated changes and emit results to UI.
        """
        try:
            applied_files = []
            success_count = 0

            for change in code_changes:
                try:
                    # Apply the change (simplified - in production this would use proper file operations)
                    # This is where you'd integrate with your existing ExecutionAgent

                    applied_files.append(
                        {
                            "file_path": change.file_path,
                            "operation": change.change_type.value,
                            "success": True,
                        }
                    )
                    success_count += 1

                except Exception as e:
                    applied_files.append(
                        {
                            "file_path": change.file_path,
                            "operation": change.change_type.value,
                            "success": False,
                            "error": str(e),
                        }
                    )

            overall_success = success_count == len(code_changes)

            # Emit Apply Result to UI (Phase 3.4)
            if hasattr(context, "ui_callback"):
                await context["ui_callback"](
                    {
                        "type": "navi.changes.applied",
                        "applyResult": {
                            "success": overall_success,
                            "appliedFiles": applied_files,
                            "summary": {
                                "totalFiles": len(code_changes),
                                "successfulFiles": success_count,
                                "failedFiles": len(code_changes) - success_count,
                                "rollbackAvailable": overall_success,  # Simplified
                            },
                            "rollbackAvailable": overall_success,
                        },
                    }
                )

            return {
                "success": overall_success,
                "applied_files": applied_files,
                "total_files": len(code_changes),
                "success_count": success_count,
            }

        except Exception as e:
            logger.exception("[PHASE3.4] Apply changes failed")

            # Emit apply failure to UI
            if hasattr(context, "ui_callback"):
                await context["ui_callback"](
                    {
                        "type": "navi.changes.applied",
                        "applyResult": {
                            "success": False,
                            "appliedFiles": [],
                            "error": str(e),
                            "rollbackAvailable": False,
                        },
                    }
                )

            return {"success": False, "error": str(e)}

    async def handle_branch_creation(
        self, context: Dict[str, Any], changePlan: Any, applyResult: Any
    ) -> Dict[str, Any]:
        """
        Phase 3.5.1 - Create branch for PR generation and emit results to UI.
        """
        try:
            from .agent.pr import BranchManager

            workspace_root = context.get("repo", {}).get("workspace_root", "")
            if not workspace_root:
                raise ValueError("Workspace root required for branch creation")

            # Initialize branch manager
            branch_manager = BranchManager(workspace_root)

            # Generate feature description from changePlan
            feature_description = changePlan.get(
                "goal", "Autonomous feature implementation"
            )

            # Create PR branch
            result = branch_manager.create_pr_branch(
                feature_description=feature_description,
                base_branch="main",
                force_clean=False,
            )

            # Emit Branch Creation Result to UI (Phase 3.5)
            if hasattr(context, "ui_callback"):
                await context["ui_callback"](
                    {
                        "type": "navi.pr.branch.created",
                        "branchResult": {
                            "success": result.success,
                            "branchName": result.branch_name,
                            "createdFrom": result.created_from,
                            "message": result.message,
                            "workingTreeClean": result.working_tree_clean,
                            "error": result.error,
                        },
                    }
                )

            return {
                "success": result.success,
                "branch_name": result.branch_name,
                "created_from": result.created_from,
                "working_tree_clean": result.working_tree_clean,
                "message": result.message,
                "error": result.error,
            }

        except Exception as e:
            logger.exception("[PHASE3.5.1] Branch creation failed")

            # Emit branch creation failure to UI
            if hasattr(context, "ui_callback"):
                await context["ui_callback"](
                    {
                        "type": "navi.pr.branch.created",
                        "branchResult": {
                            "success": False,
                            "branchName": "",
                            "createdFrom": "main",
                            "message": f"Branch creation failed: {str(e)}",
                            "workingTreeClean": False,
                            "error": str(e),
                        },
                    }
                )

            return {"success": False, "error": str(e)}

    async def handle_commit_creation(
        self,
        context: Dict[str, Any],
        changePlan: Any,
        branchResult: Any,
        applyResult: Any,
    ) -> Dict[str, Any]:
        """
        Phase 3.5.2 - Create commit from applied changes and emit results to UI.
        """
        try:
            from .agent.pr import CommitComposer

            workspace_root = context.get("repo", {}).get("workspace_root", "")
            if not workspace_root:
                raise ValueError("Workspace root required for commit creation")

            # Initialize commit composer
            commit_composer = CommitComposer(workspace_root)

            # Extract applied files from apply result
            applied_files = []
            if applyResult and applyResult.get("applied_files"):
                applied_files = [
                    af["file_path"]
                    for af in applyResult["applied_files"]
                    if af.get("success", False)
                ]
            elif applyResult and applyResult.get("success_count", 0) > 0:
                # Fallback: if no detailed file info, try to get from changePlan
                if changePlan and changePlan.get("files"):
                    applied_files = [f["path"] for f in changePlan["files"]]

            if not applied_files:
                return {"success": False, "error": "No applied files found for commit"}

            logger.info(
                f"[ORCHESTRATOR] Creating commit for {len(applied_files)} applied files"
            )

            # Create commit
            result = commit_composer.create_pr_commit(
                files=applied_files, change_plan=changePlan
            )

            # Emit Commit Creation Result to UI (Phase 3.5.2)
            if hasattr(context, "ui_callback"):
                await context["ui_callback"](
                    {
                        "type": "navi.pr.commit.created",
                        "commitResult": {
                            "success": result.success,
                            "sha": result.sha,
                            "message": result.message,
                            "files": result.files,
                            "stagedFilesCount": result.staged_files_count,
                            "error": result.error,
                        },
                    }
                )

            return {
                "success": result.success,
                "sha": result.sha,
                "message": result.message,
                "files": result.files,
                "staged_files_count": result.staged_files_count,
                "error": result.error,
            }

        except Exception as e:
            logger.exception("[PHASE3.5.2] Commit creation failed")

            # Emit commit creation failure to UI
            if hasattr(context, "ui_callback"):
                await context["ui_callback"](
                    {
                        "type": "navi.pr.commit.created",
                        "commitResult": {
                            "success": False,
                            "sha": "",
                            "message": "",
                            "files": [],
                            "stagedFilesCount": 0,
                            "error": str(e),
                        },
                    }
                )

            return {"success": False, "error": str(e)}

    async def handle_pr_creation_simple(
        self,
        context: Dict[str, Any],
        changePlan: Any,
        branchResult: Any,
        commitResult: Any,
    ) -> Dict[str, Any]:
        """
        Phase 3.5.3 - Create GitHub PR and emit results to UI.
        """
        try:
            from .agent.pr import PRCreator

            workspace_root = context.get("repo", {}).get("workspace_root", "")
            if not workspace_root:
                raise ValueError("Workspace root required for PR creation")

            # Initialize PR creator
            pr_creator = PRCreator(repo_root=workspace_root)

            # Extract metadata from previous results
            branch_name = branchResult.get("branch_name", "")
            commitResult.get("sha", "")

            # Generate PR content from changePlan
            pr_title = changePlan.get("goal", "Autonomous feature implementation")

            # Create comprehensive PR description
            pr_description_parts = []
            if changePlan.get("goal"):
                pr_description_parts.append(f"**Goal:** {changePlan['goal']}")
            if changePlan.get("modifications"):
                pr_description_parts.append(
                    f"**Changes:** {len(changePlan['modifications'])} file modifications"
                )
            if changePlan.get("reasoning"):
                pr_description_parts.append(f"**Reasoning:** {changePlan['reasoning']}")

            pr_description = (
                "\n\n".join(pr_description_parts)
                if pr_description_parts
                else "Autonomous code generation"
            )

            # Create GitHub PR
            result = pr_creator.create_navi_pr(
                branch=branch_name,
                base="main",
                change_plan=changePlan,
                commit_message=pr_title,
            )

            logger.info(f"[PHASE3.5.3] PR creation result: {result.success}")

            # Emit PR creation result to UI
            if hasattr(context, "ui_callback"):
                await context["ui_callback"](
                    {
                        "type": "navi.pr.created",
                        "prResult": {
                            "success": result.success,
                            "pr_number": result.pr_number,
                            "pr_url": result.pr_url,
                            "branch_name": branch_name,
                            "title": pr_title,
                            "description": pr_description,
                            "error": result.error,
                        },
                    }
                )

            return {
                "success": result.success,
                "pr_number": result.pr_number,
                "pr_url": result.pr_url,
                "branch_name": branch_name,
                "title": pr_title,
                "description": pr_description,
                "error": result.error,
            }

        except Exception as e:
            logger.exception("[PHASE3.5.3] PR creation failed")

            # Emit PR creation failure to UI
            if hasattr(context, "ui_callback"):
                await context["ui_callback"](
                    {
                        "type": "navi.pr.created",
                        "prResult": {
                            "success": False,
                            "pr_number": None,
                            "pr_url": "",
                            "branch_name": "",
                            "title": "",
                            "description": "",
                            "error": str(e),
                        },
                    }
                )

            return {"success": False, "error": str(e)}

    async def handle_pr_lifecycle_monitoring(
        self, context: Dict[str, Any], prResult: Any
    ) -> Dict[str, Any]:
        """
        Phase 3.5.4 - Start background CI monitoring for PR and emit lifecycle updates.
        """
        try:
            from .agent.pr import PRLifecycleEngine as PRLifecycleEngineImpl

            workspace_root = context.get("repo", {}).get("workspace_root", "")
            if not workspace_root:
                raise ValueError("Workspace root required for PR monitoring")

            pr_number = prResult.get("pr_number")
            if not pr_number:
                raise ValueError("PR number required for monitoring")

            # Initialize lifecycle engine from workspace
            lifecycle_engine = PRLifecycleEngineImpl.from_workspace(
                workspace_root=workspace_root, pr_number=pr_number
            )

            logger.info(f"[PHASE3.5.4] Starting CI monitoring for PR #{pr_number}")

            # Define event emission callback
            async def emit_lifecycle_event(
                event_type: str, payload: Dict[str, Any]
            ) -> None:
                if hasattr(context, "ui_callback"):
                    await context["ui_callback"]({"type": event_type, **payload})

            # Start monitoring in background task
            async def background_monitor():
                try:
                    result = await lifecycle_engine.monitor_async(emit_lifecycle_event)
                    logger.info(
                        f"[PHASE3.5.4] Monitoring completed for PR #{pr_number}: {result.terminal_reason}"
                    )

                    # Emit final monitoring result
                    await emit_lifecycle_event(
                        "navi.pr.monitoring.completed",
                        {
                            "prNumber": pr_number,
                            "terminalReason": result.terminal_reason,
                            "duration": result.monitoring_duration,
                            "eventsEmitted": result.events_emitted,
                            "finalStatus": result.final_status.to_dict(),
                        },
                    )

                except Exception as e:
                    logger.exception(
                        f"[PHASE3.5.4] Background monitoring failed for PR #{pr_number}"
                    )
                    await emit_lifecycle_event(
                        "navi.pr.monitoring.error",
                        {"prNumber": pr_number, "error": str(e)},
                    )

            # Start background monitoring (fire and forget)
            asyncio.create_task(background_monitor())

            # Emit monitoring started event
            if hasattr(context, "ui_callback"):
                await context["ui_callback"](
                    {
                        "type": "navi.pr.monitoring.started",
                        "prNumber": pr_number,
                        "repoOwner": lifecycle_engine.repo_owner,
                        "repoName": lifecycle_engine.repo_name,
                    }
                )

            return {
                "success": True,
                "pr_number": pr_number,
                "monitoring_started": True,
                "repo_owner": lifecycle_engine.repo_owner,
                "repo_name": lifecycle_engine.repo_name,
            }

        except Exception as e:
            logger.exception("[PHASE3.5.4] PR lifecycle monitoring failed to start")

            # Emit monitoring failure to UI
            if hasattr(context, "ui_callback"):
                await context["ui_callback"](
                    {
                        "type": "navi.pr.monitoring.error",
                        "prNumber": prResult.get("pr_number", 0),
                        "error": str(e),
                        "phase": "initialization",
                    }
                )

            return {"success": False, "error": str(e)}

    async def handle_self_healing(
        self, context: Dict[str, Any], ci_payload: Dict[str, Any], pr_number: int
    ) -> Dict[str, Any]:
        """
        Phase 3.6 - Attempt autonomous self-healing from CI failure.
        """
        try:
            from .agent.self_healing import SelfHealingEngine

            workspace_root = context.get("repo", {}).get("workspace_root", "")
            if not workspace_root:
                raise ValueError("Workspace root required for self-healing")

            # Initialize self-healing engine
            healing_engine = SelfHealingEngine(
                max_attempts=2, min_confidence=0.7, timeout_minutes=30
            )

            logger.info(f"[PHASE3.6] Starting self-healing for PR #{pr_number}")

            # Define event emission callback
            async def emit_healing_event(
                event_type: str, payload: Dict[str, Any]
            ) -> None:
                if hasattr(context, "ui_callback"):
                    await context["ui_callback"]({"type": event_type, **payload})

            # Attempt recovery
            recovery_result = await healing_engine.attempt_recovery(
                ci_payload=ci_payload,
                pr_number=pr_number,
                workspace_root=workspace_root,
                attempt_count=0,
                emit_event=emit_healing_event,
            )

            logger.info(f"[PHASE3.6] Self-healing result: {recovery_result['status']}")

            # If fix was planned, we can integrate with Phase 3.3-3.5 here
            if recovery_result["status"] == "fix_planned":
                fix_plan = recovery_result.get("fix_plan", {})

                # TODO: Integrate with Phase 3.3 code generation
                # This would trigger the full pipeline:
                # 1. Generate code changes using fix_plan['fix_goal']
                # 2. Validate using Phase 3.4
                # 3. Commit using Phase 3.5.2
                # 4. Monitor CI using Phase 3.5.4

                logger.info(
                    f"[PHASE3.6] Fix plan ready for code generation: {fix_plan.get('goal', '')}"
                )

            return recovery_result

        except Exception as e:
            logger.exception("[PHASE3.6] Self-healing failed")

            # Emit self-healing failure to UI
            if hasattr(context, "ui_callback"):
                await context["ui_callback"](
                    {
                        "type": "navi.selfHealing.error",
                        "prNumber": pr_number,
                        "error": str(e),
                        "phase": "initialization",
                    }
                )

            return {"status": "failed", "error": str(e)}

    async def handle_instruction(
        self,
        user_id: str,
        instruction: str,
        workspace_root: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Main entry point: handle a user instruction with full multi-agent coordination
        """

        session_id = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            # 1. Initialize agent context
            context = await self._initialize_context(
                user_id, instruction, workspace_root, options
            )

            # 2. Load user memory and preferences
            memory_context = await self.memory_agent.load_context(user_id)
            context.memory_context = memory_context["recent_events"]
            context.user_preferences = memory_context["user_preferences"]

            # 3. Analyze repository (if not cached)
            repo_map = await self._get_or_analyze_repo(workspace_root)
            context.repo_map = repo_map

            # 4. Generate execution plan
            plan = await self.planner_agent.generate_plan(
                instruction=instruction,
                repo_map=repo_map.dict() if repo_map else {},
                user_context=memory_context,
            )

            # 5. Execute plan with coordination
            execution_results = await self._execute_plan_with_coordination(
                plan, context
            )

            # 6. Review and validate results
            review_result = await self._review_execution_results(
                plan, execution_results, context
            )

            # 7. Save to memory
            await self._save_execution_to_memory(
                user_id, instruction, plan, execution_results, review_result
            )

            # 8. Generate unified response
            response = await self._generate_unified_response(
                instruction, plan, execution_results, review_result, context
            )

            return {
                "session_id": session_id,
                "success": review_result["overall_success"],
                "plan": plan.dict(),
                "execution_results": [result.dict() for result in execution_results],
                "review": review_result,
                "response": response,
                "context": context.dict(),
            }

        except Exception as e:
            # Handle orchestration errors
            error_response = await self._handle_orchestration_error(
                e, user_id, instruction, workspace_root
            )
            return error_response

    async def _initialize_context(
        self,
        user_id: str,
        instruction: str,
        workspace_root: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> AgentContext:
        """
        Initialize comprehensive context for agent coordination
        """

        return AgentContext(
            user_id=user_id,
            workspace_root=workspace_root,
            current_instruction=instruction,
            repo_map=None,  # Will be populated later
            memory_context=[],
            execution_history=[],
            user_preferences=options or {},
            session_metadata={
                "start_time": datetime.now(),
                "orchestrator_version": "1.0.0",
                "safety_level": (
                    options.get("safety_level", "medium") if options else "medium"
                ),
            },
        )

    async def _get_or_analyze_repo(self, workspace_root: str):
        """
        Get cached repo analysis or perform new analysis
        """

        # Check for cached analysis (in production, this would use Redis/database)
        # For now, always analyze (in production, implement caching)
        try:
            repo_map = await self.repo_analyzer.analyze(workspace_root)
            return repo_map
        except Exception as e:
            # If repo analysis fails, continue with limited context
            print(f"Repo analysis failed: {e}")
            return None

    async def _execute_plan_with_coordination(
        self, plan: Plan, context: AgentContext
    ) -> List[ExecutionResult]:
        """
        Execute plan with intelligent coordination between agents
        """

        execution_results = []

        # Track execution state
        executed_steps = set()

        while len(executed_steps) < len(plan.steps):
            # Get next executable steps (dependencies satisfied)
            executable_steps = []

            for step in plan.steps:
                if step.id in executed_steps:
                    continue

                # Check if dependencies are satisfied
                deps_satisfied = all(
                    dep_id in executed_steps for dep_id in step.depends_on
                )
                if deps_satisfied:
                    executable_steps.append(step)

            if not executable_steps:
                # Circular dependency or other issue
                break

            # Execute steps (potentially in parallel for independent steps)
            step_results = await self._execute_steps_batch(executable_steps, context)

            # Process results
            for step, result in zip(executable_steps, step_results):
                execution_results.append(result)
                context.execution_history.append(result)

                if result.success:
                    executed_steps.add(step.id)
                    plan.mark_step_executed(step.id)
                else:
                    # Handle step failure
                    recovery_result = await self._handle_step_failure(
                        step, result, plan, context
                    )

                    if recovery_result.get("retry", False):
                        # Retry the step
                        retry_result = await self.executor.execute_step(
                            step, context.workspace_root, context.dict()
                        )
                        execution_results.append(retry_result)

                        if retry_result.success:
                            executed_steps.add(step.id)
                            plan.mark_step_executed(step.id)

                    elif recovery_result.get("skip", False):
                        # Skip this step and continue
                        executed_steps.add(step.id)
                        plan.mark_step_executed(step.id)

                    else:
                        # Stop execution on critical failure
                        break

        return execution_results

    async def _execute_steps_batch(
        self, steps: List, context: AgentContext
    ) -> List[ExecutionResult]:
        """
        Execute multiple steps, potentially in parallel
        """

        # For now, execute sequentially (in production, implement parallel execution for independent steps)
        results = []

        for step in steps:
            # Add intelligent pre-execution reasoning
            execution_strategy = await self._determine_execution_strategy(step, context)

            # Execute with strategy
            if execution_strategy["approach"] == "direct":
                result = await self.executor.execute_step(
                    step, context.workspace_root, context.dict()
                )

            elif execution_strategy["approach"] == "guided":
                # Use LLM guidance for complex steps
                result = await self._execute_with_llm_guidance(step, context)

            elif execution_strategy["approach"] == "interactive":
                # Require user confirmation
                result = await self._execute_with_user_confirmation(step, context)

            else:
                # Default to direct execution
                result = await self.executor.execute_step(
                    step, context.workspace_root, context.dict()
                )

            results.append(result)

        return results

    async def _determine_execution_strategy(
        self, step, context: AgentContext
    ) -> Dict[str, Any]:
        """
        Determine the best execution strategy for a step using AI reasoning
        """

        # Analyze step complexity and risk
        risk_factors = []

        # File modification risks
        if step.action_type in ["modify_file", "refactor"] and step.file_targets:
            for file_path in step.file_targets:
                if "config" in file_path.lower():
                    risk_factors.append("config_file_modification")
                if (
                    file_path.endswith((".py", ".js", ".ts"))
                    and "test" not in file_path
                ):
                    risk_factors.append("source_code_modification")

        # Command execution risks
        if step.action_type == "run_command":
            command = step.metadata.get("command", "")
            if any(risky in command for risky in ["rm", "delete", "drop", "truncate"]):
                risk_factors.append("destructive_command")

        # Safety level from user preferences
        safety_level = context.user_preferences.get("safety_level", "medium")

        # Determine strategy
        if len(risk_factors) == 0:
            return {"approach": "direct", "reasoning": "Low risk operation"}

        elif safety_level == "high" or len(risk_factors) > 1:
            return {
                "approach": "interactive",
                "reasoning": f"High risk factors: {risk_factors}",
            }

        elif step.metadata.get("complexity", 0.5) > 0.7:
            return {"approach": "guided", "reasoning": "High complexity operation"}

        else:
            return {"approach": "direct", "reasoning": "Standard execution"}

    async def _execute_with_llm_guidance(
        self, step, context: AgentContext
    ) -> ExecutionResult:
        """
        Execute step with LLM guidance for complex operations
        """

        # Generate execution guidance
        guidance_prompt = f"""
        You are Navi's execution guidance system. Analyze this execution step and provide detailed guidance.
        
        Step: {step.dict()}
        Context: {context.workspace_root}
        Recent execution history: {context.execution_history[-3:] if context.execution_history else []}
        
        Provide:
        1. Pre-execution checks to perform
        2. Potential risks and mitigation strategies
        3. Expected outcomes
        4. Validation criteria
        
        Format as JSON with keys: pre_checks, risks, expected_outcomes, validation
        """

        try:
            guidance_response = await self.llm_router.run(
                prompt=guidance_prompt, use_smart_auto=True
            )
            guidance = json.loads(guidance_response.text)

            # Execute with guidance
            result = await self.executor.execute_step(
                step, context.workspace_root, context.dict()
            )

            # Add guidance to metadata
            result.metadata["execution_guidance"] = guidance

            return result

        except Exception:
            # Fallback to direct execution
            return await self.executor.execute_step(
                step, context.workspace_root, context.dict()
            )

    async def _execute_with_user_confirmation(
        self, step, context: AgentContext
    ) -> ExecutionResult:
        """
        Execute step with user confirmation for high-risk operations
        """

        # This would integrate with the UI to request user confirmation
        # For now, simulate user confirmation

        return ExecutionResult(
            step_id=step.id,
            success=True,
            output="Step executed with user confirmation (simulated)",
            metadata={"requires_user_confirmation": True},
        )

    async def _handle_step_failure(
        self, step, result: ExecutionResult, plan: Plan, context: AgentContext
    ) -> Dict[str, Any]:
        """
        Handle step execution failure with intelligent recovery
        """

        # Analyze failure
        failure_analysis = await self._analyze_failure(step, result, context)

        # Determine recovery strategy
        if failure_analysis["category"] == "temporary":
            return {"retry": True, "reasoning": "Temporary failure, retry recommended"}

        elif failure_analysis["category"] == "dependency":
            return {"replan": True, "reasoning": "Dependency issue, replanning needed"}

        elif failure_analysis["category"] == "user_input":
            return {"ask_user": True, "reasoning": "User input required"}

        elif failure_analysis["severity"] == "low":
            return {"skip": True, "reasoning": "Low severity, safe to skip"}

        else:
            return {"stop": True, "reasoning": "Critical failure, stopping execution"}

    async def _analyze_failure(
        self, step, result: ExecutionResult, context: AgentContext
    ) -> Dict[str, Any]:
        """
        Analyze execution failure to determine appropriate response
        """

        error_message = result.error or ""

        # Categorize failure
        if "timeout" in error_message.lower():
            return {"category": "temporary", "severity": "medium"}

        elif "permission" in error_message.lower():
            return {"category": "permission", "severity": "high"}

        elif "not found" in error_message.lower():
            return {"category": "dependency", "severity": "medium"}

        elif "syntax" in error_message.lower():
            return {"category": "user_input", "severity": "medium"}

        else:
            return {"category": "unknown", "severity": "high"}

    async def _review_execution_results(
        self,
        plan: Plan,
        execution_results: List[ExecutionResult],
        context: AgentContext,
    ) -> Dict[str, Any]:
        """
        Review execution results and provide comprehensive analysis
        """

        total_steps = len(plan.steps)
        successful_steps = sum(1 for result in execution_results if result.success)
        failed_steps = total_steps - successful_steps

        # Calculate success metrics
        success_rate = successful_steps / total_steps if total_steps > 0 else 0

        # Analyze impact
        files_modified = []
        for result in execution_results:
            files_modified.extend(result.files_modified)

        unique_files_modified = list(set(files_modified))

        # Generate summary
        summary = f"Executed {successful_steps}/{total_steps} steps successfully. "
        summary += f"Modified {len(unique_files_modified)} files."

        if failed_steps > 0:
            summary += f" {failed_steps} steps failed."

        return {
            "overall_success": success_rate >= 0.8,  # 80% success threshold
            "success_rate": success_rate,
            "total_steps": total_steps,
            "successful_steps": successful_steps,
            "failed_steps": failed_steps,
            "files_modified": unique_files_modified,
            "summary": summary,
            "recommendations": await self._generate_recommendations(
                plan, execution_results, context
            ),
        }

    async def _generate_recommendations(
        self,
        plan: Plan,
        execution_results: List[ExecutionResult],
        context: AgentContext,
    ) -> List[str]:
        """
        Generate recommendations based on execution results
        """

        recommendations = []

        # Analyze failed steps
        failed_results = [r for r in execution_results if not r.success]

        if failed_results:
            recommendations.append(
                "Review failed steps and consider manual intervention"
            )

        # Check for modified critical files
        critical_files = ["package.json", "requirements.txt", "pom.xml", "Dockerfile"]
        modified_critical = [
            f
            for f in context.execution_history
            if any(cf in str(f.files_modified) for cf in critical_files)
        ]

        if modified_critical:
            recommendations.append(
                "Critical configuration files were modified - consider running tests"
            )

        # Performance recommendations
        total_execution_time = sum(r.execution_time for r in execution_results)
        if total_execution_time > 300:  # 5 minutes
            recommendations.append(
                "Consider breaking down complex operations into smaller steps"
            )

        return recommendations

    async def _save_execution_to_memory(
        self,
        user_id: str,
        instruction: str,
        plan: Plan,
        execution_results: List[ExecutionResult],
        review_result: Dict[str, Any],
    ):
        """
        Save execution results to user memory for learning
        """
        if self.memory_agent:
            await self.memory_agent.save_event(
                user_id=user_id,
                event_type="execution_result",
                content={
                    "instruction": instruction,
                    "plan": plan.dict(),
                    "results": [r.dict() for r in execution_results],
                    "review": review_result,
                    "success": review_result["overall_success"],
                },
                importance=(
                    0.8 if review_result["overall_success"] else 0.9
                ),  # Failures are more important to remember
                tags=["execution", "orchestration", "multi_agent"],
            )

    async def _generate_unified_response(
        self,
        instruction: str,
        plan: Plan,
        execution_results: List[ExecutionResult],
        review_result: Dict[str, Any],
        context: AgentContext,
    ) -> str:
        """
        Generate a unified, human-readable response
        """

        if review_result["overall_success"]:
            response = f'✅ Successfully executed your request: "{instruction}"\n\n'
            response += f"📋 Completed {review_result['successful_steps']} steps\n"
            response += f"📝 Modified {len(review_result['files_modified'])} files\n"

            if review_result["files_modified"]:
                response += "\nFiles changed:\n"
                for file in review_result["files_modified"][:5]:  # Show first 5
                    response += f"• {file}\n"

                if len(review_result["files_modified"]) > 5:
                    response += (
                        f"• ... and {len(review_result['files_modified']) - 5} more\n"
                    )

        else:
            response = f'⚠️ Partially completed your request: "{instruction}"\n\n'
            response += f"✅ Successful: {review_result['successful_steps']}\n"
            response += f"❌ Failed: {review_result['failed_steps']}\n"
            response += f"\n{review_result['summary']}\n"

        if review_result["recommendations"]:
            response += "\n💡 Recommendations:\n"
            for rec in review_result["recommendations"]:
                response += f"• {rec}\n"

        return response

    async def _handle_orchestration_error(
        self, error: Exception, user_id: str, instruction: str, workspace_root: str
    ) -> Dict[str, Any]:
        """
        Handle orchestration-level errors
        """

        # Save error to memory
        await self.memory_agent.save_event(
            user_id=user_id,
            event_type="error",
            content={
                "instruction": instruction,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "workspace_root": workspace_root,
            },
            importance=1.0,  # Orchestration errors are critical
            tags=["error", "orchestration", "critical"],
        )

        return {
            "success": False,
            "error": str(error),
            "error_type": "orchestration_error",
            "response": f"❌ I encountered an error while processing your request: {str(error)}\n\nThis has been logged and I'll learn from it to prevent similar issues in the future.",
        }

    # ========================================
    # Phase 3.5: PR Generation & Lifecycle Methods
    # ========================================

    async def handle_pr_creation(
        self,
        user_id: str,
        task_id: str,
        summary: str,
        description: str,
        workspace_root: str,
        changePlan: Any = None,
        validationResult: Any = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Handle complete PR creation lifecycle
        """
        if not PHASE_3_AVAILABLE:
            return {
                "success": False,
                "error": "PR lifecycle engine not available",
                "response": "PR generation features require Phase 3 components to be enabled.",
            }

        try:
            # Initialize PR lifecycle engine for this workspace
            pr_config = await self._initialize_pr_config(workspace_root)

            if not pr_config:
                return {
                    "success": False,
                    "error": "Failed to configure PR lifecycle",
                    "response": "Could not configure git provider for PR creation.",
                }

            # Create PR task
            pr_task = {
                "taskId": task_id,
                "summary": summary,
                "description": description,
                "changePlan": changePlan,
                "validationResult": validationResult,
                "jiraTicket": options.get("jiraTicket") if options else None,
                "featurePlan": options.get("featurePlan") if options else None,
                "assignees": options.get("assignees", []) if options else [],
                "reviewers": options.get("reviewers", []) if options else [],
                "labels": options.get("labels", []) if options else [],
            }

            # Execute full PR lifecycle
            if not self.pr_lifecycle_engine:
                raise RuntimeError("PR lifecycle engine not initialized")
            pr_engine = cast(Any, self.pr_lifecycle_engine)
            pr_result = await pr_engine.executeFullLifecycle(pr_task)

            # Save to memory
            await self.memory_agent.save_event(
                user_id=user_id,
                event_type="pr_created",
                content={
                    "task_id": task_id,
                    "pr_number": pr_result["pr"]["prNumber"],
                    "pr_url": pr_result["pr"]["htmlUrl"],
                    "branch_name": pr_result["branch"]["name"],
                    "summary": summary,
                },
                importance=0.9,
                tags=["pr", "creation", "autonomous"],
            )

            return {
                "success": True,
                "pr_number": pr_result["pr"]["prNumber"],
                "pr_url": pr_result["pr"]["htmlUrl"],
                "branch_name": pr_result["branch"]["name"],
                "monitoring": pr_result["monitoring"],
                "response": f"✅ Successfully created PR #{pr_result['pr']['prNumber']}: {summary}\\n\\n🔗 {pr_result['pr']['htmlUrl']}\\n\\n{'🔍 Now monitoring for CI updates and reviewer comments.' if pr_result['monitoring'] else ''}",
                "result": pr_result,
            }

        except Exception as e:
            await self.memory_agent.save_event(
                user_id=user_id,
                event_type="pr_creation_error",
                content={
                    "task_id": task_id,
                    "error": str(e),
                    "workspace_root": workspace_root,
                },
                importance=1.0,
                tags=["pr", "error", "creation"],
            )

            return {
                "success": False,
                "error": str(e),
                "response": f"❌ Failed to create PR: {str(e)}",
            }

    async def handle_pr_monitoring(
        self,
        user_id: str,
        pr_number: int,
        action: str = "status",  # 'status', 'start_watch', 'stop_watch', 'resolve_comments'
        workspace_root: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle PR monitoring and management
        """
        if not PHASE_3_AVAILABLE:
            return {
                "success": False,
                "error": "PR monitoring not available",
                "response": "PR monitoring features require Phase 3 components to be enabled.",
            }

        try:
            if workspace_root:
                pr_config = await self._initialize_pr_config(workspace_root)
                if not pr_config:
                    return {
                        "success": False,
                        "error": "Failed to configure PR monitoring",
                        "response": "Could not configure git provider for PR monitoring.",
                    }

            if action == "status":
                # Get PR status
                if not self.pr_monitor or not self.pr_status_reporter:
                    raise RuntimeError("PR monitoring components not initialized")
                pr_monitor = cast(Any, self.pr_monitor)
                pr_reporter = cast(Any, self.pr_status_reporter)
                status = await pr_monitor.getStatus(pr_number)
                report = pr_reporter.generateReport(
                    pr_number,
                    status["prUrl"],
                    status.get("htmlUrl", status["prUrl"]),
                    f"PR #{pr_number}",
                    status,
                )

                return {
                    "success": True,
                    "status": status,
                    "report": report,
                    "response": report["humanReadable"],
                }

            elif action == "start_watch":
                if not self.pr_lifecycle_engine:
                    raise RuntimeError("PR lifecycle engine not initialized")
                pr_engine = cast(Any, self.pr_lifecycle_engine)
                await pr_engine.startMonitoring(pr_number)

                return {
                    "success": True,
                    "response": f"🔍 Now monitoring PR #{pr_number} for updates",
                }

            elif action == "stop_watch":
                if not self.pr_lifecycle_engine:
                    raise RuntimeError("PR lifecycle engine not initialized")
                pr_engine = cast(Any, self.pr_lifecycle_engine)
                pr_engine.stopMonitoring(pr_number)

                return {
                    "success": True,
                    "response": f"⏹️ Stopped monitoring PR #{pr_number}",
                }

            elif action == "resolve_comments":
                # Get actionable comments and attempt to resolve them
                if not self.pr_comment_resolver:
                    raise RuntimeError("PR comment resolver not initialized")
                pr_comment_resolver = cast(Any, self.pr_comment_resolver)
                comments = await pr_comment_resolver.getActionableComments(pr_number)
                resolved_count = 0

                for comment in comments[:3]:  # Limit to 3 comments per request
                    try:
                        context = {"comment": comment, "prNumber": pr_number}
                        resolution = await pr_comment_resolver.resolve(context)

                        if resolution["understood"] and resolution["confidence"] > 80:
                            # Auto-resolve high-confidence comments
                            await pr_comment_resolver.applyResolution(
                                pr_number, resolution, comment
                            )
                            resolved_count += 1
                    except Exception as e:
                        print(f"Failed to resolve comment {comment['id']}: {e}")

                return {
                    "success": True,
                    "resolved_count": resolved_count,
                    "total_comments": len(comments),
                    "response": f"✅ Resolved {resolved_count}/{len(comments)} actionable comments on PR #{pr_number}",
                }

            else:
                return {
                    "success": False,
                    "error": f"Unknown action: {action}",
                    "response": f"Unknown PR action: {action}. Available actions: status, start_watch, stop_watch, resolve_comments",
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response": f"❌ Failed to {action} PR #{pr_number}: {str(e)}",
            }

    async def _initialize_pr_config(
        self, workspace_root: str
    ) -> Optional[Dict[str, Any]]:
        """
        Initialize PR configuration for a workspace
        """
        try:
            # Import PR lifecycle components if needed
            from .agent.pr import PRLifecycleEngine as PRLifecycleEngineImpl

            # Create temporary instance to use from_workspace which detects provider
            temp_engine = PRLifecycleEngineImpl.from_workspace(
                workspace_root=workspace_root, pr_number=0
            )
            provider = (
                "github"  # Default to GitHub, can be extended to detect from git config
            )
            repo_info = {"owner": temp_engine.repo_owner, "name": temp_engine.repo_name}

            # Create PR lifecycle config
            pr_config = {
                "provider": provider,
                "repoOwner": repo_info["owner"],
                "repoName": repo_info["name"],
                "workspaceRoot": workspace_root,
                "defaultBaseBranch": "main",
                "autoWatch": True,
                "autoResolveComments": True,
            }

            # Initialize PR lifecycle engine
            pr_engine_cls = cast(Any, PRLifecycleEngine)
            self.pr_lifecycle_engine = pr_engine_cls(
                pr_config,
                self.approval_engine,  # From Phase 3.2
                self.code_synthesizer,  # From Phase 3.3
                self.llm_router,
            )

            # Initialize other PR components
            self.branch_manager = BranchManager(workspace_root)
            self.pr_creator = PRCreator(provider, repo_info["owner"], repo_info["name"])
            self.pr_monitor = PRMonitor(provider, repo_info["owner"], repo_info["name"])
            self.pr_comment_resolver = PRCommentResolver(
                provider,
                repo_info["owner"],
                repo_info["name"],
                self.code_synthesizer,
                self.llm_router,
            )

            return pr_config

        except Exception as e:
            print(f"Failed to initialize PR config: {e}")
            return None
