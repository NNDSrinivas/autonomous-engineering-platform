"""
Extension Security Service

Integrates the extension security system with the main extension platform.
Provides high-level service operations for:
- Extension security validation before installation
- Certificate management and signing
- Vulnerability scanning and reporting
- Trust and policy management
- Security monitoring and compliance

This service acts as the bridge between the extension runtime and the security system.
"""

from __future__ import annotations

import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any, Tuple
import zipfile

from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base

from .security import (
    SecurityReport,
    ExtensionCertificate,
    SecurityLevel,
    SecurityRisk,
    create_security_manager,
)

logger = logging.getLogger(__name__)

Base = declarative_base()


class SecurityReportModel(Base):
    """Database model for security reports"""

    __tablename__ = "extension_security_reports"

    id = Column(Integer, primary_key=True, index=True)
    extension_id = Column(String(255), nullable=False, index=True)
    report_id = Column(String(255), nullable=False, unique=True, index=True)
    security_level = Column(String(50), nullable=False)
    overall_score = Column(Integer, nullable=False)
    findings_count = Column(Integer, nullable=False)
    critical_findings = Column(Integer, nullable=False)
    high_findings = Column(Integer, nullable=False)
    has_certificate = Column(Boolean, nullable=False, default=False)
    policy_compliant = Column(Boolean, nullable=False, default=False)
    report_data = Column(JSON, nullable=False)  # Full report as JSON
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    tenant_id = Column(String(255), nullable=False, index=True)


class CertificateModel(Base):
    """Database model for extension certificates"""

    __tablename__ = "extension_certificates"

    id = Column(Integer, primary_key=True, index=True)
    certificate_id = Column(String(255), nullable=False, unique=True, index=True)
    extension_id = Column(String(255), nullable=False, index=True)
    issuer = Column(String(500), nullable=False)
    subject = Column(String(500), nullable=False)
    valid_from = Column(DateTime(timezone=True), nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=False)
    is_self_signed = Column(Boolean, nullable=False, default=False)
    revocation_status = Column(String(50), nullable=False, default="unknown")
    certificate_data = Column(JSON, nullable=False)  # Full certificate as JSON
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    tenant_id = Column(String(255), nullable=False, index=True)


class SecurityPolicyModel(Base):
    """Database model for security policies"""

    __tablename__ = "extension_security_policies"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(255), nullable=False, index=True)
    policy_name = Column(String(255), nullable=False)
    policy_value = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ExtensionSecurityService:
    """High-level service for extension security operations"""

    def __init__(
        self,
        db_session: Session,
        ca_key_path: Optional[str] = None,
        ca_cert_path: Optional[str] = None,
    ):
        self.db = db_session
        self.security_manager = create_security_manager(ca_key_path, ca_cert_path)

        # Default security policies
        self.default_policies = {
            "require_signature": False,  # Start permissive, can be tightened
            "allow_self_signed": True,
            "min_security_score": 60,
            "block_high_risk_permissions": False,
            "scan_for_vulnerabilities": True,
            "quarantine_suspicious": True,
            "auto_scan_dependencies": True,
            "block_critical_vulnerabilities": True,
            "require_author_verification": False,
        }

    async def validate_extension_security(
        self,
        extension_manifest: Dict[str, Any],
        extension_content: bytes,
        tenant_id: str,
        certificate: Optional[ExtensionCertificate] = None,
    ) -> Tuple[SecurityReport, bool]:
        """
        Validate extension security and return report with approval status

        Returns:
            Tuple of (SecurityReport, is_approved)
        """

        # Extract extension files from content
        extension_files = await self._extract_extension_files(extension_content)

        # Perform security assessment
        security_report = self.security_manager.assess_extension_security(
            extension_manifest, extension_files, certificate
        )

        # Store security report
        await self._store_security_report(security_report, tenant_id)

        # Determine if extension is approved
        is_approved = await self._evaluate_approval(security_report, tenant_id)

        logger.info(
            f"Security validation completed for extension {security_report.extension_id}: "
            f"score={security_report.overall_score}, level={security_report.security_level}, "
            f"approved={is_approved}"
        )

        return security_report, is_approved

    async def sign_extension(
        self,
        extension_manifest: Dict[str, Any],
        extension_content: bytes,
        tenant_id: str,
    ) -> ExtensionCertificate:
        """Sign an extension and generate certificate"""

        try:
            # Sign extension using CA
            certificate = self.security_manager.certificate_authority.sign_extension(
                extension_manifest, extension_content
            )

            # Store certificate in database
            await self._store_certificate(certificate, tenant_id)

            logger.info(f"Extension {certificate.extension_id} signed successfully")
            return certificate

        except Exception as e:
            logger.error(f"Failed to sign extension: {e}")
            raise RuntimeError(f"Extension signing failed: {e}")

    async def get_security_report(
        self, extension_id: str, tenant_id: str, latest: bool = True
    ) -> Optional[SecurityReport]:
        """Get security report for an extension"""

        try:
            query = self.db.query(SecurityReportModel).filter(
                SecurityReportModel.extension_id == extension_id,
                SecurityReportModel.tenant_id == tenant_id,
            )

            if latest:
                query = query.order_by(SecurityReportModel.created_at.desc())

            report_model = query.first()

            if report_model:
                # Deserialize report data
                report_data = self._coerce_json_dict(report_model.report_data)
                return self._deserialize_security_report(report_data)

            return None

        except Exception as e:
            logger.error(f"Failed to get security report: {e}")
            return None

    async def get_extension_certificate(
        self, extension_id: str, tenant_id: str
    ) -> Optional[ExtensionCertificate]:
        """Get certificate for an extension"""

        try:
            cert_model = (
                self.db.query(CertificateModel)
                .filter(
                    CertificateModel.extension_id == extension_id,
                    CertificateModel.tenant_id == tenant_id,
                )
                .first()
            )

            if cert_model:
                cert_data = self._coerce_json_dict(cert_model.certificate_data)
                return self._deserialize_certificate(cert_data)

            return None

        except Exception as e:
            logger.error(f"Failed to get certificate: {e}")
            return None

    async def update_security_policies(
        self, tenant_id: str, policies: Dict[str, Any]
    ) -> bool:
        """Update security policies for a tenant"""

        try:
            # Merge with default policies
            updated_policies = {**self.default_policies, **policies}

            # Store in database
            for policy_name, policy_value in updated_policies.items():
                policy_model = (
                    self.db.query(SecurityPolicyModel)
                    .filter(
                        SecurityPolicyModel.tenant_id == tenant_id,
                        SecurityPolicyModel.policy_name == policy_name,
                    )
                    .first()
                )

                if policy_model:
                    policy_model.policy_value = policy_value
                    setattr(policy_model, "updated_at", datetime.now(timezone.utc))
                else:
                    policy_model = SecurityPolicyModel(
                        tenant_id=tenant_id,
                        policy_name=policy_name,
                        policy_value=policy_value,
                    )
                    self.db.add(policy_model)

            self.db.commit()

            # Update security manager policies
            self.security_manager.security_policies.update(updated_policies)

            logger.info(f"Updated security policies for tenant {tenant_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update security policies: {e}")
            self.db.rollback()
            return False

    async def get_security_policies(self, tenant_id: str) -> Dict[str, Any]:
        """Get security policies for a tenant"""

        try:
            policies = {}

            policy_models = (
                self.db.query(SecurityPolicyModel)
                .filter(SecurityPolicyModel.tenant_id == tenant_id)
                .all()
            )

            for policy_model in policy_models:
                policies[policy_model.policy_name] = policy_model.policy_value

            # Merge with defaults for any missing policies
            return {**self.default_policies, **policies}

        except Exception as e:
            logger.error(f"Failed to get security policies: {e}")
            return self.default_policies

    async def revoke_certificate(
        self, certificate_id: str, tenant_id: str, reason: str = "unspecified"
    ) -> bool:
        """Revoke an extension certificate"""

        try:
            cert_model = (
                self.db.query(CertificateModel)
                .filter(
                    CertificateModel.certificate_id == certificate_id,
                    CertificateModel.tenant_id == tenant_id,
                )
                .first()
            )

            if cert_model:
                setattr(cert_model, "revocation_status", "revoked")
                cert_data = self._coerce_json_dict(cert_model.certificate_data)
                cert_data["revocation_reason"] = reason
                cert_data["revoked_at"] = datetime.now(timezone.utc).isoformat()
                setattr(cert_model, "certificate_data", cert_data)

                self.db.commit()

                logger.info(f"Certificate {certificate_id} revoked: {reason}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to revoke certificate: {e}")
            self.db.rollback()
            return False

    async def get_security_dashboard_data(self, tenant_id: str) -> Dict[str, Any]:
        """Get security dashboard data for a tenant"""

        try:
            # Get recent security reports
            recent_reports = (
                self.db.query(SecurityReportModel)
                .filter(SecurityReportModel.tenant_id == tenant_id)
                .order_by(SecurityReportModel.created_at.desc())
                .limit(50)
                .all()
            )

            # Calculate statistics
            total_extensions = len(set(r.extension_id for r in recent_reports))
            total_score = sum(self._coerce_int(r.overall_score) for r in recent_reports)
            avg_security_score = (
                total_score / len(recent_reports) if recent_reports else 0.0
            )
            critical_findings = sum(
                self._coerce_int(r.critical_findings) for r in recent_reports
            )
            high_findings = sum(
                self._coerce_int(r.high_findings) for r in recent_reports
            )

            # Security level distribution
            level_counts = {}
            for report in recent_reports:
                level = report.security_level
                level_counts[level] = level_counts.get(level, 0) + 1

            # Certificate statistics
            cert_count = (
                self.db.query(CertificateModel)
                .filter(CertificateModel.tenant_id == tenant_id)
                .count()
            )

            revoked_count = (
                self.db.query(CertificateModel)
                .filter(
                    CertificateModel.tenant_id == tenant_id,
                    CertificateModel.revocation_status == "revoked",
                )
                .count()
            )

            return {
                "total_extensions": total_extensions,
                "average_security_score": round(avg_security_score, 1),
                "critical_findings": critical_findings,
                "high_findings": high_findings,
                "security_level_distribution": level_counts,
                "certificates_issued": cert_count,
                "certificates_revoked": revoked_count,
                "compliance_rate": (
                    sum(
                        1
                        for r in recent_reports
                        if self._coerce_bool(r.policy_compliant)
                    )
                    / len(recent_reports)
                    * 100
                    if recent_reports
                    else 0
                ),
            }

        except Exception as e:
            logger.error(f"Failed to get dashboard data: {e}")
            return {}

    async def _extract_extension_files(
        self, extension_content: bytes
    ) -> Dict[str, str]:
        """Extract files from extension content for analysis"""

        extension_files = {}

        try:
            # Assume extension content is a ZIP file
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(extension_content)
                temp_file.flush()

                with zipfile.ZipFile(temp_file.name, "r") as zip_file:
                    for file_info in zip_file.filelist:
                        if not file_info.is_dir() and file_info.filename.endswith(
                            (".py", ".js", ".ts", ".json", ".yaml", ".yml")
                        ):
                            try:
                                content = zip_file.read(file_info.filename).decode(
                                    "utf-8", errors="ignore"
                                )
                                extension_files[file_info.filename] = content
                            except Exception as e:
                                logger.warning(
                                    f"Failed to read file {file_info.filename}: {e}"
                                )

                # Clean up temp file
                Path(temp_file.name).unlink()

        except Exception as e:
            logger.error(f"Failed to extract extension files: {e}")
            # Fallback: treat as single Python file
            try:
                content = extension_content.decode("utf-8", errors="ignore")
                extension_files["main.py"] = content
            except Exception:
                extension_files["main.py"] = "# Could not decode content"

        return extension_files

    async def _store_security_report(self, report: SecurityReport, tenant_id: str):
        """Store security report in database"""

        try:
            # Count findings by risk level
            critical_count = len(
                [f for f in report.findings if f.risk_level == SecurityRisk.CRITICAL]
            )
            high_count = len(
                [f for f in report.findings if f.risk_level == SecurityRisk.HIGH]
            )

            # Check policy compliance
            policy_compliant = all(report.policy_compliance.values())

            report_model = SecurityReportModel(
                extension_id=report.extension_id,
                report_id=report.report_id,
                security_level=report.security_level.value,
                overall_score=report.overall_score,
                findings_count=len(report.findings),
                critical_findings=critical_count,
                high_findings=high_count,
                has_certificate=report.certificate is not None,
                policy_compliant=policy_compliant,
                report_data=self._serialize_security_report(report),
                tenant_id=tenant_id,
            )

            self.db.add(report_model)
            self.db.commit()

        except Exception as e:
            logger.error(f"Failed to store security report: {e}")
            self.db.rollback()

    async def _store_certificate(
        self, certificate: ExtensionCertificate, tenant_id: str
    ):
        """Store certificate in database"""

        try:
            cert_model = CertificateModel(
                certificate_id=certificate.certificate_id,
                extension_id=certificate.extension_id,
                issuer=certificate.issuer,
                subject=certificate.subject,
                valid_from=certificate.valid_from,
                valid_until=certificate.valid_until,
                is_self_signed=certificate.is_self_signed,
                revocation_status=certificate.revocation_status,
                certificate_data=self._serialize_certificate(certificate),
                tenant_id=tenant_id,
            )

            self.db.add(cert_model)
            self.db.commit()

        except Exception as e:
            logger.error(f"Failed to store certificate: {e}")
            self.db.rollback()

    async def _evaluate_approval(self, report: SecurityReport, tenant_id: str) -> bool:
        """Evaluate if extension should be approved based on security report"""

        try:
            # Get tenant policies
            policies = await self.get_security_policies(tenant_id)

            # Block if critical vulnerabilities found and policy requires it
            if policies.get("block_critical_vulnerabilities", True):
                critical_findings = [
                    f for f in report.findings if f.risk_level == SecurityRisk.CRITICAL
                ]
                if critical_findings:
                    return False

            # Check minimum security score
            min_score = policies.get("min_security_score", 60)
            if report.overall_score < min_score:
                return False

            # Check security level
            if report.security_level == SecurityLevel.BLOCKED:
                return False

            # Check policy compliance
            if not all(report.policy_compliance.values()):
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to evaluate approval: {e}")
            return False

    def _coerce_json_dict(self, value: Any) -> Dict[str, Any]:
        """Coerce JSON-like values into a dictionary."""
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
        try:
            return dict(value)
        except (TypeError, ValueError):
            return {}

    def _coerce_int(self, value: Any) -> int:
        """Coerce numeric values into an int, defaulting to 0."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _coerce_bool(self, value: Any) -> bool:
        """Coerce values into a boolean without SQLAlchemy bool errors."""
        try:
            return bool(value)
        except Exception:
            return False

    def _serialize_security_report(self, report: SecurityReport) -> Dict[str, Any]:
        """Serialize security report to JSON-compatible dict"""

        report_dict = {
            "extension_id": report.extension_id,
            "report_id": report.report_id,
            "generated_at": report.generated_at.isoformat(),
            "security_level": report.security_level.value,
            "overall_score": report.overall_score,
            "findings": [
                {
                    "finding_id": f.finding_id,
                    "threat_type": f.threat_type.value,
                    "risk_level": f.risk_level.value,
                    "title": f.title,
                    "description": f.description,
                    "file_path": f.file_path,
                    "line_number": f.line_number,
                    "code_snippet": f.code_snippet,
                    "remediation": f.remediation,
                    "references": f.references,
                    "cve_ids": f.cve_ids,
                }
                for f in report.findings
            ],
            "certificate": (
                self._serialize_certificate(report.certificate)
                if report.certificate
                else None
            ),
            "policy_compliance": report.policy_compliance,
            "recommendations": report.recommendations,
            "scan_metadata": report.scan_metadata,
        }

        return report_dict

    def _serialize_certificate(
        self, certificate: ExtensionCertificate
    ) -> Dict[str, Any]:
        """Serialize certificate to JSON-compatible dict"""

        return {
            "certificate_id": certificate.certificate_id,
            "extension_id": certificate.extension_id,
            "issuer": certificate.issuer,
            "subject": certificate.subject,
            "public_key": certificate.public_key,
            "signature": certificate.signature,
            "valid_from": certificate.valid_from.isoformat(),
            "valid_until": certificate.valid_until.isoformat(),
            "key_usage": certificate.key_usage,
            "extensions": certificate.extensions,
            "is_self_signed": certificate.is_self_signed,
            "certificate_chain": certificate.certificate_chain,
            "revocation_status": certificate.revocation_status,
        }

    def _deserialize_security_report(
        self, report_data: Dict[str, Any]
    ) -> SecurityReport:
        """Deserialize security report from JSON dict"""

        # Note: This is a simplified deserialization
        # Production would need proper object reconstruction
        report = SecurityReport(
            extension_id=report_data["extension_id"],
            report_id=report_data["report_id"],
            generated_at=datetime.fromisoformat(report_data["generated_at"]),
            security_level=SecurityLevel(report_data["security_level"]),
            overall_score=report_data["overall_score"],
            findings=[],  # Simplified - would reconstruct SecurityFinding objects
            certificate=None,  # Simplified - would reconstruct if present
            policy_compliance=report_data["policy_compliance"],
            recommendations=report_data["recommendations"],
            scan_metadata=report_data["scan_metadata"],
        )

        return report

    def _deserialize_certificate(
        self, cert_data: Dict[str, Any]
    ) -> ExtensionCertificate:
        """Deserialize certificate from JSON dict"""

        return ExtensionCertificate(
            certificate_id=cert_data["certificate_id"],
            extension_id=cert_data["extension_id"],
            issuer=cert_data["issuer"],
            subject=cert_data["subject"],
            public_key=cert_data["public_key"],
            signature=cert_data["signature"],
            valid_from=datetime.fromisoformat(cert_data["valid_from"]),
            valid_until=datetime.fromisoformat(cert_data["valid_until"]),
            key_usage=cert_data["key_usage"],
            extensions=cert_data["extensions"],
            is_self_signed=cert_data["is_self_signed"],
            certificate_chain=cert_data["certificate_chain"],
            revocation_status=cert_data["revocation_status"],
        )


# Factory function for easy service creation
def create_security_service(
    db_session: Session,
    ca_key_path: Optional[str] = None,
    ca_cert_path: Optional[str] = None,
) -> ExtensionSecurityService:
    """Create and configure an ExtensionSecurityService"""
    return ExtensionSecurityService(db_session, ca_key_path, ca_cert_path)
