"""Authentication utility functions."""

from __future__ import annotations


def parse_comma_separated(value: str | list[str] | None) -> list[str]:
    """
    Parse a comma-separated string into a list of non-empty strings.

    Handles both string and list inputs for flexibility. Useful for parsing
    environment variables or JWT claims that may be provided as comma-separated
    strings.

    Args:
        value: A comma-separated string, a list of strings, or None

    Returns:
        A list of non-empty, trimmed strings. Empty list if value is None.

    Examples:
        >>> parse_comma_separated("proj1, proj2, proj3")
        ['proj1', 'proj2', 'proj3']
        >>> parse_comma_separated("proj1,,proj2")
        ['proj1', 'proj2']
        >>> parse_comma_separated(["proj1", " proj2 ", "proj3"])
        ['proj1', 'proj2', 'proj3']
        >>> parse_comma_separated(None)
        []
        >>> parse_comma_separated("")
        []
    """
    if value is None:
        return []

    if isinstance(value, list):
        # Strip whitespace from list elements for consistency
        return [item.strip() for item in value if item.strip()]

    # Parse comma-separated string, filtering out empty entries
    return [item.strip() for item in value.split(",") if item.strip()]
