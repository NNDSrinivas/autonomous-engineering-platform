"""
Event Emitter for NAVI Streaming

Provides ordered event streaming with sequence numbers for consistent
frontend rendering. Events are guaranteed to arrive in order.

Usage:
    emitter = EventEmitter()
    yield emitter.thinking_start("Analyzing your request...")
    yield emitter.file_read("src/index.ts", "entry point")
    yield emitter.narrative("I found the main entry point...")
    yield emitter.tool_complete(tool_id, result)
"""

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import time
import uuid
from typing import Any, Dict, Optional


class StreamEventType(Enum):
    """Types of streaming events"""
    THINKING_START = "thinking_start"
    THINKING_DELTA = "thinking_delta"
    THINKING_COMPLETE = "thinking_complete"
    TOOL_START = "tool_start"
    TOOL_DELTA = "tool_delta"
    TOOL_COMPLETE = "tool_complete"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_EDIT = "file_edit"
    NARRATIVE = "navi.narrative"
    INTENT_DETECTED = "intent.detected"
    ACTIVITY = "activity"
    CONTEXT = "context"
    DETECTION = "detection"
    RAG = "rag"
    RESPONSE = "response"
    RESULT = "result"
    ERROR = "error"


@dataclass
class StreamEvent:
    """A single streaming event with ordering metadata"""
    type: StreamEventType
    data: Dict[str, Any]
    sequence: int = field(default_factory=lambda: int(time.time() * 1000))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for SSE transmission"""
        return {
            "type": self.type.value,
            "data": self.data,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
        }


class EventEmitter:
    """
    Emitter for ordered streaming events.

    Creates events with incrementing sequence numbers to ensure
    the frontend can process them in the correct order.
    """

    def __init__(self):
        self._sequence = 0
        self._start_time = time.time()

    def _next_sequence(self) -> int:
        """Get next sequence number"""
        self._sequence += 1
        return self._sequence

    def _make_event(self, event_type: StreamEventType, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an event dictionary ready for SSE transmission"""
        return StreamEvent(
            type=event_type,
            data=data,
            sequence=self._next_sequence(),
        ).to_dict()

    # === Thinking Events ===

    def thinking_start(self, context: str = "") -> Dict[str, Any]:
        """Emit when LLM starts thinking/analyzing"""
        return {
            "activity": {
                "kind": "thinking",
                "label": "Analyzing",
                "detail": context or "Understanding your request...",
                "status": "running",
                "sequence": self._next_sequence(),
            }
        }

    def thinking_delta(self, text: str) -> Dict[str, Any]:
        """Emit streaming thinking text"""
        return {
            "thinking": text,
            "sequence": self._next_sequence(),
        }

    def thinking_complete(self) -> Dict[str, Any]:
        """Emit when thinking is complete"""
        return {
            "activity": {
                "kind": "thinking",
                "label": "Analysis complete",
                "detail": "Ready to proceed",
                "status": "done",
                "sequence": self._next_sequence(),
            }
        }

    # === Intent Events ===

    def intent_start(self) -> Dict[str, Any]:
        """Emit when starting intent classification"""
        return {
            "activity": {
                "kind": "intent",
                "label": "Understanding request",
                "detail": "Classifying intent...",
                "status": "running",
                "sequence": self._next_sequence(),
            }
        }

    def intent_detected(
        self,
        family: str,
        kind: str,
        confidence: float,
        description: str = ""
    ) -> Dict[str, Any]:
        """Emit when intent has been classified"""
        confidence_pct = int(confidence * 100)
        return {
            "intent": {
                "family": family,
                "kind": kind,
                "confidence": confidence,
            },
            "activity": {
                "kind": "intent",
                "label": "Understanding request",
                "detail": f"Detected: {kind} ({confidence_pct}%)",
                "status": "done",
                "sequence": self._next_sequence(),
            }
        }

    # === File Operation Events ===

    def file_read_start(self, file_path: str, purpose: str = "") -> Dict[str, Any]:
        """Emit when starting to read a file"""
        return {
            "activity": {
                "kind": "read",
                "label": "Reading",
                "detail": file_path,
                "filePath": file_path,
                "status": "running",
                "sequence": self._next_sequence(),
            }
        }

    def file_read(self, file_path: str, purpose: str = "") -> Dict[str, Any]:
        """Emit when a file has been read"""
        return {
            "activity": {
                "kind": "read",
                "label": "Read",
                "detail": file_path,
                "filePath": file_path,
                "status": "done",
                "sequence": self._next_sequence(),
            }
        }

    def file_write(self, file_path: str, action: str = "Created") -> Dict[str, Any]:
        """Emit when a file has been created"""
        return {
            "activity": {
                "kind": "create",
                "label": action,
                "detail": file_path,
                "filePath": file_path,
                "status": "done",
                "sequence": self._next_sequence(),
            }
        }

    def file_edit(self, file_path: str, description: str = "Modified") -> Dict[str, Any]:
        """Emit when a file has been edited"""
        return {
            "activity": {
                "kind": "edit",
                "label": "Edited",
                "detail": file_path,
                "filePath": file_path,
                "status": "done",
                "sequence": self._next_sequence(),
            }
        }

    # === Tool Events ===

    def tool_start(
        self,
        tool_name: str,
        tool_id: Optional[str] = None,
        description: str = ""
    ) -> Dict[str, Any]:
        """Emit when a tool starts execution"""
        tid = tool_id or str(uuid.uuid4())[:8]
        return {
            "activity": {
                "kind": "tool",
                "label": tool_name.replace("_", " ").title(),
                "detail": description or f"Running {tool_name}...",
                "toolId": tid,
                "status": "running",
                "sequence": self._next_sequence(),
            }
        }

    def tool_complete(
        self,
        tool_id: str,
        result: Dict[str, Any],
        success: bool = True
    ) -> Dict[str, Any]:
        """Emit when a tool completes"""
        return {
            "activity": {
                "kind": "tool",
                "label": "Complete" if success else "Failed",
                "detail": result.get("summary", "Tool execution finished"),
                "toolId": tool_id,
                "status": "done" if success else "error",
                "result": result,
                "sequence": self._next_sequence(),
            }
        }

    # === Context Events ===

    def context_start(self, description: str = "Gathering workspace information") -> Dict[str, Any]:
        """Emit when starting to build context"""
        return {
            "activity": {
                "kind": "context",
                "label": "Building context",
                "detail": description,
                "status": "running",
                "sequence": self._next_sequence(),
            }
        }

    def context_complete(self, summary: str = "Complete") -> Dict[str, Any]:
        """Emit when context building is complete"""
        return {
            "activity": {
                "kind": "context",
                "label": "Building context",
                "detail": summary,
                "status": "done",
                "sequence": self._next_sequence(),
            }
        }

    def project_detected(self, project_type: str, framework: str = "") -> Dict[str, Any]:
        """Emit project detection result"""
        detail = framework or project_type
        return {
            "activity": {
                "kind": "detection",
                "label": "Detected",
                "detail": detail,
                "status": "done",
                "sequence": self._next_sequence(),
            }
        }

    def rag_search(self, query: str, results_count: int = 0) -> Dict[str, Any]:
        """Emit RAG search activity"""
        return {
            "activity": {
                "kind": "rag",
                "label": "Searching code index",
                "detail": f"Found {results_count} relevant symbols" if results_count else "Searching...",
                "status": "done" if results_count else "running",
                "sequence": self._next_sequence(),
            }
        }

    # === Narrative Events ===

    def narrative(self, content: str, phase: str = "explaining") -> Dict[str, Any]:
        """
        Emit a narrative event - LLM-generated explanation.

        These are conversational messages shown to the user during
        processing, like Claude Code's streaming explanations.
        """
        return {
            "narrative": content,
            "phase": phase,
            "sequence": self._next_sequence(),
        }

    # === Response Events ===

    def response_start(self, description: str = "Generating response") -> Dict[str, Any]:
        """Emit when starting to generate response"""
        return {
            "activity": {
                "kind": "response",
                "label": "Generating response",
                "detail": description,
                "status": "running",
                "sequence": self._next_sequence(),
            }
        }

    def response_complete(self) -> Dict[str, Any]:
        """Emit when response generation is complete"""
        return {
            "activity": {
                "kind": "response",
                "label": "Generating response",
                "detail": "Complete",
                "status": "done",
                "sequence": self._next_sequence(),
            }
        }

    def content_chunk(self, content: str) -> Dict[str, Any]:
        """Emit a content chunk for streaming the response"""
        return {
            "content": content,
            "sequence": self._next_sequence(),
        }

    # === Error Events ===

    def error(self, message: str, details: str = "") -> Dict[str, Any]:
        """Emit an error event"""
        return {
            "error": message,
            "details": details,
            "activity": {
                "kind": "error",
                "label": "Error",
                "detail": message,
                "status": "error",
                "sequence": self._next_sequence(),
            }
        }

    # === Result Event ===

    def result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Emit the final result"""
        return {
            "result": data,
            "sequence": self._next_sequence(),
        }


# Convenience function for creating a new emitter
def create_emitter() -> EventEmitter:
    """Create a new EventEmitter instance"""
    return EventEmitter()
