"""
Dangerous Command Handler

Manages execution of potentially dangerous commands with:
- User permission requests
- Risk assessment and warnings
- Automatic backup creation
- Rollback capabilities

All dangerous commands require explicit user approval before execution.
"""

import os
import shutil
import logging
import subprocess
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk levels for dangerous commands."""

    LOW = "low"  # Recoverable, minimal impact
    MEDIUM = "medium"  # May cause issues, but recoverable with effort
    HIGH = "high"  # Significant risk, hard to recover
    CRITICAL = "critical"  # Potentially irreversible, system-wide impact


@dataclass
class DangerousCommand:
    """Definition of a dangerous command with risk info."""

    command: str
    risk_level: RiskLevel
    description: str
    consequences: List[str]
    backup_strategy: str
    rollback_possible: bool
    alternatives: List[str] = field(default_factory=list)
    requires_confirmation: bool = True


# Dangerous commands that require user permission
DANGEROUS_COMMANDS: Dict[str, DangerousCommand] = {
    # File/Directory Deletion
    "rm": DangerousCommand(
        command="rm",
        risk_level=RiskLevel.HIGH,
        description="Permanently delete files or directories",
        consequences=[
            "Files will be PERMANENTLY deleted (not moved to trash)",
            "Cannot be undone without backup",
            "May break dependencies if wrong files deleted",
            "Recursive deletion (-rf) removes entire directory trees",
        ],
        backup_strategy="backup_directory",
        rollback_possible=True,
        alternatives=["Move to a .trash folder instead", "Rename with .bak extension"],
    ),
    "rmdir": DangerousCommand(
        command="rmdir",
        risk_level=RiskLevel.LOW,
        description="Remove empty directories only",
        consequences=[
            "Only removes empty directories (safer than rm -rf)",
            "Fails if directory contains files",
        ],
        backup_strategy="none",
        rollback_possible=True,
        alternatives=["Use mkdir to recreate if needed"],
    ),
    # Process Control
    "kill": DangerousCommand(
        command="kill",
        risk_level=RiskLevel.MEDIUM,
        description="Terminate a running process",
        consequences=[
            "Process will be forcefully terminated",
            "Unsaved data in that process may be lost",
            "Child processes may become orphaned",
            "kill -9 cannot be caught or ignored by the process",
        ],
        backup_strategy="none",
        rollback_possible=False,
        alternatives=[
            "Try graceful shutdown first (kill without -9)",
            "Use the application's quit command",
        ],
    ),
    "killall": DangerousCommand(
        command="killall",
        risk_level=RiskLevel.HIGH,
        description="Terminate ALL processes with a given name",
        consequences=[
            "ALL processes matching the name will be killed",
            "May affect multiple instances you didn't intend",
            "Could kill system processes if name matches",
        ],
        backup_strategy="none",
        rollback_possible=False,
        alternatives=[
            "Use 'kill' with specific PID instead",
            "Use 'pkill -f' for more specific matching",
        ],
    ),
    "pkill": DangerousCommand(
        command="pkill",
        risk_level=RiskLevel.MEDIUM,
        description="Terminate processes by pattern matching",
        consequences=[
            "Kills processes matching the pattern",
            "Pattern matching may be broader than expected",
        ],
        backup_strategy="none",
        rollback_possible=False,
        alternatives=[
            "Use 'kill' with specific PID",
            "Use 'ps aux | grep' to verify targets first",
        ],
    ),
    # Permission Changes
    "chmod": DangerousCommand(
        command="chmod",
        risk_level=RiskLevel.MEDIUM,
        description="Change file/directory permissions",
        consequences=[
            "May make files executable (security risk)",
            "May remove read/write access accidentally",
            "Recursive changes affect all subdirectories",
            "Wrong permissions can break applications",
        ],
        backup_strategy="record_permissions",
        rollback_possible=True,
        alternatives=["Use specific numeric permissions (755, 644)"],
    ),
    "chown": DangerousCommand(
        command="chown",
        risk_level=RiskLevel.HIGH,
        description="Change file/directory ownership",
        consequences=[
            "May lose access to your own files",
            "Can break application permissions",
            "May require sudo to reverse",
            "Recursive changes affect all subdirectories",
        ],
        backup_strategy="record_ownership",
        rollback_possible=True,
        alternatives=["Use chmod instead if just need access"],
    ),
    # System Commands (still blocked but with info)
    "sudo": DangerousCommand(
        command="sudo",
        risk_level=RiskLevel.CRITICAL,
        description="Execute command as superuser (root)",
        consequences=[
            "Runs with full system privileges",
            "Can modify/delete ANY file on system",
            "Can break the operating system",
            "Cannot undo system-level changes",
        ],
        backup_strategy="none",
        rollback_possible=False,
        requires_confirmation=True,  # Extra confirmation needed
    ),
    # Git Dangerous Operations
    "git reset --hard": DangerousCommand(
        command="git reset --hard",
        risk_level=RiskLevel.HIGH,
        description="Discard all uncommitted changes",
        consequences=[
            "ALL uncommitted changes will be PERMANENTLY lost",
            "Staged files will be unstaged and reverted",
            "Cannot be undone (no reflog for working directory)",
        ],
        backup_strategy="git_stash",
        rollback_possible=False,
        alternatives=[
            "git stash (saves changes)",
            "git checkout -- <file> (single file)",
        ],
    ),
    "git clean -fd": DangerousCommand(
        command="git clean",
        risk_level=RiskLevel.HIGH,
        description="Remove untracked files and directories",
        consequences=[
            "Deletes ALL untracked files permanently",
            "Includes new files you haven't committed",
            "-d removes untracked directories too",
            "Cannot be undone",
        ],
        backup_strategy="backup_untracked",
        rollback_possible=False,
        alternatives=["git clean -n (dry run first)", "Manually delete specific files"],
    ),
    "git push --force": DangerousCommand(
        command="git push --force",
        risk_level=RiskLevel.CRITICAL,
        description="Force push, overwriting remote history",
        consequences=[
            "Overwrites remote branch history",
            "Other developers' work may be lost",
            "Can break CI/CD pipelines",
            "Team members may have conflicts",
        ],
        backup_strategy="git_backup_branch",
        rollback_possible=True,
        alternatives=[
            "git push --force-with-lease (safer)",
            "Coordinate with team first",
        ],
    ),
    # Database Operations
    "DROP": DangerousCommand(
        command="DROP",
        risk_level=RiskLevel.CRITICAL,
        description="Delete database tables or databases",
        consequences=[
            "Data will be PERMANENTLY deleted",
            "Cannot be undone without backup",
            "May break applications depending on this data",
        ],
        backup_strategy="database_backup",
        rollback_possible=True,
        alternatives=["Export data first", "Rename table instead of dropping"],
    ),
    "TRUNCATE": DangerousCommand(
        command="TRUNCATE",
        risk_level=RiskLevel.HIGH,
        description="Delete all rows from a table",
        consequences=[
            "All data in table will be deleted",
            "Faster than DELETE but cannot be rolled back",
            "Resets auto-increment counters",
        ],
        backup_strategy="database_backup",
        rollback_possible=False,
        alternatives=["DELETE with WHERE clause", "Export data first"],
    ),
    # Docker Operations
    "docker system prune": DangerousCommand(
        command="docker system prune",
        risk_level=RiskLevel.MEDIUM,
        description="Remove unused Docker data",
        consequences=[
            "Removes stopped containers",
            "Removes unused networks",
            "Removes dangling images",
            "-a flag removes ALL unused images",
        ],
        backup_strategy="docker_list",
        rollback_possible=False,
        alternatives=[
            "docker container prune (containers only)",
            "docker image prune (images only)",
        ],
    ),
    "docker volume rm": DangerousCommand(
        command="docker volume rm",
        risk_level=RiskLevel.HIGH,
        description="Remove Docker volumes (persistent data)",
        consequences=[
            "Volume data will be PERMANENTLY deleted",
            "Database data stored in volumes will be lost",
            "Cannot be undone",
        ],
        backup_strategy="docker_volume_backup",
        rollback_possible=False,
        alternatives=["Backup volume first: docker cp", "Export data from container"],
    ),
    # ============================================
    # SYSTEM-LEVEL COMMANDS (Require explicit user permission)
    # ============================================
    # Disk Operations - CRITICAL risk
    "format": DangerousCommand(
        command="format",
        risk_level=RiskLevel.CRITICAL,
        description="Format a disk or partition (data destruction)",
        consequences=[
            "ALL DATA on the disk/partition will be PERMANENTLY ERASED",
            "File system will be completely wiped",
            "Cannot be undone - data recovery extremely difficult",
            "May destroy bootable system if wrong disk selected",
        ],
        backup_strategy="none",
        rollback_possible=False,
        requires_confirmation=True,
        alternatives=[
            "Backup data first",
            "Double-check disk identifier with 'lsblk' or 'diskutil list'",
        ],
    ),
    "mkfs": DangerousCommand(
        command="mkfs",
        risk_level=RiskLevel.CRITICAL,
        description="Create filesystem on disk (destroys existing data)",
        consequences=[
            "ALL DATA on the partition will be PERMANENTLY ERASED",
            "Creates new empty filesystem",
            "Cannot be undone - data recovery extremely difficult",
            "mkfs.ext4, mkfs.xfs, mkfs.ntfs all destroy data",
        ],
        backup_strategy="none",
        rollback_possible=False,
        requires_confirmation=True,
        alternatives=[
            "Backup partition first",
            "Verify partition with 'lsblk' before running",
        ],
    ),
    "dd": DangerousCommand(
        command="dd",
        risk_level=RiskLevel.CRITICAL,
        description="Low-level data copy (can overwrite disks/partitions)",
        consequences=[
            "Can completely overwrite disks with raw data",
            "No safety checks - 'dd' means 'disk destroyer' colloquially",
            "Wrong 'of=' parameter can erase boot disk",
            "Cannot be undone",
            "Even partial execution can corrupt data",
        ],
        backup_strategy="none",
        rollback_possible=False,
        requires_confirmation=True,
        alternatives=[
            "Use 'cp' for regular file copies",
            "Use 'rsync' for backups",
            "Triple-check of= parameter",
        ],
    ),
    # System Control - CRITICAL risk
    "shutdown": DangerousCommand(
        command="shutdown",
        risk_level=RiskLevel.CRITICAL,
        description="Shutdown or halt the system",
        consequences=[
            "System will power off or halt",
            "All running processes will be terminated",
            "Unsaved work will be lost",
            "Remote access will be lost until physical restart",
            "May disrupt services for other users",
        ],
        backup_strategy="none",
        rollback_possible=False,
        requires_confirmation=True,
        alternatives=[
            "Save all work first",
            "Notify users before shutdown",
            "Use 'shutdown -c' to cancel scheduled shutdown",
        ],
    ),
    "reboot": DangerousCommand(
        command="reboot",
        risk_level=RiskLevel.CRITICAL,
        description="Restart the system",
        consequences=[
            "System will restart immediately",
            "All running processes will be terminated",
            "Unsaved work will be lost",
            "Services may have downtime during restart",
            "May disrupt other users' sessions",
        ],
        backup_strategy="none",
        rollback_possible=False,
        requires_confirmation=True,
        alternatives=[
            "Save all work first",
            "Notify users before reboot",
            "Schedule reboot during maintenance window",
        ],
    ),
    "init": DangerousCommand(
        command="init",
        risk_level=RiskLevel.CRITICAL,
        description="Change system runlevel (can halt/reboot system)",
        consequences=[
            "init 0 = shutdown/halt",
            "init 6 = reboot",
            "init 1 = single user mode (limited access)",
            "Can disrupt all running services",
            "May lock out remote users",
        ],
        backup_strategy="none",
        rollback_possible=False,
        requires_confirmation=True,
        alternatives=[
            "Use 'systemctl' for service management",
            "Use 'shutdown' or 'reboot' commands directly",
        ],
    ),
    # Privilege Escalation - CRITICAL risk
    "su": DangerousCommand(
        command="su",
        risk_level=RiskLevel.CRITICAL,
        description="Switch user (typically to root)",
        consequences=[
            "Switches to another user account",
            "'su' or 'su -' switches to root with full privileges",
            "Actions as root can modify ANY file on system",
            "Can break the operating system",
            "Security implications if password is compromised",
        ],
        backup_strategy="none",
        rollback_possible=False,
        requires_confirmation=True,
        alternatives=[
            "Use 'sudo' for single commands instead",
            "Use 'sudo -u user' to run as specific user",
        ],
    ),
    # User Management - HIGH risk
    "passwd": DangerousCommand(
        command="passwd",
        risk_level=RiskLevel.HIGH,
        description="Change user password",
        consequences=[
            "Changes password for user account",
            "If forgotten, may lock user out of system",
            "Root can change any user's password",
            "May affect automated systems using the account",
        ],
        backup_strategy="none",
        rollback_possible=False,
        requires_confirmation=True,
        alternatives=["Record new password securely", "Use password manager"],
    ),
    "useradd": DangerousCommand(
        command="useradd",
        risk_level=RiskLevel.HIGH,
        description="Create new user account",
        consequences=[
            "Creates new system user",
            "May create home directory and allocate resources",
            "User may gain shell access to system",
            "Security implications if permissions not set correctly",
        ],
        backup_strategy="none",
        rollback_possible=True,
        requires_confirmation=True,
        alternatives=[
            "Use 'adduser' for interactive creation",
            "Verify with 'id username' after creation",
        ],
    ),
    "userdel": DangerousCommand(
        command="userdel",
        risk_level=RiskLevel.HIGH,
        description="Delete user account",
        consequences=[
            "Removes user from system",
            "-r flag also removes home directory and mail",
            "User's files may become orphaned",
            "Running processes as user may be affected",
        ],
        backup_strategy="backup_directory",
        rollback_possible=False,
        requires_confirmation=True,
        alternatives=[
            "Backup user's home directory first",
            "Disable account instead: 'usermod -L username'",
        ],
    ),
    "groupadd": DangerousCommand(
        command="groupadd",
        risk_level=RiskLevel.MEDIUM,
        description="Create new group",
        consequences=[
            "Creates new system group",
            "May affect file access permissions",
            "Existing files with group may need updating",
        ],
        backup_strategy="none",
        rollback_possible=True,
        requires_confirmation=True,
        alternatives=["Verify group doesn't exist: 'getent group groupname'"],
    ),
    "visudo": DangerousCommand(
        command="visudo",
        risk_level=RiskLevel.CRITICAL,
        description="Edit sudoers file (controls root access)",
        consequences=[
            "Modifies sudo permissions for all users",
            "Syntax errors can lock everyone out of sudo",
            "Can grant root access to unauthorized users",
            "Critical security implications",
        ],
        backup_strategy="none",
        rollback_possible=True,
        requires_confirmation=True,
        alternatives=[
            "Use 'visudo -c' to check syntax first",
            "Edit files in /etc/sudoers.d/ instead",
        ],
    ),
}


class BackupManager:
    """Manages backups before dangerous operations."""

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        self.backup_dir = os.path.join(workspace_path, ".navi_backups")
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self, target: str, strategy: str) -> Dict[str, Any]:
        """Create a backup based on the strategy."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if strategy == "backup_directory":
            return self._backup_directory(target, timestamp)
        elif strategy == "record_permissions":
            return self._record_permissions(target, timestamp)
        elif strategy == "record_ownership":
            return self._record_ownership(target, timestamp)
        elif strategy == "git_stash":
            return self._git_stash(timestamp)
        elif strategy == "backup_untracked":
            return self._backup_untracked(timestamp)
        elif strategy == "git_backup_branch":
            return self._git_backup_branch(timestamp)
        elif strategy == "docker_list":
            return self._docker_list(timestamp)
        elif strategy == "none":
            return {"success": True, "message": "No backup needed", "backup_path": None}
        else:
            return {"success": False, "error": f"Unknown backup strategy: {strategy}"}

    def _backup_directory(self, target: str, timestamp: str) -> Dict[str, Any]:
        """Backup a file or directory."""
        try:
            target_path = (
                os.path.join(self.workspace_path, target)
                if not os.path.isabs(target)
                else target
            )
            if not os.path.exists(target_path):
                return {
                    "success": True,
                    "message": "Target doesn't exist, no backup needed",
                    "backup_path": None,
                }

            backup_name = f"{os.path.basename(target)}_{timestamp}"
            backup_path = os.path.join(self.backup_dir, backup_name)

            if os.path.isdir(target_path):
                shutil.copytree(target_path, backup_path)
            else:
                shutil.copy2(target_path, backup_path)

            return {
                "success": True,
                "message": f"Backed up to {backup_path}",
                "backup_path": backup_path,
                "original_path": target_path,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _record_permissions(self, target: str, timestamp: str) -> Dict[str, Any]:
        """Record current permissions for restoration."""
        try:
            target_path = (
                os.path.join(self.workspace_path, target)
                if not os.path.isabs(target)
                else target
            )
            permissions = {}

            if os.path.isdir(target_path):
                for root, dirs, files in os.walk(target_path):
                    for name in dirs + files:
                        path = os.path.join(root, name)
                        permissions[path] = oct(os.stat(path).st_mode)[-3:]
            else:
                permissions[target_path] = oct(os.stat(target_path).st_mode)[-3:]

            backup_file = os.path.join(self.backup_dir, f"permissions_{timestamp}.json")
            with open(backup_file, "w") as f:
                json.dump(permissions, f, indent=2)

            return {
                "success": True,
                "message": f"Permissions recorded to {backup_file}",
                "backup_path": backup_file,
                "permissions": permissions,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _record_ownership(self, target: str, timestamp: str) -> Dict[str, Any]:
        """Record current ownership for restoration."""
        try:
            target_path = (
                os.path.join(self.workspace_path, target)
                if not os.path.isabs(target)
                else target
            )
            ownership = {}

            if os.path.isdir(target_path):
                for root, dirs, files in os.walk(target_path):
                    for name in dirs + files:
                        path = os.path.join(root, name)
                        stat_info = os.stat(path)
                        ownership[path] = {
                            "uid": stat_info.st_uid,
                            "gid": stat_info.st_gid,
                        }
            else:
                stat_info = os.stat(target_path)
                ownership[target_path] = {
                    "uid": stat_info.st_uid,
                    "gid": stat_info.st_gid,
                }

            backup_file = os.path.join(self.backup_dir, f"ownership_{timestamp}.json")
            with open(backup_file, "w") as f:
                json.dump(ownership, f, indent=2)

            return {
                "success": True,
                "message": f"Ownership recorded to {backup_file}",
                "backup_path": backup_file,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _git_stash(self, timestamp: str) -> Dict[str, Any]:
        """Stash git changes before destructive operation."""
        try:
            # Sanitize timestamp to prevent command injection
            safe_timestamp = "".join(c for c in timestamp if c.isalnum() or c in "-_:")
            result = subprocess.run(
                ["git", "stash", "push", "-m", f"NAVI backup {safe_timestamp}"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return {
                    "success": True,
                    "message": f"Changes stashed: NAVI backup {timestamp}",
                    "restore_command": "git stash pop",
                }
            else:
                return {
                    "success": True,
                    "message": "No changes to stash",
                    "backup_path": None,
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _backup_untracked(self, timestamp: str) -> Dict[str, Any]:
        """Backup untracked files before git clean."""
        try:
            result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
            )
            untracked = (
                result.stdout.strip().split("\n") if result.stdout.strip() else []
            )

            if not untracked:
                return {
                    "success": True,
                    "message": "No untracked files to backup",
                    "backup_path": None,
                }

            backup_subdir = os.path.join(self.backup_dir, f"untracked_{timestamp}")
            os.makedirs(backup_subdir, exist_ok=True)

            for file in untracked:
                src = os.path.join(self.workspace_path, file)
                dst = os.path.join(backup_subdir, file)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if os.path.exists(src):
                    shutil.copy2(src, dst)

            return {
                "success": True,
                "message": f"Backed up {len(untracked)} untracked files to {backup_subdir}",
                "backup_path": backup_subdir,
                "files": untracked,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _git_backup_branch(self, timestamp: str) -> Dict[str, Any]:
        """Create backup branch before force push."""
        try:
            # Sanitize timestamp to prevent command injection
            safe_timestamp = "".join(c for c in timestamp if c.isalnum() or c in "-_:")
            branch_name = f"navi-backup-{safe_timestamp}"
            result = subprocess.run(
                ["git", "branch", branch_name],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return {
                    "success": True,
                    "message": f"Created backup branch: {branch_name}",
                    "backup_branch": branch_name,
                    "restore_command": f"git reset --hard {branch_name}",
                }
            else:
                return {"success": False, "error": result.stderr}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _docker_list(self, timestamp: str) -> Dict[str, Any]:
        """List Docker resources before pruning."""
        try:
            resources = {}
            for cmd, key in [
                ("docker ps -a --format '{{.ID}} {{.Names}}'", "containers"),
                ("docker images --format '{{.ID}} {{.Repository}}:{{.Tag}}'", "images"),
                ("docker volume ls --format '{{.Name}}'", "volumes"),
            ]:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                resources[key] = (
                    result.stdout.strip().split("\n") if result.stdout.strip() else []
                )

            backup_file = os.path.join(
                self.backup_dir, f"docker_resources_{timestamp}.json"
            )
            with open(backup_file, "w") as f:
                json.dump(resources, f, indent=2)

            return {
                "success": True,
                "message": f"Docker resources listed in {backup_file}",
                "backup_path": backup_file,
                "resources": resources,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


def get_command_info(command: str) -> Optional[DangerousCommand]:
    """Get danger info for a command if it's dangerous."""
    cmd_parts = command.split()
    if not cmd_parts:
        return None

    cmd_name = cmd_parts[0]

    # Check for exact command matches first
    if command in DANGEROUS_COMMANDS:
        return DANGEROUS_COMMANDS[command]

    # Check for command prefix matches (e.g., "git reset --hard")
    for key in DANGEROUS_COMMANDS:
        if command.startswith(key):
            return DANGEROUS_COMMANDS[key]

    # Check for base command
    if cmd_name in DANGEROUS_COMMANDS:
        return DANGEROUS_COMMANDS[cmd_name]

    return None


def format_permission_request(
    command: str, cmd_info: DangerousCommand, target: Optional[str] = None
) -> Dict[str, Any]:
    """Format a permission request for the UI."""
    risk_colors = {
        RiskLevel.LOW: "yellow",
        RiskLevel.MEDIUM: "orange",
        RiskLevel.HIGH: "red",
        RiskLevel.CRITICAL: "darkred",
    }

    risk_icons = {
        RiskLevel.LOW: "⚠️",
        RiskLevel.MEDIUM: "🔶",
        RiskLevel.HIGH: "🔴",
        RiskLevel.CRITICAL: "💀",
    }

    return {
        "type": "dangerous_command_permission",
        "command": command,
        "target": target,
        "risk_level": cmd_info.risk_level.value,
        "risk_color": risk_colors[cmd_info.risk_level],
        "risk_icon": risk_icons[cmd_info.risk_level],
        "description": cmd_info.description,
        "consequences": cmd_info.consequences,
        "alternatives": cmd_info.alternatives,
        "backup_strategy": cmd_info.backup_strategy,
        "rollback_possible": cmd_info.rollback_possible,
        "warning_message": f"{risk_icons[cmd_info.risk_level]} DANGEROUS OPERATION: {cmd_info.description}",
        "confirmation_required": cmd_info.requires_confirmation,
    }


def is_dangerous_command(command: str) -> bool:
    """Check if a command is in the dangerous list."""
    return get_command_info(command) is not None
