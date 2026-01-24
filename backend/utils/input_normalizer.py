"""
Input Normalizer - Safe request parsing and validation for NAVI

Handles different input formats gracefully to prevent failures when
requests come in different structures or types.

Usage:
    from backend.utils.input_normalizer import (
        normalize_message,
        safe_get,
        safe_get_nested,
        extract_text_content,
    )

    # Extract message from any format
    message = normalize_message(request_data)

    # Safe nested dict access
    content = safe_get_nested(response, ["choices", 0, "message", "content"], "")
"""

import logging
from typing import Any, Dict, List, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar("T")


def safe_get(obj: Any, key: Any, default: T = None) -> Union[Any, T]:
    """
    Safely get a value from a dict-like object or list.

    Args:
        obj: Dictionary, list, or object with attributes
        key: Key (str), index (int), or attribute name
        default: Default value if key not found

    Returns:
        Value at key or default
    """
    if obj is None:
        return default

    try:
        # Handle dict-like objects
        if isinstance(obj, dict):
            return obj.get(key, default)

        # Handle list/tuple with integer index
        if isinstance(key, int) and isinstance(obj, (list, tuple)):
            if 0 <= key < len(obj):
                return obj[key]
            return default

        # Handle objects with attributes
        if hasattr(obj, key):
            return getattr(obj, key, default)

        # Handle Pydantic models
        if hasattr(obj, "__dict__"):
            return obj.__dict__.get(key, default)

        return default
    except Exception:
        return default


def safe_get_nested(
    obj: Any,
    keys: List[Any],
    default: T = None,
) -> Union[Any, T]:
    """
    Safely traverse nested dict/list structure.

    Args:
        obj: Root object to traverse
        keys: List of keys/indices to traverse
        default: Default value if any key not found

    Returns:
        Value at nested path or default

    Example:
        # Instead of: data["choices"][0]["message"]["content"]
        safe_get_nested(data, ["choices", 0, "message", "content"], "")
    """
    current = obj
    for key in keys:
        current = safe_get(current, key)
        if current is None:
            return default
    return current if current is not None else default


def normalize_message(
    data: Any,
    field_priority: List[str] = None,
) -> str:
    """
    Extract message content from various request formats.

    Supports multiple field names commonly used across APIs:
    - message, text, content, prompt, input, query, question

    Args:
        data: Request data (dict, object, or string)
        field_priority: Custom field name priority list

    Returns:
        Extracted message as string, empty string if not found
    """
    if data is None:
        return ""

    # If it's already a string, return it
    if isinstance(data, str):
        return data.strip()

    # Default field priority - common field names across APIs
    if field_priority is None:
        field_priority = [
            "message",
            "text",
            "content",
            "prompt",
            "input",
            "query",
            "question",
            "user_message",
            "user_input",
        ]

    # Try each field name
    for field in field_priority:
        value = safe_get(data, field)
        if value is not None:
            if isinstance(value, str):
                return value.strip()
            # Handle nested content (e.g., {"content": {"text": "..."}})
            if isinstance(value, dict):
                nested = normalize_message(value, field_priority)
                if nested:
                    return nested
            # Handle list content (e.g., {"content": ["text1", "text2"]})
            if isinstance(value, list) and value:
                if isinstance(value[0], str):
                    return " ".join(str(v) for v in value if v)
                # Handle Anthropic-style content blocks
                if isinstance(value[0], dict):
                    texts = [
                        safe_get(block, "text", "")
                        for block in value
                        if safe_get(block, "type") == "text"
                    ]
                    return "".join(texts)

    return ""


def normalize_role(role: Any) -> str:
    """
    Normalize role to valid LLM API role.

    Args:
        role: Role value (string, None, or other)

    Returns:
        Normalized role: "user", "assistant", or "system"
    """
    if role is None:
        return "user"

    role_str = str(role).lower().strip()

    # Map common variations
    role_map = {
        "user": "user",
        "human": "user",
        "customer": "user",
        "client": "user",
        "assistant": "assistant",
        "bot": "assistant",
        "ai": "assistant",
        "navi": "assistant",
        "agent": "assistant",
        "system": "system",
        "sys": "system",
        "instruction": "system",
    }

    return role_map.get(role_str, "user")


def extract_text_content(response: Any, provider: str = "auto") -> str:
    """
    Extract text content from LLM API response.

    Supports multiple provider formats with graceful fallbacks.

    Args:
        response: API response object
        provider: Provider hint ("openai", "anthropic", "google", "ollama", "auto")

    Returns:
        Extracted text content or empty string
    """
    if response is None:
        return ""

    if isinstance(response, str):
        return response

    # Try provider-specific extraction first
    extractors = {
        "openai": _extract_openai_content,
        "xai": _extract_openai_content,
        "mistral": _extract_openai_content,
        "groq": _extract_openai_content,
        "openrouter": _extract_openai_content,
        "anthropic": _extract_anthropic_content,
        "google": _extract_google_content,
        "ollama": _extract_ollama_content,
    }

    if provider != "auto" and provider in extractors:
        result = extractors[provider](response)
        if result:
            return result

    # Auto-detect: try all extractors
    for name, extractor in extractors.items():
        try:
            result = extractor(response)
            if result:
                logger.debug(f"Extracted content using {name} extractor")
                return result
        except Exception:
            continue

    # Last resort: try to stringify
    logger.warning("Could not extract text content, using str() fallback")
    return str(response) if response else ""


def _extract_openai_content(data: Any) -> str:
    """Extract content from OpenAI-style response."""
    # Standard format: {"choices": [{"message": {"content": "..."}}]}
    content = safe_get_nested(data, ["choices", 0, "message", "content"])
    if content:
        return str(content)

    # Alternative: delta format for streaming
    content = safe_get_nested(data, ["choices", 0, "delta", "content"])
    if content:
        return str(content)

    # Direct content field
    content = safe_get(data, "content")
    if isinstance(content, str):
        return content

    return ""


def _extract_anthropic_content(data: Any) -> str:
    """Extract content from Anthropic-style response."""
    content = safe_get(data, "content", [])

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict):
                if safe_get(block, "type") == "text":
                    text = safe_get(block, "text", "")
                    if text:
                        texts.append(text)
            elif isinstance(block, str):
                texts.append(block)
        return "".join(texts)

    return ""


def _extract_google_content(data: Any) -> str:
    """Extract content from Google-style response."""
    # Format: {"candidates": [{"content": {"parts": [{"text": "..."}]}}]}
    parts = safe_get_nested(data, ["candidates", 0, "content", "parts"])
    if isinstance(parts, list) and parts:
        first_part = parts[0]
        if isinstance(first_part, dict):
            return safe_get(first_part, "text", "")
        if isinstance(first_part, str):
            return first_part

    return ""


def _extract_ollama_content(data: Any) -> str:
    """Extract content from Ollama-style response."""
    # Format: {"message": {"content": "..."}}
    content = safe_get_nested(data, ["message", "content"])
    if content:
        return str(content)

    # Alternative: direct response field
    content = safe_get(data, "response")
    if content:
        return str(content)

    return ""


def normalize_history(
    history: Any,
    max_messages: int = 50,
) -> List[Dict[str, str]]:
    """
    Normalize conversation history to standard format.

    Args:
        history: Conversation history in various formats
        max_messages: Maximum messages to keep

    Returns:
        List of {"role": "...", "content": "..."} dicts
    """
    if history is None:
        return []

    if not isinstance(history, (list, tuple)):
        logger.warning(f"Expected list for history, got {type(history)}")
        return []

    normalized = []

    for item in history:
        if isinstance(item, dict):
            role = normalize_role(safe_get(item, "role") or safe_get(item, "type"))
            content = normalize_message(item)
            if content:
                normalized.append({"role": role, "content": content})
        elif isinstance(item, str):
            normalized.append({"role": "user", "content": item})
        elif hasattr(item, "__dict__"):
            # Handle Pydantic models or dataclasses
            role = normalize_role(
                getattr(item, "role", None) or getattr(item, "type", None)
            )
            content = normalize_message(item.__dict__)
            if content:
                normalized.append({"role": role, "content": content})

    # Limit to max messages
    if len(normalized) > max_messages:
        normalized = normalized[-max_messages:]

    return normalized


def safe_lower(value: Any) -> str:
    """
    Safely convert value to lowercase string.

    Args:
        value: Any value to convert

    Returns:
        Lowercase string
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value.lower().strip()
    return str(value).lower().strip()


def validate_request_fields(
    data: Dict[str, Any],
    required_fields: List[str],
    optional_fields: List[str] = None,
) -> Dict[str, Any]:
    """
    Validate and extract fields from request data.

    Args:
        data: Request data dict
        required_fields: Fields that must be present
        optional_fields: Fields that are optional

    Returns:
        Dict with extracted fields

    Raises:
        ValueError: If required field is missing
    """
    result = {}

    for field in required_fields:
        value = safe_get(data, field)
        if value is None:
            # Try common alternatives
            alternatives = {
                "message": ["text", "content", "prompt", "input"],
                "workspace_root": ["workspace", "cwd", "path", "root"],
                "file_path": ["path", "file", "filePath"],
            }
            for alt in alternatives.get(field, []):
                value = safe_get(data, alt)
                if value is not None:
                    break

        if value is None:
            raise ValueError(f"Required field '{field}' not found in request")

        result[field] = value

    if optional_fields:
        for field in optional_fields:
            value = safe_get(data, field)
            if value is not None:
                result[field] = value

    return result
