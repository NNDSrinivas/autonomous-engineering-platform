"""
Enterprise Reliability & Disaster Recovery for NAVI

Comprehensive reliability system providing:
- Stateless execution architecture with durable state management  
- Automatic retry mechanisms with exponential backoff
- Initiative resumption capabilities after failures
- Distributed system coordination and consensus
- Data backup and restoration procedures
- System health monitoring and self-healing
- Graceful degradation under load
- Circuit breaker patterns for external dependencies
"""

from typing import Dict, List, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json
import logging
import hashlib
import traceback
from functools import wraps
import uuid
import time

from .tenancy import require_tenant
from .tenant_database import TenantRepository, get_tenant_db

logger = logging.getLogger(__name__)

class ExecutionState(Enum):
    """States for stateless execution tracking"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"

class BackupType(Enum):
    """Types of backup operations"""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    CONFIG = "config"

class HealthStatus(Enum):
    """System health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"

@dataclass
class ExecutionCheckpoint:
    """Durable checkpoint for stateless execution"""
    id: str
    org_id: str
    execution_id: str
    step_name: str
    step_index: int
    total_steps: int
    state: ExecutionState
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "id": self.id,
            "org_id": self.org_id,
            "execution_id": self.execution_id,
            "step_name": self.step_name,
            "step_index": self.step_index,
            "total_steps": self.total_steps,
            "state": self.state.value,
            "data": json.dumps(self.data),
            "metadata": json.dumps(self.metadata),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionCheckpoint':
        """Create from dictionary"""
        return cls(
            id=data["id"],
            org_id=data["org_id"],
            execution_id=data["execution_id"],
            step_name=data["step_name"],
            step_index=data["step_index"],
            total_steps=data["total_steps"],
            state=ExecutionState(data["state"]),
            data=json.loads(data["data"]),
            metadata=json.loads(data["metadata"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data["expires_at"] else None
        )

@dataclass
class RetryConfig:
    """Configuration for automatic retry behavior"""
    max_attempts: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on_exceptions: List[type] = field(default_factory=lambda: [Exception])
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number"""
        delay = self.initial_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            # Add ±25% jitter to avoid thundering herd
            import random
            jitter_amount = delay * 0.25
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0, delay)

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker pattern"""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0  # seconds
    expected_exception: type = Exception

@dataclass
class CircuitBreakerState:
    """Current state of a circuit breaker"""
    is_open: bool = False
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    next_attempt_time: Optional[datetime] = None

@dataclass
class BackupMetadata:
    """Metadata for backup operations"""
    id: str
    org_id: str
    backup_type: BackupType
    created_at: datetime
    size_bytes: int
    checksum: str
    retention_days: int
    encrypted: bool
    location: str
    tags: Dict[str, str] = field(default_factory=dict)

@dataclass
class HealthCheck:
    """Individual health check result"""
    name: str
    status: HealthStatus
    message: str
    response_time_ms: float
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

class StatelessExecutionEngine:
    """Engine for stateless execution with durable checkpoints"""
    
    def __init__(self):
        self.checkpoint_repo = CheckpointRepository()
        self.default_ttl_hours = 24
    
    async def execute_with_checkpoints(self,
                                     execution_id: str,
                                     steps: List[Callable],
                                     initial_data: Optional[Dict[str, Any]] = None,
                                     step_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """Execute a multi-step process with automatic checkpointing"""
        tenant = require_tenant()
        initial_data = initial_data or {}
        step_names = step_names or [f"step_{i}" for i in range(len(steps))]
        
        # Check for existing checkpoints (resumption)
        existing_checkpoint = await self.checkpoint_repo.get_latest_checkpoint(execution_id)
        
        if existing_checkpoint and existing_checkpoint.state != ExecutionState.COMPLETED:
            logger.info(f"Resuming execution {execution_id} from step {existing_checkpoint.step_index}")
            start_index = existing_checkpoint.step_index
            current_data = existing_checkpoint.data
        else:
            start_index = 0
            current_data = initial_data
        
        # Execute steps from checkpoint
        for i, step in enumerate(steps[start_index:], start_index):
            step_name = step_names[i]
            checkpoint_id = f"{execution_id}_step_{i}"
            
            # Create checkpoint before execution
            checkpoint = ExecutionCheckpoint(
                id=checkpoint_id,
                org_id=tenant.org_id,
                execution_id=execution_id,
                step_name=step_name,
                step_index=i,
                total_steps=len(steps),
                state=ExecutionState.RUNNING,
                data=current_data,
                metadata={"started_at": datetime.utcnow().isoformat()},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=self.default_ttl_hours)
            )
            
            await self.checkpoint_repo.save_checkpoint(checkpoint)
            
            try:
                # Execute step
                logger.info(f"Executing step {i}: {step_name}")
                
                if asyncio.iscoroutinefunction(step):
                    result = await step(current_data)
                else:
                    result = step(current_data)
                
                # Update data with step result
                if isinstance(result, dict):
                    current_data.update(result)
                else:
                    current_data[f"step_{i}_result"] = result
                
                # Update checkpoint with success
                checkpoint.state = ExecutionState.COMPLETED
                checkpoint.data = current_data
                checkpoint.metadata["completed_at"] = datetime.utcnow().isoformat()
                checkpoint.updated_at = datetime.utcnow()
                
                await self.checkpoint_repo.save_checkpoint(checkpoint)
                
            except Exception as e:
                logger.error(f"Step {i} failed: {str(e)}")
                
                # Update checkpoint with failure
                checkpoint.state = ExecutionState.FAILED
                checkpoint.metadata["error"] = str(e)
                checkpoint.metadata["traceback"] = traceback.format_exc()
                checkpoint.metadata["failed_at"] = datetime.utcnow().isoformat()
                checkpoint.updated_at = datetime.utcnow()
                
                await self.checkpoint_repo.save_checkpoint(checkpoint)
                
                # Re-raise for retry handling at higher level
                raise
        
        return current_data
    
    async def resume_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Resume failed execution from last checkpoint"""
        checkpoint = await self.checkpoint_repo.get_latest_checkpoint(execution_id)
        
        if not checkpoint:
            logger.warning(f"No checkpoint found for execution {execution_id}")
            return None
        
        if checkpoint.state == ExecutionState.COMPLETED:
            logger.info(f"Execution {execution_id} already completed")
            return checkpoint.data
        
        logger.info(f"Resuming execution {execution_id} from step {checkpoint.step_index}")
        
        # This would typically trigger re-execution with the stored steps
        # For now, return the checkpoint data for manual handling
        return checkpoint.data

class RetryDecorator:
    """Decorator for automatic retries with exponential backoff"""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
    
    def __call__(self, func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(self.config.max_attempts):
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
                        
                except Exception as e:
                    last_exception = e
                    
                    # Check if this exception should trigger retry
                    should_retry = any(isinstance(e, exc_type) for exc_type in self.config.retry_on_exceptions)
                    
                    if not should_retry or attempt == self.config.max_attempts - 1:
                        logger.error(f"Function {func.__name__} failed after {attempt + 1} attempts: {str(e)}")
                        raise
                    
                    # Calculate delay and wait
                    delay = self.config.calculate_delay(attempt)
                    logger.warning(f"Function {func.__name__} failed on attempt {attempt + 1}, retrying in {delay:.2f}s: {str(e)}")
                    
                    await asyncio.sleep(delay)
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
        
        return async_wrapper

class CircuitBreaker:
    """Circuit breaker for external service calls"""
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitBreakerState()
    
    def __call__(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Check if circuit is open
            if self._is_circuit_open():
                raise Exception(f"Circuit breaker '{self.name}' is open")
            
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Reset failure count on success
                self._record_success()
                return result
                
            except Exception as e:
                # Record failure and potentially open circuit
                self._record_failure()
                
                if isinstance(e, self.config.expected_exception):
                    raise
                else:
                    # Unexpected exception, re-raise immediately
                    raise
        
        return wrapper
    
    def _is_circuit_open(self) -> bool:
        """Check if circuit breaker is currently open"""
        if not self.state.is_open:
            return False
        
        # Check if recovery timeout has passed
        if (self.state.next_attempt_time and 
            datetime.utcnow() >= self.state.next_attempt_time):
            # Half-open state - allow one attempt
            self.state.is_open = False
            return False
        
        return True
    
    def _record_success(self):
        """Record successful call"""
        self.state.failure_count = 0
        self.state.is_open = False
        self.state.last_failure_time = None
        self.state.next_attempt_time = None
    
    def _record_failure(self):
        """Record failed call"""
        self.state.failure_count += 1
        self.state.last_failure_time = datetime.utcnow()
        
        if self.state.failure_count >= self.config.failure_threshold:
            self.state.is_open = True
            self.state.next_attempt_time = datetime.utcnow() + timedelta(
                seconds=self.config.recovery_timeout
            )
            logger.warning(f"Circuit breaker '{self.name}' opened after {self.state.failure_count} failures")

class BackupManager:
    """Enterprise backup and recovery management"""
    
    def __init__(self):
        self.backup_repo = BackupRepository()
        self.default_retention_days = 90
    
    async def create_backup(self,
                           backup_type: BackupType,
                           data_sources: List[str],
                           encrypt: bool = True,
                           retention_days: Optional[int] = None) -> BackupMetadata:
        """Create backup with specified configuration"""
        tenant = require_tenant()
        retention_days = retention_days or self.default_retention_days
        
        backup_id = f"backup_{tenant.org_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Perform backup operation (placeholder - would implement actual backup)
        backup_data = await self._perform_backup(data_sources, backup_type)
        
        # Calculate checksum
        checksum = hashlib.sha256(json.dumps(backup_data, sort_keys=True).encode()).hexdigest()
        
        # Store backup (placeholder - would store to external backup storage)
        location = await self._store_backup(backup_id, backup_data, encrypt)
        
        # Create metadata
        metadata = BackupMetadata(
            id=backup_id,
            org_id=tenant.org_id,
            backup_type=backup_type,
            created_at=datetime.utcnow(),
            size_bytes=len(json.dumps(backup_data).encode()),
            checksum=checksum,
            retention_days=retention_days,
            encrypted=encrypt,
            location=location,
            tags={"source": "navi_system", "version": "1.0"}
        )
        
        await self.backup_repo.save_backup_metadata(metadata)
        
        logger.info(f"Created {backup_type.value} backup {backup_id} ({metadata.size_bytes} bytes)")
        
        return metadata
    
    async def restore_from_backup(self,
                                backup_id: str,
                                target_location: Optional[str] = None,
                                verify_checksum: bool = True) -> bool:
        """Restore data from backup"""
        metadata = await self.backup_repo.get_backup_metadata(backup_id)
        if not metadata:
            logger.error(f"Backup {backup_id} not found")
            return False
        
        # Load backup data
        backup_data = await self._load_backup(metadata.location, metadata.encrypted)
        
        # Verify checksum if requested
        if verify_checksum:
            current_checksum = hashlib.sha256(
                json.dumps(backup_data, sort_keys=True).encode()
            ).hexdigest()
            
            if current_checksum != metadata.checksum:
                logger.error(f"Backup {backup_id} checksum verification failed")
                return False
        
        # Perform restore operation
        target = target_location or metadata.location
        success = await self._perform_restore(backup_data, target)
        
        if success:
            logger.info(f"Successfully restored from backup {backup_id}")
        else:
            logger.error(f"Failed to restore from backup {backup_id}")
        
        return success
    
    async def cleanup_expired_backups(self) -> int:
        """Remove expired backups based on retention policy"""
        tenant = require_tenant()
        expired_backups = await self.backup_repo.get_expired_backups(tenant.org_id)
        
        cleaned_count = 0
        for backup in expired_backups:
            try:
                await self._delete_backup(backup.location)
                await self.backup_repo.delete_backup_metadata(backup.id)
                cleaned_count += 1
                logger.info(f"Cleaned up expired backup {backup.id}")
            except Exception as e:
                logger.error(f"Failed to cleanup backup {backup.id}: {str(e)}")
        
        return cleaned_count
    
    async def _perform_backup(self, data_sources: List[str], backup_type: BackupType) -> Dict[str, Any]:
        """Perform actual backup operation (placeholder)"""
        # This would implement actual backup logic for different data sources
        return {
            "data_sources": data_sources,
            "backup_type": backup_type.value,
            "timestamp": datetime.utcnow().isoformat(),
            "data": "compressed_backup_data_placeholder"
        }
    
    async def _store_backup(self, backup_id: str, data: Dict[str, Any], encrypt: bool) -> str:
        """Store backup to external storage (placeholder)"""
        # This would implement storage to S3, Azure Blob, etc.
        location = f"s3://navi-backups/{backup_id}.backup"
        return location
    
    async def _load_backup(self, location: str, encrypted: bool) -> Dict[str, Any]:
        """Load backup from external storage (placeholder)"""
        # This would implement loading from S3, Azure Blob, etc.
        return {"restored_data": "placeholder"}
    
    async def _perform_restore(self, backup_data: Dict[str, Any], target_location: str) -> bool:
        """Perform actual restore operation (placeholder)"""
        # This would implement actual restore logic
        return True
    
    async def _delete_backup(self, location: str):
        """Delete backup from external storage (placeholder)"""
        pass

class HealthMonitor:
    """System health monitoring and self-healing"""
    
    def __init__(self):
        self.health_checks: Dict[str, Callable] = {}
        self.self_healing_actions: Dict[str, Callable] = {}
        self.check_interval = 60  # seconds
        self.monitoring_task: Optional[asyncio.Task] = None
    
    def register_health_check(self, name: str, check_func: Callable[[], Awaitable[HealthCheck]]):
        """Register a health check function"""
        self.health_checks[name] = check_func
    
    def register_self_healing_action(self, condition: str, action_func: Callable[[], Awaitable[bool]]):
        """Register a self-healing action for specific conditions"""
        self.self_healing_actions[condition] = action_func
    
    async def start_monitoring(self):
        """Start continuous health monitoring"""
        if self.monitoring_task and not self.monitoring_task.done():
            logger.warning("Health monitoring already running")
            return
        
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Started health monitoring")
    
    async def stop_monitoring(self):
        """Stop health monitoring"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped health monitoring")
    
    async def perform_health_check(self) -> Dict[str, HealthCheck]:
        """Perform all registered health checks"""
        results = {}
        
        for name, check_func in self.health_checks.items():
            try:
                start_time = time.time()
                result = await check_func()
                result.response_time_ms = (time.time() - start_time) * 1000
                results[name] = result
                
            except Exception as e:
                results[name] = HealthCheck(
                    name=name,
                    status=HealthStatus.CRITICAL,
                    message=f"Health check failed: {str(e)}",
                    response_time_ms=0,
                    timestamp=datetime.utcnow()
                )
        
        return results
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while True:
            try:
                health_results = await self.perform_health_check()
                
                # Check for unhealthy conditions and trigger self-healing
                for name, result in health_results.items():
                    if result.status in [HealthStatus.UNHEALTHY, HealthStatus.CRITICAL]:
                        await self._trigger_self_healing(name, result)
                
                # Log overall system health
                overall_status = self._calculate_overall_health(health_results)
                logger.info(f"System health: {overall_status.value}")
                
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitoring error: {str(e)}")
                await asyncio.sleep(self.check_interval)
    
    async def _trigger_self_healing(self, check_name: str, health_result: HealthCheck):
        """Trigger self-healing actions for unhealthy conditions"""
        logger.warning(f"Triggering self-healing for {check_name}: {health_result.message}")
        
        # Look for matching self-healing actions
        for condition, action in self.self_healing_actions.items():
            if condition in check_name.lower() or condition in health_result.message.lower():
                try:
                    success = await action()
                    if success:
                        logger.info(f"Self-healing action '{condition}' succeeded for {check_name}")
                    else:
                        logger.warning(f"Self-healing action '{condition}' failed for {check_name}")
                except Exception as e:
                    logger.error(f"Self-healing action '{condition}' error: {str(e)}")
    
    def _calculate_overall_health(self, health_results: Dict[str, HealthCheck]) -> HealthStatus:
        """Calculate overall system health from individual checks"""
        if not health_results:
            return HealthStatus.UNHEALTHY
        
        statuses = [result.status for result in health_results.values()]
        
        if any(status == HealthStatus.CRITICAL for status in statuses):
            return HealthStatus.CRITICAL
        elif any(status == HealthStatus.UNHEALTHY for status in statuses):
            return HealthStatus.UNHEALTHY
        elif any(status == HealthStatus.DEGRADED for status in statuses):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

# Repository classes
class CheckpointRepository(TenantRepository):
    """Repository for execution checkpoints"""
    
    def __init__(self):
        super().__init__(get_tenant_db(), "execution_checkpoints")
    
    async def save_checkpoint(self, checkpoint: ExecutionCheckpoint) -> bool:
        """Save execution checkpoint"""
        try:
            await self.create_or_update(checkpoint.to_dict(), checkpoint.id)
            return True
        except Exception as e:
            logger.error(f"Failed to save checkpoint {checkpoint.id}: {e}")
            return False
    
    async def get_latest_checkpoint(self, execution_id: str) -> Optional[ExecutionCheckpoint]:
        """Get latest checkpoint for execution"""
        try:
            # This would query for latest checkpoint by execution_id
            # Placeholder implementation
            results = await self.find_all({"execution_id": execution_id})
            if results:
                # Get most recent by updated_at
                latest = max(results, key=lambda x: x["updated_at"])
                return ExecutionCheckpoint.from_dict(latest)
            return None
        except Exception as e:
            logger.error(f"Failed to get checkpoint for {execution_id}: {e}")
            return None

class BackupRepository(TenantRepository):
    """Repository for backup metadata"""
    
    def __init__(self):
        super().__init__(get_tenant_db(), "backup_metadata")
    
    async def save_backup_metadata(self, metadata: BackupMetadata) -> bool:
        """Save backup metadata"""
        try:
            data = asdict(metadata)
            data["backup_type"] = metadata.backup_type.value
            data["created_at"] = metadata.created_at.isoformat()
            data["tags"] = json.dumps(metadata.tags)
            
            await self.create(data)
            return True
        except Exception as e:
            logger.error(f"Failed to save backup metadata {metadata.id}: {e}")
            return False
    
    async def get_backup_metadata(self, backup_id: str) -> Optional[BackupMetadata]:
        """Get backup metadata by ID"""
        try:
            result = await self.find_by_id(backup_id)
            if result:
                # Convert back to BackupMetadata object
                result["backup_type"] = BackupType(result["backup_type"])
                result["created_at"] = datetime.fromisoformat(result["created_at"])
                result["tags"] = json.loads(result.get("tags", "{}"))
                
                return BackupMetadata(**result)
            return None
        except Exception as e:
            logger.error(f"Failed to get backup metadata {backup_id}: {e}")
            return None
    
    async def get_expired_backups(self, org_id: str) -> List[BackupMetadata]:
        """Get backups that have exceeded retention period"""
        # Placeholder implementation
        return []
    
    async def delete_backup_metadata(self, backup_id: str) -> bool:
        """Delete backup metadata"""
        try:
            return await self.delete_by_id(backup_id)
        except Exception as e:
            logger.error(f"Failed to delete backup metadata {backup_id}: {e}")
            return False

# Global services
stateless_engine = StatelessExecutionEngine()
backup_manager = BackupManager()
health_monitor = HealthMonitor()

# Common retry configurations
STANDARD_RETRY = RetryConfig(max_attempts=3, initial_delay=1.0)
AGGRESSIVE_RETRY = RetryConfig(max_attempts=5, initial_delay=0.5, max_delay=30.0)
CONSERVATIVE_RETRY = RetryConfig(max_attempts=2, initial_delay=2.0, max_delay=10.0)

# Common circuit breaker configurations
EXTERNAL_API_CIRCUIT = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30.0)
DATABASE_CIRCUIT = CircuitBreakerConfig(failure_threshold=5, recovery_timeout=60.0)

# Decorators for easy use
retry = RetryDecorator
standard_retry = RetryDecorator(STANDARD_RETRY)
aggressive_retry = RetryDecorator(AGGRESSIVE_RETRY)

__all__ = [
    'ExecutionState',
    'BackupType', 
    'HealthStatus',
    'ExecutionCheckpoint',
    'RetryConfig',
    'CircuitBreakerConfig',
    'BackupMetadata',
    'HealthCheck',
    'StatelessExecutionEngine',
    'RetryDecorator',
    'CircuitBreaker',
    'BackupManager', 
    'HealthMonitor',
    'stateless_engine',
    'backup_manager',
    'health_monitor',
    'retry',
    'standard_retry',
    'aggressive_retry'
]
