from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_apply_endpoint_creates_file(client, tmp_path: Path):
    resp = client.post(
        "/api/navi/apply",
        json={
            "workspace": str(tmp_path),
            "file_edits": [
                {"filePath": "applied.txt", "content": "hello", "operation": "create"}
            ],
            "commands_run": [],
            "allow_commands": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert (tmp_path / "applied.txt").read_text() == "hello"
