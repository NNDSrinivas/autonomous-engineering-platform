# backend/services/confluence_service.py

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

try:
    from backend.core.integrations.confluence_client import ConfluenceClient  # type: ignore
except Exception:  # pragma: no cover
    ConfluenceClient = None  # type: ignore[misc]


def _get_client(db: Optional[Session] = None) -> Optional["ConfluenceClient"]:
    """
    Helper to construct a ConfluenceClient instance if the integration is available.
    """
    if ConfluenceClient is None:
        return None

    try:
        return ConfluenceClient()
    except Exception:
        return None


def search_pages(
    db: Session,
    query: str,
    user_id: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Search Confluence pages by query text (for unified memory retriever).
    
    Returns normalized page format:
    {
        "id": str,
        "title": str,
        "excerpt": str,
        "body": str,
        "url": str | None,
        "updated_at": str | None,
        "space": str | None,
        "labels": list | None,
    }
    """
    client = _get_client(db)
    if client is None:
        return []

    try:
        raw_pages = client.search_pages(
            query=query,
            limit=limit,
        )
    except AttributeError:
        return []
    except Exception:
        return []

    normalized: List[Dict[str, Any]] = []
    for page in raw_pages or []:
        normalized.append(
            {
                "id": str(page.get("id") or ""),
                "title": page.get("title") or "",
                "excerpt": page.get("excerpt") or "",
                "body": page.get("body") or page.get("content") or "",
                "url": page.get("url") or page.get("_links", {}).get("webui"),
                "updated_at": page.get("updated") or page.get("lastModified"),
                "space": page.get("space", {}).get("key") if isinstance(page.get("space"), dict) else page.get("space"),
                "labels": page.get("labels") or [],
            }
        )

    return normalized