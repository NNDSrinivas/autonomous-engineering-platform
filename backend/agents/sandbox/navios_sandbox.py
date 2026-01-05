"""
NaviOS Execution Sandbox - Safe Autonomous Code Execution
Implements snapshot → apply patch → rollback system for safer execution than Cursor.
"""

import os
import json
import logging
import subprocess
import tempfile
import shutil
import hashlib
import psutil
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import asyncio
import threading
import time

try:
    from ...memory.episodic_memory import EpisodicMemory
except ImportError:
    from backend.memory.episodic_memory import EpisodicMemory


class SandboxState(Enum):
    """States of the sandbox execution environment."""

    INITIALIZING = "initializing"
    READY = "ready"
    EXECUTING = "executing"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class ResourceLimitType(Enum):
    """Types of resource limits that can be enforced."""

    CPU_PERCENT = "cpu_percent"
    MEMORY_MB = "memory_mb"
    DISK_MB = "disk_mb"
    EXECUTION_TIME_SEC = "execution_time_sec"
    NETWORK_REQUESTS = "network_requests"
    FILE_OPERATIONS = "file_operations"


@dataclass
class ResourceLimits:
    """Resource limits for sandbox execution."""

    cpu_percent: float = 50.0  # Max CPU usage percentage
    memory_mb: int = 512  # Max memory usage in MB
    disk_mb: int = 100  # Max disk usage in MB
    execution_time_sec: int = 300  # Max execution time in seconds
    network_requests: int = 100  # Max network requests
    file_operations: int = 1000  # Max file operations
    subprocess_count: int = 5  # Max subprocess count


@dataclass
class SnapshotMetadata:
    """Metadata for filesystem snapshots."""

    snapshot_id: str
    created_at: datetime
    workspace_root: str
    file_count: int
    total_size_bytes: int
    checksum: str
    description: str


@dataclass
class ExecutionResult:
    """Result of sandbox execution."""

    success: bool
    output: Any
    logs: List[str]
    errors: List[str]
    execution_time_seconds: float
    resources_used: Dict[str, Any]
    snapshot_id: Optional[str]
    rollback_available: bool
    metadata: Dict[str, Any]


class ResourceMonitor:
    """
    Monitors resource usage during execution and enforces limits.
    """

    def __init__(self, limits: ResourceLimits, process_id: Optional[int] = None):
        self.limits = limits
        self.process_id = process_id or os.getpid()
        self.monitoring = False
        self.peak_usage = {
            "cpu_percent": 0.0,
            "memory_mb": 0.0,
            "disk_mb": 0.0,
            "network_requests": 0,
            "file_operations": 0,
            "subprocess_count": 0,
        }
        self.violations = []
        self.logger = logging.getLogger(__name__)

    def start_monitoring(self):
        """Start resource monitoring in background thread."""
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self):
        """Stop resource monitoring."""
        self.monitoring = False
        if hasattr(self, "monitor_thread"):
            self.monitor_thread.join(timeout=1.0)

    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.monitoring:
            try:
                self._check_resources()
                time.sleep(0.1)  # Monitor every 100ms
            except Exception as e:
                self.logger.warning(f"Resource monitoring error: {e}")

    def _check_resources(self):
        """Check resource usage against limits."""
        try:
            process = psutil.Process(self.process_id)

            # Check CPU usage
            cpu_percent = process.cpu_percent()
            self.peak_usage["cpu_percent"] = max(
                self.peak_usage["cpu_percent"], cpu_percent
            )

            if cpu_percent > self.limits.cpu_percent:
                self.violations.append(
                    f"CPU usage {cpu_percent:.1f}% exceeds limit {self.limits.cpu_percent}%"
                )

            # Check memory usage
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            self.peak_usage["memory_mb"] = max(self.peak_usage["memory_mb"], memory_mb)

            if memory_mb > self.limits.memory_mb:
                self.violations.append(
                    f"Memory usage {memory_mb:.1f}MB exceeds limit {self.limits.memory_mb}MB"
                )

            # Check subprocess count
            children = process.children(recursive=True)
            subprocess_count = len(children)
            self.peak_usage["subprocess_count"] = max(
                self.peak_usage["subprocess_count"], subprocess_count
            )

            if subprocess_count > self.limits.subprocess_count:
                self.violations.append(
                    f"Subprocess count {subprocess_count} exceeds limit {self.limits.subprocess_count}"
                )

        except psutil.NoSuchProcess:
            self.monitoring = False
        except Exception as e:
            self.logger.debug(f"Resource check error: {e}")


class FilesystemSnapshot:
    """
    Creates and manages filesystem snapshots for rollback capability.
    """

    def __init__(self, workspace_root: str, snapshots_dir: Optional[str] = None):
        self.workspace_root = Path(workspace_root)
        self.snapshots_dir = Path(
            snapshots_dir or (self.workspace_root / ".navi_snapshots")
        )
        self.snapshots_dir.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)

        # Snapshot metadata
        self.metadata_file = self.snapshots_dir / "snapshots.json"
        self.snapshots_metadata = self._load_snapshots_metadata()

    def create_snapshot(
        self, description: str = "Auto-generated snapshot"
    ) -> SnapshotMetadata:
        """
        Create a new filesystem snapshot.

        Args:
            description: Description of the snapshot

        Returns:
            Snapshot metadata
        """
        timestamp = datetime.utcnow()
        snapshot_id = f"snapshot_{timestamp.strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(description.encode()).hexdigest()[:8]}"

        snapshot_dir = self.snapshots_dir / snapshot_id
        snapshot_dir.mkdir()

        try:
            # Copy workspace files to snapshot directory
            file_count = 0
            total_size = 0

            # Use rsync for efficient copying if available, otherwise shutil
            if shutil.which("rsync"):
                result = subprocess.run(
                    [
                        "rsync",
                        "-av",
                        "--exclude=.git",
                        "--exclude=node_modules",
                        "--exclude=__pycache__",
                        "--exclude=.navi_snapshots",
                        "--exclude=.navi_sandbox",
                        str(self.workspace_root) + "/",
                        str(snapshot_dir) + "/",
                    ],
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    raise Exception(f"rsync failed: {result.stderr}")
            else:
                # Fallback to Python copying
                self._copy_workspace_filtered(self.workspace_root, snapshot_dir)

            # Calculate statistics
            for file_path in snapshot_dir.rglob("*"):
                if file_path.is_file():
                    file_count += 1
                    total_size += file_path.stat().st_size

            # Create checksum of snapshot
            checksum = self._calculate_directory_checksum(snapshot_dir)

            # Create metadata
            metadata = SnapshotMetadata(
                snapshot_id=snapshot_id,
                created_at=timestamp,
                workspace_root=str(self.workspace_root),
                file_count=file_count,
                total_size_bytes=total_size,
                checksum=checksum,
                description=description,
            )

            # Save snapshot metadata
            metadata_file = snapshot_dir / "metadata.json"
            metadata_file.write_text(
                json.dumps(
                    {
                        "snapshot_id": metadata.snapshot_id,
                        "created_at": metadata.created_at.isoformat(),
                        "workspace_root": metadata.workspace_root,
                        "file_count": metadata.file_count,
                        "total_size_bytes": metadata.total_size_bytes,
                        "checksum": metadata.checksum,
                        "description": metadata.description,
                    },
                    indent=2,
                )
            )

            # Update snapshots registry
            self.snapshots_metadata[snapshot_id] = metadata
            self._save_snapshots_metadata()

            self.logger.info(
                f"Created snapshot {snapshot_id} with {file_count} files ({total_size / 1024 / 1024:.1f}MB)"
            )
            return metadata

        except Exception as e:
            # Cleanup failed snapshot
            if snapshot_dir.exists():
                shutil.rmtree(snapshot_dir, ignore_errors=True)
            raise Exception(f"Snapshot creation failed: {e}")

    def restore_snapshot(self, snapshot_id: str) -> bool:
        """
        Restore workspace from a snapshot.

        Args:
            snapshot_id: Snapshot identifier

        Returns:
            True if restoration was successful
        """
        if snapshot_id not in self.snapshots_metadata:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        snapshot_dir = self.snapshots_dir / snapshot_id
        if not snapshot_dir.exists():
            raise ValueError(f"Snapshot directory not found: {snapshot_dir}")

        try:
            # Backup current state before restoration
            backup_snapshot = self.create_snapshot("Pre-restore backup")

            # Clear workspace (except snapshots directory)
            for item in self.workspace_root.iterdir():
                if item.name == ".navi_snapshots":
                    continue  # Don't delete snapshots

                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

            # Restore files from snapshot
            if shutil.which("rsync"):
                result = subprocess.run(
                    [
                        "rsync",
                        "-av",
                        str(snapshot_dir) + "/",
                        str(self.workspace_root) + "/",
                    ],
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    # Try to restore from backup
                    self.restore_snapshot(backup_snapshot.snapshot_id)
                    raise Exception(f"Restore failed: {result.stderr}")
            else:
                # Fallback to Python copying
                for item in snapshot_dir.iterdir():
                    if item.name == "metadata.json":
                        continue

                    dest = self.workspace_root / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)

            self.logger.info(f"Successfully restored snapshot {snapshot_id}")
            return True

        except Exception as e:
            self.logger.error(f"Snapshot restoration failed: {e}")
            return False

    def list_snapshots(self) -> List[SnapshotMetadata]:
        """
        List all available snapshots.

        Returns:
            List of snapshot metadata
        """
        return list(self.snapshots_metadata.values())

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """
        Delete a snapshot.

        Args:
            snapshot_id: Snapshot identifier

        Returns:
            True if deletion was successful
        """
        try:
            if snapshot_id in self.snapshots_metadata:
                del self.snapshots_metadata[snapshot_id]
                self._save_snapshots_metadata()

            snapshot_dir = self.snapshots_dir / snapshot_id
            if snapshot_dir.exists():
                shutil.rmtree(snapshot_dir)

            self.logger.info(f"Deleted snapshot {snapshot_id}")
            return True

        except Exception as e:
            self.logger.error(f"Snapshot deletion failed: {e}")
            return False

    def cleanup_old_snapshots(self, keep_count: int = 10, max_age_days: int = 7):
        """
        Clean up old snapshots based on count and age limits.

        Args:
            keep_count: Maximum number of snapshots to keep
            max_age_days: Maximum age of snapshots in days
        """
        try:
            snapshots = sorted(
                self.snapshots_metadata.values(),
                key=lambda x: x.created_at,
                reverse=True,
            )

            cutoff_time = datetime.utcnow() - timedelta(days=max_age_days)

            # Keep recent snapshots and delete old ones
            for i, snapshot in enumerate(snapshots):
                should_delete = (
                    i >= keep_count  # Beyond count limit
                    or snapshot.created_at < cutoff_time  # Beyond age limit
                )

                if should_delete:
                    self.delete_snapshot(snapshot.snapshot_id)

        except Exception as e:
            self.logger.warning(f"Snapshot cleanup failed: {e}")

    def _copy_workspace_filtered(self, src: Path, dst: Path):
        """Copy workspace files with filtering."""
        excluded_dirs = {
            ".git",
            "node_modules",
            "__pycache__",
            ".navi_snapshots",
            ".navi_sandbox",
        }

        for item in src.iterdir():
            if item.name in excluded_dirs:
                continue

            dest_item = dst / item.name

            if item.is_dir():
                dest_item.mkdir()
                self._copy_workspace_filtered(item, dest_item)
            else:
                shutil.copy2(item, dest_item)

    def _calculate_directory_checksum(self, directory: Path) -> str:
        """Calculate MD5 checksum of directory contents."""
        hash_md5 = hashlib.md5()

        for file_path in sorted(directory.rglob("*")):
            if file_path.is_file() and file_path.name != "metadata.json":
                try:
                    with open(file_path, "rb") as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            hash_md5.update(chunk)
                except Exception:
                    pass  # Skip files that can't be read

        return hash_md5.hexdigest()

    def _load_snapshots_metadata(self) -> Dict[str, SnapshotMetadata]:
        """Load snapshots metadata from file."""
        if not self.metadata_file.exists():
            return {}

        try:
            data = json.loads(self.metadata_file.read_text())
            metadata = {}

            for snapshot_id, snapshot_data in data.items():
                metadata[snapshot_id] = SnapshotMetadata(
                    snapshot_id=snapshot_data["snapshot_id"],
                    created_at=datetime.fromisoformat(snapshot_data["created_at"]),
                    workspace_root=snapshot_data["workspace_root"],
                    file_count=snapshot_data["file_count"],
                    total_size_bytes=snapshot_data["total_size_bytes"],
                    checksum=snapshot_data["checksum"],
                    description=snapshot_data["description"],
                )

            return metadata

        except Exception as e:
            self.logger.warning(f"Failed to load snapshots metadata: {e}")
            return {}

    def _save_snapshots_metadata(self):
        """Save snapshots metadata to file."""
        try:
            data = {}
            for snapshot_id, metadata in self.snapshots_metadata.items():
                data[snapshot_id] = {
                    "snapshot_id": metadata.snapshot_id,
                    "created_at": metadata.created_at.isoformat(),
                    "workspace_root": metadata.workspace_root,
                    "file_count": metadata.file_count,
                    "total_size_bytes": metadata.total_size_bytes,
                    "checksum": metadata.checksum,
                    "description": metadata.description,
                }

            self.metadata_file.write_text(json.dumps(data, indent=2))

        except Exception as e:
            self.logger.warning(f"Failed to save snapshots metadata: {e}")


class NaviOSSandbox:
    """
    Main NaviOS execution sandbox providing safe autonomous code execution.

    Features:
    - Filesystem snapshots for rollback
    - Resource monitoring and limits
    - Isolated execution environment
    - Automatic recovery on failure
    - Comprehensive logging and audit trail
    """

    def __init__(
        self,
        workspace_root: str,
        memory: Optional[EpisodicMemory] = None,
        resource_limits: Optional[ResourceLimits] = None,
    ):
        """
        Initialize NaviOS sandbox.

        Args:
            workspace_root: Root directory of workspace
            memory: Episodic memory for learning
            resource_limits: Resource limits for execution
        """
        self.workspace_root = Path(workspace_root)
        self.memory = memory or EpisodicMemory()
        self.limits = resource_limits or ResourceLimits()
        self.logger = logging.getLogger(__name__)

        # Initialize components
        self.snapshot_manager = FilesystemSnapshot(str(self.workspace_root))
        self.state = SandboxState.INITIALIZING

        # Execution tracking
        self.current_snapshot_id: Optional[str] = None
        self.execution_history: List[Dict[str, Any]] = []

        self.logger.info(f"NaviOS Sandbox initialized for workspace: {workspace_root}")
        self.state = SandboxState.READY

    async def safe_execute(
        self,
        operation_code: str,
        operation_description: str,
        parameters: Optional[Dict[str, Any]] = None,
        auto_rollback_on_error: bool = True,
        create_snapshot: bool = True,
    ) -> ExecutionResult:
        """
        Safely execute code with automatic snapshot and rollback capability.

        Args:
            operation_code: Python code to execute
            operation_description: Description of the operation
            parameters: Optional parameters for the operation
            auto_rollback_on_error: Whether to auto-rollback on failure
            create_snapshot: Whether to create snapshot before execution

        Returns:
            Execution result with rollback information
        """
        execution_start = datetime.utcnow()
        execution_id = f"exec_{execution_start.strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(operation_description.encode()).hexdigest()[:8]}"

        self.logger.info(f"Starting safe execution: {execution_id}")
        self.state = SandboxState.EXECUTING

        # Initialize result
        result = ExecutionResult(
            success=False,
            output=None,
            logs=[f"Execution started: {execution_id}"],
            errors=[],
            execution_time_seconds=0.0,
            resources_used={},
            snapshot_id=None,
            rollback_available=False,
            metadata={
                "execution_id": execution_id,
                "description": operation_description,
                "parameters": parameters or {},
            },
        )

        pre_execution_snapshot = None

        try:
            # Create pre-execution snapshot
            if create_snapshot:
                pre_execution_snapshot = self.snapshot_manager.create_snapshot(
                    f"Pre-execution snapshot for: {operation_description}"
                )
                result.snapshot_id = pre_execution_snapshot.snapshot_id
                result.rollback_available = True
                result.logs.append(
                    f"Created snapshot: {pre_execution_snapshot.snapshot_id}"
                )

            # Execute operation in monitored environment
            execution_result = await self._execute_monitored(
                operation_code, operation_description, parameters or {}
            )

            # Update result with execution data
            result.success = execution_result["success"]
            result.output = execution_result["output"]
            result.logs.extend(execution_result["logs"])
            result.errors.extend(execution_result["errors"])
            result.resources_used = execution_result["resources_used"]

            # Handle execution failure
            if not result.success and auto_rollback_on_error and pre_execution_snapshot:
                result.logs.append("Execution failed, attempting rollback...")

                rollback_success = self.snapshot_manager.restore_snapshot(
                    pre_execution_snapshot.snapshot_id
                )

                if rollback_success:
                    result.logs.append(
                        "Successfully rolled back to pre-execution state"
                    )
                    self.state = SandboxState.ROLLED_BACK
                else:
                    result.errors.append(
                        "Rollback failed - manual intervention may be required"
                    )
                    self.state = SandboxState.FAILED
            else:
                self.state = SandboxState.COMPLETED

        except Exception as e:
            result.errors.append(f"Execution framework error: {str(e)}")
            self.logger.error(f"Sandbox execution error: {e}")

            # Emergency rollback
            if auto_rollback_on_error and pre_execution_snapshot:
                try:
                    self.snapshot_manager.restore_snapshot(
                        pre_execution_snapshot.snapshot_id
                    )
                    result.logs.append("Emergency rollback completed")
                    self.state = SandboxState.ROLLED_BACK
                except Exception as rollback_error:
                    result.errors.append(f"Emergency rollback failed: {rollback_error}")
                    self.state = SandboxState.FAILED
            else:
                self.state = SandboxState.FAILED

        finally:
            # Calculate execution time
            result.execution_time_seconds = (
                datetime.utcnow() - execution_start
            ).total_seconds()

            # Record execution in history and memory
            execution_record = {
                "execution_id": execution_id,
                "timestamp": execution_start.isoformat(),
                "description": operation_description,
                "success": result.success,
                "execution_time": result.execution_time_seconds,
                "snapshot_id": result.snapshot_id,
                "rollback_performed": self.state == SandboxState.ROLLED_BACK,
                "resource_usage": result.resources_used,
            }

            self.execution_history.append(execution_record)

            # Record in memory
            await self._record_execution_in_memory(execution_record, result)

        self.logger.info(
            f"Execution completed: {execution_id}, Success: {result.success}, State: {self.state}"
        )
        return result

    async def _execute_monitored(
        self, operation_code: str, description: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute code with resource monitoring and safety checks.

        Args:
            operation_code: Python code to execute
            description: Operation description
            parameters: Execution parameters

        Returns:
            Execution result dictionary
        """
        result = {
            "success": False,
            "output": None,
            "logs": [],
            "errors": [],
            "resources_used": {},
        }

        # Create temporary execution script
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as temp_script:
            # Wrap code with parameter injection and safety
            wrapped_code = f"""
import sys
import os
import json
from pathlib import Path

# Injected parameters
PARAMETERS = {json.dumps(parameters)}
WORKSPACE_ROOT = Path(r"{self.workspace_root}")

# Change to workspace directory
os.chdir(WORKSPACE_ROOT)

try:
    print("=== OPERATION EXECUTION START ===")
    
    # User operation code
{self._indent_code(operation_code, "    ")}
    
    print("=== OPERATION EXECUTION END ===")
    
except Exception as e:
    print(f"OPERATION ERROR: {{e}}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
"""

            temp_script.write(wrapped_code)
            temp_script_path = temp_script.name

        try:
            # Start resource monitoring
            monitor = ResourceMonitor(self.limits)
            monitor.start_monitoring()

            # Execute with timeout
            process = await asyncio.create_subprocess_exec(
                "python",
                temp_script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace_root),
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.limits.execution_time_sec
                )

                # Stop monitoring
                monitor.stop_monitoring()

                if process.returncode == 0:
                    result["success"] = True
                    result["output"] = stdout.decode("utf-8")
                    result["logs"].append("Operation completed successfully")
                else:
                    result["errors"].append(
                        f"Operation failed with return code {process.returncode}"
                    )
                    if stderr:
                        result["errors"].append(stderr.decode("utf-8"))

                # Collect resource usage
                result["resources_used"] = {
                    "peak_cpu_percent": monitor.peak_usage["cpu_percent"],
                    "peak_memory_mb": monitor.peak_usage["memory_mb"],
                    "peak_subprocess_count": monitor.peak_usage["subprocess_count"],
                    "resource_violations": monitor.violations,
                }

                # Check for resource violations
                if monitor.violations:
                    result["errors"].extend(
                        [f"Resource violation: {v}" for v in monitor.violations]
                    )
                    if result["success"]:  # Demote success to failure if violations
                        result["success"] = False
                        result["errors"].append(
                            "Operation succeeded but violated resource limits"
                        )

            except asyncio.TimeoutError:
                process.kill()
                result["errors"].append(
                    f"Operation timed out after {self.limits.execution_time_sec} seconds"
                )
                monitor.stop_monitoring()

        except Exception as e:
            result["errors"].append(f"Execution setup error: {str(e)}")

        finally:
            # Cleanup temporary script
            try:
                os.unlink(temp_script_path)
            except Exception:
                pass

        return result

    def _indent_code(self, code: str, indent: str = "    ") -> str:
        """Indent code block for embedding in wrapper."""
        lines = code.split("\n")
        return "\n".join(indent + line if line.strip() else line for line in lines)

    async def _record_execution_in_memory(
        self, execution_record: Dict[str, Any], result: ExecutionResult
    ):
        """Record execution in episodic memory."""
        try:
            event_content = f"NaviOS execution: {execution_record['description']}"
            if result.success:
                event_content += " (SUCCESS)"
            else:
                event_content += " (FAILED)"
                if result.snapshot_id:
                    event_content += " - Rollback available"

            await self.memory.record_event(
                event_type="code_execution",
                content=event_content,
                metadata={
                    "execution_id": execution_record["execution_id"],
                    "success": result.success,
                    "execution_time": result.execution_time_seconds,
                    "snapshot_id": result.snapshot_id,
                    "rollback_performed": execution_record["rollback_performed"],
                    "resource_violations": result.resources_used.get(
                        "resource_violations", []
                    ),
                    "peak_memory_mb": result.resources_used.get("peak_memory_mb", 0),
                    "peak_cpu_percent": result.resources_used.get(
                        "peak_cpu_percent", 0
                    ),
                },
            )

        except Exception as e:
            self.logger.warning(f"Failed to record execution in memory: {e}")

    def get_execution_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent execution history.

        Args:
            limit: Maximum number of executions to return

        Returns:
            List of execution records
        """
        return self.execution_history[-limit:]

    def get_available_snapshots(self) -> List[SnapshotMetadata]:
        """
        Get list of available snapshots for rollback.

        Returns:
            List of snapshot metadata
        """
        return self.snapshot_manager.list_snapshots()

    def manual_rollback(self, snapshot_id: str) -> bool:
        """
        Manually rollback to a specific snapshot.

        Args:
            snapshot_id: Snapshot identifier

        Returns:
            True if rollback was successful
        """
        try:
            success = self.snapshot_manager.restore_snapshot(snapshot_id)
            if success:
                self.state = SandboxState.ROLLED_BACK
                self.logger.info(f"Manual rollback to snapshot {snapshot_id} completed")
            return success
        except Exception as e:
            self.logger.error(f"Manual rollback failed: {e}")
            return False

    def cleanup_resources(self, max_snapshots: int = 10, max_age_days: int = 7):
        """
        Clean up sandbox resources.

        Args:
            max_snapshots: Maximum number of snapshots to keep
            max_age_days: Maximum age of snapshots in days
        """
        try:
            # Clean up old snapshots
            self.snapshot_manager.cleanup_old_snapshots(max_snapshots, max_age_days)

            # Trim execution history
            if len(self.execution_history) > 100:
                self.execution_history = self.execution_history[-100:]

            self.logger.info("Sandbox resource cleanup completed")

        except Exception as e:
            self.logger.warning(f"Resource cleanup failed: {e}")

    def get_sandbox_status(self) -> Dict[str, Any]:
        """
        Get current sandbox status and statistics.

        Returns:
            Sandbox status information
        """
        snapshots = self.snapshot_manager.list_snapshots()

        total_snapshot_size = sum(s.total_size_bytes for s in snapshots)
        recent_executions = len(
            [
                e
                for e in self.execution_history
                if datetime.fromisoformat(e["timestamp"])
                > datetime.utcnow() - timedelta(hours=24)
            ]
        )

        success_rate = 0.0
        if self.execution_history:
            successful = len([e for e in self.execution_history if e["success"]])
            success_rate = successful / len(self.execution_history) * 100

        return {
            "state": self.state.value,
            "workspace_root": str(self.workspace_root),
            "total_executions": len(self.execution_history),
            "recent_executions_24h": recent_executions,
            "success_rate_percent": success_rate,
            "available_snapshots": len(snapshots),
            "total_snapshot_size_mb": total_snapshot_size / 1024 / 1024,
            "current_snapshot_id": self.current_snapshot_id,
            "resource_limits": {
                "cpu_percent": self.limits.cpu_percent,
                "memory_mb": self.limits.memory_mb,
                "execution_time_sec": self.limits.execution_time_sec,
            },
        }
