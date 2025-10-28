"""Authentication and authorization models for RBAC."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Role(str, Enum):
    """
    User roles for role-based access control (RBAC).

    Hierarchy: viewer < planner < admin
    - viewer: read-only access (can subscribe to SSE streams)
    - planner: can modify plans (add steps, publish)
    - admin: full access (manage plans, users, settings)
    """

    VIEWER = "viewer"
    PLANNER = "planner"
    ADMIN = "admin"

    # Role hierarchy order for comparison operations
    _ROLE_ORDER = {"viewer": 0, "planner": 1, "admin": 2}

    def __lt__(self, other):
        """Define ordering for role hierarchy comparisons."""
        if not isinstance(other, Role):
            return NotImplemented
        return self._ROLE_ORDER[self.value] < self._ROLE_ORDER[other.value]

    def __le__(self, other):
        """Define less-than-or-equal for role hierarchy."""
        if not isinstance(other, Role):
            return NotImplemented
        return self == other or self < other

    def __gt__(self, other):
        """Define greater-than for role hierarchy."""
        if not isinstance(other, Role):
            return NotImplemented
        return other < self

    def __ge__(self, other):
        """Define greater-than-or-equal for role hierarchy."""
        if not isinstance(other, Role):
            return NotImplemented
        return self == other or self > other


class User(BaseModel):
    """
    User context for authentication and authorization.

    In production, this would be populated from JWT claims or session.
    For development, use DEV_* environment variables as a shim.
    """

    user_id: str = Field(..., description="Unique user identifier")
    email: Optional[str] = Field(None, description="User email address")
    role: Role = Field(
        default=Role.VIEWER, description="User role (viewer, planner, admin)"
    )
    org_id: Optional[str] = Field(None, description="Organization ID")
    projects: list[str] = Field(
        default_factory=list,
        description="Project IDs the user has access to",
    )

    class Config:
        """Pydantic model configuration."""

        use_enum_values = False  # Keep Role enum instances
