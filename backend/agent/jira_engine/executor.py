"""
Jira Executor

Executes Jira workflow operations (transitions, comments, updates).
This is the "action layer" that actually modifies Jira state.
"""

import logging
from typing import Dict, Any, Optional

from backend.integrations.jira_client import JiraClient

logger = logging.getLogger(__name__)


async def start_jira_work(user_id: str, issue_id: str) -> Dict[str, Any]:
    """
    Start working on a Jira issue.
    
    This will:
    1. Transition issue to "In Progress" (if possible)
    2. Add a comment indicating NAVI assistance started
    3. Update user state to track active Jira
    
    Args:
        user_id: User starting work
        issue_id: Jira issue key (e.g., "SCRUM-123")
        
    Returns:
        Dict with:
        {
            "success": True/False,
            "message": "Started work on SCRUM-123",
            "issue_id": "SCRUM-123",
            "new_status": "In Progress"
        }
    """
    
    try:
        logger.info(f"User {user_id} starting work on {issue_id}")
        
        jira = JiraClient()
        
        # Try to transition to In Progress
        try:
            await jira.transition_issue(issue_id, "In Progress")
            logger.info(f"Transitioned {issue_id} to In Progress")
        except Exception as e:
            logger.warning(f"Could not transition {issue_id} to In Progress: {e}")
            # Continue anyway - maybe already in progress
        
        # Add comment
        comment = f"🤖 NAVI started assisting on this task for {user_id}"
        try:
            await jira.add_comment(issue_id, comment)
            logger.info(f"Added start comment to {issue_id}")
        except Exception as e:
            logger.warning(f"Could not add comment to {issue_id}: {e}")
        
        return {
            "success": True,
            "message": f"🚀 Started work on {issue_id}",
            "issue_id": issue_id,
            "new_status": "In Progress"
        }
        
    except Exception as e:
        logger.error(f"Error starting work on {issue_id}: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to start work on {issue_id}: {str(e)}",
            "issue_id": issue_id,
            "error": str(e)
        }


async def complete_jira_work(
    user_id: str,
    issue_id: str,
    summary: Optional[str] = None
) -> Dict[str, Any]:
    """
    Complete work on a Jira issue.
    
    This will:
    1. Transition issue to "Done" (if possible)
    2. Add completion comment with optional summary
    3. Clear active Jira from user state
    
    Args:
        user_id: User completing work
        issue_id: Jira issue key
        summary: Optional summary of work done
        
    Returns:
        Dict with success status and message
    """
    
    try:
        logger.info(f"User {user_id} completing work on {issue_id}")
        
        jira = JiraClient()
        
        # Try to transition to Done
        try:
            await jira.transition_issue(issue_id, "Done")
            logger.info(f"Transitioned {issue_id} to Done")
        except Exception as e:
            logger.warning(f"Could not transition {issue_id} to Done: {e}")
        
        # Add completion comment
        comment_lines = [f"✅ Task completed by NAVI for {user_id}"]
        if summary:
            comment_lines.append("")
            comment_lines.append("**Summary of work:**")
            comment_lines.append(summary)
        
        comment = "\n".join(comment_lines)
        
        try:
            await jira.add_comment(issue_id, comment)
            logger.info(f"Added completion comment to {issue_id}")
        except Exception as e:
            logger.warning(f"Could not add comment to {issue_id}: {e}")
        
        return {
            "success": True,
            "message": f"✅ Completed {issue_id}",
            "issue_id": issue_id,
            "new_status": "Done"
        }
        
    except Exception as e:
        logger.error(f"Error completing work on {issue_id}: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to complete {issue_id}: {str(e)}",
            "issue_id": issue_id,
            "error": str(e)
        }


async def add_jira_comment(
    user_id: str,
    issue_id: str,
    comment: str
) -> Dict[str, Any]:
    """
    Add a comment to a Jira issue.
    
    Args:
        user_id: User adding comment
        issue_id: Jira issue key
        comment: Comment text
        
    Returns:
        Dict with success status
    """
    
    try:
        logger.info(f"Adding comment to {issue_id} from {user_id}")
        
        jira = JiraClient()
        await jira.add_comment(issue_id, comment)
        
        return {
            "success": True,
            "message": f"Added comment to {issue_id}",
            "issue_id": issue_id
        }
        
    except Exception as e:
        logger.error(f"Error adding comment to {issue_id}: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to add comment: {str(e)}",
            "issue_id": issue_id,
            "error": str(e)
        }


async def transition_jira(
    user_id: str,
    issue_id: str,
    target_status: str,
    comment: Optional[str] = None
) -> Dict[str, Any]:
    """
    Transition a Jira issue to a new status.
    
    Args:
        user_id: User performing transition
        issue_id: Jira issue key
        target_status: Target status (e.g., "In Progress", "Done", "In Review")
        comment: Optional comment to add with transition
        
    Returns:
        Dict with success status
    """
    
    try:
        logger.info(f"Transitioning {issue_id} to {target_status} for {user_id}")
        
        jira = JiraClient()
        await jira.transition_issue(issue_id, target_status)
        
        # Add comment if provided
        if comment:
            try:
                await jira.add_comment(issue_id, comment)
            except Exception as e:
                logger.warning(f"Could not add comment during transition: {e}")
        
        return {
            "success": True,
            "message": f"Transitioned {issue_id} to {target_status}",
            "issue_id": issue_id,
            "new_status": target_status
        }
        
    except Exception as e:
        logger.error(f"Error transitioning {issue_id}: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to transition: {str(e)}",
            "issue_id": issue_id,
            "error": str(e)
        }


async def update_jira_description(
    user_id: str,
    issue_id: str,
    new_description: str
) -> Dict[str, Any]:
    """
    Update a Jira issue's description.
    
    Useful when NAVI helps improve poorly-written Jira tickets.
    
    Args:
        user_id: User performing update
        issue_id: Jira issue key
        new_description: New description text
        
    Returns:
        Dict with success status
    """
    
    try:
        logger.info(f"Updating description for {issue_id}")
        
        jira = JiraClient()
        await jira.update_issue(issue_id, {"description": new_description})
        
        return {
            "success": True,
            "message": f"Updated description for {issue_id}",
            "issue_id": issue_id
        }
        
    except Exception as e:
        logger.error(f"Error updating description for {issue_id}: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to update description: {str(e)}",
            "issue_id": issue_id,
            "error": str(e)
        }


async def suggest_story_points(
    issue: Dict[str, Any],
    enriched_context: Dict[str, Any]
) -> int:
    """
    Suggest story points for a Jira issue based on complexity analysis.
    
    Args:
        issue: Normalized Jira issue
        enriched_context: Enriched organizational context
        
    Returns:
        Suggested story points (1, 2, 3, 5, 8, 13, etc.)
    """
    
    try:
        # Simple heuristic based on:
        # - Description length
        # - Number of acceptance criteria
        # - Number of related artifacts
        # - Labels/complexity indicators
        
        complexity_score = 0
        
        # Description complexity
        desc_length = len(issue.get("description", ""))
        if desc_length > 1000:
            complexity_score += 5
        elif desc_length > 500:
            complexity_score += 3
        elif desc_length > 200:
            complexity_score += 2
        else:
            complexity_score += 1
        
        # Related artifacts (indicates cross-cutting concern)
        total_artifacts = (
            len(enriched_context.get("slack", [])) +
            len(enriched_context.get("docs", [])) +
            len(enriched_context.get("prs", []))
        )
        
        if total_artifacts > 10:
            complexity_score += 3
        elif total_artifacts > 5:
            complexity_score += 2
        elif total_artifacts > 0:
            complexity_score += 1
        
        # Priority
        priority = issue.get("priority", "")
        if priority in ["Critical", "Blocker"]:
            complexity_score += 2
        
        # Map to Fibonacci scale
        if complexity_score <= 2:
            return 1
        elif complexity_score <= 4:
            return 2
        elif complexity_score <= 6:
            return 3
        elif complexity_score <= 8:
            return 5
        elif complexity_score <= 10:
            return 8
        else:
            return 13
        
    except Exception as e:
        logger.error(f"Error suggesting story points: {e}")
        return 3  # Default to 3
