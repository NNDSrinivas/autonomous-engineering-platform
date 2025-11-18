"""
Tool Executor - Execute Agent Tools

Central hub for executing all NAVI tools.
Routes tool requests to specific tool implementations.

Tools are organized by category:
- File operations: read_file, create_file, edit_file, apply_diff, search_repo
- Command execution: run_command
- Jira operations: jira_fetch_issue, jira_comment, jira_transition
- GitHub operations: github_create_branch, github_create_pr

All write operations require user approval (enforced by planner).
"""

import logging
from typing import Dict, Any, Optional

from backend.agent.tools import (
    read_file, create_file, edit_file, apply_diff, search_repo,
    run_command,
    jira_fetch_issue, jira_comment, jira_transition,
    github_create_branch, github_create_pr
)

logger = logging.getLogger(__name__)


# Tool registry: maps tool names to implementations
TOOL_REGISTRY = {
    # File operations
    "read_file": read_file,
    "create_file": create_file,
    "edit_file": edit_file,
    "apply_diff": apply_diff,
    "search_repo": search_repo,
    
    # Command execution
    "run_command": run_command,
    
    # Jira operations
    "jira_fetch_issue": jira_fetch_issue,
    "jira_comment": jira_comment,
    "jira_transition": jira_transition,
    
    # GitHub operations
    "github_create_branch": github_create_branch,
    "github_create_pr": github_create_pr,
}


async def execute_tool(
    user_id: str,
    tool_name: str,
    tool_args: Dict[str, Any],
    db = None
) -> Dict[str, Any]:
    """
    Execute tool and return result.
    
    Args:
        user_id: User ID executing the tool
        tool_name: Name of tool to execute (e.g., "create_file")
        tool_args: Arguments to pass to tool
        db: Database session (optional)
    
    Returns:
        {
            "success": bool,
            "message": str,
            "data": Dict (tool-specific output),
            "error": str (if failure)
        }
    """
    logger.info(f"[TOOL_EXECUTOR] Executing {tool_name} for user={user_id}")
    
    try:
        # Check if tool exists
        if tool_name not in TOOL_REGISTRY:
            available_tools = ", ".join(sorted(TOOL_REGISTRY.keys())[:10])
            return {
                "success": False,
                "message": f"❌ Unknown tool: `{tool_name}`\nAvailable tools: {available_tools}...",
                "error": f"Tool not found: {tool_name}"
            }
        
        # Get tool function
        tool_func = TOOL_REGISTRY[tool_name]
        
        # Execute tool with user_id + args
        result = await tool_func(user_id=user_id, **tool_args)
        
        # Ensure result has required fields
        if not isinstance(result, dict):
            return {
                "success": False,
                "message": f"❌ Tool {tool_name} returned invalid result",
                "error": "Invalid tool result format"
            }
        
        result.setdefault("success", True)
        result.setdefault("message", "Tool executed successfully")
        
        logger.info(f"[TOOL_EXECUTOR] {tool_name} completed: success={result['success']}")
        return result
    
    except TypeError as e:
        # Missing or incorrect arguments
        logger.error(f"[TOOL_EXECUTOR] Argument error in {tool_name}: {e}")
        return {
            "success": False,
            "message": f"❌ Invalid arguments for {tool_name}: {str(e)}",
            "error": f"Argument error: {str(e)}"
        }
    
    except Exception as e:
        # Unexpected error
        logger.error(f"[TOOL_EXECUTOR] Error executing {tool_name}: {e}")
        return {
            "success": False,
            "message": f"❌ Error executing {tool_name}: {str(e)}",
            "error": str(e)
        }


def get_available_tools() -> Dict[str, str]:
    """
    Get list of all available tools with descriptions.
    
    Returns:
        Dict mapping tool name to description
    """
    return {
        "read_file": "Read file contents",
        "create_file": "Create new file",
        "edit_file": "Replace entire file content",
        "apply_diff": "Apply unified diff to file",
        "search_repo": "Search workspace for text",
        "run_command": "Execute safe terminal command",
        "jira_fetch_issue": "Get Jira issue details",
        "jira_comment": "Add comment to Jira issue",
        "jira_transition": "Change Jira issue status",
        "github_create_branch": "Create new Git branch",
        "github_create_pr": "Create pull request",
    }


def is_write_operation(tool_name: str) -> bool:
    """
    Check if tool performs write operations.
    
    Write operations always require user approval.
    
    Returns:
        True if write operation, False if read-only
    """
    read_only_tools = {
        "read_file",
        "search_repo",
        "jira_fetch_issue"
    }
    
    return tool_name not in read_only_tools

