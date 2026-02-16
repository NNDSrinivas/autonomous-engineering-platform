from typing import Any, Dict, List

import pytest

from backend.services.streaming_agent import StreamEventType, stream_with_tools_openai


@pytest.mark.asyncio
async def test_stream_with_tools_maps_self_hosted_to_openai_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: Dict[str, Any] = {}

    class FakeLLMClient:
        def __init__(
            self,
            *,
            provider: str,
            model: str,
            api_key: str,
            api_base: str,
        ) -> None:
            captured["provider"] = provider
            captured["model"] = model
            captured["api_key"] = api_key
            captured["api_base"] = api_base

        async def stream(self, _messages: List[Any]):
            yield "ok"

    monkeypatch.setattr("backend.services.llm_client.LLMClient", FakeLLMClient)

    events = []
    async for event in stream_with_tools_openai(
        message="hello",
        workspace_path="/tmp",
        api_key="test-key",
        model="qwen2.5-coder",
        base_url="http://localhost:8000/v1",
        provider="self_hosted",
    ):
        events.append(event)

    assert captured["provider"] == "openai"
    assert captured["model"] == "qwen2.5-coder"
    assert captured["api_base"] == "http://localhost:8000/v1"
    assert events[0].type == StreamEventType.TEXT
    assert events[-1].type == StreamEventType.DONE
