"""
Org Retriever - Fetch Organizational Artifacts

Retrieves relevant context from:
- Jira (issues, comments, activity)
- Slack (messages, threads, channels)
- Confluence (pages, spaces)
- GitHub (PRs, commits, code)
- Zoom (meeting notes, transcripts)

Uses semantic search and direct lookups to build org context.
"""

import logging
from typing import Dict, Any, List
import re

logger = logging.getLogger(__name__)


async def retrieve_org_context(
    user_id: str,
    query: str,
    db=None
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
            "zoom_meetings": []
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
        if _is_jira_list_intent(query):
            logger.info(f"[ORG] Detected Jira list intent")
            result["jira_issues"] = await _fetch_user_jira_tasks(user_id, db)
        
        # ---------------------------------------------------------
        # 3. Semantic search across org memory for related artifacts
        # ---------------------------------------------------------
        # This would search navi_memory for task/interaction records
        # related to the query
        
        logger.info(f"[ORG] Retrieved {len(result['jira_issues'])} Jira issues")
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
    """Fetch specific Jira issues by their keys."""
    try:
        from backend.services.navi_memory_service import get_memory_by_scope
        
        issues = []
        for key in keys:
            mem = get_memory_by_scope(
                db=db,
                user_id=user_id,
                scope=key,
                categories=["task"]
            )
            if mem:
                issues.append({
                    "key": key,
                    "summary": mem.get("title"),
                    "content": mem.get("content"),
                    "meta": mem.get("meta_json", {})
                })
        
        return issues
    
    except Exception as e:
        logger.error(f"[ORG] Error fetching Jira issues by keys: {e}")
        return []


async def _fetch_user_jira_tasks(user_id: str, db) -> List[Dict[str, Any]]:
    """Fetch all Jira tasks assigned to user."""
    try:
        from backend.services.navi_memory_service import search_memory
        
        # Search for task memories
        tasks = search_memory(
            db=db,
            user_id=user_id,
            query="",  # Empty query returns all
            categories=["task"],
            limit=20,
            min_importance=0
        )
        
        return [
            {
                "key": task.get("scope"),
                "summary": task.get("title"),
                "content": task.get("content"),
                "meta": task.get("meta_json", {})
            }
            for task in tasks
        ]
    
    except Exception as e:
        logger.error(f"[ORG] Error fetching user Jira tasks: {e}")
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
