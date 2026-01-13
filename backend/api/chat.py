"""
Enhanced Chat API for conversational interface
Provides context-aware responses with team intelligence + Navi diff review
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
from datetime import datetime, timezone, timedelta
from pathlib import Path
import asyncio
import logging
import httpx
from sqlalchemy.orm import Session
from urllib.parse import urlparse
import os
import re
import json

from backend.core.db import get_db
from backend.core.settings import settings
from backend.services.navi_memory_service import (
    search_memory,
    get_recent_memories,
    store_memory,
)
from backend.services.git_service import GitService
from backend.core.ai.llm_service import LLMService
from backend.autonomous.enhanced_coding_engine import (
    TaskType as AutonomousTaskType,
)

logger = logging.getLogger(__name__)

# Initialize LLM service for chat
_llm_service: Optional[LLMService] = None


def get_llm_service() -> Optional[LLMService]:
    """Get or initialize LLM service"""
    global _llm_service
    if _llm_service is None:
        try:
            _llm_service = LLMService()
            logger.info("LLM service initialized for chat")
        except Exception as e:
            logger.warning(f"LLM service unavailable: {e}")
            return None
    return _llm_service


# ------------------------------------------------------------------------------
# Routers
# ------------------------------------------------------------------------------
# Backward-compatible routes (existing)
router = APIRouter(prefix="/api/chat", tags=["chat"])

# New Navi routes
navi_router = APIRouter(prefix="/api/navi", tags=["navi"])

# ------------------------------------------------------------------------------
# Time constants
# ------------------------------------------------------------------------------
SECONDS_PER_MINUTE = int(timedelta(minutes=1).total_seconds())
SECONDS_PER_HOUR = int(timedelta(hours=1).total_seconds())
SECONDS_PER_DAY = int(timedelta(days=1).total_seconds())
SECONDS_PER_WEEK = int(timedelta(weeks=1).total_seconds())
SECONDS_PER_MONTH = int(timedelta(days=30.44).total_seconds())
SECONDS_PER_YEAR = int(timedelta(days=365).total_seconds())

# ------------------------------------------------------------------------------
# HTTP client management - thread-safe singleton pattern
# ------------------------------------------------------------------------------
_async_client: Optional[httpx.AsyncClient] = None
_client_lock: Optional[asyncio.Lock] = None


async def get_http_client() -> httpx.AsyncClient:
    """Get or create httpx.AsyncClient instance with thread-safe initialization"""
    global _async_client, _client_lock

    if _client_lock is None:
        _client_lock = asyncio.Lock()

    async with _client_lock:
        if _async_client is None:
            _async_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            )
        return _async_client


async def close_http_client():
    """Close shared httpx client (for use in app lifespan)"""
    global _async_client, _client_lock

    if _client_lock is None:
        _client_lock = asyncio.Lock()

    async with _client_lock:
        if _async_client is not None:
            await _async_client.aclose()
            _async_client = None


# ------------------------------------------------------------------------------
# Configuration helpers
# ------------------------------------------------------------------------------
def get_api_base_url() -> str:
    """Get the API base URL from settings or environment with validation"""
    url = getattr(settings, "API_BASE_URL", "http://localhost:8002")
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            logger.warning(f"Invalid API_BASE_URL: {url}, using default")
            return "http://localhost:8002"
        return url
    except Exception as e:
        logger.error(f"Error parsing API_BASE_URL {url}: {e}")
        return "http://localhost:8002"


def _get_openai_config() -> Tuple[Optional[str], str, str]:
    """
    Returns: (api_key, base_url, model)
    Defaults are chosen for compatibility.
    """
    api_key = getattr(settings, "OPENAI_API_KEY", None) or os.environ.get(
        "OPENAI_API_KEY"
    )
    base_url = (
        getattr(settings, "OPENAI_BASE_URL", None)
        or os.environ.get("OPENAI_BASE_URL")
        or "https://api.openai.com/v1"
    )
    model = (
        getattr(settings, "OPENAI_MODEL", None)
        or os.environ.get("OPENAI_MODEL")
        or "gpt-3.5-turbo"
    )
    return api_key, base_url.rstrip("/"), model


# ------------------------------------------------------------------------------
# Models
# ------------------------------------------------------------------------------
class ChatMessage(BaseModel):
    id: str
    type: str  # 'user', 'assistant', 'system', 'suggestion'
    content: str
    timestamp: datetime
    context: Optional[Dict[str, Any]] = None


class Attachment(BaseModel):
    """
    Generic attachment model. For Phase 1, we care about git diffs:

    {
      "kind": "diff",
      "language": "diff",
      "name": "working-tree.diff",
      "path": null,
      "content": "diff --git a/... b/...\n..."
    }
    """

    kind: str
    content: str
    language: Optional[str] = None
    name: Optional[str] = None
    path: Optional[str] = None
    id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    message: str
    conversationHistory: List[ChatMessage] = []
    currentTask: Optional[str] = None
    teamContext: Optional[Dict[str, Any]] = None


class NaviChatRequest(ChatRequest):
    attachments: List[Attachment] = Field(default_factory=list)
    executionMode: Optional[str] = None  # e.g., plan_propose | plan_and_run (future)
    workspace_root: Optional[str] = None  # Workspace root for reading new file contents
    state: Optional[
        Dict[str, Any]
    ] = None  # State from previous response for autonomous coding continuity


class ChatResponse(BaseModel):
    content: str
    context: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None
    # Add autonomous coding support fields
    actions: Optional[List[Dict[str, Any]]] = None
    agentRun: Optional[Dict[str, Any]] = None
    state: Optional[Dict[str, Any]] = None
    should_stream: Optional[bool] = None
    duration_ms: Optional[int] = None
    reply: Optional[str] = None


class ProactiveSuggestionsRequest(BaseModel):
    context: Dict[str, Any]


# ------------------------------------------------------------------------------
# Fake review endpoint deleted - use real review endpoint in navi.py instead
# Extension now calls /repo/review/stream (navi.py) not /api/navi/repo/review/stream (this file)

# All fake review code removed to prevent conflicts with real review endpoint

# All fake review code removed to prevent conflicts with real review endpoint


@navi_router.post("/repo/fix/{fix_id}")
async def apply_auto_fix(fix_id: str) -> dict:
    """
    Apply an auto-fix by fix ID.
    """
    try:
        # Parse fix ID to determine action
        if fix_id.startswith("remove-console-"):
            # Remove console.log from specific line
            line_num = int(fix_id.split("-")[-1])
            # This is a simplified implementation - in production you'd want more robust parsing
            return {
                "success": True,
                "message": f"Console.log removal simulated for line {line_num}",
            }

        elif fix_id.startswith("fix-duplicate-"):
            # Remove duplicate JSON key
            key_name = fix_id.replace("fix-duplicate-", "")
            return {
                "success": True,
                "message": f"Duplicate key '{key_name}' removal simulated",
            }

        elif fix_id == "fix-dep-overlap":
            # Move overlapping deps to devDependencies
            return {"success": True, "message": "Dependency overlap fix simulated"}

        elif fix_id.startswith("remove-import-"):
            # Remove unused import
            line_num = int(fix_id.split("-")[-1])
            return {
                "success": True,
                "message": f"Unused import removal simulated for line {line_num}",
            }

        elif fix_id.startswith("remove-print-"):
            # Remove print statement
            line_num = int(fix_id.split("-")[-1])
            return {
                "success": True,
                "message": f"Print statement removal simulated for line {line_num}",
            }

        else:
            return {"success": False, "message": f"Unknown fix ID: {fix_id}"}

    except Exception as e:
        return {"success": False, "message": f"Fix failed: {str(e)}"}


# ------------------------------------------------------------------------------
# Streaming helper for LLM responses
# ------------------------------------------------------------------------------
async def stream_llm_response(question: str, context: Dict[str, Any]):
    """Stream LLM response as Server-Sent Events"""
    llm_service = get_llm_service()

    if not llm_service:
        yield f"data: {json.dumps({'error': 'LLM service unavailable'})}\n\n"
        return

    try:
        # Use OpenAI streaming
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=llm_service.settings.openai_api_key)

        system_prompt = llm_service._build_engineering_system_prompt(context)
        user_prompt = llm_service._build_user_prompt(question, context)

        stream = await client.chat.completions.create(
            model=llm_service.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=1500,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                yield f"data: {json.dumps({'content': content})}\n\n"

        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Streaming error: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


# ------------------------------------------------------------------------------
# Navi entrypoints: /api/navi/chat and /api/navi/chat/stream
# ------------------------------------------------------------------------------
@navi_router.post("/chat/stream")
async def navi_chat_stream(request: NaviChatRequest, db: Session = Depends(get_db)):
    """Streaming version of navi_chat with SSE"""
    try:
        intent = await _analyze_user_intent(request.message)
        context = await _build_enhanced_context(
            ChatRequest(
                message=request.message,
                conversationHistory=request.conversationHistory,
                currentTask=request.currentTask,
                teamContext=request.teamContext,
            ),
            intent,
        )

        return StreamingResponse(
            stream_llm_response(request.message, context),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as stream_error:
        logger.error(f"Stream initialization error: {stream_error}")
        error_msg = str(stream_error)

        async def error_stream():
            yield f"data: {json.dumps({'error': error_msg})}\n\n"

        return StreamingResponse(error_stream(), media_type="text/event-stream")


@navi_router.post("/chat", response_model=ChatResponse)
async def navi_chat(
    request: NaviChatRequest, db: Session = Depends(get_db)
) -> ChatResponse:
    """
    Navi Chat API (Phase 1): Diff-aware code review + Comprehensive Analysis.

    Router:
      - if attachments contain a diff -> handle diff review
      - if code analysis request + workspace -> comprehensive analysis
      - else -> fall back to existing /api/chat/respond behavior
    """
    # DEBUG: Log incoming request state
    print(f"\n{'='*80}")
    print("🔵 CHAT.PY NAVI_CHAT CALLED 🔵")
    print(f"DEBUG REQUEST - Message: {request.message[:50]}...")
    print(f"DEBUG REQUEST - Has state: {request.state is not None}")
    print(f"DEBUG REQUEST - State content: {request.state}")
    print(f"{'='*80}\n")
    logger.info(
        f"🔵 CHAT.PY navi_chat handler called with message: {request.message[:50]}"
    )

    try:
        # Fetch relevant memories to ground the response
        memories: List[Dict[str, Any]] = []
        try:
            memories = await search_memory(
                db=db,
                user_id="default_user",
                query=request.message,
                limit=5,
                min_importance=1,
            )
        except Exception:
            # Fallback: recent memories if embeddings/search fail (e.g., no OpenAI key)
            try:
                memories = await get_recent_memories(
                    db=db, user_id="default_user", limit=5
                )
            except Exception:
                memories = []

        if _has_diff_attachments(request.attachments):
            return await _handle_diff_review(request)

        # Check for comprehensive code analysis requests
        message = request.message.strip()
        message_lower = message.lower()
        workspace_root = request.workspace_root

        # 🚀 CHECK FOR NEW PROJECT CREATION
        # Detect if the user is asking to create a new project
        # Check for combinations of action verbs + project/website/app keywords
        action_verbs = ["create", "build", "make", "start", "scaffold"]
        project_keywords = ["project", "website", "app", "application", "workspace"]

        # Check if message contains any action verb + any project keyword
        has_action = any(verb in message_lower for verb in action_verbs)
        has_project_keyword = any(
            keyword in message_lower for keyword in project_keywords
        )
        is_project_creation = has_action and has_project_keyword

        # Also check explicit patterns for higher confidence
        explicit_patterns = [
            "new project",
            "new workspace",
            "new app",
            "new application",
        ]
        if any(pattern in message_lower for pattern in explicit_patterns):
            is_project_creation = True

        # Exclude conversational/clarification responses
        # These are NOT project creation requests
        clarification_phrases = [
            "ok please",
            "okay please",
            "can you",
            "could you",
            "please choose",
            "choose the",
            "which one",
            "what should",
            "help me choose",
        ]
        if any(phrase in message_lower for phrase in clarification_phrases):
            is_project_creation = False
            logger.info(
                f"Message contains clarification phrase, not treating as project creation: {message[:50]}"
            )

        if is_project_creation:
            logger.info(f"Detected project creation request: {message}")

            # Simple extraction without LLM - parse project name from message
            try:
                # Extract project name by looking for common patterns
                # e.g., "create the Marketing website" -> "marketing-website"
                # e.g., "build a blog app" -> "blog-app"

                words = message.lower().split()

                # Find the main subject words (skip common words)
                skip_words = {
                    "the",
                    "a",
                    "an",
                    "for",
                    "to",
                    "and",
                    "or",
                    "of",
                    "in",
                    "on",
                    "at",
                    "with",
                }
                action_verbs_set = set(action_verbs)

                subject_words = []
                found_action = False
                for word in words:
                    clean_word = re.sub(r"[^\w-]", "", word)  # Remove punctuation
                    if clean_word in action_verbs_set:
                        found_action = True
                        continue
                    if found_action and clean_word and clean_word not in skip_words:
                        subject_words.append(clean_word)

                # Generate project name (take first 3-4 meaningful words)
                if subject_words:
                    project_name = "-".join(subject_words[:4])
                else:
                    project_name = "new-project"

                description = message
                parent_dir = os.path.expanduser("~/dev")

                logger.info(
                    f"Extracted project_name: {project_name}, description: {description}"
                )

                # Return a special response asking user to confirm the location
                return ChatResponse(
                    content=f"""I'll help you create a new project: **{project_name}**

📁 **Suggested location**: `{parent_dir}/{project_name}`

I'll automatically detect the best tech stack based on your description (Next.js, React, Vue, static HTML, etc.) and set everything up for you.

**Reply "yes" to create it at the suggested location**, or specify a different directory.
""",
                    agentRun={
                        "mode": "project_creation",
                        "project_name": project_name,
                        "description": description,
                        "parent_dir": parent_dir,
                    },
                    state={
                        "project_creation": True,
                        "project_name": project_name,
                        "description": description,
                        "parent_dir": parent_dir,
                    },
                    suggestions=["Yes, create it", "Use /different/path", "Cancel"],
                )

            except Exception as e:
                logger.error(f"Error extracting project details: {e}", exc_info=True)
                # Fall through to normal chat handling

        # Check if this is a confirmation for project creation
        # IMPORTANT: This must be checked BEFORE autonomous coding approval to avoid conflicts
        if request.state and request.state.get("project_creation"):
            logger.info(f"Processing project creation confirmation: {message}")
            project_name = request.state.get("project_name")
            description = request.state.get("description")
            parent_dir = request.state.get("parent_dir")

            # Check if user is confirming or providing a different path
            if message_lower in [
                "yes",
                "create it",
                "proceed",
                "go ahead",
                "okay",
                "ok",
            ]:
                # Use the suggested parent directory
                logger.info(f"User confirmed project creation at: {parent_dir}")
                pass
            elif "use " in message_lower:
                # Extract the path from "use /path/to/dir"
                path_match = re.search(r"use\s+([~/\w\-/.]+)", message, re.IGNORECASE)
                if path_match:
                    parent_dir = os.path.expanduser(path_match.group(1))
                    logger.info(f"User specified custom parent directory: {parent_dir}")
            elif os.path.exists(os.path.expanduser(message.strip())):
                # User provided a direct path
                parent_dir = os.path.expanduser(message.strip())
                logger.info(f"User provided direct path: {parent_dir}")

            # Call the project creation API
            try:
                import httpx

                # Use port 8787 (the port where the backend is running)
                backend_url = "http://localhost:8787"
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{backend_url}/api/autonomous/create-project",
                        json={
                            "project_name": project_name,
                            "description": description,
                            "parent_directory": parent_dir,
                            "typescript": True,
                            "git_init": True,
                            "install_dependencies": True,
                        },
                        timeout=300.0,  # 5 minutes for npm install
                    )

                    result = response.json()

                    if result["success"]:
                        return ChatResponse(
                            content=f"""✅ **Project created successfully!**

📁 **Location**: `{result['project_path']}`
🎯 **Type**: {result['project_type']}

**Commands executed**:
```bash
{chr(10).join(result['commands_run'])}
```

{result['message']}

I'll now open this project in VSCode for you. Once it opens, I can help you customize it further!
""",
                            agentRun={
                                "mode": "project_created",
                                "project_path": result["project_path"],
                                "open_in_vscode": True,
                            },
                            state={
                                "recent_project": {
                                    "path": result["project_path"],
                                    "name": project_name,
                                    "type": result["project_type"],
                                    "description": description,
                                },
                                "context": "project_created",
                            },
                            suggestions=["Customize project", "Add features", "Done"],
                        )
                    else:
                        return ChatResponse(
                            content=f"""❌ **Failed to create project**

{result['message']}

Error: {result.get('error', 'Unknown error')}

Would you like to try a different location or project name?
""",
                            state={
                                "project_creation_failed": True,
                                "project_name": project_name,
                                "description": description,
                                "parent_dir": parent_dir,
                                "error": result.get("error", "Unknown error"),
                            },
                            suggestions=[
                                "Try different location",
                                "Change project name",
                                "Cancel",
                            ],
                        )

            except Exception as e:
                logger.error(f"Error creating project: {e}", exc_info=True)
                return ChatResponse(
                    content=f"""❌ **Error creating project**

{str(e)}

Would you like to try again with different settings?
""",
                    suggestions=["Try again", "Change location", "Cancel"],
                )

        # 🤖 CHECK FOR AUTONOMOUS STEP APPROVAL
        # If the message is a simple approval and there's an active autonomous task in state
        approval_keywords = [
            "yes",
            "proceed",
            "continue",
            "go ahead",
            "approve",
            "ok",
            "okay",
            "sure",
            "do it",
        ]
        is_approval = (
            any(keyword in message_lower for keyword in approval_keywords)
            and len(message.split()) <= 5
        )

        # Check for bulk approval (approve all remaining steps)
        is_bulk_approval = any(
            phrase in message_lower
            for phrase in [
                "approve all",
                "all remaining",
                "approve remaining",
                "do all",
                "yes to all",
            ]
        )

        logger.error("=== DEBUG APPROVAL ===")
        logger.error(f"Message: {message}")
        logger.error(f"is_approval: {is_approval}")
        logger.error(f"is_bulk_approval: {is_bulk_approval}")
        logger.error(f"has state: {request.state is not None}")
        logger.error(f"state content: {request.state}")
        logger.error("===================")
        print(
            f"DEBUG APPROVAL - is_approval: {is_approval}, is_bulk: {is_bulk_approval}, has state: {request.state is not None}, state content: {request.state}"
        )

        if (
            (is_approval or is_bulk_approval)
            and request.state
            and request.state.get("autonomous_coding")
        ):
            logger.error("=== ENTERING EXECUTION BLOCK ===")
            try:
                task_id = request.state.get("task_id")
                current_step_index = request.state.get("current_step", 0)
                logger.error(f"Task ID: {task_id}, Current Step: {current_step_index}")

                # Use the shared engine instance from autonomous_coding router
                # Import the shared _coding_engines dict
                from backend.api.routers.autonomous_coding import _coding_engines

                # Get the shared engine instance that has our tasks
                workspace_id = request.state.get("workspace_id", "default")
                coding_engine = _coding_engines.get(workspace_id)

                if not coding_engine:
                    # Engine not found - fall through to normal chat
                    logger.warning(
                        f"Coding engine not found for workspace {workspace_id}"
                    )
                    raise ValueError("Engine not available")

                # Get the task from the shared engine
                task = coding_engine.active_tasks.get(task_id)
                logger.error(f"Task found: {task is not None}")
                if task:
                    logger.error(
                        f"Task has {len(task.steps)} steps, current step: {current_step_index}"
                    )

                if task and current_step_index < len(task.steps):
                    # Check if we should auto-execute all steps (from initial approval)
                    auto_execute_all = request.state and request.state.get(
                        "auto_execute_all", False
                    )
                    logger.error(f"Auto execute all: {auto_execute_all}")

                    # Determine if we're executing all remaining steps or just one
                    steps_to_execute = (
                        range(current_step_index, len(task.steps))
                        if (is_bulk_approval or auto_execute_all)
                        else [current_step_index]
                    )

                    logger.error("=== EXECUTION LOOP STARTING ===")
                    logger.error(f"Steps to execute: {list(steps_to_execute)}")

                    completed_steps = []
                    failed_step = None

                    # Build progress message
                    if len(list(steps_to_execute)) > 1:
                        progress_msg = f"🚀 **Executing {len(list(steps_to_execute))} steps automatically...**\n\n"
                    else:
                        progress_msg = ""

                    logger.error("About to enter for loop...")
                    for step_index in steps_to_execute:
                        logger.error(f"=== LOOP ITERATION {step_index + 1} ===")
                        current_step = task.steps[step_index]

                        # Log progress for user visibility
                        logger.info(
                            f"[NAVI PROGRESS] Executing Step {step_index + 1}/{len(task.steps)}: {current_step.description}"
                        )
                        logger.info(
                            f"[NAVI PROGRESS] Working on file: {current_step.file_path}"
                        )

                        # Add progress info to message
                        progress_msg += f"⏳ **Step {step_index + 1}/{len(task.steps)}:** {current_step.description}\n"
                        progress_msg += f"📝 Working on: `{current_step.file_path}`\n\n"

                        # Execute the step
                        result = await coding_engine.execute_step(
                            task_id=task_id, step_id=current_step.id, user_approved=True
                        )

                        if result["status"] == "completed":
                            completed_steps.append((step_index, current_step, result))
                        else:
                            failed_step = (step_index, current_step, result)
                            break  # Stop on first failure

                    # Build response based on results
                    if completed_steps and not failed_step:
                        # All requested steps completed successfully
                        last_step_index, last_step, last_result = completed_steps[-1]
                        next_step_index = last_step_index + 1

                        if is_bulk_approval or auto_execute_all:
                            reply = f"{progress_msg}\n✅ **All steps execution completed!**\n\n"
                            reply += f"Successfully executed {len(completed_steps)} step{'s' if len(completed_steps) != 1 else ''}:\n"
                            for idx, step, _ in completed_steps:
                                # Try to get git diff stats for this file
                                diff_stats = ""
                                try:
                                    import subprocess

                                    result = subprocess.run(
                                        [
                                            "git",
                                            "diff",
                                            "--numstat",
                                            "HEAD",
                                            step.file_path,
                                        ],
                                        cwd=workspace_root,
                                        capture_output=True,
                                        text=True,
                                        timeout=2,
                                    )
                                    if result.returncode == 0 and result.stdout.strip():
                                        parts = result.stdout.strip().split()
                                        if len(parts) >= 2:
                                            additions = parts[0]
                                            deletions = parts[1]
                                            if additions != "-" and deletions != "-":
                                                diff_stats = f" <span style='color:#22c55e'>+{additions}</span> <span style='color:#ef4444'>-{deletions}</span>"
                                except Exception:
                                    pass

                                reply += f"- ✅ Step {idx + 1}: `{step.file_path}`{diff_stats}\n"
                            reply += "\n"
                        else:
                            reply = f"✅ **Step {last_step_index + 1} completed!**\n\n"
                            reply += f"Changes applied to `{last_step.file_path}`\n\n"

                        if next_step_index < len(task.steps):
                            # More steps remaining - prompt for next step
                            next_step = task.steps[next_step_index]
                            reply += f"**Next: Step {next_step_index + 1}/{len(task.steps)}**\n"
                            reply += f"{next_step.description}\n"
                            reply += f"📁 File: `{next_step.file_path}` ({next_step.operation})\n\n"
                            reply += "Ready to proceed?"

                            return ChatResponse(
                                content=reply,
                                agentRun={
                                    "mode": "autonomous_coding",
                                    "task_id": task_id,
                                    "status": "awaiting_approval",
                                    "current_step": next_step_index,
                                    "total_steps": len(task.steps),
                                },
                                state={
                                    "autonomous_coding": True,
                                    "task_id": task_id,
                                    "workspace": workspace_root,
                                    "workspace_id": workspace_id,
                                    "current_step": next_step_index,
                                    "total_steps": len(task.steps),
                                },
                                suggestions=[
                                    "Yes",
                                    "Approve all remaining",
                                    "Skip this step",
                                    "Cancel",
                                ],
                            )
                        else:
                            # Task complete! Show detailed summary
                            reply += progress_msg if progress_msg else ""
                            reply += "🎉 **All steps completed!**\n\n"

                            # List all files that were modified with git diff stats
                            reply += "**📝 Files Created/Modified:**\n"
                            for step in task.steps:
                                if step.file_path and step.file_path not in (
                                    "N/A",
                                    "n/a",
                                ):
                                    operation_icon = (
                                        "📄"
                                        if step.operation == "create"
                                        else "✏️"
                                        if step.operation == "modify"
                                        else "🗑️"
                                    )

                                    # Try to get git diff stats for this file
                                    diff_stats = ""
                                    try:
                                        import subprocess

                                        result = subprocess.run(
                                            [
                                                "git",
                                                "diff",
                                                "--numstat",
                                                "HEAD",
                                                step.file_path,
                                            ],
                                            cwd=workspace_root,
                                            capture_output=True,
                                            text=True,
                                            timeout=2,
                                        )
                                        if (
                                            result.returncode == 0
                                            and result.stdout.strip()
                                        ):
                                            parts = result.stdout.strip().split()
                                            if len(parts) >= 2:
                                                additions = parts[0]
                                                deletions = parts[1]
                                                if (
                                                    additions != "-"
                                                    and deletions != "-"
                                                ):
                                                    diff_stats = (
                                                        f" `+{additions} -{deletions}`"
                                                    )
                                    except Exception:
                                        pass

                                    reply += f"{operation_icon} `{step.file_path}` ({step.operation}){diff_stats}\n"
                            reply += "\n"

                            # Add implementation summary
                            reply += "**✨ What Was Implemented:**\n"
                            reply += f"- {task.title}\n"
                            reply += f"- Completed {len(task.steps)} step{'s' if len(task.steps) != 1 else ''} successfully\n"
                            reply += (
                                "- All changes have been applied to your workspace\n\n"
                            )

                            # Add testing instructions
                            reply += "**🧪 How to Test:**\n"
                            reply += "1. Review the modified files in your editor\n"
                            reply += "2. Run your application to test the changes\n"
                            reply += "3. Test the new functionality manually\n"
                            reply += "4. Run your test suite if available\n\n"

                            # Add next steps
                            reply += "**🚀 Next Steps:**\n"
                            reply += "- Review the changes and ensure they meet your requirements\n"
                            reply += "- Test the implementation thoroughly\n"
                            reply += "- Commit the changes when ready\n"
                            reply += "- Create a PR or continue with more changes\n"

                            # Store memory of completed task
                            try:
                                files_modified = [
                                    step.file_path
                                    for step in task.steps
                                    if step.file_path
                                    and step.file_path not in ("N/A", "n/a")
                                ]
                                memory_content = (
                                    f"Implemented: {task.title}\n"
                                    f"Files modified: {', '.join(files_modified)}\n"
                                    f"Steps completed: {len(task.steps)}"
                                )
                                await store_memory(
                                    db=db,
                                    user_id="default_user",
                                    category="task",
                                    content=memory_content,
                                    scope=workspace_root,
                                    title=f"Completed: {task.title}",
                                    tags={
                                        "type": "autonomous_coding",
                                        "task_id": task_id,
                                        "files": files_modified,
                                        "workspace": workspace_root,
                                    },
                                    importance=4,
                                )
                                logger.info(
                                    f"[NAVI MEMORY] Stored task completion: {task.title}"
                                )
                            except Exception as e:
                                logger.warning(
                                    f"[NAVI MEMORY] Failed to store memory: {e}"
                                )

                            return ChatResponse(
                                content=reply,
                                suggestions=[
                                    "Show me the changes",
                                    "Create PR",
                                    "Make more changes",
                                    "Done",
                                ],
                            )
                    elif failed_step:
                        # A step failed during bulk or single execution
                        step_index, current_step, result = failed_step

                        if completed_steps:
                            reply = f"⚠️ **Partial completion: {len(completed_steps)}/{len(steps_to_execute)} steps completed**\n\n"
                            reply += "Completed steps:\n"
                            for idx, step, _ in completed_steps:
                                reply += f"- ✅ Step {idx + 1}: {step.file_path}\n"
                            reply += f"\n❌ Step {step_index + 1} failed: {result.get('error', 'Unknown error')}\n\n"
                        else:
                            reply = f"❌ Step {step_index + 1} failed: {result.get('error', 'Unknown error')}\n\n"

                        reply += "Would you like to retry or skip this step?"

                        return ChatResponse(
                            content=reply,
                            state={
                                "autonomous_coding": True,
                                "task_id": task_id,
                                "workspace": workspace_root,
                                "workspace_id": workspace_id,
                                "current_step": step_index,  # Keep at failed step
                                "total_steps": len(task.steps),
                                "failed_step": step_index,  # Remember which step failed
                            },
                            suggestions=["Retry", "Skip", "Cancel"],
                        )
            except Exception as e:
                logger.error(f"Error executing autonomous step: {e}")
                # Fall through to normal chat handling

        # 🏗️ CHECK FOR FOLLOW-UP REQUESTS ON RECENTLY CREATED PROJECT OR FAILED PROJECT
        if request.state and (
            request.state.get("recent_project")
            or request.state.get("project_creation_failed")
        ):
            # Handle failed project creation - user might want to open existing or try again
            if request.state.get("project_creation_failed"):
                failed_project_name = request.state.get("project_name", "")
                parent_dir = request.state.get("parent_dir", "")

                # Check if user wants to open the existing project
                open_keywords = ["open", "show", "navigate", "go to", "switch to"]
                wants_to_open = any(kw in message_lower for kw in open_keywords)

                if wants_to_open and failed_project_name:
                    # User wants to open the existing project
                    project_path = os.path.join(parent_dir, failed_project_name)
                    if os.path.exists(project_path):
                        return ChatResponse(
                            content=f"""I'll open the existing project **{failed_project_name}** for you.

📁 **Location**: `{project_path}`

Opening in a new VSCode window...""",
                            agentRun={
                                "mode": "open_existing_project",
                                "project_path": project_path,
                            },
                            state={
                                "recent_project": {
                                    "path": project_path,
                                    "name": failed_project_name,
                                    "type": "existing",
                                    "description": request.state.get("description", ""),
                                },
                                "context": "opened_existing",
                            },
                            suggestions=[
                                "Add features",
                                "Review project",
                                "Done",
                            ],
                        )
                    else:
                        return ChatResponse(
                            content=f"""❌ Project not found at `{project_path}`.

Would you like to create it at a different location?""",
                            state=request.state,  # Keep the failure state
                            suggestions=["Try different location", "Cancel"],
                        )

            recent_project = request.state.get("recent_project")
            if not recent_project:
                # No recent project context, continue
                pass
            else:
                # Check if this is a casual acknowledgment (should maintain context)
                casual_acknowledgments = [
                    "sure",
                    "ok",
                    "okay",
                    "thanks",
                    "thank you",
                    "great",
                    "cool",
                    "nice",
                ]
                is_casual = (
                    any(ack in message_lower for ack in casual_acknowledgments)
                    and len(message.split()) <= 3
                )

                if is_casual:
                    # User is just acknowledging - maintain context and ask what's next
                    return ChatResponse(
                        content=f"""Great! Your project **{recent_project['name']}** is ready at `{recent_project['path']}`.

What would you like to do next? I can help you:
- Add specific files or features to the project
- Install additional dependencies
- Set up configuration files
- Customize the project structure
- Or start working on something else

What would you like to work on?""",
                        state={
                            "recent_project": recent_project,
                            "context": "project_created",
                        },
                        suggestions=[
                            "Add a homepage",
                            "Install dependencies",
                            "Configure settings",
                            "Start new task",
                        ],
                    )

                # Check for modification requests
                modification_keywords = [
                    "add",
                    "install",
                    "create",
                    "setup",
                    "configure",
                    "modify",
                    "change",
                    "update",
                ]
                is_modification = any(
                    kw in message_lower for kw in modification_keywords
                )

                if is_modification:
                    # User wants to modify the recently created project
                    # Set workspace_root to the new project path so autonomous coding can work
                    workspace_root = recent_project["path"]
                    logger.info(
                        f"[NAVI] Detected follow-up request for project {recent_project['name']} at {workspace_root}"
                    )
                    # Continue to autonomous coding detection below

        # Check if this is a code analysis request (include common error/bug wording + typos)
        code_analysis_keywords = [
            "analyze",
            "analysis",
            "review",
            "changes",
            "code",
            "diff",
            "git",
            "quality",
            "security",
            "performance",
            "lint",
            "test",
            "tests",
            "bug",
            "bugs",
            "issue",
            "issues",
            "problem",
            "problems",
            "error",
            "errors",
            "fail",
            "failed",
            "failing",
        ]
        error_typo_pattern = re.compile(r"\berr+o?r?s?\b")
        is_code_analysis = any(
            keyword in message_lower for keyword in code_analysis_keywords
        ) or bool(error_typo_pattern.search(message_lower))

        # Exclude explanation/overview questions from code analysis and autonomous mode
        # But allow action requests like "fix errors", "create feature"
        has_action_keywords = any(
            keyword in message_lower
            for keyword in ["fix", "create", "implement", "add", "build", "generate"]
        )

        is_explanation_request = not has_action_keywords and any(
            keyword in message_lower
            for keyword in [
                "explain",
                "what is",
                "what does",
                "describe",
                "tell me about",
                "how does",
                "overview",
                "summary",
            ]
        )

        print(f"DEBUG NAVI CHAT - Message: '{message[:100]}'")
        print(f"DEBUG NAVI CHAT - Workspace root: '{workspace_root}'")
        print(f"DEBUG NAVI CHAT - Is code analysis: {is_code_analysis}")
        print(f"DEBUG NAVI CHAT - Is explanation: {is_explanation_request}")
        print(
            f"DEBUG NAVI CHAT - Should trigger comprehensive: {is_code_analysis and workspace_root and not is_explanation_request}"
        )

        # 🤖 AUTONOMOUS CODING DETECTION - Add this before comprehensive analysis
        autonomous_keywords = [
            "create",
            "implement",
            "build",
            "generate",
            "add",
            "write",
            "make",
            "develop",
            "code",
        ]
        message_lower = message.lower()
        has_autonomous_keywords = any(
            keyword in message_lower for keyword in autonomous_keywords
        )

        # Exclude explanation/analysis questions from autonomous mode
        is_explanation_question = any(
            keyword in message_lower
            for keyword in [
                "explain",
                "what is",
                "what does",
                "describe",
                "tell me about",
                "how does",
                "overview",
                "summary",
                "analyze",
            ]
        )

        print(f"DEBUG AUTONOMOUS - Has keywords: {has_autonomous_keywords}")
        print(f"DEBUG AUTONOMOUS - Has workspace: {bool(workspace_root)}")
        print(f"DEBUG AUTONOMOUS - Is explanation: {is_explanation_question}")

        if has_autonomous_keywords and workspace_root and not is_explanation_question:
            print("DEBUG AUTONOMOUS - TRIGGERING AUTONOMOUS CODING ENGINE")

            try:
                # Initialize autonomous coding engine
                llm_service = get_llm_service()
                if not llm_service:
                    return ChatResponse(
                        content="⚠️ Autonomous coding requires LLM service. Please configure OPENAI_API_KEY.",
                        suggestions=["Configure API key", "Try a different approach"],
                    )

                # Use shared coding engine instance from autonomous_coding router
                # This ensures tasks persist across requests
                from backend.api.routers.autonomous_coding import get_coding_engine

                # Use "default" workspace ID for now (can be customized per user/project later)
                workspace_id = "default"
                coding_engine = get_coding_engine(workspace_id=workspace_id, db=db)

                # Check memory for similar previous tasks
                previous_memories = []
                try:
                    previous_memories = await search_memory(
                        db=db,
                        user_id="default_user",
                        query=message,
                        categories=["task"],
                        limit=5,
                        min_importance=3,
                    )
                    if previous_memories:
                        logger.info(
                            f"[NAVI MEMORY] Found {len(previous_memories)} related memories"
                        )
                except Exception as e:
                    logger.warning(f"[NAVI MEMORY] Failed to search memory: {e}")

                # Check if similar work was already done
                if previous_memories:
                    # Look for memories in the same workspace
                    workspace_memories = [
                        m
                        for m in previous_memories
                        if m.get("scope") == workspace_root
                        and m.get("similarity", 0) > 0.8
                    ]

                    if workspace_memories:
                        # Found very similar previous work!
                        latest_memory = workspace_memories[0]
                        return ChatResponse(
                            content=f"""✅ **I already implemented something similar!**

I previously worked on: **{latest_memory.get('title', 'this task')}**

**What I implemented:**
{latest_memory.get('content', 'Previous implementation details')}

**Options:**
- If you want me to enhance or modify what's already there, please specify what changes you'd like
- If you want me to implement this differently, I can create a new implementation
- If you want to review what I did, I can show you the changes

What would you like to do?""",
                            suggestions=[
                                "Show me what you implemented",
                                "Add more features",
                                "Implement it differently",
                                "Test the existing implementation",
                            ],
                        )

                # Check if related files already exist in workspace
                # This helps provide better context to the LLM when planning
                workspace_context = None
                try:
                    # Extract potential file/feature names from the message
                    # e.g., "signin", "signup", "login", "auth", etc.
                    # os and Path are already imported at the top of the file

                    # Look for common patterns that might indicate what to search for
                    # Extract words from message (simple approach)
                    words = re.findall(r"\b\w+\b", message_lower)
                    # Filter for relevant keywords (avoid common words)
                    relevant_keywords = [
                        w
                        for w in words
                        if len(w) > 3
                        and w
                        not in {
                            "create",
                            "make",
                            "add",
                            "build",
                            "implement",
                            "write",
                            "please",
                            "could",
                            "would",
                            "should",
                            "want",
                            "need",
                            "have",
                            "already",
                            "there",
                            "check",
                        }
                    ]

                    # Check if any relevant files exist
                    existing_files = []
                    workspace_path = Path(workspace_root)
                    if workspace_path.exists() and relevant_keywords:
                        # Search for files that might be related
                        for keyword in relevant_keywords[
                            :5
                        ]:  # Limit to first 5 keywords
                            # Case-insensitive glob search
                            for pattern in [f"**/*{keyword}*", f"**/{keyword}*"]:
                                try:
                                    matches = list(workspace_path.glob(pattern))
                                    for match in matches[
                                        :3
                                    ]:  # Limit matches per keyword
                                        if match.is_file() and match.suffix in {
                                            ".js",
                                            ".ts",
                                            ".tsx",
                                            ".jsx",
                                            ".py",
                                            ".vue",
                                            ".svelte",
                                        }:
                                            rel_path = match.relative_to(workspace_path)
                                            existing_files.append(str(rel_path))
                                except Exception:
                                    pass

                    if existing_files:
                        workspace_context = (
                            f"Existing related files: {', '.join(existing_files[:10])}"
                        )
                        logger.info(
                            f"[NAVI WORKSPACE] Found {len(existing_files)} related files"
                        )
                except Exception as e:
                    logger.warning(f"[NAVI WORKSPACE] Failed to analyze workspace: {e}")

                # Determine task type from keywords
                task_type = AutonomousTaskType.FEATURE
                if any(kw in message_lower for kw in ["fix", "bug", "error"]):
                    task_type = AutonomousTaskType.BUG_FIX
                elif any(
                    kw in message_lower for kw in ["refactor", "improve", "optimize"]
                ):
                    task_type = AutonomousTaskType.REFACTOR
                elif any(kw in message_lower for kw in ["test", "tests"]):
                    task_type = AutonomousTaskType.TEST

                # Enhance description with workspace context if available
                enhanced_description = message
                if workspace_context:
                    enhanced_description = (
                        f"{message}\n\nWorkspace context: {workspace_context}"
                    )

                # Create autonomous task with proper parameters
                task = await coding_engine.create_task(
                    title=message[:100],  # Use first 100 chars as title
                    description=enhanced_description,
                    task_type=task_type,
                    repository_path=workspace_root,
                    user_id=None,  # Optional user tracking
                )

                # Get task ID and steps from the created task
                task_id = task.id
                steps = task.steps

                # Build concise response without repetition
                reply = f"""🤖 **Implementation Plan Created**

I'll implement this in **{len(steps)} step{'s' if len(steps) != 1 else ''}**:

"""
                # Show all steps (usually just 1-3 steps from enhanced engine)
                for i, step in enumerate(steps, 1):
                    reply += f"**Step {i}:** {step.description}\n"
                    reply += f"   📁 File: `{step.file_path}` ({step.operation})\n"
                    if step.reasoning:
                        reply += f"   💡 Why: {step.reasoning}\n"
                    reply += "\n"

                reply += """I'll execute all steps automatically once you approve. Ready to proceed?"""

                return ChatResponse(
                    content=reply,
                    # Don't include actions array - it causes unwanted "Apply" button
                    agentRun={
                        "mode": "autonomous_coding",
                        "task_id": task_id,
                        "status": "awaiting_approval",
                        "current_step": 0,
                        "total_steps": len(steps),
                    },
                    state={
                        "autonomous_coding": True,
                        "task_id": task_id,
                        "workspace": workspace_root,
                        "workspace_id": workspace_id,  # Add workspace_id for approval flow
                        "current_step": 0,
                        "total_steps": len(steps),
                        "auto_execute_all": True,  # Flag to execute all steps automatically
                    },
                    suggestions=[
                        "Yes, execute all steps",
                        "Show me more details",
                        "Cancel",
                    ],
                )
            except Exception as e:
                import traceback

                logger.error(f"Error starting autonomous coding: {e}")
                logger.error(f"Full traceback: {traceback.format_exc()}")
                return ChatResponse(
                    content=f"❌ Failed to start autonomous coding: {str(e)}\n\nPlease try again or rephrase your request.",
                    suggestions=["Try again", "Ask a different question"],
                )

        if is_code_analysis and workspace_root and not is_explanation_request:
            print("DEBUG NAVI CHAT - ENTERING comprehensive analysis branch")
            try:
                try:
                    git_service = GitService(workspace_root)
                except ValueError:
                    return ChatResponse(
                        content=(
                            "I cannot review changes because this folder does not look like a Git repository.\n\n"
                            "How to fix:\n"
                            "- Open the repo root that contains the `.git` folder.\n"
                            "- Or initialize a repo: `git init`, then add and commit your files.\n"
                            "- If this is a subfolder, reopen VS Code at the project root.\n"
                        ),
                        suggestions=[
                            "Open repo root",
                            "Initialize git",
                            "Retry review",
                        ],
                    )

                if not git_service.has_head():
                    return ChatResponse(
                        content=(
                            "I cannot compare against main/HEAD because this repository has no commits yet.\n\n"
                            "How to fix:\n"
                            "- Make sure you opened the repo root in VS Code.\n"
                            '- Create an initial commit: `git add -A` then `git commit -m "Initial commit"`.\n'
                            "- If you expect a remote main branch: `git fetch origin` and `git checkout main`.\n"
                        ),
                        suggestions=[
                            "Create initial commit",
                            "Fetch main branch",
                            "Retry review",
                        ],
                    )

                from backend.services.review_service import RealReviewService

                service = RealReviewService(workspace_root, analysis_depth="quick")
                changes = service.get_working_tree_changes()

                if not changes:
                    content = (
                        "🔍 **Repository Analysis Complete**\n\n"
                        "No changes detected in your working tree. Your repository is clean!"
                    )
                else:
                    review_entries = await service.analyze_working_tree()
                    total_issues = sum(len(entry.issues) for entry in review_entries)
                    severity_counts: Dict[str, int] = {}
                    for entry in review_entries:
                        for issue in entry.issues:
                            severity_counts[issue.severity] = (
                                severity_counts.get(issue.severity, 0) + 1
                            )

                    content = "🎯 **Code Analysis Complete**\n\n"
                    content += "📋 **Summary:**\n"
                    content += f"- Files analyzed: {len(review_entries)}\n"
                    content += f"- Total issues: {total_issues}\n"

                    if severity_counts:
                        content += "\n**Issues by Severity:**\n"
                        for severity, count in sorted(severity_counts.items()):
                            content += f"- {severity.title()}: {count}\n"

                    # Show a few example issues
                    top_issues = []
                    for entry in review_entries:
                        for issue in entry.issues:
                            top_issues.append((entry.file, issue))
                        if len(top_issues) >= 3:
                            break
                    if top_issues:
                        content += "\n**Top Findings:**\n"
                        for idx, (file_path, issue) in enumerate(top_issues[:3], 1):
                            content += f"{idx}. {file_path}: {issue.title}\n"

                # Return comprehensive analysis result
                return ChatResponse(
                    content=content,
                    suggestions=[
                        "Get detailed analysis",
                        "Review security findings",
                        "View performance issues",
                    ],
                )

            except Exception as e:
                print(f"DEBUG NAVI CHAT - Exception in comprehensive analysis: {e}")
                logger.error(f"Comprehensive analysis failed: {e}")
                # Fall through to standard processing

        # Fallback to your existing intent system
        base_response = await generate_chat_response(
            ChatRequest(
                message=request.message,
                conversationHistory=request.conversationHistory,
                currentTask=request.currentTask,
                teamContext=request.teamContext,
            ),
            db=db,
        )
        # Attach memories into context and surface a short blurb so users see what was referenced
        if base_response.context is None:
            base_response.context = {}
        base_response.context["memories"] = memories

        if memories:
            if not _is_simple_greeting(message_lower):
                bullets = []
                seen = set()
                for mem in memories:
                    title = mem.get("title") or mem.get("scope") or mem.get("category")
                    summary = (mem.get("content") or "").split("\n")[0][:180]
                    key = (title or "", summary)
                    if key in seen:
                        continue
                    seen.add(key)
                    bullets.append(f"- {title}: {summary}")
                    if len(bullets) >= 3:
                        break
                if bullets:
                    memory_snippet = "\n\nContext I referenced:\n" + "\n".join(bullets)
                    base_response.content = (
                        base_response.content or ""
                    ) + memory_snippet
        return base_response
    except Exception as e:
        logger.error(f"/api/navi/chat error: {e}")
        return ChatResponse(
            content="I ran into an error while processing that. Try again, or send a smaller diff.",
            suggestions=[
                "Review working changes",
                "Review staged changes",
                "Explain this repo",
            ],
        )


def _has_diff_attachments(attachments: List[Attachment]) -> bool:
    for a in attachments or []:
        kind = (a.kind or "").lower()
        lang = (a.language or "").lower()
        name = (a.name or "").lower()
        if kind in {"diff", "git_diff", "patch"}:
            return True
        if lang == "diff":
            return True
        if name.endswith(".diff") or name.endswith(".patch"):
            return True
        # Heuristic: content begins like a diff
        if a.content and (
            "diff --git " in a.content or a.content.lstrip().startswith("--- ")
        ):
            return True
    return False


def _is_simple_greeting(message: str) -> bool:
    cleaned = message.strip().lower()
    if not cleaned:
        return False
    return bool(
        re.fullmatch(r"(hi+|hello+|hey+|yo+|hola+|greetings)([!.\\s]*)", cleaned)
    )


# ------------------------------------------------------------------------------
# Existing /api/chat/respond (kept)
# ------------------------------------------------------------------------------
@router.post("/respond", response_model=ChatResponse)
async def generate_chat_response(
    request: ChatRequest, db: Session = Depends(get_db)
) -> ChatResponse:
    """
    Generate context-aware chat response using team intelligence
    """
    try:
        intent = await _analyze_user_intent(request.message)
        enhanced_context = await _build_enhanced_context(request, intent)

        if intent["type"] == "task_query":
            response = await _handle_task_query(intent, enhanced_context)
        elif intent["type"] == "team_query":
            response = await _handle_team_query(intent, enhanced_context)
        elif intent["type"] == "plan_request":
            response = await _handle_plan_request(intent, enhanced_context)
        elif intent["type"] == "code_help":
            response = await _handle_code_help(intent, enhanced_context)
        else:
            response = await _handle_general_query(intent, enhanced_context)

        return response

    except Exception as e:
        logger.error(f"Chat response error: {e}")
        return ChatResponse(
            content=f"I encountered an error: {str(e)}. Let me try a different approach.",
            suggestions=["Show my tasks", "Help with current work", "Generate a plan"],
        )


# ------------------------------------------------------------------------------
# Proactive suggestions (kept)
# ------------------------------------------------------------------------------
@router.post("/proactive")
@router.post("/suggestions/proactive")  # Backward compatibility
async def generate_proactive_suggestions(
    request: ProactiveSuggestionsRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Generate proactive suggestions based on current context
    """
    try:
        suggestions = []

        if request.context.get("recentChanges"):
            suggestions.extend(
                [
                    "I notice recent changes in multiple files. Would you like me to check for conflicts?",
                    "There might be merge conflicts brewing. Should I check dependencies?",
                ]
            )

        if request.context.get("currentFiles"):
            suggestions.extend(
                [
                    "The current files look like they might need testing. Want me to help with that?",
                    "I see some work in progress. Need help finishing up?",
                ]
            )

        if request.context.get("activeTask"):
            suggestions.extend(
                [
                    "Your current task might overlap with team work. Want to check?",
                    "There could be related work happening. Want to see team activity?",
                ]
            )

        return {"items": suggestions[:3]}

    except Exception as e:
        logger.error(f"Proactive suggestions error: {e}")
        return {"items": []}


# ------------------------------------------------------------------------------
# Phase 1: Diff review handler
# ------------------------------------------------------------------------------
MAX_DIFF_CHARS_PER_CALL = 120_000  # conservative to avoid blowing context
MAX_NEW_FILE_SIZE = 50_000  # Max bytes to read from a new file


def _is_text_file(filename: str) -> bool:
    """Check if a file should be treated as text (safe to read and review)."""
    text_extensions = {
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".json",
        ".md",
        ".txt",
        ".yaml",
        ".yml",
        ".env",
        ".example",
        ".gitignore",
        ".gitattributes",
        ".eslintrc",
        ".prettierrc",
        ".config",
        ".py",
        ".java",
        ".go",
        ".rs",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".css",
        ".scss",
        ".sass",
        ".less",
        ".html",
        ".xml",
        ".toml",
        ".ini",
        ".sh",
        ".bash",
        ".zsh",
        ".fish",
        ".vue",
        ".svelte",
        ".astro",
    }

    name_lower = filename.lower()

    # Check by extension
    for ext in text_extensions:
        if name_lower.endswith(ext):
            return True

    # Check by name patterns
    text_names = {
        ".env.local",
        ".env.development",
        ".env.production",
        ".env.test",
        "dockerfile",
        "makefile",
        "rakefile",
        "gemfile",
        "podfile",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "tsconfig.json",
        "jsconfig.json",
        "next.config.js",
        "vite.config.js",
        "tailwind.config.js",
        "postcss.config.js",
        "webpack.config.js",
    }

    return name_lower in text_names or any(name_lower.endswith(n) for n in text_names)


def _extract_new_files_from_diff(diff_text: str) -> List[str]:
    """Extract paths of files that are newly added (not just modified)."""
    new_files = []
    current_file = None
    is_new = False

    for line in diff_text.split("\n"):
        if line.startswith("diff --git"):
            # Reset for new file section
            match = re.search(r"diff --git a/(.+?) b/(.+?)$", line)
            if match:
                current_file = match.group(2)  # b path is the new path
                is_new = False
        elif line.startswith("new file mode"):
            is_new = True
        elif line.startswith("---"):
            # Check if it's /dev/null (confirms new file)
            if "/dev/null" in line and is_new and current_file:
                new_files.append(current_file)

    return new_files


async def _read_new_file_content(
    filepath: str, workspace_root: Optional[str] = None
) -> Optional[str]:
    """
    Attempt to read content of a newly added file from the workspace.
    Returns None if file doesn't exist, is binary, or is too large.
    """
    if not workspace_root:
        logger.debug(f"[Navi] No workspace root provided, cannot read {filepath}")
        return None

    if not _is_text_file(filepath):
        logger.debug(f"[Navi] Skipping binary/non-text file: {filepath}")
        return None

    full_path = os.path.join(workspace_root, filepath)

    try:
        # Check file size first
        stat_info = os.stat(full_path)
        if stat_info.st_size > MAX_NEW_FILE_SIZE:
            logger.warning(
                f"[Navi] File too large ({stat_info.st_size} bytes): {filepath}"
            )
            return f"(File too large: {stat_info.st_size} bytes)"

        # Read content
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        logger.info(f"[Navi] Read new file content: {filepath} ({len(content)} chars)")
        return content

    except FileNotFoundError:
        logger.debug(f"[Navi] File not found: {full_path}")
        return None
    except UnicodeDecodeError:
        logger.debug(f"[Navi] Binary file (decode error): {filepath}")
        return None
    except Exception as e:
        logger.error(f"[Navi] Error reading {filepath}: {e}")
        return None


# Phase 1 Formatting Helpers: Structure reviews with severity, metadata, and diffs
# ================================================================================


def _get_worst_severity(issues: List[Dict[str, Any]]) -> str:
    """Determine the worst severity from a list of issues."""
    priority = {"none": 0, "info": 1, "warning": 2, "error": 3}
    worst = "none"
    for issue in issues:
        sev = issue.get("severity", "info")
        if priority.get(sev, 0) > priority.get(worst, 0):
            worst = sev
    return worst


def _format_issues_markdown(issues: List[Dict[str, Any]]) -> str:
    """Convert a list of issue dicts to a Markdown bullet list."""
    if not issues:
        return "✅ No issues found."

    bullets = []
    for issue in issues:
        severity = issue.get("severity", "info").upper()
        message = issue.get("message", "Unknown issue")
        bullets.append(f"- **{severity}**: {message}")

    return "\n".join(bullets)


def _format_diff_review_block(
    file_path: str, diff_text: str, issues: List[Dict[str, Any]]
) -> str:
    """
    Returns a Markdown-formatted review block for a single file.
    Includes diff, issues, and metadata comments for future auto-fix (Phase 3).

    Args:
        file_path: The file being reviewed
        diff_text: The git diff for this file
        issues: List of issue dicts with 'severity', 'message', etc.

    Returns:
        Formatted Markdown string with severity icon, diff block, issues, and metadata
    """
    severity = _get_worst_severity(issues)
    severity_icon = {"info": "ℹ️", "warning": "⚠️", "error": "🚨", "none": "✅"}.get(
        severity, "✅"
    )

    issue_text = _format_issues_markdown(issues)

    # Metadata comment for Phase 3 auto-fix (extension can parse this later)
    metadata_comment = (
        f"<!-- navi-issue: {json.dumps({'file': file_path, 'issues': issues})} -->"
    )

    return f"""### 📄 `{file_path}` {severity_icon}

```diff
{diff_text.strip()}
```

**📝 Review:**

{issue_text}

{metadata_comment}
"""


def _parse_diff_by_file(diff_text: str) -> Dict[str, str]:
    """
    Parse a full diff into a dict of {file_path: file_diff}.
    Each entry starts with 'diff --git a/... b/...' and goes until the next diff line.
    """
    files: Dict[str, str] = {}
    current_file: Optional[str] = None
    current_diff_lines: List[str] = []

    for line in diff_text.split("\n"):
        if line.startswith("diff --git "):
            # Save previous file if any
            if current_file and current_diff_lines:
                files[current_file] = "\n".join(current_diff_lines)

            # Extract new file path
            match = re.search(r"diff --git a/(.+?) b/(.+?)$", line)
            if match:
                current_file = match.group(2)  # Use b/ (new/target) path
                current_diff_lines = [line]
            else:
                current_file = None
                current_diff_lines = []
        else:
            if current_file:
                current_diff_lines.append(line)

    # Don't forget the last file
    if current_file and current_diff_lines:
        files[current_file] = "\n".join(current_diff_lines)

    return files


def _extract_issues_from_review(review_text: str) -> List[Dict[str, Any]]:
    """
    Parse LLM review text to extract issues with severity levels.

    Looks for patterns like:
    - **ERROR**: message
    - **WARNING**: message
    - **INFO**: message

    Returns a list of issue dicts.
    """
    issues = []

    # Match patterns like "- **SEVERITY**: message"
    pattern = r"^- \*\*(ERROR|WARNING|INFO)\*\*: (.+)$"
    for match in re.finditer(pattern, review_text, re.MULTILINE):
        severity_str = match.group(1).lower()
        message = match.group(2).strip()

        severity_map = {
            "error": "error",
            "warning": "warning",
            "info": "info",
        }

        issues.append(
            {
                "severity": severity_map.get(severity_str, "info"),
                "message": message,
                "type": "review_comment",
            }
        )

    # If no issues found with that pattern, default to "no issues"
    if not issues:
        issues.append(
            {
                "severity": "none",
                "message": "No issues found",
                "type": "review_comment",
            }
        )

    return issues


def _structure_review_output(merged_review: str, files_by_path: Dict[str, str]) -> str:
    """
    Phase 1: Enhance a merged review to include per-file structured blocks with:
    - Syntax-highlighted diffs
    - Severity indicators
    - Issue metadata for future auto-fix

    For now, we parse per-file sections from the LLM's review text and
    reconstruct with proper formatting using _format_diff_review_block().

    Args:
        merged_review: Raw LLM output (Markdown)
        files_by_path: Dict of {file_path: diff_text}

    Returns:
        Enhanced Markdown with per-file structured blocks
    """
    output_lines = []

    # Start with the summary from the LLM
    lines = merged_review.split("\n")
    i = 0

    # Extract summary section (usually before per-file notes)
    while i < len(lines) and not lines[i].startswith("### "):
        output_lines.append(lines[i])
        i += 1

    # Now process per-file sections
    formatted_blocks = []
    for file_path, diff_text in files_by_path.items():
        # Extract issues for this file from merged_review if present
        # For Phase 1, we'll just pass an empty list; the LLM review is the main output
        issues = []

        # Format with the new structured format
        block = _format_diff_review_block(file_path, diff_text, issues)
        formatted_blocks.append(block)

    # Combine summary + formatted blocks + rest of review
    if formatted_blocks:
        output_lines.append("\n---\n")
        output_lines.extend(formatted_blocks)

    # Add the LLM's per-file notes if they exist
    while i < len(lines):
        output_lines.append(lines[i])
        i += 1

    return "\n".join(output_lines)


async def _handle_diff_review(request: NaviChatRequest) -> ChatResponse:
    diffs = [a.content for a in request.attachments if a.content]
    if not diffs:
        return ChatResponse(
            content='I didn\'t receive a diff attachment. Try "Review working changes" again.',
            suggestions=[
                "Review working changes",
                "Review staged changes",
                "Review last commit",
            ],
        )

    combined_diff = "\n\n".join(diffs).strip()
    files = _extract_files_from_diff(combined_diff)
    new_files = _extract_new_files_from_diff(combined_diff)

    # Get workspace root from request context if available
    workspace_root = None
    if hasattr(request, "workspace_root") and request.workspace_root:
        workspace_root = request.workspace_root
    elif request.teamContext and isinstance(request.teamContext, dict):
        workspace_root = request.teamContext.get("workspace_root")

    # Read content of new files
    new_file_contents: Dict[str, str] = {}
    if workspace_root and new_files:
        logger.info(
            f"[Navi] Found {len(new_files)} new files, attempting to read content"
        )
        for filepath in new_files[
            :10
        ]:  # Limit to 10 files to avoid overwhelming context
            content = await _read_new_file_content(filepath, workspace_root)
            if content:
                new_file_contents[filepath] = content

    chunks = _chunk_diff_by_file_boundaries(combined_diff, MAX_DIFF_CHARS_PER_CALL)
    user_prompt = request.message.strip() or "Review this diff."

    system_prompt = (
        "You are Navi, a senior staff software engineer performing a rigorous code review.\n"
        "Be direct, practical, and repo-friendly. Focus on correctness, security, performance, readability, "
        "tests, and API/behavior changes. Avoid fluff.\n\n"
        "OUTPUT FORMAT (CRITICAL for Phase 1 structured reviews):\n"
        "When listing issues or findings, use this format:\n"
        "- **ERROR**: <message for correctness/security issues>\n"
        "- **WARNING**: <message for style/performance issues>\n"
        "- **INFO**: <message for suggestions>\n\n"
        "Full structure:\n"
        "1) Summary (bullets)\n"
        "2) Risk & regressions (bullets)\n"
        "3) Per-file notes (use headings '### <path>')\n"
        "4) Suggested tests (bullets)\n"
        "5) If you propose code changes, show them as small patch snippets (fenced code blocks) where helpful.\n"
    )

    partial_reviews: List[str] = []

    # If we have new file contents, add them to the first chunk or create a dedicated review
    if new_file_contents:
        new_files_prompt = "\n\n---\n\n**Newly Added Files (full content):**\n\n"
        for filepath, content in new_file_contents.items():
            # Truncate very long files
            display_content = content[:5000] if len(content) > 5000 else content
            truncated = " (truncated)" if len(content) > 5000 else ""
            new_files_prompt += (
                f"### {filepath}{truncated}\n```\n{display_content}\n```\n\n"
            )

        # Review new files separately
        new_files_review = await _call_llm_for_review(
            system_prompt,
            f"{user_prompt}\n\nReview these newly added files. Check for: missing configurations, security issues, best practices, and potential improvements.",
            new_files_prompt,
        )
        partial_reviews.append(new_files_review)

    # Review the diff chunks
    for i, chunk in enumerate(chunks, start=1):
        chunk_header = f"[DIFF CHUNK {i}/{len(chunks)}]\n"
        content = chunk_header + chunk
        review = await _call_llm_for_review(system_prompt, user_prompt, content)
        partial_reviews.append(review)

    merged = await _merge_partial_reviews(system_prompt, user_prompt, partial_reviews)

    # Ensure merged is a clean string with no unexpected characters
    if not merged or not isinstance(merged, str):
        merged = "### Summary\n- No diff content to review."

    merged = merged.strip()

    # Phase 1: Structure the output with per-file blocks, diffs, and metadata
    files_by_path = _parse_diff_by_file(combined_diff)
    structured_output = _structure_review_output(merged, files_by_path)

    suggestions = [
        "Apply fixes for the top issues",
        "Generate unit tests for the risky parts",
        "Explain the biggest behavior change",
    ]

    logger.info(
        f"[Navi] Diff review completed: {len(files)} files ({len(new_files)} new), {len(chunks)} chunks, {len(structured_output)} chars in response"
    )

    return ChatResponse(
        content=structured_output,
        context={
            "type": "diff_review",
            "files": files,
            "new_files": new_files,
            "new_files_with_content": list(new_file_contents.keys()),
            "chunks": len(chunks),
        },
        suggestions=suggestions,
    )


def _extract_files_from_diff(diff_text: str) -> List[str]:
    # Typical: diff --git a/path b/path
    paths = []
    for m in re.finditer(
        r"^diff --git a/(.+?) b/(.+?)$", diff_text, flags=re.MULTILINE
    ):
        a_path, b_path = m.group(1), m.group(2)
        # prefer b_path (new name) unless it's /dev/null
        chosen = b_path if b_path and b_path != "dev/null" else a_path
        if chosen and chosen not in paths:
            paths.append(chosen)
    return paths


def _chunk_diff_by_file_boundaries(diff_text: str, max_chars: int) -> List[str]:
    """
    Splits the diff by 'diff --git' boundaries, then groups into <= max_chars chunks.
    """
    if len(diff_text) <= max_chars:
        return [diff_text]

    parts = re.split(r"(?=^diff --git )", diff_text, flags=re.MULTILINE)
    parts = [p for p in parts if p.strip()]

    chunks: List[str] = []
    buf = ""
    for part in parts:
        if not buf:
            buf = part
            continue

        if len(buf) + len(part) + 2 <= max_chars:
            buf = buf + "\n" + part
        else:
            chunks.append(buf)
            buf = part

    if buf:
        chunks.append(buf)

    # Fallback: if a single part is huge, hard-split by size
    final_chunks: List[str] = []
    for ch in chunks:
        if len(ch) <= max_chars:
            final_chunks.append(ch)
        else:
            for i in range(0, len(ch), max_chars):
                final_chunks.append(ch[i : i + max_chars])

    return final_chunks


async def _call_llm_for_review(
    system_prompt: str, user_prompt: str, diff_chunk: str
) -> str:
    api_key, base_url, model = _get_openai_config()
    if not api_key:
        # Safe fallback: still return something useful without an LLM call.
        return (
            "### Summary\n"
            "- (LLM not configured) Set `OPENAI_API_KEY` to enable automated diff review.\n\n"
            "### Risk & regressions\n"
            "- Cannot analyze without model access.\n\n"
            "### Per-file notes\n"
            "- Provide `OPENAI_API_KEY` and retry.\n\n"
            "### Suggested tests\n"
            "- Run your unit/integration tests.\n"
        )

    client = await get_http_client()
    url = f"{base_url}/chat/completions"

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"{user_prompt}\n\nHere is the git diff:\n\n{diff_chunk}",
        },
    ]

    resp = None
    try:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.2,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        content = (data.get("choices", [{}])[0].get("message", {}) or {}).get(
            "content", ""
        )

        # Ensure we always return a clean string
        if not content or not isinstance(content, str):
            logger.warning(f"LLM returned unexpected content type: {type(content)}")
            return "### Summary\n- LLM response was malformed."

        return content.strip()
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"LLM diff review call failed: {error_msg}")
        logger.error(f"  URL: {url}")
        logger.error(f"  Model: {model}")
        logger.error(
            f"  Status code: {getattr(resp, 'status_code', 'N/A') if resp else 'N/A'}"
        )
        if resp:
            try:
                logger.error(f"  Response body: {resp.text[:500]}")
            except Exception:
                pass

        # Return a clean fallback message
        return (
            "### Summary\n"
            f"- I couldn't reach the LLM endpoint: `{type(e).__name__}`.\n\n"
            "### Risk & regressions\n"
            "- Review unavailable due to LLM call failure.\n\n"
            "### Per-file notes\n"
            "- Try again after fixing LLM configuration.\n"
        )


async def _merge_partial_reviews(
    system_prompt: str, user_prompt: str, partials: List[str]
) -> str:
    if not partials:
        return "### Summary\n- No diff content to review."

    # If there is only one, use it.
    if len(partials) == 1:
        result = partials[0]
        # Ensure it's a clean string
        if not isinstance(result, str):
            return "### Summary\n- Diff review content was malformed."
        return result.strip()

    api_key, base_url, model = _get_openai_config()
    if not api_key:
        # No LLM: just concatenate
        return "\n\n---\n\n".join(partials)

    client = await get_http_client()
    url = f"{base_url}/chat/completions"

    merged_prompt = (
        "Merge these partial code reviews into ONE coherent review.\n"
        "De-duplicate repeated points, keep the required Markdown structure, and ensure per-file notes are grouped.\n"
        "If partials disagree, explain the uncertainty.\n\n"
        + "\n\n---\n\n".join(partials)
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{user_prompt}\n\n{merged_prompt}"},
    ]

    resp = None
    try:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.2,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        content = (data.get("choices", [{}])[0].get("message", {}) or {}).get(
            "content", ""
        )

        # Ensure we always return a clean string
        if not content or not isinstance(content, str):
            logger.warning(
                f"LLM merge returned unexpected content type: {type(content)}"
            )
            return "\n\n---\n\n".join(partials)

        return content.strip()
    except Exception as e:
        logger.error(f"LLM merge call failed: {e}")
        logger.debug(f"  Using fallback: concatenating {len(partials)} partial reviews")
        return "\n\n---\n\n".join(partials)


# ------------------------------------------------------------------------------
# Intent analysis + context building (kept)
# ------------------------------------------------------------------------------
async def _analyze_user_intent(message: str) -> Dict[str, Any]:
    """Analyze user intent using LLM for better classification"""
    message_lower = message.lower()

    # Try LLM-based intent classification first
    llm_service = get_llm_service()
    if llm_service:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=llm_service.settings.openai_api_key)

            intent_prompt = f"""Classify the user's intent into ONE of these categories:
- task_query: Questions about JIRA tasks, tickets, assignments
- team_query: Questions about team members, their work, collaboration
- plan_request: Requests for implementation plans, steps, approach
- code_help: Requests for code help, debugging, code review
- general_query: General questions or conversation

User message: "{message}"

Respond with ONLY the category name (e.g., "code_help"). No explanation."""

            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",  # Use faster model for classification
                messages=[{"role": "user", "content": intent_prompt}],
                temperature=0.1,
                max_tokens=20,
            )

            intent_type = response.choices[0].message.content.strip().lower()

            # Validate the response
            valid_intents = [
                "task_query",
                "team_query",
                "plan_request",
                "code_help",
                "general_query",
            ]
            if intent_type in valid_intents:
                return {
                    "type": intent_type,
                    "query": message,
                    "confidence": 0.95,
                    "method": "llm",
                }
        except Exception as e:
            logger.warning(
                f"LLM intent classification failed, falling back to keywords: {e}"
            )

    # Fallback to keyword-based classification
    if any(
        keyword in message_lower
        for keyword in ["task", "jira", "ticket", "assigned", "priority"]
    ):
        return {
            "type": "task_query",
            "query": message,
            "keywords": ["task", "jira", "priority"],
            "confidence": 0.9,
            "method": "keyword",
        }

    if any(
        keyword in message_lower
        for keyword in ["team", "colleague", "teammate", "working on", "activity"]
    ):
        return {
            "type": "team_query",
            "query": message,
            "keywords": ["team", "activity", "collaboration"],
            "confidence": 0.8,
            "method": "keyword",
        }

    if any(
        keyword in message_lower
        for keyword in ["plan", "how", "implement", "steps", "approach"]
    ):
        return {
            "type": "plan_request",
            "query": message,
            "keywords": ["plan", "implementation", "steps"],
            "confidence": 0.85,
            "method": "keyword",
        }

    if any(
        keyword in message_lower
        for keyword in ["code", "bug", "error", "fix", "debug", "review"]
    ):
        return {
            "type": "code_help",
            "query": message,
            "keywords": ["code", "debug", "review"],
            "confidence": 0.8,
            "method": "keyword",
        }

    return {
        "type": "general_query",
        "query": message,
        "keywords": [],
        "confidence": 0.5,
        "method": "keyword",
    }


async def _build_enhanced_context(
    request: ChatRequest, intent: Dict[str, Any]
) -> Dict[str, Any]:
    enhanced_context: Dict[str, Any] = {
        "intent": intent,
        "conversation_history": request.conversationHistory[-5:],
        "current_task": request.currentTask,
        "team_context": request.teamContext or {},
    }

    if request.currentTask:
        try:
            api_base = get_api_base_url()
            client = await get_http_client()
            response = await client.get(
                f"{api_base}/api/context/task/{request.currentTask}"
            )
            if response.status_code == 200:
                enhanced_context["task_context"] = response.json()
        except Exception as e:
            logger.warning(f"Could not fetch task context: {e}")

    return enhanced_context


# ------------------------------------------------------------------------------
# Existing handlers (kept as-is, lightly touched only if needed)
# ------------------------------------------------------------------------------
async def _handle_task_query(
    intent: Dict[str, Any], context: Dict[str, Any]
) -> ChatResponse:
    try:
        tasks = []
        try:
            from backend.services.navi_memory_service import list_jira_tasks_for_user
            from backend.core.db import get_engine
            from sqlalchemy.orm import sessionmaker

            user_id = os.environ.get("DEV_USER_ID", "default_user")
            engine = get_engine()
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

            with SessionLocal() as db:
                memory_rows = list_jira_tasks_for_user(db, user_id, limit=20)
                for row in memory_rows:
                    tags = row.get("tags", {})
                    tasks.append(
                        {
                            "jira_key": tags.get("key", row.get("scope", "")),
                            "title": row.get("title", ""),
                            "status": tags.get("status", "Unknown"),
                            "scope": row.get("scope", ""),
                            "updated_at": row.get("updated_at", ""),
                        }
                    )
        except Exception as e:
            logger.error(f"Error fetching tasks from NAVI memory: {e}")
            tasks = []

        if not tasks:
            return ChatResponse(
                content="You don't have any assigned tasks right now. Would you like me to help you find work to do?",
                suggestions=[
                    "Show available tasks",
                    "Check team priorities",
                    "Find tasks I can help with",
                ],
            )

        content = f"You have {len(tasks)} assigned tasks.\n\n�� **Your JIRA Tasks:**\n"
        for task in tasks[:5]:
            status = task.get("status")
            status_emoji = (
                "🔄"
                if status == "In Progress"
                else "📝"
                if status == "To Do"
                else "✅"
                if status == "Done"
                else "📌"
            )
            jira_key = task.get("jira_key", "")
            title = task.get("title", "").replace(f"[Jira] {jira_key}: ", "")
            content += (
                f"{status_emoji} **{jira_key}**: {title} ({status or 'Unknown'})\n"
            )

        suggestions = [
            (
                f"Work on {tasks[0].get('jira_key', 'first task')}"
                if tasks
                else "Find new tasks"
            ),
            "Generate plan for highest priority task",
            "Show task dependencies",
            "Check what teammates are working on",
        ]

        return ChatResponse(content=content, suggestions=suggestions)
    except Exception:
        return ChatResponse(
            content="I had trouble fetching your tasks. Let me try a different approach.",
            suggestions=[
                "Refresh task list",
                "Check JIRA connection",
                "Show cached tasks",
            ],
        )


async def _handle_team_query(
    intent: Dict[str, Any], context: Dict[str, Any]
) -> ChatResponse:
    try:
        team_activity = []
        try:
            api_base = get_api_base_url()
            client = await get_http_client()
            response = await client.get(f"{api_base}/api/activity/recent")
            if response.status_code == 200:
                data = response.json()
                team_activity = data.get("items", [])
        except Exception as e:
            logger.warning(f"Failed to fetch team activity: {e}")

        if not team_activity:
            return ChatResponse(
                content="I don't have recent team activity data. Let me help you connect with your team.",
                suggestions=[
                    "Check Slack for updates",
                    "Review recent commits",
                    "Show team calendar",
                ],
            )

        content = "🔄 **Recent Team Activity:**\n\n"
        for activity in team_activity[:5]:
            time_ago = _format_time_ago(activity.get("timestamp"))
            content += f"• **{activity.get('author')}** {activity.get('action')} on **{activity.get('target')}** ({time_ago})\n"

        if context.get("current_task"):
            content += "\n💡 **Tip:** I can help you coordinate with teammates working on related tasks."

        suggestions = [
            "Show detailed team status",
            "Find teammates working on related tasks",
            "Check for coordination opportunities",
            "View team dependencies",
        ]
        return ChatResponse(content=content, suggestions=suggestions)
    except Exception:
        return ChatResponse(
            content="I had trouble getting team information. Let me help you in other ways.",
            suggestions=[
                "Check team chat",
                "Review recent changes",
                "Show project status",
            ],
        )


async def _handle_plan_request(
    intent: Dict[str, Any], context: Dict[str, Any]
) -> ChatResponse:
    try:
        current_task = context.get("current_task") or context.get(
            "task_context", {}
        ).get("key")
        if not current_task:
            return ChatResponse(
                content="I'd love to help you create a plan! Which task would you like me to plan for?",
                suggestions=[
                    "Plan for my highest priority task",
                    "Create a general work plan",
                    "Help me break down a complex task",
                ],
            )

        task_context = context.get("task_context", {})
        content = f"I'll create a detailed plan for **{current_task}**.\n\n"
        content += (
            f"**Task**: {task_context.get('summary', 'Task details loading...')}\n\n"
        )
        if task_context.get("description"):
            content += f"**Description**: {task_context['description'][:200]}...\n\n"
        content += (
            "Let me analyze the requirements and generate an implementation plan."
        )

        return ChatResponse(
            content=content,
            suggestions=[
                "Generate detailed implementation plan",
                "Show task dependencies first",
                "Break into smaller subtasks",
                "Include testing strategy",
            ],
            context={"taskKey": current_task, "action": "plan_generation"},
        )
    except Exception:
        return ChatResponse(
            content="I had trouble analyzing the task for planning. Let me help you get started anyway.",
            suggestions=[
                "Tell me about the task manually",
                "Show existing plans",
                "Create simple task breakdown",
            ],
        )


async def _handle_code_help(
    intent: Dict[str, Any], context: Dict[str, Any]
) -> ChatResponse:
    """Handle code help requests with actual LLM call"""
    llm_service = get_llm_service()

    if llm_service:
        try:
            # Call LLM with engineering context
            question = intent.get("query", "Help me with coding")
            response = await llm_service.generate_engineering_response(
                question, context
            )

            return ChatResponse(
                content=response.answer,
                suggestions=response.suggested_actions,
                context={
                    "confidence": response.confidence,
                    "reasoning": response.reasoning,
                },
            )
        except Exception as e:
            logger.error(f"Error in code help LLM call: {e}")
            # Fall through to default response

    # Fallback if LLM unavailable
    content = (
        "I'm here to help with your code!\n\n"
        "I can assist with:\n"
        "• **Code review** - Analyze your changes and suggest improvements\n"
        "• **Debugging** - Help identify and fix issues\n"
        "• **Implementation** - Guide you through coding tasks\n"
        "• **Testing** - Create tests and validate your code\n\n"
        "⚠️ Note: LLM service is currently unavailable. Please configure OPENAI_API_KEY."
    )

    suggestions = [
        "Review my current changes",
        "Help debug an issue",
        "Generate tests for my code",
    ]

    return ChatResponse(content=content, suggestions=suggestions)


async def _handle_general_query(
    intent: Dict[str, Any], context: Dict[str, Any]
) -> ChatResponse:
    """Handle general queries with actual LLM call"""
    llm_service = get_llm_service()

    if llm_service:
        try:
            # Call LLM with full context
            question = intent.get("query", "Tell me about what you can do")
            response = await llm_service.generate_engineering_response(
                question, context
            )

            return ChatResponse(
                content=response.answer,
                suggestions=response.suggested_actions,
                context={
                    "confidence": response.confidence,
                    "reasoning": response.reasoning,
                },
            )
        except Exception as e:
            logger.error(f"Error in general query LLM call: {e}")
            # Fall through to default response

    # Fallback if LLM unavailable
    content = (
        "I'm your autonomous engineering assistant!\n\n"
        "I can help you with:\n"
        "• **Task Management** - Show your JIRA tasks and priorities\n"
        "• **Team Coordination** - Keep you updated on team activity\n"
        "• **Implementation Planning** - Generate detailed plans for your work\n"
        "• **Code Assistance** - Review, debug, and improve your code\n"
        "• **Context Intelligence** - Connect related work across your team\n\n"
        "⚠️ Note: LLM service is currently unavailable. Please configure OPENAI_API_KEY."
    )

    suggestions: List[str] = [
        "Show my tasks",
        "Help me with current work",
        "Review recent changes",
    ]

    return ChatResponse(content=content, suggestions=suggestions)


# ------------------------------------------------------------------------------
# Timestamp formatting (kept)
# ------------------------------------------------------------------------------
def _format_time_ago(timestamp: Any) -> str:
    if not timestamp:
        return "unknown time"

    try:
        now = datetime.now(timezone.utc)

        if isinstance(timestamp, str):
            try:
                ts_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                try:
                    ts_dt = datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
                except (ValueError, TypeError):
                    return "unknown time"
        elif isinstance(timestamp, datetime):
            ts_dt = timestamp
            if ts_dt.tzinfo is None:
                ts_dt = ts_dt.replace(tzinfo=timezone.utc)
        else:
            return "unknown time"

        diff = now - ts_dt
        seconds = int(diff.total_seconds())

        if seconds < 0:
            return "in the future"
        if seconds < SECONDS_PER_MINUTE:
            return f"{seconds} second{'s' if seconds != 1 else ''} ago"
        if seconds < SECONDS_PER_HOUR:
            minutes = seconds // SECONDS_PER_MINUTE
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        if seconds < SECONDS_PER_DAY:
            hours = seconds // SECONDS_PER_HOUR
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        if seconds < SECONDS_PER_WEEK:
            days = seconds // SECONDS_PER_DAY
            return f"{days} day{'s' if days != 1 else ''} ago"
        if seconds < SECONDS_PER_MONTH:
            weeks = seconds // SECONDS_PER_WEEK
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        if seconds < SECONDS_PER_YEAR:
            months = seconds // SECONDS_PER_MONTH
            return f"{months} month{'s' if months != 1 else ''} ago"
        years = seconds // SECONDS_PER_YEAR
        return f"{years} year{'s' if years != 1 else ''} ago"
    except Exception as e:
        logger.warning(f"Error formatting timestamp {timestamp}: {e}")
        return "recently"
