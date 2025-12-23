"""
Commit Composer for NAVI Phase 3.5.2

Responsibility:
- Stage applied files
- Generate commit message from ChangePlan
- Create a single clean commit

Order:
- Runs AFTER BranchManager
- Runs BEFORE PR creation
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Iterable, List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class CommitCreationError(RuntimeError):
    """Raised when commit creation fails"""
    pass


@dataclass(frozen=True)
class CommitInfo:
    """Commit information result"""
    sha: str
    message: str
    files: List[str]


@dataclass(frozen=True)
class CommitResult:
    """Complete commit creation result for UI emission"""
    success: bool
    sha: str
    message: str
    files: List[str]
    staged_files_count: int
    error: Optional[str] = None


class CommitComposer:
    """
    Handles commit creation for NAVI PR workflows.
    
    This is production-grade code with selective staging,
    deterministic message generation, and clean error handling.
    """

    def __init__(self, repo_root: str) -> None:
        """
        Initialize CommitComposer for a repository.
        
        Args:
            repo_root: Absolute path to git repository root
        """
        self.repo_root = os.path.abspath(repo_root)
        self._validate_git_repo()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_pr_commit(
        self,
        *,
        files: Iterable[str],
        change_plan: Dict[str, Any],
        author_email: Optional[str] = None,
        author_name: Optional[str] = None,
    ) -> CommitResult:
        """
        Stage files and create a commit for PR generation.
        
        This is the main entry point for Phase 3.5.2.
        
        Args:
            files: Iterable of file paths to stage
            change_plan: Structured ChangePlan used to generate message
            author_email: Optional commit author email
            author_name: Optional commit author name
            
        Returns:
            CommitResult with success status and commit info
        """
        try:
            files_list = list(files)
            logger.info(f"[COMMIT_COMPOSER] Creating commit for {len(files_list)} files")
            
            if not files_list:
                return CommitResult(
                    success=False,
                    sha="",
                    message="",
                    files=[],
                    staged_files_count=0,
                    error="No files provided for commit"
                )
            
            # Filter to only existing files that have changes
            valid_files = self._filter_valid_files(files_list)
            if not valid_files:
                return CommitResult(
                    success=False,
                    sha="",
                    message="",
                    files=files_list,
                    staged_files_count=0,
                    error="No valid files with changes found"
                )
            
            logger.info(f"[COMMIT_COMPOSER] Staging {len(valid_files)} valid files")
            
            # Stage the files
            self._stage_files(valid_files)
            
            # Generate commit message from change plan
            message = self._generate_commit_message(change_plan)
            logger.info(f"[COMMIT_COMPOSER] Generated commit message: {message[:50]}...")
            
            # Create the commit
            sha = self._commit(message, author_email, author_name)
            
            logger.info(f"[COMMIT_COMPOSER] Successfully created commit: {sha[:8]}")
            
            return CommitResult(
                success=True,
                sha=sha,
                message=message,
                files=valid_files,
                staged_files_count=len(valid_files)
            )
            
        except Exception as e:
            logger.error(f"[COMMIT_COMPOSER] Commit creation failed: {str(e)}")
            return CommitResult(
                success=False,
                sha="",
                message="",
                files=list(files) if files else [],
                staged_files_count=0,
                error=str(e)
            )

    def create_commit(
        self,
        *,
        files: Iterable[str],
        change_plan: dict,
    ) -> CommitInfo:
        """
        Stage files and create a commit.
        
        Legacy API - use create_pr_commit for new code.

        Args:
            files: iterable of file paths to stage
            change_plan: structured ChangePlan used to generate message
            
        Returns:
            CommitInfo with commit details
            
        Raises:
            CommitCreationError on failure
        """
        files_list = list(files)
        if not files_list:
            raise CommitCreationError("No files provided for commit")

        self._stage_files(files_list)
        message = self._generate_commit_message(change_plan)
        sha = self._commit(message)

        return CommitInfo(
            sha=sha,
            message=message,
            files=files_list,
        )

    def get_staged_files(self) -> List[str]:
        """Get list of currently staged files."""
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=self.repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            logger.error(f"[COMMIT_COMPOSER] Failed to get staged files: {result.stderr.strip()}")
            return []

        return [f.strip() for f in result.stdout.split('\n') if f.strip()]

    def has_staged_changes(self) -> bool:
        """Check if there are any staged changes."""
        return len(self.get_staged_files()) > 0

    # ------------------------------------------------------------------
    # Validation and filtering
    # ------------------------------------------------------------------

    def _validate_git_repo(self) -> None:
        """Ensure the repo_root is a valid git repository."""
        git_dir = os.path.join(self.repo_root, '.git')
        if not os.path.exists(git_dir):
            raise CommitCreationError(
                f"Not a git repository: {self.repo_root}"
            )

    def _filter_valid_files(self, files: List[str]) -> List[str]:
        """Filter to only existing files that have changes."""
        valid_files = []
        
        for file_path in files:
            # Convert to absolute path if relative
            if not os.path.isabs(file_path):
                abs_path = os.path.join(self.repo_root, file_path)
            else:
                abs_path = file_path
            
            # Check if file exists
            if not os.path.exists(abs_path):
                logger.warning(f"[COMMIT_COMPOSER] File does not exist: {file_path}")
                continue
            
            # Convert back to relative path for git operations
            try:
                rel_path = os.path.relpath(abs_path, self.repo_root)
                
                # Check if file has changes (either modified or new)
                if self._file_has_changes(rel_path):
                    valid_files.append(rel_path)
                else:
                    logger.debug(f"[COMMIT_COMPOSER] No changes in file: {rel_path}")
            except ValueError:
                logger.warning(f"[COMMIT_COMPOSER] File outside repository: {file_path}")
                continue
        
        return valid_files

    def _file_has_changes(self, file_path: str) -> bool:
        """Check if a file has unstaged or staged changes."""
        # Check for unstaged changes
        result = subprocess.run(
            ["git", "diff", "--name-only", file_path],
            cwd=self.repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        
        if result.stdout.strip():
            return True
        
        # Check for staged changes
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", file_path],
            cwd=self.repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        
        if result.stdout.strip():
            return True
        
        # Check if file is untracked
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", file_path],
            cwd=self.repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        
        return bool(result.stdout.strip())

    # ------------------------------------------------------------------
    # Git operations
    # ------------------------------------------------------------------

    def _stage_files(self, files: List[str]) -> None:
        """Stage specified files."""
        result = subprocess.run(
            ["git", "add", "--"] + files,
            cwd=self.repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            raise CommitCreationError(
                f"Failed to stage files: {result.stderr.strip()}"
            )
        
        logger.debug(f"[COMMIT_COMPOSER] Successfully staged {len(files)} files")

    def _commit(
        self, 
        message: str, 
        author_email: Optional[str] = None, 
        author_name: Optional[str] = None
    ) -> str:
        """Create a commit with the given message."""
        cmd = ["git", "commit", "-m", message]
        
        # Set author if provided
        env = os.environ.copy()
        if author_email:
            env["GIT_AUTHOR_EMAIL"] = author_email
            env["GIT_COMMITTER_EMAIL"] = author_email
        if author_name:
            env["GIT_AUTHOR_NAME"] = author_name
            env["GIT_COMMITTER_NAME"] = author_name
        
        result = subprocess.run(
            cmd,
            cwd=self.repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        if result.returncode != 0:
            raise CommitCreationError(
                f"git commit failed: {result.stderr.strip()}"
            )

        # Extract SHA
        sha_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if sha_result.returncode != 0:
            raise CommitCreationError("Unable to resolve commit SHA")

        return sha_result.stdout.strip()

    # ------------------------------------------------------------------
    # Message generation
    # ------------------------------------------------------------------

    def _generate_commit_message(self, change_plan: Dict[str, Any]) -> str:
        """
        Generate a clean, human-reviewable commit message.
        
        Format:
        - First line: Goal/title (max 72 chars)
        - Empty line
        - Strategy/description (if provided)
        """
        title = change_plan.get("goal", "Apply automated changes")
        strategy = change_plan.get("strategy")
        
        # Truncate title to 72 characters for good Git practice
        title = self._truncate(title, 72)
        
        lines = [title]

        if strategy:
            lines.append("")  # Empty line after title
            
            # Wrap strategy text to reasonable line length
            strategy_lines = self._wrap_text(strategy, 72)
            lines.extend(strategy_lines)
        
        # Add NAVI signature for tracking
        lines.append("")
        lines.append("Generated by NAVI autonomous PR system")

        return "\n".join(lines)

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        """Truncate text to specified limit with ellipsis."""
        if len(text) <= limit:
            return text
        return text[:limit - 3] + "..."

    @staticmethod 
    def _wrap_text(text: str, width: int) -> List[str]:
        """Wrap text to specified width, preserving word boundaries."""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) + len(current_line) > width:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                    current_length = len(word)
                else:
                    # Single word longer than width
                    lines.append(word)
                    current_length = 0
            else:
                current_line.append(word)
                current_length += len(word)
        
        if current_line:
            lines.append(" ".join(current_line))
        
        return lines