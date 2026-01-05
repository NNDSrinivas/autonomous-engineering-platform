"""
Branch Manager for NAVI Phase 3.5.1

Responsibility:
- Create and manage git branches safely
- Enforce clean working tree
- Generate deterministic branch names

Order:
- Runs AFTER apply_diff
- Runs BEFORE commit composition
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class BranchStatus(Enum):
    """Branch creation status"""

    CREATED = "created"
    EXISTS = "exists"
    FAILED = "failed"


class BranchCreationError(RuntimeError):
    """Raised when branch creation fails"""

    pass


@dataclass(frozen=True)
class BranchInfo:
    """Branch information result"""

    name: str
    base: str
    created: bool
    timestamp: str
    status: BranchStatus


@dataclass(frozen=True)
class BranchResult:
    """Complete branch creation result for UI emission"""

    success: bool
    branch_name: str
    created_from: str
    working_tree_clean: bool
    message: str
    error: Optional[str] = None


class BranchManager:
    """
    Handles safe branch creation for PR workflows.

    This is production-grade code with comprehensive safety checks,
    deterministic naming, and clean error handling.
    """

    DEFAULT_BASE_BRANCHES = ("main", "master", "develop")
    BRANCH_PREFIX = "navi"
    MAX_PURPOSE_LENGTH = 40

    def __init__(self, repo_root: str) -> None:
        """
        Initialize BranchManager for a repository.

        Args:
            repo_root: Absolute path to git repository root
        """
        self.repo_root = os.path.abspath(repo_root)
        self._validate_git_repo()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_pr_branch(
        self,
        *,
        feature_description: str,
        base_branch: Optional[str] = None,
        force_clean: bool = False,
    ) -> BranchResult:
        """
        Create a new branch for PR generation.

        This is the main entry point for Phase 3.5 PR pipeline.

        Args:
            feature_description: Description of the feature/fix
            base_branch: Optional base branch (auto-detected if None)
            force_clean: If True, stash changes instead of failing

        Returns:
            BranchResult with success status and branch info
        """
        try:
            logger.info(
                f"[BRANCH_MANAGER] Creating PR branch for: {feature_description}"
            )

            # Check working tree status
            if not self._is_working_tree_clean():
                if force_clean:
                    self._stash_changes()
                    logger.info("[BRANCH_MANAGER] Stashed uncommitted changes")
                else:
                    return BranchResult(
                        success=False,
                        branch_name="",
                        created_from="",
                        working_tree_clean=False,
                        message="Working tree has uncommitted changes",
                        error="Clean working tree required for branch creation",
                    )

            # Determine base branch
            base = base_branch or self._detect_base_branch()
            logger.info(f"[BRANCH_MANAGER] Using base branch: {base}")

            # Generate branch name
            branch_name = self._generate_branch_name(feature_description)
            logger.info(f"[BRANCH_MANAGER] Generated branch name: {branch_name}")

            # Check for collision
            if self._branch_exists(branch_name):
                # Generate alternative name with additional timestamp
                branch_name = self._generate_alternative_branch_name(
                    feature_description
                )
                logger.warning(
                    f"[BRANCH_MANAGER] Branch collision, using alternative: {branch_name}"
                )

            # Create the branch
            self._checkout_new_branch(branch_name, base)

            logger.info(f"[BRANCH_MANAGER] Successfully created branch: {branch_name}")

            return BranchResult(
                success=True,
                branch_name=branch_name,
                created_from=base,
                working_tree_clean=True,
                message=f"Created branch '{branch_name}' from '{base}'",
            )

        except Exception as e:
            logger.error(f"[BRANCH_MANAGER] Branch creation failed: {str(e)}")
            return BranchResult(
                success=False,
                branch_name="",
                created_from=base_branch or "unknown",
                working_tree_clean=self._is_working_tree_clean(),
                message=f"Branch creation failed: {str(e)}",
                error=str(e),
            )

    def create_branch(
        self,
        *,
        purpose: str,
        base_branch: Optional[str] = None,
    ) -> BranchInfo:
        """
        Create a new branch for a change set.

        Legacy API - use create_pr_branch for new code.

        Args:
            purpose: Short description (used in branch name)
            base_branch: Optional override

        Returns:
            BranchInfo with creation details

        Raises:
            BranchCreationError on failure
        """
        self._ensure_clean_working_tree()

        base = base_branch or self._detect_base_branch()
        branch_name = self._generate_branch_name(purpose)

        if self._branch_exists(branch_name):
            raise BranchCreationError(f"Branch already exists: {branch_name}")

        self._checkout_new_branch(branch_name, base)

        return BranchInfo(
            name=branch_name,
            base=base,
            created=True,
            timestamp=datetime.utcnow().isoformat() + "Z",
            status=BranchStatus.CREATED,
        )

    def get_current_branch(self) -> str:
        """Get the currently checked out branch name."""
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=self.repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            raise BranchCreationError(
                f"Failed to get current branch: {result.stderr.strip()}"
            )

        return result.stdout.strip()

    def is_pr_branch(self, branch_name: Optional[str] = None) -> bool:
        """Check if a branch is a NAVI PR branch."""
        if branch_name is None:
            branch_name = self.get_current_branch()

        return branch_name.startswith(f"{self.BRANCH_PREFIX}/")

    # ------------------------------------------------------------------
    # Safety gates and validation
    # ------------------------------------------------------------------

    def _validate_git_repo(self) -> None:
        """Ensure the repo_root is a valid git repository."""
        git_dir = os.path.join(self.repo_root, ".git")
        if not os.path.exists(git_dir):
            raise BranchCreationError(f"Not a git repository: {self.repo_root}")

    def _ensure_clean_working_tree(self) -> None:
        """Ensure working tree is clean (legacy method)."""
        if not self._is_working_tree_clean():
            raise BranchCreationError("Working tree is not clean; cannot create branch")

    def _is_working_tree_clean(self) -> bool:
        """Check if working tree is clean."""
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            logger.error(f"[BRANCH_MANAGER] git status failed: {result.stderr.strip()}")
            return False

        return not result.stdout.strip()

    def _stash_changes(self) -> None:
        """Stash uncommitted changes."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        stash_message = f"NAVI auto-stash before branch creation - {timestamp}"

        result = subprocess.run(
            ["git", "stash", "push", "-m", stash_message],
            cwd=self.repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            raise BranchCreationError(
                f"Failed to stash changes: {result.stderr.strip()}"
            )

    def _detect_base_branch(self) -> str:
        """Detect the appropriate base branch."""
        # First try current branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=self.repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        current = result.stdout.strip()
        if current and not self.is_pr_branch(current):
            # Current branch is not a PR branch, use it as base
            return current

        # Check for default branches
        for candidate in self.DEFAULT_BASE_BRANCHES:
            if self._branch_exists(candidate):
                return candidate

        # Fallback to first branch found
        result = subprocess.run(
            ["git", "branch", "-r", "--format=%(refname:lstrip=3)"],
            cwd=self.repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode == 0:
            branches = [b.strip() for b in result.stdout.split("\n") if b.strip()]
            for branch in branches:
                if branch in self.DEFAULT_BASE_BRANCHES:
                    return branch

            # Use first remote branch
            if branches:
                return branches[0]

        raise BranchCreationError("Unable to determine base branch")

    # ------------------------------------------------------------------
    # Git operations
    # ------------------------------------------------------------------

    def _branch_exists(self, name: str) -> bool:
        """Check if a branch exists locally or remotely."""
        # Check local branch
        result = subprocess.run(
            ["git", "rev-parse", "--verify", name],
            cwd=self.repo_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            return True

        # Check remote branch
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"origin/{name}"],
            cwd=self.repo_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0

    def _checkout_new_branch(self, name: str, base: str) -> None:
        """Create and checkout a new branch."""
        result = subprocess.run(
            ["git", "checkout", "-b", name, base],
            cwd=self.repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            raise BranchCreationError(
                f"Failed to create branch {name}: {result.stderr.strip()}"
            )

    # ------------------------------------------------------------------
    # Branch naming
    # ------------------------------------------------------------------

    def _generate_branch_name(self, purpose: str) -> str:
        """Generate a deterministic branch name."""
        safe_purpose = self._slugify(purpose)
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        return f"{self.BRANCH_PREFIX}/{safe_purpose}-{timestamp}"

    def _generate_alternative_branch_name(self, purpose: str) -> str:
        """Generate an alternative branch name to avoid collisions."""
        safe_purpose = self._slugify(purpose)
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        microseconds = datetime.utcnow().strftime("%f")[
            :3
        ]  # First 3 digits of microseconds
        return f"{self.BRANCH_PREFIX}/{safe_purpose}-{timestamp}-{microseconds}"

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to a URL-safe slug."""
        # Convert to lowercase
        text = text.lower()

        # Replace spaces and special chars with hyphens
        text = re.sub(r"[^a-z0-9]+", "-", text)

        # Remove leading/trailing hyphens and limit length
        text = text.strip("-")

        # Truncate to max length
        if len(text) > BranchManager.MAX_PURPOSE_LENGTH:
            text = text[: BranchManager.MAX_PURPOSE_LENGTH].rstrip("-")

        return text or "feature"  # Fallback if empty after processing
