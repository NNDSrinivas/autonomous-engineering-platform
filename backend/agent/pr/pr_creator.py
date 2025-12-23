"""
PR Creator for NAVI Phase 3.5.3

Responsibility:
- Create Pull Requests using git provider APIs
- Generate structured PR metadata from ChangePlan
- Return UI-ready PR info

Currently supports:
- GitHub (via REST API)
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:
    logger.warning("requests library not available - PR creation will be disabled")
    requests = None


class PRCreationError(RuntimeError):
    """Raised when PR creation fails"""
    pass


@dataclass(frozen=True)
class PRInfo:
    """PR information result"""
    number: int
    title: str
    body: str
    url: str
    base: str
    head: str


@dataclass(frozen=True)
class PRResult:
    """Complete PR creation result for UI emission"""
    success: bool
    pr_number: Optional[int]
    pr_title: str
    pr_url: str
    pr_body: str
    base_branch: str
    head_branch: str
    provider: str
    error: Optional[str] = None


class PRCreator:
    """
    Creates Pull Requests for NAVI workflows.
    
    This is production-grade code with GitHub API integration,
    structured metadata generation, and clean error handling.
    """

    def __init__(
        self,
        *,
        repo_root: str,
        github_token: Optional[str] = None,
    ) -> None:
        """
        Initialize PRCreator for a repository.
        
        Args:
            repo_root: Absolute path to git repository root
            github_token: GitHub API token (falls back to GITHUB_TOKEN env var)
        """
        self.repo_root = os.path.abspath(repo_root)
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        
        self._validate_dependencies()
        
        if self.github_token:
            try:
                self.repo_owner, self.repo_name = self._detect_github_repo()
                self.provider = "github"
                logger.info(f"[PR_CREATOR] Initialized for {self.repo_owner}/{self.repo_name}")
            except Exception as e:
                logger.warning(f"[PR_CREATOR] GitHub repo detection failed: {e}")
                self.repo_owner = None
                self.repo_name = None
                self.provider = "unknown"
        else:
            logger.warning("[PR_CREATOR] No GitHub token provided")
            self.repo_owner = None
            self.repo_name = None
            self.provider = "unknown"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_navi_pr(
        self,
        *,
        branch: str,
        base: str,
        change_plan: Dict[str, Any],
        commit_message: str,
        commit_sha: Optional[str] = None,
    ) -> PRResult:
        """
        Create a PR for NAVI autonomous changes.
        
        This is the main entry point for Phase 3.5.3.
        
        Args:
            branch: Head branch name
            base: Base branch name
            change_plan: Structured ChangePlan used to generate PR content
            commit_message: Full commit message
            commit_sha: Optional commit SHA for reference
            
        Returns:
            PRResult with success status and PR info
        """
        try:
            logger.info(f"[PR_CREATOR] Creating PR: {branch} -> {base}")
            
            if not self._can_create_pr():
                return PRResult(
                    success=False,
                    pr_number=None,
                    pr_title="",
                    pr_url="",
                    pr_body="",
                    base_branch=base,
                    head_branch=branch,
                    provider=self.provider,
                    error="PR creation not available - missing GitHub token or invalid repository"
                )
            
            # Generate PR metadata
            title = self._generate_title(change_plan)
            body = self._generate_body(change_plan, commit_message, commit_sha)
            
            logger.info(f"[PR_CREATOR] Generated PR title: {title[:50]}...")
            
            # Create the PR via GitHub API
            pr_data = self._github_create_pr(
                title=title,
                body=body,
                head=branch,
                base=base,
            )
            
            logger.info(f"[PR_CREATOR] Successfully created PR #{pr_data['number']}")
            
            return PRResult(
                success=True,
                pr_number=pr_data["number"],
                pr_title=pr_data["title"],
                pr_url=pr_data["html_url"],
                pr_body=pr_data["body"],
                base_branch=base,
                head_branch=branch,
                provider="github"
            )
            
        except Exception as e:
            logger.error(f"[PR_CREATOR] PR creation failed: {str(e)}")
            return PRResult(
                success=False,
                pr_number=None,
                pr_title=self._generate_title(change_plan) if change_plan else "",
                pr_url="",
                pr_body="",
                base_branch=base,
                head_branch=branch,
                provider=self.provider,
                error=str(e)
            )

    def create_pr(
        self,
        *,
        branch: str,
        base: str,
        change_plan: dict,
        commit_message: str,
    ) -> PRInfo:
        """
        Create a Pull Request.
        
        Legacy API - use create_navi_pr for new code.

        Args:
            branch: Head branch name
            base: Base branch name
            change_plan: Structured ChangePlan
            commit_message: Full commit message
            
        Returns:
            PRInfo with PR details
            
        Raises:
            PRCreationError on failure
        """
        if not self.github_token:
            raise PRCreationError("GITHUB_TOKEN not configured")

        if not self.repo_owner or not self.repo_name:
            raise PRCreationError("GitHub repository not detected")

        title = self._generate_title(change_plan)
        body = self._generate_body(change_plan, commit_message)

        response = self._github_create_pr(
            title=title,
            body=body,
            head=branch,
            base=base,
        )

        return PRInfo(
            number=response["number"],
            title=response["title"],
            body=response["body"],
            url=response["html_url"],
            base=base,
            head=branch,
        )

    def get_pr_info(self, pr_number: int) -> Optional[Dict[str, Any]]:
        """Get information about an existing PR."""
        if not self._can_create_pr():
            return None
            
        try:
            url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/pulls/{pr_number}"
            headers = {
                "Authorization": f"token {self.github_token}",
                "Accept": "application/vnd.github+json",
            }
            
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.error(f"[PR_CREATOR] Failed to get PR info: {resp.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"[PR_CREATOR] Error getting PR info: {e}")
            return None

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_dependencies(self) -> None:
        """Validate required dependencies."""
        if requests is None:
            logger.warning("[PR_CREATOR] requests library not available")

    def _can_create_pr(self) -> bool:
        """Check if PR creation is possible."""
        return (
            requests is not None and
            self.github_token is not None and
            self.repo_owner is not None and
            self.repo_name is not None
        )

    # ------------------------------------------------------------------
    # GitHub API
    # ------------------------------------------------------------------

    def _github_create_pr(
        self,
        *,
        title: str,
        body: str,
        head: str,
        base: str,
    ) -> dict:
        """Create a PR via GitHub API."""
        if requests is None:
            raise PRCreationError("requests library not available")

        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/pulls"

        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "NAVI-Autonomous-PR-System/1.0"
        }

        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
        except requests.exceptions.Timeout:
            raise PRCreationError("GitHub API request timed out")
        except requests.exceptions.RequestException as e:
            raise PRCreationError(f"GitHub API request failed: {e}")

        if resp.status_code not in (200, 201):
            error_msg = f"GitHub PR creation failed ({resp.status_code})"
            try:
                error_data = resp.json()
                if "message" in error_data:
                    error_msg += f": {error_data['message']}"
            except:
                error_msg += f": {resp.text[:200]}"
                
            raise PRCreationError(error_msg)

        return resp.json()

    # ------------------------------------------------------------------
    # Repository detection
    # ------------------------------------------------------------------

    def _detect_github_repo(self) -> tuple[str, str]:
        """
        Detect GitHub owner/repo from git remote.
        
        Returns:
            Tuple of (owner, repo_name)
        """
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=self.repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            raise PRCreationError("Unable to detect git remote")

        remote = result.stdout.strip()
        logger.debug(f"[PR_CREATOR] Detected git remote: {remote}")

        # Supports:
        # - git@github.com:owner/repo.git
        # - https://github.com/owner/repo.git
        # - https://github.com/owner/repo
        match = re.search(r"github\.com[:/](.+?)/(.+?)(\.git)?/?$", remote)
        if not match:
            raise PRCreationError(f"Not a GitHub repository: {remote}")

        owner = match.group(1)
        repo = match.group(2)
        
        # Clean up repo name
        if repo.endswith('.git'):
            repo = repo[:-4]

        return owner, repo

    # ------------------------------------------------------------------
    # Content generation
    # ------------------------------------------------------------------

    def _generate_title(self, change_plan: Dict[str, Any]) -> str:
        """Generate PR title from change plan."""
        title = change_plan.get("goal", "Automated changes by NAVI")
        
        # Ensure title isn't too long (GitHub limit is ~256 chars)
        if len(title) > 72:
            title = title[:69] + "..."
            
        return title

    def _generate_body(
        self, 
        change_plan: Dict[str, Any], 
        commit_message: str, 
        commit_sha: Optional[str] = None
    ) -> str:
        """Generate PR body from change plan and commit info."""
        lines = []

        # Add strategy section if available
        strategy = change_plan.get("strategy")
        if strategy:
            lines.append("## 🎯 Strategy")
            lines.append("")
            lines.append(strategy)
            lines.append("")

        # Add changed files section
        files = change_plan.get("files", [])
        if files:
            lines.append("## 📝 Changes")
            lines.append("")
            for f in files:
                file_path = f.get('path', 'unknown')
                intent = f.get('intent', 'modified')
                rationale = f.get('rationale', '')
                
                if rationale:
                    lines.append(f"- `{file_path}` ({intent}) - {rationale}")
                else:
                    lines.append(f"- `{file_path}` ({intent})")
            lines.append("")

        # Add commit information
        lines.append("## 💻 Commit Details")
        lines.append("")
        if commit_sha:
            lines.append(f"**Commit SHA:** `{commit_sha[:8]}`")
            lines.append("")
        lines.append("**Commit Message:**")
        lines.append("```")
        lines.append(commit_message.strip())
        lines.append("```")
        lines.append("")

        # Add risk level if available
        risk_level = change_plan.get("riskLevel")
        if risk_level:
            lines.append(f"**Risk Level:** {risk_level}")
            lines.append("")

        # Add tests required notice if applicable
        tests_required = change_plan.get("testsRequired", False)
        if tests_required:
            lines.append("⚠️ **Tests Required:** This change may require additional testing.")
            lines.append("")

        # Add footer
        lines.append("---")
        lines.append("")
        lines.append("🤖 _Generated automatically by [NAVI](https://github.com/navi-ai/navi) autonomous PR system_")

        return "\n".join(lines)