"""
Run Command Tool

Executes safe terminal commands.
This is a write operation with strict sandboxing (requires user approval).
"""

import subprocess
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


# Whitelist of safe commands
SAFE_COMMANDS = {
    # Package managers
    "npm",
    "yarn",
    "pnpm",
    "pip",
    "pip3",
    "poetry",
    "pipenv",
    "cargo",
    "go",
    "mvn",
    "gradle",
    "composer",
    "bundle",
    # Testing
    "pytest",
    "jest",
    "mocha",
    "vitest",
    "go test",
    "cargo test",
    # Build tools
    "make",
    "cmake",
    "tsc",
    "webpack",
    "vite",
    "esbuild",
    # Linters/formatters
    "eslint",
    "prettier",
    "black",
    "flake8",
    "mypy",
    "pylint",
    "rustfmt",
    "gofmt",
    # Git (read-only)
    "git status",
    "git log",
    "git diff",
    "git branch",
    "git show",
    # Info commands
    "echo",  # Safe output command
    "ls",    # Directory listing
    "pwd",   # Print working directory
    "node",
    "python",
    "python3",
    "java",
    "go version",
    "cargo --version",
}


# Commands that are NEVER allowed
BLOCKED_COMMANDS = {
    "rm",
    "rmdir",
    "del",
    "format",
    "mkfs",
    "dd",
    "shutdown",
    "reboot",
    "init",
    "kill",
    "killall",
    "pkill",
    "chmod",
    "chown",
    "sudo",
    "su",
}


async def run_command(
    user_id: str, command: str, cwd: Optional[str] = None, timeout: int = 30
) -> Dict[str, Any]:
    """
    Execute safe terminal command.

    Args:
        user_id: User ID executing the tool
        command: Command to execute
        cwd: Working directory (optional)
        timeout: Command timeout in seconds (default 30)

    Returns:
        {
            "success": bool,
            "message": str,
            "stdout": str,
            "stderr": str,
            "exit_code": int,
            "error": str (if failure)
        }
    """
    logger.info(f"[TOOL:run_command] user={user_id}, command={command}")

    try:
        # Parse command
        cmd_parts = command.split()
        if not cmd_parts:
            return {
                "success": False,
                "message": "❌ Empty command",
                "error": "No command provided",
            }

        cmd_name = cmd_parts[0]

        # Check if command is blocked
        if cmd_name in BLOCKED_COMMANDS or command in BLOCKED_COMMANDS:
            return {
                "success": False,
                "message": f"❌ Command blocked for safety: `{cmd_name}`",
                "error": "Command not allowed",
            }

        # Check if command is in whitelist
        is_safe = False
        for safe_cmd in SAFE_COMMANDS:
            if command.startswith(safe_cmd) or cmd_name in safe_cmd:
                is_safe = True
                break

        if not is_safe:
            return {
                "success": False,
                "message": f"❌ Command not in whitelist: `{cmd_name}`\nSafe commands: {', '.join(sorted(SAFE_COMMANDS)[:10])}...",
                "error": "Command not whitelisted",
            }

        # Execute command
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # Format output
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        exit_code = result.returncode

        success = exit_code == 0
        status_icon = "✅" if success else "❌"

        message_parts = [f"{status_icon} Command: `{command}`"]
        if stdout:
            message_parts.append(f"\n**Output:**\n```\n{stdout[:2000]}\n```")
        if stderr:
            message_parts.append(f"\n**Errors:**\n```\n{stderr[:2000]}\n```")
        if exit_code != 0:
            message_parts.append(f"\n**Exit code:** {exit_code}")

        return {
            "success": success,
            "message": "".join(message_parts),
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": f"❌ Command timed out after {timeout}s: `{command}`",
            "error": "Command timeout",
        }

    except Exception as e:
        logger.error(f"[TOOL:run_command] Error: {e}")
        return {
            "success": False,
            "message": f"❌ Error executing command: {str(e)}",
            "error": str(e),
        }
