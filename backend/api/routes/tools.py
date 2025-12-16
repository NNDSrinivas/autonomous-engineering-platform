"""
Tool execution API for NAVI agent actions.

This endpoint allows the VS Code extension to execute agent tools directly
(e.g., repo.inspect, code.read_files) and get results back.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...agent.tool_executor import execute_tool

router = APIRouter()


class ToolExecutionRequest(BaseModel):
    """Request to execute a tool."""

    user_id: str
    tool_name: str
    args: Dict[str, Any]
    workspace: Optional[Dict[str, Any]] = None


class ToolExecutionResponse(BaseModel):
    """Response from tool execution."""

    tool: str
    text: str
    output: Optional[Dict[str, Any]] = None
    sources: Optional[list] = None
    error: Optional[str] = None


@router.post("/api/tools/execute", response_model=ToolExecutionResponse)
async def execute_tool_endpoint(
    request: ToolExecutionRequest,
    db: Session = Depends(get_db),
) -> ToolExecutionResponse:
    """
    Execute a tool and return its results.

    This is used by the VS Code extension to run workspace read operations
    (repo.inspect, code.read_files, etc.) when the user clicks "Run step".

    Args:
        request: Tool execution request with user_id, tool_name, and args
        db: Database session

    Returns:
        Tool execution result with text summary and optional structured output

    Raises:
        HTTPException: If tool execution fails
    """
    try:
        result = await execute_tool(
            user_id=request.user_id,
            tool_name=request.tool_name,
            args=request.args,
            db=db,
            workspace=request.workspace,
        )

        return ToolExecutionResponse(
            tool=result.get("tool", request.tool_name),
            text=result.get("text", ""),
            output=result if isinstance(result, dict) else None,
            sources=result.get("sources", []),
            error=result.get("error"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)}")
