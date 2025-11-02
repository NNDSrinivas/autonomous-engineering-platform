"""
Security utilities for the autonomous engineering platform.
Provides functions for sanitization, validation, and security-related operations.
"""

import re


def sanitize_for_logging(value: str) -> str:
    """
    Comprehensive sanitization to prevent log injection attacks.
    Removes or escapes control characters and potential injection patterns.
    
    Args:
        value: The string value to sanitize for safe logging
        
    Returns:
        str: Sanitized string safe for logging without injection risks
    """
    if not isinstance(value, str):
        value = str(value)

    # Remove or replace all line-breaking characters (CR, LF, Unicode line/paragraph separators)
    # to prevent CRLF injection attacks that could break log file structure
    value = re.sub(r"[\r\n\u2028\u2029]+", r" ", value)

    # Replace control characters with safe representations
    # Only escape C0 and DEL characters, preserve printable Unicode
    value = re.sub(r"[\x00-\x1f\x7f]", lambda m: f"\\x{ord(m.group(0)):02x}", value)

    # Limit length to prevent log flooding
    if len(value) > 200:
        value = value[:197] + "..."

    return value