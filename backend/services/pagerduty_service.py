"""
PagerDuty service for NAVI connector integration.

Provides syncing and querying of PagerDuty incidents, services, and on-call schedules.
"""

from typing import Any, Dict, List, Optional
import structlog

from backend.services.connector_base import ConnectorServiceBase

logger = structlog.get_logger(__name__)


class PagerDutyService(ConnectorServiceBase):
    """Service for PagerDuty incident management integration."""

    PROVIDER = "pagerduty"
    SUPPORTED_ITEM_TYPES = ["incident", "service", "schedule"]
    WRITE_OPERATIONS = ["acknowledge_incident", "resolve_incident", "add_note"]

    @classmethod
    async def sync_items(
        cls,
        db,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, int]:
        """
        Sync PagerDuty incidents and services to local database.

        Args:
            db: Database session
            connection: Connector connection dict with credentials
            item_types: Types to sync (incident, service)
            **kwargs: Additional args

        Returns:
            Dict with counts of synced items by type
        """
        from backend.integrations.pagerduty_client import PagerDutyClient

        config = connection.get("config", {})
        api_token = config.get("access_token") or config.get("api_token")

        if not api_token:
            raise ValueError("PagerDuty API token not configured")

        user_id = connection.get("user_id")
        types_to_sync = item_types or cls.SUPPORTED_ITEM_TYPES
        counts = {}

        async with PagerDutyClient(api_token=api_token) as client:
            # Sync services
            if "service" in types_to_sync:
                data = await client.list_services(limit=100)
                services = data.get("services", [])
                counts["service"] = 0

                for svc in services:
                    svc_id = svc.get("id", "")
                    name = svc.get("name", "Untitled")
                    status = svc.get("status", "unknown")

                    cls.upsert_item(
                        db=db,
                        user_id=user_id,
                        provider=cls.PROVIDER,
                        item_type="service",
                        external_id=svc_id,
                        title=name,
                        url=svc.get("html_url", ""),
                        metadata={
                            "status": status,
                            "description": svc.get("description"),
                        },
                    )
                    counts["service"] += 1

                logger.info(
                    "pagerduty.sync_services",
                    user_id=user_id,
                    count=counts["service"],
                )

            # Sync incidents
            if "incident" in types_to_sync:
                # Get open incidents by default
                data = await client.list_incidents(
                    statuses=["triggered", "acknowledged"],
                    limit=100,
                )
                incidents = data.get("incidents", [])
                counts["incident"] = 0

                for inc in incidents:
                    inc_id = inc.get("id", "")
                    title = inc.get("title", "Untitled")
                    status = inc.get("status", "unknown")
                    urgency = inc.get("urgency", "unknown")

                    cls.upsert_item(
                        db=db,
                        user_id=user_id,
                        provider=cls.PROVIDER,
                        item_type="incident",
                        external_id=inc_id,
                        title=title,
                        url=inc.get("html_url", ""),
                        metadata={
                            "status": status,
                            "urgency": urgency,
                            "service": inc.get("service", {}).get("summary"),
                            "created_at": inc.get("created_at"),
                        },
                    )
                    counts["incident"] += 1

                logger.info(
                    "pagerduty.sync_incidents",
                    user_id=user_id,
                    count=counts["incident"],
                )

        return counts

    @classmethod
    async def write_item(
        cls,
        db,
        connection: Dict[str, Any],
        operation: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Perform write operations on PagerDuty.

        Supported operations:
        - acknowledge_incident: Acknowledge an incident
        - resolve_incident: Resolve an incident
        - add_note: Add a note to an incident

        Args:
            db: Database session
            connection: Connector connection dict
            operation: Operation name
            **kwargs: Operation-specific arguments

        Returns:
            Result dict with operation outcome
        """
        from backend.integrations.pagerduty_client import PagerDutyClient

        config = connection.get("config", {})
        api_token = config.get("access_token") or config.get("api_token")
        from_email = config.get("email") or kwargs.get("from_email")

        if not api_token:
            raise ValueError("PagerDuty API token not configured")

        async with PagerDutyClient(api_token=api_token) as client:
            if operation == "acknowledge_incident":
                incident_id = kwargs.get("incident_id")

                if not incident_id:
                    raise ValueError("incident_id is required")

                result = await client.acknowledge_incident(
                    incident_id=incident_id,
                    from_email=from_email or "navi@aep.local",
                )

                return {
                    "success": True,
                    "incident_id": incident_id,
                    "status": "acknowledged",
                }

            elif operation == "resolve_incident":
                incident_id = kwargs.get("incident_id")
                resolution = kwargs.get("resolution")

                if not incident_id:
                    raise ValueError("incident_id is required")

                result = await client.resolve_incident(
                    incident_id=incident_id,
                    from_email=from_email or "navi@aep.local",
                    resolution=resolution,
                )

                return {
                    "success": True,
                    "incident_id": incident_id,
                    "status": "resolved",
                }

            elif operation == "add_note":
                incident_id = kwargs.get("incident_id")
                content = kwargs.get("content")

                if not incident_id or not content:
                    raise ValueError("incident_id and content are required")

                result = await client.add_incident_note(
                    incident_id=incident_id,
                    from_email=from_email or "navi@aep.local",
                    content=content,
                )

                return {
                    "success": True,
                    "incident_id": incident_id,
                    "note_id": result.get("id"),
                }

            else:
                raise ValueError(f"Unsupported operation: {operation}")

    @classmethod
    async def list_incidents(
        cls,
        db,
        connection: Dict[str, Any],
        statuses: Optional[List[str]] = None,
        urgencies: Optional[List[str]] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List PagerDuty incidents.

        Args:
            db: Database session
            connection: Connector connection dict
            statuses: Filter by status (triggered, acknowledged, resolved)
            urgencies: Filter by urgency (high, low)
            max_results: Maximum results to return

        Returns:
            List of incident dicts
        """
        from backend.integrations.pagerduty_client import PagerDutyClient

        config = connection.get("config", {})
        api_token = config.get("access_token") or config.get("api_token")

        if not api_token:
            return []

        async with PagerDutyClient(api_token=api_token) as client:
            data = await client.list_incidents(
                statuses=statuses,
                urgencies=urgencies,
                limit=max_results,
            )
            incidents = data.get("incidents", [])

            return [
                {
                    "id": inc.get("id", ""),
                    "title": inc.get("title", "Untitled"),
                    "status": inc.get("status", "unknown"),
                    "urgency": inc.get("urgency", "unknown"),
                    "service": inc.get("service", {}).get("summary", ""),
                    "url": inc.get("html_url", ""),
                    "created_at": inc.get("created_at", ""),
                }
                for inc in incidents
            ]

    @classmethod
    async def get_oncall(
        cls,
        db,
        connection: Dict[str, Any],
        schedule_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get current on-call users.

        Args:
            db: Database session
            connection: Connector connection dict
            schedule_ids: Filter by schedule IDs

        Returns:
            List of on-call entries
        """
        from backend.integrations.pagerduty_client import PagerDutyClient

        config = connection.get("config", {})
        api_token = config.get("access_token") or config.get("api_token")

        if not api_token:
            return []

        async with PagerDutyClient(api_token=api_token) as client:
            data = await client.list_oncalls(schedule_ids=schedule_ids)
            oncalls = data.get("oncalls", [])

            return [
                {
                    "user": oc.get("user", {}).get("summary", "Unknown"),
                    "user_email": oc.get("user", {}).get("email", ""),
                    "schedule": oc.get("schedule", {}).get("summary", ""),
                    "escalation_policy": oc.get("escalation_policy", {}).get("summary", ""),
                    "escalation_level": oc.get("escalation_level"),
                    "start": oc.get("start", ""),
                    "end": oc.get("end", ""),
                }
                for oc in oncalls
            ]

    @classmethod
    async def list_services(
        cls,
        db,
        connection: Dict[str, Any],
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List PagerDuty services.

        Args:
            db: Database session
            connection: Connector connection dict
            max_results: Maximum results to return

        Returns:
            List of service dicts
        """
        from backend.integrations.pagerduty_client import PagerDutyClient

        config = connection.get("config", {})
        api_token = config.get("access_token") or config.get("api_token")

        if not api_token:
            return []

        async with PagerDutyClient(api_token=api_token) as client:
            data = await client.list_services(limit=max_results)
            services = data.get("services", [])

            return [
                {
                    "id": svc.get("id", ""),
                    "name": svc.get("name", "Untitled"),
                    "status": svc.get("status", "unknown"),
                    "description": svc.get("description", ""),
                    "url": svc.get("html_url", ""),
                }
                for svc in services
            ]
