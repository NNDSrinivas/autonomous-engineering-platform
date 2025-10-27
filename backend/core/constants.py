"""Shared constants for the autonomous engineering platform

This module defines constants used across multiple modules to ensure consistency
and maintainability. Centralizing these values prevents duplication and makes
updates easier.
"""

import re

# Entity identifier patterns
JIRA_KEY_PATTERN = re.compile(
    r"\b[A-Z]{2,10}-\d+\b"
)  # JIRA project keys are 2-10 chars, word boundaries enforced
PR_NUMBER_PATTERN = re.compile(r"#(\d+)")
SLACK_THREAD_PATTERN = re.compile(r"p\d{10,}")

# Relationship detection patterns
FIXES_PATTERN = re.compile(
    r"(?:fixes?|closes?|resolves?)\s+(?:#(\d+)|([A-Z]{2,10}-\d+))",
    re.IGNORECASE,
)
REVERT_PATTERN = re.compile(r"revert|reverts", re.IGNORECASE)

# Graph edge thresholds
TEMPORAL_WINDOW_HOURS = 48
MIN_SHARED_TERMS_COUNT = 3

# Temporal reasoning limits
MAX_CAUSALITY_PATHS = 10
MAX_PATH_LENGTH = 5
MAX_NODES_IN_CONTEXT = 10  # Used for narrative generation and API validation
MAX_EDGES_IN_CONTEXT = 20  # Limit edges shown in LLM context
MAX_PATHS_IN_CONTEXT = 5  # Limit causality chains shown in LLM context

# Text processing
STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "is",
    "of",
    "with",
}

# Future: SEMANTIC_SIMILARITY_THRESHOLD = 0.75  # Requires embedding vectors


def parse_time_window(window_str: str) -> int:
    """Parse time window string to days

    Args:
        window_str: Time window string (e.g., '30d', '7d')

    Returns:
        Number of days as integer, defaults to 30 if parsing fails

    Examples:
        >>> parse_time_window('7d')
        7
        >>> parse_time_window('invalid')
        30
    """
    import re

    match = re.match(r"(\d+)d", window_str.lower())
    if match:
        return int(match.group(1))
    return 30  # Default to 30 days
