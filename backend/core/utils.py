"""Core utilities for the autonomous engineering platform."""

import hashlib
import json
import re
from typing import Any, Dict, Optional

# Configuration constants
MAX_HEADER_LENGTH = 100  # Maximum allowed length for header values

# Header value validation pattern using re.VERBOSE for maintainability
HEADER_VALUE_PATTERN = re.compile(
    r"""
    ^                   # Start of string
    (?!.*\.\.)         # Negative lookahead: no consecutive dots anywhere
    [a-zA-Z0-9_]       # First character: alphanumeric or underscore only
    [a-zA-Z0-9_.-]*    # Remaining characters: alphanumeric, underscore, dot, or hyphen
    $                   # End of string
    """,
    re.VERBOSE,
)


def generate_prompt_hash(prompt: str, context: Dict[str, Any] = None) -> str:
    """
    Generate a consistent hash for a prompt and context combination.

    Args:
        prompt: The prompt text
        context: Optional context dictionary

    Returns:
        SHA256 hash as hexadecimal string
    """
    if context is None:
        context = {}

    # Use json.dumps with sort_keys=True for consistent serialization
    context_str = json.dumps(context, sort_keys=True, separators=(",", ":"))
    combined_input = prompt + context_str

    return hashlib.sha256(combined_input.encode("utf-8")).hexdigest()


def validate_header_value(
    value: Optional[str], max_length: int = MAX_HEADER_LENGTH
) -> Optional[str]:
    """
    Validate and sanitize header values for audit logging.

    Args:
        value: The header value to validate
        max_length: Maximum allowed length for the header value

    Returns:
        Sanitized header value or None if invalid/empty
    """
    if not value or not isinstance(value, str):
        return None

    # Remove any leading/trailing whitespace
    value = value.strip()

    # Check length limits
    if len(value) > max_length:
        return None

    # Only allow alphanumeric characters, hyphens, underscores, and dots
    # This prevents injection attacks while allowing common ID formats
    # Disallow leading dot and consecutive dots to prevent path traversal
    if not HEADER_VALUE_PATTERN.match(value):
        return None

    return value
