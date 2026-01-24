"""
Vercel tools for NAVI agent.

Provides tools to query and manage Vercel projects and deployments.
"""

from typing import Any, Dict, Optional
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


async def list_vercel_projects(
    context: Dict[str, Any],
    max_results: int = 20,
) -> ToolResult:
    """List Vercel projects."""
    from backend.services.vercel_service import VercelService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "vercel")

        if not connection:
            return ToolResult(
                output="Vercel is not connected. Please connect your Vercel account first.",
                sources=[],
            )

        projects = await VercelService.list_projects(
            db=db, connection=connection, max_results=max_results
        )

        if not projects:
            return ToolResult(output="No Vercel projects found.", sources=[])

        lines = [f"Found {len(projects)} Vercel project(s):\n"]
        sources = []

        for proj in projects:
            name = proj.get("name", "Untitled")
            framework = proj.get("framework", "")
            url = proj.get("url", "")

            lines.append(f"- **{name}**")
            if framework:
                lines.append(f"  - Framework: {framework}")
            if url:
                lines.append(f"  - [View Project]({url})")
            lines.append("")

            if url:
                sources.append({"type": "vercel_project", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_vercel_projects.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def list_vercel_deployments(
    context: Dict[str, Any],
    project_id: Optional[str] = None,
    state: Optional[str] = None,
    max_results: int = 10,
) -> ToolResult:
    """List Vercel deployments."""
    from backend.services.vercel_service import VercelService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "vercel")

        if not connection:
            return ToolResult(output="Vercel is not connected.", sources=[])

        deployments = await VercelService.list_deployments(
            db=db,
            connection=connection,
            project_id=project_id,
            state=state,
            max_results=max_results,
        )

        if not deployments:
            return ToolResult(output="No Vercel deployments found.", sources=[])

        lines = [f"Found {len(deployments)} deployment(s):\n"]
        sources = []

        state_emoji = {
            "READY": "✅",
            "BUILDING": "🔄",
            "QUEUED": "⏳",
            "ERROR": "❌",
            "CANCELED": "🚫",
            "INITIALIZING": "🔄",
        }

        for d in deployments:
            name = d.get("name", "Untitled")
            deploy_state = d.get("state", "unknown")
            target = d.get("target", "preview")
            url = d.get("url", "")

            emoji = state_emoji.get(deploy_state, "❓")
            lines.append(f"- {emoji} **{name}** ({target})")
            lines.append(f"  - State: {deploy_state}")
            if url:
                lines.append(f"  - URL: [{url}]({url})")
            lines.append("")

            if url:
                sources.append({"type": "vercel_deployment", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_vercel_deployments.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def get_vercel_deployment_status(
    context: Dict[str, Any],
    deployment_id: str,
) -> ToolResult:
    """Get status of a Vercel deployment."""
    from backend.services.vercel_service import VercelService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "vercel")

        if not connection:
            return ToolResult(output="Vercel is not connected.", sources=[])

        deployment = await VercelService.get_deployment_status(
            db=db, connection=connection, deployment_id=deployment_id
        )

        if not deployment:
            return ToolResult(
                output=f"Could not find deployment {deployment_id}.",
                sources=[],
            )

        name = deployment.get("name", "Untitled")
        state = deployment.get("state", "unknown")
        target = deployment.get("target", "preview")
        url = deployment.get("url", "")
        error = deployment.get("error_message")

        state_emoji = {"READY": "✅", "BUILDING": "🔄", "ERROR": "❌"}.get(state, "❓")

        lines = [
            f"# {state_emoji} {name}\n",
            f"**State:** {state}",
            f"**Target:** {target}",
        ]

        if url:
            lines.append(f"**URL:** [{url}]({url})")

        if error:
            lines.append(f"\n**Error:** {error}")

        sources = []
        if url:
            sources.append({"type": "vercel_deployment", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("get_vercel_deployment_status.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def redeploy_vercel_deployment(
    context: Dict[str, Any],
    deployment_id: str,
    target: Optional[str] = None,
) -> ToolResult:
    """Redeploy a Vercel deployment (requires approval)."""
    from backend.services.vercel_service import VercelService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "vercel")

        if not connection:
            return ToolResult(output="Vercel is not connected.", sources=[])

        result = await VercelService.write_item(
            db=db,
            connection=connection,
            operation="redeploy",
            deployment_id=deployment_id,
            target=target,
        )

        if result.get("success"):
            url = result.get("url", "")
            if url and not url.startswith("http"):
                url = f"https://{url}"
            return ToolResult(
                output=(
                    f"Deployment triggered successfully.\n\nURL: {url}"
                    if url
                    else "Deployment triggered."
                ),
                sources=(
                    [
                        {
                            "type": "vercel_deployment",
                            "name": "New deployment",
                            "url": url,
                        }
                    ]
                    if url
                    else []
                ),
            )
        else:
            return ToolResult(output="Failed to trigger redeployment.", sources=[])

    except Exception as e:
        logger.error("redeploy_vercel_deployment.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


VERCEL_TOOLS = {
    "vercel.list_projects": list_vercel_projects,
    "vercel.list_deployments": list_vercel_deployments,
    "vercel.get_deployment_status": get_vercel_deployment_status,
    "vercel.redeploy": redeploy_vercel_deployment,
}
