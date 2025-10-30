"""
Intelligent Context Agent - Core AI that provides contextual answers
across all integrated platforms with source attribution.
"""

from .agent import IntelligentContextAgent
from .models import ContextSource, ContextQuery, ContextResponse
from .search import ContextSearchEngine

__all__ = [
    "IntelligentContextAgent",
    "ContextSource", 
    "ContextQuery",
    "ContextResponse",
    "ContextSearchEngine"
]