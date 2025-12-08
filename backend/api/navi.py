# backend/api/navi.py

"""
NAVI Chat API (agent OS v2)

Main chat endpoint used by the VS Code extension:

  POST /api/navi/chat

Payload (from extension):
{
  "message": "hi could you list the jira tasks assigned to me?",
  "model": "gpt-5.1",
  "mode": "agent-full",
  "attachments": [],
  "user_id": "default_user"
}

This file:

- Calls the NAVI agent loop (`run_agent_loop`) for every message.
- Maps `reply` -> `content` so the extension can render it.
- Returns `actions` and a lightweight `agentRun` for the Workspace plan card.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.core.db import get_db
from backend.agent.agent_loop import run_agent_loop
from backend.agent.planner_v3 import PlannerV3
from backend.agent.tool_executor import execute_tool_with_sources
from backend.agent.intent_schema import IntentFamily, IntentKind, IntentSource, IntentPriority, NaviIntent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/navi", tags=["navi-chat"])

# Feature-flag: still allow running without OpenAI, but in degraded mode
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_ENABLED = bool(OPENAI_API_KEY)
if not OPENAI_ENABLED:
    logger.warning("OPENAI_API_KEY is not set; NAVI agent will run in degraded mode.")

# Initialize PlannerV3 for fast-path routing
planner_v3 = PlannerV3()

# Jira keywords for fast-path routing
JIRA_KEYWORDS = ("jira", "ticket", "tickets", "issue", "issues", "story", "stories", "assigned")
ME_KEYWORDS = ("assigned to me", "my tickets", "my issues", "my tasks", "assigned for me", "my jira")
WORK_KEYWORDS = ("jira", "ticket", "issue", "pr", "pull request", "code", "build", "test", "plan", "doc", "repo")

def _looks_like_jira_my_issues(message: str) -> bool:
    """Check if message is asking for user's Jira issues."""
    msg = message.lower()
    has_jira = any(k in msg for k in JIRA_KEYWORDS)
    has_me = any(k in msg for k in ME_KEYWORDS) or "assigned to me" in msg or "my " in msg
    return has_jira and has_me


def _is_smalltalk(message: str) -> bool:
    """Lightweight detector for non-work chatter."""
    msg = (message or "").lower().strip()
    if not msg:
        return False
    smalltalk_phrases = (
        "how are you",
        "what's up",
        "what is up",
        "how are you doing",
        "hello",
        "hi",
        "hey",
        "latest news",
        "news",
        "what's going on",
        "what is going on",
    )
    if any(p in msg for p in smalltalk_phrases):
        return True
    # If very short and contains no work keywords, treat as small talk
    if len(msg) <= 40 and not any(k in msg for k in WORK_KEYWORDS):
        return True
    return False


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class FileAttachment(BaseModel):
    kind: Literal["selection", "currentFile", "pickedFile", "file"]
    path: str
    language: Optional[str] = None
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    model: str = Field(
        default="gpt-4o-mini",
        description="LLM model (e.g., gpt-4o-mini, gpt-4.1, gpt-5.1)",
    )
    mode: str = Field(
        default="chat-only",
        description="Mode used by the extension (chat-only | agent-full etc.)",
    )
    # VS Code extension attachments with workspace context
    attachments: Optional[List[FileAttachment]] = None
    workspace: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Perfect workspace context from VS Code extension",
    )
    workspace_root: Optional[str] = Field(
        default=None,
        description="VS Code workspace root path for workspace-aware operations",
    )
    user_id: str = Field(
        default="default_user",
        description="Logical user identifier (maps to NAVI memory user_id)",
    )


class ChatResponse(BaseModel):
    # Shape that the VS Code extension expects:
    #   - `content` (main text)
    #   - optional `actions` (workspace plan steps)
    #   - optional `agentRun` (for the plan card)
    #   - optional `sources` (for source pills)
    content: str
    actions: List[Dict[str, Any]] = []
    agentRun: Optional[Dict[str, Any]] = None
    sources: List[Dict[str, Any]] = []  # Add sources field

    # Extra debugging / future features from agent loop; extension ignores these
    reply: Optional[str] = None
    should_stream: Optional[bool] = None
    state: Optional[Dict[str, Any]] = None
    duration_ms: Optional[int] = None


@router.get("/test-agent")
async def test_agent_endpoint():
    """Simple test endpoint so we can sanity-check wiring."""
    return {
        "message": "Agent mode test",
        "agentRun": {
            "steps": [
                {
                    "id": "test-1",
                    "label": "Test step",
                    "detail": "This is a test",
                    "status": "pending",
                }
            ]
        },
    }


# ---------------------------------------------------------------------------
# Main chat endpoint
# ---------------------------------------------------------------------------


@router.post("/chat", response_model=ChatResponse)
async def navi_chat(
    request: ChatRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> ChatResponse:
    """
    Main NAVI chat endpoint used by the VS Code extension.

    - Guards on OPENAI_API_KEY (degraded mode if missing).
    - Calls `run_agent_loop` (7-stage agent OS pipeline).
    - Maps the result into the `{ content, actions, agentRun }` shape the
      VS Code panel expects.
    """
    if not OPENAI_ENABLED:
        # Still return a `content` field so the extension stays happy
        msg = (
            "Hi! NAVI chat is currently running in degraded mode because "
            "OPENAI_API_KEY is not configured on the backend."
        )
        return ChatResponse(
            content=msg,
            actions=[],
            agentRun=None,
            reply=msg,
            should_stream=False,
            state={"degraded": True},
            duration_ms=0,
        )

    smalltalk_phrases = (
        "how are you",
        "what's up",
        "what is up",
        "how are you doing",
        "hello",
        "hi",
        "hey",
        "latest news",
        "what's going on",
        "what is going on",
        "news",
    )

    try:
        user_id = (request.user_id or "default_user").strip() or "default_user"
        mode = (request.mode or "chat-only").strip() or "chat-only"
        workspace_root = request.workspace_root or (request.workspace or {}).get("workspace_root")
        org_id = http_request.headers.get("x-org-id") if http_request else None

        logger.info(
            "[NAVI-CHAT] user=%s model=%s mode=%s org=%s workspace=%s msg='%s...'",
            user_id,
            request.model,
            mode,
            org_id,
            workspace_root,
            request.message[:80],
        )

        # If this is clear small talk and not a work request, reply directly
        msg_lower = request.message.lower().strip()
        if any(p in msg_lower for p in smalltalk_phrases) and not _looks_like_jira_my_issues(msg_lower):
            if "how are" in msg_lower:
                reply = "I’m doing well and ready to help. What do you want to tackle—code, Jira, docs, or builds?"
            elif "news" in msg_lower or "what's up" in msg_lower or "what is up" in msg_lower:
                reply = "All clear on my side. Tell me what you want to work on—code, Jira, docs, or builds."
            else:
                reply = "Hi there—ready when you are. What should we work on—code, Jira, docs, or builds?"
            return ChatResponse(
                content=reply,
                actions=[],
                agentRun=None,
                reply=reply,
                should_stream=False,
                state={"smalltalk": True},
                duration_ms=0,
            )

        # Require workspace path to avoid describing the wrong repo
        if not workspace_root:
            msg = (
                "I don't have your workspace path from the extension. "
                "Open the folder you want me to use in VS Code and retry."
            )
            return ChatResponse(
                content=msg,
                actions=[],
                agentRun=None,
                reply=msg,
                should_stream=False,
                state={"missing_workspace": True},
                duration_ms=0,
            )

        # Guard: if user mentions Jira but there is no connection, respond directly
        if "jira" in msg_lower and not _looks_like_jira_my_issues(msg_lower):
            # Fallback: if no org_id header, use the most recent Jira connection's org_id
            if not org_id:
                org_id = db.execute(text("SELECT org_id FROM jira_connection ORDER BY id DESC LIMIT 1")).scalar()
            conn_count = db.execute(text("SELECT COUNT(*) FROM jira_connection")).scalar() or 0
            
            # Check if Jira connector is connected (don't wait for slow sync)
            if conn_count == 0:
                msg = "Jira is not connected. Connect Jira in the Connectors tab and retry."
                return ChatResponse(
                    content=msg,
                    actions=[],
                    agentRun=None,
                    sources=[],
                    reply=msg,
                    should_stream=False,
                    state={"jira_fast_path": True},
                    duration_ms=0,
                )

        # ✅ Jira fast-path: bypass workspace planner for direct tool execution
        jira_match = _looks_like_jira_my_issues(request.message)
        logger.info("[NAVI-CHAT] Checking Jira fast-path for: '%s' -> %s", request.message, jira_match)
        
        if jira_match:
            logger.info("[NAVI-CHAT] Using Jira fast-path for message: %s", request.message[:50])

            # Guard: Jira connection present for this org?
            if not org_id:
                org_id = db.execute(text("SELECT org_id FROM jira_connection ORDER BY id DESC LIMIT 1")).scalar()
            conn_count = db.execute(text("SELECT COUNT(*) FROM jira_connection")).scalar() or 0
            
            # Just check if Jira is connected (don't wait for slow sync)
            if conn_count == 0:
                msg = "Jira is not connected. Connect Jira in the Connectors tab and retry."
                return ChatResponse(
                    content=msg,
                    actions=[],
                    agentRun=None,
                    sources=[],
                    reply=msg,
                    should_stream=False,
                    state={"jira_fast_path": True},
                    duration_ms=0,
                )
            
            # Track timing
            started = time.monotonic()
            
            # Create Jira intent
            NaviIntent(
                family=IntentFamily.PROJECT_MANAGEMENT,
                kind=IntentKind.SUMMARIZE_TICKETS,  # Use existing enum value
                raw_text=request.message,
                source=IntentSource.CHAT,
                priority=IntentPriority.NORMAL,
                confidence=0.9
            )
            
            context = {
                "message": request.message,
                "user_id": user_id,
                "workspace": request.workspace or {"workspace_root": workspace_root},
            }
            
            # Direct tool execution with sources
            try:
                tool_result = await execute_tool_with_sources(
                    user_id=user_id,
                    tool_name="jira.list_assigned_issues_for_user",
                    args={"limit": 20, "context": context},
                    db=db
                )
                
                # Format response for VS Code
                issues_text = "Here are your Jira issues:\n"
                if tool_result.output:
                    for issue in tool_result.output[:10]:  # Limit to 10 for display
                        key = issue.get('issue_key', 'Unknown')
                        summary = issue.get('summary', 'No summary')
                        status = issue.get('status', 'Unknown')
                        issues_text += f"• **{key}** - {summary} ({status})\n"
                else:
                    issues_text = "No Jira issues found for you."
                
                # Return direct response with sources
                return ChatResponse(
                    content=issues_text,
                    actions=[],
                    agentRun=None,
                    sources=tool_result.sources,  # Pass through sources for pills
                    reply=issues_text,
                    should_stream=False,
                    state={"jira_fast_path": True},
                    duration_ms=int((time.monotonic() - started) * 1000),
                )
                
            except Exception as e:
                logger.error("[NAVI-CHAT] Jira fast-path failed: %s", e)
                # Fall through to regular agent loop
        
        # Call the NAVI agent loop with perfect workspace context
        workspace_data = request.workspace or {}
        if workspace_root:
            workspace_data["workspace_root"] = workspace_root
        
        agent_result = await run_agent_loop(
            user_id=user_id,
            message=request.message,
            model=request.model,
            mode=mode,
            db=db,
            attachments=[a.dict() for a in (request.attachments or [])],
            workspace=workspace_data,
        )

        # Core reply text
        reply = str(agent_result.get("reply") or "").strip()
        if not reply:
            reply = (
                "I generated an empty response. Could you try asking that again "
                "in a slightly different way?"
            )

        # Planned actions (already shaped in agent_loop)
        actions: List[Dict[str, Any]] = agent_result.get("actions") or []

        # Build a minimal agentRun payload for the Workspace plan card
        agent_run: Optional[Dict[str, Any]] = None
        if actions:
            steps = []
            for idx, step in enumerate(actions):
                if not isinstance(step, dict):
                    try:
                        step = dict(step)
                    except Exception:  # noqa: BLE001
                        step = {"description": str(step)}

                label = (
                    step.get("title")
                    or step.get("description")
                    or step.get("tool")
                    or f"Step {idx + 1}"
                )

                detail_parts = []
                tool_name = step.get("tool")
                if tool_name:
                    detail_parts.append(f"Tool: {tool_name}")

                args = step.get("arguments") or step.get("args")
                if args:
                    detail_parts.append(f"Args: {str(args)[:160]}")

                detail = " | ".join(detail_parts) if detail_parts else ""

                steps.append(
                    {
                        "id": step.get("id") or f"step-{idx + 1}",
                        "label": label,
                        "status": "planned",
                        "detail": detail,
                    }
                )

            agent_run = {
                "duration_ms": agent_result.get("duration_ms"),
                "steps": steps,
            }

        # Extract sources from agent result
        sources = agent_result.get("sources") or []
        
        # Map `reply` -> `content` for the extension
        return ChatResponse(
            content=reply,
            actions=actions,
            agentRun=agent_run,
            sources=sources,  # Pass through sources
            reply=reply,
            should_stream=bool(agent_result.get("should_stream", False)),
            state=agent_result.get("state") or {},
            duration_ms=agent_result.get("duration_ms"),
        )

    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error("[NAVI-CHAT] Error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process NAVI chat: {str(e)}",
        )
