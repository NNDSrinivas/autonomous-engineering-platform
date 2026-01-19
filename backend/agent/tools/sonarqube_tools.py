"""
SonarQube tools for NAVI agent.

Provides tools to query SonarQube projects, issues, and quality gates.
"""

from typing import Any, Dict, Optional
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


async def list_sonarqube_projects(
    context: Dict[str, Any],
    max_results: int = 20,
) -> ToolResult:
    """List SonarQube projects."""
    from backend.services.sonarqube_service import SonarQubeService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "sonarqube")

        if not connection:
            return ToolResult(
                output="SonarQube is not connected. Please connect first.",
                sources=[],
            )

        projects = await SonarQubeService.list_projects(
            db=db, connection=connection, max_results=max_results
        )

        if not projects:
            return ToolResult(output="No SonarQube projects found.", sources=[])

        lines = [f"Found {len(projects)} SonarQube project(s):\n"]
        sources = []

        for proj in projects:
            name = proj.get("name", "Unnamed")
            key = proj.get("key", "")
            url = proj.get("url", "")
            last_analysis = proj.get("last_analysis", "Never")

            lines.append(f"- **{name}** (`{key}`)")
            lines.append(f"  - Last Analysis: {last_analysis[:10] if last_analysis else 'Never'}")
            if url:
                lines.append(f"  - [Open Dashboard]({url})")
            lines.append("")

            if url:
                sources.append({"type": "sonarqube_project", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_sonarqube_projects.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def list_sonarqube_issues(
    context: Dict[str, Any],
    project_key: Optional[str] = None,
    severity: Optional[str] = None,
    max_results: int = 20,
) -> ToolResult:
    """List SonarQube issues."""
    from backend.services.sonarqube_service import SonarQubeService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "sonarqube")

        if not connection:
            return ToolResult(output="SonarQube is not connected.", sources=[])

        issues = await SonarQubeService.list_issues(
            db=db,
            connection=connection,
            project_key=project_key,
            severity=severity,
            max_results=max_results,
        )

        if not issues:
            return ToolResult(output="No SonarQube issues found.", sources=[])

        lines = [f"Found {len(issues)} issue(s):\n"]

        severity_emoji = {
            "BLOCKER": "🔴",
            "CRITICAL": "🔴",
            "MAJOR": "🟠",
            "MINOR": "🟡",
            "INFO": "🔵",
        }

        for issue in issues:
            message = issue.get("message", "No message")[:100]
            sev = issue.get("severity", "UNKNOWN")
            issue_type = issue.get("type", "UNKNOWN")
            component = issue.get("component", "").split(":")[-1]
            line = issue.get("line")

            emoji = severity_emoji.get(sev, "⚪")

            lines.append(f"- {emoji} **{sev}** ({issue_type})")
            lines.append(f"  - {message}")
            lines.append(f"  - File: {component}" + (f":{line}" if line else ""))
            lines.append("")

        return ToolResult(output="\n".join(lines), sources=[])

    except Exception as e:
        logger.error("list_sonarqube_issues.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def get_sonarqube_quality_gate(
    context: Dict[str, Any],
    project_key: str,
) -> ToolResult:
    """Get quality gate status for a SonarQube project."""
    from backend.services.sonarqube_service import SonarQubeService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "sonarqube")

        if not connection:
            return ToolResult(output="SonarQube is not connected.", sources=[])

        gate = await SonarQubeService.get_quality_gate(
            db=db, connection=connection, project_key=project_key
        )

        if not gate:
            return ToolResult(
                output=f"Could not get quality gate for project {project_key}.",
                sources=[],
            )

        status = gate.get("status", "UNKNOWN")
        conditions = gate.get("conditions", [])

        status_emoji = "✅" if status == "OK" else "❌" if status == "ERROR" else "⚠️"

        lines = [
            f"**Quality Gate Status for `{project_key}`**: {status_emoji} {status}\n",
        ]

        if conditions:
            lines.append("**Conditions:**")
            for cond in conditions:
                metric = cond.get("metricKey", "unknown")
                cond_status = cond.get("status", "UNKNOWN")
                actual = cond.get("actualValue", "N/A")
                threshold = cond.get("errorThreshold", cond.get("warningThreshold", "N/A"))

                emoji = "✅" if cond_status == "OK" else "❌"
                lines.append(f"- {emoji} {metric}: {actual} (threshold: {threshold})")

        config = connection.get("config", {})
        base_url = config.get("base_url", "")

        return ToolResult(
            output="\n".join(lines),
            sources=[{
                "type": "sonarqube_project",
                "name": project_key,
                "url": f"{base_url}/dashboard?id={project_key}" if base_url else "",
            }],
        )

    except Exception as e:
        logger.error("get_sonarqube_quality_gate.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


SONARQUBE_TOOLS = {
    "sonarqube.list_projects": list_sonarqube_projects,
    "sonarqube.list_issues": list_sonarqube_issues,
    "sonarqube.get_quality_gate": get_sonarqube_quality_gate,
}
