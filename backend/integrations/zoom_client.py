"""
Zoom REST API Client for AEP/NAVI

Supports:
- Server-to-Server OAuth authentication
- Retrieving cloud recordings for a user in a date range
- Locating and downloading transcript files for meetings
"""

import os
import base64
from typing import Dict, Any, List, Optional
from datetime import date, datetime, timezone, timedelta

import requests


class ZoomClient:
    """
    Minimal Zoom REST API client for AEP/NAVI.

    Supports:
      - retrieving cloud recordings for a user in a date range
      - locating transcript files for meetings
    """

    def __init__(
        self,
        account_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> None:
        self.account_id = account_id or os.getenv("AEP_ZOOM_ACCOUNT_ID", "")
        self.client_id = client_id or os.getenv("AEP_ZOOM_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("AEP_ZOOM_CLIENT_SECRET", "")
        self.refresh_token = refresh_token
        self.expires_at = expires_at
        self._token: Optional[str] = access_token
        self.base_url = "https://api.zoom.us/v2"

        if not self._token and not (
            self.account_id and self.client_id and self.client_secret
        ):
            raise RuntimeError(
                "ZoomClient requires either an access token or "
                "AEP_ZOOM_ACCOUNT_ID, AEP_ZOOM_CLIENT_ID, AEP_ZOOM_CLIENT_SECRET."
            )

    def _token_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) >= self.expires_at

    def _refresh_access_token(self) -> str:
        if not self.refresh_token or not self.client_id or not self.client_secret:
            raise RuntimeError("Zoom refresh requires client_id, client_secret, refresh_token")

        auth_bytes = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        basic_auth = base64.b64encode(auth_bytes).decode("utf-8")

        resp = requests.post(
            "https://zoom.us/oauth/token",
            headers={
                "Authorization": f"Basic {basic_auth}",
            },
            params={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            },
            timeout=30,
        )
        if not resp.ok:
            raise RuntimeError(
                f"Zoom refresh token error: {resp.status_code} {resp.text[:300]}"
            )

        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError("Zoom refresh token response missing access_token")

        self._token = token
        new_refresh = data.get("refresh_token")
        if new_refresh:
            self.refresh_token = new_refresh
        expires_in = data.get("expires_in")
        if expires_in:
            try:
                self.expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
            except Exception:
                self.expires_at = None
        return token

    # ------------------------------------------------------------------ #
    # Auth
    # ------------------------------------------------------------------ #
    def _get_access_token(self) -> str:
        """Get OAuth access token using Server-to-Server OAuth flow"""
        if self._token and not self._token_expired():
            return self._token
        if self.refresh_token:
            return self._refresh_access_token()

        auth_bytes = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        basic_auth = base64.b64encode(auth_bytes).decode("utf-8")

        resp = requests.post(
            "https://zoom.us/oauth/token",
            headers={
                "Authorization": f"Basic {basic_auth}",
            },
            params={
                "grant_type": "account_credentials",
                "account_id": self.account_id,
            },
            timeout=30,
        )
        if not resp.ok:
            raise RuntimeError(
                f"Zoom token error: {resp.status_code} {resp.text[:300]}"
            )

        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError("Zoom token response missing access_token")

        self._token = token
        return token

    def _get(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make authenticated GET request to Zoom API"""
        token = self._get_access_token()
        url = f"{self.base_url}{path}"
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
            timeout=30,
        )
        if not resp.ok:
            raise RuntimeError(
                f"Zoom GET {url} failed: {resp.status_code} {resp.text[:300]}"
            )
        return resp.json()

    def _download(self, url: str) -> str:
        """Download file content from Zoom with authentication"""
        token = self._get_access_token()
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        if not resp.ok:
            raise RuntimeError(
                f"Zoom download failed: {resp.status_code} {resp.text[:300]}"
            )
        return resp.text

    # ------------------------------------------------------------------ #
    # Recordings & transcripts
    # ------------------------------------------------------------------ #
    def list_recordings_for_user(
        self,
        user_id: str,
        from_date: date,
        to_date: date,
        page_size: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        List cloud recordings for a user between from_date and to_date.

        Args:
            user_id: Zoom user ID or email
            from_date: Start date for recordings
            to_date: End date for recordings
            page_size: Maximum number of results per page

        Returns:
            List of meeting dictionaries with recording data
        """
        data = self._get(
            f"/users/{user_id}/recordings",
            params={
                "from": from_date.isoformat(),
                "to": to_date.isoformat(),
                "page_size": page_size,
            },
        )
        return data.get("meetings", [])

    def get_meeting_transcript_text(self, meeting: Dict[str, Any]) -> Optional[str]:
        """
        Given a meeting entry from list_recordings_for_user, try to find
        a transcript recording file (VTT or text) and return its content.

        Args:
            meeting: Meeting dictionary from list_recordings_for_user

        Returns:
            Transcript text content, or None if no transcript available
        """
        recording_files = meeting.get("recording_files", []) or []
        transcript_file = None

        # Look for a transcript-like file
        for f in recording_files:
            file_type = (f.get("file_type") or "").upper()
            if file_type in ("TRANSCRIPT", "TRANSCRIPT_VTT", "VTT"):
                transcript_file = f
                break

        if not transcript_file:
            return None

        download_url = transcript_file.get("download_url")
        if not download_url:
            return None

        # Zoom requires auth header even for download_url
        return self._download(download_url)
