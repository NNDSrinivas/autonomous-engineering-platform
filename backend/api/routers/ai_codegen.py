"""
AI Code Generation API endpoints.
Provides context-aware diff generation and safe patch application.
"""

from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import logging

from backend.core.auth.deps import require_role
from backend.core.auth.models import User, Role
from backend.core.ai.codegen_service import generate_unified_diff
from backend.core.ai.diff_utils import (
    validate_unified_diff,
    apply_diff,
    DiffValidationError,
    count_diff_stats,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["ai-codegen"])


class GenerateDiffIn(BaseModel):
    """Request body for diff generation."""

    intent: str = Field(
        ..., min_length=10, max_length=5000, description="What to implement"
    )
    files: List[str] = Field(
        default_factory=list, description="Target file paths (max 5)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "intent": "Add rate limiting middleware to reject requests with payloads > 1MB",
                "files": [
                    "backend/api/middleware/rate_limit.py",
                    "backend/core/config.py",
                ],
            }
        }


class GenerateDiffOut(BaseModel):
    """Response from diff generation."""

    diff: str = Field(..., description="Unified diff in git format")
    stats: dict = Field(
        ..., description="Diff statistics (files, additions, deletions)"
    )


@router.post("/generate-diff", response_model=GenerateDiffOut)
async def generate_diff(
    body: GenerateDiffIn, user: User = Depends(require_role(Role.PLANNER))
):
    """
    Generate a context-aware unified diff for the given intent.

    Requires 'planner' role.

    Process:
    1. Gathers current file contents and neighboring context
    2. Builds a precise prompt for the AI model
    3. Generates unified diff in git format
    4. Validates the diff before returning

    Security:
    - Max 5 files per request
    - Intent limited to 5000 chars
    - Output validated for safety
    """
    logger.info(f"User {user.user_id} generating diff for {len(body.files)} files")

    try:
        # Generate diff using AI service
        diff = await generate_unified_diff(body.intent, body.files)

        # Validate the generated diff
        try:
            validate_unified_diff(diff)
            files, additions, deletions = count_diff_stats(diff)

            stats = {
                "files": files,
                "additions": additions,
                "deletions": deletions,
                "size_kb": len(diff.encode("utf-8")) / 1024,
            }

            logger.info(f"Generated valid diff: {stats}")
            return {"diff": diff, "stats": stats}

        except DiffValidationError as e:
            logger.error(f"Model output failed validation: {e}")
            raise HTTPException(
                status_code=422,
                detail=f"Model output was not a valid unified diff: {str(e)}",
            )

    except ValueError as e:
        # Input validation errors
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        # Model or service errors
        logger.error(f"Diff generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to generate diff: {str(e)}"
        )


class ApplyPatchIn(BaseModel):
    """Request body for patch application."""

    diff: str = Field(..., min_length=1, description="Unified diff to apply")
    dry_run: bool = Field(default=False, description="Validate only, don't apply")

    class Config:
        json_schema_extra = {
            "example": {"diff": "diff --git a/file.py b/file.py\n...", "dry_run": False}
        }


class ApplyPatchOut(BaseModel):
    """Response from patch application."""

    applied: bool = Field(..., description="Whether patch was applied successfully")
    output: str = Field(..., description="Output from git apply command")
    dry_run: bool = Field(..., description="Was this a dry run?")


@router.post("/apply-patch", response_model=ApplyPatchOut)
async def apply_patch_endpoint(
    body: ApplyPatchIn, user: User = Depends(require_role(Role.ADMIN))
):
    """
    Validate and apply a unified diff to the repository.

    Requires 'admin' role.

    Process:
    1. Validates diff format and size limits
    2. Uses 'git apply --index --whitespace=fix'
    3. Returns success status and git output

    Security:
    - Admin-only operation
    - Validates diff before applying
    - Max 5 files, 2000 additions, 256KB size
    - All operations logged to audit log

    Note: Does NOT auto-commit. Files are staged in git index.
    """
    logger.info(f"User {user.user_id} applying patch (dry_run={body.dry_run})")

    if not body.diff.strip():
        raise HTTPException(status_code=400, detail="Empty diff")

    try:
        # Validate diff format and limits
        validate_unified_diff(body.diff)

        if body.dry_run:
            # In dry run, check if the diff can be applied using git apply --check
            exit_code, output = apply_diff(body.diff, dry_run=True)
            success = exit_code == 0
            if success:
                logger.info("Dry run - diff can be applied successfully")
            else:
                logger.warning(f"Dry run - diff cannot be applied: {output[:200]}")
            return {
                "applied": success,
                "output": (
                    output if success else "Dry run failed: patch cannot be applied"
                ),
                "dry_run": True,
            }

        # Apply the diff
        exit_code, output = apply_diff(body.diff, dry_run=False)

        success = exit_code == 0

        if success:
            logger.info("Patch applied successfully")
            response_output = output
        else:
            logger.warning(f"Patch application failed: {output[:200]}")
            response_output = "Patch application failed. See server logs for details."

        return {"applied": success, "output": response_output, "dry_run": False}

    except DiffValidationError as e:
        logger.error(f"Diff validation failed: {e}")
        raise HTTPException(status_code=422, detail=f"Invalid diff: {str(e)}")

    except Exception as e:
        logger.error(f"Patch application failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to apply patch: {str(e)}")
