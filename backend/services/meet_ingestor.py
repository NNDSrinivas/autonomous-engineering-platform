"""Google Meet ingestion helpers (Calendar events)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import re
from typing import Any, Dict, List, Optional

import structlog
from dotenv import load_dotenv
from openai import AsyncOpenAI
from sqlalchemy import text

from backend.core.config import settings
from backend.integrations.google_calendar_client import GoogleCalendarClient
from backend.integrations.google_drive_client import GoogleDriveClient
from backend.services import connectors as connectors_service
from backend.services.navi_memory_service import store_memory

logger = structlog.get_logger(__name__)
load_dotenv()

JIRA_KEY_RE = re.compile(r"\b[A-Z]{2,10}-\d+\b")
_openai_client: Optional[AsyncOpenAI] = None


def _event_start_end(event: Dict[str, Any]) -> tuple[str | None, str | None]:
    start = (event.get("start") or {}).get("dateTime") or (event.get("start") or {}).get("date")
    end = (event.get("end") or {}).get("dateTime") or (event.get("end") or {}).get("date")
    return start, end


def _meet_link(event: Dict[str, Any]) -> Optional[str]:
    link = event.get("hangoutLink")
    if link:
        return link
    conference = event.get("conferenceData") or {}
    for entry in conference.get("entryPoints", []) or []:
        if entry.get("entryPointType") == "video" and entry.get("uri"):
            return entry.get("uri")
    return None


def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY environment variable must be set")
        _openai_client = AsyncOpenAI(api_key=api_key)
    return _openai_client


def _clean_transcript_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if "-->" in stripped and ":" in stripped:
            continue
        if stripped.isdigit():
            continue
        if stripped:
            lines.append(stripped)
    cleaned = " ".join(lines)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


async def _summarize_transcript(title: str, transcript: str) -> str:
    prompt = f"""
You are NAVI. Summarize this engineering meeting transcript.

Focus on:
- context & purpose of the meeting
- key technical decisions
- Jira keys or tickets mentioned
- action items and owners
- risks / open questions

Meeting: {title}

Transcript:
{transcript[:16000]}

Return only the summary, no section headings.
""".strip()
    try:
        openai_client = _get_openai_client()
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.3,
        )
        content = response.choices[0].message.content
        return content.strip() if content else ""
    except Exception as exc:
        logger.warning("Meet transcript summarization failed", error=str(exc))
        return transcript[:2000]


def _parse_event_datetime(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def _safe_drive_query_value(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.replace("'", "").strip()


def _build_transcript_query(
    *,
    title: Optional[str],
    start: Optional[datetime],
    end: Optional[datetime],
) -> str:
    parts = [
        "trashed = false",
        "(mimeType = 'application/vnd.google-apps.document' or mimeType = 'text/plain')",
        "name contains 'Transcript'",
    ]
    safe_title = _safe_drive_query_value(title)
    if safe_title and safe_title.lower() not in {"google meet", "meeting"}:
        parts.append(f"name contains '{safe_title}'")
    if start:
        window_start = (start - timedelta(hours=2)).astimezone(timezone.utc).isoformat()
        parts.append(f"modifiedTime >= '{window_start}'")
    if end:
        window_end = (end + timedelta(hours=12)).astimezone(timezone.utc).isoformat()
        parts.append(f"modifiedTime <= '{window_end}'")
    return " and ".join(parts)


def _resolve_google_oauth_app(
    db,
    org_id: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    if not org_id:
        return settings.google_client_id, settings.google_client_secret

    stored = connectors_service.get_oauth_app_config(
        db=db,
        org_id=str(org_id),
        provider="meet",
    )
    config = (stored or {}).get("config") or {}
    secrets = (stored or {}).get("secrets") or {}
    client_id = config.get("client_id") or settings.google_client_id
    client_secret = secrets.get("client_secret") or settings.google_client_secret
    return client_id, client_secret


def _build_client(
    connector: Dict[str, Any],
    *,
    client_id: Optional[str],
    client_secret: Optional[str],
) -> GoogleCalendarClient:
    secrets = connector.get("secrets") or {}
    cfg = connector.get("config") or {}
    return GoogleCalendarClient(
        access_token=secrets.get("access_token") or secrets.get("token"),
        refresh_token=secrets.get("refresh_token"),
        expires_at=cfg.get("expires_at"),
        client_id=client_id,
        client_secret=client_secret,
    )


def _build_drive_client(
    connector: Dict[str, Any],
    *,
    client_id: Optional[str],
    client_secret: Optional[str],
) -> GoogleDriveClient:
    secrets = connector.get("secrets") or {}
    cfg = connector.get("config") or {}
    return GoogleDriveClient(
        access_token=secrets.get("access_token") or secrets.get("token"),
        refresh_token=secrets.get("refresh_token"),
        expires_at=cfg.get("expires_at"),
        client_id=client_id,
        client_secret=client_secret,
    )


async def list_meet_events(
    *,
    db,
    user_id: str,
    org_id: Optional[str],
    calendar_id: str,
    days_back: int,
    updated_min: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    connector = connectors_service.get_connector_for_context(
        db,
        user_id=user_id,
        org_id=org_id,
        provider="meet",
    )
    if not connector:
        raise RuntimeError("Meet connector not configured")

    resolved_org_id = org_id or (connector.get("config") or {}).get("org_id")
    client_id, client_secret = _resolve_google_oauth_app(db, resolved_org_id)
    client = _build_client(connector, client_id=client_id, client_secret=client_secret)
    time_min = datetime.now(timezone.utc) - timedelta(days=days_back)
    events = await client.list_events(
        calendar_id=calendar_id,
        time_min=time_min,
        updated_min=updated_min,
    )

    # Persist refreshed token if needed
    cfg = connector.get("config") or {}
    secrets = connector.get("secrets") or {}
    if client.access_token and client.access_token != secrets.get("access_token"):
        connectors_service.save_meet_connection(
            user_id=str(user_id),
            org_id=org_id or cfg.get("org_id"),
            calendar_id=calendar_id,
            scopes=cfg.get("scopes"),
            access_token=client.access_token,
            refresh_token=secrets.get("refresh_token"),
            expires_at=client.expires_at.isoformat() if client.expires_at else cfg.get("expires_at"),
            channel_id=cfg.get("channel_id"),
            resource_id=cfg.get("resource_id"),
            channel_token=cfg.get("channel_token"),
            db=db,
        )

    return events


async def store_meet_events(
    *,
    db,
    user_id: str,
    events: List[Dict[str, Any]],
) -> List[str]:
    processed: List[str] = []
    for event in events:
        event_id = event.get("id")
        if not event_id:
            continue

        meet_link = _meet_link(event)
        if not meet_link:
            continue

        summary = event.get("summary") or "Google Meet"
        description = event.get("description") or ""
        organizer = (event.get("organizer") or {}).get("email")
        attendees = [a.get("email") for a in (event.get("attendees") or []) if a.get("email")]
        start, end = _event_start_end(event)

        content = (
            f"Meeting: {summary}\n"
            f"Start: {start}\nEnd: {end}\n"
            f"Organizer: {organizer}\n"
            f"Attendees: {', '.join(attendees) if attendees else 'N/A'}\n"
            f"Meet Link: {meet_link}\n\n"
            f"{description}".strip()
        )

        await store_memory(
            db,
            user_id=user_id,
            category="interaction",
            scope="meet",
            title=f"[Meet] {summary}",
            content=content,
            tags={
                "source": "meet",
                "event_id": event_id,
                "meet_link": meet_link,
                "start": start,
                "end": end,
            },
            importance=3,
        )
        processed.append(event_id)

    return processed


async def store_meet_transcripts(
    *,
    db,
    user_id: str,
    org_id: Optional[str],
    events: List[Dict[str, Any]],
    max_files_per_event: int = 3,
) -> List[str]:
    connector = connectors_service.get_connector_for_context(
        db,
        user_id=user_id,
        org_id=org_id,
        provider="meet",
    )
    if not connector:
        raise RuntimeError("Meet connector not configured")

    resolved_org_id = org_id or (connector.get("config") or {}).get("org_id")
    client_id, client_secret = _resolve_google_oauth_app(db, resolved_org_id)
    drive_client = _build_drive_client(connector, client_id=client_id, client_secret=client_secret)
    cfg = connector.get("config") or {}
    secrets = connector.get("secrets") or {}

    processed_files: List[str] = []

    for event in events:
        event_id = event.get("id")
        if not event_id:
            continue

        summary = event.get("summary") or "Google Meet"
        start_raw, end_raw = _event_start_end(event)
        start_dt = _parse_event_datetime(start_raw)
        end_dt = _parse_event_datetime(end_raw)

        query = _build_transcript_query(title=summary, start=start_dt, end=end_dt)
        try:
            files = await drive_client.list_files(query=query, page_size=max_files_per_event)
        except Exception as exc:
            logger.warning("Drive transcript search failed", error=str(exc), event_id=event_id)
            continue

        for file_info in files:
            file_id = file_info.get("id")
            if not file_id:
                continue
            scope = f"meet_transcript:{file_id}"
            existing = db.execute(
                text(
                    """
                    SELECT id FROM navi_memory
                    WHERE user_id = :user_id AND scope = :scope
                    LIMIT 1
                    """
                ),
                {"user_id": user_id, "scope": scope},
            ).first()
            if existing:
                continue

            mime_type = file_info.get("mimeType") or ""
            transcript_text = await drive_client.download_text(file_id, mime_type)
            if not transcript_text:
                continue

            cleaned = _clean_transcript_text(transcript_text)
            if not cleaned:
                continue

            jira_keys = set(JIRA_KEY_RE.findall(cleaned))
            jira_hint = f" ({list(jira_keys)[0]})" if jira_keys else ""
            title = f"[Meet Transcript] {summary}{jira_hint}"
            summary_text = await _summarize_transcript(summary, cleaned)

            await store_memory(
                db,
                user_id=user_id,
                category="interaction",
                scope=scope,
                title=title,
                content=summary_text or cleaned[:2000],
                tags={
                    "source": "meet_transcript",
                    "event_id": event_id,
                    "file_id": file_id,
                    "file_name": file_info.get("name"),
                    "mime_type": mime_type,
                    "meet_link": _meet_link(event),
                    "jira_keys": list(jira_keys),
                    "web_view_link": file_info.get("webViewLink"),
                },
                importance=4,
            )
            processed_files.append(file_id)

    if drive_client.access_token and drive_client.access_token != secrets.get("access_token"):
        connectors_service.save_meet_connection(
            user_id=str(user_id),
            org_id=org_id or cfg.get("org_id"),
            calendar_id=cfg.get("calendar_id") or "primary",
            scopes=cfg.get("scopes"),
            access_token=drive_client.access_token,
            refresh_token=secrets.get("refresh_token"),
            expires_at=drive_client.expires_at.isoformat() if drive_client.expires_at else cfg.get("expires_at"),
            channel_id=cfg.get("channel_id"),
            resource_id=cfg.get("resource_id"),
            channel_token=cfg.get("channel_token"),
            last_sync=cfg.get("last_sync"),
            db=db,
        )

    return processed_files


async def create_meet_watch(
    *,
    access_token: Optional[str],
    refresh_token: Optional[str],
    expires_at: Optional[str],
    calendar_id: str,
    channel_id: str,
    notification_url: str,
    channel_token: Optional[str],
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
) -> Dict[str, Any]:
    client = GoogleCalendarClient(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        client_id=client_id or settings.google_client_id,
        client_secret=client_secret or settings.google_client_secret,
    )
    response = await client.watch_events(
        calendar_id=calendar_id,
        channel_id=channel_id,
        notification_url=notification_url,
        token=channel_token,
    )
    expires_at_iso = None
    if response.get("expiration"):
        try:
            expires_at_iso = datetime.fromtimestamp(int(response["expiration"]) / 1000, tz=timezone.utc).isoformat()
        except Exception:
            expires_at_iso = None

    return {
        "channel_id": response.get("id") or channel_id,
        "resource_id": response.get("resourceId"),
        "expires_at": expires_at_iso,
        "channel_token": channel_token,
    }
