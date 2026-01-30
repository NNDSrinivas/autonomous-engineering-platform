# backend/api/apply_fix.py
"""
Auto-Fix API Endpoint

Handles AI-powered patch generation for code issues.
Part of Batch 6 — Real Auto-Fix Engine.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
import logging
from typing import Dict, Any

from backend.services.auto_fix_service import run_auto_fix, register_fix, AutoFixService
from backend.services.review_service import ReviewService
from backend.schemas.review_schemas import FixRequest, FixResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repo", tags=["auto-fix"])


def _safe_json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


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


@router.post("/fix/{fix_id}")
async def apply_fix_legacy(fix_id: str, request: Request) -> JSONResponse:
    """Legacy endpoint used by tests/clients for direct fix application."""
    body = await request.json()
    file_path = body.get("filePath") or body.get("path")
    fix_data = body.get("fixData") or {}

    service = AutoFixService()
    result = service.apply_fix(file_path, fix_id, fix_data)
    message = result.message
    if file_path and file_path not in message:
        message = f"{message} ({file_path})"

    if result.success:
        return JSONResponse(
            status_code=200,
            content={
                "status": "applied",
                "success": True,
                "message": message,
                "file_path": _safe_json_value(result.file_path),
                "fix_id": _safe_json_value(result.fix_id),
            },
        )

    return JSONResponse(
        status_code=400,
        content={
            "status": "failed",
            "success": False,
            "message": message,
            "file_path": _safe_json_value(result.file_path),
            "fix_id": _safe_json_value(result.fix_id),
        },
    )


@router.post("/fixes/batch")
async def apply_batch_fixes(request: Request) -> JSONResponse:
    """Apply multiple fixes in a single request."""
    body = await request.json()
    fixes = body.get("fixes", [])
    if not fixes:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "No fixes provided"},
        )

    service = AutoFixService()
    results = service.apply_batch_fixes(None, fixes)
    total = len(results)
    successful = sum(1 for result in results if result.success)

    serialized = [
        {
            "fix_id": _safe_json_value(result.fix_id),
            "success": result.success,
            "message": result.message,
            "file_path": _safe_json_value(result.file_path),
        }
        for result in results
    ]

    return JSONResponse(
        status_code=200,
        content={
            "total_fixes": total,
            "successful_fixes": successful,
            "results": serialized,
        },
    )


@router.get("/fixes")
async def get_available_fixes(file: str) -> Dict[str, Any]:
    """List available fixes for a file based on review results."""
    service = ReviewService()
    reviews = service.review_files([file])

    fixes = []
    for review in reviews:
        for issue in getattr(review, "issues", []):
            fixes.append(
                {
                    "id": getattr(issue, "id", None),
                    "type": getattr(issue, "type", None),
                    "line": getattr(issue, "line", getattr(issue, "line_number", None)),
                    "description": getattr(issue, "description", None),
                    "fix_available": getattr(issue, "fix_available", False),
                }
            )

    return {
        "file": file,
        "total_fixes": len(fixes),
        "fixes": fixes,
        "available_fixes": fixes,
    }


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
