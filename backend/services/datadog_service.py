"""
Datadog service for NAVI connector integration.

Provides syncing and querying of Datadog monitors, incidents, and metrics.
"""

from typing import Any, Dict, List, Optional
import structlog

from backend.services.connector_base import ConnectorServiceBase

logger = structlog.get_logger(__name__)


class DatadogService(ConnectorServiceBase):
    """Service for Datadog monitoring and observability integration."""

    PROVIDER = "datadog"
    SUPPORTED_ITEM_TYPES = ["monitor", "incident", "dashboard"]
    WRITE_OPERATIONS = ["create_event", "mute_monitor", "unmute_monitor", "create_incident"]

    @classmethod
    async def sync_items(
        cls,
        db,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, int]:
        """
        Sync Datadog monitors and incidents to local database.

        Args:
            db: Database session
            connection: Connector connection dict with credentials
            item_types: Types to sync (monitor, incident, dashboard)
            **kwargs: Additional args

        Returns:
            Dict with counts of synced items by type
        """
        from backend.integrations.datadog_client import DatadogClient

        config = connection.get("config", {})
        api_key = config.get("api_key")
        app_key = config.get("app_key") or config.get("application_key")
        site = config.get("site", "datadoghq.com")

        if not api_key or not app_key:
            raise ValueError("Datadog API key and application key not configured")

        user_id = connection.get("user_id")
        types_to_sync = item_types or cls.SUPPORTED_ITEM_TYPES
        counts = {}

        async with DatadogClient(api_key=api_key, app_key=app_key, site=site) as client:
            # Sync monitors
            if "monitor" in types_to_sync:
                monitors = await client.list_monitors(page_size=100)
                counts["monitor"] = 0

                for mon in monitors:
                    mon_id = str(mon.get("id", ""))
                    name = mon.get("name", "Untitled Monitor")
                    overall_state = mon.get("overall_state", "")

                    cls.upsert_item(
                        db=db,
                        user_id=user_id,
                        provider=cls.PROVIDER,
                        item_type="monitor",
                        external_id=mon_id,
                        title=name,
                        url=f"https://app.{site}/monitors/{mon_id}",
                        metadata={
                            "type": mon.get("type"),
                            "overall_state": overall_state,
                            "query": mon.get("query"),
                            "tags": mon.get("tags", []),
                        },
                    )
                    counts["monitor"] += 1

                logger.info(
                    "datadog.sync_monitors",
                    user_id=user_id,
                    count=counts["monitor"],
                )

            # Sync dashboards
            if "dashboard" in types_to_sync:
                dashboards_data = await client.list_dashboards()
                dashboards = dashboards_data.get("dashboards", [])
                counts["dashboard"] = 0

                for dash in dashboards:
                    dash_id = dash.get("id", "")
                    title = dash.get("title", "Untitled Dashboard")

                    cls.upsert_item(
                        db=db,
                        user_id=user_id,
                        provider=cls.PROVIDER,
                        item_type="dashboard",
                        external_id=dash_id,
                        title=title,
                        url=f"https://app.{site}/dashboard/{dash_id}",
                        metadata={
                            "layout_type": dash.get("layout_type"),
                            "author_name": dash.get("author_name"),
                        },
                    )
                    counts["dashboard"] += 1

                logger.info(
                    "datadog.sync_dashboards",
                    user_id=user_id,
                    count=counts["dashboard"],
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
        Perform write operations on Datadog.

        Supported operations:
        - create_event: Create an event
        - mute_monitor: Mute a monitor
        - unmute_monitor: Unmute a monitor
        - create_incident: Create an incident

        Args:
            db: Database session
            connection: Connector connection dict
            operation: Operation name
            **kwargs: Operation-specific arguments

        Returns:
            Result dict with operation outcome
        """
        from backend.integrations.datadog_client import DatadogClient

        config = connection.get("config", {})
        api_key = config.get("api_key")
        app_key = config.get("app_key") or config.get("application_key")
        site = config.get("site", "datadoghq.com")

        if not api_key or not app_key:
            raise ValueError("Datadog API key and application key not configured")

        async with DatadogClient(api_key=api_key, app_key=app_key, site=site) as client:
            if operation == "create_event":
                title = kwargs.get("title")
                text = kwargs.get("text")
                alert_type = kwargs.get("alert_type", "info")
                tags = kwargs.get("tags")

                if not title or not text:
                    raise ValueError("title and text are required")

                result = await client.create_event(
                    title=title,
                    text=text,
                    alert_type=alert_type,
                    tags=tags,
                )

                return {
                    "success": True,
                    "event": result.get("event", {}),
                }

            elif operation == "mute_monitor":
                monitor_id = kwargs.get("monitor_id")
                scope = kwargs.get("scope")
                end = kwargs.get("end")

                if not monitor_id:
                    raise ValueError("monitor_id is required")

                result = await client.mute_monitor(
                    monitor_id=int(monitor_id),
                    scope=scope,
                    end=end,
                )

                return {
                    "success": True,
                    "monitor_id": monitor_id,
                }

            elif operation == "unmute_monitor":
                monitor_id = kwargs.get("monitor_id")
                scope = kwargs.get("scope")

                if not monitor_id:
                    raise ValueError("monitor_id is required")

                result = await client.unmute_monitor(
                    monitor_id=int(monitor_id),
                    scope=scope,
                )

                return {
                    "success": True,
                    "monitor_id": monitor_id,
                }

            elif operation == "create_incident":
                title = kwargs.get("title")
                customer_impacted = kwargs.get("customer_impacted", False)

                if not title:
                    raise ValueError("title is required")

                result = await client.create_incident(
                    title=title,
                    customer_impacted=customer_impacted,
                )

                return {
                    "success": True,
                    "incident": result.get("data", {}),
                }

            else:
                raise ValueError(f"Unsupported operation: {operation}")

    @classmethod
    async def list_monitors(
        cls,
        db,
        connection: Dict[str, Any],
        state: Optional[str] = None,
        name: Optional[str] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List Datadog monitors.

        Args:
            db: Database session
            connection: Connector connection dict
            state: Filter by state (Alert, Warn, No Data, OK)
            name: Filter by name
            max_results: Maximum results to return

        Returns:
            List of monitor dicts
        """
        from backend.integrations.datadog_client import DatadogClient

        config = connection.get("config", {})
        api_key = config.get("api_key")
        app_key = config.get("app_key") or config.get("application_key")
        site = config.get("site", "datadoghq.com")

        if not api_key or not app_key:
            return []

        async with DatadogClient(api_key=api_key, app_key=app_key, site=site) as client:
            monitors = await client.list_monitors(
                group_states=state,
                name=name,
                page_size=max_results,
            )

            return [
                {
                    "id": str(m.get("id", "")),
                    "name": m.get("name", "Untitled Monitor"),
                    "type": m.get("type", ""),
                    "overall_state": m.get("overall_state", ""),
                    "query": m.get("query", ""),
                    "message": m.get("message", ""),
                    "tags": m.get("tags", []),
                    "url": f"https://app.{site}/monitors/{m.get('id', '')}",
                }
                for m in monitors
            ]

    @classmethod
    async def list_incidents(
        cls,
        db,
        connection: Dict[str, Any],
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List Datadog incidents.

        Args:
            db: Database session
            connection: Connector connection dict
            max_results: Maximum results to return

        Returns:
            List of incident dicts
        """
        from backend.integrations.datadog_client import DatadogClient

        config = connection.get("config", {})
        api_key = config.get("api_key")
        app_key = config.get("app_key") or config.get("application_key")
        site = config.get("site", "datadoghq.com")

        if not api_key or not app_key:
            return []

        async with DatadogClient(api_key=api_key, app_key=app_key, site=site) as client:
            incidents_data = await client.list_incidents(page_size=max_results)
            incidents = incidents_data.get("data", [])

            return [
                {
                    "id": inc.get("id", ""),
                    "title": inc.get("attributes", {}).get("title", "Untitled"),
                    "status": inc.get("attributes", {}).get("state", ""),
                    "severity": inc.get("attributes", {}).get("severity", ""),
                    "customer_impacted": inc.get("attributes", {}).get("customer_impacted", False),
                    "created": inc.get("attributes", {}).get("created", ""),
                    "url": f"https://app.{site}/incidents/{inc.get('id', '')}",
                }
                for inc in incidents
            ]

    @classmethod
    async def list_dashboards(
        cls,
        db,
        connection: Dict[str, Any],
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List Datadog dashboards.

        Args:
            db: Database session
            connection: Connector connection dict
            max_results: Maximum results to return

        Returns:
            List of dashboard dicts
        """
        from backend.integrations.datadog_client import DatadogClient

        config = connection.get("config", {})
        api_key = config.get("api_key")
        app_key = config.get("app_key") or config.get("application_key")
        site = config.get("site", "datadoghq.com")

        if not api_key or not app_key:
            return []

        async with DatadogClient(api_key=api_key, app_key=app_key, site=site) as client:
            dashboards_data = await client.list_dashboards()
            dashboards = dashboards_data.get("dashboards", [])[:max_results]

            return [
                {
                    "id": d.get("id", ""),
                    "title": d.get("title", "Untitled Dashboard"),
                    "layout_type": d.get("layout_type", ""),
                    "author_name": d.get("author_name", ""),
                    "url": f"https://app.{site}/dashboard/{d.get('id', '')}",
                }
                for d in dashboards
            ]

    @classmethod
    async def get_alerting_monitors(
        cls,
        db,
        connection: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Get monitors that are currently alerting.

        Args:
            db: Database session
            connection: Connector connection dict

        Returns:
            List of alerting monitors
        """
        return await cls.list_monitors(
            db=db,
            connection=connection,
            state="alert",
            max_results=50,
        )
