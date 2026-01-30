"""
Code Validation Pipeline for NAVI

Validates generated code before presenting to users:
1. Syntax validation (language-specific)
2. Linting (style and best practices)
3. Type checking (for typed languages)
4. Security scanning (basic vulnerability detection)
5. Import validation (check if imports are valid)

Supports:
- Python (.py)
- JavaScript (.js)
- TypeScript (.ts, .tsx)
- Go (.go)
- Docker (Dockerfile)
- YAML (.yml, .yaml)
"""

import subprocess
import tempfile
import os
import re
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    ERROR = "error"  # Code won't run
    WARNING = "warning"  # Code runs but has issues
    INFO = "info"  # Suggestions


@dataclass
class ValidationIssue:
    level: ValidationLevel
    message: str
    line: Optional[int] = None
    column: Optional[int] = None
    rule: Optional[str] = None
    fix_suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    is_valid: bool
    language: str
    issues: List[ValidationIssue] = field(default_factory=list)
    syntax_valid: bool = True
    lint_passed: bool = True
    type_check_passed: bool = True
    security_passed: bool = True

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.level == ValidationLevel.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.level == ValidationLevel.WARNING)

    def to_dict(self) -> Dict:
        return {
            "is_valid": self.is_valid,
            "language": self.language,
            "syntax_valid": self.syntax_valid,
            "lint_passed": self.lint_passed,
            "type_check_passed": self.type_check_passed,
            "security_passed": self.security_passed,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [
                {
                    "level": i.level.value,
                    "message": i.message,
                    "line": i.line,
                    "column": i.column,
                    "rule": i.rule,
                    "fix_suggestion": i.fix_suggestion,
                }
                for i in self.issues
            ],
        }


class CodeValidator:
    """Main code validation class."""

    # Language detection by file extension
    LANGUAGE_MAP = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".json": "json",
        ".sql": "sql",
        ".sh": "bash",
        ".dockerfile": "dockerfile",
    }

    # Security patterns to detect
    SECURITY_PATTERNS = {
        "python": [
            (r"eval\s*\(", "Use of eval() is dangerous - potential code injection"),
            (r"exec\s*\(", "Use of exec() is dangerous - potential code injection"),
            (
                r"os\.system\s*\(",
                "Use of os.system() - prefer subprocess with shell=False",
            ),
            (
                r"subprocess.*shell\s*=\s*True",
                "subprocess with shell=True is vulnerable to injection",
            ),
            (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password detected"),
            (r'api_key\s*=\s*["\'][^"\']+["\']', "Hardcoded API key detected"),
            (r'secret\s*=\s*["\'][^"\']+["\']', "Hardcoded secret detected"),
            (r"pickle\.loads?\s*\(", "pickle is insecure - can execute arbitrary code"),
            (
                r"yaml\.load\s*\([^)]*\)",
                "yaml.load without Loader is unsafe - use safe_load",
            ),
        ],
        "javascript": [
            (r"eval\s*\(", "Use of eval() is dangerous"),
            (
                r"innerHTML\s*=",
                "innerHTML can lead to XSS - use textContent or sanitize",
            ),
            (r"document\.write\s*\(", "document.write can be exploited"),
            (r'password\s*[=:]\s*["\'][^"\']+["\']', "Hardcoded password detected"),
            (r'api_key\s*[=:]\s*["\'][^"\']+["\']', "Hardcoded API key detected"),
        ],
        "sql": [
            (r"SELECT\s+\*\s+FROM", "SELECT * is inefficient - specify columns"),
            (
                r"'\s*\+\s*\w+\s*\+\s*'",
                "String concatenation in SQL - use parameterized queries",
            ),
            (r"DROP\s+TABLE", "DROP TABLE detected - ensure this is intentional"),
            (r"DELETE\s+FROM\s+\w+\s*$", "DELETE without WHERE - will delete all rows"),
        ],
    }

    def __init__(self):
        self._check_tools()

    def _check_tools(self):
        """Check which validation tools are available."""
        self.tools = {
            "python_syntax": True,  # Always available via py_compile
            "ruff": self._command_exists("ruff"),
            "pylint": self._command_exists("pylint"),
            "mypy": self._command_exists("mypy"),
            "eslint": self._command_exists("eslint"),
            "tsc": self._command_exists("tsc"),
            "go": self._command_exists("go"),
            "rustc": self._command_exists("rustc"),
        }
        logger.info(f"Code validator tools available: {self.tools}")

    def _command_exists(self, cmd: str) -> bool:
        """Check if a command exists."""
        try:
            subprocess.run(["which", cmd], capture_output=True, timeout=5)
            return True
        except Exception:
            return False

    def _get_node_env(self) -> dict:
        """Get environment for Node.js commands with nvm compatibility."""
        env = os.environ.copy()
        env.pop("npm_config_prefix", None)  # Remove to fix nvm compatibility
        env["SHELL"] = env.get("SHELL", "/bin/bash")
        return env

    def _get_node_command_with_setup(self, cmd_args: List[str]) -> Tuple[str, dict]:
        """
        Get shell command with nvm setup for Node.js tools.
        Returns (command_string, env_dict).
        """
        env = self._get_node_env()
        home = os.environ.get("HOME", os.path.expanduser("~"))

        # Build command with nvm setup
        cmd_str = " ".join(cmd_args)
        nvm_dir = env.get("NVM_DIR", os.path.join(home, ".nvm"))
        if os.path.exists(os.path.join(nvm_dir, "nvm.sh")):
            full_cmd = (
                f"unset npm_config_prefix 2>/dev/null; "
                f'export NVM_DIR="{nvm_dir}" && '
                f'[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" --no-use 2>/dev/null && '
                f"nvm use default 2>/dev/null || true && {cmd_str}"
            )
        else:
            full_cmd = cmd_str

        return full_cmd, env

    def detect_language(self, filepath: str, content: str = None) -> str:
        """Detect language from filepath or content."""
        path = Path(filepath)
        ext = path.suffix.lower()

        # Special case for Dockerfile
        if path.name.lower() == "dockerfile" or path.name.lower().startswith(
            "dockerfile."
        ):
            return "dockerfile"

        if ext in self.LANGUAGE_MAP:
            return self.LANGUAGE_MAP[ext]

        # Try to detect from content
        if content:
            if "#!/usr/bin/env python" in content or "#!/usr/bin/python" in content:
                return "python"
            if "#!/bin/bash" in content or "#!/bin/sh" in content:
                return "bash"
            if content.strip().startswith("FROM "):
                return "dockerfile"

        return "unknown"

    def validate(self, filepath: str, content: str) -> ValidationResult:
        """Validate code and return results."""
        language = self.detect_language(filepath, content)

        result = ValidationResult(
            is_valid=True,
            language=language,
        )

        if language == "unknown":
            result.issues.append(
                ValidationIssue(
                    level=ValidationLevel.INFO,
                    message=f"Unknown language for {filepath} - skipping validation",
                )
            )
            return result

        # Run language-specific validation
        validator_method = getattr(self, f"_validate_{language}", None)
        if validator_method:
            validator_method(filepath, content, result)
        else:
            # Fallback to basic validation
            self._validate_basic(filepath, content, result)

        # Run security scan
        self._security_scan(content, language, result)

        # Update is_valid based on errors
        result.is_valid = result.error_count == 0

        return result

    def validate_multiple(self, files: Dict[str, str]) -> Dict[str, ValidationResult]:
        """Validate multiple files."""
        results = {}
        for filepath, content in files.items():
            results[filepath] = self.validate(filepath, content)
        return results

    # ============================================================
    # LANGUAGE-SPECIFIC VALIDATORS
    # ============================================================

    def _validate_python(self, filepath: str, content: str, result: ValidationResult):
        """Validate Python code."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            # 1. Syntax check (py_compile)
            proc = subprocess.run(
                ["python3", "-m", "py_compile", temp_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode != 0:
                result.syntax_valid = False
                # Parse error message
                error_msg = proc.stderr or proc.stdout
                match = re.search(r"line (\d+)", error_msg)
                line_num = int(match.group(1)) if match else None
                result.issues.append(
                    ValidationIssue(
                        level=ValidationLevel.ERROR,
                        message=f"Syntax error: {error_msg[:200]}",
                        line=line_num,
                        rule="syntax",
                    )
                )

            # 2. Linting with ruff (fast) or pylint
            if self.tools.get("ruff"):
                self._run_ruff(temp_path, result)
            elif self.tools.get("pylint"):
                self._run_pylint(temp_path, result)

            # 3. Type checking with mypy
            if self.tools.get("mypy"):
                self._run_mypy(temp_path, result)

            # 4. Check imports
            self._check_python_imports(content, result)

        finally:
            os.unlink(temp_path)

    def _run_ruff(self, filepath: str, result: ValidationResult):
        """Run ruff linter."""
        try:
            proc = subprocess.run(
                ["ruff", "check", "--output-format=json", filepath],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.stdout:
                issues = json.loads(proc.stdout)
                for issue in issues[:10]:  # Limit to 10 issues
                    result.issues.append(
                        ValidationIssue(
                            level=ValidationLevel.WARNING,
                            message=issue.get("message", "Unknown issue"),
                            line=issue.get("location", {}).get("row"),
                            column=issue.get("location", {}).get("column"),
                            rule=issue.get("code"),
                            fix_suggestion=issue.get("fix", {}).get("message"),
                        )
                    )
                if issues:
                    result.lint_passed = False
        except Exception as e:
            logger.warning(f"Ruff failed: {e}")

    def _run_pylint(self, filepath: str, result: ValidationResult):
        """Run pylint."""
        try:
            proc = subprocess.run(
                ["pylint", "--output-format=json", "--max-line-length=120", filepath],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.stdout:
                issues = json.loads(proc.stdout)
                for issue in issues[:10]:
                    level = (
                        ValidationLevel.ERROR
                        if issue.get("type") == "error"
                        else ValidationLevel.WARNING
                    )
                    result.issues.append(
                        ValidationIssue(
                            level=level,
                            message=issue.get("message", "Unknown"),
                            line=issue.get("line"),
                            column=issue.get("column"),
                            rule=issue.get("message-id"),
                        )
                    )
                if any(i.get("type") == "error" for i in issues):
                    result.lint_passed = False
        except Exception as e:
            logger.warning(f"Pylint failed: {e}")

    def _run_mypy(self, filepath: str, result: ValidationResult):
        """Run mypy type checker."""
        try:
            proc = subprocess.run(
                ["mypy", "--ignore-missing-imports", "--no-error-summary", filepath],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode != 0 and proc.stdout:
                for line in proc.stdout.strip().split("\n")[:5]:
                    match = re.match(r".*:(\d+): (error|warning): (.+)", line)
                    if match:
                        result.issues.append(
                            ValidationIssue(
                                level=ValidationLevel.WARNING,
                                message=match.group(3),
                                line=int(match.group(1)),
                                rule="mypy",
                            )
                        )
                result.type_check_passed = False
        except Exception as e:
            logger.warning(f"Mypy failed: {e}")

    def _check_python_imports(self, content: str, result: ValidationResult):
        """Check Python imports for common issues."""
        # Find all imports
        imports = re.findall(r"^(?:from\s+(\S+)|import\s+(\S+))", content, re.MULTILINE)

        # Check for relative imports in what looks like a standalone file
        for match in imports:
            module = match[0] or match[1]
            if module.startswith("."):
                result.issues.append(
                    ValidationIssue(
                        level=ValidationLevel.INFO,
                        message=f"Relative import '{module}' - ensure package structure exists",
                        rule="import-check",
                    )
                )

    def _validate_javascript(
        self, filepath: str, content: str, result: ValidationResult
    ):
        """Validate JavaScript code."""
        # Basic syntax check using Node
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            # Use shell command with nvm setup for proper Node.js environment
            full_cmd, env = self._get_node_command_with_setup(
                ["node", "--check", temp_path]
            )
            proc = subprocess.run(
                full_cmd,
                shell=True,
                executable="/bin/bash",
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )
            if proc.returncode != 0:
                result.syntax_valid = False
                result.issues.append(
                    ValidationIssue(
                        level=ValidationLevel.ERROR,
                        message=f"Syntax error: {proc.stderr[:200]}",
                        rule="syntax",
                    )
                )
        except FileNotFoundError:
            # Node not installed, skip syntax check
            pass
        except Exception as e:
            logger.warning(f"JS validation failed: {e}")
        finally:
            os.unlink(temp_path)

    def _validate_typescript(
        self, filepath: str, content: str, result: ValidationResult
    ):
        """Validate TypeScript code."""
        # TypeScript validation needs tsc
        if not self.tools.get("tsc"):
            result.issues.append(
                ValidationIssue(
                    level=ValidationLevel.INFO,
                    message="TypeScript compiler not available - skipping type check",
                )
            )
            return

        with tempfile.NamedTemporaryFile(mode="w", suffix=".ts", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            # Use shell command with nvm setup for proper Node.js environment
            full_cmd, env = self._get_node_command_with_setup(
                ["tsc", "--noEmit", "--esModuleInterop", "--skipLibCheck", temp_path]
            )
            proc = subprocess.run(
                full_cmd,
                shell=True,
                executable="/bin/bash",
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )
            if proc.returncode != 0:
                # tsc outputs errors to stdout, not stderr
                output = proc.stdout or proc.stderr
                for line in output.strip().split("\n")[:5]:
                    if line.strip():
                        result.issues.append(
                            ValidationIssue(
                                level=ValidationLevel.ERROR,
                                message=line[:200],
                                rule="typescript",
                            )
                        )
                result.type_check_passed = False
        except Exception as e:
            logger.warning(f"TS validation failed: {e}")
        finally:
            os.unlink(temp_path)

    def _validate_go(self, filepath: str, content: str, result: ValidationResult):
        """Validate Go code."""
        if not self.tools.get("go"):
            return

        # Create temp directory for Go module
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write go.mod
            go_mod = Path(tmpdir) / "go.mod"
            go_mod.write_text("module temp\n\ngo 1.21\n")

            # Write file
            go_file = Path(tmpdir) / "main.go"
            go_file.write_text(content)

            try:
                # Check syntax
                proc = subprocess.run(
                    ["go", "build", "-o", "/dev/null", "."],
                    capture_output=True,
                    text=True,
                    cwd=tmpdir,
                    timeout=30,
                )
                if proc.returncode != 0:
                    result.syntax_valid = False
                    result.issues.append(
                        ValidationIssue(
                            level=ValidationLevel.ERROR,
                            message=proc.stderr[:200],
                            rule="go-build",
                        )
                    )

                # Run go vet
                proc = subprocess.run(
                    ["go", "vet", "."],
                    capture_output=True,
                    text=True,
                    cwd=tmpdir,
                    timeout=30,
                )
                if proc.returncode != 0:
                    result.issues.append(
                        ValidationIssue(
                            level=ValidationLevel.WARNING,
                            message=proc.stderr[:200],
                            rule="go-vet",
                        )
                    )
            except Exception as e:
                logger.warning(f"Go validation failed: {e}")

    def _validate_yaml(self, filepath: str, content: str, result: ValidationResult):
        """Validate YAML syntax."""
        try:
            import yaml

            yaml.safe_load(content)
        except yaml.YAMLError as e:
            result.syntax_valid = False
            result.issues.append(
                ValidationIssue(
                    level=ValidationLevel.ERROR,
                    message=f"YAML syntax error: {str(e)[:200]}",
                    rule="yaml-syntax",
                )
            )
        except ImportError:
            # PyYAML not installed
            pass

    def _validate_json(self, filepath: str, content: str, result: ValidationResult):
        """Validate JSON syntax."""
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            result.syntax_valid = False
            result.issues.append(
                ValidationIssue(
                    level=ValidationLevel.ERROR,
                    message=f"JSON syntax error at line {e.lineno}: {e.msg}",
                    line=e.lineno,
                    rule="json-syntax",
                )
            )

    def _validate_dockerfile(
        self, filepath: str, content: str, result: ValidationResult
    ):
        """Validate Dockerfile."""
        # Check for common Dockerfile issues
        lines = content.split("\n")
        has_from = False

        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("FROM"):
                has_from = True
                # Check for latest tag
                if ":latest" in line or (line.count(":") == 0 and " " in line):
                    result.issues.append(
                        ValidationIssue(
                            level=ValidationLevel.WARNING,
                            message="Avoid using 'latest' tag - pin to specific version",
                            line=i,
                            rule="dockerfile-latest",
                        )
                    )

            # Check for ADD vs COPY
            if line.startswith("ADD ") and "http" not in line and ".tar" not in line:
                result.issues.append(
                    ValidationIssue(
                        level=ValidationLevel.WARNING,
                        message="Use COPY instead of ADD for simple file copying",
                        line=i,
                        rule="dockerfile-add",
                    )
                )

            # Check for apt-get without cleanup
            if "apt-get install" in line and "rm -rf /var/lib/apt" not in content:
                result.issues.append(
                    ValidationIssue(
                        level=ValidationLevel.WARNING,
                        message="Consider cleaning apt cache to reduce image size",
                        line=i,
                        rule="dockerfile-apt-cleanup",
                    )
                )

        if not has_from:
            result.syntax_valid = False
            result.issues.append(
                ValidationIssue(
                    level=ValidationLevel.ERROR,
                    message="Dockerfile must start with FROM instruction",
                    rule="dockerfile-from",
                )
            )

    def _validate_sql(self, filepath: str, content: str, result: ValidationResult):
        """Validate SQL (basic checks)."""
        # Basic SQL validation - just pattern checks
        pass

    def _validate_bash(self, filepath: str, content: str, result: ValidationResult):
        """Validate bash script."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            # Check syntax with bash -n
            proc = subprocess.run(
                ["bash", "-n", temp_path], capture_output=True, text=True, timeout=10
            )
            if proc.returncode != 0:
                result.syntax_valid = False
                result.issues.append(
                    ValidationIssue(
                        level=ValidationLevel.ERROR,
                        message=f"Bash syntax error: {proc.stderr[:200]}",
                        rule="bash-syntax",
                    )
                )
        except Exception as e:
            logger.warning(f"Bash validation failed: {e}")
        finally:
            os.unlink(temp_path)

    def _validate_basic(self, filepath: str, content: str, result: ValidationResult):
        """Basic validation for unknown/unsupported languages."""
        # Just check it's not empty
        if not content.strip():
            result.issues.append(
                ValidationIssue(
                    level=ValidationLevel.WARNING,
                    message="File is empty",
                    rule="empty-file",
                )
            )

    # ============================================================
    # SECURITY SCANNING
    # ============================================================

    def _security_scan(self, content: str, language: str, result: ValidationResult):
        """Scan for security issues."""
        patterns = self.SECURITY_PATTERNS.get(language, [])

        for pattern, message in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                # Find line number
                line_num = content[: match.start()].count("\n") + 1
                result.issues.append(
                    ValidationIssue(
                        level=ValidationLevel.WARNING,
                        message=f"Security: {message}",
                        line=line_num,
                        rule="security",
                    )
                )
                result.security_passed = False


# ============================================================
# INTEGRATION WITH NAVI
# ============================================================

# Global validator instance
_validator = None


def get_validator() -> CodeValidator:
    """Get or create the global validator instance."""
    global _validator
    if _validator is None:
        _validator = CodeValidator()
    return _validator


def validate_navi_output(
    files: Dict[str, str],
) -> Tuple[bool, Dict[str, ValidationResult]]:
    """
    Validate NAVI's generated files before presenting to user.

    Returns:
        Tuple of (all_valid, results_by_file)
    """
    validator = get_validator()
    results = validator.validate_multiple(files)

    all_valid = all(r.is_valid for r in results.values())

    return all_valid, results


def format_validation_summary(results: Dict[str, ValidationResult]) -> str:
    """Format validation results as a summary string."""
    lines = []

    for filepath, result in results.items():
        if result.is_valid:
            lines.append(f"✅ {filepath}: Valid")
        else:
            lines.append(
                f"❌ {filepath}: {result.error_count} errors, {result.warning_count} warnings"
            )
            for issue in result.issues[:3]:
                loc = f"L{issue.line}" if issue.line else ""
                lines.append(f"   - [{issue.level.value}] {loc} {issue.message}")

    return "\n".join(lines)
