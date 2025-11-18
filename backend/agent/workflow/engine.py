"""
Workflow Engine Orchestrator

Central routing system that executes workflow steps based on current state.
This is the "conductor" that coordinates all autonomous workflow execution.
"""

import logging
from typing import Dict, Any, Optional

from .state import WorkflowState, WorkflowStatus
from .steps import (
    step_analysis,
    step_locate_files,
    step_propose_diffs,
    step_apply_diffs,
    step_run_tests,
    step_commit_changes,
    step_push_branch,
    step_create_pr,
    step_update_jira,
    step_done
)

logger = logging.getLogger(__name__)

# Global workflow storage (in production, use database or Redis)
ACTIVE_WORKFLOWS: Dict[str, WorkflowState] = {}


async def run_workflow_step(
    state: WorkflowState,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute the current workflow step.
    
    This is the central routing function that determines which step to execute
    based on the workflow's current state.
    
    Args:
        state: Current workflow state
        context: Execution context (user_id, workspace, tools, etc.)
        
    Returns:
        Dict with step execution result:
        {
            "success": True/False,
            "message": "User-facing message",
            "data": {...},
            "actions": ["continue", "approve", "cancel", etc.]
        }
    """
    
    try:
        logger.info(f"Executing workflow step: {state.current_step} for {state.issue_id}")
        
        # Route to appropriate step handler
        step = state.current_step
        
        if step == "analysis":
            result = await step_analysis(
                state=state,
                issue=state.issue,
                enriched_context=state.enriched_context,
                workspace_context=context.get("workspace_context")
            )
        
        elif step == "locate_files":
            result = await step_locate_files(
                state=state,
                user_id=context["user_id"],
                workspace_root=context["workspace_root"]
            )
        
        elif step == "propose_diffs":
            result = await step_propose_diffs(
                state=state,
                user_id=context["user_id"]
            )
        
        elif step == "apply_diffs":
            result = await step_apply_diffs(
                state=state,
                user_id=context["user_id"]
            )
        
        elif step == "run_tests":
            result = await step_run_tests(
                state=state,
                user_id=context["user_id"],
                cwd=context["workspace_root"]
            )
        
        elif step == "commit_changes":
            result = await step_commit_changes(
                state=state,
                user_id=context["user_id"],
                cwd=context["workspace_root"]
            )
        
        elif step == "push_branch":
            result = await step_push_branch(
                state=state,
                user_id=context["user_id"],
                cwd=context["workspace_root"]
            )
        
        elif step == "create_pr":
            result = await step_create_pr(
                state=state,
                user_id=context["user_id"]
            )
        
        elif step == "update_jira":
            result = await step_update_jira(
                state=state,
                user_id=context["user_id"]
            )
        
        elif step == "done":
            result = await step_done(state)
        
        else:
            raise ValueError(f"Unknown workflow step: {step}")
        
        # Record step completion
        state.record_step_completion(step, result)
        
        # Check if step requires approval
        if "approve" in result.get("actions", []) or "approve all" in result.get("actions", []):
            state.set_waiting_approval({
                "step": step,
                "result": result
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error executing workflow step {state.current_step}: {e}", exc_info=True)
        state.record_error(str(e))
        
        return {
            "success": False,
            "message": f"❌ Step failed: {str(e)}",
            "error": str(e),
            "actions": ["retry", "cancel"]
        }


async def create_workflow(
    issue_id: str,
    user_id: str,
    issue: Dict[str, Any],
    enriched_context: Dict[str, Any]
) -> WorkflowState:
    """
    Create a new autonomous workflow.
    
    Args:
        issue_id: Jira issue key
        user_id: User ID
        issue: Parsed Jira issue
        enriched_context: Enriched organizational context
        
    Returns:
        New WorkflowState instance
    """
    
    logger.info(f"Creating workflow for {issue_id} by {user_id}")
    
    # Create state
    state = WorkflowState(issue_id, user_id)
    state.issue = issue
    state.enriched_context = enriched_context
    state.status = WorkflowStatus.IN_PROGRESS
    
    # Store in global registry
    ACTIVE_WORKFLOWS[issue_id] = state
    
    return state


async def resume_workflow(issue_id: str) -> Optional[WorkflowState]:
    """
    Resume an existing workflow.
    
    Args:
        issue_id: Jira issue key
        
    Returns:
        WorkflowState instance or None if not found
    """
    
    state = ACTIVE_WORKFLOWS.get(issue_id)
    
    if state:
        logger.info(f"Resuming workflow for {issue_id} at step {state.current_step}")
    else:
        logger.warning(f"No active workflow found for {issue_id}")
    
    return state


async def approve_workflow_step(issue_id: str) -> Dict[str, Any]:
    """
    Approve the current workflow step and advance.
    
    Args:
        issue_id: Jira issue key
        
    Returns:
        Dict with approval result
    """
    
    state = ACTIVE_WORKFLOWS.get(issue_id)
    
    if not state:
        return {
            "success": False,
            "message": f"No active workflow found for {issue_id}",
            "error": "Workflow not found"
        }
    
    if state.status != WorkflowStatus.WAITING_APPROVAL:
        return {
            "success": False,
            "message": f"Workflow is not waiting for approval (status: {state.status.value})",
            "error": "Invalid state"
        }
    
    # Approve and advance
    state.approve()
    state.next_step()
    
    logger.info(f"Approved workflow {issue_id}, advanced to step {state.current_step}")
    
    return {
        "success": True,
        "message": f"Approved! Moving to step: {state.current_step}",
        "data": {"next_step": state.current_step}
    }


async def cancel_workflow(issue_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
    """
    Cancel an active workflow.
    
    Args:
        issue_id: Jira issue key
        reason: Optional cancellation reason
        
    Returns:
        Dict with cancellation result
    """
    
    state = ACTIVE_WORKFLOWS.get(issue_id)
    
    if not state:
        return {
            "success": False,
            "message": f"No active workflow found for {issue_id}",
            "error": "Workflow not found"
        }
    
    state.cancel()
    
    if reason:
        state.record_error(f"Cancelled: {reason}")
    
    # Remove from active workflows
    del ACTIVE_WORKFLOWS[issue_id]
    
    logger.info(f"Cancelled workflow {issue_id}: {reason}")
    
    return {
        "success": True,
        "message": f"Workflow cancelled: {reason or 'User requested'}",
        "data": {"final_state": state.to_dict()}
    }


def get_workflow_status(issue_id: str) -> Optional[Dict[str, Any]]:
    """
    Get current status of a workflow.
    
    Args:
        issue_id: Jira issue key
        
    Returns:
        Dict with workflow status or None
    """
    
    state = ACTIVE_WORKFLOWS.get(issue_id)
    
    if not state:
        return None
    
    return {
        "issue_id": issue_id,
        "status": state.status.value,
        "current_step": state.current_step,
        "progress": state.get_progress_percentage(),
        "started_at": state.started_at.isoformat(),
        "updated_at": state.updated_at.isoformat(),
        "errors": state.errors,
        "branch": state.branch_name,
        "pr_url": state.pr_url
    }


def list_active_workflows(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all active workflows, optionally filtered by user.
    
    Args:
        user_id: Optional user ID filter
        
    Returns:
        List of workflow status dicts
    """
    
    workflows = []
    
    for issue_id, state in ACTIVE_WORKFLOWS.items():
        if user_id and state.user_id != user_id:
            continue
        
        workflows.append({
            "issue_id": issue_id,
            "user_id": state.user_id,
            "status": state.status.value,
            "current_step": state.current_step,
            "progress": state.get_progress_percentage(),
            "summary": state.get_progress_summary()
        })
    
    return workflows
