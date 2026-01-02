"""
Syntax Validator for NAVI Phase 3.4.

Responsibility:
- Enforce language-aware syntax correctness
- Fail fast on parse errors
- Delegate to appropriate parsers per language

Order:
- Runs AFTER ScopeValidator
- Runs BEFORE Security / Policy validators
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import tempfile
from typing import Iterable, List

from backend.agent.codegen.types import CodeChange
from backend.agent.validation.result import (
    ValidationIssue,
    ValidationResult,
    ValidationStatus,
)

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class SyntaxValidator:
    """
    Validates syntax correctness for modified files based on file type.
    """

    def __init__(self, *, repo_root: str) -> None:
        self._repo_root = os.path.abspath(repo_root)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(self, changes: Iterable[CodeChange]) -> ValidationResult:
        issues: List[ValidationIssue] = []

        for change in changes:
            # Only validate files that result in actual content
            if not hasattr(change, 'diff') or not change.diff.strip():
                continue

            ext = os.path.splitext(change.file_path)[1].lower()

            try:
                if ext == ".py":
                    self._validate_python(change)
                elif ext in (".json",):
                    self._validate_json(change)
                elif ext in (".yaml", ".yml"):
                    self._validate_yaml(change)
                elif ext in (".js", ".jsx", ".ts", ".tsx"):
                    self._validate_javascript(change)
                else:
                    # Unknown / unsupported extensions are skipped by design
                    continue

            except Exception as e:
                issues.append(
                    ValidationIssue(
                        validator=self.__class__.__name__,
                        file_path=change.file_path,
                        message=str(e),
                    )
                )
                return ValidationResult(
                    status=ValidationStatus.FAILED,
                    issues=issues,
                )

        return ValidationResult(
            status=ValidationStatus.PASSED,
            issues=[],
        )

    # ------------------------------------------------------------------
    # Language-specific validators
    # ------------------------------------------------------------------

    def _validate_python(self, change: CodeChange) -> None:
        """
        Validate Python syntax using ast.parse on patched content.
        """
        content = self._apply_diff_to_temp_file(change)
        try:
            ast.parse(content)
        except SyntaxError as e:
            raise SyntaxError(
                f"Python syntax error at line {e.lineno}: {e.msg}"
            ) from e

    def _validate_json(self, change: CodeChange) -> None:
        """
        Validate JSON syntax.
        """
        content = self._apply_diff_to_temp_file(change)
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"JSON syntax error at line {e.lineno}: {e.msg}"
            ) from e

    def _validate_yaml(self, change: CodeChange) -> None:
        """
        Validate YAML syntax.
        """
        if not YAML_AVAILABLE:
            raise RuntimeError("YAML validation unavailable (PyYAML not installed)")
            
        content = self._apply_diff_to_temp_file(change)
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(
                f"YAML syntax error: {e}"
            ) from e

    def _validate_javascript(self, change: CodeChange) -> None:
        """
        Validate JS/TS syntax via Node-based parser.

        This delegates to the existing Node AST engine.
        """
        content = self._apply_diff_to_temp_file(change)

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=os.path.splitext(change.file_path)[1],
            delete=False,
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                ["node", "node_ast_engine/dist/runner.js", tmp_path],
                cwd=self._repo_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

        if result.returncode != 0:
            raise SyntaxError(
                f"JS/TS syntax error:\n{result.stderr.strip()}"
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _apply_diff_to_temp_file(self, change: CodeChange) -> str:
        """
        Apply a diff to the current file content in-memory
        and return the resulting content.

        NOTE:
        - This is a simplified implementation.
        - It relies on git apply to materialize content safely.
        """
        os.path.join(self._repo_root, change.file_path)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_repo = os.path.join(tmpdir, "repo")
            subprocess.run(
                ["git", "clone", "--no-checkout", self._repo_root, tmp_repo],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

            patch_file = os.path.join(tmpdir, "patch.diff")
            with open(patch_file, "w", encoding="utf-8") as f:
                f.write(change.diff)

            result = subprocess.run(
                ["git", "apply", patch_file],
                cwd=tmp_repo,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"Failed to apply patch for syntax validation:\n{result.stderr}"
                )

            final_path = os.path.join(tmp_repo, change.file_path)
            if not os.path.exists(final_path):
                # File may have been deleted
                return ""

            with open(final_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()