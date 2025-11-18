"""
Workflow Runner

High-level interface for starting and managing autonomous workflows.
This is the entry point for autonomous task execution.
"""

import logging
from typing import Dict, Any, Optional

from .state import WorkflowState, WorkflowStatus
from .engine import (
    run_workflow_step,
    create_workflow,
    resume_workflow,
    approve_workflow_step,
    cancel_workflow
)
from backend.agent.jira_engine.parser import parse_jira_issue
from backend.agent.jira_engine.enricher import enrich_jira_context
from backend.agent.jira_engine.executor import start_jira_work

logger = logging.getLogger(__name__)


class WorkflowRunner:
    """
    High-level workflow execution manager.
    
    Provides simple interface for starting, resuming, and managing
    autonomous engineering workflows.
    """
    
    def __init__(self, user_id: str, workspace_root: str):
        """
        Initialize workflow runner.
        
        Args:
            user_id: User ID
            workspace_root: Workspace root directory
        """
        self.user_id = user_id
        self.workspace_root = workspace_root
    
    async def start_workflow(
        self,
        issue: Dict[str, Any],
        org_context: Dict[str, Any],
        workspace_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Start a new autonomous workflow for a Jira issue.
        
        Args:
            issue: Raw Jira issue from API
            org_context: Full organizational context
            workspace_context: Optional workspace/codebase context
            
        Returns:
            Dict with workflow start result
        """
        
        try:
            # Parse Jira issue
            parsed_issue = parse_jira_issue(issue)
            issue_id = parsed_issue["id"]
            
            logger.info(f"Starting autonomous workflow for {issue_id}")
            
            # Enrich with organizational context
            enriched_context = await enrich_jira_context(parsed_issue, org_context)
            
            # Update Jira status to In Progress
            await start_jira_work(self.user_id, issue_id)
            
            # Create workflow state
            state = await create_workflow(
                issue_id=issue_id,
                user_id=self.user_id,
                issue=parsed_issue,
                enriched_context=enriched_context
            )
            
            # Execute first step (analysis)
            context = {
                "user_id": self.user_id,
                "workspace_root": self.workspace_root,
                "workspace_context": workspace_context
            }
            
            result = await run_workflow_step(state, context)
            
            return {
                "success": True,
                "message": f"🚀 Started autonomous workflow for {issue_id}",
                "workflow_id": issue_id,
                "current_step": state.current_step,
                "step_result": result
            }
            
        except Exception as e:
            logger.error(f"Error starting workflow: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to start workflow: {str(e)}",
                "error": str(e)
            }
    
    async def continue_workflow(self, issue_id: str) -> Dict[str, Any]:
        """
        Continue an existing workflow to the next step.
        
        Args:
            issue_id: Jira issue key
            
        Returns:
            Dict with continuation result
        """
        
        try:
            # Resume workflow
            state = await resume_workflow(issue_id)
            
            if not state:
                return {
                    "success": False,
                    "message": f"No active workflow found for {issue_id}",
                    "error": "Workflow not found"
                }
            
            # Approve if waiting
            if state.status == WorkflowStatus.WAITING_APPROVAL:
                await approve_workflow_step(issue_id)
            
            # Advance to next step
            state.next_step()
            
            # Execute next step
            context = {
                "user_id": self.user_id,
                "workspace_root": self.workspace_root
            }
            
            result = await run_workflow_step(state, context)
            
            return {
                "success": True,
                "message": f"Continuing workflow for {issue_id}",
                "current_step": state.current_step,
                "step_result": result
            }
            
        except Exception as e:
            logger.error(f"Error continuing workflow: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to continue workflow: {str(e)}",
                "error": str(e)
            }
    
    async def approve_and_continue(self, issue_id: str) -> Dict[str, Any]:
        """
        Approve current step and continue to next step.
        
        Args:
            issue_id: Jira issue key
            
        Returns:
            Dict with approval and continuation result
        """
        
        try:
            # Approve
            approval_result = await approve_workflow_step(issue_id)
            
            if not approval_result["success"]:
                return approval_result
            
            # Continue to next step
            return await self.continue_workflow(issue_id)
            
        except Exception as e:
            logger.error(f"Error approving workflow: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to approve workflow: {str(e)}",
                "error": str(e)
            }
    
    async def cancel(self, issue_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Cancel an active workflow.
        
        Args:
            issue_id: Jira issue key
            reason: Optional cancellation reason
            
        Returns:
            Dict with cancellation result
        """
        
        return await cancel_workflow(issue_id, reason)


async def start_autonomous_task(
    user_id: str,
    issue_id: str,
    jira_client: Any,
    org_context: Dict[str, Any],
    workspace_root: str
) -> Dict[str, Any]:
    """
    Convenience function to start autonomous task execution.
    
    This is the main entry point for triggering autonomous workflows
    from the agent loop or API endpoints.
    
    Args:
        user_id: User ID
        issue_id: Jira issue key (e.g., "SCRUM-123")
        jira_client: Jira client instance
        org_context: Organizational context
        workspace_root: Workspace root directory
        
    Returns:
        Dict with workflow start result
        
    Example:
        result = await start_autonomous_task(
            user_id="user@example.com",
            issue_id="SCRUM-123",
            jira_client=jira,
            org_context=org_ctx,
            workspace_root="/path/to/workspace"
        )
    """
    
    try:
        logger.info(f"Starting autonomous task for {issue_id}")
        
        # Fetch Jira issue
        issue = await jira_client.get_issue(issue_id)
        
        if not issue:
            return {
                "success": False,
                "message": f"Could not fetch Jira issue {issue_id}",
                "error": "Issue not found"
            }
        
        # Create runner
        runner = WorkflowRunner(user_id, workspace_root)
        
        # Start workflow
        result = await runner.start_workflow(issue, org_context)
        
        return result
        
    except Exception as e:
        logger.error(f"Error starting autonomous task: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to start autonomous task: {str(e)}",
            "error": str(e)
        }


async def continue_autonomous_task(user_id: str, issue_id: str, workspace_root: str) -> Dict[str, Any]:
    """
    Continue an existing autonomous workflow.
    
    Args:
        user_id: User ID
        issue_id: Jira issue key
        workspace_root: Workspace root directory
        
    Returns:
        Dict with continuation result
    """
    
    runner = WorkflowRunner(user_id, workspace_root)
    return await runner.continue_workflow(issue_id)


async def approve_autonomous_task(user_id: str, issue_id: str, workspace_root: str) -> Dict[str, Any]:
    """
    Approve and continue autonomous workflow.
    
    Args:
        user_id: User ID
        issue_id: Jira issue key
        workspace_root: Workspace root directory
        
    Returns:
        Dict with approval result
    """
    
    runner = WorkflowRunner(user_id, workspace_root)
    return await runner.approve_and_continue(issue_id)


async def cancel_autonomous_task(
    user_id: str,
    issue_id: str,
    workspace_root: str,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    Cancel an autonomous workflow.
    
    Args:
        user_id: User ID
        issue_id: Jira issue key
        workspace_root: Workspace root directory
        reason: Optional cancellation reason
        
    Returns:
        Dict with cancellation result
    """
    
    runner = WorkflowRunner(user_id, workspace_root)
    return await runner.cancel(issue_id, reason)
