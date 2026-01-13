"""
NAVI Router - FastAPI endpoints for NAVI engine
Provides aggressive action-taking endpoints for the NAVI AI assistant
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import asyncio
import json
import logging

from backend.services.navi_engine import process_request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/navi", tags=["navi"])


# Request/Response Models
class NaviRequest(BaseModel):
    """Request model for NAVI processing"""

    message: str = Field(..., description="User's natural language message")
    workspace: str = Field(..., description="Workspace root path")
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional context (current file, selection, etc.)"
    )


class NaviResponse(BaseModel):
    """Response model for NAVI processing"""

    success: bool = Field(..., description="Whether the action succeeded")
    action: str = Field(..., description="Action that was taken")
    message: str = Field(..., description="Human-readable message")
    result: Optional[Dict[str, Any]] = Field(
        default=None, description="Action result details"
    )
    vscode_command: Optional[Dict[str, Any]] = Field(
        default=None, description="VS Code command to execute"
    )
    files_created: Optional[List[str]] = Field(
        default=None, description="Files that were created"
    )
    dependencies_installed: Optional[List[str]] = Field(
        default=None, description="Dependencies that were installed"
    )
    git_operations: Optional[List[str]] = Field(
        default=None, description="Git operations performed"
    )


class ProjectDetectRequest(BaseModel):
    """Request model for project detection"""

    workspace: str = Field(..., description="Workspace root path")


class ProjectDetectResponse(BaseModel):
    """Response model for project detection"""

    project_type: str = Field(..., description="Detected project type")
    technologies: List[str] = Field(..., description="Detected technologies")
    dependencies: Dict[str, str] = Field(..., description="Project dependencies")
    package_manager: str = Field(..., description="Detected package manager")


class StreamRequest(BaseModel):
    """Request model for streaming responses"""

    message: str = Field(..., description="User's natural language message")
    workspace: str = Field(..., description="Workspace root path")
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional context"
    )


# Endpoints


@router.post("/process", response_model=NaviResponse)
async def process_navi_request(request: NaviRequest):
    """
    Main NAVI processing endpoint.
    Parses user intent and executes actions immediately.

    Example:
        POST /api/navi/process
        {
            "message": "create a LoginButton component",
            "workspace": "/path/to/project",
            "context": {"currentFile": "src/App.tsx"}
        }

    Returns:
        {
            "success": true,
            "action": "create_component",
            "message": "Created LoginButton component",
            "result": {...},
            "vscode_command": {
                "command": "navi.createAndOpenFile",
                "args": ["src/components/LoginButton.tsx", "...code..."]
            },
            "files_created": ["src/components/LoginButton.tsx", "src/components/__tests__/LoginButton.test.tsx"]
        }
    """
    try:
        logger.info(f"🎯 Processing NAVI request: {request.message[:100]}...")

        result = await process_request(
            message=request.message,
            workspace=request.workspace,
            context=request.context,
        )

        return NaviResponse(**result)

    except Exception as e:
        logger.error(f"❌ NAVI processing failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"NAVI processing failed: {str(e)}")


@router.post("/detect-project", response_model=ProjectDetectResponse)
async def detect_project_type(request: ProjectDetectRequest):
    """
    Detect project type, technologies, and dependencies.

    Example:
        POST /api/navi/detect-project
        {
            "workspace": "/path/to/project"
        }

    Returns:
        {
            "project_type": "react",
            "technologies": ["React", "TypeScript", "Vite"],
            "dependencies": {"react": "^18.2.0", "vite": "^5.0.0"},
            "package_manager": "npm"
        }
    """
    try:
        from backend.services.navi_engine import ProjectDetector

        project_type, technologies, dependencies = ProjectDetector.detect(
            request.workspace
        )

        # Detect package manager
        import os

        if os.path.exists(os.path.join(request.workspace, "yarn.lock")):
            package_manager = "yarn"
        elif os.path.exists(os.path.join(request.workspace, "pnpm-lock.yaml")):
            package_manager = "pnpm"
        elif os.path.exists(os.path.join(request.workspace, "bun.lockb")):
            package_manager = "bun"
        elif os.path.exists(os.path.join(request.workspace, "package-lock.json")):
            package_manager = "npm"
        elif os.path.exists(os.path.join(request.workspace, "requirements.txt")):
            package_manager = "pip"
        elif os.path.exists(os.path.join(request.workspace, "Pipfile")):
            package_manager = "pipenv"
        elif os.path.exists(os.path.join(request.workspace, "Cargo.lock")):
            package_manager = "cargo"
        elif os.path.exists(os.path.join(request.workspace, "go.sum")):
            package_manager = "go"
        elif os.path.exists(os.path.join(request.workspace, "pom.xml")):
            package_manager = "maven"
        elif os.path.exists(os.path.join(request.workspace, "build.gradle")):
            package_manager = "gradle"
        else:
            package_manager = "unknown"

        return ProjectDetectResponse(
            project_type=project_type,
            technologies=technologies,
            dependencies=dependencies,
            package_manager=package_manager,
        )

    except Exception as e:
        logger.error(f"❌ Project detection failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Project detection failed: {str(e)}"
        )


@router.post("/stream")
async def stream_navi_response(request: StreamRequest):
    """
    Streaming endpoint with Server-Sent Events (SSE).
    Returns real-time updates as NAVI processes the request.

    Example:
        POST /api/navi/stream
        {
            "message": "create a dashboard page with charts",
            "workspace": "/path/to/project"
        }

    Returns (SSE stream):
        data: {"type": "status", "message": "Analyzing project..."}
        data: {"type": "status", "message": "Generating Dashboard component..."}
        data: {"type": "file_created", "path": "src/pages/Dashboard.tsx"}
        data: {"type": "status", "message": "Installing dependencies..."}
        data: {"type": "dependency_installed", "package": "recharts"}
        data: {"type": "complete", "result": {...}}
    """

    async def event_generator():
        try:
            yield f'data: {json.dumps({"type": "status", "message": "Starting NAVI processing..."})}\n\n'
            await asyncio.sleep(0.1)

            yield f'data: {json.dumps({"type": "status", "message": "Analyzing project structure..."})}\n\n'
            await asyncio.sleep(0.1)

            # Process request
            result = await process_request(
                message=request.message,
                workspace=request.workspace,
                context=request.context,
            )

            # Send file creation events
            if result.get("files_created"):
                for file_path in result["files_created"]:
                    yield f'data: {json.dumps({"type": "file_created", "path": file_path})}\n\n'
                    await asyncio.sleep(0.1)

            # Send dependency installation events
            if result.get("dependencies_installed"):
                for package in result["dependencies_installed"]:
                    yield f'data: {json.dumps({"type": "dependency_installed", "package": package})}\n\n'
                    await asyncio.sleep(0.1)

            # Send git operation events
            if result.get("git_operations"):
                for operation in result["git_operations"]:
                    yield f'data: {json.dumps({"type": "git_operation", "operation": operation})}\n\n'
                    await asyncio.sleep(0.1)

            # Send final result
            yield f'data: {json.dumps({"type": "complete", "result": result})}\n\n'

        except Exception as e:
            logger.error(f"❌ Streaming failed: {str(e)}", exc_info=True)
            yield f'data: {json.dumps({"type": "error", "message": str(e)})}\n\n'

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/health")
async def health_check():
    """
    Health check endpoint.

    Returns:
        {
            "status": "healthy",
            "service": "navi",
            "version": "1.0.0"
        }
    """
    return {"status": "healthy", "service": "navi", "version": "1.0.0"}


@router.get("/supported-actions")
async def get_supported_actions():
    """
    Get list of supported NAVI actions.

    Returns:
        {
            "actions": [
                {
                    "name": "create_component",
                    "description": "Create a new component",
                    "examples": ["create a Button component", "make a LoginForm component"]
                },
                ...
            ]
        }
    """
    return {
        "actions": [
            {
                "name": "create_component",
                "description": "Create a new component with tests",
                "examples": [
                    "create a Button component",
                    "make a LoginForm component",
                    "add a UserCard component",
                ],
            },
            {
                "name": "create_page",
                "description": "Create a new page/route",
                "examples": [
                    "create a dashboard page",
                    "make a settings page",
                    "add a profile page",
                ],
            },
            {
                "name": "create_api",
                "description": "Create API endpoint/route",
                "examples": [
                    "create a users API endpoint",
                    "make a /auth/login endpoint",
                    "add a products API",
                ],
            },
            {
                "name": "add_feature",
                "description": "Add a feature to existing code",
                "examples": [
                    "add dark mode support",
                    "add authentication",
                    "add search functionality",
                ],
            },
            {
                "name": "refactor_code",
                "description": "Refactor existing code",
                "examples": [
                    "refactor UserList component",
                    "extract reusable logic from Header",
                    "improve error handling in api.ts",
                ],
            },
            {
                "name": "fix_error",
                "description": "Fix bugs and errors",
                "examples": [
                    "fix the login error",
                    "debug the API call issue",
                    "resolve the type error in Header",
                ],
            },
            {
                "name": "install_package",
                "description": "Install dependencies",
                "examples": [
                    "install axios",
                    "add react-router-dom",
                    "install date-fns as dev dependency",
                ],
            },
            {
                "name": "run_command",
                "description": "Run terminal commands",
                "examples": ["run npm test", "build the project", "start dev server"],
            },
            {
                "name": "git_commit",
                "description": "Commit changes to git",
                "examples": [
                    "commit these changes",
                    "create a commit with message 'Add login'",
                    "commit and push",
                ],
            },
            {
                "name": "create_pr",
                "description": "Create pull request",
                "examples": [
                    "create a PR",
                    "make a pull request",
                    "open PR for review",
                ],
            },
        ]
    }
