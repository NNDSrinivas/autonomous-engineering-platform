# backend/api/apply_fix.py
"""
Auto-Fix API Endpoint

Handles AI-powered patch generation for code issues.
Part of Batch 6 — Real Auto-Fix Engine.
"""

from fastapi import APIRouter, HTTPException
import logging
from typing import Dict, Any

from backend.services.auto_fix_service import run_auto_fix, register_fix
from backend.schemas.review_schemas import FixRequest, FixResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repo", tags=["auto-fix"])


@router.post("/register-fix")
async def register_fix_endpoint(request: FixRequest) -> Dict[str, str]:
    """
    Register a new fix for later application.

    Args:
        request: FixRequest with file path, hunk, and issue details

    Returns:
        Dict with generated fix_id
    """
    try:
        fix_id = register_fix(
            file=request.file_path,
            hunk=request.hunk,
            issue=request.issue,
            line_number=request.line_number,
            severity=request.severity,
        )

        logger.info(f"Registered fix with ID: {fix_id}")

        return {"fix_id": fix_id, "status": "registered"}

    except Exception as e:
        logger.error(f"Fix registration failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@router.post("/fix/apply/{fix_id}", response_model=FixResponse)
async def apply_fix(fix_id: str) -> FixResponse:
    """
    Generate AI-powered patch for a specific code issue.

    Args:
        fix_id: Unique identifier for the fix to apply

    Returns:
        FixResponse with generated unified diff patch

    Raises:
        HTTPException: If fix_id not found or patch generation fails
    """
    try:
        logger.info(f"Starting auto-fix for fix_id: {fix_id}")

        # Generate AI-powered patch
        patch_data = await run_auto_fix(fix_id)

        logger.info(f"Auto-fix completed for fix_id: {fix_id}")

        return FixResponse(
            status="success",
            patch=patch_data["patch"],
            file_path=patch_data["file_path"],
            fix_id=fix_id,
            metadata=patch_data.get("metadata", {}),
        )

    except ValueError as e:
        logger.error(f"Invalid fix_id {fix_id}: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Fix not found: {str(e)}")

    except Exception as e:
        logger.error(f"Auto-fix failed for {fix_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Auto-fix failed: {str(e)}")


@router.get("/fix/{fix_id}/status")
async def get_fix_status(fix_id: str) -> Dict[str, Any]:
    """
    Get status of a registered fix.

    Args:
        fix_id: Unique identifier for the fix

    Returns:
        Dict with fix status and metadata
    """
    try:
        from backend.services.auto_fix_service import get_fix_info

        fix_info = get_fix_info(fix_id)
        if not fix_info:
            raise HTTPException(status_code=404, detail="Fix not found")

        return {
            "fix_id": fix_id,
            "status": "ready",
            "file_path": fix_info["file"],
            "issue": fix_info.get("issue", ""),
            "severity": fix_info.get("severity", "info"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Status check failed for {fix_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")
