"""
RegressionPredictor — Predict Failures Before CI

Advanced regression prediction system that analyzes historical incident data
and file change patterns to predict the likelihood of failure BEFORE commits
and PRs are submitted. This enables NAVI to provide proactive warnings and
recommendations to prevent incidents.

Key Capabilities:
- Predict regression risk based on changed files
- Analyze historical failure patterns
- Generate confidence-scored predictions
- Provide preventive recommendations
- Risk-based testing suggestions
"""

import logging
import math
from collections import defaultdict, Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any
from .incident_store import Incident

logger = logging.getLogger(__name__)


@dataclass
class RegressionRisk:
    """Represents predicted regression risk for a set of changes"""

    overall_risk: float  # 0.0 - 1.0
    risk_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    confidence: float  # Confidence in the prediction
    risky_files: List[str]  # Files contributing to risk
    risk_factors: List[str]  # Human-readable risk explanations
    recommendations: List[str]  # Suggested actions
    historical_incidents: List[str]  # Related historical incidents
    predicted_failure_types: List[str]  # Likely failure modes


@dataclass
class FileRisk:
    """Risk assessment for individual files"""

    file_path: str
    risk_score: float
    failure_count: int
    last_failure: Optional[datetime]
    failure_types: List[str]
    failure_rate: float  # failures per change (estimated)
    risk_factors: List[str]


@dataclass
class PredictionModel:
    """Machine learning model for regression prediction"""

    model_type: str
    feature_weights: Dict[str, float]
    accuracy: float
    last_trained: datetime
    training_incidents: int


class RegressionPredictor:
    """
    Advanced regression prediction engine that analyzes historical patterns
    to predict failure risk before code changes are made, enabling proactive
    incident prevention.
    """

    def __init__(self, lookback_days: int = 90, min_incidents_for_prediction: int = 3):
        """
        Initialize the regression predictor

        Args:
            lookback_days: How many days of history to consider
            min_incidents_for_prediction: Minimum incidents needed for file risk calculation
        """
        self.lookback_days = lookback_days
        self.min_incidents_for_prediction = min_incidents_for_prediction
        self.prediction_model: Optional[PredictionModel] = None
        self.file_risk_cache: Dict[str, FileRisk] = {}
        self.last_model_update: Optional[datetime] = None
        logger.info("RegressionPredictor initialized for proactive failure prevention")

    def predict_regression_risk(
        self,
        changed_files: List[str],
        incidents: List[Incident],
        branch: str = "main",
        author: Optional[str] = None,
    ) -> RegressionRisk:
        """
        Predict regression risk for a set of changed files

        Args:
            changed_files: List of files being changed
            incidents: Historical incident data
            branch: Target branch for changes
            author: Author making changes (for personalized risk assessment)

        Returns:
            Comprehensive regression risk assessment
        """
        logger.info(
            f"Predicting regression risk for {len(changed_files)} changed files"
        )

        # Update prediction model if needed
        self._update_prediction_model(incidents)

        # Calculate individual file risks
        file_risks = self._calculate_file_risks(changed_files, incidents)

        # Calculate overall risk
        overall_risk = self._calculate_overall_risk(
            file_risks, changed_files, incidents, author
        )

        # Determine risk level
        risk_level = self._determine_risk_level(overall_risk)

        # Generate risk factors and explanations
        risk_factors = self._generate_risk_factors(
            file_risks, incidents, branch, author
        )

        # Find historical incidents
        historical_incidents = self._find_related_incidents(changed_files, incidents)

        # Predict likely failure types
        predicted_failures = self._predict_failure_types(
            file_risks, historical_incidents, incidents
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            risk_level, file_risks, risk_factors
        )

        # Calculate prediction confidence
        confidence = self._calculate_prediction_confidence(
            file_risks, len(historical_incidents)
        )

        return RegressionRisk(
            overall_risk=overall_risk,
            risk_level=risk_level,
            confidence=confidence,
            risky_files=[fr.file_path for fr in file_risks if fr.risk_score > 0.3],
            risk_factors=risk_factors,
            recommendations=recommendations,
            historical_incidents=[inc.id for inc in historical_incidents],
            predicted_failure_types=predicted_failures,
        )

    def _update_prediction_model(self, incidents: List[Incident]) -> None:
        """Update the prediction model with latest incident data"""
        # Only update if we have new data or it's been a while
        if (
            self.last_model_update is None
            or (datetime.now() - self.last_model_update).days >= 7
        ):

            logger.info("Updating regression prediction model")
            self.prediction_model = self._train_prediction_model(incidents)
            self.last_model_update = datetime.now()

            # Update file risk cache
            self._update_file_risk_cache(incidents)

    def _train_prediction_model(self, incidents: List[Incident]) -> PredictionModel:
        """Train a simple prediction model from historical data"""
        # This is a simplified model - in practice, you'd use ML libraries

        # Analyze feature importance from historical incidents
        feature_weights = {}

        # File-based features
        file_failure_counts = Counter()
        for incident in incidents:
            for file_path in incident.files:
                file_failure_counts[file_path] += 1

        # Calculate weights based on failure frequency
        max_failures = max(file_failure_counts.values()) if file_failure_counts else 1
        for file_path, count in file_failure_counts.items():
            feature_weights[f"file:{file_path}"] = count / max_failures

        # Branch-based features
        branch_failures = Counter(inc.branch for inc in incidents if inc.branch)
        max_branch_failures = max(branch_failures.values()) if branch_failures else 1
        for branch, count in branch_failures.items():
            feature_weights[f"branch:{branch}"] = count / max_branch_failures

        # Author-based features
        author_failures = Counter(inc.author for inc in incidents if inc.author)
        max_author_failures = max(author_failures.values()) if author_failures else 1
        for author, count in author_failures.items():
            feature_weights[f"author:{author}"] = count / max_author_failures

        # Calculate model accuracy (simplified)
        # In practice, you'd use cross-validation
        accuracy = min(0.9, len(incidents) / 100.0)  # More data = higher accuracy

        return PredictionModel(
            model_type="weighted_features",
            feature_weights=feature_weights,
            accuracy=accuracy,
            last_trained=datetime.now(),
            training_incidents=len(incidents),
        )

    def _update_file_risk_cache(self, incidents: List[Incident]) -> None:
        """Update cached risk scores for files"""
        self.file_risk_cache.clear()

        # Calculate risk for each file that appears in incidents
        file_incidents = defaultdict(list)
        for incident in incidents:
            for file_path in incident.files:
                file_incidents[file_path].append(incident)

        for file_path, file_incident_list in file_incidents.items():
            if len(file_incident_list) >= self.min_incidents_for_prediction:
                risk = self._calculate_individual_file_risk(
                    file_path, file_incident_list, incidents
                )
                self.file_risk_cache[file_path] = risk

    def _calculate_file_risks(
        self, changed_files: List[str], incidents: List[Incident]
    ) -> List[FileRisk]:
        """Calculate risk for each changed file"""
        file_risks = []

        for file_path in changed_files:
            if file_path in self.file_risk_cache:
                file_risks.append(self.file_risk_cache[file_path])
            else:
                # Calculate risk on-demand for files not in cache
                file_incidents = [inc for inc in incidents if file_path in inc.files]
                if len(file_incidents) >= 2:  # Lower threshold for changed files
                    risk = self._calculate_individual_file_risk(
                        file_path, file_incidents, incidents
                    )
                    file_risks.append(risk)
                else:
                    # New or rarely-changed file
                    risk = FileRisk(
                        file_path=file_path,
                        risk_score=0.1,  # Low baseline risk
                        failure_count=len(file_incidents),
                        last_failure=(
                            file_incidents[-1].timestamp if file_incidents else None
                        ),
                        failure_types=[inc.failure_type for inc in file_incidents],
                        failure_rate=0.0,
                        risk_factors=(
                            ["New or rarely-changed file"] if not file_incidents else []
                        ),
                    )
                    file_risks.append(risk)

        return sorted(file_risks, key=lambda x: x.risk_score, reverse=True)

    def _calculate_individual_file_risk(
        self,
        file_path: str,
        file_incidents: List[Incident],
        all_incidents: List[Incident],
    ) -> FileRisk:
        """Calculate risk metrics for an individual file"""
        # Basic metrics
        failure_count = len(file_incidents)
        last_failure = (
            max(inc.timestamp for inc in file_incidents) if file_incidents else None
        )
        failure_types = [inc.failure_type for inc in file_incidents]

        # Calculate failure rate (failures per estimated change)
        if file_incidents:
            time_span = max(inc.timestamp for inc in file_incidents) - min(
                inc.timestamp for inc in file_incidents
            )
            estimated_changes = max(
                1, int(time_span.days / 7)
            )  # Assume ~1 change per week
            failure_rate = failure_count / estimated_changes
        else:
            failure_rate = 0.0

        # Calculate base risk score
        risk_score = self._calculate_base_risk_score(
            failure_count, failure_rate, file_incidents
        )

        # Apply risk modifiers
        risk_score = self._apply_risk_modifiers(risk_score, file_path, file_incidents)

        # Generate risk factors
        risk_factors = self._generate_file_risk_factors(
            file_path, file_incidents, risk_score
        )

        return FileRisk(
            file_path=file_path,
            risk_score=min(1.0, risk_score),
            failure_count=failure_count,
            last_failure=last_failure,
            failure_types=list(set(failure_types)),
            failure_rate=failure_rate,
            risk_factors=risk_factors,
        )

    def _calculate_base_risk_score(
        self, failure_count: int, failure_rate: float, incidents: List[Incident]
    ) -> float:
        """Calculate base risk score from failure metrics"""
        # Frequency component (logarithmic to prevent dominance)
        frequency_score = math.log(1 + failure_count) / math.log(10)  # Log base 10

        # Rate component
        rate_score = min(1.0, failure_rate * 2)  # Cap at 1.0

        # Recency component
        if incidents:
            days_since_last = (
                datetime.now() - max(inc.timestamp for inc in incidents)
            ).days
            recency_score = max(
                0.0, 1.0 - (days_since_last / 30.0)
            )  # Decay over 30 days
        else:
            recency_score = 0.0

        # Weighted combination
        base_score = frequency_score * 0.4 + rate_score * 0.4 + recency_score * 0.2

        return min(1.0, base_score)

    def _apply_risk_modifiers(
        self, base_score: float, file_path: str, incidents: List[Incident]
    ) -> float:
        """Apply modifiers based on file type and incident patterns"""
        modified_score = base_score

        # File type modifiers
        if self._is_critical_file(file_path):
            modified_score *= 1.3  # Critical files have higher impact

        if self._is_test_file(file_path):
            modified_score *= 0.7  # Test failures are less critical for production

        # Pattern modifiers
        if incidents:
            # Severity modifier
            critical_incidents = [
                inc for inc in incidents if inc.severity == "CRITICAL"
            ]
            if len(critical_incidents) > len(incidents) * 0.5:
                modified_score *= 1.2

            # Consistency modifier (same failure type = higher risk)
            failure_types = [inc.failure_type for inc in incidents]
            if failure_types:
                most_common_count = Counter(failure_types).most_common(1)[0][1]
                consistency = most_common_count / len(failure_types)
                modified_score *= 1.0 + consistency * 0.2

        return min(1.0, modified_score)

    def _calculate_overall_risk(
        self,
        file_risks: List[FileRisk],
        changed_files: List[str],
        incidents: List[Incident],
        author: Optional[str],
    ) -> float:
        """Calculate overall regression risk from individual file risks"""
        if not file_risks:
            return 0.1  # Baseline risk for any change

        # Primary risk from file risks (weighted by severity)
        weighted_risk = 0.0
        total_weight = 0.0

        for file_risk in file_risks:
            weight = 1.0
            if self._is_critical_file(file_risk.file_path):
                weight = 2.0  # Critical files matter more

            weighted_risk += file_risk.risk_score * weight
            total_weight += weight

        primary_risk = weighted_risk / total_weight if total_weight > 0 else 0.0

        # Apply contextual modifiers
        overall_risk = primary_risk

        # Author history modifier
        if author and self.prediction_model:
            author_feature = f"author:{author}"
            if author_feature in self.prediction_model.feature_weights:
                author_risk = self.prediction_model.feature_weights[author_feature]
                overall_risk = overall_risk * 0.7 + author_risk * 0.3

        # Change size modifier (more files = higher risk)
        size_modifier = min(1.2, 1.0 + len(changed_files) * 0.02)
        overall_risk *= size_modifier

        # Recent incident density (if system is already unstable)
        recent_incidents = [
            inc for inc in incidents if (datetime.now() - inc.timestamp).days <= 7
        ]
        if len(recent_incidents) > 5:
            overall_risk *= 1.1  # System instability modifier

        return min(1.0, overall_risk)

    def _determine_risk_level(self, overall_risk: float) -> str:
        """Convert risk score to categorical risk level"""
        if overall_risk >= 0.8:
            return "CRITICAL"
        elif overall_risk >= 0.6:
            return "HIGH"
        elif overall_risk >= 0.4:
            return "MEDIUM"
        else:
            return "LOW"

    def _generate_risk_factors(
        self,
        file_risks: List[FileRisk],
        incidents: List[Incident],
        branch: str,
        author: Optional[str],
    ) -> List[str]:
        """Generate human-readable risk factor explanations"""
        factors = []

        # High-risk files
        high_risk_files = [fr for fr in file_risks if fr.risk_score > 0.5]
        if high_risk_files:
            factors.append(
                f"{len(high_risk_files)} files with high historical failure rates"
            )

        # Recent failures
        recent_failures = [
            fr
            for fr in file_risks
            if fr.last_failure and (datetime.now() - fr.last_failure).days <= 7
        ]
        if recent_failures:
            factors.append(
                f"{len(recent_failures)} files failed recently (last 7 days)"
            )

        # Critical file involvement
        critical_files = [
            fr for fr in file_risks if self._is_critical_file(fr.file_path)
        ]
        if critical_files:
            factors.append(
                f"{len(critical_files)} critical system files being modified"
            )

        # Branch risk
        if branch in ["main", "master", "production"]:
            factors.append("Changes targeting production branch")

        # Author pattern (if applicable)
        if author:
            author_incidents = [inc for inc in incidents if inc.author == author]
            if len(author_incidents) > 5:
                factors.append(
                    f"Author has {len(author_incidents)} historical incidents"
                )

        # Failure type patterns
        common_failure_types = []
        for file_risk in file_risks:
            if file_risk.failure_types:
                common_failure_types.extend(file_risk.failure_types)

        if common_failure_types:
            type_counts = Counter(common_failure_types)
            most_common = type_counts.most_common(2)
            if most_common[0][1] > 1:
                factors.append(f"Common failure pattern: {most_common[0][0]}")

        return factors[:5]  # Limit to top 5 factors

    def _find_related_incidents(
        self, changed_files: List[str], incidents: List[Incident]
    ) -> List[Incident]:
        """Find historical incidents related to the changed files"""
        related = []

        for incident in incidents:
            # Check if incident involves any of the changed files
            if any(file_path in incident.files for file_path in changed_files):
                related.append(incident)

        # Sort by relevance (more recent = more relevant)
        return sorted(related, key=lambda x: x.timestamp, reverse=True)[:10]

    def _predict_failure_types(
        self,
        file_risks: List[FileRisk],
        related_incidents: List[Incident],
        all_incidents: List[Incident],
    ) -> List[str]:
        """Predict likely failure types based on historical patterns"""
        failure_type_counts: Counter[str] = Counter()

        # Count failure types from file risks
        for file_risk in file_risks:
            for failure_type in file_risk.failure_types:
                failure_type_counts[failure_type] += int(
                    file_risk.risk_score * 100
                )  # Convert to int

        # Count failure types from related incidents (weighted by recency)
        for incident in related_incidents:
            days_ago = (datetime.now() - incident.timestamp).days
            recency_weight = max(0.1, 1.0 - days_ago / 90.0)
            failure_type_counts[incident.failure_type] += int(
                recency_weight * 100
            )  # Convert to int

        # Return top predicted failure types
        return [ft for ft, _ in failure_type_counts.most_common(3)]

    def _generate_recommendations(
        self, risk_level: str, file_risks: List[FileRisk], risk_factors: List[str]
    ) -> List[str]:
        """Generate actionable recommendations based on risk assessment"""
        recommendations = []

        if risk_level == "CRITICAL":
            recommendations.append(
                "🚨 CRITICAL RISK: Consider deferring this change or adding extensive testing"
            )
            recommendations.append("🔒 Require senior engineer review before merge")
            recommendations.append("📊 Run full regression test suite")

        elif risk_level == "HIGH":
            recommendations.append("⚠️ HIGH RISK: Add extra testing and code review")
            recommendations.append("🧪 Run integration tests for affected components")
            recommendations.append("📈 Monitor closely after deployment")

        elif risk_level == "MEDIUM":
            recommendations.append("⚡ MEDIUM RISK: Standard testing recommended")
            recommendations.append("👥 Ensure proper code review")

        # Specific recommendations based on file types
        high_risk_files = [fr for fr in file_risks if fr.risk_score > 0.5]
        if high_risk_files:
            test_files = [
                fr.file_path
                for fr in high_risk_files
                if self._is_test_file(fr.file_path)
            ]
            if test_files:
                recommendations.append(
                    f"🧪 Pay special attention to test files: {len(test_files)} have high failure rates"
                )

            critical_files = [
                fr.file_path
                for fr in high_risk_files
                if self._is_critical_file(fr.file_path)
            ]
            if critical_files:
                recommendations.append(
                    "🏗️ Critical files modified - consider feature flags or gradual rollout"
                )

        # Recommendations based on risk factors
        if any("recent" in factor.lower() for factor in risk_factors):
            recommendations.append(
                "🕐 Recent failures detected - investigate root cause before proceeding"
            )

        if any("author" in factor.lower() for factor in risk_factors):
            recommendations.append(
                "👨‍💻 Consider pair programming or additional code review"
            )

        return recommendations[:6]  # Limit to top 6 recommendations

    def _calculate_prediction_confidence(
        self, file_risks: List[FileRisk], historical_incident_count: int
    ) -> float:
        """Calculate confidence in the regression prediction"""
        # Base confidence from model accuracy
        if self.prediction_model:
            base_confidence = self.prediction_model.accuracy
        else:
            base_confidence = 0.5

        # Data quality factors
        data_confidence = min(
            1.0, historical_incident_count / 10.0
        )  # More history = higher confidence

        # File risk confidence (based on how many files we have data for)
        files_with_data = len([fr for fr in file_risks if fr.failure_count > 0])
        total_files = len(file_risks)
        coverage_confidence = files_with_data / total_files if total_files > 0 else 0.0

        # Combined confidence
        overall_confidence = (
            base_confidence * 0.4 + data_confidence * 0.4 + coverage_confidence * 0.2
        )

        return min(1.0, overall_confidence)

    def _is_critical_file(self, file_path: str) -> bool:
        """Determine if a file is critical to system operation"""
        critical_indicators = [
            "/main/",
            "/core/",
            "/api/",
            "/server/",
            "config",
            "database",
            "auth",
            "security",
            "index.js",
            "main.py",
            "__init__.py",
        ]
        return any(indicator in file_path.lower() for indicator in critical_indicators)

    def _is_test_file(self, file_path: str) -> bool:
        """Determine if a file is a test file"""
        test_indicators = ["test", "spec", "__test__", ".test.", ".spec."]
        return any(indicator in file_path.lower() for indicator in test_indicators)

    def _generate_file_risk_factors(
        self, file_path: str, incidents: List[Any], risk_score: float
    ) -> List[str]:
        """Generate human-readable risk factors for a file"""
        factors = []

        if len(incidents) > 5:
            factors.append(f"High failure history ({len(incidents)} incidents)")
        elif len(incidents) > 2:
            factors.append(f"Multiple failures ({len(incidents)} incidents)")

        if risk_score > 0.8:
            factors.append("Very high risk score")
        elif risk_score > 0.6:
            factors.append("High risk score")
        elif risk_score > 0.4:
            factors.append("Medium risk score")

        # Check for recent failures
        recent_incidents = [
            inc for inc in incidents if (datetime.now() - inc.timestamp).days < 7
        ]
        if recent_incidents:
            factors.append(f"Recent failures ({len(recent_incidents)} in last week)")

        # Check file type specific risks
        if file_path.endswith((".py", ".js", ".ts", ".java")):
            factors.append("Source code file")
        elif file_path.endswith((".yml", ".yaml", ".json", ".xml")):
            factors.append("Configuration file")
        elif "test" in file_path.lower():
            factors.append("Test file")

        return factors

    def get_model_statistics(self) -> Dict[str, Any]:
        """Get statistics about the prediction model"""
        if not self.prediction_model:
            return {"status": "not_trained"}

        return {
            "model_type": self.prediction_model.model_type,
            "accuracy": self.prediction_model.accuracy,
            "last_trained": self.prediction_model.last_trained.isoformat(),
            "training_incidents": self.prediction_model.training_incidents,
            "feature_count": len(self.prediction_model.feature_weights),
            "cached_file_risks": len(self.file_risk_cache),
        }
