"""
User synchronization endpoint for Auth0 Actions.
Called post-login to sync user data from Auth0 to our database.
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from typing import Optional
import logging

from backend.core.config import get_settings
from backend.database.session import get_db
from backend.database.models.user import User
from datetime import datetime

router = APIRouter(prefix="/internal/auth", tags=["auth-sync"])
logger = logging.getLogger(__name__)
settings = get_settings()


class UserSyncPayload(BaseModel):
    """Payload from Auth0 post-login action."""
    auth0_user_id: str
    email: EmailStr
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    email_verified: bool = False


def verify_action_secret(x_auth0_action_secret: str = Header(...)):
    """Verify request is coming from Auth0 Action."""
    expected_secret = getattr(settings, "auth0_action_secret", None)

    if not expected_secret:
        raise HTTPException(
            status_code=500,
            detail="AUTH0_ACTION_SECRET not configured"
        )

    if x_auth0_action_secret != expected_secret:
        raise HTTPException(
            status_code=401,
            detail="Invalid action secret"
        )

    return True


@router.post("/sync-user")
async def sync_user_from_auth0(
    payload: UserSyncPayload,
    db: Session = Depends(get_db),
    _verified: bool = Depends(verify_action_secret)
):
    """
    Sync user data from Auth0 to database.

    Called by Auth0 post-login action to create or update user record.
    This ensures every authenticated user exists in our database.
    """

    try:
        # Check if user exists
        user = db.query(User).filter(
            User.auth0_user_id == payload.auth0_user_id
        ).first()

        if user:
            # Update existing user
            user.email = payload.email
            user.name = payload.name
            user.avatar_url = payload.avatar_url
            user.email_verified = payload.email_verified
            user.updated_at = datetime.utcnow()

            logger.info(f"Updated user: {payload.auth0_user_id}")

        else:
            # Create new user
            user = User(
                auth0_user_id=payload.auth0_user_id,
                email=payload.email,
                name=payload.name,
                avatar_url=payload.avatar_url,
                email_verified=payload.email_verified,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(user)

            logger.info(f"Created new user: {payload.auth0_user_id}")

        db.commit()
        db.refresh(user)

        return {
            "success": True,
            "user_id": str(user.id),
            "is_new_user": user.created_at == user.updated_at
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to sync user {payload.auth0_user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync user: {str(e)}"
        )


@router.get("/user/{auth0_user_id}")
async def get_user_by_auth0_id(
    auth0_user_id: str,
    db: Session = Depends(get_db),
    _verified: bool = Depends(verify_action_secret)
):
    """Get user by Auth0 user ID (for internal use)."""

    user = db.query(User).filter(
        User.auth0_user_id == auth0_user_id
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": str(user.id),
        "auth0_user_id": user.auth0_user_id,
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "email_verified": user.email_verified,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat()
    }
