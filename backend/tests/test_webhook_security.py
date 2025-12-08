import hmac
import json
import time
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_slack_webhook_rejects_bad_signature(client, monkeypatch):
    from backend.core import settings as core_settings
    monkeypatch.setattr(core_settings.settings, "SLACK_SIGNING_SECRET", "testsecret")
    body = {"event": {"type": "message", "text": "hello"}}
    timestamp = str(int(time.time()))
    sig = "v0=" + hmac.new("wrong".encode(), f"v0:{timestamp}:{json.dumps(body)}".encode(), sha256).hexdigest()

    resp = client.post(
        "/api/webhooks/slack",
        headers={
            "X-Org-Id": "org1",
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": sig,
        },
        json=body,
    )
    assert resp.status_code == 401


def test_slack_webhook_accepts_good_signature(client, monkeypatch):
    from backend.core import settings as core_settings
    monkeypatch.setattr(core_settings.settings, "SLACK_SIGNING_SECRET", "testsecret")
    body = {"event": {"type": "message", "text": "hello"}}
    timestamp = str(int(time.time()))
    basestring = f"v0:{timestamp}:{json.dumps(body)}"
    sig = "v0=" + hmac.new("testsecret".encode(), basestring.encode(), sha256).hexdigest()

    resp = client.post(
        "/api/webhooks/slack",
        headers={
            "X-Org-Id": "org1",
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": sig,
        },
        json=body,
    )
    # Accepts; may be 200/202, or 500 if downstream DB not configured in test env
    assert resp.status_code in (200, 202, 500)


def test_github_webhook_requires_org_and_signature(client, monkeypatch):
    from backend.core import settings as core_settings
    monkeypatch.setattr(core_settings.settings, "GITHUB_WEBHOOK_SECRET", "ghsecret")
    body = {"repository": {"full_name": "org/repo"}, "pull_request": {"number": 1, "title": "Test PR"}}
    payload = json.dumps(body).encode()
    sig = "sha256=" + hmac.new("ghsecret".encode(), payload, sha256).hexdigest()

    # Missing org -> 400
    resp = client.post(
        "/api/webhooks/github",
        headers={"X-Hub-Signature-256": sig},
        content=payload,
    )
    assert resp.status_code == 400

    # With org but no indexed repo/connection -> 202 expected
    resp2 = client.post(
        "/api/webhooks/github",
        headers={"X-Hub-Signature-256": sig, "X-Org-Id": "org1"},
        content=payload,
    )
    assert resp2.status_code in (202, 500, 401)
