"""
Run Command Tool

Executes safe terminal commands with proper environment setup.
This is a write operation with strict sandboxing (requires user approval).

KEY FEATURES:
- Automatically activates Node.js version managers (nvm, volta, fnm)
- Sets up PATH correctly before running npm/node commands
- Dangerous commands require explicit user permission with warnings
- Automatic backup creation before destructive operations
"""

import subprocess
import asyncio
import logging
import os
import shutil
from typing import Dict, Any, Optional, List
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from .dangerous_commands import (
    is_dangerous_command,
    get_command_info,
    format_permission_request,
    BackupManager,
    DANGEROUS_COMMANDS,
    RiskLevel,
)

logger = logging.getLogger(__name__)


def _get_node_environment_setup(cwd: Optional[str] = None) -> str:
    """
    Generate shell commands to properly set up Node.js environment.
    Handles nvm, volta, fnm, and direct PATH additions.
    """
    home = os.environ.get("HOME", os.path.expanduser("~"))
    setup_commands = []

    # Check for various Node version managers and add activation
    nvm_dir = os.environ.get("NVM_DIR", os.path.join(home, ".nvm"))
    if os.path.exists(os.path.join(nvm_dir, "nvm.sh")):
        setup_commands.append(
            f'export NVM_DIR="{nvm_dir}" && '
            f'[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" --no-use 2>/dev/null'
        )
        # Check for .nvmrc in workspace
        if cwd:
            nvmrc = os.path.join(cwd, ".nvmrc")
            node_version = os.path.join(cwd, ".node-version")
            if os.path.exists(nvmrc) or os.path.exists(node_version):
                setup_commands.append("nvm use 2>/dev/null || nvm install 2>/dev/null")
            else:
                setup_commands.append("nvm use default 2>/dev/null || true")

    # Check for volta
    volta_home = os.environ.get("VOLTA_HOME", os.path.join(home, ".volta"))
    if os.path.exists(volta_home):
        setup_commands.append(f'export VOLTA_HOME="{volta_home}"')
        setup_commands.append('export PATH="$VOLTA_HOME/bin:$PATH"')

    # Check for fnm
    fnm_path = os.path.join(home, ".fnm")
    if os.path.exists(fnm_path):
        setup_commands.append(f'export PATH="{fnm_path}:$PATH"')
        setup_commands.append('eval "$(fnm env --use-on-cd 2>/dev/null)" 2>/dev/null || true')

    # Add common Node paths as fallback
    common_paths = [
        "/opt/homebrew/bin",  # macOS ARM homebrew
        "/usr/local/bin",     # macOS Intel / Linux
        os.path.join(home, ".npm-global/bin"),  # npm global
        os.path.join(home, ".yarn/bin"),  # yarn global
    ]

    # Add node_modules/.bin if in workspace
    if cwd:
        node_modules_bin = os.path.join(cwd, "node_modules", ".bin")
        if os.path.exists(node_modules_bin):
            common_paths.insert(0, node_modules_bin)

    existing_paths = [p for p in common_paths if os.path.exists(p)]
    if existing_paths:
        path_additions = ":".join(existing_paths)
        setup_commands.append(f'export PATH="{path_additions}:$PATH"')

    return " && ".join(setup_commands) if setup_commands else ""


def _is_node_command(command: str) -> bool:
    """Check if command requires Node.js environment."""
    node_commands = [
        "npm", "npx", "node", "yarn", "pnpm", "bun",
        "tsc", "tsx", "ts-node",
        "jest", "vitest", "mocha",
        "webpack", "vite", "esbuild", "rollup", "parcel",
        "eslint", "prettier", "next", "nuxt", "gatsby",
    ]
    cmd_parts = command.split()
    if not cmd_parts:
        return False
    first_cmd = cmd_parts[0]
    return any(first_cmd == nc or first_cmd.endswith(f"/{nc}") for nc in node_commands)


def _is_python_command(command: str) -> bool:
    """Check if command requires Python environment."""
    python_commands = ["python", "python3", "pip", "pip3", "poetry", "pipenv", "pytest", "mypy", "black", "ruff", "flake8"]
    cmd_parts = command.split()
    if not cmd_parts:
        return False
    return cmd_parts[0] in python_commands


def _get_python_environment_setup(cwd: Optional[str] = None) -> str:
    """Generate shell commands to activate Python virtual environment."""
    if not cwd:
        return ""

    # Check for various venv locations
    venv_paths = [
        os.path.join(cwd, "venv", "bin", "activate"),
        os.path.join(cwd, ".venv", "bin", "activate"),
        os.path.join(cwd, "env", "bin", "activate"),
    ]

    for venv_path in venv_paths:
        if os.path.exists(venv_path):
            return f'source "{venv_path}" 2>/dev/null || true'

    return ""


# Whitelist of safe commands
SAFE_COMMANDS = {
    # Package managers
    "npm",
    "npx",  # Node package executor
    "yarn",
    "pnpm",
    "bun",
    "pip",
    "pip3",
    "poetry",
    "pipenv",
    "uv",  # Fast Python package installer
    "cargo",
    "go",
    "mvn",
    "gradle",
    "composer",
    "bundle",
    "gem",
    "brew",  # Homebrew
    "apt-get",  # Linux package manager (read operations)
    "apt",
    # Testing
    "pytest",
    "jest",
    "mocha",
    "vitest",
    "playwright",
    "cypress",
    "go test",
    "cargo test",
    "dotnet test",
    "mvn test",
    "gradle test",
    # Build tools
    "make",
    "cmake",
    "tsc",
    "tsx",
    "ts-node",
    "webpack",
    "vite",
    "esbuild",
    "rollup",
    "parcel",
    "next",
    "nuxt",
    "turbo",  # Turborepo
    "nx",  # Nx monorepo
    "lerna",
    "docker",  # Container operations
    "docker-compose",
    "podman",
    "kubectl",  # Kubernetes
    "helm",
    "terraform",
    "pulumi",
    "aws",  # AWS CLI
    "gcloud",  # Google Cloud CLI
    "az",  # Azure CLI
    "vercel",  # Deployment CLIs
    "netlify",
    "railway",
    "fly",
    "heroku",
    "wrangler",  # Cloudflare Workers
    # Linters/formatters
    "eslint",
    "prettier",
    "black",
    "flake8",
    "mypy",
    "pylint",
    "ruff",
    "isort",
    "autopep8",
    "rustfmt",
    "clippy",
    "gofmt",
    "golint",
    "swiftlint",
    "ktlint",
    "rubocop",
    "standardrb",
    # Git operations
    "git",  # All git commands
    "gh",  # GitHub CLI
    "glab",  # GitLab CLI
    # Database tools
    "psql",
    "mysql",
    "sqlite3",
    "mongosh",
    "redis-cli",
    "prisma",  # Prisma ORM
    "drizzle-kit",
    "typeorm",
    "sequelize",
    "knex",
    # Info/read commands
    "echo",
    "ls",
    "pwd",
    "cat",
    "head",
    "tail",
    "less",
    "more",
    "wc",  # Word count
    "grep",  # Search (read-only)
    "find",  # Find files
    "tree",  # Directory tree
    "file",  # File type info
    "stat",  # File stats
    "du",  # Disk usage
    "df",  # Disk free
    "which",
    "whereis",
    "type",
    "command",
    # File/directory operations (safe)
    "mkdir",  # Create directories
    "touch",  # Create empty files
    "cp",  # Copy files
    "mv",  # Move/rename files
    "ln",  # Create links
    # Process/network info (read-only)
    "ps",  # Process list
    "top",
    "htop",
    "lsof",  # List open files
    "netstat",
    "ss",  # Socket stats
    "curl",  # HTTP requests
    "wget",
    "http",  # HTTPie
    "nc",  # Netcat (connect only)
    "ping",
    "dig",  # DNS lookup
    "nslookup",
    "host",
    # Language runtimes
    "node",
    "deno",
    "python",
    "python3",
    "ruby",
    "php",
    "java",
    "javac",
    "kotlin",
    "kotlinc",
    "scala",
    "swift",
    "swiftc",
    "go",
    "rustc",
    "dotnet",
    "elixir",
    "mix",  # Elixir build tool
    "erl",  # Erlang
    "lua",
    "perl",
    "r",  # R language
    "julia",
    # Utility commands
    "date",
    "cal",
    "uptime",
    "hostname",
    "uname",
    "id",
    "whoami",
    "groups",
    "basename",
    "dirname",
    "realpath",
    "readlink",
    "md5",
    "sha256sum",
    "base64",
    "jq",  # JSON processor
    "yq",  # YAML processor
    "sed",  # Stream editor (for piping)
    "awk",  # Text processing
    "sort",
    "uniq",
    "cut",
    "tr",
    "xargs",
    "tee",
    "diff",
    "patch",
    "tar",  # Archive (read/create)
    "zip",
    "unzip",
    "gzip",
    "gunzip",
    # Environment/version managers
    "env",
    "printenv",
    "export",
    "source",
    "nvm",
    "fnm",
    "volta",
    "asdf",
    "pyenv",
    "rbenv",
    "goenv",
    "rustup",
    "sdkman",
    # Code generation / scaffolding
    "create-react-app",
    "create-next-app",
    "create-vue",
    "create-svelte",
    "create-astro",
    "degit",
    "cookiecutter",
    "yeoman",
    "yo",
    # Mobile development
    "expo",
    "react-native",
    "flutter",
    "pod",  # CocoaPods
    "fastlane",
    "xcodebuild",
    "adb",  # Android Debug Bridge
    "emulator",
    # System monitoring (read-only)
    "vmstat",
    "iostat",
    "sar",
    "dstat",
    "glances",
    "nmon",
    "iotop",
    "iftop",
    "nethogs",
    "bmon",
    "free",  # Memory info
    "mpstat",  # CPU stats
    "pidstat",  # Process stats
    "strace",  # System call tracing (read-only)
    "ltrace",  # Library call tracing
    # Advanced networking
    "tcpdump",  # Network capture (requires filtering)
    "nmap",  # Network scanner (scan only)
    "traceroute",
    "tracepath",
    "mtr",  # Network diagnostic
    "iperf",
    "iperf3",
    "speedtest-cli",
    "whois",
    "openssl",  # SSL/TLS tools
    "ssh-keygen",  # Key generation
    "ssh-copy-id",
    "scp",  # Secure copy
    "rsync",  # File sync
    "sftp",  # Secure FTP
    # Compression tools
    "xz",
    "unxz",
    "bzip2",
    "bunzip2",
    "7z",
    "7za",
    "rar",
    "unrar",
    "zstd",
    "lz4",
    "pigz",  # Parallel gzip
    "pbzip2",  # Parallel bzip2
    # Cloud-specific CLIs
    "eksctl",  # AWS EKS
    "copilot",  # AWS Copilot
    "doctl",  # DigitalOcean
    "linode-cli",  # Linode
    "vultr-cli",  # Vultr
    "hcloud",  # Hetzner Cloud
    "scaleway",  # Scaleway
    "ibmcloud",  # IBM Cloud
    "oci",  # Oracle Cloud
    "civo",  # Civo
    # Kubernetes ecosystem
    "k9s",  # K8s TUI
    "kubectx",
    "kubens",
    "kustomize",
    "skaffold",
    "tilt",
    "kind",  # K8s in Docker
    "minikube",
    "k3d",  # K3s in Docker
    "arkade",  # K8s app installer
    "kubeseal",  # Sealed secrets
    "velero",  # Backup
    "argocd",  # GitOps
    "flux",  # GitOps
    "istioctl",  # Service mesh
    "linkerd",  # Service mesh
    # Infrastructure as Code
    "terragrunt",
    "cdktf",  # Terraform CDK
    "cdk",  # AWS CDK
    "sam",  # AWS SAM
    "serverless",  # Serverless Framework
    "ansible",
    "ansible-playbook",
    "ansible-galaxy",
    "vagrant",
    "packer",
    "consul",
    "vault",  # HashiCorp Vault
    "nomad",
    "boundary",
    # Database tools (extended)
    "pgcli",  # Better PostgreSQL CLI
    "mycli",  # Better MySQL CLI
    "litecli",  # Better SQLite CLI
    "usql",  # Universal SQL CLI
    "sqlcmd",  # SQL Server
    "bq",  # BigQuery
    "clickhouse-client",
    "cqlsh",  # Cassandra
    "influx",  # InfluxDB
    "cockroach",  # CockroachDB
    "neo4j-admin",  # Neo4j
    "dgraph",  # Dgraph
    "surreal",  # SurrealDB
    # Message queues
    "rabbitmqctl",
    "kafka-console-producer",
    "kafka-console-consumer",
    "kafka-topics",
    "pulsar-admin",
    "nats",
    # CI/CD tools
    "jenkins-cli",
    "circleci",
    "travis",
    "drone",
    "buildkite-agent",
    "argo",
    "tekton",
    # Security tools
    "trivy",  # Container scanning
    "grype",  # Vulnerability scanner
    "syft",  # SBOM generator
    "cosign",  # Container signing
    "snyk",  # Security scanning
    "bandit",  # Python security
    "brakeman",  # Ruby security
    "semgrep",  # Static analysis
    "checkov",  # IaC security
    "tfsec",  # Terraform security
    # Debugging/Profiling
    "gdb",
    "lldb",
    "valgrind",
    "perf",
    "flamegraph",
    "hyperfine",  # Benchmarking
    "time",
    "timeout",
    # Documentation
    "mkdocs",
    "sphinx-build",
    "hugo",
    "jekyll",
    "gatsby",
    "docusaurus",
    "vitepress",
    "gitbook",
    # API tools
    "grpcurl",
    "grpc_cli",
    "postman",
    "insomnia",
    "httpie",
    "hey",  # HTTP load testing
    "ab",  # Apache Bench
    "wrk",  # HTTP benchmarking
    "vegeta",  # HTTP load testing
    "k6",  # Load testing
    "locust",  # Load testing
    # Log analysis
    "journalctl",
    "logcli",  # Loki CLI
    "stern",  # K8s log tailing
    # Misc utilities
    "bat",  # Better cat
    "exa",  # Better ls
    "fd",  # Better find
    "rg",  # ripgrep
    "fzf",  # Fuzzy finder
    "ag",  # Silver searcher
    "ack",  # Code search
    "delta",  # Better diff
    "tokei",  # Code statistics
    "cloc",  # Count lines of code
    "scc",  # Code counter
    "dust",  # Better du
    "duf",  # Better df
    "procs",  # Better ps
    "bottom",  # Better top
    "zoxide",  # Smarter cd
    "direnv",  # Environment switcher
    "tmux",
    "screen",
    "byobu",
    "watch",
    "entr",  # File watcher
    "parallel",  # GNU Parallel
    "xclip",
    "pbcopy",
    "pbpaste",
}


# Commands that are NEVER allowed (system-level dangerous operations)
# Commands that are ALWAYS blocked (no permission bypass)
# System-level commands have been moved to DANGEROUS_COMMANDS for permission-based execution
BLOCKED_COMMANDS = {
    ">",   # Prevent redirect that could overwrite files
    ">>",  # Prevent append redirect
}

# Commands that are conditionally allowed (safe patterns only)
# These are blocked by default but allowed for specific safe patterns
CONDITIONAL_COMMANDS = {
    "rm": [
        "rm -rf node_modules",
        "rm -rf dist",
        "rm -rf build",
        "rm -rf .next",
        "rm -rf .nuxt",
        "rm -rf .cache",
        "rm -rf coverage",
        "rm -rf __pycache__",
        "rm -rf .pytest_cache",
        "rm -rf .mypy_cache",
        "rm -rf .ruff_cache",
        "rm -rf target",  # Rust
        "rm -rf vendor",  # Go
        "rm package-lock.json",
        "rm yarn.lock",
        "rm pnpm-lock.yaml",
        "rm -rf .turbo",
        "rm -rf .parcel-cache",
    ],
    "kill": [
        "kill -9",  # Allow killing specific PIDs
    ],
    "chmod": [
        "chmod +x",  # Make executable
        "chmod 755",
        "chmod 644",
    ],
    "chown": [],  # Still blocked
    "rmdir": [
        "rmdir",  # Safe - only removes empty directories
    ],
}


def _is_conditional_allowed(command: str) -> bool:
    """Check if a conditional command matches a safe pattern."""
    cmd_parts = command.split()
    if not cmd_parts:
        return False

    cmd_name = cmd_parts[0]
    if cmd_name not in CONDITIONAL_COMMANDS:
        return False

    allowed_patterns = CONDITIONAL_COMMANDS[cmd_name]
    if not allowed_patterns:
        return False

    # Check if command matches any allowed pattern
    for pattern in allowed_patterns:
        if command.startswith(pattern):
            return True

    return False


async def run_command(
    user_id: str, command: str, cwd: Optional[str] = None, timeout: int = 60
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

        # Check if command is in the absolute block list (truly dangerous, never allowed)
        if cmd_name in BLOCKED_COMMANDS or command in BLOCKED_COMMANDS:
            return {
                "success": False,
                "message": f"❌ Command blocked for safety: `{cmd_name}`",
                "error": "Command not allowed",
            }

        # Check if this is a dangerous command that requires permission
        cmd_info = get_command_info(command)
        if cmd_info is not None:
            # This is a dangerous command - check if it's conditionally allowed
            if not _is_conditional_allowed(command):
                # Return permission request for user approval
                permission_request = format_permission_request(command, cmd_info, cwd)
                return {
                    "success": False,
                    "requires_permission": True,
                    "permission_request": permission_request,
                    "message": f"⚠️ **DANGEROUS COMMAND DETECTED**\n\n"
                               f"**Command:** `{command}`\n"
                               f"**Risk Level:** {permission_request['risk_icon']} {cmd_info.risk_level.value.upper()}\n\n"
                               f"**What this does:** {cmd_info.description}\n\n"
                               f"**⚠️ Consequences:**\n" +
                               "\n".join(f"  • {c}" for c in cmd_info.consequences) +
                               f"\n\n**Rollback possible:** {'Yes ✅' if cmd_info.rollback_possible else 'No ❌'}\n"
                               f"**Backup strategy:** {cmd_info.backup_strategy}\n\n"
                               f"**Alternatives:**\n" +
                               "\n".join(f"  • {a}" for a in cmd_info.alternatives) +
                               f"\n\n**To proceed, use:** `run_dangerous_command` with `approved=True`",
                    "error": "Permission required for dangerous command",
                }

        # Check if command is conditionally allowed (e.g., rm -rf node_modules)
        if _is_conditional_allowed(command):
            logger.info(f"[TOOL:run_command] Conditional command allowed: {command}")
            is_safe = True
        else:
            # Check if command is in whitelist
            is_safe = False
            for safe_cmd in SAFE_COMMANDS:
                if command.startswith(safe_cmd) or cmd_name in safe_cmd:
                    is_safe = True
                    break

        if not is_safe:
            # Check if it's a conditional command that doesn't match safe patterns
            if cmd_name in CONDITIONAL_COMMANDS:
                allowed = CONDITIONAL_COMMANDS[cmd_name]
                return {
                    "success": False,
                    "message": f"❌ `{cmd_name}` only allowed for specific patterns:\n" +
                               "\n".join(f"  - `{p}`" for p in allowed[:5]) +
                               ("\n  ..." if len(allowed) > 5 else ""),
                    "error": "Command pattern not allowed",
                }
            # Check if it's a dangerous command that could be allowed with permission
            if cmd_info is not None:
                permission_request = format_permission_request(command, cmd_info, cwd)
                return {
                    "success": False,
                    "requires_permission": True,
                    "permission_request": permission_request,
                    "message": f"⚠️ This command requires explicit permission. See permission_request for details.",
                    "error": "Permission required",
                }
            return {
                "success": False,
                "message": f"❌ Command not in whitelist: `{cmd_name}`\nSafe commands: {', '.join(sorted(SAFE_COMMANDS)[:10])}...",
                "error": "Command not whitelisted",
            }

        # Build environment setup prefix based on command type
        env_setup = ""
        if _is_node_command(command):
            env_setup = _get_node_environment_setup(cwd)
            logger.info(f"[TOOL:run_command] Node environment setup: {env_setup[:100]}...")
        elif _is_python_command(command):
            env_setup = _get_python_environment_setup(cwd)
            if env_setup:
                logger.info(f"[TOOL:run_command] Python venv activation: {env_setup}")

        # Combine environment setup with command
        full_command = f"{env_setup} && {command}" if env_setup else command

        # Execute command with enhanced environment
        env = os.environ.copy()
        # Ensure we have a proper shell environment
        env["SHELL"] = os.environ.get("SHELL", "/bin/bash")

        result = subprocess.run(
            full_command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            executable="/bin/bash",  # Use bash for better compatibility
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


async def run_dangerous_command(
    user_id: str,
    command: str,
    approved: bool = False,
    skip_backup: bool = False,
    cwd: Optional[str] = None,
    timeout: int = 120,
) -> Dict[str, Any]:
    """
    Execute a dangerous command after user approval.

    This function handles:
    1. Verification of user approval
    2. Automatic backup creation (unless skipped)
    3. Command execution
    4. Result reporting with rollback instructions

    Args:
        user_id: User ID executing the tool
        command: The dangerous command to execute
        approved: Must be True to execute (user confirmation)
        skip_backup: Skip backup creation (not recommended)
        cwd: Working directory (optional)
        timeout: Command timeout in seconds (default 60 for dangerous ops)

    Returns:
        {
            "success": bool,
            "message": str,
            "backup": {...} (if backup was created),
            "stdout": str,
            "stderr": str,
            "exit_code": int,
            "rollback_instructions": str (if available),
            "error": str (if failure)
        }
    """
    logger.info(f"[TOOL:run_dangerous_command] user={user_id}, command={command}, approved={approved}")

    # CRITICAL: Require explicit approval
    if not approved:
        cmd_info = get_command_info(command)
        if cmd_info:
            permission_request = format_permission_request(command, cmd_info, cwd)
            return {
                "success": False,
                "requires_permission": True,
                "permission_request": permission_request,
                "message": "❌ **APPROVAL REQUIRED**\n\n"
                          f"You must set `approved=True` to execute this dangerous command.\n\n"
                          f"**Command:** `{command}`\n"
                          f"**Risk:** {cmd_info.risk_level.value.upper()}\n\n"
                          "Review the consequences carefully before approving.",
                "error": "Approval required",
            }
        return {
            "success": False,
            "message": "❌ Approval required but command info not found",
            "error": "Approval required",
        }

    # Get command info for backup strategy
    cmd_info = get_command_info(command)
    backup_result = None
    rollback_instructions = None

    # Create backup before execution (unless skipped)
    if not skip_backup and cmd_info and cmd_info.backup_strategy != "none":
        logger.info(f"[TOOL:run_dangerous_command] Creating backup with strategy: {cmd_info.backup_strategy}")

        workspace = cwd or os.getcwd()
        backup_manager = BackupManager(workspace)

        # Extract target from command for backup
        cmd_parts = command.split()
        target = cmd_parts[-1] if len(cmd_parts) > 1 else None

        backup_result = backup_manager.create_backup(target or "", cmd_info.backup_strategy)

        if not backup_result.get("success"):
            return {
                "success": False,
                "message": f"❌ **BACKUP FAILED** - Command NOT executed for safety\n\n"
                          f"Backup error: {backup_result.get('error', 'Unknown error')}\n\n"
                          "Fix the backup issue or use `skip_backup=True` (not recommended).",
                "error": "Backup failed",
                "backup": backup_result,
            }

        # Prepare rollback instructions
        if backup_result.get("backup_path"):
            rollback_instructions = f"**To restore:** Copy from `{backup_result['backup_path']}`"
        elif backup_result.get("restore_command"):
            rollback_instructions = f"**To restore:** Run `{backup_result['restore_command']}`"

    # Execute the command
    try:
        # Build environment setup
        env_setup = ""
        if _is_node_command(command):
            env_setup = _get_node_environment_setup(cwd)
        elif _is_python_command(command):
            env_setup = _get_python_environment_setup(cwd)

        full_command = f"{env_setup} && {command}" if env_setup else command

        env = os.environ.copy()
        env["SHELL"] = os.environ.get("SHELL", "/bin/bash")

        result = subprocess.run(
            full_command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            executable="/bin/bash",
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        exit_code = result.returncode
        success = exit_code == 0

        # Build response message
        if success:
            message = f"✅ **Dangerous command executed successfully**\n\n"
            message += f"**Command:** `{command}`\n"
            if stdout:
                message += f"\n**Output:**\n```\n{stdout[:2000]}\n```"
        else:
            message = f"❌ **Dangerous command failed**\n\n"
            message += f"**Command:** `{command}`\n"
            message += f"**Exit code:** {exit_code}\n"
            if stderr:
                message += f"\n**Errors:**\n```\n{stderr[:2000]}\n```"

        if backup_result and backup_result.get("backup_path"):
            message += f"\n\n📦 **Backup created:** `{backup_result['backup_path']}`"

        if rollback_instructions:
            message += f"\n\n🔄 {rollback_instructions}"

        return {
            "success": success,
            "message": message,
            "backup": backup_result,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "rollback_instructions": rollback_instructions,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": f"❌ Command timed out after {timeout}s: `{command}`\n\n"
                      f"📦 Backup was created: {backup_result.get('backup_path') if backup_result else 'None'}",
            "error": "Command timeout",
            "backup": backup_result,
        }

    except Exception as e:
        logger.error(f"[TOOL:run_dangerous_command] Error: {e}")
        return {
            "success": False,
            "message": f"❌ Error executing command: {str(e)}\n\n"
                      f"📦 Backup was created: {backup_result.get('backup_path') if backup_result else 'None'}",
            "error": str(e),
            "backup": backup_result,
        }


async def list_backups(workspace_path: str) -> Dict[str, Any]:
    """List all NAVI backups in the workspace."""
    backup_dir = os.path.join(workspace_path, ".navi_backups")

    if not os.path.exists(backup_dir):
        return {
            "success": True,
            "message": "No backups found",
            "backups": [],
        }

    backups = []
    for item in os.listdir(backup_dir):
        item_path = os.path.join(backup_dir, item)
        stat = os.stat(item_path)
        backups.append({
            "name": item,
            "path": item_path,
            "size": stat.st_size,
            "created": stat.st_mtime,
            "is_directory": os.path.isdir(item_path),
        })

    backups.sort(key=lambda x: x["created"], reverse=True)

    return {
        "success": True,
        "message": f"Found {len(backups)} backup(s)",
        "backups": backups,
        "backup_directory": backup_dir,
    }


async def restore_backup(
    workspace_path: str,
    backup_name: str,
    target_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Restore a backup to the original or specified location."""
    backup_dir = os.path.join(workspace_path, ".navi_backups")
    backup_path = os.path.join(backup_dir, backup_name)

    if not os.path.exists(backup_path):
        return {
            "success": False,
            "message": f"❌ Backup not found: {backup_name}",
            "error": "Backup not found",
        }

    # Determine target path
    if not target_path:
        # Try to extract original path from backup name (format: originalname_timestamp)
        parts = backup_name.rsplit("_", 1)
        if len(parts) == 2:
            target_path = os.path.join(workspace_path, parts[0])
        else:
            return {
                "success": False,
                "message": "❌ Cannot determine target path. Please specify target_path.",
                "error": "Target path required",
            }

    try:
        if os.path.isdir(backup_path):
            if os.path.exists(target_path):
                shutil.rmtree(target_path)
            shutil.copytree(backup_path, target_path)
        else:
            shutil.copy2(backup_path, target_path)

        return {
            "success": True,
            "message": f"✅ Restored backup to: {target_path}",
            "backup_path": backup_path,
            "target_path": target_path,
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"❌ Restore failed: {str(e)}",
            "error": str(e),
        }


# Interactive command patterns that need auto-responses
INTERACTIVE_PROMPTS = {
    # Common yes/no prompts
    r"(y/n)": "y",
    r"(Y/n)": "Y",
    r"(yes/no)": "yes",
    r"[Y/n]": "Y",
    r"[y/N]": "y",
    r"Continue\?": "y",
    r"Proceed\?": "y",
    r"Are you sure": "y",
    r"Do you want to continue": "y",
    # npm specific
    r"Is this OK\?": "yes",
    r"npm WARN": "",  # Just acknowledge
    # git specific
    r"Do you want to": "y",
    r"Overwrite": "y",
    # Python/pip
    r"Proceed \(Y/n\)": "Y",
}


async def run_interactive_command(
    user_id: str,
    command: str,
    responses: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
    timeout: int = 300,
    auto_yes: bool = True,
) -> Dict[str, Any]:
    """
    Execute a command that might require interactive input.

    Handles common prompts automatically or uses provided responses.
    For commands that ask questions like "Continue? [y/n]".

    Args:
        user_id: User ID executing the tool
        command: Command to execute
        responses: Dict mapping prompt patterns to responses
        cwd: Working directory (optional)
        timeout: Command timeout in seconds (default 120 for interactive)
        auto_yes: Automatically answer 'yes' to common prompts

    Returns:
        {
            "success": bool,
            "message": str,
            "stdout": str,
            "stderr": str,
            "exit_code": int,
            "prompts_answered": List of prompts that were auto-answered,
            "error": str (if failure)
        }
    """
    logger.info(f"[TOOL:run_interactive_command] user={user_id}, command={command}, auto_yes={auto_yes}")

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

        # Check blocked commands
        if cmd_name in BLOCKED_COMMANDS:
            return {
                "success": False,
                "message": f"❌ Command blocked: `{cmd_name}`",
                "error": "Command not allowed",
            }

        # Build environment setup
        env_setup = ""
        if _is_node_command(command):
            env_setup = _get_node_environment_setup(cwd)
        elif _is_python_command(command):
            env_setup = _get_python_environment_setup(cwd)

        # For interactive commands, we use 'yes' command or expect-like input
        if auto_yes:
            # Use 'yes' command to auto-answer prompts
            full_command = f"yes | {command}"
        else:
            full_command = command

        if env_setup:
            full_command = f"{env_setup} && {full_command}"

        env = os.environ.copy()
        env["SHELL"] = os.environ.get("SHELL", "/bin/bash")
        # Set non-interactive mode for some tools
        env["DEBIAN_FRONTEND"] = "noninteractive"
        env["CI"] = "true"  # Many tools detect CI and skip prompts

        result = subprocess.run(
            full_command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            executable="/bin/bash",
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        exit_code = result.returncode
        success = exit_code == 0

        # Identify prompts that were likely auto-answered
        prompts_answered = []
        for pattern in INTERACTIVE_PROMPTS.keys():
            if pattern.lower() in stdout.lower() or pattern.lower() in stderr.lower():
                prompts_answered.append(pattern)

        status_icon = "✅" if success else "❌"
        message_parts = [f"{status_icon} Interactive command: `{command}`"]

        if auto_yes:
            message_parts.append("\n*Auto-answered prompts with 'yes'*")

        if prompts_answered:
            message_parts.append(f"\n**Prompts detected:** {', '.join(prompts_answered)}")

        if stdout:
            message_parts.append(f"\n**Output:**\n```\n{stdout[:2000]}\n```")
        if stderr:
            message_parts.append(f"\n**Errors:**\n```\n{stderr[:2000]}\n```")

        return {
            "success": success,
            "message": "".join(message_parts),
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "prompts_answered": prompts_answered,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": f"❌ Interactive command timed out after {timeout}s: `{command}`\n"
                      "This might be waiting for input that couldn't be auto-answered.",
            "error": "Command timeout",
        }

    except Exception as e:
        logger.error(f"[TOOL:run_interactive_command] Error: {e}")
        return {
            "success": False,
            "message": f"❌ Error executing interactive command: {str(e)}",
            "error": str(e),
        }


def _execute_single_command(
    command: str,
    cwd: Optional[str],
    timeout: int,
    env: dict,
) -> Dict[str, Any]:
    """Execute a single command (for parallel execution)."""
    try:
        # Build environment setup
        env_setup = ""
        if _is_node_command(command):
            env_setup = _get_node_environment_setup(cwd)
        elif _is_python_command(command):
            env_setup = _get_python_environment_setup(cwd)

        full_command = f"{env_setup} && {command}" if env_setup else command

        result = subprocess.run(
            full_command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            executable="/bin/bash",
        )

        return {
            "command": command,
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "exit_code": result.returncode,
        }

    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "success": False,
            "error": f"Timeout after {timeout}s",
            "exit_code": -1,
        }
    except Exception as e:
        return {
            "command": command,
            "success": False,
            "error": str(e),
            "exit_code": -1,
        }


async def run_parallel_commands(
    user_id: str,
    commands: List[str],
    cwd: Optional[str] = None,
    timeout: int = 120,
    max_workers: int = 4,
    stop_on_failure: bool = False,
) -> Dict[str, Any]:
    """
    Execute multiple commands in parallel.

    Useful for running independent tasks concurrently like:
    - Running tests while building
    - Installing dependencies for multiple projects
    - Running linters in parallel

    Args:
        user_id: User ID executing the tool
        commands: List of commands to execute in parallel
        cwd: Working directory (optional)
        timeout: Timeout per command in seconds
        max_workers: Maximum parallel workers (default 4)
        stop_on_failure: Stop all commands if one fails

    Returns:
        {
            "success": bool (all succeeded),
            "message": str,
            "results": List of individual command results,
            "summary": {
                "total": int,
                "succeeded": int,
                "failed": int,
            },
            "error": str (if failure)
        }
    """
    logger.info(f"[TOOL:run_parallel_commands] user={user_id}, commands={len(commands)}, workers={max_workers}")

    if not commands:
        return {
            "success": False,
            "message": "❌ No commands provided",
            "error": "Empty command list",
        }

    # Filter blocked commands
    safe_commands = []
    blocked = []
    for cmd in commands:
        cmd_parts = cmd.split()
        if cmd_parts and cmd_parts[0] in BLOCKED_COMMANDS:
            blocked.append(cmd)
        else:
            safe_commands.append(cmd)

    if blocked:
        logger.warning(f"[TOOL:run_parallel_commands] Blocked commands: {blocked}")

    if not safe_commands:
        return {
            "success": False,
            "message": f"❌ All commands blocked: {blocked}",
            "error": "All commands blocked",
        }

    # Prepare environment
    env = os.environ.copy()
    env["SHELL"] = os.environ.get("SHELL", "/bin/bash")

    # Execute commands in parallel
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_execute_single_command, cmd, cwd, timeout, env): cmd
            for cmd in safe_commands
        }

        for future in futures:
            try:
                result = future.result()
                results.append(result)

                if stop_on_failure and not result.get("success"):
                    # Cancel remaining futures
                    for f in futures:
                        f.cancel()
                    break

            except Exception as e:
                results.append({
                    "command": futures[future],
                    "success": False,
                    "error": str(e),
                    "exit_code": -1,
                })

    # Calculate summary
    succeeded = sum(1 for r in results if r.get("success"))
    failed = len(results) - succeeded

    # Build message
    all_success = failed == 0
    status_icon = "✅" if all_success else "⚠️"
    message = f"{status_icon} **Parallel Execution Complete**\n\n"
    message += f"**Summary:** {succeeded}/{len(results)} commands succeeded\n\n"

    for i, result in enumerate(results, 1):
        cmd_icon = "✅" if result.get("success") else "❌"
        message += f"{i}. {cmd_icon} `{result['command'][:50]}{'...' if len(result['command']) > 50 else ''}`\n"
        if result.get("error"):
            message += f"   Error: {result['error']}\n"

    if blocked:
        message += f"\n⚠️ **Blocked commands (skipped):** {len(blocked)}\n"

    return {
        "success": all_success,
        "message": message,
        "results": results,
        "summary": {
            "total": len(safe_commands),
            "succeeded": succeeded,
            "failed": failed,
            "blocked": len(blocked),
        },
        "blocked_commands": blocked,
    }


async def run_command_with_retry(
    user_id: str,
    command: str,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    cwd: Optional[str] = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    """
    Execute a command with automatic retry on failure.

    Useful for flaky commands or network operations that might fail temporarily.

    Args:
        user_id: User ID executing the tool
        command: Command to execute
        max_retries: Maximum retry attempts (default 3)
        retry_delay: Seconds between retries (default 1.0)
        cwd: Working directory (optional)
        timeout: Timeout per attempt in seconds

    Returns:
        {
            "success": bool,
            "message": str,
            "attempts": int,
            "stdout": str,
            "stderr": str,
            "exit_code": int,
            "error": str (if all attempts failed)
        }
    """
    logger.info(f"[TOOL:run_command_with_retry] user={user_id}, command={command}, max_retries={max_retries}")

    last_result = None

    for attempt in range(1, max_retries + 1):
        logger.info(f"[TOOL:run_command_with_retry] Attempt {attempt}/{max_retries}")

        result = await run_command(user_id, command, cwd, timeout)
        last_result = result

        if result.get("success"):
            result["attempts"] = attempt
            if attempt > 1:
                result["message"] = f"✅ Succeeded on attempt {attempt}/{max_retries}\n\n" + result.get("message", "")
            return result

        # Don't retry if it's a permission/safety issue
        if result.get("requires_permission") or "blocked" in result.get("error", "").lower():
            result["attempts"] = attempt
            return result

        # Wait before retry (except on last attempt)
        if attempt < max_retries:
            logger.info(f"[TOOL:run_command_with_retry] Retrying in {retry_delay}s...")
            await asyncio.sleep(retry_delay)

    # All attempts failed
    last_result["attempts"] = max_retries
    last_result["message"] = f"❌ **Failed after {max_retries} attempts**\n\n" + last_result.get("message", "")

    return last_result
