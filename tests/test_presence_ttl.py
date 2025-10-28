"""Unit tests for presence TTL and cursor endpoints."""

import os

from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def test_presence_join_and_heartbeat_monotonic():
    """Test presence join and heartbeat endpoints work correctly."""
    os.environ["DEV_USER_ROLE"] = "viewer"
    os.environ["DEV_USER_ID"] = "u1"
    os.environ["DEV_USER_EMAIL"] = "u1@example.com"
    os.environ["DEV_ORG_ID"] = "o1"

    resp = client.post(
        "/api/plan/pz1/presence/join",
        headers={"X-Org-Id": "o1"},
        json={
            "user_id": "u1",
            "email": "u1@example.com",
            "org_id": "o1",
            "display_name": "U1",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    hb = client.post(
        "/api/plan/pz1/presence/heartbeat",
        headers={"X-Org-Id": "o1"},
        json={"user_id": "u1", "org_id": "o1"},
    )
    assert hb.status_code == 200
    assert hb.json() == {"ok": True}


def test_cursor_post_ok():
    """Test cursor update endpoint works correctly."""
    os.environ["DEV_USER_ROLE"] = "viewer"
    os.environ["DEV_USER_ID"] = "u1"
    os.environ["DEV_USER_EMAIL"] = "u1@example.com"
    os.environ["DEV_ORG_ID"] = "o1"

    cur = client.post(
        "/api/plan/pz2/cursor",
        headers={"X-Org-Id": "o1"},
        json={
            "plan_id": "pz2",
            "user_id": "u1",
            "org_id": "o1",
            "x": 12.3,
            "y": 45.6,
            # ts is optional and will be auto-populated by server
        },
    )
    assert cur.status_code == 200
    assert cur.json() == {"ok": True}


def test_presence_join_user_impersonation_blocked():
    """Test that users cannot impersonate other users."""
    os.environ["DEV_USER_ROLE"] = "viewer"
    os.environ["DEV_USER_ID"] = "u1"
    os.environ["DEV_USER_EMAIL"] = "u1@example.com"
    os.environ["DEV_ORG_ID"] = "o1"

    # Try to join as a different user
    resp = client.post(
        "/api/plan/pz1/presence/join",
        headers={"X-Org-Id": "o1"},
        json={
            "user_id": "u2",  # Different user
            "email": "u2@example.com",
            "org_id": "o1",
            "display_name": "U2",
        },
    )
    assert resp.status_code == 403
    assert "different user" in resp.json()["detail"].lower()


def test_presence_join_org_mismatch_blocked():
    """Test that users cannot join with mismatched org ID."""
    os.environ["DEV_USER_ROLE"] = "viewer"
    os.environ["DEV_USER_ID"] = "u1"
    os.environ["DEV_USER_EMAIL"] = "u1@example.com"
    os.environ["DEV_ORG_ID"] = "o1"

    # Try to join with different org
    resp = client.post(
        "/api/plan/pz1/presence/join",
        headers={"X-Org-Id": "o1"},
        json={
            "user_id": "u1",
            "email": "u1@example.com",
            "org_id": "o2",  # Different org
            "display_name": "U1",
        },
    )
    assert resp.status_code == 403
    assert "organization" in resp.json()["detail"].lower()


def test_cursor_plan_id_mismatch_blocked():
    """Test that cursor endpoint validates plan_id consistency."""
    os.environ["DEV_USER_ROLE"] = "viewer"
    os.environ["DEV_USER_ID"] = "u1"
    os.environ["DEV_USER_EMAIL"] = "u1@example.com"
    os.environ["DEV_ORG_ID"] = "o1"

    # Try to send cursor with mismatched plan_id
    resp = client.post(
        "/api/plan/pz1/cursor",
        headers={"X-Org-Id": "o1"},
        json={
            "plan_id": "pz2",  # Different from path parameter
            "user_id": "u1",
            "org_id": "o1",
            "x": 12.3,
            "y": 45.6,
        },
    )
    assert resp.status_code == 400
    assert "plan id mismatch" in resp.json()["detail"].lower()
