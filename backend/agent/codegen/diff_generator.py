"""
Diff Generator for NAVI Phase 3.3 Code Generation Engine.

Responsibility:
- Generate unified diffs ONLY
- Enforce diff-only output (no full-file rewrites)
- Remain model-agnostic (LLM integration happens via adapters)

This module does NOT:
- Apply patches
- Validate syntax
- Execute tools
"""

from __future__ import annotations

import difflib
from typing import Dict, List, Protocol

from backend.agent.codegen.types import (
    ChangePlan,
    PlannedFileChange,
    CodeChange,
    ChangeIntent,
)
from backend.agent.codegen.context_assembler import FileContext


def validate_unified_diff(diff: str) -> bool:
    """Validate that a string is a proper unified diff."""
    if not diff.strip():
        return False
    
    lines = diff.splitlines()
    if not lines:
        return False
    
    # Check for unified diff headers
    has_from_file = any(line.startswith('---') for line in lines[:10])
    has_to_file = any(line.startswith('+++') for line in lines[:10])
    has_hunk_header = any(line.startswith('@@') for line in lines)
    
    return has_from_file and has_to_file and has_hunk_header


# ---------------------------------------------------------------------------
# Protocols (Model-Agnostic)
# ---------------------------------------------------------------------------

class DiffSynthesisBackend(Protocol):
    """
    Protocol for any backend capable of proposing diff hunks.

    Implementations may be:
    - LLM-based
    - Rule-based
    - Template-based
    """

    def propose_diff(
        self,
        *,
        file_context: FileContext,
        planned_change: PlannedFileChange,
        plan: ChangePlan,
    ) -> str:
        """
        Return a unified diff string.
        Must NOT return full file contents.
        """
        ...


class DiffGenerationError(RuntimeError):
    """Raised when a valid unified diff cannot be produced."""


# ---------------------------------------------------------------------------
# Diff Generator
# ---------------------------------------------------------------------------

class DiffGenerator:
    """
    Generates diff-only CodeChange artifacts from a ChangePlan.
    """

    def __init__(
        self,
        *,
        synthesis_backend: DiffSynthesisBackend,
        max_diff_bytes: int = 128 * 1024,  # 128 KB per diff
    ) -> None:
        self._backend = synthesis_backend
        self._max_diff_bytes = max_diff_bytes

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        *,
        plan: ChangePlan,
        file_contexts: Dict[str, FileContext],
    ) -> List[CodeChange]:
        """
        Generate diff-only CodeChange objects for the given plan.

        :param plan: Approved ChangePlan
        :param file_contexts: Output of ContextAssembler
        """
        changes: List[CodeChange] = []

        for planned in plan.file_changes:
            ctx = file_contexts.get(planned.path)
            if not ctx:
                raise DiffGenerationError(
                    f"Missing FileContext for {planned.path}"
                )

            diff = self._generate_diff_for_file(
                planned_change=planned,
                ctx=ctx,
                plan=plan,
            )

            if not validate_unified_diff(diff):
                raise DiffGenerationError(
                    f"Invalid unified diff produced for {planned.path}"
                )

            if len(diff.encode("utf-8")) > self._max_diff_bytes:
                raise DiffGenerationError(
                    f"Diff exceeds max size ({self._max_diff_bytes} bytes) "
                    f"for {planned.path}"
                )

            changes.append(
                CodeChange(
                    line_start=0,  # Will be parsed from diff
                    line_end=0,    # Will be parsed from diff
                    original_code="",  # Will be extracted from diff
                    new_code="",      # Will be extracted from diff
                    change_type="replace",  # Default, can be refined
                    reasoning=planned.reasoning,
                    confidence=0.8,
                    # Add custom fields for diff storage
                    diff=diff,
                    file_path=planned.path,
                    change_intent=planned.intent,
                )
            )

        return changes

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_diff_for_file(
        self,
        *,
        planned_change: PlannedFileChange,
        ctx: FileContext,
        plan: ChangePlan,
    ) -> str:
        """
        Delegate diff synthesis and enforce invariants.
        """
        if planned_change.intent == ChangeIntent.CREATE:
            return self._generate_create_diff(planned_change, ctx)

        diff = self._backend.propose_diff(
            file_context=ctx,
            planned_change=planned_change,
            plan=plan,
        )

        if not diff.strip():
            raise DiffGenerationError(
                f"Empty diff generated for {planned_change.path}"
            )

        return diff

    def _generate_create_diff(
        self,
        planned_change: PlannedFileChange,
        ctx: FileContext,
    ) -> str:
        """
        Generate a unified diff for file creation.
        """
        if ctx.content is not None:
            raise DiffGenerationError(
                f"CREATE intent received but file already exists: {ctx.path}"
            )

        # For CREATE, backend must still provide content,
        # but we wrap it in a unified diff format.
        content = self._backend.propose_diff(
            file_context=ctx,
            planned_change=planned_change,
            plan=None,  # creation does not rely on existing content
        )

        if not content:
            raise DiffGenerationError(
                f"No content provided for CREATE diff: {ctx.path}"
            )

        diff = "\n".join(
            difflib.unified_diff(
                [],
                content.splitlines(keepends=True),
                fromfile="/dev/null",
                tofile=ctx.path,
                lineterm="",
            )
        )

        return diff