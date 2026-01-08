# backend/services/auto_fix_service.py
"""
Auto-Fix Service with AI-powered patch generation and risk assessment.

This service handles:
- Fix registration and tracking
- AI-powered unified diff patch generation
- Enterprise-grade risk assessment and safety scoring
- Patch validation with confidence metrics
- Integration with LLM router for intelligent code fixes

Part of Batch 7 — Advanced Intelligence Layer (Enterprise-Grade AI Code Rewrite Engine).
"""

import os
import uuid
import logging
from typing import Dict, Any, Optional, List
import re
from pathlib import Path

from backend.ai.llm_router import get_router
from backend.services.risk_assessment_service import RiskAssessmentService

logger = logging.getLogger(__name__)

# Global fix registry - in production this should be Redis/DB
_FIX_REGISTRY: Dict[str, Dict[str, Any]] = {}

# Initialize risk assessment service
risk_assessor = RiskAssessmentService()


def register_fix(
    file: str,
    hunk: str,
    issue: str,
    line_number: Optional[int] = None,
    severity: str = "info",
) -> str:
    """
    Register a new fix for later application.

    Args:
        file: Path to the file containing the issue
        hunk: Git diff hunk showing the problematic code
        issue: Description of the issue to fix
        line_number: Optional line number where the issue occurs
        severity: Severity level of the issue

    Returns:
        str: Unique fix ID for tracking this fix
    """
    fix_id = f"fix_{uuid.uuid4().hex[:8]}"

    _FIX_REGISTRY[fix_id] = {
        "file": file,
        "hunk": hunk,
        "issue": issue,
        "line_number": line_number,
        "severity": severity,
        "registered_at": str(uuid.uuid4()),  # Simple timestamp
    }

    logger.info(f"Registered fix {fix_id} for file {file}: {issue}")
    return fix_id


def get_fix_info(fix_id: str) -> Optional[Dict[str, Any]]:
    """
    Get information about a registered fix.

    Args:
        fix_id: Unique identifier for the fix

    Returns:
        Dict with fix information or None if not found
    """
    return _FIX_REGISTRY.get(fix_id)


async def run_auto_fix(fix_id: str) -> Dict[str, Any]:
    """
    Generate AI-powered patch for a registered fix.

    Args:
        fix_id: Unique identifier for the fix to apply

    Returns:
        Dict containing the generated patch and metadata

    Raises:
        ValueError: If fix_id not found or file doesn't exist
        Exception: If AI patch generation fails
    """
    if fix_id not in _FIX_REGISTRY:
        raise ValueError(f"Unknown fix_id: {fix_id}")

    fix_data = _FIX_REGISTRY[fix_id]
    file_path = fix_data["file"]
    hunk = fix_data["hunk"]
    issue = fix_data["issue"]

    logger.info(f"Starting auto-fix for {fix_id}: {file_path}")

    # Validate file exists
    if not os.path.exists(file_path):
        raise ValueError(f"File not found: {file_path}")

    # Read original file content
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            original_content = f.read()
    except Exception as e:
        raise ValueError(f"Failed to read file {file_path}: {str(e)}")

    # Generate AI-powered patch
    patch = await _generate_ai_patch(file_path, original_content, hunk, issue)

    # Validate patch format
    if not _is_valid_patch(patch):
        raise Exception(f"AI generated invalid patch format for {fix_id}")

    # Extract affected file paths from patch
    affected_files = _extract_file_paths_from_patch(patch)

    # Perform enterprise-grade risk assessment
    risk_assessment = risk_assessor.assess_patch(patch, affected_files)

    # Calculate confidence and safety metrics (legacy function)
    legacy_metadata = _analyze_patch_safety(patch, original_content)

    logger.info(
        f"Successfully generated patch for {fix_id} with {risk_assessment.overall_risk.value} risk level"
    )

    return {
        "patch": patch,
        "file_path": file_path,
        "affected_files": affected_files,
        "risk_assessment": {
            "overall_risk": risk_assessment.overall_risk.value,
            "risk_score": risk_assessment.risk_score,
            "confidence_score": risk_assessment.confidence_score,
            "requires_review": risk_assessment.requires_review,
            "safe_to_auto_apply": risk_assessment.safe_to_auto_apply,
            "factors": [
                {
                    "factor": f.factor,
                    "score": f.score,
                    "reasoning": f.reasoning,
                    "category": f.category,
                    "examples": f.examples,
                }
                for f in risk_assessment.factors
            ],
            "impact_analysis": risk_assessment.impact_analysis,
            "recommendations": risk_assessment.recommendations,
        },
        "metadata": {
            **legacy_metadata,
            "fix_id": fix_id,
            "issue": issue,
            "original_severity": fix_data["severity"],
        },
    }


async def _generate_ai_patch(
    file_path: str, original_content: str, hunk: str, issue: str
) -> str:
    """
    Generate unified diff patch using AI with multi-file support.

    Args:
        file_path: Path to the file being fixed
        original_content: Current content of the file
        hunk: Git diff hunk showing the issue
        issue: Description of what needs to be fixed

    Returns:
        str: Valid unified diff patch (potentially spanning multiple files)
    """
    # Get file extension for language context
    file_ext = Path(file_path).suffix
    language_hint = _get_language_from_extension(file_ext)

    # Build workspace context for cross-file analysis
    workspace_context = _build_workspace_context(file_path)

    prompt = f"""You are Navi, an autonomous engineering agent with enterprise-grade code analysis capabilities.

Generate a UNIFIED DIFF PATCH that applies the fix for this issue.
It MAY modify MULTIPLE FILES if cross-file changes are required.

Rules:
- Output MUST be valid unified diff format
- You MUST include a separate diff section per file
- You MUST use paths relative to the repo root  
- Patch must apply cleanly to original files
- No explanation text, ONLY the patch
- For multi-file fixes: include ALL necessary changes

File: {file_path} ({language_hint})
Issue: {issue}

Current file content:
```
{original_content}
```

Problematic hunk (for reference):
```
{hunk}
```

Workspace context (related files that might need changes):
{workspace_context}

Requirements:
1. Output MUST be valid unified diff format starting with "--- a/" and "+++ b/"
2. For cross-file changes, include multiple file sections
3. Fix should address dependencies and imports
4. Preserve code style and formatting
5. Use proper line context (3 lines before/after changes)

Analyze dependencies and generate appropriate multi-file patch:"""

    try:
        # Use LLM router directly for AI patch generation
        logger.info("Calling router.run directly for AI patch generation")
        router = get_router()
        ai_response = await router.run(
            prompt=prompt,
            system_prompt="You are an expert code fixer. Generate unified diff patches for code issues.",
            max_tokens=2048,
            temperature=0.1,
            model="gpt-4o-mini",
        )

        patch = ai_response.text.strip()

        # Clean up the patch if it has markdown formatting
        if "```" in patch:
            # Extract patch from markdown code blocks
            lines = patch.split("\n")
            in_code_block = False
            patch_lines = []

            for line in lines:
                if line.strip().startswith("```"):
                    in_code_block = not in_code_block
                    continue
                if in_code_block or (
                    line.startswith("--- ")
                    or line.startswith("+++ ")
                    or line.startswith("@@")
                ):
                    patch_lines.append(line)

            patch = "\n".join(patch_lines)

        logger.info(f"Generated patch for {file_path}: {len(patch)} characters")
        return patch

    except Exception as e:
        logger.error(f"AI patch generation failed for {file_path}: {str(e)}")
        raise Exception(f"Failed to generate patch: {str(e)}")


def _get_language_from_extension(ext: str) -> str:
    """Get programming language from file extension."""
    lang_map = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".tsx": "TypeScript React",
        ".jsx": "JavaScript React",
        ".java": "Java",
        ".cpp": "C++",
        ".c": "C",
        ".go": "Go",
        ".rs": "Rust",
        ".php": "PHP",
        ".rb": "Ruby",
        ".cs": "C#",
        ".swift": "Swift",
        ".kt": "Kotlin",
    }
    return lang_map.get(ext.lower(), "Unknown")


def _is_valid_patch(patch: str) -> bool:
    """
    Validate that the patch is in proper unified diff format.

    Args:
        patch: The patch string to validate

    Returns:
        bool: True if patch format is valid
    """
    if not patch or not patch.strip():
        return False

    lines = patch.strip().split("\n")

    # Must have at least header lines
    if len(lines) < 4:
        return False

    # Check for unified diff headers
    has_old_file = any(line.startswith("--- ") for line in lines[:3])
    has_new_file = any(line.startswith("+++ ") for line in lines[:3])
    has_hunk_header = any(line.startswith("@@ ") for line in lines)

    if not (has_old_file and has_new_file and has_hunk_header):
        logger.warning("Invalid patch format - missing headers")
        return False

    # Basic syntax validation
    try:
        for line in lines:
            if line.startswith("@@"):
                # Validate hunk header format
                if not re.match(r"@@ -\d+,?\d* \+\d+,?\d* @@", line):
                    logger.warning(f"Invalid hunk header: {line}")
                    return False
    except Exception as e:
        logger.warning(f"Patch validation error: {e}")
        return False

    return True


def _build_workspace_context(primary_file: str, max_files: int = 5) -> str:
    """
    Build workspace context for cross-file dependency analysis.

    Args:
        primary_file: Primary file being analyzed
        max_files: Maximum number of related files to include

    Returns:
        str: Formatted context of related files
    """
    try:
        # Get workspace root
        workspace_root = Path(primary_file).parent
        while workspace_root.parent != workspace_root:
            if (workspace_root / ".git").exists() or (
                workspace_root / "package.json"
            ).exists():
                break
            workspace_root = workspace_root.parent

        # Find related files (same directory, imports, etc.)
        related_files = []
        primary_path = Path(primary_file)

        # Add files in same directory
        for file in primary_path.parent.glob(f"*.{primary_path.suffix[1:]}"):
            if file != primary_path and len(related_files) < max_files:
                related_files.append(file)

        # Build context string
        context_parts = []
        for file in related_files[:max_files]:
            try:
                with open(file, "r") as f:
                    content = f.read()[:500]  # First 500 chars
                relative_path = file.relative_to(workspace_root)
                context_parts.append(f"File: {relative_path}\n```\n{content}\n```")
            except Exception:
                continue

        return "\n\n".join(context_parts) if context_parts else "No related files found"

    except Exception as e:
        logger.warning(f"Could not build workspace context: {e}")
        return "Workspace context unavailable"


def _analyze_patch_safety(patch: str, original_content: str) -> Dict[str, Any]:
    """
    Analyze patch for safety metrics and confidence scoring.

    Args:
        patch: The generated patch
        original_content: Original file content

    Returns:
        Dict with safety and confidence metrics
    """
    lines = patch.split("\n")

    # Count changes
    additions = len([line for line in lines if line.startswith("+")])
    deletions = len([line for line in lines if line.startswith("-")])

    # Calculate relative change size
    original_lines = len(original_content.split("\n"))
    change_ratio = (additions + deletions) / max(original_lines, 1)

    # Estimate safety based on change characteristics
    safety_score = 1.0

    # Penalize large changes
    if change_ratio > 0.5:
        safety_score *= 0.3  # Major changes are riskier
    elif change_ratio > 0.2:
        safety_score *= 0.6  # Moderate changes
    elif change_ratio > 0.1:
        safety_score *= 0.8  # Small changes

    # Bonus for minimal changes
    if additions + deletions <= 5:
        safety_score *= 1.2

    # Classify safety level
    if safety_score >= 0.8:
        safety_level = "high"
    elif safety_score >= 0.5:
        safety_level = "medium"
    else:
        safety_level = "low"

    return {
        "confidence": min(safety_score, 1.0),
        "safety_level": safety_level,
        "change_stats": {
            "additions": additions,
            "deletions": deletions,
            "change_ratio": round(change_ratio, 3),
        },
        "estimated_risk": (
            "low"
            if safety_score >= 0.7
            else "medium"
            if safety_score >= 0.4
            else "high"
        ),
    }


def _build_workspace_context(primary_file: str, max_files: int = 5) -> str:
    """
    Build workspace context for cross-file dependency analysis.

    Args:
        primary_file: Primary file being analyzed
        max_files: Maximum number of related files to include

    Returns:
        str: Formatted context of related files
    """
    try:
        # Get workspace root
        workspace_root = Path(primary_file).parent
        while workspace_root.parent != workspace_root:
            if (workspace_root / ".git").exists() or (
                workspace_root / "package.json"
            ).exists():
                break
            workspace_root = workspace_root.parent

        # Find related files (same directory, imports, etc.)
        related_files = []
        primary_path = Path(primary_file)

        # Add files in same directory
        for file in primary_path.parent.glob(f"*.{primary_path.suffix[1:]}"):
            if file != primary_path and len(related_files) < max_files:
                related_files.append(file)

        # Build context string
        context_parts = []
        for file in related_files[:max_files]:
            try:
                with open(file, "r") as f:
                    content = f.read()[:500]  # First 500 chars
                relative_path = file.relative_to(workspace_root)
                context_parts.append(f"File: {relative_path}\n```\n{content}\n```")
            except Exception:
                continue

        return "\n\n".join(context_parts) if context_parts else "No related files found"

    except Exception as e:
        logger.warning(f"Could not build workspace context: {e}")
        return "Workspace context unavailable"


def _extract_file_paths_from_patch(patch: str) -> List[str]:
    """
    Extract list of file paths affected by a unified diff patch.

    Args:
        patch: Unified diff patch content

    Returns:
        List of file paths mentioned in the patch
    """
    file_paths = []
    lines = patch.split("\n")

    for line in lines:
        # Look for file headers in unified diff format
        if line.startswith("--- a/") or line.startswith("+++ b/"):
            # Extract path after 'a/' or 'b/'
            path = line[6:]  # Remove '--- a/' or '+++ b/'
            if path not in file_paths:
                file_paths.append(path)
        elif line.startswith("--- ") and not line.startswith("--- a/"):
            # Handle alternate diff formats
            path = line[4:]  # Remove '--- '
            if path not in file_paths and path != "/dev/null":
                file_paths.append(path)
        elif line.startswith("+++ ") and not line.startswith("+++ b/"):
            # Handle alternate diff formats
            path = line[4:]  # Remove '+++ '
            if path not in file_paths and path != "/dev/null":
                file_paths.append(path)

    return file_paths
