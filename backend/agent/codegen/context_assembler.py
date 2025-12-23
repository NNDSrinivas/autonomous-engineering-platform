"""
Context Assembler for NAVI Phase 3.3 Code Generation Engine.

Responsibility:
- Load file contents safely
- Build bounded, file-scoped context
- Enforce scope, size, and policy limits
- Provide deterministic inputs to the diff generator

This module does NOT:
- Generate diffs
- Execute tools
- Call LLMs directly
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from backend.agent.codegen.types import PlannedFileChange, ChangeIntent


class ContextAssemblyError(RuntimeError):
    """Raised when file context cannot be safely assembled."""


@dataclass(frozen=True)
class FileContext:
    """
    Bounded context for a single file.
    """
    path: str
    intent: ChangeIntent
    content: Optional[str]
    language: Optional[str]
    size_bytes: int


class ContextAssembler:
    """
    Safely assembles file-scoped context for code generation.
    """

    DEFAULT_MAX_FILE_BYTES = 256 * 1024  # 256 KB per file
    DEFAULT_ALLOWED_EXTENSIONS = {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".md",
        ".sh",
        ".sql",
    }

    def __init__(
        self,
        *,
        repo_root: str,
        max_file_bytes: int | None = None,
        allowed_extensions: set[str] | None = None,
    ) -> None:
        self._repo_root = os.path.abspath(repo_root)
        self._max_file_bytes = max_file_bytes or self.DEFAULT_MAX_FILE_BYTES
        self._allowed_extensions = (
            allowed_extensions or self.DEFAULT_ALLOWED_EXTENSIONS
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assemble(
        self,
        planned_files: List[PlannedFileChange],
    ) -> Dict[str, FileContext]:
        """
        Assemble bounded context for all planned file changes.

        :param planned_files: Output of ChangePlanGenerator
        :return: Mapping of file path → FileContext
        """
        contexts: Dict[str, FileContext] = {}

        for planned in planned_files:
            file_path = planned.path
            abs_path = self._resolve_path(file_path)

            if planned.intent == ChangeIntent.CREATE:
                contexts[file_path] = FileContext(
                    path=file_path,
                    intent=planned.intent,
                    content=None,
                    language=self._infer_language(file_path),
                    size_bytes=0,
                )
                continue

            if not os.path.exists(abs_path):
                raise ContextAssemblyError(
                    f"File does not exist for intent {planned.intent}: {file_path}"
                )

            self._validate_extension(file_path)
            size_bytes = os.path.getsize(abs_path)
            if size_bytes > self._max_file_bytes:
                raise ContextAssemblyError(
                    f"File exceeds max size ({self._max_file_bytes} bytes): {file_path}"
                )

            content = self._read_file(abs_path)

            contexts[file_path] = FileContext(
                path=file_path,
                intent=planned.intent,
                content=content,
                language=self._infer_language(file_path),
                size_bytes=size_bytes,
            )

        return contexts

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_path(self, relative_path: str) -> str:
        """
        Resolve and validate that a path stays within the repo root.
        """
        abs_path = os.path.abspath(os.path.join(self._repo_root, relative_path))
        if not abs_path.startswith(self._repo_root):
            raise ContextAssemblyError(
                f"Path traversal detected: {relative_path}"
            )
        return abs_path

    def _validate_extension(self, path: str) -> None:
        ext = os.path.splitext(path)[1].lower()
        if ext and ext not in self._allowed_extensions:
            raise ContextAssemblyError(
                f"File extension not allowed for codegen: {path}"
            )

    def _read_file(self, abs_path: str) -> str:
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError as e:
            raise ContextAssemblyError(
                f"Failed to read file: {abs_path}"
            ) from e

    def _infer_language(self, path: str) -> Optional[str]:
        """
        Infer language from file extension.
        """
        ext = os.path.splitext(path)[1].lower()
        return {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescriptreact",
            ".js": "javascript",
            ".jsx": "javascriptreact",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".md": "markdown",
            ".sh": "shell",
            ".sql": "sql",
        }.get(ext)