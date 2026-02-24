"""
User model for database.
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from backend.core.database import Base


class User(Base):
    """User model - synced from Auth0."""

    __tablename__ = "users"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Auth0 identity
    auth0_user_id = Column(String(255), unique=True, nullable=False, index=True)

    # Profile data
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    avatar_url = Column(Text, nullable=True)
    email_verified = Column(Boolean, default=False, nullable=False)

    # Subscription & billing
    subscription_plan = Column(
        String(50),
        default="free",
        nullable=False
    )  # free, premium, enterprise
    subscription_status = Column(
        String(50),
        default="active",
        nullable=False
    )  # active, canceled, past_due

    # Metadata
    user_metadata = Column(JSON, default=dict, nullable=False)  # User-editable
    app_metadata = Column(JSON, default=dict, nullable=False)   # System-managed

    # Settings
    preferences = Column(JSON, default=dict, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Soft delete
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<User {self.email}>"

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "auth0_user_id": self.auth0_user_id,
            "email": self.email,
            "name": self.name,
            "avatar_url": self.avatar_url,
            "email_verified": self.email_verified,
            "subscription_plan": self.subscription_plan,
            "subscription_status": self.subscription_status,
            "preferences": self.preferences,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None
        }
