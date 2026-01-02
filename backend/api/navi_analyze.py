"""
NAVI Analyze Problems API

This endpoint implements Phase 4.2-4.3 - FIX_PROBLEMS grounding and execution for NAVI.
It provides a clean, deterministic interface for problem analysis and resolution without
LLM guessing or validation errors.
"""

from fastapi import APIRouter
from dataclasses import dataclass
from pydantic import BaseModel, Field
from threading import Lock
from typing import Dict, Any, List, Optional
import logging
import time

from backend.agent.task_grounder import ground_task, GroundingResult
from backend.agent.task_grounder.types import GroundedTask
from backend.agent.execution_engine import ExecutionEngine, ExecutionResult, ExecutionStatus, FixProblemsExecutor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/navi", tags=["navi-analyze"])

_PENDING_EXECUTIONS_TTL_SECONDS = 30 * 60


@dataclass
class PendingExecution:
    execution_result: ExecutionResult
    context: Dict[str, Any]
    session_id: str
    created_at: float


_PENDING_EXECUTIONS: Dict[str, PendingExecution] = {}
_PENDING_EXECUTIONS_LOCK = Lock()


def _build_execution_engine(workspace_root: Optional[str]) -> ExecutionEngine:
    engine = ExecutionEngine()
    engine.register_executor("FIX_PROBLEMS", FixProblemsExecutor(workspace_root=workspace_root))
    return engine


def _prune_pending_executions(now: Optional[float] = None) -> None:
    current_time = now or time.time()
    expired = [
        task_id
        for task_id, pending in _PENDING_EXECUTIONS.items()
        if current_time - pending.created_at > _PENDING_EXECUTIONS_TTL_SECONDS
    ]
    for task_id in expired:
        del _PENDING_EXECUTIONS[task_id]


def _store_pending_execution(task_id: str, execution_result: ExecutionResult, context: Dict[str, Any], session_id: str) -> None:
    with _PENDING_EXECUTIONS_LOCK:
        _prune_pending_executions()
        _PENDING_EXECUTIONS[task_id] = PendingExecution(
            execution_result=execution_result,
            context=context,
            session_id=session_id,
            created_at=time.time()
        )


def _pop_pending_execution(task_id: str, session_id: str) -> Optional[PendingExecution]:
    with _PENDING_EXECUTIONS_LOCK:
        pending = _PENDING_EXECUTIONS.get(task_id)
        if not pending:
            return None
        if pending.session_id != session_id:
            return None
        del _PENDING_EXECUTIONS[task_id]
        return pending


class AnalyzeProblemsRequest(BaseModel):
    """Request to analyze problems in the workspace"""
    user_input: str = Field(description="User's input message")
    session_id: str = Field(description="Session identifier")
    workspace: Optional[str] = Field(default=None, description="Workspace name/path")
    diagnostics: Optional[List[Dict[str, Any]]] = Field(default=None, description="VS Code diagnostics")
    diagnostics_count: Optional[int] = Field(default=None, description="Count of diagnostics")
    active_file: Optional[str] = Field(default=None, description="Currently active file")


class AnalyzeProblemsResponse(BaseModel):
    """Response from analyze problems"""
    success: bool
    plan: Optional[Dict[str, Any]] = None
    reasoning: Optional[str] = None
    error: Optional[str] = None
    grounding_result: Optional[Dict[str, Any]] = None
    execution_result: Optional[Dict[str, Any]] = None  # Phase 4.3 - execution details
    session_id: str


class ExecuteTaskRequest(BaseModel):
    """Request to execute an approved task"""
    task_id: str = Field(description="ID of the task to execute")
    session_id: str = Field(description="Session identifier")
    approved: bool = Field(description="User approval confirmation")
    workspace_root: Optional[str] = Field(default=None, description="Workspace root path")


class ExecuteTaskResponse(BaseModel):
    """Response from task execution"""
    success: bool
    task_id: str
    status: str
    execution_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    session_id: str


@router.post("/analyze-problems", response_model=AnalyzeProblemsResponse)
async def analyze_problems(request: AnalyzeProblemsRequest) -> AnalyzeProblemsResponse:
    """
    Analyze problems in the workspace using deterministic task grounding.
    
    This endpoint:
    1. Takes user input like "can you fix the errors in the problems tab?"
    2. Uses task grounding to classify as FIX_PROBLEMS intent
    3. Validates workspace context (diagnostics count, etc.)
    4. Returns structured plan or rejection
    
    No LLM guessing, no validation errors - pure deterministic logic.
    """
    logger.info(f"Analyze problems request: user_input='{request.user_input[:100]}...', session={request.session_id}")
    
    start_time = time.time()
    
    try:
        # Step 1: Extract context from request
        workspace_root = request.workspace or ""
        context = {
            "workspace": workspace_root or "default-workspace",
            "workspace_root": workspace_root,
            "diagnostics": request.diagnostics or [],
            "diagnostics_count": request.diagnostics_count or 0,
            "active_file": request.active_file,
            "user_input": request.user_input,
            "session_id": request.session_id
        }
        
        # Transform diagnostics for the task grounder if provided
        if request.diagnostics:
            transformed_diagnostics = []
            for diag_entry in request.diagnostics:
                # Handle two formats:
                # 1. VS Code format: { "path": "file.ts", "diagnostics": [...] }
                # 2. Direct format: { "source": "file.ts", "message": "...", ... }
                
                if "diagnostics" in diag_entry:
                    # Format 1: VS Code nested format
                    file_path = diag_entry.get("path", diag_entry.get("uri", ""))
                    for diag in diag_entry.get("diagnostics", []):
                        transformed_diag = {
                            "file": file_path,
                            "message": diag.get("message", ""),
                            "severity": _map_severity_to_string(diag.get("severity", 1)),
                            "code": str(diag.get("code", "")) if diag.get("code") else None,
                            "line": diag.get("line"),
                            "column": diag.get("character")  # VS Code uses 'character', task grounder expects 'column'
                        }
                        transformed_diagnostics.append(transformed_diag)
                else:
                    # Format 2: Direct diagnostic format
                    transformed_diag = {
                        "file": diag_entry.get("source", diag_entry.get("file", "")),
                        "message": diag_entry.get("message", ""),
                        "severity": _map_severity_to_string(diag_entry.get("severity", 1)),
                        "code": str(diag_entry.get("code", "")) if diag_entry.get("code") else None,
                        "line": diag_entry.get("startLineNumber", diag_entry.get("line")),
                        "column": diag_entry.get("startColumn", diag_entry.get("column"))
                    }
                    transformed_diagnostics.append(transformed_diag)
            context["diagnostics"] = transformed_diagnostics
        
        logger.info(f"Context extracted: workspace={context['workspace']}, diagnostics_count={context['diagnostics_count']}")
        
        # Step 2: Determine intent from user input
        # For Phase 4.2, we're focusing on FIX_PROBLEMS
        user_input_lower = request.user_input.lower()
        context["message"] = request.user_input  # Add message to context for grounding
        
        # Simple intent classification based on keywords
        intent_str = None
        if any(word in user_input_lower for word in ["fix", "error", "errors", "problem", "problems", "diagnostic", "diagnostics"]):
            intent_str = "FIX_PROBLEMS"
        elif any(word in user_input_lower for word in ["deploy", "deployment", "publish", "release"]):
            intent_str = "DEPLOY"
        else:
            # For now, reject other intents
            return AnalyzeProblemsResponse(
                success=False,
                error="Intent not supported yet. Currently only 'fix problems' and 'deploy' type requests are implemented.",
                session_id=request.session_id,
                reasoning="Phase 4.2 only supports FIX_PROBLEMS and DEPLOY intents"
            )
        
        logger.info(f"Intent classified: {intent_str}")
        
        # Step 3: Create mock intent object that matches what grounder expects
        # The grounder was designed to work with classified intent objects, not strings
        class MockIntent:
            def __init__(self, intent_type: str):
                if intent_type == "FIX_PROBLEMS":
                    self.family = type('Family', (), {'value': 'ENGINEERING'})()
                    self.kind = type('Kind', (), {'value': 'FIX_PROBLEMS'})()
                elif intent_type == "DEPLOY":
                    self.family = type('Family', (), {'value': 'DEPLOYMENT'})()
                    self.kind = type('Kind', (), {'value': 'DEPLOY'})()
        
        mock_intent = MockIntent(intent_str)
        
        # Ground the task using our deterministic grounding system
        grounding_result: GroundingResult = await ground_task(mock_intent, context)
        
        logger.info(f"Grounding result: type={grounding_result.type}")
        
        # Step 4: Handle different grounding outcomes
        if grounding_result.type == "rejected":
            return AnalyzeProblemsResponse(
                success=False,
                error=grounding_result.reason,
                session_id=request.session_id,
                reasoning="Task grounding rejected the request",
                grounding_result=grounding_result.model_dump()
            )
        
        elif grounding_result.type == "clarification":
            # For Phase 4.2, we're not implementing clarification yet
            return AnalyzeProblemsResponse(
                success=False,
                error="Clarification requests not implemented in Phase 4.2",
                session_id=request.session_id,
                reasoning="Would need user clarification",
                grounding_result=grounding_result.model_dump()
            )
        
        elif grounding_result.type == "ready":
            # Success! We have a grounded task
            if grounding_result.task is None:
                logger.error("Task grounding failed - no task generated")
                return AnalyzeProblemsResponse(
                    success=False,
                    error="Task grounding returned None",
                    session_id=request.session_id
                )
            
            grounded_task: GroundedTask = grounding_result.task
            
            execution_engine = _build_execution_engine(workspace_root)

            # Phase 4.3: Execute the grounded task through execution engine
            execution_context = {
                "workspace_root": workspace_root,
                "session_id": request.session_id,
                "original_task": grounded_task,
                "intent": grounded_task.intent
            }
            
            # The grounded task already has the diagnostics in the correct format
            # from the grounding system - no need to transform again!
            
            try:
                # Run the execution engine (Analyze → Plan → Propose)
                execution_result = await execution_engine.execute_task(grounded_task, execution_context)
                
                if execution_result.success and execution_result.proposal:
                    _store_pending_execution(
                        execution_result.task_id,
                        execution_result,
                        execution_context,
                        request.session_id
                    )
                    # Convert execution result to plan format expected by frontend
                    plan = {
                        "goal": f"Fix {grounded_task.inputs.get('total_count', 0)} problems in workspace",
                        "intent": grounded_task.intent,
                        "scope": grounded_task.scope,
                        "target": grounded_task.target,
                        "confidence": grounded_task.confidence,
                        "requires_approval": grounded_task.requires_approval,
                        
                        # Phase 4.3: Rich execution details
                        "execution": {
                            "task_id": execution_result.task_id,
                            "status": execution_result.status,
                            "analysis": execution_result.analysis.model_dump() if execution_result.analysis else None,
                            "plan": execution_result.plan.model_dump() if execution_result.plan else None,
                            "proposal": execution_result.proposal.model_dump() if execution_result.proposal else None,
                        },
                        
                        "diagnostics": {
                            "total_count": execution_result.analysis.total_issues if execution_result.analysis else grounded_task.inputs.get("total_count", 0),
                            "error_count": execution_result.analysis.error_count if execution_result.analysis else grounded_task.inputs.get("error_count", 0),
                            "warning_count": execution_result.analysis.warning_count if execution_result.analysis else grounded_task.inputs.get("warning_count", 0),
                            "fixable_count": execution_result.analysis.fixable_count if execution_result.analysis else 0,
                            "affected_files": execution_result.analysis.affected_files if execution_result.analysis else grounded_task.inputs.get("affected_files", [])
                        },
                        
                        "steps": [
                            {
                                "id": step.step_id,
                                "title": step.title,
                                "description": step.description,
                                "status": "ready" if i == 0 else "pending"
                            }
                            for i, step in enumerate(execution_result.plan.steps if execution_result.plan else [])
                        ]
                    }
                    
                    reasoning = execution_result.final_report
                    
                else:
                    # Execution failed - fall back to basic plan
                    plan = {
                        "goal": f"Fix {grounded_task.inputs.get('total_count', 0)} problems in workspace",
                        "intent": grounded_task.intent,
                        "scope": grounded_task.scope,
                        "target": grounded_task.target,
                        "confidence": grounded_task.confidence,
                        "requires_approval": grounded_task.requires_approval,
                        "diagnostics": {
                            "total_count": grounded_task.inputs.get("total_count", 0),
                            "error_count": grounded_task.inputs.get("error_count", 0),
                            "warning_count": grounded_task.inputs.get("warning_count", 0),
                            "affected_files": grounded_task.inputs.get("affected_files", [])
                        },
                        "steps": [
                            {
                                "id": "basic_analysis",
                                "title": "Analyze workspace diagnostics",
                                "description": "Gather and categorize diagnostic issues",
                                "status": "ready"
                            }
                        ]
                    }
                    reasoning = f"Task grounded successfully but execution analysis failed: {execution_result.final_report}"
            
            except Exception as e:
                logger.error(f"Execution engine failed: {e}", exc_info=True)
                
                # Fall back to basic plan if execution fails
                plan = {
                    "goal": f"Fix {grounded_task.inputs.get('total_count', 0)} problems in workspace",
                    "intent": grounded_task.intent,
                    "scope": grounded_task.scope,
                    "target": grounded_task.target,
                    "confidence": grounded_task.confidence,
                    "requires_approval": grounded_task.requires_approval,
                    "diagnostics": {
                        "total_count": grounded_task.inputs.get("total_count", 0),
                        "error_count": grounded_task.inputs.get("error_count", 0),
                        "warning_count": grounded_task.inputs.get("warning_count", 0),
                        "affected_files": grounded_task.inputs.get("affected_files", [])
                    },
                    "steps": [
                        {
                            "id": "fallback_analysis",
                            "title": "Basic diagnostic analysis",
                            "description": "Fallback to basic diagnostic handling",
                            "status": "ready"
                        }
                    ]
                }
                reasoning = f"Successfully grounded task but execution failed: {str(e)}"
                execution_result = None

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Analysis completed successfully in {duration_ms}ms")
            
            return AnalyzeProblemsResponse(
                success=True,
                plan=plan,
                reasoning=reasoning,
                session_id=request.session_id,
                grounding_result=grounding_result.model_dump(),
                execution_result=execution_result.model_dump() if execution_result else None
            )
        
        else:
            # Unknown grounding result type
            return AnalyzeProblemsResponse(
                success=False,
                error=f"Unknown grounding result type: {grounding_result.type}",
                session_id=request.session_id,
                reasoning="Internal error in task grounding system"
            )
    
    except Exception as e:
        logger.error(f"Error in analyze_problems: {e}", exc_info=True)
        return AnalyzeProblemsResponse(
            success=False,
            error=f"Internal server error: {str(e)}",
            session_id=request.session_id,
            reasoning="Exception occurred during analysis"
        )


def _map_severity_to_string(severity: int) -> str:
    """Map VS Code diagnostic severity integer to string"""
    severity_map = {
        1: "error",     # DiagnosticSeverity.Error
        2: "warning",   # DiagnosticSeverity.Warning  
        3: "info",      # DiagnosticSeverity.Information
        4: "info"       # DiagnosticSeverity.Hint -> map to info
    }
    return severity_map.get(severity, "error")


@router.get("/health")
async def health_check():
    """Health check for the analyze endpoint"""
    return {
        "status": "healthy",
        "service": "navi-analyze",
        "capabilities": ["FIX_PROBLEMS", "DEPLOY"],
        "phase": "4.3",
        "execution_engine": "enabled"
    }


@router.post("/execute-task", response_model=ExecuteTaskResponse)
async def execute_task(request: ExecuteTaskRequest) -> ExecuteTaskResponse:
    """
    Execute an approved task.
    
    This endpoint handles the "Apply Changes" action from the approval workflow.
    It takes a task_id from a previous analyze-problems call and applies the 
    proposed changes if the user approved them.
    """
    logger.info(f"Execute task request: task_id='{request.task_id}', approved={request.approved}")
    
    if not request.approved:
        _pop_pending_execution(request.task_id, request.session_id)
        return ExecuteTaskResponse(
            success=False,
            task_id=request.task_id,
            status="cancelled",
            error="User did not approve the task execution",
            session_id=request.session_id
        )
    
    pending = _pop_pending_execution(request.task_id, request.session_id)
    if not pending:
        return ExecuteTaskResponse(
            success=False,
            task_id=request.task_id,
            status="failed",
            error="No pending execution found for this task. Please re-run analysis.",
            session_id=request.session_id
        )

    workspace_root = request.workspace_root or pending.context.get("workspace_root") or ""
    pending.context["workspace_root"] = workspace_root
    pending.context.setdefault("intent", pending.execution_result.task_id.split('-')[-1])

    logger.info(f"Task {request.task_id} approved for execution")

    try:
        execution_engine = _build_execution_engine(workspace_root)
        execution_result = await execution_engine.execute_approved_changes(
            pending.execution_result,
            pending.context
        )

        return ExecuteTaskResponse(
            success=execution_result.success,
            task_id=execution_result.task_id,
            status=execution_result.status.value if isinstance(execution_result.status, ExecutionStatus) else str(execution_result.status),
            execution_result=execution_result.model_dump(),
            error=None if execution_result.success else execution_result.final_report,
            session_id=request.session_id
        )
    except Exception as exc:
        logger.error(f"Execute task failed: {exc}", exc_info=True)
        return ExecuteTaskResponse(
            success=False,
            task_id=request.task_id,
            status="failed",
            error=f"Execution failed: {exc}",
            session_id=request.session_id
        )
