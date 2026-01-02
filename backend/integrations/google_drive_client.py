"""Google Drive client for Meet transcript ingestion."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import httpx


class GoogleDriveClient:
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
        self.expires_at: Optional[datetime] = None
        if expires_at:
            try:
                self.expires_at = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            except Exception:
                self.expires_at = None

        if not self.access_token and not self.refresh_token:
            raise RuntimeError("GoogleDriveClient requires access_token or refresh_token")

    def _token_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) >= self.expires_at

    async def _refresh_access_token(self) -> str:
        if not self.refresh_token or not self.client_id or not self.client_secret:
            raise RuntimeError("Google token refresh requires client_id, client_secret, refresh_token")

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
            raise RuntimeError(f"Google refresh token failed: {resp.status_code} {resp.text[:200]}")

        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError("Google refresh response missing access_token")
        self.access_token = token
        expires_in = data.get("expires_in")
        if expires_in:
            try:
                self.expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
            except Exception:
                self.expires_at = None
        return token

    async def _get_token(self) -> str:
        if self.access_token and not self._token_expired():
            return self.access_token
        if self.refresh_token:
            return await self._refresh_access_token()
        raise RuntimeError("Google access token missing or expired")

    async def list_files(
        self,
        *,
        query: str,
        page_size: int = 20,
    ) -> List[Dict[str, Any]]:
        token = await self._get_token()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                "https://www.googleapis.com/drive/v3/files",
                params={
                    "q": query,
                    "pageSize": page_size,
                    "fields": "files(id,name,mimeType,createdTime,modifiedTime,webViewLink,webContentLink)",
                    "orderBy": "modifiedTime desc",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code >= 400:
            raise RuntimeError(f"Google Drive list failed: {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        return data.get("files", []) or []

    async def download_text(self, file_id: str, mime_type: str) -> Optional[str]:
        token = await self._get_token()
        if mime_type == "application/vnd.google-apps.document":
            url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
            params = {"mimeType": "text/plain"}
        else:
            url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
            params = {"alt": "media"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code >= 400:
            return None
        try:
            return resp.text.strip()
        except Exception:
            return None
