from typing import Dict, Any, List, Optional, Protocol
import asyncio
import json
import logging
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    # Try relative imports first (for when run as module)
    from .models.plan import Plan, ExecutionResult, AgentContext
    from .agents.planner_agent import PlannerAgent
    from .agents.memory_agent import MemoryAgent
    from .agents.repo_analysis_agent import RepoAnalysisAgent
    from .agents.execution_agent import ExecutionAgent
    from .services.llm_router import LLMRouter
    from .core.config import get_settings
    from .agent.intent_schema import NaviIntent
    from .agent.intent_classifier import IntentClassifier
    # Phase 3.3 - AEI-Grade Code Generation Engine
    from .agent.codegen import ChangePlanGenerator, ChangePlan, ContextAssembler, DiffGenerator
except ImportError:
    # Fallback to absolute imports (for direct execution)
    from backend.models.plan import Plan, ExecutionResult, AgentContext
    from backend.agents.planner_agent import PlannerAgent
    from backend.agents.memory_agent import MemoryAgent
    from backend.agents.repo_analysis_agent import RepoAnalysisAgent
    from backend.agents.execution_agent import ExecutionAgent
    from backend.services.llm_router import LLMRouter
    from backend.core.config import get_settings
    from backend.agent.intent_schema import NaviIntent
    from backend.agent.intent_classifier import IntentClassifier
    # Phase 3.3 - AEI-Grade Code Generation Engine
    from backend.agent.codegen import ChangePlanGenerator, ChangePlan, ContextAssembler, DiffGenerator

# Phase 3.3/3.4 - navi-core components integration (placeholder)
# These components will be initialized when available
GENERATION_AVAILABLE = False
PHASE_3_AVAILABLE = False


# ============================================================================
# Protocol Interfaces for Orchestrator Components
# ============================================================================

class StateManager(Protocol):
    def load_state(self, session_id: str) -> Dict[str, Any]: ...
    def save_state(self, session_id: str, state: Dict[str, Any]) -> None: ...

class MemoryRetriever(Protocol):
    def retrieve(self, intent: NaviIntent, context: Dict[str, Any]) -> Dict[str, Any]: ...

class Planner(Protocol):
    async def plan(self, intent: NaviIntent, context: Dict[str, Any]) -> "PlanResult": ...

class ToolExecutor(Protocol):
    async def execute_step(self, step: "PlannedStep", intent: NaviIntent, context: Dict[str, Any]) -> "StepResult": ...

class LLMIntentClassifier(Protocol):
    async def classify(
        self,
        message: Any,
        *,
        repo: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
        org_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> NaviIntent: ...


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
    - Error handling and recovery
    - Learning from outcomes
    - Unified responses to API/UI
    
    This consolidation eliminates architectural conflicts and provides a single
    source of truth for orchestration logic.
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
        
        # Phase 3.3 - Change Plan Generator (AEI-Grade)
        self.change_plan_generator = ChangePlanGenerator()
        
        # Phase 3.3 - Context Assembler and Diff Generator
        self.context_assembler = None  # Will be initialized per workspace
        self.diff_generator = None     # Will be initialized with synthesis backend
        
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
                
                logger.info("[ORCHESTRATOR] Phase 3.3/3.4/3.5 generation engines initialized successfully")
            except Exception as e:
                logger.error(f"[ORCHESTRATOR] Failed to initialize Phase 3 components: {e}")
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

    # ============================================================================
    # Production Orchestrator API - Unified Message Handling
    # ============================================================================

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
        if (hasattr(intent, 'kind') and 
            str(intent.kind.value).upper() in ['GENERATE_CODE', 'IMPLEMENT_FEATURE', 'FIX_CODE']):
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

        # 7. Execute steps
        trace = []
        for step in plan_result.steps:
            try:
                step_result = await self.tool_executor.execute_step(
                    step, intent, planner_context
                )
                trace.append(step_result)
                
                # Stop execution on critical failure
                if not step_result.ok and hasattr(intent, 'critical') and intent.critical:
                    logger.error(f"[EXECUTION] Critical step failed: {step_result.error}")
                    break
                    
            except Exception as e:
                logger.exception(f"[EXECUTION] Step execution failed: {step.id}")
                trace.append(StepResult(
                    step_id=step.id,
                    ok=False,
                    output=None,
                    error=str(e)
                ))

        # 8. Generate final response
        success_count = sum(1 for t in trace if t.ok)
        total_count = len(trace)
        
        if success_count == total_count:
            final_message = f"Successfully completed {total_count} steps for your request."
        else:
            final_message = f"Completed {success_count}/{total_count} steps. Some issues encountered."

        # 9. Save session state if enabled
        if self.state_manager:
            try:
                updated_state = {**state, "last_intent": intent, "last_execution": datetime.now()}
                self.state_manager.save_state(session_id, updated_state)
            except Exception as e:
                logger.error(f"[STATE] Failed to save session state: {e}")

        return AgentTurnResult(
            intent=intent,
            trace=trace,
            final_message=final_message,
            raw_plan_summary=plan_result.summary,
        )

    async def handle_code_generation(self, intent: NaviIntent, context: Dict[str, Any]) -> AgentTurnResult:
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
            workspace_root = context.get('repo', {}).get('workspace_root')
            if not workspace_root:
                raise ValueError("Workspace root required for code generation")
            
            repo_context = await self.repo_context_builder.build(workspace_root)
            
            # Create generation context
            generation_context = {
                'intent': intent,
                'repo_context': repo_context,
                'workspace_root': workspace_root,
                'user_context': context
            }
            
            # Generate code using Phase 3.3 engine
            if not self.code_generation_engine:
                # Initialize per-workspace (requires LLM access)
                from .ai.llm_router import LLMRouter
                llm = LLMRouter()
                # TODO: Initialize CodeGenerationEngine with LLM once available
                raise NotImplementedError("CodeGenerationEngine initialization pending LLM integration")
            
            generation_result = await self.code_generation_engine.generate(generation_context)
            
            # Apply validation if enabled
            if self.validation_engine and generation_result.files:
                validation_result = await self.validation_engine.validate({
                    'modifiedFiles': [f.path for f in generation_result.files],
                    'workspaceRoot': workspace_root,
                    'language': repo_context.primary_language,
                    'validationTypes': ['syntax', 'typecheck', 'lint'],
                    'allowAutoFix': True,
                    'maxRetries': 3,
                    'skipValidation': []
                })
                
                if not validation_result.passed and self.self_healing_loop:
                    # Attempt self-healing
                    healing_result = await self.self_healing_loop.heal(
                        validation_result,
                        generation_result
                    )
                    if healing_result.healed:
                        logger.info("[ORCHESTRATOR] Self-healing successful")
                        generation_result = healing_result.updated_result
            
            return AgentTurnResult(
                intent=intent,
                trace=[StepResult(
                    step_id="code_generation",
                    ok=generation_result.success,
                    output=generation_result,
                    error=None if generation_result.success else "Code generation failed"
                )],
                final_message="Code generation completed" if generation_result.success else "Code generation failed",
                raw_plan_summary=f"Generated {len(generation_result.files)} files",
            )
            
        except Exception as e:
            logger.exception("[ORCHESTRATOR] Code generation failed")
            return AgentTurnResult(
                intent=intent,
                trace=[StepResult(
                    step_id="code_generation",
                    ok=False,
                    output=None,
                    error=str(e)
                )],
                final_message=f"Code generation failed: {e}",
                raw_plan_summary=None,
            )
        
    async def handle_aei_code_generation(self, intent: NaviIntent, context: Dict[str, Any]) -> AgentTurnResult:
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
                user_request=str(intent.description) if hasattr(intent, 'description') else context.get('user_request', ''),
                workspace_root=context.get('repo', {}).get('workspace_root', ''),
                repo_context=context.get('repo_context', {}),
                user_preferences=context.get('user_preferences', {})
            )
            
            # Emit ChangePlan to UI (Phase 3.3)
            if hasattr(context, 'ui_callback'):
                await context['ui_callback']({
                    'type': 'navi.changePlan.generated',
                    'changePlan': {
                        'goal': change_plan.description,
                        'strategy': change_plan.reasoning,
                        'files': [{
                            'path': fc.file_path,
                            'intent': fc.change_type.value,
                            'rationale': fc.reasoning
                        } for fc in change_plan.file_changes],
                        'riskLevel': change_plan.complexity,
                        'testsRequired': any('test' in fc.file_path.lower() for fc in change_plan.file_changes)
                    }
                })
            
            # 3. Phase 3.3 - Assemble file contexts and generate diffs
            workspace_root = context.get('repo', {}).get('workspace_root', '')
            if workspace_root:
                # Initialize context assembler for this workspace
                context_assembler = ContextAssembler(repo_root=workspace_root)
                file_contexts = context_assembler.assemble(change_plan.file_changes)
                
                # Skip diff generation for now - requires synthesis backend implementation
                # TODO: Initialize DiffGenerator with proper synthesis backend (LLM or rule-based)
                logger.info("[PHASE3.3] Diff generation skipped - synthesis backend not configured")
                diff_generator = None
                
                # Generate diffs (when synthesis backend is available)
                if diff_generator:
                    code_changes = diff_generator.generate(
                        plan=change_plan,
                        file_contexts=file_contexts
                    )
                    logger.info(f"[PHASE3.3] Generated {len(code_changes)} diff-based code changes")
                    
                    # Emit Diffs to UI (Phase 3.3)
                    if hasattr(context, 'ui_callback'):
                        await context['ui_callback']({
                            'type': 'navi.diffs.generated',
                            'codeChanges': [{
                                'file_path': change.file_path,
                                'change_type': change.change_type.value,
                                'diff': '\n'.join(h.content for h in change.hunks) if change.hunks else change.new_file_content,
                                'reasoning': getattr(change, 'reasoning', 'Code generation')
                            } for change in code_changes]
                        })
                else:
                    code_changes = []
                    logger.info("[PHASE3.3] Code changes generation deferred - synthesis backend needed")
            else:
                logger.warning("[PHASE3.3] No workspace root provided, skipping diff generation")
                code_changes = []
            
            # 4. Convert ChangePlan back to traditional steps for existing tool_executor
            enhanced_steps = self._convert_change_plan_to_steps(change_plan, traditional_plan.steps)
            
            # 4. Execute using existing tool_executor (no changes needed)
            trace = []
            for step in enhanced_steps:
                try:
                    step_result = await self.tool_executor.execute_step(step, intent, context)
                    trace.append(step_result)
                    
                    if not step_result.ok:
                        logger.error(f"[PHASE3.3] Step failed: {step_result.error}")
                        break
                        
                except Exception as e:
                    logger.exception(f"[PHASE3.3] Step execution failed: {step.id}")
                    trace.append(StepResult(
                        step_id=step.id,
                        ok=False,
                        output=None,
                        error=str(e)
                    ))
            
            # 5. Generate enhanced response with diff information
            success_count = sum(1 for t in trace if t.ok)
            total_count = len(trace)
            
            if success_count == total_count:
                final_message = f"✅ AEI Code Generation: Successfully generated {len(code_changes)} diffs for {change_plan.total_files_affected} files"
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
                trace=[StepResult(
                    step_id="aei_code_generation",
                    ok=False,
                    output=None,
                    error=str(e)
                )],
                final_message=f"AEI Code generation failed: {e}",
                raw_plan_summary=None,
            )
    
    def _convert_change_plan_to_steps(self, change_plan: ChangePlan, original_steps: List) -> List:
        """
        Convert Phase 3.3 ChangePlan back to traditional planner steps.
        
        This allows Phase 3.3 to enhance planning while keeping execution unchanged.
        """
        enhanced_steps = []
        
        for i, file_change in enumerate(change_plan.file_changes):
            if file_change.change_type.value == "create_file":
                step = PlannedStep(
                    id=f"aei_create_{i}",
                    description=f"Create {file_change.file_path}: {file_change.reasoning}",
                    tool="create_file",
                    arguments={
                        "file_path": file_change.file_path,
                        "content": file_change.new_file_content or "",
                        "reasoning": file_change.reasoning
                    }
                )
            elif file_change.change_type.value == "modify_file":
                step = PlannedStep(
                    id=f"aei_modify_{i}",
                    description=f"Modify {file_change.file_path}: {file_change.reasoning}",
                    tool="edit_file",
                    arguments={
                        "file_path": file_change.file_path,
                        "changes": [change.to_dict() for change in file_change.changes],
                        "reasoning": file_change.reasoning
                    }
                )
            else:  # delete_file
                step = PlannedStep(
                    id=f"aei_delete_{i}",
                    description=f"Delete {file_change.file_path}: {file_change.reasoning}",
                    tool="delete_file",
                    arguments={
                        "file_path": file_change.file_path,
                        "reasoning": file_change.reasoning
                    }
                )
            
            enhanced_steps.append(step)
        
            return enhanced_steps
        
    async def handle_validation(self, context: Dict[str, Any], code_changes: List[Any]) -> Dict[str, Any]:
        """
        Phase 3.4 - Run validation pipeline and emit results to UI.
        """
        try:
            # Import Phase 3.4 ValidationPipeline
            from .agent.validation import ValidationPipeline, ValidationStatus
            
            workspace_root = context.get('repo', {}).get('workspace_root', '')
            if not workspace_root:
                raise ValueError("Workspace root required for validation")
            
            # Initialize validation pipeline
            validator = ValidationPipeline(repo_root=workspace_root)
            
            # Run validation
            validation_result = validator.validate(code_changes)
            
            # Emit Validation Result to UI (Phase 3.4)
            if hasattr(context, 'ui_callback'):
                await context['ui_callback']({
                    'type': 'navi.validation.result',
                    'validationResult': {
                        'status': validation_result.status.value,
                        'issues': [{
                            'validator': issue.validator,
                            'file_path': issue.file_path,
                            'line_number': getattr(issue, 'line_number', None),
                            'message': issue.message
                        } for issue in validation_result.issues],
                        'canProceed': validation_result.status == ValidationStatus.PASSED
                    }
                })
            
            return {
                'success': validation_result.status == ValidationStatus.PASSED,
                'result': validation_result,
                'can_proceed': validation_result.status == ValidationStatus.PASSED
            }
            
        except Exception as e:
            logger.exception("[PHASE3.4] Validation failed")
            
            # Emit validation failure to UI
            if hasattr(context, 'ui_callback'):
                await context['ui_callback']({
                    'type': 'navi.validation.result',
                    'validationResult': {
                        'status': 'FAILED',
                        'issues': [{
                            'validator': 'ValidationPipeline',
                            'message': f'Validation system error: {str(e)}'
                        }],
                        'canProceed': False
                    }
                })
            
            return {
                'success': False,
                'error': str(e),
                'can_proceed': False
            }
    
    async def handle_apply_changes(self, context: Dict[str, Any], code_changes: List[Any]) -> Dict[str, Any]:
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
                    
                    applied_files.append({
                        'file_path': change.file_path,
                        'operation': change.change_type.value,
                        'success': True
                    })
                    success_count += 1
                    
                except Exception as e:
                    applied_files.append({
                        'file_path': change.file_path,
                        'operation': change.change_type.value,
                        'success': False,
                        'error': str(e)
                    })
            
            overall_success = success_count == len(code_changes)
            
            # Emit Apply Result to UI (Phase 3.4)
            if hasattr(context, 'ui_callback'):
                await context['ui_callback']({
                    'type': 'navi.changes.applied',
                    'applyResult': {
                        'success': overall_success,
                        'appliedFiles': applied_files,
                        'summary': {
                            'totalFiles': len(code_changes),
                            'successfulFiles': success_count,
                            'failedFiles': len(code_changes) - success_count,
                            'rollbackAvailable': overall_success  # Simplified
                        },
                        'rollbackAvailable': overall_success
                    }
                })
            
            return {
                'success': overall_success,
                'applied_files': applied_files,
                'total_files': len(code_changes),
                'success_count': success_count
            }
            
        except Exception as e:
            logger.exception("[PHASE3.4] Apply changes failed")
            
            # Emit apply failure to UI
            if hasattr(context, 'ui_callback'):
                await context['ui_callback']({
                    'type': 'navi.changes.applied', 
                    'applyResult': {
                        'success': False,
                        'appliedFiles': [],
                        'error': str(e),
                        'rollbackAvailable': False
                    }
                })
            
            return {
                'success': False,
                'error': str(e)
            }

    async def handle_branch_creation(self, context: Dict[str, Any], changePlan: Any, applyResult: Any) -> Dict[str, Any]:
        """
        Phase 3.5.1 - Create branch for PR generation and emit results to UI.
        """
        try:
            from .agent.pr import BranchManager
            
            workspace_root = context.get('repo', {}).get('workspace_root', '')
            if not workspace_root:
                raise ValueError("Workspace root required for branch creation")
            
            # Initialize branch manager
            branch_manager = BranchManager(workspace_root)
            
            # Generate feature description from changePlan
            feature_description = changePlan.get('goal', 'Autonomous feature implementation')
            
            # Create PR branch
            result = branch_manager.create_pr_branch(
                feature_description=feature_description,
                base_branch='main',
                force_clean=False
            )
            
            # Emit Branch Creation Result to UI (Phase 3.5)
            if hasattr(context, 'ui_callback'):
                await context['ui_callback']({
                    'type': 'navi.pr.branch.created',
                    'branchResult': {
                        'success': result.success,
                        'branchName': result.branch_name,
                        'createdFrom': result.created_from,
                        'message': result.message,
                        'workingTreeClean': result.working_tree_clean,
                        'error': result.error
                    }
                })
            
            return {
                'success': result.success,
                'branch_name': result.branch_name,
                'created_from': result.created_from,
                'working_tree_clean': result.working_tree_clean,
                'message': result.message,
                'error': result.error
            }
            
        except Exception as e:
            logger.exception("[PHASE3.5.1] Branch creation failed")
            
            # Emit branch creation failure to UI
            if hasattr(context, 'ui_callback'):
                await context['ui_callback']({
                    'type': 'navi.pr.branch.created',
                    'branchResult': {
                        'success': False,
                        'branchName': '',
                        'createdFrom': 'main',
                        'message': f'Branch creation failed: {str(e)}',
                        'workingTreeClean': False,
                        'error': str(e)
                    }
                })
            
            return {
                'success': False,
                'error': str(e)
            }

    async def handle_commit_creation(self, context: Dict[str, Any], changePlan: Any, branchResult: Any, applyResult: Any) -> Dict[str, Any]:
        """
        Phase 3.5.2 - Create commit from applied changes and emit results to UI.
        """
        try:
            from .agent.pr import CommitComposer
            
            workspace_root = context.get('repo', {}).get('workspace_root', '')
            if not workspace_root:
                raise ValueError("Workspace root required for commit creation")
            
            # Initialize commit composer
            commit_composer = CommitComposer(workspace_root)
            
            # Extract applied files from apply result
            applied_files = []
            if applyResult and applyResult.get('applied_files'):
                applied_files = [
                    af['file_path'] for af in applyResult['applied_files'] 
                    if af.get('success', False)
                ]
            elif applyResult and applyResult.get('success_count', 0) > 0:
                # Fallback: if no detailed file info, try to get from changePlan
                if changePlan and changePlan.get('files'):
                    applied_files = [f['path'] for f in changePlan['files']]
            
            if not applied_files:
                return {
                    'success': False,
                    'error': 'No applied files found for commit'
                }
            
            logger.info(f"[ORCHESTRATOR] Creating commit for {len(applied_files)} applied files")
            
            # Create commit
            result = commit_composer.create_pr_commit(
                files=applied_files,
                change_plan=changePlan
            )
            
            # Emit Commit Creation Result to UI (Phase 3.5.2)
            if hasattr(context, 'ui_callback'):
                await context['ui_callback']({
                    'type': 'navi.pr.commit.created',
                    'commitResult': {
                        'success': result.success,
                        'sha': result.sha,
                        'message': result.message,
                        'files': result.files,
                        'stagedFilesCount': result.staged_files_count,
                        'error': result.error
                    }
                })
            
            return {
                'success': result.success,
                'sha': result.sha,
                'message': result.message,
                'files': result.files,
                'staged_files_count': result.staged_files_count,
                'error': result.error
            }
            
        except Exception as e:
            logger.exception("[PHASE3.5.2] Commit creation failed")
            
            # Emit commit creation failure to UI
            if hasattr(context, 'ui_callback'):
                await context['ui_callback']({
                    'type': 'navi.pr.commit.created',
                    'commitResult': {
                        'success': False,
                        'sha': '',
                        'message': '',
                        'files': [],
                        'stagedFilesCount': 0,
                        'error': str(e)
                    }
                })
            
            return {
                'success': False,
                'error': str(e)
            }

    async def handle_pr_creation_simple(self, context: Dict[str, Any], changePlan: Any, branchResult: Any, commitResult: Any) -> Dict[str, Any]:
        """
        Phase 3.5.3 - Create GitHub PR and emit results to UI.
        """
        try:
            from .agent.pr import PRCreator
            
            workspace_root = context.get('repo', {}).get('workspace_root', '')
            if not workspace_root:
                raise ValueError("Workspace root required for PR creation")
            
            # Initialize PR creator
            pr_creator = PRCreator(repo_root=workspace_root)
            
            # Extract metadata from previous results
            branch_name = branchResult.get('branch_name', '')
            commit_sha = commitResult.get('sha', '')
            
            # Generate PR content from changePlan
            pr_title = changePlan.get('goal', 'Autonomous feature implementation')
            
            # Create comprehensive PR description
            pr_description_parts = []
            if changePlan.get('goal'):
                pr_description_parts.append(f"**Goal:** {changePlan['goal']}")
            if changePlan.get('modifications'):
                pr_description_parts.append(f"**Changes:** {len(changePlan['modifications'])} file modifications")
            if changePlan.get('reasoning'):
                pr_description_parts.append(f"**Reasoning:** {changePlan['reasoning']}")
            
            pr_description = "\n\n".join(pr_description_parts) if pr_description_parts else "Autonomous code generation"
            
            # Create GitHub PR
            result = pr_creator.create_navi_pr(
                branch=branch_name,
                base='main',
                change_plan=changePlan,
                commit_message=pr_title
            )
            
            logger.info(f"[PHASE3.5.3] PR creation result: {result.success}")
            
            # Emit PR creation result to UI
            if hasattr(context, 'ui_callback'):
                await context['ui_callback']({
                    'type': 'navi.pr.created',
                    'prResult': {
                        'success': result.success,
                        'pr_number': result.pr_number,
                        'pr_url': result.pr_url,
                        'branch_name': branch_name,
                        'title': pr_title,
                        'description': pr_description,
                        'error': result.error
                    }
                })
            
            return {
                'success': result.success,
                'pr_number': result.pr_number,
                'pr_url': result.pr_url,
                'branch_name': branch_name,
                'title': pr_title,
                'description': pr_description,
                'error': result.error
            }
            
        except Exception as e:
            logger.exception("[PHASE3.5.3] PR creation failed")
            
            # Emit PR creation failure to UI
            if hasattr(context, 'ui_callback'):
                await context['ui_callback']({
                    'type': 'navi.pr.created',
                    'prResult': {
                        'success': False,
                        'pr_number': None,
                        'pr_url': '',
                        'branch_name': '',
                        'title': '',
                        'description': '',
                        'error': str(e)
                    }
                })
            
            return {
                'success': False,
                'error': str(e)
            }

    async def handle_pr_lifecycle_monitoring(self, context: Dict[str, Any], prResult: Any) -> Dict[str, Any]:
        """
        Phase 3.5.4 - Start background CI monitoring for PR and emit lifecycle updates.
        """
        try:
            from .agent.pr import PRLifecycleEngine
            
            workspace_root = context.get('repo', {}).get('workspace_root', '')
            if not workspace_root:
                raise ValueError("Workspace root required for PR monitoring")
            
            pr_number = prResult.get('pr_number')
            if not pr_number:
                raise ValueError("PR number required for monitoring")
            
            # Initialize lifecycle engine from workspace
            lifecycle_engine = PRLifecycleEngine.from_workspace(
                workspace_root=workspace_root,
                pr_number=pr_number
            )
            
            logger.info(f"[PHASE3.5.4] Starting CI monitoring for PR #{pr_number}")
            
            # Define event emission callback
            async def emit_lifecycle_event(event_type: str, payload: Dict[str, Any]) -> None:
                if hasattr(context, 'ui_callback'):
                    await context['ui_callback']({
                        'type': event_type,
                        **payload
                    })
            
            # Start monitoring in background task
            async def background_monitor():
                try:
                    result = await lifecycle_engine.monitor_async(emit_lifecycle_event)
                    logger.info(f"[PHASE3.5.4] Monitoring completed for PR #{pr_number}: {result.terminal_reason}")
                    
                    # Emit final monitoring result
                    await emit_lifecycle_event("navi.pr.monitoring.completed", {
                        "prNumber": pr_number,
                        "terminalReason": result.terminal_reason,
                        "duration": result.monitoring_duration,
                        "eventsEmitted": result.events_emitted,
                        "finalStatus": result.final_status.to_dict()
                    })
                    
                except Exception as e:
                    logger.exception(f"[PHASE3.5.4] Background monitoring failed for PR #{pr_number}")
                    await emit_lifecycle_event("navi.pr.monitoring.error", {
                        "prNumber": pr_number,
                        "error": str(e)
                    })
            
            # Start background monitoring (fire and forget)
            asyncio.create_task(background_monitor())
            
            # Emit monitoring started event
            if hasattr(context, 'ui_callback'):
                await context['ui_callback']({
                    'type': 'navi.pr.monitoring.started',
                    'prNumber': pr_number,
                    'repoOwner': lifecycle_engine.repo_owner,
                    'repoName': lifecycle_engine.repo_name
                })
            
            return {
                'success': True,
                'pr_number': pr_number,
                'monitoring_started': True,
                'repo_owner': lifecycle_engine.repo_owner,
                'repo_name': lifecycle_engine.repo_name
            }
            
        except Exception as e:
            logger.exception("[PHASE3.5.4] PR lifecycle monitoring failed to start")
            
            # Emit monitoring failure to UI
            if hasattr(context, 'ui_callback'):
                await context['ui_callback']({
                    'type': 'navi.pr.monitoring.error',
                    'prNumber': prResult.get('pr_number', 0),
                    'error': str(e),
                    'phase': 'initialization'
                })
            
            return {
                'success': False,
                'error': str(e)
            }

    async def handle_self_healing(self, context: Dict[str, Any], ci_payload: Dict[str, Any], pr_number: int) -> Dict[str, Any]:
        """
        Phase 3.6 - Attempt autonomous self-healing from CI failure.
        """
        try:
            from .agent.self_healing import SelfHealingEngine
            
            workspace_root = context.get('repo', {}).get('workspace_root', '')
            if not workspace_root:
                raise ValueError("Workspace root required for self-healing")
            
            # Initialize self-healing engine
            healing_engine = SelfHealingEngine(
                max_attempts=2,
                min_confidence=0.7,
                timeout_minutes=30
            )
            
            logger.info(f"[PHASE3.6] Starting self-healing for PR #{pr_number}")
            
            # Define event emission callback
            async def emit_healing_event(event_type: str, payload: Dict[str, Any]) -> None:
                if hasattr(context, 'ui_callback'):
                    await context['ui_callback']({
                        'type': event_type,
                        **payload
                    })
            
            # Attempt recovery
            recovery_result = await healing_engine.attempt_recovery(
                ci_payload=ci_payload,
                pr_number=pr_number,
                workspace_root=workspace_root,
                attempt_count=0,
                emit_event=emit_healing_event
            )
            
            logger.info(f"[PHASE3.6] Self-healing result: {recovery_result['status']}")
            
            # If fix was planned, we can integrate with Phase 3.3-3.5 here
            if recovery_result['status'] == 'fix_planned':
                fix_plan = recovery_result.get('fix_plan', {})
                
                # TODO: Integrate with Phase 3.3 code generation
                # This would trigger the full pipeline:
                # 1. Generate code changes using fix_plan['fix_goal']
                # 2. Validate using Phase 3.4
                # 3. Commit using Phase 3.5.2
                # 4. Monitor CI using Phase 3.5.4
                
                logger.info(f"[PHASE3.6] Fix plan ready for code generation: {fix_plan.get('goal', '')}")
            
            return recovery_result
            
        except Exception as e:
            logger.exception("[PHASE3.6] Self-healing failed")
            
            # Emit self-healing failure to UI
            if hasattr(context, 'ui_callback'):
                await context['ui_callback']({
                    'type': 'navi.selfHealing.error',
                    'prNumber': pr_number,
                    'error': str(e),
                    'phase': 'initialization'
                })
            
            return {
                'status': 'failed',
                'error': str(e)
            }

    async def handle_instruction(
        self, 
        user_id: str, 
        instruction: str, 
        workspace_root: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point: handle a user instruction with full multi-agent coordination
        """
        
        session_id = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # 1. Initialize agent context
            context = await self._initialize_context(user_id, instruction, workspace_root, options)
            
            # 2. Load user memory and preferences
            memory_context = await self.memory_agent.load_context(user_id)
            context.memory_context = memory_context['recent_events']
            context.user_preferences = memory_context['user_preferences']
            
            # 3. Analyze repository (if not cached)
            repo_map = await self._get_or_analyze_repo(workspace_root)
            context.repo_map = repo_map
            
            # 4. Generate execution plan
            plan = await self.planner_agent.generate_plan(
                instruction=instruction,
                repo_map=repo_map.dict() if repo_map else {},
                user_context=memory_context
            )
            
            # 5. Execute plan with coordination
            execution_results = await self._execute_plan_with_coordination(plan, context)
            
            # 6. Review and validate results
            review_result = await self._review_execution_results(plan, execution_results, context)
            
            # 7. Save to memory
            await self._save_execution_to_memory(user_id, instruction, plan, execution_results, review_result)
            
            # 8. Generate unified response
            response = await self._generate_unified_response(
                instruction, plan, execution_results, review_result, context
            )
            
            return {
                'session_id': session_id,
                'success': review_result['overall_success'],
                'plan': plan.dict(),
                'execution_results': [result.dict() for result in execution_results],
                'review': review_result,
                'response': response,
                'context': context.dict()
            }
            
        except Exception as e:
            # Handle orchestration errors
            error_response = await self._handle_orchestration_error(e, user_id, instruction, workspace_root)
            return error_response
    
    async def _initialize_context(
        self, 
        user_id: str, 
        instruction: str, 
        workspace_root: str,
        options: Optional[Dict[str, Any]] = None
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
                'start_time': datetime.now(),
                'orchestrator_version': '1.0.0',
                'safety_level': options.get('safety_level', 'medium') if options else 'medium'
            }
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
        self, 
        plan: Plan, 
        context: AgentContext
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
                deps_satisfied = all(dep_id in executed_steps for dep_id in step.depends_on)
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
                    recovery_result = await self._handle_step_failure(step, result, plan, context)
                    
                    if recovery_result.get('retry', False):
                        # Retry the step
                        retry_result = await self.executor.execute_step(step, context.workspace_root, context.dict())
                        execution_results.append(retry_result)
                        
                        if retry_result.success:
                            executed_steps.add(step.id)
                            plan.mark_step_executed(step.id)
                    
                    elif recovery_result.get('skip', False):
                        # Skip this step and continue
                        executed_steps.add(step.id)
                        plan.mark_step_executed(step.id)
                    
                    else:
                        # Stop execution on critical failure
                        break
        
        return execution_results
    
    async def _execute_steps_batch(
        self, 
        steps: List, 
        context: AgentContext
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
            if execution_strategy['approach'] == 'direct':
                result = await self.executor.execute_step(step, context.workspace_root, context.dict())
            
            elif execution_strategy['approach'] == 'guided':
                # Use LLM guidance for complex steps
                result = await self._execute_with_llm_guidance(step, context)
            
            elif execution_strategy['approach'] == 'interactive':
                # Require user confirmation
                result = await self._execute_with_user_confirmation(step, context)
            
            else:
                # Default to direct execution
                result = await self.executor.execute_step(step, context.workspace_root, context.dict())
            
            results.append(result)
        
        return results
    
    async def _determine_execution_strategy(self, step, context: AgentContext) -> Dict[str, Any]:
        """
        Determine the best execution strategy for a step using AI reasoning
        """
        
        # Analyze step complexity and risk
        risk_factors = []
        
        # File modification risks
        if step.action_type in ['modify_file', 'refactor'] and step.file_targets:
            for file_path in step.file_targets:
                if 'config' in file_path.lower():
                    risk_factors.append('config_file_modification')
                if file_path.endswith(('.py', '.js', '.ts')) and 'test' not in file_path:
                    risk_factors.append('source_code_modification')
        
        # Command execution risks
        if step.action_type == 'run_command':
            command = step.metadata.get('command', '')
            if any(risky in command for risky in ['rm', 'delete', 'drop', 'truncate']):
                risk_factors.append('destructive_command')
        
        # Safety level from user preferences
        safety_level = context.user_preferences.get('safety_level', 'medium')
        
        # Determine strategy
        if len(risk_factors) == 0:
            return {'approach': 'direct', 'reasoning': 'Low risk operation'}
        
        elif safety_level == 'high' or len(risk_factors) > 1:
            return {'approach': 'interactive', 'reasoning': f'High risk factors: {risk_factors}'}
        
        elif step.metadata.get('complexity', 0.5) > 0.7:
            return {'approach': 'guided', 'reasoning': 'High complexity operation'}
        
        else:
            return {'approach': 'direct', 'reasoning': 'Standard execution'}
    
    async def _execute_with_llm_guidance(self, step, context: AgentContext) -> ExecutionResult:
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
            guidance_response = await self.llm_router.run(prompt=guidance_prompt, use_smart_auto=True)
            guidance = json.loads(guidance_response.text)
            
            # Execute with guidance
            result = await self.executor.execute_step(step, context.workspace_root, context.dict())
            
            # Add guidance to metadata
            result.metadata['execution_guidance'] = guidance
            
            return result
            
        except Exception:
            # Fallback to direct execution
            return await self.executor.execute_step(step, context.workspace_root, context.dict())
    
    async def _execute_with_user_confirmation(self, step, context: AgentContext) -> ExecutionResult:
        """
        Execute step with user confirmation for high-risk operations
        """
        
        # This would integrate with the UI to request user confirmation
        # For now, simulate user confirmation
        
        return ExecutionResult(
            step_id=step.id,
            success=True,
            output="Step executed with user confirmation (simulated)",
            metadata={'requires_user_confirmation': True}
        )
    
    async def _handle_step_failure(
        self, 
        step, 
        result: ExecutionResult, 
        plan: Plan, 
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Handle step execution failure with intelligent recovery
        """
        
        # Analyze failure
        failure_analysis = await self._analyze_failure(step, result, context)
        
        # Determine recovery strategy
        if failure_analysis['category'] == 'temporary':
            return {'retry': True, 'reasoning': 'Temporary failure, retry recommended'}
        
        elif failure_analysis['category'] == 'dependency':
            return {'replan': True, 'reasoning': 'Dependency issue, replanning needed'}
        
        elif failure_analysis['category'] == 'user_input':
            return {'ask_user': True, 'reasoning': 'User input required'}
        
        elif failure_analysis['severity'] == 'low':
            return {'skip': True, 'reasoning': 'Low severity, safe to skip'}
        
        else:
            return {'stop': True, 'reasoning': 'Critical failure, stopping execution'}
    
    async def _analyze_failure(self, step, result: ExecutionResult, context: AgentContext) -> Dict[str, Any]:
        """
        Analyze execution failure to determine appropriate response
        """
        
        error_message = result.error or ""
        
        # Categorize failure
        if "timeout" in error_message.lower():
            return {'category': 'temporary', 'severity': 'medium'}
        
        elif "permission" in error_message.lower():
            return {'category': 'permission', 'severity': 'high'}
        
        elif "not found" in error_message.lower():
            return {'category': 'dependency', 'severity': 'medium'}
        
        elif "syntax" in error_message.lower():
            return {'category': 'user_input', 'severity': 'medium'}
        
        else:
            return {'category': 'unknown', 'severity': 'high'}
    
    async def _review_execution_results(
        self, 
        plan: Plan, 
        execution_results: List[ExecutionResult], 
        context: AgentContext
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
            'overall_success': success_rate >= 0.8,  # 80% success threshold
            'success_rate': success_rate,
            'total_steps': total_steps,
            'successful_steps': successful_steps,
            'failed_steps': failed_steps,
            'files_modified': unique_files_modified,
            'summary': summary,
            'recommendations': await self._generate_recommendations(plan, execution_results, context)
        }
    
    async def _generate_recommendations(
        self, 
        plan: Plan, 
        execution_results: List[ExecutionResult], 
        context: AgentContext
    ) -> List[str]:
        """
        Generate recommendations based on execution results
        """
        
        recommendations = []
        
        # Analyze failed steps
        failed_results = [r for r in execution_results if not r.success]
        
        if failed_results:
            recommendations.append("Review failed steps and consider manual intervention")
        
        # Check for modified critical files
        critical_files = ['package.json', 'requirements.txt', 'pom.xml', 'Dockerfile']
        modified_critical = [f for f in context.execution_history if any(cf in str(f.files_modified) for cf in critical_files)]
        
        if modified_critical:
            recommendations.append("Critical configuration files were modified - consider running tests")
        
        # Performance recommendations
        total_execution_time = sum(r.execution_time for r in execution_results)
        if total_execution_time > 300:  # 5 minutes
            recommendations.append("Consider breaking down complex operations into smaller steps")
        
        return recommendations
    
    async def _save_execution_to_memory(
        self, 
        user_id: str, 
        instruction: str, 
        plan: Plan, 
        execution_results: List[ExecutionResult],
        review_result: Dict[str, Any]
    ):
        """
        Save execution results to user memory for learning
        """
        
        await self.memory.save_event(
            user_id=user_id,
            event_type='execution_result',
            content={
                'instruction': instruction,
                'plan': plan.dict(),
                'results': [r.dict() for r in execution_results],
                'review': review_result,
                'success': review_result['overall_success']
            },
            importance=0.8 if review_result['overall_success'] else 0.9,  # Failures are more important to remember
            tags=['execution', 'orchestration', 'multi_agent']
        )
    
    async def _generate_unified_response(
        self, 
        instruction: str, 
        plan: Plan, 
        execution_results: List[ExecutionResult],
        review_result: Dict[str, Any], 
        context: AgentContext
    ) -> str:
        """
        Generate a unified, human-readable response
        """
        
        if review_result['overall_success']:
            response = f"✅ Successfully executed your request: \"{instruction}\"\n\n"
            response += f"📋 Completed {review_result['successful_steps']} steps\n"
            response += f"📝 Modified {len(review_result['files_modified'])} files\n"
            
            if review_result['files_modified']:
                response += "\nFiles changed:\n"
                for file in review_result['files_modified'][:5]:  # Show first 5
                    response += f"• {file}\n"
                
                if len(review_result['files_modified']) > 5:
                    response += f"• ... and {len(review_result['files_modified']) - 5} more\n"
        
        else:
            response = f"⚠️ Partially completed your request: \"{instruction}\"\n\n"
            response += f"✅ Successful: {review_result['successful_steps']}\n"
            response += f"❌ Failed: {review_result['failed_steps']}\n"
            response += f"\n{review_result['summary']}\n"
        
        if review_result['recommendations']:
            response += "\n💡 Recommendations:\n"
            for rec in review_result['recommendations']:
                response += f"• {rec}\n"
        
        return response
    
    async def _handle_orchestration_error(
        self, 
        error: Exception, 
        user_id: str, 
        instruction: str, 
        workspace_root: str
    ) -> Dict[str, Any]:
        """
        Handle orchestration-level errors
        """
        
        # Save error to memory
        await self.memory_agent.save_event(
            user_id=user_id,
            event_type='error',
            content={
                'instruction': instruction,
                'error_type': type(error).__name__,
                'error_message': str(error),
                'workspace_root': workspace_root
            },
            importance=1.0,  # Orchestration errors are critical
            tags=['error', 'orchestration', 'critical']
        )
        
        return {
            'success': False,
            'error': str(error),
            'error_type': 'orchestration_error',
            'response': f"❌ I encountered an error while processing your request: {str(error)}\n\nThis has been logged and I'll learn from it to prevent similar issues in the future."
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
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle complete PR creation lifecycle
        """
        if not PHASE_3_AVAILABLE:
            return {
                'success': False,
                'error': 'PR lifecycle engine not available',
                'response': 'PR generation features require Phase 3 components to be enabled.'
            }
        
        try:
            # Initialize PR lifecycle engine for this workspace
            pr_config = await self._initialize_pr_config(workspace_root)
            
            if not pr_config:
                return {
                    'success': False,
                    'error': 'Failed to configure PR lifecycle',
                    'response': 'Could not configure git provider for PR creation.'
                }
            
            # Create PR task
            pr_task = {
                'taskId': task_id,
                'summary': summary,
                'description': description,
                'changePlan': changePlan,
                'validationResult': validationResult,
                'jiraTicket': options.get('jiraTicket') if options else None,
                'featurePlan': options.get('featurePlan') if options else None,
                'assignees': options.get('assignees', []) if options else [],
                'reviewers': options.get('reviewers', []) if options else [],
                'labels': options.get('labels', []) if options else []
            }
            
            # Execute full PR lifecycle
            pr_result = await self.pr_lifecycle_engine.executeFullLifecycle(pr_task)
            
            # Save to memory
            await self.memory_agent.save_event(
                user_id=user_id,
                event_type='pr_created',
                content={
                    'task_id': task_id,
                    'pr_number': pr_result['pr']['prNumber'],
                    'pr_url': pr_result['pr']['htmlUrl'],
                    'branch_name': pr_result['branch']['name'],
                    'summary': summary
                },
                importance=0.9,
                tags=['pr', 'creation', 'autonomous']
            )
            
            return {
                'success': True,
                'pr_number': pr_result['pr']['prNumber'],
                'pr_url': pr_result['pr']['htmlUrl'],
                'branch_name': pr_result['branch']['name'],
                'monitoring': pr_result['monitoring'],
                'response': f"✅ Successfully created PR #{pr_result['pr']['prNumber']}: {summary}\\n\\n🔗 {pr_result['pr']['htmlUrl']}\\n\\n{'🔍 Now monitoring for CI updates and reviewer comments.' if pr_result['monitoring'] else ''}",
                'result': pr_result
            }
            
        except Exception as e:
            await self.memory_agent.save_event(
                user_id=user_id,
                event_type='pr_creation_error',
                content={
                    'task_id': task_id,
                    'error': str(e),
                    'workspace_root': workspace_root
                },
                importance=1.0,
                tags=['pr', 'error', 'creation']
            )
            
            return {
                'success': False,
                'error': str(e),
                'response': f"❌ Failed to create PR: {str(e)}"
            }
    
    async def handle_pr_monitoring(
        self,
        user_id: str,
        pr_number: int,
        action: str = 'status',  # 'status', 'start_watch', 'stop_watch', 'resolve_comments'
        workspace_root: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle PR monitoring and management
        """
        if not PHASE_3_AVAILABLE:
            return {
                'success': False,
                'error': 'PR monitoring not available',
                'response': 'PR monitoring features require Phase 3 components to be enabled.'
            }
        
        try:
            if workspace_root:
                pr_config = await self._initialize_pr_config(workspace_root)
                if not pr_config:
                    return {
                        'success': False,
                        'error': 'Failed to configure PR monitoring',
                        'response': 'Could not configure git provider for PR monitoring.'
                    }
            
            if action == 'status':
                # Get PR status
                status = await self.pr_monitor.getStatus(pr_number)
                report = self.pr_status_reporter.generateReport(
                    pr_number, status['prUrl'], status.get('htmlUrl', status['prUrl']), 
                    f"PR #{pr_number}", status
                )
                
                return {
                    'success': True,
                    'status': status,
                    'report': report,
                    'response': report['humanReadable']
                }
            
            elif action == 'start_watch':
                await self.pr_lifecycle_engine.startMonitoring(pr_number)
                
                return {
                    'success': True,
                    'response': f"🔍 Now monitoring PR #{pr_number} for updates"
                }
            
            elif action == 'stop_watch':
                self.pr_lifecycle_engine.stopMonitoring(pr_number)
                
                return {
                    'success': True,
                    'response': f"⏹️ Stopped monitoring PR #{pr_number}"
                }
            
            elif action == 'resolve_comments':
                # Get actionable comments and attempt to resolve them
                comments = await self.pr_comment_resolver.getActionableComments(pr_number)
                resolved_count = 0
                
                for comment in comments[:3]:  # Limit to 3 comments per request
                    try:
                        context = {'comment': comment, 'prNumber': pr_number}
                        resolution = await self.pr_comment_resolver.resolve(context)
                        
                        if resolution['understood'] and resolution['confidence'] > 80:
                            # Auto-resolve high-confidence comments
                            await self.pr_comment_resolver.applyResolution(
                                pr_number, resolution, comment
                            )
                            resolved_count += 1
                    except Exception as e:
                        print(f"Failed to resolve comment {comment['id']}: {e}")
                
                return {
                    'success': True,
                    'resolved_count': resolved_count,
                    'total_comments': len(comments),
                    'response': f"✅ Resolved {resolved_count}/{len(comments)} actionable comments on PR #{pr_number}"
                }
            
            else:
                return {
                    'success': False,
                    'error': f'Unknown action: {action}',
                    'response': f'Unknown PR action: {action}. Available actions: status, start_watch, stop_watch, resolve_comments'
                }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'response': f"❌ Failed to {action} PR #{pr_number}: {str(e)}"
            }
    
    async def _initialize_pr_config(self, workspace_root: str) -> Optional[Dict[str, Any]]:
        """
        Initialize PR configuration for a workspace
        """
        try:
            # Import PR lifecycle components if needed
            from .agent.pr import PRLifecycleEngine
            
            # Create temporary instance to use from_workspace which detects provider
            temp_engine = PRLifecycleEngine.from_workspace(workspace_root=workspace_root, pr_number=0)
            provider = 'github'  # Default to GitHub, can be extended to detect from git config
            repo_info = {'owner': temp_engine.repo_owner, 'name': temp_engine.repo_name}
            
            # Create PR lifecycle config
            pr_config = {
                'provider': provider,
                'repoOwner': repo_info['owner'],
                'repoName': repo_info['name'],
                'workspaceRoot': workspace_root,
                'defaultBaseBranch': 'main',
                'autoWatch': True,
                'autoResolveComments': True
            }
            
            # Initialize PR lifecycle engine
            self.pr_lifecycle_engine = PRLifecycleEngine(
                pr_config, 
                self.approval_engine,  # From Phase 3.2
                self.code_synthesizer,  # From Phase 3.3
                self.llm_router
            )
            
            # Initialize other PR components
            self.branch_manager = BranchManager(workspace_root)
            self.pr_creator = PRCreator(provider, repo_info['owner'], repo_info['name'])
            self.pr_monitor = PRMonitor(provider, repo_info['owner'], repo_info['name'])
            self.pr_comment_resolver = PRCommentResolver(
                provider, repo_info['owner'], repo_info['name'],
                self.code_synthesizer, self.llm_router
            )
            
            return pr_config
            
        except Exception as e:
            print(f"Failed to initialize PR config: {e}")
            return None
