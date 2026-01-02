"""
PR Comment Analyzer - Phase 4.6

Intelligent classification and analysis of PR comments to determine fix actions.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple, cast, Literal

from .review_types import (
    PrComment, CommentClassification, CommentType, 
    FixAction, ReviewContext
)

logger = logging.getLogger(__name__)


class PrCommentAnalyzer:
    """
    Intelligent PR comment analyzer that classifies comments and suggests actions.
    
    Uses pattern matching, keyword analysis, and contextual understanding
    to determine what type of comment it is and how NAVI should respond.
    """
    
    def __init__(self):
        self.classification_patterns = self._initialize_patterns()
        self.keyword_weights = self._initialize_keyword_weights()
        
    def analyze_comment(
        self, 
        comment: PrComment, 
        context: ReviewContext
    ) -> CommentClassification:
        """
        Analyze a single PR comment and classify it.
        
        Args:
            comment: The comment to analyze
            context: PR context for better classification
            
        Returns:
            Classification result with suggested action
        """
        logger.debug(f"Analyzing comment {comment.id}: '{comment.body[:50]}...'")
        
        # Extract features from comment
        features = self._extract_comment_features(comment, context)
        
        # Classify comment type
        comment_type, confidence = self._classify_comment_type(features)
        
        # Determine suggested action
        suggested_action = self._determine_action(comment_type, features, confidence)
        
        # Assess fixability
        fixable = self._is_comment_fixable(comment_type, features)
        
        # Determine priority
        priority = self._determine_priority(comment_type, features)
        
        # Generate reasoning
        reasoning = self._generate_reasoning(comment_type, features, confidence)
        
        classification = CommentClassification(
            comment_id=comment.id,
            comment_type=comment_type,
            confidence=confidence,
            suggested_action=suggested_action,
            fixable=fixable,
            priority=cast(Literal["low", "medium", "high", "critical"], priority if priority in ["low", "medium", "high", "critical"] else "medium"),
            reasoning=reasoning,
            keywords=features.get("matched_keywords", [])
        )
        
        logger.info(
            f"Comment {comment.id} classified as {comment_type.value} "
            f"(confidence: {confidence:.2f}, action: {suggested_action.value})"
        )
        
        return classification
        
    def analyze_multiple_comments(
        self, 
        comments: List[PrComment], 
        context: ReviewContext
    ) -> List[CommentClassification]:
        """
        Analyze multiple comments with batch optimizations.
        
        Args:
            comments: List of comments to analyze
            context: PR context
            
        Returns:
            List of classification results
        """
        logger.info(f"Analyzing {len(comments)} comments for PR #{context.pr_number}")
        
        classifications = []
        
        for comment in comments:
            try:
                classification = self.analyze_comment(comment, context)
                classifications.append(classification)
            except Exception as e:
                logger.error(f"Failed to analyze comment {comment.id}: {e}")
                # Create fallback classification
                fallback = CommentClassification(
                    comment_id=comment.id,
                    comment_type=CommentType.UNKNOWN,
                    confidence=0.0,
                    suggested_action=FixAction.ESCALATE,
                    fixable=False,
                    priority="low",
                    reasoning=f"Analysis failed: {e}",
                    keywords=[]
                )
                classifications.append(fallback)
                
        return classifications
        
    def get_fixable_comments(
        self, 
        classifications: List[CommentClassification]
    ) -> List[CommentClassification]:
        """Filter classifications to only fixable comments"""
        fixable = [
            c for c in classifications 
            if c.fixable and c.suggested_action == FixAction.CODE_FIX
        ]
        
        logger.info(f"Found {len(fixable)} fixable comments out of {len(classifications)}")
        return fixable
        
    def prioritize_comments(
        self, 
        classifications: List[CommentClassification]
    ) -> List[CommentClassification]:
        """Sort comments by priority for processing order"""
        priority_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        
        return sorted(
            classifications,
            key=lambda c: (priority_order.get(c.priority, 0), c.confidence),
            reverse=True
        )
        
    def _extract_comment_features(self, comment: PrComment, context: ReviewContext) -> Dict[str, Any]:
        """Extract features from comment for classification"""
        text = comment.body.lower().strip()
        
        features = {
            "text": text,
            "length": len(text),
            "has_code": bool(re.search(r'```|`[^`]+`', comment.body)),
            "has_question": bool(re.search(r'\\?|what|why|how|when|where', text)),
            "is_inline": comment.line_number is not None,
            "file_type": self._get_file_type(comment.file_path) if comment.file_path else None,
            "author": comment.author,
            "is_author_comment": comment.author == context.author,
            "matched_keywords": [],
            "matched_patterns": []
        }
        
        # Match keywords and patterns
        for keyword, weight in self.keyword_weights.items():
            if keyword in text:
                features["matched_keywords"].append(keyword)
                
        for pattern_name, pattern_data in self.classification_patterns.items():
            for pattern in pattern_data["patterns"]:
                if re.search(pattern, text, re.IGNORECASE):
                    features["matched_patterns"].append(pattern_name)
                    
        return features
        
    def _classify_comment_type(self, features: Dict[str, Any]) -> Tuple[CommentType, float]:
        """Classify comment type based on features"""
        scores = {comment_type: 0.0 for comment_type in CommentType}
        
        # Score based on matched patterns
        for pattern_name in features["matched_patterns"]:
            if pattern_name in self.classification_patterns:
                pattern_data = self.classification_patterns[pattern_name]
                comment_type = CommentType(pattern_data["type"])
                scores[comment_type] += pattern_data["weight"]
                
        # Score based on keywords
        for keyword in features["matched_keywords"]:
            weight = self.keyword_weights.get(keyword, 0.1)
            
            # Determine which comment types this keyword supports
            if keyword in ["null", "undefined", "nullable", "optional"]:
                scores[CommentType.NULL_SAFETY] += weight
            elif keyword in ["style", "format", "indent", "spacing"]:
                scores[CommentType.STYLE] += weight
            elif keyword in ["name", "rename", "variable", "function"]:
                scores[CommentType.NAMING] += weight
            elif keyword in ["test", "testing", "spec", "coverage"]:
                scores[CommentType.TESTING] += weight
            elif keyword in ["performance", "slow", "optimize", "efficient"]:
                scores[CommentType.PERFORMANCE] += weight
            elif keyword in ["security", "vulnerable", "exploit", "sanitize"]:
                scores[CommentType.SECURITY] += weight
                
        # Additional heuristics
        if features["has_question"]:
            scores[CommentType.DISCUSSION] += 0.3
            
        if "lgtm" in features["text"] or "looks good" in features["text"]:
            scores[CommentType.APPROVAL] += 0.8
            
        # Find highest scoring type
        best_type = max(scores.items(), key=lambda x: x[1])
        
        if best_type[1] > 0.0:
            confidence = min(best_type[1], 1.0)
            return best_type[0], confidence
        else:
            return CommentType.UNKNOWN, 0.1
            
    def _determine_action(self, comment_type: CommentType, features: Dict[str, Any], confidence: float) -> FixAction:
        """Determine what action to take for this comment type"""
        # Low confidence comments should be escalated
        if confidence < 0.3:
            return FixAction.ESCALATE
            
        # Action mappings based on comment type
        action_map = {
            CommentType.NULL_SAFETY: FixAction.CODE_FIX,
            CommentType.STYLE: FixAction.CODE_FIX,
            CommentType.NAMING: FixAction.CODE_FIX,
            CommentType.LOGIC_ERROR: FixAction.CODE_FIX if confidence > 0.7 else FixAction.ESCALATE,
            CommentType.PERFORMANCE: FixAction.REPLY_ONLY,
            CommentType.SECURITY: FixAction.ESCALATE,  # Security issues need human review
            CommentType.TESTING: FixAction.CODE_FIX,
            CommentType.DOCUMENTATION: FixAction.CODE_FIX,
            CommentType.DISCUSSION: FixAction.REPLY_ONLY,
            CommentType.APPROVAL: FixAction.IGNORE,
            CommentType.UNKNOWN: FixAction.REQUEST_CLARIFICATION
        }
        
        return action_map.get(comment_type, FixAction.ESCALATE)
        
    def _is_comment_fixable(self, comment_type: CommentType, features: Dict[str, Any]) -> bool:
        """Determine if comment represents a fixable issue"""
        fixable_types = {
            CommentType.NULL_SAFETY,
            CommentType.STYLE,
            CommentType.NAMING,
            CommentType.TESTING,
            CommentType.DOCUMENTATION
        }
        
        if comment_type == CommentType.LOGIC_ERROR:
            # Only simple logic errors are auto-fixable
            return len(features.get("matched_keywords", [])) > 2
            
        return comment_type in fixable_types
        
    def _determine_priority(self, comment_type: CommentType, features: Dict[str, Any]) -> str:
        """Determine priority level for comment"""
        priority_map = {
            CommentType.SECURITY: "critical",
            CommentType.LOGIC_ERROR: "high",
            CommentType.NULL_SAFETY: "high",
            CommentType.PERFORMANCE: "medium",
            CommentType.TESTING: "medium",
            CommentType.STYLE: "low",
            CommentType.NAMING: "low",
            CommentType.DOCUMENTATION: "low",
            CommentType.DISCUSSION: "low",
            CommentType.APPROVAL: "low",
            CommentType.UNKNOWN: "medium"
        }
        
        return priority_map.get(comment_type, "low")
        
    def _generate_reasoning(self, comment_type: CommentType, features: Dict[str, Any], confidence: float) -> str:
        """Generate human-readable reasoning for classification"""
        reasons = []
        
        if features["matched_keywords"]:
            reasons.append(f"Keywords: {', '.join(features['matched_keywords'])}")
            
        if features["matched_patterns"]:
            reasons.append(f"Patterns: {', '.join(features['matched_patterns'])}")
            
        if features["is_inline"]:
            reasons.append("Inline comment on specific code")
            
        if features["has_code"]:
            reasons.append("Contains code examples")
            
        if features["has_question"]:
            reasons.append("Contains questions")
            
        reasoning = f"Classified as {comment_type.value} (confidence: {confidence:.2f}). "
        
        if reasons:
            reasoning += "Evidence: " + "; ".join(reasons)
        else:
            reasoning += "Based on text analysis"
            
        return reasoning
        
    def _get_file_type(self, file_path: str) -> Optional[str]:
        """Get file type from path"""
        if not file_path:
            return None
            
        extension = file_path.split('.')[-1].lower()
        
        type_map = {
            'py': 'python',
            'js': 'javascript', 
            'ts': 'typescript',
            'java': 'java',
            'cpp': 'cpp',
            'c': 'c',
            'go': 'go',
            'rs': 'rust',
            'php': 'php',
            'rb': 'ruby'
        }
        
        return type_map.get(extension, extension)
        
    def _initialize_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize regex patterns for comment classification"""
        return {
            "null_safety": {
                "type": "null_safety",
                "weight": 0.8,
                "patterns": [
                    r"\\bnull\\b|\\bundefined\\b|\\bNone\\b",
                    r"null.?check|null.?safe|optional.?chain",
                    r"might be null|could be null|may be null",
                    r"nullable|non.?null|not.?null"
                ]
            },
            "style_issues": {
                "type": "style",
                "weight": 0.7,
                "patterns": [
                    r"format|formatting|indent|indentation",
                    r"style|spacing|whitespace",
                    r"line.?length|too.?long|wrap",
                    r"consistent|consistency"
                ]
            },
            "naming_issues": {
                "type": "naming",
                "weight": 0.7,
                "patterns": [
                    r"name|naming|rename",
                    r"variable.?name|function.?name",
                    r"descriptive|meaningful",
                    r"camel.?case|snake.?case|pascal.?case"
                ]
            },
            "logic_errors": {
                "type": "logic_error",
                "weight": 0.9,
                "patterns": [
                    r"logic|logical|algorithm",
                    r"wrong|incorrect|error|bug",
                    r"should be|expected|instead",
                    r"condition|if.?statement|comparison"
                ]
            },
            "performance": {
                "type": "performance",
                "weight": 0.6,
                "patterns": [
                    r"performance|slow|fast|optimize",
                    r"efficient|inefficient|bottleneck",
                    r"memory|cpu|time.?complex",
                    r"cache|caching"
                ]
            },
            "security": {
                "type": "security",
                "weight": 0.9,
                "patterns": [
                    r"security|secure|vulnerable",
                    r"exploit|attack|malicious",
                    r"sanitize|validate|escape",
                    r"injection|xss|csrf"
                ]
            },
            "testing": {
                "type": "testing",
                "weight": 0.6,
                "patterns": [
                    r"test|testing|spec",
                    r"coverage|unit.?test|integration",
                    r"mock|stub|assert",
                    r"test.?case|test.?suite"
                ]
            },
            "documentation": {
                "type": "documentation",
                "weight": 0.5,
                "patterns": [
                    r"document|doc|comment",
                    r"explain|clarify|description",
                    r"readme|docstring|javadoc",
                    r"example|usage"
                ]
            },
            "approval": {
                "type": "approval",
                "weight": 0.9,
                "patterns": [
                    r"lgtm|looks.?good|approve",
                    r"\\+1|👍|✅",
                    r"great|excellent|nice",
                    r"merge|ship.?it"
                ]
            }
        }
        
    def _initialize_keyword_weights(self) -> Dict[str, float]:
        """Initialize keyword weights for classification"""
        return {
            # Null safety keywords
            "null": 0.8, "undefined": 0.8, "none": 0.6, "nullable": 0.7,
            "optional": 0.5, "empty": 0.4,
            
            # Style keywords  
            "format": 0.6, "style": 0.7, "indent": 0.6, "spacing": 0.5,
            "consistent": 0.5, "whitespace": 0.5,
            
            # Naming keywords
            "name": 0.6, "rename": 0.7, "variable": 0.5, "function": 0.5,
            "descriptive": 0.6, "meaningful": 0.6,
            
            # Logic keywords
            "wrong": 0.8, "incorrect": 0.8, "error": 0.7, "bug": 0.8,
            "should": 0.4, "expected": 0.6, "logic": 0.7,
            
            # Performance keywords
            "slow": 0.7, "fast": 0.6, "optimize": 0.8, "performance": 0.8,
            "efficient": 0.6, "memory": 0.5, "cpu": 0.6,
            
            # Security keywords
            "security": 0.9, "vulnerable": 0.9, "exploit": 0.9, "attack": 0.8,
            "sanitize": 0.7, "validate": 0.6, "injection": 0.9,
            
            # Testing keywords
            "test": 0.6, "testing": 0.7, "coverage": 0.6, "mock": 0.5,
            "assert": 0.6, "spec": 0.5,
            
            # Documentation keywords
            "document": 0.5, "explain": 0.5, "clarify": 0.5, "comment": 0.4,
            "example": 0.4, "usage": 0.4,
            
            # Approval keywords
            "lgtm": 0.9, "good": 0.4, "great": 0.6, "excellent": 0.7,
            "approve": 0.8, "merge": 0.6
        }