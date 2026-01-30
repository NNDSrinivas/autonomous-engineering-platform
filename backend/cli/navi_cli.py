#!/usr/bin/env python3
"""
NAVI CLI - invoke NAVI via API and optionally apply returned actions locally.

Usage:
  python backend/cli/navi_cli.py run --message "build a login page" --workspace /path/to/repo
  python backend/cli/navi_cli.py run --message "..." --apply --yes
  python backend/cli/navi_cli.py apply --response response.json --workspace /path/to/repo
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from backend.services.action_apply import apply_file_edits, run_commands
from backend.services.action_apply import ApplyResult


DEFAULT_BACKEND_URL = os.getenv("AEP_BACKEND_URL", "http://127.0.0.1:8787").rstrip("/")


def run_commands_with_approval(
    workspace_root: str, commands: List[str], auto_approve: bool
) -> Tuple[List[str], List[str]]:
    ran: List[str] = []
    failures: List[str] = []
    for command in commands:
        if not auto_approve:
            response = input(f"Run command? {command} [y/N]: ").strip().lower()
            if response not in ("y", "yes"):
                continue
        cmd_ran, cmd_failures = run_commands(workspace_root, [command])
        ran.extend(cmd_ran)
        failures.extend(cmd_failures)
    return ran, failures


def call_navi_process(
    backend_url: str,
    message: str,
    workspace: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"message": message, "workspace": workspace}
    if provider:
        payload["llm_provider"] = provider
    if model:
        payload["llm_model"] = model
    if api_key:
        payload["api_key"] = api_key

    url = f"{backend_url}/api/navi/process"
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()


def summarize_response(resp: Dict[str, Any]) -> None:
    print("NAVI response:")
    print(json.dumps(resp, indent=2))


def load_response(path: Optional[str]) -> Dict[str, Any]:
    if path:
        return json.loads(Path(path).read_text())
    data = sys.stdin.read().strip()
    if not data:
        raise ValueError("No response provided via --response or stdin")
    return json.loads(data)


def handle_apply_with_approval(
    workspace: str,
    response: Dict[str, Any],
    apply_commands: bool,
    auto_approve: bool,
) -> ApplyResult:
    file_edits = response.get("file_edits", [])
    created, modified, warnings = apply_file_edits(workspace, file_edits)

    commands = response.get("commands_run", []) if apply_commands else []
    ran, failures = (
        run_commands_with_approval(workspace, commands, auto_approve)
        if commands
        else ([], [])
    )

    return ApplyResult(
        files_created=created,
        files_modified=modified,
        commands_run=ran,
        command_failures=failures,
        warnings=warnings,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NAVI CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser(
        "run", help="Call /api/navi/process and optionally apply edits"
    )
    run_cmd.add_argument("--message", required=True, help="User request to NAVI")
    run_cmd.add_argument("--workspace", required=True, help="Workspace root path")
    run_cmd.add_argument(
        "--backend-url", default=DEFAULT_BACKEND_URL, help="Backend base URL"
    )
    run_cmd.add_argument(
        "--provider", default=None, help="LLM provider (openai, anthropic, ...)"
    )
    run_cmd.add_argument("--model", default=None, help="LLM model")
    run_cmd.add_argument("--api-key", default=None, help="API key (optional)")
    run_cmd.add_argument(
        "--apply", action="store_true", help="Apply file edits locally"
    )
    run_cmd.add_argument(
        "--yes", action="store_true", help="Auto-approve command execution"
    )
    run_cmd.add_argument(
        "--no-commands", action="store_true", help="Do not run commands"
    )
    run_cmd.add_argument(
        "--save-response", default=None, help="Write response JSON to file"
    )

    apply_cmd = sub.add_parser("apply", help="Apply a saved NAVI response JSON")
    apply_cmd.add_argument(
        "--response", default=None, help="Path to response JSON (or stdin)"
    )
    apply_cmd.add_argument("--workspace", required=True, help="Workspace root path")
    apply_cmd.add_argument(
        "--yes", action="store_true", help="Auto-approve command execution"
    )
    apply_cmd.add_argument(
        "--no-commands", action="store_true", help="Do not run commands"
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        response = call_navi_process(
            backend_url=args.backend_url,
            message=args.message,
            workspace=args.workspace,
            provider=args.provider,
            model=args.model,
            api_key=args.api_key,
        )

        if args.save_response:
            Path(args.save_response).write_text(json.dumps(response, indent=2))

        if not args.apply:
            summarize_response(response)
            return 0

        result = handle_apply_with_approval(
            workspace=args.workspace,
            response=response,
            apply_commands=not args.no_commands,
            auto_approve=args.yes,
        )
    else:
        response = load_response(args.response)
        result = handle_apply_with_approval(
            workspace=args.workspace,
            response=response,
            apply_commands=not args.no_commands,
            auto_approve=args.yes,
        )

    print("Applied changes:")
    print(f"- files created: {len(result.files_created)}")
    print(f"- files modified: {len(result.files_modified)}")
    if result.commands_run:
        print(f"- commands run: {len(result.commands_run)}")
    if result.command_failures:
        print("Command failures:")
        for failure in result.command_failures:
            print(failure)
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")

    return 1 if result.command_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
