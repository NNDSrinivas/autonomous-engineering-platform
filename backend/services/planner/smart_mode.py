from dataclasses import dataclass
from typing import List, Literal
import re
import os


CRITICAL_FILES = {
    "auth",
    "login",
    "security",
    "jwt",
    "session",
    "password",
    "token",
    "db",
    "database",
    "schema",
    "migrations",
    "model",
    "entity",
    "middleware",
    "api",
    "server",
    "payments",
    "billing",
    "checkout",
    "config",
    "settings",
    "env",
    "docker",
    "kubernetes",
    "deploy",
}

AUTOSAFE_FILE_TYPES = {
    ".md",
    ".json",
    ".yml",
    ".yaml",
    ".css",
    ".scss",
    ".txt",
    ".gitignore",
}

HIGH_RISK_PATTERNS = [
    r"DROP\s+TABLE",
    r"DELETE\s+FROM",
    r"TRUNCATE",
    r"rm\s+-rf",
    r"sudo",
    r"chmod\s+777",
    r"eval\s*\(",
    r"exec\s*\(",
    r"__import__",
    r"process\.env",
    r"os\.system",
    r"shell_exec",
]

FRAMEWORK_CRITICAL_FILES = {
    # React/Next.js
    "package.json",
    "next.config.js",
    "webpack.config.js",
    # Python/Django
    "settings.py",
    "urls.py",
    "wsgi.py",
    "asgi.py",
    # Node.js/Express
    "app.js",
    "server.js",
    "index.js",
    # Database
    "requirements.txt",
    "Pipfile",
    "poetry.lock",
}


@dataclass
class RiskAssessment:
    score: float
    reasons: List[str]
    recommended_mode: Literal["auto", "review", "smart"]
    confidence: float
    risk_level: Literal["low", "medium", "high", "critical"]


class SmartModePlanner:
    """
    Intelligent risk assessment for autonomous code changes.
    Determines whether changes should be auto-applied, reviewed, or require manual approval.
    """

    def assess_risk(
        self,
        changed_files: List[str],
        diff_content: str = "",
        llm_confidence: float = 0.9,
        change_size: int = 0,
    ) -> RiskAssessment:
        """
        Comprehensive risk assessment for code changes.

        Args:
            changed_files: List of file paths being modified
            diff_content: The actual diff content for pattern analysis
            llm_confidence: AI model confidence score (0-1)
            change_size: Number of lines changed

        Returns:
            RiskAssessment with score, reasons, and recommended mode
        """
        score = 0.0
        reasons = []

        # File-based risk assessment
        file_risk = self._assess_file_risk(changed_files)
        score += file_risk["score"]
        reasons.extend(file_risk["reasons"])

        # Content-based risk assessment
        if diff_content:
            content_risk = self._assess_content_risk(diff_content)
            score += content_risk["score"]
            reasons.extend(content_risk["reasons"])

        # Size-based risk assessment
        size_risk = self._assess_size_risk(change_size or len(diff_content.split("\n")))
        score += size_risk["score"]
        reasons.extend(size_risk["reasons"])

        # Confidence-based risk adjustment
        confidence_risk = self._assess_confidence_risk(llm_confidence)
        score += confidence_risk["score"]
        reasons.extend(confidence_risk["reasons"])

        # Clamp score to 0-1 range
        score = max(0.0, min(1.0, score))

        # Determine recommended mode and risk level
        if score < 0.2:
            mode = "auto"
            risk_level = "low"
        elif score < 0.4:
            mode = "smart"
            risk_level = "low"
        elif score < 0.6:
            mode = "smart"
            risk_level = "medium"
        elif score < 0.8:
            mode = "review"
            risk_level = "high"
        else:
            mode = "review"
            risk_level = "critical"

        return RiskAssessment(
            score=score,
            reasons=reasons,
            recommended_mode=mode,
            confidence=llm_confidence,
            risk_level=risk_level,
        )

    def _assess_file_risk(self, changed_files: List[str]) -> dict:
        """Assess risk based on which files are being changed."""
        score = 0.0
        reasons = []

        for file_path in changed_files:
            filename = os.path.basename(file_path).lower()
            filepath_lower = file_path.lower()

            # Critical system files
            if any(critical in filepath_lower for critical in CRITICAL_FILES):
                score += 0.3
                reasons.append(f"Critical file: {file_path}")

            # Framework configuration files
            if filename in FRAMEWORK_CRITICAL_FILES:
                score += 0.25
                reasons.append(f"Framework config file: {filename}")

            # Auto-safe file types (documentation, config)
            if any(filename.endswith(ext) for ext in AUTOSAFE_FILE_TYPES):
                score -= 0.1
                reasons.append(f"Safe file type: {filename}")

            # Production/deployment files
            if any(
                prod in filepath_lower
                for prod in ["prod", "production", "deploy", "release"]
            ):
                score += 0.2
                reasons.append(f"Production file: {file_path}")

            # Test files (generally safer)
            if any(
                test in filepath_lower
                for test in ["test", "spec", "__tests__", "testing"]
            ):
                score -= 0.05
                reasons.append(f"Test file: {file_path}")

        return {"score": score, "reasons": reasons}

    def _assess_content_risk(self, diff_content: str) -> dict:
        """Assess risk based on the actual changes in the diff."""
        score = 0.0
        reasons = []

        # Check for high-risk patterns
        for pattern in HIGH_RISK_PATTERNS:
            if re.search(pattern, diff_content, re.IGNORECASE):
                score += 0.4
                reasons.append(f"High-risk pattern detected: {pattern}")

        # Count deletions vs additions
        additions = len(
            [line for line in diff_content.split("\n") if line.startswith("+")]
        )
        deletions = len(
            [line for line in diff_content.split("\n") if line.startswith("-")]
        )

        # High deletion ratio is risky
        if additions > 0:
            deletion_ratio = deletions / (additions + deletions)
            if deletion_ratio > 0.7:
                score += 0.2
                reasons.append("High deletion ratio - removing significant code")

        # Look for sensitive operations
        sensitive_patterns = [
            r"DROP",
            r"DELETE",
            r"REMOVE",
            r"TRUNCATE",
            r"password",
            r"secret",
            r"key",
            r"token",
            r"admin",
            r"root",
            r"sudo",
        ]

        for pattern in sensitive_patterns:
            if re.search(pattern, diff_content, re.IGNORECASE):
                score += 0.15
                reasons.append(f"Sensitive operation: {pattern}")

        return {"score": score, "reasons": reasons}

    def _assess_size_risk(self, change_size: int) -> dict:
        """Assess risk based on the size of changes."""
        score = 0.0
        reasons = []

        if change_size > 500:
            score += 0.3
            reasons.append(f"Very large change: {change_size} lines")
        elif change_size > 200:
            score += 0.2
            reasons.append(f"Large change: {change_size} lines")
        elif change_size > 100:
            score += 0.1
            reasons.append(f"Medium change: {change_size} lines")
        elif change_size < 10:
            score -= 0.05
            reasons.append(f"Small change: {change_size} lines")

        return {"score": score, "reasons": reasons}

    def _assess_confidence_risk(self, llm_confidence: float) -> dict:
        """Assess risk based on AI model confidence."""
        score = 0.0
        reasons = []

        if llm_confidence < 0.5:
            score += 0.4
            reasons.append("Very low AI confidence")
        elif llm_confidence < 0.7:
            score += 0.2
            reasons.append("Low AI confidence")
        elif llm_confidence < 0.8:
            score += 0.1
            reasons.append("Medium AI confidence")
        elif llm_confidence > 0.95:
            score -= 0.05
            reasons.append("Very high AI confidence")

        return {"score": score, "reasons": reasons}

    def should_auto_apply(self, risk: RiskAssessment) -> bool:
        """Determine if changes should be automatically applied."""
        return (
            risk.recommended_mode == "auto"
            and risk.confidence > 0.8
            and risk.score < 0.3
        )

    def get_mode_explanation(self, risk: RiskAssessment) -> str:
        """Get human-readable explanation for the recommended mode."""
        explanations = {
            "auto": "Low risk changes that can be safely applied automatically",
            "smart": "Medium risk changes that will be applied with extra verification",
            "review": "High risk changes that require manual review and approval",
        }

        base_explanation = explanations.get(risk.recommended_mode, "Unknown mode")

        if risk.reasons:
            reason_summary = "; ".join(risk.reasons[:3])  # Top 3 reasons
            if len(risk.reasons) > 3:
                reason_summary += f" (and {len(risk.reasons) - 3} more)"
            return f"{base_explanation}. Key factors: {reason_summary}"

        return base_explanation
