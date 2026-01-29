"""
Test generation tools for NAVI agent.

Provides tools to generate tests for code files, functions, and entire projects.
Supports multiple testing frameworks and languages without hardcoding - dynamically
detects project configuration and generates appropriate tests.
"""

import os
import re
import json
import ast
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


class TestFramework(Enum):
    """Supported testing frameworks"""

    JEST = "jest"
    VITEST = "vitest"
    MOCHA = "mocha"
    PYTEST = "pytest"
    UNITTEST = "unittest"
    PLAYWRIGHT = "playwright"
    CYPRESS = "cypress"
    GO_TEST = "go_test"
    RUST_TEST = "rust_test"


class TestType(Enum):
    """Types of tests"""

    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    SNAPSHOT = "snapshot"
    API = "api"


# Test framework detection patterns
FRAMEWORK_PATTERNS = {
    "jest": {
        "config_files": ["jest.config.js", "jest.config.ts", "jest.config.json"],
        "package_deps": ["jest", "@jest/globals"],
        "import_pattern": r"(from\s+['\"]@jest/globals['\"]|require\(['\"]jest['\"])",
    },
    "vitest": {
        "config_files": ["vitest.config.js", "vitest.config.ts", "vite.config.ts"],
        "package_deps": ["vitest"],
        "import_pattern": r"from\s+['\"]vitest['\"]",
    },
    "mocha": {
        "config_files": [".mocharc.js", ".mocharc.json", "mocharc.yml"],
        "package_deps": ["mocha"],
        "import_pattern": r"(from\s+['\"]mocha['\"]|require\(['\"]mocha['\"])",
    },
    "pytest": {
        "config_files": ["pytest.ini", "pyproject.toml", "setup.cfg"],
        "package_deps": ["pytest"],
        "import_pattern": r"import\s+pytest|from\s+pytest",
    },
    "playwright": {
        "config_files": ["playwright.config.ts", "playwright.config.js"],
        "package_deps": ["@playwright/test", "playwright"],
        "import_pattern": r"from\s+['\"]@playwright/test['\"]",
    },
    "cypress": {
        "config_files": ["cypress.config.js", "cypress.config.ts", "cypress.json"],
        "package_deps": ["cypress"],
        "import_pattern": r"cy\.",
    },
}

# Test templates by framework
TEST_TEMPLATES = {
    "jest": {
        "unit": """import {{ describe, it, expect, beforeEach, afterEach, jest }} from '@jest/globals';
{imports}

describe('{test_name}', () => {{
  beforeEach(() => {{
    // Setup
  }});

  afterEach(() => {{
    // Cleanup
    jest.clearAllMocks();
  }});

{test_cases}
}});
""",
        "test_case": """  it('{description}', {async_keyword}() => {{
    {test_body}
  }});
""",
        "mock": """  jest.mock('{module}', () => ({{
    {mock_implementation}
  }}));
""",
    },
    "vitest": {
        "unit": """import {{ describe, it, expect, beforeEach, afterEach, vi }} from 'vitest';
{imports}

describe('{test_name}', () => {{
  beforeEach(() => {{
    // Setup
  }});

  afterEach(() => {{
    // Cleanup
    vi.clearAllMocks();
  }});

{test_cases}
}});
""",
        "test_case": """  it('{description}', {async_keyword}() => {{
    {test_body}
  }});
""",
        "mock": """  vi.mock('{module}', () => ({{
    {mock_implementation}
  }}));
""",
    },
    "pytest": {
        "unit": '''"""
Tests for {test_name}
"""
import pytest
{imports}


class Test{test_class}:
    """Test class for {test_name}"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup before each test"""
        # Setup
        yield
        # Teardown

{test_cases}
''',
        "test_case": '''    def test_{test_name}(self):
        """{description}"""
        {test_body}
''',
        "async_test_case": '''    @pytest.mark.asyncio
    async def test_{test_name}(self):
        """{description}"""
        {test_body}
''',
        "mock": '''    @pytest.fixture
    def mock_{name}(self, mocker):
        """Mock {name}"""
        return mocker.patch('{module}')
''',
    },
    "playwright": {
        "e2e": """import {{ test, expect }} from '@playwright/test';

test.describe('{test_name}', () => {{
  test.beforeEach(async ({{ page }}) => {{
    // Navigate to page
    await page.goto('/');
  }});

{test_cases}
}});
""",
        "test_case": """  test('{description}', async ({{ page }}) => {{
    {test_body}
  }});
""",
    },
    "cypress": {
        "e2e": """describe('{test_name}', () => {{
  beforeEach(() => {{
    // Navigate to page
    cy.visit('/');
  }});

{test_cases}
}});
""",
        "test_case": """  it('{description}', () => {{
    {test_body}
  }});
""",
    },
}


@dataclass
class CodeFunction:
    """Represents a function/method extracted from code"""

    name: str
    params: List[str]
    return_type: Optional[str]
    is_async: bool
    docstring: Optional[str]
    start_line: int
    end_line: int
    body_preview: str


@dataclass
class CodeClass:
    """Represents a class extracted from code"""

    name: str
    methods: List[CodeFunction]
    docstring: Optional[str]
    start_line: int


async def generate_tests_for_file(
    context: Dict[str, Any],
    file_path: str,
    test_type: str = "unit",
    framework: Optional[str] = None,
    coverage_target: float = 0.8,
    workspace_path: Optional[str] = None,
) -> ToolResult:
    """
    Generate tests for a source code file.

    Analyzes the file to identify testable units (functions, classes, methods)
    and generates comprehensive tests.

    Args:
        file_path: Path to the source file
        test_type: Type of tests (unit, integration, e2e, snapshot, api)
        framework: Testing framework (auto-detected if not specified)
        coverage_target: Target coverage percentage (0.0-1.0)
        workspace_path: Project root directory (for framework detection)

    Returns:
        ToolResult with generated test code
    """
    logger.info(
        "generate_tests_for_file",
        file_path=file_path,
        test_type=test_type,
        framework=framework,
    )

    # Resolve paths
    if workspace_path and not os.path.isabs(file_path):
        full_path = os.path.join(workspace_path, file_path)
    else:
        full_path = file_path
        workspace_path = os.path.dirname(full_path)

    if not os.path.exists(full_path):
        return ToolResult(
            output=f"File not found: {full_path}",
            sources=[],
        )

    # Read source file
    with open(full_path, "r") as f:
        source_code = f.read()

    # Detect language
    _, ext = os.path.splitext(full_path)
    language = _detect_language(ext)

    if not language:
        return ToolResult(
            output=f"Unsupported file type: {ext}\n\nSupported: .ts, .tsx, .js, .jsx, .py",
            sources=[],
        )

    # Detect or validate framework
    if not framework:
        framework = _detect_test_framework(workspace_path, language)

    # Extract testable units
    if language == "python":
        functions, classes = _extract_python_units(source_code)
    else:
        functions, classes = _extract_js_units(source_code)

    if not functions and not classes:
        return ToolResult(
            output=f"No testable units found in {file_path}\n\n"
            f"The file may be:\n"
            f"- A type definition file\n"
            f"- Configuration only\n"
            f"- Already test files",
            sources=[],
        )

    # Generate tests
    test_code = _generate_test_code(
        file_path=file_path,
        functions=functions,
        classes=classes,
        framework=framework,
        test_type=test_type,
        language=language,
        coverage_target=coverage_target,
    )

    # Determine test file path
    test_file_path = _get_test_file_path(file_path, framework, language)

    # Build output
    lines = [f"## Generated Tests for {os.path.basename(file_path)}\n"]
    lines.append(f"**Framework**: {framework}")
    lines.append(f"**Test Type**: {test_type}")
    lines.append(f"**Language**: {language}")
    lines.append(f"**Test File**: `{test_file_path}`")

    # Statistics
    total_functions = len(functions) + sum(len(c.methods) for c in classes)
    lines.append(f"\n**Testable Units Found**: {total_functions}")
    if functions:
        lines.append(f"- Functions: {len(functions)}")
    if classes:
        lines.append(f"- Classes: {len(classes)}")
        for cls in classes:
            lines.append(f"  - {cls.name}: {len(cls.methods)} methods")

    lines.append("\n**Generated Test Code**:")
    lines.append(f"```{language}")
    lines.append(test_code)
    lines.append("```")

    lines.append("\n**Next Steps**:")
    lines.append(f"1. Save to `{test_file_path}`")
    lines.append("2. Review and customize test cases")
    lines.append("3. Add mock implementations as needed")
    lines.append("4. Run tests with `npm test` or `pytest`")

    return ToolResult(output="\n".join(lines), sources=[])


async def generate_tests_for_function(
    context: Dict[str, Any],
    file_path: str,
    function_name: str,
    framework: Optional[str] = None,
    workspace_path: Optional[str] = None,
) -> ToolResult:
    """
    Generate tests for a specific function.

    Args:
        file_path: Path to the source file
        function_name: Name of the function to test
        framework: Testing framework (auto-detected if not specified)
        workspace_path: Project root directory

    Returns:
        ToolResult with generated test code for the function
    """
    logger.info(
        "generate_tests_for_function",
        file_path=file_path,
        function_name=function_name,
    )

    # Resolve paths
    if workspace_path and not os.path.isabs(file_path):
        full_path = os.path.join(workspace_path, file_path)
    else:
        full_path = file_path
        workspace_path = os.path.dirname(full_path)

    if not os.path.exists(full_path):
        return ToolResult(output=f"File not found: {full_path}", sources=[])

    # Read source file
    with open(full_path, "r") as f:
        source_code = f.read()

    # Detect language
    _, ext = os.path.splitext(full_path)
    language = _detect_language(ext)

    if not language:
        return ToolResult(output=f"Unsupported file type: {ext}", sources=[])

    # Detect framework
    if not framework:
        framework = _detect_test_framework(workspace_path, language)

    # Extract function
    if language == "python":
        functions, _ = _extract_python_units(source_code)
    else:
        functions, _ = _extract_js_units(source_code)

    target_func = next((f for f in functions if f.name == function_name), None)

    if not target_func:
        available = [f.name for f in functions]
        return ToolResult(
            output=f"Function '{function_name}' not found in {file_path}\n\n"
            f"Available functions: {', '.join(available) if available else 'None'}",
            sources=[],
        )

    # Generate test for this function
    test_code = _generate_function_test(target_func, framework, language, file_path)

    lines = [f"## Generated Test for `{function_name}`\n"]
    lines.append(f"**Framework**: {framework}")
    lines.append(f"**Function Signature**: `{_format_signature(target_func)}`")
    if target_func.docstring:
        lines.append(f"**Docstring**: {target_func.docstring[:100]}...")
    lines.append("\n**Generated Test Code**:")
    lines.append(f"```{language}")
    lines.append(test_code)
    lines.append("```")

    return ToolResult(output="\n".join(lines), sources=[])


async def generate_test_suite(
    context: Dict[str, Any],
    workspace_path: str,
    scope: str = "changed",
    test_type: str = "unit",
    framework: Optional[str] = None,
) -> ToolResult:
    """
    Generate tests for multiple files in a project.

    Args:
        workspace_path: Project root directory
        scope: Which files to generate tests for ("changed", "all", "directory")
        test_type: Type of tests to generate
        framework: Testing framework (auto-detected if not specified)

    Returns:
        ToolResult with summary of generated tests
    """
    logger.info(
        "generate_test_suite",
        workspace_path=workspace_path,
        scope=scope,
    )

    if not os.path.exists(workspace_path):
        return ToolResult(output=f"Directory not found: {workspace_path}", sources=[])

    # Detect framework
    language = _detect_primary_language(workspace_path)
    if not framework:
        framework = _detect_test_framework(workspace_path, language)

    # Get files to process
    if scope == "changed":
        files = _get_changed_files(workspace_path)
    elif scope == "all":
        files = _get_all_source_files(workspace_path, language)
    else:
        files = _get_all_source_files(workspace_path, language)

    if not files:
        return ToolResult(
            output=f"No source files found to generate tests for.\n\n"
            f"Scope: {scope}\n"
            f"Language: {language}",
            sources=[],
        )

    # Generate summary
    lines = ["## Test Suite Generation\n"]
    lines.append(f"**Scope**: {scope}")
    lines.append(f"**Framework**: {framework}")
    lines.append(f"**Language**: {language}")
    lines.append(f"**Files Found**: {len(files)}")

    lines.append("\n### Files to Process")
    for file in files[:20]:  # Limit display
        test_path = _get_test_file_path(file, framework, language)
        lines.append(f"- `{file}` -> `{test_path}`")

    if len(files) > 20:
        lines.append(f"- ... and {len(files) - 20} more files")

    # Estimate test count
    total_units = 0
    for file in files[:10]:  # Sample
        full_path = os.path.join(workspace_path, file)
        if os.path.exists(full_path):
            with open(full_path, "r") as f:
                source = f.read()
            if language == "python":
                funcs, classes = _extract_python_units(source)
            else:
                funcs, classes = _extract_js_units(source)
            total_units += len(funcs) + sum(len(c.methods) for c in classes)

    avg_units = total_units / min(10, len(files)) if files else 0
    estimated_tests = int(avg_units * len(files))

    lines.append(f"\n**Estimated Test Cases**: ~{estimated_tests}")

    lines.append("\n### Next Steps")
    lines.append("1. Run `test.generate_for_file` for each file")
    lines.append("2. Review and customize generated tests")
    lines.append("3. Run test suite: `npm test` or `pytest`")

    return ToolResult(output="\n".join(lines), sources=[])


async def detect_test_framework(
    context: Dict[str, Any],
    workspace_path: str,
) -> ToolResult:
    """
    Detect the testing framework used in a project.

    Args:
        workspace_path: Project root directory

    Returns:
        ToolResult with detected framework and configuration
    """
    logger.info("detect_test_framework", workspace_path=workspace_path)

    if not os.path.exists(workspace_path):
        return ToolResult(output=f"Directory not found: {workspace_path}", sources=[])

    detected = []

    # Check for framework config files
    for framework, config in FRAMEWORK_PATTERNS.items():
        for config_file in config["config_files"]:
            if os.path.exists(os.path.join(workspace_path, config_file)):
                detected.append(
                    {
                        "framework": framework,
                        "config_file": config_file,
                        "confidence": "high",
                    }
                )

    # Check package.json
    package_json_path = os.path.join(workspace_path, "package.json")
    if os.path.exists(package_json_path):
        try:
            with open(package_json_path, "r") as f:
                pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                for framework, config in FRAMEWORK_PATTERNS.items():
                    for dep in config["package_deps"]:
                        if dep in deps:
                            if not any(d["framework"] == framework for d in detected):
                                detected.append(
                                    {
                                        "framework": framework,
                                        "config_file": f"package.json (dep: {dep})",
                                        "confidence": "medium",
                                    }
                                )
        except (json.JSONDecodeError, IOError):
            pass

    # Check requirements.txt for Python
    requirements_path = os.path.join(workspace_path, "requirements.txt")
    if os.path.exists(requirements_path):
        try:
            with open(requirements_path, "r") as f:
                content = f.read().lower()
                if "pytest" in content:
                    detected.append(
                        {
                            "framework": "pytest",
                            "config_file": "requirements.txt",
                            "confidence": "high",
                        }
                    )
        except IOError:
            pass

    # Build output
    lines = ["## Test Framework Detection\n"]

    if detected:
        primary = detected[0]
        lines.append(f"**Primary Framework**: {primary['framework']}")
        lines.append(f"**Config File**: {primary['config_file']}")
        lines.append(f"**Confidence**: {primary['confidence']}")

        if len(detected) > 1:
            lines.append("\n**Other Frameworks Detected**:")
            for d in detected[1:]:
                lines.append(f"- {d['framework']} (from {d['config_file']})")
    else:
        lines.append("**No testing framework detected**")
        lines.append("\n**Recommendations**:")

        # Check if Node or Python project
        if os.path.exists(package_json_path):
            lines.append("- **Jest**: Most popular for React/Node projects")
            lines.append("  `npm install --save-dev jest @types/jest`")
            lines.append("- **Vitest**: Fast, Vite-native testing")
            lines.append("  `npm install --save-dev vitest`")
        elif os.path.exists(requirements_path):
            lines.append("- **pytest**: Standard Python testing framework")
            lines.append("  `pip install pytest pytest-asyncio`")

    return ToolResult(output="\n".join(lines), sources=[])


async def suggest_test_improvements(
    context: Dict[str, Any],
    test_file_path: str,
    workspace_path: Optional[str] = None,
) -> ToolResult:
    """
    Analyze existing tests and suggest improvements.

    Args:
        test_file_path: Path to test file
        workspace_path: Project root directory

    Returns:
        ToolResult with improvement suggestions
    """
    logger.info("suggest_test_improvements", test_file_path=test_file_path)

    # Resolve path
    if workspace_path and not os.path.isabs(test_file_path):
        full_path = os.path.join(workspace_path, test_file_path)
    else:
        full_path = test_file_path

    if not os.path.exists(full_path):
        return ToolResult(output=f"Test file not found: {full_path}", sources=[])

    with open(full_path, "r") as f:
        test_code = f.read()

    suggestions = []

    # Analyze test structure
    _, ext = os.path.splitext(full_path)
    language = _detect_language(ext)

    # Check for common issues
    if language == "python":
        # Check for assert statements
        if "assert " not in test_code and "self.assert" not in test_code:
            suggestions.append(
                {
                    "type": "missing",
                    "message": "No assertions found - tests should verify behavior",
                    "severity": "high",
                }
            )

        # Check for docstrings
        if '"""' not in test_code and "'''" not in test_code:
            suggestions.append(
                {
                    "type": "documentation",
                    "message": "Consider adding docstrings to describe test purpose",
                    "severity": "low",
                }
            )

        # Check for fixtures
        if "@pytest.fixture" not in test_code:
            suggestions.append(
                {
                    "type": "improvement",
                    "message": "Consider using pytest fixtures for test setup",
                    "severity": "medium",
                }
            )

    else:  # JavaScript/TypeScript
        # Check for expect statements
        if "expect(" not in test_code:
            suggestions.append(
                {
                    "type": "missing",
                    "message": "No expect() assertions found",
                    "severity": "high",
                }
            )

        # Check for async handling
        if "async" in test_code and "await" not in test_code:
            suggestions.append(
                {
                    "type": "bug",
                    "message": "Async function without await - tests may not wait for completion",
                    "severity": "high",
                }
            )

        # Check for error handling tests
        if "throw" not in test_code and "reject" not in test_code:
            suggestions.append(
                {
                    "type": "coverage",
                    "message": "Consider adding tests for error cases",
                    "severity": "medium",
                }
            )

    # Check for edge case patterns
    edge_case_patterns = ["null", "undefined", "empty", "zero", "negative", "boundary"]
    found_edge_cases = sum(
        1 for p in edge_case_patterns if p.lower() in test_code.lower()
    )
    if found_edge_cases < 2:
        suggestions.append(
            {
                "type": "coverage",
                "message": "Consider testing edge cases (null, empty, boundary values)",
                "severity": "medium",
            }
        )

    # Build output
    lines = ["## Test Improvement Suggestions\n"]
    lines.append(f"**File**: {test_file_path}")

    if suggestions:
        lines.append(f"\n**Issues Found**: {len(suggestions)}")
        for s in sorted(
            suggestions, key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["severity"]]
        ):
            icon = {"high": "", "medium": "", "low": ""}[s["severity"]]
            lines.append(f"\n{icon} **{s['type'].title()}** ({s['severity']})")
            lines.append(f"   {s['message']}")
    else:
        lines.append("\nNo obvious issues found. Test file looks good!")

    lines.append("\n### General Best Practices")
    lines.append("- Test one thing per test case")
    lines.append("- Use descriptive test names")
    lines.append("- Test both happy path and error cases")
    lines.append("- Mock external dependencies")
    lines.append("- Keep tests fast and independent")

    return ToolResult(output="\n".join(lines), sources=[])


# Helper functions


def _detect_language(ext: str) -> Optional[str]:
    """Detect programming language from file extension."""
    ext_map = {
        "_ts": "typescript",
        "_tsx": "typescript",
        "_js": "javascript",
        "_jsx": "javascript",
        "_py": "python",
        "_go": "go",
        "_rs": "rust",
    }
    return ext_map.get(ext.lower())


def _detect_test_framework(workspace_path: str, language: str) -> str:
    """Detect testing framework from project configuration."""
    if language in ("typescript", "javascript"):
        # Check for config files
        for framework, config in FRAMEWORK_PATTERNS.items():
            if framework in ("jest", "vitest", "mocha", "playwright", "cypress"):
                for config_file in config["config_files"]:
                    if os.path.exists(os.path.join(workspace_path, config_file)):
                        return framework

        # Check package.json
        package_json_path = os.path.join(workspace_path, "package.json")
        if os.path.exists(package_json_path):
            try:
                with open(package_json_path, "r") as f:
                    pkg = json.load(f)
                    deps = {
                        **pkg.get("dependencies", {}),
                        **pkg.get("devDependencies", {}),
                    }

                    if "vitest" in deps:
                        return "vitest"
                    if "jest" in deps:
                        return "jest"
                    if "@playwright/test" in deps:
                        return "playwright"
                    if "cypress" in deps:
                        return "cypress"
            except (json.JSONDecodeError, IOError):
                pass

        return "jest"  # Default for JS/TS

    elif language == "python":
        return "pytest"

    elif language == "go":
        return "go_test"

    elif language == "rust":
        return "rust_test"

    return "jest"  # Fallback


def _detect_primary_language(workspace_path: str) -> str:
    """Detect primary language of a project."""
    if os.path.exists(os.path.join(workspace_path, "package.json")):
        # Check for TypeScript
        if os.path.exists(os.path.join(workspace_path, "tsconfig.json")):
            return "typescript"
        return "javascript"
    elif os.path.exists(
        os.path.join(workspace_path, "requirements.txt")
    ) or os.path.exists(os.path.join(workspace_path, "pyproject.toml")):
        return "python"
    elif os.path.exists(os.path.join(workspace_path, "go.mod")):
        return "go"
    elif os.path.exists(os.path.join(workspace_path, "Cargo.toml")):
        return "rust"
    return "javascript"  # Default


def _extract_python_units(
    source_code: str,
) -> Tuple[List[CodeFunction], List[CodeClass]]:
    """Extract functions and classes from Python source code."""
    functions = []
    classes = []

    try:
        tree = ast.parse(source_code)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(
                node, ast.AsyncFunctionDef
            ):
                # Skip private functions
                if node.name.startswith("_") and not node.name.startswith("__"):
                    continue

                func = CodeFunction(
                    name=node.name,
                    params=[arg.arg for arg in node.args.args if arg.arg != "self"],
                    return_type=ast.unparse(node.returns) if node.returns else None,
                    is_async=isinstance(node, ast.AsyncFunctionDef),
                    docstring=ast.get_docstring(node),
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    body_preview="",
                )
                functions.append(func)

            elif isinstance(node, ast.ClassDef):
                methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not item.name.startswith("_") or item.name.startswith("__"):
                            method = CodeFunction(
                                name=item.name,
                                params=[
                                    arg.arg
                                    for arg in item.args.args
                                    if arg.arg != "self"
                                ],
                                return_type=(
                                    ast.unparse(item.returns) if item.returns else None
                                ),
                                is_async=isinstance(item, ast.AsyncFunctionDef),
                                docstring=ast.get_docstring(item),
                                start_line=item.lineno,
                                end_line=item.end_lineno or item.lineno,
                                body_preview="",
                            )
                            methods.append(method)

                cls = CodeClass(
                    name=node.name,
                    methods=methods,
                    docstring=ast.get_docstring(node),
                    start_line=node.lineno,
                )
                classes.append(cls)

    except SyntaxError as e:
        logger.warning("Failed to parse Python source", error=str(e))

    return functions, classes


def _extract_js_units(source_code: str) -> Tuple[List[CodeFunction], List[CodeClass]]:
    """Extract functions and classes from JavaScript/TypeScript source code using regex."""
    functions = []
    classes = []

    # Function patterns
    func_patterns = [
        # export function name(params): return
        r"export\s+(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)(?:\s*:\s*([^{]+))?\s*\{",
        # const name = async (params): return =>
        r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)(?:\s*:\s*([^=]+))?\s*=>",
        # function name(params): return
        r"(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)(?:\s*:\s*([^{]+))?\s*\{",
    ]

    for pattern in func_patterns:
        for match in re.finditer(pattern, source_code, re.MULTILINE):
            name = match.group(1)
            params_str = match.group(2)
            return_type = match.group(3).strip() if match.group(3) else None

            # Skip private/test functions
            if name.startswith("_") or name.startswith("test"):
                continue

            params = [
                p.strip().split(":")[0].strip()
                for p in params_str.split(",")
                if p.strip()
            ]
            is_async = "async" in match.group(0)

            func = CodeFunction(
                name=name,
                params=params,
                return_type=return_type,
                is_async=is_async,
                docstring=None,
                start_line=source_code[: match.start()].count("\n") + 1,
                end_line=0,
                body_preview="",
            )
            functions.append(func)

    # Class pattern
    class_pattern = r"(?:export\s+)?class\s+(\w+)(?:\s+extends\s+\w+)?\s*\{"
    for match in re.finditer(class_pattern, source_code, re.MULTILINE):
        name = match.group(1)
        cls = CodeClass(
            name=name,
            methods=[],  # Would need more complex parsing
            docstring=None,
            start_line=source_code[: match.start()].count("\n") + 1,
        )
        classes.append(cls)

    return functions, classes


def _generate_test_code(
    file_path: str,
    functions: List[CodeFunction],
    classes: List[CodeClass],
    framework: str,
    test_type: str,
    language: str,
    coverage_target: float,
) -> str:
    """Generate test code for extracted units."""
    template = TEST_TEMPLATES.get(framework, TEST_TEMPLATES["jest"])
    test_template = template.get(test_type, template.get("unit"))

    test_cases = []

    # Generate test cases for functions
    for func in functions:
        test_case = _generate_function_test_case(func, framework, language)
        test_cases.append(test_case)

    # Generate test cases for class methods
    for cls in classes:
        for method in cls.methods:
            test_case = _generate_function_test_case(
                method, framework, language, cls.name
            )
            test_cases.append(test_case)

    # Build imports
    module_name = os.path.splitext(os.path.basename(file_path))[0]
    if language == "python":
        imports = f"from {module_name} import *"
    else:
        imports = f"import {{ {', '.join(f.name for f in functions)} }} from './{module_name}';"

    # Format final test code
    test_name = module_name.replace("_", " ").replace("-", " ").title()
    test_class = module_name.replace("_", "").replace("-", "").title()

    return test_template.format(
        test_name=test_name,
        test_class=test_class,
        imports=imports,
        test_cases="\n".join(test_cases),
    )


def _generate_function_test_case(
    func: CodeFunction,
    framework: str,
    language: str,
    class_name: Optional[str] = None,
) -> str:
    """Generate a test case for a single function."""
    template = TEST_TEMPLATES.get(framework, TEST_TEMPLATES["jest"])
    test_case_template = template.get(
        "async_test_case" if func.is_async and framework == "pytest" else "test_case"
    )

    # Generate description
    if class_name:
        description = f"{class_name}.{func.name} should work correctly"
    else:
        description = f"{func.name} should work correctly"

    # Generate test body
    if language == "python":
        if func.params:
            params_str = ", ".join(["test_value"] * len(func.params))
            test_body = (
                f"result = {func.name}({params_str})\n        assert result is not None"
            )
        else:
            test_body = f"result = {func.name}()\n        assert result is not None"
    else:
        async_keyword = "async " if func.is_async else ""
        if func.params:
            params_str = ", ".join(["testValue"] * len(func.params))
            test_body = f"const result = {async_keyword.strip() + 'await ' if func.is_async else ''}{func.name}({params_str});\n    expect(result).toBeDefined();"
        else:
            test_body = f"const result = {async_keyword.strip() + 'await ' if func.is_async else ''}{func.name}();\n    expect(result).toBeDefined();"

    return test_case_template.format(
        test_name=func.name,
        description=description,
        test_body=test_body,
        async_keyword="async " if func.is_async and framework != "pytest" else "",
    )


def _generate_function_test(
    func: CodeFunction,
    framework: str,
    language: str,
    file_path: str,
) -> str:
    """Generate a complete test for a single function."""
    test_case = _generate_function_test_case(func, framework, language)

    module_name = os.path.splitext(os.path.basename(file_path))[0]

    if language == "python":
        return f'''"""
Test for {func.name}
"""
import pytest
from {module_name} import {func.name}


class Test{func.name.title().replace("_", "")}:
    """Tests for {func.name}"""

{test_case}

    def test_{func.name}_edge_cases(self):
        """Test edge cases"""
        # TODO: Add edge case tests
        pass

    def test_{func.name}_error_handling(self):
        """Test error handling"""
        # TODO: Add error handling tests
        pass
'''
    else:
        return f"""import {{ describe, it, expect }} from '{framework}';
import {{ {func.name} }} from './{module_name}';

describe('{func.name}', () => {{
{test_case}

  it('should handle edge cases', () => {{
    // TODO: Add edge case tests
  }});

  it('should handle errors', () => {{
    // TODO: Add error handling tests
  }});
}});
"""


def _get_test_file_path(source_path: str, framework: str, language: str) -> str:
    """Generate the test file path for a source file."""
    dirname = os.path.dirname(source_path)
    basename = os.path.basename(source_path)
    name, ext = os.path.splitext(basename)

    if language == "python":
        # Python convention: test_*.py in tests/ or same directory
        return os.path.join("tests", f"test_{name}.py")
    else:
        # JS/TS convention: *.test.ts or *.spec.ts
        if framework == "vitest":
            return os.path.join(dirname, f"{name}.test{ext}")
        elif framework in ("playwright", "cypress"):
            return os.path.join("e2e", f"{name}.spec{ext}")
        else:
            return os.path.join("__tests__", f"{name}.test{ext}")


def _format_signature(func: CodeFunction) -> str:
    """Format a function signature for display."""
    params = ", ".join(func.params) if func.params else ""
    async_prefix = "async " if func.is_async else ""
    return_suffix = f" -> {func.return_type}" if func.return_type else ""
    return f"{async_prefix}{func.name}({params}){return_suffix}"


def _get_changed_files(workspace_path: str) -> List[str]:
    """Get list of changed files from git."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=workspace_path,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            files = [f for f in result.stdout.strip().split("\n") if f]
            # Filter to source files
            return [f for f in files if _detect_language(os.path.splitext(f)[1])]
    except Exception:
        pass
    return []


def _get_all_source_files(workspace_path: str, language: str) -> List[str]:
    """Get all source files in a project."""
    files = []
    extensions = {
        "typescript": [".ts", ".tsx"],
        "javascript": [".js", ".jsx"],
        "python": [".py"],
        "go": [".go"],
        "rust": [".rs"],
    }

    exts = extensions.get(language, extensions["javascript"])

    for root, dirs, filenames in os.walk(workspace_path):
        # Skip common non-source directories
        dirs[:] = [
            d
            for d in dirs
            if d
            not in (
                "node_modules",
                ".git",
                "dist",
                "build",
                "__pycache__",
                ".pytest_cache",
                "venv",
                ".venv",
                "coverage",
                ".next",
            )
        ]

        for filename in filenames:
            if any(filename.endswith(ext) for ext in exts):
                # Skip test files
                if "test" not in filename.lower() and "spec" not in filename.lower():
                    rel_path = os.path.relpath(
                        os.path.join(root, filename), workspace_path
                    )
                    files.append(rel_path)

    return files


# Export tools for the agent dispatcher
TEST_GENERATION_TOOLS = {
    "test_generate_for_file": generate_tests_for_file,
    "test_generate_for_function": generate_tests_for_function,
    "test_generate_suite": generate_test_suite,
    "test_detect_framework": detect_test_framework,
    "test_suggest_improvements": suggest_test_improvements,
}
