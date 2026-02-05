from __future__ import annotations

import logging
from typing import Optional

from backend.core.config import get_settings

logger = logging.getLogger(__name__)


class SimpleCharTokenizer:
    """Fallback tokenizer for offline/test environments."""

    def encode(self, text: str) -> list[str]:
        return list(text)

    def decode(self, tokens: list[str]) -> str:
        return "".join(tokens)


def _should_allow_fallback() -> bool:
    settings = get_settings()
    if getattr(settings, "tokenizer_fallback_enabled", False):
        return True
    return settings.app_env in ("test", "ci")


def get_tokenizer(model_name: Optional[str] = None):
    """Return a tokenizer, falling back to a simple tokenizer in test/ci if needed."""
    try:
        import tiktoken  # type: ignore

        if model_name:
            try:
                return tiktoken.encoding_for_model(model_name)
            except Exception:
                pass
        return tiktoken.get_encoding("cl100k_base")
    except Exception as exc:
        if _should_allow_fallback():
            logger.warning(
                "Tokenizer fallback to SimpleCharTokenizer due to error: %s", exc
            )
            return SimpleCharTokenizer()
        raise
