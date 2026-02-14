"""Append-only JSONL trace logging for NAVI model routing and outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import threading
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class TraceEvent:
    event_type: str
    payload: Dict[str, Any]


logger = logging.getLogger(__name__)


class TraceStore:
    def __init__(self, trace_path: Optional[Path] = None) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        self.trace_path = trace_path or (repo_root / "data" / "navi_traces.jsonl")
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, event_type: str, payload: Dict[str, Any]) -> None:
        try:
            record = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                **payload,
            }
            line = json.dumps(record, ensure_ascii=True)
            with self._lock:
                with self.trace_path.open("a", encoding="utf-8") as fh:
                    fh.write(line)
                    fh.write("\n")
        except Exception as exc:
            # Tracing should never break user-facing request handling.
            logger.warning("[TraceStore] Failed to append trace event: %s", exc)


_default_trace_store: Optional[TraceStore] = None


def get_trace_store() -> TraceStore:
    global _default_trace_store
    if _default_trace_store is None:
        _default_trace_store = TraceStore()
    return _default_trace_store
