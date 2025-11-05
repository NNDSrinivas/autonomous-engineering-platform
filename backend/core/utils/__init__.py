# Utils package

# Re-export functions from parent utils module to avoid circular imports
# These are core utilities needed by the API layer

import hashlib
import json
import string
from typing import Any, Dict, Optional

# Configuration constants
MAX_HEADER_LENGTH = 100  # Maximum allowed length for header values
ALLOWED_HEADER_CHARS = set(string.ascii_letters + string.digits + "_.-")
COST_SCALE = 6  # Number of decimal places for cost formatting


def format_cost_usd(cost_usd: float) -> str:
    """
    Format cost in USD with consistent decimal places across the platform.

    Args:
        cost_usd: Cost value in USD

    Returns:
        Formatted cost string with currency symbol (e.g., "$0.001234")
    """
    return f"${cost_usd:.{COST_SCALE}f}"


def generate_prompt_hash(prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
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


def _is_valid_header_char(char: str) -> bool:
    """Check if a character is valid for HTTP headers."""
    return char in ALLOWED_HEADER_CHARS


def validate_header_value(
    value: str, field_name: str = "header", max_length: int = MAX_HEADER_LENGTH
) -> str:
    """
    Validate and sanitize header values for HTTP responses.
    
    Args:
        value: The header value to validate
        field_name: Name of the field being validated (for error messages)
        max_length: Maximum allowed length
        
    Returns:
        Validated header value
        
    Raises:
        ValueError: If validation fails
    """
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    
    if len(value) > max_length:
        raise ValueError(f"{field_name} exceeds maximum length of {max_length}")
    
    # Check for invalid characters
    for char in value:
        if not _is_valid_header_char(char):
            raise ValueError(f"{field_name} contains invalid character: '{char}'")
    
    return value


__all__ = ["generate_prompt_hash", "validate_header_value", "format_cost_usd"]
