"""
Snyk tools for NAVI agent.

Provides tools to query Snyk vulnerabilities, projects, and security data.
"""

from typing import Any, Dict, Optional
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


async def list_snyk_vulnerabilities(
    context: Dict[str, Any],
    project_id: Optional[str] = None,
    severity: Optional[str] = None,
    max_results: int = 20,
) -> ToolResult:
    """List Snyk vulnerabilities."""
    from backend.services.snyk_service import SnykService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "snyk")

        if not connection:
            return ToolResult(
                output="Snyk is not connected. Please connect your Snyk account first.",
                sources=[],
            )

        vulnerabilities = await SnykService.list_vulnerabilities(
            db=db,
            connection=connection,
            project_id=project_id,
            severity=severity,
            max_results=max_results,
        )

        if not vulnerabilities:
            return ToolResult(output="No Snyk vulnerabilities found.", sources=[])

        lines = [f"Found {len(vulnerabilities)} vulnerability(s):\n"]
        sources = []

        severity_emoji = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🔵",
        }

        for vuln in vulnerabilities:
            title = vuln.get("title", "Unknown")[:60]
            sev = vuln.get("severity", "unknown").lower()
            package = vuln.get("package_name", "")
            version = vuln.get("package_version", "")
            project_name = vuln.get("project_name", "")
            url = vuln.get("url", "")
            is_patchable = vuln.get("is_patchable", False)
            is_upgradeable = vuln.get("is_upgradeable", False)

            emoji = severity_emoji.get(sev, "⚪")
            fix_hint = []
            if is_upgradeable:
                fix_hint.append("⬆️ Upgradeable")
            if is_patchable:
                fix_hint.append("🩹 Patchable")

            lines.append(f"- {emoji} **{sev.upper()}**: {title}")
            if package:
                lines.append(f"  - Package: `{package}@{version}`")
            if project_name:
                lines.append(f"  - Project: {project_name}")
            if fix_hint:
                lines.append(f"  - {' | '.join(fix_hint)}")
            if url:
                lines.append(f"  - [View in Snyk]({url})")
            lines.append("")

            if url:
                sources.append(
                    {"type": "snyk_vulnerability", "name": title[:40], "url": url}
                )

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_snyk_vulnerabilities.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def list_snyk_projects(
    context: Dict[str, Any],
    max_results: int = 20,
) -> ToolResult:
    """List Snyk projects."""
    from backend.services.snyk_service import SnykService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "snyk")

        if not connection:
            return ToolResult(output="Snyk is not connected.", sources=[])

        projects = await SnykService.list_projects(
            db=db, connection=connection, max_results=max_results
        )

        if not projects:
            return ToolResult(output="No Snyk projects found.", sources=[])

        lines = [f"Found {len(projects)} Snyk project(s):\n"]
        sources = []

        for proj in projects:
            name = proj.get("name", "Untitled")
            origin = proj.get("origin", "")
            proj_type = proj.get("type", "")
            url = proj.get("url", "")

            lines.append(f"- **{name}**")
            if origin or proj_type:
                lines.append(f"  - Origin: {origin} | Type: {proj_type}")
            if url:
                lines.append(f"  - [Open in Snyk]({url})")
            lines.append("")

            if url:
                sources.append({"type": "snyk_project", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_snyk_projects.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def get_snyk_security_summary(
    context: Dict[str, Any],
) -> ToolResult:
    """Get a security summary with vulnerability counts."""
    from backend.services.snyk_service import SnykService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "snyk")

        if not connection:
            return ToolResult(output="Snyk is not connected.", sources=[])

        counts = await SnykService.get_vulnerability_count(db=db, connection=connection)

        if not counts:
            return ToolResult(
                output="Could not retrieve vulnerability counts.",
                sources=[],
            )

        critical = counts.get("critical", 0)
        high = counts.get("high", 0)
        medium = counts.get("medium", 0)
        low = counts.get("low", 0)
        total = critical + high + medium + low

        lines = [
            "# Snyk Security Summary\n",
            f"**Total Vulnerabilities:** {total}\n",
            "| Severity | Count |",
            "|----------|-------|",
            f"| 🔴 Critical | {critical} |",
            f"| 🟠 High | {high} |",
            f"| 🟡 Medium | {medium} |",
            f"| 🔵 Low | {low} |",
        ]

        if critical > 0 or high > 0:
            lines.append(
                "\n⚠️ **Action Required:** You have critical or high severity vulnerabilities that should be addressed."
            )

        org_id = connection.get("config", {}).get("org_id", "")
        url = f"https://app.snyk.io/org/{org_id}" if org_id else ""

        sources = []
        if url:
            sources.append(
                {"type": "snyk_dashboard", "name": "Snyk Dashboard", "url": url}
            )
            lines.append(f"\n[View full report in Snyk]({url})")

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("get_snyk_security_summary.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def get_snyk_project_issues(
    context: Dict[str, Any],
    project_id: str,
) -> ToolResult:
    """Get vulnerabilities for a specific Snyk project."""
    from backend.services.snyk_service import SnykService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "snyk")

        if not connection:
            return ToolResult(output="Snyk is not connected.", sources=[])

        vulnerabilities = await SnykService.list_vulnerabilities(
            db=db,
            connection=connection,
            project_id=project_id,
            max_results=50,
        )

        if not vulnerabilities:
            return ToolResult(
                output=f"No vulnerabilities found for project {project_id}.",
                sources=[],
            )

        # Group by severity
        by_severity = {"critical": [], "high": [], "medium": [], "low": []}
        for vuln in vulnerabilities:
            sev = vuln.get("severity", "low").lower()
            if sev in by_severity:
                by_severity[sev].append(vuln)

        lines = ["# Vulnerabilities for Project\n"]
        lines.append(f"**Total:** {len(vulnerabilities)}")
        lines.append(f"- 🔴 Critical: {len(by_severity['critical'])}")
        lines.append(f"- 🟠 High: {len(by_severity['high'])}")
        lines.append(f"- 🟡 Medium: {len(by_severity['medium'])}")
        lines.append(f"- 🔵 Low: {len(by_severity['low'])}")
        lines.append("")

        # Show critical and high issues
        for sev in ["critical", "high"]:
            if by_severity[sev]:
                emoji = "🔴" if sev == "critical" else "🟠"
                lines.append(f"## {emoji} {sev.title()} Issues\n")
                for vuln in by_severity[sev][:5]:
                    title = vuln.get("title", "Unknown")
                    package = vuln.get("package_name", "")
                    version = vuln.get("package_version", "")
                    lines.append(f"- **{title}**")
                    if package:
                        lines.append(f"  - `{package}@{version}`")
                lines.append("")

        org_id = connection.get("config", {}).get("org_id", "")
        url = f"https://app.snyk.io/org/{org_id}/project/{project_id}" if org_id else ""

        sources = []
        if url:
            sources.append(
                {"type": "snyk_project", "name": f"Project {project_id}", "url": url}
            )
            lines.append(f"[View in Snyk]({url})")

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("get_snyk_project_issues.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


SNYK_TOOLS = {
    "snyk_list_vulnerabilities": list_snyk_vulnerabilities,
    "snyk_list_projects": list_snyk_projects,
    "snyk_get_security_summary": get_snyk_security_summary,
    "snyk_get_project_issues": get_snyk_project_issues,
}
