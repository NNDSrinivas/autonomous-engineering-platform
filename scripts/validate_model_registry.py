#!/usr/bin/env python3
"""Validate shared/model-registry.json integrity."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "shared" / "model-registry.json"
ALLOWED_PROVIDER_TYPES = {"saas", "local", "self_hosted"}
VENDOR_ID_RE = re.compile(r"^[a-z0-9_\-]+\/[A-Za-z0-9._\-]+$")
MODE_ID_RE = re.compile(r"^navi\/[a-z0-9_\-]+$")


class ValidationError(Exception):
    pass


def _fail(message: str) -> None:
    raise ValidationError(message)


def _load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        _fail(f"registry file not found: {REGISTRY_PATH}")
    with REGISTRY_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def validate_registry(registry: dict[str, Any]) -> None:
    providers = registry.get("providers")
    modes = registry.get("naviModes")
    defaults = registry.get("defaults")

    if not isinstance(providers, list) or not providers:
        _fail("providers must be a non-empty list")
    if not isinstance(modes, list) or not modes:
        _fail("naviModes must be a non-empty list")
    if not isinstance(defaults, dict):
        _fail("defaults must be an object")

    provider_ids: set[str] = set()
    model_ids: set[str] = set()

    for provider in providers:
        provider_id = provider.get("id")
        provider_type = provider.get("type")
        models = provider.get("models")

        if not isinstance(provider_id, str) or not provider_id:
            _fail(f"provider id missing/invalid: {provider}")
        if provider_id in provider_ids:
            _fail(f"duplicate provider id: {provider_id}")
        provider_ids.add(provider_id)

        if provider_type not in ALLOWED_PROVIDER_TYPES:
            _fail(
                f"provider '{provider_id}' has invalid type '{provider_type}'. "
                f"allowed={sorted(ALLOWED_PROVIDER_TYPES)}"
            )

        if not isinstance(models, list) or not models:
            _fail(f"provider '{provider_id}' models must be non-empty list")

        for model in models:
            model_id = model.get("id")
            if not isinstance(model_id, str) or not model_id:
                _fail(f"provider '{provider_id}' has model with missing id: {model}")
            if model_id in model_ids:
                _fail(f"duplicate model id: {model_id}")
            if not VENDOR_ID_RE.match(model_id):
                _fail(f"model id must be provider/model format; got '{model_id}'")
            model_ids.add(model_id)

    mode_ids: set[str] = set()
    for mode in modes:
        mode_id = mode.get("id")
        candidates = mode.get("candidateModelIds")

        if not isinstance(mode_id, str) or not MODE_ID_RE.match(mode_id):
            _fail(f"mode id must be navi/<mode>, got: {mode_id!r}")
        if mode_id in mode_ids:
            _fail(f"duplicate mode id: {mode_id}")
        mode_ids.add(mode_id)

        if not isinstance(candidates, list) or not candidates:
            _fail(f"mode '{mode_id}' must include non-empty candidateModelIds")

        for candidate in candidates:
            if candidate not in model_ids:
                _fail(
                    f"mode '{mode_id}' candidate model does not exist in providers: {candidate}"
                )

    default_mode_id = defaults.get("defaultModeId")
    default_model_id = defaults.get("defaultModelId")

    if default_mode_id not in mode_ids:
        _fail(f"defaults.defaultModeId '{default_mode_id}' is not a valid navi mode")
    if default_model_id not in model_ids:
        _fail(f"defaults.defaultModelId '{default_model_id}' is not a known model id")


def main() -> int:
    try:
        registry = _load_registry()
        validate_registry(registry)
    except ValidationError as exc:
        print(f"[model-registry] INVALID: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"[model-registry] INVALID JSON: {exc}", file=sys.stderr)
        return 1

    print(f"[model-registry] OK: {REGISTRY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
