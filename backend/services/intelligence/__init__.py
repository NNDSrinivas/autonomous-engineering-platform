"""
NAVI Intelligence Services Package.

Provides intelligent analysis and learning capabilities for personalized
AI responses based on user behavior and patterns.

Services:
- PatternDetector: Detect patterns in user behavior and code
- PreferenceLearner: Learn preferences from feedback and interactions
- ContextPredictor: Predict relevant context for queries
- ResponsePersonalizer: Personalize NAVI responses
"""

__all__ = [
    "PatternDetector",
    "get_pattern_detector",
    "PreferenceLearner",
    "get_preference_learner",
    "ContextPredictor",
    "get_context_predictor",
    "ResponsePersonalizer",
    "get_response_personalizer",
]


def __getattr__(name):
    """Lazy import to avoid circular dependencies."""
    if name in ("PatternDetector", "get_pattern_detector"):
        from backend.services.intelligence.pattern_detector import (
            PatternDetector,
            get_pattern_detector,
        )
        return PatternDetector if name == "PatternDetector" else get_pattern_detector
    elif name in ("PreferenceLearner", "get_preference_learner"):
        from backend.services.intelligence.preference_learner import (
            PreferenceLearner,
            get_preference_learner,
        )
        return PreferenceLearner if name == "PreferenceLearner" else get_preference_learner
    elif name in ("ContextPredictor", "get_context_predictor"):
        from backend.services.intelligence.context_predictor import (
            ContextPredictor,
            get_context_predictor,
        )
        return ContextPredictor if name == "ContextPredictor" else get_context_predictor
    elif name in ("ResponsePersonalizer", "get_response_personalizer"):
        from backend.services.intelligence.response_personalizer import (
            ResponsePersonalizer,
            get_response_personalizer,
        )
        return ResponsePersonalizer if name == "ResponsePersonalizer" else get_response_personalizer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
