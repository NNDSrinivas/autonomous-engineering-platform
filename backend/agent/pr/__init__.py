"""
NAVI Phase 3.5 - PR Generation & Lifecycle Package

This package contains the components for autonomous PR generation:
- BranchManager: Safe branch creation and management (Phase 3.5.1)
- CommitComposer: Commit message generation and staging (Phase 3.5.2)
- PRCreator: PR creation and metadata management (Phase 3.5.3)
- PRMonitor: CI monitoring and status updates (Phase 3.5.4)
"""

from .branch_manager import BranchManager, BranchResult, BranchInfo, BranchCreationError
from .commit_composer import (
    CommitComposer,
    CommitResult,
    CommitInfo,
    CommitCreationError,
)
from .pr_creator import PRCreator, PRResult, PRCreationError
from .pr_lifecycle_engine import (
    PRLifecycleEngine,
    PRStatus,
    PRLifecycleResult,
    PRLifecycleError,
)

__all__ = [
    # Branch Management (Phase 3.5.1)
    "BranchManager",
    "BranchResult",
    "BranchInfo",
    "BranchCreationError",
    # Commit Composition (Phase 3.5.2)
    "CommitComposer",
    "CommitResult",
    "CommitInfo",
    "CommitCreationError",
    # PR Creation (Phase 3.5.3)
    "PRCreator",
    "PRResult",
    "PRCreationError",
    # PR Lifecycle (Phase 3.5.4)
    "PRLifecycleEngine",
    "PRStatus",
    "PRLifecycleResult",
    "PRLifecycleError",
]
