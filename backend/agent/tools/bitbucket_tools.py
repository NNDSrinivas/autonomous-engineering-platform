"""
Bitbucket tools for NAVI agent.

Provides tools to query and manage Bitbucket repositories, PRs, and pipelines.
"""

from typing import Any, Dict, Optional
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


async def list_my_bitbucket_prs(
    context: Dict[str, Any],
    status: Optional[str] = None,
    max_results: int = 20,
) -> ToolResult:
    """
    List pull requests authored by the current user.

    Args:
        context: Context with user_id and connection info
        status: Filter by status (OPEN, MERGED, DECLINED)
        max_results: Maximum results to return

    Returns:
        ToolResult with PR list and sources
    """
    from backend.services.bitbucket_service import BitbucketService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(
            output="Error: No user ID in context. Please sign in first.",
            sources=[],
        )

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "bitbucket")

        if not connection:
            return ToolResult(
                output="Bitbucket is not connected. Please connect your Bitbucket account first.",
                sources=[],
            )

        prs = await BitbucketService.list_my_prs(
            db=db,
            connection=connection,
            status=status,
            max_results=max_results,
        )

        if not prs:
            status_text = f" with status '{status}'" if status else ""
            return ToolResult(
                output=f"No pull requests found{status_text}.",
                sources=[],
            )

        # Build output
        lines = [f"Found {len(prs)} Bitbucket pull request(s):\n"]
        sources = []

        for pr in prs:
            pr_id = pr.get("id")
            title = pr.get("title", "Untitled")
            state = pr.get("state", "UNKNOWN")
            url = pr.get("url", "")
            workspace = pr.get("workspace", "")
            repo_slug = pr.get("repo_slug", "")
            source_branch = pr.get("source_branch", "")
            dest_branch = pr.get("destination_branch", "")

            lines.append(f"- **PR #{pr_id}**: {title}")
            lines.append(f"  - Status: {state}")
            lines.append(f"  - Repo: {workspace}/{repo_slug}")
            lines.append(f"  - Branch: {source_branch} → {dest_branch}")
            if url:
                lines.append(f"  - [View PR]({url})")
            lines.append("")

            if url:
                sources.append(
                    {
                        "type": "bitbucket_pr",
                        "name": f"PR #{pr_id}: {title}",
                        "url": url,
                    }
                )

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_my_bitbucket_prs.error", error=str(e))
        return ToolResult(
            output=f"Error listing Bitbucket PRs: {e}",
            sources=[],
        )


async def list_bitbucket_repos(
    context: Dict[str, Any],
    max_results: int = 20,
) -> ToolResult:
    """
    List Bitbucket repositories the user has access to.

    Args:
        context: Context with user_id and connection info
        max_results: Maximum results to return

    Returns:
        ToolResult with repository list and sources
    """
    from backend.services.bitbucket_service import BitbucketService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(
            output="Error: No user ID in context. Please sign in first.",
            sources=[],
        )

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "bitbucket")

        if not connection:
            return ToolResult(
                output="Bitbucket is not connected. Please connect your Bitbucket account first.",
                sources=[],
            )

        repos = await BitbucketService.list_repos(
            db=db,
            connection=connection,
            max_results=max_results,
        )

        if not repos:
            return ToolResult(
                output="No Bitbucket repositories found.",
                sources=[],
            )

        # Build output
        lines = [f"Found {len(repos)} Bitbucket repository(ies):\n"]
        sources = []

        for repo in repos:
            full_name = repo.get("full_name", "")
            description = repo.get("description", "No description")
            url = repo.get("url", "")
            language = repo.get("language", "Unknown")
            is_private = "Private" if repo.get("is_private") else "Public"

            lines.append(f"- **{full_name}**")
            if description:
                lines.append(f"  - {description}")
            lines.append(f"  - Language: {language} | {is_private}")
            if url:
                lines.append(f"  - [View Repository]({url})")
            lines.append("")

            if url:
                sources.append(
                    {
                        "type": "bitbucket_repo",
                        "name": full_name,
                        "url": url,
                    }
                )

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_bitbucket_repos.error", error=str(e))
        return ToolResult(
            output=f"Error listing Bitbucket repositories: {e}",
            sources=[],
        )


async def get_bitbucket_pipeline_status(
    context: Dict[str, Any],
    workspace: Optional[str] = None,
    repo_slug: Optional[str] = None,
    max_results: int = 10,
) -> ToolResult:
    """
    Get recent pipeline statuses for a Bitbucket repository.

    Args:
        context: Context with user_id and connection info
        workspace: Workspace slug (optional, will use first repo if not provided)
        repo_slug: Repository slug (optional)
        max_results: Maximum results to return

    Returns:
        ToolResult with pipeline status and sources
    """
    from backend.services.bitbucket_service import BitbucketService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(
            output="Error: No user ID in context. Please sign in first.",
            sources=[],
        )

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "bitbucket")

        if not connection:
            return ToolResult(
                output="Bitbucket is not connected. Please connect your Bitbucket account first.",
                sources=[],
            )

        # If no workspace/repo provided, get from first repo
        if not workspace or not repo_slug:
            repos = await BitbucketService.list_repos(
                db=db,
                connection=connection,
                max_results=1,
            )
            if repos:
                workspace = repos[0].get("workspace")
                repo_slug = repos[0].get("slug")
            else:
                return ToolResult(
                    output="No Bitbucket repositories found to check pipelines.",
                    sources=[],
                )

        pipelines = await BitbucketService.get_pipeline_status(
            db=db,
            connection=connection,
            workspace=workspace,
            repo_slug=repo_slug,
            max_results=max_results,
        )

        if not pipelines:
            return ToolResult(
                output=f"No pipelines found for {workspace}/{repo_slug}.",
                sources=[],
            )

        # Build output
        lines = [f"Pipeline status for **{workspace}/{repo_slug}**:\n"]
        sources = []

        for pipeline in pipelines:
            build_num = pipeline.get("build_number", "?")
            state = pipeline.get("state", "unknown")
            result = pipeline.get("result")
            target = pipeline.get("target", "unknown")
            creator = pipeline.get("creator", "unknown")
            duration = pipeline.get("duration_in_seconds")

            status_emoji = (
                "⏳"
                if state == "IN_PROGRESS"
                else ("✅" if result == "SUCCESSFUL" else "❌" if result else "⚪")
            )

            lines.append(f"- {status_emoji} **Build #{build_num}**")
            lines.append(f"  - State: {state}" + (f" ({result})" if result else ""))
            lines.append(f"  - Branch: {target}")
            lines.append(f"  - Creator: {creator}")
            if duration:
                mins = duration // 60
                secs = duration % 60
                lines.append(f"  - Duration: {mins}m {secs}s")
            lines.append("")

        repo_url = f"https://bitbucket.org/{workspace}/{repo_slug}/pipelines"
        sources.append(
            {
                "type": "bitbucket_pipelines",
                "name": f"Pipelines - {workspace}/{repo_slug}",
                "url": repo_url,
            }
        )

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("get_bitbucket_pipeline_status.error", error=str(e))
        return ToolResult(
            output=f"Error getting pipeline status: {e}",
            sources=[],
        )


async def add_bitbucket_pr_comment(
    context: Dict[str, Any],
    workspace: str,
    repo_slug: str,
    pr_id: int,
    content: str,
    approve: bool = False,
) -> ToolResult:
    """
    Add a comment to a Bitbucket pull request.

    Args:
        context: Context with user_id and connection info
        workspace: Workspace slug
        repo_slug: Repository slug
        pr_id: Pull request ID
        content: Comment content
        approve: Whether to actually execute (requires user approval)

    Returns:
        ToolResult with operation result
    """
    from backend.services.bitbucket_service import BitbucketService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(
            output="Error: No user ID in context. Please sign in first.",
            sources=[],
        )

    if not approve:
        # Return preview for approval
        return ToolResult(
            output=f"**Preview: Add comment to PR #{pr_id}**\n\n"
            f"Repository: {workspace}/{repo_slug}\n"
            f"Comment:\n```\n{content}\n```\n\n"
            f"Please approve this action to add the comment.",
            sources=[],
        )

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "bitbucket")

        if not connection:
            return ToolResult(
                output="Bitbucket is not connected. Please connect your Bitbucket account first.",
                sources=[],
            )

        result = await BitbucketService.write_item(
            db=db,
            connection=connection,
            action="add_comment",
            data={
                "workspace": workspace,
                "repo_slug": repo_slug,
                "pr_id": pr_id,
                "content": content,
            },
        )

        if result.success:
            return ToolResult(
                output=f"Comment added successfully to PR #{pr_id}.",
                sources=[
                    {
                        "type": "bitbucket_comment",
                        "name": f"Comment on PR #{pr_id}",
                        "url": result.url
                        or f"https://bitbucket.org/{workspace}/{repo_slug}/pull-requests/{pr_id}",
                    }
                ],
            )
        else:
            return ToolResult(
                output=f"Failed to add comment: {result.error}",
                sources=[],
            )

    except Exception as e:
        logger.error("add_bitbucket_pr_comment.error", error=str(e))
        return ToolResult(
            output=f"Error adding comment: {e}",
            sources=[],
        )


# Tool registry for the dispatcher
BITBUCKET_TOOLS = {
    "bitbucket.list_my_prs": list_my_bitbucket_prs,
    "bitbucket.list_repos": list_bitbucket_repos,
    "bitbucket.get_pipeline_status": get_bitbucket_pipeline_status,
    "bitbucket.add_comment": add_bitbucket_pr_comment,
}
