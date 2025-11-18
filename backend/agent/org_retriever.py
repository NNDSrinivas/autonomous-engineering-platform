"""
Org Retriever - Fetch Organizational Artifacts (STEP C Enhanced)

Retrieves relevant context from:
- Jira (issues, comments, activity)
- Slack (messages, threads, channels)
- Confluence (pages, spaces)
- GitHub (PRs, commits, code)
- Zoom (meeting notes, transcripts)
- Teams (chats, channels)

Uses semantic search, direct lookups, and intelligent filtering.
This provides NAVI with full enterprise context awareness.
"""

import logging
from typing import Dict, Any, List
import re

logger = logging.getLogger(__name__)


async def retrieve_org_context(
    user_id: str,
    query: str,
    db=None,
    include_slack: bool = True,
    include_confluence: bool = True,
    include_github: bool = True,
    include_zoom: bool = True
) -> Dict[str, Any]:
    """
    Retrieve relevant organizational artifacts.
    
    Args:
        user_id: User identifier
        query: Current user message
        db: Database session
    
    Returns:
        {
            "jira_issues": [...],
            "slack_threads": [...],
            "confluence_pages": [...],
            "github_prs": [...],
            "zoom_meetings": [...]
        }
    """
    
    if not db:
        logger.warning("[ORG] No DB session, returning empty org context")
        return _empty_org_result()
    
    try:
        logger.info(f"[ORG] Retrieving org context for user={user_id}, query='{query[:50]}...'")
        
        result = {
            "jira_issues": [],
            "slack_threads": [],
            "confluence_pages": [],
            "github_prs": [],
            "zoom_meetings": [],
            "teams_messages": []
        }
        
        # ---------------------------------------------------------
        # 1. Check if query mentions a specific Jira key
        # ---------------------------------------------------------
        jira_keys = _extract_jira_keys(query)
        if jira_keys:
            logger.info(f"[ORG] Found Jira keys in query: {jira_keys}")
            result["jira_issues"] = await _fetch_jira_issues_by_keys(
                jira_keys, user_id, db
            )
        
        # ---------------------------------------------------------
        # 2. Check for Jira-related intents (list tasks, etc.)
        # ---------------------------------------------------------
        if _is_jira_list_intent(query) or not jira_keys:
            logger.info(f"[ORG] Detected Jira list intent or no specific keys")
            user_tasks = await _fetch_user_jira_tasks(user_id, db)
            
            # Merge with any specific key results
            existing_keys = {issue.get("key") for issue in result["jira_issues"]}
            for task in user_tasks:
                if task.get("key") not in existing_keys:
                    result["jira_issues"].append(task)
        
        # ---------------------------------------------------------
        # 3. Search Slack for related discussions
        # ---------------------------------------------------------
        if include_slack and jira_keys:
            logger.info(f"[ORG] Searching Slack for Jira keys: {jira_keys}")
            result["slack_threads"] = await _search_slack_for_jira(
                jira_keys, user_id, db
            )
        
        # ---------------------------------------------------------
        # 4. Search Confluence for related documentation
        # ---------------------------------------------------------
        if include_confluence and jira_keys:
            logger.info(f"[ORG] Searching Confluence for Jira keys: {jira_keys}")
            result["confluence_pages"] = await _search_confluence_for_jira(
                jira_keys, user_id, db
            )
        
        # ---------------------------------------------------------
        # 5. Search GitHub for related PRs
        # ---------------------------------------------------------
        if include_github and jira_keys:
            logger.info(f"[ORG] Searching GitHub for Jira keys: {jira_keys}")
            result["github_prs"] = await _search_github_for_jira(
                jira_keys, user_id, db
            )
        
        # ---------------------------------------------------------
        # 6. Search Zoom meeting notes
        # ---------------------------------------------------------
        if include_zoom and jira_keys:
            logger.info(f"[ORG] Searching Zoom for Jira keys: {jira_keys}")
            result["zoom_meetings"] = await _search_zoom_for_jira(
                jira_keys, user_id, db
            )
        
        logger.info(f"[ORG] Retrieved {len(result['jira_issues'])} Jira issues, "
                   f"{len(result['slack_threads'])} Slack threads, "
                   f"{len(result['confluence_pages'])} Confluence pages")
        return result
    
    except Exception as e:
        logger.error(f"[ORG] Error retrieving org context: {e}", exc_info=True)
        return _empty_org_result()


def _extract_jira_keys(text: str) -> List[str]:
    """Extract Jira issue keys like SCRUM-1, ENG-102, etc."""
    pattern = r'\b([A-Z][A-Z0-9]+-\d+)\b'
    matches = re.findall(pattern, text)
    return list(set(matches))


def _is_jira_list_intent(query: str) -> bool:
    """Check if user wants to list Jira tasks."""
    query_lower = query.lower()
    triggers = [
        "my tasks",
        "my tickets",
        "my issues",
        "jira tasks",
        "assigned to me",
        "what should i work on",
        "what's on my plate"
    ]
    return any(trigger in query_lower for trigger in triggers)


async def _fetch_jira_issues_by_keys(
    keys: List[str],
    user_id: str,
    db
) -> List[Dict[str, Any]]:
    """Fetch specific Jira issues by their keys from navi_memory."""
    try:
        from backend.services.navi_memory_service import search_memory
        
        issues = []
        for key in keys:
            # Search for this specific key in task memories
            results = await search_memory(
                db=db,
                user_id=user_id,
                query=key,
                categories=["task"],
                limit=1,
                min_importance=0
            )
            
            if results:
                mem = results[0]
                issues.append({
                    "key": key,
                    "summary": mem.get("title", ""),
                    "content": mem.get("content", ""),
                    "meta": mem.get("meta_json", {})
                })
        
        return issues
    
    except Exception as e:
        logger.error(f"[ORG] Error fetching Jira issues by keys: {e}")
        return []


async def _fetch_user_jira_tasks(user_id: str, db) -> List[Dict[str, Any]]:
    """Fetch all Jira tasks assigned to user from navi_memory."""
    try:
        from backend.services.navi_memory_service import search_memory
        
        # Search for task memories
        tasks = await search_memory(
            db=db,
            user_id=user_id,
            query="",  # Empty query with category filter
            categories=["task"],
            limit=20,
            min_importance=0
        )
        
        return [
            {
                "key": task.get("scope", ""),
                "summary": task.get("title", ""),
                "content": task.get("content", ""),
                "meta": task.get("meta_json", {})
            }
            for task in tasks
        ]
    
    except Exception as e:
        logger.error(f"[ORG] Error fetching user Jira tasks: {e}")
        return []


async def _search_slack_for_jira(
    jira_keys: List[str],
    user_id: str,
    db
) -> List[Dict[str, Any]]:
    """Search Slack messages/threads mentioning these Jira keys."""
    try:
        from backend.services.navi_memory_service import search_memory
        
        threads = []
        for key in jira_keys:
            # Search interaction memories for Slack discussions
            results = await search_memory(
                db=db,
                user_id=user_id,
                query=key,
                categories=["interaction"],
                limit=3,
                min_importance=0
            )
            
            for mem in results:
                meta = mem.get("meta_json", {})
                if meta.get("source") == "slack":
                    threads.append({
                        "channel": meta.get("channel", ""),
                        "content": mem.get("content", ""),
                        "timestamp": meta.get("timestamp", ""),
                        "meta": meta
                    })
        
        return threads
    
    except Exception as e:
        logger.error(f"[ORG] Error searching Slack: {e}")
        return []


async def _search_confluence_for_jira(
    jira_keys: List[str],
    user_id: str,
    db
) -> List[Dict[str, Any]]:
    """Search Confluence pages mentioning these Jira keys."""
    try:
        from backend.services.navi_memory_service import search_memory
        
        pages = []
        for key in jira_keys:
            # Search workspace memories for Confluence docs
            results = await search_memory(
                db=db,
                user_id=user_id,
                query=key,
                categories=["workspace"],
                limit=2,
                min_importance=0
            )
            
            for mem in results:
                meta = mem.get("meta_json", {})
                if meta.get("source") == "confluence":
                    pages.append({
                        "title": mem.get("title", ""),
                        "content": mem.get("content", ""),
                        "url": meta.get("url", ""),
                        "meta": meta
                    })
        
        return pages
    
    except Exception as e:
        logger.error(f"[ORG] Error searching Confluence: {e}")
        return []


async def _search_github_for_jira(
    jira_keys: List[str],
    user_id: str,
    db
) -> List[Dict[str, Any]]:
    """Search GitHub PRs/commits mentioning these Jira keys."""
    try:
        from backend.services.navi_memory_service import search_memory
        
        prs = []
        for key in jira_keys:
            # Search interaction memories for GitHub activity
            results = await search_memory(
                db=db,
                user_id=user_id,
                query=key,
                categories=["interaction"],
                limit=2,
                min_importance=0
            )
            
            for mem in results:
                meta = mem.get("meta_json", {})
                if meta.get("source") == "github":
                    prs.append({
                        "title": mem.get("title", ""),
                        "content": mem.get("content", ""),
                        "pr_number": meta.get("pr_number", ""),
                        "url": meta.get("url", ""),
                        "meta": meta
                    })
        
        return prs
    
    except Exception as e:
        logger.error(f"[ORG] Error searching GitHub: {e}")
        return []


async def _search_zoom_for_jira(
    jira_keys: List[str],
    user_id: str,
    db
) -> List[Dict[str, Any]]:
    """Search Zoom meeting notes mentioning these Jira keys."""
    try:
        from backend.services.navi_memory_service import search_memory
        
        meetings = []
        for key in jira_keys:
            # Search interaction memories for Zoom meetings
            results = await search_memory(
                db=db,
                user_id=user_id,
                query=key,
                categories=["interaction"],
                limit=2,
                min_importance=0
            )
            
            for mem in results:
                meta = mem.get("meta_json", {})
                if meta.get("source") == "zoom":
                    meetings.append({
                        "title": mem.get("title", ""),
                        "content": mem.get("content", ""),
                        "date": meta.get("date", ""),
                        "meta": meta
                    })
        
        return meetings
    
    except Exception as e:
        logger.error(f"[ORG] Error searching Zoom: {e}")
        return []


def _empty_org_result() -> Dict[str, Any]:
    """Return empty org context structure."""
    return {
        "jira_issues": [],
        "slack_threads": [],
        "confluence_pages": [],
        "github_prs": [],
        "zoom_meetings": []
    }
