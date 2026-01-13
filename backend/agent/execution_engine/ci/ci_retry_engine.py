"""
Enterprise CI Retry Engine

Production-grade system for re-running CI pipelines after automated
repairs with intelligent retry logic, rate limiting, and failure tracking.
"""

import asyncio

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None  # type: ignore
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from .ci_types import CIProvider, CIEvent, GitHubActionsConfig

logger = logging.getLogger(__name__)


class RetryStatus(Enum):
    """Status of CI retry attempt"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    UNAUTHORIZED = "unauthorized"


@dataclass
class RetryAttempt:
    """Track individual retry attempt"""

    attempt_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: RetryStatus = RetryStatus.PENDING
    error_message: Optional[str] = None
    ci_run_id: Optional[str] = None
    response_data: Optional[Dict[str, Any]] = None


@dataclass
class RetrySession:
    """Track complete retry session with multiple attempts"""

    session_id: str
    original_event: CIEvent
    created_at: datetime
    max_attempts: int = 3
    retry_delay_seconds: int = 60
    attempts: List[RetryAttempt] = field(default_factory=list)
    final_status: Optional[RetryStatus] = None
    total_duration: Optional[timedelta] = None


class CIRetryEngine:
    """
    Enterprise CI retry engine with intelligent backoff and monitoring

    Handles CI pipeline re-execution after automated repairs with
    proper rate limiting, error handling, and retry strategy.
    """

    def __init__(self, github_config: Optional[GitHubActionsConfig] = None):
        self.github_config = github_config
        self.session: Optional[aiohttp.ClientSession] = None
        self.active_retries: Dict[str, RetrySession] = {}

        # Rate limiting configuration
        self.max_concurrent_retries = 5
        self.min_retry_interval = 30  # seconds
        self.max_daily_retries = 100
        self.daily_retry_count = 0
        self.last_retry_reset = datetime.now().date()

    async def __aenter__(self):
        """Async context manager for session lifecycle"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=300),
            headers={"User-Agent": "NAVI-CI-RetryEngine/1.0"},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up session resources"""
        if self.session:
            await self.session.close()

    async def retry_ci_pipeline(
        self,
        event: CIEvent,
        session_id: str,
        max_attempts: int = 3,
        retry_delay: int = 60,
    ) -> RetrySession:
        """
        Retry CI pipeline with intelligent backoff

        Args:
            event: Original CI event that failed
            session_id: Unique session ID for tracking
            max_attempts: Maximum retry attempts
            retry_delay: Base delay between retries in seconds

        Returns:
            Complete retry session with attempt history
        """
        # Check rate limits
        if not self._check_rate_limits():
            logger.warning("CI retry rate limit exceeded")
            return self._create_rate_limited_session(event, session_id)

        # Create retry session
        retry_session = RetrySession(
            session_id=session_id,
            original_event=event,
            created_at=datetime.now(),
            max_attempts=max_attempts,
            retry_delay_seconds=retry_delay,
        )

        self.active_retries[session_id] = retry_session

        try:
            # Execute retry attempts
            for attempt_num in range(max_attempts):
                logger.info(
                    f"CI retry attempt {attempt_num + 1}/{max_attempts} for {event.run_id}"
                )

                attempt = await self._execute_retry_attempt(
                    event, attempt_num, retry_delay
                )

                retry_session.attempts.append(attempt)

                # Check if successful
                if attempt.status == RetryStatus.SUCCESS:
                    retry_session.final_status = RetryStatus.SUCCESS
                    break

                # Check if should continue retrying
                if not self._should_continue_retry(
                    attempt, attempt_num, max_attempts - 1
                ):
                    break

                # Wait before next attempt (exponential backoff)
                if attempt_num < max_attempts - 1:
                    wait_time = retry_delay * (2**attempt_num)
                    logger.info(f"Waiting {wait_time}s before next retry attempt")
                    await asyncio.sleep(wait_time)

            # Set final status if not already set
            if not retry_session.final_status:
                retry_session.final_status = RetryStatus.FAILED

            # Calculate total duration
            retry_session.total_duration = datetime.now() - retry_session.created_at

            self._increment_daily_retry_count()

        except Exception as e:
            logger.error(f"Critical error in CI retry session {session_id}: {e}")
            retry_session.final_status = RetryStatus.FAILED

        finally:
            # Clean up active session
            self.active_retries.pop(session_id, None)

        return retry_session

    async def _execute_retry_attempt(
        self, event: CIEvent, attempt_num: int, base_delay: int
    ) -> RetryAttempt:
        """Execute single retry attempt"""
        attempt_id = f"{event.run_id}_attempt_{attempt_num + 1}"

        attempt = RetryAttempt(attempt_id=attempt_id, started_at=datetime.now())

        try:
            if event.provider == CIProvider.GITHUB_ACTIONS:
                attempt = await self._retry_github_actions(event, attempt)
            elif event.provider == CIProvider.JENKINS:
                attempt = await self._retry_jenkins(event, attempt)
            elif event.provider == CIProvider.CIRCLECI:
                attempt = await self._retry_circleci(event, attempt)
            else:
                attempt.status = RetryStatus.FAILED
                attempt.error_message = f"Unsupported provider: {event.provider}"

        except Exception as e:
            attempt.status = RetryStatus.FAILED
            attempt.error_message = str(e)
            logger.error(f"Retry attempt {attempt_id} failed: {e}")

        finally:
            attempt.completed_at = datetime.now()

        return attempt

    async def _retry_github_actions(
        self, event: CIEvent, attempt: RetryAttempt
    ) -> RetryAttempt:
        """Retry GitHub Actions workflow"""
        if not self.github_config or not self.github_config.token:
            attempt.status = RetryStatus.UNAUTHORIZED
            attempt.error_message = "GitHub token not configured"
            return attempt

        if not self.session:
            attempt.status = RetryStatus.FAILED
            attempt.error_message = "HTTP session not initialized"
            return attempt

        headers = {
            "Authorization": f"Bearer {self.github_config.token}",
            "Accept": "application/vnd.github.v3+json",
        }

        # Retry workflow run
        retry_url = f"{self.github_config.base_url}/repos/{event.repo_owner}/{event.repo_name}/actions/runs/{event.run_id}/rerun"

        try:
            async with self.session.post(retry_url, headers=headers) as response:
                response_data = {}

                try:
                    response_data = await response.json()
                except Exception:
                    response_data = {"raw_response": await response.text()}

                attempt.response_data = response_data

                if response.status == 201:
                    # Successfully triggered retry
                    attempt.status = RetryStatus.SUCCESS
                    attempt.ci_run_id = response_data.get("id", event.run_id)
                    logger.info(
                        f"Successfully triggered GitHub Actions retry for {event.run_id}"
                    )

                elif response.status == 403:
                    attempt.status = RetryStatus.UNAUTHORIZED
                    attempt.error_message = "Insufficient permissions to retry workflow"

                elif response.status == 422:
                    attempt.status = RetryStatus.FAILED
                    attempt.error_message = (
                        "Workflow cannot be re-run (possibly already running)"
                    )

                elif response.status == 429:
                    attempt.status = RetryStatus.RATE_LIMITED
                    attempt.error_message = "GitHub API rate limit exceeded"

                else:
                    attempt.status = RetryStatus.FAILED
                    attempt.error_message = (
                        f"GitHub API error: {response.status} - {response_data}"
                    )

        except aiohttp.ClientError as e:
            attempt.status = RetryStatus.FAILED
            attempt.error_message = f"Network error: {str(e)}"

        return attempt

    async def _retry_jenkins(
        self, event: CIEvent, attempt: RetryAttempt
    ) -> RetryAttempt:
        """Retry Jenkins build"""
        # Jenkins retry implementation - placeholder for production deployment
        logger.warning("Jenkins retry not yet implemented")
        attempt.status = RetryStatus.FAILED
        attempt.error_message = "Jenkins retry not implemented"
        return attempt

    async def _retry_circleci(
        self, event: CIEvent, attempt: RetryAttempt
    ) -> RetryAttempt:
        """Retry CircleCI pipeline"""
        # CircleCI retry implementation - placeholder for production deployment
        logger.warning("CircleCI retry not yet implemented")
        attempt.status = RetryStatus.FAILED
        attempt.error_message = "CircleCI retry not implemented"
        return attempt

    def _check_rate_limits(self) -> bool:
        """Check if retry is allowed based on rate limits"""
        # Reset daily count if needed
        current_date = datetime.now().date()
        if current_date > self.last_retry_reset:
            self.daily_retry_count = 0
            self.last_retry_reset = current_date

        # Check daily limit
        if self.daily_retry_count >= self.max_daily_retries:
            logger.warning(f"Daily retry limit ({self.max_daily_retries}) exceeded")
            return False

        # Check concurrent limit
        if len(self.active_retries) >= self.max_concurrent_retries:
            logger.warning(
                f"Concurrent retry limit ({self.max_concurrent_retries}) exceeded"
            )
            return False

        return True

    def _should_continue_retry(
        self, attempt: RetryAttempt, attempt_num: int, max_attempts: int
    ) -> bool:
        """Determine if should continue retrying based on attempt result"""
        if attempt.status == RetryStatus.SUCCESS:
            return False

        if attempt_num >= max_attempts:
            return False

        # Don't retry certain failures
        no_retry_statuses = [RetryStatus.UNAUTHORIZED]
        if attempt.status in no_retry_statuses:
            logger.info(f"Not retrying due to status: {attempt.status}")
            return False

        # Rate limited - wait longer but continue
        if attempt.status == RetryStatus.RATE_LIMITED:
            logger.info("Rate limited - will retry with longer delay")
            return True

        return True

    def _create_rate_limited_session(
        self, event: CIEvent, session_id: str
    ) -> RetrySession:
        """Create session when rate limited"""
        session = RetrySession(
            session_id=session_id,
            original_event=event,
            created_at=datetime.now(),
            final_status=RetryStatus.RATE_LIMITED,
        )

        # Add single attempt showing rate limit
        attempt = RetryAttempt(
            attempt_id=f"{session_id}_rate_limited",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            status=RetryStatus.RATE_LIMITED,
            error_message="Daily or concurrent retry limit exceeded",
        )

        session.attempts.append(attempt)
        return session

    def _increment_daily_retry_count(self):
        """Increment daily retry counter"""
        self.daily_retry_count += 1
        logger.debug(
            f"Daily retry count: {self.daily_retry_count}/{self.max_daily_retries}"
        )

    async def get_retry_status(self, session_id: str) -> Optional[RetrySession]:
        """Get status of active or completed retry session"""
        return self.active_retries.get(session_id)

    async def cancel_retry_session(self, session_id: str) -> bool:
        """Cancel active retry session"""
        session = self.active_retries.get(session_id)
        if session:
            session.final_status = RetryStatus.FAILED
            self.active_retries.pop(session_id, None)
            logger.info(f"Cancelled retry session {session_id}")
            return True
        return False

    def get_retry_statistics(self) -> Dict[str, Any]:
        """Get retry engine statistics"""
        return {
            "active_retries": len(self.active_retries),
            "daily_retry_count": self.daily_retry_count,
            "max_daily_retries": self.max_daily_retries,
            "max_concurrent_retries": self.max_concurrent_retries,
            "last_reset_date": self.last_retry_reset.isoformat(),
            "rate_limit_status": (
                "ok"
                if self.daily_retry_count < self.max_daily_retries * 0.8
                else "approaching_limit"
            ),
        }

    async def monitor_retry_progress(
        self, event: CIEvent, new_run_id: str
    ) -> Dict[str, Any]:
        """Monitor progress of retriggered CI run"""
        if event.provider == CIProvider.GITHUB_ACTIONS:
            return await self._monitor_github_run(event, new_run_id)
        else:
            return {
                "status": "unknown",
                "message": f"Monitoring not implemented for {event.provider}",
            }

    async def _monitor_github_run(self, event: CIEvent, run_id: str) -> Dict[str, Any]:
        """Monitor GitHub Actions run progress"""
        if not self.github_config or not self.session:
            return {"status": "error", "message": "GitHub monitoring not configured"}

        headers = {
            "Authorization": f"Bearer {self.github_config.token}",
            "Accept": "application/vnd.github.v3+json",
        }

        run_url = f"{self.github_config.base_url}/repos/{event.repo_owner}/{event.repo_name}/actions/runs/{run_id}"

        try:
            async with self.session.get(run_url, headers=headers) as response:
                if response.status == 200:
                    run_data = await response.json()
                    return {
                        "status": run_data.get("status", "unknown"),
                        "conclusion": run_data.get("conclusion"),
                        "run_number": run_data.get("run_number"),
                        "created_at": run_data.get("created_at"),
                        "updated_at": run_data.get("updated_at"),
                        "html_url": run_data.get("html_url"),
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"GitHub API error: {response.status}",
                    }

        except Exception as e:
            return {"status": "error", "message": f"Monitoring error: {str(e)}"}
