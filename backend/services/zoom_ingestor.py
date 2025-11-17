"""
Zoom Meeting Ingestion Service for AEP/NAVI

Downloads Zoom meeting transcripts, summarizes them with LLM,
detects Jira ticket references, and stores as NAVI memory entries.
"""

import re
import os
from datetime import date
from typing import List

from sqlalchemy.orm import Session
from openai import AsyncOpenAI
import structlog

from backend.integrations.zoom_client import ZoomClient
from backend.services.navi_memory_service import store_memory

logger = structlog.get_logger(__name__)

# Initialize OpenAI client
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

JIRA_KEY_RE = re.compile(r"\b[A-Z]{2,10}-\d+\b")  # LAB-158, ENG-102, etc.


def _clean_transcript_text(text: str) -> str:
    """
    Basic cleanup for Zoom transcript/VTT:
    - strip timestamp lines
    - collapse multiple spaces
    """
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        # skip typical VTT timestamp lines (00:00:00.000 --> 00:00:02.000)
        if "-->" in stripped and ":" in stripped:
            continue
        if stripped.isdigit():
            # sequence numbers in some transcript formats
            continue
        if stripped:
            lines.append(stripped)

    cleaned = " ".join(lines)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


async def _summarize_meeting(topic: str, transcript: str) -> str:
    """
    Summarize a Zoom meeting transcript into NAVI-friendly memory.

    Args:
        topic: Meeting topic/title
        transcript: Raw transcript text

    Returns:
        Summarized meeting content
    """
    prompt = f"""
You are NAVI. Summarize this engineering meeting.

Focus on:
- context & purpose of the meeting
- key technical decisions
- Jira keys or tickets mentioned
- action items and owners
- risks / open questions

Meeting topic: {topic}

Transcript:
{transcript[:16000]}

Return only the summary, no section headings.
"""

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.3,
    )
    content = response.choices[0].message.content
    return content.strip() if content else ""


async def ingest_zoom_meetings(
    db: Session,
    *,
    user_id: str,
    zoom_user: str,
    from_date: date,
    to_date: date,
    max_meetings: int = 20,
) -> List[str]:
    """
    Ingest Zoom meetings for a given Zoom user and date range.

    Stores summaries in NAVI memory as interaction entries:
      - category = "interaction"
      - tags.source = "zoom"
      - scope = first Jira key mentioned OR meeting topic

    Args:
        db: Database session
        user_id: NAVI user identifier
        zoom_user: Zoom user ID or email
        from_date: Start date for meeting search
        to_date: End date for meeting search
        max_meetings: Maximum number of meetings to process

    Returns:
        List of processed meeting IDs

    Raises:
        RuntimeError: If Zoom credentials are not configured
    """
    logger.info(
        "Starting Zoom ingestion",
        user_id=user_id,
        zoom_user=zoom_user,
        from_date=str(from_date),
        to_date=str(to_date),
        max_meetings=max_meetings,
    )

    zc = ZoomClient()
    meetings = zc.list_recordings_for_user(
        user_id=zoom_user,
        from_date=from_date,
        to_date=to_date,
        page_size=max_meetings,
    )

    logger.info(f"Found {len(meetings)} Zoom meetings with recordings")

    processed_meetings: List[str] = []

    for m in meetings:
        meeting_id = str(m.get("id") or m.get("uuid") or "")
        topic_raw = m.get("topic") or "Zoom meeting"
        topic = topic_raw.strip() if topic_raw else "Zoom meeting"
        start_time_raw = m.get("start_time") or ""
        start_time = start_time_raw.strip() if start_time_raw else ""
        host_email_raw = m.get("host_email") or ""
        host_email = host_email_raw.strip() if host_email_raw else ""

        logger.info(
            "Processing Zoom meeting",
            meeting_id=meeting_id,
            topic=topic,
            start_time=start_time,
        )

        transcript_text = zc.get_meeting_transcript_text(m)
        if not transcript_text:
            logger.info(
                "No transcript available for meeting",
                meeting_id=meeting_id,
                topic=topic,
            )
            continue

        cleaned = _clean_transcript_text(transcript_text)
        if not cleaned:
            logger.info(
                "Transcript is empty after cleaning",
                meeting_id=meeting_id,
            )
            continue

        summary = await _summarize_meeting(topic, cleaned)

        # Detect Jira keys
        jira_keys = set(JIRA_KEY_RE.findall(cleaned))
        scope = list(jira_keys)[0] if jira_keys else topic

        logger.info(
            "Storing Zoom meeting in memory",
            meeting_id=meeting_id,
            topic=topic,
            scope=scope,
            jira_keys=list(jira_keys),
        )

        await store_memory(
            db,
            user_id=user_id,
            category="interaction",
            scope=scope,
            title=f"[Zoom] {topic} ({start_time or 'no time'})",
            content=summary,
            tags={
                "source": "zoom",
                "meeting_id": meeting_id,
                "topic": topic,
                "start_time": start_time,
                "host_email": host_email,
                "jira_keys": list(jira_keys),
            },
            importance=5,  # meetings usually important
        )

        processed_meetings.append(meeting_id)

    logger.info(
        "Zoom ingestion complete",
        user_id=user_id,
        processed_count=len(processed_meetings),
    )

    return processed_meetings
