"""
Streaming Utilities for NAVI - Real-time UX Enhancement

Provides utilities for Cline/Copilot-style real-time streaming:
- Token-by-token content streaming
- Activity event generation
- Progress tracking
- Latency metrics

Usage:
    from backend.services.streaming_utils import StreamingSession, ActivityKind

    session = StreamingSession()
    async for event in session.stream_with_progress(async_generator):
        yield event
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class ActivityKind(str, Enum):
    """Activity event types for real-time UI updates."""
    # Context building
    DETECTION = "detection"
    CONTEXT = "context"
    FILE_READ = "file_read"
    FILE_SCAN = "file_scan"

    # LLM interaction
    PROMPT = "prompt"
    LLM_CALL = "llm_call"
    THINKING = "thinking"
    STREAMING = "streaming"

    # Processing
    PARSING = "parsing"
    VALIDATION = "validation"

    # Actions
    CREATE = "create"
    EDIT = "edit"
    DELETE = "delete"
    COMMAND = "command"

    # Status
    RECOVERY = "recovery"
    RESPONSE = "response"
    COMPLETE = "complete"
    ERROR = "error"


class ActivityStatus(str, Enum):
    """Status of an activity."""
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass
class ActivityEvent:
    """Structured activity event for frontend consumption."""
    kind: ActivityKind
    label: str
    detail: str
    status: ActivityStatus = ActivityStatus.RUNNING
    progress: Optional[float] = None  # 0.0 to 1.0
    timestamp: float = field(default_factory=time.time)
    latency_ms: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "kind": self.kind.value if isinstance(self.kind, ActivityKind) else self.kind,
            "label": self.label,
            "detail": self.detail,
            "status": self.status.value if isinstance(self.status, ActivityStatus) else self.status,
        }
        if self.progress is not None:
            result["progress"] = round(self.progress, 2)
        if self.latency_ms is not None:
            result["latency_ms"] = round(self.latency_ms, 1)
        if self.metadata:
            result["metadata"] = self.metadata
        return result


@dataclass
class StreamingMetrics:
    """Metrics for streaming performance tracking."""
    start_time: float = field(default_factory=time.time)
    first_token_time: Optional[float] = None
    last_token_time: Optional[float] = None
    total_tokens: int = 0
    total_chars: int = 0
    activity_events: int = 0

    @property
    def time_to_first_token_ms(self) -> Optional[float]:
        if self.first_token_time:
            return (self.first_token_time - self.start_time) * 1000
        return None

    @property
    def total_duration_ms(self) -> float:
        end = self.last_token_time or time.time()
        return (end - self.start_time) * 1000

    @property
    def tokens_per_second(self) -> float:
        duration_s = self.total_duration_ms / 1000
        if duration_s > 0:
            return self.total_tokens / duration_s
        return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time_to_first_token_ms": self.time_to_first_token_ms,
            "total_duration_ms": round(self.total_duration_ms, 1),
            "total_tokens": self.total_tokens,
            "total_chars": self.total_chars,
            "tokens_per_second": round(self.tokens_per_second, 1),
            "activity_events": self.activity_events,
        }


class StreamingSession:
    """
    Manages a streaming session with activity tracking and metrics.

    Provides Cline-style real-time streaming experience:
    - Token-by-token content delivery
    - Activity events for UI updates
    - Latency and performance metrics
    """

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or f"stream_{int(time.time() * 1000)}"
        self.metrics = StreamingMetrics()
        self._activity_stack: List[ActivityEvent] = []
        self._start_times: Dict[str, float] = {}

    def activity(
        self,
        kind: ActivityKind,
        label: str,
        detail: str,
        status: ActivityStatus = ActivityStatus.RUNNING,
        progress: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create an activity event for streaming to the frontend.

        Returns:
            Dict with 'activity' key containing the event data
        """
        event = ActivityEvent(
            kind=kind,
            label=label,
            detail=detail,
            status=status,
            progress=progress,
            metadata=metadata,
        )
        self.metrics.activity_events += 1

        # Track timing for latency calculation
        key = f"{kind.value}:{label}"
        if status == ActivityStatus.RUNNING:
            self._start_times[key] = time.time()
        elif status == ActivityStatus.DONE and key in self._start_times:
            event.latency_ms = (time.time() - self._start_times[key]) * 1000
            del self._start_times[key]

        return {"activity": event.to_dict()}

    def start_activity(
        self,
        kind: ActivityKind,
        label: str,
        detail: str,
        progress: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Start a running activity (convenience method)."""
        return self.activity(kind, label, detail, ActivityStatus.RUNNING, progress)

    def complete_activity(
        self,
        kind: ActivityKind,
        label: str,
        detail: str = "Complete",
        progress: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Complete an activity (convenience method)."""
        return self.activity(kind, label, detail, ActivityStatus.DONE, progress)

    def error_activity(
        self,
        kind: ActivityKind,
        label: str,
        detail: str,
    ) -> Dict[str, Any]:
        """Report an error activity."""
        return self.activity(kind, label, detail, ActivityStatus.ERROR)

    def thinking(self, text: str) -> Dict[str, Any]:
        """
        Emit a thinking event (LLM inner monologue).

        Returns:
            Dict with 'thinking' key
        """
        self.metrics.total_chars += len(text)
        if self.metrics.first_token_time is None:
            self.metrics.first_token_time = time.time()
        self.metrics.last_token_time = time.time()
        return {"thinking": text}

    def content(self, text: str) -> Dict[str, Any]:
        """
        Emit a content chunk for token-by-token streaming.

        Returns:
            Dict with 'content' key
        """
        self.metrics.total_chars += len(text)
        self.metrics.total_tokens += 1  # Approximate
        if self.metrics.first_token_time is None:
            self.metrics.first_token_time = time.time()
        self.metrics.last_token_time = time.time()
        return {"content": text}

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current streaming metrics.

        Returns:
            Dict with 'metrics' key
        """
        return {"metrics": self.metrics.to_dict()}

    def heartbeat(self, message: str = "Working...", count: int = 0) -> Dict[str, Any]:
        """
        Emit a heartbeat event to keep the connection alive.

        Returns:
            Dict with 'heartbeat' key
        """
        elapsed = time.time() - self.metrics.start_time
        return {
            "heartbeat": True,
            "message": message,
            "elapsed_seconds": round(elapsed, 1),
            "heartbeat_count": count,
        }


async def heartbeat_generator(
    session: "StreamingSession",
    interval_seconds: float = 15.0,
    messages: Optional[List[str]] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Generate periodic heartbeat events for long-running operations.

    Args:
        session: The streaming session
        interval_seconds: Seconds between heartbeats (default: 15s)
        messages: List of rotating messages to show

    Yields:
        Heartbeat events
    """
    default_messages = [
        "Still working on your request...",
        "Processing...",
        "This may take a moment...",
        "Working on it...",
        "Almost there...",
    ]
    messages = messages or default_messages
    count = 0

    while True:
        await asyncio.sleep(interval_seconds)
        message = messages[count % len(messages)]
        count += 1
        yield session.heartbeat(message, count)


async def stream_with_heartbeat(
    main_generator: AsyncGenerator[Dict[str, Any], None],
    session: Optional["StreamingSession"] = None,
    heartbeat_interval: float = 15.0,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Wrap a generator with automatic heartbeats for long-running operations.

    This ensures the frontend receives periodic updates even when the main
    operation takes a long time.

    Args:
        main_generator: The main async generator to wrap
        session: Optional streaming session (creates one if not provided)
        heartbeat_interval: Seconds between heartbeats

    Yields:
        Events from main generator, interspersed with heartbeats
    """

    session = session or StreamingSession()
    heartbeat_count = 0
    last_heartbeat_time = time.time()

    async for event in main_generator:
        yield event

        # Check if we need to send a heartbeat
        now = time.time()
        if now - last_heartbeat_time >= heartbeat_interval:
            heartbeat_count += 1
            yield session.heartbeat(f"Working... ({heartbeat_count * int(heartbeat_interval)}s elapsed)", heartbeat_count)
            last_heartbeat_time = now


async def stream_text_with_typing(
    text: str,
    chunk_size: int = 3,
    delay_ms: float = 15,
) -> AsyncGenerator[str, None]:
    """
    Stream text with a typing effect for Cline-style UX.

    Preserves formatting (newlines, code blocks) while streaming.

    Args:
        text: Full text to stream
        chunk_size: Number of words per chunk
        delay_ms: Delay between chunks in milliseconds

    Yields:
        Text chunks
    """
    lines = text.split('\n')

    for line_idx, line in enumerate(lines):
        if not line.strip():
            # Empty line, yield newline
            if line_idx > 0:
                yield '\n'
            continue

        # Check if this is a code block marker
        if line.strip().startswith('```'):
            if line_idx > 0:
                yield '\n'
            yield line
            continue

        # Stream words within this line
        words = line.split(' ')

        for i in range(0, len(words), chunk_size):
            chunk_words = words[i:i + chunk_size]
            chunk = ' '.join(chunk_words)

            # Add space after chunk if not at end
            if i + chunk_size < len(words):
                chunk += ' '

            yield chunk

            if delay_ms > 0:
                await asyncio.sleep(delay_ms / 1000)

        # Add newline after each line (except last)
        if line_idx < len(lines) - 1:
            yield '\n'


async def stream_file_operation(
    operation: str,
    file_path: str,
    total_size: Optional[int] = None,
    session: Optional[StreamingSession] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Generate streaming events for a file operation.

    Args:
        operation: "read", "write", "create", "delete"
        file_path: Path to the file
        total_size: Optional file size for progress tracking
        session: Optional streaming session

    Yields:
        Activity events
    """
    session = session or StreamingSession()

    kind_map = {
        "read": ActivityKind.FILE_READ,
        "write": ActivityKind.EDIT,
        "create": ActivityKind.CREATE,
        "delete": ActivityKind.DELETE,
    }

    label_map = {
        "read": "Reading",
        "write": "Writing",
        "create": "Creating",
        "delete": "Deleting",
    }

    kind = kind_map.get(operation, ActivityKind.FILE_READ)
    label = label_map.get(operation, "Processing")

    # Start activity
    yield session.start_activity(
        kind=kind,
        label=label,
        detail=file_path,
        progress=0.0,
    )

    # Simulate progress (actual progress would come from real operation)
    yield session.complete_activity(
        kind=kind,
        label=label,
        detail=file_path,
        progress=1.0,
    )


class ProgressTracker:
    """
    Track progress of multi-step operations.

    Usage:
        tracker = ProgressTracker(total_steps=5)
        for i in range(5):
            progress = tracker.advance()
            yield session.activity(..., progress=progress)
    """

    def __init__(self, total_steps: int):
        self.total_steps = total_steps
        self.current_step = 0

    def advance(self, steps: int = 1) -> float:
        """Advance progress and return current percentage (0.0 to 1.0)."""
        self.current_step = min(self.current_step + steps, self.total_steps)
        return self.current_step / self.total_steps

    def set_step(self, step: int) -> float:
        """Set current step and return percentage."""
        self.current_step = min(step, self.total_steps)
        return self.current_step / self.total_steps

    @property
    def progress(self) -> float:
        """Current progress as percentage (0.0 to 1.0)."""
        return self.current_step / self.total_steps


def format_activity_for_sse(activity_dict: Dict[str, Any]) -> str:
    """
    Format an activity event for Server-Sent Events.

    Args:
        activity_dict: Activity dictionary (from session.activity())

    Returns:
        SSE-formatted string
    """
    import json
    return f"data: {json.dumps(activity_dict)}\n\n"


# Singleton streaming session for shared metrics
_global_sessions: Dict[str, StreamingSession] = {}


def get_or_create_session(session_id: str) -> StreamingSession:
    """Get or create a streaming session by ID."""
    if session_id not in _global_sessions:
        _global_sessions[session_id] = StreamingSession(session_id)
    return _global_sessions[session_id]


def cleanup_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Clean up a session and return its final metrics.

    Returns:
        Final metrics dictionary, or None if session not found
    """
    if session_id in _global_sessions:
        session = _global_sessions.pop(session_id)
        return session.get_metrics()
    return None
