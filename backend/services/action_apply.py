from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass
class ApplyResult:
    files_created: List[str]
    files_modified: List[str]
    commands_run: List[str]
    command_failures: List[str]
    warnings: List[str]


def resolve_path(workspace_root: Path, file_path: str) -> Path:
    candidate = Path(file_path)
    if not candidate.is_absolute():
        candidate = workspace_root / candidate
    resolved = candidate.resolve()
    workspace_resolved = workspace_root.resolve()
    if not str(resolved).startswith(str(workspace_resolved)):
        raise ValueError(f"Path escapes workspace: {file_path}")
    return resolved


def apply_file_edits(
    workspace_root: str, file_edits: List[Dict[str, Any]]
) -> Tuple[List[str], List[str], List[str]]:
    root = Path(workspace_root)
    created: List[str] = []
    modified: List[str] = []
    warnings: List[str] = []

    for edit in file_edits:
        file_path = edit.get("filePath") or edit.get("path")
        if not file_path:
            warnings.append("Skipped edit with no filePath")
            continue
        operation = (edit.get("operation") or "modify").lower()
        content = edit.get("content", "")

        try:
            abs_path = resolve_path(root, file_path)
        except ValueError as exc:
            warnings.append(str(exc))
            continue

        abs_path.parent.mkdir(parents=True, exist_ok=True)
        exists = abs_path.exists()

        if operation in ("create", "write"):
            abs_path.write_text(content)
            created.append(str(abs_path))
        elif operation in ("modify", "edit"):
            if not exists:
                abs_path.write_text(content)
                created.append(str(abs_path))
            else:
                abs_path.write_text(content)
                modified.append(str(abs_path))
        elif operation == "delete":
            if exists:
                abs_path.unlink()
                modified.append(str(abs_path))
            else:
                warnings.append(f"File not found for delete: {file_path}")
        else:
            warnings.append(f"Unknown operation '{operation}' for {file_path}")

    return created, modified, warnings


def run_commands(
    workspace_root: str, commands: List[str]
) -> Tuple[List[str], List[str]]:
    ran: List[str] = []
    failures: List[str] = []
    for command in commands:
        result = subprocess.run(
            command,
            cwd=workspace_root,
            shell=True,
            capture_output=True,
            text=True,
        )
        ran.append(command)
        if result.returncode != 0:
            failures.append(
                f"{command} (exit {result.returncode})\n{result.stderr.strip()}"
            )
    return ran, failures


def handle_apply(
    workspace: str,
    response: Dict[str, Any],
    allow_commands: bool,
) -> ApplyResult:
    file_edits = response.get("file_edits", [])
    created, modified, warnings = apply_file_edits(workspace, file_edits)

    commands = response.get("commands_run", []) if allow_commands else []
    ran, failures = run_commands(workspace, commands) if commands else ([], [])

    return ApplyResult(
        files_created=created,
        files_modified=modified,
        commands_run=ran,
        command_failures=failures,
        warnings=warnings,
    )
