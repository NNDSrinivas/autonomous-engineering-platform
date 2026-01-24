"""
Datadog API client for monitoring and observability.

Provides access to Datadog metrics, events, monitors, and logs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import structlog

import httpx

logger = structlog.get_logger(__name__)


class DatadogClient:
    """
    Async Datadog API client.

    Supports:
    - Metrics querying and submission
    - Events and incidents
    - Monitors and alerts
    - Dashboards
    - Logs
    """

    def __init__(
        self,
        api_key: str,
        app_key: str,
        site: str = "datadoghq.com",
        timeout: float = 30.0,
    ):
        """
        Initialize Datadog client.

        Args:
            api_key: Datadog API key
            app_key: Datadog application key
            site: Datadog site (datadoghq.com, datadoghq.eu, etc.)
            timeout: Request timeout
        """
        self.api_key = api_key
        self.app_key = app_key
        self.site = site
        self.base_url = f"https://api.{site}"
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "DatadogClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "DD-API-KEY": self.api_key,
                "DD-APPLICATION-KEY": self.app_key,
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        return self._client

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    async def validate(self) -> Dict[str, Any]:
        """Validate API and application keys."""
        resp = await self.client.get("/api/v1/validate")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------------------

    async def query_metrics(
        self,
        query: str,
        from_ts: int,
        to_ts: int,
    ) -> Dict[str, Any]:
        """
        Query timeseries metrics.

        Args:
            query: Metrics query string
            from_ts: Start timestamp (UNIX seconds)
            to_ts: End timestamp (UNIX seconds)

        Returns:
            Timeseries data
        """
        params = {
            "query": query,
            "from": from_ts,
            "to": to_ts,
        }
        resp = await self.client.get("/api/v1/query", params=params)
        resp.raise_for_status()
        return resp.json()

    async def list_metrics(
        self,
        from_ts: int,
        host: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        List available metrics.

        Args:
            from_ts: Start timestamp
            host: Filter by host
            tags: Filter by tags

        Returns:
            List of metric names
        """
        params: Dict[str, Any] = {"from": from_ts}
        if host:
            params["host"] = host
        if tags:
            params["tags"] = ",".join(tags)

        resp = await self.client.get("/api/v1/metrics", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_metric_metadata(
        self,
        metric_name: str,
    ) -> Dict[str, Any]:
        """Get metadata for a metric."""
        resp = await self.client.get(f"/api/v1/metrics/{metric_name}")
        resp.raise_for_status()
        return resp.json()

    async def submit_metrics(
        self,
        series: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Submit metrics.

        Args:
            series: List of metric series

        Example series:
            {
                "metric": "custom.metric",
                "type": "gauge",
                "points": [[timestamp, value], ...],
                "tags": ["env:prod"]
            }
        """
        payload = {"series": series}
        resp = await self.client.post("/api/v2/series", json=payload)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Events
    # -------------------------------------------------------------------------

    async def list_events(
        self,
        start: int,
        end: int,
        priority: Optional[str] = None,
        sources: Optional[str] = None,
        tags: Optional[str] = None,
        unaggregated: bool = False,
    ) -> Dict[str, Any]:
        """
        List events.

        Args:
            start: Start timestamp
            end: End timestamp
            priority: Filter by priority (normal, low)
            sources: Filter by sources
            tags: Filter by tags
            unaggregated: Return unaggregated events

        Returns:
            List of events
        """
        params: Dict[str, Any] = {
            "start": start,
            "end": end,
            "unaggregated": str(unaggregated).lower(),
        }
        if priority:
            params["priority"] = priority
        if sources:
            params["sources"] = sources
        if tags:
            params["tags"] = tags

        resp = await self.client.get("/api/v1/events", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_event(
        self,
        event_id: int,
    ) -> Dict[str, Any]:
        """Get a specific event."""
        resp = await self.client.get(f"/api/v1/events/{event_id}")
        resp.raise_for_status()
        return resp.json()

    async def create_event(
        self,
        title: str,
        text: str,
        alert_type: str = "info",
        priority: str = "normal",
        host: Optional[str] = None,
        tags: Optional[List[str]] = None,
        aggregation_key: Optional[str] = None,
        source_type_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create an event.

        Args:
            title: Event title
            text: Event body
            alert_type: info, warning, error, success
            priority: normal, low
            host: Related host
            tags: Event tags
            aggregation_key: Key for aggregating events
            source_type_name: Source type

        Returns:
            Created event
        """
        payload: Dict[str, Any] = {
            "title": title,
            "text": text,
            "alert_type": alert_type,
            "priority": priority,
        }
        if host:
            payload["host"] = host
        if tags:
            payload["tags"] = tags
        if aggregation_key:
            payload["aggregation_key"] = aggregation_key
        if source_type_name:
            payload["source_type_name"] = source_type_name

        resp = await self.client.post("/api/v1/events", json=payload)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Monitors
    # -------------------------------------------------------------------------

    async def list_monitors(
        self,
        group_states: Optional[str] = None,
        name: Optional[str] = None,
        tags: Optional[str] = None,
        monitor_tags: Optional[str] = None,
        with_downtimes: bool = False,
        page: int = 0,
        page_size: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        List monitors.

        Args:
            group_states: Filter by states (all, alert, warn, no data, ok)
            name: Filter by name
            tags: Filter by scope tags
            monitor_tags: Filter by monitor tags
            with_downtimes: Include downtime info
            page: Page number
            page_size: Results per page

        Returns:
            List of monitors
        """
        params: Dict[str, Any] = {
            "with_downtimes": str(with_downtimes).lower(),
            "page": page,
            "page_size": page_size,
        }
        if group_states:
            params["group_states"] = group_states
        if name:
            params["name"] = name
        if tags:
            params["tags"] = tags
        if monitor_tags:
            params["monitor_tags"] = monitor_tags

        resp = await self.client.get("/api/v1/monitor", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_monitor(
        self,
        monitor_id: int,
        group_states: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a specific monitor."""
        params = {}
        if group_states:
            params["group_states"] = group_states

        resp = await self.client.get(f"/api/v1/monitor/{monitor_id}", params=params)
        resp.raise_for_status()
        return resp.json()

    async def create_monitor(
        self,
        name: str,
        monitor_type: str,
        query: str,
        message: str,
        tags: Optional[List[str]] = None,
        priority: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a monitor.

        Args:
            name: Monitor name
            monitor_type: Type (metric alert, query alert, etc.)
            query: Monitor query
            message: Notification message
            tags: Monitor tags
            priority: Priority (1-5)
            options: Additional options

        Returns:
            Created monitor
        """
        payload: Dict[str, Any] = {
            "name": name,
            "type": monitor_type,
            "query": query,
            "message": message,
        }
        if tags:
            payload["tags"] = tags
        if priority:
            payload["priority"] = priority
        if options:
            payload["options"] = options

        resp = await self.client.post("/api/v1/monitor", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def update_monitor(
        self,
        monitor_id: int,
        name: Optional[str] = None,
        query: Optional[str] = None,
        message: Optional[str] = None,
        tags: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update a monitor."""
        payload: Dict[str, Any] = {}
        if name:
            payload["name"] = name
        if query:
            payload["query"] = query
        if message:
            payload["message"] = message
        if tags:
            payload["tags"] = tags
        if options:
            payload["options"] = options

        resp = await self.client.put(f"/api/v1/monitor/{monitor_id}", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def delete_monitor(
        self,
        monitor_id: int,
    ) -> Dict[str, Any]:
        """Delete a monitor."""
        resp = await self.client.delete(f"/api/v1/monitor/{monitor_id}")
        resp.raise_for_status()
        return resp.json()

    async def mute_monitor(
        self,
        monitor_id: int,
        scope: Optional[str] = None,
        end: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Mute a monitor."""
        payload: Dict[str, Any] = {}
        if scope:
            payload["scope"] = scope
        if end:
            payload["end"] = end

        resp = await self.client.post(
            f"/api/v1/monitor/{monitor_id}/mute",
            json=payload if payload else None,
        )
        resp.raise_for_status()
        return resp.json()

    async def unmute_monitor(
        self,
        monitor_id: int,
        scope: Optional[str] = None,
        all_scopes: bool = False,
    ) -> Dict[str, Any]:
        """Unmute a monitor."""
        payload: Dict[str, Any] = {}
        if scope:
            payload["scope"] = scope
        if all_scopes:
            payload["all_scopes"] = True

        resp = await self.client.post(
            f"/api/v1/monitor/{monitor_id}/unmute",
            json=payload if payload else None,
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Dashboards
    # -------------------------------------------------------------------------

    async def list_dashboards(self) -> Dict[str, Any]:
        """List all dashboards."""
        resp = await self.client.get("/api/v1/dashboard")
        resp.raise_for_status()
        return resp.json()

    async def get_dashboard(
        self,
        dashboard_id: str,
    ) -> Dict[str, Any]:
        """Get a specific dashboard."""
        resp = await self.client.get(f"/api/v1/dashboard/{dashboard_id}")
        resp.raise_for_status()
        return resp.json()

    async def create_dashboard(
        self,
        title: str,
        layout_type: str,
        widgets: List[Dict[str, Any]],
        description: Optional[str] = None,
        is_read_only: bool = False,
        notify_list: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a dashboard.

        Args:
            title: Dashboard title
            layout_type: ordered or free
            widgets: Dashboard widgets
            description: Dashboard description
            is_read_only: Read-only mode
            notify_list: Users to notify on changes

        Returns:
            Created dashboard
        """
        payload: Dict[str, Any] = {
            "title": title,
            "layout_type": layout_type,
            "widgets": widgets,
            "is_read_only": is_read_only,
        }
        if description:
            payload["description"] = description
        if notify_list:
            payload["notify_list"] = notify_list

        resp = await self.client.post("/api/v1/dashboard", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def delete_dashboard(
        self,
        dashboard_id: str,
    ) -> Dict[str, Any]:
        """Delete a dashboard."""
        resp = await self.client.delete(f"/api/v1/dashboard/{dashboard_id}")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Logs
    # -------------------------------------------------------------------------

    async def search_logs(
        self,
        query: str,
        from_ts: str,
        to_ts: str,
        sort: str = "desc",
        limit: int = 50,
        start_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search logs.

        Args:
            query: Log query
            from_ts: Start time (ISO 8601)
            to_ts: End time (ISO 8601)
            sort: Sort order (asc, desc)
            limit: Maximum logs to return
            start_at: Pagination cursor

        Returns:
            Log search results
        """
        payload: Dict[str, Any] = {
            "filter": {
                "query": query,
                "from": from_ts,
                "to": to_ts,
            },
            "sort": sort,
            "page": {
                "limit": limit,
            },
        }
        if start_at:
            payload["page"]["cursor"] = start_at

        resp = await self.client.post("/api/v2/logs/events/search", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def submit_logs(
        self,
        logs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Submit logs.

        Args:
            logs: List of log entries

        Example log:
            {
                "message": "Log message",
                "ddsource": "my-app",
                "ddtags": "env:prod",
                "hostname": "my-host",
                "service": "my-service"
            }
        """
        resp = await self.client.post("/api/v2/logs", json=logs)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Incidents
    # -------------------------------------------------------------------------

    async def list_incidents(
        self,
        page_size: int = 10,
        page_offset: int = 0,
    ) -> Dict[str, Any]:
        """List incidents."""
        params = {
            "page[size]": page_size,
            "page[offset]": page_offset,
        }
        resp = await self.client.get("/api/v2/incidents", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_incident(
        self,
        incident_id: str,
    ) -> Dict[str, Any]:
        """Get a specific incident."""
        resp = await self.client.get(f"/api/v2/incidents/{incident_id}")
        resp.raise_for_status()
        return resp.json()

    async def create_incident(
        self,
        title: str,
        customer_impact_scope: Optional[str] = None,
        customer_impact_start: Optional[str] = None,
        customer_impacted: bool = False,
        detected: Optional[str] = None,
        fields: Optional[Dict[str, Any]] = None,
        notification_handles: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create an incident."""
        attributes: Dict[str, Any] = {
            "title": title,
            "customer_impacted": customer_impacted,
        }
        if customer_impact_scope:
            attributes["customer_impact_scope"] = customer_impact_scope
        if customer_impact_start:
            attributes["customer_impact_start"] = customer_impact_start
        if detected:
            attributes["detected"] = detected
        if fields:
            attributes["fields"] = fields
        if notification_handles:
            attributes["notification_handles"] = notification_handles

        payload = {
            "data": {
                "type": "incidents",
                "attributes": attributes,
            }
        }
        resp = await self.client.post("/api/v2/incidents", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def update_incident(
        self,
        incident_id: str,
        attributes: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update an incident."""
        payload = {
            "data": {
                "id": incident_id,
                "type": "incidents",
                "attributes": attributes,
            }
        }
        resp = await self.client.patch(f"/api/v2/incidents/{incident_id}", json=payload)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Hosts
    # -------------------------------------------------------------------------

    async def list_hosts(
        self,
        filter: Optional[str] = None,
        sort_field: Optional[str] = None,
        sort_dir: Optional[str] = None,
        start: int = 0,
        count: int = 100,
        include_muted_hosts_data: bool = True,
        include_hosts_metadata: bool = True,
    ) -> Dict[str, Any]:
        """List hosts."""
        params: Dict[str, Any] = {
            "start": start,
            "count": count,
            "include_muted_hosts_data": str(include_muted_hosts_data).lower(),
            "include_hosts_metadata": str(include_hosts_metadata).lower(),
        }
        if filter:
            params["filter"] = filter
        if sort_field:
            params["sort_field"] = sort_field
        if sort_dir:
            params["sort_dir"] = sort_dir

        resp = await self.client.get("/api/v1/hosts", params=params)
        resp.raise_for_status()
        return resp.json()

    async def mute_host(
        self,
        hostname: str,
        end: Optional[int] = None,
        message: Optional[str] = None,
        override: bool = False,
    ) -> Dict[str, Any]:
        """Mute a host."""
        payload: Dict[str, Any] = {"override": override}
        if end:
            payload["end"] = end
        if message:
            payload["message"] = message

        resp = await self.client.post(f"/api/v1/host/{hostname}/mute", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def unmute_host(
        self,
        hostname: str,
    ) -> Dict[str, Any]:
        """Unmute a host."""
        resp = await self.client.post(f"/api/v1/host/{hostname}/unmute")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Service Level Objectives (SLOs)
    # -------------------------------------------------------------------------

    async def list_slos(
        self,
        ids: Optional[str] = None,
        query: Optional[str] = None,
        tags_query: Optional[str] = None,
        metrics_query: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List SLOs."""
        params: Dict[str, Any] = {
            "limit": limit,
            "offset": offset,
        }
        if ids:
            params["ids"] = ids
        if query:
            params["query"] = query
        if tags_query:
            params["tags_query"] = tags_query
        if metrics_query:
            params["metrics_query"] = metrics_query

        resp = await self.client.get("/api/v1/slo", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_slo(
        self,
        slo_id: str,
        with_configured_alert_ids: bool = False,
    ) -> Dict[str, Any]:
        """Get a specific SLO."""
        params = {"with_configured_alert_ids": str(with_configured_alert_ids).lower()}
        resp = await self.client.get(f"/api/v1/slo/{slo_id}", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_slo_history(
        self,
        slo_id: str,
        from_ts: int,
        to_ts: int,
    ) -> Dict[str, Any]:
        """Get SLO history data."""
        params = {"from_ts": from_ts, "to_ts": to_ts}
        resp = await self.client.get(f"/api/v1/slo/{slo_id}/history", params=params)
        resp.raise_for_status()
        return resp.json()
