"""
Utility functions for consistent hashing across the platform.
"""

import hashlib


def sha256_hash(text: str) -> str:
    """
    Generate a SHA-256 hash for the given text.

    Args:
        text: The text to hash

    Returns:
        str: The SHA-256 hash as a 64-character hexadecimal string
    """
    return hashlib.sha256(text.encode()).hexdigest()
