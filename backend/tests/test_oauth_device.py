import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers.oauth_device import router as oauth_device_router
from backend.core.config import settings as core_config


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(oauth_device_router)
    return TestClient(app)


def test_device_flow_and_rotate_token(client, monkeypatch):
    monkeypatch.setattr(core_config, "oauth_device_use_in_memory_store", True)
    os.environ["OAUTH_DEVICE_USE_IN_MEMORY_STORE"] = "true"

    start = client.post("/oauth/device/start", json={})
    assert start.status_code == 200
    data = start.json()
    device_code = data["device_code"]
    user_code = data["user_code"]

    authorize = client.post(
        "/oauth/device/authorize",
        json={"user_code": user_code, "action": "approve", "user_id": "user1"},
    )
    assert authorize.status_code == 200

    poll = client.post("/oauth/device/poll", json={"device_code": device_code})
    assert poll.status_code == 200
    token = poll.json()["access_token"]

    rotate = client.post(
        "/oauth/device/rotate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rotate.status_code == 200
    new_token = rotate.json()["access_token"]
    assert new_token != token

    # Old token should be invalid after rotation
    rotate_old = client.post(
        "/oauth/device/rotate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rotate_old.status_code == 401
