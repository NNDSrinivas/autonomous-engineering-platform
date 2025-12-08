# backend/navi/workflows/repo_diagnostics.py

from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class PatchKind(str, Enum):
    REPLACE_FILE = "replace_file"


@dataclass
class FileEdit:
    """
    Minimal FileEdit object used by Navi diagnostics.

    navi_chat.py only relies on:
      - relative_path
      - kind.value
      - new_text
      - description
    """

    relative_path: str
    kind: PatchKind
    new_text: str
    description: str


class RepoDiagnosticsWorkflow:
    """
    Lightweight diagnostics for JavaScript / TypeScript repos.

    Current checks:
      - package.json presence + JSON validity
      - presence of useful npm scripts (lint / test)
      - optional execution of `npm run lint` and `npm test` with short timeouts

    It then returns:
      - a structured summary dict for Navi to render
      - a list of FileEdit objects for simple, safe auto-fixes
    """

    def __init__(
        self, *, run_npm_scripts: bool = True, npm_timeout_sec: int = 25
    ) -> None:
        self.run_npm_scripts = run_npm_scripts
        self.npm_timeout_sec = npm_timeout_sec

    # --------------------------------------------------------------------- #
    # Public API called from navi_chat.py
    # --------------------------------------------------------------------- #

    async def diagnose_and_summarize(self, repo_root: Path) -> Dict:
        summary: Dict[str, List[str]] = {
            "high_level_findings": [],
            "blocking_issues": [],
            "non_blocking_issues": [],
            "fix_plan_steps": [],
        }

        raw_details: Dict[str, Dict] = {}

        pkg_path = repo_root / "package.json"
        pkg_data: Optional[dict] = None

        # 1) package.json presence + parse
        if not pkg_path.exists():
            summary["blocking_issues"].append("No package.json found at repo root.")
        else:
            summary["high_level_findings"].append("package.json present at repo root.")
            try:
                pkg_data = json.loads(pkg_path.read_text())
                if pkg_data is not None:
                    raw_details["package_json"] = pkg_data
            except json.JSONDecodeError as exc:
                msg = f"package.json could not be parsed: {exc}"
                summary["blocking_issues"].append(msg)
                # If JSON is invalid, don't attempt any further JS/TS checks.
                return {
                    "summary": summary,
                    "details": raw_details,
                }

        # 2) Inspect npm scripts if package.json parsed
        scripts = (pkg_data or {}).get("scripts", {}) if pkg_data else {}
        lint_script = scripts.get("lint")
        test_script = scripts.get("test")

        if not lint_script:
            summary["non_blocking_issues"].append(
                'No `lint` script defined in package.json. Consider adding `"lint": "eslint ."`.'
            )
        else:
            summary["high_level_findings"].append(
                f"`npm run lint` script found: `{lint_script}`"
            )

        if not test_script:
            summary["non_blocking_issues"].append(
                "No `test` script defined in package.json. Consider adding Jest / Vitest / your test runner."
            )
        else:
            summary["high_level_findings"].append(
                f"`npm test` script found: `{test_script}`"
            )

        # 3) Optional: actually run npm scripts
        ci_results: Dict[str, Dict] = {}
        if self.run_npm_scripts and pkg_path.exists():
            for script_name, label in (("lint", "lint"), ("test", "test")):
                if script_name not in scripts:
                    continue
                ok, output = await self._run_npm_script(repo_root, script_name)
                ci_results[script_name] = {
                    "ok": ok,
                    "output": output,
                }
                if not ok:
                    summary["blocking_issues"].append(
                        f"`npm run {script_name}` failed. See CI output in diagnostics details."
                    )
                else:
                    summary["high_level_findings"].append(
                        f"`npm run {script_name}` succeeded."
                    )

        raw_details["npm_scripts"] = ci_results

        # 4) Fix-plan suggestion bullets (high-level, human steps)
        if summary["blocking_issues"]:
            summary["fix_plan_steps"].append(
                {
                    "title": "Fix blocking issues",
                    "actions": summary["blocking_issues"],
                }
            )

        non_blocking_actions: List[str] = []
        if not lint_script:
            non_blocking_actions.append(
                'Add a `lint` script to package.json and wire up ESLint (for example: `"lint": "eslint ."`).'
            )
        if not test_script:
            non_blocking_actions.append(
                "Define a `test` script and configure a test runner (Jest, Vitest, Playwright, etc.)."
            )

        if non_blocking_actions:
            summary["fix_plan_steps"].append(
                {
                    "title": "Improve dev-experience & safety",
                    "actions": non_blocking_actions,
                }
            )

        return {
            "summary": summary,
            "details": raw_details,
        }

    async def plan_simple_fixes(
        self, repo_root: Path, diagnostics: Dict
    ) -> List[FileEdit]:
        """
        Plan safe, automatic edits. We keep this **very conservative**.

        Current behavior:
          - If package.json exists and parses
          - AND there is no `lint` script
          - add a basic `"lint": "eslint ."` script (or merge into scripts object).
        """
        edits: List[FileEdit] = []

        pkg_path = repo_root / "package.json"
        if not pkg_path.exists():
            return edits

        try:
            pkg_data = json.loads(pkg_path.read_text())
        except json.JSONDecodeError:
            # Already surfaced as blocking; do not auto-edit malformed JSON.
            return edits

        scripts = pkg_data.setdefault("scripts", {})

        if "lint" not in scripts:
            scripts["lint"] = "eslint ."

            new_text = json.dumps(pkg_data, indent=2) + "\n"
            edits.append(
                FileEdit(
                    relative_path=str(pkg_path.relative_to(repo_root)),
                    kind=PatchKind.REPLACE_FILE,
                    new_text=new_text,
                    description="Add a basic `npm run lint` script to package.json.",
                )
            )

        return edits

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    async def _run_npm_script(self, repo_root: Path, script: str) -> Tuple[bool, str]:
        """
        Run `npm run <script>` with a short timeout, returning (ok, combined_output).

        This runs blocking subprocess call in thread pool to avoid blocking FastAPI event loop.
        """

        def _run_sync() -> Tuple[bool, str]:
            try:
                completed = subprocess.run(
                    ["npm", "run", script],
                    cwd=str(repo_root),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=self.npm_timeout_sec,
                    check=False,
                    text=True,
                )
            except (FileNotFoundError, PermissionError) as exc:
                return False, f"Failed to run npm: {exc}"
            except subprocess.TimeoutExpired:
                return (
                    False,
                    f"`npm run {script}` timed out after {self.npm_timeout_sec} seconds.",
                )

            ok = completed.returncode == 0
            return ok, completed.stdout or ""

        return await asyncio.to_thread(_run_sync)
