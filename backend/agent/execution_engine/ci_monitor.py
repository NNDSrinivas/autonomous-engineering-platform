"""
CI Monitor - Phase 4.4

Intelligent CI/CD pipeline monitoring for NAVI's autonomous workflow.
Makes smart decisions about build failures and next actions.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import time
import re

logger = logging.getLogger(__name__)


class CIStatus(Enum):
    """CI pipeline status types"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class CIFailureType(Enum):
    """Types of CI failures"""

    BUILD_ERROR = "build_error"  # Compilation/build failure
    TEST_FAILURE = "test_failure"  # Unit/integration test failure
    LINT_ERROR = "lint_error"  # Code quality/linting issues
    SECURITY_SCAN = "security_scan"  # Security vulnerability found
    INFRASTRUCTURE = "infrastructure"  # CI infrastructure issues
    TIMEOUT = "timeout"  # Build timeout
    UNKNOWN = "unknown"  # Unclassified failure


@dataclass
class CIJob:
    """Information about a CI job"""

    name: str
    status: CIStatus
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    duration: Optional[int] = None  # seconds
    logs: Optional[str] = None
    failure_type: Optional[CIFailureType] = None
    failure_reason: Optional[str] = None


@dataclass
class CIResult:
    """Complete CI pipeline result"""

    pr_number: int
    pr_url: str
    repository: str
    branch: str
    overall_status: CIStatus
    jobs: List[CIJob]
    started_at: float
    completed_at: Optional[float] = None
    total_duration: Optional[int] = None
    can_retry: bool = False
    suggested_action: Optional[str] = None


class CIMonitor:
    """
    Intelligent CI/CD monitoring for NAVI's autonomous operations.

    Features:
    - Real-time pipeline monitoring
    - Intelligent failure analysis
    - Actionable recommendations
    - Auto-retry logic for flaky tests
    """

    def __init__(self, github_service=None):
        self.github_service = github_service
        self.monitoring_jobs = {}  # pr_number -> asyncio.Task

    async def wait_for_ci_result(
        self, repository: str, pr_number: int, timeout_minutes: int = 30
    ) -> CIResult:
        """
        Monitor CI pipeline and wait for completion.

        Args:
            repository: Repository name (owner/repo)
            pr_number: PR number to monitor
            timeout_minutes: Max time to wait

        Returns:
            CIResult with complete pipeline status
        """
        logger.info(f"Monitoring CI for PR #{pr_number} in {repository}")

        start_time = time.time()
        timeout_seconds = timeout_minutes * 60

        try:
            # Start monitoring
            pr_url = f"https://github.com/{repository}/pull/{pr_number}"

            result = CIResult(
                pr_number=pr_number,
                pr_url=pr_url,
                repository=repository,
                branch=f"pr-{pr_number}",  # Will be updated with actual branch
                overall_status=CIStatus.PENDING,
                jobs=[],
                started_at=start_time,
            )

            # Monitor with polling (in real implementation, use webhooks)
            while time.time() - start_time < timeout_seconds:
                # Get current CI status
                ci_status = await self._fetch_ci_status(repository, pr_number)

                if ci_status:
                    result.overall_status = ci_status["status"]
                    result.jobs = ci_status["jobs"]
                    result.branch = ci_status.get("branch", result.branch)

                    # Check if pipeline is complete
                    if result.overall_status in [
                        CIStatus.SUCCESS,
                        CIStatus.FAILURE,
                        CIStatus.CANCELLED,
                    ]:
                        result.completed_at = time.time()
                        result.total_duration = int(
                            result.completed_at - result.started_at
                        )

                        # Analyze results and suggest actions
                        await self._analyze_ci_results(result)

                        logger.info(
                            f"CI monitoring complete for PR #{pr_number}: {result.overall_status.value}"
                        )
                        return result

                # Wait before next poll
                await asyncio.sleep(30)  # Poll every 30 seconds

            # Timeout reached
            result.overall_status = CIStatus.UNKNOWN
            result.suggested_action = (
                "CI monitoring timed out - check pipeline manually"
            )
            logger.warning(f"CI monitoring timed out for PR #{pr_number}")

            return result

        except Exception as e:
            logger.error(f"CI monitoring failed for PR #{pr_number}: {e}")
            return CIResult(
                pr_number=pr_number,
                pr_url=f"https://github.com/{repository}/pull/{pr_number}",
                repository=repository,
                branch="unknown",
                overall_status=CIStatus.UNKNOWN,
                jobs=[],
                started_at=start_time,
                suggested_action=f"Monitoring error: {str(e)}",
            )

    async def _fetch_ci_status(
        self, repository: str, pr_number: int
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch current CI status from GitHub API.

        In a real implementation, this would use GitHub Checks API.
        For now, we simulate CI status changes.
        """
        try:
            # Simulate CI pipeline progression
            elapsed_time = time.time() - self.monitoring_jobs.get(
                pr_number, time.time()
            )

            if elapsed_time < 120:  # First 2 minutes: pending/running
                return {
                    "status": CIStatus.RUNNING,
                    "branch": f"navi/fix-{pr_number}",
                    "jobs": [
                        CIJob(
                            name="build",
                            status=CIStatus.RUNNING,
                            started_at=time.time() - elapsed_time,
                        ),
                        CIJob(name="test", status=CIStatus.PENDING),
                    ],
                }
            elif elapsed_time < 300:  # 2-5 minutes: completing
                return {
                    "status": CIStatus.RUNNING,
                    "branch": f"navi/fix-{pr_number}",
                    "jobs": [
                        CIJob(
                            name="build",
                            status=CIStatus.SUCCESS,
                            started_at=time.time() - elapsed_time,
                            completed_at=time.time() - elapsed_time + 90,
                            duration=90,
                        ),
                        CIJob(
                            name="test",
                            status=CIStatus.RUNNING,
                            started_at=time.time() - elapsed_time + 90,
                        ),
                    ],
                }
            else:  # After 5 minutes: complete
                # Simulate success/failure (90% success rate for NAVI fixes)
                success = (pr_number % 10) != 0  # 90% success

                if success:
                    return {
                        "status": CIStatus.SUCCESS,
                        "branch": f"navi/fix-{pr_number}",
                        "jobs": [
                            CIJob(name="build", status=CIStatus.SUCCESS, duration=90),
                            CIJob(name="test", status=CIStatus.SUCCESS, duration=150),
                            CIJob(name="lint", status=CIStatus.SUCCESS, duration=30),
                        ],
                    }
                else:
                    return {
                        "status": CIStatus.FAILURE,
                        "branch": f"navi/fix-{pr_number}",
                        "jobs": [
                            CIJob(name="build", status=CIStatus.SUCCESS, duration=90),
                            CIJob(
                                name="test",
                                status=CIStatus.FAILURE,
                                duration=120,
                                failure_type=CIFailureType.TEST_FAILURE,
                                failure_reason="Unit test failed: expected 'true' but got 'false'",
                                logs="TestExample.test_function: AssertionError at line 45",
                            ),
                        ],
                    }

        except Exception as e:
            logger.error(f"Failed to fetch CI status: {e}")
            return None

    async def _analyze_ci_results(self, result: CIResult) -> None:
        """
        Analyze CI results and suggest intelligent next actions.
        """
        if result.overall_status == CIStatus.SUCCESS:
            result.suggested_action = "✅ All CI checks passed - PR is ready for review"
            return

        if result.overall_status == CIStatus.FAILURE:
            # Analyze failure types
            failed_jobs = [job for job in result.jobs if job.status == CIStatus.FAILURE]

            if not failed_jobs:
                result.suggested_action = (
                    "❌ CI failed but no specific job failures identified"
                )
                return

            # Categorize failures
            failure_types = [
                job.failure_type for job in failed_jobs if job.failure_type
            ]

            if CIFailureType.BUILD_ERROR in failure_types:
                result.suggested_action = (
                    "🔧 Build failure detected - NAVI can analyze and fix build issues"
                )
                result.can_retry = True

            elif CIFailureType.TEST_FAILURE in failure_types:
                test_job = next(
                    job
                    for job in failed_jobs
                    if job.failure_type == CIFailureType.TEST_FAILURE
                )
                if self._is_flaky_test(test_job):
                    result.suggested_action = "🔄 Flaky test detected - recommend retry"
                    result.can_retry = True
                else:
                    result.suggested_action = (
                        "🧪 Test failure - NAVI can analyze test logs and suggest fixes"
                    )
                    result.can_retry = True

            elif CIFailureType.LINT_ERROR in failure_types:
                result.suggested_action = (
                    "📝 Linting issues - NAVI can auto-fix code style problems"
                )
                result.can_retry = True

            elif CIFailureType.SECURITY_SCAN in failure_types:
                result.suggested_action = (
                    "🔒 Security issues found - manual review required"
                )
                result.can_retry = False

            elif CIFailureType.INFRASTRUCTURE in failure_types:
                result.suggested_action = (
                    "⚠️ Infrastructure failure - retry recommended"
                )
                result.can_retry = True

            else:
                result.suggested_action = "❌ CI failure - manual investigation needed"
                result.can_retry = False
        else:
            result.suggested_action = f"CI status: {result.overall_status.value}"

    def _is_flaky_test(self, job: CIJob) -> bool:
        """
        Detect if a test failure is likely flaky.

        Looks for common flaky test patterns in logs.
        """
        if not job.logs:
            return False

        flaky_patterns = [
            r"timeout|timed out",
            r"network|connection|socket",
            r"race condition|timing",
            r"random|flaky|intermittent",
            r"retry|attempt \d+",
            r"assertion.*sometimes fails",
        ]

        logs_lower = job.logs.lower()
        for pattern in flaky_patterns:
            if re.search(pattern, logs_lower):
                return True

        return False

    async def start_monitoring(self, repository: str, pr_number: int) -> None:
        """
        Start background monitoring for a PR.

        Args:
            repository: Repository name
            pr_number: PR number to monitor
        """
        if pr_number in self.monitoring_jobs:
            logger.warning(f"Already monitoring PR #{pr_number}")
            return

        self.monitoring_jobs[pr_number] = time.time()
        logger.info(f"Started monitoring PR #{pr_number}")

    async def stop_monitoring(self, pr_number: int) -> None:
        """Stop monitoring a specific PR."""
        if pr_number in self.monitoring_jobs:
            del self.monitoring_jobs[pr_number]
            logger.info(f"Stopped monitoring PR #{pr_number}")

    def get_ci_decision(self, result: CIResult) -> Dict[str, Any]:
        """
        Get NAVI's intelligent decision about what to do next.

        Args:
            result: CI result to analyze

        Returns:
            Decision with recommended action
        """
        if result.overall_status == CIStatus.SUCCESS:
            return {
                "action": "success",
                "message": "🎉 CI passed! PR is ready for review.",
                "next_steps": [
                    "Notify team of successful automation",
                    "Add PR comment with success summary",
                    "Monitor for reviewer feedback",
                ],
            }

        elif result.overall_status == CIStatus.FAILURE and result.can_retry:
            failed_jobs = [job for job in result.jobs if job.status == CIStatus.FAILURE]
            failure_types = [
                job.failure_type for job in failed_jobs if job.failure_type
            ]

            if CIFailureType.TEST_FAILURE in failure_types:
                return {
                    "action": "analyze_and_fix",
                    "message": "🔍 Test failures detected. NAVI can analyze and suggest fixes.",
                    "next_steps": [
                        "Analyze test failure logs",
                        "Generate fixes for failing tests",
                        "Apply fixes and push to same branch",
                        "Monitor CI again",
                    ],
                }
            elif CIFailureType.LINT_ERROR in failure_types:
                return {
                    "action": "auto_fix",
                    "message": "🧹 Linting errors detected. NAVI can auto-fix these.",
                    "next_steps": [
                        "Run code formatting/linting fixes",
                        "Commit and push fixes",
                        "Monitor CI pipeline again",
                    ],
                }
            else:
                return {
                    "action": "retry",
                    "message": "🔄 Retryable failure detected.",
                    "next_steps": [
                        "Wait for infrastructure recovery",
                        "Retry CI pipeline",
                        "Escalate if retry fails",
                    ],
                }

        else:
            return {
                "action": "escalate",
                "message": "⚠️ CI failure requires human attention.",
                "next_steps": [
                    "Add PR comment explaining the failure",
                    "Notify team of manual intervention needed",
                    "Provide failure analysis and logs",
                ],
            }

    async def generate_ci_summary(self, result: CIResult) -> str:
        """Generate a human-readable CI summary for PR comments."""
        lines = []

        lines.append("## 🤖 NAVI CI Report")
        lines.append("")

        # Overall status
        if result.overall_status == CIStatus.SUCCESS:
            lines.append("✅ **All CI checks passed!**")
        elif result.overall_status == CIStatus.FAILURE:
            lines.append("❌ **CI checks failed**")
        else:
            lines.append(f"⏳ **CI Status**: {result.overall_status.value}")

        lines.append("")

        # Job details
        if result.jobs:
            lines.append("### Job Results")
            for job in result.jobs:
                if job.status == CIStatus.SUCCESS:
                    status_icon = "✅"
                elif job.status == CIStatus.FAILURE:
                    status_icon = "❌"
                elif job.status == CIStatus.RUNNING:
                    status_icon = "🔄"
                else:
                    status_icon = "⏸️"

                lines.append(f"- {status_icon} **{job.name}**: {job.status.value}")

                if job.failure_reason:
                    lines.append(f"  - Error: {job.failure_reason}")

            lines.append("")

        # Duration
        if result.total_duration:
            minutes = result.total_duration // 60
            seconds = result.total_duration % 60
            lines.append(f"⏱️ **Total Duration**: {minutes}m {seconds}s")
            lines.append("")

        # Next steps
        if result.suggested_action:
            lines.append("### Recommended Action")
            lines.append(result.suggested_action)
            lines.append("")

        lines.append("---")
        lines.append("*Generated by NAVI Autonomous Engineering*")

        return "\n".join(lines)
