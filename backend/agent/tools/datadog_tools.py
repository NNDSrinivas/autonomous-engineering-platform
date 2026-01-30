"""
Datadog tools for NAVI agent.

Provides tools to query Datadog monitors, incidents, and dashboards.
"""

from typing import Any, Dict, Optional
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


async def list_datadog_monitors(
    context: Dict[str, Any],
    state: Optional[str] = None,
    max_results: int = 20,
) -> ToolResult:
    """List Datadog monitors."""
    from backend.services.datadog_service import DatadogService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "datadog")

        if not connection:
            return ToolResult(
                output="Datadog is not connected. Please connect your Datadog account first.",
                sources=[],
            )

        monitors = await DatadogService.list_monitors(
            db=db,
            connection=connection,
            state=state,
            max_results=max_results,
        )

        if not monitors:
            filter_msg = f" with state '{state}'" if state else ""
            return ToolResult(
                output=f"No Datadog monitors found{filter_msg}.",
                sources=[],
            )

        lines = [f"Found {len(monitors)} monitor(s):\n"]
        sources = []

        state_emoji = {
            "Alert": "🔴",
            "Warn": "🟠",
            "No Data": "⚪",
            "OK": "✅",
        }

        for m in monitors:
            name = m.get("name", "Untitled")
            overall_state = m.get("overall_state", "")
            mon_type = m.get("type", "")
            url = m.get("url", "")
            tags = m.get("tags", [])

            emoji = state_emoji.get(overall_state, "❓")
            lines.append(f"- {emoji} **{name}**")
            lines.append(f"  - State: {overall_state} | Type: {mon_type}")
            if tags:
                lines.append(f"  - Tags: {', '.join(tags[:5])}")
            if url:
                lines.append(f"  - [View Monitor]({url})")
            lines.append("")

            if url:
                sources.append({"type": "datadog_monitor", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_datadog_monitors.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def get_datadog_alerting_monitors(
    context: Dict[str, Any],
) -> ToolResult:
    """Get Datadog monitors that are currently alerting."""
    from backend.services.datadog_service import DatadogService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "datadog")

        if not connection:
            return ToolResult(output="Datadog is not connected.", sources=[])

        monitors = await DatadogService.get_alerting_monitors(
            db=db,
            connection=connection,
        )

        if not monitors:
            return ToolResult(
                output="✅ No monitors are currently alerting.",
                sources=[],
            )

        lines = [f"# 🔴 Alerting Monitors ({len(monitors)})\n"]
        sources = []

        for m in monitors:
            name = m.get("name", "Untitled")
            mon_type = m.get("type", "")
            url = m.get("url", "")
            message = m.get("message", "")[:100]

            lines.append(f"- 🔴 **{name}**")
            lines.append(f"  - Type: {mon_type}")
            if message:
                lines.append(f"  - Message: {message}")
            if url:
                lines.append(f"  - [View Monitor]({url})")
            lines.append("")

            if url:
                sources.append({"type": "datadog_monitor", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("get_datadog_alerting_monitors.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def list_datadog_incidents(
    context: Dict[str, Any],
    max_results: int = 20,
) -> ToolResult:
    """List Datadog incidents."""
    from backend.services.datadog_service import DatadogService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "datadog")

        if not connection:
            return ToolResult(output="Datadog is not connected.", sources=[])

        incidents = await DatadogService.list_incidents(
            db=db,
            connection=connection,
            max_results=max_results,
        )

        if not incidents:
            return ToolResult(output="No Datadog incidents found.", sources=[])

        lines = [f"Found {len(incidents)} incident(s):\n"]
        sources = []

        severity_emoji = {
            "SEV-1": "🔴",
            "SEV-2": "🟠",
            "SEV-3": "🟡",
            "SEV-4": "🔵",
            "SEV-5": "⚪",
        }

        status_emoji = {
            "active": "🔥",
            "stable": "🔄",
            "resolved": "✅",
        }

        for inc in incidents:
            title = inc.get("title", "Untitled")
            status = inc.get("status", "")
            severity = inc.get("severity", "")
            customer_impacted = inc.get("customer_impacted", False)
            url = inc.get("url", "")

            sev_emoji = severity_emoji.get(severity, "❓")
            stat_emoji = status_emoji.get(status, "❓")

            lines.append(f"- {sev_emoji} {stat_emoji} **{title}**")
            lines.append(f"  - Status: {status} | Severity: {severity}")
            if customer_impacted:
                lines.append("  - ⚠️ Customer Impacted")
            if url:
                lines.append(f"  - [View Incident]({url})")
            lines.append("")

            if url:
                sources.append({"type": "datadog_incident", "name": title, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_datadog_incidents.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def list_datadog_dashboards(
    context: Dict[str, Any],
    max_results: int = 20,
) -> ToolResult:
    """List Datadog dashboards."""
    from backend.services.datadog_service import DatadogService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "datadog")

        if not connection:
            return ToolResult(output="Datadog is not connected.", sources=[])

        dashboards = await DatadogService.list_dashboards(
            db=db,
            connection=connection,
            max_results=max_results,
        )

        if not dashboards:
            return ToolResult(output="No Datadog dashboards found.", sources=[])

        lines = [f"Found {len(dashboards)} dashboard(s):\n"]
        sources = []

        for d in dashboards:
            title = d.get("title", "Untitled")
            layout = d.get("layout_type", "")
            author = d.get("author_name", "")
            url = d.get("url", "")

            lines.append(f"- 📊 **{title}**")
            if layout:
                lines.append(f"  - Layout: {layout}")
            if author:
                lines.append(f"  - Author: {author}")
            if url:
                lines.append(f"  - [Open Dashboard]({url})")
            lines.append("")

            if url:
                sources.append({"type": "datadog_dashboard", "name": title, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_datadog_dashboards.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def mute_datadog_monitor(
    context: Dict[str, Any],
    monitor_id: int,
    scope: Optional[str] = None,
) -> ToolResult:
    """Mute a Datadog monitor (requires approval)."""
    from backend.services.datadog_service import DatadogService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "datadog")

        if not connection:
            return ToolResult(output="Datadog is not connected.", sources=[])

        result = await DatadogService.write_item(
            db=db,
            connection=connection,
            operation="mute_monitor",
            monitor_id=monitor_id,
            scope=scope,
        )

        if result.get("success"):
            return ToolResult(
                output=f"Monitor {monitor_id} has been muted.",
                sources=[],
            )
        else:
            return ToolResult(output="Failed to mute monitor.", sources=[])

    except Exception as e:
        logger.error("mute_datadog_monitor.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


DATADOG_TOOLS = {
    "datadog_list_monitors": list_datadog_monitors,
    "datadog_alerting_monitors": get_datadog_alerting_monitors,
    "datadog_list_incidents": list_datadog_incidents,
    "datadog_list_dashboards": list_datadog_dashboards,
    "datadog_mute_monitor": mute_datadog_monitor,
}
