"""
NAVI Settings - User-configurable execution preferences.

This module defines the settings that control how NAVI behaves when
executing tasks. Users can configure these through the VS Code settings panel.

Settings Categories:
1. Execution Mode - How autonomous should NAVI be
2. Approval Gates - What operations require user approval
3. Auto-Actions - What NAVI can do automatically
4. Safety Limits - Boundaries for autonomous operation
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ExecutionStyle(Enum):
    """Overall execution style for NAVI."""

    FULLY_AUTONOMOUS = "fully_autonomous"  # Execute everything without asking
    SEMI_AUTONOMOUS = "semi_autonomous"  # Execute most things, ask for critical ops
    GUIDED = "guided"  # Always show plan, ask before execution
    MANUAL = "manual"  # Only suggest, never execute without explicit approval


class ApprovalLevel(Enum):
    """When to require approval for an operation."""

    NEVER = "never"  # Never ask (fully trusted)
    DANGEROUS_ONLY = "dangerous_only"  # Only for destructive operations
    WRITES_ONLY = "writes_only"  # For any write operation
    ALWAYS = "always"  # Always ask before executing


@dataclass
class ApprovalSettings:
    """Settings for when NAVI should ask for approval."""

    # File operations
    file_create: ApprovalLevel = ApprovalLevel.NEVER
    file_edit: ApprovalLevel = ApprovalLevel.NEVER
    file_delete: ApprovalLevel = ApprovalLevel.ALWAYS  # Default: always ask for deletes

    # Command operations
    run_commands: ApprovalLevel = ApprovalLevel.DANGEROUS_ONLY
    run_tests: ApprovalLevel = ApprovalLevel.NEVER
    install_packages: ApprovalLevel = ApprovalLevel.WRITES_ONLY

    # External operations
    api_calls: ApprovalLevel = ApprovalLevel.NEVER
    git_operations: ApprovalLevel = ApprovalLevel.WRITES_ONLY
    deploy_operations: ApprovalLevel = ApprovalLevel.ALWAYS

    def requires_approval(self, operation: str, context: Optional[Dict] = None) -> bool:
        """Check if an operation requires approval based on settings."""
        # Map operations to their approval levels
        operation_map = {
            "file_create": self.file_create,
            "file_edit": self.file_edit,
            "file_delete": self.file_delete,
            "run_command": self.run_commands,
            "run_test": self.run_tests,
            "install_package": self.install_packages,
            "api_call": self.api_calls,
            "git_commit": self.git_operations,
            "git_push": self.git_operations,
            "deploy": self.deploy_operations,
        }

        level = operation_map.get(operation, ApprovalLevel.WRITES_ONLY)

        if level == ApprovalLevel.NEVER:
            return False
        elif level == ApprovalLevel.ALWAYS:
            return True
        elif level == ApprovalLevel.DANGEROUS_ONLY:
            # Check if operation is considered dangerous
            dangerous_patterns = ["delete", "remove", "drop", "force", "reset --hard"]
            if context:
                cmd = str(context.get("command", "")).lower()
                return any(p in cmd for p in dangerous_patterns)
            return False
        elif level == ApprovalLevel.WRITES_ONLY:
            # These are write operations by definition
            return operation in [
                "file_create",
                "file_edit",
                "file_delete",
                "git_commit",
                "git_push",
                "deploy",
                "install_package",
            ]

        return True  # Default to requiring approval

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApprovalSettings":
        """Create ApprovalSettings from a dictionary."""

        def parse_level(key: str, default: ApprovalLevel) -> ApprovalLevel:
            value = data.get(key, default.value)
            try:
                return ApprovalLevel(value)
            except ValueError:
                return default

        return cls(
            file_create=parse_level("file_create", ApprovalLevel.NEVER),
            file_edit=parse_level("file_edit", ApprovalLevel.NEVER),
            file_delete=parse_level("file_delete", ApprovalLevel.ALWAYS),
            run_commands=parse_level("run_commands", ApprovalLevel.DANGEROUS_ONLY),
            run_tests=parse_level("run_tests", ApprovalLevel.NEVER),
            install_packages=parse_level("install_packages", ApprovalLevel.WRITES_ONLY),
            api_calls=parse_level("api_calls", ApprovalLevel.NEVER),
            git_operations=parse_level("git_operations", ApprovalLevel.WRITES_ONLY),
            deploy_operations=parse_level("deploy_operations", ApprovalLevel.ALWAYS),
        )

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for storage."""
        return {
            "file_create": self.file_create.value,
            "file_edit": self.file_edit.value,
            "file_delete": self.file_delete.value,
            "run_commands": self.run_commands.value,
            "run_tests": self.run_tests.value,
            "install_packages": self.install_packages.value,
            "api_calls": self.api_calls.value,
            "git_operations": self.git_operations.value,
            "deploy_operations": self.deploy_operations.value,
        }


@dataclass
class AutoActionSettings:
    """Settings for what NAVI can do automatically."""

    # Auto-run tests after code changes
    auto_run_tests: bool = True

    # Auto-fix lint errors
    auto_fix_lint: bool = True

    # Auto-format code
    auto_format_code: bool = True

    # Auto-install missing dependencies
    auto_install_deps: bool = False

    # Auto-commit after successful changes (with approval)
    auto_commit: bool = False

    # Auto-iterate on test failures (up to max_iterations)
    auto_iterate_on_failures: bool = True
    max_auto_iterations: int = 5

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AutoActionSettings":
        """Create AutoActionSettings from a dictionary."""
        return cls(
            auto_run_tests=data.get("auto_run_tests", True),
            auto_fix_lint=data.get("auto_fix_lint", True),
            auto_format_code=data.get("auto_format_code", True),
            auto_install_deps=data.get("auto_install_deps", False),
            auto_commit=data.get("auto_commit", False),
            auto_iterate_on_failures=data.get("auto_iterate_on_failures", True),
            max_auto_iterations=data.get("max_auto_iterations", 5),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "auto_run_tests": self.auto_run_tests,
            "auto_fix_lint": self.auto_fix_lint,
            "auto_format_code": self.auto_format_code,
            "auto_install_deps": self.auto_install_deps,
            "auto_commit": self.auto_commit,
            "auto_iterate_on_failures": self.auto_iterate_on_failures,
            "max_auto_iterations": self.max_auto_iterations,
        }


@dataclass
class SafetySettings:
    """Safety limits for autonomous operation."""

    # Maximum files that can be modified in one operation
    max_files_per_operation: int = 20

    # Maximum lines of code that can be changed
    max_lines_changed: int = 500

    # Paths that NAVI should never modify
    protected_paths: List[str] = field(
        default_factory=lambda: [
            ".env",
            ".env.local",
            ".env.production",
            "credentials.json",
            "secrets.yaml",
            "**/secrets/**",
            "**/.git/**",
        ]
    )

    # Commands that should never be run
    blocked_commands: List[str] = field(
        default_factory=lambda: [
            "rm -rf /",
            "rm -rf ~",
            "DROP DATABASE",
            "DROP TABLE",
            "> /dev/sda",
            ":(){ :|:& };:",
        ]
    )

    # Require confirmation for operations in production branches
    confirm_production_branches: bool = True
    production_branches: List[str] = field(
        default_factory=lambda: [
            "main",
            "master",
            "production",
            "prod",
        ]
    )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SafetySettings":
        """Create SafetySettings from a dictionary."""
        return cls(
            max_files_per_operation=data.get("max_files_per_operation", 20),
            max_lines_changed=data.get("max_lines_changed", 500),
            protected_paths=data.get(
                "protected_paths",
                cls.__dataclass_fields__["protected_paths"].default_factory(),
            ),
            blocked_commands=data.get(
                "blocked_commands",
                cls.__dataclass_fields__["blocked_commands"].default_factory(),
            ),
            confirm_production_branches=data.get("confirm_production_branches", True),
            production_branches=data.get(
                "production_branches",
                cls.__dataclass_fields__["production_branches"].default_factory(),
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "max_files_per_operation": self.max_files_per_operation,
            "max_lines_changed": self.max_lines_changed,
            "protected_paths": self.protected_paths,
            "blocked_commands": self.blocked_commands,
            "confirm_production_branches": self.confirm_production_branches,
            "production_branches": self.production_branches,
        }

    def is_path_protected(self, path: str) -> bool:
        """Check if a path is protected."""
        import fnmatch

        for pattern in self.protected_paths:
            if fnmatch.fnmatch(path, pattern):
                return True
        return False

    def is_command_blocked(self, command: str) -> bool:
        """Check if a command is blocked."""
        cmd_lower = command.lower()
        for blocked in self.blocked_commands:
            if blocked.lower() in cmd_lower:
                return True
        return False


@dataclass
class NaviSettings:
    """Complete NAVI settings configuration."""

    # Overall execution style
    execution_style: ExecutionStyle = ExecutionStyle.SEMI_AUTONOMOUS

    # Detailed approval settings
    approvals: ApprovalSettings = field(default_factory=ApprovalSettings)

    # Auto-action settings
    auto_actions: AutoActionSettings = field(default_factory=AutoActionSettings)

    # Safety settings
    safety: SafetySettings = field(default_factory=SafetySettings)

    # UI preferences
    show_plan_before_execution: bool = True
    show_progress_updates: bool = True
    verbose_logging: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NaviSettings":
        """Create NaviSettings from a dictionary (e.g., from VS Code settings)."""
        # Parse execution style
        exec_style_str = data.get("execution_style", "semi_autonomous")
        try:
            exec_style = ExecutionStyle(exec_style_str)
        except ValueError:
            exec_style = ExecutionStyle.SEMI_AUTONOMOUS

        return cls(
            execution_style=exec_style,
            approvals=ApprovalSettings.from_dict(data.get("approvals", {})),
            auto_actions=AutoActionSettings.from_dict(data.get("auto_actions", {})),
            safety=SafetySettings.from_dict(data.get("safety", {})),
            show_plan_before_execution=data.get("show_plan_before_execution", True),
            show_progress_updates=data.get("show_progress_updates", True),
            verbose_logging=data.get("verbose_logging", False),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "execution_style": self.execution_style.value,
            "approvals": self.approvals.to_dict(),
            "auto_actions": self.auto_actions.to_dict(),
            "safety": self.safety.to_dict(),
            "show_plan_before_execution": self.show_plan_before_execution,
            "show_progress_updates": self.show_progress_updates,
            "verbose_logging": self.verbose_logging,
        }

    def should_show_plan(self) -> bool:
        """Check if plan should be shown before execution."""
        if self.execution_style == ExecutionStyle.FULLY_AUTONOMOUS:
            return False
        return self.show_plan_before_execution

    def should_iterate_on_failures(self) -> bool:
        """Check if NAVI should auto-iterate on test failures."""
        return self.auto_actions.auto_iterate_on_failures

    def get_max_iterations(self) -> int:
        """Get maximum number of auto-iterations."""
        return self.auto_actions.max_auto_iterations

    def requires_approval_for(
        self, operation: str, context: Optional[Dict] = None
    ) -> bool:
        """Check if an operation requires approval."""
        # Fully autonomous mode skips most approvals
        if self.execution_style == ExecutionStyle.FULLY_AUTONOMOUS:
            # Still respect dangerous-only for safety
            if operation in ["file_delete", "deploy"]:
                return self.approvals.requires_approval(operation, context)
            return False

        # Manual mode always requires approval
        if self.execution_style == ExecutionStyle.MANUAL:
            return True

        # Semi-autonomous and guided modes use approval settings
        return self.approvals.requires_approval(operation, context)


# Default settings for different presets
PRESET_SETTINGS = {
    "autonomous": NaviSettings(
        execution_style=ExecutionStyle.FULLY_AUTONOMOUS,
        approvals=ApprovalSettings(
            file_create=ApprovalLevel.NEVER,
            file_edit=ApprovalLevel.NEVER,
            file_delete=ApprovalLevel.DANGEROUS_ONLY,
            run_commands=ApprovalLevel.DANGEROUS_ONLY,
        ),
        auto_actions=AutoActionSettings(
            auto_run_tests=True,
            auto_fix_lint=True,
            auto_iterate_on_failures=True,
        ),
        show_plan_before_execution=False,
    ),
    "balanced": NaviSettings(
        execution_style=ExecutionStyle.SEMI_AUTONOMOUS,
        approvals=ApprovalSettings(
            file_create=ApprovalLevel.NEVER,
            file_edit=ApprovalLevel.NEVER,
            file_delete=ApprovalLevel.ALWAYS,
            run_commands=ApprovalLevel.DANGEROUS_ONLY,
            git_operations=ApprovalLevel.WRITES_ONLY,
        ),
        auto_actions=AutoActionSettings(
            auto_run_tests=True,
            auto_fix_lint=True,
            auto_iterate_on_failures=True,
        ),
        show_plan_before_execution=True,
    ),
    "careful": NaviSettings(
        execution_style=ExecutionStyle.GUIDED,
        approvals=ApprovalSettings(
            file_create=ApprovalLevel.WRITES_ONLY,
            file_edit=ApprovalLevel.WRITES_ONLY,
            file_delete=ApprovalLevel.ALWAYS,
            run_commands=ApprovalLevel.ALWAYS,
            git_operations=ApprovalLevel.ALWAYS,
        ),
        auto_actions=AutoActionSettings(
            auto_run_tests=True,
            auto_fix_lint=False,
            auto_iterate_on_failures=False,
        ),
        show_plan_before_execution=True,
    ),
    "manual": NaviSettings(
        execution_style=ExecutionStyle.MANUAL,
        approvals=ApprovalSettings(
            file_create=ApprovalLevel.ALWAYS,
            file_edit=ApprovalLevel.ALWAYS,
            file_delete=ApprovalLevel.ALWAYS,
            run_commands=ApprovalLevel.ALWAYS,
            git_operations=ApprovalLevel.ALWAYS,
        ),
        auto_actions=AutoActionSettings(
            auto_run_tests=False,
            auto_fix_lint=False,
            auto_iterate_on_failures=False,
        ),
        show_plan_before_execution=True,
    ),
}


def get_settings_for_preset(preset: str) -> NaviSettings:
    """Get settings for a named preset."""
    return PRESET_SETTINGS.get(preset, PRESET_SETTINGS["balanced"])


# In-memory cache for user settings
_user_settings_cache: Dict[str, NaviSettings] = {}


async def get_user_settings(user_id: str, db=None) -> NaviSettings:
    """
    Get settings for a user.

    Loads from database if available, otherwise returns defaults.
    """
    if user_id in _user_settings_cache:
        return _user_settings_cache[user_id]

    # Try to load from database
    if db:
        try:
            # TODO: Implement database storage
            # For now, return defaults
            pass
        except Exception as e:
            logger.warning("Failed to load user settings: %s", e)

    # Return default settings
    settings = NaviSettings()
    _user_settings_cache[user_id] = settings
    return settings


async def save_user_settings(user_id: str, settings: NaviSettings, db=None) -> bool:
    """
    Save settings for a user.

    Stores in database and updates cache.
    """
    _user_settings_cache[user_id] = settings

    if db:
        try:
            # TODO: Implement database storage
            pass
        except Exception as e:
            logger.error("Failed to save user settings: %s", e)
            return False

    return True


def update_user_settings_from_workspace(
    user_id: str, workspace_settings: Dict[str, Any]
):
    """
    Update user settings from VS Code workspace settings.

    Called when workspace settings change.
    """
    navi_config = workspace_settings.get("navi", {})
    if navi_config:
        settings = NaviSettings.from_dict(navi_config)
        _user_settings_cache[user_id] = settings
        logger.info("Updated NAVI settings for user %s from workspace", user_id)
