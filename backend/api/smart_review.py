# backend/api/smart_review.py
"""Smart Mode review endpoint."""

from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json
from typing import AsyncGenerator

from backend.services.planner.smart_mode import SmartModePlanner


class AutonomousRefactorEngine:
    """Placeholder engine for auto-apply Smart Mode changes."""

    def apply_changes(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": False,
            "files_modified": [],
            "patch_summary": "Auto-apply not implemented",
        }


router = APIRouter(prefix="/api/smart", tags=["smart"])


def _safe_json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _pick_typed_value(obj: Any, primary: str, fallback: str, expected_type: Any) -> Any:
    primary_value = getattr(obj, primary, None)
    if isinstance(primary_value, expected_type):
        return primary_value
    fallback_value = getattr(obj, fallback, None)
    if isinstance(fallback_value, expected_type):
        return fallback_value
    return primary_value if primary_value is not None else fallback_value


@router.post("/review")
async def smart_review(payload: Dict[str, Any]) -> Dict[str, Any]:
    planner = SmartModePlanner()
    assessment = planner.assess_risk(
        changed_files=payload.get("files", []),
        diff_content=payload.get("instruction", ""),
        llm_confidence=payload.get("llm_confidence", 0.9),
    )

    mode = _pick_typed_value(assessment, "recommended_mode", "mode", str) or "smart"
    response: Dict[str, Any] = {"mode": _safe_json_value(mode)}

    if mode == "auto":
        engine = AutonomousRefactorEngine()
        response.update(engine.apply_changes(payload))
        response["mode"] = "auto"
        return response

    response.update(
        {
            "success": False,
            "files_modified": [],
            "patch_summary": "Auto-apply not permitted for this risk level",
        }
    )
    return response


@router.post("/review/stream")
async def smart_review_stream(payload: Dict[str, Any]) -> StreamingResponse:
    async def event_stream() -> AsyncGenerator[str, None]:
        if not payload.get("files"):
            yield f"event: error\ndata: {json.dumps({'message': 'No files provided'})}\n\n"
            return

        planner = SmartModePlanner()
        assessment = planner.assess_risk(
            changed_files=payload.get("files", []),
            diff_content=payload.get("instruction", ""),
            llm_confidence=payload.get("llm_confidence", 0.9),
        )

        mode = _pick_typed_value(assessment, "recommended_mode", "mode", str) or "smart"
        event_data = {
            "mode": _safe_json_value(mode),
            "risk_score": _safe_json_value(getattr(assessment, "risk_score", None)),
            "risk_level": _safe_json_value(getattr(assessment, "risk_level", None)),
            "reasons": _safe_json_value(getattr(assessment, "reasons", None)),
            "confidence": _safe_json_value(getattr(assessment, "confidence", None)),
            "explanation": _safe_json_value(getattr(assessment, "explanation", None)),
        }

        yield f"event: modeSelected\ndata: {json.dumps(event_data)}\n\n"
        yield f"event: done\ndata: {json.dumps({'status': 'completed'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
