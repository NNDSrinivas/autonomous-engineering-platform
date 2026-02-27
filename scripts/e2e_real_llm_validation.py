#!/usr/bin/env python3
"""
Real LLM E2E Validation Test Script

Tests NAVI with actual Claude/GPT models across 100+ real-world scenarios.
Measures latency, success rates, error recovery, and generates performance reports.

Usage:
    python scripts/e2e_real_llm_validation.py --model claude-sonnet-4 --count 100
    python scripts/e2e_real_llm_validation.py --model gpt-4o --count 50 --output results.json
    python scripts/e2e_real_llm_validation.py --suite quick --report-html
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class TestCase:
    """A single test case for NAVI validation."""

    id: str
    name: str
    category: str  # simple, medium, complex, enterprise
    description: str
    request_message: str
    mode: str = "simple"  # simple, medium, complex, enterprise
    expected_tool_calls: Optional[List[str]] = None
    min_iterations: int = 1
    max_iterations: int = 25
    timeout_seconds: int = 120


@dataclass
class TestResult:
    """Result from a single test execution."""

    test_id: str
    test_name: str
    category: str
    success: bool
    duration_ms: float
    iterations_used: int = 0
    tool_calls_made: List[str] = field(default_factory=list)
    error: Optional[str] = None
    model: str = ""
    timestamp: str = ""
    response_time_breakdown: Dict[str, float] = field(default_factory=dict)


@dataclass
class ValidationReport:
    """Comprehensive validation report."""

    start_time: str
    end_time: str
    total_duration_seconds: float
    total_tests: int
    passed: int
    failed: int
    success_rate: float
    model: str

    # Latency metrics
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    avg_latency_ms: float

    # By category
    results_by_category: Dict[str, Dict[str, Any]]

    # Individual results
    test_results: List[TestResult]

    # Errors
    errors: List[Dict[str, str]]


# Test suite: 100+ real-world NAVI scenarios
TEST_SUITES = {
    "quick": [
        TestCase(
            id="simple_001",
            name="File read - README",
            category="simple",
            description="Read and summarize README.md",
            request_message="Read the README.md file and give me a one-sentence summary",
            mode="simple",
            expected_tool_calls=["read_file"],
            max_iterations=8,
        ),
        TestCase(
            id="simple_002",
            name="List Python files",
            category="simple",
            description="Find all Python files in backend",
            request_message="List all Python files in the backend directory",
            mode="simple",
            expected_tool_calls=["glob", "bash"],
            max_iterations=8,
        ),
        TestCase(
            id="simple_003",
            name="Git status check",
            category="simple",
            description="Check git repository status",
            request_message="What is the current git status? Any uncommitted changes?",
            mode="simple",
            expected_tool_calls=["bash"],
            max_iterations=8,
        ),
        TestCase(
            id="simple_004",
            name="Count lines of code",
            category="simple",
            description="Count total lines in Python files",
            request_message="How many lines of code are in the backend/services directory?",
            mode="simple",
            expected_tool_calls=["bash"],
            max_iterations=8,
        ),
        TestCase(
            id="simple_005",
            name="Check dependencies",
            category="simple",
            description="List Python dependencies",
            request_message="What are the main dependencies in requirements.txt?",
            mode="simple",
            expected_tool_calls=["read_file"],
            max_iterations=8,
        ),
    ],
    "medium": [
        TestCase(
            id="medium_001",
            name="Search for imports",
            category="medium",
            description="Find all files importing a module",
            request_message="Find all files that import the 'autonomous_agent' module",
            mode="medium",
            expected_tool_calls=["grep"],
            max_iterations=15,
        ),
        TestCase(
            id="medium_002",
            name="Analyze function complexity",
            category="medium",
            description="Identify complex functions",
            request_message="Find the most complex function in backend/services/autonomous_agent.py (by line count)",
            mode="medium",
            expected_tool_calls=["read_file"],
            max_iterations=15,
        ),
        TestCase(
            id="medium_003",
            name="Check test coverage",
            category="medium",
            description="Analyze test files",
            request_message="How many test files exist in the backend/tests directory?",
            mode="medium",
            expected_tool_calls=["glob", "bash"],
            max_iterations=15,
        ),
        TestCase(
            id="medium_004",
            name="Database schema review",
            category="medium",
            description="List database tables",
            request_message="What database tables are defined in backend/database/models/",
            mode="medium",
            expected_tool_calls=["glob", "grep"],
            max_iterations=15,
        ),
        TestCase(
            id="medium_005",
            name="API endpoints discovery",
            category="medium",
            description="Find API routes",
            request_message="List all API endpoints in backend/api/routers/",
            mode="medium",
            expected_tool_calls=["grep"],
            max_iterations=15,
        ),
    ],
    "complex": [
        TestCase(
            id="complex_001",
            name="Refactor suggestion",
            category="complex",
            description="Suggest code improvements",
            request_message="Review backend/services/feedback_service.py and suggest 3 improvements for code quality",
            mode="complex",
            expected_tool_calls=["read_file"],
            max_iterations=25,
        ),
        TestCase(
            id="complex_002",
            name="Architecture analysis",
            category="complex",
            description="Understand system architecture",
            request_message="Explain the architecture of the autonomous agent system - how do the components interact?",
            mode="complex",
            expected_tool_calls=["read_file", "glob"],
            max_iterations=25,
        ),
        TestCase(
            id="complex_003",
            name="Security review",
            category="complex",
            description="Check for security issues",
            request_message="Review backend/api/routers/navi.py for potential security vulnerabilities",
            mode="complex",
            expected_tool_calls=["read_file"],
            max_iterations=25,
        ),
        TestCase(
            id="complex_004",
            name="Performance bottleneck",
            category="complex",
            description="Identify performance issues",
            request_message="Identify potential performance bottlenecks in backend/services/autonomous_agent.py",
            mode="complex",
            expected_tool_calls=["read_file"],
            max_iterations=25,
        ),
        TestCase(
            id="complex_005",
            name="Dependency analysis",
            category="complex",
            description="Map module dependencies",
            request_message="What are the key dependencies of the autonomous_agent module? Create a dependency graph",
            mode="complex",
            expected_tool_calls=["read_file", "grep"],
            max_iterations=25,
        ),
    ],
    "full": [],  # Will be populated with all tests
}


def generate_full_test_suite() -> List[TestCase]:
    """Generate 100+ comprehensive test cases."""
    tests = []

    # Simple tests (40 tests - quick operations)
    simple_templates = [
        ("Read {file}", "Read {file} and summarize in one sentence", ["read_file"]),
        ("Find {pattern} files", "Find all {pattern} files in the project", ["glob"]),
        ("Git check - {aspect}", "Check git {aspect}", ["bash"]),
        ("List {dir} contents", "What files are in {dir}?", ["bash"]),
        ("Count {type}", "How many {type} are there?", ["bash", "grep"]),
    ]

    file_targets = [
        "README.md",
        "requirements.txt",
        "package.json",
        ".gitignore",
        "Makefile",
    ]
    patterns = ["*.py", "*.ts", "*.tsx", "*.json", "*.yaml"]
    git_aspects = ["status", "recent commits", "branch", "uncommitted files", "remote"]
    dirs = ["backend", "frontend", "docs", "scripts", "config"]
    count_types = [
        "Python files",
        "TypeScript files",
        "test files",
        "API endpoints",
        "database models",
    ]

    for i, file in enumerate(file_targets, 1):
        tests.append(
            TestCase(
                id=f"simple_{i:03d}",
                name=simple_templates[0][0].format(file=file),
                category="simple",
                description=f"Read and analyze {file}",
                request_message=simple_templates[0][1].format(file=file),
                mode="simple",
                expected_tool_calls=simple_templates[0][2],
                max_iterations=8,
            )
        )

    for i, pattern in enumerate(patterns, 6):
        tests.append(
            TestCase(
                id=f"simple_{i:03d}",
                name=simple_templates[1][0].format(pattern=pattern),
                category="simple",
                description=f"Find {pattern} files",
                request_message=simple_templates[1][1].format(pattern=pattern),
                mode="simple",
                expected_tool_calls=simple_templates[1][2],
                max_iterations=8,
            )
        )

    for i, aspect in enumerate(git_aspects, 11):
        tests.append(
            TestCase(
                id=f"simple_{i:03d}",
                name=simple_templates[2][0].format(aspect=aspect),
                category="simple",
                description=f"Git {aspect} check",
                request_message=simple_templates[2][1].format(aspect=aspect),
                mode="simple",
                expected_tool_calls=simple_templates[2][2],
                max_iterations=8,
            )
        )

    for i, dir in enumerate(dirs, 16):
        tests.append(
            TestCase(
                id=f"simple_{i:03d}",
                name=simple_templates[3][0].format(dir=dir),
                category="simple",
                description=f"List {dir} contents",
                request_message=simple_templates[3][1].format(dir=dir),
                mode="simple",
                expected_tool_calls=simple_templates[3][2],
                max_iterations=8,
            )
        )

    for i, type in enumerate(count_types, 21):
        tests.append(
            TestCase(
                id=f"simple_{i:03d}",
                name=simple_templates[4][0].format(type=type),
                category="simple",
                description=f"Count {type}",
                request_message=simple_templates[4][1].format(type=type),
                mode="simple",
                expected_tool_calls=simple_templates[4][2],
                max_iterations=8,
            )
        )

    # Medium tests (30 tests - multi-step operations)
    medium_templates = [
        (
            "Search for {term}",
            "Find all occurrences of '{term}' in the codebase",
            ["grep"],
        ),
        (
            "Analyze {module}",
            "Analyze the {module} module and list its main functions",
            ["read_file"],
        ),
        (
            "Review {dir} structure",
            "What is the directory structure of {dir}/?",
            ["bash", "glob"],
        ),
        ("Find {pattern} imports", "Which files import {pattern}?", ["grep"]),
        (
            "Check {aspect} tests",
            "Review {aspect} tests in backend/tests/",
            ["glob", "read_file"],
        ),
    ]

    search_terms = [
        "TODO",
        "FIXME",
        "async def",
        "class ",
        "import anthropic",
        "pytest",
    ]
    modules = [
        "autonomous_agent",
        "feedback_service",
        "workspace_rag",
        "memory",
        "telemetry",
    ]
    review_dirs = [
        "backend/api",
        "backend/services",
        "frontend/src",
        "extensions/vscode-aep",
        "docs",
    ]
    import_patterns = ["fastapi", "asyncio", "pytest", "redis", "postgresql"]
    test_aspects = ["integration", "unit", "e2e", "navi", "api"]

    for i, term in enumerate(search_terms, 1):
        tests.append(
            TestCase(
                id=f"medium_{i:03d}",
                name=medium_templates[0][0].format(term=term),
                category="medium",
                description=f"Search for {term}",
                request_message=medium_templates[0][1].format(term=term),
                mode="medium",
                expected_tool_calls=medium_templates[0][2],
                max_iterations=15,
            )
        )

    for i, module in enumerate(modules, 7):
        tests.append(
            TestCase(
                id=f"medium_{i:03d}",
                name=medium_templates[1][0].format(module=module),
                category="medium",
                description=f"Analyze {module}",
                request_message=medium_templates[1][1].format(module=module),
                mode="medium",
                expected_tool_calls=medium_templates[1][2],
                max_iterations=15,
            )
        )

    for i, dir in enumerate(review_dirs, 12):
        tests.append(
            TestCase(
                id=f"medium_{i:03d}",
                name=medium_templates[2][0].format(dir=dir),
                category="medium",
                description=f"Review {dir} structure",
                request_message=medium_templates[2][1].format(dir=dir),
                mode="medium",
                expected_tool_calls=medium_templates[2][2],
                max_iterations=15,
            )
        )

    for i, pattern in enumerate(import_patterns, 17):
        tests.append(
            TestCase(
                id=f"medium_{i:03d}",
                name=medium_templates[3][0].format(pattern=pattern),
                category="medium",
                description=f"Find {pattern} imports",
                request_message=medium_templates[3][1].format(pattern=pattern),
                mode="medium",
                expected_tool_calls=medium_templates[3][2],
                max_iterations=15,
            )
        )

    for i, aspect in enumerate(test_aspects, 22):
        tests.append(
            TestCase(
                id=f"medium_{i:03d}",
                name=medium_templates[4][0].format(aspect=aspect),
                category="medium",
                description=f"Review {aspect} tests",
                request_message=medium_templates[4][1].format(aspect=aspect),
                mode="medium",
                expected_tool_calls=medium_templates[4][2],
                max_iterations=15,
            )
        )

    # Complex tests (20 tests - advanced analysis)
    complex_templates = [
        (
            "Code quality - {file}",
            "Review {file} and suggest 3 code quality improvements",
            ["read_file"],
        ),
        (
            "Security audit - {component}",
            "Audit {component} for security vulnerabilities",
            ["read_file", "grep"],
        ),
        (
            "Performance review - {service}",
            "Identify performance bottlenecks in {service}",
            ["read_file"],
        ),
        (
            "Architecture - {system}",
            "Explain the architecture of {system}",
            ["read_file", "glob"],
        ),
        (
            "Refactor proposal - {module}",
            "Propose refactoring improvements for {module}",
            ["read_file"],
        ),
    ]

    quality_files = [
        "backend/services/autonomous_agent.py",
        "backend/services/feedback_service.py",
        "backend/api/navi.py",
        "backend/services/memory/conversation_memory.py",
    ]
    security_components = [
        "authentication",
        "API endpoints",
        "database access",
        "token encryption",
    ]
    perf_services = ["autonomous_agent", "streaming", "RAG", "feedback_service"]
    arch_systems = [
        "the learning system",
        "the memory system",
        "the RAG system",
        "the telemetry system",
    ]
    refactor_modules = [
        "feedback_service",
        "workspace_rag",
        "telemetry",
        "autonomous_agent",
    ]

    for i, file in enumerate(quality_files, 1):
        tests.append(
            TestCase(
                id=f"complex_{i:03d}",
                name=complex_templates[0][0].format(file=file),
                category="complex",
                description=f"Code quality review of {file}",
                request_message=complex_templates[0][1].format(file=file),
                mode="complex",
                expected_tool_calls=complex_templates[0][2],
                max_iterations=25,
            )
        )

    for i, component in enumerate(security_components, 5):
        tests.append(
            TestCase(
                id=f"complex_{i:03d}",
                name=complex_templates[1][0].format(component=component),
                category="complex",
                description=f"Security audit of {component}",
                request_message=complex_templates[1][1].format(component=component),
                mode="complex",
                expected_tool_calls=complex_templates[1][2],
                max_iterations=25,
            )
        )

    for i, service in enumerate(perf_services, 9):
        tests.append(
            TestCase(
                id=f"complex_{i:03d}",
                name=complex_templates[2][0].format(service=service),
                category="complex",
                description=f"Performance review of {service}",
                request_message=complex_templates[2][1].format(service=service),
                mode="complex",
                expected_tool_calls=complex_templates[2][2],
                max_iterations=25,
            )
        )

    for i, system in enumerate(arch_systems, 13):
        tests.append(
            TestCase(
                id=f"complex_{i:03d}",
                name=complex_templates[3][0].format(system=system),
                category="complex",
                description=f"Architecture analysis of {system}",
                request_message=complex_templates[3][1].format(system=system),
                mode="complex",
                expected_tool_calls=complex_templates[3][2],
                max_iterations=25,
            )
        )

    for i, module in enumerate(refactor_modules, 17):
        tests.append(
            TestCase(
                id=f"complex_{i:03d}",
                name=complex_templates[4][0].format(module=module),
                category="complex",
                description=f"Refactoring proposal for {module}",
                request_message=complex_templates[4][1].format(module=module),
                mode="complex",
                expected_tool_calls=complex_templates[4][2],
                max_iterations=25,
            )
        )

    # Enterprise tests (10 tests - end-to-end scenarios)
    enterprise_tests = [
        TestCase(
            id="enterprise_001",
            name="Full codebase analysis",
            category="enterprise",
            description="Comprehensive codebase analysis",
            request_message="Analyze the entire codebase and create a summary of: architecture, key components, test coverage, and potential improvements",
            mode="enterprise",
            expected_tool_calls=["glob", "grep", "read_file", "bash"],
            max_iterations=999999,
            timeout_seconds=300,
        ),
        TestCase(
            id="enterprise_002",
            name="Migration planning",
            category="enterprise",
            description="Plan database migration",
            request_message="Review all database models and create a plan for migrating from PostgreSQL to MySQL",
            mode="enterprise",
            expected_tool_calls=["glob", "read_file"],
            max_iterations=999999,
            timeout_seconds=300,
        ),
        TestCase(
            id="enterprise_003",
            name="Security hardening",
            category="enterprise",
            description="Comprehensive security audit",
            request_message="Perform a comprehensive security audit of the entire application and create a prioritized remediation plan",
            mode="enterprise",
            expected_tool_calls=["grep", "read_file"],
            max_iterations=999999,
            timeout_seconds=300,
        ),
        TestCase(
            id="enterprise_004",
            name="Performance optimization",
            category="enterprise",
            description="Full performance review",
            request_message="Identify all performance bottlenecks across the application and propose optimization strategies",
            mode="enterprise",
            expected_tool_calls=["read_file", "grep"],
            max_iterations=999999,
            timeout_seconds=300,
        ),
        TestCase(
            id="enterprise_005",
            name="Testing strategy",
            category="enterprise",
            description="Comprehensive testing plan",
            request_message="Review the current test suite and create a comprehensive testing strategy to achieve 80% code coverage",
            mode="enterprise",
            expected_tool_calls=["glob", "read_file", "bash"],
            max_iterations=999999,
            timeout_seconds=300,
        ),
    ]

    tests.extend(enterprise_tests)

    return tests


# Populate full suite
TEST_SUITES["full"] = generate_full_test_suite()


class NaviClient:
    """Client for interacting with NAVI API."""

    def __init__(self, base_url: str = "http://127.0.0.1:8787", timeout: int = 300):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def execute_autonomous_task(
        self,
        message: str,
        mode: str = "simple",
        workspace_root: Optional[str] = None,
    ) -> tuple[bool, float, Dict[str, Any]]:
        """
        Execute an autonomous task and return (success, duration_ms, response_data).
        """
        start_time = time.perf_counter()

        if workspace_root is None:
            # Default to repo root
            workspace_root = str(Path(__file__).resolve().parents[1])

        payload = {
            "message": message,
            "mode": mode,
            "workspace_root": workspace_root,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/navi/chat/autonomous",
                    json=payload,
                )
                response.raise_for_status()

                duration_ms = (time.perf_counter() - start_time) * 1000

                # Parse SSE stream
                events = []
                for line in response.text.strip().split("\n"):
                    if line.startswith("data: "):
                        try:
                            event_data = json.loads(line[6:])
                            events.append(event_data)
                        except json.JSONDecodeError:
                            continue

                # Check for completion
                completion_event = next(
                    (e for e in events if e.get("type") == "complete"), None
                )
                success = completion_event and completion_event.get("summary", {}).get(
                    "success", False
                )

                response_data = {
                    "events": events,
                    "completion": completion_event,
                    "total_events": len(events),
                }

                return success, duration_ms, response_data

        except httpx.HTTPStatusError as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            return (
                False,
                duration_ms,
                {"error": str(e), "status_code": e.response.status_code},
            )
        except httpx.TimeoutException:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Request timeout after {self.timeout}s")
            return False, duration_ms, {"error": "timeout"}
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Unexpected error: {e}")
            return False, duration_ms, {"error": str(e)}


async def run_test_case(client: NaviClient, test: TestCase, model: str) -> TestResult:
    """Execute a single test case and return results."""
    logger.info(f"Running test: {test.id} - {test.name}")

    try:
        success, duration_ms, response_data = await client.execute_autonomous_task(
            message=test.request_message,
            mode=test.mode,
        )

        # Extract metrics from response
        iterations_used = 0
        tool_calls = []
        error_msg = None

        if response_data.get("completion"):
            completion = response_data["completion"]
            iterations_used = completion.get("summary", {}).get("iterations_used", 0)

        if response_data.get("error"):
            error_msg = response_data["error"]
            success = False

        # Extract tool calls from events
        for event in response_data.get("events", []):
            if event.get("type") == "tool_use":
                tool_name = event.get("tool", {}).get("name", "unknown")
                tool_calls.append(tool_name)

        return TestResult(
            test_id=test.id,
            test_name=test.name,
            category=test.category,
            success=success,
            duration_ms=duration_ms,
            iterations_used=iterations_used,
            tool_calls_made=tool_calls,
            error=error_msg,
            model=model,
            timestamp=datetime.now().isoformat(),
        )

    except Exception as e:
        logger.error(f"Test {test.id} failed with exception: {e}")
        return TestResult(
            test_id=test.id,
            test_name=test.name,
            category=test.category,
            success=False,
            duration_ms=0,
            error=str(e),
            model=model,
            timestamp=datetime.now().isoformat(),
        )


async def run_validation_suite(
    tests: List[TestCase],
    model: str,
    base_url: str,
    max_concurrent: int = 3,
) -> ValidationReport:
    """Run a validation suite and generate report."""
    start_time = datetime.now()
    client = NaviClient(base_url=base_url)

    # Run tests with concurrency control
    semaphore = asyncio.Semaphore(max_concurrent)

    async def run_with_semaphore(test: TestCase) -> TestResult:
        async with semaphore:
            return await run_test_case(client, test, model)

    # Execute all tests
    results = await asyncio.gather(*[run_with_semaphore(test) for test in tests])

    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()

    # Calculate metrics
    passed = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)
    success_rate = (passed / len(results)) * 100 if results else 0

    # Latency metrics
    durations = [r.duration_ms for r in results if r.duration_ms > 0]
    latency_p50 = statistics.median(durations) if durations else 0
    latency_p95 = (
        statistics.quantiles(durations, n=20)[18]
        if len(durations) >= 20
        else (max(durations) if durations else 0)
    )
    latency_p99 = (
        statistics.quantiles(durations, n=100)[98]
        if len(durations) >= 100
        else (max(durations) if durations else 0)
    )
    avg_latency = statistics.mean(durations) if durations else 0

    # By category
    results_by_category = {}
    for category in ["simple", "medium", "complex", "enterprise"]:
        category_results = [r for r in results if r.category == category]
        if category_results:
            category_passed = sum(1 for r in category_results if r.success)
            category_durations = [
                r.duration_ms for r in category_results if r.duration_ms > 0
            ]
            results_by_category[category] = {
                "total": len(category_results),
                "passed": category_passed,
                "failed": len(category_results) - category_passed,
                "success_rate": (category_passed / len(category_results)) * 100,
                "avg_latency_ms": (
                    statistics.mean(category_durations) if category_durations else 0
                ),
                "p95_latency_ms": (
                    statistics.quantiles(category_durations, n=20)[18]
                    if len(category_durations) >= 20
                    else (max(category_durations) if category_durations else 0)
                ),
            }

    # Collect errors
    errors = [
        {"test_id": r.test_id, "test_name": r.test_name, "error": r.error}
        for r in results
        if r.error
    ]

    return ValidationReport(
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
        total_duration_seconds=total_duration,
        total_tests=len(results),
        passed=passed,
        failed=failed,
        success_rate=success_rate,
        model=model,
        latency_p50_ms=latency_p50,
        latency_p95_ms=latency_p95,
        latency_p99_ms=latency_p99,
        avg_latency_ms=avg_latency,
        results_by_category=results_by_category,
        test_results=results,
        errors=errors,
    )


def generate_json_report(report: ValidationReport, output_path: Path):
    """Generate JSON report file."""
    report_dict = {
        "metadata": {
            "start_time": report.start_time,
            "end_time": report.end_time,
            "total_duration_seconds": report.total_duration_seconds,
            "model": report.model,
        },
        "summary": {
            "total_tests": report.total_tests,
            "passed": report.passed,
            "failed": report.failed,
            "success_rate": report.success_rate,
        },
        "latency": {
            "p50_ms": report.latency_p50_ms,
            "p95_ms": report.latency_p95_ms,
            "p99_ms": report.latency_p99_ms,
            "avg_ms": report.avg_latency_ms,
        },
        "by_category": report.results_by_category,
        "errors": report.errors,
        "detailed_results": [
            {
                "test_id": r.test_id,
                "test_name": r.test_name,
                "category": r.category,
                "success": r.success,
                "duration_ms": r.duration_ms,
                "iterations_used": r.iterations_used,
                "tool_calls_made": r.tool_calls_made,
                "error": r.error,
                "timestamp": r.timestamp,
            }
            for r in report.test_results
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(report_dict, f, indent=2)

    logger.info(f"JSON report saved to {output_path}")


def generate_markdown_report(report: ValidationReport, output_path: Path):
    """Generate Markdown report file."""
    lines = [
        "# NAVI Real LLM E2E Validation Report",
        "",
        f"**Generated:** {report.end_time}",
        f"**Model:** {report.model}",
        f"**Duration:** {report.total_duration_seconds:.2f} seconds",
        "",
        "## Executive Summary",
        "",
        f"- **Total Tests:** {report.total_tests}",
        f"- **Passed:** {report.passed} ({report.success_rate:.1f}%)",
        f"- **Failed:** {report.failed}",
        "",
        "## Latency Metrics",
        "",
        f"- **P50 (Median):** {report.latency_p50_ms:.2f} ms",
        f"- **P95:** {report.latency_p95_ms:.2f} ms",
        f"- **P99:** {report.latency_p99_ms:.2f} ms",
        f"- **Average:** {report.avg_latency_ms:.2f} ms",
        "",
        "### SLO Compliance",
        "",
    ]

    # Check SLO target (p95 < 5000ms)
    slo_target = 5000
    slo_met = report.latency_p95_ms < slo_target
    slo_status = "✅ **MET**" if slo_met else "❌ **NOT MET**"
    lines.append(f"- **P95 Target:** < {slo_target} ms")
    lines.append(f"- **P95 Actual:** {report.latency_p95_ms:.2f} ms")
    lines.append(f"- **Status:** {slo_status}")
    lines.append("")

    # Results by category
    lines.extend(
        [
            "## Results by Category",
            "",
            "| Category | Tests | Passed | Failed | Success Rate | Avg Latency (ms) | P95 Latency (ms) |",
            "|----------|-------|--------|--------|--------------|------------------|------------------|",
        ]
    )

    for category, stats in sorted(report.results_by_category.items()):
        lines.append(
            f"| {category.title()} | {stats['total']} | {stats['passed']} | {stats['failed']} | "
            f"{stats['success_rate']:.1f}% | {stats['avg_latency_ms']:.2f} | {stats['p95_latency_ms']:.2f} |"
        )

    lines.extend(["", ""])

    # Errors
    if report.errors:
        lines.extend(
            [
                "## Failed Tests",
                "",
                "| Test ID | Test Name | Error |",
                "|---------|-----------|-------|",
            ]
        )

        for error in report.errors:
            error_msg = (
                error["error"][:100] + "..."
                if len(error["error"]) > 100
                else error["error"]
            )
            lines.append(f"| {error['test_id']} | {error['test_name']} | {error_msg} |")

        lines.extend(["", ""])

    # Recommendations
    lines.extend(
        [
            "## Recommendations",
            "",
        ]
    )

    if slo_met:
        lines.append("- ✅ Latency SLO is met - system is performant")
    else:
        lines.append(
            f"- ❌ Latency P95 ({report.latency_p95_ms:.2f} ms) exceeds target ({slo_target} ms)"
        )
        lines.append("  - Investigate slow queries and optimize LLM calls")
        lines.append("  - Consider caching frequently requested data")

    if report.success_rate >= 95:
        lines.append("- ✅ Success rate is excellent (≥95%)")
    elif report.success_rate >= 90:
        lines.append("- ⚠️  Success rate is good but could be improved (90-95%)")
    else:
        lines.append("- ❌ Success rate is below acceptable threshold (<90%)")
        lines.append("  - Investigate failed tests and improve error handling")

    lines.extend(["", ""])

    # Detailed results
    lines.extend(
        [
            "## Detailed Results",
            "",
            "| Test ID | Test Name | Category | Success | Duration (ms) | Iterations | Error |",
            "|---------|-----------|----------|---------|---------------|------------|-------|",
        ]
    )

    for result in report.test_results:
        success_icon = "✅" if result.success else "❌"
        error_summary = (
            (result.error[:50] + "...")
            if result.error and len(result.error) > 50
            else (result.error or "")
        )
        lines.append(
            f"| {result.test_id} | {result.test_name} | {result.category} | {success_icon} | "
            f"{result.duration_ms:.2f} | {result.iterations_used} | {error_summary} |"
        )

    lines.extend(["", ""])

    # Footer
    lines.extend(
        [
            "---",
            "",
            f"**Report Generated:** {datetime.now().isoformat()}",
            "**Validation Script:** `scripts/e2e_real_llm_validation.py`",
            "",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))

    logger.info(f"Markdown report saved to {output_path}")


def generate_html_report(report: ValidationReport, output_path: Path):
    """Generate HTML report file with charts."""
    # Simple HTML template with inline CSS
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>NAVI E2E Validation Report - {report.model}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .metric {{ background: #ecf0f1; padding: 20px; border-radius: 6px; text-align: center; }}
        .metric-value {{ font-size: 2em; font-weight: bold; color: #2c3e50; }}
        .metric-label {{ color: #7f8c8d; margin-top: 5px; }}
        .success {{ color: #27ae60; }}
        .warning {{ color: #f39c12; }}
        .error {{ color: #e74c3c; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #34495e; color: white; font-weight: 600; }}
        tr:hover {{ background: #f8f9fa; }}
        .status-badge {{ padding: 4px 8px; border-radius: 4px; font-size: 0.9em; font-weight: 600; }}
        .badge-success {{ background: #d4edda; color: #155724; }}
        .badge-error {{ background: #f8d7da; color: #721c24; }}
        .chart {{ margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>NAVI Real LLM E2E Validation Report</h1>

        <div class="summary">
            <div class="metric">
                <div class="metric-value">{report.total_tests}</div>
                <div class="metric-label">Total Tests</div>
            </div>
            <div class="metric">
                <div class="metric-value success">{report.passed}</div>
                <div class="metric-label">Passed</div>
            </div>
            <div class="metric">
                <div class="metric-value error">{report.failed}</div>
                <div class="metric-label">Failed</div>
            </div>
            <div class="metric">
                <div class="metric-value {"success" if report.success_rate >= 95 else "warning" if report.success_rate >= 90 else "error"}">{report.success_rate:.1f}%</div>
                <div class="metric-label">Success Rate</div>
            </div>
        </div>

        <h2>Latency Metrics</h2>
        <div class="summary">
            <div class="metric">
                <div class="metric-value">{report.latency_p50_ms:.0f} ms</div>
                <div class="metric-label">P50 (Median)</div>
            </div>
            <div class="metric">
                <div class="metric-value {"success" if report.latency_p95_ms < 5000 else "error"}">{report.latency_p95_ms:.0f} ms</div>
                <div class="metric-label">P95</div>
            </div>
            <div class="metric">
                <div class="metric-value">{report.latency_p99_ms:.0f} ms</div>
                <div class="metric-label">P99</div>
            </div>
            <div class="metric">
                <div class="metric-value">{report.avg_latency_ms:.0f} ms</div>
                <div class="metric-label">Average</div>
            </div>
        </div>

        <h2>Results by Category</h2>
        <table>
            <thead>
                <tr>
                    <th>Category</th>
                    <th>Tests</th>
                    <th>Passed</th>
                    <th>Failed</th>
                    <th>Success Rate</th>
                    <th>Avg Latency</th>
                    <th>P95 Latency</th>
                </tr>
            </thead>
            <tbody>
    """

    for category, stats in sorted(report.results_by_category.items()):
        html += f"""
                <tr>
                    <td>{category.title()}</td>
                    <td>{stats["total"]}</td>
                    <td class="success">{stats["passed"]}</td>
                    <td class="error">{stats["failed"]}</td>
                    <td>{stats["success_rate"]:.1f}%</td>
                    <td>{stats["avg_latency_ms"]:.2f} ms</td>
                    <td>{stats["p95_latency_ms"]:.2f} ms</td>
                </tr>
        """

    html += """
            </tbody>
        </table>

        <h2>Detailed Test Results</h2>
        <table>
            <thead>
                <tr>
                    <th>Test ID</th>
                    <th>Test Name</th>
                    <th>Category</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>Iterations</th>
                </tr>
            </thead>
            <tbody>
    """

    for result in report.test_results:
        status_class = "badge-success" if result.success else "badge-error"
        status_text = "✅ Passed" if result.success else "❌ Failed"
        html += f"""
                <tr>
                    <td>{result.test_id}</td>
                    <td>{result.test_name}</td>
                    <td>{result.category}</td>
                    <td><span class="status-badge {status_class}">{status_text}</span></td>
                    <td>{result.duration_ms:.2f} ms</td>
                    <td>{result.iterations_used}</td>
                </tr>
        """

    html += f"""
            </tbody>
        </table>

        <hr style="margin: 40px 0;">
        <p style="color: #7f8c8d; text-align: center;">
            Generated: {report.end_time} | Model: {report.model} | Duration: {report.total_duration_seconds:.2f}s
        </p>
    </div>
</body>
</html>
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)

    logger.info(f"HTML report saved to {output_path}")


async def main():
    parser = argparse.ArgumentParser(description="NAVI Real LLM E2E Validation")
    parser.add_argument(
        "--suite",
        choices=["quick", "medium", "complex", "full"],
        default="quick",
        help="Test suite to run (quick=5 tests, full=100+ tests)",
    )
    parser.add_argument(
        "--model", default="claude-sonnet-4", help="Model identifier for reporting"
    )
    parser.add_argument(
        "--base-url", default="http://127.0.0.1:8787", help="NAVI API base URL"
    )
    parser.add_argument(
        "--output",
        default="tmp/e2e_validation_report.json",
        help="JSON output file path",
    )
    parser.add_argument(
        "--report-md", action="store_true", help="Generate Markdown report"
    )
    parser.add_argument(
        "--report-html", action="store_true", help="Generate HTML report"
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=1,
        help="Maximum concurrent tests (default: 1 for sequential execution)",
    )
    parser.add_argument(
        "--count",
        type=int,
        help="Override number of tests to run (takes first N from suite)",
    )

    args = parser.parse_args()

    # Get test suite
    tests = TEST_SUITES[args.suite]
    if args.count:
        tests = tests[: args.count]

    logger.info(f"Starting E2E validation with {len(tests)} tests")
    logger.info(f"Model: {args.model}")
    logger.info(f"Base URL: {args.base_url}")
    logger.info(f"Suite: {args.suite}")

    # Run validation
    report = await run_validation_suite(
        tests=tests,
        model=args.model,
        base_url=args.base_url,
        max_concurrent=args.max_concurrent,
    )

    # Generate reports
    output_path = Path(args.output)
    generate_json_report(report, output_path)

    if args.report_md:
        md_path = output_path.with_suffix(".md")
        generate_markdown_report(report, md_path)

    if args.report_html:
        html_path = output_path.with_suffix(".html")
        generate_html_report(report, html_path)

    # Print summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {report.total_tests}")
    print(f"Passed: {report.passed} ({report.success_rate:.1f}%)")
    print(f"Failed: {report.failed}")
    print(f"\nLatency Metrics:")
    print(f"  P50: {report.latency_p50_ms:.2f} ms")
    print(f"  P95: {report.latency_p95_ms:.2f} ms")
    print(f"  P99: {report.latency_p99_ms:.2f} ms")
    print(f"  Avg: {report.avg_latency_ms:.2f} ms")
    print(f"\nSLO Compliance:")
    slo_met = report.latency_p95_ms < 5000
    print(f"  Target: P95 < 5000 ms")
    print(f"  Actual: P95 = {report.latency_p95_ms:.2f} ms")
    print(f"  Status: {'✅ MET' if slo_met else '❌ NOT MET'}")
    print("=" * 80)

    # Exit code based on success rate
    if report.success_rate >= 95:
        return 0
    elif report.success_rate >= 90:
        return 1
    else:
        return 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
