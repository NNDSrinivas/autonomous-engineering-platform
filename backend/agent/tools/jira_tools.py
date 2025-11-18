"""
Jira Tools

Operations for interacting with Jira issues.
These integrate with existing Jira client.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def jira_fetch_issue(user_id: str, issue_key: str) -> Dict[str, Any]:
    """
    Fetch Jira issue details.
    
    This is a read-only operation (no approval needed).
    
    Args:
        user_id: User ID executing the tool
        issue_key: Jira issue key (e.g., SCRUM-123)
    
    Returns:
        {
            "success": bool,
            "message": str,
            "issue": Dict with issue details,
            "error": str (if failure)
        }
    """
    logger.info(f"[TOOL:jira_fetch] user={user_id}, issue={issue_key}")
    
    try:
        # Import Jira client
        from backend.integrations.jira_client import get_jira_client
        
        # Get issue
        jira_client = await get_jira_client()
        if not jira_client:
            return {
                "success": False,
                "message": "❌ Jira not configured",
                "error": "Jira client not available"
            }
        
        issue = await jira_client.get_issue(issue_key)
        
        if not issue:
            return {
                "success": False,
                "message": f"❌ Issue not found: {issue_key}",
                "error": "Issue not found"
            }
        
        # Format response
        summary = issue.get("fields", {}).get("summary", "No summary")
        status = issue.get("fields", {}).get("status", {}).get("name", "Unknown")
        assignee = issue.get("fields", {}).get("assignee", {}).get("displayName", "Unassigned")
        
        message = f"""📋 **{issue_key}**: {summary}
**Status:** {status}
**Assignee:** {assignee}"""
        
        return {
            "success": True,
            "message": message,
            "issue": issue,
            "issue_key": issue_key
        }
    
    except Exception as e:
        logger.error(f"[TOOL:jira_fetch] Error: {e}")
        return {
            "success": False,
            "message": f"❌ Error fetching Jira issue: {str(e)}",
            "error": str(e)
        }


async def jira_comment(user_id: str, issue_key: str, comment: str) -> Dict[str, Any]:
    """
    Add comment to Jira issue.
    
    This is a write operation (requires user approval).
    
    Args:
        user_id: User ID executing the tool
        issue_key: Jira issue key (e.g., SCRUM-123)
        comment: Comment text
    
    Returns:
        {
            "success": bool,
            "message": str,
            "error": str (if failure)
        }
    """
    logger.info(f"[TOOL:jira_comment] user={user_id}, issue={issue_key}")
    
    try:
        from backend.integrations.jira_client import get_jira_client
        
        jira_client = await get_jira_client()
        if not jira_client:
            return {
                "success": False,
                "message": "❌ Jira not configured",
                "error": "Jira client not available"
            }
        
        await jira_client.add_comment(issue_key, comment)
        
        return {
            "success": True,
            "message": f"💬 Added comment to {issue_key}",
            "issue_key": issue_key
        }
    
    except Exception as e:
        logger.error(f"[TOOL:jira_comment] Error: {e}")
        return {
            "success": False,
            "message": f"❌ Error adding comment: {str(e)}",
            "error": str(e)
        }


async def jira_transition(user_id: str, issue_key: str, status: str) -> Dict[str, Any]:
    """
    Transition Jira issue to new status.
    
    This is a write operation (requires user approval).
    
    Args:
        user_id: User ID executing the tool
        issue_key: Jira issue key (e.g., SCRUM-123)
        status: Target status (e.g., "In Progress", "Done")
    
    Returns:
        {
            "success": bool,
            "message": str,
            "error": str (if failure)
        }
    """
    logger.info(f"[TOOL:jira_transition] user={user_id}, issue={issue_key}, status={status}")
    
    try:
        from backend.integrations.jira_client import get_jira_client
        
        jira_client = await get_jira_client()
        if not jira_client:
            return {
                "success": False,
                "message": "❌ Jira not configured",
                "error": "Jira client not available"
            }
        
        await jira_client.transition_issue(issue_key, status)
        
        return {
            "success": True,
            "message": f"🔄 Moved {issue_key} to '{status}'",
            "issue_key": issue_key,
            "new_status": status
        }
    
    except Exception as e:
        logger.error(f"[TOOL:jira_transition] Error: {e}")
        return {
            "success": False,
            "message": f"❌ Error transitioning issue: {str(e)}",
            "error": str(e)
        }
