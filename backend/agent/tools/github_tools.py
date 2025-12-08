"""
GitHub Tools

Operations for interacting with GitHub API.
These integrate with existing GitHub client.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def github_create_branch(user_id: str, branch_name: str, base_branch: str = "main") -> Dict[str, Any]:
    """
    Create new GitHub branch.
    
    This is a write operation (requires user approval).
    
    Args:
        user_id: User ID executing the tool
        branch_name: Name for new branch
        base_branch: Base branch to branch from (default: main)
    
    Returns:
        {
            "success": bool,
            "message": str,
            "branch": str,
            "error": str (if failure)
        }
    """
    logger.info(f"[TOOL:github_branch] user={user_id}, branch={branch_name}, base={base_branch}")
    
    try:
        from backend.integrations.github.service import GitHubService
        
        import os; gh_client = GitHubService(token=os.getenv("GITHUB_TOKEN", ""))
        if not gh_client:
            return {
                "success": False,
                "message": "❌ GitHub not configured",
                "error": "GitHub client not available"
            }
        
        await gh_client.create_branch(branch_name, base_branch)
        
        return {
            "success": True,
            "message": f"🌿 Created branch `{branch_name}` from `{base_branch}`",
            "branch": branch_name,
            "base_branch": base_branch
        }
    
    except Exception as e:
        logger.error(f"[TOOL:github_branch] Error: {e}")
        return {
            "success": False,
            "message": f"❌ Error creating branch: {str(e)}",
            "error": str(e)
        }


async def github_create_pr(
    user_id: str,
    branch: str,
    title: str,
    body: str,
    base_branch: str = "main"
) -> Dict[str, Any]:
    """
    Create GitHub pull request.
    
    This is a write operation (requires user approval).
    
    Args:
        user_id: User ID executing the tool
        branch: Source branch
        title: PR title
        body: PR description
        base_branch: Target branch (default: main)
    
    Returns:
        {
            "success": bool,
            "message": str,
            "pr_url": str,
            "pr_number": int,
            "error": str (if failure)
        }
    """
    logger.info(f"[TOOL:github_pr] user={user_id}, branch={branch}, title={title}")
    
    try:
        from backend.integrations.github.service import GitHubService
        
        import os; gh_client = GitHubService(token=os.getenv("GITHUB_TOKEN", ""))
        if not gh_client:
            return {
                "success": False,
                "message": "❌ GitHub not configured",
                "error": "GitHub client not available"
            }
        
        pr = await gh_client.create_pull_request(
            head=branch,
            base=base_branch,
            title=title,
            body=body
        )
        
        pr_url = pr.get("html_url", "")
        pr_number = pr.get("number", 0)
        
        return {
            "success": True,
            "message": f"🔀 Created PR #{pr_number}: {title}\n{pr_url}",
            "pr_url": pr_url,
            "pr_number": pr_number,
            "branch": branch
        }
    
    except Exception as e:
        logger.error(f"[TOOL:github_pr] Error: {e}")
        return {
            "success": False,
            "message": f"❌ Error creating PR: {str(e)}",
            "error": str(e)
        }
