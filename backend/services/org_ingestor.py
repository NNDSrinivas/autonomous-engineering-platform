"""Organization Ingestor Service

This service ingests data from external systems (Jira, Confluence, etc.)
into NAVI's conversational memory system.

Uses LLM to compress and summarize content for efficient memory storage.
"""

from typing import List, Dict, Any, Optional

from openai import AsyncOpenAI
from sqlalchemy.orm import Session
import structlog

from backend.integrations.jira_client import JiraClient
from backend.integrations.confluence_client import ConfluenceClient
from backend.services.navi_memory_service import store_memory

logger = structlog.get_logger(__name__)

# Initialize OpenAI for summarization
openai_client = AsyncOpenAI()


async def summarize_for_memory(title: str, raw_text: str, max_tokens: int = 512) -> str:
    """
    Use LLM to condense Jira/Confluence content into a compact memory-friendly summary.
    
    Args:
        title: Title of the content
        raw_text: Raw text content
        max_tokens: Maximum tokens for summary
        
    Returns:
        Condensed summary suitable for memory storage
    """
    prompt = f"""You are NAVI's memory compression assistant.

Summarize the following content into a concise, developer-friendly note that
captures the key requirements, decisions, and implementation hints.

Title: {title}

Content:
{raw_text[:6000]}

Return just the summary, no bullet labels unless needed.
"""
    
    try:
        completion = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        
        summary = completion.choices[0].message.content.strip()
        logger.info("Generated memory summary", title=title, summary_length=len(summary))
        
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
    
    try:
        async with JiraClient() as jira:
            issues = await jira.get_assigned_issues(jql=custom_jql, max_results=max_issues)
        
        processed_keys: List[str] = []
        
        for issue in issues:
            try:
                key = issue.get("key")
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
                
                # Build raw text for summarization
                raw_text = f"""
Jira issue: {key}
Summary: {summary}
Status: {status}
Priority: {priority}
Assignee: {assignee}

Description:
{description_text}
""".strip()
                
                memory_title = f"[Jira] {key}: {summary}"
                summary_text = await summarize_for_memory(memory_title, raw_text)
                
                # Store as NAVI memory (category = task)
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
                    },
                    importance=5,  # Jira tasks are high importance
                )
                
                processed_keys.append(key)
                logger.info("Ingested Jira issue", key=key, user_id=user_id)
                
            except Exception as e:
                logger.error("Failed to ingest Jira issue", error=str(e), issue_key=issue.get("key"))
                continue
        
        logger.info(
            "Jira ingestion complete",
            user_id=user_id,
            processed=len(processed_keys),
            total=len(issues)
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
        limit=limit
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
                body_storage = (
                    page.get("body", {})
                    .get("storage", {})
                    .get("value", "")
                )
                
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
                logger.error("Failed to ingest Confluence page", error=str(e), page_id=page.get("id"))
                continue
        
        logger.info(
            "Confluence ingestion complete",
            user_id=user_id,
            space_key=space_key,
            processed=len(processed_ids),
            total=len(pages)
        )
        
        return processed_ids
        
    except Exception as e:
        logger.error("Confluence ingestion failed", error=str(e), user_id=user_id, space_key=space_key)
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
