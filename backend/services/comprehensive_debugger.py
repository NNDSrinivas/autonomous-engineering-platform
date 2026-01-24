"""
Comprehensive Multi-Language Debugger and Fixer.

Supports 15+ programming languages with:
- Runtime error/exception analysis
- Compiler error analysis
- Build system error analysis
- Linter output parsing
- Test failure analysis
- Memory/performance issue detection
- Auto-fix generation

Languages Supported:
- Python (runtime, pytest, mypy, pylint, black)
- JavaScript/TypeScript (runtime, ESLint, TSC, Jest, Webpack)
- Go (runtime, compiler, go vet, golint)
- Rust (runtime, compiler, clippy, cargo)
- Java (runtime, javac, Maven, Gradle, JUnit)
- Kotlin (runtime, compiler, Gradle)
- Swift (runtime, compiler, SwiftLint)
- C/C++ (runtime, gcc/clang, valgrind, sanitizers)
- C# (runtime, compiler, MSBuild, NUnit)
- Ruby (runtime, RuboCop, RSpec)
- PHP (runtime, PHPStan, PHPUnit)
- Scala (runtime, compiler, SBT)
- Elixir (runtime, compiler, mix, ExUnit)
- Haskell (runtime, GHC, HLint)
- Dart/Flutter (runtime, analyzer, flutter)
"""

import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Categories of errors."""

    RUNTIME = "runtime"
    COMPILE = "compile"
    LINT = "lint"
    TEST = "test"
    BUILD = "build"
    MEMORY = "memory"
    PERFORMANCE = "performance"
    SECURITY = "security"
    TYPE = "type"
    SYNTAX = "syntax"


@dataclass
class ParsedError:
    """Structured error information."""

    language: str
    category: ErrorCategory
    error_type: str
    message: str
    file_path: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    function: Optional[str] = None
    code_snippet: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)
    auto_fix: Optional[Dict[str, Any]] = None
    related_errors: List[Dict] = field(default_factory=list)
    stack_trace: List[Dict] = field(default_factory=list)
    severity: str = "error"  # error, warning, info
    error_code: Optional[str] = None


class ComprehensiveDebugger:
    """
    Advanced multi-language debugger with comprehensive error analysis.
    """

    # Supported languages and their file extensions
    LANGUAGE_EXTENSIONS = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".kt": "kotlin",
        ".kts": "kotlin",
        ".swift": "swift",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".rb": "ruby",
        ".php": "php",
        ".scala": "scala",
        ".ex": "elixir",
        ".exs": "elixir",
        ".hs": "haskell",
        ".dart": "dart",
        ".lua": "lua",
        ".pl": "perl",
        ".pm": "perl",
        ".r": "r",
        ".R": "r",
        ".jl": "julia",
        ".groovy": "groovy",
        ".gradle": "gradle",
        ".clj": "clojure",
        ".erl": "erlang",
        ".fs": "fsharp",
        ".vb": "visualbasic",
        ".m": "objectivec",
        ".mm": "objectivec",
        ".zig": "zig",
        ".nim": "nim",
        ".cr": "crystal",
        ".v": "vlang",
        ".sol": "solidity",
    }

    @classmethod
    async def analyze(
        cls,
        error_output: str,
        workspace_path: str = ".",
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Main entry point for error analysis.
        Auto-detects language and error type.
        """
        result = {
            "success": False,
            "errors": [],
            "warnings": [],
            "summary": {},
            "auto_fixes": [],
            "suggested_commands": [],
        }

        # Try all parsers and collect results
        parsers = [
            # Runtime errors
            cls._parse_python_error,
            cls._parse_javascript_error,
            cls._parse_typescript_error,
            cls._parse_go_error,
            cls._parse_rust_error,
            cls._parse_java_error,
            cls._parse_kotlin_error,
            cls._parse_swift_error,
            cls._parse_c_cpp_error,
            cls._parse_csharp_error,
            cls._parse_ruby_error,
            cls._parse_php_error,
            cls._parse_scala_error,
            cls._parse_elixir_error,
            cls._parse_haskell_error,
            cls._parse_dart_error,
            # Compiler errors
            cls._parse_gcc_clang_error,
            cls._parse_rustc_error,
            cls._parse_tsc_error,
            cls._parse_javac_error,
            cls._parse_go_compiler_error,
            cls._parse_swift_compiler_error,
            cls._parse_dotnet_compiler_error,
            # Linter outputs
            cls._parse_eslint_output,
            cls._parse_pylint_output,
            cls._parse_mypy_output,
            cls._parse_golint_output,
            cls._parse_clippy_output,
            cls._parse_rubocop_output,
            cls._parse_phpstan_output,
            cls._parse_swiftlint_output,
            # Test failures
            cls._parse_pytest_output,
            cls._parse_jest_output,
            cls._parse_go_test_output,
            cls._parse_cargo_test_output,
            cls._parse_junit_output,
            cls._parse_rspec_output,
            cls._parse_phpunit_output,
            # Build systems
            cls._parse_npm_error,
            cls._parse_yarn_error,
            cls._parse_pip_error,
            cls._parse_cargo_error,
            cls._parse_maven_error,
            cls._parse_gradle_error,
            cls._parse_cmake_error,
            cls._parse_make_error,
            # Memory/Performance
            cls._parse_valgrind_output,
            cls._parse_sanitizer_output,
        ]

        for parser in parsers:
            try:
                parsed = parser(error_output, workspace_path)
                if parsed:
                    for error in parsed:
                        if error.severity == "error":
                            result["errors"].append(cls._error_to_dict(error))
                        else:
                            result["warnings"].append(cls._error_to_dict(error))
            except Exception as e:
                logger.debug(f"Parser {parser.__name__} failed: {e}")

        if result["errors"] or result["warnings"]:
            result["success"] = True
            result["summary"] = cls._generate_summary(
                result["errors"], result["warnings"]
            )
            result["auto_fixes"] = cls._generate_auto_fixes(
                result["errors"], workspace_path
            )
            result["suggested_commands"] = cls._generate_suggested_commands(
                result["errors"]
            )

        return result

    @classmethod
    def _error_to_dict(cls, error: ParsedError) -> Dict[str, Any]:
        """Convert ParsedError to dictionary."""
        return {
            "language": error.language,
            "category": error.category.value,
            "error_type": error.error_type,
            "message": error.message,
            "file": error.file_path,
            "line": error.line,
            "column": error.column,
            "function": error.function,
            "code_snippet": error.code_snippet,
            "suggestions": error.suggestions,
            "auto_fix": error.auto_fix,
            "related_errors": error.related_errors,
            "stack_trace": error.stack_trace,
            "severity": error.severity,
            "error_code": error.error_code,
        }

    # ============================================================
    # PYTHON PARSERS
    # ============================================================

    @classmethod
    def _parse_python_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse Python runtime errors and exceptions."""
        errors = []

        # Standard traceback
        if "Traceback (most recent call last):" in output:
            error = ParsedError(
                language="python",
                category=ErrorCategory.RUNTIME,
                error_type="",
                message="",
            )

            # Extract stack trace
            file_pattern = r'File "([^"]+)", line (\d+), in (\w+)'
            for match in re.finditer(file_pattern, output):
                error.stack_trace.append(
                    {
                        "file": match.group(1),
                        "line": int(match.group(2)),
                        "function": match.group(3),
                    }
                )

            if error.stack_trace:
                last_frame = error.stack_trace[-1]
                error.file_path = last_frame["file"]
                error.line = last_frame["line"]
                error.function = last_frame["function"]

            # Extract error type and message
            lines = output.strip().splitlines()
            error_line = lines[-1] if lines else ""
            if ":" in error_line:
                parts = error_line.split(":", 1)
                error.error_type = parts[0].strip()
                error.message = parts[1].strip() if len(parts) > 1 else ""

            # Add suggestions based on error type
            error.suggestions = cls._get_python_suggestions(
                error.error_type, error.message
            )

            errors.append(error)

        # SyntaxError special handling
        syntax_match = re.search(
            r'File "([^"]+)", line (\d+)\n.*\n\s*\^\nSyntaxError:\s*(.+)',
            output,
            re.MULTILINE,
        )
        if syntax_match:
            errors.append(
                ParsedError(
                    language="python",
                    category=ErrorCategory.SYNTAX,
                    error_type="SyntaxError",
                    message=syntax_match.group(3),
                    file_path=syntax_match.group(1),
                    line=int(syntax_match.group(2)),
                    suggestions=[
                        "Check for missing colons, parentheses, or brackets",
                        "Verify indentation is consistent (use 4 spaces)",
                        "Look for invalid syntax near the indicated position",
                    ],
                )
            )

        return errors

    @classmethod
    def _parse_pytest_output(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse pytest test failure output."""
        errors = []

        # Test failure pattern
        failure_pattern = r"FAILED\s+([^\s:]+)::(\w+)\s*-\s*(.+)"
        for match in re.finditer(failure_pattern, output):
            file_path = match.group(1)
            test_name = match.group(2)
            reason = match.group(3)

            errors.append(
                ParsedError(
                    language="python",
                    category=ErrorCategory.TEST,
                    error_type="TestFailure",
                    message=f"{test_name}: {reason}",
                    file_path=file_path,
                    function=test_name,
                    suggestions=[
                        f"Review test {test_name} for assertion failures",
                        "Check if test fixtures are properly set up",
                        "Verify expected values match actual results",
                    ],
                )
            )

        # AssertionError with details
        assert_pattern = r">?\s+assert\s+(.+)\nE\s+AssertionError:\s*(.+)?"
        for match in re.finditer(assert_pattern, output):
            errors.append(
                ParsedError(
                    language="python",
                    category=ErrorCategory.TEST,
                    error_type="AssertionError",
                    message=f"Failed assertion: {match.group(1)}",
                    suggestions=[
                        "Compare expected and actual values",
                        "Check if the test data is correct",
                        "Verify the function under test behaves as expected",
                    ],
                )
            )

        return errors

    @classmethod
    def _parse_mypy_output(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse mypy type checking output."""
        errors = []

        # mypy format: file.py:line: error: message
        pattern = r"([^:\s]+):(\d+)(?::(\d+))?: (error|warning|note): (.+)"
        for match in re.finditer(pattern, output):
            severity = "warning" if match.group(4) == "warning" else "error"
            errors.append(
                ParsedError(
                    language="python",
                    category=ErrorCategory.TYPE,
                    error_type=f"mypy_{match.group(4)}",
                    message=match.group(5),
                    file_path=match.group(1),
                    line=int(match.group(2)),
                    column=int(match.group(3)) if match.group(3) else None,
                    severity=severity,
                    suggestions=cls._get_mypy_suggestions(match.group(5)),
                )
            )

        return errors

    @classmethod
    def _parse_pylint_output(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse pylint output."""
        errors = []

        # pylint format: file.py:line:col: CODE: message
        pattern = r"([^:\s]+):(\d+):(\d+): ([A-Z]\d+): (.+) \(([^)]+)\)"
        for match in re.finditer(pattern, output):
            code = match.group(4)
            severity = "error" if code.startswith(("E", "F")) else "warning"
            errors.append(
                ParsedError(
                    language="python",
                    category=ErrorCategory.LINT,
                    error_type=match.group(6),
                    message=match.group(5),
                    file_path=match.group(1),
                    line=int(match.group(2)),
                    column=int(match.group(3)),
                    error_code=code,
                    severity=severity,
                )
            )

        return errors

    @classmethod
    def _get_python_suggestions(cls, error_type: str, message: str) -> List[str]:
        """Get Python-specific error suggestions."""
        suggestions_map = {
            "ImportError": [
                "Install the missing module: pip install <module>",
                "Check if the module name is spelled correctly",
                "Verify the module is in your PYTHONPATH",
                "Ensure virtual environment is activated",
            ],
            "ModuleNotFoundError": [
                "Install the missing module: pip install <module>",
                "Check requirements.txt or pyproject.toml",
                "Run: pip install -r requirements.txt",
            ],
            "AttributeError": [
                "Check if the object has the attribute/method",
                "Verify the object is not None",
                "Use hasattr() to check attribute existence",
                "Review class definition for typos",
            ],
            "TypeError": [
                "Check function argument types",
                "Verify you're not calling None as a function",
                "Review the function signature",
                "Use type hints and mypy for type checking",
            ],
            "KeyError": [
                "Use dict.get(key, default) to avoid KeyError",
                "Check if key exists: if key in dict",
                "Verify the dictionary has the expected keys",
            ],
            "IndexError": [
                "Check list/array bounds before accessing",
                "Use len() to verify size",
                "Consider using try/except for bounds checking",
            ],
            "ValueError": [
                "Validate input data before processing",
                "Check data types and formats",
                "Add input validation with clear error messages",
            ],
            "ZeroDivisionError": [
                "Add check: if divisor != 0",
                "Use try/except to handle division by zero",
                "Validate divisor before operation",
            ],
            "FileNotFoundError": [
                "Verify the file path is correct",
                "Use os.path.exists() to check file existence",
                "Check current working directory with os.getcwd()",
                "Use pathlib.Path for cross-platform paths",
            ],
            "PermissionError": [
                "Check file/directory permissions",
                "Run with appropriate privileges if needed",
                "Verify the path is accessible",
            ],
            "RecursionError": [
                "Add a base case to stop recursion",
                "Consider iterative approach instead",
                "Increase recursion limit: sys.setrecursionlimit()",
            ],
            "MemoryError": [
                "Process data in chunks/batches",
                "Use generators instead of lists",
                "Consider memory-efficient data structures",
                "Profile memory usage with memory_profiler",
            ],
            "ConnectionError": [
                "Check network connectivity",
                "Verify the server URL/host",
                "Implement retry logic with exponential backoff",
                "Check firewall settings",
            ],
            "TimeoutError": [
                "Increase timeout value",
                "Implement async operations",
                "Check for slow database queries",
                "Use connection pooling",
            ],
        }

        for error_key, suggs in suggestions_map.items():
            if error_key in error_type:
                return suggs

        return [
            "Review the error message for specific details",
            "Add debugging logs to trace the issue",
        ]

    @classmethod
    def _get_mypy_suggestions(cls, message: str) -> List[str]:
        """Get mypy-specific suggestions."""
        if "incompatible type" in message.lower():
            return [
                "Check the expected vs actual types",
                "Add type annotation to clarify the type",
                "Use typing.cast() if you're sure about the type",
            ]
        elif "has no attribute" in message.lower():
            return [
                "Add the missing attribute to the class",
                "Check if you're using the correct type",
                "Use Protocol for structural typing",
            ]
        elif "missing return" in message.lower():
            return [
                "Add return statement for all code paths",
                "Use Optional[T] if function can return None",
            ]
        return ["Review type annotations", "Consider using typing module"]

    # ============================================================
    # JAVASCRIPT/TYPESCRIPT PARSERS
    # ============================================================

    @classmethod
    def _parse_javascript_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse JavaScript runtime errors."""
        errors = []

        # Standard Error format
        error_match = re.search(r"(\w+Error):\s*(.+?)(?:\n|$)", output)
        if error_match:
            error = ParsedError(
                language="javascript",
                category=ErrorCategory.RUNTIME,
                error_type=error_match.group(1),
                message=error_match.group(2),
            )

            # Extract stack trace
            stack_pattern = r"at\s+(?:(\S+)\s+)?\(?([^:]+):(\d+):(\d+)\)?"
            for match in re.finditer(stack_pattern, output):
                frame = {
                    "file": match.group(2),
                    "line": int(match.group(3)),
                    "column": int(match.group(4)),
                }
                if match.group(1):
                    frame["function"] = match.group(1)
                error.stack_trace.append(frame)

            if error.stack_trace:
                first_frame = error.stack_trace[0]
                error.file_path = first_frame.get("file")
                error.line = first_frame.get("line")
                error.column = first_frame.get("column")
                error.function = first_frame.get("function")

            error.suggestions = cls._get_javascript_suggestions(
                error.error_type, error.message
            )
            errors.append(error)

        return errors

    @classmethod
    def _parse_typescript_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse TypeScript compiler errors."""
        errors = []

        # TSC error format: file.ts(line,col): error TS####: message
        pattern = r"([^(\s]+)\((\d+),(\d+)\): (error|warning) (TS\d+): (.+)"
        for match in re.finditer(pattern, output):
            errors.append(
                ParsedError(
                    language="typescript",
                    category=ErrorCategory.COMPILE,
                    error_type=match.group(5),
                    message=match.group(6),
                    file_path=match.group(1),
                    line=int(match.group(2)),
                    column=int(match.group(3)),
                    error_code=match.group(5),
                    severity="error" if match.group(4) == "error" else "warning",
                    suggestions=cls._get_typescript_suggestions(
                        match.group(5), match.group(6)
                    ),
                )
            )

        return errors

    @classmethod
    def _parse_tsc_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Alias for TypeScript compiler."""
        return cls._parse_typescript_error(output, workspace)

    @classmethod
    def _parse_eslint_output(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse ESLint output."""
        errors = []

        # ESLint format: /path/file.js
        #   line:col  error/warning  message  rule-name
        file_pattern = r"^(/[^\n]+\.(?:js|jsx|ts|tsx))$"
        error_pattern = r"^\s+(\d+):(\d+)\s+(error|warning)\s+(.+?)\s+(\S+)$"

        current_file = None
        for line in output.splitlines():
            file_match = re.match(file_pattern, line)
            if file_match:
                current_file = file_match.group(1)
                continue

            if current_file:
                error_match = re.match(error_pattern, line)
                if error_match:
                    errors.append(
                        ParsedError(
                            language="javascript",
                            category=ErrorCategory.LINT,
                            error_type=error_match.group(5),
                            message=error_match.group(4),
                            file_path=current_file,
                            line=int(error_match.group(1)),
                            column=int(error_match.group(2)),
                            severity=(
                                "error"
                                if error_match.group(3) == "error"
                                else "warning"
                            ),
                            error_code=error_match.group(5),
                        )
                    )

        return errors

    @classmethod
    def _parse_jest_output(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse Jest test output."""
        errors = []

        # Jest failure pattern
        failure_pattern = r"●\s+(.+)\n\n\s+(.+)\n"
        for match in re.finditer(failure_pattern, output):
            test_name = match.group(1)
            error_msg = match.group(2).strip()

            errors.append(
                ParsedError(
                    language="javascript",
                    category=ErrorCategory.TEST,
                    error_type="TestFailure",
                    message=f"{test_name}: {error_msg}",
                    function=test_name,
                    suggestions=[
                        "Check the expected vs actual values",
                        "Verify mock functions are set up correctly",
                        "Review async/await handling in tests",
                    ],
                )
            )

        # Extract file location from "at" lines
        at_pattern = r"at\s+(?:Object\.)?\<anonymous\>\s+\(([^:]+):(\d+):(\d+)\)"
        for match in re.finditer(at_pattern, output):
            if errors:
                errors[-1].file_path = match.group(1)
                errors[-1].line = int(match.group(2))

        return errors

    @classmethod
    def _get_javascript_suggestions(cls, error_type: str, message: str) -> List[str]:
        """Get JavaScript-specific suggestions."""
        suggestions_map = {
            "TypeError": [
                "Check if the variable is undefined or null",
                "Use optional chaining (?.) for safe property access",
                "Verify the object structure matches expectations",
                "Add null checks before method calls",
            ],
            "ReferenceError": [
                "Check if the variable is declared (let/const/var)",
                "Verify the variable is in scope",
                "Check for typos in variable names",
                "Ensure imports are correct",
            ],
            "SyntaxError": [
                "Check for missing brackets, braces, or semicolons",
                "Verify JSON syntax if parsing JSON",
                "Look for reserved words used incorrectly",
            ],
            "RangeError": [
                "Check array index bounds",
                "Verify recursion has a proper base case",
                "Check for invalid array lengths",
            ],
            "URIError": [
                "Use encodeURIComponent() for special characters",
                "Verify URI format is correct",
            ],
        }

        for error_key, suggs in suggestions_map.items():
            if error_key in error_type:
                return suggs

        return [
            "Check the error message for details",
            "Add console.log to trace the issue",
        ]

    @classmethod
    def _get_typescript_suggestions(cls, error_code: str, message: str) -> List[str]:
        """Get TypeScript-specific suggestions."""
        ts_suggestions = {
            "TS2304": [
                "Import the missing type/module",
                "Check spelling of the identifier",
            ],
            "TS2322": ["Fix type mismatch", "Use type assertion if certain about type"],
            "TS2339": [
                "Add the missing property to the type",
                "Check object structure",
            ],
            "TS2345": ["Fix argument type to match parameter", "Add type assertion"],
            "TS2551": [
                "Check for typos in property name",
                "Add the property to interface",
            ],
            "TS2307": [
                "Install missing @types package",
                "Create type declaration file",
            ],
            "TS7006": [
                "Add type annotation to parameter",
                "Enable noImplicitAny: false",
            ],
            "TS2554": ["Check number of arguments", "Review function signature"],
        }

        return ts_suggestions.get(
            error_code, ["Review TypeScript documentation for error code"]
        )

    # ============================================================
    # GO PARSERS
    # ============================================================

    @classmethod
    def _parse_go_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse Go runtime errors."""
        errors = []

        # Panic
        if "panic:" in output:
            panic_match = re.search(r"panic:\s*(.+?)(?:\n|$)", output)
            if panic_match:
                error = ParsedError(
                    language="go",
                    category=ErrorCategory.RUNTIME,
                    error_type="panic",
                    message=panic_match.group(1),
                )

                # Extract goroutine stack
                stack_pattern = r"([/\w.-]+\.go):(\d+)"
                for match in re.finditer(stack_pattern, output):
                    error.stack_trace.append(
                        {
                            "file": match.group(1),
                            "line": int(match.group(2)),
                        }
                    )

                if error.stack_trace:
                    error.file_path = error.stack_trace[0]["file"]
                    error.line = error.stack_trace[0]["line"]

                error.suggestions = [
                    "Add nil checks before dereferencing pointers",
                    "Use recover() to handle panics gracefully",
                    "Validate slice indices before accessing",
                    "Check for division by zero",
                ]

                errors.append(error)

        return errors

    @classmethod
    def _parse_go_compiler_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse Go compiler errors."""
        errors = []

        # Go compiler format: file.go:line:col: error message
        pattern = r"([^:\s]+\.go):(\d+):(\d+):\s*(.+)"
        for match in re.finditer(pattern, output):
            errors.append(
                ParsedError(
                    language="go",
                    category=ErrorCategory.COMPILE,
                    error_type="compile_error",
                    message=match.group(4),
                    file_path=match.group(1),
                    line=int(match.group(2)),
                    column=int(match.group(3)),
                    suggestions=cls._get_go_compiler_suggestions(match.group(4)),
                )
            )

        return errors

    @classmethod
    def _parse_golint_output(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse golint/staticcheck output."""
        errors = []

        # Format: file.go:line:col: message
        pattern = r"([^:\s]+\.go):(\d+):(\d+):\s*(.+)"
        for match in re.finditer(pattern, output):
            errors.append(
                ParsedError(
                    language="go",
                    category=ErrorCategory.LINT,
                    error_type="lint_warning",
                    message=match.group(4),
                    file_path=match.group(1),
                    line=int(match.group(2)),
                    column=int(match.group(3)),
                    severity="warning",
                )
            )

        return errors

    @classmethod
    def _parse_go_test_output(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse go test output."""
        errors = []

        # Test failure: --- FAIL: TestName (duration)
        fail_pattern = r"--- FAIL: (\w+)\s+\(([\d.]+)s\)"
        for match in re.finditer(fail_pattern, output):
            errors.append(
                ParsedError(
                    language="go",
                    category=ErrorCategory.TEST,
                    error_type="TestFailure",
                    message=f"Test {match.group(1)} failed after {match.group(2)}s",
                    function=match.group(1),
                    suggestions=[
                        "Check test assertions",
                        "Verify test setup and teardown",
                        "Run with -v flag for verbose output",
                    ],
                )
            )

        return errors

    @classmethod
    def _get_go_compiler_suggestions(cls, message: str) -> List[str]:
        """Get Go compiler error suggestions."""
        if "undefined:" in message:
            return ["Import the package or declare the identifier", "Check for typos"]
        elif "cannot use" in message:
            return ["Fix type mismatch", "Use type conversion if appropriate"]
        elif "declared but not used" in message:
            return ["Remove unused variable", "Use _ to ignore the value"]
        elif "imported but not used" in message:
            return ["Remove unused import", 'Use blank identifier: _ "package"']
        elif "missing return" in message:
            return ["Add return statement", "Ensure all paths return a value"]
        return ["Review Go documentation for the error"]

    # ============================================================
    # RUST PARSERS
    # ============================================================

    @classmethod
    def _parse_rust_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse Rust runtime errors."""
        errors = []

        # Panic
        if "panicked at" in output:
            panic_match = re.search(
                r"thread '([^']+)' panicked at ['\"](.+?)['\"],?\s*([^:\s]+):(\d+):(\d+)",
                output,
            )
            if panic_match:
                errors.append(
                    ParsedError(
                        language="rust",
                        category=ErrorCategory.RUNTIME,
                        error_type="panic",
                        message=panic_match.group(2),
                        file_path=panic_match.group(3),
                        line=int(panic_match.group(4)),
                        column=int(panic_match.group(5)),
                        suggestions=[
                            "Use Result<T, E> instead of unwrap()",
                            "Replace unwrap() with expect() for better errors",
                            "Use pattern matching for Option/Result",
                            "Consider the ? operator for error propagation",
                        ],
                    )
                )

        return errors

    @classmethod
    def _parse_rustc_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse Rust compiler errors."""
        errors = []

        # rustc format: error[E####]: message
        #   --> file.rs:line:col
        error_pattern = r"(error|warning)\[([^\]]+)\]:\s*(.+?)(?:\n|$)"
        loc_pattern = r"-->\s*([^:\s]+):(\d+):(\d+)"

        error_matches = list(re.finditer(error_pattern, output))
        loc_matches = list(re.finditer(loc_pattern, output))

        for i, match in enumerate(error_matches):
            error = ParsedError(
                language="rust",
                category=ErrorCategory.COMPILE,
                error_type=match.group(2),
                message=match.group(3),
                error_code=match.group(2),
                severity="error" if match.group(1) == "error" else "warning",
            )

            # Find corresponding location
            if i < len(loc_matches):
                loc = loc_matches[i]
                error.file_path = loc.group(1)
                error.line = int(loc.group(2))
                error.column = int(loc.group(3))

            error.suggestions = cls._get_rust_compiler_suggestions(match.group(2))
            errors.append(error)

        return errors

    @classmethod
    def _parse_clippy_output(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse Clippy output."""
        return cls._parse_rustc_error(output, workspace)  # Similar format

    @classmethod
    def _parse_cargo_test_output(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse cargo test output."""
        errors = []

        # Test failure: test path::to::test ... FAILED
        fail_pattern = r"test\s+(\S+)\s+\.\.\.\s+FAILED"
        for match in re.finditer(fail_pattern, output):
            errors.append(
                ParsedError(
                    language="rust",
                    category=ErrorCategory.TEST,
                    error_type="TestFailure",
                    message=f"Test {match.group(1)} failed",
                    function=match.group(1),
                    suggestions=[
                        "Check assert! and assert_eq! statements",
                        "Run with --nocapture to see println! output",
                        "Use RUST_BACKTRACE=1 for stack trace",
                    ],
                )
            )

        return errors

    @classmethod
    def _get_rust_compiler_suggestions(cls, error_code: str) -> List[str]:
        """Get Rust compiler error suggestions."""
        rust_suggestions = {
            "E0382": [
                "Use .clone() to copy the value",
                "Use references instead of ownership",
            ],
            "E0502": [
                "Reduce the scope of the mutable borrow",
                "Use interior mutability",
            ],
            "E0277": ["Implement the required trait", "Check trait bounds"],
            "E0308": ["Fix type mismatch", "Use type annotation"],
            "E0433": ["Import the module with use", "Check module path"],
            "E0599": ["Import the trait for the method", "Check method name spelling"],
        }
        return rust_suggestions.get(
            error_code, ["Check Rust error codes documentation"]
        )

    # ============================================================
    # JAVA/KOTLIN PARSERS
    # ============================================================

    @classmethod
    def _parse_java_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse Java runtime exceptions."""
        errors = []

        # Exception pattern
        exception_match = re.search(
            r"([\w.]+(?:Exception|Error))(?::\s*(.+?))?(?:\n|\s+at\s)", output
        )
        if exception_match:
            error = ParsedError(
                language="java",
                category=ErrorCategory.RUNTIME,
                error_type=exception_match.group(1),
                message=exception_match.group(2) or "",
            )

            # Stack trace
            stack_pattern = r"at\s+([\w.$]+)\(([\w.]+):(\d+)\)"
            for match in re.finditer(stack_pattern, output):
                error.stack_trace.append(
                    {
                        "function": match.group(1),
                        "file": match.group(2),
                        "line": int(match.group(3)),
                    }
                )

            if error.stack_trace:
                first = error.stack_trace[0]
                error.file_path = first.get("file")
                error.line = first.get("line")
                error.function = first.get("function")

            # Caused by
            caused_by = re.findall(
                r"Caused by:\s*([\w.]+(?:Exception|Error))(?::\s*(.+?))?(?:\n|$)",
                output,
            )
            error.related_errors = [
                {"type": c[0], "message": c[1] or ""} for c in caused_by
            ]

            error.suggestions = cls._get_java_suggestions(error.error_type)
            errors.append(error)

        return errors

    @classmethod
    def _parse_javac_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse javac compiler errors."""
        errors = []

        # Format: file.java:line: error: message
        pattern = r"([^:\s]+\.java):(\d+): (error|warning): (.+)"
        for match in re.finditer(pattern, output):
            errors.append(
                ParsedError(
                    language="java",
                    category=ErrorCategory.COMPILE,
                    error_type="javac_error",
                    message=match.group(4),
                    file_path=match.group(1),
                    line=int(match.group(2)),
                    severity="error" if match.group(3) == "error" else "warning",
                )
            )

        return errors

    @classmethod
    def _parse_kotlin_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse Kotlin errors."""
        errors = []

        # Kotlin exception (similar to Java)
        if "Exception" in output or "Error" in output:
            java_errors = cls._parse_java_error(output, workspace)
            for e in java_errors:
                e.language = "kotlin"
            errors.extend(java_errors)

        # Kotlin compiler: e: file.kt: (line, col): message
        pattern = r"e:\s*([^:]+\.kt):\s*\((\d+),\s*(\d+)\):\s*(.+)"
        for match in re.finditer(pattern, output):
            errors.append(
                ParsedError(
                    language="kotlin",
                    category=ErrorCategory.COMPILE,
                    error_type="kotlinc_error",
                    message=match.group(4),
                    file_path=match.group(1),
                    line=int(match.group(2)),
                    column=int(match.group(3)),
                )
            )

        return errors

    @classmethod
    def _parse_maven_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse Maven build errors."""
        errors = []

        # Maven error: [ERROR] /path/file.java:[line,col] error message
        pattern = r"\[ERROR\]\s*([^:]+):?\[?(\d+)?[,:]?(\d+)?\]?\s*(.+)"
        for match in re.finditer(pattern, output):
            errors.append(
                ParsedError(
                    language="java",
                    category=ErrorCategory.BUILD,
                    error_type="maven_error",
                    message=match.group(4),
                    file_path=match.group(1) if match.group(1) else None,
                    line=int(match.group(2)) if match.group(2) else None,
                    column=int(match.group(3)) if match.group(3) else None,
                )
            )

        return errors

    @classmethod
    def _parse_gradle_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse Gradle build errors."""
        errors = []

        # Gradle error patterns
        patterns = [
            r"> Task :(\S+) FAILED",
            r"FAILURE: (.+)",
            r"e:\s*(.+\.kt):\s*\((\d+),\s*(\d+)\):\s*(.+)",
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, output):
                errors.append(
                    ParsedError(
                        language="java",
                        category=ErrorCategory.BUILD,
                        error_type="gradle_error",
                        message=match.group(0),
                    )
                )

        return errors

    @classmethod
    def _parse_junit_output(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse JUnit test output."""
        errors = []

        # JUnit failure
        test_pattern = r"(\w+)\(([^)]+)\)\s+Time elapsed:.+<<<\s*(?:FAILURE|ERROR)"

        for match in re.finditer(test_pattern, output):
            errors.append(
                ParsedError(
                    language="java",
                    category=ErrorCategory.TEST,
                    error_type="TestFailure",
                    message=f"Test {match.group(1)} in {match.group(2)} failed",
                    function=match.group(1),
                )
            )

        return errors

    @classmethod
    def _get_java_suggestions(cls, error_type: str) -> List[str]:
        """Get Java-specific suggestions."""
        suggestions_map = {
            "NullPointerException": [
                "Add null checks: if (obj != null)",
                "Use Optional<T> for nullable values",
                "Use @NonNull/@Nullable annotations",
                "Initialize objects in constructors",
            ],
            "ArrayIndexOutOfBoundsException": [
                "Check array.length before accessing",
                "Use enhanced for-loop: for (T item : array)",
                "Validate indices from user input",
            ],
            "ClassCastException": [
                "Use instanceof before casting",
                "Review type hierarchy",
                "Consider using generics",
            ],
            "NumberFormatException": [
                "Validate string before parsing",
                "Use try-catch around parse methods",
                "Trim whitespace: str.trim()",
            ],
            "IOException": [
                "Use try-with-resources for streams",
                "Handle or declare the exception",
                "Check file paths and permissions",
            ],
            "SQLException": [
                "Check database connection",
                "Verify SQL syntax",
                "Use PreparedStatement",
            ],
            "OutOfMemoryError": [
                "Increase heap size: -Xmx",
                "Check for memory leaks",
                "Use profiler to find issues",
            ],
            "StackOverflowError": [
                "Add base case to recursion",
                "Convert to iterative approach",
                "Increase stack size: -Xss",
            ],
        }

        for key, suggs in suggestions_map.items():
            if key in error_type:
                return suggs

        return ["Review Java documentation for this exception"]

    # ============================================================
    # C/C++ PARSERS
    # ============================================================

    @classmethod
    def _parse_c_cpp_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse C/C++ runtime errors (segfault, etc.)."""
        errors = []

        # Segmentation fault
        if "Segmentation fault" in output or "SIGSEGV" in output:
            errors.append(
                ParsedError(
                    language="cpp",
                    category=ErrorCategory.RUNTIME,
                    error_type="SegmentationFault",
                    message="Memory access violation",
                    suggestions=[
                        "Check for null pointer dereference",
                        "Verify array bounds",
                        "Check for use-after-free",
                        "Run with valgrind for detailed analysis",
                        "Compile with -fsanitize=address",
                    ],
                )
            )

        # Double free
        if "double free" in output.lower():
            errors.append(
                ParsedError(
                    language="cpp",
                    category=ErrorCategory.MEMORY,
                    error_type="DoubleFree",
                    message="Memory freed twice",
                    suggestions=[
                        "Set pointer to nullptr after free",
                        "Use smart pointers (unique_ptr, shared_ptr)",
                        "Review ownership semantics",
                    ],
                )
            )

        return errors

    @classmethod
    def _parse_gcc_clang_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse GCC/Clang compiler errors."""
        errors = []

        # Format: file:line:col: error/warning: message
        pattern = (
            r"([^:\s]+\.[ch](?:pp|xx)?):(\d+):(\d+):\s*(error|warning|note):\s*(.+)"
        )
        for match in re.finditer(pattern, output, re.IGNORECASE):
            severity = match.group(4).lower()
            errors.append(
                ParsedError(
                    language=(
                        "cpp" if match.group(1).endswith(("pp", "xx", "hpp")) else "c"
                    ),
                    category=ErrorCategory.COMPILE,
                    error_type="compiler_error",
                    message=match.group(5),
                    file_path=match.group(1),
                    line=int(match.group(2)),
                    column=int(match.group(3)),
                    severity="warning" if severity == "warning" else "error",
                    suggestions=cls._get_c_cpp_suggestions(match.group(5)),
                )
            )

        return errors

    @classmethod
    def _parse_valgrind_output(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse Valgrind memory checker output."""
        errors = []

        # Memory leak
        leak_pattern = r"(\d+(?:,\d+)*)\s+bytes\s+in\s+(\d+)\s+blocks\s+are\s+(definitely|indirectly|possibly)\s+lost"
        for match in re.finditer(leak_pattern, output):
            errors.append(
                ParsedError(
                    language="cpp",
                    category=ErrorCategory.MEMORY,
                    error_type="MemoryLeak",
                    message=f"{match.group(1)} bytes {match.group(3)} lost in {match.group(2)} blocks",
                    severity="warning" if match.group(3) == "possibly" else "error",
                    suggestions=[
                        "Free allocated memory before losing reference",
                        "Use smart pointers for automatic memory management",
                        "Review ownership of dynamically allocated objects",
                    ],
                )
            )

        # Invalid read/write
        invalid_pattern = r"Invalid\s+(read|write)\s+of\s+size\s+(\d+)"
        for match in re.finditer(invalid_pattern, output):
            errors.append(
                ParsedError(
                    language="cpp",
                    category=ErrorCategory.MEMORY,
                    error_type=f"Invalid{match.group(1).title()}",
                    message=f"Invalid {match.group(1)} of size {match.group(2)}",
                    suggestions=[
                        "Check array/buffer bounds",
                        "Verify pointer validity before use",
                        "Check for use-after-free",
                    ],
                )
            )

        return errors

    @classmethod
    def _parse_sanitizer_output(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse AddressSanitizer/UBSan output."""
        errors = []

        # AddressSanitizer
        asan_pattern = (
            r"ERROR:\s*AddressSanitizer:\s*(\S+)\s+on\s+(?:address|unknown address)"
        )
        for match in re.finditer(asan_pattern, output):
            errors.append(
                ParsedError(
                    language="cpp",
                    category=ErrorCategory.MEMORY,
                    error_type=f"ASan_{match.group(1)}",
                    message=f"AddressSanitizer: {match.group(1)}",
                    suggestions=[
                        "Check memory access patterns",
                        "Verify buffer sizes",
                        "Review pointer arithmetic",
                    ],
                )
            )

        # UndefinedBehaviorSanitizer
        ubsan_pattern = r"runtime error:\s*(.+)"
        for match in re.finditer(ubsan_pattern, output):
            errors.append(
                ParsedError(
                    language="cpp",
                    category=ErrorCategory.RUNTIME,
                    error_type="UndefinedBehavior",
                    message=match.group(1),
                    suggestions=[
                        "Fix the undefined behavior",
                        "Check for integer overflow",
                        "Verify type conversions",
                    ],
                )
            )

        return errors

    @classmethod
    def _get_c_cpp_suggestions(cls, message: str) -> List[str]:
        """Get C/C++ compiler error suggestions."""
        msg_lower = message.lower()

        if "undeclared" in msg_lower or "not declared" in msg_lower:
            return ["Include the required header", "Check spelling of identifier"]
        elif "undefined reference" in msg_lower:
            return ["Link the required library", "Implement the missing function"]
        elif "incompatible" in msg_lower:
            return ["Check types match", "Use explicit cast if appropriate"]
        elif "expected" in msg_lower:
            return ["Check syntax", "Add missing punctuation or keyword"]
        elif "redefinition" in msg_lower:
            return ["Remove duplicate definition", "Use include guards"]

        return ["Review compiler documentation"]

    # ============================================================
    # SWIFT PARSERS
    # ============================================================

    @classmethod
    def _parse_swift_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse Swift runtime errors."""
        errors = []

        # Fatal error
        if "Fatal error:" in output:
            fatal_match = re.search(r"Fatal error:\s*(.+?)(?:\n|$)", output)
            if fatal_match:
                errors.append(
                    ParsedError(
                        language="swift",
                        category=ErrorCategory.RUNTIME,
                        error_type="FatalError",
                        message=fatal_match.group(1),
                        suggestions=[
                            "Use guard statements for early exit",
                            "Handle optionals safely with if-let or guard-let",
                            "Avoid force unwrapping (!)",
                        ],
                    )
                )

        return errors

    @classmethod
    def _parse_swift_compiler_error(
        cls, output: str, workspace: str
    ) -> List[ParsedError]:
        """Parse Swift compiler errors."""
        errors = []

        # Format: file.swift:line:col: error: message
        pattern = r"([^:\s]+\.swift):(\d+):(\d+):\s*(error|warning):\s*(.+)"
        for match in re.finditer(pattern, output):
            errors.append(
                ParsedError(
                    language="swift",
                    category=ErrorCategory.COMPILE,
                    error_type="swiftc_error",
                    message=match.group(5),
                    file_path=match.group(1),
                    line=int(match.group(2)),
                    column=int(match.group(3)),
                    severity="error" if match.group(4) == "error" else "warning",
                )
            )

        return errors

    @classmethod
    def _parse_swiftlint_output(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse SwiftLint output."""
        errors = []

        # Format: file.swift:line:col: warning/error: message (rule_name)
        pattern = (
            r"([^:\s]+\.swift):(\d+):(\d+):\s*(warning|error):\s*(.+?)\s*\((\S+)\)"
        )
        for match in re.finditer(pattern, output):
            errors.append(
                ParsedError(
                    language="swift",
                    category=ErrorCategory.LINT,
                    error_type=match.group(6),
                    message=match.group(5),
                    file_path=match.group(1),
                    line=int(match.group(2)),
                    column=int(match.group(3)),
                    severity="error" if match.group(4) == "error" else "warning",
                    error_code=match.group(6),
                )
            )

        return errors

    # ============================================================
    # C# PARSERS
    # ============================================================

    @classmethod
    def _parse_csharp_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse C# runtime exceptions."""
        errors = []

        # Exception format
        exception_match = re.search(r"([\w.]+Exception):\s*(.+?)(?:\n|$)", output)
        if exception_match:
            error = ParsedError(
                language="csharp",
                category=ErrorCategory.RUNTIME,
                error_type=exception_match.group(1),
                message=exception_match.group(2),
            )

            # Stack trace: at Namespace.Class.Method() in file.cs:line N
            stack_pattern = r"at\s+([\w.<>]+)\([^)]*\)(?:\s+in\s+([^:]+):line\s+(\d+))?"
            for match in re.finditer(stack_pattern, output):
                frame = {"function": match.group(1)}
                if match.group(2):
                    frame["file"] = match.group(2)
                    frame["line"] = int(match.group(3))
                error.stack_trace.append(frame)

            if error.stack_trace and "file" in error.stack_trace[0]:
                error.file_path = error.stack_trace[0]["file"]
                error.line = error.stack_trace[0]["line"]
                error.function = error.stack_trace[0]["function"]

            error.suggestions = cls._get_csharp_suggestions(error.error_type)
            errors.append(error)

        return errors

    @classmethod
    def _parse_dotnet_compiler_error(
        cls, output: str, workspace: str
    ) -> List[ParsedError]:
        """Parse .NET compiler errors (csc, Roslyn)."""
        errors = []

        # Format: file.cs(line,col): error CS####: message
        pattern = r"([^(\s]+\.cs)\((\d+),(\d+)\):\s*(error|warning)\s+(CS\d+):\s*(.+)"
        for match in re.finditer(pattern, output):
            errors.append(
                ParsedError(
                    language="csharp",
                    category=ErrorCategory.COMPILE,
                    error_type=match.group(5),
                    message=match.group(6),
                    file_path=match.group(1),
                    line=int(match.group(2)),
                    column=int(match.group(3)),
                    error_code=match.group(5),
                    severity="error" if match.group(4) == "error" else "warning",
                )
            )

        return errors

    @classmethod
    def _get_csharp_suggestions(cls, error_type: str) -> List[str]:
        """Get C#-specific suggestions."""
        suggestions_map = {
            "NullReferenceException": [
                "Use null-conditional operator (?.) for safe access",
                "Use null-coalescing operator (??) for defaults",
                "Enable nullable reference types",
                "Add null checks before accessing members",
            ],
            "InvalidOperationException": [
                "Check object state before operation",
                "Verify collection is not empty",
                "Review operation sequence",
            ],
            "ArgumentException": [
                "Validate arguments at method entry",
                "Use ArgumentNullException.ThrowIfNull()",
                "Check for valid enum values",
            ],
            "InvalidCastException": [
                "Use 'as' operator for safe casting",
                "Check type with 'is' before casting",
                "Use pattern matching",
            ],
            "IndexOutOfRangeException": [
                "Check collection bounds",
                "Use foreach instead of index",
                "Validate index before access",
            ],
            "OutOfMemoryException": [
                "Dispose IDisposable objects",
                "Use 'using' statements",
                "Consider streaming for large data",
            ],
        }

        for key, suggs in suggestions_map.items():
            if key in error_type:
                return suggs

        return ["Review .NET documentation"]

    # ============================================================
    # RUBY PARSERS
    # ============================================================

    @classmethod
    def _parse_ruby_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse Ruby exceptions."""
        errors = []

        # Exception format
        exception_match = re.search(
            r"(\w+(?:Error|Exception)):\s*(.+?)(?:\n|$)", output
        )
        if exception_match:
            error = ParsedError(
                language="ruby",
                category=ErrorCategory.RUNTIME,
                error_type=exception_match.group(1),
                message=exception_match.group(2),
            )

            # Stack trace: /path/file.rb:line:in `method'
            stack_pattern = r"([/\w.-]+\.rb):(\d+)(?::in\s+[`\'](\w+)[\'`])?"
            for match in re.finditer(stack_pattern, output):
                frame = {
                    "file": match.group(1),
                    "line": int(match.group(2)),
                }
                if match.group(3):
                    frame["function"] = match.group(3)
                error.stack_trace.append(frame)

            if error.stack_trace:
                error.file_path = error.stack_trace[0]["file"]
                error.line = error.stack_trace[0]["line"]

            error.suggestions = cls._get_ruby_suggestions(error.error_type)
            errors.append(error)

        return errors

    @classmethod
    def _parse_rubocop_output(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse RuboCop output."""
        errors = []

        # Format: file.rb:line:col: C/W/E: Cop/Name: message
        pattern = r"([^:\s]+\.rb):(\d+):(\d+):\s*([CWE]):\s*(?:(\S+):\s*)?(.+)"
        for match in re.finditer(pattern, output):
            severity_map = {"C": "info", "W": "warning", "E": "error"}
            errors.append(
                ParsedError(
                    language="ruby",
                    category=ErrorCategory.LINT,
                    error_type=match.group(5) or "rubocop",
                    message=match.group(6),
                    file_path=match.group(1),
                    line=int(match.group(2)),
                    column=int(match.group(3)),
                    severity=severity_map.get(match.group(4), "warning"),
                )
            )

        return errors

    @classmethod
    def _parse_rspec_output(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse RSpec test output."""
        errors = []

        # Failure: spec_name
        fail_pattern = r"Failure/Error:\s*(.+?)(?:\n\s+(.+))?"
        for match in re.finditer(fail_pattern, output, re.MULTILINE):
            errors.append(
                ParsedError(
                    language="ruby",
                    category=ErrorCategory.TEST,
                    error_type="TestFailure",
                    message=match.group(1)
                    + (f": {match.group(2)}" if match.group(2) else ""),
                    suggestions=[
                        "Check expected vs actual values",
                        "Verify test setup",
                        "Review mock/stub configuration",
                    ],
                )
            )

        return errors

    @classmethod
    def _get_ruby_suggestions(cls, error_type: str) -> List[str]:
        """Get Ruby-specific suggestions."""
        suggestions_map = {
            "NoMethodError": [
                "Check if object responds_to? the method",
                "Verify object is not nil",
                "Use safe navigation operator (&.)",
            ],
            "NameError": [
                "Check for typos in variable/method name",
                "Verify constant is defined",
                "Check require/require_relative",
            ],
            "ArgumentError": [
                "Check number of arguments",
                "Verify argument types",
                "Review method signature",
            ],
            "TypeError": [
                "Check object type before operation",
                "Verify type compatibility",
                "Use explicit type conversion",
            ],
            "LoadError": [
                "Check gem is installed",
                "Run: bundle install",
                "Verify require path",
            ],
        }

        for key, suggs in suggestions_map.items():
            if key in error_type:
                return suggs

        return ["Review Ruby documentation"]

    # ============================================================
    # PHP PARSERS
    # ============================================================

    @classmethod
    def _parse_php_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse PHP errors."""
        errors = []

        # Fatal error format
        fatal_pattern = r"(?:Fatal error|PHP Fatal[^:]*|Exception):\s*(.+?)\s+in\s+([^\s]+)\s+on\s+line\s+(\d+)"
        for match in re.finditer(fatal_pattern, output, re.IGNORECASE):
            errors.append(
                ParsedError(
                    language="php",
                    category=ErrorCategory.RUNTIME,
                    error_type="FatalError",
                    message=match.group(1),
                    file_path=match.group(2),
                    line=int(match.group(3)),
                    suggestions=[
                        "Check for undefined functions/classes",
                        "Verify autoloading configuration",
                        "Review error message for details",
                    ],
                )
            )

        # Stack trace: #N /path/file.php(line): function()
        stack_pattern = r"#(\d+)\s+([^\(]+)\((\d+)\):\s*([\w\\]+(?:->|::)?\w+)"
        for match in re.finditer(stack_pattern, output):
            if errors:
                errors[-1].stack_trace.append(
                    {
                        "index": int(match.group(1)),
                        "file": match.group(2),
                        "line": int(match.group(3)),
                        "function": match.group(4),
                    }
                )

        return errors

    @classmethod
    def _parse_phpstan_output(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse PHPStan output."""
        errors = []

        # Format: Line   file.php
        #         N      Error message
        pattern = r"(\d+)\s+(.+\.php)\n\s+(.+)"
        for match in re.finditer(pattern, output):
            errors.append(
                ParsedError(
                    language="php",
                    category=ErrorCategory.TYPE,
                    error_type="phpstan",
                    message=match.group(3),
                    file_path=match.group(2),
                    line=int(match.group(1)),
                )
            )

        return errors

    @classmethod
    def _parse_phpunit_output(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse PHPUnit test output."""
        errors = []

        # Test failure
        fail_pattern = r"FAILURES!\s*Tests:\s*(\d+).*Failures:\s*(\d+)"
        if re.search(fail_pattern, output):
            # Individual failures
            test_pattern = r"(\d+)\)\s+(\w+::test\w+)"
            for match in re.finditer(test_pattern, output):
                errors.append(
                    ParsedError(
                        language="php",
                        category=ErrorCategory.TEST,
                        error_type="TestFailure",
                        message=f"Test {match.group(2)} failed",
                        function=match.group(2),
                    )
                )

        return errors

    # ============================================================
    # OTHER LANGUAGE PARSERS
    # ============================================================

    @classmethod
    def _parse_scala_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse Scala errors."""
        errors = []

        # Compiler error: file.scala:line: error: message
        pattern = r"([^:\s]+\.scala):(\d+):\s*(error|warning):\s*(.+)"
        for match in re.finditer(pattern, output):
            errors.append(
                ParsedError(
                    language="scala",
                    category=ErrorCategory.COMPILE,
                    error_type="scalac_error",
                    message=match.group(4),
                    file_path=match.group(1),
                    line=int(match.group(2)),
                    severity="error" if match.group(3) == "error" else "warning",
                )
            )

        return errors

    @classmethod
    def _parse_elixir_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse Elixir errors."""
        errors = []

        # Compile error: ** (CompileError) file.ex:line: message
        pattern = r"\*\*\s*\((\w+)\)\s*([^:]+):(\d+):\s*(.+)"
        for match in re.finditer(pattern, output):
            errors.append(
                ParsedError(
                    language="elixir",
                    category=ErrorCategory.COMPILE,
                    error_type=match.group(1),
                    message=match.group(4),
                    file_path=match.group(2),
                    line=int(match.group(3)),
                )
            )

        return errors

    @classmethod
    def _parse_haskell_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse Haskell/GHC errors."""
        errors = []

        # GHC format: file.hs:line:col: error: message
        pattern = r"([^:\s]+\.hs):(\d+):(\d+):\s*(error|warning):\s*(.+)"
        for match in re.finditer(pattern, output):
            errors.append(
                ParsedError(
                    language="haskell",
                    category=ErrorCategory.COMPILE,
                    error_type="ghc_error",
                    message=match.group(5),
                    file_path=match.group(1),
                    line=int(match.group(2)),
                    column=int(match.group(3)),
                    severity="error" if match.group(4) == "error" else "warning",
                )
            )

        return errors

    @classmethod
    def _parse_dart_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse Dart/Flutter errors."""
        errors = []

        # Dart analyzer: file.dart:line:col • message • code
        pattern = r"([^:\s]+\.dart):(\d+):(\d+)\s*[•·]\s*(.+?)\s*[•·]\s*(\S+)"
        for match in re.finditer(pattern, output):
            errors.append(
                ParsedError(
                    language="dart",
                    category=ErrorCategory.LINT,
                    error_type=match.group(5),
                    message=match.group(4),
                    file_path=match.group(1),
                    line=int(match.group(2)),
                    column=int(match.group(3)),
                    error_code=match.group(5),
                )
            )

        return errors

    # ============================================================
    # BUILD SYSTEM PARSERS
    # ============================================================

    @classmethod
    def _parse_npm_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse npm errors."""
        errors = []

        # npm ERR! message
        pattern = r"npm ERR!\s*(.+)"
        messages = re.findall(pattern, output)
        if messages:
            errors.append(
                ParsedError(
                    language="javascript",
                    category=ErrorCategory.BUILD,
                    error_type="npm_error",
                    message="\n".join(messages[:5]),
                    suggestions=[
                        "Run: npm cache clean --force",
                        "Delete node_modules and run: npm install",
                        "Check package.json for version conflicts",
                    ],
                )
            )

        return errors

    @classmethod
    def _parse_yarn_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse yarn errors."""
        errors = []

        # error message
        pattern = r"error\s+(.+)"
        for match in re.finditer(pattern, output, re.IGNORECASE):
            errors.append(
                ParsedError(
                    language="javascript",
                    category=ErrorCategory.BUILD,
                    error_type="yarn_error",
                    message=match.group(1),
                )
            )

        return errors

    @classmethod
    def _parse_pip_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse pip errors."""
        errors = []

        # ERROR: message
        pattern = r"ERROR:\s*(.+)"
        for match in re.finditer(pattern, output):
            errors.append(
                ParsedError(
                    language="python",
                    category=ErrorCategory.BUILD,
                    error_type="pip_error",
                    message=match.group(1),
                    suggestions=[
                        "Upgrade pip: pip install --upgrade pip",
                        "Check Python version compatibility",
                        "Try: pip install --no-cache-dir",
                    ],
                )
            )

        return errors

    @classmethod
    def _parse_cargo_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse Cargo build errors."""
        errors = []

        # error: message or error[E####]: message
        pattern = r"error(?:\[([^\]]+)\])?:\s*(.+?)(?:\n|$)"
        for match in re.finditer(pattern, output):
            errors.append(
                ParsedError(
                    language="rust",
                    category=ErrorCategory.BUILD,
                    error_type=match.group(1) or "cargo_error",
                    message=match.group(2),
                    error_code=match.group(1),
                )
            )

        return errors

    @classmethod
    def _parse_cmake_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse CMake errors."""
        errors = []

        # CMake Error at file:line
        pattern = r"CMake Error at\s+([^:]+):(\d+)"
        for match in re.finditer(pattern, output):
            errors.append(
                ParsedError(
                    language="cmake",
                    category=ErrorCategory.BUILD,
                    error_type="cmake_error",
                    message=output[match.end() : match.end() + 200]
                    .strip()
                    .split("\n")[0],
                    file_path=match.group(1),
                    line=int(match.group(2)),
                )
            )

        return errors

    @classmethod
    def _parse_make_error(cls, output: str, workspace: str) -> List[ParsedError]:
        """Parse Make errors."""
        errors = []

        # make: *** [target] Error N
        pattern = r"make:\s*\*\*\*\s*\[([^\]]+)\]\s*Error\s*(\d+)"
        for match in re.finditer(pattern, output):
            errors.append(
                ParsedError(
                    language="make",
                    category=ErrorCategory.BUILD,
                    error_type="make_error",
                    message=f"Target '{match.group(1)}' failed with error code {match.group(2)}",
                )
            )

        return errors

    # ============================================================
    # HELPER METHODS
    # ============================================================

    @classmethod
    def _generate_summary(
        cls, errors: List[Dict], warnings: List[Dict]
    ) -> Dict[str, Any]:
        """Generate summary of all errors."""
        summary = {
            "total_errors": len(errors),
            "total_warnings": len(warnings),
            "by_language": {},
            "by_category": {},
            "by_file": {},
        }

        for e in errors + warnings:
            # By language
            lang = e.get("language", "unknown")
            summary["by_language"][lang] = summary["by_language"].get(lang, 0) + 1

            # By category
            cat = e.get("category", "unknown")
            summary["by_category"][cat] = summary["by_category"].get(cat, 0) + 1

            # By file
            file = e.get("file")
            if file:
                summary["by_file"][file] = summary["by_file"].get(file, 0) + 1

        return summary

    @classmethod
    def _generate_auto_fixes(
        cls, errors: List[Dict], workspace: str
    ) -> List[Dict[str, Any]]:
        """Generate auto-fix suggestions for errors."""
        fixes = []

        for error in errors:
            fix = cls._get_auto_fix(error, workspace)
            if fix:
                fixes.append(fix)

        return fixes

    @classmethod
    def _get_auto_fix(cls, error: Dict, workspace: str) -> Optional[Dict[str, Any]]:
        """Get auto-fix for a specific error."""
        error_type = error.get("error_type", "")
        language = error.get("language", "")

        # Python auto-fixes
        if language == "python":
            if error_type == "ImportError" or error_type == "ModuleNotFoundError":
                module = re.search(
                    r"No module named ['\"](\w+)['\"]", error.get("message", "")
                )
                if module:
                    return {
                        "type": "command",
                        "command": f"pip install {module.group(1)}",
                        "description": f"Install missing module: {module.group(1)}",
                    }

        # JavaScript auto-fixes
        if language in ("javascript", "typescript"):
            if "Cannot find module" in error.get("message", ""):
                module = re.search(
                    r"Cannot find module ['\"]([^'\"]+)['\"]", error.get("message", "")
                )
                if module:
                    return {
                        "type": "command",
                        "command": f"npm install {module.group(1)}",
                        "description": f"Install missing module: {module.group(1)}",
                    }

        return None

    @classmethod
    def _generate_suggested_commands(cls, errors: List[Dict]) -> List[str]:
        """Generate suggested debugging commands."""
        commands = []
        languages = {e.get("language") for e in errors}

        if "python" in languages:
            commands.extend(
                [
                    "python -m pytest -v",
                    "python -m mypy .",
                    "python -m pylint .",
                ]
            )

        if "javascript" in languages or "typescript" in languages:
            commands.extend(
                [
                    "npm test",
                    "npm run lint",
                    "npx tsc --noEmit",
                ]
            )

        if "go" in languages:
            commands.extend(
                [
                    "go test ./...",
                    "go vet ./...",
                    "staticcheck ./...",
                ]
            )

        if "rust" in languages:
            commands.extend(
                [
                    "cargo test",
                    "cargo clippy",
                    "cargo check",
                ]
            )

        if "cpp" in languages or "c" in languages:
            commands.extend(
                [
                    "make clean && make",
                    "valgrind --leak-check=full ./program",
                ]
            )

        return commands


# Public API functions
async def analyze_errors(
    error_output: str,
    workspace_path: str = ".",
    context: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Analyze error output from any supported language/tool.

    Args:
        error_output: The error message, traceback, or compiler output
        workspace_path: Path to the workspace for context
        context: Optional additional context

    Returns:
        Structured analysis with errors, suggestions, and auto-fixes
    """
    return await ComprehensiveDebugger.analyze(error_output, workspace_path, context)
