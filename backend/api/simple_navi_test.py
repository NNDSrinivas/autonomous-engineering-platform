# backend/api/simple_navi_test.py
"""
Simple non-streaming test for NAVI analysis
"""
from fastapi import APIRouter, HTTPException
import logging
from pathlib import Path
from typing import Dict, Any

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/simple-navi-test")
async def simple_navi_test() -> Dict[str, Any]:
    """
    Simple test of NAVI real review service without streaming
    """
    try:
        # Import real services
        from backend.services.review_service import RealReviewService
        
        # Use current directory
        repo_path = str(Path.cwd())
        logger.info(f"Testing NAVI with repo path: {repo_path}")
        
        # Initialize service
        service = RealReviewService(repo_path)
        
        # Get repository summary
        summary = service.get_repository_summary()
        logger.info(f"Repository summary: {summary}")
        
        # Get first 3 changes only
        changes = service.repo_service.get_working_tree_changes()[:3]
        logger.info(f"Got {len(changes)} changes for analysis")
        
        # Create simple analysis results
        simple_results = []
        for i, change in enumerate(changes):
            result = {
                'file': change['path'],
                'status': change['status'],
                'has_diff': len(change.get('diff', '')) > 0,
                'diff_size': len(change.get('diff', '')),
                'content_size': len(change.get('content', '')),
                'file_type': change.get('file_type', 'unknown')
            }
            simple_results.append(result)
            logger.info(f"Processed file {i+1}: {change['path']}")
        
        return {
            'status': 'success',
            'message': 'NAVI real analysis working!',
            'repo_summary': summary,
            'analyzed_files': len(simple_results),
            'total_changes': len(changes) if changes else 0,
            'sample_files': simple_results
        }
        
    except Exception as e:
        logger.error(f"Simple NAVI test failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")