"""
CI Failures API - Support for CI failure fixer extension

Provides endpoints for:
- Fetching latest CI failures
- Triggering CI failure analysis
- Managing CI failure fix proposals
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
import logging

from .agent.execution_engine.ci_failure_engine import CIFailureAnalyzer
from .core.tenancy import require_tenant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ci", tags=["ci"])

class CIFailureResponse(BaseModel):
    """CI failure information"""
    job: str
    step: str
    error_message: str
    log_snippet: str
    file_path: Optional[str]
    line_number: Optional[int]
    failure_type: str
    full_logs: str

class CIFailureRequest(BaseModel):
    """Request CI failure analysis"""
    project: str
    repo_url: Optional[str]
    ci_provider: str = "github"

@router.get("/failures/latest")
async def get_latest_failure(
    project: str,
    repo_url: Optional[str] = None,
    tenant=Depends(require_tenant)
) -> Optional[CIFailureResponse]:
    """Get the latest CI failure for a project"""
    try:
        # For now, we'll return a mock failure since we don't have real CI integration
        # In production, this would query the actual CI provider
        
        analyzer = CIFailureAnalyzer()
        
        # Mock CI log for testing
        mock_ci_log = """
        [2024-12-25T10:30:00.000Z] Starting npm install...
        [2024-12-25T10:30:01.000Z] npm WARN deprecated package@1.0.0: This package is deprecated
        [2024-12-25T10:30:02.000Z] npm ERR! code ERESOLVE
        [2024-12-25T10:30:02.000Z] npm ERR! Cannot resolve dependency "react-nonexistent-lib"
        [2024-12-25T10:30:02.000Z] npm ERR! Could not resolve dependency:
        [2024-12-25T10:30:02.000Z] npm ERR! peer react-nonexistent-lib@"^1.0.0" from the root project
        [2024-12-25T10:30:02.000Z] npm ERR! 
        [2024-12-25T10:30:02.000Z] npm ERR! Fix the upstream dependency conflict, or retry
        [2024-12-25T10:30:02.000Z] npm ERR! this command with --force, or --legacy-peer-deps
        [2024-12-25T10:30:02.000Z] npm install failed with exit code 1
        """
        
        # Analyze the mock failure
        failures = analyzer.analyze_ci_failure(mock_ci_log, "build", "install-dependencies")
        
        if not failures:
            return None
            
        failure = failures[0]  # Return first failure
        
        return CIFailureResponse(
            job=failure.job,
            step=failure.step,
            error_message=failure.error_message,
            log_snippet=failure.log_snippet,
            file_path=failure.file_path,
            line_number=failure.line_number,
            failure_type=failure.failure_type,
            full_logs=mock_ci_log
        )
        
    except Exception as e:
        logger.error(f"Failed to get latest CI failure: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch CI failure data")

@router.post("/failures/analyze")
async def analyze_ci_logs(
    ci_logs: str,
    job_name: str = "build",
    step_name: str = "unknown",
    tenant=Depends(require_tenant)
) -> List[CIFailureResponse]:
    """Analyze CI logs and extract failure information"""
    try:
        analyzer = CIFailureAnalyzer()
        failures = analyzer.analyze_ci_failure(ci_logs, job_name, step_name)
        
        return [
            CIFailureResponse(
                job=failure.job,
                step=failure.step,
                error_message=failure.error_message,
                log_snippet=failure.log_snippet,
                file_path=failure.file_path,
                line_number=failure.line_number,
                failure_type=failure.failure_type,
                full_logs=ci_logs
            )
            for failure in failures
        ]
        
    except Exception as e:
        logger.error(f"Failed to analyze CI logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze CI logs")