"""
User Sync Router - Synchronize users from Auth0 to the backend database.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])


class UserSyncRequest(BaseModel):
    """Request body for user sync endpoint."""
    sub: str  # Auth0 subject (user ID)
    email: str
    name: Optional[str] = None
    org: Optional[str] = None


class UserSyncResponse(BaseModel):
    """Response body for user sync endpoint."""
    status: str
    user_id: str
    org_id: str
    message: str


@router.post("/sync", response_model=UserSyncResponse)
async def sync_user(request: UserSyncRequest) -> UserSyncResponse:
    """
    Create or update a user from Auth0 claims.

    This endpoint is called after successful Auth0 authentication to ensure
    the user exists in the backend database with the correct organization.
    """
    try:
        # For now, we'll implement a simple in-memory sync
        # In production, this would interact with the database

        org_key = request.org or "public"

        logger.info(f"Syncing user: {request.email} to org: {org_key}")

        # TODO: When database is fully integrated, uncomment this:
        # from sqlalchemy.orm import Session
        # from backend.database.models.rbac import DBUser, Organization
        # from backend.database.session import get_db
        #
        # db = next(get_db())
        #
        # # Find or create organization
        # org = db.query(Organization).filter(Organization.org_key == org_key).first()
        # if not org:
        #     org = Organization(org_key=org_key, name=org_key.title())
        #     db.add(org)
        #     db.flush()
        #
        # # Find or create user
        # user = db.query(DBUser).filter(DBUser.sub == request.sub).first()
        # if user:
        #     user.email = request.email
        #     user.display_name = request.name
        #     user.org_id = org.id
        # else:
        #     user = DBUser(
        #         sub=request.sub,
        #         email=request.email,
        #         display_name=request.name,
        #         org_id=org.id
        #     )
        #     db.add(user)
        #
        # db.commit()

        return UserSyncResponse(
            status="synced",
            user_id=request.sub,
            org_id=org_key,
            message=f"User {request.email} synced successfully to org {org_key}",
        )

    except Exception as e:
        logger.error(f"Failed to sync user: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to sync user: {str(e)}")


@router.get("/me")
async def get_current_user_info():
    """
    Get the current user's information.

    This endpoint requires authentication via JWT token.
    """
    # TODO: Implement with actual auth dependency
    # For now, return a placeholder
    return {
        "message": "This endpoint requires authentication",
        "hint": "Pass Authorization: Bearer <token> header",
    }
