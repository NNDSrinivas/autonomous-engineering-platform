# backend/api/smart.py
"""Smart Mode API endpoints."""

from typing import Any, Dict

from fastapi import APIRouter

from backend.services.planner.smart_mode import SmartModePlanner

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


@router.post("/assess")
async def assess_risk(payload: Dict[str, Any]) -> Dict[str, Any]:
    planner = SmartModePlanner()
    assessment = planner.assess_risk(
        changed_files=payload.get("files", []),
        diff_content=payload.get("instruction", ""),
        llm_confidence=payload.get("llm_confidence", 0.9),
    )

    return {
        "mode": _safe_json_value(
            _pick_typed_value(assessment, "recommended_mode", "mode", str)
        ),
        "risk_score": _safe_json_value(
            _pick_typed_value(assessment, "score", "risk_score", (int, float))
        ),
        "risk_level": _safe_json_value(getattr(assessment, "risk_level", None)),
        "reasons": getattr(assessment, "reasons", []),
        "confidence": _safe_json_value(getattr(assessment, "confidence", None)),
        "explanation": _safe_json_value(getattr(assessment, "explanation", None)),
    }
