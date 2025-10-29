"""
RBAC (Role-Based Access Control) database models.

Provides persistent storage for Organizations, Users, and their Role assignments.
Supports both org-wide and project-scoped role grants.
"""

from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.core.database import Base


class Organization(Base):
    """
    Organization/tenant entity.

    Each org has a unique key (e.g., 'navralabs') used for lookups
    and isolation of users/resources.
    """

    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    org_key = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)

    # Relationships
    users = relationship("DBUser", back_populates="organization", cascade="all, delete-orphan")


class DBUser(Base):
    """
    User entity linked to an Organization.

    The 'sub' (subject) claim from JWT serves as the stable identifier.
    Email and display_name can be updated from JWT or admin API.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sub = Column(String(128), unique=True, index=True, nullable=False)  # JWT subject
    email = Column(String(255), index=True, nullable=False)
    display_name = Column(String(255), nullable=False, default="")
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="users")
    roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")


class DBRole(Base):
    """
    Role definition: viewer, planner, admin.

    Seeded during migration with the three standard roles.
    """

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(32), unique=True, nullable=False)


class UserRole(Base):
    """
    Assignment of a Role to a User, optionally scoped to a project.

    - project_key=None: org-wide role
    - project_key='proj-123': role applies only to that project
    """

    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    project_key = Column(String(128), nullable=True)  # None = org-wide

    # Relationships
    user = relationship("DBUser", back_populates="roles")
    role = relationship("DBRole")

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", "project_key", name="uq_user_role_scope"),
    )
