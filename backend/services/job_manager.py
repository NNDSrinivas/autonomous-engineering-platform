"""
Background job manager for long-running NAVI tasks.

Features:
- in-process execution/task control
- replayable event log with sequence cursors
- optional Redis-backed durability for metadata/events

State model:
- Execution control (`task`, `condition`) is process-local.
- Job metadata/events are mirrored to Redis when available.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

import redis.asyncio as redis


logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"completed", "failed", "canceled"}
_UNSET = object()
DEFAULT_LOCK_TTL_SECONDS = 90


class DistributedLockUnavailableError(RuntimeError):
    """Raised when Redis-backed runner locking is required but unavailable."""


_RELEASE_LOCK_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
else
  return 0
end
"""

_RENEW_LOCK_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('PEXPIRE', KEYS[1], ARGV[2])
else
  return 0
end
"""


@dataclass
class JobRecord:
    job_id: str
    created_at: float
    updated_at: float
    status: str
    phase: str
    user_id: str
    org_id: Optional[str]
    payload: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    pending_approval: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    events: List[Dict[str, Any]] = field(default_factory=list)
    next_sequence: int = 1
    task: Optional[asyncio.Task] = None
    local_runner_token: Optional[str] = None  # Tracks local lock ownership when Redis unavailable
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    condition: asyncio.Condition = field(init=False)

    def __post_init__(self) -> None:
        self.condition = asyncio.Condition(self.lock)

    def to_public(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "phase": self.phase,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "pending_approval": self.pending_approval,
            "error": self.error,
            "last_sequence": self.next_sequence - 1,
            "metadata": self.metadata,
        }

    def to_serializable(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "phase": self.phase,
            "user_id": self.user_id,
            "org_id": self.org_id,
            "payload": self.payload,
            "metadata": self.metadata,
            "pending_approval": self.pending_approval,
            "error": self.error,
            "next_sequence": self.next_sequence,
        }

    @classmethod
    def from_serializable(cls, data: Dict[str, Any]) -> "JobRecord":
        return cls(
            job_id=str(data.get("job_id") or f"job-{uuid4()}"),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
            status=str(data.get("status", "queued")),
            phase=str(data.get("phase", "queued")),
            user_id=str(data.get("user_id") or ""),
            org_id=data.get("org_id"),
            payload=dict(data.get("payload") or {}),
            metadata=dict(data.get("metadata") or {}),
            pending_approval=data.get("pending_approval"),
            error=data.get("error"),
            next_sequence=max(1, int(data.get("next_sequence", 1))),
        )


class JobManager:
    def __init__(self, *, max_events_per_job: int = 5000) -> None:
        self._jobs: Dict[str, JobRecord] = {}
        self._jobs_lock = asyncio.Lock()
        self._max_events = max_events_per_job
        self._max_event_bytes = max(
            256 * 1024, int(os.getenv("NAVI_JOB_MAX_EVENT_BYTES", str(2 * 1024 * 1024)))
        )
        self._max_event_payload_bytes = max(
            8 * 1024,
            int(os.getenv("NAVI_JOB_MAX_EVENT_PAYLOAD_BYTES", str(32 * 1024))),
        )
        self._ttl_seconds = max(300, int(os.getenv("NAVI_JOB_TTL_SECONDS", "86400")))
        self._namespace = os.getenv("NAVI_JOB_NAMESPACE", "navi:jobs")
        self._allow_distributed_degrade = str(
            os.getenv("AEP_ALLOW_DISTRIBUTED_DEGRADE", "false")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self._redis_configured = False
        self._redis: Optional[redis.Redis] = None
        self._redis_available = False
        self._init_redis()

    def _handle_redis_runtime_failure(self, operation: str, exc: Exception) -> bool:
        """
        Handle Redis runtime errors.

        Returns True when local degrade is allowed, False when callers must fail closed.
        """
        if not self._redis_configured:
            logger.warning(
                "[JobManager] Redis %s failed: %s. Redis not configured; using in-memory mode.",
                operation,
                exc,
            )
            self._redis_available = False
            return True

        if self._allow_distributed_degrade:
            logger.warning(
                "[JobManager] Redis %s failed: %s. Degrading to in-memory mode "
                "because AEP_ALLOW_DISTRIBUTED_DEGRADE=true.",
                operation,
                exc,
            )
            self._redis_available = False
            return True

        logger.error(
            "[JobManager] Redis %s failed while distributed locking is required: %s",
            operation,
            exc,
        )
        return False

    def _init_redis(self) -> None:
        try:
            from backend.core.config import settings as config_settings

            url = getattr(config_settings, "redis_url", None)
            if not url:
                self._redis_configured = False
                return
            self._redis_configured = True
            self._redis = redis.from_url(url, encoding="utf-8", decode_responses=True)
            self._redis_available = True
        except Exception as exc:
            logger.warning("[JobManager] Redis disabled for jobs: %s", exc)
            self._redis = None
            self._redis_available = False
            self._redis_configured = False

    def _record_key(self, job_id: str) -> str:
        return f"{self._namespace}:{job_id}:record"

    def _events_key(self, job_id: str) -> str:
        return f"{self._namespace}:{job_id}:events"

    def _lock_key(self, job_id: str) -> str:
        return f"{self._namespace}:{job_id}:runner_lock"

    @staticmethod
    def _event_size_bytes(event_payload: Dict[str, Any]) -> int:
        try:
            return len(
                json.dumps(
                    event_payload, ensure_ascii=False, separators=(",", ":")
                ).encode("utf-8")
            )
        except Exception:
            return len(str(event_payload).encode("utf-8"))

    def _current_events_size(self, events: List[Dict[str, Any]]) -> int:
        return sum(self._event_size_bytes(evt) for evt in events)

    @staticmethod
    def _normalize_redis_token(value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if value is None:
            return ""
        return str(value)

    def _truncate_for_event_storage(
        self, value: Any, *, max_string_len: int = 4096
    ) -> Any:
        if isinstance(value, str):
            if len(value) <= max_string_len:
                return value
            return value[:max_string_len] + "... [truncated]"
        if isinstance(value, dict):
            trimmed: Dict[str, Any] = {}
            for key, item in value.items():
                trimmed[str(key)] = self._truncate_for_event_storage(
                    item, max_string_len=max_string_len
                )
            return trimmed
        if isinstance(value, list):
            limited = value[:200]
            return [
                self._truncate_for_event_storage(item, max_string_len=max_string_len)
                for item in limited
            ]
        return value

    def _sanitize_event_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        event_payload = dict(payload)
        if self._event_size_bytes(event_payload) <= self._max_event_payload_bytes:
            return event_payload

        sanitized = self._truncate_for_event_storage(event_payload, max_string_len=2048)
        if isinstance(sanitized, dict):
            sanitized.setdefault(
                "payload_truncation",
                {
                    "reason": "event_too_large",
                    "max_payload_bytes": self._max_event_payload_bytes,
                },
            )
            return sanitized
        # Fallback should never happen, but keep event format stable.
        return {
            "type": str(event_payload.get("type", "event")),
            "message": "Event payload truncated",
            "payload_truncation": {
                "reason": "event_too_large",
                "max_payload_bytes": self._max_event_payload_bytes,
            },
        }

    async def acquire_runner_lock(
        self,
        job_id: str,
        owner_token: str,
        *,
        ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS,
    ) -> bool:
        async def _acquire_local_lock() -> bool:
            # Best-effort local lock: track ownership with local_runner_token
            # rather than record.task existence to avoid self-blocking on first acquisition.
            record = await self.require_job(job_id)
            async with record.lock:
                if record.local_runner_token is not None:
                    return False
                record.local_runner_token = owner_token
                return True

        if not self._redis_available or not self._redis:
            return await _acquire_local_lock()
        try:
            acquired = await self._redis.set(
                self._lock_key(job_id),
                owner_token,
                ex=max(15, ttl_seconds),
                nx=True,
            )
            return bool(acquired)
        except Exception as exc:
            if self._handle_redis_runtime_failure("acquire_runner_lock", exc):
                return await _acquire_local_lock()
            raise DistributedLockUnavailableError(
                "Redis runner lock unavailable; distributed lock is required"
            ) from exc

    async def renew_runner_lock(
        self,
        job_id: str,
        owner_token: str,
        *,
        ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS,
    ) -> bool:
        if not self._redis_available or not self._redis:
            return True
        try:
            lock_key = self._lock_key(job_id)
            ttl_ms = max(15, ttl_seconds) * 1000
            renewed = await self._redis.eval(
                _RENEW_LOCK_LUA,
                1,
                lock_key,
                str(owner_token),
                ttl_ms,
            )
            return bool(renewed)
        except Exception as exc:
            if self._handle_redis_runtime_failure("renew_runner_lock", exc):
                return True
            raise DistributedLockUnavailableError(
                "Redis runner lock renew unavailable; distributed lock is required"
            ) from exc

    async def release_runner_lock(self, job_id: str, owner_token: str) -> None:
        if not self._redis_available or not self._redis:
            # Clear local lock ownership token
            record = await self.require_job(job_id)
            async with record.lock:
                if record.local_runner_token == owner_token:
                    record.local_runner_token = None
            return
        try:
            lock_key = self._lock_key(job_id)
            await self._redis.eval(
                _RELEASE_LOCK_LUA,
                1,
                lock_key,
                str(owner_token),
            )
        except Exception as exc:
            if not self._handle_redis_runtime_failure("release_runner_lock", exc):
                logger.error(
                    "[JobManager] Failed to release distributed runner lock for %s: %s",
                    job_id,
                    exc,
                )

    async def has_active_runner(self, job_id: str) -> bool:
        if self._redis_available and self._redis:
            try:
                return bool(await self._redis.get(self._lock_key(job_id)))
            except Exception as exc:
                if not self._handle_redis_runtime_failure("has_active_runner", exc):
                    raise DistributedLockUnavailableError(
                        "Redis runner lock lookup unavailable; distributed lock is required"
                    ) from exc
        record = await self.get_job(job_id)
        if not record:
            return False
        async with record.lock:
            return bool(record.task and not record.task.done())

    async def _persist_record(self, record: JobRecord) -> None:
        if not self._redis_available or not self._redis:
            return
        try:
            await self._redis.set(
                self._record_key(record.job_id), json.dumps(record.to_serializable())
            )
            await self._redis.expire(self._record_key(record.job_id), self._ttl_seconds)
        except Exception as exc:
            logger.warning(
                "[JobManager] Failed to persist job record %s: %s", record.job_id, exc
            )

    async def _append_event_redis(
        self, job_id: str, event_payload: Dict[str, Any]
    ) -> None:
        if not self._redis_available or not self._redis:
            return
        try:
            key = self._events_key(job_id)
            await self._redis.rpush(key, json.dumps(event_payload))
            # Trim oldest events.
            await self._redis.ltrim(key, -self._max_events, -1)
            await self._redis.expire(key, self._ttl_seconds)
        except Exception as exc:
            logger.warning(
                "[JobManager] Failed to persist job event %s: %s", job_id, exc
            )

    async def _load_record_redis(self, job_id: str) -> Optional[JobRecord]:
        if not self._redis_available or not self._redis:
            return None
        try:
            raw = await self._redis.get(self._record_key(job_id))
            if not raw:
                return None
            payload = json.loads(raw)
            return JobRecord.from_serializable(payload)
        except Exception as exc:
            logger.warning("[JobManager] Failed loading job record %s: %s", job_id, exc)
            return None

    async def _load_events_redis(self, job_id: str) -> List[Dict[str, Any]]:
        if not self._redis_available or not self._redis:
            return []
        try:
            rows = await self._redis.lrange(self._events_key(job_id), 0, -1)
            events: List[Dict[str, Any]] = []
            for row in rows:
                try:
                    payload = json.loads(row)
                except Exception:
                    continue
                if isinstance(payload, dict):
                    events.append(payload)
            return events
        except Exception as exc:
            logger.warning("[JobManager] Failed loading job events %s: %s", job_id, exc)
            return []

    async def _hydrate_from_redis(self, job_id: str) -> Optional[JobRecord]:
        record = await self._load_record_redis(job_id)
        if not record:
            return None
        events = await self._load_events_redis(job_id)
        if events:
            record.events = events[-self._max_events :]
            max_seq = max(int(evt.get("sequence", 0)) for evt in record.events)
            if max_seq >= record.next_sequence:
                record.next_sequence = max_seq + 1
        async with self._jobs_lock:
            existing = self._jobs.get(job_id)
            if existing:
                # Preserve local task/locks for active process.
                existing.created_at = record.created_at
                existing.updated_at = record.updated_at
                existing.status = record.status
                existing.phase = record.phase
                existing.user_id = record.user_id
                existing.org_id = record.org_id
                existing.payload = record.payload
                existing.metadata = record.metadata
                existing.pending_approval = record.pending_approval
                existing.error = record.error
                existing.events = record.events
                existing.next_sequence = record.next_sequence
                return existing
            self._jobs[job_id] = record
            return record

    async def create_job(
        self,
        *,
        payload: Dict[str, Any],
        user_id: str,
        org_id: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> JobRecord:
        if not str(user_id or "").strip():
            raise ValueError("user_id is required when creating jobs")
        now = time.time()
        record = JobRecord(
            job_id=f"job-{uuid4()}",
            created_at=now,
            updated_at=now,
            status="queued",
            phase="queued",
            user_id=user_id,
            org_id=org_id,
            payload=payload,
            metadata=metadata or {},
        )
        async with self._jobs_lock:
            self._jobs[record.job_id] = record
        await self._persist_record(record)
        await self.append_event(
            record.job_id,
            {
                "type": "job_created",
                "status": "queued",
                "message": "Background job created",
            },
        )
        return record

    async def get_job(self, job_id: str) -> Optional[JobRecord]:
        async with self._jobs_lock:
            record = self._jobs.get(job_id)
        if record:
            # Refresh metadata from Redis for cross-worker visibility.
            refreshed = await self._load_record_redis(job_id)
            if refreshed:
                refreshed_events: Optional[List[Dict[str, Any]]] = None
                if refreshed.next_sequence > record.next_sequence:
                    refreshed_events = await self._load_events_redis(job_id)
                async with record.condition:
                    record.updated_at = refreshed.updated_at
                    record.status = refreshed.status
                    record.phase = refreshed.phase
                    record.user_id = refreshed.user_id
                    record.org_id = refreshed.org_id
                    record.payload = refreshed.payload
                    record.metadata = refreshed.metadata
                    record.pending_approval = refreshed.pending_approval
                    record.error = refreshed.error
                    # Keep sequence monotonic across workers to prevent
                    # duplicate/out-of-order event sequence assignment.
                    if refreshed.next_sequence > record.next_sequence:
                        record.next_sequence = refreshed.next_sequence
                    if refreshed_events:
                        record.events = refreshed_events[-self._max_events :]
                        max_seq = max(
                            int(evt.get("sequence", 0)) for evt in record.events
                        )
                        if max_seq >= record.next_sequence:
                            record.next_sequence = max_seq + 1
            return record
        return await self._hydrate_from_redis(job_id)

    async def require_job(self, job_id: str) -> JobRecord:
        record = await self.get_job(job_id)
        if not record:
            raise KeyError(job_id)
        return record

    async def append_event(self, job_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        record = await self.require_job(job_id)
        async with record.condition:
            sequence = record.next_sequence
            record.next_sequence += 1
            record.updated_at = time.time()
            event_payload = self._sanitize_event_payload(event)
            event_payload["sequence"] = sequence
            event_payload["job_id"] = record.job_id
            event_payload["job_status"] = record.status
            event_payload.setdefault("timestamp", int(record.updated_at * 1000))
            record.events.append(event_payload)
            truncated_count = 0
            truncated_bytes = 0
            if len(record.events) > self._max_events:
                excess = len(record.events) - self._max_events
                truncated_count += excess
                trimmed = record.events[:excess]
                truncated_bytes += self._current_events_size(trimmed)
                record.events = record.events[-self._max_events :]

            total_bytes = self._current_events_size(record.events)
            while len(record.events) > 1 and total_bytes > self._max_event_bytes:
                removed = record.events.pop(0)
                truncated_count += 1
                removed_size = self._event_size_bytes(removed)
                truncated_bytes += removed_size
                total_bytes -= removed_size

            if truncated_count > 0:
                event_payload.setdefault(
                    "truncation",
                    {
                        "truncated_events": truncated_count,
                        "truncated_bytes": truncated_bytes,
                        "reason": "older_events_dropped",
                    },
                )
            await self._persist_record(record)
            await self._append_event_redis(record.job_id, event_payload)
            record.condition.notify_all()
            return event_payload

    async def set_status(
        self,
        job_id: str,
        *,
        status: Optional[str] = None,
        phase: Optional[str] = None,
        error: Optional[str] = None,
        pending_approval: Any = _UNSET,
    ) -> JobRecord:
        record = await self.require_job(job_id)
        async with record.condition:
            if status is not None:
                record.status = status
                # Clear local lock ownership when reaching terminal state
                if status in TERMINAL_STATUSES:
                    record.local_runner_token = None
            if phase is not None:
                record.phase = phase
            if error is not None:
                record.error = error
            if pending_approval is not _UNSET:
                record.pending_approval = pending_approval
            record.updated_at = time.time()
            await self._persist_record(record)
            record.condition.notify_all()
            return record

    async def update_metadata(self, job_id: str, patch: Dict[str, Any]) -> JobRecord:
        record = await self.require_job(job_id)
        async with record.condition:
            merged = dict(record.metadata or {})
            merged.update(patch or {})
            record.metadata = merged
            record.updated_at = time.time()
            await self._persist_record(record)
            record.condition.notify_all()
            return record

    async def request_cancel(
        self, job_id: str, requested_by: Optional[str] = None
    ) -> JobRecord:
        record = await self.require_job(job_id)
        async with record.condition:
            metadata = dict(record.metadata or {})
            metadata["cancel_requested"] = True
            if requested_by:
                metadata["cancel_requested_by"] = requested_by
            metadata["cancel_requested_at"] = time.time()
            record.metadata = metadata
            record.updated_at = time.time()
            await self._persist_record(record)
            record.condition.notify_all()
            return record

    async def clear_cancel_request(self, job_id: str) -> JobRecord:
        record = await self.require_job(job_id)
        async with record.condition:
            metadata = dict(record.metadata or {})
            metadata.pop("cancel_requested", None)
            metadata.pop("cancel_requested_by", None)
            metadata.pop("cancel_requested_at", None)
            record.metadata = metadata
            record.updated_at = time.time()
            await self._persist_record(record)
            record.condition.notify_all()
            return record

    async def is_cancel_requested(self, job_id: str) -> bool:
        record = await self.require_job(job_id)
        async with record.lock:
            return bool((record.metadata or {}).get("cancel_requested"))

    async def set_task(self, job_id: str, task: asyncio.Task) -> None:
        record = await self.require_job(job_id)
        async with record.condition:
            record.task = task
            record.updated_at = time.time()
            await self._persist_record(record)
            record.condition.notify_all()

    async def set_task_if_idle(self, job_id: str, task: asyncio.Task) -> bool:
        record = await self.require_job(job_id)
        async with record.condition:
            if record.task and not record.task.done():
                return False
            record.task = task
            record.updated_at = time.time()
            await self._persist_record(record)
            record.condition.notify_all()
            return True

    async def cancel_job(self, job_id: str) -> JobRecord:
        await self.request_cancel(job_id)
        record = await self.require_job(job_id)
        task: Optional[asyncio.Task] = None
        async with record.condition:
            if record.status in TERMINAL_STATUSES:
                return record
            record.status = "canceled"
            record.phase = "canceled"
            record.pending_approval = None
            record.updated_at = time.time()
            task = record.task
            await self._persist_record(record)
            record.condition.notify_all()
        if task and not task.done():
            task.cancel()
        await self.append_event(
            job_id,
            {
                "type": "job_canceled",
                "status": "canceled",
                "message": "Job canceled by user request",
            },
        )
        return record

    async def get_events_after(
        self, job_id: str, after_sequence: int
    ) -> List[Dict[str, Any]]:
        record = await self.require_job(job_id)
        redis_events = await self._load_events_redis(job_id)
        if redis_events:
            async with record.lock:
                record.events = redis_events[-self._max_events :]
                max_seq = max(
                    (int(evt.get("sequence", 0)) for evt in record.events), default=0
                )
                if max_seq >= record.next_sequence:
                    record.next_sequence = max_seq + 1
        async with record.lock:
            return [
                evt
                for evt in record.events
                if int(evt.get("sequence", 0)) > after_sequence
            ]

    async def wait_for_events(
        self,
        job_id: str,
        *,
        after_sequence: int,
        timeout_seconds: float = 15.0,
    ) -> List[Dict[str, Any]]:
        record = await self.require_job(job_id)
        deadline = time.time() + timeout_seconds
        poll_interval = 1.0
        while time.time() < deadline:
            ready = await self.get_events_after(job_id, after_sequence)
            if ready:
                return ready
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            wait_for = min(poll_interval, remaining)
            # Local notify path (same process) + periodic poll path (cross-process).
            async with record.condition:
                try:
                    await asyncio.wait_for(record.condition.wait(), timeout=wait_for)
                except asyncio.TimeoutError:
                    pass
        return await self.get_events_after(job_id, after_sequence)

    async def is_terminal(self, job_id: str) -> bool:
        record = await self.require_job(job_id)
        async with record.lock:
            return record.status in TERMINAL_STATUSES


_job_manager: Optional[JobManager] = None


def get_job_manager() -> JobManager:
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager
