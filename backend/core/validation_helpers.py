"""
Validation helper functions for centralized validation logic.
"""

from typing import Any, Optional


def validate_telemetry_value(value: Any, expected_type: type, default: Any = 0) -> Any:
    """
    Validate and sanitize telemetry values with consistent error handling.

    Args:
        value: The value to validate
        expected_type: Expected type for validation
        default: Default value to return if validation fails

    Returns:
        Validated value or safe default

    Raises:
        ValueError: If validation fails and no default provided
    """
    if value is None:
        return default

    # Try type conversion if not already the expected type
    if not isinstance(value, expected_type):
        try:
            # Attempt type conversion
            if expected_type is int:
                value = int(value)
            elif expected_type is float:
                value = float(value)
            elif expected_type is str:
                value = str(value)
            else:
                # For other types, return default
                return default
        except (ValueError, TypeError):
            return default

    # Additional validation for specific types
    if expected_type in (int, float) and value < 0:
        return default

    if expected_type is str and not value.strip():
        return str(default) if isinstance(default, (int, float)) else default

    return value


def validate_string_bounds(
    text: Optional[str], min_length: int = 0, max_length: Optional[int] = None
) -> str:
    """
    Validate string length with proper bounds checking.

    Args:
        text: String to validate
        min_length: Minimum required length
        max_length: Maximum allowed length (None for no limit)

    Returns:
        Validated string

    Raises:
        ValueError: If validation fails
    """
    if not text:
        if min_length > 0:
            raise ValueError(f"String must be at least {min_length} characters")
        return ""

    if len(text) < min_length:
        raise ValueError(f"String must be at least {min_length} characters, got {len(text)}")

    if max_length is not None and len(text) > max_length:
        raise ValueError(f"String must be at most {max_length} characters, got {len(text)}")

    return text
