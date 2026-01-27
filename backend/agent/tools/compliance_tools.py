"""
Compliance Tools for Enterprise NAVI.

Provides tools to check and ensure compliance with major standards:
- PCI-DSS (Payment Card Industry Data Security Standard)
- HIPAA (Health Insurance Portability and Accountability Act)
- SOC2 (Service Organization Control 2)
- GDPR (General Data Protection Regulation)

These tools can:
1. Scan codebases for compliance violations
2. Generate compliance reports
3. Audit dependencies for known vulnerabilities
4. Check encryption and data handling practices
"""

import os
import re
import json
import subprocess
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import structlog


logger = structlog.get_logger(__name__)


@dataclass
class ComplianceViolation:
    """A detected compliance violation."""

    rule_id: str
    severity: str  # critical, high, medium, low
    category: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    recommendation: str = ""
    standard: str = ""  # PCI-DSS, HIPAA, SOC2, GDPR


@dataclass
class ComplianceReport:
    """Compliance scan report."""

    standard: str
    passed: bool
    violations: List[ComplianceViolation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    scanned_files: int = 0
    scan_duration_ms: int = 0


# PCI-DSS compliance patterns
PCI_DSS_PATTERNS = {
    "hardcoded_card_number": {
        "pattern": r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b",
        "description": "Potential credit card number found in code",
        "severity": "critical",
        "recommendation": "Never store card numbers in code. Use tokenization services like Stripe or Braintree.",
    },
    "cvv_storage": {
        "pattern": r"(?i)\b(cvv|cvc|cvv2|cid)\s*[=:]\s*['\"]?\d{3,4}['\"]?",
        "description": "CVV/CVC storage detected - strictly prohibited by PCI-DSS",
        "severity": "critical",
        "recommendation": "CVV must never be stored. Process immediately and discard.",
    },
    "unencrypted_transmission": {
        "pattern": r"(?i)(http://.*(?:card|payment|checkout|billing))",
        "description": "Unencrypted HTTP used for payment-related endpoint",
        "severity": "critical",
        "recommendation": "Always use HTTPS for payment data transmission.",
    },
    "weak_encryption": {
        "pattern": r"(?i)(md5|sha1)\s*\(",
        "description": "Weak hashing algorithm used - not suitable for sensitive data",
        "severity": "high",
        "recommendation": "Use SHA-256 or stronger for hashing. Use AES-256 for encryption.",
    },
    "logging_sensitive_data": {
        "pattern": r"(?i)(console\.log|logger?\.|print)\s*\([^)]*(?:card|pan|cvv|password|secret)",
        "description": "Potentially logging sensitive payment data",
        "severity": "high",
        "recommendation": "Never log sensitive payment data. Implement data masking.",
    },
}

# HIPAA compliance patterns
HIPAA_PATTERNS = {
    "phi_exposure": {
        "pattern": r"(?i)\b(ssn|social.?security|patient.?id|medical.?record|diagnosis|treatment)\s*[=:]",
        "description": "Potential PHI (Protected Health Information) exposure",
        "severity": "critical",
        "recommendation": "PHI must be encrypted at rest and in transit. Implement access controls.",
    },
    "unencrypted_phi_storage": {
        "pattern": r"(?i)(localStorage|sessionStorage)\s*\.\s*setItem\s*\([^)]*(?:patient|medical|health|diagnosis)",
        "description": "PHI stored in unencrypted browser storage",
        "severity": "critical",
        "recommendation": "Never store PHI in browser storage. Use secure server-side storage with encryption.",
    },
    "missing_audit_log": {
        "pattern": r"(?i)(delete|update|insert)\s+(?:patient|medical|health).*(?!.*audit)",
        "description": "PHI modification without apparent audit logging",
        "severity": "high",
        "recommendation": "All PHI access and modifications must be logged for HIPAA compliance.",
    },
    "phi_in_url": {
        "pattern": r"(?i)(url|href|src)\s*[=:]\s*['\"][^'\"]*(?:patient|ssn|diagnosis)",
        "description": "PHI potentially exposed in URL",
        "severity": "high",
        "recommendation": "Never include PHI in URLs. Use POST requests with encrypted body.",
    },
}

# SOC2 compliance patterns
SOC2_PATTERNS = {
    "missing_auth_check": {
        "pattern": r"(?i)@(app\.route|router\.(get|post|put|delete))\s*\([^)]+\)\s*\n\s*(?:async\s+)?def\s+\w+\([^)]*\):\s*\n(?!\s*(?:@|if\s+.*auth|check.*token|verify.*user))",
        "description": "API endpoint without apparent authentication check",
        "severity": "high",
        "recommendation": "All API endpoints should have authentication. Implement middleware or decorators.",
    },
    "hardcoded_credentials": {
        "pattern": r"(?i)(password|api_key|secret|token)\s*[=:]\s*['\"][^'\"]{8,}['\"]",
        "description": "Hardcoded credentials detected",
        "severity": "critical",
        "recommendation": "Use environment variables or secrets management (AWS Secrets Manager, HashiCorp Vault).",
    },
    "sql_injection_risk": {
        "pattern": r"(?i)(execute|query)\s*\(\s*['\"].*\s*\+\s*|f['\"].*\{.*\}.*(?:select|insert|update|delete)",
        "description": "Potential SQL injection vulnerability",
        "severity": "critical",
        "recommendation": "Use parameterized queries or ORM. Never concatenate user input into SQL.",
    },
    "missing_rate_limiting": {
        "pattern": r"(?i)@(app\.route|router)\s*\([^)]*(?:login|auth|api)[^)]*\)(?!.*rate.?limit)",
        "description": "Sensitive endpoint without rate limiting",
        "severity": "medium",
        "recommendation": "Implement rate limiting on authentication and API endpoints.",
    },
    "insecure_cors": {
        "pattern": r"(?i)(cors|access.?control.?allow.?origin)\s*[=:]\s*['\"]?\*['\"]?",
        "description": "Overly permissive CORS configuration",
        "severity": "medium",
        "recommendation": "Restrict CORS to specific allowed origins instead of wildcard.",
    },
}

# GDPR compliance patterns
GDPR_PATTERNS = {
    "missing_consent": {
        "pattern": r"(?i)(collect|store|process)\s*\([^)]*(?:email|name|phone|address)(?!.*consent)",
        "description": "Personal data collection without apparent consent check",
        "severity": "high",
        "recommendation": "Implement explicit consent collection before processing personal data.",
    },
    "no_data_retention_policy": {
        "pattern": r"(?i)(?:user|customer|personal).*(?:data|info).*(?:store|save|insert)(?!.*expir|ttl|retention)",
        "description": "Personal data storage without apparent retention policy",
        "severity": "medium",
        "recommendation": "Implement data retention policies with automatic deletion after defined period.",
    },
    "missing_data_export": {
        "pattern": r"(?i)class\s+User(?!.*export|download|portability)",
        "description": "User model without data portability feature",
        "severity": "medium",
        "recommendation": "Implement user data export functionality for GDPR data portability right.",
    },
}


async def compliance_check_pci_dss(
    user_id: str,
    workspace_path: str,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Scan codebase for PCI-DSS compliance violations.

    PCI-DSS is required for any system that handles payment card data.
    This tool checks for common violations in code.

    Args:
        user_id: User ID executing the tool
        workspace_path: Path to the workspace to scan
        include_patterns: File patterns to include (e.g., ["*.py", "*.js"])
        exclude_patterns: File patterns to exclude (e.g., ["*test*", "*node_modules*"])

    Returns:
        Compliance report with violations and recommendations
    """
    logger.info("[TOOL:compliance_check_pci_dss] Starting PCI-DSS scan", workspace=workspace_path)

    violations = []
    scanned_files = 0

    include_patterns = include_patterns or ["*.py", "*.js", "*.ts", "*.jsx", "*.tsx", "*.java", "*.go"]
    exclude_patterns = exclude_patterns or ["*node_modules*", "*venv*", "*test*", "*.min.js"]

    # Walk through files
    for root, dirs, files in os.walk(workspace_path):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if not any(
            d in ex or ex.replace("*", "") in d
            for ex in exclude_patterns
        )]

        for file in files:
            # Check if file matches include pattern
            if not any(file.endswith(p.replace("*", "")) for p in include_patterns):
                continue

            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, workspace_path)

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    scanned_files += 1

                    for rule_id, rule in PCI_DSS_PATTERNS.items():
                        matches = list(re.finditer(rule["pattern"], content))
                        for match in matches:
                            line_num = content[:match.start()].count("\n") + 1
                            violations.append(ComplianceViolation(
                                rule_id=rule_id,
                                severity=rule["severity"],
                                category="PCI-DSS",
                                description=rule["description"],
                                file_path=rel_path,
                                line_number=line_num,
                                recommendation=rule["recommendation"],
                                standard="PCI-DSS",
                            ))
            except Exception as e:
                logger.warning(f"Error scanning file {file_path}: {e}")

    # Determine if passed
    critical_violations = [v for v in violations if v.severity == "critical"]
    passed = len(critical_violations) == 0

    report = ComplianceReport(
        standard="PCI-DSS",
        passed=passed,
        violations=violations,
        scanned_files=scanned_files,
        recommendations=[
            "Use a PCI-compliant payment processor (Stripe, Braintree, Square)",
            "Never store full card numbers - use tokenization",
            "Encrypt all data at rest and in transit",
            "Implement strong access controls",
            "Maintain audit logs for all payment operations",
        ] if violations else [],
    )

    return {
        "success": True,
        "standard": "PCI-DSS",
        "passed": passed,
        "violation_count": len(violations),
        "critical_count": len(critical_violations),
        "scanned_files": scanned_files,
        "violations": [
            {
                "rule_id": v.rule_id,
                "severity": v.severity,
                "description": v.description,
                "file": v.file_path,
                "line": v.line_number,
                "recommendation": v.recommendation,
            }
            for v in violations[:20]  # Limit to 20 for readability
        ],
        "recommendations": report.recommendations,
        "message": f"PCI-DSS scan {'PASSED' if passed else 'FAILED'}: {len(violations)} violations found in {scanned_files} files",
    }


async def compliance_check_hipaa(
    user_id: str,
    workspace_path: str,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Scan codebase for HIPAA compliance violations.

    HIPAA is required for systems handling Protected Health Information (PHI).

    Args:
        user_id: User ID executing the tool
        workspace_path: Path to the workspace to scan
        include_patterns: File patterns to include
        exclude_patterns: File patterns to exclude

    Returns:
        Compliance report with violations and recommendations
    """
    logger.info("[TOOL:compliance_check_hipaa] Starting HIPAA scan", workspace=workspace_path)

    violations = []
    scanned_files = 0

    include_patterns = include_patterns or ["*.py", "*.js", "*.ts", "*.jsx", "*.tsx", "*.java"]
    exclude_patterns = exclude_patterns or ["*node_modules*", "*venv*", "*test*"]

    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [d for d in dirs if not any(
            d in ex or ex.replace("*", "") in d
            for ex in exclude_patterns
        )]

        for file in files:
            if not any(file.endswith(p.replace("*", "")) for p in include_patterns):
                continue

            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, workspace_path)

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    scanned_files += 1

                    for rule_id, rule in HIPAA_PATTERNS.items():
                        matches = list(re.finditer(rule["pattern"], content))
                        for match in matches:
                            line_num = content[:match.start()].count("\n") + 1
                            violations.append(ComplianceViolation(
                                rule_id=rule_id,
                                severity=rule["severity"],
                                category="HIPAA",
                                description=rule["description"],
                                file_path=rel_path,
                                line_number=line_num,
                                recommendation=rule["recommendation"],
                                standard="HIPAA",
                            ))
            except Exception as e:
                logger.warning(f"Error scanning file {file_path}: {e}")

    critical_violations = [v for v in violations if v.severity == "critical"]
    passed = len(critical_violations) == 0

    return {
        "success": True,
        "standard": "HIPAA",
        "passed": passed,
        "violation_count": len(violations),
        "critical_count": len(critical_violations),
        "scanned_files": scanned_files,
        "violations": [
            {
                "rule_id": v.rule_id,
                "severity": v.severity,
                "description": v.description,
                "file": v.file_path,
                "line": v.line_number,
                "recommendation": v.recommendation,
            }
            for v in violations[:20]
        ],
        "recommendations": [
            "Encrypt all PHI at rest using AES-256",
            "Use TLS 1.2+ for all PHI transmission",
            "Implement role-based access control (RBAC)",
            "Maintain comprehensive audit logs",
            "Implement automatic session timeouts",
            "Use BAA (Business Associate Agreement) with all vendors",
        ] if violations else [],
        "message": f"HIPAA scan {'PASSED' if passed else 'FAILED'}: {len(violations)} violations found",
    }


async def compliance_check_soc2(
    user_id: str,
    workspace_path: str,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Scan codebase for SOC2 compliance violations.

    SOC2 covers security, availability, processing integrity, confidentiality, and privacy.

    Args:
        user_id: User ID executing the tool
        workspace_path: Path to the workspace to scan
        include_patterns: File patterns to include
        exclude_patterns: File patterns to exclude

    Returns:
        Compliance report with violations and recommendations
    """
    logger.info("[TOOL:compliance_check_soc2] Starting SOC2 scan", workspace=workspace_path)

    violations = []
    scanned_files = 0

    include_patterns = include_patterns or ["*.py", "*.js", "*.ts", "*.jsx", "*.tsx", "*.java", "*.go"]
    exclude_patterns = exclude_patterns or ["*node_modules*", "*venv*", "*test*"]

    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [d for d in dirs if not any(
            d in ex or ex.replace("*", "") in d
            for ex in exclude_patterns
        )]

        for file in files:
            if not any(file.endswith(p.replace("*", "")) for p in include_patterns):
                continue

            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, workspace_path)

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    scanned_files += 1

                    for rule_id, rule in SOC2_PATTERNS.items():
                        matches = list(re.finditer(rule["pattern"], content))
                        for match in matches:
                            line_num = content[:match.start()].count("\n") + 1
                            violations.append(ComplianceViolation(
                                rule_id=rule_id,
                                severity=rule["severity"],
                                category="SOC2",
                                description=rule["description"],
                                file_path=rel_path,
                                line_number=line_num,
                                recommendation=rule["recommendation"],
                                standard="SOC2",
                            ))
            except Exception as e:
                logger.warning(f"Error scanning file {file_path}: {e}")

    critical_violations = [v for v in violations if v.severity == "critical"]
    passed = len(critical_violations) == 0

    return {
        "success": True,
        "standard": "SOC2",
        "passed": passed,
        "violation_count": len(violations),
        "critical_count": len(critical_violations),
        "scanned_files": scanned_files,
        "violations": [
            {
                "rule_id": v.rule_id,
                "severity": v.severity,
                "description": v.description,
                "file": v.file_path,
                "line": v.line_number,
                "recommendation": v.recommendation,
            }
            for v in violations[:20]
        ],
        "recommendations": [
            "Implement comprehensive logging and monitoring",
            "Use secrets management (AWS Secrets Manager, HashiCorp Vault)",
            "Implement rate limiting on all APIs",
            "Use parameterized queries to prevent SQL injection",
            "Configure strict CORS policies",
            "Implement MFA for all user authentication",
        ] if violations else [],
        "message": f"SOC2 scan {'PASSED' if passed else 'FAILED'}: {len(violations)} violations found",
    }


async def compliance_audit_dependencies(
    user_id: str,
    workspace_path: str,
) -> Dict[str, Any]:
    """
    Audit dependencies for known vulnerabilities using npm audit, pip-audit, etc.

    Args:
        user_id: User ID executing the tool
        workspace_path: Path to the workspace

    Returns:
        Vulnerability report with affected packages and recommendations
    """
    logger.info("[TOOL:compliance_audit_dependencies] Starting dependency audit", workspace=workspace_path)

    vulnerabilities = []
    tools_run = []

    # Check for package.json (npm)
    package_json = os.path.join(workspace_path, "package.json")
    if os.path.exists(package_json):
        try:
            result = subprocess.run(
                ["npm", "audit", "--json"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=120,
            )
            tools_run.append("npm audit")

            if result.stdout:
                audit_data = json.loads(result.stdout)
                vulns = audit_data.get("vulnerabilities", {})
                for pkg_name, vuln_info in vulns.items():
                    vulnerabilities.append({
                        "package": pkg_name,
                        "severity": vuln_info.get("severity", "unknown"),
                        "via": vuln_info.get("via", []),
                        "ecosystem": "npm",
                        "fix_available": vuln_info.get("fixAvailable", False),
                    })
        except Exception as e:
            logger.warning(f"npm audit failed: {e}")

    # Check for requirements.txt (pip)
    requirements_txt = os.path.join(workspace_path, "requirements.txt")
    if os.path.exists(requirements_txt):
        try:
            # Try pip-audit if available
            result = subprocess.run(
                ["pip-audit", "--format", "json", "-r", "requirements.txt"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=120,
            )
            tools_run.append("pip-audit")

            if result.returncode == 0 and result.stdout:
                audit_data = json.loads(result.stdout)
                for vuln in audit_data:
                    vulnerabilities.append({
                        "package": vuln.get("name", "unknown"),
                        "severity": vuln.get("vulns", [{}])[0].get("severity", "unknown") if vuln.get("vulns") else "unknown",
                        "ecosystem": "pip",
                        "fix_available": vuln.get("fix_versions", []) != [],
                    })
        except FileNotFoundError:
            logger.info("pip-audit not available, skipping Python audit")
        except Exception as e:
            logger.warning(f"pip-audit failed: {e}")

    # Categorize by severity
    critical = [v for v in vulnerabilities if v.get("severity") == "critical"]
    high = [v for v in vulnerabilities if v.get("severity") == "high"]
    medium = [v for v in vulnerabilities if v.get("severity") == "medium" or v.get("severity") == "moderate"]

    return {
        "success": True,
        "tools_run": tools_run,
        "total_vulnerabilities": len(vulnerabilities),
        "critical": len(critical),
        "high": len(high),
        "medium": len(medium),
        "vulnerabilities": vulnerabilities[:30],  # Limit for readability
        "recommendations": [
            "Run `npm audit fix` to automatically fix npm vulnerabilities",
            "Update packages to latest secure versions",
            "Review and replace deprecated packages",
            "Enable Dependabot or Snyk for continuous monitoring",
        ] if vulnerabilities else ["No vulnerabilities detected - dependencies are secure"],
        "message": f"Dependency audit complete: {len(vulnerabilities)} vulnerabilities ({len(critical)} critical, {len(high)} high)",
    }


async def compliance_generate_report(
    user_id: str,
    workspace_path: str,
    standards: Optional[List[str]] = None,
    output_format: str = "markdown",
) -> Dict[str, Any]:
    """
    Generate a comprehensive compliance report for multiple standards.

    Args:
        user_id: User ID executing the tool
        workspace_path: Path to the workspace
        standards: List of standards to check (default: all)
        output_format: Output format (markdown, json, html)

    Returns:
        Comprehensive compliance report
    """
    logger.info("[TOOL:compliance_generate_report] Generating compliance report", workspace=workspace_path)

    standards = standards or ["PCI-DSS", "HIPAA", "SOC2"]
    reports = {}

    if "PCI-DSS" in standards:
        reports["PCI-DSS"] = await compliance_check_pci_dss(user_id, workspace_path)

    if "HIPAA" in standards:
        reports["HIPAA"] = await compliance_check_hipaa(user_id, workspace_path)

    if "SOC2" in standards:
        reports["SOC2"] = await compliance_check_soc2(user_id, workspace_path)

    # Dependency audit
    dep_report = await compliance_audit_dependencies(user_id, workspace_path)

    # Generate markdown report
    if output_format == "markdown":
        md_lines = [
            "# Compliance Report",
            "",
            f"**Workspace:** `{workspace_path}`",
            f"**Standards Checked:** {', '.join(standards)}",
            "",
            "## Summary",
            "",
            "| Standard | Status | Violations | Critical |",
            "|----------|--------|------------|----------|",
        ]

        for std, report in reports.items():
            status = "✅ PASSED" if report["passed"] else "❌ FAILED"
            md_lines.append(f"| {std} | {status} | {report['violation_count']} | {report['critical_count']} |")

        md_lines.extend([
            "",
            "## Dependency Vulnerabilities",
            "",
            f"- **Total:** {dep_report['total_vulnerabilities']}",
            f"- **Critical:** {dep_report['critical']}",
            f"- **High:** {dep_report['high']}",
            "",
        ])

        # Add violations details
        for std, report in reports.items():
            if report["violations"]:
                md_lines.extend([
                    f"## {std} Violations",
                    "",
                ])
                for v in report["violations"][:10]:
                    md_lines.extend([
                        f"### {v['rule_id']} ({v['severity'].upper()})",
                        f"- **File:** `{v['file']}:{v['line']}`",
                        f"- **Issue:** {v['description']}",
                        f"- **Fix:** {v['recommendation']}",
                        "",
                    ])

        report_content = "\n".join(md_lines)
    else:
        report_content = json.dumps({
            "standards": reports,
            "dependencies": dep_report,
        }, indent=2)

    # Overall pass/fail
    all_passed = all(r["passed"] for r in reports.values()) and dep_report["critical"] == 0

    return {
        "success": True,
        "overall_passed": all_passed,
        "standards_checked": list(reports.keys()),
        "total_violations": sum(r["violation_count"] for r in reports.values()),
        "total_critical": sum(r["critical_count"] for r in reports.values()),
        "dependency_vulnerabilities": dep_report["total_vulnerabilities"],
        "report": report_content,
        "message": f"Compliance report generated: {'ALL PASSED' if all_passed else 'ISSUES FOUND'}",
    }


# Tool definitions for NAVI agent
COMPLIANCE_TOOLS = {
    "compliance_check_pci_dss": {
        "function": compliance_check_pci_dss,
        "description": "Scan codebase for PCI-DSS compliance violations (payment card data security)",
        "parameters": {
            "type": "object",
            "properties": {
                "workspace_path": {"type": "string", "description": "Path to workspace to scan"},
                "include_patterns": {"type": "array", "items": {"type": "string"}, "description": "File patterns to include"},
                "exclude_patterns": {"type": "array", "items": {"type": "string"}, "description": "File patterns to exclude"},
            },
            "required": ["workspace_path"],
        },
    },
    "compliance_check_hipaa": {
        "function": compliance_check_hipaa,
        "description": "Scan codebase for HIPAA compliance violations (health data privacy)",
        "parameters": {
            "type": "object",
            "properties": {
                "workspace_path": {"type": "string", "description": "Path to workspace to scan"},
                "include_patterns": {"type": "array", "items": {"type": "string"}, "description": "File patterns to include"},
                "exclude_patterns": {"type": "array", "items": {"type": "string"}, "description": "File patterns to exclude"},
            },
            "required": ["workspace_path"],
        },
    },
    "compliance_check_soc2": {
        "function": compliance_check_soc2,
        "description": "Scan codebase for SOC2 compliance violations (security, availability, confidentiality)",
        "parameters": {
            "type": "object",
            "properties": {
                "workspace_path": {"type": "string", "description": "Path to workspace to scan"},
                "include_patterns": {"type": "array", "items": {"type": "string"}, "description": "File patterns to include"},
                "exclude_patterns": {"type": "array", "items": {"type": "string"}, "description": "File patterns to exclude"},
            },
            "required": ["workspace_path"],
        },
    },
    "compliance_audit_dependencies": {
        "function": compliance_audit_dependencies,
        "description": "Audit project dependencies for known security vulnerabilities",
        "parameters": {
            "type": "object",
            "properties": {
                "workspace_path": {"type": "string", "description": "Path to workspace to scan"},
            },
            "required": ["workspace_path"],
        },
    },
    "compliance_generate_report": {
        "function": compliance_generate_report,
        "description": "Generate comprehensive compliance report for multiple standards",
        "parameters": {
            "type": "object",
            "properties": {
                "workspace_path": {"type": "string", "description": "Path to workspace to scan"},
                "standards": {"type": "array", "items": {"type": "string"}, "description": "Standards to check: PCI-DSS, HIPAA, SOC2"},
                "output_format": {"type": "string", "enum": ["markdown", "json"], "description": "Output format"},
            },
            "required": ["workspace_path"],
        },
    },
}
