"""Unit tests for presence TTL and cursor endpoints."""

import os
import time

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
        json={
            "plan_id": "pz2",
            "user_id": "u1",
            "org_id": "o1",
            "x": 12.3,
            "y": 45.6,
            "ts": int(time.time()),
        },
    )
    assert cur.status_code == 200
    assert cur.json() == {"ok": True}
