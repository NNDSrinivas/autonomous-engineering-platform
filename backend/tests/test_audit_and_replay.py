"""
Tests for audit logging and event replay functionality
"""

import os
import pytest
from contextlib import closing
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.api.main import app
from backend.core.db import get_db
from backend.core.eventstore.service import append_event, replay, get_plan_event_count

client = TestClient(app)

# Enable dev auth for testing
os.environ["ALLOW_DEV_AUTH"] = "true"


@pytest.fixture
def test_db():
    """Get test database session"""
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()


def test_append_and_replay_plan_events(test_db: Session):
    """Test appending events and replaying them in order"""
    plan_id = "test-plan-replay"

    # Clear any existing test data
    test_db.execute(
        text("DELETE FROM plan_events WHERE plan_id = :plan_id"), {"plan_id": plan_id}
    )
    test_db.commit()

    # Append multiple events
    evt1 = append_event(
        test_db,
        plan_id=plan_id,
        type="note",
        payload={"text": "First event"},
        user_sub="user-123",
        org_key="org-test",
    )

    evt2 = append_event(
        test_db,
        plan_id=plan_id,
        type="step",
        payload={"text": "Second event"},
        user_sub="user-123",
        org_key="org-test",
    )

    test_db.commit()

    # Verify sequence numbers
    assert evt1.seq == 1
    assert evt2.seq == 2

    # Replay all events
    events = replay(test_db, plan_id=plan_id)
    assert len(events) == 2
    assert events[0].seq == 1
    assert events[1].seq == 2
    assert events[0].payload == {"text": "First event"}
    assert events[1].payload == {"text": "Second event"}

    # Replay since sequence 1
    events_since = replay(test_db, plan_id=plan_id, since_seq=1)
    assert len(events_since) == 1
    assert events_since[0].seq == 2

    # Test event count
    count = get_plan_event_count(test_db, plan_id)
    assert count == 2


def test_replay_api_endpoint():
    """Test the replay API endpoint"""
    # Set up auth
    os.environ["DEV_USER_ROLE"] = "viewer"
    os.environ["DEV_USER_ID"] = "u-tester"
    os.environ["DEV_ORG_ID"] = "org-demo"

    plan_id = "test-plan-api"

    # First add some events via the database (simulating plan activity)
    with closing(next(get_db())) as db:
        append_event(
            db,
            plan_id=plan_id,
            type="note",
            payload={"text": "API test event 1"},
            user_sub="u-tester",
            org_key="org-demo",
        )
        append_event(
            db,
            plan_id=plan_id,
            type="step",
            payload={"text": "API test event 2"},
            user_sub="u-tester",
            org_key="org-demo",
        )
        db.commit()

    # Test replay all events
    response = client.get(f"/api/plan/{plan_id}/replay")
    assert response.status_code == 200
    events = response.json()
    assert len(events) >= 2
    assert events[0]["seq"] == 1
    assert events[0]["type"] == "note"
    assert events[1]["seq"] == 2
    assert events[1]["type"] == "step"

    # Test replay with since parameter
    response = client.get(f"/api/plan/{plan_id}/replay?since=1")
    assert response.status_code == 200
    events = response.json()
    assert all(event["seq"] > 1 for event in events)

    # Test event count endpoint
    response = client.get(f"/api/plan/{plan_id}/events/count")
    assert response.status_code == 200
    count_data = response.json()
    assert count_data["plan_id"] == plan_id
    assert count_data["event_count"] >= 2


def test_audit_endpoint_permissions():
    """Test audit endpoint requires admin permissions"""
    # Test with viewer role (should fail)
    os.environ["DEV_USER_ROLE"] = "viewer"
    response = client.get("/api/audit")
    assert response.status_code == 403

    # Test with planner role (should fail)
    os.environ["DEV_USER_ROLE"] = "planner"
    response = client.get("/api/audit")
    assert response.status_code == 403

    # Test with admin role (should succeed)
    os.environ["DEV_USER_ROLE"] = "admin"
    response = client.get("/api/audit?limit=5")
    assert response.status_code == 200
    audit_logs = response.json()
    assert isinstance(audit_logs, list)


def test_audit_middleware_captures_requests():
    """Test that the audit middleware captures mutating requests"""
    os.environ["DEV_USER_ROLE"] = "admin"
    os.environ["DEV_USER_ID"] = "u-admin"
    os.environ["DEV_ORG_ID"] = "org-test"

    # Make a POST request (should be audited)
    test_data = {"test": "data"}
    client.post("/api/plan/test-plan-audit/events", json=test_data)

    # The response might fail (endpoint might not exist), but audit should capture it

    # Check if audit log was created
    response = client.get("/api/audit?limit=10")
    assert response.status_code == 200
    audit_logs = response.json()

    # Look for our request in the audit logs
    matching_logs = [
        log
        for log in audit_logs
        if log["route"] == "/api/plan/test-plan-audit/events"
        and log["method"] == "POST"
    ]

    # We should find at least one matching audit log
    assert len(matching_logs) > 0
    log = matching_logs[0]
    assert log["actor_sub"] == "u-admin"
    assert log["org_key"] == "org-test"
    assert log["event_type"] == "http.request"


def test_event_sequence_monotonic():
    """Test that event sequences are monotonic per plan"""
    plan_id = "test-monotonic"

    with closing(next(get_db())) as db:
        # Add events in multiple transactions
        evt1 = append_event(
            db, plan_id=plan_id, type="event", payload={}, user_sub=None, org_key=None
        )
        db.commit()

        evt2 = append_event(
            db, plan_id=plan_id, type="event", payload={}, user_sub=None, org_key=None
        )
        db.commit()

        evt3 = append_event(
            db, plan_id=plan_id, type="event", payload={}, user_sub=None, org_key=None
        )
        db.commit()

        assert evt1.seq == 1
        assert evt2.seq == 2
        assert evt3.seq == 3

        # Events for different plans should have independent sequences
        other_plan_evt = append_event(
            db,
            plan_id="other-plan",
            type="event",
            payload={},
            user_sub=None,
            org_key=None,
        )
        assert other_plan_evt.seq == 1  # Starts at 1 for new plan


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
