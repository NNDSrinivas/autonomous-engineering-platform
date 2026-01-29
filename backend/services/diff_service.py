# backend/services/diff_service.py
from typing import Any, Dict


class DiffService:
    """Service for applying diff hunks."""

    def apply_hunk(self, hunk_id: str, file_path: str) -> Dict[str, Any]:
        return {
            "success": False,
            "message": "Hunk application not implemented",
            "lines_changed": 0,
            "hunk_id": hunk_id,
            "file_path": file_path,
        }
