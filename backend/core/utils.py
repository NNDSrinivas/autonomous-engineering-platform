"""Core utilities for the autonomous engineering platform."""

import hashlib
import json
import string
from typing import Any, Dict, Optional
from .models import COST_SCALE

# Configuration constants
MAX_HEADER_LENGTH = 100  # Maximum allowed length for header values

# Simple character set for header validation - more maintainable than complex regex
ALLOWED_HEADER_CHARS = set(string.ascii_letters + string.digits + "_.-")


def format_cost_usd(cost_usd: float) -> str:
    """
    Format cost in USD with consistent decimal places across the platform.

    Args:
        cost_usd: Cost value in USD

    Returns:
        Formatted cost string with currency symbol (e.g., "$0.001234")
    """
    return f"${cost_usd:.{COST_SCALE}f}"


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


def _is_valid_start_end_char(char: str) -> bool:
    """Check if character is valid for start/end of header value (alphanumeric or underscore)."""
    return char.isalnum() or char == "_"


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

    # Check if empty after stripping or exceeds length limits
    if not value or len(value) > max_length:
        return None

    # Simple validation using string methods for better maintainability
    # 1. Must start with valid character (alphanumeric or underscore)
    if not _is_valid_start_end_char(value[0]):
        return None

    # 2. Must end with valid character (alphanumeric or underscore)
    if not _is_valid_start_end_char(value[-1]):
        return None

    # 3. Only allow specific characters
    if not all(c in ALLOWED_HEADER_CHARS for c in value):
        return None

    # 4. Disallow consecutive dots to prevent path traversal
    if ".." in value:
        return None

    return value
