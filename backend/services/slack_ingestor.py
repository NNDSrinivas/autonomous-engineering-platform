"""Slack Ingestor Service

This service ingests Slack messages from engineering channels into NAVI's
conversational memory system. It groups messages by thread, summarizes them
with LLM, and automatically links them to Jira tickets when mentioned.
"""

import os
import re
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
import structlog

from backend.integrations.slack_client import SlackClient
from backend.services import connectors as connectors_service
from backend.services.navi_memory_service import store_memory

# Load environment variables
load_dotenv()

logger = structlog.get_logger(__name__)

# Global OpenAI client (lazy-initialized)
_openai_client: Optional[AsyncOpenAI] = None


def _get_openai_client() -> AsyncOpenAI:
    """Get or initialize OpenAI client lazily."""
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY environment variable must be set for summarization"
            )
        _openai_client = AsyncOpenAI(api_key=api_key)
    return _openai_client


# Regex to detect Jira keys (e.g., LAB-158, ENG-102)
JIRA_KEY_RE = re.compile(r"\b[A-Z]{2,10}-\d+\b")

TEXT_FILE_TYPES = {
    "txt",
    "md",
    "markdown",
    "json",
    "yaml",
    "yml",
    "csv",
    "log",
    "ini",
    "conf",
    "toml",
    "py",
    "js",
    "ts",
    "tsx",
    "jsx",
    "java",
    "go",
    "rb",
    "sh",
    "bash",
    "zsh",
}


def _clean_slack_text(text: str) -> str:
    """
    Remove Slack markup from text.

    - Removes user mentions: <@U0382ACD1> → ""
    - Removes links: <http://example.com> → ""
    - Unescapes HTML entities: &amp; → &

    Args:
        text: Raw Slack message text

    Returns:
        Cleaned text suitable for LLM processing
    """
    text = re.sub(r"<@([A-Z0-9]+)>", "", text)  # remove mentions
    text = re.sub(r"<[^>]+>", "", text)  # remove links
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    return text.strip()

def _should_fetch_file(file_info: Dict[str, Any]) -> bool:
    mimetype = (file_info.get("mimetype") or "").lower()
    if mimetype.startswith("text/"):
        return True
    filetype = (file_info.get("filetype") or "").lower()
    return filetype in TEXT_FILE_TYPES


async def _summarize_thread(
    messages: List[Dict[str, Any]],
    *,
    file_snippets: Optional[List[str]] = None,
) -> str:
    """
    Summarize a Slack thread using OpenAI.

    Focuses on:
    - Engineering decisions
    - Issues raised
    - Jira references
    - Action items
    - Conclusions

    Args:
        messages: List of Slack message dictionaries

    Returns:
        Concise summary suitable for memory storage
    """
    body = ""
    for m in messages:
        user = m.get("user", "unknown")
        text = _clean_slack_text(m.get("text", ""))
        if text:  # Skip empty messages
            body += f"[{user}] {text}\n"

    if file_snippets:
        body += "\n[Files]\n" + "\n".join(file_snippets[:10]) + "\n"

    if not body.strip():
        return "Empty thread"

    prompt = f"""You are NAVI's memory compression assistant.

Summarize this Slack engineering discussion.

Focus on:
- Key decisions made
- Technical issues raised
- Jira ticket references
- Blockers or concerns
- Action items
- Conclusions

Slack messages:
{body[:4000]}

Return only the summary, no bullet labels unless needed."""

    try:
        client = _get_openai_client()
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3,
        )
        content = response.choices[0].message.content
        return content.strip() if content else ""
    except Exception as e:
        logger.error("Failed to summarize thread", error=str(e))
        # Fallback: return truncated raw text
        return body[:300] + "..." if len(body) > 300 else body


async def ingest_slack(
    db: Session,
    *,
    user_id: str,
    channels: List[str],
    limit: int = 200,
    include_dms: bool = False,
    include_files: bool = False,
) -> List[str]:
    """
    Ingest Slack messages from specified channels into NAVI memory.

    Process:
    1. Fetch messages from each channel
    2. Group by thread
    3. Fetch full thread replies
    4. Summarize with LLM
    5. Detect Jira keys
    6. Store in navi_memory with embeddings

    Args:
        db: Database session
        user_id: User identifier
        channels: List of channel names (e.g., ["eng-backend", "specimen-collection"])
        limit: Maximum messages per channel

    Returns:
        List of processed channel IDs
    """
    logger.info(
        "Starting Slack ingestion", user_id=user_id, channels=channels, limit=limit
    )

    token = None
    connector = connectors_service.get_connector_for_context(
        db, user_id=user_id, org_id=None, provider="slack"
    )
    if connector:
        token = (connector.get("secrets") or {}).get("bot_token")
    sc = SlackClient(bot_token=token) if token else SlackClient()

    # Map channel names to channel objects
    all_channels = sc.list_channels()
    name_to_channel = {
        c["name"].lower(): c for c in all_channels if c.get("name")
    }

    user_name_cache: Dict[str, str] = {}

    def _user_name(user_id_value: Optional[str]) -> str:
        if not user_id_value:
            return "unknown"
        if user_id_value in user_name_cache:
            return user_name_cache[user_id_value]
        name = sc.get_user_name(user_id_value)
        user_name_cache[user_id_value] = name
        return name

    def _channel_label(channel: Dict[str, Any]) -> str:
        if channel.get("name"):
            return channel["name"]
        if channel.get("is_im"):
            return f"dm-{_user_name(channel.get('user'))}"
        if channel.get("is_mpim"):
            members = channel.get("members") or []
            if members:
                names = [_user_name(m) for m in members[:3]]
                joined = "-".join([n.replace(" ", "-") for n in names if n])
                return f"group-dm-{joined}" if joined else "group-dm"
            return "group-dm"
        return channel.get("id") or "unknown"

    processed_channels: List[str] = []
    channel_entries: List[Dict[str, Any]] = []
    seen_channel_ids: set[str] = set()

    for chan in channels:
        chan = chan.strip().lower()
        if not chan:
            continue
        channel = name_to_channel.get(chan)
        if not channel:
            logger.warning("Slack channel not found", channel=chan)
            continue
        channel_id = channel.get("id")
        if not channel_id or channel_id in seen_channel_ids:
            continue
        seen_channel_ids.add(channel_id)
        channel_entries.append(channel)

    if include_dms:
        for dm in sc.list_direct_messages():
            channel_id = dm.get("id")
            if not channel_id or channel_id in seen_channel_ids:
                continue
            seen_channel_ids.add(channel_id)
            channel_entries.append(dm)

    for channel in channel_entries:
        channel_id = channel.get("id")
        if not channel_id:
            continue
        channel_label = _channel_label(channel)
        channel_type = "channel"
        if channel.get("is_im"):
            channel_type = "im"
        elif channel.get("is_mpim"):
            channel_type = "mpim"

        processed_channels.append(channel_id)
        logger.info(
            "Fetching Slack messages",
            channel=channel_label,
            channel_id=channel_id,
            channel_type=channel_type,
        )

        try:
            msgs = sc.fetch_channel_messages(channel_id, limit=limit)

            # Group by parent thread
            threads = {}
            for m in msgs:
                # Skip bot messages and system messages
                if m.get("subtype") in ["bot_message", "channel_join", "channel_leave"]:
                    continue

                ts = m.get("thread_ts") or m.get("ts")
                threads.setdefault(ts, []).append(m)

            logger.info(
                "Grouped messages into threads",
                channel=channel_label,
                thread_count=len(threads),
            )

            for thread_ts, thread_msgs in threads.items():
                try:
                    # Fetch full thread if replies exist
                    if (
                        len(thread_msgs) == 1
                        and thread_msgs[0].get("reply_count", 0) > 0
                    ):
                        thread_msgs = sc.fetch_thread_replies(channel_id, thread_ts)

                    file_snippets: List[str] = []
                    file_ids: List[str] = []
                    if include_files:
                        seen_files: set[str] = set()
                        for message in thread_msgs:
                            for file_info in message.get("files", []) or []:
                                file_id = str(
                                    file_info.get("id")
                                    or file_info.get("name")
                                    or ""
                                )
                                if file_id and file_id in seen_files:
                                    continue
                                if file_id:
                                    seen_files.add(file_id)
                                    file_ids.append(file_id)

                                file_name = (
                                    file_info.get("name")
                                    or file_info.get("title")
                                    or file_id
                                    or "attachment"
                                )
                                file_text = None
                                if _should_fetch_file(file_info):
                                    file_text = await sc.fetch_file_content(file_info)

                                if file_text:
                                    snippet = file_text[:800].strip()
                                    if snippet:
                                        file_snippets.append(
                                            f"[file:{file_name}] {snippet}"
                                        )
                                    await store_memory(
                                        db,
                                        user_id=user_id,
                                        category="interaction",
                                        scope=channel_label,
                                        title=f"[Slack:{channel_label}] File {file_name}",
                                        content=file_text,
                                        tags={
                                            "source": "slack",
                                            "artifact_type": "file",
                                            "channel": channel_label,
                                            "channel_id": channel_id,
                                            "channel_type": channel_type,
                                            "thread_ts": thread_ts,
                                            "file_id": file_info.get("id"),
                                            "file_name": file_name,
                                            "mimetype": file_info.get("mimetype"),
                                            "url": file_info.get("url_private")
                                            or file_info.get("permalink"),
                                        },
                                        importance=3,
                                    )
                                else:
                                    file_snippets.append(
                                        f"[file:{file_name}] (binary or unavailable)"
                                    )

                    # Create summary
                    summary = await _summarize_thread(
                        thread_msgs, file_snippets=file_snippets
                    )

                    # Detect Jira keys
                    jira_keys = set()
                    raw_text = " ".join([m.get("text", "") for m in thread_msgs])
                    for key in JIRA_KEY_RE.findall(raw_text):
                        jira_keys.add(key)

                    # Memory scope: tie to Jira if found, otherwise channel
                    scope = list(jira_keys)[0] if jira_keys else channel_label

                    # Store in memory
                    await store_memory(
                        db,
                        user_id=user_id,
                        category="interaction",
                        scope=scope,
                        title=f"[Slack:{channel_label}] Discussion ({scope})",
                        content=summary,
                        tags={
                            "source": "slack",
                            "channel": channel_label,
                            "channel_id": channel_id,
                            "channel_type": channel_type,
                            "jira_keys": list(jira_keys),
                            "thread_ts": thread_ts,
                            "file_ids": file_ids,
                        },
                        importance=4,
                    )

                    logger.debug(
                        "Stored Slack thread in memory",
                        channel=channel_label,
                        scope=scope,
                        jira_keys=list(jira_keys),
                    )

                except Exception as e:
                    logger.error(
                        "Failed to process Slack thread",
                        channel=channel_label,
                        thread_ts=thread_ts,
                        error=str(e),
                    )
                    continue

        except Exception as e:
            logger.error(
                "Failed to process Slack channel",
                channel=channel_label,
                error=str(e),
            )
            continue

    logger.info(
        "Slack ingestion complete",
        user_id=user_id,
        processed_count=len(processed_channels),
    )

    return processed_channels
