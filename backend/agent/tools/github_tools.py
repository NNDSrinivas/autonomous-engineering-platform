"""
GitHub Tools for NAVI Agent

Full operations for interacting with GitHub API:
- Create/manage branches
- Create/manage pull requests
- Create/list/comment on issues
- Review pull requests
- List repositories and commits

These integrate with the existing GitHub client.
"""

import logging
import os
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


def _get_github_client():
    """Get GitHub client or return None if not configured."""
    try:
        from backend.integrations.github.service import GitHubService

        token = os.getenv("GITHUB_TOKEN", "")
        if not token:
            return None
        return GitHubService(token=token)
    except Exception:
        return None


async def github_create_branch(
    user_id: str, branch_name: str, base_branch: str = "main"
) -> Dict[str, Any]:
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
    logger.info(
        f"[TOOL:github_branch] user={user_id}, branch={branch_name}, base={base_branch}"
    )

    try:
        from backend.integrations.github.service import GitHubService

        import os

        gh_client = GitHubService(token=os.getenv("GITHUB_TOKEN", ""))
        if not gh_client:
            return {
                "success": False,
                "message": "❌ GitHub not configured",
                "error": "GitHub client not available",
            }

        await gh_client.create_branch(branch_name, base_branch)

        return {
            "success": True,
            "message": f"🌿 Created branch `{branch_name}` from `{base_branch}`",
            "branch": branch_name,
            "base_branch": base_branch,
        }

    except Exception as e:
        logger.error(f"[TOOL:github_branch] Error: {e}")
        return {
            "success": False,
            "message": f"❌ Error creating branch: {str(e)}",
            "error": str(e),
        }


async def github_create_pr(
    user_id: str, branch: str, title: str, body: str, base_branch: str = "main"
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

        import os

        gh_client = GitHubService(token=os.getenv("GITHUB_TOKEN", ""))
        if not gh_client:
            return {
                "success": False,
                "message": "❌ GitHub not configured",
                "error": "GitHub client not available",
            }

        pr = await gh_client.create_pull_request(
            head=branch, base=base_branch, title=title, body=body
        )

        pr_url = pr.get("html_url", "")
        pr_number = pr.get("number", 0)

        return {
            "success": True,
            "message": f"🔀 Created PR #{pr_number}: {title}\n{pr_url}",
            "pr_url": pr_url,
            "pr_number": pr_number,
            "branch": branch,
        }

    except Exception as e:
        logger.error(f"[TOOL:github_pr] Error: {e}")
        return {
            "success": False,
            "message": f"❌ Error creating PR: {str(e)}",
            "error": str(e),
        }


async def github_create_issue(
    user_id: str,
    repo: str,
    title: str,
    body: Optional[str] = None,
    labels: Optional[List[str]] = None,
    assignees: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Create a new GitHub issue.

    Args:
        user_id: User ID executing the tool
        repo: Repository in format 'owner/repo'
        title: Issue title
        body: Issue description (supports markdown)
        labels: List of labels to add
        assignees: List of GitHub usernames to assign

    Returns:
        {
            "success": bool,
            "message": str,
            "issue_url": str,
            "issue_number": int,
            "error": str (if failure)
        }
    """
    logger.info(
        f"[TOOL:github_create_issue] user={user_id}, repo={repo}, title={title}"
    )

    try:
        gh_client = _get_github_client()
        if not gh_client:
            return {
                "success": False,
                "message": "❌ GitHub not configured. Set GITHUB_TOKEN environment variable.",
                "error": "GitHub not configured",
            }

        issue_data = {
            "title": title,
            "body": body or "",
        }
        if labels:
            issue_data["labels"] = labels
        if assignees:
            issue_data["assignees"] = assignees

        issue = await gh_client.create_issue(repo, **issue_data)

        return {
            "success": True,
            "message": f"📋 Created issue #{issue['number']}: {title}\n{issue['html_url']}",
            "issue_url": issue.get("html_url", ""),
            "issue_number": issue.get("number", 0),
        }

    except Exception as e:
        logger.error(f"[TOOL:github_create_issue] Error: {e}")
        return {
            "success": False,
            "message": f"❌ Error creating issue: {str(e)}",
            "error": str(e),
        }


async def github_list_issues(
    user_id: str,
    repo: str,
    state: str = "open",
    labels: Optional[List[str]] = None,
    assignee: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    List GitHub issues in a repository.

    Args:
        user_id: User ID executing the tool
        repo: Repository in format 'owner/repo'
        state: Issue state ('open', 'closed', 'all')
        labels: Filter by labels
        assignee: Filter by assignee username
        limit: Maximum issues to return

    Returns:
        {
            "success": bool,
            "message": str,
            "issues": List of issue info,
            "error": str (if failure)
        }
    """
    logger.info(f"[TOOL:github_list_issues] user={user_id}, repo={repo}, state={state}")

    try:
        gh_client = _get_github_client()
        if not gh_client:
            return {
                "success": False,
                "message": "❌ GitHub not configured",
                "error": "GitHub not configured",
            }

        params = {"state": state, "per_page": limit}
        if labels:
            params["labels"] = ",".join(labels)
        if assignee:
            params["assignee"] = assignee

        issues_list = await gh_client.list_issues(repo, **params)

        issues = [
            {
                "number": issue["number"],
                "title": issue["title"],
                "state": issue["state"],
                "url": issue["html_url"],
                "labels": [label["name"] for label in issue.get("labels", [])],
                "assignees": [a["login"] for a in issue.get("assignees", [])],
            }
            for issue in issues_list[:limit]
        ]

        output = f"Found {len(issues)} issues in {repo}:\n\n"
        for issue in issues:
            status = "🟢" if issue["state"] == "open" else "🔴"
            output += f"• {status} #{issue['number']}: {issue['title']}\n"
            if issue["labels"]:
                output += f"  Labels: {', '.join(issue['labels'])}\n"
            output += f"  {issue['url']}\n\n"

        return {
            "success": True,
            "message": output,
            "issues": issues,
        }

    except Exception as e:
        logger.error(f"[TOOL:github_list_issues] Error: {e}")
        return {
            "success": False,
            "message": f"❌ Error listing issues: {str(e)}",
            "error": str(e),
        }


async def github_add_issue_comment(
    user_id: str,
    repo: str,
    issue_number: int,
    body: str,
) -> Dict[str, Any]:
    """
    Add a comment to a GitHub issue.

    Args:
        user_id: User ID executing the tool
        repo: Repository in format 'owner/repo'
        issue_number: Issue number
        body: Comment body (supports markdown)

    Returns:
        {
            "success": bool,
            "message": str,
            "comment_url": str,
            "error": str (if failure)
        }
    """
    logger.info(
        f"[TOOL:github_add_issue_comment] user={user_id}, repo={repo}, issue={issue_number}"
    )

    try:
        gh_client = _get_github_client()
        if not gh_client:
            return {
                "success": False,
                "message": "❌ GitHub not configured",
                "error": "GitHub not configured",
            }

        comment = await gh_client.add_issue_comment(repo, issue_number, body)

        return {
            "success": True,
            "message": f"💬 Added comment to issue #{issue_number}",
            "comment_url": comment.get("html_url", ""),
        }

    except Exception as e:
        logger.error(f"[TOOL:github_add_issue_comment] Error: {e}")
        return {
            "success": False,
            "message": f"❌ Error adding comment: {str(e)}",
            "error": str(e),
        }


async def github_add_pr_review(
    user_id: str,
    repo: str,
    pr_number: int,
    body: str,
    event: str = "COMMENT",
) -> Dict[str, Any]:
    """
    Add a review to a GitHub pull request.

    Args:
        user_id: User ID executing the tool
        repo: Repository in format 'owner/repo'
        pr_number: PR number
        body: Review body (supports markdown)
        event: Review event ('COMMENT', 'APPROVE', 'REQUEST_CHANGES')

    Returns:
        {
            "success": bool,
            "message": str,
            "review_url": str,
            "error": str (if failure)
        }
    """
    logger.info(
        f"[TOOL:github_add_pr_review] user={user_id}, repo={repo}, pr={pr_number}, event={event}"
    )

    try:
        gh_client = _get_github_client()
        if not gh_client:
            return {
                "success": False,
                "message": "❌ GitHub not configured",
                "error": "GitHub not configured",
            }

        review = await gh_client.create_pr_review(repo, pr_number, body, event)

        event_icons = {
            "COMMENT": "💬",
            "APPROVE": "✅",
            "REQUEST_CHANGES": "🔄",
        }
        icon = event_icons.get(event, "💬")

        return {
            "success": True,
            "message": f"{icon} Added {event.lower().replace('_', ' ')} review to PR #{pr_number}",
            "review_url": review.get("html_url", ""),
        }

    except Exception as e:
        logger.error(f"[TOOL:github_add_pr_review] Error: {e}")
        return {
            "success": False,
            "message": f"❌ Error adding review: {str(e)}",
            "error": str(e),
        }


async def github_list_prs(
    user_id: str,
    repo: str,
    state: str = "open",
    head: Optional[str] = None,
    base: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    List GitHub pull requests in a repository.

    Args:
        user_id: User ID executing the tool
        repo: Repository in format 'owner/repo'
        state: PR state ('open', 'closed', 'all')
        head: Filter by head branch
        base: Filter by base branch
        limit: Maximum PRs to return

    Returns:
        {
            "success": bool,
            "message": str,
            "prs": List of PR info,
            "error": str (if failure)
        }
    """
    logger.info(f"[TOOL:github_list_prs] user={user_id}, repo={repo}, state={state}")

    try:
        gh_client = _get_github_client()
        if not gh_client:
            return {
                "success": False,
                "message": "❌ GitHub not configured",
                "error": "GitHub not configured",
            }

        params = {"state": state, "per_page": limit}
        if head:
            params["head"] = head
        if base:
            params["base"] = base

        prs_list = await gh_client.list_pull_requests(repo, **params)

        prs = [
            {
                "number": pr["number"],
                "title": pr["title"],
                "state": pr["state"],
                "url": pr["html_url"],
                "head": pr["head"]["ref"],
                "base": pr["base"]["ref"],
                "author": pr["user"]["login"],
                "draft": pr.get("draft", False),
            }
            for pr in prs_list[:limit]
        ]

        output = f"Found {len(prs)} pull requests in {repo}:\n\n"
        for pr in prs:
            status = "🟢" if pr["state"] == "open" else "🟣"
            draft = " (draft)" if pr["draft"] else ""
            output += f"• {status} #{pr['number']}: {pr['title']}{draft}\n"
            output += f"  {pr['head']} → {pr['base']} by @{pr['author']}\n"
            output += f"  {pr['url']}\n\n"

        return {
            "success": True,
            "message": output,
            "prs": prs,
        }

    except Exception as e:
        logger.error(f"[TOOL:github_list_prs] Error: {e}")
        return {
            "success": False,
            "message": f"❌ Error listing PRs: {str(e)}",
            "error": str(e),
        }


async def github_merge_pr(
    user_id: str,
    repo: str,
    pr_number: int,
    commit_title: Optional[str] = None,
    commit_message: Optional[str] = None,
    merge_method: str = "merge",
) -> Dict[str, Any]:
    """
    Merge a GitHub pull request.

    Args:
        user_id: User ID executing the tool
        repo: Repository in format 'owner/repo'
        pr_number: PR number to merge
        commit_title: Custom merge commit title
        commit_message: Custom merge commit message
        merge_method: Merge method ('merge', 'squash', 'rebase')

    Returns:
        {
            "success": bool,
            "message": str,
            "sha": str (merge commit SHA),
            "error": str (if failure)
        }
    """
    logger.info(
        f"[TOOL:github_merge_pr] user={user_id}, repo={repo}, pr={pr_number}, method={merge_method}"
    )

    try:
        gh_client = _get_github_client()
        if not gh_client:
            return {
                "success": False,
                "message": "❌ GitHub not configured",
                "error": "GitHub not configured",
            }

        merge_data = {"merge_method": merge_method}
        if commit_title:
            merge_data["commit_title"] = commit_title
        if commit_message:
            merge_data["commit_message"] = commit_message

        result = await gh_client.merge_pull_request(repo, pr_number, **merge_data)

        return {
            "success": True,
            "message": f"✅ Merged PR #{pr_number} using {merge_method}",
            "sha": result.get("sha", ""),
            "merged": result.get("merged", True),
        }

    except Exception as e:
        logger.error(f"[TOOL:github_merge_pr] Error: {e}")
        return {
            "success": False,
            "message": f"❌ Error merging PR: {str(e)}",
            "error": str(e),
        }


# Tool registry
GITHUB_TOOLS = {
    "github_create_branch": github_create_branch,
    "github_create_pr": github_create_pr,
    "github_create_issue": github_create_issue,
    "github_list_issues": github_list_issues,
    "github_add_issue_comment": github_add_issue_comment,
    "github_add_pr_review": github_add_pr_review,
    "github_list_prs": github_list_prs,
    "github_merge_pr": github_merge_pr,
}
