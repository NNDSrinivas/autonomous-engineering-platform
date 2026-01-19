"""
Test Executor - Integrated Test Execution and Verification

Provides:
1. Automatic test discovery
2. Test execution across frameworks
3. Coverage analysis
4. Test result parsing
5. Failure diagnosis and auto-fix suggestions

NAVI uses this to verify code works after generating it.
"""

import os
import re
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ============================================================
# DATA CLASSES
# ============================================================

class TestStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    PENDING = "pending"


class TestFramework(Enum):
    PYTEST = "pytest"
    JEST = "jest"
    VITEST = "vitest"
    MOCHA = "mocha"
    JUNIT = "junit"
    GO_TEST = "go_test"
    CARGO_TEST = "cargo_test"
    RSPEC = "rspec"
    PHPUNIT = "phpunit"
    DOTNET_TEST = "dotnet_test"
    UNKNOWN = "unknown"


@dataclass
class TestCase:
    """A single test case result"""
    name: str
    status: TestStatus
    duration_ms: float = 0.0
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    stdout: Optional[str] = None


@dataclass
class TestSuiteResult:
    """Results from running a test suite"""
    framework: TestFramework
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_ms: float = 0.0
    test_cases: List[TestCase] = field(default_factory=list)
    coverage_percent: Optional[float] = None
    coverage_details: Optional[Dict[str, Any]] = None
    raw_output: str = ""
    command_run: str = ""
    exit_code: int = 0

    @property
    def success(self) -> bool:
        return self.failed == 0 and self.errors == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "framework": self.framework.value,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "coverage_percent": self.coverage_percent,
            "test_cases": [
                {
                    "name": tc.name,
                    "status": tc.status.value,
                    "duration_ms": tc.duration_ms,
                    "file_path": tc.file_path,
                    "error_message": tc.error_message,
                }
                for tc in self.test_cases
            ],
            "failed_tests": [
                {
                    "name": tc.name,
                    "error_message": tc.error_message,
                    "stack_trace": tc.stack_trace[:500] if tc.stack_trace else None,
                    "file_path": tc.file_path,
                    "line_number": tc.line_number,
                }
                for tc in self.test_cases
                if tc.status == TestStatus.FAILED
            ],
        }


@dataclass
class TestDiscovery:
    """Results of test discovery"""
    framework: TestFramework
    test_files: List[str] = field(default_factory=list)
    test_count: int = 0
    config_file: Optional[str] = None


# ============================================================
# FRAMEWORK DETECTION
# ============================================================

class FrameworkDetector:
    """Detect which test framework a project uses"""

    # Config files that indicate test frameworks
    FRAMEWORK_INDICATORS = {
        TestFramework.PYTEST: ["pytest.ini", "pyproject.toml", "setup.cfg", "conftest.py"],
        TestFramework.JEST: ["jest.config.js", "jest.config.ts", "jest.config.json"],
        TestFramework.VITEST: ["vitest.config.js", "vitest.config.ts", "vite.config.ts"],
        TestFramework.MOCHA: [".mocharc.js", ".mocharc.json", ".mocharc.yml"],
        TestFramework.JUNIT: ["pom.xml", "build.gradle", "build.gradle.kts"],
        TestFramework.GO_TEST: ["go.mod"],
        TestFramework.CARGO_TEST: ["Cargo.toml"],
        TestFramework.RSPEC: [".rspec", "spec/spec_helper.rb"],
        TestFramework.PHPUNIT: ["phpunit.xml", "phpunit.xml.dist"],
        TestFramework.DOTNET_TEST: ["*.csproj", "*.sln"],
    }

    # Package.json dependencies that indicate frameworks
    NPM_INDICATORS = {
        "jest": TestFramework.JEST,
        "vitest": TestFramework.VITEST,
        "mocha": TestFramework.MOCHA,
        "@jest/core": TestFramework.JEST,
    }

    @classmethod
    def detect_framework(cls, workspace_path: str) -> TestFramework:
        """Detect the primary test framework in a workspace"""
        # Check for config files
        for framework, indicators in cls.FRAMEWORK_INDICATORS.items():
            for indicator in indicators:
                if "*" in indicator:
                    # Glob pattern
                    matches = list(Path(workspace_path).glob(indicator))
                    if matches:
                        return framework
                else:
                    if os.path.exists(os.path.join(workspace_path, indicator)):
                        return framework

        # Check package.json for JS/TS projects
        package_json_path = os.path.join(workspace_path, "package.json")
        if os.path.exists(package_json_path):
            try:
                with open(package_json_path) as f:
                    package = json.load(f)

                deps = {}
                deps.update(package.get("dependencies", {}))
                deps.update(package.get("devDependencies", {}))

                for dep, framework in cls.NPM_INDICATORS.items():
                    if dep in deps:
                        return framework
            except Exception:
                pass

        # Check for Python test files
        for root, dirs, files in os.walk(workspace_path):
            dirs[:] = [d for d in dirs if d not in ["node_modules", ".git", "__pycache__", "venv"]]
            for f in files:
                if f.startswith("test_") and f.endswith(".py"):
                    return TestFramework.PYTEST
                if f.endswith(".test.ts") or f.endswith(".test.js") or f.endswith(".spec.ts"):
                    return TestFramework.JEST  # Default for TS/JS
            break  # Only check top-level

        return TestFramework.UNKNOWN

    @classmethod
    def discover_tests(cls, workspace_path: str) -> TestDiscovery:
        """Discover test files in a workspace"""
        framework = cls.detect_framework(workspace_path)

        test_files = []
        patterns = cls._get_test_patterns(framework)

        for root, dirs, files in os.walk(workspace_path):
            # Skip common non-test directories
            dirs[:] = [d for d in dirs if d not in [
                "node_modules", ".git", "__pycache__", "venv", ".venv",
                "dist", "build", "coverage", ".next"
            ]]

            for f in files:
                for pattern in patterns:
                    if pattern.startswith("*"):
                        if f.endswith(pattern[1:]):
                            test_files.append(os.path.join(root, f))
                            break
                    elif pattern.endswith("*"):
                        if f.startswith(pattern[:-1]):
                            test_files.append(os.path.join(root, f))
                            break

        return TestDiscovery(
            framework=framework,
            test_files=test_files,
            test_count=len(test_files),
        )

    @classmethod
    def _get_test_patterns(cls, framework: TestFramework) -> List[str]:
        """Get file patterns for test files"""
        patterns = {
            TestFramework.PYTEST: ["test_*", "*_test.py"],
            TestFramework.JEST: ["*.test.js", "*.test.ts", "*.test.tsx", "*.spec.js", "*.spec.ts"],
            TestFramework.VITEST: ["*.test.js", "*.test.ts", "*.spec.js", "*.spec.ts"],
            TestFramework.MOCHA: ["*.test.js", "*.spec.js"],
            TestFramework.JUNIT: ["*Test.java", "*Tests.java"],
            TestFramework.GO_TEST: ["*_test.go"],
            TestFramework.CARGO_TEST: ["*.rs"],  # Rust tests are inline
            TestFramework.RSPEC: ["*_spec.rb"],
            TestFramework.PHPUNIT: ["*Test.php"],
            TestFramework.DOTNET_TEST: ["*Tests.cs", "*Test.cs"],
        }
        return patterns.get(framework, ["test_*", "*.test.*", "*.spec.*"])


# ============================================================
# TEST RUNNERS
# ============================================================

class TestRunner:
    """Execute tests and parse results"""

    # Commands for each framework
    FRAMEWORK_COMMANDS = {
        TestFramework.PYTEST: "python -m pytest -v --tb=short",
        TestFramework.JEST: "npx jest --json",
        TestFramework.VITEST: "npx vitest run --reporter=json",
        TestFramework.MOCHA: "npx mocha --reporter json",
        TestFramework.JUNIT: "mvn test -B",
        TestFramework.GO_TEST: "go test -v -json ./...",
        TestFramework.CARGO_TEST: "cargo test -- --test-threads=1",
        TestFramework.RSPEC: "bundle exec rspec --format json",
        TestFramework.PHPUNIT: "vendor/bin/phpunit --log-junit results.xml",
        TestFramework.DOTNET_TEST: "dotnet test --logger 'trx'",
    }

    # Coverage commands
    COVERAGE_COMMANDS = {
        TestFramework.PYTEST: "python -m pytest --cov --cov-report=json",
        TestFramework.JEST: "npx jest --coverage --json",
        TestFramework.VITEST: "npx vitest run --coverage --reporter=json",
        TestFramework.GO_TEST: "go test -v -cover -json ./...",
        TestFramework.CARGO_TEST: "cargo tarpaulin --out json",
    }

    @classmethod
    async def run_tests(
        cls,
        workspace_path: str,
        framework: Optional[TestFramework] = None,
        test_filter: Optional[str] = None,
        with_coverage: bool = False,
        timeout: int = 300,
        env: Optional[Dict[str, str]] = None,
    ) -> TestSuiteResult:
        """
        Run tests in a workspace.

        Args:
            workspace_path: Path to the workspace
            framework: Test framework (auto-detected if None)
            test_filter: Filter to run specific tests
            with_coverage: Whether to collect coverage
            timeout: Timeout in seconds
            env: Additional environment variables
        """
        if not framework:
            framework = FrameworkDetector.detect_framework(workspace_path)

        if framework == TestFramework.UNKNOWN:
            return TestSuiteResult(
                framework=framework,
                raw_output="No test framework detected",
                exit_code=1,
            )

        # Build command
        if with_coverage and framework in cls.COVERAGE_COMMANDS:
            command = cls.COVERAGE_COMMANDS[framework]
        else:
            command = cls.FRAMEWORK_COMMANDS.get(framework, "")

        if not command:
            return TestSuiteResult(
                framework=framework,
                raw_output=f"No test command for {framework.value}",
                exit_code=1,
            )

        # Add filter if provided
        if test_filter:
            command = cls._add_filter_to_command(command, framework, test_filter)

        # Run the command
        result = await cls._execute_command(
            command,
            workspace_path,
            timeout,
            env,
        )

        # Parse results
        parsed = cls._parse_output(result, framework)
        parsed.command_run = command

        return parsed

    @classmethod
    async def run_single_test(
        cls,
        workspace_path: str,
        test_path: str,
        test_name: Optional[str] = None,
    ) -> TestSuiteResult:
        """Run a single test file or test case"""
        framework = FrameworkDetector.detect_framework(workspace_path)

        # Build specific test command
        if framework == TestFramework.PYTEST:
            command = f"python -m pytest -v {test_path}"
            if test_name:
                command += f"::{test_name}"
        elif framework in [TestFramework.JEST, TestFramework.VITEST]:
            command = f"npx {'jest' if framework == TestFramework.JEST else 'vitest'} {test_path}"
            if test_name:
                command += f" -t '{test_name}'"
        elif framework == TestFramework.GO_TEST:
            command = f"go test -v -run {test_name or '.'} {test_path}"
        else:
            # Generic fallback
            command = cls.FRAMEWORK_COMMANDS.get(framework, "")

        result = await cls._execute_command(command, workspace_path, 60)
        parsed = cls._parse_output(result, framework)
        parsed.command_run = command

        return parsed

    @classmethod
    async def _execute_command(
        cls,
        command: str,
        workspace_path: str,
        timeout: int,
        env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Execute a test command"""
        # Prepare environment
        run_env = os.environ.copy()
        run_env["CI"] = "true"  # Many test frameworks behave better in CI mode
        if env:
            run_env.update(env)

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=workspace_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=run_env,
            )

            try:
                stdout, _ = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
                output = stdout.decode("utf-8", errors="replace")
                exit_code = process.returncode or 0

            except asyncio.TimeoutError:
                process.kill()
                output = "Test execution timed out"
                exit_code = 124

        except Exception as e:
            output = f"Failed to execute tests: {str(e)}"
            exit_code = 1

        return {
            "output": output,
            "exit_code": exit_code,
            "command": command,
        }

    @classmethod
    def _add_filter_to_command(cls, command: str, framework: TestFramework, filter_str: str) -> str:
        """Add a test filter to the command"""
        if framework == TestFramework.PYTEST:
            return f"{command} -k '{filter_str}'"
        elif framework in [TestFramework.JEST, TestFramework.VITEST]:
            return f"{command} -t '{filter_str}'"
        elif framework == TestFramework.GO_TEST:
            return f"{command} -run '{filter_str}'"
        return command

    @classmethod
    def _parse_output(cls, result: Dict[str, Any], framework: TestFramework) -> TestSuiteResult:
        """Parse test output into structured results"""
        output = result["output"]
        exit_code = result["exit_code"]

        suite = TestSuiteResult(
            framework=framework,
            raw_output=output,
            exit_code=exit_code,
        )

        # Framework-specific parsing
        if framework == TestFramework.PYTEST:
            return cls._parse_pytest(suite, output)
        elif framework in [TestFramework.JEST, TestFramework.VITEST]:
            return cls._parse_jest(suite, output)
        elif framework == TestFramework.GO_TEST:
            return cls._parse_go_test(suite, output)
        else:
            return cls._parse_generic(suite, output)

    @classmethod
    def _parse_pytest(cls, suite: TestSuiteResult, output: str) -> TestSuiteResult:
        """Parse pytest output"""
        # Parse summary line: "3 passed, 1 failed, 1 skipped in 1.23s"
        # Each component can appear in any order, so match them individually

        passed_match = re.search(r'(\d+)\s+passed', output)
        failed_match = re.search(r'(\d+)\s+failed', output)
        skipped_match = re.search(r'(\d+)\s+skipped', output)
        error_match = re.search(r'(\d+)\s+error', output)
        duration_match = re.search(r'in\s+([\d.]+)s', output)

        suite.passed = int(passed_match.group(1)) if passed_match else 0
        suite.failed = int(failed_match.group(1)) if failed_match else 0
        suite.skipped = int(skipped_match.group(1)) if skipped_match else 0
        suite.errors = int(error_match.group(1)) if error_match else 0
        suite.duration_ms = float(duration_match.group(1)) * 1000 if duration_match else 0.0
        suite.total = suite.passed + suite.failed + suite.skipped + suite.errors

        # Parse individual test results
        # Format: "test_file.py::test_name PASSED" or "FAILED"
        for match in re.finditer(r'([\w/]+\.py)::(\w+)\s+(PASSED|FAILED|SKIPPED|ERROR)', output):
            file_path, test_name, status = match.groups()
            status_map = {
                "PASSED": TestStatus.PASSED,
                "FAILED": TestStatus.FAILED,
                "SKIPPED": TestStatus.SKIPPED,
                "ERROR": TestStatus.ERROR,
            }

            test_case = TestCase(
                name=test_name,
                status=status_map.get(status, TestStatus.PENDING),
                file_path=file_path,
            )

            # Try to extract error message for failed tests
            if status == "FAILED":
                error_match = re.search(
                    rf'{re.escape(test_name)}.*?(?:AssertionError|Error|Exception):\s*(.+?)(?:\n|$)',
                    output,
                    re.DOTALL,
                )
                if error_match:
                    test_case.error_message = error_match.group(1).strip()[:500]

            suite.test_cases.append(test_case)

        # Parse coverage if present
        cov_match = re.search(r'TOTAL\s+\d+\s+\d+\s+(\d+)%', output)
        if cov_match:
            suite.coverage_percent = float(cov_match.group(1))

        return suite

    @classmethod
    def _parse_jest(cls, suite: TestSuiteResult, output: str) -> TestSuiteResult:
        """Parse Jest/Vitest JSON output"""
        # Try to find JSON in output
        json_match = re.search(r'\{[\s\S]*"numTotalTests"[\s\S]*\}', output)

        if json_match:
            try:
                data = json.loads(json_match.group(0))
                suite.total = data.get("numTotalTests", 0)
                suite.passed = data.get("numPassedTests", 0)
                suite.failed = data.get("numFailedTests", 0)
                suite.skipped = data.get("numPendingTests", 0)

                # Parse test results
                for test_result in data.get("testResults", []):
                    for assertion in test_result.get("assertionResults", []):
                        status_map = {
                            "passed": TestStatus.PASSED,
                            "failed": TestStatus.FAILED,
                            "pending": TestStatus.SKIPPED,
                        }

                        test_case = TestCase(
                            name=assertion.get("title", "unknown"),
                            status=status_map.get(assertion.get("status"), TestStatus.PENDING),
                            file_path=test_result.get("name"),
                            duration_ms=assertion.get("duration", 0),
                        )

                        if assertion.get("failureMessages"):
                            test_case.error_message = "\n".join(assertion["failureMessages"])[:500]

                        suite.test_cases.append(test_case)

                # Coverage
                if "coverageMap" in data:
                    total_lines = 0
                    covered_lines = 0
                    for file_cov in data["coverageMap"].values():
                        for line, count in file_cov.get("s", {}).items():
                            total_lines += 1
                            if count > 0:
                                covered_lines += 1
                    if total_lines > 0:
                        suite.coverage_percent = (covered_lines / total_lines) * 100

                return suite

            except json.JSONDecodeError:
                pass

        # Fallback to regex parsing
        return cls._parse_generic(suite, output)

    @classmethod
    def _parse_go_test(cls, suite: TestSuiteResult, output: str) -> TestSuiteResult:
        """Parse go test output"""
        # Try JSON output first
        for line in output.split("\n"):
            if line.startswith("{"):
                try:
                    data = json.loads(line)
                    if data.get("Action") == "pass":
                        if data.get("Test"):
                            suite.test_cases.append(TestCase(
                                name=data["Test"],
                                status=TestStatus.PASSED,
                                duration_ms=data.get("Elapsed", 0) * 1000,
                            ))
                            suite.passed += 1
                    elif data.get("Action") == "fail":
                        if data.get("Test"):
                            suite.test_cases.append(TestCase(
                                name=data["Test"],
                                status=TestStatus.FAILED,
                                duration_ms=data.get("Elapsed", 0) * 1000,
                            ))
                            suite.failed += 1
                except json.JSONDecodeError:
                    continue

        suite.total = suite.passed + suite.failed + suite.skipped

        # Parse coverage
        cov_match = re.search(r'coverage:\s+([\d.]+)%', output)
        if cov_match:
            suite.coverage_percent = float(cov_match.group(1))

        return suite

    @classmethod
    def _parse_generic(cls, suite: TestSuiteResult, output: str) -> TestSuiteResult:
        """Generic parsing for unknown frameworks"""
        # Count common patterns
        suite.passed = len(re.findall(r'(?:PASS|✓|passed|ok)', output, re.IGNORECASE))
        suite.failed = len(re.findall(r'(?:FAIL|✗|failed|error)', output, re.IGNORECASE))
        suite.total = suite.passed + suite.failed

        return suite


# ============================================================
# FAILURE ANALYZER
# ============================================================

class FailureAnalyzer:
    """Analyze test failures and suggest fixes"""

    @classmethod
    def analyze_failure(cls, test_case: TestCase, workspace_path: str) -> Dict[str, Any]:
        """Analyze a test failure and suggest fixes"""
        analysis = {
            "test_name": test_case.name,
            "file_path": test_case.file_path,
            "error_type": "unknown",
            "root_cause": None,
            "suggested_fixes": [],
            "related_files": [],
        }

        error = test_case.error_message or ""
        stack = test_case.stack_trace or ""

        # Categorize error type
        if "AssertionError" in error or "assert" in error.lower():
            analysis["error_type"] = "assertion"
            analysis["root_cause"] = "Test assertion failed - expected value doesn't match actual"
            analysis["suggested_fixes"] = [
                "Check if the expected value in the test is correct",
                "Verify the function under test is returning the right value",
                "Look for edge cases that might cause unexpected behavior",
            ]

        elif "TypeError" in error:
            analysis["error_type"] = "type_error"
            analysis["root_cause"] = "Type mismatch - wrong type passed to function"
            analysis["suggested_fixes"] = [
                "Check parameter types in the function call",
                "Verify the return type of any called functions",
                "Add type validation or conversion",
            ]

        elif "ImportError" in error or "ModuleNotFoundError" in error:
            analysis["error_type"] = "import_error"
            analysis["root_cause"] = "Missing module or incorrect import"
            analysis["suggested_fixes"] = [
                "Install the missing dependency",
                "Check the import path is correct",
                "Verify the module exists in the project",
            ]

        elif "ConnectionError" in error or "timeout" in error.lower():
            analysis["error_type"] = "connection_error"
            analysis["root_cause"] = "Network/connection issue in test"
            analysis["suggested_fixes"] = [
                "Mock external API calls in tests",
                "Ensure test database is running",
                "Increase timeout values",
            ]

        elif "undefined" in error.lower() or "null" in error.lower():
            analysis["error_type"] = "null_error"
            analysis["root_cause"] = "Null/undefined value encountered"
            analysis["suggested_fixes"] = [
                "Add null checks before accessing properties",
                "Ensure test data is properly initialized",
                "Check for async timing issues",
            ]

        else:
            analysis["error_type"] = "general"
            analysis["root_cause"] = "Test failed - see error message for details"
            analysis["suggested_fixes"] = [
                "Review the error message and stack trace",
                "Check recent changes to the tested code",
                "Verify test setup and teardown",
            ]

        # Extract file references from stack trace
        file_pattern = r'[\w/]+\.(py|js|ts|go|rs|java|rb)(?::\d+)?'
        related_files = list(set(re.findall(file_pattern, stack + error)))
        analysis["related_files"] = related_files[:5]

        return analysis

    @classmethod
    def generate_fix_suggestions(cls, suite: TestSuiteResult) -> List[Dict[str, Any]]:
        """Generate fix suggestions for all failures in a test suite"""
        suggestions = []

        for test_case in suite.test_cases:
            if test_case.status == TestStatus.FAILED:
                analysis = cls.analyze_failure(test_case, "")
                suggestions.append({
                    "test": test_case.name,
                    "analysis": analysis,
                })

        return suggestions


# ============================================================
# PUBLIC API
# ============================================================

async def run_tests(
    workspace_path: str,
    with_coverage: bool = False,
    test_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run all tests in a workspace.

    Returns test results with pass/fail counts and coverage.
    """
    result = await TestRunner.run_tests(
        workspace_path,
        with_coverage=with_coverage,
        test_filter=test_filter,
    )

    response = result.to_dict()

    # Add fix suggestions for failures
    if result.failed > 0:
        response["fix_suggestions"] = FailureAnalyzer.generate_fix_suggestions(result)

    return response


async def run_single_test(
    workspace_path: str,
    test_path: str,
    test_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a single test file or test case"""
    result = await TestRunner.run_single_test(
        workspace_path,
        test_path,
        test_name,
    )
    return result.to_dict()


def discover_tests(workspace_path: str) -> Dict[str, Any]:
    """Discover tests in a workspace"""
    discovery = FrameworkDetector.discover_tests(workspace_path)
    return {
        "framework": discovery.framework.value,
        "test_files": discovery.test_files,
        "test_count": discovery.test_count,
    }


def detect_framework(workspace_path: str) -> str:
    """Detect the test framework used"""
    framework = FrameworkDetector.detect_framework(workspace_path)
    return framework.value


async def verify_tests_pass(workspace_path: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Verify all tests pass.

    Returns (success, results) tuple.
    This is what NAVI uses after generating code to ensure it works.
    """
    result = await run_tests(workspace_path)

    success = result.get("success", False)

    if not success and result.get("failed", 0) > 0:
        # Add diagnostic info
        result["diagnosis"] = "Tests failed - review the failed tests and fix suggestions"
        result["next_steps"] = [
            "Review the error messages for failed tests",
            "Check the suggested fixes",
            "Update the code or tests as needed",
            "Re-run tests to verify fixes",
        ]

    return success, result
