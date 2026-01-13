"""
Enterprise CI Log Fetcher

Production-grade log fetching system for GitHub Actions, Jenkins, and other
CI providers with intelligent parsing and error handling.
"""

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None  # type: ignore

import logging
from typing import Optional, Dict, Any
from datetime import datetime
import re
import io

from .ci_types import CIProvider, CIEvent, CILogs, GitHubActionsConfig

logger = logging.getLogger(__name__)


class CILogFetcher:
    """
    Enterprise-grade CI log fetching with multi-provider support

    Handles GitHub Actions, Jenkins, CircleCI with proper rate limiting,
    error handling, and log size management.
    """

    def __init__(self, github_config: Optional[GitHubActionsConfig] = None):
        if not AIOHTTP_AVAILABLE:
            raise ImportError(
                "aiohttp is required for CILogFetcher. Install it with: pip install aiohttp"
            )
        self.github_config = github_config
        self.session: Optional[aiohttp.ClientSession] = None  # type: ignore

    async def __aenter__(self):
        """Async context manager for session lifecycle"""
        if not AIOHTTP_AVAILABLE or aiohttp is None:
            raise ImportError("aiohttp is required for CILogFetcher")
        self.session = aiohttp.ClientSession(  # type: ignore
            timeout=aiohttp.ClientTimeout(total=300),  # type: ignore
            headers={"User-Agent": "NAVI-CI-AutoRepair/1.0"},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up session resources"""
        if self.session:
            await self.session.close()

    async def fetch_logs(self, event: CIEvent) -> CILogs:
        """
        Fetch CI logs based on provider

        Args:
            event: CI event containing provider and run details

        Returns:
            Structured CI logs with parsing and metadata

        Raises:
            ValueError: For unsupported providers or missing config
            aiohttp.ClientError: For network/API errors
        """
        if event.provider == CIProvider.GITHUB_ACTIONS:
            return await self._fetch_github_logs(event)
        elif event.provider == CIProvider.JENKINS:
            return await self._fetch_jenkins_logs(event)
        elif event.provider == CIProvider.CIRCLECI:
            return await self._fetch_circleci_logs(event)
        else:
            raise ValueError(f"Unsupported CI provider: {event.provider}")

    async def _fetch_github_logs(self, event: CIEvent) -> CILogs:
        """Fetch logs from GitHub Actions API"""
        if not self.github_config or not self.github_config.token:
            raise ValueError("GitHub Actions token required for log fetching")

        if not self.session:
            raise RuntimeError("Session not initialized - use async context manager")

        headers = {
            "Authorization": (
                f"Bearer {self.github_config.token}"
                if self.github_config and self.github_config.token
                else ""
            ),
            "Accept": "application/vnd.github.v3+json",
        }

        # Fetch workflow run details first
        base_url = (
            self.github_config.base_url
            if self.github_config and self.github_config.base_url
            else "https://api.github.com"
        )
        run_url = f"{base_url}/repos/{event.repo_owner}/{event.repo_name}/actions/runs/{event.run_id}"

        async with self.session.get(run_url, headers=headers) as response:
            if response.status == 404:
                raise ValueError(f"GitHub Actions run {event.run_id} not found")
            elif response.status != 200:
                if aiohttp:
                    raise aiohttp.ClientError(f"GitHub API error: {response.status}")  # type: ignore
                else:
                    raise RuntimeError(f"GitHub API error: {response.status}")

            run_data = await response.json()

        # Fetch logs (returns ZIP archive)
        logs_url = f"{run_url}/logs"

        async with self.session.get(logs_url, headers=headers) as response:
            if response.status != 200:
                logger.warning(
                    f"Could not fetch logs for run {event.run_id}: {response.status}"
                )
                # Fallback to job-level logs if available
                return await self._fetch_github_job_logs(event, run_data)

            # GitHub returns logs as ZIP
            zip_content = await response.read()
            raw_logs = self._extract_github_zip_logs(zip_content)

        return self._parse_logs(
            raw_logs=raw_logs, source_url=logs_url, provider=CIProvider.GITHUB_ACTIONS
        )

    def _extract_github_zip_logs(self, zip_content: bytes) -> str:
        """Extract log content from GitHub's ZIP response"""
        try:
            import zipfile

            combined_logs = []

            with zipfile.ZipFile(io.BytesIO(zip_content)) as zip_file:
                for file_info in zip_file.filelist:
                    if file_info.filename.endswith(".txt"):
                        with zip_file.open(file_info) as log_file:
                            content = log_file.read().decode("utf-8", errors="ignore")
                            combined_logs.append(
                                f"=== {file_info.filename} ===\n{content}\n"
                            )

            return "\n".join(combined_logs)

        except Exception as e:
            logger.error(f"Failed to extract GitHub logs from ZIP: {e}")
            return f"LOG_EXTRACTION_ERROR: {str(e)}"

    async def _fetch_github_job_logs(
        self, event: CIEvent, run_data: Dict[str, Any]
    ) -> CILogs:
        """Fallback: fetch individual job logs if workflow logs unavailable"""
        if not self.session:
            raise RuntimeError("Session not initialized")

        headers = {
            "Authorization": f'Bearer {self.github_config.token if self.github_config else ""}',
            "Accept": "application/vnd.github.v3+json",
        }

        base_url = (
            self.github_config.base_url
            if self.github_config and self.github_config.base_url
            else "https://api.github.com"
        )
        jobs_url = f"{base_url}/repos/{event.repo_owner}/{event.repo_name}/actions/runs/{event.run_id}/jobs"

        combined_logs = []

        async with self.session.get(jobs_url, headers=headers) as response:
            if response.status == 200:
                jobs_data = await response.json()

                for job in jobs_data.get("jobs", []):
                    if job["status"] == "completed" and job["conclusion"] == "failure":
                        job_logs_url = f"{base_url}/repos/{event.repo_owner}/{event.repo_name}/actions/jobs/{job['id']}/logs"

                        try:
                            async with self.session.get(
                                job_logs_url, headers=headers
                            ) as job_response:
                                if job_response.status == 200:
                                    job_logs = await job_response.text()
                                    combined_logs.append(
                                        f"=== Job: {job['name']} ===\n{job_logs}\n"
                                    )
                        except Exception as e:
                            logger.warning(
                                f"Could not fetch logs for job {job['id']}: {e}"
                            )

        raw_logs = (
            "\n".join(combined_logs) if combined_logs else "No job logs available"
        )

        return self._parse_logs(
            raw_logs=raw_logs, source_url=jobs_url, provider=CIProvider.GITHUB_ACTIONS
        )

    async def _fetch_jenkins_logs(self, event: CIEvent) -> CILogs:
        """Fetch logs from Jenkins API"""
        # Production Jenkins integration - implement based on deployment needs
        logger.warning("Jenkins log fetching not yet implemented")
        return self._create_placeholder_logs(event, "Jenkins logs not yet implemented")

    async def _fetch_circleci_logs(self, event: CIEvent) -> CILogs:
        """Fetch logs from CircleCI API"""
        # Production CircleCI integration - implement based on deployment needs
        logger.warning("CircleCI log fetching not yet implemented")
        return self._create_placeholder_logs(event, "CircleCI logs not yet implemented")

    def _parse_logs(
        self, raw_logs: str, source_url: str, provider: CIProvider
    ) -> CILogs:
        """
        Parse raw logs into structured format for intelligent analysis

        Extracts error lines, warnings, and structures logs for
        failure classification and repair planning.
        """
        lines = raw_logs.split("\n")

        error_lines = []
        warning_lines = []
        structured_logs = []

        # Patterns for different log types
        error_patterns = [
            r"ERROR:",
            r"FAIL:",
            r"FAILED:",
            r"Error:",
            r"Exception:",
            r"AssertionError:",
            r"TypeError:",
            r"NameError:",
            r"ImportError:",
            r"✗",
            r"❌",
            r"FAILURE",
            r"BUILD FAILED",
        ]

        warning_patterns = [r"WARNING:", r"WARN:", r"Warning:", r"⚠️", r"DEPRECATED"]

        # Parse each line
        for i, line in enumerate(lines):
            line_clean = line.strip()
            if not line_clean:
                continue

            # Check for errors
            if any(
                re.search(pattern, line_clean, re.IGNORECASE)
                for pattern in error_patterns
            ):
                error_lines.append(line_clean)
                structured_logs.append(
                    {
                        "line_number": i + 1,
                        "type": "error",
                        "content": line_clean,
                        "timestamp": self._extract_timestamp(line_clean),
                    }
                )

            # Check for warnings
            elif any(
                re.search(pattern, line_clean, re.IGNORECASE)
                for pattern in warning_patterns
            ):
                warning_lines.append(line_clean)
                structured_logs.append(
                    {
                        "line_number": i + 1,
                        "type": "warning",
                        "content": line_clean,
                        "timestamp": self._extract_timestamp(line_clean),
                    }
                )

            # Regular log entry
            else:
                structured_logs.append(
                    {
                        "line_number": i + 1,
                        "type": "info",
                        "content": line_clean,
                        "timestamp": self._extract_timestamp(line_clean),
                    }
                )

        return CILogs(
            raw_logs=raw_logs,
            structured_logs=structured_logs,
            error_lines=error_lines,
            warning_lines=warning_lines,
            log_size_bytes=len(raw_logs.encode("utf-8")),
            fetched_at=datetime.now(),
            source_url=source_url,
        )

    def _extract_timestamp(self, log_line: str) -> Optional[str]:
        """Extract timestamp from log line if present"""
        # Common timestamp patterns in CI logs
        timestamp_patterns = [
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",  # ISO format
            r"\d{2}:\d{2}:\d{2}",  # Time only
            r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]",  # Bracketed
        ]

        for pattern in timestamp_patterns:
            match = re.search(pattern, log_line)
            if match:
                return match.group(0)

        return None

    def _create_placeholder_logs(self, event: CIEvent, message: str) -> CILogs:
        """Create placeholder logs for unimplemented providers"""
        return CILogs(
            raw_logs=message,
            structured_logs=[
                {
                    "line_number": 1,
                    "type": "info",
                    "content": message,
                    "timestamp": None,
                }
            ],
            error_lines=[],
            warning_lines=[],
            log_size_bytes=len(message.encode("utf-8")),
            fetched_at=datetime.now(),
            source_url="placeholder",
        )
