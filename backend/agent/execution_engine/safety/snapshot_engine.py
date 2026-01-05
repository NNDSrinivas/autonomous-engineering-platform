"""
SnapshotEngine - Phase 4.5

Enterprise-grade snapshot system for safe rollbacks.
Takes comprehensive snapshots of file system and git state before risky operations.
"""

import os
import hashlib
import subprocess
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
import uuid

from .safety_types import (
    FileState,
    GitState,
    SnapshotMetadata,
    SafetyStatus,
    SafetyReport,
)

logger = logging.getLogger(__name__)


class Snapshot:
    """
    Comprehensive snapshot containing file states, git state, and metadata.

    This is the core data structure for enterprise rollback operations.
    """

    def __init__(
        self,
        files: Dict[str, FileState],
        git_state: GitState,
        metadata: SnapshotMetadata,
    ):
        self.files = files
        self.git_state = git_state
        self.metadata = metadata

    def to_dict(self) -> Dict[str, Any]:
        """Serialize snapshot to dictionary for storage"""
        return {
            "files": {path: state.model_dump() for path, state in self.files.items()},
            "git_state": self.git_state.model_dump(),
            "metadata": self.metadata.model_dump(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Snapshot":
        """Deserialize snapshot from dictionary"""
        files = {
            path: FileState(**state_data) for path, state_data in data["files"].items()
        }
        git_state = GitState(**data["git_state"])
        metadata = SnapshotMetadata(**data["metadata"])

        return cls(files, git_state, metadata)

    def get_file_count(self) -> int:
        """Get number of files in snapshot"""
        return len(self.files)

    def get_total_size(self) -> int:
        """Get total size of all files in bytes"""
        return sum(
            len(file_state.content.encode("utf-8"))
            for file_state in self.files.values()
        )

    def contains_file(self, file_path: str) -> bool:
        """Check if snapshot contains specific file"""
        return file_path in self.files


class SnapshotEngine:
    """
    Enterprise snapshot engine for safe autonomous operations.

    Features:
    - Comprehensive file state capture
    - Git repository state tracking
    - Integrity verification with checksums
    - Efficient storage and retrieval
    - Automated cleanup of old snapshots
    """

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root).resolve()
        self.snapshots_dir = self.workspace_root / ".navi" / "snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache of recent snapshots
        self._snapshot_cache: Dict[str, Snapshot] = {}
        self._load_recent_snapshots()

    def take_snapshot(
        self,
        files: List[str],
        operation: str = "autonomous_operation",
        trigger: str = "before_changes",
        description: Optional[str] = None,
    ) -> Snapshot:
        """
        Take a comprehensive snapshot before risky operations.

        Args:
            files: List of file paths to include in snapshot
            operation: Name of operation that triggered snapshot
            trigger: What triggered this snapshot
            description: Human-readable description

        Returns:
            Snapshot object containing all captured state
        """
        logger.info(f"Taking safety snapshot for {len(files)} files")

        snapshot_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc)

        try:
            # Capture file states
            file_states = {}
            total_size = 0

            for file_path in files:
                abs_path = self._resolve_file_path(file_path)
                if abs_path.exists() and abs_path.is_file():
                    file_state = self._capture_file_state(abs_path)
                    file_states[file_path] = file_state
                    total_size += len(file_state.content.encode("utf-8"))

            # Capture git state
            git_state = self._capture_git_state()

            # Create metadata
            metadata = SnapshotMetadata(
                snapshot_id=snapshot_id,
                created_at=created_at,
                operation=operation,
                trigger=trigger,
                workspace_path=str(self.workspace_root),
                file_count=len(file_states),
                total_size_bytes=total_size,
                description=description or f"Snapshot for {operation}",
            )

            # Create snapshot
            snapshot = Snapshot(file_states, git_state, metadata)

            # Store snapshot
            self._store_snapshot(snapshot)

            # Cache recent snapshot
            self._snapshot_cache[snapshot_id] = snapshot

            logger.info(
                f"Created snapshot {snapshot_id}: {len(file_states)} files, "
                f"{total_size} bytes, git branch: {git_state.current_branch}"
            )

            return snapshot

        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            raise

    def get_latest_snapshot(self) -> Optional[Snapshot]:
        """Get the most recent snapshot"""
        if not self._snapshot_cache:
            return None

        # Find most recent snapshot by creation time
        latest_snapshot = max(
            self._snapshot_cache.values(),
            key=lambda s: s.metadata.created_at,
            default=None,
        )

        return latest_snapshot

    def get_snapshot_by_id(self, snapshot_id: str) -> Optional[Snapshot]:
        """Get specific snapshot by ID"""
        if snapshot_id in self._snapshot_cache:
            return self._snapshot_cache[snapshot_id]

        # Try loading from storage
        snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"
        if snapshot_file.exists():
            try:
                with open(snapshot_file, "r") as f:
                    data = json.load(f)
                snapshot = Snapshot.from_dict(data)
                self._snapshot_cache[snapshot_id] = snapshot
                return snapshot
            except Exception as e:
                logger.error(f"Failed to load snapshot {snapshot_id}: {e}")

        return None

    def list_snapshots(self, limit: int = 10) -> List[SnapshotMetadata]:
        """List recent snapshots with metadata only"""
        snapshots = sorted(
            self._snapshot_cache.values(),
            key=lambda s: s.metadata.created_at,
            reverse=True,
        )

        return [s.metadata for s in snapshots[:limit]]

    def cleanup_old_snapshots(self, keep_count: int = 5) -> int:
        """Clean up old snapshots, keeping only the most recent"""
        all_snapshots = sorted(
            self._snapshot_cache.values(),
            key=lambda s: s.metadata.created_at,
            reverse=True,
        )

        snapshots_to_remove = all_snapshots[keep_count:]
        removed_count = 0

        for snapshot in snapshots_to_remove:
            try:
                snapshot_file = (
                    self.snapshots_dir / f"{snapshot.metadata.snapshot_id}.json"
                )
                if snapshot_file.exists():
                    snapshot_file.unlink()

                # Remove from cache
                if snapshot.metadata.snapshot_id in self._snapshot_cache:
                    del self._snapshot_cache[snapshot.metadata.snapshot_id]

                removed_count += 1
                logger.info(f"Cleaned up old snapshot: {snapshot.metadata.snapshot_id}")

            except Exception as e:
                logger.warning(
                    f"Failed to cleanup snapshot {snapshot.metadata.snapshot_id}: {e}"
                )

        return removed_count

    def generate_safety_report(self) -> SafetyReport:
        """Generate comprehensive safety report for UI"""
        latest_snapshot = self.get_latest_snapshot()
        current_time = datetime.now(timezone.utc)

        # Calculate snapshot age
        snapshot_age_minutes = None
        if latest_snapshot:
            age_delta = current_time - latest_snapshot.metadata.created_at
            snapshot_age_minutes = int(age_delta.total_seconds() / 60)

        # Assess current status
        current_status = SafetyStatus.SAFE
        risk_factors = []
        recommended_actions = []

        if not latest_snapshot:
            current_status = SafetyStatus.AT_RISK
            risk_factors.append("No safety snapshot available")
            recommended_actions.append("Take snapshot before autonomous operations")
        elif snapshot_age_minutes and snapshot_age_minutes > 60:
            risk_factors.append(f"Snapshot is {snapshot_age_minutes} minutes old")
            recommended_actions.append("Consider taking fresh snapshot")

        # Check git state
        try:
            git_state = self._capture_git_state()
            if not git_state.is_clean:
                risk_factors.append("Uncommitted changes in git")
                recommended_actions.append("Commit or stash changes before operations")
        except Exception:
            risk_factors.append("Unable to check git status")

        # Determine rollback scope
        rollback_scope = []
        if latest_snapshot:
            rollback_scope = list(latest_snapshot.files.keys())

        return SafetyReport(
            current_status=current_status,
            snapshot_available=latest_snapshot is not None,
            snapshot_age_minutes=snapshot_age_minutes,
            risk_factors=risk_factors,
            recommended_actions=recommended_actions,
            can_rollback=latest_snapshot is not None,
            rollback_scope=rollback_scope,
        )

    def _resolve_file_path(self, file_path: str) -> Path:
        """Resolve file path relative to workspace"""
        if os.path.isabs(file_path):
            return Path(file_path)
        return self.workspace_root / file_path

    def _capture_file_state(self, file_path: Path) -> FileState:
        """Capture complete state of a single file"""
        try:
            content = file_path.read_text(encoding="utf-8")
            stat_info = file_path.stat()

            # Generate checksum for integrity
            checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()

            return FileState(
                path=str(file_path.relative_to(self.workspace_root)),
                content=content,
                last_modified=datetime.fromtimestamp(stat_info.st_mtime, timezone.utc),
                permissions=oct(stat_info.st_mode)[-3:],
                checksum=checksum,
            )

        except Exception as e:
            logger.error(f"Failed to capture state for {file_path}: {e}")
            raise

    def _capture_git_state(self) -> GitState:
        """Capture current git repository state"""
        try:
            # Get current branch
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                cwd=self.workspace_root,
            )
            current_branch = (
                result.stdout.strip() if result.returncode == 0 else "unknown"
            )

            # Get current commit SHA
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.workspace_root,
            )
            commit_sha = result.stdout.strip() if result.returncode == 0 else None

            # Check if working directory is clean
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=self.workspace_root,
            )
            is_clean = len(result.stdout.strip()) == 0
            uncommitted_changes = (
                result.stdout.strip().split("\n") if not is_clean else []
            )

            # Get remote URL (optional)
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                cwd=self.workspace_root,
            )
            remote_url = result.stdout.strip() if result.returncode == 0 else None

            return GitState(
                current_branch=current_branch,
                commit_sha=commit_sha,
                is_clean=is_clean,
                remote_url=remote_url,
                uncommitted_changes=uncommitted_changes,
            )

        except Exception as e:
            logger.warning(f"Failed to capture git state: {e}")
            # Return minimal git state on failure
            return GitState(
                current_branch="unknown",
                commit_sha=None,
                is_clean=False,
                remote_url=None,
                uncommitted_changes=[],
            )

    def _store_snapshot(self, snapshot: Snapshot) -> None:
        """Store snapshot to persistent storage"""
        snapshot_file = self.snapshots_dir / f"{snapshot.metadata.snapshot_id}.json"

        try:
            with open(snapshot_file, "w") as f:
                json.dump(snapshot.to_dict(), f, indent=2, default=str)

            logger.info(f"Stored snapshot to {snapshot_file}")

        except Exception as e:
            logger.error(f"Failed to store snapshot: {e}")
            raise

    def _load_recent_snapshots(self) -> None:
        """Load recent snapshots from storage into cache"""
        if not self.snapshots_dir.exists():
            return

        snapshot_files = list(self.snapshots_dir.glob("*.json"))

        # Sort by modification time, load most recent first
        snapshot_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        for snapshot_file in snapshot_files[:10]:  # Load up to 10 recent snapshots
            try:
                with open(snapshot_file, "r") as f:
                    data = json.load(f)

                snapshot = Snapshot.from_dict(data)
                self._snapshot_cache[snapshot.metadata.snapshot_id] = snapshot

                logger.info(f"Loaded snapshot: {snapshot.metadata.snapshot_id}")

            except Exception as e:
                logger.warning(f"Failed to load snapshot from {snapshot_file}: {e}")

        logger.info(f"Loaded {len(self._snapshot_cache)} snapshots into cache")
