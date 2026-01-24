"""
PagerDuty API client for incident management.

Provides access to PagerDuty services, incidents, schedules, and escalation policies.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import structlog

import httpx

logger = structlog.get_logger(__name__)


class PagerDutyClient:
    """
    Async PagerDuty API client.

    Supports:
    - Incident management
    - Service management
    - Schedules
    - Escalation policies
    - On-call management
    """

    BASE_URL = "https://api.pagerduty.com"

    def __init__(
        self,
        api_token: str,
        timeout: float = 30.0,
    ):
        self.api_token = api_token
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "PagerDutyClient":
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Token token={self.api_token}",
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
    # Users
    # -------------------------------------------------------------------------

    async def get_current_user(self) -> Dict[str, Any]:
        """Get the current user."""
        resp = await self.client.get("/users/me")
        resp.raise_for_status()
        return resp.json().get("user", {})

    async def list_users(
        self,
        query: Optional[str] = None,
        team_ids: Optional[List[str]] = None,
        limit: int = 25,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List users."""
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if query:
            params["query"] = query
        if team_ids:
            params["team_ids[]"] = team_ids

        resp = await self.client.get("/users", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_user(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """Get a user."""
        resp = await self.client.get(f"/users/{user_id}")
        resp.raise_for_status()
        return resp.json().get("user", {})

    # -------------------------------------------------------------------------
    # Services
    # -------------------------------------------------------------------------

    async def list_services(
        self,
        query: Optional[str] = None,
        team_ids: Optional[List[str]] = None,
        limit: int = 25,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List services."""
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if query:
            params["query"] = query
        if team_ids:
            params["team_ids[]"] = team_ids

        resp = await self.client.get("/services", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_service(
        self,
        service_id: str,
    ) -> Dict[str, Any]:
        """Get a service."""
        resp = await self.client.get(f"/services/{service_id}")
        resp.raise_for_status()
        return resp.json().get("service", {})

    async def create_service(
        self,
        name: str,
        escalation_policy_id: str,
        description: Optional[str] = None,
        auto_resolve_timeout: Optional[int] = None,
        acknowledgement_timeout: Optional[int] = None,
        alert_creation: str = "create_alerts_and_incidents",
    ) -> Dict[str, Any]:
        """Create a service."""
        payload: Dict[str, Any] = {
            "service": {
                "name": name,
                "escalation_policy": {
                    "id": escalation_policy_id,
                    "type": "escalation_policy_reference",
                },
                "alert_creation": alert_creation,
            }
        }
        if description:
            payload["service"]["description"] = description
        if auto_resolve_timeout:
            payload["service"]["auto_resolve_timeout"] = auto_resolve_timeout
        if acknowledgement_timeout:
            payload["service"]["acknowledgement_timeout"] = acknowledgement_timeout

        resp = await self.client.post("/services", json=payload)
        resp.raise_for_status()
        return resp.json().get("service", {})

    async def update_service(
        self,
        service_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a service."""
        service: Dict[str, Any] = {"type": "service"}
        if name:
            service["name"] = name
        if description:
            service["description"] = description
        if status:
            service["status"] = status

        resp = await self.client.put(
            f"/services/{service_id}", json={"service": service}
        )
        resp.raise_for_status()
        return resp.json().get("service", {})

    async def delete_service(
        self,
        service_id: str,
    ) -> bool:
        """Delete a service."""
        resp = await self.client.delete(f"/services/{service_id}")
        return resp.status_code == 204

    # -------------------------------------------------------------------------
    # Incidents
    # -------------------------------------------------------------------------

    async def list_incidents(
        self,
        statuses: Optional[List[str]] = None,
        service_ids: Optional[List[str]] = None,
        urgencies: Optional[List[str]] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 25,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        List incidents.

        Args:
            statuses: Filter by status (triggered, acknowledged, resolved)
            service_ids: Filter by service
            urgencies: Filter by urgency (high, low)
            since: Start date (ISO 8601)
            until: End date (ISO 8601)
            limit: Results per page
            offset: Pagination offset

        Returns:
            List of incidents
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if statuses:
            params["statuses[]"] = statuses
        if service_ids:
            params["service_ids[]"] = service_ids
        if urgencies:
            params["urgencies[]"] = urgencies
        if since:
            params["since"] = since
        if until:
            params["until"] = until

        resp = await self.client.get("/incidents", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_incident(
        self,
        incident_id: str,
    ) -> Dict[str, Any]:
        """Get an incident."""
        resp = await self.client.get(f"/incidents/{incident_id}")
        resp.raise_for_status()
        return resp.json().get("incident", {})

    async def create_incident(
        self,
        service_id: str,
        title: str,
        urgency: str = "high",
        body: Optional[str] = None,
        escalation_policy_id: Optional[str] = None,
        incident_key: Optional[str] = None,
        priority_id: Optional[str] = None,
        assignments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Create an incident."""
        incident: Dict[str, Any] = {
            "type": "incident",
            "title": title,
            "service": {"id": service_id, "type": "service_reference"},
            "urgency": urgency,
        }
        if body:
            incident["body"] = {"type": "incident_body", "details": body}
        if escalation_policy_id:
            incident["escalation_policy"] = {
                "id": escalation_policy_id,
                "type": "escalation_policy_reference",
            }
        if incident_key:
            incident["incident_key"] = incident_key
        if priority_id:
            incident["priority"] = {"id": priority_id, "type": "priority_reference"}
        if assignments:
            incident["assignments"] = assignments

        resp = await self.client.post("/incidents", json={"incident": incident})
        resp.raise_for_status()
        return resp.json().get("incident", {})

    async def update_incident(
        self,
        incident_id: str,
        status: Optional[str] = None,
        title: Optional[str] = None,
        urgency: Optional[str] = None,
        resolution: Optional[str] = None,
        escalation_level: Optional[int] = None,
        assignments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Update an incident."""
        incident: Dict[str, Any] = {"id": incident_id, "type": "incident_reference"}
        if status:
            incident["status"] = status
        if title:
            incident["title"] = title
        if urgency:
            incident["urgency"] = urgency
        if resolution:
            incident["resolution"] = resolution
        if escalation_level is not None:
            incident["escalation_level"] = escalation_level
        if assignments:
            incident["assignments"] = assignments

        resp = await self.client.put(
            f"/incidents/{incident_id}", json={"incident": incident}
        )
        resp.raise_for_status()
        return resp.json().get("incident", {})

    async def acknowledge_incident(
        self,
        incident_id: str,
        from_email: str,
    ) -> Dict[str, Any]:
        """Acknowledge an incident."""
        return await self.update_incident(incident_id, status="acknowledged")

    async def resolve_incident(
        self,
        incident_id: str,
        from_email: str,
        resolution: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resolve an incident."""
        return await self.update_incident(
            incident_id, status="resolved", resolution=resolution
        )

    async def merge_incidents(
        self,
        parent_incident_id: str,
        source_incident_ids: List[str],
        from_email: str,
    ) -> Dict[str, Any]:
        """Merge incidents."""
        source_incidents = [
            {"id": sid, "type": "incident_reference"} for sid in source_incident_ids
        ]
        payload = {"source_incidents": source_incidents}
        headers = {"From": from_email}

        resp = await self.client.put(
            f"/incidents/{parent_incident_id}/merge",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json().get("incident", {})

    async def snooze_incident(
        self,
        incident_id: str,
        from_email: str,
        duration: int,
    ) -> Dict[str, Any]:
        """Snooze an incident."""
        payload = {"duration": duration}
        headers = {"From": from_email}

        resp = await self.client.post(
            f"/incidents/{incident_id}/snooze",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json().get("incident", {})

    async def add_incident_note(
        self,
        incident_id: str,
        from_email: str,
        content: str,
    ) -> Dict[str, Any]:
        """Add a note to an incident."""
        payload = {"note": {"content": content}}
        headers = {"From": from_email}

        resp = await self.client.post(
            f"/incidents/{incident_id}/notes",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json().get("note", {})

    async def get_incident_notes(
        self,
        incident_id: str,
    ) -> List[Dict[str, Any]]:
        """Get notes for an incident."""
        resp = await self.client.get(f"/incidents/{incident_id}/notes")
        resp.raise_for_status()
        return resp.json().get("notes", [])

    async def get_incident_alerts(
        self,
        incident_id: str,
    ) -> List[Dict[str, Any]]:
        """Get alerts for an incident."""
        resp = await self.client.get(f"/incidents/{incident_id}/alerts")
        resp.raise_for_status()
        return resp.json().get("alerts", [])

    # -------------------------------------------------------------------------
    # Escalation Policies
    # -------------------------------------------------------------------------

    async def list_escalation_policies(
        self,
        query: Optional[str] = None,
        limit: int = 25,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List escalation policies."""
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if query:
            params["query"] = query

        resp = await self.client.get("/escalation_policies", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_escalation_policy(
        self,
        policy_id: str,
    ) -> Dict[str, Any]:
        """Get an escalation policy."""
        resp = await self.client.get(f"/escalation_policies/{policy_id}")
        resp.raise_for_status()
        return resp.json().get("escalation_policy", {})

    # -------------------------------------------------------------------------
    # Schedules
    # -------------------------------------------------------------------------

    async def list_schedules(
        self,
        query: Optional[str] = None,
        limit: int = 25,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List schedules."""
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if query:
            params["query"] = query

        resp = await self.client.get("/schedules", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_schedule(
        self,
        schedule_id: str,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a schedule with on-call info."""
        params: Dict[str, Any] = {}
        if since:
            params["since"] = since
        if until:
            params["until"] = until

        resp = await self.client.get(f"/schedules/{schedule_id}", params=params)
        resp.raise_for_status()
        return resp.json().get("schedule", {})

    # -------------------------------------------------------------------------
    # On-Call
    # -------------------------------------------------------------------------

    async def list_oncalls(
        self,
        since: Optional[str] = None,
        until: Optional[str] = None,
        schedule_ids: Optional[List[str]] = None,
        user_ids: Optional[List[str]] = None,
        escalation_policy_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """List on-call entries."""
        params: Dict[str, Any] = {}
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        if schedule_ids:
            params["schedule_ids[]"] = schedule_ids
        if user_ids:
            params["user_ids[]"] = user_ids
        if escalation_policy_ids:
            params["escalation_policy_ids[]"] = escalation_policy_ids

        resp = await self.client.get("/oncalls", params=params)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Webhooks
    # -------------------------------------------------------------------------

    async def list_webhooks(
        self,
        limit: int = 25,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List webhooks."""
        params = {"limit": limit, "offset": offset}
        resp = await self.client.get("/webhook_subscriptions", params=params)
        resp.raise_for_status()
        return resp.json()

    async def create_webhook(
        self,
        description: str,
        delivery_method_url: str,
        delivery_method_type: str = "http_delivery_method",
        events: Optional[List[str]] = None,
        filter_type: str = "account_reference",
    ) -> Dict[str, Any]:
        """
        Create a webhook subscription.

        Args:
            description: Webhook description
            delivery_method_url: URL to receive events
            delivery_method_type: http_delivery_method
            events: Event types to subscribe to
            filter_type: account_reference or service_reference

        Returns:
            Created webhook
        """
        if events is None:
            events = [
                "incident.triggered",
                "incident.acknowledged",
                "incident.resolved",
                "incident.reassigned",
            ]

        payload = {
            "webhook_subscription": {
                "type": "webhook_subscription",
                "description": description,
                "delivery_method": {
                    "type": delivery_method_type,
                    "url": delivery_method_url,
                },
                "events": events,
                "filter": {"type": filter_type},
            }
        }

        resp = await self.client.post("/webhook_subscriptions", json=payload)
        resp.raise_for_status()
        return resp.json().get("webhook_subscription", {})

    async def delete_webhook(
        self,
        webhook_id: str,
    ) -> bool:
        """Delete a webhook."""
        resp = await self.client.delete(f"/webhook_subscriptions/{webhook_id}")
        return resp.status_code == 204
