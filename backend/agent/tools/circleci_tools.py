"""
CircleCI tools for NAVI agent.

Provides tools to query and manage CircleCI pipelines, workflows, and jobs.
"""

from typing import Any, Dict, Optional
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


async def list_circleci_pipelines(
    context: Dict[str, Any],
    project_slug: str,
    branch: Optional[str] = None,
    max_results: int = 10,
) -> ToolResult:
    """List CircleCI pipelines for a project."""
    from backend.services.circleci_service import CircleCIService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "circleci")

        if not connection:
            return ToolResult(
                output="CircleCI is not connected. Please connect your CircleCI account first.",
                sources=[],
            )

        pipelines = await CircleCIService.list_pipelines(
            db=db,
            connection=connection,
            project_slug=project_slug,
            branch=branch,
            max_results=max_results,
        )

        if not pipelines:
            return ToolResult(
                output=f"No pipelines found for {project_slug}.",
                sources=[],
            )

        lines = [f"Found {len(pipelines)} pipeline(s) for `{project_slug}`:\n"]
        sources = []

        state_emoji = {
            "created": "🔵",
            "errored": "❌",
            "setup-pending": "🔄",
            "setup": "🔄",
            "pending": "🔄",
        }

        for p in pipelines:
            num = p.get("number", "")
            state = p.get("state", "unknown")
            trigger = p.get("trigger_type", "")
            created = p.get("created_at", "")[:10] if p.get("created_at") else ""
            url = p.get("url", "")

            emoji = state_emoji.get(state, "❓")
            lines.append(f"- {emoji} **Pipeline #{num}**")
            lines.append(f"  - State: {state}")
            lines.append(f"  - Trigger: {trigger} | Created: {created}")
            if url:
                lines.append(f"  - [View Pipeline]({url})")
            lines.append("")

            if url:
                sources.append(
                    {
                        "type": "circleci_pipeline",
                        "name": f"Pipeline #{num}",
                        "url": url,
                    }
                )

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_circleci_pipelines.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def get_circleci_pipeline_status(
    context: Dict[str, Any],
    pipeline_id: str,
) -> ToolResult:
    """Get status of a CircleCI pipeline with its workflows."""
    from backend.services.circleci_service import CircleCIService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "circleci")

        if not connection:
            return ToolResult(output="CircleCI is not connected.", sources=[])

        pipeline = await CircleCIService.get_pipeline_status(
            db=db, connection=connection, pipeline_id=pipeline_id
        )

        if not pipeline:
            return ToolResult(
                output=f"Could not find pipeline {pipeline_id}.",
                sources=[],
            )

        num = pipeline.get("number", "")
        state = pipeline.get("state", "unknown")
        workflows = pipeline.get("workflows", [])

        state_emoji = {"created": "✅", "errored": "❌"}.get(state, "🔄")

        lines = [
            f"# {state_emoji} Pipeline #{num}\n",
            f"**State:** {state}",
            f"**Trigger:** {pipeline.get('trigger_type', 'unknown')}",
            f"**Created:** {pipeline.get('created_at', '')[:10] if pipeline.get('created_at') else 'Unknown'}",
        ]

        if workflows:
            lines.append("\n**Workflows:**")
            status_emoji = {
                "success": "✅",
                "running": "🔄",
                "not_run": "⏸️",
                "failed": "❌",
                "error": "❌",
                "failing": "❌",
                "on_hold": "⏸️",
                "canceled": "🚫",
            }
            for wf in workflows:
                wf_name = wf.get("name", "Unknown")
                wf_status = wf.get("status", "unknown")
                emoji = status_emoji.get(wf_status, "❓")
                lines.append(f"  - {emoji} **{wf_name}**: {wf_status}")

        return ToolResult(output="\n".join(lines), sources=[])

    except Exception as e:
        logger.error("get_circleci_pipeline_status.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def trigger_circleci_pipeline(
    context: Dict[str, Any],
    project_slug: str,
    branch: str = "main",
) -> ToolResult:
    """Trigger a CircleCI pipeline (requires approval)."""
    from backend.services.circleci_service import CircleCIService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "circleci")

        if not connection:
            return ToolResult(output="CircleCI is not connected.", sources=[])

        result = await CircleCIService.write_item(
            db=db,
            connection=connection,
            operation="trigger_pipeline",
            project_slug=project_slug,
            branch=branch,
        )

        if result.get("success"):
            pipeline_num = result.get("number", "")
            url = f"https://app.circleci.com/pipelines/{project_slug}/{pipeline_num}"
            return ToolResult(
                output=f"Pipeline #{pipeline_num} triggered on branch `{branch}`.\n\n[View Pipeline]({url})",
                sources=[
                    {
                        "type": "circleci_pipeline",
                        "name": f"Pipeline #{pipeline_num}",
                        "url": url,
                    }
                ],
            )
        else:
            return ToolResult(output="Failed to trigger pipeline.", sources=[])

    except Exception as e:
        logger.error("trigger_circleci_pipeline.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def get_circleci_job_status(
    context: Dict[str, Any],
    project_slug: str,
    job_number: int,
) -> ToolResult:
    """Get status of a CircleCI job."""
    from backend.services.circleci_service import CircleCIService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "circleci")

        if not connection:
            return ToolResult(output="CircleCI is not connected.", sources=[])

        job = await CircleCIService.get_job_status(
            db=db,
            connection=connection,
            project_slug=project_slug,
            job_number=job_number,
        )

        if not job:
            return ToolResult(
                output=f"Could not find job {job_number} in {project_slug}.",
                sources=[],
            )

        name = job.get("name", "Unknown")
        status = job.get("status", "unknown")
        duration = job.get("duration")

        status_emoji = {
            "success": "✅",
            "running": "🔄",
            "failed": "❌",
            "canceled": "🚫",
        }.get(status, "❓")

        lines = [
            f"# {status_emoji} Job: {name}\n",
            f"**Job Number:** {job_number}",
            f"**Status:** {status}",
        ]

        if duration:
            lines.append(f"**Duration:** {duration}s")

        return ToolResult(output="\n".join(lines), sources=[])

    except Exception as e:
        logger.error("get_circleci_job_status.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


CIRCLECI_TOOLS = {
    "circleci.list_pipelines": list_circleci_pipelines,
    "circleci.get_pipeline_status": get_circleci_pipeline_status,
    "circleci.trigger_pipeline": trigger_circleci_pipeline,
    "circleci.get_job_status": get_circleci_job_status,
}
