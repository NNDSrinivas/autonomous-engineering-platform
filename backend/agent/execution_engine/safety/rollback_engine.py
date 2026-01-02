"""
RollbackEngine - Phase 4.5

Enterprise-grade rollback system for safe autonomous operations.
Provides complete restoration of file system and git state from snapshots.
"""

import os
import subprocess
import logging
import time
from typing import List, Optional, Dict, Any
from pathlib import Path

from .safety_types import (
    RollbackResult, RollbackTrigger, SafetyStatus, 
    FileState, GitState
)
from .snapshot_engine import Snapshot, SnapshotEngine

logger = logging.getLogger(__name__)


class RollbackEngine:
    """
    Enterprise rollback engine for autonomous operation safety.
    
    Features:
    - Complete file system restoration
    - Git repository state restoration  
    - Integrity verification during rollback
    - Comprehensive rollback reporting
    - Graceful handling of partial failures
    """
    
    def __init__(self, workspace_root: str, snapshot_engine: Optional[SnapshotEngine] = None):
        self.workspace_root = Path(workspace_root).resolve()
        self.snapshot_engine = snapshot_engine or SnapshotEngine(str(self.workspace_root))
        
    def rollback_to_snapshot(
        self, 
        snapshot: Snapshot, 
        trigger: RollbackTrigger,
        verify_integrity: bool = True
    ) -> RollbackResult:
        """
        Perform complete rollback to specific snapshot.
        
        Args:
            snapshot: Snapshot to restore to
            trigger: What triggered this rollback
            verify_integrity: Whether to verify file integrity after restore
            
        Returns:
            Comprehensive rollback result
        """
        start_time = time.time()
        logger.info(f"Starting rollback to snapshot {snapshot.metadata.snapshot_id}")
        
        files_restored = []
        files_failed = []
        git_restored = False
        error_message = None
        
        try:
            # Phase 1: Restore files
            logger.info(f"Restoring {len(snapshot.files)} files")
            
            for file_path, file_state in snapshot.files.items():
                try:
                    self._restore_file(file_path, file_state, verify_integrity)
                    files_restored.append(file_path)
                    logger.debug(f"Restored file: {file_path}")
                    
                except Exception as e:
                    files_failed.append(file_path)
                    logger.error(f"Failed to restore {file_path}: {e}")
                    
            # Phase 2: Restore git state
            logger.info(f"Restoring git state: branch={snapshot.git_state.current_branch}")
            
            try:
                self._restore_git_state(snapshot.git_state)
                git_restored = True
                logger.info("Git state restored successfully")
                
            except Exception as e:
                logger.error(f"Failed to restore git state: {e}")
                error_message = f"Git restoration failed: {e}"
                
            # Phase 3: Verify rollback success
            success = len(files_failed) == 0 and git_restored
            
            final_status = SafetyStatus.RESTORED if success else SafetyStatus.AT_RISK
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            result = RollbackResult(
                success=success,
                trigger=trigger,
                files_restored=files_restored,
                files_failed=files_failed,
                git_restored=git_restored,
                duration_ms=duration_ms,
                error_message=error_message,
                final_status=final_status
            )
            
            if success:
                logger.info(
                    f"Rollback completed successfully in {duration_ms}ms: "
                    f"{len(files_restored)} files restored"
                )
            else:
                logger.warning(
                    f"Rollback partially failed: {len(files_failed)} files failed, "
                    f"git_restored={git_restored}"
                )
                
            return result
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Rollback failed with exception: {e}")
            
            return RollbackResult(
                success=False,
                trigger=trigger,
                files_restored=files_restored,
                files_failed=list(snapshot.files.keys()),
                git_restored=False,
                duration_ms=duration_ms,
                error_message=str(e),
                final_status=SafetyStatus.REQUIRES_ROLLBACK
            )
            
    def rollback_to_latest(self, trigger: RollbackTrigger) -> Optional[RollbackResult]:
        """
        Rollback to the most recent snapshot.
        
        Args:
            trigger: What triggered this rollback
            
        Returns:
            Rollback result or None if no snapshot available
        """
        latest_snapshot = self.snapshot_engine.get_latest_snapshot()
        
        if not latest_snapshot:
            logger.warning("No snapshot available for rollback")
            return None
            
        logger.info(
            f"Rolling back to latest snapshot: {latest_snapshot.metadata.snapshot_id} "
            f"(created {latest_snapshot.metadata.created_at})"
        )
        
        return self.rollback_to_snapshot(latest_snapshot, trigger)
        
    def rollback_files_only(
        self, 
        file_paths: List[str], 
        trigger: RollbackTrigger
    ) -> Optional[RollbackResult]:
        """
        Rollback only specific files from latest snapshot.
        
        Args:
            file_paths: List of files to rollback
            trigger: What triggered this rollback
            
        Returns:
            Rollback result or None if no snapshot available
        """
        latest_snapshot = self.snapshot_engine.get_latest_snapshot()
        
        if not latest_snapshot:
            logger.warning("No snapshot available for file rollback")
            return None
            
        start_time = time.time()
        logger.info(f"Rolling back {len(file_paths)} specific files")
        
        files_restored = []
        files_failed = []
        
        for file_path in file_paths:
            if file_path in latest_snapshot.files:
                try:
                    file_state = latest_snapshot.files[file_path]
                    self._restore_file(file_path, file_state, verify_integrity=True)
                    files_restored.append(file_path)
                    logger.info(f"Restored file: {file_path}")
                    
                except Exception as e:
                    files_failed.append(file_path)
                    logger.error(f"Failed to restore {file_path}: {e}")
            else:
                files_failed.append(file_path)
                logger.warning(f"File {file_path} not found in snapshot")                
        duration_ms = int((time.time() - start_time) * 1000)
        success = len(files_failed) == 0
        
        return RollbackResult(
            success=success,
            trigger=trigger,
            files_restored=files_restored,
            files_failed=files_failed,
            git_restored=False,  # Git not touched in file-only rollback
            duration_ms=duration_ms,
            error_message=None,
            final_status=SafetyStatus.SAFE if success else SafetyStatus.AT_RISK
        )
        
    def can_rollback(self) -> bool:
        """Check if rollback is currently possible"""
        return self.snapshot_engine.get_latest_snapshot() is not None
        
    def get_rollback_preview(self) -> Optional[Dict[str, Any]]:
        """Get preview of what would be rolled back"""
        latest_snapshot = self.snapshot_engine.get_latest_snapshot()
        
        if not latest_snapshot:
            return None
            
        return {
            "snapshot_id": latest_snapshot.metadata.snapshot_id,
            "created_at": latest_snapshot.metadata.created_at,
            "operation": latest_snapshot.metadata.operation,
            "files_count": len(latest_snapshot.files),
            "files_list": list(latest_snapshot.files.keys()),
            "git_branch": latest_snapshot.git_state.current_branch,
            "total_size_bytes": latest_snapshot.metadata.total_size_bytes
        }
        
    def emergency_rollback(self) -> Optional[RollbackResult]:
        """Emergency rollback with minimal checks for critical situations"""
        logger.warning("Performing emergency rollback with minimal safety checks")
        
        latest_snapshot = self.snapshot_engine.get_latest_snapshot()
        if not latest_snapshot:
            logger.error("No snapshot available for emergency rollback")
            return None
            
        # Skip integrity verification for speed
        return self.rollback_to_snapshot(
            latest_snapshot, 
            RollbackTrigger.SAFETY_OVERRIDE,
            verify_integrity=False
        )
        
    def _restore_file(self, file_path: str, file_state: FileState, verify_integrity: bool = True) -> None:
        """Restore a single file from snapshot"""
        abs_path = self._resolve_file_path(file_path)
        
        # Ensure parent directory exists
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file content
        abs_path.write_text(file_state.content, encoding='utf-8')
        
        # Restore permissions if available
        if file_state.permissions:
            try:
                os.chmod(abs_path, int(file_state.permissions, 8))
            except Exception as e:
                logger.warning(f"Failed to restore permissions for {file_path}: {e}")
                
        # Verify integrity if requested
        if verify_integrity:
            import hashlib
            actual_content = abs_path.read_text(encoding='utf-8')
            actual_checksum = hashlib.sha256(actual_content.encode('utf-8')).hexdigest()
            
            if actual_checksum != file_state.checksum:
                raise ValueError(f"File integrity check failed: {file_path}")
                
        logger.debug(f"Restored file: {file_path} ({len(file_state.content)} bytes)")
        
    def _restore_git_state(self, git_state: GitState) -> None:
        """Restore git repository to snapshot state"""
        try:
            # Check if we're in a git repository
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                cwd=self.workspace_root
            )
            
            if result.returncode != 0:
                logger.warning("Not in a git repository, skipping git state restoration")
                return
                
            # Get current branch
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                cwd=self.workspace_root
            )
            current_branch = result.stdout.strip()
            
            # Switch to target branch if different
            if current_branch != git_state.current_branch:
                logger.info(f"Switching from {current_branch} to {git_state.current_branch}")
                
                result = subprocess.run(
                    ["git", "checkout", git_state.current_branch],
                    capture_output=True,
                    text=True,
                    cwd=self.workspace_root
                )
                
                if result.returncode != 0:
                    raise RuntimeError(f"Failed to checkout branch {git_state.current_branch}: {result.stderr}")
                    
            # If we have a specific commit SHA, reset to it (optional)
            if git_state.commit_sha:
                logger.info(f"Resetting to commit {git_state.commit_sha}")
                
                result = subprocess.run(
                    ["git", "reset", "--hard", git_state.commit_sha],
                    capture_output=True,
                    text=True,
                    cwd=self.workspace_root
                )
                
                if result.returncode != 0:
                    logger.warning(f"Failed to reset to {git_state.commit_sha}: {result.stderr}")
                    
            logger.info(f"Git state restored: branch={git_state.current_branch}")
            
        except Exception as e:
            logger.error(f"Git state restoration failed: {e}")
            raise
            
    def _resolve_file_path(self, file_path: str) -> Path:
        """Resolve file path relative to workspace"""
        if os.path.isabs(file_path):
            return Path(file_path)
        return self.workspace_root / file_path
        
    def get_rollback_statistics(self) -> Dict[str, Any]:
        """Get statistics about rollback capabilities"""
        snapshots = self.snapshot_engine.list_snapshots(limit=20)
        
        if not snapshots:
            return {
                "snapshots_available": 0,
                "latest_snapshot": None,
                "total_files_protected": 0,
                "rollback_ready": False
            }
            
        latest = snapshots[0]
        total_files = sum(s.file_count for s in snapshots)
        
        return {
            "snapshots_available": len(snapshots),
            "latest_snapshot": {
                "id": latest.snapshot_id,
                "created_at": latest.created_at,
                "operation": latest.operation,
                "file_count": latest.file_count
            },
            "total_files_protected": total_files,
            "rollback_ready": True,
            "oldest_snapshot": snapshots[-1].created_at if snapshots else None
        }