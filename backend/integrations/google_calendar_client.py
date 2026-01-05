"""Google Calendar client for NAVI Meet ingestion."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import httpx


class GoogleCalendarClient:
    def __init__(
        self,
        *,
        access_token: Optional[str],
        refresh_token: Optional[str] = None,
        expires_at: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.expires_at = None
        if expires_at:
            try:
                self.expires_at = datetime.fromisoformat(
                    str(expires_at).replace("Z", "+00:00")
                )
            except Exception:
                self.expires_at = None

        if not self.access_token and not self.refresh_token:
            raise RuntimeError(
                "GoogleCalendarClient requires access_token or refresh_token"
            )

    def _token_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) >= self.expires_at

    async def _refresh_access_token(self) -> str:
        if not self.refresh_token or not self.client_id or not self.client_secret:
            raise RuntimeError(
                "Google token refresh requires client_id, client_secret, refresh_token"
            )

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Google refresh token failed: {resp.status_code} {resp.text[:200]}"
            )

        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError("Google refresh response missing access_token")
        self.access_token = token
        expires_in = data.get("expires_in")
        if expires_in:
            try:
                self.expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=int(expires_in)
                )
            except Exception:
                self.expires_at = None
        return token

    async def _get_token(self) -> str:
        if self.access_token and not self._token_expired():
            return self.access_token
        if self.refresh_token:
            return await self._refresh_access_token()
        raise RuntimeError("Google access token missing or expired")

    async def _get(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        token = await self._get_token()
        url = f"https://www.googleapis.com/calendar/v3{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url,
                params=params or {},
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Google Calendar GET {url} failed: {resp.status_code} {resp.text[:200]}"
            )
        return resp.json()

    async def _post(self, path: str, json_body: Dict[str, Any]) -> Dict[str, Any]:
        token = await self._get_token()
        url = f"https://www.googleapis.com/calendar/v3{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                json=json_body,
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Google Calendar POST {url} failed: {resp.status_code} {resp.text[:200]}"
            )
        return resp.json()

    async def list_events(
        self,
        *,
        calendar_id: str,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        updated_min: Optional[datetime] = None,
        max_results: int = 250,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": max_results,
        }
        if time_min:
            params["timeMin"] = time_min.astimezone(timezone.utc).isoformat()
        if time_max:
            params["timeMax"] = time_max.astimezone(timezone.utc).isoformat()
        if updated_min:
            params["updatedMin"] = updated_min.astimezone(timezone.utc).isoformat()

        data = await self._get(f"/calendars/{calendar_id}/events", params=params)
        return data.get("items", []) or []

    async def watch_events(
        self,
        *,
        calendar_id: str,
        channel_id: str,
        notification_url: str,
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        body = {
            "id": channel_id,
            "type": "web_hook",
            "address": notification_url,
        }
        if token:
            body["token"] = token
        return await self._post(
            f"/calendars/{calendar_id}/events/watch", json_body=body
        )
