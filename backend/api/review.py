# backend/api/review.py
"""Review API endpoints for file and working-tree analysis."""

from typing import Any, Dict, List

from fastapi import APIRouter

from backend.services.review_service import ReviewService

router = APIRouter(prefix="/api/review", tags=["review"])


@router.post("/working-tree")
async def review_working_tree(payload: Dict[str, Any]) -> Dict[str, Any]:
    service = ReviewService(repo_path=payload.get("workspace_root"))
    return service.review_working_tree()


@router.get("/file")
async def review_single_file(path: str) -> Dict[str, Any]:
    service = ReviewService()
    reviews = service.review_files([path])

    issues: List[Dict[str, Any]] = []
    for review in reviews:
        for issue in getattr(review, "issues", []):
            issues.append(
                {
                    "type": getattr(issue, "type", None),
                    "line": getattr(issue, "line", getattr(issue, "line_number", None)),
                    "description": getattr(issue, "description", None),
                    "severity": getattr(issue, "severity", None),
                }
            )

    return {"file_path": path, "issues": issues}
