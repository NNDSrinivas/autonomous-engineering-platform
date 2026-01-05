# backend/api/debug_navi.py
"""
Debug endpoint for NAVI analysis
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json
import asyncio
import logging
from pathlib import Path

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/debug-analyze")
async def debug_analyze():
    """
    Simple debug endpoint for NAVI analysis
    """

    async def debug_stream():
        try:
            yield f"data: {json.dumps({'type': 'progress', 'step': 'Debug: Starting analysis...', 'progress': 10})}\n\n"
            await asyncio.sleep(0.1)

            yield f"data: {json.dumps({'type': 'progress', 'step': 'Debug: Checking git status...', 'progress': 30})}\n\n"
            await asyncio.sleep(0.1)

            # Import real services
            from backend.services.review_service import RealReviewService

            repo_path = str(Path.cwd())

            yield f"data: {json.dumps({'type': 'progress', 'step': f'Debug: Using repo path {repo_path}', 'progress': 50})}\n\n"
            await asyncio.sleep(0.1)

            service = RealReviewService(repo_path)
            summary = service.get_repository_summary()

            total_changes = summary.get("total_changes", 0)
            yield f"data: {json.dumps({'type': 'progress', 'step': f'Debug: Found {total_changes} changes', 'progress': 80})}\n\n"
            await asyncio.sleep(0.1)

            # Send simple result
            yield f"data: {json.dumps({'type': 'complete', 'step': 'Debug complete!', 'summary': summary, 'progress': 100})}\n\n"

        except Exception as e:
            logger.error(f"Debug analysis failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        debug_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )
