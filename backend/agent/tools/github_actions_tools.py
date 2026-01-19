"""
GitHub Actions tools for NAVI agent.

Provides tools to query and manage GitHub Actions workflows and runs.
"""

from typing import Any, Dict, Optional
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


async def list_github_actions_workflows(
    context: Dict[str, Any],
    owner: str,
    repo: str,
) -> ToolResult:
    """List GitHub Actions workflows for a repository."""
    from backend.services.github_actions_service import GitHubActionsService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "github")

        if not connection:
            return ToolResult(
                output="GitHub is not connected. Please connect your GitHub account first.",
                sources=[],
            )

        workflows = await GitHubActionsService.list_workflows(
            db=db, connection=connection, owner=owner, repo=repo
        )

        if not workflows:
            return ToolResult(
                output=f"No workflows found in {owner}/{repo}.",
                sources=[],
            )

        lines = [f"Found {len(workflows)} workflow(s) in `{owner}/{repo}`:\n"]
        sources = []

        state_emoji = {
            "active": "✅",
            "disabled_fork": "⏸️",
            "disabled_inactivity": "⏸️",
            "disabled_manually": "⏸️",
        }

        for wf in workflows:
            name = wf.get("name", "Untitled")
            state = wf.get("state", "unknown")
            path = wf.get("path", "")
            url = wf.get("url", "")

            emoji = state_emoji.get(state, "❓")
            lines.append(f"- {emoji} **{name}**")
            lines.append(f"  - State: {state}")
            if path:
                lines.append(f"  - Path: `{path}`")
            if url:
                lines.append(f"  - [View Workflow]({url})")
            lines.append("")

            if url:
                sources.append({"type": "github_workflow", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_github_actions_workflows.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def list_github_actions_runs(
    context: Dict[str, Any],
    owner: str,
    repo: str,
    workflow_id: Optional[str] = None,
    status: Optional[str] = None,
    max_results: int = 10,
) -> ToolResult:
    """List recent GitHub Actions workflow runs."""
    from backend.services.github_actions_service import GitHubActionsService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "github")

        if not connection:
            return ToolResult(output="GitHub is not connected.", sources=[])

        runs = await GitHubActionsService.list_workflow_runs(
            db=db,
            connection=connection,
            owner=owner,
            repo=repo,
            workflow_id=workflow_id,
            status=status,
            max_results=max_results,
        )

        if not runs:
            return ToolResult(
                output=f"No workflow runs found in {owner}/{repo}.",
                sources=[],
            )

        lines = [f"Found {len(runs)} workflow run(s) in `{owner}/{repo}`:\n"]
        sources = []

        conclusion_emoji = {
            "success": "✅",
            "failure": "❌",
            "cancelled": "🚫",
            "skipped": "⏭️",
            "timed_out": "⏰",
            "pending": "🔄",
        }

        for run in runs:
            name = run.get("name", "Untitled")
            run_number = run.get("run_number", "")
            status_val = run.get("status", "unknown")
            conclusion = run.get("conclusion", "pending")
            branch = run.get("branch", "")
            actor = run.get("actor", "")
            url = run.get("url", "")

            emoji = conclusion_emoji.get(conclusion, "❓")
            lines.append(f"- {emoji} **{name}** #{run_number}")
            lines.append(f"  - Status: {status_val} / {conclusion}")
            lines.append(f"  - Branch: `{branch}` | By: {actor}")
            if url:
                lines.append(f"  - [View Run]({url})")
            lines.append("")

            if url:
                sources.append({"type": "github_run", "name": f"{name} #{run_number}", "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_github_actions_runs.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def get_github_actions_run_status(
    context: Dict[str, Any],
    owner: str,
    repo: str,
    run_id: int,
) -> ToolResult:
    """Get status of a specific GitHub Actions workflow run."""
    from backend.services.github_actions_service import GitHubActionsService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "github")

        if not connection:
            return ToolResult(output="GitHub is not connected.", sources=[])

        run = await GitHubActionsService.get_run_status(
            db=db, connection=connection, owner=owner, repo=repo, run_id=run_id
        )

        if not run:
            return ToolResult(
                output=f"Could not find workflow run {run_id} in {owner}/{repo}.",
                sources=[],
            )

        name = run.get("name", "Untitled")
        run_number = run.get("run_number", "")
        status = run.get("status", "unknown")
        conclusion = run.get("conclusion", "pending")
        branch = run.get("branch", "")
        event = run.get("event", "")
        actor = run.get("actor", "")
        url = run.get("url", "")
        created_at = run.get("created_at", "")[:10] if run.get("created_at") else ""

        conclusion_emoji = {
            "success": "✅",
            "failure": "❌",
            "cancelled": "🚫",
            "pending": "🔄",
        }
        emoji = conclusion_emoji.get(conclusion, "❓")

        lines = [
            f"# {emoji} {name} #{run_number}\n",
            f"**Status:** {status}",
            f"**Conclusion:** {conclusion}",
            f"**Branch:** `{branch}`",
            f"**Event:** {event}",
            f"**Triggered by:** {actor}",
            f"**Created:** {created_at}",
        ]

        if url:
            lines.append(f"\n[View in GitHub]({url})")

        sources = []
        if url:
            sources.append({"type": "github_run", "name": f"{name} #{run_number}", "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("get_github_actions_run_status.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def trigger_github_actions_workflow(
    context: Dict[str, Any],
    owner: str,
    repo: str,
    workflow_id: str,
    ref: str = "main",
) -> ToolResult:
    """Trigger a GitHub Actions workflow (requires approval)."""
    from backend.services.github_actions_service import GitHubActionsService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "github")

        if not connection:
            return ToolResult(output="GitHub is not connected.", sources=[])

        result = await GitHubActionsService.write_item(
            db=db,
            connection=connection,
            operation="trigger_workflow",
            owner=owner,
            repo=repo,
            workflow_id=workflow_id,
            ref=ref,
        )

        if result.get("success"):
            url = f"https://github.com/{owner}/{repo}/actions"
            return ToolResult(
                output=f"Workflow triggered successfully on branch `{ref}`.\n\n[View Actions]({url})",
                sources=[{"type": "github_actions", "name": f"{owner}/{repo}", "url": url}],
            )
        else:
            return ToolResult(output="Failed to trigger workflow.", sources=[])

    except Exception as e:
        logger.error("trigger_github_actions_workflow.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


GITHUB_ACTIONS_TOOLS = {
    "github_actions.list_workflows": list_github_actions_workflows,
    "github_actions.list_runs": list_github_actions_runs,
    "github_actions.get_run_status": get_github_actions_run_status,
    "github_actions.trigger_workflow": trigger_github_actions_workflow,
}
