from __future__ import annotations

from pathlib import Path

from backend.services.model_router import ModelRouter


_REQUIRED_ROUTER_FIELDS = {
    "requestedModelId",
    "effectiveModelId",
    "wasFallback",
    "fallbackReason",
    "provider",
    "model",
    "requestedModeId",
}


def test_router_info_fields_are_consistent_across_endpoints(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    router = ModelRouter()

    for endpoint in ("stream", "stream_v2", "autonomous"):
        decision = router.route("openai/gpt-4o", endpoint=endpoint)
        payload = decision.to_public_dict()
        missing = _REQUIRED_ROUTER_FIELDS - set(payload.keys())
        assert not missing, f"missing fields for endpoint {endpoint}: {missing}"


def test_all_navi_endpoints_call_model_router() -> None:
    source_path = Path("backend/api/navi.py")
    source = source_path.read_text(encoding="utf-8")

    assert 'endpoint="stream"' in source
    assert 'endpoint="stream_v2"' in source
    assert 'endpoint="autonomous"' in source

    # All streaming endpoints should emit router_info based on routing_decision metadata.
    assert "_build_router_info(routing_decision" in source
