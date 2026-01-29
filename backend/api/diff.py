# backend/api/diff.py
from typing import Any, Dict

from fastapi import APIRouter, Request

from backend.services.diff_service import DiffService
from backend.services.explanation_service import ExplanationService
from backend.services.diff_metadata_builder import DiffMetadataBuilder

router = APIRouter(prefix="/api/diff", tags=["diff"])


@router.post("/apply-hunk")
async def apply_hunk(payload: Dict[str, Any]) -> Dict[str, Any]:
    service = DiffService()
    return service.apply_hunk(payload.get("hunk_id"), payload.get("file_path"))


@router.post("/explain-hunk")
async def explain_hunk(payload: Dict[str, Any]) -> Dict[str, Any]:
    service = ExplanationService()
    return service.explain_hunk(payload.get("hunk_id"), payload.get("file_path"))


@router.post("/metadata")
async def diff_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
    builder = DiffMetadataBuilder()
    base_lines = payload.get("base_content", "").splitlines()
    target_lines = payload.get("target_content", "").splitlines()
    file_path = payload.get("file_path", "")
    return builder.build(base_lines, target_lines, file_path)
