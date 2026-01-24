"""
PagerDuty tools for NAVI agent.

Provides tools to query and manage PagerDuty incidents, services, and on-call schedules.
"""

from typing import Any, Dict, List, Optional
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


async def list_pagerduty_incidents(
    context: Dict[str, Any],
    statuses: Optional[List[str]] = None,
    urgencies: Optional[List[str]] = None,
    max_results: int = 10,
) -> ToolResult:
    """List PagerDuty incidents."""
    from backend.services.pagerduty_service import PagerDutyService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "pagerduty")

        if not connection:
            return ToolResult(
                output="PagerDuty is not connected. Please connect your PagerDuty account first.",
                sources=[],
            )

        # Default to open incidents
        if not statuses:
            statuses = ["triggered", "acknowledged"]

        incidents = await PagerDutyService.list_incidents(
            db=db,
            connection=connection,
            statuses=statuses,
            urgencies=urgencies,
            max_results=max_results,
        )

        if not incidents:
            return ToolResult(output="No PagerDuty incidents found.", sources=[])

        lines = [f"Found {len(incidents)} incident(s):\n"]
        sources = []

        status_emoji = {
            "triggered": "🔴",
            "acknowledged": "🟠",
            "resolved": "✅",
        }

        urgency_indicator = {
            "high": "⚠️ HIGH",
            "low": "LOW",
        }

        for inc in incidents:
            title = inc.get("title", "Untitled")[:60]
            status = inc.get("status", "unknown")
            urgency = inc.get("urgency", "unknown")
            service = inc.get("service", "")
            url = inc.get("url", "")
            created = inc.get("created_at", "")[:10] if inc.get("created_at") else ""

            emoji = status_emoji.get(status, "❓")
            urg = urgency_indicator.get(urgency, urgency.upper())

            lines.append(f"- {emoji} **{title}**")
            lines.append(f"  - Status: {status.title()} | Urgency: {urg}")
            if service:
                lines.append(f"  - Service: {service}")
            if created:
                lines.append(f"  - Created: {created}")
            if url:
                lines.append(f"  - [View Incident]({url})")
            lines.append("")

            if url:
                sources.append(
                    {"type": "pagerduty_incident", "name": title[:40], "url": url}
                )

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_pagerduty_incidents.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def get_pagerduty_oncall(
    context: Dict[str, Any],
) -> ToolResult:
    """Get current PagerDuty on-call users."""
    from backend.services.pagerduty_service import PagerDutyService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "pagerduty")

        if not connection:
            return ToolResult(output="PagerDuty is not connected.", sources=[])

        oncalls = await PagerDutyService.get_oncall(db=db, connection=connection)

        if not oncalls:
            return ToolResult(output="No on-call entries found.", sources=[])

        lines = ["# Current On-Call\n"]

        # Group by escalation policy
        by_policy = {}
        for oc in oncalls:
            policy = oc.get("escalation_policy", "Unknown")
            if policy not in by_policy:
                by_policy[policy] = []
            by_policy[policy].append(oc)

        for policy, entries in by_policy.items():
            lines.append(f"## {policy}\n")
            for oc in entries:
                user = oc.get("user", "Unknown")
                level = oc.get("escalation_level", "?")
                schedule = oc.get("schedule", "")

                lines.append(f"- **Level {level}:** {user}")
                if schedule:
                    lines.append(f"  - Schedule: {schedule}")
            lines.append("")

        return ToolResult(output="\n".join(lines), sources=[])

    except Exception as e:
        logger.error("get_pagerduty_oncall.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def list_pagerduty_services(
    context: Dict[str, Any],
    max_results: int = 20,
) -> ToolResult:
    """List PagerDuty services."""
    from backend.services.pagerduty_service import PagerDutyService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "pagerduty")

        if not connection:
            return ToolResult(output="PagerDuty is not connected.", sources=[])

        services = await PagerDutyService.list_services(
            db=db, connection=connection, max_results=max_results
        )

        if not services:
            return ToolResult(output="No PagerDuty services found.", sources=[])

        lines = [f"Found {len(services)} service(s):\n"]
        sources = []

        status_emoji = {
            "active": "✅",
            "warning": "⚠️",
            "critical": "🔴",
            "maintenance": "🔧",
            "disabled": "⏸️",
        }

        for svc in services:
            name = svc.get("name", "Untitled")
            status = svc.get("status", "unknown")
            description = svc.get("description", "")[:60]
            url = svc.get("url", "")

            emoji = status_emoji.get(status, "❓")
            lines.append(f"- {emoji} **{name}**")
            lines.append(f"  - Status: {status}")
            if description:
                lines.append(f"  - {description}")
            if url:
                lines.append(f"  - [View Service]({url})")
            lines.append("")

            if url:
                sources.append({"type": "pagerduty_service", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_pagerduty_services.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def acknowledge_pagerduty_incident(
    context: Dict[str, Any],
    incident_id: str,
) -> ToolResult:
    """Acknowledge a PagerDuty incident (requires approval)."""
    from backend.services.pagerduty_service import PagerDutyService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "pagerduty")

        if not connection:
            return ToolResult(output="PagerDuty is not connected.", sources=[])

        result = await PagerDutyService.write_item(
            db=db,
            connection=connection,
            operation="acknowledge_incident",
            incident_id=incident_id,
        )

        if result.get("success"):
            return ToolResult(
                output=f"Incident {incident_id} has been acknowledged.",
                sources=[],
            )
        else:
            return ToolResult(output="Failed to acknowledge incident.", sources=[])

    except Exception as e:
        logger.error("acknowledge_pagerduty_incident.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def resolve_pagerduty_incident(
    context: Dict[str, Any],
    incident_id: str,
    resolution: Optional[str] = None,
) -> ToolResult:
    """Resolve a PagerDuty incident (requires approval)."""
    from backend.services.pagerduty_service import PagerDutyService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "pagerduty")

        if not connection:
            return ToolResult(output="PagerDuty is not connected.", sources=[])

        result = await PagerDutyService.write_item(
            db=db,
            connection=connection,
            operation="resolve_incident",
            incident_id=incident_id,
            resolution=resolution,
        )

        if result.get("success"):
            return ToolResult(
                output=f"Incident {incident_id} has been resolved.",
                sources=[],
            )
        else:
            return ToolResult(output="Failed to resolve incident.", sources=[])

    except Exception as e:
        logger.error("resolve_pagerduty_incident.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


PAGERDUTY_TOOLS = {
    "pagerduty.list_incidents": list_pagerduty_incidents,
    "pagerduty.get_oncall": get_pagerduty_oncall,
    "pagerduty.list_services": list_pagerduty_services,
    "pagerduty.acknowledge_incident": acknowledge_pagerduty_incident,
    "pagerduty.resolve_incident": resolve_pagerduty_incident,
}
