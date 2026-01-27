"""
NAVI Router - Clean LLM-First API (No Regex, No Hybrid Modes)
Pure LLM intelligence with safety features
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/navi", tags=["navi"])


# ==================== REQUEST/RESPONSE MODELS ====================


class NaviRequest(BaseModel):
    """Request model for NAVI processing"""

    message: str = Field(..., description="User's natural language message")
    workspace: str = Field(..., description="Workspace root path")

    # LLM configuration (user's choice)
    llm_provider: str = Field(
        default="openai",
        description="LLM provider: openai, anthropic, google, groq, mistral, openrouter, ollama",
    )
    llm_model: Optional[str] = Field(
        default=None,
        description="Specific model name (optional, uses provider default)",
    )
    api_key: Optional[str] = Field(
        default=None, description="API key (optional, can use environment variable)"
    )

    # Context from VS Code
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional context (current file, selection, etc.)"
    )

    # Conversation context for multi-turn conversations
    conversation_id: Optional[str] = Field(
        default=None,
        description="Unique conversation/session ID for tracking multi-turn conversations",
    )
    conversation_history: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Recent conversation history (last N messages) for context",
    )


class NaviResponse(BaseModel):
    """Response model for NAVI processing"""

    success: bool = Field(..., description="Whether the action succeeded")
    message: str = Field(..., description="Human-readable message")

    # Files
    files_created: List[str] = Field(
        default_factory=list, description="Files that were created"
    )
    files_modified: List[str] = Field(
        default_factory=list, description="Files that were modified"
    )

    # Commands
    commands_run: List[str] = Field(
        default_factory=list, description="Commands that were executed"
    )

    # VS Code integration
    vscode_commands: List[Dict[str, Any]] = Field(
        default_factory=list, description="VS Code commands to execute"
    )

    # User interaction
    needs_user_input: bool = Field(
        default=False, description="Whether user input is needed"
    )
    user_input_prompt: Optional[str] = Field(
        default=None, description="Prompt for user input"
    )

    # Safety
    needs_user_confirmation: bool = Field(
        default=False, description="Whether dangerous commands need confirmation"
    )
    dangerous_commands: List[str] = Field(
        default_factory=list, description="Commands that need confirmation"
    )
    warnings: List[str] = Field(default_factory=list, description="Safety warnings")

    # Execution details
    execution_results: Optional[Dict[str, Any]] = Field(
        default=None, description="Detailed execution results"
    )


# ==================== MAIN ENDPOINT ====================


@router.post("/process", response_model=NaviResponse)
async def process_navi_request(request: NaviRequest):
    """
    Process a natural language request with NAVI (LLM-First, No Regex).

    NAVI understands ANY request naturally:
    - "I need user authentication" → Creates complete auth system
    - "add a navbar" → Creates component with proper structure
    - "fix the login error" → Analyzes and fixes automatically
    - "install axios and create api service" → Chains multiple actions

    Safety Features:
    ✅ Command whitelist (only safe commands auto-execute)
    ✅ Dangerous command detection (requires confirmation)
    ✅ File size limits (max 100KB per file)
    ✅ Path validation (files stay in workspace)
    ✅ Multi-layer validation before execution

    Example:
        POST /api/navi/process
        {
            "message": "create a login component with tests",
            "workspace": "/path/to/project",
            "llm_provider": "anthropic"
        }

    Returns:
        {
            "success": true,
            "message": "Created Login component with tests",
            "files_created": ["src/components/Login.tsx", "src/components/Login.test.tsx"],
            "commands_run": ["npm install --save-dev @testing-library/react"],
            "vscode_commands": [{"command": "vscode.open", "args": ["src/components/Login.tsx"]}]
        }
    """
    try:
        # Import the clean LLM-first system
        from backend.services.navi_brain import (
            process_navi_request as process_llm_request,
        )

        # Get API key from request or environment
        api_key = request.api_key
        if not api_key:
            env_vars = {
                "anthropic": "ANTHROPIC_API_KEY",
                "openai": "OPENAI_API_KEY",
                "google": "GOOGLE_API_KEY",
                "groq": "GROQ_API_KEY",
                "mistral": "MISTRAL_API_KEY",
                "openrouter": "OPENROUTER_API_KEY",
            }
            api_key = os.getenv(env_vars.get(request.llm_provider, ""))

        if not api_key and request.llm_provider != "ollama":
            raise HTTPException(
                status_code=400,
                detail=f"API key required for {request.llm_provider}. Set {env_vars.get(request.llm_provider, 'API_KEY')} environment variable or pass api_key in request.",
            )

        logger.info(f"🎯 Processing NAVI request: {request.message[:100]}...")
        logger.info(
            f"🤖 Using LLM: {request.llm_provider} {request.llm_model or '(default model)'}"
        )

        # Extract context fields
        context = request.context or {}
        current_file = context.get("currentFile") or context.get("current_file")
        current_file_content = context.get("currentFileContent") or context.get(
            "current_file_content"
        )
        selection = context.get("selection")
        open_files = context.get("openFiles") or context.get("open_files")
        errors = context.get("errors")
        # Use direct field if provided, otherwise fallback to context
        conversation_history = (
            request.conversation_history
            or context.get("conversationHistory")
            or context.get("conversation_history")
        )

        # Process with clean LLM-first system
        result = await process_llm_request(
            message=request.message,
            workspace_path=request.workspace,
            llm_provider=request.llm_provider,
            llm_model=request.llm_model,
            api_key=api_key,
            current_file=current_file,
            current_file_content=current_file_content,
            selection=selection,
            open_files=open_files,
            errors=errors,
            conversation_history=conversation_history,
        )

        return NaviResponse(**result)

    except Exception as e:
        logger.error(f"❌ NAVI processing failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"NAVI processing failed: {str(e)}")


# ==================== NAVI V2: APPROVAL FLOW ENDPOINTS ====================


class PlanResponse(BaseModel):
    """Response for plan creation (NAVI V2)"""

    plan_id: str = Field(..., description="Unique plan ID")
    message: str = Field(..., description="Response message")
    requires_approval: bool = Field(..., description="Whether user approval is needed")
    actions_with_risk: List[Dict[str, Any]] = Field(
        default_factory=list, description="Actions with risk assessment"
    )
    thinking_steps: List[str] = Field(
        default_factory=list, description="Thinking process"
    )
    files_read: List[str] = Field(default_factory=list, description="Files analyzed")
    project_type: Optional[str] = Field(
        default=None, description="Detected project type"
    )
    framework: Optional[str] = Field(default=None, description="Detected framework")


class ApproveRequest(BaseModel):
    """Request to approve a plan"""

    approved_action_indices: List[int] = Field(
        ..., description="Indices of actions to execute"
    )


class ExecutionUpdate(BaseModel):
    """Execution progress update"""

    type: str = Field(
        ..., description="Update type: action_start, action_complete, plan_complete"
    )
    index: Optional[int] = Field(default=None, description="Action index")
    action: Optional[Dict[str, Any]] = Field(default=None, description="Action details")
    success: Optional[bool] = Field(default=None, description="Action success status")
    output: Optional[str] = Field(default=None, description="Command output")
    error: Optional[str] = Field(default=None, description="Error message")


@router.post("/plan", response_model=PlanResponse)
async def create_plan(request: NaviRequest):
    """
    NAVI V2: Create a plan without executing (for human approval).

    This endpoint analyzes the request and generates actions with risk assessment,
    but doesn't execute them. The user can then approve/reject specific actions.

    Example:
        POST /api/navi/plan
        {
            "message": "create a login page",
            "workspace": "/path/to/project",
            "llm_provider": "anthropic"
        }

    Returns:
        {
            "plan_id": "uuid",
            "message": "I'll create a login page with form validation...",
            "requires_approval": true,
            "actions_with_risk": [
                {
                    "type": "createFile",
                    "path": "src/pages/Login.tsx",
                    "risk": "low",
                    "warnings": [],
                    "preview": "..."
                }
            ],
            "thinking_steps": ["Analyzing project...", "Detected Next.js project", ...]
        }
    """
    try:
        from backend.services.navi_brain import NaviBrain, NaviContext

        # Get API key
        api_key = request.api_key or os.getenv(
            {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}.get(
                request.llm_provider, ""
            )
        )

        if not api_key and request.llm_provider != "ollama":
            raise HTTPException(
                status_code=400, detail=f"API key required for {request.llm_provider}"
            )

        logger.info(f"🎯 [NAVI V2] Creating plan for: {request.message[:100]}...")

        # Initialize brain
        brain = NaviBrain(
            provider=request.llm_provider, model=request.llm_model, api_key=api_key
        )

        # Build context
        context_dict = request.context or {}
        context = NaviContext(
            workspace_path=request.workspace,
            current_file=context_dict.get("currentFile"),
            current_file_content=context_dict.get("currentFileContent"),
            selection=context_dict.get("selection"),
            open_files=context_dict.get("openFiles", []),
            errors=context_dict.get("errors", []),
            recent_conversation=context_dict.get("conversationHistory", []),
        )

        # Generate plan (doesn't execute)
        response = await brain.plan(request.message, context)

        await brain.close()

        return PlanResponse(
            plan_id=response.plan_id or "",
            message=response.message,
            requires_approval=response.requires_approval,
            actions_with_risk=response.actions_with_risk,
            thinking_steps=response.thinking_steps,
            files_read=response.files_read,
            project_type=response.project_type,
            framework=response.framework,
        )

    except Exception as e:
        logger.error(f"❌ [NAVI V2] Plan creation failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Plan creation failed: {str(e)}")


@router.post("/plan/{plan_id}/approve")
async def approve_plan(plan_id: str, approve_request: ApproveRequest):
    """
    NAVI V2: Approve and execute specific actions from a plan.

    Example:
        POST /api/navi/plan/abc-123/approve
        {
            "approved_action_indices": [0, 1, 3]
        }

    Returns:
        {
            "execution_id": "xyz-456",
            "status": "executing",
            "message": "Executing 3 approved actions..."
        }
    """
    try:
        # Get the brain instance (in production, you'd store this globally)
        # For now, we'll track plans globally in the module
        brain = getattr(approve_plan, "_brain_instance", None)
        if not brain:
            raise HTTPException(status_code=404, detail="Plan not found")

        plan = brain.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")

        logger.info(
            f"🎯 [NAVI V2] Approved {len(approve_request.approved_action_indices)} actions for plan {plan_id}"
        )

        # Start execution in background
        execution_id = plan_id + "-exec"

        return {
            "execution_id": execution_id,
            "status": "executing",
            "message": f"Executing {len(approve_request.approved_action_indices)} approved actions...",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [NAVI V2] Plan approval failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Plan approval failed: {str(e)}")


@router.get("/plan/{plan_id}")
async def get_plan(plan_id: str):
    """
    NAVI V2: Get plan details by ID.

    Returns the full plan including actions and status.
    """
    try:
        brain = getattr(approve_plan, "_brain_instance", None)
        if not brain:
            raise HTTPException(status_code=404, detail="Plan not found")

        plan = brain.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")

        return plan.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [NAVI V2] Get plan failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Get plan failed: {str(e)}")


# ==================== HEALTH & INFO ENDPOINTS ====================


@router.get("/health")
async def health_check():
    """
    Health check endpoint

    Returns:
        {
            "status": "healthy",
            "service": "navi",
            "version": "2.0-llm-first-clean",
            "features": [...]
        }
    """
    return {
        "status": "healthy",
        "service": "navi",
        "version": "2.0-llm-first-clean",
        "architecture": "LLM-First (No Regex Patterns)",
        "features": [
            "Pure LLM intelligence (no regex patterns)",
            "Multi-provider support (Anthropic, OpenAI, Google, Groq, Mistral, OpenRouter, Ollama)",
            "Command whitelist safety",
            "File size limits (100KB max)",
            "Path validation (workspace boundaries)",
            "Dangerous command detection",
            "Graceful error handling",
            "Natural language understanding (infinite variations)",
        ],
    }


@router.get("/supported-actions")
async def supported_actions():
    """
    Return supported action types and any registered backend handlers.
    """
    try:
        from backend.core.action_registry import get_action_registry

        registry = get_action_registry()
        handler_actions = registry.get_supported_actions()
    except Exception:
        handler_actions = []

    built_in_action_types = [
        {
            "type": "editFile",
            "fields": ["filePath", "content", "operation"],
            "operations": ["create", "modify", "delete", "write"],
        },
        {"type": "runCommand", "fields": ["command", "cwd"]},
        {"type": "vscode_command", "fields": ["command", "args"]},
    ]

    return {
        "handlers": handler_actions,
        "action_types": built_in_action_types,
    }


@router.get("/providers")
async def get_providers():
    """
    Get available LLM providers and their models

    Returns:
        {
            "providers": [
                {
                    "id": "anthropic",
                    "name": "Anthropic (Claude)",
                    "models": [...],
                    "default": "claude-3-5-sonnet-20241022",
                    "recommended": true,
                    "best_for": "Code generation, reasoning, complex tasks"
                },
                ...
            ]
        }
    """
    return {
        "providers": [
            {
                "id": "anthropic",
                "name": "Anthropic (Claude)",
                "models": [
                    "claude-3-5-sonnet-20241022",
                    "claude-3-5-haiku-20241022",
                    "claude-3-opus-20240229",
                    "claude-3-haiku-20240307",
                ],
                "default": "claude-3-5-sonnet-20241022",
                "requires_api_key": True,
                "recommended": True,
                "best_for": "Code generation, reasoning, complex tasks",
                "cost_per_1k_requests": "$10-15",
                "latency": "300-800ms",
            },
            {
                "id": "openai",
                "name": "OpenAI (GPT)",
                "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
                "default": "gpt-4o",
                "requires_api_key": True,
                "best_for": "Fast responses, general tasks",
                "cost_per_1k_requests": "$5-10",
                "latency": "200-600ms",
            },
            {
                "id": "google",
                "name": "Google (Gemini)",
                "models": ["gemini-1.5-pro", "gemini-1.5-flash"],
                "default": "gemini-1.5-pro",
                "requires_api_key": True,
                "best_for": "Multimodal, large context",
                "cost_per_1k_requests": "$8-12",
                "latency": "400-1000ms",
            },
            {
                "id": "groq",
                "name": "Groq (Ultra-Fast)",
                "models": [
                    "llama-3.3-70b-versatile",
                    "llama3-70b-8192",
                    "mixtral-8x7b-32768",
                ],
                "default": "llama-3.3-70b-versatile",
                "requires_api_key": True,
                "best_for": "Ultra-fast responses",
                "cost_per_1k_requests": "$2-5",
                "latency": "100-300ms",
            },
            {
                "id": "mistral",
                "name": "Mistral AI",
                "models": ["mistral-large-latest", "codestral-latest"],
                "default": "mistral-large-latest",
                "requires_api_key": True,
                "best_for": "European data sovereignty, coding",
                "cost_per_1k_requests": "$6-10",
                "latency": "300-700ms",
            },
            {
                "id": "openrouter",
                "name": "OpenRouter (Unified API)",
                "models": [
                    "anthropic/claude-3-5-sonnet-20241022",
                    "openai/gpt-4o",
                    "google/gemini-pro",
                ],
                "default": "anthropic/claude-3-5-sonnet-20241022",
                "requires_api_key": True,
                "best_for": "Access multiple providers through one API",
                "cost_per_1k_requests": "Varies by model",
                "latency": "Varies by model",
            },
            {
                "id": "ollama",
                "name": "Ollama (Local)",
                "models": ["llama3", "codellama", "mistral", "mixtral"],
                "default": "llama3",
                "requires_api_key": False,
                "best_for": "Privacy, offline mode, no API costs",
                "cost_per_1k_requests": "$0 (free, runs locally)",
                "latency": "1000-3000ms (depends on hardware)",
            },
        ]
    }


@router.get("/safety/limits")
async def get_safety_limits():
    """
    Get safety limits and constraints

    Returns:
        {
            "max_file_size_bytes": 102400,
            "max_file_size_readable": "100KB",
            "max_files_per_request": 20,
            ...
        }
    """
    from backend.services.navi_brain import MAX_FILE_SIZE, MAX_FILES_PER_REQUEST

    return {
        "max_file_size_bytes": MAX_FILE_SIZE,
        "max_file_size_readable": f"{MAX_FILE_SIZE / 1024}KB",
        "max_files_per_request": MAX_FILES_PER_REQUEST,
        "path_validation": "All files must be within workspace directory",
        "command_validation": "Commands must be in whitelist or require user confirmation",
        "dangerous_patterns": [
            "rm -rf (recursive delete)",
            "sudo (elevated privileges)",
            "chmod 777 (insecure permissions)",
            "git push --force (force push)",
            "DROP TABLE/DATABASE (SQL drops)",
        ],
    }


@router.get("/safety/commands")
async def get_safe_commands():
    """
    Get list of safe commands that don't require confirmation

    Returns:
        {
            "safe_commands": ["npm", "yarn", "pip", "git status", ...],
            "note": "Commands not in this list will require user confirmation"
        }
    """
    from backend.services.navi_brain import SAFE_COMMANDS

    return {
        "safe_commands": sorted(list(SAFE_COMMANDS)),
        "categories": {
            "package_managers": ["npm", "yarn", "pnpm", "pip", "poetry", "cargo"],
            "build_tools": ["make", "cmake", "gradle", "mvn"],
            "testing": ["pytest", "jest", "vitest", "mocha"],
            "linting": ["eslint", "prettier", "black", "flake8"],
            "git_safe": [
                "git status",
                "git log",
                "git diff",
                "git add",
                "git commit",
                "git pull",
            ],
            "docker_readonly": ["docker ps", "docker images", "docker logs"],
            "file_ops": ["ls", "cat", "head", "tail", "grep", "find"],
        },
        "note": "Commands not in this list will require user confirmation before execution",
    }


# ==================== PROJECT DETECTION ====================


class ProjectDetectionRequest(BaseModel):
    """Request model for project detection"""

    workspace: str = Field(..., description="Workspace root path")


@router.post("/detect-project")
async def detect_project_type(request: ProjectDetectionRequest):
    """
    Detect project type, technologies, and setup

    Example:
        POST /api/navi/detect-project
        {
            "workspace": "/path/to/project"
        }

    Returns:
        {
            "project_type": "nextjs",
            "technologies": ["Next.js", "React", "TypeScript", "Tailwind"],
            "has_git": true,
            "has_docker": true
        }
    """
    try:
        from backend.services.navi_brain import NaviEngine
        from pathlib import Path

        # Create engine just to detect project
        engine = NaviEngine(workspace_path=request.workspace, llm_provider="anthropic")

        return {
            "project_type": engine.project_type,
            "technologies": engine.technologies,
            "workspace": request.workspace,
            "has_git": (Path(request.workspace) / ".git").exists(),
            "has_docker": (Path(request.workspace) / "Dockerfile").exists()
            or (Path(request.workspace) / "docker-compose.yml").exists(),
        }
    except Exception as e:
        logger.error(f"❌ Project detection failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Project detection failed: {str(e)}"
        )


# ==================== QUICK ACTIONS ====================


@router.post("/quick/fix")
async def quick_fix(request: NaviRequest):
    """Quick action: Fix errors in current file"""
    request.message = f"Fix the errors in {request.context.get('currentFile', 'the current file')}. Errors: {request.context.get('errors', [])}"
    return await process_navi_request(request)


@router.post("/quick/explain")
async def quick_explain(request: NaviRequest):
    """Quick action: Explain selected code"""
    selection = request.context.get("selection") if request.context else None
    if selection:
        request.message = f"Explain this code:\n{selection}"
    else:
        request.message = f"Explain {request.context.get('currentFile', 'this code')}"
    return await process_navi_request(request)


@router.post("/quick/refactor")
async def quick_refactor(request: NaviRequest):
    """Quick action: Refactor selected code"""
    selection = request.context.get("selection") if request.context else None
    if selection:
        request.message = (
            f"Refactor this code to be cleaner and more efficient:\n{selection}"
        )
    else:
        request.message = f"Refactor {request.context.get('currentFile', 'this file')}"
    return await process_navi_request(request)


@router.post("/quick/test")
async def quick_test(request: NaviRequest):
    """Quick action: Generate tests"""
    request.message = f"Generate comprehensive tests for {request.context.get('currentFile', 'this code')}"
    return await process_navi_request(request)


@router.post("/quick/document")
async def quick_document(request: NaviRequest):
    """Quick action: Add documentation"""
    request.message = f"Add JSDoc/docstrings to all functions in {request.context.get('currentFile', 'this file')}"
    return await process_navi_request(request)


@router.post("/quick/optimize")
async def quick_optimize(request: NaviRequest):
    """Quick action: Optimize code"""
    selection = request.context.get("selection") if request.context else None
    if selection:
        request.message = f"Optimize this code for performance:\n{selection}"
    else:
        request.message = f"Optimize {request.context.get('currentFile', 'this file')} for performance"
    return await process_navi_request(request)
