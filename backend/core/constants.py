"""Shared constants for the autonomous engineering platform

This module defines constants used across multiple modules to ensure consistency
and maintainability. Centralizing these values prevents duplication and makes
updates easier.
"""

import re

# Entity identifier patterns
JIRA_KEY_PATTERN = re.compile(r"[A-Z]{2,}-\d+")
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

# Future: SEMANTIC_SIMILARITY_THRESHOLD = 0.75  # Requires embedding vectors
