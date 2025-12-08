from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.llm.factory import get_llm_client
from backend.llm.base import ChatMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/navi", tags=["navi-chat"])


# ---------------------------------------------------------------------------
# Models (aligned with frontend Navi types)
# ---------------------------------------------------------------------------


class NaviFilePatch(BaseModel):
    path: str
    kind: str
    newText: Optional[str] = None
    description: Optional[str] = None


class NaviAction(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    patches: List[NaviFilePatch] = []
    approvalRequired: bool = True


class NaviChatRequest(BaseModel):
    message: str
    workspace_root: Optional[str] = None


class NaviChatResponse(BaseModel):
    content: str
    actions: List[NaviAction] = []


# ---------------------------------------------------------------------------
# Intent → chat mode refinement
# ---------------------------------------------------------------------------


class ChatMode(str, Enum):
    REPO_INFO = "repo_info"
    EXPLAIN_REPO = "explain_repo"
    DIAGNOSE_REPO = "diagnose_repo"
    GENERAL = "general"


def _looks_like_diagnostics(text: str, primary_intent: str) -> bool:
    """
    Decide whether the user is asking us to *inspect* the repo for errors.

    We are intentionally generous here, so that natural phrases like:
      - "can you check for errors in this project?"
      - "are there any errors in this repo?"
    all route into the diagnostics workflow.
    """
    t = text.lower()

    diagnostics_phrases = [
        "check for errors",
        "check errors",
        "check any errors",
        "scan for errors",
        "scan this repo for errors",
        "scan this project for errors",
        "find errors",
        "look for errors",
        "check this project for issues",
        "check this repo for issues",
        "any errors in this project",
        "any errors in this repo",
    ]
    if any(p in t for p in diagnostics_phrases):
        return True

    # Generic "errors/issues" when talking about repo/code/project
    if ("error" in t or "errors" in t or "issues" in t) and any(
        kw in t
        for kw in ("project", "repo", "repository", "codebase", "code", "workspace")
    ):
        return True

    # Code/workspace intent + mentions of tests/lint/build failing
    if primary_intent in {"code", "workspace"} and any(
        kw in t
        for kw in [
            "tests failing",
            "test failures",
            "lint errors",
            "build fails",
            "build failing",
            "ci is red",
        ]
    ):
        return True

    return False


def _refine_chat_mode(message: str, primary_intent: str) -> ChatMode:
    text = message.lower().strip()

    logger.info("[NAVI-CHAT] refine: text=%s intent=%s", text, primary_intent)

    # Explicit diagnostics triggers
    if _looks_like_diagnostics(text, primary_intent):
        logger.info("[NAVI-CHAT] refine matched diagnostics")
        return ChatMode.DIAGNOSE_REPO

    # Repo info / explanation live under workspace questions
    if primary_intent == "workspace":
        if "which repo" in text or "which project" in text or "where are we" in text:
            logger.info("[NAVI-CHAT] refine matched repo_info (workspace intent)")
            return ChatMode.REPO_INFO
        if "explain" in text and (
            "project" in text or "repo" in text or "workspace" in text
        ):
            logger.info("[NAVI-CHAT] refine matched explain_repo (workspace intent)")
            return ChatMode.EXPLAIN_REPO

    # Fallbacks: some users will say "what project am i in" without intent=workspace
    if "which repo" in text or "which project" in text:
        logger.info("[NAVI-CHAT] refine matched repo_info (fallback)")
        return ChatMode.REPO_INFO
    if "explain" in text and (
        "project" in text or "repo" in text or "workspace" in text
    ):
        logger.info("[NAVI-CHAT] refine matched explain_repo (fallback)")
        return ChatMode.EXPLAIN_REPO

    return ChatMode.GENERAL


# ---------------------------------------------------------------------------
# Repo overview helpers (LAZY imports so they can't break startup)
# ---------------------------------------------------------------------------


async def _handle_repo_info(workspace_root: Optional[str]) -> str:
    from backend.navi.tools.repo_overview import describe_workspace

    return await describe_workspace(workspace_root)


async def _handle_explain_repo(workspace_root: Optional[str]) -> str:
    from backend.navi.tools.repo_overview import explain_repo

    return await explain_repo(workspace_root)


# ---------------------------------------------------------------------------
# Diagnostics helpers (also LAZY imports)
# ---------------------------------------------------------------------------


def _file_edit_to_patch(edit) -> NaviFilePatch:
    """
    Map whatever FileEdit-like object we get into a NaviFilePatch.
    We don't import FileEdit/PatchKind at module import time to avoid startup issues.
    """
    path = getattr(edit, "relative_path", "")
    kind_obj = getattr(edit, "kind", "")
    kind = getattr(kind_obj, "value", str(kind_obj) if kind_obj else "")

    return NaviFilePatch(
        path=path,
        kind=kind,
        newText=getattr(edit, "new_text", None),
        description=getattr(edit, "description", None),
    )


def _make_diagnostics_action(edits: List[object]) -> List[NaviAction]:
    if not edits:
        return []

    patches = [_file_edit_to_patch(e) for e in edits]

    return [
        NaviAction(
            id="diagnostics-auto-fix",
            title="Apply diagnostics-driven fixes",
            description=(
                "Apply Navi's proposed simple fixes (for example adding basic "
                "test / lint scripts to package.json)."
            ),
            patches=patches,
            approvalRequired=True,
        )
    ]


async def _run_diagnostics(workspace_root: str) -> NaviChatResponse:
    """
    Run repo diagnostics and produce a response + optional actions.

    All heavy imports are done here so startup can't be broken by missing modules.
    """
    try:
        from backend.navi.workflows.repo_diagnostics import RepoDiagnosticsWorkflow
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to import RepoDiagnosticsWorkflow", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Diagnostics module not available: {exc}",
        )

    repo_root = Path(workspace_root).expanduser().resolve()
    workflow = RepoDiagnosticsWorkflow()

    diagnostics = await workflow.diagnose_and_summarize(repo_root)
    edits = await workflow.plan_simple_fixes(repo_root, diagnostics)

    summary = diagnostics.get("summary") or {}
    high_level = summary.get("high_level_findings") or []
    blocking = summary.get("blocking_issues") or []
    non_blocking = summary.get("non_blocking_issues") or []
    fix_steps = summary.get("fix_plan_steps") or []

    parts: List[str] = []
    parts.append("Navi diagnostics summary\n")
    parts.append(f"Workspace:\n`{repo_root}`\n")

    if high_level:
        parts.append("\nHigh-level findings:\n")
        for item in high_level:
            parts.append(f"- {item}")

    if blocking:
        parts.append("\nBlocking issues:\n")
        for item in blocking:
            parts.append(f"- {item}")

    if non_blocking:
        parts.append("\nNon-blocking issues:\n")
        for item in non_blocking:
            parts.append(f"- {item}")

    if fix_steps:
        parts.append("\nSuggested fix plan:\n")
        for step in fix_steps:
            title = step.get("title", "Fix step")
            parts.append(f"- {title}")
            for act in step.get("actions") or []:
                parts.append(f"  • {act}")

    if not edits:
        parts.append(
            "\nI didn't find any safe, automatic fixes to apply yet. "
            "You may need to configure tests / linting manually, "
            "but we can iterate together on specific files."
        )

    content = "\n".join(parts)
    actions = _make_diagnostics_action(edits)

    return NaviChatResponse(content=content, actions=actions)


# ---------------------------------------------------------------------------
# Main chat handler
# ---------------------------------------------------------------------------


@router.post("/chat", response_model=NaviChatResponse)
async def navi_chat(req: NaviChatRequest) -> NaviChatResponse:
    """
    Main chat endpoint used by the VS Code webview.

    - Classifies intent using backend/api/navi_intent.py
    - Refines into a ChatMode
    - Delegates to repo overview, diagnostics, or general LLM chat
    """
    # Lazy import to avoid blocking startup
    from backend.api.navi_intent import IntentRequest, classify_intent

    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    intent_resp = await classify_intent(IntentRequest(message=req.message))
    primary_intent = intent_resp.intent
    logger.info("[NAVI-CHAT] Primary intent=%s", primary_intent)

    mode = _refine_chat_mode(req.message, primary_intent)
    logger.info("[NAVI-CHAT] Mode=%s", mode)

    # Repo info
    if mode == ChatMode.REPO_INFO:
        content = await _handle_repo_info(req.workspace_root)
        return NaviChatResponse(content=content, actions=[])

    # Explain repo (uses real source files)
    if mode == ChatMode.EXPLAIN_REPO:
        content = await _handle_explain_repo(req.workspace_root)
        return NaviChatResponse(content=content, actions=[])

    # Diagnostics
    if mode == ChatMode.DIAGNOSE_REPO:
        if not req.workspace_root:
            raise HTTPException(
                status_code=400,
                detail="workspace_root is required for diagnostics",
            )
        return await _run_diagnostics(req.workspace_root)

    # General Q&A (fallback)
    llm = get_llm_client()
    system_prompt = (
        "You are Navi, an expert engineering assistant inside VS Code.\n"
        "You are talking to a single developer inside their editor.\n\n"
        "If the user asks about the current workspace, it's okay to answer in general\n"
        "terms, but DO NOT claim to have run the code or scanned the repo unless a\n"
        "specific workspace-aware tool was used. Be honest about what you can and\n"
        "cannot see.\n"
    )

    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=req.message),
    ]

    result = await llm.chat(messages=messages, temperature=0.4, max_tokens=1200)
    return NaviChatResponse(content=result.content.strip(), actions=[])
