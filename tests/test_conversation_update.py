"""
Tests for PATCH /conversations/{conversation_id} endpoint.

Covers security and validation requirements per Copilot PR review:
1. Owner can update allowed fields
2. Non-owner gets 403
3. Org mismatch gets 403
4. Status validation rejects invalid values
"""

import pytest
from uuid import uuid4
from unittest.mock import Mock
from fastapi import HTTPException

from backend.api.routers.navi_memory import update_conversation, ConversationUpdate
from backend.core.auth.models import User


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock()


@pytest.fixture
def mock_conversation_service():
    """Mock conversation memory service."""
    service = Mock()
    return service


@pytest.fixture
def owner_user():
    """Create a mock owner user."""
    user = Mock(spec=User)
    user.user_id = "user-123"
    user.id = "user-123"
    user.org_id = "org-456"
    user.org_key = "org-456"
    return user


@pytest.fixture
def non_owner_user():
    """Create a mock non-owner user."""
    user = Mock(spec=User)
    user.user_id = "user-999"
    user.id = "user-999"
    user.org_id = "org-456"
    user.org_key = "org-456"
    return user


@pytest.fixture
def different_org_user():
    """Create a mock user from different org."""
    user = Mock(spec=User)
    user.user_id = "user-123"
    user.id = "user-123"
    user.org_id = "org-999"
    user.org_key = "org-999"
    return user


@pytest.fixture
def mock_conversation():
    """Create a mock conversation."""
    conversation = Mock()
    conversation.id = uuid4()
    conversation.user_id = "user-123"
    conversation.org_id = "org-456"
    conversation.title = "Original Title"
    conversation.status = "active"
    conversation.is_pinned = False
    conversation.is_starred = False
    conversation.workspace_path = "/workspace"
    conversation.initial_context = {}
    conversation.created_at = Mock()
    conversation.updated_at = Mock()
    conversation.created_at.isoformat = Mock(return_value="2024-01-01T00:00:00")
    conversation.updated_at.isoformat = Mock(return_value="2024-01-01T00:00:00")
    return conversation


@pytest.mark.asyncio
async def test_owner_can_update_allowed_fields(
    mock_db, mock_conversation_service, owner_user, mock_conversation, monkeypatch
):
    """Test that owner can update allowed fields."""
    conversation_id = mock_conversation.id

    # Mock service
    def mock_get_service(db):
        return mock_conversation_service

    monkeypatch.setattr(
        "backend.api.routers.navi_memory.get_conversation_memory_service",
        mock_get_service,
    )

    mock_conversation_service.get_conversation.return_value = mock_conversation

    # Update conversation with new values
    updated_conv = Mock()
    updated_conv.id = conversation_id
    updated_conv.user_id = "user-123"
    updated_conv.org_id = "org-456"
    updated_conv.title = "Updated Title"
    updated_conv.status = "archived"
    updated_conv.is_pinned = True
    updated_conv.is_starred = True
    updated_conv.workspace_path = "/workspace"
    updated_conv.initial_context = {}
    updated_conv.created_at = mock_conversation.created_at
    updated_conv.updated_at = Mock()
    updated_conv.updated_at.isoformat = Mock(return_value="2024-01-02T00:00:00")

    mock_conversation_service.update_conversation.return_value = updated_conv

    # Perform update
    update_data = ConversationUpdate(
        title="Updated Title",
        status="archived",
        is_pinned=True,
        is_starred=True,
    )

    result = await update_conversation(
        conversation_id=conversation_id,
        update=update_data,
        current_user=owner_user,
        db=mock_db,
    )

    # Verify service was called correctly
    mock_conversation_service.get_conversation.assert_called_once_with(conversation_id)
    mock_conversation_service.update_conversation.assert_called_once()

    # Verify response
    assert result["id"] == str(conversation_id)
    assert result["title"] == "Updated Title"
    assert result["status"] == "archived"
    assert result["is_pinned"] is True
    assert result["is_starred"] is True


@pytest.mark.asyncio
async def test_non_owner_gets_403(
    mock_db, mock_conversation_service, non_owner_user, mock_conversation, monkeypatch
):
    """Test that non-owner gets 403 error."""
    conversation_id = mock_conversation.id

    # Mock service
    def mock_get_service(db):
        return mock_conversation_service

    monkeypatch.setattr(
        "backend.api.routers.navi_memory.get_conversation_memory_service",
        mock_get_service,
    )

    mock_conversation_service.get_conversation.return_value = mock_conversation

    # Attempt update by non-owner
    update_data = ConversationUpdate(title="Hacked Title")

    with pytest.raises(HTTPException) as exc_info:
        await update_conversation(
            conversation_id=conversation_id,
            update=update_data,
            current_user=non_owner_user,
            db=mock_db,
        )

    assert exc_info.value.status_code == 403
    assert "Not authorized to modify this conversation" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_org_mismatch_gets_403(
    mock_db,
    mock_conversation_service,
    different_org_user,
    mock_conversation,
    monkeypatch,
):
    """Test that user from different org gets 403 error."""
    conversation_id = mock_conversation.id

    # Mock service
    def mock_get_service(db):
        return mock_conversation_service

    monkeypatch.setattr(
        "backend.api.routers.navi_memory.get_conversation_memory_service",
        mock_get_service,
    )

    mock_conversation_service.get_conversation.return_value = mock_conversation

    # Attempt update by user from different org
    update_data = ConversationUpdate(title="Cross-org Title")

    with pytest.raises(HTTPException) as exc_info:
        await update_conversation(
            conversation_id=conversation_id,
            update=update_data,
            current_user=different_org_user,
            db=mock_db,
        )

    assert exc_info.value.status_code == 403
    assert "Not authorized to modify this conversation" in str(exc_info.value.detail)


def test_status_validation_rejects_invalid_values():
    """Test that status validation rejects invalid values."""
    # Valid statuses should pass
    valid_update = ConversationUpdate(status="active")
    assert valid_update.status == "active"

    valid_update = ConversationUpdate(status="archived")
    assert valid_update.status == "archived"

    valid_update = ConversationUpdate(status="deleted")
    assert valid_update.status == "deleted"

    # Invalid status should fail validation
    with pytest.raises(ValueError):
        ConversationUpdate(status="invalid_status")


@pytest.mark.asyncio
async def test_conversation_not_found_returns_404(
    mock_db, mock_conversation_service, owner_user, monkeypatch
):
    """Test that non-existent conversation returns 404."""
    conversation_id = uuid4()

    # Mock service
    def mock_get_service(db):
        return mock_conversation_service

    monkeypatch.setattr(
        "backend.api.routers.navi_memory.get_conversation_memory_service",
        mock_get_service,
    )

    mock_conversation_service.get_conversation.return_value = None

    update_data = ConversationUpdate(title="New Title")

    with pytest.raises(HTTPException) as exc_info:
        await update_conversation(
            conversation_id=conversation_id,
            update=update_data,
            current_user=owner_user,
            db=mock_db,
        )

    assert exc_info.value.status_code == 404
    assert "Conversation not found" in str(exc_info.value.detail)
