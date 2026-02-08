"""
Enhanced Chat API for conversational interface
Provides context-aware responses with team intelligence + Navi diff review
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional, Tuple, TypedDict
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
from backend.core.response_cache import (
    get_cached_response,
    set_cached_response,
    generate_cache_key,
)
from backend.autonomous.enhanced_coding_engine import (
    TaskType as AutonomousTaskType,
)
from backend.services.streaming_utils import (
    StreamingSession,
    stream_text_with_typing,
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
    model: Optional[str] = (
        None  # requested model id (e.g., openai/gpt-4o or auto/recommended)
    )
    mode: Optional[str] = None  # chat mode (agent | plan | ask | edit)
    execution: Optional[str] = None  # UI execution mode label (agent/auto)
    scope: Optional[str] = None  # scope for routing (this_repo/current_file)
    provider: Optional[str] = None  # requested provider id
    workspace_root: Optional[str] = None  # Workspace root for reading new file contents
    state: Optional[Dict[str, Any]] = (
        None  # State from previous response for autonomous coding continuity
    )

    # 🚀 LLM-FIRST: Full VS Code context fields
    current_file: Optional[str] = (
        None  # Currently open file path (relative to workspace)
    )
    current_file_content: Optional[str] = None  # Content of the current file
    selection: Optional[str] = None  # Selected text in the editor
    errors: Optional[List[Dict[str, Any]]] = (
        None  # List of errors from VS Code diagnostics
    )

    # AUTO-RECOVERY: Last action error for NAVI to debug and continue
    last_action_error: Optional[Dict[str, Any]] = None


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

    # Intelligence fields (like Codex/Claude Code)
    thinking_steps: Optional[List[str]] = None  # Show what NAVI did
    files_read: Optional[List[str]] = None  # Show what files were analyzed
    project_type: Optional[str] = None  # Detected project type
    framework: Optional[str] = None  # Detected framework
    warnings: Optional[List[str]] = None  # Safety warnings
    next_steps: Optional[List[str]] = None  # Suggested follow-up actions


class ProactiveSuggestionsRequest(BaseModel):
    context: Dict[str, Any]


# ------------------------------------------------------------------------------
# LLM routing helpers (server-side metadata for UI badges)
# ------------------------------------------------------------------------------

AUTO_MODEL_IDS = {
    "auto",
    "auto/recommended",
    "auto_recommended",
    "auto-recommended",
    "",
}

TASK_PATTERNS: Dict[str, Dict[str, List[Any]]] = {
    "code_generation": {
        "patterns": [
            re.compile(r"write\s+(a\s+)?code", re.I),
            re.compile(r"create\s+(a\s+)?function", re.I),
            re.compile(r"implement", re.I),
            re.compile(r"build\s+(a\s+)?", re.I),
        ],
        "keywords": [
            "write",
            "create",
            "generate",
            "implement",
            "build",
            "scaffold",
            "new function",
            "new component",
        ],
    },
    "code_refactoring": {
        "patterns": [
            re.compile(r"refactor", re.I),
            re.compile(r"improve\s+(the\s+)?code", re.I),
            re.compile(r"optimize", re.I),
            re.compile(r"clean\s+up", re.I),
        ],
        "keywords": [
            "refactor",
            "optimize",
            "improve",
            "clean up",
            "restructure",
            "reorganize",
            "simplify",
        ],
    },
    "code_review": {
        "patterns": [
            re.compile(r"review\s+(this\s+)?code", re.I),
            re.compile(r"check\s+(this\s+)?code", re.I),
            re.compile(r"what('s|\s+is)\s+wrong", re.I),
        ],
        "keywords": ["review", "check", "analyze", "audit", "inspect", "evaluate"],
    },
    "bug_fix": {
        "patterns": [
            re.compile(r"fix\s+(this\s+)?bug", re.I),
            re.compile(r"debug", re.I),
            re.compile(r"error", re.I),
            re.compile(r"not\s+working", re.I),
            re.compile(r"broken", re.I),
        ],
        "keywords": [
            "fix",
            "bug",
            "error",
            "debug",
            "broken",
            "issue",
            "problem",
            "crash",
            "fail",
        ],
    },
    "test_generation": {
        "patterns": [
            re.compile(r"write\s+(unit\s+)?tests?", re.I),
            re.compile(r"create\s+tests?", re.I),
            re.compile(r"test\s+coverage", re.I),
        ],
        "keywords": [
            "test",
            "unit test",
            "integration test",
            "coverage",
            "testing",
            "spec",
            "jest",
            "vitest",
        ],
    },
    "documentation": {
        "patterns": [
            re.compile(r"document", re.I),
            re.compile(r"write\s+(a\s+)?readme", re.I),
            re.compile(r"add\s+comments", re.I),
            re.compile(r"jsdoc", re.I),
        ],
        "keywords": [
            "document",
            "readme",
            "documentation",
            "comments",
            "jsdoc",
            "explain code",
        ],
    },
    "summarization": {
        "patterns": [
            re.compile(r"summarize", re.I),
            re.compile(r"summary", re.I),
            re.compile(r"tldr", re.I),
            re.compile(r"key\s+points", re.I),
        ],
        "keywords": [
            "summarize",
            "summary",
            "tldr",
            "key points",
            "overview",
            "brief",
            "highlights",
        ],
    },
    "conversation": {
        "patterns": [
            re.compile(r"how\s+are\s+you", re.I),
            re.compile(r"hello", re.I),
            re.compile(r"hi\s+navi", re.I),
            re.compile(r"good\s+morning", re.I),
        ],
        "keywords": [
            "hello",
            "hi",
            "how are you",
            "good morning",
            "good afternoon",
            "thanks",
            "thank you",
        ],
    },
    "rag_reasoning": {
        "patterns": [
            re.compile(r"what\s+was\s+discussed", re.I),
            re.compile(r"find\s+(information|docs)", re.I),
            re.compile(r"search\s+(for|in)", re.I),
        ],
        "keywords": [
            "find",
            "search",
            "what was",
            "where is",
            "who said",
            "meeting notes",
            "discussed",
            "decided",
        ],
    },
    "ui_generation": {
        "patterns": [
            re.compile(r"create\s+(a\s+)?ui", re.I),
            re.compile(r"design\s+(a\s+)?component", re.I),
            re.compile(r"build\s+(a\s+)?page", re.I),
            re.compile(r"style", re.I),
        ],
        "keywords": [
            "ui",
            "component",
            "page",
            "design",
            "layout",
            "style",
            "css",
            "tailwind",
            "button",
            "form",
        ],
    },
    "planning": {
        "patterns": [
            re.compile(r"plan\s+(the\s+)?", re.I),
            re.compile(r"how\s+should\s+(i|we)", re.I),
            re.compile(r"steps\s+to", re.I),
            re.compile(r"approach", re.I),
        ],
        "keywords": [
            "plan",
            "approach",
            "steps",
            "strategy",
            "how should",
            "best way",
            "architecture",
        ],
    },
    "explanation": {
        "patterns": [
            re.compile(r"explain", re.I),
            re.compile(r"what\s+is", re.I),
            re.compile(r"how\s+does", re.I),
            re.compile(r"why\s+", re.I),
            re.compile(r"tell\s+me\s+about", re.I),
        ],
        "keywords": [
            "explain",
            "what is",
            "how does",
            "why",
            "tell me",
            "describe",
            "understand",
        ],
    },
}

# Provider-specific model recommendations
# Used based on DEFAULT_LLM_PROVIDER environment variable
MODEL_RECOMMENDATIONS_BY_PROVIDER: Dict[str, Dict[str, Dict[str, str]]] = {
    "openai": {
        "code_generation": {
            "model_id": "openai/gpt-5",
            "model_name": "GPT-5",
            "reason": "Best for generating clean, well-structured code",
        },
        "code_refactoring": {
            "model_id": "openai/gpt-5",
            "model_name": "GPT-5",
            "reason": "Excellent at understanding and restructuring large codebases",
        },
        "code_review": {
            "model_id": "openai/gpt-5",
            "model_name": "GPT-5",
            "reason": "Strong analytical capabilities for code review",
        },
        "bug_fix": {
            "model_id": "openai/gpt-5",
            "model_name": "GPT-5",
            "reason": "Superior debugging and error analysis",
        },
        "test_generation": {
            "model_id": "openai/gpt-5-mini",
            "model_name": "GPT-5 Mini",
            "reason": "Fast and efficient for test generation",
        },
        "documentation": {
            "model_id": "openai/gpt-5-mini",
            "model_name": "GPT-5 Mini",
            "reason": "Great for clear, concise documentation",
        },
        "summarization": {
            "model_id": "openai/gpt-5-mini",
            "model_name": "GPT-5 Mini",
            "reason": "Fast summarization with good accuracy",
        },
        "conversation": {
            "model_id": "openai/gpt-5",
            "model_name": "GPT-5",
            "reason": "Natural, engaging conversational responses",
        },
        "rag_reasoning": {
            "model_id": "openai/gpt-5",
            "model_name": "GPT-5",
            "reason": "Excellent at multi-source reasoning and RAG",
        },
        "ui_generation": {
            "model_id": "openai/gpt-5",
            "model_name": "GPT-5",
            "reason": "Strong UI/UX generation capabilities",
        },
        "planning": {
            "model_id": "openai/gpt-5",
            "model_name": "GPT-5",
            "reason": "Great for strategic planning and architecture",
        },
        "explanation": {
            "model_id": "openai/gpt-5",
            "model_name": "GPT-5",
            "reason": "Clear, detailed explanations",
        },
    },
    "anthropic": {
        "code_generation": {
            "model_id": "anthropic/claude-sonnet-4",
            "model_name": "Claude Sonnet 4",
            "reason": "Excellent code generation with strong reasoning",
        },
        "code_refactoring": {
            "model_id": "anthropic/claude-sonnet-4",
            "model_name": "Claude Sonnet 4",
            "reason": "Great at understanding and restructuring codebases",
        },
        "code_review": {
            "model_id": "anthropic/claude-sonnet-4",
            "model_name": "Claude Sonnet 4",
            "reason": "Strong analytical capabilities for code review",
        },
        "bug_fix": {
            "model_id": "anthropic/claude-sonnet-4",
            "model_name": "Claude Sonnet 4",
            "reason": "Superior debugging and error analysis",
        },
        "test_generation": {
            "model_id": "anthropic/claude-sonnet-4",
            "model_name": "Claude Sonnet 4",
            "reason": "Fast and efficient for test generation",
        },
        "documentation": {
            "model_id": "anthropic/claude-sonnet-4",
            "model_name": "Claude Sonnet 4",
            "reason": "Great for clear, concise documentation",
        },
        "summarization": {
            "model_id": "anthropic/claude-sonnet-4",
            "model_name": "Claude Sonnet 4",
            "reason": "Fast summarization with good accuracy",
        },
        "conversation": {
            "model_id": "anthropic/claude-sonnet-4",
            "model_name": "Claude Sonnet 4",
            "reason": "Natural, engaging conversational responses",
        },
        "rag_reasoning": {
            "model_id": "anthropic/claude-sonnet-4",
            "model_name": "Claude Sonnet 4",
            "reason": "Excellent at multi-source reasoning and RAG",
        },
        "ui_generation": {
            "model_id": "anthropic/claude-sonnet-4",
            "model_name": "Claude Sonnet 4",
            "reason": "Strong UI/UX generation capabilities",
        },
        "planning": {
            "model_id": "anthropic/claude-sonnet-4",
            "model_name": "Claude Sonnet 4",
            "reason": "Great for strategic planning and architecture",
        },
        "explanation": {
            "model_id": "anthropic/claude-sonnet-4",
            "model_name": "Claude Sonnet 4",
            "reason": "Clear, detailed explanations",
        },
    },
}

# Default to OpenAI recommendations for backward compatibility
MODEL_RECOMMENDATIONS: Dict[str, Dict[str, str]] = MODEL_RECOMMENDATIONS_BY_PROVIDER[
    "openai"
]


def _get_model_recommendations() -> Dict[str, Dict[str, str]]:
    """Get model recommendations based on DEFAULT_LLM_PROVIDER environment variable"""
    default_provider = os.environ.get("DEFAULT_LLM_PROVIDER", "openai").lower()
    return MODEL_RECOMMENDATIONS_BY_PROVIDER.get(
        default_provider, MODEL_RECOMMENDATIONS_BY_PROVIDER["openai"]
    )


MODEL_ALIASES: Dict[str, Dict[str, str]] = {
    # OpenAI models - map fake/future model IDs to real valid models
    "openai/gpt-5": {"provider": "openai", "model": "gpt-4o", "label": "GPT-4o (Best)"},
    "openai/gpt-5-mini": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "label": "GPT-4o Mini",
    },
    "openai/gpt-5-nano": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "label": "GPT-4o Mini",
    },
    "openai/gpt-4.1": {"provider": "openai", "model": "gpt-4o", "label": "GPT-4o"},
    "openai/gpt-4o": {"provider": "openai", "model": "gpt-4o", "label": "GPT-4o"},
    "openai/gpt-4o-mini": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "label": "GPT-4o Mini",
    },
    "openai/gpt-4-turbo": {
        "provider": "openai",
        "model": "gpt-4-turbo",
        "label": "GPT-4 Turbo",
    },
    # Anthropic models
    "anthropic/claude-sonnet-4": {
        "provider": "anthropic",
        "model": "claude-3-5-sonnet-20241022",
        "label": "Claude Sonnet 4",
    },
    "anthropic/claude-opus-4": {
        "provider": "anthropic",
        "model": "claude-opus-4-20250514",
        "label": "Claude Opus 4",
    },
    "anthropic/claude-3.5-sonnet": {
        "provider": "anthropic",
        "model": "claude-3-5-sonnet-20241022",
        "label": "Claude 3.5 Sonnet",
    },
    "anthropic/claude-3-opus": {
        "provider": "anthropic",
        "model": "claude-3-opus-20240229",
        "label": "Claude 3 Opus",
    },
    # Google models
    "google/gemini-2.5-pro": {
        "provider": "google",
        "model": "gemini-2.0-flash-exp",
        "label": "Gemini 2.0 Flash",
    },
    "google/gemini-2.5-flash": {
        "provider": "google",
        "model": "gemini-2.0-flash-exp",
        "label": "Gemini 2.0 Flash",
    },
    "google/gemini-2.5-flash-lite": {
        "provider": "google",
        "model": "gemini-1.5-flash",
        "label": "Gemini 1.5 Flash",
    },
    "google/gemini-3-pro-preview": {
        "provider": "google",
        "model": "gemini-1.5-pro",
        "label": "Gemini 1.5 Pro",
    },
}


def _humanize_model_name(model_id: str) -> str:
    if not model_id:
        return "Unknown"
    base = model_id.split("/")[-1]
    return base.replace("_", " ").replace("-", " ").title()


def _detect_task_type(message: str) -> str:
    if not message:
        return "conversation"
    lower = message.lower()
    scores: Dict[str, int] = {}

    for task_type, pattern in TASK_PATTERNS.items():
        score = 0
        for regex in pattern["patterns"]:
            if regex.search(message):
                score += 3
        for keyword in pattern["keywords"]:
            if keyword.lower() in lower:
                score += 1
        scores[task_type] = score

    detected = "conversation"
    max_score = 0
    for task_type, score in scores.items():
        if score > max_score:
            max_score = score
            detected = task_type

    if max_score < 2:
        return "conversation"
    return detected


def _resolve_llm_selection(
    message: str,
    requested_model: Optional[str],
    requested_mode: Optional[str],
    requested_provider: Optional[str],
) -> Dict[str, Any]:
    raw_model = (requested_model or "").strip()
    mode = (requested_mode or "").strip() or "agent"

    # Get default provider from environment
    default_provider = os.environ.get("DEFAULT_LLM_PROVIDER", "openai").lower()

    if raw_model.lower() in AUTO_MODEL_IDS:
        task_type = _detect_task_type(message)
        # Use provider-specific recommendations based on DEFAULT_LLM_PROVIDER
        recommendations = _get_model_recommendations()
        rec = recommendations.get(task_type, recommendations["conversation"])
        requested_model_id = raw_model or "auto/recommended"
        recommended_model_id = rec["model_id"]
        alias = MODEL_ALIASES.get(recommended_model_id, {})
        provider = alias.get("provider") or recommended_model_id.split("/")[0]
        resolved_model = alias.get("model") or recommended_model_id.split("/", 1)[-1]
        resolved_model_id = f"{provider}/{resolved_model}"
        resolved_model_name = alias.get("label") or _humanize_model_name(
            recommended_model_id
        )
        logger.info(
            f"Auto model selection: provider={provider}, model={resolved_model} (DEFAULT_LLM_PROVIDER={default_provider})"
        )
        return {
            "source": "auto",
            "task_type": task_type,
            "reason": rec.get("reason"),
            "requested_model": requested_model_id,
            "requested_model_name": "Auto (Recommended)",
            "resolved_model": resolved_model,
            "resolved_model_id": resolved_model_id,
            "resolved_model_name": resolved_model_name,
            "provider": provider,
            "mode": mode,
        }

    alias = MODEL_ALIASES.get(raw_model, {})
    provider = alias.get("provider")
    resolved_model = alias.get("model")
    resolved_model_name = alias.get("label")

    if not provider:
        if "/" in raw_model:
            provider, resolved_model = raw_model.split("/", 1)
        else:
            # Use DEFAULT_LLM_PROVIDER as fallback instead of hardcoded "openai"
            provider = requested_provider or default_provider
            resolved_model = raw_model

    resolved_model_id = (
        f"{provider}/{resolved_model}" if provider and resolved_model else raw_model
    )
    resolved_model_name = resolved_model_name or _humanize_model_name(resolved_model_id)
    requested_model_name = alias.get("label") or _humanize_model_name(raw_model)

    return {
        "source": "manual",
        "task_type": "manual",
        "reason": "Manual model selection",
        "requested_model": raw_model,
        "requested_model_name": requested_model_name,
        "resolved_model": resolved_model,
        "resolved_model_id": resolved_model_id,
        "resolved_model_name": resolved_model_name,
        "provider": provider or requested_provider or default_provider,
        "mode": mode,
    }


def _attach_llm_context(
    response: ChatResponse, llm_context: Dict[str, Any]
) -> ChatResponse:
    if response.context is None:
        response.context = {}
    response.context["llm"] = llm_context
    return response


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

        token_kwargs = _openai_token_kwargs(llm_service.model, 1500)
        stream = await client.chat.completions.create(
            model=llm_service.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            stream=True,
            **token_kwargs,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                yield f"data: {json.dumps({'content': content})}\n\n"

        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Streaming error: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


class _OpenAITokenKwargs(TypedDict, total=False):
    max_tokens: int
    max_completion_tokens: int


def _openai_token_kwargs(model: str, max_tokens: int) -> _OpenAITokenKwargs:
    normalized = (model or "").lower()
    if any(
        token in normalized
        for token in ("gpt-5", "gpt-4.2", "gpt-4.1", "gpt-4o", "o1", "o3", "o4")
    ):
        return {"max_completion_tokens": max_tokens}
    return {"max_tokens": max_tokens}


def _normalize_conversation_history(
    history: Optional[List[ChatMessage]],
) -> Optional[List[Dict[str, Any]]]:
    if not history:
        return None

    normalized: List[Dict[str, Any]] = []
    for msg in history:
        if isinstance(msg, dict):
            role = msg.get("type") or msg.get("role", "user")
            content = msg.get("content", "")
        else:
            role = getattr(msg, "type", getattr(msg, "role", "user"))
            content = getattr(msg, "content", "")

        if content:
            normalized.append({"role": role, "content": content})

    return normalized or None


# ------------------------------------------------------------------------------
# Navi entrypoints: /api/navi/chat and /api/navi/chat/stream
# ------------------------------------------------------------------------------
@navi_router.post("/chat/stream")
async def navi_chat_stream(request: NaviChatRequest, db: Session = Depends(get_db)):
    """Streaming version of navi_chat with SSE - routes based on mode (chat/agent/agent-full-access)"""
    try:
        # Resolve LLM selection and mode first
        llm_context = _resolve_llm_selection(
            request.message,
            request.model,
            request.mode,
            request.provider,
        )
        # Safe mode extraction with type checking
        mode_value = llm_context.get("mode", "agent")
        mode = str(mode_value).lower() if mode_value is not None else "agent"
        llm_provider = llm_context.get("provider") or os.environ.get(
            "DEFAULT_LLM_PROVIDER", "openai"
        )
        llm_model = llm_context.get("resolved_model") or None

        logger.info(
            f"[NAVI Stream] Mode: {mode}, Provider: {llm_provider}, Model: {llm_model}"
        )

        # =====================================================================
        # MODE ROUTING: Chat vs Agent vs Agent Full Access
        # =====================================================================

        # CHAT MODE: Simple conversational LLM (no file reading/editing)
        if mode == "chat":
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

            async def chat_mode_stream():
                """Simple chat streaming with router info"""
                # Emit router info first
                yield f"data: {json.dumps({'router_info': {'provider': llm_provider, 'model': llm_model or 'auto', 'mode': 'chat', 'task_type': llm_context.get('task_type', 'conversation')}})}\n\n"

                # Stream LLM response using existing helper
                async for chunk in stream_llm_response(request.message, context):
                    yield chunk

            return StreamingResponse(
                chat_mode_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        # AGENT MODE or AGENT FULL ACCESS: Use NAVI brain for intelligent code analysis
        # Requires workspace_root for file operations
        if not request.workspace_root:
            # No workspace - fall back to chat mode behavior
            logger.warning(
                "[NAVI Stream] Agent mode requested but no workspace_root, falling back to chat"
            )
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

        # =====================================================================
        # UNIFIED AGENT: Route action-oriented requests to the agentic engine
        # =====================================================================
        # Check if this is an action request that should use native tool-use
        if _should_use_unified_agent(request.message):
            logger.info(
                f"[NAVI Stream] 🚀 Routing to Unified Agent for action request: {request.message[:50]}..."
            )
            from backend.services.unified_agent import UnifiedAgent, AgentEventType

            provider = (
                request.provider
                or llm_provider
                or os.environ.get("DEFAULT_LLM_PROVIDER", "anthropic")
            )
            model = request.model or llm_model

            # Build project context from request
            project_context = None
            if getattr(request, "current_file", None) or getattr(
                request, "errors", None
            ):
                project_context = {
                    "current_file": getattr(request, "current_file", None),
                    "errors": getattr(request, "errors", None),
                }

            async def unified_agent_stream():
                """Stream unified agent events as SSE for action requests."""
                try:
                    agent = UnifiedAgent(
                        provider=provider,
                        model=model,
                    )

                    # Emit start event with router info
                    yield f"data: {json.dumps({'router_info': {'provider': provider, 'model': model or 'auto', 'mode': 'unified_agent', 'task_type': 'action'}})}\n\n"
                    yield f"data: {json.dumps({'activity': {'kind': 'agent_start', 'label': 'Agent', 'detail': 'Starting unified agent with native tool-use...', 'status': 'running'}})}\n\n"

                    # Normalize conversation history
                    conversation_history = _normalize_conversation_history(
                        request.conversationHistory
                    )

                    async for event in agent.run(
                        message=request.message,
                        workspace_path=request.workspace_root or ".",
                        conversation_history=conversation_history,
                        project_context=project_context,
                    ):
                        # Convert agent events to SSE format
                        if event.type == AgentEventType.THINKING:
                            yield f"data: {json.dumps({'activity': {'kind': 'thinking', 'label': 'Thinking', 'detail': event.data.get('message', ''), 'status': 'running'}})}\n\n"

                        elif event.type == AgentEventType.TEXT:
                            yield f"data: {json.dumps({'content': event.data})}\n\n"

                        elif event.type == AgentEventType.TOOL_CALL:
                            tool_name = event.data.get("name", "unknown")
                            tool_args = event.data.get("arguments", {})

                            kind = "command"
                            label = tool_name
                            detail = ""

                            if tool_name == "read_file":
                                kind = "read"
                                label = "Reading"
                                detail = tool_args.get("path", "")
                            elif tool_name == "write_file":
                                kind = "create"
                                label = "Creating"
                                detail = tool_args.get("path", "")
                            elif tool_name == "edit_file":
                                kind = "edit"
                                label = "Editing"
                                detail = tool_args.get("path", "")
                            elif tool_name == "run_command":
                                kind = "command"
                                label = "Running"
                                detail = tool_args.get("command", "")
                            elif tool_name == "search_files":
                                kind = "search"
                                label = "Searching"
                                detail = tool_args.get("pattern", "")
                            elif tool_name == "list_directory":
                                kind = "read"
                                label = "Listing"
                                detail = tool_args.get("path", "")

                            yield f"data: {json.dumps({'activity': {'kind': kind, 'label': label, 'detail': detail, 'status': 'running'}})}\n\n"

                        elif event.type == AgentEventType.TOOL_RESULT:
                            result = event.data
                            success = result.get("success", False)
                            status = "done" if success else "error"
                            yield f"data: {json.dumps({'activity': {'kind': 'tool_result', 'label': 'Result', 'detail': result.get('output', '')[:200], 'status': status}})}\n\n"

                        elif event.type == AgentEventType.VERIFICATION:
                            yield f"data: {json.dumps({'verification': event.data})}\n\n"

                        elif event.type == AgentEventType.FIXING:
                            yield f"data: {json.dumps({'activity': {'kind': 'fixing', 'label': 'Fixing', 'detail': event.data.get('message', ''), 'status': 'running'}})}\n\n"

                        elif event.type == AgentEventType.DONE:
                            yield f"data: {json.dumps({'activity': {'kind': 'done', 'label': 'Complete', 'detail': event.data.get('summary', 'Task completed'), 'status': 'done'}})}\n\n"
                            yield f"data: {json.dumps({'done': True, 'summary': event.data})}\n\n"

                        elif event.type == AgentEventType.ERROR:
                            yield f"data: {json.dumps({'error': event.data.get('message', 'Unknown error')})}\n\n"

                except Exception as e:
                    logger.exception(f"[NAVI Unified Agent] Error: {e}")
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"

            return StreamingResponse(
                unified_agent_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive",
                },
            )

        # =====================================================================
        # NAVI BRAIN: For analysis, explanation, and conversation requests
        # =====================================================================
        # Use NAVI brain for intelligent code analysis (Agent / Agent Full Access)
        from backend.services.navi_brain import process_navi_request_streaming

        workspace_path = request.workspace_root or str(Path.cwd())

        # Extract context from request
        current_file = getattr(request, "current_file", None)
        current_file_content = getattr(request, "current_file_content", None)
        selection = getattr(request, "selection", None)
        errors = getattr(request, "errors", None)

        # Check attachments for file content
        # Handle both Pydantic model and dict formats
        if not current_file_content and request.attachments:
            for att in request.attachments:
                # Support both Pydantic model attributes and dict .get()
                att_kind = getattr(att, "kind", None) or (
                    att.get("kind") if isinstance(att, dict) else None
                )
                att_content = getattr(att, "content", None) or (
                    att.get("content") if isinstance(att, dict) else None
                )
                att_path = getattr(att, "path", None) or (
                    att.get("path") if isinstance(att, dict) else None
                )

                if att_kind in ("file", "code") and att_content:
                    if not current_file:
                        current_file = att_path
                    if not current_file_content:
                        current_file_content = att_content
                    break

        # Determine if auto-execute is enabled (Agent Full Access mode)
        auto_execute = mode in (
            "agent-full-access",
            "agent_full_access",
            "full-access",
            "full_access",
        )

        async def navi_brain_stream():
            """Stream NAVI brain response with REAL activity events - shows actual backend progress"""
            # Initialize streaming session for metrics tracking
            stream_session = StreamingSession()

            try:
                # AUTO-RECOVERY: If there was a previous action error, prepend context to the message
                actual_message = request.message
                last_error = getattr(request, "last_action_error", None)
                if last_error and isinstance(last_error, dict):
                    error_msg = last_error.get("errorMessage", "Unknown error")
                    error_details = last_error.get("errorDetails", "")
                    failed_action = last_error.get("action", {})
                    failed_path = failed_action.get("filePath", "unknown path")
                    exit_code = last_error.get("exitCode")
                    command_output = (
                        last_error.get("commandOutput")
                        or last_error.get("stderr")
                        or last_error.get("stdout")
                        or ""
                    )
                    command_output = command_output.strip()[:4000]

                    # Prepend error context so NAVI knows to debug and continue
                    actual_message = f"""[AUTO-RECOVERY] The previous action failed with error:
Error: {error_msg}
Details: {error_details}
Exit code: {exit_code if exit_code is not None else 'unknown'}
Command output:
```
{command_output or 'No output captured'}
```
Failed action type: {failed_action.get('type', 'unknown')}
Failed file path: {failed_path}

Please debug this issue and continue with the original task. The user's new message is:
{request.message}"""
                    logger.info(
                        f"[NAVI STREAM] 🔧 Auto-recovery mode activated - previous action failed on {failed_path}"
                    )
                    yield f"data: {json.dumps({'activity': {'kind': 'recovery', 'label': 'Debugging', 'detail': 'Analyzing previous error...', 'status': 'running'}})}\n\n"

                # Only show current file context if actually provided
                if current_file:
                    yield f"data: {json.dumps({'activity': {'kind': 'context', 'label': 'Active file', 'detail': current_file, 'status': 'done'}})}\n\n"

                # ============ REAL-TIME STREAMING with process_navi_request_streaming ============
                navi_result = None
                files_read_live = []

                conversation_history = _normalize_conversation_history(
                    request.conversationHistory
                )

                # OPTIMIZATION: Check cache for 50-95% latency improvement on repeated queries
                # Include workspace/model/provider for proper cache scoping
                # Note: org_id/user_id would improve tenant isolation but aren't available
                # on this unauthenticated VS Code extension endpoint
                cache_key = generate_cache_key(
                    message=actual_message,
                    mode=request.mode,
                    conversation_history=conversation_history[
                        -5:
                    ],  # Last 5 for cache key
                    workspace_path=workspace_path,
                    model=llm_model,
                    provider=llm_provider,
                )
                cached_result = get_cached_response(cache_key)

                if cached_result:
                    # Cache HIT - return immediately without LLM call!
                    logger.info(
                        "🚀 Cache HIT - serving cached response (latency saved!)"
                    )
                    yield f"data: {json.dumps({'activity': {'kind': 'cache_hit', 'label': 'Cache', 'detail': 'Serving cached response', 'status': 'done'}})}\n\n"
                    navi_result = cached_result
                    # Skip to result processing
                else:
                    # Cache MISS - proceed with LLM call
                    async for event in process_navi_request_streaming(
                        message=actual_message,
                        workspace_path=workspace_path,
                        llm_provider=llm_provider,
                        llm_model=llm_model,
                        api_key=None,
                        current_file=current_file,
                        current_file_content=current_file_content,
                        selection=selection,
                        open_files=None,
                        errors=errors,
                        conversation_history=conversation_history,
                    ):
                        # Stream activity events directly to the frontend
                        if "activity" in event:
                            activity = event["activity"]
                            # Track files read to avoid duplicates
                            if activity.get("kind") == "file_read":
                                files_read_live.append(activity.get("detail", ""))
                            yield f"data: {json.dumps({'activity': activity})}\n\n"

                        # Stream thinking content in real-time (LLM inner monologue)
                        elif "thinking" in event:
                            thinking_text = event["thinking"]
                            yield f"data: {json.dumps({'thinking': thinking_text})}\n\n"

                        # Stream narrative text for interleaved display (Claude Code style)
                        elif "narrative" in event:
                            narrative_text = event["narrative"]
                            yield f"data: {json.dumps({'type': 'navi.narrative', 'text': narrative_text})}\n\n"

                        # Capture the final result
                        elif "result" in event:
                            navi_result = event["result"]

                    # Cache the result for future requests
                    if navi_result:
                        set_cached_response(cache_key, navi_result)
                        logger.info(f"💾 Result cached for key {cache_key[:8]}...")

                # Process the final result
                if navi_result:
                    # Debug logging for file operations
                    logger.info(
                        f"[NAVI STREAM] Result keys: {list(navi_result.keys())}"
                    )
                    logger.info(
                        f"[NAVI STREAM] files_created: {navi_result.get('files_created', [])}"
                    )
                    logger.info(
                        f"[NAVI STREAM] file_edits count: {len(navi_result.get('file_edits', []))}"
                    )

                    # Emit activity: files to create/modify
                    files_created = navi_result.get("files_created", [])
                    files_modified = navi_result.get("files_modified", [])
                    file_edits = navi_result.get("file_edits", [])

                    for file_path in files_created:
                        yield f"data: {json.dumps({'activity': {'kind': 'create', 'label': 'Creating', 'detail': file_path, 'status': 'done'}})}\n\n"

                    for file_path in files_modified:
                        yield f"data: {json.dumps({'activity': {'kind': 'edit', 'label': 'Editing', 'detail': file_path, 'status': 'done'}})}\n\n"

                    # Build response content
                    response_content = navi_result.get(
                        "message", "Task completed successfully."
                    )

                    # Stream the response content with Cline-style typing effect
                    # Uses streaming_utils for smooth, real-time token delivery
                    async for chunk in stream_text_with_typing(
                        response_content,
                        chunk_size=3,  # Smaller chunks for smoother typing effect
                        delay_ms=12,  # Faster for responsive feel
                    ):
                        content_event = stream_session.content(chunk)
                        yield f"data: {json.dumps(content_event)}\n\n"

                    # Include actions in the response
                    actions = []

                    # First, include any proposed actions from the result (e.g., command proposals)
                    proposed_actions = navi_result.get("actions", [])
                    for action in proposed_actions:
                        actions.append(action)

                    # Then, add file edits as editFile actions
                    for edit in file_edits:
                        # Backend uses 'filePath', not 'path'
                        file_path_value = edit.get("filePath") or edit.get("path")
                        if file_path_value:
                            actions.append(
                                {
                                    "type": edit.get("type", "editFile"),
                                    "filePath": file_path_value,
                                    "content": edit.get("content"),
                                    "diff": edit.get("diff"),
                                    "additions": edit.get("additions"),
                                    "deletions": edit.get("deletions"),
                                }
                            )
                        else:
                            logger.warning(
                                f"[NAVI STREAM] Skipping action with no filePath: {edit}"
                            )

                    # Only add files_created that aren't already in file_edits
                    existing_paths = {
                        a.get("filePath") for a in actions if a.get("filePath")
                    }
                    for file_path in files_created:
                        if file_path not in existing_paths:
                            # Find content for this file in file_edits
                            content = None
                            for edit in file_edits:
                                edit_path = edit.get("filePath") or edit.get("path")
                                if edit_path == file_path:
                                    content = edit.get("content")
                                    break
                            if content:
                                actions.append(
                                    {
                                        "type": "createFile",
                                        "filePath": file_path,
                                        "content": content,
                                    }
                                )

                    if actions:
                        logger.info(
                            f"[NAVI STREAM] Sending {len(actions)} actions: {[a.get('type') for a in actions]}"
                        )
                        # Emit narrative before actions for interleaved display
                        action_types = [a.get("type") for a in actions]
                        if "runCommand" in action_types:
                            cmd_count = sum(
                                1 for a in actions if a.get("type") == "runCommand"
                            )
                            plural = "s" if cmd_count > 1 else ""
                            narrative = f"Now I'll run {cmd_count} command{plural} to complete this task."
                            yield f"data: {json.dumps({'type': 'navi.narrative', 'text': narrative})}\n\n"
                        if any(t in ["editFile", "createFile"] for t in action_types):
                            file_count = sum(
                                1
                                for a in actions
                                if a.get("type") in ["editFile", "createFile"]
                            )
                            plural = "s" if file_count > 1 else ""
                            narrative = f"Making changes to {file_count} file{plural}."
                            yield f"data: {json.dumps({'type': 'navi.narrative', 'text': narrative})}\n\n"
                        yield f"data: {json.dumps({'actions': actions})}\n\n"

                    # Include next_steps if available
                    next_steps = navi_result.get("next_steps", [])
                    if next_steps:
                        yield f"data: {json.dumps({'next_steps': next_steps})}\n\n"

                # Include router info with mode and task type
                yield f"data: {json.dumps({'router_info': {'provider': llm_provider, 'model': llm_model or 'auto', 'mode': mode, 'task_type': llm_context.get('task_type', 'code_generation'), 'auto_execute': auto_execute}})}\n\n"

                # Include streaming metrics for performance tracking
                metrics = stream_session.get_metrics()
                yield f"data: {json.dumps(metrics)}\n\n"

                yield "data: [DONE]\n\n"

            except Exception as e:
                logger.error(f"NAVI brain streaming error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                # Still emit metrics on error for debugging
                metrics = stream_session.get_metrics()
                yield f"data: {json.dumps(metrics)}\n\n"

        return StreamingResponse(
            navi_brain_stream(),
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

    llm_context: Dict[str, Any] = {}

    try:
        # 🚀 LLM-FIRST NAVI BRAIN - Pure LLM intelligence for code generation and execution
        # Uses new clean NAVI brain with safety features and multi-provider LLM support

        # Check if workspace_root is provided, if not, skip NAVI processing
        if not request.workspace_root:
            logger.warning("⚠️ workspace_root is None, skipping NAVI brain processing")
            raise ValueError("workspace_root is required for NAVI processing")
        workspace_path = request.workspace_root

        from backend.services.navi_brain import process_navi_request

        # 🚀 LLM-FIRST: Extract full context from request
        current_file = getattr(request, "current_file", None)
        current_file_content = getattr(request, "current_file_content", None)
        selection = getattr(request, "selection", None)
        errors = getattr(request, "errors", None)

        # Also check attachments for file content (backward compatibility)
        # Handle both Pydantic model and dict formats
        if not current_file_content and request.attachments:
            for att in request.attachments:
                # Support both Pydantic model attributes and dict .get()
                att_kind = getattr(att, "kind", None) or (
                    att.get("kind") if isinstance(att, dict) else None
                )
                att_content = getattr(att, "content", None) or (
                    att.get("content") if isinstance(att, dict) else None
                )
                att_path = getattr(att, "path", None) or (
                    att.get("path") if isinstance(att, dict) else None
                )

                if att_kind in ("file", "code") and att_content:
                    if not current_file:
                        current_file = att_path
                    if not current_file_content:
                        current_file_content = att_content
                    break

        logger.info(
            f"🎯 Context extracted - current_file: {current_file}, has_content: {bool(current_file_content)}, has_selection: {bool(selection)}, errors: {len(errors) if errors else 0}"
        )

        # Resolve server-side routing (auto/manual) so UI badges reflect actual selection
        llm_context = _resolve_llm_selection(
            request.message,
            request.model,
            request.mode,
            request.provider,
        )
        llm_provider = llm_context.get("provider") or os.environ.get(
            "DEFAULT_LLM_PROVIDER", "openai"
        )
        llm_model = llm_context.get("resolved_model") or None

        # Call the new LLM-first NAVI brain with full context
        conversation_history = _normalize_conversation_history(
            request.conversationHistory
        )
        navi_result = await process_navi_request(
            message=request.message,
            workspace_path=workspace_path,
            llm_provider=llm_provider,
            llm_model=llm_model,
            api_key=None,  # Will use environment variable
            current_file=current_file,
            current_file_content=current_file_content,
            selection=selection,
            open_files=None,
            errors=errors,
            conversation_history=conversation_history,
        )

        logger.info(
            f"🎯 NAVI brain processed: success={navi_result.get('success', False)}, "
            f"files_created={len(navi_result.get('files_created', []))}, "
            f"files_modified={len(navi_result.get('files_modified', []))}, "
            f"file_edits={len(navi_result.get('file_edits', []))}"
        )

        # Build response content from NAVI brain result
        response_content = navi_result.get("message", "Task completed successfully.")

        # Add warnings if any (safety features)
        if navi_result.get("warnings"):
            response_content += "\n\n**⚠️ Warnings:**\n"
            for warning in navi_result["warnings"]:
                response_content += f"- {warning}\n"

        # Add helpful context about files to be created (not yet - user needs to click Apply)
        if navi_result.get("files_created"):
            response_content += "\n\n**Files to create** (click Apply to create):\n"
            for file_path in navi_result["files_created"]:
                response_content += f"- {file_path}\n"

        # Add helpful context about files to be modified (not yet - user needs to click Apply)
        if navi_result.get("files_modified"):
            response_content += "\n\n**Files to modify** (click Apply to apply fix):\n"
            for file_path in navi_result["files_modified"]:
                response_content += f"- {file_path}\n"

        # Add helpful context about commands to run (not yet - user needs to click Apply)
        if navi_result.get("commands_run"):
            response_content += "\n\n**Commands to run** (click Apply to execute):\n"
            for command in navi_result["commands_run"]:
                response_content += f"- `{command}`\n"

        # Add next steps suggestions if provided by LLM
        if navi_result.get("next_steps"):
            response_content += "\n\n**Suggested next steps:**\n"
            for step in navi_result["next_steps"]:
                response_content += f"- {step}\n"

        # Convert NAVI's file edits, commands and VS Code commands into actions array
        actions = []

        # Add file edits as editFile actions (these are actual code changes for VS Code to apply)
        file_edits = navi_result.get("file_edits", [])
        logger.info(
            f"[Chat API] Building actions - file_edits: {len(file_edits)}, commands_run: {navi_result.get('commands_run', [])}, vscode_commands: {len(navi_result.get('vscode_commands', []))}"
        )
        for file_edit in file_edits:
            workspace_root = request.workspace_root or ""
            file_path = file_edit.get("filePath", "")
            # Convert to absolute path
            if file_path and not os.path.isabs(file_path):
                file_path = os.path.join(workspace_root, file_path)
            actions.append(
                {
                    "type": "editFile",
                    "filePath": file_path,
                    "content": file_edit.get("content", ""),
                    "operation": file_edit.get("operation", "modify"),
                }
            )

        # Add shell commands as runCommand actions
        commands_run = navi_result.get("commands_run", [])
        for command in commands_run:
            actions.append(
                {
                    "type": "runCommand",
                    "command": command,
                    "cwd": request.workspace_root,
                }
            )

        # Add VS Code commands as vscode_command actions (only if no file edits - avoid duplicate "open file" actions)
        vscode_commands = navi_result.get("vscode_commands", [])
        for vscode_cmd in vscode_commands:
            # Skip vscode.open if we already have file edits (redundant)
            if vscode_cmd.get("command") == "vscode.open" and file_edits:
                continue

            # Convert relative paths to absolute paths for vscode.open command
            args = vscode_cmd.get("args", [])
            if vscode_cmd.get("command") == "vscode.open" and args:
                workspace_root = request.workspace_root or ""
                # Make first arg absolute if it's a relative path
                if args[0] and not os.path.isabs(args[0]):
                    args[0] = os.path.join(workspace_root, args[0])

            actions.append(
                {
                    "type": "vscode_command",
                    "command": vscode_cmd.get("command"),
                    "args": args,
                }
            )

        logger.info(
            f"[Chat API] Final actions to return: {len(actions)} - types: {[a.get('type') for a in actions]}"
        )

        # Return actions if we have any
        if actions or navi_result.get("success"):
            return _attach_llm_context(
                ChatResponse(
                    content=response_content,
                    actions=actions,
                    thinking_steps=navi_result.get("thinking_steps"),
                    files_read=navi_result.get("files_read"),
                    project_type=navi_result.get("project_type"),
                    framework=navi_result.get("framework"),
                    warnings=navi_result.get("warnings"),
                    next_steps=navi_result.get("next_steps"),
                ),
                llm_context,
            )

        # If successful but no VS Code commands, just return the message
        if navi_result.get("success"):
            return _attach_llm_context(
                ChatResponse(
                    content=response_content,
                    actions=[],
                    thinking_steps=navi_result.get("thinking_steps"),
                    files_read=navi_result.get("files_read"),
                    project_type=navi_result.get("project_type"),
                    framework=navi_result.get("framework"),
                    warnings=navi_result.get("warnings"),
                    next_steps=navi_result.get("next_steps"),
                ),
                llm_context,
            )

        # OPTIMIZATION: Fetch memories in parallel for 50% faster context loading
        memories: List[Dict[str, Any]] = []
        try:
            # Run both memory searches concurrently instead of sequential fallback
            semantic_task = search_memory(
                db=db,
                user_id="default_user",
                query=request.message,
                limit=5,
                min_importance=1,
            )
            recent_task = get_recent_memories(db=db, user_id="default_user", limit=5)

            search_result, recent_result = await asyncio.gather(
                semantic_task, recent_task, return_exceptions=True
            )

            # Use semantic search if successful, otherwise fall back to recent
            if not isinstance(search_result, Exception) and search_result:
                memories = search_result
            elif not isinstance(recent_result, Exception) and recent_result:
                memories = recent_result
            else:
                memories = []
        except Exception:
            memories = []

        if _has_diff_attachments(request.attachments):
            diff_response = await _handle_diff_review(request)
            return _attach_llm_context(diff_response, llm_context)

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
                return _attach_llm_context(
                    ChatResponse(
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
                    ),
                    llm_context,
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
                        return _attach_llm_context(
                            ChatResponse(
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
                                suggestions=[
                                    "Customize project",
                                    "Add features",
                                    "Done",
                                ],
                            ),
                            llm_context,
                        )
                    else:
                        return _attach_llm_context(
                            ChatResponse(
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
                            ),
                            llm_context,
                        )

            except Exception as e:
                logger.error(f"Error creating project: {e}", exc_info=True)
                return _attach_llm_context(
                    ChatResponse(
                        content=f"""❌ **Error creating project**

{str(e)}

Would you like to try again with different settings?
""",
                        suggestions=["Try again", "Change location", "Cancel"],
                    ),
                    llm_context,
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
                if not task_id:
                    raise ValueError("Missing task_id in request state")
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
                                        else "✏️" if step.operation == "modify" else "🗑️"
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
        base_response.context["llm"] = llm_context

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
        return _attach_llm_context(
            ChatResponse(
                content="I ran into an error while processing that. Try again, or send a smaller diff.",
                suggestions=[
                    "Review working changes",
                    "Review staged changes",
                    "Explain this repo",
                ],
            ),
            llm_context if "llm_context" in locals() else {},
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

            intent_content = response.choices[0].message.content or ""
            intent_type = intent_content.strip().lower()

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
        # OPTIMIZATION: Limit to last 5 messages for 20-30% faster LLM responses
        # More context = longer prompts = slower API calls
        "conversation_history": (
            request.conversationHistory[-5:] if request.conversationHistory else []
        ),
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
                else "📝" if status == "To Do" else "✅" if status == "Done" else "📌"
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


# ------------------------------------------------------------------------------
# UNIFIED AGENT ENDPOINT - Native Tool-Use Agentic Loop
# ------------------------------------------------------------------------------
# This is the new architecture that makes NAVI competitive with Cline, Copilot,
# and Claude Code by using native LLM tool-use APIs.


@navi_router.post("/agent/stream")
async def navi_agent_stream(request: NaviChatRequest):
    """
    Streaming endpoint for the unified agentic agent.

    This endpoint uses native LLM tool-use (not text parsing) and implements
    a continuous agentic loop where:
    1. LLM receives tools and decides what to do
    2. Tools are executed and results fed back
    3. Loop continues until task is complete

    Returns SSE events for real-time UI updates.
    """
    from backend.services.unified_agent import UnifiedAgent, AgentEventType

    # Validate workspace
    if not request.workspace_root:

        async def error_stream():
            yield f"data: {json.dumps({'error': 'workspace_root is required for agent mode'})}\n\n"

        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
        )

    # Get provider/model from request or environment
    provider = request.provider or os.environ.get("DEFAULT_LLM_PROVIDER", "anthropic")
    model = request.model

    # Build project context from request
    project_context = None
    if request.current_file or request.errors:
        project_context = {
            "current_file": request.current_file,
            "errors": request.errors,
        }

    async def agent_event_stream():
        """Stream unified agent events as SSE."""
        try:
            agent = UnifiedAgent(
                provider=provider,
                model=model,
            )

            # Emit start event with router info
            yield f"data: {json.dumps({'router_info': {'provider': provider, 'model': model or 'auto', 'mode': 'unified_agent'}})}\n\n"

            # Normalize conversation history
            conversation_history = _normalize_conversation_history(
                request.conversationHistory
            )

            async for event in agent.run(
                message=request.message,
                workspace_path=request.workspace_root or ".",
                conversation_history=conversation_history,
                project_context=project_context,
            ):
                # Convert agent events to SSE format that frontend understands
                if event.type == AgentEventType.THINKING:
                    yield f"data: {json.dumps({'activity': {'kind': 'thinking', 'label': 'Thinking', 'detail': event.data.get('message', ''), 'status': 'running'}})}\n\n"

                elif event.type == AgentEventType.TEXT:
                    # Stream text content
                    yield f"data: {json.dumps({'content': event.data})}\n\n"

                elif event.type == AgentEventType.TOOL_CALL:
                    # Map tool calls to activity events
                    tool_name = event.data.get("name", "unknown")
                    tool_args = event.data.get("arguments", {})

                    kind = "command"
                    label = tool_name
                    detail = ""

                    if tool_name == "read_file":
                        kind = "read"
                        label = "Reading"
                        detail = tool_args.get("path", "")
                    elif tool_name == "write_file":
                        kind = "create"
                        label = "Creating"
                        detail = tool_args.get("path", "")
                    elif tool_name == "edit_file":
                        kind = "edit"
                        label = "Editing"
                        detail = tool_args.get("path", "")
                    elif tool_name == "run_command":
                        kind = "command"
                        label = "Running"
                        detail = tool_args.get("command", "")
                    elif tool_name == "search_files":
                        kind = "search"
                        label = "Searching"
                        detail = tool_args.get("pattern", "")
                    elif tool_name == "list_directory":
                        kind = "read"
                        label = "Listing"
                        detail = tool_args.get("path", "")

                    yield f"data: {json.dumps({'activity': {'kind': kind, 'label': label, 'detail': detail, 'status': 'running', 'tool_id': event.data.get('id')}})}\n\n"

                elif event.type == AgentEventType.TOOL_RESULT:
                    # Update activity status based on result
                    result = event.data.get("result", {})
                    success = result.get("success", True)
                    status = "done" if success else "error"

                    yield f"data: {json.dumps({'activity': {'kind': 'tool_result', 'label': event.data.get('name', 'Tool'), 'detail': 'completed' if success else result.get('error', 'failed'), 'status': status, 'tool_id': event.data.get('id')}})}\n\n"

                    # Also emit the result content for display
                    if result.get("stdout"):
                        yield f"data: {json.dumps({'tool_output': {'type': 'stdout', 'content': result['stdout'][:2000]}})}\n\n"
                    if result.get("stderr"):
                        yield f"data: {json.dumps({'tool_output': {'type': 'stderr', 'content': result['stderr'][:2000]}})}\n\n"
                    if result.get("content"):
                        # File content - truncate for large files
                        content = result["content"]
                        if len(content) > 5000:
                            content = (
                                content[:5000]
                                + f"\n... (truncated, {len(result['content'])} total chars)"
                            )
                        yield f"data: {json.dumps({'tool_output': {'type': 'file_content', 'path': result.get('path'), 'content': content}})}\n\n"

                elif event.type == AgentEventType.ERROR:
                    yield f"data: {json.dumps({'error': event.data.get('error', 'Unknown error')})}\n\n"

                elif event.type == AgentEventType.DONE:
                    # Emit summary
                    yield f"data: {json.dumps({'done': {'task_id': event.data.get('task_id'), 'iterations': event.data.get('iterations'), 'files_read': event.data.get('files_read', []), 'files_modified': event.data.get('files_modified', []), 'commands_run': event.data.get('commands_run', [])}})}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"[NAVI Agent] Error in agent stream: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        agent_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _should_use_unified_agent(message: str) -> bool:
    """
    Detect if a message should use the unified agent (action-oriented requests).

    Returns True for requests that involve taking action rather than just chatting.
    """
    action_patterns = [
        # File/code creation
        r"\b(create|write|make|add|build|generate)\b.*\b(file|component|function|class|test|module|page)\b",
        # Running things - more permissive
        r"\b(run|execute|start|stop|restart|launch)\b.*(project|server|test|build|app|application|script|command)",
        r"\b(run|execute)\s+(the\s+)?(project|tests?|build|server|app)",  # "run the project", "run tests"
        # Bug fixing
        r"\b(fix|debug|repair|resolve|solve)\b.*\b(bug|error|issue|problem|crash|failure)\b",
        # Code editing
        r"\b(edit|modify|update|change|refactor|rename)\b.*\b(file|code|function|variable|class)\b",
        # Package management
        r"\b(install|uninstall|add|remove|upgrade|update)\b.*\b(package|dependency|module|library)\b",
        r"\bnpm\s+(install|run|start|build|test)",  # npm commands
        r"\byarn\s+(install|add|run|start|build|test)",  # yarn commands
        r"\bpip\s+(install|uninstall)",  # pip commands
        r"\bcargo\s+(build|run|test)",  # cargo commands
        r"\bgo\s+(build|run|test|get)",  # go commands
        r"\bpython\s+",  # python scripts
        r"\bnode\s+",  # node scripts
        # Git commands
        r"\bgit\s+(commit|push|pull|merge|rebase|checkout|branch)",
        # Imperative action phrases
        r"^(please\s+)?(can\s+you\s+)?(run|execute|start|create|fix|install|build)",  # "run...", "can you run..."
        # Direct command patterns
        r"^\s*(npm|yarn|pip|cargo|go|python|node|git)\s+",  # Commands at start of message
    ]

    message_lower = message.lower()
    for pattern in action_patterns:
        if re.search(pattern, message_lower, re.IGNORECASE):
            return True

    return False
