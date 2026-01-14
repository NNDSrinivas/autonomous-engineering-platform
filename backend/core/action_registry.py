"""
Dynamic Action Registry System for NAVI Backend

This provides a plugin-based approach to handling actions.
Instead of hardcoding action types, handlers are registered based on capabilities.

Benefits:
- Actions can be added without modifying core code
- Handlers are self-describing based on their capabilities
- Easy to extend with new action types
- No tight coupling between intent detection and action execution
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ActionPriority(Enum):
    """Priority levels for action handlers"""

    CRITICAL = 100  # System-level actions
    HIGH = 80  # Core functionality
    NORMAL = 50  # Default priority
    LOW = 20  # Optional/experimental


@dataclass
class ActionContext:
    """Context provided to action handlers"""

    workspace: str
    project_type: str = "unknown"
    current_file: Optional[str] = None
    technologies: List[str] = None
    dependencies: Dict[str, str] = None
    user_id: str = "default"
    session_id: Optional[str] = None

    def __post_init__(self):
        if self.technologies is None:
            self.technologies = []
        if self.dependencies is None:
            self.dependencies = {}


@dataclass
class ActionResult:
    """Result of action execution"""

    success: bool
    action: str
    message: str
    data: Optional[Dict[str, Any]] = None
    files_created: Optional[List[str]] = None
    files_modified: Optional[List[str]] = None
    commands_run: Optional[List[str]] = None
    error: Optional[str] = None
    vscode_command: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        result = {
            "success": self.success,
            "action": self.action,
            "message": self.message,
        }

        if self.data:
            result["data"] = self.data
        if self.files_created:
            result["files_created"] = self.files_created
        if self.files_modified:
            result["files_modified"] = self.files_modified
        if self.commands_run:
            result["commands_run"] = self.commands_run
        if self.error:
            result["error"] = self.error
        if self.vscode_command:
            result["vscode_command"] = self.vscode_command

        return result


class ActionHandler(ABC):
    """
    Abstract base class for action handlers

    Handlers register themselves with capabilities and implement
    can_handle() to determine if they can process an action.
    """

    def __init__(
        self, handler_id: str, priority: ActionPriority = ActionPriority.NORMAL
    ):
        self.handler_id = handler_id
        self.priority = priority

    @abstractmethod
    def can_handle(self, action: str, target: str, context: ActionContext) -> bool:
        """
        Determine if this handler can process the given action

        Args:
            action: The action type/name (e.g., "create_component", "open_project")
            target: The action target (e.g., "Button", "my-app")
            context: Execution context with workspace info

        Returns:
            True if this handler can process the action
        """
        pass

    @abstractmethod
    async def execute(
        self, action: str, target: str, context: ActionContext
    ) -> ActionResult:
        """
        Execute the action

        Args:
            action: The action type/name
            target: The action target
            context: Execution context

        Returns:
            ActionResult with success status and details
        """
        pass

    def get_description(self) -> str:
        """Get human-readable description of what this handler does"""
        return f"Handler: {self.handler_id}"

    def get_examples(self) -> List[str]:
        """Get example actions this handler can process"""
        return []


class ActionRegistry:
    """
    Registry for action handlers

    Provides dynamic routing of actions to appropriate handlers
    based on capability matching.
    """

    def __init__(self):
        self.handlers: List[ActionHandler] = []
        self._handler_map: Dict[str, ActionHandler] = {}

    def register(self, handler: ActionHandler) -> None:
        """
        Register an action handler

        Handlers are sorted by priority (highest first)
        """
        self.handlers.append(handler)
        self.handlers.sort(key=lambda h: h.priority.value, reverse=True)

        logger.info(
            f"[ActionRegistry] Registered handler: {handler.handler_id} "
            f"(priority: {handler.priority.name})"
        )

    def unregister(self, handler_id: str) -> None:
        """Unregister a handler by ID"""
        self.handlers = [h for h in self.handlers if h.handler_id != handler_id]
        logger.info(f"[ActionRegistry] Unregistered handler: {handler_id}")

    async def execute(
        self, action: str, target: str, context: ActionContext
    ) -> ActionResult:
        """
        Execute an action by finding the appropriate handler

        Args:
            action: The action type/name
            target: The action target
            context: Execution context

        Returns:
            ActionResult with execution status and details
        """
        if not action:
            return ActionResult(
                success=False,
                action="unknown",
                message="No action specified",
                error="Action is required",
            )

        # Find the first handler that can handle this action
        handler = None
        for h in self.handlers:
            try:
                if h.can_handle(action, target, context):
                    handler = h
                    break
            except Exception as e:
                logger.error(
                    f"[ActionRegistry] Error checking handler {h.handler_id}: {e}"
                )
                continue

        if not handler:
            logger.warning(
                f"[ActionRegistry] No handler found for action: {action} (target: {target})"
            )
            return ActionResult(
                success=False,
                action=action,
                message=f"No handler found for action: {action}",
                error=f"Unsupported action type: {action}",
            )

        logger.info(
            f"[ActionRegistry] Executing action '{action}' with handler: {handler.handler_id}"
        )

        try:
            result = await handler.execute(action, target, context)
            return result
        except Exception as e:
            logger.error(
                f"[ActionRegistry] Handler {handler.handler_id} failed: {e}",
                exc_info=True,
            )
            return ActionResult(
                success=False,
                action=action,
                message=f"Action execution failed: {str(e)}",
                error=str(e),
            )

    def get_handlers(self) -> List[ActionHandler]:
        """Get all registered handlers"""
        return list(self.handlers)

    def get_handler(self, handler_id: str) -> Optional[ActionHandler]:
        """Get handler by ID"""
        return next((h for h in self.handlers if h.handler_id == handler_id), None)

    def get_supported_actions(self) -> List[Dict[str, Any]]:
        """
        Get list of all supported actions from registered handlers

        Returns:
            List of action definitions with name, description, examples
        """
        actions = []
        seen_handlers = set()

        for handler in self.handlers:
            if handler.handler_id in seen_handlers:
                continue

            seen_handlers.add(handler.handler_id)

            actions.append(
                {
                    "handler_id": handler.handler_id,
                    "description": handler.get_description(),
                    "examples": handler.get_examples(),
                    "priority": handler.priority.name,
                }
            )

        return actions


# Global registry instance
_global_registry: Optional[ActionRegistry] = None


def get_action_registry() -> ActionRegistry:
    """Get the global action registry instance"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ActionRegistry()
    return _global_registry


def register_handler(handler: ActionHandler) -> None:
    """Register a handler with the global registry"""
    registry = get_action_registry()
    registry.register(handler)
