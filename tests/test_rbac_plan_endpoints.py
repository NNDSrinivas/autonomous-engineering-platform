"""Tests for RBAC and policy enforcement on Live Plan APIs."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.core.db import get_db


def get_mock_db():
    """
    Create a mock database session with pre-configured query chain.

    Sets up: query().filter().order_by().limit().all() -> []
    This helper improves readability over inline chained mock configuration.
    """
    mock_session = MagicMock()

    # Configure the query chain step-by-step for clarity
    mock_all = MagicMock(return_value=[])
    mock_limit = MagicMock()
    mock_limit.all = mock_all

    mock_order_by = MagicMock()
    mock_order_by.limit.return_value = mock_limit

    mock_filter = MagicMock()
    mock_filter.order_by.return_value = mock_order_by

    mock_query = MagicMock()
    mock_query.filter.return_value = mock_filter

    mock_session.query.return_value = mock_query

    return mock_session


@pytest.fixture
def client():
    """Test client for FastAPI app with mocked database."""
    app.dependency_overrides[get_db] = get_mock_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestRBACHappyPaths:
    """Test successful operations with correct roles."""

    def test_viewer_can_list_plans(self, client):
        """Viewer role can list plans."""
        # Set up dev auth shim
        env_vars = {
            "DEV_USER_ID": "u-viewer",
            "DEV_USER_ROLE": "viewer",
            "DEV_ORG_ID": "org-1",
        }
        with patch.dict(os.environ, env_vars):
            response = client.get(
                "/api/plan/list",
                headers={"X-Org-Id": "org-1"},
            )

            assert response.status_code == 200
            assert "plans" in response.json()

    def test_viewer_can_stream_plans(self, client):
        """Viewer role can subscribe to SSE stream."""
        from backend.database.models.live_plan import LivePlan

        # Mock SessionLocal for the endpoint's short-lived session
        mock_plan = LivePlan(
            id="plan-123",
            org_id="org-1",
            title="Test Plan",
            steps=[],
            participants=[],
            archived=False,
        )

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_plan
        )
        mock_session.close = MagicMock()

        with patch("backend.api.routers.plan.SessionLocal", return_value=mock_session):
            env_vars = {
                "DEV_USER_ID": "u-viewer",
                "DEV_USER_ROLE": "viewer",
                "DEV_ORG_ID": "org-1",
            }
            with patch.dict(os.environ, env_vars):
                # Use streaming context to avoid blocking
                with client.stream(
                    "GET",
                    "/api/plan/plan-123/stream",
                    headers={"X-Org-Id": "org-1"},
                ) as response:
                    # Verify we got 200 (not 403 forbidden)
                    assert response.status_code == 200

                    # Read first chunk to verify SSE format
                    first_chunk = next(response.iter_bytes())
                    assert b"data:" in first_chunk

                    # Close immediately to avoid blocking test
                    response.close()

    def test_planner_can_start_plan(self, client):
        """Planner role can create new plans."""

        def get_mock_db_for_create():
            mock_session = MagicMock()
            mock_session.add = MagicMock()
            mock_session.commit = MagicMock()
            mock_session.refresh = MagicMock()
            return mock_session

        app.dependency_overrides[get_db] = get_mock_db_for_create

        env_vars = {
            "DEV_USER_ID": "u-planner",
            "DEV_USER_ROLE": "planner",
            "DEV_ORG_ID": "org-1",
        }
        with patch.dict(os.environ, env_vars):
            response = client.post(
                "/api/plan/start",
                json={"title": "New Plan", "description": "Test"},
                headers={"X-Org-Id": "org-1"},
            )

            assert response.status_code == 200
            assert "plan_id" in response.json()

    def test_planner_can_add_step(self, client):
        """Planner role can add steps to plans."""
        # Mock plan lookup
        from backend.database.models.live_plan import LivePlan

        mock_plan = LivePlan(
            id="plan-123",
            org_id="org-1",
            title="Test Plan",
            steps=[],
            participants=[],
            archived=False,
        )

        def get_mock_db_for_step():
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = (
                mock_plan
            )
            mock_session.commit = MagicMock()
            return mock_session

        app.dependency_overrides[get_db] = get_mock_db_for_step

        # Mock broadcaster
        from backend.api.deps import get_broadcaster

        mock_bc = AsyncMock()
        mock_bc.publish = AsyncMock()
        app.dependency_overrides[get_broadcaster] = lambda: mock_bc

        env_vars = {
            "DEV_USER_ID": "u-planner",
            "DEV_USER_ROLE": "planner",
            "DEV_ORG_ID": "org-1",
        }
        with patch.dict(os.environ, env_vars):
            response = client.post(
                "/api/plan/step",
                json={
                    "plan_id": "plan-123",
                    "text": "Run pytest",
                    "owner": "u-planner",
                },
                headers={"X-Org-Id": "org-1"},
            )

            assert response.status_code == 200
            assert response.json()["status"] == "step_added"


class TestRBACDenyPaths:
    """Test operations blocked due to insufficient roles."""

    def test_viewer_cannot_start_plan(self, client):
        """Viewer role blocked from creating plans."""
        env_vars = {
            "DEV_USER_ID": "u-viewer",
            "DEV_USER_ROLE": "viewer",
            "DEV_ORG_ID": "org-1",
        }
        with patch.dict(os.environ, env_vars):
            response = client.post(
                "/api/plan/start",
                json={"title": "Blocked Plan"},
                headers={"X-Org-Id": "org-1"},
            )

            assert response.status_code == 403
            assert "planner" in response.json()["detail"].lower()

    def test_viewer_cannot_add_step(self, client):
        """Viewer role blocked from adding steps."""
        env_vars = {
            "DEV_USER_ID": "u-viewer",
            "DEV_USER_ROLE": "viewer",
            "DEV_ORG_ID": "org-1",
        }
        with patch.dict(os.environ, env_vars):
            response = client.post(
                "/api/plan/step",
                json={
                    "plan_id": "plan-123",
                    "text": "Blocked step",
                },
                headers={"X-Org-Id": "org-1"},
            )

            assert response.status_code == 403
            assert "planner" in response.json()["detail"].lower()

    def test_viewer_cannot_archive_plan(self, client):
        """Viewer role blocked from archiving plans."""
        env_vars = {
            "DEV_USER_ID": "u-viewer",
            "DEV_USER_ROLE": "viewer",
            "DEV_ORG_ID": "org-1",
        }
        with patch.dict(os.environ, env_vars):
            response = client.post(
                "/api/plan/plan-123/archive",
                headers={"X-Org-Id": "org-1"},
            )

            assert response.status_code == 403
            assert "planner" in response.json()["detail"].lower()


class TestPolicyEnforcement:
    """Test policy guardrails on dangerous operations."""

    def test_dangerous_command_blocked_rm_rf(self, client):
        """Policy blocks step with 'rm -rf' command."""
        # Mock plan lookup
        from backend.database.models.live_plan import LivePlan

        mock_plan = LivePlan(
            id="plan-123",
            org_id="org-1",
            title="Test Plan",
            steps=[],
            participants=[],
            archived=False,
        )

        def get_mock_db_for_policy():
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = (
                mock_plan
            )
            return mock_session

        app.dependency_overrides[get_db] = get_mock_db_for_policy

        env_vars = {
            "DEV_USER_ID": "u-planner",
            "DEV_USER_ROLE": "planner",
            "DEV_ORG_ID": "org-1",
        }
        with patch.dict(os.environ, env_vars):
            response = client.post(
                "/api/plan/step",
                json={
                    "plan_id": "plan-123",
                    "text": "Clean up with rm -rf /tmp/*",
                },
                headers={"X-Org-Id": "org-1"},
            )

            assert response.status_code == 403
            assert "policy violation" in response.json()["detail"].lower()

    def test_dangerous_command_blocked_drop_table(self, client):
        """Policy blocks step with SQL DROP TABLE."""
        from backend.database.models.live_plan import LivePlan

        mock_plan = LivePlan(
            id="plan-123",
            org_id="org-1",
            title="Test Plan",
            steps=[],
            participants=[],
            archived=False,
        )

        def get_mock_db_for_policy():
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = (
                mock_plan
            )
            return mock_session

        app.dependency_overrides[get_db] = get_mock_db_for_policy

        env_vars = {
            "DEV_USER_ID": "u-planner",
            "DEV_USER_ROLE": "planner",
            "DEV_ORG_ID": "org-1",
        }
        with patch.dict(os.environ, env_vars):
            response = client.post(
                "/api/plan/step",
                json={
                    "plan_id": "plan-123",
                    "text": "DROP TABLE users CASCADE",
                },
                headers={"X-Org-Id": "org-1"},
            )

            assert response.status_code == 403
            assert "policy violation" in response.json()["detail"].lower()

    def test_safe_command_allowed(self, client):
        """Policy allows safe commands."""
        from backend.database.models.live_plan import LivePlan

        mock_plan = LivePlan(
            id="plan-123",
            org_id="org-1",
            title="Test Plan",
            steps=[],
            participants=[],
            archived=False,
        )

        def get_mock_db_for_safe():
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = (
                mock_plan
            )
            mock_session.commit = MagicMock()
            return mock_session

        app.dependency_overrides[get_db] = get_mock_db_for_safe

        # Mock broadcaster
        from backend.api.deps import get_broadcaster

        mock_bc = AsyncMock()
        mock_bc.publish = AsyncMock()
        app.dependency_overrides[get_broadcaster] = lambda: mock_bc

        env_vars = {
            "DEV_USER_ID": "u-planner",
            "DEV_USER_ROLE": "planner",
            "DEV_ORG_ID": "org-1",
        }
        with patch.dict(os.environ, env_vars):
            response = client.post(
                "/api/plan/step",
                json={
                    "plan_id": "plan-123",
                    "text": "Run pytest tests/",
                },
                headers={"X-Org-Id": "org-1"},
            )

            assert response.status_code == 200
            assert response.json()["status"] == "step_added"


class TestAuthShims:
    """Test dev authentication shims."""

    def test_missing_dev_user_id_rejected(self, client):
        """Request rejected when DEV_USER_ID not set."""
        # Clear all DEV_* vars
        with patch.dict(os.environ, {}, clear=True):
            response = client.get(
                "/api/plan/list",
                headers={"X-Org-Id": "org-1"},
            )

            assert response.status_code == 401
            assert "DEV_USER_ID" in response.json()["detail"]

    def test_invalid_role_defaults_to_viewer(self, client):
        """Invalid role in DEV_USER_ROLE defaults to viewer."""
        env_vars = {
            "DEV_USER_ID": "u-test",
            "DEV_USER_ROLE": "invalid_role",
            "DEV_ORG_ID": "org-1",
        }
        with patch.dict(os.environ, env_vars):
            # Should succeed (viewer can list)
            response = client.get(
                "/api/plan/list",
                headers={"X-Org-Id": "org-1"},
            )
            assert response.status_code == 200

            # Should fail (viewer cannot start plan)
            response = client.post(
                "/api/plan/start",
                json={"title": "Test"},
                headers={"X-Org-Id": "org-1"},
            )
            assert response.status_code == 403
