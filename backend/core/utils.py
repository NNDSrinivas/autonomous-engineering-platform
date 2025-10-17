"""Core utilities for the autonomous engineering platform."""

import hashlib
import json
import re
from typing import Any, Dict, Optional

# Configuration constants
MAX_HEADER_LENGTH = 100  # Maximum allowed length for header values

# Allowed header value pattern (single-line compact form):
# - ^                         : start of string
# - (?!.*\.\.)              : negative lookahead to disallow consecutive dots
# - [a-zA-Z0-9_]              : first character must be alphanumeric or underscore
# - [a-zA-Z0-9_.-]*           : remaining characters may include dot, underscore, or hyphen
# - $                         : end of string
#
# Keep the compact pattern for runtime matching, but for readability and
# maintainability consider using a verbose multi-line pattern with
# re.VERBOSE in code that constructs or documents the regex.
HEADER_VALUE_PATTERN = r"^(?!.*\.\.)[a-zA-Z0-9_][a-zA-Z0-9_.-]*$"

# Example (commented) verbose pattern for maintainers:
#
# HEADER_VALUE_PATTERN_VERBOSE = r"""
# ^               # start
# (?!.*\.{2})    # no consecutive dots
# [A-Za-z0-9_]     # first char alnum or underscore
# [A-Za-z0-9_.-]*  # rest: alnum, underscore, dot, hyphen
# $               # end
# """
#
# Use with: re.compile(HEADER_VALUE_PATTERN_VERBOSE, re.VERBOSE)


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
    if not re.match(HEADER_VALUE_PATTERN, value):
        return None

    return value
