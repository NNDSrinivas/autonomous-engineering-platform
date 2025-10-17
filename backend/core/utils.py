"""Core utilities for the autonomous engineering platform."""

import hashlib
import json
from typing import Any, Dict


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
    context_str = json.dumps(context, sort_keys=True, separators=(',', ':'))
    combined_input = prompt + context_str
    
    return hashlib.sha256(combined_input.encode('utf-8')).hexdigest()