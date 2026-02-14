from __future__ import annotations

import json
from pathlib import Path

import importlib.util


def test_shared_model_registry_is_valid() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    registry_path = repo_root / "shared" / "model-registry.json"
    assert registry_path.exists(), f"missing registry file: {registry_path}"

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    validator_path = repo_root / "scripts" / "validate_model_registry.py"
    spec = importlib.util.spec_from_file_location(
        "model_registry_validator", validator_path
    )
    assert spec and spec.loader, f"failed to load validator: {validator_path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_registry(registry)
