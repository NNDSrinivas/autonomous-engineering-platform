"""
Gated Approval System for NAVI

Implements multi-level approval workflow for:
1. Security-sensitive operations (database changes, auth, encryption)
2. Complex distributed systems changes
3. Operations that affect production or critical paths
4. Changes based on organization-specific policies

Approval Gates:
- NONE: Auto-approve (simple, low-risk operations)
- USER: Requires user confirmation (default)
- TEAM_LEAD: Requires team lead approval
- SECURITY: Requires security team review
- MULTI_PARTY: Requires multiple approvals

This integrates with the human-in-the-loop flow to ensure
appropriate oversight for risky changes.
"""

import os
import json
import logging
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import re

logger = logging.getLogger(__name__)


class ApprovalLevel(Enum):
    """Levels of approval required."""

    NONE = "none"  # Auto-approve
    USER = "user"  # User confirmation
    TEAM_LEAD = "team_lead"  # Team lead approval
    SECURITY = "security"  # Security team review
    MULTI_PARTY = "multi"  # Multiple approvers


class RiskCategory(Enum):
    """Categories of risk for operations."""

    SECURITY = "security"  # Auth, encryption, secrets
    DATA = "data"  # Database, data manipulation
    INFRASTRUCTURE = "infrastructure"  # Cloud, servers, deployment
    FINANCIAL = "financial"  # Payments, billing, pricing
    COMPLIANCE = "compliance"  # GDPR, HIPAA, SOC2
    PRODUCTION = "production"  # Direct production changes
    THIRD_PARTY = "third_party"  # External API integrations
    CUSTOM = "custom"  # Organization-defined


@dataclass
class RiskIndicator:
    """A pattern that indicates risk."""

    id: str
    category: RiskCategory
    pattern: str  # Regex pattern to match
    description: str
    severity: int  # 1-10, higher = more risky
    required_approval: ApprovalLevel
    languages: List[str] = field(default_factory=list)  # Empty = all languages


@dataclass
class ApprovalRequest:
    """A request for approval on a gated operation."""

    id: str
    operation_type: str  # "file_create", "file_edit", "command", etc.
    content: str
    filepath: Optional[str] = None

    # Risk assessment
    risk_categories: List[RiskCategory] = field(default_factory=list)
    risk_score: int = 0  # Aggregate risk score
    risk_reasons: List[str] = field(default_factory=list)

    # Required approval
    required_level: ApprovalLevel = ApprovalLevel.USER
    required_approvers: List[str] = field(default_factory=list)

    # Status
    status: str = "pending"  # pending, approved, rejected, expired
    approvals: List[Dict] = field(default_factory=list)  # Who approved
    rejections: List[Dict] = field(default_factory=list)  # Who rejected

    # Context
    org_id: Optional[str] = None
    team_id: Optional[str] = None
    user_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None


class RiskDetector:
    """
    Detects risk patterns in code and operations.
    """

    # Default risk patterns - organizations can add their own
    DEFAULT_PATTERNS: List[RiskIndicator] = [
        # Security risks
        RiskIndicator(
            id="auth_bypass",
            category=RiskCategory.SECURITY,
            pattern=r"skip.{0,10}auth|bypass.{0,10}auth|disable.{0,10}auth|auth.{0,10}false",
            description="Potential authentication bypass",
            severity=9,
            required_approval=ApprovalLevel.SECURITY,
        ),
        RiskIndicator(
            id="hardcoded_secret",
            category=RiskCategory.SECURITY,
            pattern=r"(password|secret|api[_-]?key|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]",
            description="Hardcoded secret or credential",
            severity=8,
            required_approval=ApprovalLevel.SECURITY,
        ),
        RiskIndicator(
            id="eval_exec",
            category=RiskCategory.SECURITY,
            pattern=r"\b(eval|exec|execfile|compile)\s*\(",
            description="Dynamic code execution (eval/exec)",
            severity=7,
            required_approval=ApprovalLevel.SECURITY,
            languages=["python"],
        ),
        RiskIndicator(
            id="sql_injection",
            category=RiskCategory.SECURITY,
            pattern=r"(execute|cursor\.execute|query)\s*\(\s*['\"].*?\%s|\{.*?\}|f['\"]",
            description="Potential SQL injection vulnerability",
            severity=8,
            required_approval=ApprovalLevel.SECURITY,
        ),
        RiskIndicator(
            id="command_injection",
            category=RiskCategory.SECURITY,
            pattern=r"(subprocess|os\.system|os\.popen|shell=True)",
            description="Shell command execution",
            severity=6,
            required_approval=ApprovalLevel.TEAM_LEAD,
        ),
        RiskIndicator(
            id="crypto_custom",
            category=RiskCategory.SECURITY,
            pattern=r"(md5|sha1|des|blowfish|arc4|rc4)\s*\(|custom.{0,10}(encrypt|hash)",
            description="Weak or custom cryptography",
            severity=7,
            required_approval=ApprovalLevel.SECURITY,
        ),
        # Data risks
        RiskIndicator(
            id="delete_cascade",
            category=RiskCategory.DATA,
            pattern=r"delete.*cascade|truncate|drop\s+table|drop\s+database",
            description="Destructive database operation",
            severity=9,
            required_approval=ApprovalLevel.TEAM_LEAD,
        ),
        RiskIndicator(
            id="migration_dangerous",
            category=RiskCategory.DATA,
            pattern=r"alter\s+table.*drop|remove.*column|delete.*migration",
            description="Dangerous database migration",
            severity=7,
            required_approval=ApprovalLevel.TEAM_LEAD,
        ),
        RiskIndicator(
            id="bulk_update",
            category=RiskCategory.DATA,
            pattern=r"update.*where\s+1\s*=\s*1|update.*set.*without.*where",
            description="Bulk data update without proper filtering",
            severity=8,
            required_approval=ApprovalLevel.TEAM_LEAD,
        ),
        # Infrastructure risks
        RiskIndicator(
            id="production_config",
            category=RiskCategory.INFRASTRUCTURE,
            pattern=r"production|prod\.env|PRODUCTION|--prod",
            description="Production environment configuration",
            severity=6,
            required_approval=ApprovalLevel.TEAM_LEAD,
        ),
        RiskIndicator(
            id="aws_root",
            category=RiskCategory.INFRASTRUCTURE,
            pattern=r"aws.{0,20}root|arn:aws:iam::\d+:root",
            description="AWS root account usage",
            severity=9,
            required_approval=ApprovalLevel.SECURITY,
        ),
        RiskIndicator(
            id="firewall_any",
            category=RiskCategory.INFRASTRUCTURE,
            pattern=r"0\.0\.0\.0/0|allow.{0,10}any|inbound.{0,20}\*",
            description="Open firewall rule",
            severity=7,
            required_approval=ApprovalLevel.SECURITY,
        ),
        RiskIndicator(
            id="privilege_escalation",
            category=RiskCategory.INFRASTRUCTURE,
            pattern=r"sudo|chmod\s+777|chown\s+root|setuid|capabilities",
            description="Privilege escalation",
            severity=7,
            required_approval=ApprovalLevel.TEAM_LEAD,
        ),
        # Financial risks
        RiskIndicator(
            id="payment_logic",
            category=RiskCategory.FINANCIAL,
            pattern=r"charge|refund|payment|billing|price|subscription|invoice",
            description="Payment/billing logic change",
            severity=6,
            required_approval=ApprovalLevel.TEAM_LEAD,
        ),
        # Compliance risks
        RiskIndicator(
            id="pii_handling",
            category=RiskCategory.COMPLIANCE,
            pattern=r"(ssn|social.security|passport|license.number|date.of.birth|dob)",
            description="PII data handling",
            severity=6,
            required_approval=ApprovalLevel.TEAM_LEAD,
        ),
        RiskIndicator(
            id="logging_sensitive",
            category=RiskCategory.COMPLIANCE,
            pattern=r"(log|print|console\.log).{0,30}(password|token|secret|credit.card)",
            description="Logging sensitive data",
            severity=7,
            required_approval=ApprovalLevel.SECURITY,
        ),
        # Third party risks
        RiskIndicator(
            id="new_dependency",
            category=RiskCategory.THIRD_PARTY,
            pattern=r"pip\s+install|npm\s+install|yarn\s+add|go\s+get|cargo\s+add",
            description="New dependency installation",
            severity=4,
            required_approval=ApprovalLevel.USER,
        ),
        RiskIndicator(
            id="webhook_external",
            category=RiskCategory.THIRD_PARTY,
            pattern=r"webhook|callback.{0,10}url|external.{0,10}api",
            description="External webhook/callback",
            severity=5,
            required_approval=ApprovalLevel.USER,
        ),
    ]

    def __init__(self, custom_patterns: List[RiskIndicator] = None):
        self.patterns = list(self.DEFAULT_PATTERNS)
        if custom_patterns:
            self.patterns.extend(custom_patterns)

    def detect_risks(
        self,
        content: str,
        filepath: Optional[str] = None,
        language: Optional[str] = None,
    ) -> List[Dict]:
        """
        Detect risk patterns in content.
        Returns list of detected risks with details.
        """
        detected = []

        # Determine language from filepath if not provided
        if not language and filepath:
            ext = Path(filepath).suffix.lower()
            language = {
                ".py": "python",
                ".js": "javascript",
                ".ts": "typescript",
                ".go": "go",
                ".java": "java",
                ".rb": "ruby",
                ".sh": "bash",
                ".sql": "sql",
            }.get(ext)

        content_lower = content.lower()

        for pattern in self.patterns:
            # Skip patterns that don't apply to this language
            if pattern.languages and language and language not in pattern.languages:
                continue

            # Search for pattern
            try:
                matches = re.findall(pattern.pattern, content_lower, re.IGNORECASE)
                if matches:
                    detected.append(
                        {
                            "id": pattern.id,
                            "category": pattern.category,
                            "description": pattern.description,
                            "severity": pattern.severity,
                            "required_approval": pattern.required_approval,
                            "matches": matches[:3],  # First 3 matches
                        }
                    )
            except re.error as e:
                logger.warning(f"Invalid regex pattern {pattern.id}: {e}")

        return detected


class ApprovalPolicyEngine:
    """
    Evaluates operations against organization-specific approval policies.
    """

    def __init__(self):
        self.detector = RiskDetector()
        self.org_policies: Dict[str, Dict] = {}  # org_id -> policy

    def load_org_policy(self, org_id: str, policy: Dict) -> None:
        """Load organization-specific approval policy."""
        self.org_policies[org_id] = policy

        # Add custom patterns from policy
        if policy.get("custom_patterns"):
            custom = [
                RiskIndicator(
                    id=p["id"],
                    category=RiskCategory[p.get("category", "CUSTOM").upper()],
                    pattern=p["pattern"],
                    description=p.get("description", "Custom policy"),
                    severity=p.get("severity", 5),
                    required_approval=ApprovalLevel[p.get("approval", "USER").upper()],
                    languages=p.get("languages", []),
                )
                for p in policy["custom_patterns"]
            ]
            self.detector.patterns.extend(custom)

    def evaluate(
        self,
        operation_type: str,
        content: str,
        filepath: Optional[str] = None,
        org_id: Optional[str] = None,
        team_id: Optional[str] = None,
    ) -> ApprovalRequest:
        """
        Evaluate an operation and determine required approval.
        """
        request_id = hashlib.sha256(
            f"{operation_type}:{filepath}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        # Detect risks
        risks = self.detector.detect_risks(content, filepath)

        # Aggregate risk data
        risk_categories = list(set(r["category"] for r in risks))
        risk_score = sum(r["severity"] for r in risks)
        risk_reasons = [r["description"] for r in risks]

        # Determine required approval level
        required_level = ApprovalLevel.USER  # Default
        if risks:
            # Use highest required approval from detected risks
            for risk in risks:
                level = risk["required_approval"]
                if level == ApprovalLevel.MULTI_PARTY:
                    required_level = ApprovalLevel.MULTI_PARTY
                    break
                elif level == ApprovalLevel.SECURITY and required_level not in [
                    ApprovalLevel.MULTI_PARTY
                ]:
                    required_level = ApprovalLevel.SECURITY
                elif level == ApprovalLevel.TEAM_LEAD and required_level not in [
                    ApprovalLevel.MULTI_PARTY,
                    ApprovalLevel.SECURITY,
                ]:
                    required_level = ApprovalLevel.TEAM_LEAD

        # Apply org-specific policies
        if org_id and org_id in self.org_policies:
            policy = self.org_policies[org_id]

            # Check file-based rules
            if filepath and policy.get("protected_paths"):
                for protected in policy["protected_paths"]:
                    if re.match(protected["pattern"], filepath):
                        required_level = ApprovalLevel[
                            protected.get("approval", "SECURITY").upper()
                        ]
                        risk_reasons.append(
                            f"Protected path: {protected.get('reason', filepath)}"
                        )

            # Check operation type rules
            if policy.get("operation_rules", {}).get(operation_type):
                rule = policy["operation_rules"][operation_type]
                if ApprovalLevel[rule["approval"].upper()].value > required_level.value:
                    required_level = ApprovalLevel[rule["approval"].upper()]

        # Auto-approve if no risks detected
        if not risks and operation_type not in ["command", "file_delete"]:
            required_level = ApprovalLevel.USER  # Still needs user confirmation

        # Create request
        request = ApprovalRequest(
            id=request_id,
            operation_type=operation_type,
            content=content,
            filepath=filepath,
            risk_categories=risk_categories,
            risk_score=risk_score,
            risk_reasons=risk_reasons,
            required_level=required_level,
            org_id=org_id,
            team_id=team_id,
            expires_at=datetime.now() + timedelta(hours=24),
        )

        return request


class ApprovalWorkflowManager:
    """
    Manages the approval workflow for gated operations.
    """

    def __init__(self, storage_path: str = None):
        self.storage_path = Path(
            storage_path
            or os.getenv("NAVI_APPROVAL_PATH", os.path.expanduser("~/.navi/approvals"))
        )
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.policy_engine = ApprovalPolicyEngine()
        self.pending_requests: Dict[str, ApprovalRequest] = {}

        self._load_pending()

    def _load_pending(self):
        """Load pending approval requests."""
        pending_file = self.storage_path / "pending.json"
        if pending_file.exists():
            try:
                data = json.loads(pending_file.read_text())
                for r in data.get("requests", []):
                    request = ApprovalRequest(
                        id=r["id"],
                        operation_type=r["operation_type"],
                        content=r["content"],
                        filepath=r.get("filepath"),
                        risk_categories=[
                            RiskCategory(c) for c in r.get("risk_categories", [])
                        ],
                        risk_score=r.get("risk_score", 0),
                        risk_reasons=r.get("risk_reasons", []),
                        required_level=ApprovalLevel(r.get("required_level", "user")),
                        status=r.get("status", "pending"),
                        org_id=r.get("org_id"),
                        team_id=r.get("team_id"),
                        user_id=r.get("user_id"),
                    )
                    self.pending_requests[request.id] = request
            except Exception as e:
                logger.error(f"Error loading pending approvals: {e}")

    def _save_pending(self):
        """Save pending approval requests."""
        pending_file = self.storage_path / "pending.json"
        data = {
            "requests": [
                {
                    "id": r.id,
                    "operation_type": r.operation_type,
                    "content": r.content,
                    "filepath": r.filepath,
                    "risk_categories": [c.value for c in r.risk_categories],
                    "risk_score": r.risk_score,
                    "risk_reasons": r.risk_reasons,
                    "required_level": r.required_level.value,
                    "status": r.status,
                    "org_id": r.org_id,
                    "team_id": r.team_id,
                    "user_id": r.user_id,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                }
                for r in self.pending_requests.values()
            ]
        }
        pending_file.write_text(json.dumps(data, indent=2, default=str))

    def evaluate_operation(
        self,
        operation_type: str,
        content: str,
        filepath: Optional[str] = None,
        org_id: Optional[str] = None,
        team_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> ApprovalRequest:
        """
        Evaluate an operation and create approval request if needed.
        """
        request = self.policy_engine.evaluate(
            operation_type=operation_type,
            content=content,
            filepath=filepath,
            org_id=org_id,
            team_id=team_id,
        )
        request.user_id = user_id

        # Store if approval required
        if request.required_level != ApprovalLevel.NONE:
            self.pending_requests[request.id] = request
            self._save_pending()

        return request

    def approve(
        self,
        request_id: str,
        approver_id: str,
        approver_role: str = "user",
        comment: Optional[str] = None,
    ) -> bool:
        """
        Record an approval for a request.
        Returns True if fully approved, False if more approvals needed.
        """
        request = self.pending_requests.get(request_id)
        if not request:
            return False

        # Record approval
        request.approvals.append(
            {
                "approver_id": approver_id,
                "role": approver_role,
                "comment": comment,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Check if fully approved
        if self._check_approval_complete(request):
            request.status = "approved"
            self._save_pending()
            return True

        self._save_pending()
        return False

    def reject(
        self,
        request_id: str,
        rejecter_id: str,
        reason: str,
    ) -> None:
        """Reject an approval request."""
        request = self.pending_requests.get(request_id)
        if request:
            request.status = "rejected"
            request.rejections.append(
                {
                    "rejecter_id": rejecter_id,
                    "reason": reason,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            self._save_pending()

    def _check_approval_complete(self, request: ApprovalRequest) -> bool:
        """Check if request has sufficient approvals."""
        if request.required_level == ApprovalLevel.NONE:
            return True

        if request.required_level == ApprovalLevel.USER:
            return len(request.approvals) >= 1

        if request.required_level == ApprovalLevel.TEAM_LEAD:
            # Need at least one team lead approval
            return any(
                a.get("role") in ["team_lead", "admin", "security"]
                for a in request.approvals
            )

        if request.required_level == ApprovalLevel.SECURITY:
            # Need security team approval
            return any(
                a.get("role") in ["security", "admin"] for a in request.approvals
            )

        if request.required_level == ApprovalLevel.MULTI_PARTY:
            # Need at least 2 different approvers including one elevated role
            has_elevated = any(
                a.get("role") in ["team_lead", "security", "admin"]
                for a in request.approvals
            )
            return len(request.approvals) >= 2 and has_elevated

        return False

    def get_pending_for_user(self, user_id: str) -> List[ApprovalRequest]:
        """Get pending requests created by a user."""
        return [
            r
            for r in self.pending_requests.values()
            if r.user_id == user_id and r.status == "pending"
        ]

    def get_pending_for_approver(
        self,
        approver_role: str,
        org_id: Optional[str] = None,
        team_id: Optional[str] = None,
    ) -> List[ApprovalRequest]:
        """Get pending requests that this approver can approve."""
        results = []
        for request in self.pending_requests.values():
            if request.status != "pending":
                continue

            # Filter by org/team
            if org_id and request.org_id != org_id:
                continue
            if team_id and request.team_id != team_id:
                continue

            # Check if approver role is sufficient
            if request.required_level == ApprovalLevel.USER:
                results.append(request)
            elif request.required_level == ApprovalLevel.TEAM_LEAD:
                if approver_role in ["team_lead", "security", "admin"]:
                    results.append(request)
            elif request.required_level == ApprovalLevel.SECURITY:
                if approver_role in ["security", "admin"]:
                    results.append(request)
            elif request.required_level == ApprovalLevel.MULTI_PARTY:
                results.append(request)

        return results

    def get_risk_summary(self, request: ApprovalRequest) -> Dict:
        """Get a human-readable risk summary for a request."""
        severity_label = "Low"
        if request.risk_score >= 15:
            severity_label = "Critical"
        elif request.risk_score >= 10:
            severity_label = "High"
        elif request.risk_score >= 5:
            severity_label = "Medium"

        return {
            "severity": severity_label,
            "score": request.risk_score,
            "categories": [c.value for c in request.risk_categories],
            "reasons": request.risk_reasons,
            "required_approval": request.required_level.value,
            "status": request.status,
        }


# ============================================================
# GLOBAL INSTANCE
# ============================================================

_approval_manager: Optional[ApprovalWorkflowManager] = None


def get_approval_manager() -> ApprovalWorkflowManager:
    """Get the global approval workflow manager."""
    global _approval_manager
    if _approval_manager is None:
        _approval_manager = ApprovalWorkflowManager()
    return _approval_manager


def evaluate_for_approval(
    operation_type: str,
    content: str,
    filepath: Optional[str] = None,
    org_id: Optional[str] = None,
    team_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> ApprovalRequest:
    """Convenience function to evaluate an operation for approval."""
    return get_approval_manager().evaluate_operation(
        operation_type=operation_type,
        content=content,
        filepath=filepath,
        org_id=org_id,
        team_id=team_id,
        user_id=user_id,
    )


def get_risk_summary(request_id: str) -> Optional[Dict]:
    """Get risk summary for a request."""
    manager = get_approval_manager()
    request = manager.pending_requests.get(request_id)
    if request:
        return manager.get_risk_summary(request)
    return None
