"""
Risk Assessment Service - AI-powered patch safety analysis with confidence scoring
Provides enterprise-grade risk classification for code changes with detailed impact analysis
"""

import re
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk classification levels for code changes"""

    MINIMAL = "minimal"  # Safe changes (comments, docs, formatting)
    LOW = "low"  # Simple logic changes, variable renames
    MEDIUM = "medium"  # Function modifications, new features
    HIGH = "high"  # API changes, database operations
    CRITICAL = "critical"  # Security, auth, core infrastructure


@dataclass
class RiskFactor:
    """Individual risk factor with scoring and reasoning"""

    factor: str
    score: float  # 0.0 to 1.0
    reasoning: str
    category: str
    examples: List[str]


@dataclass
class RiskAssessment:
    """Complete risk analysis for a code patch"""

    overall_risk: RiskLevel
    confidence_score: float  # 0.0 to 1.0 (how confident we are in the assessment)
    risk_score: float  # 0.0 to 1.0 (aggregated risk level)
    factors: List[RiskFactor]
    impact_analysis: Dict[str, Any]
    recommendations: List[str]
    requires_review: bool
    safe_to_auto_apply: bool


class RiskAssessmentService:
    """
    Enterprise-grade risk assessment for code patches
    Analyzes changes for potential security, stability, and correctness issues
    """

    def __init__(self):
        self.critical_patterns = {
            # Security-related patterns
            "auth_changes": [
                r"password",
                r"token",
                r"secret",
                r"auth",
                r"login",
                r"session",
                r"jwt",
                r"oauth",
                r"permissions",
                r"roles",
                r"security",
            ],
            "database_operations": [
                r"DELETE\s+FROM",
                r"DROP\s+TABLE",
                r"ALTER\s+TABLE",
                r"CREATE\s+INDEX",
                r"TRUNCATE",
                r"\.execute\(",
                r"\.query\(",
                r"raw_sql",
            ],
            "system_calls": [
                r"os\.system",
                r"subprocess",
                r"exec",
                r"eval",
                r"__import__",
                r'open\(.*[\'"]w',
                r"file\.write",
                r"fs\.write",
            ],
            "network_operations": [
                r"requests\.",
                r"urllib",
                r"socket",
                r"http\.client",
                r"fetch\(",
                r"axios\.",
            ],
            "core_infrastructure": [
                r"config",
                r"settings",
                r"environment",
                r"deployment",
                r"docker",
                r"kubernetes",
                r"nginx",
                r"apache",
            ],
        }

        self.medium_risk_patterns = {
            "api_changes": [
                r"@app\.route",
                r"@api\.",
                r"endpoint",
                r"handler",
                r"def\s+\w+_api",
                r"class\s+\w+API",
            ],
            "data_structures": [
                r"class\s+\w+",
                r"def\s+__init__",
                r"@dataclass",
                r"schema",
                r"model",
                r"entity",
            ],
            "business_logic": [
                r"calculate",
                r"process",
                r"validate",
                r"transform",
                r"algorithm",
                r"logic",
                r"rule",
            ],
        }

        self.low_risk_patterns = {
            "formatting": [
                r"^\s*#",
                r'"""',
                r"'''",
                r"//\s*",
                r"/\*",
                r"\*/",
                r"console\.log",
                r"print\(",
                r"logger\.",
            ],
            "simple_changes": [
                r"variable\s*=",
                r"const\s+\w+",
                r"let\s+\w+",
                r"import\s+",
                r"from\s+.*\s+import",
            ],
        }

    def assess_patch(self, patch_content: str, file_paths: List[str]) -> RiskAssessment:
        """
        Perform comprehensive risk assessment on a code patch

        Args:
            patch_content: The unified diff content
            file_paths: List of files being modified

        Returns:
            Complete risk assessment with scoring and recommendations
        """
        try:
            # Parse patch for analysis
            patch_lines = patch_content.split("\n")
            added_lines = [
                line[1:]
                for line in patch_lines
                if line.startswith("+") and not line.startswith("+++")
            ]
            removed_lines = [
                line[1:]
                for line in patch_lines
                if line.startswith("-") and not line.startswith("---")
            ]

            # Collect risk factors
            factors = []

            # Analyze file paths
            factors.extend(self._analyze_file_paths(file_paths))

            # Analyze code changes
            factors.extend(self._analyze_code_changes(added_lines, removed_lines))

            # Analyze change magnitude
            factors.extend(self._analyze_change_magnitude(added_lines, removed_lines))

            # Analyze dependencies
            factors.extend(self._analyze_dependencies(patch_content))

            # Calculate overall risk
            risk_score = self._calculate_risk_score(factors)
            overall_risk = self._determine_risk_level(risk_score)
            confidence_score = self._calculate_confidence(
                factors, len(added_lines) + len(removed_lines)
            )

            # Generate impact analysis
            impact_analysis = self._generate_impact_analysis(
                factors, file_paths, len(added_lines)
            )

            # Generate recommendations
            recommendations = self._generate_recommendations(factors, overall_risk)

            # Determine review requirements
            requires_review = (
                overall_risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]
                or confidence_score < 0.7
            )
            safe_to_auto_apply = (
                overall_risk == RiskLevel.MINIMAL and confidence_score > 0.9
            )

            return RiskAssessment(
                overall_risk=overall_risk,
                confidence_score=confidence_score,
                risk_score=risk_score,
                factors=factors,
                impact_analysis=impact_analysis,
                recommendations=recommendations,
                requires_review=requires_review,
                safe_to_auto_apply=safe_to_auto_apply,
            )

        except Exception as e:
            logger.error(f"Risk assessment failed: {str(e)}")
            # Return conservative assessment on error
            return RiskAssessment(
                overall_risk=RiskLevel.HIGH,
                confidence_score=0.3,
                risk_score=0.8,
                factors=[
                    RiskFactor(
                        "analysis_error",
                        0.8,
                        f"Assessment failed: {str(e)}",
                        "system",
                        [],
                    )
                ],
                impact_analysis={"error": "Risk analysis failed"},
                recommendations=["Manual review required due to assessment failure"],
                requires_review=True,
                safe_to_auto_apply=False,
            )

    def _analyze_file_paths(self, file_paths: List[str]) -> List[RiskFactor]:
        """Analyze risk based on which files are being modified"""
        factors = []

        for file_path in file_paths:
            path_lower = file_path.lower()

            # Critical files
            if any(
                critical in path_lower
                for critical in [
                    "config",
                    "settings",
                    ".env",
                    "security",
                    "auth",
                    "password",
                    "docker",
                    "deploy",
                    "infra",
                    "migration",
                    "schema",
                ]
            ):
                factors.append(
                    RiskFactor(
                        factor="critical_file_modification",
                        score=0.9,
                        reasoning=f"Modifying critical infrastructure file: {file_path}",
                        category="infrastructure",
                        examples=[file_path],
                    )
                )

            # Core system files
            elif any(
                core in path_lower
                for core in ["main", "app", "server", "api", "core", "base", "models"]
            ):
                factors.append(
                    RiskFactor(
                        factor="core_system_modification",
                        score=0.6,
                        reasoning=f"Modifying core system file: {file_path}",
                        category="system",
                        examples=[file_path],
                    )
                )

        return factors

    def _analyze_code_changes(
        self, added_lines: List[str], removed_lines: List[str]
    ) -> List[RiskFactor]:
        """Analyze the actual code changes for risk patterns"""
        factors = []
        all_lines = added_lines + removed_lines

        for category, patterns in self.critical_patterns.items():
            matches = []
            for line in all_lines:
                for pattern in patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        matches.append(line.strip())

            if matches:
                factors.append(
                    RiskFactor(
                        factor=f"critical_{category}",
                        score=0.85,
                        reasoning=f"Critical {category.replace('_', ' ')} detected in code changes",
                        category="security",
                        examples=matches[:3],  # Limit examples
                    )
                )

        for category, patterns in self.medium_risk_patterns.items():
            matches = []
            for line in all_lines:
                for pattern in patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        matches.append(line.strip())

            if matches:
                factors.append(
                    RiskFactor(
                        factor=f"medium_{category}",
                        score=0.5,
                        reasoning=f"Medium risk {category.replace('_', ' ')} changes detected",
                        category="functionality",
                        examples=matches[:3],
                    )
                )

        return factors

    def _analyze_change_magnitude(
        self, added_lines: List[str], removed_lines: List[str]
    ) -> List[RiskFactor]:
        """Analyze risk based on the size and scope of changes"""
        factors = []

        total_changes = len(added_lines) + len(removed_lines)

        if total_changes > 100:
            factors.append(
                RiskFactor(
                    factor="large_change_set",
                    score=0.7,
                    reasoning=f"Large change set with {total_changes} modified lines",
                    category="magnitude",
                    examples=[
                        f"{len(added_lines)} additions, {len(removed_lines)} deletions"
                    ],
                )
            )
        elif total_changes > 50:
            factors.append(
                RiskFactor(
                    factor="medium_change_set",
                    score=0.4,
                    reasoning=f"Medium change set with {total_changes} modified lines",
                    category="magnitude",
                    examples=[
                        f"{len(added_lines)} additions, {len(removed_lines)} deletions"
                    ],
                )
            )

        # Analyze deletion ratio
        if len(removed_lines) > 0:
            deletion_ratio = len(removed_lines) / total_changes
            if deletion_ratio > 0.5:
                factors.append(
                    RiskFactor(
                        factor="high_deletion_ratio",
                        score=0.6,
                        reasoning=f"High deletion ratio ({deletion_ratio:.1%}) may indicate refactoring or removal of functionality",
                        category="magnitude",
                        examples=[
                            f"{len(removed_lines)} deletions out of {total_changes} total changes"
                        ],
                    )
                )

        return factors

    def _analyze_dependencies(self, patch_content: str) -> List[RiskFactor]:
        """Analyze dependency changes and imports"""
        factors = []

        # Look for new imports or dependency changes
        import_changes = re.findall(
            r"^[+-].*(?:import|require|from)\s+[\w\.\-]+", patch_content, re.MULTILINE
        )

        if import_changes:
            factors.append(
                RiskFactor(
                    factor="dependency_changes",
                    score=0.3,
                    reasoning="Code changes include new imports or dependency modifications",
                    category="dependencies",
                    examples=import_changes[:3],
                )
            )

        return factors

    def _calculate_risk_score(self, factors: List[RiskFactor]) -> float:
        """Calculate overall risk score from individual factors"""
        if not factors:
            return 0.1  # Minimal risk for empty changes

        # Weighted scoring - highest scores dominate
        scores = [factor.score for factor in factors]
        max_score = max(scores)
        avg_score = sum(scores) / len(scores)

        # Combine max and average with bias toward max
        return min(1.0, max_score * 0.7 + avg_score * 0.3)

    def _determine_risk_level(self, risk_score: float) -> RiskLevel:
        """Convert numeric risk score to categorical risk level"""
        if risk_score >= 0.8:
            return RiskLevel.CRITICAL
        elif risk_score >= 0.6:
            return RiskLevel.HIGH
        elif risk_score >= 0.3:
            return RiskLevel.MEDIUM
        elif risk_score >= 0.1:
            return RiskLevel.LOW
        else:
            return RiskLevel.MINIMAL

    def _calculate_confidence(
        self, factors: List[RiskFactor], total_lines: int
    ) -> float:
        """Calculate confidence in the risk assessment"""
        # Base confidence on analysis completeness
        base_confidence = 0.8

        # Reduce confidence for very small changes (less context)
        if total_lines < 5:
            base_confidence -= 0.2

        # Reduce confidence for very large changes (harder to analyze)
        if total_lines > 200:
            base_confidence -= 0.1

        # Increase confidence if we found specific risk patterns
        if len(factors) > 3:
            base_confidence += 0.1

        return max(0.3, min(1.0, base_confidence))

    def _generate_impact_analysis(
        self, factors: List[RiskFactor], file_paths: List[str], additions: int
    ) -> Dict[str, Any]:
        """Generate detailed impact analysis"""
        categories = {}
        for factor in factors:
            if factor.category not in categories:
                categories[factor.category] = []
            categories[factor.category].append(factor.factor)

        return {
            "files_affected": len(file_paths),
            "lines_added": additions,
            "risk_categories": categories,
            "highest_risk_factor": (
                max(factors, key=lambda f: f.score).factor if factors else None
            ),
            "critical_areas": [f.factor for f in factors if f.score > 0.7],
            "affected_systems": list(set(f.category for f in factors)),
        }

    def _generate_recommendations(
        self, factors: List[RiskFactor], risk_level: RiskLevel
    ) -> List[str]:
        """Generate actionable recommendations based on risk assessment"""
        recommendations = []

        if risk_level == RiskLevel.CRITICAL:
            recommendations.extend(
                [
                    "🚨 Critical risk detected - require senior developer review",
                    "Consider breaking changes into smaller, focused patches",
                    "Run comprehensive test suite before applying",
                    "Consider staging environment deployment first",
                ]
            )
        elif risk_level == RiskLevel.HIGH:
            recommendations.extend(
                [
                    "⚠️ High risk - peer review recommended",
                    "Verify test coverage for modified code",
                    "Consider rollback plan before applying",
                ]
            )
        elif risk_level == RiskLevel.MEDIUM:
            recommendations.extend(
                [
                    "📋 Medium risk - basic review recommended",
                    "Ensure relevant tests are updated",
                ]
            )

        # Add specific recommendations based on risk factors
        for factor in factors:
            if "security" in factor.category or "auth" in factor.factor:
                recommendations.append(
                    "🔒 Security review required for authentication/authorization changes"
                )
            elif "database" in factor.factor:
                recommendations.append(
                    "💾 Database backup recommended before schema changes"
                )
            elif "infrastructure" in factor.category:
                recommendations.append(
                    "🏗️ Infrastructure changes require DevOps review"
                )

        return list(set(recommendations))  # Remove duplicates
