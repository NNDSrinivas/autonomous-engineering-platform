"""
Test rate limiting for AI and feedback endpoints.

Ensures that expensive AI operations and feedback endpoints are properly
throttled according to PR-32a rate limiting configuration.
"""

import os
import time
from fastapi.testclient import TestClient
from backend.api.main import app

# Rate limiter configuration constants
# Token bucket refills at 1 token per second, so we need to wait slightly longer
# than 1 second to ensure tokens are replenished between test runs
TOKEN_REFILL_WAIT_SEC = 1.1  # Slightly longer than token refill interval

client = TestClient(app)


def setup_module(_):
    """Set up test environment with rate limiting enabled."""
    os.environ.setdefault("RATE_LIMIT_ENABLED", "true")
    os.environ.setdefault("ALLOW_DEV_AUTH", "true")
    os.environ.setdefault("DEV_USER_ID", "u-ae")
    os.environ.setdefault("DEV_ORG_ID", "org-ae")
    os.environ.setdefault("DEV_USER_ROLE", "planner")

    # Set low limits for testing
    os.environ.setdefault("RL_AI_GEN_PM", "2")
    os.environ.setdefault("RL_AI_GEN_BURST", "1")
    os.environ.setdefault("RL_FB_PM", "3")
    os.environ.setdefault("RL_FB_BURST", "1")


def test_ai_generate_rate_limited():
    """Test that AI generation endpoint is rate limited."""
    # First request should succeed (or fail with validation, but not rate limit)
    r1 = client.post("/api/ai/generate-diff", json={"intent": "test", "files": []})
    assert r1.status_code in (200, 422, 404)  # Not rate limited

    # Second request within same window should be rate limited (burst=1)
    r2 = client.post("/api/ai/generate-diff", json={"intent": "test", "files": []})
    assert r2.status_code == 429, f"Expected 429, got {r2.status_code}: {r2.text}"


def test_ai_apply_patch_rate_limited():
    """Test that AI apply patch endpoint is rate limited."""
    # First request should succeed (or fail with validation, but not rate limit)
    r1 = client.post("/api/ai/apply-patch", json={"patch": "test", "files": []})
    assert r1.status_code in (200, 422, 404)  # Not rate limited

    # Second request within same window should be rate limited (burst=1)
    r2 = client.post("/api/ai/apply-patch", json={"patch": "test", "files": []})
    assert r2.status_code == 429, f"Expected 429, got {r2.status_code}: {r2.text}"


def test_feedback_endpoints_rate_limited():
    """Test that feedback endpoints are rate limited."""
    # Test feedback submission - only include fields from FeedbackSubmission schema
    feedback_data = {
        "gen_id": 123,  # Integer as required by FeedbackSubmission schema
        "rating": 1,
        # Note: org_key and user_sub are extracted from current_user by the API
    }

    # First request should succeed
    r1 = client.post("/api/feedback/submit", json=feedback_data)
    assert r1.status_code in (200, 422, 404)  # Not rate limited

    # Second request within same window should be rate limited (burst=1)
    r2 = client.post("/api/feedback/submit", json=feedback_data)
    assert r2.status_code == 429, f"Expected 429, got {r2.status_code}: {r2.text}"


def test_feedback_stats_rate_limited():
    """Test that feedback stats endpoint is rate limited."""
    # First request should succeed
    r1 = client.get("/api/feedback/stats")
    assert r1.status_code in (200, 422, 404)  # Not rate limited

    # Multiple requests to test burst limit
    for i in range(3):
        r = client.get("/api/feedback/stats")
        # Should eventually hit rate limit
        if r.status_code == 429:
            break
    else:
        # If we didn't hit rate limit after multiple requests,
        # make one more to ensure we do
        r_final = client.get("/api/feedback/stats")
        assert (
            r_final.status_code == 429
        ), f"Expected eventual 429, got {r_final.status_code}"


def test_different_endpoints_separate_limits():
    """Test that different endpoint categories have separate rate limits."""
    # Reset any existing rate limit state by waiting for token refill
    time.sleep(TOKEN_REFILL_WAIT_SEC)

    # AI generate should be limited independently from feedback
    r1 = client.post("/api/ai/generate-diff", json={"intent": "test", "files": []})
    assert r1.status_code in (200, 422, 404)

    # Feedback should still work (separate limit)
    feedback_data = {
        "gen_id": 456,  # Integer as required by FeedbackSubmission schema
        "rating": 1,
        # Note: org_key and user_sub are extracted from current_user by the API
    }
    r2 = client.post("/api/feedback/submit", json=feedback_data)
    assert r2.status_code in (200, 422, 404)  # Should not be rate limited
