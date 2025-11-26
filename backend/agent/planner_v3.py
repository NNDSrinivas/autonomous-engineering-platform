"""
NAVI Planner v3
===============

The production-grade planner for NAVI autonomous agent.

Responsibilities:
- Accept NaviIntent and context from Orchestrator
- Generate optimized execution plan using LLM reasoning
- Create concrete PlannedStep objects for ToolExecutor
- Handle complex multi-step workflows with dependencies

Key improvements over v2:
- LLM-powered step generation for complex tasks
- Better dependency tracking between steps
- Adaptive planning based on execution context
- Integration with tool executor capabilities
"""

import logging
from typing import Any, Dict, List, Optional

from .orchestrator import PlanResult, PlannedStep
from .intent_schema import NaviIntent, IntentFamily, IntentKind

logger = logging.getLogger(__name__)


class PlannerV3:
    """
    Production-grade planner for NAVI autonomous engineering platform.
    """

    def __init__(self, llm_router: Optional[Any] = None):
        self.llm_router = llm_router
        if not self.llm_router:
            try:
                from ..ai.llm_router import LLMRouter
                self.llm_router = LLMRouter()
            except ImportError:
                logger.warning("LLM router not available for planner")

    async def plan(self, intent: NaviIntent, context: Dict[str, Any]) -> PlanResult:
        """
        Generate execution plan for the given intent.
        """
        try:
            # Route to appropriate planning strategy
            if intent.family == IntentFamily.ENGINEERING:
                return await self._plan_code_intent(intent, context)
            elif intent.family == IntentFamily.PROJECT_MANAGEMENT:
                return await self._plan_project_intent(intent, context)
            elif intent.family == IntentFamily.AUTONOMOUS_ORCHESTRATION:
                return await self._plan_autonomous_intent(intent, context)
            else:
                return await self._plan_default_intent(intent, context)
        except Exception as e:
            logger.exception(f"Planning failed for intent {intent.family}/{intent.kind}")
            return PlanResult(
                steps=[
                    PlannedStep(
                        id="error_step",
                        description=f"Planning failed: {e}",
                        tool="error",
                        arguments={"error": str(e)}
                    )
                ],
                summary=f"Planning failed: {e}"
            )

    async def _plan_code_intent(self, intent: NaviIntent, context: Dict[str, Any]) -> PlanResult:
        """Plan code-related intents."""
        steps = []
        
        if intent.kind == IntentKind.ANALYZE:
            steps.extend([
                PlannedStep(
                    id="analyze_codebase",
                    description="Analyze codebase structure and dependencies",
                    tool="code.analyze",
                    arguments={"repo": context.get("repo")}
                ),
                PlannedStep(
                    id="generate_insights",
                    description="Generate analysis insights",
                    tool="code.insights",
                    arguments={"analysis_results": "{{analyze_codebase.output}}"}
                )
            ])
        elif intent.kind == IntentKind.IMPLEMENT:
            steps.extend([
                PlannedStep(
                    id="plan_implementation",
                    description="Plan implementation approach",
                    tool="code.plan",
                    arguments={"intent": intent.dict(), "context": context}
                ),
                PlannedStep(
                    id="implement_changes",
                    description="Implement planned changes",
                    tool="code.implement",
                    arguments={"plan": "{{plan_implementation.output}}"}
                ),
                PlannedStep(
                    id="validate_implementation",
                    description="Validate implementation",
                    tool="code.validate",
                    arguments={"changes": "{{implement_changes.output}}"}
                )
            ])
        elif intent.kind == IntentKind.FIX:
            steps.extend([
                PlannedStep(
                    id="diagnose_issue",
                    description="Diagnose the issue",
                    tool="code.diagnose",
                    arguments={"repo": context.get("repo"), "error_context": context.get("metadata", {})}
                ),
                PlannedStep(
                    id="fix_issue",
                    description="Apply fix",
                    tool="code.fix",
                    arguments={"diagnosis": "{{diagnose_issue.output}}"}
                ),
                PlannedStep(
                    id="test_fix",
                    description="Test the fix",
                    tool="code.test",
                    arguments={"changes": "{{fix_issue.output}}"}
                )
            ])
        else:
            steps.append(
                PlannedStep(
                    id="generic_code_action",
                    description=f"Execute {intent.kind.value} code action",
                    tool="code.generic",
                    arguments={"intent": intent.dict(), "context": context}
                )
            )

        return PlanResult(
            steps=steps,
            summary=f"Code {intent.kind.value} plan with {len(steps)} steps"
        )

    async def _plan_project_intent(self, intent: NaviIntent, context: Dict[str, Any]) -> PlanResult:
        """Plan project-related intents."""
        steps = []
        
        if intent.kind == IntentKind.CREATE:
            steps.extend([
                PlannedStep(
                    id="setup_project_structure",
                    description="Set up project structure",
                    tool="project.setup",
                    arguments={"project_type": context.get("project_type", "generic")}
                ),
                PlannedStep(
                    id="initialize_git",
                    description="Initialize git repository",
                    tool="git.init",
                    arguments={}
                ),
                PlannedStep(
                    id="create_initial_files",
                    description="Create initial project files",
                    tool="project.scaffold",
                    arguments={"template": context.get("template")}
                )
            ])
        elif intent.kind == IntentKind.DEPLOY:
            steps.extend([
                PlannedStep(
                    id="prepare_deployment",
                    description="Prepare deployment configuration",
                    tool="deploy.prepare",
                    arguments={"target": context.get("deploy_target", "production")}
                ),
                PlannedStep(
                    id="run_tests",
                    description="Run pre-deployment tests",
                    tool="test.run",
                    arguments={"scope": "deployment"}
                ),
                PlannedStep(
                    id="execute_deployment",
                    description="Execute deployment",
                    tool="deploy.execute",
                    arguments={"config": "{{prepare_deployment.output}}"}
                )
            ])
        else:
            steps.append(
                PlannedStep(
                    id="generic_project_action",
                    description=f"Execute {intent.kind.value} project action",
                    tool="project.generic",
                    arguments={"intent": intent.dict(), "context": context}
                )
            )

        return PlanResult(
            steps=steps,
            summary=f"Project {intent.kind.value} plan with {len(steps)} steps"
        )

    async def _plan_repository_intent(self, intent: NaviIntent, context: Dict[str, Any]) -> PlanResult:
        """Plan repository-related intents."""
        steps = []
        
        if intent.kind == IntentKind.SYNC:
            steps.extend([
                PlannedStep(
                    id="fetch_remote_changes",
                    description="Fetch remote changes",
                    tool="git.fetch",
                    arguments={"remote": "origin"}
                ),
                PlannedStep(
                    id="merge_changes",
                    description="Merge remote changes",
                    tool="git.merge",
                    arguments={"branch": context.get("branch", "main")}
                )
            ])
        elif intent.kind == IntentKind.ANALYZE:
            steps.extend([
                PlannedStep(
                    id="analyze_repo_structure",
                    description="Analyze repository structure",
                    tool="repo.analyze",
                    arguments={"path": context.get("repo")}
                ),
                PlannedStep(
                    id="generate_repo_insights",
                    description="Generate repository insights",
                    tool="repo.insights",
                    arguments={"analysis": "{{analyze_repo_structure.output}}"}
                )
            ])
        else:
            steps.append(
                PlannedStep(
                    id="generic_repo_action",
                    description=f"Execute {intent.kind.value} repository action",
                    tool="repo.generic",
                    arguments={"intent": intent.dict(), "context": context}
                )
            )

        return PlanResult(
            steps=steps,
            summary=f"Repository {intent.kind.value} plan with {len(steps)} steps"
        )

    async def _plan_knowledge_intent(self, intent: NaviIntent, context: Dict[str, Any]) -> PlanResult:
        """Plan knowledge-related intents."""
        steps = []
        
        if intent.kind == IntentKind.SEARCH:
            steps.extend([
                PlannedStep(
                    id="semantic_search",
                    description="Perform semantic search",
                    tool="search.semantic",
                    arguments={"query": context.get("search_query")}
                ),
                PlannedStep(
                    id="rank_results",
                    description="Rank search results",
                    tool="search.rank",
                    arguments={"results": "{{semantic_search.output}}"}
                )
            ])
        elif intent.kind == IntentKind.EXPLAIN:
            steps.extend([
                PlannedStep(
                    id="gather_context",
                    description="Gather relevant context",
                    tool="knowledge.gather",
                    arguments={"topic": context.get("topic")}
                ),
                PlannedStep(
                    id="generate_explanation",
                    description="Generate explanation",
                    tool="knowledge.explain",
                    arguments={"context": "{{gather_context.output}}"}
                )
            ])
        else:
            steps.append(
                PlannedStep(
                    id="generic_knowledge_action",
                    description=f"Execute {intent.kind.value} knowledge action",
                    tool="knowledge.generic",
                    arguments={"intent": intent.dict(), "context": context}
                )
            )

        return PlanResult(
            steps=steps,
            summary=f"Knowledge {intent.kind.value} plan with {len(steps)} steps"
        )

    async def _plan_system_intent(self, intent: NaviIntent, context: Dict[str, Any]) -> PlanResult:
        """Plan system-related intents."""
        steps = []
        
        if intent.kind == IntentKind.CONFIGURE:
            steps.extend([
                PlannedStep(
                    id="validate_config",
                    description="Validate configuration",
                    tool="system.validate",
                    arguments={"config": context.get("config")}
                ),
                PlannedStep(
                    id="apply_config",
                    description="Apply configuration",
                    tool="system.configure",
                    arguments={"validated_config": "{{validate_config.output}}"}
                )
            ])
        else:
            steps.append(
                PlannedStep(
                    id="generic_system_action",
                    description=f"Execute {intent.kind.value} system action",
                    tool="system.generic",
                    arguments={"intent": intent.dict(), "context": context}
                )
            )

        return PlanResult(
            steps=steps,
            summary=f"System {intent.kind.value} plan with {len(steps)} steps"
        )

    async def _plan_default_intent(self, intent: NaviIntent, context: Dict[str, Any]) -> PlanResult:
        """Fallback planning for unhandled intent families."""
        steps = [
            PlannedStep(
                id="generic_action",
                description=f"Execute {intent.family.value} {intent.kind.value} action",
                tool="generic",
                arguments={"intent": intent.dict(), "context": context}
            )
        ]

        return PlanResult(
            steps=steps,
            summary=f"Generic {intent.family.value} {intent.kind.value} plan"
        )


class SimplePlanner:
    """Minimal planner for FastAPI integration."""
    
    async def plan(self, intent: NaviIntent, context: Dict[str, Any]) -> PlanResult:
        """Create a simple single-step plan."""
        step = PlannedStep(
            id="simple_step",
            description=f"Execute {intent.family.value} {intent.kind.value}",
            tool="simple",
            arguments={"intent": intent.dict(), "context": context}
        )
        
        return PlanResult(
            steps=[step],
            summary=f"Simple plan for {intent.family.value} {intent.kind.value}"
        )