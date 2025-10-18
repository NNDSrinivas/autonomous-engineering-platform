"""
Validation helper functions for centralized validation logic.
"""

from typing import Any, Optional, Union


def validate_telemetry_value(
    value: Any, field_name: str, expected_type: type, default: Union[str, int, float] = 0
) -> Union[str, int, float]:
    """
    Validate and sanitize telemetry values with consistent error handling.

    Args:
        value: The value to validate
        field_name: Name of the field for error reporting
        expected_type: Expected type for validation
        default: Default value to return if validation fails

    Returns:
        Validated value or safe default

    Raises:
        ValueError: If validation fails and no default provided
    """
    if value is None:
        return default

    if not isinstance(value, expected_type):
        if default is not None:
            return default
        raise ValueError(
            f"Invalid {field_name}: expected {expected_type.__name__}, got {type(value).__name__}"
        )

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
