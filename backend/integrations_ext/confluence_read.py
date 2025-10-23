"""Confluence Read Connector - read-only access to Confluence pages"""

import httpx
from typing import List, Dict, Optional


class ConfluenceReader:
    def __init__(self, base_url: str, token: str, email: Optional[str] = None):
        self.base = base_url.rstrip("/")
        self.token = token
        self.email = email

    async def pages(
        self,
        client: httpx.AsyncClient,
        space_key: str,
        start=0,
        limit=100,
    ) -> List[Dict]:
        """Fetch pages from a Confluence space with pagination"""
        auth = {"Authorization": f"Basic {self.token}"}
        r = await client.get(
            f"{self.base}/rest/api/space/{space_key}/content",
            headers=auth,
            params={"start": start, "limit": limit, "expand": "body.storage,version"},
        )
        r.raise_for_status()
        j = r.json()
        results = (j.get("page", {}) or {}).get("results") or j.get("results") or []
        out = []
        for p in results:
            title = p.get("title")
            pid = p.get("id")
            body = ((p.get("body") or {}).get("storage") or {}).get("value", "")
            url = f"{self.base}/pages/{pid}"
            ver = ((p.get("version") or {}).get("number")) or 1
            out.append(
                {
                    "id": pid,
                    "title": title,
                    "url": url,
                    "html": body,
                    "version": ver,
                }
            )
        return out
