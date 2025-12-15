# LLM providers package

from dataclasses import dataclass


@dataclass
class ChatMessage:
    role: str
    content: str


def get_llm_client():
    """Stub for LLM client"""
    from .router import ModelRouter

    return ModelRouter()


__all__ = ["ChatMessage", "get_llm_client"]
