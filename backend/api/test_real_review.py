# backend/api/test_real_review.py
"""
Test endpoint for real git review service
"""
from fastapi import APIRouter, Query, HTTPException
from pathlib import Path
import logging
from typing import Optional

from backend.services.review_service import RealReviewService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/test-real-review")
async def test_real_review(workspace_root: Optional[str] = Query(None)):
    """
    Test the real review service with current repository
    """
    try:
        # Get workspace root
        repo_path = workspace_root or str(Path.cwd())

        # Initialize service
        service = RealReviewService(repo_path)

        # Get repository summary
        summary = service.get_repository_summary()

        # Get working tree changes
        changes = service.repo_service.get_working_tree_changes()

        return {
            "status": "success",
            "repo_summary": summary,
            "changes_count": len(changes),
            "sample_changes": changes[:3] if changes else [],
            "message": f"Found {len(changes)} changed files in repository",
        }

    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
