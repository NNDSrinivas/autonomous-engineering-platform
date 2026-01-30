"""
Enterprise Failure Classification Engine

Intelligent CI failure analysis system that classifies root causes
with high accuracy using pattern matching, machine learning approaches,
and contextual analysis for targeted autonomous repairs.
"""

import re
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
from .ci_types import FailureType, CILogs, FailureContext

logger = logging.getLogger(__name__)


@dataclass
class ClassificationRule:
    """Individual classification rule with patterns and confidence"""

    failure_type: FailureType
    patterns: List[str]
    confidence_weight: float
    context_keywords: List[str]
    exclusion_patterns: List[str] = field(default_factory=list)


class FailureClassifier:
    """
    Enterprise-grade CI failure classification system

    Uses sophisticated pattern matching, keyword analysis, and contextual
    understanding to accurately classify CI failures for targeted repairs.
    """

    def __init__(self):
        self.rules = self._initialize_classification_rules()
        self.keyword_weights = self._initialize_keyword_weights()
        self.file_extension_context = self._initialize_file_context()

    def classify_failure(self, logs: CILogs) -> FailureContext:
        """
        Analyze CI logs and classify failure type with confidence

        Args:
            logs: Structured CI logs from log fetcher

        Returns:
            Rich failure context with type, confidence, and repair guidance
        """
        # Extract key information from logs
        error_analysis = self._analyze_error_content(logs.error_lines)
        file_analysis = self._extract_file_references(logs.raw_logs)
        stack_trace_analysis = self._extract_stack_traces(logs.raw_logs)

        # Score each failure type
        type_scores = self._score_failure_types(logs, error_analysis)

        # Determine best match
        best_type, confidence = self._select_best_classification(type_scores)

        # Build rich context
        context = FailureContext(
            failure_type=best_type,
            confidence=confidence,
            affected_files=file_analysis["files"],
            error_messages=error_analysis["messages"],
            stack_traces=stack_trace_analysis,
            relevant_logs=self._extract_relevant_logs(logs, best_type),
            failure_location=self._determine_failure_location(logs, file_analysis),
            related_errors=error_analysis["related"],
            dependencies_involved=self._extract_dependencies(logs.raw_logs),
            environment_context=self._extract_environment_context(logs.raw_logs),
        )

        logger.info(
            f"Classified CI failure as {best_type.value} with {confidence:.2f} confidence"
        )
        return context

    def _initialize_classification_rules(self) -> List[ClassificationRule]:
        """Initialize comprehensive failure classification rules"""
        return [
            # Test Failures
            ClassificationRule(
                failure_type=FailureType.TEST_FAILURE,
                patterns=[
                    r"FAIL:",
                    r"FAILED:",
                    r"Test.*fail",
                    r"AssertionError",
                    r"test.*error",
                    r"expect.*to.*equal",
                    r"expect.*to.*be",
                    r"should.*but.*got",
                    r"✗.*test",
                    r"❌.*test",
                    r"failing test",
                    r"test suite fail",
                    r"jest.*fail",
                    r"mocha.*fail",
                    r"pytest.*fail",
                    r"unittest.*fail",
                ],
                confidence_weight=0.9,
                context_keywords=["test", "spec", "assert", "expect", "should", "mock"],
            ),
            # Build/Compilation Errors
            ClassificationRule(
                failure_type=FailureType.BUILD_ERROR,
                patterns=[
                    r"BUILD FAILED",
                    r"compilation.*error",
                    r"compile.*fail",
                    r"cannot find.*module",
                    r"module not found",
                    r"unresolved import",
                    r"webpack.*error",
                    r"babel.*error",
                    r"tsc.*error",
                    r"build.*error",
                    r"syntax error",
                    r"parse.*error",
                    r"invalid syntax",
                ],
                confidence_weight=0.85,
                context_keywords=[
                    "build",
                    "compile",
                    "webpack",
                    "babel",
                    "tsc",
                    "module",
                    "import",
                ],
            ),
            # Type Errors (TypeScript/Python/etc.)
            ClassificationRule(
                failure_type=FailureType.TYPE_ERROR,
                patterns=[
                    r"Type.*error",
                    r"TypeError",
                    r"type.*mismatch",
                    r"type.*check.*fail",
                    r"Property.*does not exist",
                    r"Cannot.*assign.*type",
                    r"is not assignable",
                    r"Expected.*but got",
                    r"mypy.*error",
                    r"tsc.*type.*error",
                    r"AttributeError",
                    r"has no attribute",
                    r"NoneType.*object",
                ],
                confidence_weight=0.9,
                context_keywords=[
                    "type",
                    "interface",
                    "class",
                    "property",
                    "method",
                    "null",
                    "undefined",
                ],
            ),
            # Linting/Style Errors
            ClassificationRule(
                failure_type=FailureType.LINT_ERROR,
                patterns=[
                    r"lint.*error",
                    r"eslint.*error",
                    r"pylint.*error",
                    r"flake8.*error",
                    r"formatting.*error",
                    r"style.*error",
                    r"code.*style",
                    r"prettier.*error",
                    r"black.*error",
                    r"isort.*error",
                    r"unused.*variable",
                    r"unused.*import",
                    r"missing.*semicolon",
                ],
                confidence_weight=0.8,
                context_keywords=[
                    "lint",
                    "style",
                    "format",
                    "unused",
                    "missing",
                    "semicolon",
                    "indent",
                ],
            ),
            # Environment/Configuration Issues
            ClassificationRule(
                failure_type=FailureType.ENV_MISSING,
                patterns=[
                    r"environment.*variable.*not.*found",
                    r"missing.*env",
                    r"env.*not.*set",
                    r"secret.*not.*found",
                    r"token.*not.*provided",
                    r"API.*key.*missing",
                    r"configuration.*missing",
                    r"config.*error",
                    r"credential.*error",
                ],
                confidence_weight=0.9,
                context_keywords=[
                    "env",
                    "environment",
                    "secret",
                    "token",
                    "key",
                    "config",
                    "credential",
                ],
            ),
            # Dependency/Package Issues
            ClassificationRule(
                failure_type=FailureType.DEPENDENCY_ERROR,
                patterns=[
                    r"dependency.*error",
                    r"package.*not.*found",
                    r"npm.*error",
                    r"pip.*error",
                    r"yarn.*error",
                    r"poetry.*error",
                    r"requirements.*error",
                    r"node_modules.*error",
                    r"package.*lock.*error",
                    r"version.*conflict",
                    r"could not.*resolve.*dependency",
                ],
                confidence_weight=0.85,
                context_keywords=[
                    "dependency",
                    "package",
                    "npm",
                    "pip",
                    "yarn",
                    "version",
                    "install",
                ],
            ),
            # Security Scan Failures
            ClassificationRule(
                failure_type=FailureType.SECURITY_SCAN,
                patterns=[
                    r"security.*vulnerability",
                    r"security.*scan.*fail",
                    r"CVE-",
                    r"vulnerability.*found",
                    r"security.*alert",
                    r"snyk.*error",
                    r"audit.*fail",
                    r"security.*check.*fail",
                ],
                confidence_weight=0.95,
                context_keywords=["security", "vulnerability", "CVE", "audit", "scan"],
            ),
            # Performance Regression
            ClassificationRule(
                failure_type=FailureType.PERFORMANCE_REGRESSION,
                patterns=[
                    r"performance.*regression",
                    r"performance.*test.*fail",
                    r"timeout.*error",
                    r"too.*slow",
                    r"exceeds.*threshold",
                    r"memory.*limit",
                    r"cpu.*limit",
                    r"lighthouse.*fail",
                    r"performance.*budget",
                ],
                confidence_weight=0.8,
                context_keywords=[
                    "performance",
                    "timeout",
                    "slow",
                    "memory",
                    "cpu",
                    "threshold",
                ],
            ),
            # Deployment Errors
            ClassificationRule(
                failure_type=FailureType.DEPLOYMENT_ERROR,
                patterns=[
                    r"deployment.*fail",
                    r"deploy.*error",
                    r"infrastructure.*error",
                    r"docker.*error",
                    r"container.*error",
                    r"k8s.*error",
                    r"kubernetes.*error",
                    r"terraform.*error",
                    r"cloudformation.*error",
                    r"helm.*error",
                ],
                confidence_weight=0.85,
                context_keywords=[
                    "deploy",
                    "deployment",
                    "docker",
                    "container",
                    "k8s",
                    "terraform",
                ],
            ),
        ]

    def _initialize_keyword_weights(self) -> Dict[str, float]:
        """Initialize keyword importance weights for classification"""
        return {
            # High confidence indicators
            "test": 0.9,
            "fail": 0.8,
            "error": 0.8,
            "exception": 0.9,
            "assert": 0.85,
            "expect": 0.8,
            "build": 0.7,
            "compile": 0.8,
            # Medium confidence indicators
            "warning": 0.4,
            "deprecated": 0.3,
            "missing": 0.6,
            "not found": 0.7,
            # Context-specific weights
            "typescript": 0.6,
            "javascript": 0.6,
            "python": 0.6,
            "java": 0.6,
            "docker": 0.7,
            "kubernetes": 0.7,
            "terraform": 0.7,
        }

    def _initialize_file_context(self) -> Dict[str, FailureType]:
        """Map file extensions to likely failure types"""
        return {
            ".test.ts": FailureType.TEST_FAILURE,
            ".test.js": FailureType.TEST_FAILURE,
            ".spec.ts": FailureType.TEST_FAILURE,
            ".spec.js": FailureType.TEST_FAILURE,
            "test_*.py": FailureType.TEST_FAILURE,
            ".ts": FailureType.TYPE_ERROR,
            ".tsx": FailureType.TYPE_ERROR,
            "Dockerfile": FailureType.DEPLOYMENT_ERROR,
            "docker-compose.yml": FailureType.DEPLOYMENT_ERROR,
            "k8s.yml": FailureType.DEPLOYMENT_ERROR,
            "package.json": FailureType.DEPENDENCY_ERROR,
            "requirements.txt": FailureType.DEPENDENCY_ERROR,
            "Pipfile": FailureType.DEPENDENCY_ERROR,
        }

    def _analyze_error_content(self, error_lines: List[str]) -> Dict[str, List[str]]:
        """Deep analysis of error message content"""
        messages = []
        related = []

        for line in error_lines:
            # Extract clean error messages
            clean_msg = self._clean_error_message(line)
            if clean_msg and len(clean_msg) > 10:  # Filter out noise
                messages.append(clean_msg)

                # Find related/chained errors
                if "caused by" in clean_msg.lower() or "due to" in clean_msg.lower():
                    related.append(clean_msg)

        return {"messages": messages[:10], "related": related}  # Limit to most relevant

    def _clean_error_message(self, error_line: str) -> str:
        """Clean and normalize error message"""
        # Remove ANSI codes, timestamps, prefixes
        clean = re.sub(r"\x1b\[[0-9;]*m", "", error_line)  # ANSI codes
        clean = re.sub(r"^\[\d{4}-\d{2}-\d{2}.*?\]", "", clean)  # Timestamps
        clean = re.sub(r"^ERROR:|^FAIL:|^FAILED:", "", clean, flags=re.IGNORECASE)
        clean = clean.strip()

        return clean

    def _extract_file_references(self, logs: str) -> Dict[str, List[str]]:
        """Extract file paths and references from logs"""
        # Common file path patterns in logs
        file_patterns = [
            r"/?[\w\-/.]+\.(ts|js|py|java|cpp|c|h|json|yml|yaml|xml|md)",
            r"at [\w\-/.]+\.(ts|js|py):\d+:\d+",
            r'File "[\w\-/.]+"',
            r"in file [\w\-/.]+",
        ]

        files = set()

        for pattern in file_patterns:
            matches = re.finditer(pattern, logs, re.IGNORECASE)
            for match in matches:
                file_path = match.group(0)
                # Clean up the path
                file_path = re.sub(r'^(at |File "|in file )', "", file_path)
                file_path = re.sub(
                    r'".*$', "", file_path
                )  # Remove trailing quotes/info
                file_path = re.sub(r":\d+:\d+$", "", file_path)  # Remove line:column

                if len(file_path) > 3:  # Filter out very short matches
                    files.add(file_path)

        return {"files": list(files)}

    def _extract_stack_traces(self, logs: str) -> List[str]:
        """Extract complete stack traces from logs"""
        stack_traces = []

        # Pattern for stack trace start
        stack_patterns = [
            r"Traceback \(most recent call last\):",
            r"Stack trace:",
            r"at [\w\-/.]+\.(ts|js|py):\d+:\d+",
        ]

        lines = logs.split("\n")
        in_stack_trace = False
        current_trace = []

        for line in lines:
            line = line.strip()

            # Check if starting a stack trace
            if any(
                re.search(pattern, line, re.IGNORECASE) for pattern in stack_patterns
            ):
                if current_trace:  # Save previous trace
                    stack_traces.append("\n".join(current_trace))
                current_trace = [line]
                in_stack_trace = True

            elif in_stack_trace:
                if (
                    line.startswith("  ")
                    or line.startswith("\t")
                    or re.match(r"^\s*at ", line)
                ):
                    current_trace.append(line)
                else:
                    # End of stack trace
                    if current_trace:
                        stack_traces.append("\n".join(current_trace))
                    current_trace = []
                    in_stack_trace = False

        # Don't forget the last trace
        if current_trace:
            stack_traces.append("\n".join(current_trace))

        return stack_traces[:5]  # Limit to 5 most relevant traces

    def _score_failure_types(
        self, logs: CILogs, error_analysis: Dict
    ) -> Dict[FailureType, float]:
        """Score each failure type based on evidence in logs"""
        scores = defaultdict(float)

        # Content to analyze
        all_content = logs.raw_logs.lower()
        " ".join(logs.error_lines).lower()

        # Score each classification rule
        for rule in self.rules:
            rule_score = 0.0
            pattern_matches = 0

            # Check pattern matches
            for pattern in rule.patterns:
                if re.search(pattern, all_content, re.IGNORECASE):
                    pattern_matches += 1
                    rule_score += rule.confidence_weight

            # Bonus for multiple pattern matches
            if pattern_matches > 1:
                rule_score *= 1.0 + (pattern_matches - 1) * 0.1

            # Check exclusion patterns
            if rule.exclusion_patterns:
                for exclusion in rule.exclusion_patterns:
                    if re.search(exclusion, all_content, re.IGNORECASE):
                        rule_score *= 0.5  # Reduce confidence

            # Keyword context bonus
            keyword_bonus = 0.0
            for keyword in rule.context_keywords:
                if keyword in all_content:
                    weight = self.keyword_weights.get(keyword, 0.5)
                    keyword_bonus += weight * 0.1

            rule_score += keyword_bonus
            scores[rule.failure_type] = max(scores[rule.failure_type], rule_score)

        # Normalize scores
        if scores:
            max_score = max(scores.values())
            if max_score > 0:
                for failure_type in scores:
                    scores[failure_type] = scores[failure_type] / max_score

        return dict(scores)

    def _select_best_classification(
        self, type_scores: Dict[FailureType, float]
    ) -> Tuple[FailureType, float]:
        """Select best failure classification with confidence"""
        if not type_scores:
            return FailureType.UNKNOWN, 0.1

        # Find best match
        best_type = max(type_scores.keys(), key=lambda k: type_scores[k])
        confidence = type_scores[best_type]

        # Apply confidence adjustments
        if confidence < 0.3:
            return FailureType.UNKNOWN, confidence

        return best_type, min(confidence, 0.99)  # Cap confidence at 99%

    def _extract_relevant_logs(
        self, logs: CILogs, failure_type: FailureType
    ) -> List[str]:
        """Extract most relevant log lines for the identified failure type"""
        relevant = []

        # Get type-specific keywords
        type_keywords = []
        for rule in self.rules:
            if rule.failure_type == failure_type:
                type_keywords.extend(rule.context_keywords)
                break

        # Find relevant log entries
        for log_entry in logs.structured_logs:
            content = log_entry["content"].lower()

            # Include error lines
            if log_entry["type"] == "error":
                relevant.append(log_entry["content"])

            # Include lines with relevant keywords
            elif any(keyword in content for keyword in type_keywords):
                relevant.append(log_entry["content"])

        return relevant[:20]  # Limit to most relevant

    def _determine_failure_location(
        self, logs: CILogs, file_analysis: Dict
    ) -> Optional[Dict[str, Any]]:
        """Determine specific location of failure if possible"""
        # Look for line:column patterns
        location_pattern = r"([\w\-/.]+\.(ts|js|py|java)):(\d+):(\d+)"

        for line in logs.error_lines:
            match = re.search(location_pattern, line)
            if match:
                return {
                    "file": match.group(1),
                    "line": int(match.group(3)),
                    "column": int(match.group(4)),
                    "context": line.strip(),
                }

        # Fallback to first identified file
        if file_analysis["files"]:
            return {
                "file": file_analysis["files"][0],
                "line": None,
                "column": None,
                "context": "Inferred from error logs",
            }

        return None

    def _extract_dependencies(self, logs: str) -> List[str]:
        """Extract dependency names from error logs"""
        dependencies = set()

        # Common dependency patterns
        patterns = [
            r"npm install ([\w@/-]+)",
            r"pip install ([\w-]+)",
            r"yarn add ([\w@/-]+)",
            r'cannot find module ["\']([^"\']+)["\']',
            r'import.*from ["\']([^"\']+)["\']',
            r'ModuleNotFoundError.*["\']([^"\']+)["\']',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, logs, re.IGNORECASE)
            for match in matches:
                dep = match.group(1)
                if not dep.startswith("."):  # Skip relative imports
                    dependencies.add(dep)

        return list(dependencies)[:10]  # Limit results

    def _extract_environment_context(self, logs: str) -> Dict[str, Any]:
        """Extract environment context from logs"""
        context = {}

        # Extract Node.js version
        node_match = re.search(r"node.*v?(\d+\.\d+\.\d+)", logs, re.IGNORECASE)
        if node_match:
            context["node_version"] = node_match.group(1)

        # Extract Python version
        python_match = re.search(r"python\s+(\d+\.\d+\.\d+)", logs, re.IGNORECASE)
        if python_match:
            context["python_version"] = python_match.group(1)

        # Extract OS information
        if "ubuntu" in logs.lower():
            context["os"] = "ubuntu"
        elif "windows" in logs.lower():
            context["os"] = "windows"
        elif "macos" in logs.lower():
            context["os"] = "macos"

        # Extract CI environment
        if "github actions" in logs.lower() or "GITHUB_" in logs:
            context["ci_provider"] = "github_actions"
        elif "jenkins" in logs.lower():
            context["ci_provider"] = "jenkins"
        elif "circleci" in logs.lower():
            context["ci_provider"] = "circleci"

        return context
