"""
PR Lifecycle Engine for NAVI Phase 3.5.4

Responsibility:
- Monitor CI status for PRs
- Emit lifecycle updates
- Detect terminal states
- Stream real-time status to UI

Supports:
- GitHub Checks API
- Continuous polling with state change detection
- Event emission for UI updates
- Terminal state detection (success/failure/cancelled)

Flow:
1. Initialize with PR details and GitHub token
2. Start monitoring loop with emit_event callback
3. Poll GitHub Checks API for CI status
4. Emit events on state changes
5. Return on terminal states
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, Callable, Awaitable
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


class PRLifecycleError(RuntimeError):
    """Raised when PR lifecycle operations fail."""
    pass


@dataclass(frozen=True)
class PRStatus:
    """Normalized CI status for a PR."""
    state: str                      # pending | success | failure | cancelled
    conclusion: Optional[str]       # success | failure | cancelled | None
    url: Optional[str]              # URL to CI results
    check_count: int = 0           # Number of checks
    failed_checks: int = 0         # Number of failed checks
    last_updated: Optional[str] = None  # ISO timestamp
    details: Optional[Dict[str, Any]] = None  # Raw check data

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass(frozen=True)
class PRLifecycleResult:
    """Result of PR lifecycle monitoring."""
    pr_number: int
    final_status: PRStatus
    monitoring_duration: float      # seconds
    events_emitted: int
    terminal_reason: str           # success | failure | cancelled | timeout


class PRLifecycleEngine:
    """
    Monitors CI lifecycle of a Pull Request.
    
    Provides:
    - Continuous CI status polling
    - State change detection
    - Event emission for UI updates
    - Terminal state detection
    - Comprehensive error handling
    """

    POLL_INTERVAL_SECONDS = 10
    TERMINAL_STATES = {"success", "failure", "cancelled"}
    MAX_MONITORING_DURATION = 3600  # 1 hour
    REQUEST_TIMEOUT = 30  # seconds

    def __init__(
        self,
        *,
        repo_owner: str,
        repo_name: str,
        pr_number: int,
        github_token: Optional[str] = None,
        workspace_root: Optional[str] = None
    ) -> None:
        """
        Initialize PR lifecycle monitoring.
        
        Args:
            repo_owner: GitHub repository owner
            repo_name: GitHub repository name
            pr_number: PR number to monitor
            github_token: GitHub API token (or from GITHUB_TOKEN env var)
            workspace_root: Optional workspace root for git operations
        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.pr_number = pr_number
        self.workspace_root = workspace_root
        
        # GitHub API configuration
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        if not self.github_token:
            raise PRLifecycleError("GitHub token required - set GITHUB_TOKEN environment variable")
        
        self.headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "NAVI-PRLifecycleEngine/1.0"
        }
        
        # Monitoring state
        self.start_time: Optional[datetime] = None
        self.events_emitted = 0
        self.last_status: Optional[PRStatus] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def monitor_sync(self, emit_event: Callable[[str, Dict[str, Any]], None]) -> PRLifecycleResult:
        """
        Synchronously monitor PR CI status and emit updates.
        
        Args:
            emit_event: Callback for emitting events (event_type, payload)
            
        Returns:
            PRLifecycleResult with final status and monitoring details
        """
        logger.info(f"[PR{self.pr_number}] Starting CI lifecycle monitoring")
        
        self.start_time = datetime.now()
        self.events_emitted = 0
        last_state: Optional[str] = None
        
        try:
            while True:
                # Check monitoring timeout
                if self._is_monitoring_timeout():
                    logger.warning(f"[PR{self.pr_number}] Monitoring timeout reached")
                    emit_event("navi.pr.timeout", {
                        "prNumber": self.pr_number,
                        "reason": "monitoring_timeout",
                        "duration": self._get_monitoring_duration()
                    })
                    return self._create_result("timeout", self.last_status or 
                                             PRStatus(state="pending", conclusion=None, url=None))
                
                # Fetch current status
                try:
                    status = self._fetch_ci_status()
                    self.last_status = status
                except Exception as e:
                    logger.error(f"[PR{self.pr_number}] Failed to fetch CI status: {e}")
                    time.sleep(self.POLL_INTERVAL_SECONDS)
                    continue
                
                # Emit update if state changed
                if status.state != last_state:
                    self._emit_status_update(emit_event, status)
                    last_state = status.state
                
                # Check for terminal state
                if status.state in self.TERMINAL_STATES:
                    self._emit_completion(emit_event, status)
                    logger.info(f"[PR{self.pr_number}] Terminal state reached: {status.state}")
                    return self._create_result(status.state, status)
                
                # Wait before next poll
                time.sleep(self.POLL_INTERVAL_SECONDS)
                
        except KeyboardInterrupt:
            logger.info(f"[PR{self.pr_number}] Monitoring interrupted by user")
            emit_event("navi.pr.interrupted", {
                "prNumber": self.pr_number,
                "reason": "user_interrupt"
            })
            return self._create_result("interrupted", self.last_status or 
                                     PRStatus(state="pending", conclusion=None, url=None))
        except Exception as e:
            logger.exception(f"[PR{self.pr_number}] Monitoring failed")
            emit_event("navi.pr.error", {
                "prNumber": self.pr_number,
                "error": str(e)
            })
            return self._create_result("error", self.last_status or 
                                     PRStatus(state="pending", conclusion=None, url=None))

    async def monitor_async(self, emit_event: Callable[[str, Dict[str, Any]], Awaitable[None]]) -> PRLifecycleResult:
        """
        Asynchronously monitor PR CI status and emit updates.
        
        Args:
            emit_event: Async callback for emitting events (event_type, payload)
            
        Returns:
            PRLifecycleResult with final status and monitoring details
        """
        logger.info(f"[PR{self.pr_number}] Starting async CI lifecycle monitoring")
        
        self.start_time = datetime.now()
        self.events_emitted = 0
        last_state: Optional[str] = None
        
        try:
            while True:
                # Check monitoring timeout
                if self._is_monitoring_timeout():
                    logger.warning(f"[PR{self.pr_number}] Monitoring timeout reached")
                    await emit_event("navi.pr.timeout", {
                        "prNumber": self.pr_number,
                        "reason": "monitoring_timeout",
                        "duration": self._get_monitoring_duration()
                    })
                    return self._create_result("timeout", self.last_status or 
                                             PRStatus(state="pending", conclusion=None, url=None))
                
                # Fetch current status
                try:
                    status = self._fetch_ci_status()
                    self.last_status = status
                except Exception as e:
                    logger.error(f"[PR{self.pr_number}] Failed to fetch CI status: {e}")
                    await asyncio.sleep(self.POLL_INTERVAL_SECONDS)
                    continue
                
                # Emit update if state changed
                if status.state != last_state:
                    await self._emit_status_update_async(emit_event, status)
                    last_state = status.state
                
                # Check for terminal state
                if status.state in self.TERMINAL_STATES:
                    await self._emit_completion_async(emit_event, status)
                    logger.info(f"[PR{self.pr_number}] Terminal state reached: {status.state}")
                    return self._create_result(status.state, status)
                
                # Wait before next poll
                await asyncio.sleep(self.POLL_INTERVAL_SECONDS)
                
        except asyncio.CancelledError:
            logger.info(f"[PR{self.pr_number}] Monitoring cancelled")
            await emit_event("navi.pr.cancelled", {
                "prNumber": self.pr_number,
                "reason": "monitoring_cancelled"
            })
            return self._create_result("cancelled", self.last_status or 
                                     PRStatus(state="pending", conclusion=None, url=None))
        except Exception as e:
            logger.exception(f"[PR{self.pr_number}] Async monitoring failed")
            await emit_event("navi.pr.error", {
                "prNumber": self.pr_number,
                "error": str(e)
            })
            return self._create_result("error", self.last_status or 
                                     PRStatus(state="pending", conclusion=None, url=None))

    def get_current_status(self) -> PRStatus:
        """
        Get current CI status without monitoring.
        
        Returns:
            Current PRStatus
        """
        return self._fetch_ci_status()

    # ------------------------------------------------------------------
    # GitHub API Integration
    # ------------------------------------------------------------------

    def _fetch_ci_status(self) -> PRStatus:
        """
        Fetch combined CI status via GitHub Checks API.
        
        Returns:
            PRStatus with normalized CI state
        """
        try:
            # Get PR to resolve HEAD SHA
            pr_info = self._fetch_pr_info()
            sha = pr_info["head"]["sha"]
            pr_url = pr_info["html_url"]
            
            # Fetch check runs for the commit
            check_runs = self._fetch_check_runs(sha)
            
            if not check_runs:
                return PRStatus(
                    state="pending",
                    conclusion=None,
                    url=pr_url,
                    check_count=0,
                    failed_checks=0,
                    last_updated=datetime.now().isoformat(),
                    details={"message": "No CI checks found"}
                )
            
            # Aggregate check results
            return self._aggregate_check_results(check_runs, pr_url)
            
        except Exception as e:
            logger.error(f"[PR{self.pr_number}] CI status fetch failed: {e}")
            raise PRLifecycleError(f"Failed to fetch CI status: {e}")

    def _fetch_pr_info(self) -> Dict[str, Any]:
        """Fetch PR information from GitHub API."""
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/pulls/{self.pr_number}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=self.REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise PRLifecycleError(f"Failed to fetch PR info: {e}")

    def _fetch_check_runs(self, sha: str) -> list:
        """Fetch check runs for a commit SHA."""
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/commits/{sha}/check-runs"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=self.REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json().get("check_runs", [])
        except requests.exceptions.RequestException as e:
            raise PRLifecycleError(f"Failed to fetch check runs: {e}")

    def _aggregate_check_results(self, check_runs: list, pr_url: str) -> PRStatus:
        """
        Aggregate multiple check runs into a single status.
        
        Args:
            check_runs: List of GitHub check run objects
            pr_url: PR URL for fallback
            
        Returns:
            Aggregated PRStatus
        """
        if not check_runs:
            return PRStatus(state="pending", conclusion=None, url=pr_url)
        
        # Extract statuses and conclusions
        statuses = [run.get("status") for run in check_runs]
        conclusions = [run.get("conclusion") for run in check_runs]
        
        # Count checks and failures
        total_checks = len(check_runs)
        failed_checks = sum(1 for c in conclusions if c in ["failure", "timed_out", "action_required"])
        
        # Get the most relevant URL (failed check or first check)
        check_url = pr_url
        for run in check_runs:
            if run.get("conclusion") in ["failure", "timed_out"]:
                check_url = run.get("html_url", pr_url)
                break
        else:
            check_url = check_runs[0].get("html_url", pr_url)
        
        # Determine overall state
        if "in_progress" in statuses or "queued" in statuses:
            state = "pending"
            conclusion = None
        elif "failure" in conclusions or "timed_out" in conclusions or "action_required" in conclusions:
            state = "failure"
            conclusion = "failure"
        elif "cancelled" in conclusions:
            state = "cancelled"
            conclusion = "cancelled"
        elif all(c == "success" for c in conclusions if c is not None):
            state = "success"
            conclusion = "success"
        else:
            state = "pending"
            conclusion = None
        
        return PRStatus(
            state=state,
            conclusion=conclusion,
            url=check_url,
            check_count=total_checks,
            failed_checks=failed_checks,
            last_updated=datetime.now().isoformat(),
            details={
                "check_runs": len(check_runs),
                "statuses": statuses,
                "conclusions": conclusions
            }
        )

    # ------------------------------------------------------------------
    # Event Emission Helpers
    # ------------------------------------------------------------------

    def _emit_status_update(self, emit_event: Callable, status: PRStatus) -> None:
        """Emit status update event (sync)."""
        payload = {
            "prNumber": self.pr_number,
            "state": status.state,
            "conclusion": status.conclusion,
            "url": status.url,
            "checkCount": status.check_count,
            "failedChecks": status.failed_checks,
            "lastUpdated": status.last_updated
        }
        
        emit_event("navi.pr.ci.updated", payload)
        self.events_emitted += 1
        logger.info(f"[PR{self.pr_number}] Status update: {status.state}")

    async def _emit_status_update_async(self, emit_event: Callable, status: PRStatus) -> None:
        """Emit status update event (async)."""
        payload = {
            "prNumber": self.pr_number,
            "state": status.state,
            "conclusion": status.conclusion,
            "url": status.url,
            "checkCount": status.check_count,
            "failedChecks": status.failed_checks,
            "lastUpdated": status.last_updated
        }
        
        await emit_event("navi.pr.ci.updated", payload)
        self.events_emitted += 1
        logger.info(f"[PR{self.pr_number}] Status update: {status.state}")

    def _emit_completion(self, emit_event: Callable, status: PRStatus) -> None:
        """Emit completion event (sync)."""
        payload = {
            "prNumber": self.pr_number,
            "state": status.state,
            "conclusion": status.conclusion,
            "url": status.url,
            "checkCount": status.check_count,
            "failedChecks": status.failed_checks,
            "monitoringDuration": self._get_monitoring_duration()
        }
        
        emit_event("navi.pr.completed", payload)
        self.events_emitted += 1
        logger.info(f"[PR{self.pr_number}] Monitoring completed: {status.state}")

    async def _emit_completion_async(self, emit_event: Callable, status: PRStatus) -> None:
        """Emit completion event (async)."""
        payload = {
            "prNumber": self.pr_number,
            "state": status.state,
            "conclusion": status.conclusion,
            "url": status.url,
            "checkCount": status.check_count,
            "failedChecks": status.failed_checks,
            "monitoringDuration": self._get_monitoring_duration()
        }
        
        await emit_event("navi.pr.completed", payload)
        self.events_emitted += 1
        logger.info(f"[PR{self.pr_number}] Monitoring completed: {status.state}")

    # ------------------------------------------------------------------
    # Monitoring State Management
    # ------------------------------------------------------------------

    def _is_monitoring_timeout(self) -> bool:
        """Check if monitoring has exceeded timeout."""
        if not self.start_time:
            return False
        
        duration = (datetime.now() - self.start_time).total_seconds()
        return duration > self.MAX_MONITORING_DURATION

    def _get_monitoring_duration(self) -> float:
        """Get monitoring duration in seconds."""
        if not self.start_time:
            return 0.0
        
        return (datetime.now() - self.start_time).total_seconds()

    def _create_result(self, terminal_reason: str, final_status: PRStatus) -> PRLifecycleResult:
        """Create monitoring result."""
        return PRLifecycleResult(
            pr_number=self.pr_number,
            final_status=final_status,
            monitoring_duration=self._get_monitoring_duration(),
            events_emitted=self.events_emitted,
            terminal_reason=terminal_reason
        )

    # ------------------------------------------------------------------
    # Utility Methods
    # ------------------------------------------------------------------

    @classmethod
    def from_workspace(cls, workspace_root: str, pr_number: int) -> 'PRLifecycleEngine':
        """
        Create engine from workspace by auto-detecting GitHub repo.
        
        Args:
            workspace_root: Path to git repository
            pr_number: PR number to monitor
            
        Returns:
            Configured PRLifecycleEngine
        """
        import subprocess
        
        try:
            # Get git remote URL
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=workspace_root,
                capture_output=True,
                text=True,
                check=True
            )
            
            remote_url = result.stdout.strip()
            
            # Parse GitHub repo info
            if "github.com" not in remote_url:
                raise PRLifecycleError("Not a GitHub repository")
            
            # Extract owner/repo from URL
            if remote_url.startswith("git@github.com:"):
                repo_path = remote_url.replace("git@github.com:", "").replace(".git", "")
            elif remote_url.startswith("https://github.com/"):
                repo_path = remote_url.replace("https://github.com/", "").replace(".git", "")
            else:
                raise PRLifecycleError(f"Unsupported GitHub URL format: {remote_url}")
            
            owner, repo = repo_path.split("/", 1)
            
            return cls(
                repo_owner=owner,
                repo_name=repo,
                pr_number=pr_number,
                workspace_root=workspace_root
            )
            
        except subprocess.CalledProcessError as e:
            raise PRLifecycleError(f"Failed to get git remote: {e}")
        except ValueError as e:
            raise PRLifecycleError(f"Invalid repository path: {e}")

    def __str__(self) -> str:
        return f"PRLifecycleEngine({self.repo_owner}/{self.repo_name}#{self.pr_number})"

    def __repr__(self) -> str:
        return (
            f"PRLifecycleEngine("
            f"repo_owner='{self.repo_owner}', "
            f"repo_name='{self.repo_name}', "
            f"pr_number={self.pr_number})"
        )