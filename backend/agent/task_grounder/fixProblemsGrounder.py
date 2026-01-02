"""
FIX_PROBLEMS Task Grounder

Deterministic grounding logic for FIX_PROBLEMS intent.
Supports both workspace diagnostics AND CI pipeline failures.
No LLM guessing, no phrase matching - pure logic based on workspace state.
"""

import logging
import os
from urllib.parse import urlparse, unquote
from typing import Dict, Any, List

from .types import GroundingResult, FixProblemsTask, Diagnostic

logger = logging.getLogger(__name__)


def _normalize_diagnostic_path(file_path: str, workspace_root: str | None) -> str:
    if not file_path:
        return file_path

    if file_path.startswith("file:"):
        parsed = urlparse(file_path)
        if parsed.path:
            file_path = unquote(parsed.path)

    if workspace_root and os.path.isabs(file_path):
        try:
            workspace_root = os.path.abspath(workspace_root)
            file_path_abs = os.path.abspath(file_path)
            if os.path.commonpath([workspace_root, file_path_abs]) == workspace_root:
                return os.path.relpath(file_path_abs, workspace_root)
        except ValueError:
            return file_path

    return file_path


async def ground_fix_problems(context: Dict[str, Any]) -> GroundingResult:
    """
    Ground FIX_PROBLEMS intent based on workspace context.
    Enhanced for Phase 4.3 - now supports CI failure analysis.
    
    Args:
        context: Workspace context containing diagnostics, workspace info, etc.
        
    Returns:
        GroundingResult with ready task, clarification request, or rejection
    """
    logger.info("Grounding FIX_PROBLEMS intent (Phase 4.3)")
    
    # Extract workspace information
    workspace = context.get("workspace")
    if not workspace:
        return GroundingResult(
            type="rejected",
            reason="No workspace found. Cannot analyze problems without workspace context."
        )
    
    # Check for CI failures first (Phase 4.3 enhancement)
    user_input = context.get("message", context.get("user_input", "")).lower()
    ci_keywords = ["build", "ci", "pipeline", "failing", "deployment", "tests failing"]
    
    if any(keyword in user_input for keyword in ci_keywords):
        # This might be a CI failure request
        try:
            from ..execution_engine.ci_failure_engine import CIFailureTaskGrounder
            ci_grounder = CIFailureTaskGrounder()
            ci_result = await ci_grounder.ground_ci_fix_task(user_input, context)
            
            if ci_result and ci_result["type"] == "ready":
                # Return CI failure task
                logger.info("Grounded as CI failure fix task")
                return GroundingResult(
                    type="ready",
                    task=FixProblemsTask(
                        intent="FIX_PROBLEMS",
                        scope=ci_result["task"]["scope"],
                        target=ci_result["task"]["target"],
                        confidence=ci_result["task"]["confidence"],
                        inputs=ci_result["task"]["inputs"],
                        requires_approval=ci_result["task"]["requires_approval"],
                        metadata=ci_result["task"].get("metadata", {})
                    )
                )
        except Exception as e:
            logger.warning(f"CI failure grounding failed, falling back to workspace diagnostics: {e}")
    
    # Continue with standard workspace diagnostics
    
    # Extract workspace information
    workspace = context.get("workspace")
    if not workspace:
        return GroundingResult(
            type="rejected",
            reason="No workspace found. Cannot analyze problems without workspace context."
        )
    
    # Extract diagnostics
    workspace_root = context.get("workspace_root") or workspace
    diagnostics_raw = context.get("diagnostics", [])
    diagnostics_count = context.get("diagnostics_count", len(diagnostics_raw))
    
    # Convert raw diagnostics to structured format
    diagnostics = []
    for diag in diagnostics_raw:
        if isinstance(diag, dict) and "diagnostics" in diag:
            raw_group_path = str(diag.get("path") or diag.get("file") or "")
            group_path = _normalize_diagnostic_path(raw_group_path, workspace_root)
            group_diagnostics = diag.get("diagnostics") or []

            for entry in group_diagnostics:
                severity_map = {1: "error", 2: "warning", 4: "info"}
                severity = entry.get("severity", 1)
                if isinstance(severity, int):
                    severity = severity_map.get(severity, "error")

                message = str(entry.get("message", ""))
                file_path = group_path or "unknown"

                logger.info(f"Processing diagnostic: file='{file_path}', message='{message}', severity={severity}")

                diagnostics.append(Diagnostic(
                    file=file_path,
                    message=message,
                    severity=severity,
                    code=entry.get("code"),
                    line=entry.get("line"),
                    column=entry.get("character", entry.get("column")),
                    range=entry.get("range")
                ))
        elif isinstance(diag, dict):
            # Map VS Code diagnostic format to our Diagnostic model
            severity_map = {1: "error", 2: "warning", 4: "info"}
            severity = diag.get("severity", 1)
            if isinstance(severity, int):
                severity = severity_map.get(severity, "error")
            
            raw_file_path = str(diag.get("file") or diag.get("source") or "unknown")
            file_path = _normalize_diagnostic_path(raw_file_path, workspace_root)
            message = str(diag.get("message", ""))
            
            logger.info(f"Processing diagnostic: file='{file_path}', message='{message}', severity={severity}")
            
            diagnostics.append(Diagnostic(
                file=file_path,
                message=message,
                severity=severity,
                code=diag.get("code"),
                line=diag.get("startLineNumber", diag.get("line")),
                column=diag.get("startColumn", diag.get("column")),
                range=diag.get("range")
            ))
        else:
            # Handle various diagnostic formats
            diagnostics.append(Diagnostic(
                file=str(diag.get("file", "unknown")),
                message=str(diag.get("message", str(diag))),
                severity=diag.get("severity", "error")
            ))
    
    # Decision logic - deterministic, no guessing
    if diagnostics_count == 0:
        return GroundingResult(
            type="rejected",
            reason=f"No problems found in workspace '{workspace}'. The Problems tab shows 0 diagnostics."
        )
    
    # Calculate affected files
    affected_files = list(set(d.file for d in diagnostics if d.file != "unknown"))
    
    # Categorize diagnostics by severity
    errors = [d for d in diagnostics if d.severity == "error"]
    warnings = [d for d in diagnostics if d.severity == "warning"]
    
    # Group diagnostics by file for execution engine
    diagnostics_by_file = {}
    for diag in diagnostics:
        file_path = diag.file
        logger.info(f"Grouping diagnostic: file_path='{file_path}'")
        if file_path not in diagnostics_by_file:
            diagnostics_by_file[file_path] = []
        diag_data = diag.model_dump()
        logger.info(f"Diagnostic data: {diag_data}")
        diagnostics_by_file[file_path].append(diag_data)
    
    # Convert to the format expected by execution engine
    grouped_diagnostics = [
        {
            "path": file_path,
            "diagnostics": file_diagnostics
        }
        for file_path, file_diagnostics in diagnostics_by_file.items()
    ]
    
    logger.info(f"Grouped diagnostics: {grouped_diagnostics}")
    
    # Create grounded task
    task = FixProblemsTask(
        inputs={
            "diagnostics": grouped_diagnostics,  # Grouped by file format
            "affected_files": affected_files,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "total_count": diagnostics_count
        },
        requires_approval=True,
        confidence=0.95,  # High confidence - we have concrete diagnostics
        metadata={
            "workspace": workspace,
            "grounding_source": "vscode_diagnostics",
            "severity_breakdown": {
                "errors": len(errors),
                "warnings": len(warnings)
            }
        }
    )
    
    logger.info(f"Successfully grounded FIX_PROBLEMS: {diagnostics_count} diagnostics in {len(affected_files)} files")
    
    return GroundingResult(
        type="ready",
        task=task
    )


def _should_request_clarification(diagnostics: List[Diagnostic], context: Dict[str, Any]) -> bool:
    """
    Determine if we need clarification from the user.
    For now, we don't need clarification for FIX_PROBLEMS - diagnostics are clear.
    Future: Could ask about priority (errors first vs warnings) or scope (specific files).
    """
    # For Phase 4.2, we handle all diagnostics without clarification
    return False
