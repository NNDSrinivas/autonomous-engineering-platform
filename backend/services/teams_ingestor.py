"""Microsoft Teams Ingestor Service

This service ingests Teams messages from engineering teams/channels into NAVI's
conversational memory system. It fetches messages, summarizes them with LLM,
and automatically links them to Jira tickets when mentioned.
"""

import os
import re
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
import structlog

from backend.integrations.teams_client import TeamsClient
from backend.services.navi_memory_service import store_memory

# Load environment variables
load_dotenv()

logger = structlog.get_logger(__name__)

# Initialize OpenAI for summarization
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Regex to detect Jira keys (e.g., LAB-158, ENG-102)
JIRA_KEY_RE = re.compile(r"\b[A-Z]{2,10}-\d+\b")


def _clean_teams_text(text: str) -> str:
    """
    Remove Teams markup from text.

    - Removes @mention tags: <at>user</at> → ""
    - Removes HTML tags
    - Unescapes HTML entities

    Args:
        text: Raw Teams message content (HTML)

    Returns:
        Cleaned text suitable for LLM processing
    """
    text = re.sub(r"<at>.*?</at>", "", text)  # remove @mention tags
    text = re.sub(r"<[^>]+>", " ", text)  # remove HTML tags
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


async def _summarize_teams_messages(messages: List[Dict[str, Any]]) -> str:
    """
    Summarize a batch of Teams messages using OpenAI.

    Focuses on:
    - Engineering decisions
    - Technical issues and debugging
    - Jira references
    - Action items and blockers

    Args:
        messages: List of Teams message dictionaries

    Returns:
        Concise summary suitable for memory storage
    """
    body_lines = []

    for m in messages:
        from_info = m.get("from", {}) or {}
        user_info = from_info.get("user", {}) or {}
        app_info = from_info.get("application", {}) or {}

        user_name = (
            user_info.get("displayName") or app_info.get("displayName") or "unknown"
        )

        body_info = m.get("body", {}) or {}
        content = body_info.get("content", "") or ""
        text = _clean_teams_text(content)

        if text:
            body_lines.append(f"[{user_name}] {text}")

    body = "\n".join(body_lines)

    if not body.strip():
        return ""

    prompt = f"""You are NAVI's memory compression assistant.

Summarize this Microsoft Teams engineering discussion.

Focus on:
- Key engineering decisions
- Technical issues and debugging steps
- Jira ticket references
- Blockers and concerns
- Action items and next steps

Teams messages:
{body[:4000]}

Return only the summary, no bullet labels unless needed."""

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=350,
            temperature=0.3,
        )
        content = response.choices[0].message.content
        return content.strip() if content else ""
    except Exception as e:
        logger.error("Failed to summarize Teams messages", error=str(e))
        # Fallback: return truncated raw text
        return body[:300] + "..." if len(body) > 300 else body


async def ingest_teams(
    db: Session,
    *,
    user_id: str,
    team_names: List[str],
    channels_per_team: Optional[List[str]] = None,
    limit: int = 50,
) -> List[str]:
    """
    Ingest Teams messages from specified teams and channels into NAVI memory.

    Process:
    1. Find teams by displayName
    2. Fetch channels (all or filtered)
    3. Fetch messages from each channel
    4. Summarize with LLM
    5. Detect Jira keys
    6. Store in navi_memory with embeddings

    Args:
        db: Database session
        user_id: User identifier
        team_names: List of team displayNames (e.g., ["Engineering", "Platform"])
        channels_per_team: Optional list of channel names to filter
        limit: Maximum messages per channel

    Returns:
        List of processed "team:channel" keys
    """
    logger.info(
        "Starting Teams ingestion", user_id=user_id, team_names=team_names, limit=limit
    )

    tc = TeamsClient()
    processed_channel_keys: List[str] = []

    for tname in team_names:
        tname = tname.strip()
        if not tname:
            continue

        try:
            team = tc.get_team_by_display_name(tname)
            if not team:
                logger.warning("Teams team not found", team_name=tname)
                continue

            team_id = team.get("id")
            if not team_id:
                continue

            channels = tc.list_channels(team_id)

            # Filter channels if requested
            selected_channels = []
            if channels_per_team:
                wanted = {c.lower() for c in channels_per_team}
                for c in channels:
                    dn = (c.get("displayName") or "").lower()
                    if dn in wanted:
                        selected_channels.append(c)
            else:
                selected_channels = channels

            logger.info(
                "Processing Teams channels",
                team=tname,
                channel_count=len(selected_channels),
            )

            for chan in selected_channels:
                try:
                    chan_name = chan.get("displayName", "unknown")
                    chan_id = chan.get("id")
                    if not chan_id:
                        continue

                    logger.info(
                        "Fetching Teams messages", team=tname, channel=chan_name
                    )

                    msgs = tc.fetch_channel_messages(team_id, chan_id, limit=limit)
                    if not msgs:
                        logger.debug(
                            "No messages in channel", team=tname, channel=chan_name
                        )
                        continue

                    # Summarize messages
                    summary = await _summarize_teams_messages(msgs)
                    if not summary:
                        continue

                    # Detect Jira keys
                    jira_keys = set()
                    for m in msgs:
                        content = (m.get("body", {}) or {}).get("content", "") or ""
                        for key in JIRA_KEY_RE.findall(content):
                            jira_keys.add(key)

                    # Memory scope: tie to Jira if found, otherwise team name
                    scope = list(jira_keys)[0] if jira_keys else tname

                    # Store in memory
                    await store_memory(
                        db,
                        user_id=user_id,
                        category="interaction",
                        scope=scope,
                        title=f"[Teams:{tname}/{chan_name}] Discussion ({scope})",
                        content=summary,
                        tags={
                            "source": "teams",
                            "team": tname,
                            "channel": chan_name,
                            "jira_keys": list(jira_keys),
                        },
                        importance=4,
                    )

                    processed_channel_keys.append(f"{tname}:{chan_name}")
                    logger.debug(
                        "Stored Teams thread in memory",
                        team=tname,
                        channel=chan_name,
                        scope=scope,
                        jira_keys=list(jira_keys),
                    )

                except Exception as e:
                    logger.error(
                        "Failed to process Teams channel",
                        team=tname,
                        channel=chan.get("displayName"),
                        error=str(e),
                    )
                    continue

        except Exception as e:
            logger.error("Failed to process Teams team", team=tname, error=str(e))
            continue

    logger.info(
        "Teams ingestion complete",
        user_id=user_id,
        processed_count=len(processed_channel_keys),
    )

    return processed_channel_keys
