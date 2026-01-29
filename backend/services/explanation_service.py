# backend/services/explanation_service.py
from typing import Any, Dict


class ExplanationService:
    """Service for explaining diff hunks."""

    def explain_hunk(self, hunk_id: str, file_path: str) -> Dict[str, Any]:
        return {
            "explanation": "Explanation not implemented",
            "complexity": "unknown",
            "impact": "unknown",
            "hunk_id": hunk_id,
            "file_path": file_path,
        }
