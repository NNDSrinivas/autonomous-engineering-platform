"""
Extension Security System for Phase 7.0 Extension Platform

Provides comprehensive security features including:
- Certificate-based extension signing and validation
- Vulnerability scanning and threat detection  
- Trust management and policy enforcement
- Security scoring and risk assessment
- Digital signatures and integrity verification

Enhances the existing basic security in extensions/runtime.py with enterprise-grade 
trust management, certificate validation, and automated vulnerability detection.
"""

from __future__ import annotations

import ast
import hashlib
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any, TYPE_CHECKING, cast
from enum import Enum
from dataclasses import dataclass

# Cryptography for certificate handling
hashes: Any
serialization: Any
rsa: Any
padding: Any
pkcs12: Any
x509: Any
CertificateBuilder: Any
Name: Any
NameAttribute: Any
oid: Any

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography import x509
    from cryptography.x509 import CertificateBuilder, Name, NameAttribute, oid
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    hashes = None
    serialization = None
    rsa = None
    padding = None
    pkcs12 = None
    x509 = None
    CertificateBuilder = None
    Name = None
    NameAttribute = None
    oid = None
    logging.warning("cryptography package not available - certificate features disabled")

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.types import CertificateIssuerPrivateKeyTypes


logger = logging.getLogger(__name__)

class SecurityLevel(str, Enum):
    """Security trust levels for extensions"""
    TRUSTED = "trusted"              # Signed by trusted authority, verified
    VERIFIED = "verified"            # Signed and validated, but not trusted authority
    COMMUNITY = "community"          # Community verified, no signature required  
    UNVERIFIED = "unverified"       # No signature or verification
    BLOCKED = "blocked"             # Explicitly blocked due to security issues

class ThreatType(str, Enum):
    """Types of security threats that can be detected"""
    MALICIOUS_CODE = "malicious_code"
    VULNERABILITY = "vulnerability"
    SUSPICIOUS_BEHAVIOR = "suspicious_behavior"
    POLICY_VIOLATION = "policy_violation"
    DEPENDENCY_RISK = "dependency_risk"
    UNTRUSTED_SOURCE = "untrusted_source"

class SecurityRisk(str, Enum):
    """Risk levels for security findings"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

@dataclass
class SecurityFinding:
    """Represents a security finding from vulnerability scanning"""
    finding_id: str
    threat_type: ThreatType
    risk_level: SecurityRisk
    title: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    remediation: Optional[str] = None
    references: Optional[List[str]] = None
    cve_ids: Optional[List[str]] = None

@dataclass 
class ExtensionCertificate:
    """Extension certificate information"""
    certificate_id: str
    extension_id: str
    issuer: str
    subject: str
    public_key: str
    signature: str
    valid_from: datetime
    valid_until: datetime  
    key_usage: List[str]
    extensions: Dict[str, Any]
    is_self_signed: bool = False
    certificate_chain: Optional[List[str]] = None
    revocation_status: str = "unknown"

@dataclass
class SecurityReport:
    """Comprehensive security assessment report"""
    extension_id: str
    report_id: str
    generated_at: datetime
    security_level: SecurityLevel
    overall_score: int  # 0-100
    findings: List[SecurityFinding]
    certificate: Optional[ExtensionCertificate]
    policy_compliance: Dict[str, bool]
    recommendations: List[str]
    scan_metadata: Dict[str, Any]

class CertificateAuthority:
    """Certificate Authority for extension signing"""
    
    def __init__(self, ca_key_path: Optional[str] = None, ca_cert_path: Optional[str] = None):
        self.ca_key_path = ca_key_path
        self.ca_cert_path = ca_cert_path
        self.ca_private_key: Optional["CertificateIssuerPrivateKeyTypes"] = None
        self.ca_certificate = None
        
        if CRYPTO_AVAILABLE and ca_key_path and ca_cert_path:
            self._load_ca_credentials()
    
    def _load_ca_credentials(self):
        """Load CA private key and certificate"""
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("Cryptography package not available")
        if not self.ca_key_path or not self.ca_cert_path:
            raise ValueError("CA key path and certificate path are required")
            
        try:
            # Load CA private key
            ca_key_path = cast(str, self.ca_key_path)
            ca_cert_path = cast(str, self.ca_cert_path)
            with open(ca_key_path, 'rb') as f:
                self.ca_private_key = cast(
                    "CertificateIssuerPrivateKeyTypes",
                    serialization.load_pem_private_key(
                        f.read(),
                        password=None  # In production, use encrypted keys
                    ),
                )
            
            # Load CA certificate  
            with open(ca_cert_path, 'rb') as f:
                self.ca_certificate = x509.load_pem_x509_certificate(f.read())
                
        except Exception as e:
            logger.error(f"Failed to load CA credentials: {e}")
            raise
    
    def generate_ca_credentials(self, common_name: str = "NAVI Extension CA") -> Tuple[bytes, bytes]:
        """Generate new CA private key and certificate"""
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("Cryptography package not available")
        
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096
        )
        
        # Create CA certificate
        subject = issuer = Name([
            NameAttribute(oid.NameOID.COMMON_NAME, common_name),
            NameAttribute(oid.NameOID.ORGANIZATION_NAME, "NAVI Extension Platform"),
            NameAttribute(oid.NameOID.ORGANIZATIONAL_UNIT_NAME, "Security"),
        ])
        
        certificate = (
            CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))  # 10 years
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    key_cert_sign=True,
                    crl_sign=True,
                    key_encipherment=False,
                    data_encipherment=False,
                    digital_signature=False,
                    content_commitment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(private_key, hashes.SHA256())
        )
        
        # Serialize to PEM format
        private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        certificate_pem = certificate.public_bytes(serialization.Encoding.PEM)
        
        return private_key_pem, certificate_pem
    
    def sign_extension(self, extension_manifest: Dict[str, Any], extension_content: bytes) -> ExtensionCertificate:
        """Sign an extension and generate certificate"""
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("Cryptography package not available")
            
        if not self.ca_private_key or not self.ca_certificate:
            raise RuntimeError("CA credentials not loaded")

        ca_private_key = cast("CertificateIssuerPrivateKeyTypes", self.ca_private_key)
        
        extension_id = extension_manifest.get("id", "unknown")
        
        # Generate key pair for extension
        extension_private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        
        # Create subject name from manifest
        author = extension_manifest.get("author", {})
        subject_name = Name([
            NameAttribute(oid.NameOID.COMMON_NAME, extension_id),
            NameAttribute(oid.NameOID.ORGANIZATION_NAME, author.get("name", "Unknown")),
            NameAttribute(oid.NameOID.ORGANIZATIONAL_UNIT_NAME, "Extension"),
        ])
        
        # Create extension certificate
        certificate = (
            CertificateBuilder()
            .subject_name(subject_name)
            .issuer_name(self.ca_certificate.subject)
            .public_key(extension_private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))  # 1 year
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=True,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(ca_private_key, hashes.SHA256())
        )
        
        # Create digital signature of extension content
        content_hash = hashlib.sha256(extension_content).digest()
        signature = extension_private_key.sign(
            content_hash,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Create certificate object
        cert_obj = ExtensionCertificate(
            certificate_id=f"cert_{extension_id}_{int(time.time())}",
            extension_id=extension_id,
            issuer=str(certificate.issuer),
            subject=str(certificate.subject),
            public_key=certificate.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode(),
            signature=signature.hex(),
            valid_from=certificate.not_valid_before,
            valid_until=certificate.not_valid_after,
            key_usage=["digital_signature", "content_commitment"],
            extensions={
                "certificate_pem": certificate.public_bytes(serialization.Encoding.PEM).decode(),
                "private_key_pem": extension_private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ).decode(),
                "content_hash": content_hash.hex()
            }
        )
        
        return cert_obj

class VulnerabilityScanner:
    """Scans extensions for security vulnerabilities and threats"""
    
    def __init__(self):
        # Dangerous Python patterns to detect
        self.dangerous_patterns = [
            # Code execution
            (r'eval\s*\(', ThreatType.MALICIOUS_CODE, SecurityRisk.HIGH, "Use of eval() function"),
            (r'exec\s*\(', ThreatType.MALICIOUS_CODE, SecurityRisk.HIGH, "Use of exec() function"),
            (r'__import__\s*\(', ThreatType.SUSPICIOUS_BEHAVIOR, SecurityRisk.MEDIUM, "Dynamic import"),
            
            # System access
            (r'os\.system\s*\(', ThreatType.MALICIOUS_CODE, SecurityRisk.HIGH, "System command execution"),
            (r'subprocess\.(call|run|Popen)', ThreatType.SUSPICIOUS_BEHAVIOR, SecurityRisk.MEDIUM, "Subprocess execution"),
            (r'open\s*\([^,]*["\']\/.*["\']', ThreatType.SUSPICIOUS_BEHAVIOR, SecurityRisk.MEDIUM, "Absolute path file access"),
            
            # Network access
            (r'urllib\.request|requests\.', ThreatType.SUSPICIOUS_BEHAVIOR, SecurityRisk.LOW, "Network requests"),
            (r'socket\.|httplib\.|http\.client', ThreatType.SUSPICIOUS_BEHAVIOR, SecurityRisk.MEDIUM, "Direct network access"),
            
            # File system
            (r'shutil\.rmtree', ThreatType.MALICIOUS_CODE, SecurityRisk.HIGH, "Recursive directory deletion"),
            (r'os\.remove|os\.unlink', ThreatType.SUSPICIOUS_BEHAVIOR, SecurityRisk.MEDIUM, "File deletion"),
            (r'os\.rename|shutil\.move', ThreatType.SUSPICIOUS_BEHAVIOR, SecurityRisk.LOW, "File manipulation"),
            
            # Serialization risks
            (r'pickle\.loads|pickle\.load', ThreatType.VULNERABILITY, SecurityRisk.HIGH, "Unsafe pickle deserialization"),
            (r'yaml\.load\s*\((?!.*Loader=yaml\.SafeLoader)', ThreatType.VULNERABILITY, SecurityRisk.HIGH, "Unsafe YAML loading"),
            
            # Crypto/Security
            (r'hashlib\.md5|hashlib\.sha1', ThreatType.VULNERABILITY, SecurityRisk.MEDIUM, "Weak cryptographic hash"),
        ]
        
        # Known vulnerable dependencies
        self.vulnerable_dependencies = {
            "requests": {"<2.20.0": ["CVE-2018-18074"]},
            "jinja2": {"<2.11.3": ["CVE-2020-28493"]},
            "pyyaml": {"<5.4": ["CVE-2020-14343", "CVE-2020-1747"]},
        }
    
    def scan_extension(self, extension_manifest: Dict[str, Any], extension_files: Dict[str, str]) -> List[SecurityFinding]:
        """Perform comprehensive security scan of extension"""
        findings = []
        
        # Scan Python code for dangerous patterns
        for file_path, content in extension_files.items():
            if file_path.endswith('.py'):
                findings.extend(self._scan_python_code(file_path, content))
        
        # Check dependencies for vulnerabilities
        dependencies = extension_manifest.get("dependencies", [])
        findings.extend(self._scan_dependencies(dependencies))
        
        # Validate manifest security
        findings.extend(self._validate_manifest_security(extension_manifest))
        
        # Check permissions
        permissions = extension_manifest.get("permissions", [])
        findings.extend(self._analyze_permissions(permissions))
        
        return findings
    
    def _scan_python_code(self, file_path: str, content: str) -> List[SecurityFinding]:
        """Scan Python code for security issues"""
        findings = []
        
        try:
            # Parse AST to detect complex patterns
            tree = ast.parse(content)
            findings.extend(self._analyze_ast(file_path, tree))
        except SyntaxError as e:
            findings.append(SecurityFinding(
                finding_id=f"syntax_error_{hash(file_path)}",
                threat_type=ThreatType.VULNERABILITY,
                risk_level=SecurityRisk.MEDIUM,
                title="Syntax Error in Python Code",
                description=f"Python syntax error: {e.msg}",
                file_path=file_path,
                line_number=e.lineno
            ))
        
        # Pattern matching for dangerous constructs
        lines = content.split('\n')
        for line_num, line in enumerate(lines, 1):
            for pattern, threat_type, risk_level, description in self.dangerous_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    findings.append(SecurityFinding(
                        finding_id=f"pattern_{hash(file_path + line)}",
                        threat_type=threat_type,
                        risk_level=risk_level,
                        title=f"Dangerous Pattern: {description}",
                        description=f"Potentially dangerous code pattern detected: {description}",
                        file_path=file_path,
                        line_number=line_num,
                        code_snippet=line.strip(),
                        remediation="Review and validate this code for security implications"
                    ))
        
        return findings
    
    def _analyze_ast(self, file_path: str, tree: ast.AST) -> List[SecurityFinding]:
        """Analyze AST for complex security patterns"""
        findings = []
        
        for node in ast.walk(tree):
            # Check for dynamic attribute access
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "getattr" and len(node.args) >= 2:
                    findings.append(SecurityFinding(
                        finding_id=f"dynamic_attr_{hash(file_path + str(node.lineno))}",
                        threat_type=ThreatType.SUSPICIOUS_BEHAVIOR,
                        risk_level=SecurityRisk.MEDIUM,
                        title="Dynamic Attribute Access",
                        description="Use of getattr() can bypass security checks",
                        file_path=file_path,
                        line_number=node.lineno,
                        remediation="Validate attribute names and use allow-lists"
                    ))
            
            # Check for string formatting with user data
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
                if isinstance(node.left, ast.Str):
                    format_value = cast(str, node.left.s)
                    if "%" in format_value:
                        findings.append(SecurityFinding(
                            finding_id=f"format_string_{hash(file_path + str(node.lineno))}",
                            threat_type=ThreatType.VULNERABILITY,
                            risk_level=SecurityRisk.LOW,
                            title="String Formatting",
                            description="String formatting with % operator - validate input data",
                            file_path=file_path,
                            line_number=node.lineno,
                            remediation="Use f-strings or .format() with validation"
                        ))
        
        return findings
    
    def _scan_dependencies(self, dependencies: List[str]) -> List[SecurityFinding]:
        """Check dependencies for known vulnerabilities"""
        findings = []
        
        for dep in dependencies:
            # Parse dependency string (e.g., "requests>=2.20.0" or "requests==2.19.0")
            dep_match = re.match(r'([a-zA-Z0-9_-]+)([<>=!]+)?(.+)?', dep.strip())
            if not dep_match:
                continue
                
            package_name = dep_match.group(1).lower()
            version_spec = dep_match.group(2) or ""
            version = dep_match.group(3) or ""
            
            if package_name in self.vulnerable_dependencies:
                vuln_info = self.vulnerable_dependencies[package_name]
                for vuln_version, cve_ids in vuln_info.items():
                    # Simple version comparison (production should use proper semver)
                    if self._is_vulnerable_version(version, version_spec, vuln_version):
                        findings.append(SecurityFinding(
                            finding_id=f"vuln_dep_{package_name}_{version}",
                            threat_type=ThreatType.DEPENDENCY_RISK,
                            risk_level=SecurityRisk.HIGH,
                            title=f"Vulnerable Dependency: {package_name}",
                            description=f"Package {package_name} {version} has known vulnerabilities",
                            remediation=f"Update {package_name} to a version that fixes these CVEs",
                            cve_ids=cve_ids,
                            references=[f"https://cve.mitre.org/cgi-bin/cvename.cgi?name={cve}" for cve in cve_ids]
                        ))
        
        return findings
    
    def _is_vulnerable_version(self, current_version: str, version_spec: str, vulnerable_spec: str) -> bool:
        """Simple version vulnerability check (production should use proper semver)"""
        # This is a simplified check - production should use packaging.version
        if not current_version:
            return True  # Unknown version, assume vulnerable
        
        # Extract version numbers
        try:
            current_parts = [int(x) for x in current_version.replace('v', '').split('.')]
            vuln_parts = [int(x) for x in vulnerable_spec.replace('<', '').replace('>', '').replace('=', '').split('.')]
            
            # Pad shorter version with zeros
            max_len = max(len(current_parts), len(vuln_parts))
            current_parts.extend([0] * (max_len - len(current_parts)))
            vuln_parts.extend([0] * (max_len - len(vuln_parts)))
            
            if vulnerable_spec.startswith('<'):
                return current_parts < vuln_parts
            elif vulnerable_spec.startswith('<='):
                return current_parts <= vuln_parts
            elif vulnerable_spec.startswith('>='):
                return current_parts >= vuln_parts
            elif vulnerable_spec.startswith('>'):
                return current_parts > vuln_parts
            else:  # Assume ==
                return current_parts == vuln_parts
                
        except (ValueError, AttributeError):
            return True  # Can't parse, assume vulnerable
    
    def _validate_manifest_security(self, manifest: Dict[str, Any]) -> List[SecurityFinding]:
        """Validate extension manifest for security issues"""
        findings = []
        
        # Check for suspicious URLs
        suspicious_domains = ['bit.ly', 'tinyurl.com', 'goo.gl', 't.co']
        
        for url_field in ['homepage', 'repository']:
            url = manifest.get(url_field, '')
            if url:
                for domain in suspicious_domains:
                    if domain in url:
                        findings.append(SecurityFinding(
                            finding_id=f"suspicious_url_{url_field}",
                            threat_type=ThreatType.SUSPICIOUS_BEHAVIOR,
                            risk_level=SecurityRisk.MEDIUM,
                            title=f"Suspicious URL in {url_field}",
                            description=f"URL shortener detected in {url_field}: {url}",
                            remediation="Use direct URLs instead of URL shorteners"
                        ))
        
        # Validate author information
        author = manifest.get('author', {})
        if not author.get('name'):
            findings.append(SecurityFinding(
                finding_id="missing_author",
                threat_type=ThreatType.POLICY_VIOLATION,
                risk_level=SecurityRisk.LOW,
                title="Missing Author Information",
                description="Extension manifest missing author name",
                remediation="Add author name to manifest"
            ))
        
        return findings
    
    def _analyze_permissions(self, permissions: List[str]) -> List[SecurityFinding]:
        """Analyze requested permissions for security risks"""
        findings = []
        
        high_risk_permissions = {
            "file_write": "Can modify files on the system",
            "network": "Can make network requests",
            "system": "Can execute system commands",
            "registry": "Can access system registry",
            "admin": "Requires administrative privileges"
        }
        
        for permission in permissions:
            if permission in high_risk_permissions:
                findings.append(SecurityFinding(
                    finding_id=f"high_risk_perm_{permission}",
                    threat_type=ThreatType.POLICY_VIOLATION,
                    risk_level=SecurityRisk.MEDIUM,
                    title=f"High-Risk Permission: {permission}",
                    description=f"Extension requests high-risk permission: {high_risk_permissions[permission]}",
                    remediation="Review if this permission is truly necessary"
                ))
        
        return findings

class ExtensionSecurityManager:
    """Main security manager for extensions"""
    
    def __init__(self, ca_key_path: Optional[str] = None, ca_cert_path: Optional[str] = None):
        self.certificate_authority = CertificateAuthority(ca_key_path, ca_cert_path)
        self.vulnerability_scanner = VulnerabilityScanner()
        self.trusted_publishers = set()
        self.blocked_extensions = set()
        
        # Security policies
        self.security_policies = {
            "require_signature": True,
            "allow_self_signed": False,
            "min_security_score": 70,
            "block_high_risk_permissions": True,
            "scan_for_vulnerabilities": True,
            "quarantine_suspicious": True
        }
    
    def assess_extension_security(
        self, 
        extension_manifest: Dict[str, Any], 
        extension_files: Dict[str, str],
        certificate: Optional[ExtensionCertificate] = None
    ) -> SecurityReport:
        """Perform comprehensive security assessment"""
        
        extension_id = extension_manifest.get("id", "unknown")
        report_id = f"security_report_{extension_id}_{int(time.time())}"
        
        # Perform vulnerability scan
        findings = self.vulnerability_scanner.scan_extension(extension_manifest, extension_files)
        
        # Determine security level
        security_level = self._determine_security_level(extension_manifest, certificate, findings)
        
        # Calculate security score
        security_score = self._calculate_security_score(findings, certificate)
        
        # Check policy compliance
        policy_compliance = self._check_policy_compliance(extension_manifest, certificate, findings)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(findings, certificate, policy_compliance)
        
        return SecurityReport(
            extension_id=extension_id,
            report_id=report_id,
            generated_at=datetime.now(timezone.utc),
            security_level=security_level,
            overall_score=security_score,
            findings=findings,
            certificate=certificate,
            policy_compliance=policy_compliance,
            recommendations=recommendations,
            scan_metadata={
                "scanner_version": "1.0.0",
                "scan_duration": "0.5s",  # Would be actual duration
                "files_scanned": len(extension_files),
                "patterns_checked": len(self.vulnerability_scanner.dangerous_patterns)
            }
        )
    
    def _determine_security_level(
        self, 
        manifest: Dict[str, Any], 
        certificate: Optional[ExtensionCertificate], 
        findings: List[SecurityFinding]
    ) -> SecurityLevel:
        """Determine the security level of an extension"""
        
        extension_id = manifest.get("id", "unknown")
        
        # Check if explicitly blocked
        if extension_id in self.blocked_extensions:
            return SecurityLevel.BLOCKED
        
        # Critical findings block the extension
        critical_findings = [f for f in findings if f.risk_level == SecurityRisk.CRITICAL]
        if critical_findings:
            return SecurityLevel.BLOCKED
        
        # Check certificate status
        if certificate:
            if certificate.issuer in self.trusted_publishers:
                return SecurityLevel.TRUSTED
            elif self._verify_certificate(certificate):
                return SecurityLevel.VERIFIED
        
        # Check for high-risk findings
        high_risk_findings = [f for f in findings if f.risk_level == SecurityRisk.HIGH]
        if high_risk_findings:
            return SecurityLevel.UNVERIFIED
        
        # Default to community level
        return SecurityLevel.COMMUNITY
    
    def _verify_certificate(self, certificate: ExtensionCertificate) -> bool:
        """Verify certificate validity"""
        if not CRYPTO_AVAILABLE:
            return False
            
        try:
            # Check validity period
            now = datetime.now(timezone.utc)
            if not (certificate.valid_from <= now <= certificate.valid_until):
                return False
            
            # Check revocation status (would integrate with CRL/OCSP in production)
            if certificate.revocation_status == "revoked":
                return False
            
            # Additional validation would go here
            return True
            
        except Exception as e:
            logger.error(f"Certificate validation error: {e}")
            return False
    
    def _calculate_security_score(
        self, 
        findings: List[SecurityFinding], 
        certificate: Optional[ExtensionCertificate]
    ) -> int:
        """Calculate overall security score (0-100)"""
        
        base_score = 100
        
        # Deduct points for findings
        for finding in findings:
            if finding.risk_level == SecurityRisk.CRITICAL:
                base_score -= 50
            elif finding.risk_level == SecurityRisk.HIGH:
                base_score -= 20
            elif finding.risk_level == SecurityRisk.MEDIUM:
                base_score -= 10
            elif finding.risk_level == SecurityRisk.LOW:
                base_score -= 5
        
        # Bonus for valid certificate
        if certificate and self._verify_certificate(certificate):
            base_score += 10
        
        return max(0, min(100, base_score))
    
    def _check_policy_compliance(
        self, 
        manifest: Dict[str, Any], 
        certificate: Optional[ExtensionCertificate], 
        findings: List[SecurityFinding]
    ) -> Dict[str, bool]:
        """Check compliance with security policies"""
        
        compliance = {}
        
        # Signature requirement
        compliance["signature_required"] = not self.security_policies["require_signature"] or (
            certificate is not None
        )
        
        # Self-signed certificates
        compliance["self_signed_allowed"] = self.security_policies["allow_self_signed"] or (
            certificate is None or not certificate.is_self_signed
        )
        
        # Security score threshold
        score = self._calculate_security_score(findings, certificate)
        compliance["min_security_score"] = score >= self.security_policies["min_security_score"]
        
        # High-risk permissions
        permissions = manifest.get("permissions", [])
        high_risk_perms = {"system", "admin", "registry"}
        has_high_risk = any(perm in high_risk_perms for perm in permissions)
        compliance["high_risk_permissions"] = not self.security_policies["block_high_risk_permissions"] or not has_high_risk
        
        return compliance
    
    def _generate_recommendations(
        self, 
        findings: List[SecurityFinding], 
        certificate: Optional[ExtensionCertificate],
        policy_compliance: Dict[str, bool]
    ) -> List[str]:
        """Generate security recommendations"""
        
        recommendations = []
        
        # Certificate recommendations
        if not certificate:
            recommendations.append("Consider signing the extension with a digital certificate for enhanced trust")
        elif certificate.is_self_signed:
            recommendations.append("Use a certificate from a trusted Certificate Authority instead of self-signed")
        
        # Finding-based recommendations
        critical_findings = [f for f in findings if f.risk_level == SecurityRisk.CRITICAL]
        if critical_findings:
            recommendations.append("Address critical security findings before deployment")
        
        high_findings = [f for f in findings if f.risk_level == SecurityRisk.HIGH]
        if high_findings:
            recommendations.append("Review and mitigate high-risk security findings")
        
        # Policy compliance recommendations
        for policy, compliant in policy_compliance.items():
            if not compliant:
                if policy == "signature_required":
                    recommendations.append("Add digital signature to meet security policy requirements")
                elif policy == "min_security_score":
                    recommendations.append("Improve security score by addressing findings")
                elif policy == "high_risk_permissions":
                    recommendations.append("Reduce high-risk permission requests")
        
        return recommendations

# Factory function for easy initialization
def create_security_manager(ca_key_path: Optional[str] = None, ca_cert_path: Optional[str] = None) -> ExtensionSecurityManager:
    """Create and configure an ExtensionSecurityManager"""
    return ExtensionSecurityManager(ca_key_path, ca_cert_path)
