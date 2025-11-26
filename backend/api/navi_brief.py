"""
NAVI Task Brief API - Comprehensive Jira Task Context
Pulls cross-system context (Jira, Confluence, Slack, Teams, Zoom) to generate
structured briefs for engineering tasks.
"""

from typing import List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import logging
import os

from ..core.db import get_db
from ..services.navi_memory_service import search_memory, list_jira_tasks_for_user
# from .navi import _ensure_fresh_jira_tasks  # Removed - using new agent architecture

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/navi", tags=["navi-brief"])

# OpenAI client
try:
    from openai import AsyncOpenAI

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
    OPENAI_ENABLED = bool(openai_client)
except ImportError:
    openai_client = None
    OPENAI_ENABLED = False
    logger.warning("OpenAI not installed for task brief generation")


# ============================================================================
# REQUEST / RESPONSE MODELS
# ============================================================================


class TaskBriefRequest(BaseModel):
    """Request for comprehensive task brief"""

    user_id: str = Field(..., description="User identifier")
    jira_key: str = Field(..., description="Jira ticket key (e.g. LAB-158)")
    model: str = Field(
        default="gpt-4o-mini", description="Model to use for summarization"
    )


class TaskBriefSection(BaseModel):
    """Section of a task brief"""

    title: str
    content: str


class TaskBriefResponse(BaseModel):
    """Comprehensive task brief with cross-system context"""

    jira_key: str = Field(..., description="Jira ticket key")
    summary: str = Field(..., description="High-level summary")
    sections: List[TaskBriefSection] = Field(
        ..., description="Structured brief sections"
    )
    sources: List[str] = Field(
        ..., description="Data sources used (Jira, Confluence, Slack, Teams, Zoom)"
    )


class JiraTaskItem(BaseModel):
    """Individual Jira task item"""

    jira_key: str = Field(..., description="Jira ticket key")
    title: str = Field(..., description="Task title/summary")
    status: str = Field(..., description="Task status (e.g., To Do, In Progress)")
    scope: str = Field(..., description="Scope/project identifier")
    updated_at: str = Field(..., description="Last updated timestamp (ISO format)")
    url: Optional[str] = Field(
        None, description="Direct Jira URL for this ticket (if available)"
    )
    links: Dict[str, List[str]] = Field(
        default_factory=dict,
        description=(
            "Related resource links grouped by system, e.g. "
            "{'confluence': [...], 'slack': [...], 'zoom': [...], 'jenkins': [...]} "
        ),
    )


class JiraTaskListResponse(BaseModel):
    """List of Jira tasks from NAVI memory with snapshot tracking"""

    tasks: List[JiraTaskItem] = Field(..., description="List of Jira tasks")
    total: int = Field(..., description="Total number of tasks returned")
    snapshot_ts: Optional[str] = Field(
        None,
        description="ISO timestamp of latest Jira sync snapshot (if known)"
    )


# ============================================================================
# MAIN ENDPOINTS
# ============================================================================


@router.get("/jira-tasks", response_model=JiraTaskListResponse)
async def list_jira_tasks(
    user_id: str = "default_user",
    limit: int = 20,
    db: Session = Depends(get_db),
) -> JiraTaskListResponse:
    """
    List Jira tasks NAVI knows about for this user.

    Automatically ensures tasks are fresh (real-time sync if needed), then
    returns tasks with URLs and related links for clickable references.

    Args:
        user_id: User identifier (query parameter, defaults to "default_user")
        limit: Maximum number of tasks to return (default 20)
        db: Database session (injected)

    Returns:
        List of Jira tasks with keys, titles, statuses, URLs, and related links
    """
    try:
        uid = user_id.strip()
        if not uid:
            uid = "default_user"

        logger.info("[JIRA-TASKS] Listing tasks for user: %s, limit: %s", uid, limit)

        # Ensure Jira tasks are fresh (real-time sync if needed)
        # await _ensure_fresh_jira_tasks(db, uid)  # Removed - using new agent architecture

        rows = list_jira_tasks_for_user(db, uid, limit=limit)

        items: List[JiraTaskItem] = []
        for m in rows:
            tags = m.get("tags") or {}
            jira_key = tags.get("key") or (m.get("scope") or "").upper()
            status = tags.get("status") or "Unknown"
            title = m.get("title") or jira_key
            scope = m.get("scope") or ""

            updated_at_raw = m.get("updated_at") or ""
            if hasattr(updated_at_raw, "isoformat"):
                updated_at = updated_at_raw.isoformat()  # type: ignore
            else:
                updated_at = str(updated_at_raw)

            # Extract URL and links from tags
            url = tags.get("jira_url") or tags.get("url")
            links = tags.get("links") or {}

            if not jira_key:
                # Skip memories that don't have any meaningful Jira identifier
                continue

            items.append(
                JiraTaskItem(
                    jira_key=jira_key,
                    title=title,
                    status=status,
                    scope=scope,
                    updated_at=updated_at,
                    url=url,
                    links=links,
                )
            )

        logger.info("[JIRA-TASKS] Found %d tasks for %s", len(items), uid)

        # Track latest snapshot timestamp from all tasks
        snapshot_ts: Optional[str] = None
        for row in rows:
            tags = row.get("tags") or {}
            sync_ts = tags.get("synced_at")
            if sync_ts and (snapshot_ts is None or sync_ts > snapshot_ts):
                snapshot_ts = sync_ts

        return JiraTaskListResponse(tasks=items, total=len(items), snapshot_ts=snapshot_ts)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[JIRA-TASKS] Error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list Jira tasks: {str(e)}"
        )


@router.get("/jira-tasks/live", response_model=JiraTaskListResponse)
async def list_jira_tasks_live(
    user_id: str = "default_user",
    limit: int = 20,
    db: Session = Depends(get_db),
) -> JiraTaskListResponse:
    """
    Live Jira view: query Jira API directly, bypassing navi_memory cache.
    
    Use this when user specifically asks for "latest", "current", "right now" data.
    This always returns the most up-to-date information from Jira.
    """
    try:
        uid = user_id.strip() or "default_user"
        
        logger.info("[JIRA-LIVE] Fetching live tasks from Jira API for user: %s", uid)
        
        # Import here to avoid circular imports
        from ..integrations.jira_client import JiraClient
        from ..services.org_ingestor import _get_jira_client_for_user
        
        # Get Jira client for this user
        jira_client = await _get_jira_client_for_user(db, uid)
        if not jira_client:
            logger.warning("[JIRA-LIVE] No Jira connection found for user %s", uid)
            return JiraTaskListResponse(tasks=[], total=0, snapshot_ts=None)
        
        # Fetch live data from Jira API
        async with jira_client as jira:
            issues = await jira.get_assigned_issues(
                jql="assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC",
                max_results=limit
            )
        
        logger.info("[JIRA-LIVE] Fetched %d live issues from Jira", len(issues))
        
        # Convert to JiraTaskItem objects
        items: List[JiraTaskItem] = []
        for issue in issues:
            try:
                key = issue.get("key", "")
                fields = issue.get("fields", {}) or {}
                
                summary = fields.get("summary", "").strip()
                status_obj = fields.get("status", {}) or {}
                status = status_obj.get("name", "Unknown")
                
                priority_obj = fields.get("priority", {}) or {}
                priority = priority_obj.get("name", "Medium")
                
                assignee_obj = fields.get("assignee", {}) or {}
                assignee = assignee_obj.get("displayName", "Unassigned")
                
                # Build Jira URL
                jira_url = f"{jira_client.base_url}/browse/{key}"
                
                # Use updated timestamp from Jira
                updated = fields.get("updated", "")
                created = fields.get("created", "")
                
                items.append(
                    JiraTaskItem(
                        jira_key=key,
                        title=summary,
                        status=status,
                        scope=key,
                        updated_at=updated,
                        url=jira_url,
                        links={
                            "confluence": [],
                            "slack": [],
                            "zoom": [],
                            "teams": [],
                            "gmeet": [],
                            "jenkins": [],
                            "devops": [],
                            "other": []
                        }
                    )
                )
                
            except Exception as item_error:
                logger.warning("[JIRA-LIVE] Failed to process issue %s: %s", 
                             issue.get("key", "unknown"), item_error)
                continue
        
        logger.info("[JIRA-LIVE] Returning %d live tasks for %s", len(items), uid)
        # For live endpoint, snapshot_ts is current time since we just fetched
        from datetime import datetime, timezone
        current_ts = datetime.now(timezone.utc).isoformat()
        return JiraTaskListResponse(tasks=items, total=len(items), snapshot_ts=current_ts)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[JIRA-LIVE] Error fetching live tasks: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch live Jira tasks: {str(e)}"
        )


@router.post("/task-brief", response_model=TaskBriefResponse)
async def navi_task_brief(
    request: TaskBriefRequest, db: Session = Depends(get_db)
) -> TaskBriefResponse:
    """
    Generate a comprehensive task brief for a Jira ticket.

    Pulls context from:
    - Jira task details
    - Related Confluence documentation
    - Slack discussions mentioning the ticket
    - Teams conversations
    - Zoom meeting summaries

    Returns a structured brief with:
    - High-level summary
    - Requirements & scope
    - Architecture/design hints
    - Implementation plan
    - Risks & open questions
    - Useful references
    """
    try:
        user_id = request.user_id.strip()
        jira_key = request.jira_key.strip().upper()

        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")
        if not jira_key:
            raise HTTPException(status_code=400, detail="jira_key is required")

        logger.info(f"[TASK-BRIEF] Generating brief for {jira_key}, user: {user_id}")

        # Pull all memories scoped to this Jira key
        memories = await search_memory(
            db=db,
            user_id=user_id,
            query=jira_key,
            categories=["task", "workspace", "interaction", "profile"],
            limit=20,
            min_importance=0,  # Include all relevant memories
        )

        if not memories:
            raise HTTPException(
                status_code=404,
                detail=f"No NAVI memory found for Jira key {jira_key}. "
                "Try syncing Jira, Confluence, Slack, Teams, or Zoom data first.",
            )

        logger.info(f"[TASK-BRIEF] Found {len(memories)} memory items for {jira_key}")

        # Build context block for LLM
        context_lines: List[str] = []
        sources_set = set()

        for m in memories:
            source = (m.get("tags") or {}).get("source", m.get("category", "unknown"))
            sources_set.add(source)
            title = m.get("title") or "(no title)"
            scope = m.get("scope") or ""
            content = m.get("content") or ""

            context_lines.append(
                f"--- SOURCE: {source.upper()} ---\n"
                f"Title: {title}\n"
                f"Scope: {scope}\n"
                f"Content:\n{content}\n"
                f"---"
            )

        context_blob = "\n\n".join(context_lines)

        # Generate comprehensive brief with LLM
        if not OPENAI_ENABLED or not openai_client:
            raise HTTPException(
                status_code=503,
                detail="OpenAI not configured. Set OPENAI_API_KEY to generate task briefs.",
            )

        prompt = f"""
You are NAVI, the developer's personal engineering assistant.

The user wants a **comprehensive brief** on Jira ticket {jira_key}.

You have cross-system context from:
- Jira (task description, acceptance criteria)
- Confluence (design docs, architecture)
- Slack (team discussions)
- Teams (channel conversations)
- Zoom (meeting summaries)
- Profile/workspace notes

CONTEXT:
{context_blob}

Generate a concise, well-structured brief with the following sections:

## 1. High-Level Summary
1-3 sentences explaining what this task is about and why it matters.

## 2. Requirements & Scope
- What needs to be built or changed?
- What are the acceptance criteria?
- What's in scope vs out of scope?

## 3. Architecture & Design
- Key technical decisions
- Design patterns or approaches mentioned
- System components involved
- Any Confluence design docs referenced

## 4. Implementation Plan
Step-by-step approach:
1. First step...
2. Second step...
etc.

## 5. Discussions & Context
- Key points from Slack/Teams discussions
- Decisions made in Zoom meetings
- Open questions or concerns raised

## 6. Risks & Open Questions
- Technical risks
- Unknowns that need clarification
- Dependencies or blockers

## 7. References
- Link types mentioned (Confluence pages, Slack threads, Zoom meetings)
- Related Jira tickets

Return ONLY the markdown-formatted brief. No preamble, no code blocks around it.
"""

        completion = await openai_client.chat.completions.create(
            model=request.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.35,
        )

        brief_md = completion.choices[0].message.content or ""

        logger.info(f"[TASK-BRIEF] Generated {len(brief_md)} chars for {jira_key}")

        # Return structured response
        sections = [
            TaskBriefSection(
                title=f"Comprehensive Brief for {jira_key}",
                content=brief_md,
            )
        ]

        sources = sorted(sources_set)

        return TaskBriefResponse(
            jira_key=jira_key,
            summary=f"Comprehensive task brief generated for {jira_key} from {len(sources)} data sources",
            sections=sections,
            sources=sources,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[TASK-BRIEF] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to generate task brief: {str(e)}"
        )


# ============================================================================
# HEALTH CHECK
# ============================================================================


@router.get("/task-brief/status")
async def task_brief_status():
    """Check if task brief service is available"""
    return {
        "status": "ok" if OPENAI_ENABLED else "degraded",
        "openai_enabled": OPENAI_ENABLED,
        "message": (
            "Task brief service ready" if OPENAI_ENABLED else "OpenAI not configured"
        ),
    }
