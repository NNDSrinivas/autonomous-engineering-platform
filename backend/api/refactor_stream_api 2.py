"""
Refactor Stream API - SSE Live Streaming for Autonomous Refactoring

This module provides Server-Sent Events (SSE) streaming for real-time refactor execution,
matching the experience of Cursor AI Edit and Replit Agent with live progress updates.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import AsyncGenerator, Dict, Any, List, Optional
import asyncio
import json
import time
import traceback
from pathlib import Path

# from ..refactor_engine.planner.python_planner import PythonPlanner
# from ..refactor_engine.planner.node_planner import NodePlanner


class PythonPlanner:
    def __init__(self, path):
        pass

    def analyze_files(self, files):
        return {}

    def analyze_workspace(self):
        return {}

    def create_execution_plan(self, instruction, analysis):
        return {}


class NodePlanner:
    def __init__(self, path):
        pass

    def analyze_files(self, files):
        return {}

    def analyze_workspace(self):
        return {}

    def create_execution_plan(self, instruction, analysis):
        return {}


# Placeholder classes for missing modules
class PatchBuilder:
    def __init__(self, path):
        pass

    def build_from_plan(self, plan):
        return {}


class DiffEngine:
    def __init__(self):
        pass

    def generate_diff(self, original, modified):
        return ""


class PatchRunner:
    def __init__(self, path):
        pass

    def apply_patch(self, patch):
        return type(
            "Result", (), {"success": True, "applied_files": [], "error_message": None}
        )()


class PatchSerializer:
    def __init__(self):
        pass

    def serialize_patch_plan(self, plan, format="json"):
        return {}

    def serialize_patch_result(self, result, edits):
        return {}

    def serialize_refactor_progress(self, stage, progress, message):
        return {"stage": stage, "progress": progress, "message": message}

    def serialize_error_response(self, error, stage):
        return {"error": str(error), "stage": stage}


class NodeASTClient:
    def __init__(self):
        pass

    async def run_transform(self, file_path, project_root, command):
        return {"success": True}


# from ..refactor_engine.patch.patch_builder import PatchBuilder
# from ..refactor_engine.patch.diff_engine import DiffEngine
# from ..refactor_engine.patch.patch_runner import PatchRunner
# from ..refactor_engine.patch.patch_serializer import PatchSerializer
# from ..refactor_engine.node_bridge.node_ast_client import NodeASTClient


# Pydantic Models
class StreamRefactorRequest(BaseModel):
    """Request model for SSE refactor streaming."""

    instruction: str
    project_root: str
    target_files: Optional[List[str]] = None
    language: Optional[str] = "auto"
    dry_run: bool = False
    options: Dict[str, Any] = {}


# Router setup
router = APIRouter(prefix="/api/refactor", tags=["refactor-streaming"])


# -----------------------------
# SSE Helper Functions
# -----------------------------


def sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """Format data as Server-Sent Event."""
    return f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"


def sse_heartbeat() -> str:
    """Send heartbeat to keep connection alive."""
    return f"event: heartbeat\ndata: {json.dumps({'timestamp': time.time()})}\n\n"


# -----------------------------
# Main SSE Streaming Endpoint
# -----------------------------


@router.post("/stream")
async def stream_refactor_execution(request: Request):
    """
    SSE endpoint for real-time refactor streaming.

    Provides live updates during:
    - Code analysis and planning
    - AST transformations
    - Diff generation
    - Patch application

    Events emitted:
    - liveProgress: High-level progress updates
    - refactorPlan: Complete execution plan
    - fileStart: Beginning file analysis
    - fileASTEdit: AST transformation result
    - diffChunk: Unified diff streaming
    - issue: Issues and suggestions
    - patchBundle: Final multi-file patch
    - done: Stream completion
    - error: Error occurred
    """

    async def refactor_stream() -> AsyncGenerator[str, None]:
        start_time = time.time()

        try:
            # Parse request body
            body = await request.json()
            stream_request = StreamRefactorRequest(**body)

            instruction = stream_request.instruction
            project_root = Path(stream_request.project_root)
            target_files = stream_request.target_files
            language = stream_request.language
            dry_run = stream_request.dry_run

            # Validate project root
            if not project_root.exists():
                yield sse_event(
                    "error",
                    {
                        "message": f"Project root does not exist: {project_root}",
                        "stage": "validation",
                    },
                )
                return

            # Initialize components
            serializer = PatchSerializer()

            # ---------------------------------------------------------
            # STAGE 1: PLANNING
            # ---------------------------------------------------------
            yield sse_event(
                "liveProgress",
                {
                    "stage": "planning",
                    "progress": 0.0,
                    "message": "🧠 Analyzing codebase and planning refactor...",
                    "details": {"instruction": instruction},
                },
            )

            # Auto-detect language if needed
            if language == "auto":
                language = await detect_primary_language(project_root)
                yield sse_event(
                    "liveProgress",
                    {
                        "stage": "planning",
                        "progress": 0.1,
                        "message": f"📝 Detected primary language: {language}",
                        "details": {"language": language},
                    },
                )

            # Choose appropriate planner
            if language == "python":
                planner = PythonPlanner(str(project_root))
            elif language in ["javascript", "typescript"]:
                planner = NodePlanner(str(project_root))
            else:
                yield sse_event(
                    "error",
                    {
                        "message": f"Unsupported language: {language}",
                        "stage": "planning",
                    },
                )
                return

            # Analyze workspace or specific files
            yield sse_event(
                "liveProgress",
                {
                    "stage": "planning",
                    "progress": 0.2,
                    "message": "🔍 Analyzing code structure...",
                    "details": {"analyzing": target_files or "entire workspace"},
                },
            )

            if target_files:
                analysis_result = await asyncio.to_thread(
                    planner.analyze_files, target_files
                )
                analyzed_files = target_files
            else:
                analysis_result = await asyncio.to_thread(planner.analyze_workspace)
                analyzed_files = analysis_result.get("analyzed_files", [])

            yield sse_event(
                "liveProgress",
                {
                    "stage": "planning",
                    "progress": 0.4,
                    "message": f"📊 Analyzed {len(analyzed_files)} files",
                    "details": {"file_count": len(analyzed_files)},
                },
            )

            # Create execution plan
            yield sse_event(
                "liveProgress",
                {
                    "stage": "planning",
                    "progress": 0.6,
                    "message": "⚡ Creating execution plan...",
                    "details": {},
                },
            )

            execution_plan = await asyncio.to_thread(
                planner.create_execution_plan, instruction, analysis_result
            )

            # Emit the complete refactor plan
            yield sse_event(
                "refactorPlan",
                {
                    "instruction": instruction,
                    "language": language,
                    "analyzed_files": analyzed_files,
                    "execution_plan": execution_plan,
                    "estimated_changes": len(execution_plan.get("steps", [])),
                    "complexity": _estimate_complexity(execution_plan),
                },
            )

            yield sse_event(
                "liveProgress",
                {
                    "stage": "planning",
                    "progress": 1.0,
                    "message": f"✅ Plan created: {len(execution_plan.get('steps', []))} transformations",
                    "details": {"step_count": len(execution_plan.get("steps", []))},
                },
            )

            # ---------------------------------------------------------
            # STAGE 2: AST TRANSFORMATIONS
            # ---------------------------------------------------------
            yield sse_event(
                "liveProgress",
                {
                    "stage": "transforming",
                    "progress": 0.0,
                    "message": "🔄 Executing AST transformations...",
                    "details": {},
                },
            )

            # Initialize AST clients
            node_client = (
                NodeASTClient() if language in ["javascript", "typescript"] else None
            )

            # Execute transformations step by step
            transformation_results = []
            steps = execution_plan.get("steps", [])

            for i, step in enumerate(steps):
                step_progress = i / len(steps) if steps else 0

                # Start file transformation
                yield sse_event(
                    "fileStart",
                    {
                        "file": step.get("file"),
                        "command": step.get("command"),
                        "description": step.get("description"),
                        "progress": step_progress,
                    },
                )

                yield sse_event(
                    "liveProgress",
                    {
                        "stage": "transforming",
                        "progress": step_progress,
                        "message": f"🔧 Transforming {Path(step.get('file', '')).name}...",
                        "details": {"current_file": step.get("file")},
                    },
                )

                # Execute transformation based on language
                try:
                    if language == "python":
                        # Use Python AST transformation
                        result = await _execute_python_transform(step, project_root)
                    elif language in ["javascript", "typescript"] and node_client:
                        # Use Node AST transformation
                        result = await node_client.run_transform(
                            file_path=step.get("file"),
                            project_root=str(project_root),
                            command=step,
                        )
                    else:
                        raise ValueError(f"No transformer available for {language}")

                    # Emit AST edit result
                    yield sse_event(
                        "fileASTEdit",
                        {
                            "file": step.get("file"),
                            "command": step.get("command"),
                            "before": result.get("before", ""),
                            "after": result.get("after", ""),
                            "description": step.get("description"),
                            "success": True,
                        },
                    )

                    transformation_results.append(
                        {
                            "file": step.get("file"),
                            "before": result.get("before", ""),
                            "after": result.get("after", ""),
                            "description": step.get("description"),
                        }
                    )

                except Exception as e:
                    yield sse_event(
                        "issue",
                        {
                            "type": "transformation_error",
                            "file": step.get("file"),
                            "message": str(e),
                            "severity": "error",
                        },
                    )

                    # Continue with other files
                    continue

            yield sse_event(
                "liveProgress",
                {
                    "stage": "transforming",
                    "progress": 1.0,
                    "message": f"✅ Completed {len(transformation_results)} transformations",
                    "details": {"completed_count": len(transformation_results)},
                },
            )

            # ---------------------------------------------------------
            # STAGE 3: PATCH GENERATION & DIFF STREAMING
            # ---------------------------------------------------------
            yield sse_event(
                "liveProgress",
                {
                    "stage": "generating",
                    "progress": 0.0,
                    "message": "📝 Building patches and generating diffs...",
                    "details": {},
                },
            )

            # Build file edits from transformation results
            patch_builder = PatchBuilder(str(project_root))
            file_edits = await asyncio.to_thread(
                patch_builder.build_from_results, transformation_results
            )

            yield sse_event(
                "liveProgress",
                {
                    "stage": "generating",
                    "progress": 0.3,
                    "message": f"🔨 Created {len(file_edits)} file patches",
                    "details": {"patch_count": len(file_edits)},
                },
            )

            # Generate and stream diffs
            diff_engine = DiffEngine()
            all_diffs = []

            for i, file_edit in enumerate(file_edits):
                if not file_edit.has_changes():
                    continue

                diff_progress = 0.3 + (0.6 * i / len(file_edits))

                yield sse_event(
                    "liveProgress",
                    {
                        "stage": "generating",
                        "progress": diff_progress,
                        "message": f"📊 Generating diff for {Path(file_edit.file_path).name}...",
                        "details": {"current_file": file_edit.file_path},
                    },
                )

                # Generate unified diff
                unified_diff = diff_engine.generate_unified_diff(
                    file_edit.before_content or "",
                    file_edit.after_content or "",
                    file_edit.file_path,
                )

                # Stream diff chunk
                yield sse_event(
                    "diffChunk",
                    {
                        "file": file_edit.file_path,
                        "description": next(
                            (
                                r["description"]
                                for r in transformation_results
                                if r["file"] == file_edit.file_path
                            ),
                            "File modification",
                        ),
                        "diff": unified_diff,
                        "change_summary": file_edit.get_change_summary(),
                        "change_type": file_edit.get_change_type(),
                    },
                )

                all_diffs.append(
                    {
                        "file": file_edit.file_path,
                        "diff": unified_diff,
                        "change_summary": file_edit.get_change_summary(),
                    }
                )

            yield sse_event(
                "liveProgress",
                {
                    "stage": "generating",
                    "progress": 1.0,
                    "message": f"✅ Generated {len(all_diffs)} diffs",
                    "details": {"diff_count": len(all_diffs)},
                },
            )

            # ---------------------------------------------------------
            # STAGE 4: PATCH BUNDLE & APPLICATION (if not dry run)
            # ---------------------------------------------------------

            # Create final patch bundle
            patch_data = serializer.serialize_patch_plan(
                file_edits, include_diffs=True, diff_format="unified"
            )

            yield sse_event(
                "patchBundle",
                {
                    "files": [
                        {
                            "path": edit.file_path,
                            "change_type": edit.get_change_type(),
                            "description": next(
                                (
                                    r["description"]
                                    for r in transformation_results
                                    if r["file"] == edit.file_path
                                ),
                                "File modification",
                            ),
                            "diff": diff["diff"],
                            "change_summary": edit.get_change_summary(),
                        }
                        for edit, diff in zip(file_edits, all_diffs)
                        if edit.has_changes()
                    ],
                    "statistics": patch_data["statistics"],
                    "dry_run": dry_run,
                    "ready_to_apply": not dry_run,
                },
            )

            # Apply patches if not dry run
            if not dry_run:
                yield sse_event(
                    "liveProgress",
                    {
                        "stage": "applying",
                        "progress": 0.0,
                        "message": "🚀 Applying patches safely...",
                        "details": {"atomic": True},
                    },
                )

                patch_runner = PatchRunner(str(project_root))
                result = await asyncio.to_thread(
                    patch_runner.apply_patch, file_edits, dry_run=False, atomic=True
                )

                if result.success:
                    yield sse_event(
                        "liveProgress",
                        {
                            "stage": "applying",
                            "progress": 1.0,
                            "message": f"✅ Successfully applied {len(result.applied_files)} changes",
                            "details": {
                                "applied_files": len(result.applied_files),
                                "backup_id": result.backup_id,
                            },
                        },
                    )
                else:
                    yield sse_event(
                        "issue",
                        {
                            "type": "application_error",
                            "message": result.error_message,
                            "failed_files": result.failed_files,
                            "severity": "error",
                        },
                    )

            # ---------------------------------------------------------
            # COMPLETION
            # ---------------------------------------------------------
            execution_time = time.time() - start_time

            yield sse_event(
                "done",
                {
                    "success": True,
                    "execution_time": execution_time,
                    "files_transformed": len(transformation_results),
                    "patches_generated": len(file_edits),
                    "diffs_created": len(all_diffs),
                    "dry_run": dry_run,
                    "message": "🎉 Refactor completed successfully!",
                },
            )

        except Exception as e:
            # Handle any unexpected errors
            error_details = {
                "message": str(e),
                "type": type(e).__name__,
                "stage": "execution",
                "traceback": traceback.format_exc(),
            }

            yield sse_event("error", error_details)

            yield sse_event(
                "done",
                {"success": False, "error": str(e), "message": "❌ Refactor failed"},
            )

    return StreamingResponse(
        refactor_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
    )


# -----------------------------
# Helper Functions
# -----------------------------


async def detect_primary_language(project_root: Path) -> str:
    """Auto-detect the primary programming language in the project."""
    language_indicators = {
        "python": [".py", "requirements.txt", "pyproject.toml", "setup.py"],
        "javascript": [".js", ".jsx", "package.json"],
        "typescript": [".ts", ".tsx", "tsconfig.json"],
    }

    found_files = {}

    # Scan for language indicators
    for file_path in project_root.rglob("*"):
        if file_path.is_file():
            for language, indicators in language_indicators.items():
                if any(
                    str(file_path).endswith(ext) or file_path.name == ext
                    for ext in indicators
                ):
                    found_files[language] = found_files.get(language, 0) + 1

    if not found_files:
        return "unknown"

    return max(found_files.keys(), key=lambda x: found_files[x])


async def _execute_python_transform(
    step: Dict[str, Any], project_root: Path
) -> Dict[str, Any]:
    """Execute Python AST transformation."""
    # This would integrate with your Python AST engine
    file_path = project_root / step.get("file", "")

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    before_content = file_path.read_text(encoding="utf-8")

    # Placeholder for actual Python AST transformation
    # This should integrate with your Python planner's transformation logic
    after_content = before_content  # Replace with actual transformation

    return {
        "before": before_content,
        "after": after_content,
        "file": str(file_path),
        "success": True,
    }


def _estimate_complexity(execution_plan: Dict[str, Any]) -> str:
    """Estimate refactor complexity based on execution plan."""
    steps = execution_plan.get("steps", [])

    if len(steps) == 0:
        return "minimal"
    elif len(steps) <= 3:
        return "low"
    elif len(steps) <= 10:
        return "medium"
    elif len(steps) <= 25:
        return "high"
    else:
        return "extensive"


# -----------------------------
# Additional SSE Endpoints
# -----------------------------


@router.get("/stream/test")
async def test_sse_connection():
    """Test SSE connection with simple heartbeat."""

    async def heartbeat_stream():
        for i in range(10):
            yield sse_event(
                "heartbeat",
                {"count": i, "message": f"Heartbeat {i}", "timestamp": time.time()},
            )
            await asyncio.sleep(1)

        yield sse_event("done", {"message": "Test completed"})

    return StreamingResponse(heartbeat_stream(), media_type="text/event-stream")


@router.post("/stream/validate")
async def validate_refactor_request(request: StreamRefactorRequest):
    """Validate refactor request without executing."""
    try:
        project_root = Path(request.project_root)

        if not project_root.exists():
            raise HTTPException(status_code=400, detail="Project root does not exist")

        # Detect language
        language = await detect_primary_language(project_root)

        # Basic validation
        validation_result = {
            "valid": True,
            "project_root": str(project_root),
            "detected_language": language,
            "target_files": request.target_files,
            "estimated_complexity": "unknown",
            "warnings": [],
        }

        # Add warnings for unsupported languages
        if language not in ["python", "javascript", "typescript"]:
            validation_result["warnings"].append(f"Limited support for {language}")

        return validation_result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
