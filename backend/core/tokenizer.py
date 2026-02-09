from __future__ import annotations

import logging
from typing import Optional

from backend.core.config import get_settings

logger = logging.getLogger(__name__)


class SimpleCharTokenizer:
    """Fallback tokenizer for offline/test environments.

    Returns list[int] to match tiktoken interface (using character ordinals as token IDs).
    """

    def encode(self, text: str) -> list[int]:
        """Encode text into a list of integer token IDs (character ordinals)."""
        return [ord(c) for c in text]

    def decode(self, tokens: list[int]) -> str:
        """Decode a list of integer token IDs back into text."""
        return "".join(chr(t) for t in tokens)


def _should_allow_fallback() -> bool:
    settings = get_settings()
    if getattr(settings, "tokenizer_fallback_enabled", False):
        return True
    # Defensive check: settings might not have is_test() method depending on config source
    is_test_fn = getattr(settings, "is_test", None)
    if callable(is_test_fn):
        return is_test_fn()
    return False


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
