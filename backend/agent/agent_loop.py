"""
NAVI Agent Loop - The Core 7-Stage Reasoning Pipeline

This is the main entry point for NAVI's autonomous agent behavior.
Called by /api/navi/chat for every user message.

Pipeline stages:
1. Load user state (what were they doing?)
2. Build full context (workspace + org + memory)
2.5. Process image attachments for vision analysis (NEW)
3. Classify intent (what do they want?)
4. Generate plan (how to accomplish it?)
5. Check approval (destructive actions need confirmation)
6. Execute or respond (tools vs. chat)
7. Update state (remember for next turn)
8. Verify with tests (if code was modified) (NEW)
"""

import logging
import time
import json
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from dataclasses import asdict

if TYPE_CHECKING:
    from backend.agent.navi_settings import NaviSettings

from backend.agent.context_builder import build_context
from backend.agent.memory_retriever import retrieve_memories
from backend.agent.org_retriever import retrieve_org_context
from backend.agent.workspace_retriever import retrieve_workspace_context
from backend.agent.intent_classifier import IntentClassifier
from backend.ai.intent_llm_classifier import LLMIntentClassifier
from backend.agent.tool_executor import execute_tool, execute_tool_with_sources
from backend.agent.state_manager import (
    get_user_state,
    update_user_state,
    clear_user_state,
)
from backend.services.llm import call_llm

logger = logging.getLogger(__name__)


def _extract_images_from_attachments(
    attachments: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    Extract image attachments for vision processing.

    Args:
        attachments: List of attachments from the request

    Returns:
        List of image attachments with kind='image' and base64 content
    """
    if not attachments:
        return []
    return [a for a in attachments if a.get("kind") == "image"]


async def _analyze_images_with_vision(
    images: List[Dict[str, Any]], message: str, workspace_root: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyze images using the vision service.

    Args:
        images: List of image attachments with base64 content
        message: User's message for context
        workspace_root: Optional workspace path for code generation context

    Returns:
        Dict containing image analysis results
    """
    if not images:
        return {}

    try:
        from backend.services.vision_service import analyze_ui_screenshot

        # Take the first image for now (can be extended for multiple)
        first_image = images[0]
        image_content = first_image.get("content", "")

        # Remove data URL prefix if present
        if image_content.startswith("data:"):
            # Format: data:image/png;base64,<base64_data>
            image_content = image_content.split(",", 1)[-1]

        # Analyze the UI screenshot using the public API
        analysis = await analyze_ui_screenshot(
            image_data=image_content,
            context=message,
            provider="anthropic",  # Default to Anthropic/Claude vision
        )

        logger.info("[AGENT] Vision analysis completed: %d chars", len(str(analysis)))

        # Convert analysis dict to context string for LLM
        analysis_text = _format_ui_analysis_for_context(analysis)

        return {
            "has_images": True,
            "image_count": len(images),
            "analysis": analysis_text,
            "analysis_raw": analysis,
            "image_type": first_image.get("type", "screenshot"),
        }

    except ImportError:
        logger.warning("[AGENT] Vision service not available")
        return {
            "has_images": True,
            "image_count": len(images),
            "analysis_error": "Vision service not available",
        }
    except Exception as e:
        logger.error("[AGENT] Vision analysis failed: %s", e)
        return {
            "has_images": True,
            "image_count": len(images),
            "analysis_error": str(e),
        }


def _format_ui_analysis_for_context(analysis: Dict[str, Any]) -> str:
    """
    Format UI analysis dict as a readable string for LLM context.

    Args:
        analysis: The analysis dict from vision service

    Returns:
        Formatted string for LLM context
    """
    parts = ["=== UI ANALYSIS FROM SCREENSHOT ==="]

    if analysis.get("description"):
        parts.append(f"\n**Description**: {analysis['description']}")

    if analysis.get("layout"):
        layout = analysis["layout"]
        parts.append(f"\n**Layout**: {layout.get('layout_type', 'unknown')} layout")
        if layout.get("columns", 1) > 1:
            parts.append(f"  - Columns: {layout['columns']}")

    if analysis.get("components"):
        parts.append("\n**Components Detected**:")
        for comp in analysis["components"]:
            comp_type = comp.get("type", "unknown")
            comp_desc = comp.get("description", "")
            parts.append(f"  - {comp_type}: {comp_desc}")

    if analysis.get("color_scheme"):
        colors = analysis["color_scheme"]
        color_str = ", ".join(f"{k}: {v}" for k, v in colors.items())
        parts.append(f"\n**Colors**: {color_str}")

    if analysis.get("implementation_hints"):
        parts.append("\n**Implementation Hints**:")
        for hint in analysis["implementation_hints"]:
            parts.append(f"  - {hint}")

    suggested_framework = analysis.get("suggested_framework", "react")
    suggested_css = analysis.get("suggested_css", "tailwind")
    parts.append(f"\n**Suggested Stack**: {suggested_framework} + {suggested_css}")

    return "\n".join(parts)


async def _verify_with_tests(
    workspace_path: str, modified_files: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Run tests to verify code changes work correctly.

    This is called after code modifications to ensure the changes don't break anything.

    Args:
        workspace_path: Path to the workspace
        modified_files: List of files that were modified (for targeted test runs)

    Returns:
        Dict with test results including success status, counts, and any failures
    """
    try:
        from backend.services.test_executor import (
            run_tests,
            detect_framework,
        )

        # First check if there's a test framework
        framework = detect_framework(workspace_path)
        if framework == "unknown":
            logger.info(
                "[AGENT] No test framework detected, skipping test verification"
            )
            return {
                "skipped": True,
                "reason": "no_test_framework",
                "message": "No test framework detected in workspace",
            }

        logger.info("[AGENT] Running tests with framework: %s", framework)

        # Run tests with coverage
        result = await run_tests(
            workspace_path,
            with_coverage=True,
        )

        success = result.get("success", False)
        total = result.get("total", 0)
        passed = result.get("passed", 0)
        failed = result.get("failed", 0)

        logger.info(
            "[AGENT] Test results: %d/%d passed (%s)",
            passed,
            total,
            "SUCCESS" if success else "FAILED",
        )

        return {
            "success": success,
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": result.get("skipped", 0),
            "coverage_percent": result.get("coverage_percent"),
            "failed_tests": result.get("failed_tests", []),
            "fix_suggestions": result.get("fix_suggestions", []),
            "framework": framework,
        }

    except ImportError:
        logger.warning("[AGENT] Test executor not available")
        return {
            "skipped": True,
            "reason": "test_executor_unavailable",
            "message": "Test executor service not available",
        }
    except Exception as e:
        logger.error("[AGENT] Test verification failed: %s", e)
        return {
            "skipped": True,
            "reason": "execution_error",
            "message": f"Error running tests: {str(e)}",
        }


def _format_test_results_for_response(test_result: Dict[str, Any]) -> str:
    """
    Format test results as a human-readable string for inclusion in response.

    Args:
        test_result: The test result dict from _verify_with_tests

    Returns:
        Formatted string describing test results
    """
    if test_result.get("skipped"):
        return f"\n\n**Tests**: {test_result.get('message', 'Skipped')}"

    success = test_result.get("success", False)
    total = test_result.get("total", 0)
    failed = test_result.get("failed", 0)
    coverage = test_result.get("coverage_percent")

    parts = ["\n\n**Test Results**:"]

    if success:
        parts.append(f"✅ All {total} tests passed")
    else:
        parts.append(f"❌ {failed}/{total} tests failed")

    if coverage is not None:
        parts.append(f"📊 Coverage: {coverage:.1f}%")

    # Include failed test details
    failed_tests = test_result.get("failed_tests", [])
    if failed_tests:
        parts.append("\n**Failed Tests**:")
        for ft in failed_tests[:5]:  # Limit to first 5
            parts.append(f"  - {ft.get('name', 'unknown')}")
            if ft.get("error_message"):
                error_preview = ft["error_message"][:100]
                parts.append(f"    Error: {error_preview}...")

        if len(failed_tests) > 5:
            parts.append(f"  ... and {len(failed_tests) - 5} more")

    # Include fix suggestions
    suggestions = test_result.get("fix_suggestions", [])
    if suggestions:
        parts.append("\n**Suggested Fixes**:")
        for sugg in suggestions[:3]:
            analysis = sugg.get("analysis", {})
            for fix in analysis.get("suggested_fixes", [])[:2]:
                parts.append(f"  - {fix}")

    return "\n".join(parts)


async def _analyze_errors_with_debugger(
    error_output: str,
    workspace_path: str,
) -> Dict[str, Any]:
    """
    Analyze error output using the comprehensive debugger.

    This provides deep error analysis with code context for complex debugging.

    Args:
        error_output: The error message, stack trace, or compiler output
        workspace_path: Path to the workspace for code context

    Returns:
        Dict with structured error analysis, suggestions, and auto-fixes
    """
    try:
        from backend.services.comprehensive_debugger import analyze_errors

        logger.info("[AGENT] Running comprehensive error analysis...")

        analysis = await analyze_errors(
            error_output=error_output,
            workspace_path=workspace_path,
        )

        # Enhance with code context for each error
        enhanced_errors = []
        for error in analysis.get("errors", [])[:5]:  # Limit to first 5
            enhanced = dict(error)

            # Try to read code context if we have file and line info
            if error.get("file") and error.get("line"):
                code_context = await _get_code_context(
                    workspace_path, error["file"], error["line"]
                )
                if code_context:
                    enhanced["code_context"] = code_context

            enhanced_errors.append(enhanced)

        analysis["errors"] = enhanced_errors

        logger.info(
            "[AGENT] Error analysis complete: %d errors, %d warnings",
            len(analysis.get("errors", [])),
            len(analysis.get("warnings", [])),
        )

        return analysis

    except ImportError:
        logger.warning("[AGENT] Comprehensive debugger not available")
        return {
            "errors": [],
            "warnings": [],
            "analysis_error": "Debugger not available",
        }
    except Exception as e:
        logger.error("[AGENT] Error analysis failed: %s", e)
        return {"errors": [], "warnings": [], "analysis_error": str(e)}


async def _get_code_context(
    workspace_path: str, file_path: str, line_number: int, context_lines: int = 5
) -> Optional[str]:
    """
    Get code context around a specific line for error analysis.

    Args:
        workspace_path: Root workspace path
        file_path: Path to the file (may be relative or absolute)
        line_number: Line number to get context around
        context_lines: Number of lines before/after to include

    Returns:
        Code snippet with line numbers, or None if file not accessible
    """
    import os

    try:
        # Handle relative paths
        if not os.path.isabs(file_path):
            full_path = os.path.join(workspace_path, file_path)
        else:
            full_path = file_path

        if not os.path.exists(full_path):
            return None

        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        # Calculate line range
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)

        # Format with line numbers
        context_parts = []
        for i in range(start, end):
            line_num = i + 1
            prefix = ">>> " if line_num == line_number else "    "
            context_parts.append(f"{prefix}{line_num:4d} | {lines[i].rstrip()}")

        return "\n".join(context_parts)

    except Exception as e:
        logger.debug("[AGENT] Failed to get code context: %s", e)
        return None


def _format_debug_analysis_for_response(analysis: Dict[str, Any]) -> str:
    """
    Format debug analysis as a human-readable string for inclusion in response.

    Args:
        analysis: The analysis dict from _analyze_errors_with_debugger

    Returns:
        Formatted string with error analysis and suggestions
    """
    if analysis.get("analysis_error"):
        return f"\n\n**Debug Analysis**: {analysis['analysis_error']}"

    errors = analysis.get("errors", [])
    warnings = analysis.get("warnings", [])

    if not errors and not warnings:
        return "\n\n**Debug Analysis**: No errors detected"

    parts = ["\n\n**Debug Analysis**:"]

    # Summary
    summary = analysis.get("summary", {})
    if summary:
        parts.append(
            f"Found {summary.get('total_errors', 0)} error(s), {summary.get('total_warnings', 0)} warning(s)"
        )

    # Detailed errors
    for i, error in enumerate(errors[:3], 1):
        parts.append(f"\n**Error {i}: {error.get('error_type', 'Unknown')}**")
        parts.append(f"  Message: {error.get('message', 'No message')[:200]}")

        if error.get("file"):
            location = f"{error['file']}"
            if error.get("line"):
                location += f":{error['line']}"
            parts.append(f"  Location: {location}")

        if error.get("code_context"):
            parts.append(f"  Code context:\n```\n{error['code_context']}\n```")

        # Suggestions for this error
        suggestions = error.get("suggestions", [])
        if suggestions:
            parts.append("  Suggestions:")
            for sugg in suggestions[:3]:
                parts.append(f"    - {sugg}")

    # Auto-fixes
    auto_fixes = analysis.get("auto_fixes", [])
    if auto_fixes:
        parts.append("\n**Suggested Commands**:")
        for fix in auto_fixes[:3]:
            parts.append(
                f"  - `{fix.get('command', '')}` - {fix.get('description', '')}"
            )

    return "\n".join(parts)


def _generate_approval_message(grounding_result, plan) -> str:
    """
    Generate an intelligent approval message based on grounded task and plan.

    Args:
        grounding_result: The grounding result from task grounder
        plan: The generated plan

    Returns:
        Formatted approval message for user
    """
    # Default fallback message
    approval_message = (
        plan.summary or "I have a workspace plan to help with that. Should I proceed?"
    )

    if (
        grounding_result.type == "ready"
        and grounding_result.task.intent == "FIX_PROBLEMS"
    ):
        # Enhanced message for fix problems tasks
        task = grounding_result.task
        inputs = task.inputs

        total_count = inputs.get("total_count", 0)
        error_count = inputs.get("error_count", 0)
        warning_count = inputs.get("warning_count", 0)
        affected_files = inputs.get("affected_files", [])

        # Generate intelligent message
        problem_desc = []
        if error_count > 0:
            problem_desc.append(f"{error_count} error{'s' if error_count != 1 else ''}")
        if warning_count > 0:
            problem_desc.append(
                f"{warning_count} warning{'s' if warning_count != 1 else ''}"
            )

        problem_text = (
            " and ".join(problem_desc)
            if problem_desc
            else f"{total_count} problem{'s' if total_count != 1 else ''}"
        )

        approval_message = f"I found {problem_text} in your workspace."

        if affected_files:
            approval_message += "\n\nAffected files:\n" + "\n".join(
                f"• {file}" for file in affected_files[:5]
            )
            if len(affected_files) > 5:
                approval_message += f"\n• ...and {len(affected_files) - 5} more"

        approval_message += "\n\nI can analyze these issues and propose fixes.\n\nDo you want me to proceed?"

    return approval_message


def _shape_actions_from_plan(plan) -> List[Dict[str, Any]]:
    """
    Convert planner steps into workspace-ready actions.

    Each action looks like:

    {
      "id": "step-1",
      "title": "Analyze user requirements",
      "description": "...same as title for now...",
      "tool": "repo.inspect",
      "arguments": {...},          # original arguments
      "type": "fileEdit" | "workspaceRead" | "task" | "generic",
      "filePath": "src/main.ts",   # when applicable
      "content": "diff/contents",  # when applicable
    }
    """
    actions: List[Dict[str, Any]] = []

    if not plan or not getattr(plan, "steps", None):
        return actions

    for idx, step in enumerate(plan.steps):
        # Step might be a dataclass – normalize to dict-ish access
        try:
            step_dict = asdict(step)
        except Exception:  # noqa: BLE001
            # Fall back to attribute-based access
            step_dict = {
                "id": getattr(step, "id", None),
                "description": getattr(step, "description", None),
                "tool": getattr(step, "tool", None),
                "arguments": getattr(step, "arguments", None),
            }

        tool = step_dict.get("tool") or ""
        args = step_dict.get("arguments") or step_dict.get("args") or {}  # be forgiving

        # Infer basic type + file metadata
        step_type = "generic"
        file_path: Optional[str] = None
        content: Optional[str] = None

        # File-editing tools
        if tool in {
            "code.apply_patch",
            "code.write_file",
            "code.create_file",
            "code.overwrite_file",
        }:
            step_type = "fileEdit"
            file_path = (
                args.get("path")
                or args.get("file_path")
                or args.get("filename")
                or args.get("file")
            )
            content = args.get("content") or args.get("patch") or None

        # Read-only workspace operations
        elif tool in {"repo.inspect", "code.read_files", "code.search"}:
            step_type = "workspaceRead"

        # Project-management tasks
        elif tool.startswith("pm."):
            step_type = "task"

        title = step_dict.get("description") or tool or f"Step {idx + 1}"

        actions.append(
            {
                "id": step_dict.get("id") or f"step-{idx + 1}",
                "title": title,
                "description": title,
                "tool": tool,
                "arguments": args,
                "type": step_type,
                "filePath": file_path,
                "content": content,
            }
        )

    return actions


def _looks_like_project_overview_question(text: str) -> bool:
    """
    Heuristic: is the user asking "what is this project / repo / codebase?"
    Used to trigger a repo.inspect + explanation flow.
    """
    if not text:
        return False

    text = text.lower()

    # Needs at least one "project/repo/codebase" keyword...
    project_keywords = ["project", "repo", "repository", "codebase", "service", "app"]
    if not any(k in text for k in project_keywords):
        return False

    # ...and at least one "explain/what/overview/structure" keyword.
    explain_keywords = [
        "what is",
        "what's",
        "whats",
        "about",
        "explain",
        "overview",
        "structure",
        "tell me",
        "describe",
        "summary",
        "summarise",
        "summarize",
    ]
    if not any(k in text for k in explain_keywords):
        return False

    return True


def _looks_like_implementation_request(text: str) -> bool:
    """
    Heuristic: is the user asking NAVI to implement/build/create something?
    Used to trigger plan mode workflow.
    """
    if not text:
        return False

    text = text.lower()

    # Implementation keywords
    impl_keywords = [
        "implement",
        "build",
        "create",
        "add",
        "develop",
        "make",
        "write",
        "setup",
        "set up",
        "configure",
        "integrate",
    ]

    # Feature keywords
    feature_keywords = [
        "feature",
        "functionality",
        "component",
        "module",
        "api",
        "endpoint",
        "page",
        "form",
        "service",
        "system",
        "authentication",
        "database",
        "migration",
    ]

    # Check for implementation verb
    has_impl_keyword = any(k in text for k in impl_keywords)

    # Check for feature noun OR sufficient length (complex request)
    has_feature_keyword = any(k in text for k in feature_keywords)
    is_complex_request = len(text.split()) > 10

    return has_impl_keyword and (has_feature_keyword or is_complex_request)


def _is_execution_mode_response(text: str, previous_state: Dict[str, Any]) -> bool:
    """
    Check if user is responding to execution mode choice.
    """
    if not previous_state:
        return False

    # Check if we're waiting for execution mode choice
    if previous_state.get("plan_mode_state", {}).get("waiting_for_mode_choice"):
        return True

    return False


def _is_approval_response(text: str, previous_state: Dict[str, Any]) -> bool:
    """
    Check if user is responding to an approval request.
    """
    if not previous_state:
        return False

    # Check if we're waiting for approval
    if previous_state.get("plan_mode_state", {}).get("waiting_for_approval"):
        return True

    return False


async def _handle_plan_mode_request(
    *,
    user_id: str,
    message: str,
    model: str,
    mode: str,
    db,
    started: float,
    attachments: Optional[List[Dict[str, Any]]] = None,
    workspace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Handle a request to implement a feature in plan mode.

    This:
    1. Analyzes the codebase
    2. Generates an implementation plan
    3. Presents the plan with execution options (based on user settings)
    """
    from backend.agent.plan_generator import generate_implementation_plan
    from backend.agent.plan_mode_controller import (
        generate_execution_options_message,
        PlanModeController,
    )
    from backend.agent.navi_settings import get_user_settings

    logger.info("[AGENT] Handling implementation request in plan mode")

    workspace_path = workspace.get("workspace_root") if workspace else "."

    # Load user settings
    settings = await get_user_settings(user_id, db)
    logger.info(
        "[AGENT] Loaded user settings: execution_style=%s",
        settings.execution_style.value,
    )

    # Generate implementation plan
    try:
        plan = await generate_implementation_plan(
            user_request=message,
            workspace_path=workspace_path,
            context={"attachments": attachments},
        )
    except Exception as e:
        logger.error("[AGENT] Plan generation failed: %s", e)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {
            "reply": f"I encountered an error while planning: {e}. Could you rephrase your request?",
            "actions": [],
            "should_stream": False,
            "state": {"error": str(e)},
            "duration_ms": elapsed_ms,
        }

    # Check if we should show the plan (based on settings)
    if not settings.should_show_plan():
        # Fully autonomous mode - skip to execution
        logger.info("[AGENT] Fully autonomous mode - skipping plan presentation")
        return await _execute_plan_with_mode(
            user_id=user_id,
            plan_data=plan.to_dict(),
            execution_mode="fully_autonomous",
            custom_instructions=None,
            original_request=message,
            model=model,
            mode=mode,
            db=db,
            started=started,
            workspace=workspace,
            settings=settings,
        )

    # Generate the execution options message
    options_message = generate_execution_options_message(plan)

    # Create plan mode controller state with user settings
    controller = PlanModeController(settings=settings)
    controller.set_plan(plan)

    elapsed_ms = int((time.monotonic() - started) * 1000)

    # Save state for next turn
    plan_mode_state = {
        "plan": plan.to_dict(),
        "waiting_for_mode_choice": True,
        "waiting_for_approval": False,
        "execution_mode": None,
    }

    # Update user state
    update_user_state(
        user_id,
        {
            "plan_mode_active": True,
            "plan_mode_state": plan_mode_state,
            "original_request": message,
        },
    )

    return {
        "reply": options_message,
        "actions": [],
        "should_stream": False,
        "state": {
            "plan_mode_active": True,
            "plan_mode_state": plan_mode_state,
        },
        "duration_ms": elapsed_ms,
    }


async def _handle_execution_mode_choice(
    *,
    user_id: str,
    message: str,
    previous_state: Dict[str, Any],
    model: str,
    mode: str,
    db,
    started: float,
    attachments: Optional[List[Dict[str, Any]]] = None,
    workspace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Handle user's choice of execution mode.

    Loads user settings to pass to plan execution.
    """
    from backend.agent.plan_mode_controller import (
        PlanModeController,
        parse_execution_choice,
    )
    from backend.agent.navi_settings import get_user_settings

    logger.info("[AGENT] Processing execution mode choice: %s", message[:50])

    # Load user settings
    settings = await get_user_settings(user_id, db)

    # Parse the user's choice
    exec_mode, custom_instructions = parse_execution_choice(message)

    # Rebuild plan from state
    plan_data = previous_state.get("plan_mode_state", {}).get("plan", {})

    # Update state with chosen mode
    plan_mode_state = previous_state.get("plan_mode_state", {})
    plan_mode_state["waiting_for_mode_choice"] = False
    plan_mode_state["execution_mode"] = exec_mode
    plan_mode_state["custom_instructions"] = custom_instructions

    # Create controller with the chosen mode and user settings
    controller = PlanModeController(settings=settings)
    controller.set_execution_mode(exec_mode, custom_instructions)

    # Build response based on mode
    mode_names = {
        "fully_autonomous": "Fully Autonomous",
        "with_approval_gates": "With Approval Gates",
        "custom": "Custom",
    }
    mode_name = mode_names.get(exec_mode, exec_mode)

    original_request = previous_state.get("original_request", "your feature")

    # Start execution
    if exec_mode == "fully_autonomous":
        reply = (
            f"**Execution Mode: {mode_name}**\n\n"
            f"Starting fully autonomous implementation of: {original_request}\n\n"
            f"I will execute all {plan_data.get('estimated_steps', 0)} steps automatically "
            f"and run tests to verify the implementation.\n\n"
            f"You can stop me at any time by saying 'stop' or 'pause'.\n\n"
            f"Starting execution..."
        )
        plan_mode_state["execution_started"] = True

    elif exec_mode == "with_approval_gates":
        reply = (
            f"**Execution Mode: {mode_name}**\n\n"
            f"Starting implementation of: {original_request}\n\n"
            f"I will pause before critical operations (file modifications, commands) "
            f"and ask for your approval.\n\n"
            f"Starting execution..."
        )
        plan_mode_state["execution_started"] = True

    else:  # custom
        reply = (
            f"**Execution Mode: Custom**\n\n"
            f"Custom instructions received: {custom_instructions}\n\n"
            f"Starting implementation of: {original_request}\n\n"
            f"I will follow your instructions as I work through the plan."
        )
        plan_mode_state["execution_started"] = True

    # Update state
    update_user_state(
        user_id,
        {
            "plan_mode_active": True,
            "plan_mode_state": plan_mode_state,
            "original_request": previous_state.get("original_request"),
        },
    )

    elapsed_ms = int((time.monotonic() - started) * 1000)

    # If execution started, kick off the iterative loop
    if plan_mode_state.get("execution_started"):
        # Use iterative mode for execution with user settings
        return await _execute_plan_with_mode(
            user_id=user_id,
            plan_data=plan_data,
            execution_mode=exec_mode,
            custom_instructions=custom_instructions,
            original_request=previous_state.get("original_request", ""),
            model=model,
            mode=mode,
            db=db,
            started=started,
            workspace=workspace,
            settings=settings,  # Pass user settings for approval decisions
        )

    return {
        "reply": reply,
        "actions": [],
        "should_stream": False,
        "state": {
            "plan_mode_active": True,
            "plan_mode_state": plan_mode_state,
        },
        "duration_ms": elapsed_ms,
    }


async def _execute_plan_with_mode(
    *,
    user_id: str,
    plan_data: Dict[str, Any],
    execution_mode: str,
    custom_instructions: Optional[str],
    original_request: str,
    model: str,
    mode: str,
    db,
    started: float,
    workspace: Optional[Dict[str, Any]] = None,
    settings: Optional["NaviSettings"] = None,
) -> Dict[str, Any]:
    """
    Execute the plan according to the chosen mode and user settings.

    Uses NaviSettings to determine which operations require approval.
    Settings can be loaded from user preferences in the VS Code settings panel.
    """
    from backend.agent.plan_mode_controller import PlanModeController
    from backend.agent.navi_settings import get_user_settings

    logger.info("[AGENT] Executing plan in mode: %s", execution_mode)

    # Load settings if not provided
    if settings is None:
        settings = await get_user_settings(user_id, db)

    # Create controller with settings
    controller = PlanModeController(settings=settings)
    controller.set_execution_mode(execution_mode, custom_instructions)

    # Track execution progress
    all_outputs = []
    steps = plan_data.get("steps", [])
    completed_count = 0
    failed_count = 0

    # Unused but kept for potential future use
    _ = workspace.get("workspace_root") if workspace else "."

    # Map step types to operation names for settings lookup
    STEP_TYPE_TO_OPERATION = {
        "create_file": "file_create",
        "modify_file": "file_edit",
        "delete_file": "file_delete",
        "run_command": "run_command",
        "run_tests": "run_test",
        "deploy": "deploy",
        "analyze": None,  # Never needs approval
    }

    for i, step_data in enumerate(steps):
        step_type = step_data.get("step_type", "analyze")
        tool = step_data.get("tool", "")
        description = step_data.get("description", f"Step {i+1}")

        logger.info("[AGENT] Executing step %d/%d: %s", i + 1, len(steps), description)

        # Get the operation name for this step type
        operation = STEP_TYPE_TO_OPERATION.get(step_type)

        # Determine if approval is needed based on user settings
        needs_approval = False
        if operation is not None:
            # Use settings to check if this operation requires approval
            command_context = {
                "command": step_data.get("arguments", {}).get("command", "")
            }
            needs_approval = settings.requires_approval_for(operation, command_context)
            logger.info(
                "[AGENT] Step %d: operation=%s, needs_approval=%s (settings-based)",
                i + 1,
                operation,
                needs_approval,
            )

        if needs_approval:
            # Return early with approval request
            approval_message = (
                f"**Step {i+1}/{len(steps)}: Approval Required**\n\n"
                f"**Action:** {description}\n"
                f"**Type:** {step_type}\n"
                f"**Tool:** {tool}\n\n"
                f"Reply with:\n"
                f"- `approve` or `yes` to proceed\n"
                f"- `skip` to skip this step\n"
                f"- `stop` to pause execution"
            )

            # Save state for approval
            plan_mode_state = {
                "plan": plan_data,
                "execution_mode": execution_mode,
                "waiting_for_approval": True,
                "pending_step_index": i,
                "completed_count": completed_count,
                "execution_started": True,
            }

            update_user_state(
                user_id,
                {
                    "plan_mode_active": True,
                    "plan_mode_state": plan_mode_state,
                    "original_request": original_request,
                },
            )

            elapsed_ms = int((time.monotonic() - started) * 1000)
            return {
                "reply": (
                    "\n\n".join(all_outputs) + "\n\n" + approval_message
                    if all_outputs
                    else approval_message
                ),
                "actions": [],
                "should_stream": False,
                "state": {
                    "plan_mode_active": True,
                    "plan_mode_state": plan_mode_state,
                },
                "duration_ms": elapsed_ms,
            }

        # Execute the step
        try:
            tool_result = await execute_tool_with_sources(
                user_id,
                tool,
                step_data.get("arguments", {}),
                db=db,
                workspace=workspace,
            )

            output = tool_result.output
            if isinstance(output, dict):
                output = output.get("text", str(output))

            all_outputs.append(f"**Step {i+1}: {description}**\n{output[:500]}...")
            completed_count += 1

        except Exception as e:
            logger.error("[AGENT] Step %d failed: %s", i + 1, e)
            all_outputs.append(f"**Step {i+1}: {description}** - Failed: {e}")
            failed_count += 1

    # All steps completed
    elapsed_ms = int((time.monotonic() - started) * 1000)

    # Run final test verification
    test_summary = ""
    if workspace:
        workspace_root = workspace.get("workspace_root")
        if workspace_root:
            test_result = await _verify_with_tests(workspace_root)
            test_summary = _format_test_results_for_response(test_result)

    # Build completion message
    completion_message = (
        f"\n\n---\n"
        f"**Plan Execution Complete!**\n\n"
        f"- Steps completed: {completed_count}/{len(steps)}\n"
        f"- Steps failed: {failed_count}\n"
        f"{test_summary}"
    )

    all_outputs.append(completion_message)

    # Clear plan mode state
    clear_user_state(user_id)

    return {
        "reply": "\n\n".join(all_outputs),
        "actions": [],
        "should_stream": False,
        "state": {
            "plan_mode_active": False,
            "plan_completed": True,
            "completed_steps": completed_count,
            "failed_steps": failed_count,
        },
        "duration_ms": elapsed_ms,
    }


async def _handle_approval_response(
    *,
    user_id: str,
    message: str,
    previous_state: Dict[str, Any],
    model: str,
    mode: str,
    db,
    started: float,
    workspace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Handle user's response to an approval request.

    Loads user settings to pass to plan execution.
    """
    from backend.agent.navi_settings import get_user_settings

    logger.info("[AGENT] Processing approval response: %s", message[:50])

    # Load user settings for execution
    settings = await get_user_settings(user_id, db)

    response = message.strip().lower()
    plan_mode_state = previous_state.get("plan_mode_state", {})
    plan_data = plan_mode_state.get("plan", {})
    pending_step_index = plan_mode_state.get("pending_step_index", 0)

    if response in ("approve", "yes", "ok", "proceed", "continue"):
        # Approved - continue execution from pending step
        logger.info("[AGENT] Step approved, continuing execution")

        return await _execute_plan_with_mode(
            user_id=user_id,
            plan_data=plan_data,
            execution_mode=plan_mode_state.get("execution_mode", "with_approval_gates"),
            custom_instructions=plan_mode_state.get("custom_instructions"),
            original_request=previous_state.get("original_request", ""),
            model=model,
            mode=mode,
            db=db,
            started=started,
            workspace=workspace,
            settings=settings,  # Pass user settings
        )

    elif response in ("skip", "no", "reject"):
        # Skip this step and continue
        logger.info("[AGENT] Step skipped, continuing execution")

        # Update plan to mark step as skipped
        if pending_step_index < len(plan_data.get("steps", [])):
            plan_data["steps"][pending_step_index]["status"] = "skipped"

        plan_mode_state["pending_step_index"] = pending_step_index + 1
        plan_mode_state["waiting_for_approval"] = False

        return await _execute_plan_with_mode(
            user_id=user_id,
            plan_data=plan_data,
            execution_mode=plan_mode_state.get("execution_mode", "with_approval_gates"),
            custom_instructions=plan_mode_state.get("custom_instructions"),
            original_request=previous_state.get("original_request", ""),
            model=model,
            mode=mode,
            db=db,
            started=started,
            workspace=workspace,
            settings=settings,  # Pass user settings
        )

    elif response in ("stop", "pause", "cancel"):
        # Stop execution
        logger.info("[AGENT] Execution stopped by user")

        clear_user_state(user_id)
        elapsed_ms = int((time.monotonic() - started) * 1000)

        return {
            "reply": (
                "**Execution Paused**\n\n"
                f"Completed {plan_mode_state.get('completed_count', 0)} steps before pausing.\n\n"
                "You can start a new implementation request when ready."
            ),
            "actions": [],
            "should_stream": False,
            "state": {"plan_mode_active": False},
            "duration_ms": elapsed_ms,
        }

    else:
        # Unknown response - ask again
        elapsed_ms = int((time.monotonic() - started) * 1000)

        return {
            "reply": (
                "I didn't understand that response. Please reply with:\n"
                "- `approve` or `yes` to proceed with this step\n"
                "- `skip` or `no` to skip this step\n"
                "- `stop` to pause execution"
            ),
            "actions": [],
            "should_stream": False,
            "state": {
                "plan_mode_active": True,
                "plan_mode_state": plan_mode_state,
            },
            "duration_ms": elapsed_ms,
        }


async def _handle_project_overview(
    *,
    user_id: str,
    message: str,
    model: str,
    mode: str,
    full_context: Dict[str, Any],
    db,
    started: float,
    attachments: Optional[List[Dict[str, Any]]] = None,
    workspace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Smart path for "explain the project / repo" questions.

    1) Calls repo.inspect to get structure.
    2) Tries to read a few key files (README, package.json, pyproject, pom.xml, etc).
    3) Feeds all of that into the LLM to generate a plain-language explanation.
    """

    logger.info("[AGENT] Handling project-overview question via repo.inspect")

    repo_result: Any = None
    files_result: Any = None
    tool_snippets: List[str] = []

    # 1) Always try repo.inspect first
    try:
        repo_result = await execute_tool(
            user_id,
            "repo.inspect",
            {
                # Be conservative – we just want the high-level layout.
                "max_depth": 3,
                "max_files": 200,
            },
            db=db,
            attachments=attachments,
            workspace=workspace,
        )
        repo_text = json.dumps(repo_result, indent=2, default=str)
        tool_snippets.append(f"REPO_INSPECT_RESULT:\n{repo_text}")
    except Exception as e:  # noqa: BLE001
        logger.warning("[AGENT] repo.inspect failed in project overview: %s", e)
        tool_snippets.append(f"REPO_INSPECT_ERROR: {str(e)}")

    # 2) Try to read a few "anchor" files if they exist
    try:
        # The tool executor can decide which of these actually exist.
        files_result = await execute_tool(
            user_id,
            "code.read_files",
            {
                "paths": [
                    "README.md",
                    "readme.md",
                    "package.json",
                    "pyproject.toml",
                    "pom.xml",
                    "setup.py",
                    "main.py",
                    "src/main.py",
                    "src/index.tsx",
                    "src/index.ts",
                ]
            },
            db=db,
            attachments=attachments,
            workspace=workspace,
        )
        files_text = json.dumps(files_result, indent=2, default=str)
        tool_snippets.append(f"KEY_FILES_RESULT:\n{files_text}")
    except Exception as e:  # noqa: BLE001
        logger.warning("[AGENT] code.read_files failed in project overview: %s", e)
        tool_snippets.append(f"KEY_FILES_ERROR: {str(e)}")

    # 3) Build enriched context for the LLM
    extra_context = "\n\n".join(tool_snippets)
    llm_context = dict(full_context)
    combined = llm_context.get("combined", "")
    llm_context["combined"] = combined + "\n\n" + extra_context

    # 4) Ask LLM to explain the project using actual repo info
    answer = await call_llm(
        message,
        llm_context,
        model=model,
        mode=mode,
    )

    clear_user_state(user_id)
    elapsed_ms = int((time.monotonic() - started) * 1000)

    # We can also surface the actions we *implicitly* took, so the panel
    # could show them later if desired.
    actions = [
        {
            "id": "repo-overview-1",
            "title": "Inspect repository structure",
            "description": "Inspect the repository structure and main folders.",
            "tool": "repo.inspect",
            "arguments": {"max_depth": 3, "max_files": 200},
            "type": "workspaceRead",
            "filePath": None,
            "content": None,
        },
        {
            "id": "repo-overview-2",
            "title": "Read key project files",
            "description": "Read key files like README and main entrypoints.",
            "tool": "code.read_files",
            "arguments": {
                "paths": [
                    "README.md",
                    "readme.md",
                    "package.json",
                    "pyproject.toml",
                    "pom.xml",
                    "setup.py",
                    "main.py",
                    "src/main.py",
                    "src/index.tsx",
                    "src/index.ts",
                ]
            },
            "type": "workspaceRead",
            "filePath": None,
            "content": None,
        },
    ]

    return {
        "reply": answer,
        "actions": actions,
        "should_stream": True,
        "state": {"completed": True, "mode": "project_overview"},
        "duration_ms": elapsed_ms,
    }


async def _run_iterative_agent_loop(
    user_id: str,
    message: str,
    model: str = "gpt-4",
    mode: str = "chat",
    db=None,
    attachments: Optional[List[Dict[str, Any]]] = None,
    workspace: Optional[Dict[str, Any]] = None,
    iteration_mode: str = "until_tests_pass",
    max_iterations: int = 5,
) -> Dict[str, Any]:
    """
    Run agent loop in iterative mode (e.g., until tests pass).

    This implements the "run until tests pass" workflow:
    1. Execute the initial plan
    2. Run tests
    3. If tests fail, analyze failures and generate fix plan
    4. Execute fix plan
    5. Repeat until success or max iterations

    Args:
        user_id: User identifier
        message: User's message
        model: LLM model to use
        mode: "chat" or "agent-full"
        db: Database session
        attachments: Optional attachments
        workspace: Workspace context
        iteration_mode: Mode string (e.g., "until_tests_pass")
        max_iterations: Maximum number of iterations

    Returns:
        Result dict with iteration summary included
    """
    from backend.agent.iteration_controller import (
        IterationController,
        create_fix_context,
    )
    from backend.agent.planner_v3 import PlannerV3

    started = time.monotonic()
    logger.info(
        "[AGENT] Starting iterative execution: mode=%s, max_iterations=%d",
        iteration_mode,
        max_iterations,
    )

    # Create iteration controller
    controller = IterationController.create(
        iteration_mode=iteration_mode,
        max_iterations=max_iterations,
    )

    # Track all replies for final summary
    all_replies = []
    final_result = None
    # workspace_root is available from workspace dict if needed in future
    _ = workspace.get("workspace_root") if workspace else None

    # First iteration: execute the original request (use one_shot mode)
    iteration_start = time.monotonic()
    result = await run_agent_loop(
        user_id=user_id,
        message=message,
        model=model,
        mode=mode,
        db=db,
        attachments=attachments,
        workspace=workspace,
        iteration_mode="one_shot",  # Force one_shot to avoid recursion
        max_iterations=1,
    )
    iteration_duration = int((time.monotonic() - iteration_start) * 1000)

    all_replies.append(f"**Iteration 1**:\n{result.get('reply', '')}")

    # Check test results
    test_results = result.get("state", {}).get("test_results", {})
    success = test_results.get("success", False) or test_results.get("skipped", False)

    controller.record_iteration(
        success=success,
        test_results=test_results,
        debug_analysis=result.get("state", {}).get("debug_analysis"),
        duration_ms=iteration_duration,
    )

    final_result = result

    # Continue iterating if needed
    planner = PlannerV3()

    while controller.should_iterate():
        iteration_num = controller.state.iteration_count + 1
        logger.info("[AGENT] Starting iteration %d", iteration_num)

        # Generate fix context from previous failure
        fix_context = create_fix_context(
            original_message=message,
            test_results=test_results,
            debug_analysis=result.get("state", {}).get("debug_analysis"),
            iteration_count=iteration_num,
        )

        # Generate fix plan (used for context, actual execution via run_agent_loop)
        _ = await planner.plan_fix(fix_context)

        # Create a modified message that includes fix context
        fix_message = (
            f"Fix the following test failures (iteration {iteration_num}):\n"
            f"{fix_context.get('failure_summary', 'Unknown failures')}\n\n"
            f"Hints: {', '.join(fix_context.get('fix_hints', [])[:3])}\n\n"
            f"Original request: {message}"
        )

        iteration_start = time.monotonic()
        result = await run_agent_loop(
            user_id=user_id,
            message=fix_message,
            model=model,
            mode=mode,
            db=db,
            attachments=None,  # Don't resend attachments on fix iterations
            workspace=workspace,
            iteration_mode="one_shot",  # Force one_shot to avoid recursion
            max_iterations=1,
        )
        iteration_duration = int((time.monotonic() - iteration_start) * 1000)

        all_replies.append(
            f"\n\n**Iteration {iteration_num}**:\n{result.get('reply', '')}"
        )

        # Check test results
        test_results = result.get("state", {}).get("test_results", {})
        success = test_results.get("success", False) or test_results.get(
            "skipped", False
        )

        controller.record_iteration(
            success=success,
            test_results=test_results,
            debug_analysis=result.get("state", {}).get("debug_analysis"),
            duration_ms=iteration_duration,
        )

        final_result = result

    # Build final response
    total_duration = int((time.monotonic() - started) * 1000)

    # Add iteration summary to result
    iteration_summary = controller.get_summary()
    progress_message = controller.format_progress_message()

    # Combine all replies with summary
    combined_reply = "\n".join(all_replies)
    combined_reply += f"\n\n---\n**Iteration Summary**: {progress_message}"

    return {
        "reply": combined_reply,
        "actions": final_result.get("actions", []),
        "sources": final_result.get("sources", []),
        "should_stream": False,  # Don't stream iterative results
        "state": {
            **final_result.get("state", {}),
            "iteration_mode": iteration_mode,
            "iteration_summary": iteration_summary,
        },
        "duration_ms": total_duration,
        "iteration_summary": iteration_summary,
    }


async def run_agent_loop(
    user_id: str,
    message: str,
    model: str = "gpt-4",
    mode: str = "chat",
    db=None,
    attachments: Optional[List[Dict[str, Any]]] = None,
    workspace: Optional[Dict[str, Any]] = None,
    iteration_mode: str = "one_shot",
    max_iterations: int = 5,
) -> Dict[str, Any]:
    """
    Main NAVI agent pipeline.
    This is called every time the user sends a message.

    Args:
        user_id: User identifier
        message: User's message
        model: LLM model to use
        mode: "chat" or "agent-full"
        db: Database session
        attachments: Optional attachments (images, files)
        workspace: Workspace context from VS Code
        iteration_mode: Iteration mode for test-driven development:
            - "one_shot": Single execution (default)
            - "until_tests_pass": Iterate until all tests pass
        max_iterations: Maximum iterations for iterative modes (default: 5)

    Returns:
        {
            "reply": str,              # NAVI's response
            "actions": List[Dict],     # Proposed actions (for approval / apply)
            "should_stream": bool,     # Whether to stream response
            "state": Dict,             # Updated state (for debugging)
            "duration_ms": int,        # Total run duration in ms (for UI)
            "iteration_summary": Dict  # Summary of iterations (if iterative mode)
        }
    """
    # Handle iterative mode
    if iteration_mode != "one_shot":
        return await _run_iterative_agent_loop(
            user_id=user_id,
            message=message,
            model=model,
            mode=mode,
            db=db,
            attachments=attachments,
            workspace=workspace,
            iteration_mode=iteration_mode,
            max_iterations=max_iterations,
        )

    started = time.monotonic()

    try:
        logger.info(
            "[AGENT] Starting loop for user=%s, message='%s...'",
            user_id,
            message[:50],
        )

        # ---------------------------------------------------------
        # STAGE 1: Load user state (what were they doing last?)
        # ---------------------------------------------------------
        previous_state = await get_user_state(user_id)
        logger.info("[AGENT] Previous state: %s", previous_state)

        normalized_msg = message.strip().lower()

        # Special case: user typed a generic affirmative
        if normalized_msg in (
            "yes",
            "sure",
            "okay",
            "ok",
            "go ahead",
            "yes please",
            "please",
        ):
            if previous_state and previous_state.get("pending_action"):
                logger.info("[AGENT] Affirmative detected, executing pending action")
                pending = previous_state["pending_action"]
                tool_name = (
                    pending if isinstance(pending, str) else pending.get("tool", "")
                )
                tool_args = {} if isinstance(pending, str) else pending.get("args", {})
                tool_result = await execute_tool_with_sources(
                    user_id,
                    tool_name,
                    tool_args,
                    db=db,
                    attachments=attachments,
                    workspace=workspace,
                )

                reply_text = tool_result.output.get("text", str(tool_result.output))
                response_state = {"executed_pending_action": True}

                # ---------------------------------------------------------
                # STAGE 8: Verify with tests (if code was modified)
                # ---------------------------------------------------------
                code_modifying_tools = [
                    "code.apply_patch",
                    "code.write_file",
                    "code.create_file",
                    "code.edit_file",
                    "code.overwrite_file",
                ]
                if tool_name in code_modifying_tools:
                    workspace_root = (
                        workspace.get("workspace_root") if workspace else None
                    )
                    if workspace_root:
                        logger.info(
                            "[AGENT] Code modified, running test verification..."
                        )
                        test_result = await _verify_with_tests(workspace_root)
                        response_state["test_results"] = test_result

                        # Append test results to reply
                        test_summary = _format_test_results_for_response(test_result)
                        reply_text += test_summary

                        # If tests failed, run enhanced debug analysis
                        if not test_result.get("success") and not test_result.get(
                            "skipped"
                        ):
                            failed_tests = test_result.get("failed_tests", [])
                            if failed_tests:
                                # Combine error messages and stack traces for analysis
                                error_output = "\n\n".join(
                                    [
                                        f"{ft.get('name', 'unknown')}: {ft.get('error_message', '')}\n{ft.get('stack_trace', '')}"
                                        for ft in failed_tests[:5]
                                    ]
                                )
                                debug_analysis = await _analyze_errors_with_debugger(
                                    error_output=error_output,
                                    workspace_path=workspace_root,
                                )
                                response_state["debug_analysis"] = debug_analysis
                                reply_text += _format_debug_analysis_for_response(
                                    debug_analysis
                                )

                elapsed_ms = int((time.monotonic() - started) * 1000)
                # Return unified result with sources
                return {
                    "reply": reply_text,
                    "actions": [],
                    "sources": tool_result.sources,
                    "should_stream": False,
                    "state": response_state,
                    "duration_ms": elapsed_ms,
                }

            # If no pending action, treat as continuation
            message = f"(user agrees to continue previous task) {message}"
            logger.info(
                "[AGENT] Affirmative without pending action, continuing conversation"
            )

        # ---------------------------------------------------------
        # PLAN MODE: Handle execution mode choice or approval response
        # ---------------------------------------------------------
        if _is_execution_mode_response(message, previous_state):
            return await _handle_execution_mode_choice(
                user_id=user_id,
                message=message,
                previous_state=previous_state,
                model=model,
                mode=mode,
                db=db,
                started=started,
                attachments=attachments,
                workspace=workspace,
            )

        if _is_approval_response(message, previous_state):
            return await _handle_approval_response(
                user_id=user_id,
                message=message,
                previous_state=previous_state,
                model=model,
                mode=mode,
                db=db,
                started=started,
                workspace=workspace,
            )

        # Special case: pure greetings should just chat, not plan repo work
        if normalized_msg in ("hi", "hello", "hey", "hola", "yo", "hi!", "hey!"):
            logger.info("[AGENT] Greeting detected, using direct chat mode")
            # Build minimal/lightweight context for greetings
            workspace_root = workspace.get("workspace_root") if workspace else None
            workspace_ctx = await retrieve_workspace_context(
                user_id=user_id,
                workspace_root=workspace_root,
                include_files=True,
                attachments=attachments,
            )
            org_ctx = await retrieve_org_context(user_id, message, db=db)
            memory_ctx = await retrieve_memories(user_id, message, db=db)

            # Retrieve RAG context for greetings/simple queries too
            rag_context_text = ""
            if workspace_root and isinstance(workspace_root, str):
                try:
                    from backend.services.workspace_rag import search_codebase
                    import asyncio

                    rag_results = await asyncio.wait_for(
                        search_codebase(
                            workspace_path=workspace_root,
                            query=message,
                            top_k=5,
                            allow_background_indexing=True,
                        ),
                        timeout=10.0,
                    )

                    if rag_results:
                        rag_context_text = "\n\n## Relevant Code Context:\n"
                        for result in rag_results[:3]:
                            rag_context_text += (
                                f"\n- {result.get('file_path', 'unknown')}\n"
                            )
                except (asyncio.TimeoutError, Exception) as e:
                    logger.warning(
                        f"[AGENT] RAG retrieval failed in greeting path: {e}"
                    )

            full_context = build_context(
                workspace_ctx,
                org_ctx,
                memory_ctx.to_dict(),
                previous_state,
                message,
            )

            # Add RAG context
            if rag_context_text:
                full_context["combined"] = (
                    full_context.get("combined", "") + rag_context_text
                )

            answer = await call_llm(message, full_context, model=model, mode=mode)
            clear_user_state(user_id)
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return {
                "reply": answer,
                "actions": [],
                "should_stream": True,
                "state": {"completed": True, "mode": "greeting"},
                "duration_ms": elapsed_ms,
            }

        # ---------------------------------------------------------
        # STAGE 2: Build perfect workspace context
        # ---------------------------------------------------------
        logger.info("[AGENT] Retrieving perfect workspace context...")
        from backend.agent.perfect_workspace_retriever import (
            retrieve_workspace,
        )

        workspace_ctx = {}
        if workspace and isinstance(workspace, dict):
            workspace_root = workspace.get("workspace_root")
            if workspace_root and isinstance(workspace_root, str):
                workspace_ctx = retrieve_workspace(workspace_root)

        org_ctx = await retrieve_org_context(user_id, message, db=db)
        memory_ctx = await retrieve_memories(user_id, message, db=db)

        # ---------------------------------------------------------
        # STAGE 2.2: Retrieve RAG context from codebase
        # ---------------------------------------------------------
        rag_context_text = ""
        if workspace and isinstance(workspace, dict):
            workspace_root = workspace.get("workspace_root")
            if workspace_root and isinstance(workspace_root, str):
                try:
                    logger.info("[AGENT] Retrieving RAG context from workspace...")
                    from backend.services.workspace_rag import search_codebase
                    import asyncio

                    # Use Phase 1 background indexing (non-blocking)
                    # First request returns empty, triggers indexing
                    # Subsequent requests use cached index
                    rag_results = await asyncio.wait_for(
                        search_codebase(
                            workspace_path=workspace_root,
                            query=message,
                            top_k=10,
                            allow_background_indexing=True,
                        ),
                        timeout=10.0,  # 10 second timeout
                    )

                    if rag_results:
                        logger.info(
                            "[AGENT] Retrieved %d RAG chunks from codebase",
                            len(rag_results),
                        )
                        rag_context_text = "\n\n## Relevant Code Context (RAG):\n"
                        for i, result in enumerate(rag_results[:5], 1):  # Top 5 chunks
                            file_path = result.get("file_path", "unknown")
                            content = result.get("content_preview", "")[
                                :500
                            ]  # Truncate long chunks
                            rag_context_text += (
                                f"\n### {i}. {file_path}\n```\n{content}\n```\n"
                            )
                    else:
                        logger.info(
                            "[AGENT] No RAG index available (background indexing may be in progress)"
                        )
                except asyncio.TimeoutError:
                    logger.warning(
                        "[AGENT] RAG context retrieval timed out after 10s - continuing without RAG"
                    )
                except Exception as e:
                    logger.warning(
                        f"[AGENT] RAG retrieval failed: {e} - continuing without RAG"
                    )

        full_context = build_context(
            workspace_ctx,
            org_ctx,
            memory_ctx.to_dict(),
            previous_state,
            message,
        )

        # Add RAG context to combined context
        if rag_context_text:
            full_context["combined"] = (
                full_context.get("combined", "") + rag_context_text
            )
            full_context["has_rag"] = True
            logger.info("[AGENT] Added RAG context to full_context")

        logger.info(
            "[AGENT] Context built: %d chars (RAG: %s)",
            len(full_context.get("combined", "")),
            "enabled" if rag_context_text else "not available",
        )

        # ---------------------------------------------------------
        # STAGE 2.5: Process image attachments for vision analysis
        # ---------------------------------------------------------
        images = _extract_images_from_attachments(attachments)
        if images:
            logger.info("[AGENT] Processing %d image attachment(s)", len(images))
            workspace_root = workspace.get("workspace_root") if workspace else None
            image_analysis = await _analyze_images_with_vision(
                images=images, message=message, workspace_root=workspace_root
            )
            # Add image analysis to context for LLM and planning
            full_context["image_analysis"] = image_analysis
            full_context["has_images"] = True

            # If analysis contains UI description, add to combined context
            if image_analysis.get("analysis"):
                analysis_text = f"\n\n[IMAGE ANALYSIS]\n{image_analysis['analysis']}\n"
                full_context["combined"] = (
                    full_context.get("combined", "") + analysis_text
                )
                logger.info("[AGENT] Added image analysis to context")

        # ---------------------------------------------------------
        # PROJECT OVERVIEW FAST-PATH
        # ---------------------------------------------------------
        if _looks_like_project_overview_question(normalized_msg):
            return await _handle_project_overview(
                user_id=user_id,
                message=message,
                model=model,
                mode=mode,
                full_context=full_context,
                db=db,
                started=started,
                attachments=attachments,
                workspace=workspace,
            )

        # ---------------------------------------------------------
        # PLAN MODE: Detect implementation requests
        # ---------------------------------------------------------
        # Check if mode is "plan" or user is asking to implement something
        is_plan_mode = mode == "plan" or mode == "agent-full"
        if is_plan_mode and _looks_like_implementation_request(message):
            logger.info("[AGENT] Implementation request detected, entering plan mode")
            return await _handle_plan_mode_request(
                user_id=user_id,
                message=message,
                model=model,
                mode=mode,
                db=db,
                started=started,
                attachments=attachments,
                workspace=workspace,
            )

        # ---------------------------------------------------------
        # STAGE 3: Classify the user's intent using LLM-powered provider-aware classifier
        # ---------------------------------------------------------
        logger.info("[AGENT] Classifying intent...")
        try:
            # Use new LLM-powered classifier for provider-aware classification
            llm_classifier = LLMIntentClassifier()
            intent = await llm_classifier.classify(
                message=message, metadata={"user_id": user_id, "workspace": workspace}
            )
            logger.info(
                "[AGENT] LLM Intent: %s/%s (provider: %s)",
                intent.family.value if intent.family else "None",
                intent.kind.value if intent.kind else "None",
                intent.provider.value if intent.provider else "None",
            )
        except Exception as e:
            # Fallback to rule-based classifier if LLM fails
            logger.warning(
                "[AGENT] LLM classifier failed (%s), using rule-based fallback", e
            )
            classifier = IntentClassifier()
            intent = classifier.classify(message)
            logger.info(
                "[AGENT] Fallback Intent: %s/%s", intent.family.value, intent.kind.value
            )

        # ---------------------------------------------------------
        # STAGE 4: Handle low confidence intents
        # ---------------------------------------------------------
        if intent.confidence < 0.5:
            logger.info(
                "[AGENT] Intent confidence low (%.2f), asking for clarification",
                intent.confidence,
            )
            await update_user_state(
                user_id,
                {"pending_clarification": intent.model_dump()},
            )
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return {
                "reply": (
                    "I'm not quite sure what you'd like me to do. "
                    f"Could you be more specific? (Confidence: {intent.confidence:.1f})"
                ),
                "actions": [],
                "should_stream": False,
                "state": {"intent": "ambiguous"},
                "duration_ms": elapsed_ms,
            }

        # ---------------------------------------------------------
        # STAGE 5: Task grounding + planning (Phase 4.2 integration)
        # ---------------------------------------------------------
        logger.info("[AGENT] Starting task grounding...")
        from backend.agent.task_grounder import ground_task

        # Extract VS Code diagnostics from workspace context if available
        workspace_root = workspace.get("workspace_root") if workspace else None
        diagnostics_count = 0
        if workspace and "diagnostics" in workspace:
            diagnostics_count = len(workspace.get("diagnostics", []))

        # Ground the task with intelligent validation
        grounding_context = {
            "workspace": workspace_root,
            "diagnostics_count": diagnostics_count,
            "workspace_data": workspace,
            "message": message,
            "user_id": user_id,
        }

        grounding_result = await ground_task(intent, grounding_context)

        # Handle grounding results
        if grounding_result.type == "rejected":
            logger.info(
                "[AGENT] Task rejected by grounding: %s", grounding_result.reason
            )
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return {
                "reply": grounding_result.reason,
                "actions": [],
                "should_stream": False,
                "state": {
                    "grounded": False,
                    "rejection_reason": grounding_result.reason,
                },
                "duration_ms": elapsed_ms,
            }

        if grounding_result.type == "clarification":
            logger.info(
                "[AGENT] Task needs clarification: %s",
                grounding_result.clarification.question,
            )
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return {
                "reply": grounding_result.clarification.question,
                "actions": [],
                "should_stream": False,
                "state": {"grounded": False, "needs_clarification": True},
                "duration_ms": elapsed_ms,
            }

        # Task is ready - now generate plan from structured task
        logger.info(
            "[AGENT] Task grounded successfully, generating plan from structured task..."
        )
        from backend.agent.planner_v3 import PlannerV3

        planner = PlannerV3()

        # Use grounded task for enhanced planning
        enhanced_context = dict(full_context)
        enhanced_context["grounded_task"] = grounding_result.task.__dict__
        # Confidence is on the task, not the grounding result
        grounding_confidence = (
            getattr(grounding_result.task, "confidence", 1.0)
            if grounding_result.task
            else 1.0
        )
        enhanced_context["grounding_confidence"] = grounding_confidence

        plan = await planner.plan(intent, enhanced_context)
        logger.info(
            "[AGENT] Plan generated with %d steps (grounding confidence: %.2f)",
            len(plan.steps),
            grounding_confidence,
        )

        # Prepare shaped actions once so all branches can reuse them
        planned_actions = _shape_actions_from_plan(plan)

        # ---------------------------------------------------------
        # STAGE 6: Check if plan needs approval (enhanced with grounded task data)
        # ---------------------------------------------------------
        # Check both plan steps and grounded task approval requirements
        requires_approval = any(
            step.tool in ["code.apply_patch", "pm.create_ticket", "pm.update_ticket"]
            for step in plan.steps
        )

        # Override with grounded task approval requirement (Phase 4.2 enhancement)
        if grounding_result.type == "ready" and hasattr(
            grounding_result.task, "requiresApproval"
        ):
            requires_approval = grounding_result.task.requiresApproval

        if requires_approval:
            # Save pending plan with grounded task data
            await update_user_state(
                user_id,
                {
                    "pending_plan": asdict(plan),
                    "pending_intent": intent.model_dump(),
                    "grounded_task": (
                        grounding_result.task.__dict__
                        if grounding_result.type == "ready"
                        else None
                    ),
                    "last_plan": asdict(plan),
                },
            )
            logger.info(
                "[AGENT] Plan requires approval (grounded task: %s), waiting for user",
                (
                    grounding_result.task.intent
                    if grounding_result.type == "ready"
                    else "unknown"
                ),
            )

            # Generate intelligent approval message from grounded task
            approval_message = _generate_approval_message(grounding_result, plan)

            elapsed_ms = int((time.monotonic() - started) * 1000)
            return {
                "reply": approval_message,
                # M2-1: return shaped actions so the panel can show Workspace plan + Approve/Reject
                "actions": planned_actions,
                "should_stream": False,
                "state": {
                    "pending_approval": True,
                    "grounded": True,
                    "grounding_confidence": grounding_confidence,
                },
                "duration_ms": elapsed_ms,
            }

        # ---------------------------------------------------------
        # STAGE 7a: If no executable steps, provide summary
        # ---------------------------------------------------------
        if not plan.steps:
            logger.info("[AGENT] No steps in plan, providing summary")
            answer = await call_llm(
                message,
                full_context,
                model=model,
                mode=mode,
            )
            clear_user_state(user_id)
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return {
                "reply": answer,
                "actions": [],
                "should_stream": True,
                "state": {"completed": True},
                "duration_ms": elapsed_ms,
            }

        # ---------------------------------------------------------
        # STAGE 7b: Execute safe tools immediately, then let LLM explain
        # ---------------------------------------------------------
        safe_tools = ["repo.inspect", "code.read_files", "code.search"]
        if plan.steps and all(step.tool in safe_tools for step in plan.steps):
            logger.info("[AGENT] Executing safe tools immediately (LLM will explain)")
            tool_snippets: List[str] = []
            all_sources: List[Dict[str, Any]] = []
            for step in plan.steps[:3]:  # Limit to first 3 steps
                try:
                    tool_result = await execute_tool_with_sources(
                        user_id,
                        step.tool,
                        step.arguments,
                        db=db,
                        attachments=attachments,
                        workspace=workspace,
                    )
                    # Collect sources
                    if tool_result.sources:
                        all_sources.extend(tool_result.sources)

                    # Format output for LLM context
                    result_text = json.dumps(tool_result.output, indent=2, default=str)
                    tool_snippets.append(
                        f"TOOL {step.tool} (description={step.description!r}):\n{result_text}"
                    )
                except Exception as e:  # noqa: BLE001
                    logger.exception("[AGENT] Safe tool %s failed: %s", step.tool, e)
                    tool_snippets.append(
                        f"TOOL_ERROR {step.tool} (description={step.description!r}): {str(e)}"
                    )

            extra_context = "\n\n".join(tool_snippets)
            llm_context = dict(full_context)
            combined = llm_context.get("combined", "")
            llm_context["combined"] = combined + "\n\n" + extra_context

            answer = await call_llm(
                message,
                llm_context,
                model=model,
                mode=mode,
            )

            # De-duplicate sources by (type, url, name)
            dedup = {}
            for s in all_sources:
                key = (s.get("type"), s.get("url"), s.get("name"))
                dedup[key] = s
            all_sources = list(dedup.values())

            clear_user_state(user_id)
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return {
                "reply": answer,
                "actions": planned_actions,
                "sources": all_sources,  # Add sources to response
                "should_stream": True,
                "state": {"completed": True, "mode": "safe_tools_exec"},
                "duration_ms": elapsed_ms,
            }

        # ---------------------------------------------------------
        # Safety fallback - show plan summary
        # ---------------------------------------------------------
        logger.warning(
            "[AGENT] Reached safety fallback, %d steps planned", len(plan.steps)
        )
        clear_user_state(user_id)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {
            "reply": (
                plan.summary
                or "I have a plan but need your approval to proceed. What would you like me to do?"
            ),
            "actions": planned_actions,
            "should_stream": False,
            "state": {"fallback": True},
            "duration_ms": elapsed_ms,
        }

    except Exception as e:  # noqa: BLE001
        logger.error("[AGENT] Error in agent loop: %s", e, exc_info=True)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {
            "reply": (
                "I encountered an error while processing your request. "
                "Let me try a different approach – could you rephrase what you need?"
            ),
            "actions": [],
            "should_stream": False,
            "state": {"error": str(e)},
            "duration_ms": elapsed_ms,
        }
