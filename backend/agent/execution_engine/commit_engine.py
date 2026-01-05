"""
Commit Engine - Phase 4.4

Handles intelligent git operations for NAVI's autonomous workflow.
This engine knows how to create clean commits like a Staff Engineer.
"""

import os
import subprocess
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)


@dataclass
class CommitInfo:
    """Information about a commit"""

    message: str
    files_changed: List[str]
    branch: str
    sha: Optional[str] = None
    timestamp: Optional[float] = None


@dataclass
class BranchInfo:
    """Information about a git branch"""

    name: str
    base_branch: str
    exists: bool = False
    current: bool = False


class CommitEngine:
    """
    Intelligent git operations for NAVI's autonomous workflow.

    This engine follows Staff Engineer commit practices:
    - Clean, descriptive commit messages
    - Proper branch naming conventions
    - Safe git operations with validation
    """

    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self.current_branch = None

    async def create_branch(
        self, branch_name: str, base_branch: str = "main"
    ) -> BranchInfo:
        """
        Create a new git branch for NAVI's work.

        Args:
            branch_name: Name for the new branch (NAVI will use intelligent naming)
            base_branch: Branch to branch from (default: main)

        Returns:
            BranchInfo with creation details
        """
        logger.info(f"Creating branch '{branch_name}' from '{base_branch}'")

        try:
            # Check if branch already exists
            result = await self._run_git_command(["branch", "--list", branch_name])
            branch_exists = branch_name in result.stdout

            if branch_exists:
                logger.warning(f"Branch '{branch_name}' already exists")
                return BranchInfo(
                    name=branch_name, base_branch=base_branch, exists=True
                )

            # Ensure we're on the base branch
            await self._run_git_command(["checkout", base_branch])

            # Try to pull latest changes (optional for local repos)
            try:
                await self._run_git_command(["pull", "origin", base_branch])
            except Exception as e:
                logger.warning(f"Could not pull from origin (local repo?): {e}")
                # Continue anyway - this is fine for local-only repos

            # Create and checkout new branch
            await self._run_git_command(["checkout", "-b", branch_name])

            self.current_branch = branch_name

            logger.info(f"Successfully created branch '{branch_name}'")

            return BranchInfo(
                name=branch_name, base_branch=base_branch, exists=False, current=True
            )

        except Exception as e:
            logger.error(f"Failed to create branch '{branch_name}': {e}")
            raise

    async def commit_changes(
        self, files: List[str], message: str, description: Optional[str] = None
    ) -> CommitInfo:
        """
        Create a clean, Staff Engineer-quality commit.

        Args:
            files: List of files to commit
            message: Short commit message (50 chars or less)
            description: Optional detailed description

        Returns:
            CommitInfo with commit details
        """
        logger.info(f"Committing {len(files)} files: {message}")

        try:
            # Validate files exist
            valid_files = []
            for file_path in files:
                full_path = os.path.join(self.workspace_root, file_path)
                if os.path.exists(full_path):
                    valid_files.append(file_path)
                else:
                    logger.warning(f"File not found for commit: {file_path}")

            if not valid_files:
                raise ValueError("No valid files to commit")

            # Add files to staging
            for file_path in valid_files:
                await self._run_git_command(["add", file_path])

            # Build commit message (Staff Engineer style)
            full_message = self._build_commit_message(message, description, valid_files)

            # Commit changes
            await self._run_git_command(["commit", "-m", full_message])

            # Get commit SHA
            sha_result = await self._run_git_command(["rev-parse", "HEAD"])
            sha = sha_result.stdout.strip()[:8]  # Short SHA

            current_branch = await self._get_current_branch()

            commit_info = CommitInfo(
                message=full_message,
                files_changed=valid_files,
                branch=current_branch,
                sha=sha,
                timestamp=time.time(),
            )

            logger.info(f"Successfully committed {len(valid_files)} files as {sha}")

            return commit_info

        except Exception as e:
            logger.error(f"Failed to commit changes: {e}")
            raise

    async def push_branch(self, branch_name: Optional[str] = None) -> bool:
        """
        Push branch to remote origin.

        Args:
            branch_name: Branch to push (defaults to current branch)

        Returns:
            True if successful
        """
        target_branch = branch_name or await self._get_current_branch()

        logger.info(f"Pushing branch '{target_branch}' to origin")

        try:
            # Push branch to origin
            await self._run_git_command(["push", "-u", "origin", target_branch])

            logger.info(f"Successfully pushed branch '{target_branch}'")
            return True

        except Exception as e:
            logger.error(f"Failed to push branch '{target_branch}': {e}")
            return False

    async def get_branch_status(self) -> Dict[str, Any]:
        """
        Get current git status and branch information.

        Returns:
            Dictionary with branch status details
        """
        try:
            current_branch = await self._get_current_branch()

            # Check for uncommitted changes
            status_result = await self._run_git_command(["status", "--porcelain"])
            has_changes = bool(status_result.stdout.strip())

            # Get ahead/behind info
            try:
                ahead_behind = await self._run_git_command(
                    [
                        "rev-list",
                        "--left-right",
                        "--count",
                        f"origin/{current_branch}...HEAD",
                    ]
                )
                behind, ahead = ahead_behind.stdout.strip().split("\t")
            except Exception:
                ahead, behind = "0", "0"

            return {
                "current_branch": current_branch,
                "has_uncommitted_changes": has_changes,
                "commits_ahead": int(ahead),
                "commits_behind": int(behind),
                "workspace_clean": not has_changes,
            }

        except Exception as e:
            logger.error(f"Failed to get branch status: {e}")
            return {
                "current_branch": "unknown",
                "has_uncommitted_changes": True,
                "commits_ahead": 0,
                "commits_behind": 0,
                "workspace_clean": False,
            }

    def generate_branch_name(self, context: Dict[str, Any]) -> str:
        """
        Generate intelligent branch names based on context.

        Args:
            context: Context containing fix information

        Returns:
            Clean, descriptive branch name
        """
        # Get issue types and counts
        issues = context.get("issues", [])
        file_count = len(context.get("files_affected", []))

        # Categorize issues
        issue_types = set()
        for issue in issues:
            category = getattr(issue, "category", "unknown")
            if category in ["UndefinedVariable", "ReferenceError"]:
                issue_types.add("undefined-vars")
            elif category in ["ImportError", "ModuleNotFound"]:
                issue_types.add("imports")
            elif category in ["SyntaxError", "ParseError"]:
                issue_types.add("syntax")
            elif category in ["TypeError"]:
                issue_types.add("types")
            else:
                issue_types.add("fix")

        # Build branch name
        if len(issue_types) == 1:
            issue_type = list(issue_types)[0]
        elif "syntax" in issue_types:
            issue_type = "syntax-fixes"
        elif len(issue_types) <= 2:
            issue_type = "-".join(sorted(issue_types))
        else:
            issue_type = "multi-fix"

        # Add file context if focused
        if file_count <= 3:
            branch_name = f"navi/{issue_type}"
        else:
            branch_name = f"navi/{issue_type}-{file_count}files"

        # Add timestamp for uniqueness
        timestamp = int(time.time()) % 10000  # Last 4 digits
        branch_name += f"-{timestamp}"

        return branch_name

    def _build_commit_message(
        self, summary: str, description: Optional[str], files: List[str]
    ) -> str:
        """Build a Staff Engineer-quality commit message."""

        # Ensure summary is concise (50 chars recommended)
        if len(summary) > 50:
            summary = summary[:47] + "..."

        # Start with conventional commit prefix if not present
        if not any(
            summary.startswith(prefix)
            for prefix in ["fix:", "feat:", "docs:", "style:", "refactor:", "test:"]
        ):
            summary = f"fix: {summary}"

        lines = [summary]

        if description:
            lines.append("")  # Empty line
            lines.append(description)

        # Add file summary for context
        if len(files) <= 5:
            lines.append("")
            lines.append("Files changed:")
            for file_path in files:
                lines.append(f"- {file_path}")
        else:
            lines.append("")
            lines.append(f"Modified {len(files)} files")

        # Add NAVI signature
        lines.append("")
        lines.append("Generated by NAVI Autonomous Engineering")

        return "\n".join(lines)

    async def _run_git_command(self, args: List[str]) -> subprocess.CompletedProcess:
        """Run git command safely in workspace directory."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=True,
            )
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Git command failed: git {' '.join(args)}")
            logger.error(f"Error output: {e.stderr}")
            raise

    async def _get_current_branch(self) -> str:
        """Get the current git branch name."""
        try:
            result = await self._run_git_command(["branch", "--show-current"])
            return result.stdout.strip()
        except Exception:
            return "unknown"
