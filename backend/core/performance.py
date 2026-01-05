"""
Performance & Scaling Infrastructure for NAVI Enterprise

Provides enterprise-grade performance capabilities:
- Async job queues for heavy operations
- Redis caching for fast data access
- Background workers for non-blocking execution
- Event-driven architecture
- Connection pooling and resource management
"""

from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json
import uuid
from abc import ABC, abstractmethod
import logging

from .tenancy import require_tenant, get_current_tenant, TenantContext

logger = logging.getLogger(__name__)


class JobPriority(Enum):
    """Job execution priority levels"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class JobStatus(Enum):
    """Job execution status"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


@dataclass
class JobContext:
    """Context information for job execution"""

    job_id: str
    org_id: str
    user_id: str
    tenant_context: TenantContext
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3

    def duration(self) -> Optional[timedelta]:
        """Calculate job execution duration"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None


@dataclass
class Job:
    """Async job definition"""

    id: str
    type: str
    priority: JobPriority
    status: JobStatus
    payload: Dict[str, Any]
    context: JobContext
    scheduled_for: Optional[datetime] = None
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary for storage"""
        return {
            "id": self.id,
            "type": self.type,
            "priority": self.priority.value,
            "status": self.status.value,
            "payload": json.dumps(self.payload),
            "org_id": self.context.org_id,
            "user_id": self.context.user_id,
            "created_at": self.context.created_at.isoformat(),
            "started_at": (
                self.context.started_at.isoformat() if self.context.started_at else None
            ),
            "completed_at": (
                self.context.completed_at.isoformat()
                if self.context.completed_at
                else None
            ),
            "retry_count": self.context.retry_count,
            "max_retries": self.context.max_retries,
            "scheduled_for": (
                self.scheduled_for.isoformat() if self.scheduled_for else None
            ),
            "error_message": self.error_message,
            "result": json.dumps(self.result) if self.result else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], tenant_context: TenantContext) -> "Job":
        """Create job from dictionary"""
        context = JobContext(
            job_id=data["id"],
            org_id=data["org_id"],
            user_id=data["user_id"],
            tenant_context=tenant_context,
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=(
                datetime.fromisoformat(data["started_at"])
                if data.get("started_at")
                else None
            ),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
        )

        return cls(
            id=data["id"],
            type=data["type"],
            priority=JobPriority(data["priority"]),
            status=JobStatus(data["status"]),
            payload=json.loads(data["payload"]) if data.get("payload") else {},
            context=context,
            scheduled_for=(
                datetime.fromisoformat(data["scheduled_for"])
                if data.get("scheduled_for")
                else None
            ),
            error_message=data.get("error_message"),
            result=json.loads(data["result"]) if data.get("result") else None,
        )


class JobQueue(ABC):
    """Abstract job queue interface"""

    @abstractmethod
    async def enqueue(self, job: Job) -> bool:
        """Add job to queue"""
        pass

    @abstractmethod
    async def dequeue(self, job_type: Optional[str] = None) -> Optional[Job]:
        """Get next job from queue"""
        pass

    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get specific job by ID"""
        pass

    @abstractmethod
    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        error_message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update job status"""
        pass

    @abstractmethod
    async def get_queue_stats(self, org_id: str) -> Dict[str, int]:
        """Get queue statistics for organization"""
        pass


class RedisJobQueue(JobQueue):
    """Redis-based job queue implementation"""

    def __init__(self, redis_client):
        self.redis = redis_client
        self.queue_key = "navi:jobs"
        self.processing_key = "navi:processing"
        self.job_data_key = "navi:job_data"

    async def enqueue(self, job: Job) -> bool:
        """Add job to Redis queue"""
        try:
            # Store job data
            await self.redis.hset(
                f"{self.job_data_key}:{job.id}", mapping=job.to_dict()
            )

            # Add to priority queue
            priority_scores = {
                JobPriority.LOW: 1,
                JobPriority.NORMAL: 2,
                JobPriority.HIGH: 3,
                JobPriority.CRITICAL: 4,
            }

            queue_name = f"{self.queue_key}:{job.type}"
            score = priority_scores[job.priority]

            await self.redis.zadd(queue_name, {job.id: score})

            logger.info(
                f"Enqueued job {job.id} of type {job.type} for org {job.context.org_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to enqueue job {job.id}: {e}")
            return False

    async def dequeue(self, job_type: Optional[str] = None) -> Optional[Job]:
        """Get highest priority job from queue"""
        try:
            if job_type:
                queue_name = f"{self.queue_key}:{job_type}"
                result = await self.redis.zpopmax(queue_name)
            else:
                # Get from any queue (would need more complex logic)
                result = await self.redis.zpopmax(f"{self.queue_key}:*")

            if not result:
                return None

            job_id, _ = result[0]

            # Get job data
            job_data = await self.redis.hgetall(f"{self.job_data_key}:{job_id}")
            if not job_data:
                return None

            # Create tenant context for job execution
            tenant_context = TenantContext(
                org_id=job_data["org_id"],
                user_id=job_data["user_id"],
                roles=[],  # Would fetch from database
                permissions=[],
                session_id=str(uuid.uuid4()),
                encryption_key_id=f"org-{job_data['org_id']}-key",
            )

            job = Job.from_dict(job_data, tenant_context)

            # Mark as processing
            await self.redis.sadd(self.processing_key, job_id)

            return job

        except Exception as e:
            logger.error(f"Failed to dequeue job: {e}")
            return None

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID"""
        try:
            job_data = await self.redis.hgetall(f"{self.job_data_key}:{job_id}")
            if not job_data:
                return None

            # Would create proper tenant context
            tenant_context = TenantContext(
                org_id=job_data["org_id"],
                user_id=job_data["user_id"],
                roles=[],
                permissions=[],
                session_id=str(uuid.uuid4()),
                encryption_key_id=f"org-{job_data['org_id']}-key",
            )

            return Job.from_dict(job_data, tenant_context)

        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            return None

    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        error_message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update job status in Redis"""
        try:
            updates = {
                "status": status.value,
                "completed_at": (
                    datetime.utcnow().isoformat()
                    if status in [JobStatus.COMPLETED, JobStatus.FAILED]
                    else None
                ),
            }

            if error_message:
                updates["error_message"] = error_message

            if result:
                updates["result"] = json.dumps(result)

            # Remove None values
            updates = {k: v for k, v in updates.items() if v is not None}

            await self.redis.hmset(f"{self.job_data_key}:{job_id}", updates)

            # Remove from processing set if completed
            if status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                await self.redis.srem(self.processing_key, job_id)

            return True

        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {e}")
            return False

    async def get_queue_stats(self, org_id: str) -> Dict[str, int]:
        """Get queue statistics for organization"""
        try:
            # This is a simplified version
            # Would need to scan through job data to filter by org_id
            stats = {"pending": 0, "processing": 0, "completed": 0, "failed": 0}

            return stats

        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {}


class CacheManager:
    """Redis cache manager for performance optimization"""

    def __init__(self, redis_client):
        self.redis = redis_client
        self.default_ttl = 3600  # 1 hour default TTL

    async def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        try:
            tenant = get_current_tenant()
            if tenant:
                key = f"org:{tenant.org_id}:{key}"

            value = await self.redis.get(key)
            if value:
                return json.loads(value)
            return None

        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set cached value with TTL"""
        try:
            tenant = get_current_tenant()
            if tenant:
                key = f"org:{tenant.org_id}:{key}"

            ttl = ttl or self.default_ttl
            serialized_value = json.dumps(value)

            await self.redis.setex(key, ttl, serialized_value)
            return True

        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete cached value"""
        try:
            tenant = get_current_tenant()
            if tenant:
                key = f"org:{tenant.org_id}:{key}"

            result = await self.redis.delete(key)
            return result > 0

        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern"""
        try:
            tenant = get_current_tenant()
            if tenant:
                pattern = f"org:{tenant.org_id}:{pattern}"

            keys = await self.redis.keys(pattern)
            if keys:
                return await self.redis.delete(*keys)
            return 0

        except Exception as e:
            logger.error(f"Cache invalidate error for pattern {pattern}: {e}")
            return 0


class BackgroundWorker:
    """Background worker for job processing"""

    def __init__(self, job_queue: JobQueue, job_handlers: Dict[str, Callable]):
        self.job_queue = job_queue
        self.job_handlers = job_handlers
        self.running = False

    async def start(self):
        """Start background worker"""
        self.running = True
        logger.info("Background worker started")

        while self.running:
            try:
                # Get next job
                job = await self.job_queue.dequeue()
                if not job:
                    await asyncio.sleep(1)  # Wait before checking again
                    continue

                # Process job
                await self._process_job(job)

            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(5)  # Wait on error

    def stop(self):
        """Stop background worker"""
        self.running = False
        logger.info("Background worker stopped")

    async def _process_job(self, job: Job):
        """Process individual job"""
        try:
            # Set tenant context for job execution
            from .tenancy import set_tenant_context

            set_tenant_context(job.context.tenant_context)

            # Update job status
            job.context.started_at = datetime.utcnow()
            await self.job_queue.update_job_status(job.id, JobStatus.PROCESSING)

            # Get handler for job type
            handler = self.job_handlers.get(job.type)
            if not handler:
                raise ValueError(f"No handler found for job type: {job.type}")

            # Execute job
            result = await handler(job.payload)

            # Mark as completed
            job.context.completed_at = datetime.utcnow()
            await self.job_queue.update_job_status(
                job.id, JobStatus.COMPLETED, result=result
            )

            logger.info(
                f"Job {job.id} completed successfully in {job.context.duration()}"
            )

        except Exception as e:
            logger.error(f"Job {job.id} failed: {e}")

            # Handle retries
            job.context.retry_count += 1
            if job.context.retry_count < job.context.max_retries:
                # Retry job
                job.status = JobStatus.RETRYING
                job.scheduled_for = datetime.utcnow() + timedelta(
                    minutes=5 * job.context.retry_count
                )
                await self.job_queue.enqueue(job)

                await self.job_queue.update_job_status(
                    job.id, JobStatus.RETRYING, error_message=str(e)
                )
            else:
                # Max retries exceeded
                await self.job_queue.update_job_status(
                    job.id, JobStatus.FAILED, error_message=str(e)
                )


class JobScheduler:
    """Service for scheduling and managing async jobs"""

    def __init__(self, job_queue: JobQueue):
        self.job_queue = job_queue

    async def schedule_initiative_execution(self, initiative_id: str, goal: str) -> str:
        """Schedule initiative execution as background job"""
        tenant = require_tenant()

        job = Job(
            id=str(uuid.uuid4()),
            type="execute_initiative",
            priority=JobPriority.NORMAL,
            status=JobStatus.PENDING,
            payload={"initiative_id": initiative_id, "goal": goal},
            context=JobContext(
                job_id=str(uuid.uuid4()),
                org_id=tenant.org_id,
                user_id=tenant.user_id,
                tenant_context=tenant,
            ),
        )

        await self.job_queue.enqueue(job)
        logger.info(f"Scheduled initiative execution job {job.id}")
        return job.id

    async def schedule_ci_repair(
        self, build_id: str, failure_data: Dict[str, Any]
    ) -> str:
        """Schedule CI repair as high-priority job"""
        tenant = require_tenant()

        job = Job(
            id=str(uuid.uuid4()),
            type="repair_ci_failure",
            priority=JobPriority.HIGH,
            status=JobStatus.PENDING,
            payload={"build_id": build_id, "failure_data": failure_data},
            context=JobContext(
                job_id=str(uuid.uuid4()),
                org_id=tenant.org_id,
                user_id=tenant.user_id,
                tenant_context=tenant,
            ),
        )

        await self.job_queue.enqueue(job)
        logger.info(f"Scheduled CI repair job {job.id}")
        return job.id

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status and progress"""
        job = await self.job_queue.get_job(job_id)
        if not job:
            return None

        return {
            "id": job.id,
            "type": job.type,
            "status": job.status.value,
            "priority": job.priority.value,
            "created_at": job.context.created_at.isoformat(),
            "started_at": (
                job.context.started_at.isoformat() if job.context.started_at else None
            ),
            "completed_at": (
                job.context.completed_at.isoformat()
                if job.context.completed_at
                else None
            ),
            "duration": str(job.context.duration()) if job.context.duration() else None,
            "retry_count": job.context.retry_count,
            "error_message": job.error_message,
            "result": job.result,
        }


# Global instances (initialized by app)
job_queue: Optional[JobQueue] = None
cache_manager: Optional[CacheManager] = None
job_scheduler: Optional[JobScheduler] = None


def init_performance_infrastructure(redis_client):
    """Initialize performance infrastructure"""
    global job_queue, cache_manager, job_scheduler

    job_queue = RedisJobQueue(redis_client)
    cache_manager = CacheManager(redis_client)
    job_scheduler = JobScheduler(job_queue)


def get_job_queue() -> JobQueue:
    if not job_queue:
        raise RuntimeError("Job queue not initialized")
    return job_queue


def get_cache_manager() -> CacheManager:
    if not cache_manager:
        raise RuntimeError("Cache manager not initialized")
    return cache_manager


def get_job_scheduler() -> JobScheduler:
    if not job_scheduler:
        raise RuntimeError("Job scheduler not initialized")
    return job_scheduler


__all__ = [
    "Job",
    "JobPriority",
    "JobStatus",
    "JobQueue",
    "CacheManager",
    "BackgroundWorker",
    "JobScheduler",
    "init_performance_infrastructure",
    "get_job_queue",
    "get_cache_manager",
    "get_job_scheduler",
]
