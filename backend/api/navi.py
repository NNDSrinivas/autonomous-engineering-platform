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
from typing import Any, Dict, List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.agent.agent_loop import run_agent_loop

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/navi", tags=["navi-chat"])

# Feature-flag: still allow running without OpenAI, but in degraded mode
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_ENABLED = bool(OPENAI_API_KEY)
if not OPENAI_ENABLED:
    logger.warning("OPENAI_API_KEY is not set; NAVI agent will run in degraded mode.")


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
    workspace_id: Optional[str] = Field(
        default=None,
        description="Workspace root path from VS Code for project identification",
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
    content: str
    actions: List[Dict[str, Any]] = []
    agentRun: Optional[Dict[str, Any]] = None

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

    try:
        user_id = (request.user_id or "default_user").strip() or "default_user"
        mode = (request.mode or "chat-only").strip() or "chat-only"

        logger.info(
            "[NAVI-CHAT] user=%s model=%s mode=%s msg='%s...'",
            user_id,
            request.model,
            mode,
            request.message[:80],
        )

        # Call the NAVI agent loop with VS Code attachments and workspace ID
        agent_result = await run_agent_loop(
            user_id=user_id,
            message=request.message,
            model=request.model,
            mode=mode,
            db=db,
            attachments=[a.dict() for a in (request.attachments or [])],
            workspace_id=request.workspace_id,
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

        # Map `reply` -> `content` for the extension
        return ChatResponse(
            content=reply,
            actions=actions,
            agentRun=agent_run,
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