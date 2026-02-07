"""
Shared command helpers to keep execution behavior consistent across the codebase.

Focus:
- Environment setup (nvm/fnm/volta)
- Node command detection
- Command preparation with env setup
"""

from __future__ import annotations

import os
from typing import Iterable, List, Optional, Tuple

import subprocess
import asyncio


def is_node_command(command: str, extra_cmds: Optional[Iterable[str]] = None) -> bool:
    node_commands = {
        "npm",
        "npx",
        "node",
        "yarn",
        "pnpm",
        "bun",
        "tsc",
        "tsx",
        "ts-node",
        "jest",
        "vitest",
        "mocha",
        "webpack",
        "vite",
        "esbuild",
        "rollup",
        "parcel",
        "eslint",
        "prettier",
        "next",
        "nuxt",
        "gatsby",
    }
    if extra_cmds:
        node_commands.update(extra_cmds)

    cmd_parts = (command or "").split()
    if not cmd_parts:
        return False
    first_cmd = cmd_parts[0]
    return any(first_cmd == nc or first_cmd.endswith(f"/{nc}") for nc in node_commands)


def get_command_env() -> dict:
    """
    Base environment for commands with nvm-compat tweaks.
    """
    env = os.environ.copy()
    env.pop("npm_config_prefix", None)  # Remove to fix nvm compatibility
    env["SHELL"] = env.get("SHELL", "/bin/bash")
    return env


def get_node_env_setup(
    cwd: Optional[str] = None,
    include_project_bins: bool = True,
    include_common_paths: bool = True,
    fnm_use_on_cd: bool = True,
) -> str:
    """
    Generate shell commands to properly set up Node.js environment.
    Handles nvm, volta, fnm, and PATH additions.
    """
    home = os.environ.get("HOME", os.path.expanduser("~"))
    setup_commands: List[str] = []

    # nvm
    nvm_dir = os.environ.get("NVM_DIR", os.path.join(home, ".nvm"))
    if os.path.exists(os.path.join(nvm_dir, "nvm.sh")):
        setup_commands.append(
            f'export NVM_DIR="{nvm_dir}" && '
            f'[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" --no-use 2>/dev/null'
        )
        if cwd:
            nvmrc = os.path.join(cwd, ".nvmrc")
            node_version = os.path.join(cwd, ".node-version")
            if os.path.exists(nvmrc) or os.path.exists(node_version):
                setup_commands.append("nvm use 2>/dev/null || nvm install 2>/dev/null")
            else:
                setup_commands.append("nvm use default 2>/dev/null || true")
        else:
            setup_commands.append("nvm use default 2>/dev/null || true")

    # volta
    volta_home = os.environ.get("VOLTA_HOME", os.path.join(home, ".volta"))
    if os.path.exists(volta_home):
        setup_commands.append(f'export VOLTA_HOME="{volta_home}"')
        setup_commands.append('export PATH="$VOLTA_HOME/bin:$PATH"')

    # fnm
    fnm_path = os.path.join(home, ".fnm")
    if os.path.exists(fnm_path):
        setup_commands.append(f'export PATH="{fnm_path}:$PATH"')
        if fnm_use_on_cd:
            setup_commands.append(
                'eval "$(fnm env --use-on-cd 2>/dev/null)" 2>/dev/null || true'
            )
        else:
            setup_commands.append('eval "$(fnm env 2>/dev/null)" 2>/dev/null || true')

    # PATH additions
    if include_common_paths or include_project_bins:
        common_paths: List[str] = []
        if include_project_bins and cwd:
            node_modules_bin = os.path.join(cwd, "node_modules", ".bin")
            if os.path.exists(node_modules_bin):
                common_paths.append(node_modules_bin)
        if include_common_paths:
            common_paths.extend(
                [
                    "/opt/homebrew/bin",
                    "/usr/local/bin",
                    os.path.join(home, ".npm-global/bin"),
                    os.path.join(home, ".yarn/bin"),
                ]
            )
        existing_paths = [p for p in common_paths if os.path.exists(p)]
        if existing_paths:
            path_additions = ":".join(existing_paths)
            setup_commands.append(f'export PATH="{path_additions}:$PATH"')

    return " && ".join(setup_commands) if setup_commands else ""


def prepare_command(command: str, cwd: Optional[str] = None) -> str:
    """
    Prepare command with Node environment setup if needed.
    """
    if is_node_command(command):
        env_setup = get_node_env_setup(cwd)
        if env_setup:
            return f"unset npm_config_prefix 2>/dev/null; {env_setup} && {command}"
    return command


LONG_RUNNING_PATTERNS = [
    "npm install",
    "npm ci",
    "yarn install",
    "pnpm install",
    "bun install",
    "pip install",
    "poetry install",
    "pipenv install",
    "bundle install",
    "gem install",
    "composer install",
    "composer update",
    "cargo build",
    "cargo install",
    "mvn install",
    "mvn package",
    "mvn compile",
    "gradle build",
    "gradle assemble",
    "docker build",
    "docker-compose build",
    "npm run build",
    "yarn build",
    "pnpm build",
    "npm test",
    "yarn test",
    "pytest",
    "jest --",
]


def compute_timeout(command: str, timeout: int, min_long: int = 1200) -> int:
    """
    Normalize timeout for long-running commands.
    """
    if any(pattern in command for pattern in LONG_RUNNING_PATTERNS):
        return max(timeout, min_long)
    return timeout


def run_subprocess(
    command: str,
    cwd: Optional[str] = None,
    timeout: int = 60,
    merge_stderr: bool = False,
) -> Tuple[bool, str, str, int]:
    """
    Run a command synchronously with shared env setup.
    Returns (success, stdout, stderr, exit_code).
    """
    env = get_command_env()
    full_command = prepare_command(command, cwd)
    try:
        proc = subprocess.run(
            full_command,
            shell=True,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
            env=env,
            executable="/bin/bash",
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        if merge_stderr:
            stdout = stdout + ("\n" if stdout and stderr else "") + stderr
            stderr = ""
        return proc.returncode == 0, stdout, stderr, proc.returncode
    except subprocess.TimeoutExpired:
        # Return structured timeout failure (mirrors async behavior)
        return False, "", f"Command timed out after {timeout}s", -1


async def run_subprocess_async(
    command: str,
    cwd: Optional[str] = None,
    timeout: int = 60,
    merge_stderr: bool = False,
) -> Tuple[bool, str, str, int]:
    """
    Run a command asynchronously with shared env setup.
    Returns (success, stdout, stderr, exit_code).
    """
    env = get_command_env()
    full_command = prepare_command(command, cwd)

    stderr_target = (
        asyncio.subprocess.STDOUT if merge_stderr else asyncio.subprocess.PIPE
    )
    process = await asyncio.create_subprocess_shell(
        full_command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=stderr_target,
        executable="/bin/bash",
        env=env,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return False, "", f"Command timed out after {timeout}s", -1

    stdout = (stdout_bytes or b"").decode("utf-8", errors="replace")
    stderr = (stderr_bytes or b"").decode("utf-8", errors="replace")
    return process.returncode == 0, stdout, stderr, process.returncode


def format_command_message(
    command: str, success: bool, stdout: str, stderr: str
) -> str:
    status_icon = "✅" if success else "❌"
    preview = ""
    if stderr:
        preview = stderr.splitlines()[0][:160]
    elif stdout:
        preview = stdout.splitlines()[0][:160]
    return f"{status_icon} Command: `{command}`" + (f" — {preview}" if preview else "")
