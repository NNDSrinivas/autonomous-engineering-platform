"""Slack Ingestor Service

This service ingests Slack messages from engineering channels into NAVI's
conversational memory system. It groups messages by thread, summarizes them
with LLM, and automatically links them to Jira tickets when mentioned.
"""

import os
import re
from typing import List, Dict, Any

from dotenv import load_dotenv
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
import structlog

from backend.integrations.slack_client import SlackClient
from backend.services.navi_memory_service import store_memory

# Load environment variables
load_dotenv()

logger = structlog.get_logger(__name__)

# Initialize OpenAI for summarization
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Regex to detect Jira keys (e.g., LAB-158, ENG-102)
JIRA_KEY_RE = re.compile(r"\b[A-Z]{2,10}-\d+\b")


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
    text = re.sub(r"<@([A-Z0-9]+)>", "", text)     # remove mentions
    text = re.sub(r"<[^>]+>", "", text)            # remove links
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    return text.strip()


async def _summarize_thread(messages: List[Dict[str, Any]]) -> str:
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
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3
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
    limit: int = 200
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
    logger.info("Starting Slack ingestion",
                user_id=user_id,
                channels=channels,
                limit=limit)
    
    sc = SlackClient()

    # Map channel names to IDs
    all_channels = sc.list_channels()
    name_to_id = {c["name"]: c["id"] for c in all_channels if "name" in c}

    processed_channels = []

    for chan in channels:
        chan = chan.strip().lower()

        if chan not in name_to_id:
            logger.warning("Slack channel not found", channel=chan)
            continue

        channel_id = name_to_id[chan]
        processed_channels.append(channel_id)

        logger.info("Fetching Slack messages", channel=chan, channel_id=channel_id)

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

            logger.info("Grouped messages into threads",
                       channel=chan,
                       thread_count=len(threads))

            for thread_ts, thread_msgs in threads.items():
                try:
                    # Fetch full thread if replies exist
                    if len(thread_msgs) == 1 and thread_msgs[0].get("reply_count", 0) > 0:
                        thread_msgs = sc.fetch_thread_replies(channel_id, thread_ts)

                    # Create summary
                    summary = await _summarize_thread(thread_msgs)

                    # Detect Jira keys
                    jira_keys = set()
                    raw_text = " ".join([m.get("text", "") for m in thread_msgs])
                    for key in JIRA_KEY_RE.findall(raw_text):
                        jira_keys.add(key)

                    # Memory scope: tie to Jira if found, otherwise channel
                    scope = list(jira_keys)[0] if jira_keys else chan

                    # Store in memory
                    await store_memory(
                        db,
                        user_id=user_id,
                        category="interaction",
                        scope=scope,
                        title=f"[Slack:{chan}] Discussion ({scope})",
                        content=summary,
                        tags={
                            "source": "slack",
                            "channel": chan,
                            "jira_keys": list(jira_keys),
                            "thread_ts": thread_ts,
                        },
                        importance=4
                    )

                    logger.debug("Stored Slack thread in memory",
                                channel=chan,
                                scope=scope,
                                jira_keys=list(jira_keys))
                    
                except Exception as e:
                    logger.error("Failed to process Slack thread",
                                channel=chan,
                                thread_ts=thread_ts,
                                error=str(e))
                    continue

        except Exception as e:
            logger.error("Failed to process Slack channel",
                        channel=chan,
                        error=str(e))
            continue

    logger.info("Slack ingestion complete",
                user_id=user_id,
                processed_count=len(processed_channels))
    
    return processed_channels
