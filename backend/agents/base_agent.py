"""
Base agent class for the autonomous engineering platform.
This is a stub implementation for agents that need a common base class.
"""

from typing import Dict, Any, Optional
from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.
    """

    def __init__(self):
        self.agent_id: Optional[str] = None
        self.agent_type: str = "base"

    @abstractmethod
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a task.

        Args:
            task: Task definition

        Returns:
            Execution result
        """
        pass

    @abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """
        Get agent status.

        Returns:
            Status information
        """
        pass
