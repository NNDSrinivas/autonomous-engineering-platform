"""Organization Ingestor Service

This service ingests data from external systems (Jira, Confluence, etc.)
into NAVI's conversational memory system.

Uses LLM to compress and summarize content for efficient memory storage.
"""

import os
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
import structlog

from backend.integrations.jira_client import JiraClient
from backend.integrations.confluence_client import ConfluenceClient
from backend.services.navi_memory_service import store_memory
from backend.services.jira import JiraService
from backend.core.crypto import decrypt_token

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


async def _get_jira_client_for_user(db: Session, user_id: str) -> Optional[JiraClient]:
    """Get JiraClient for user - prefer saved connection over env vars."""
    # First try to get saved connection
    connection = JiraService.get_connection_for_user(db, user_id)
    if connection:
        try:
            # Decrypt the token (access_token is encrypted)
            decrypted_token = decrypt_token(connection.access_token)

            # Create client with saved credentials
            # Note: The model doesn't have email field, use env var as fallback
            email = os.getenv("AEP_JIRA_EMAIL", "")
            return JiraClient(
                base_url=connection.cloud_base_url,
                email=email,
                api_token=decrypted_token,
            )
        except Exception as e:
            logger.warning("Failed to decrypt saved connection", error=str(e))

    # Fallback to environment variables
    if all(
        os.getenv(var)
        for var in ["AEP_JIRA_BASE_URL", "AEP_JIRA_EMAIL", "AEP_JIRA_API_TOKEN"]
    ):
        return JiraClient()

    return None


async def summarize_for_memory(title: str, raw_text: str, max_tokens: int = 200) -> str:
    """
    Use LLM to condense Jira/Confluence content into a compact memory-friendly summary.

    OPTIMIZATION: Reduced max_tokens from 512 to 200 for faster responses.

    Args:
        title: Title of the content
        raw_text: Raw text content
        max_tokens: Maximum tokens for summary (default: 200 for speed)

    Returns:
        Condensed summary suitable for memory storage
    """
    # OPTIMIZATION: Shorter, more direct prompt
    prompt = f"""Summarize this Jira task in 2-3 sentences:

{title}

{raw_text[:1000]}

Focus on: what needs to be done and current status."""

    try:
        client = _get_openai_client()
        completion = await client.chat.completions.create(
            model="gpt-4o-mini",  # Fast model
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,  # Reduced for speed
            temperature=0.1,  # Lower temperature = faster
            timeout=10.0,  # 10 second timeout
        )

        summary = completion.choices[0].message.content.strip()
        logger.info(
            "Generated memory summary", title=title, summary_length=len(summary)
        )

        return summary

    except Exception as e:
        logger.error("Failed to generate summary", error=str(e), title=title)
        # Fallback: truncate raw text
        return raw_text[:500] + "..." if len(raw_text) > 500 else raw_text


async def ingest_jira_for_user(
    db: Session,
    user_id: str,
    max_issues: int = 20,
    custom_jql: Optional[str] = None,
) -> List[str]:
    """
    Fetch Jira issues assigned to the current user and store them
    into NAVI memory (category=task).

    Args:
        db: Database session
        user_id: User identifier
        max_issues: Maximum number of issues to fetch
        custom_jql: Optional custom JQL query

    Returns:
        List of issue keys that were processed
    """
    logger.info("Starting Jira ingestion", user_id=user_id, max_issues=max_issues)

    # Get Jira client for this user (prefer saved connection over env vars)
    jira_client = await _get_jira_client_for_user(db, user_id)
    if not jira_client:
        logger.warning("No Jira configuration available for user", user_id=user_id)
        return []

    try:
        async with jira_client as jira:
            issues = await jira.get_assigned_issues(
                jql=custom_jql, max_results=max_issues
            )

        processed_keys: List[str] = []

        for issue in issues:
            try:
                key = issue.get("key")
                # Defensive: handle both missing and explicitly None 'fields' from Jira API
                fields = issue.get("fields", {}) or {}
                summary = fields.get("summary", "").strip()
                description = fields.get("description", "")

                # Handle description - it can be dict (Atlassian Document Format) or string
                if isinstance(description, dict):
                    # Extract text from Atlassian Document Format
                    description_text = _extract_text_from_adf(description)
                else:
                    description_text = (description or "").strip()

                status_obj = fields.get("status", {}) or {}
                status = status_obj.get("name", "Unknown")

                priority_obj = fields.get("priority", {}) or {}
                priority = priority_obj.get("name", "Medium")

                assignee_obj = fields.get("assignee", {}) or {}
                assignee = assignee_obj.get("displayName", "Unassigned")

                # Extract timestamps and project info
                created = fields.get("created", "")
                updated = fields.get("updated", "")

                project_obj = fields.get("project", {}) or {}
                project_key = project_obj.get("key", "")
                project_name = project_obj.get("name", "")

                issue_type_obj = fields.get("issuetype", {}) or {}
                issue_type = issue_type_obj.get("name", "Task")

                reporter_obj = fields.get("reporter", {}) or {}
                reporter = reporter_obj.get("displayName", "Unknown")

                # Build raw text for summarization with richer context
                raw_text = f"""
Jira issue: {key}
Project: {project_name} ({project_key})
Type: {issue_type}
Summary: {summary}
Status: {status}
Priority: {priority}
Assignee: {assignee}
Reporter: {reporter}
Created: {created}
Updated: {updated}

Description:
{description_text}
""".strip()

                memory_title = f"[Jira] {key}: {summary}"
                summary_text = await summarize_for_memory(memory_title, raw_text)

                # Build Jira URL from base_url
                jira_url = f"{jira_client.base_url}/browse/{key}"

                # Store as NAVI memory (category = task) with rich metadata for smart responses
                await store_memory(
                    db,
                    user_id=user_id,
                    category="task",
                    scope=key,  # scope = issue key
                    title=memory_title,
                    content=summary_text,
                    tags={
                        "source": "jira",
                        "key": key,
                        "status": status,
                        "priority": priority,
                        "assignee": assignee,
                        "created": created,
                        "updated": updated,
                        "project_key": project_key,
                        "project_name": project_name,
                        "issue_type": issue_type,
                        "reporter": reporter,
                        "jira_url": jira_url,
                        "links": {
                            # Placeholder for related resource links
                            # These will be populated by other connectors
                            "confluence": [],
                            "slack": [],
                            "zoom": [],
                            "teams": [],
                            "gmeet": [],
                            "jenkins": [],
                            "devops": [],
                            "other": [],
                        },
                    },
                    importance=5,  # Jira tasks are high importance
                )

                processed_keys.append(key)
                logger.info("Ingested Jira issue", key=key, user_id=user_id)

            except Exception as e:
                logger.error(
                    "Failed to ingest Jira issue",
                    error=str(e),
                    issue_key=issue.get("key"),
                )
                continue

        logger.info(
            "Jira ingestion complete",
            user_id=user_id,
            processed=len(processed_keys),
            total=len(issues),
        )

        return processed_keys

    except Exception as e:
        logger.error("Jira ingestion failed", error=str(e), user_id=user_id)
        raise


async def ingest_confluence_space(
    db: Session,
    user_id: str,
    space_key: str,
    limit: int = 20,
) -> List[str]:
    """
    Fetch Confluence pages for a space and store them as workspace memories.

    Args:
        db: Database session
        user_id: User identifier
        space_key: Confluence space key (e.g., "ENG")
        limit: Maximum number of pages to fetch

    Returns:
        List of page IDs that were processed
    """
    logger.info(
        "Starting Confluence ingestion",
        user_id=user_id,
        space_key=space_key,
        limit=limit,
    )

    try:
        async with ConfluenceClient() as conf:
            pages = await conf.get_pages_in_space(space_key=space_key, limit=limit)

        processed_ids: List[str] = []

        for page in pages:
            try:
                page_id = page.get("id")
                title = (page.get("title") or "").strip()

                # Extract body content
                body_storage = page.get("body", {}).get("storage", {}).get("value", "")

                # Convert HTML to text
                text = ConfluenceClient.html_to_text(body_storage)

                raw_text = f"Confluence page: {title}\n\n{text}"
                summary_text = await summarize_for_memory(title, raw_text)

                # Store as NAVI memory (category = workspace)
                await store_memory(
                    db,
                    user_id=user_id,
                    category="workspace",
                    scope=space_key,  # group pages by space
                    title=f"[Confluence:{space_key}] {title}",
                    content=summary_text,
                    tags={
                        "source": "confluence",
                        "space": space_key,
                        "page_id": page_id,
                        "title": title,
                    },
                    importance=4,  # Documentation is moderately important
                )

                processed_ids.append(page_id)
                logger.info("Ingested Confluence page", page_id=page_id, title=title)

            except Exception as e:
                logger.error(
                    "Failed to ingest Confluence page",
                    error=str(e),
                    page_id=page.get("id"),
                )
                continue

        logger.info(
            "Confluence ingestion complete",
            user_id=user_id,
            space_key=space_key,
            processed=len(processed_ids),
            total=len(pages),
        )

        return processed_ids

    except Exception as e:
        logger.error(
            "Confluence ingestion failed",
            error=str(e),
            user_id=user_id,
            space_key=space_key,
        )
        raise


def _extract_text_from_adf(adf_doc: Dict[str, Any]) -> str:
    """
    Extract plain text from Atlassian Document Format (ADF).

    Args:
        adf_doc: ADF document dictionary

    Returns:
        Plain text content
    """

    def extract_content(node: Dict[str, Any]) -> List[str]:
        texts = []

        # Get text from current node
        if node.get("type") == "text":
            texts.append(node.get("text", ""))

        # Recurse into content array
        if "content" in node:
            for child in node["content"]:
                texts.extend(extract_content(child))

        return texts

    try:
        all_text = extract_content(adf_doc)
        return " ".join(all_text).strip()
    except Exception as e:
        logger.warning("Failed to extract ADF text", error=str(e))
        return ""
