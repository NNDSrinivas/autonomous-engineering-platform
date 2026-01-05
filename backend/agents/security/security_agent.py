"""
Security Agent for Navi - Advanced SAST and CVE Analysis
Comprehensive security scanning with automated patch generation.
Equivalent to GitHub Advanced Security + Snyk + CodeQL but with AI-powered fixes.
"""

import json
import logging
import asyncio
import re
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from pathlib import Path
import hashlib

try:
    from ...services.llm import call_llm
    from ...memory.episodic_memory import EpisodicMemory, MemoryEventType
except ImportError:
    from backend.services.llm import call_llm
    from backend.memory.episodic_memory import EpisodicMemory, MemoryEventType


class SecurityFinding:
    """Represents a security finding with metadata."""

    def __init__(
        self,
        finding_id: str,
        severity: str,
        confidence: str,
        title: str,
        description: str,
        file_path: str,
        line_number: int,
        cwe_id: Optional[str] = None,
        cvss_score: Optional[float] = None,
        remediation: Optional[str] = None,
    ):
        self.finding_id = finding_id
        self.severity = severity  # critical, high, medium, low
        self.confidence = confidence  # high, medium, low
        self.title = title
        self.description = description
        self.file_path = file_path
        self.line_number = line_number
        self.cwe_id = cwe_id
        self.cvss_score = cvss_score
        self.remediation = remediation
        self.discovered_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert finding to dictionary representation."""
        return {
            "finding_id": self.finding_id,
            "severity": self.severity,
            "confidence": self.confidence,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "cwe_id": self.cwe_id,
            "cvss_score": self.cvss_score,
            "remediation": self.remediation,
            "discovered_at": self.discovered_at.isoformat(),
        }


class SecurityAgent:
    """
    Advanced security analysis agent that performs comprehensive SAST and dependency scanning.

    Capabilities:
    - Static Application Security Testing (SAST)
    - Dependency vulnerability scanning
    - Custom security rule evaluation
    - AI-powered patch generation
    - Security pattern recognition
    - Compliance checking
    - Risk assessment and prioritization
    """

    def __init__(
        self,
        workspace_root: str,
        memory: Optional[EpisodicMemory] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize Security Agent with workspace and configuration.

        Args:
            workspace_root: Root directory of the codebase to scan
            memory: Episodic memory for learning security patterns
            config: Security scanning configuration
        """
        self.workspace_root = Path(workspace_root)
        self.memory = memory or EpisodicMemory()
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # Security scanning tools configuration
        self.tools_config = {
            "bandit": {
                "enabled": True,
                "confidence_level": "medium",  # high, medium, low
                "severity_level": "medium",
            },
            "semgrep": {
                "enabled": True,
                "ruleset": "auto",  # auto, security, owasp-top-10, etc.
            },
            "npm_audit": {
                "enabled": True,
                "audit_level": "moderate",  # info, low, moderate, high, critical
            },
            "pip_audit": {"enabled": True},
            "custom_rules": {"enabled": True},
        }

        # Severity scoring
        self.severity_scores = {
            "critical": 10.0,
            "high": 7.5,
            "medium": 5.0,
            "low": 2.5,
            "info": 1.0,
        }

        self.logger.info(f"SecurityAgent initialized for workspace: {workspace_root}")

    async def comprehensive_scan(
        self,
        scan_types: Optional[List[str]] = None,
        include_dependencies: bool = True,
        generate_patches: bool = True,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive security scan of the workspace.

        Args:
            scan_types: List of scan types to perform (sast, dependencies, secrets)
            include_dependencies: Whether to scan dependencies
            generate_patches: Whether to generate auto-fix patches

        Returns:
            Comprehensive security analysis report
        """
        scan_start = datetime.utcnow()
        scan_id = f"sec_scan_{scan_start.strftime('%Y%m%d_%H%M%S')}"

        self.logger.info(f"Starting comprehensive security scan: {scan_id}")

        try:
            # Default scan types
            scan_types = scan_types or ["sast", "dependencies", "secrets", "custom"]

            scan_results = {
                "scan_id": scan_id,
                "timestamp": scan_start.isoformat(),
                "workspace_root": str(self.workspace_root),
                "scan_types": scan_types,
                "findings": [],
                "summary": {},
                "patches": [],
                "recommendations": [],
                "scan_duration_seconds": 0,
            }

            # Run different types of scans
            if "sast" in scan_types:
                sast_findings = await self._run_sast_scan()
                scan_results["findings"].extend(sast_findings)

            if "dependencies" in scan_types and include_dependencies:
                dep_findings = await self._run_dependency_scan()
                scan_results["findings"].extend(dep_findings)

            if "secrets" in scan_types:
                secret_findings = await self._run_secrets_scan()
                scan_results["findings"].extend(secret_findings)

            if "custom" in scan_types:
                custom_findings = await self._run_custom_security_rules()
                scan_results["findings"].extend(custom_findings)

            # Generate summary
            scan_results["summary"] = self._generate_scan_summary(
                scan_results["findings"]
            )

            # Generate patches if requested
            if generate_patches and scan_results["findings"]:
                patches = await self._generate_security_patches(
                    scan_results["findings"]
                )
                scan_results["patches"] = patches

            # Generate recommendations
            scan_results["recommendations"] = (
                await self._generate_security_recommendations(
                    scan_results["findings"], scan_results["summary"]
                )
            )

            # Calculate scan duration
            scan_results["scan_duration_seconds"] = (
                datetime.utcnow() - scan_start
            ).total_seconds()

            # Record in memory
            await self._record_scan_in_memory(scan_results)

            self.logger.info(
                f"Security scan {scan_id} completed. Found {len(scan_results['findings'])} issues."
            )
            return scan_results

        except Exception as e:
            self.logger.error(f"Security scan failed: {e}")
            return {
                "scan_id": scan_id,
                "error": str(e),
                "success": False,
                "timestamp": scan_start.isoformat(),
            }

    async def _run_sast_scan(self) -> List[SecurityFinding]:
        """
        Run Static Application Security Testing (SAST) using multiple tools.

        Returns:
            List of SAST security findings
        """
        findings = []

        # Run Bandit for Python files
        if self.tools_config["bandit"]["enabled"]:
            bandit_findings = await self._run_bandit_scan()
            findings.extend(bandit_findings)

        # Run Semgrep for multiple languages
        if self.tools_config["semgrep"]["enabled"]:
            semgrep_findings = await self._run_semgrep_scan()
            findings.extend(semgrep_findings)

        # Run custom SAST rules
        custom_sast_findings = await self._run_custom_sast_rules()
        findings.extend(custom_sast_findings)

        return findings

    async def _run_bandit_scan(self) -> List[SecurityFinding]:
        """
        Run Bandit security scanner for Python files.

        Returns:
            List of Bandit findings converted to SecurityFinding objects
        """
        findings = []

        try:
            # Check if bandit is available
            bandit_cmd = [
                "bandit",
                "-r",
                str(self.workspace_root),
                "-f",
                "json",
                "-ll",  # Low confidence level
            ]

            # Run bandit in a subprocess
            result = await asyncio.create_subprocess_exec(
                *bandit_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace_root),
            )

            stdout, stderr = await result.communicate()

            if result.returncode == 0 or result.returncode == 1:  # 1 means issues found
                # Parse Bandit JSON output
                try:
                    bandit_data = json.loads(stdout.decode())

                    for result_item in bandit_data.get("results", []):
                        finding = SecurityFinding(
                            finding_id=f"bandit_{hashlib.md5(str(result_item).encode()).hexdigest()[:8]}",
                            severity=result_item.get(
                                "issue_severity", "medium"
                            ).lower(),
                            confidence=result_item.get(
                                "issue_confidence", "medium"
                            ).lower(),
                            title=f"Bandit: {result_item.get('test_name', 'Security Issue')}",
                            description=result_item.get("issue_text", ""),
                            file_path=str(
                                Path(result_item.get("filename", "")).relative_to(
                                    self.workspace_root
                                )
                            ),
                            line_number=result_item.get("line_number", 0),
                            cwe_id=result_item.get("test_id", ""),
                            remediation=result_item.get("more_info", ""),
                        )
                        findings.append(finding)

                except json.JSONDecodeError:
                    self.logger.warning("Failed to parse Bandit JSON output")

        except FileNotFoundError:
            self.logger.info("Bandit not available, skipping Python SAST scan")
        except Exception as e:
            self.logger.warning(f"Bandit scan failed: {e}")

        return findings

    async def _run_semgrep_scan(self) -> List[SecurityFinding]:
        """
        Run Semgrep security scanner for multiple languages.

        Returns:
            List of Semgrep findings
        """
        findings = []

        try:
            # Check if semgrep is available
            semgrep_cmd = [
                "semgrep",
                "--config=auto",  # Use automatic ruleset
                "--json",
                str(self.workspace_root),
            ]

            result = await asyncio.create_subprocess_exec(
                *semgrep_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                try:
                    semgrep_data = json.loads(stdout.decode())

                    for result_item in semgrep_data.get("results", []):
                        # Map Semgrep severity to our scale
                        semgrep_severity = result_item.get("extra", {}).get(
                            "severity", "INFO"
                        )
                        severity_mapping = {
                            "ERROR": "high",
                            "WARNING": "medium",
                            "INFO": "low",
                        }

                        finding = SecurityFinding(
                            finding_id=f"semgrep_{hashlib.md5(str(result_item).encode()).hexdigest()[:8]}",
                            severity=severity_mapping.get(semgrep_severity, "medium"),
                            confidence="high",  # Semgrep generally has high confidence
                            title=f"Semgrep: {result_item.get('check_id', 'Security Issue')}",
                            description=result_item.get("extra", {}).get("message", ""),
                            file_path=str(
                                Path(result_item.get("path", "")).relative_to(
                                    self.workspace_root
                                )
                            ),
                            line_number=result_item.get("start", {}).get("line", 0),
                            remediation=result_item.get("extra", {}).get("fix", ""),
                        )
                        findings.append(finding)

                except json.JSONDecodeError:
                    self.logger.warning("Failed to parse Semgrep JSON output")

        except FileNotFoundError:
            self.logger.info("Semgrep not available, skipping multi-language SAST scan")
        except Exception as e:
            self.logger.warning(f"Semgrep scan failed: {e}")

        return findings

    async def _run_custom_sast_rules(self) -> List[SecurityFinding]:
        """
        Run custom SAST rules using pattern matching and AI analysis.

        Returns:
            List of custom security findings
        """
        findings = []

        # Define custom security patterns
        security_patterns = [
            {
                "pattern": r"eval\s*\(",
                "severity": "high",
                "title": "Dangerous eval() usage",
                "description": "Use of eval() can lead to code injection vulnerabilities",
                "cwe_id": "CWE-95",
            },
            {
                "pattern": r"exec\s*\(",
                "severity": "high",
                "title": "Dangerous exec() usage",
                "description": "Use of exec() can lead to code injection vulnerabilities",
                "cwe_id": "CWE-95",
            },
            {
                "pattern": r"shell=True",
                "severity": "medium",
                "title": "Shell injection risk",
                "description": "Using shell=True can lead to command injection",
                "cwe_id": "CWE-78",
            },
            {
                "pattern": r'password\s*=\s*["\'][^"\']+["\']',
                "severity": "high",
                "title": "Hardcoded password",
                "description": "Password appears to be hardcoded in source",
                "cwe_id": "CWE-798",
            },
            {
                "pattern": r'api[_-]?key\s*=\s*["\'][^"\']+["\']',
                "severity": "high",
                "title": "Hardcoded API key",
                "description": "API key appears to be hardcoded in source",
                "cwe_id": "CWE-798",
            },
        ]

        # Scan files for security patterns
        for file_path in self._get_scannable_files():
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    lines = content.split("\n")

                for pattern_config in security_patterns:
                    pattern = pattern_config["pattern"]

                    for line_num, line in enumerate(lines, 1):
                        if re.search(pattern, line, re.IGNORECASE):
                            finding = SecurityFinding(
                                finding_id=f"custom_{hashlib.md5(f'{file_path}:{line_num}:{pattern}'.encode()).hexdigest()[:8]}",
                                severity=pattern_config["severity"],
                                confidence="medium",
                                title=pattern_config["title"],
                                description=pattern_config["description"],
                                file_path=str(
                                    Path(file_path).relative_to(self.workspace_root)
                                ),
                                line_number=line_num,
                                cwe_id=pattern_config.get("cwe_id"),
                            )
                            findings.append(finding)

            except Exception as e:
                self.logger.debug(f"Error scanning {file_path}: {e}")

        return findings

    async def _run_dependency_scan(self) -> List[SecurityFinding]:
        """
        Scan dependencies for known vulnerabilities.

        Returns:
            List of dependency vulnerability findings
        """
        findings = []

        # Scan npm packages
        npm_findings = await self._scan_npm_dependencies()
        findings.extend(npm_findings)

        # Scan Python packages
        python_findings = await self._scan_python_dependencies()
        findings.extend(python_findings)

        return findings

    async def _scan_npm_dependencies(self) -> List[SecurityFinding]:
        """
        Scan npm dependencies for vulnerabilities.

        Returns:
            List of npm vulnerability findings
        """
        findings = []

        try:
            package_json_path = self.workspace_root / "package.json"
            if not package_json_path.exists():
                return findings

            # Run npm audit
            audit_cmd = ["npm", "audit", "--json"]

            result = await asyncio.create_subprocess_exec(
                *audit_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace_root),
            )

            stdout, stderr = await result.communicate()

            try:
                audit_data = json.loads(stdout.decode())

                # Parse npm audit results
                vulnerabilities = audit_data.get("vulnerabilities", {})

                for package_name, vuln_data in vulnerabilities.items():
                    severity = vuln_data.get("severity", "medium")

                    finding = SecurityFinding(
                        finding_id=f"npm_{hashlib.md5(f'{package_name}:{severity}'.encode()).hexdigest()[:8]}",
                        severity=severity,
                        confidence="high",
                        title=f"NPM Vulnerability: {package_name}",
                        description=vuln_data.get(
                            "title", f"Vulnerability in {package_name}"
                        ),
                        file_path="package.json",
                        line_number=0,
                        cwe_id=str(vuln_data.get("cwe", [])),
                        cvss_score=vuln_data.get("cvss", {}).get("score"),
                        remediation=f"Update {package_name} to version {vuln_data.get('fixAvailable', 'latest')}",
                    )
                    findings.append(finding)

            except json.JSONDecodeError:
                self.logger.warning("Failed to parse npm audit output")

        except FileNotFoundError:
            self.logger.info("npm not available, skipping Node.js dependency scan")
        except Exception as e:
            self.logger.warning(f"npm audit failed: {e}")

        return findings

    async def _scan_python_dependencies(self) -> List[SecurityFinding]:
        """
        Scan Python dependencies for vulnerabilities.

        Returns:
            List of Python vulnerability findings
        """
        findings = []

        try:
            # Check for requirements files
            req_files = ["requirements.txt", "Pipfile", "pyproject.toml"]
            has_python_deps = any((self.workspace_root / f).exists() for f in req_files)

            if not has_python_deps:
                return findings

            # Try using pip-audit if available
            audit_cmd = ["pip-audit", "--format=json"]

            result = await asyncio.create_subprocess_exec(
                *audit_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace_root),
            )

            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                try:
                    audit_data = json.loads(stdout.decode())

                    for vuln in audit_data:
                        package_name = vuln.get("package", "unknown")

                        finding = SecurityFinding(
                            finding_id=f"pip_{hashlib.md5(str(vuln).encode()).hexdigest()[:8]}",
                            severity=self._map_cvss_to_severity(
                                vuln.get("fix_versions", [])
                            ),
                            confidence="high",
                            title=f"Python Vulnerability: {package_name}",
                            description=vuln.get(
                                "description", f"Vulnerability in {package_name}"
                            ),
                            file_path="requirements.txt",  # Simplified
                            line_number=0,
                            cwe_id=vuln.get("cwe"),
                            cvss_score=vuln.get("cvss"),
                            remediation=f"Update {package_name} to a fixed version",
                        )
                        findings.append(finding)

                except json.JSONDecodeError:
                    self.logger.warning("Failed to parse pip-audit output")

        except FileNotFoundError:
            self.logger.info("pip-audit not available, skipping Python dependency scan")
        except Exception as e:
            self.logger.warning(f"Python dependency scan failed: {e}")

        return findings

    async def _run_secrets_scan(self) -> List[SecurityFinding]:
        """
        Scan for secrets and credentials in the codebase.

        Returns:
            List of secret findings
        """
        findings = []

        # Secret patterns to detect
        secret_patterns = [
            {
                "pattern": r"-----BEGIN [A-Z ]+-----",
                "title": "Private key detected",
                "severity": "critical",
            },
            {
                "pattern": r"sk-[a-zA-Z0-9]{48}",
                "title": "OpenAI API key detected",
                "severity": "high",
            },
            {
                "pattern": r"ghp_[a-zA-Z0-9]{36}",
                "title": "GitHub personal access token",
                "severity": "high",
            },
            {
                "pattern": r"AKIA[0-9A-Z]{16}",
                "title": "AWS access key detected",
                "severity": "high",
            },
            {
                "pattern": r"ya29\.[a-zA-Z0-9_-]+",
                "title": "Google OAuth token",
                "severity": "medium",
            },
        ]

        for file_path in self._get_scannable_files():
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    lines = content.split("\n")

                for pattern_config in secret_patterns:
                    pattern = pattern_config["pattern"]

                    for line_num, line in enumerate(lines, 1):
                        if re.search(pattern, line):
                            finding = SecurityFinding(
                                finding_id=f"secret_{hashlib.md5(f'{file_path}:{line_num}'.encode()).hexdigest()[:8]}",
                                severity=pattern_config["severity"],
                                confidence="high",
                                title=pattern_config["title"],
                                description=f"Potential secret found in {file_path}:{line_num}",
                                file_path=str(
                                    Path(file_path).relative_to(self.workspace_root)
                                ),
                                line_number=line_num,
                                cwe_id="CWE-798",  # Use of hard-coded credentials
                            )
                            findings.append(finding)

            except Exception as e:
                self.logger.debug(f"Error scanning {file_path} for secrets: {e}")

        return findings

    async def _run_custom_security_rules(self) -> List[SecurityFinding]:
        """
        Run custom security rules using AI analysis.

        Returns:
            List of custom security findings
        """
        findings = []

        # This would use AI to analyze code patterns for security issues
        # For now, return empty list - would implement AI-based analysis

        return findings

    async def _generate_security_patches(
        self, findings: List[SecurityFinding]
    ) -> List[Dict[str, Any]]:
        """
        Generate automated patches for security findings.

        Args:
            findings: List of security findings to generate patches for

        Returns:
            List of generated security patches
        """
        patches = []

        # Focus on high-severity, fixable issues
        patchable_findings = [
            f
            for f in findings
            if f.severity in ["critical", "high"] and f.confidence in ["high", "medium"]
        ][
            :5
        ]  # Limit to top 5 for performance

        for finding in patchable_findings:
            try:
                patch = await self._generate_single_security_patch(finding)
                if patch:
                    patches.append(patch)
            except Exception as e:
                self.logger.warning(
                    f"Failed to generate patch for {finding.finding_id}: {e}"
                )

        return patches

    async def _generate_single_security_patch(
        self, finding: SecurityFinding
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a patch for a single security finding.

        Args:
            finding: Security finding to patch

        Returns:
            Generated patch or None if generation failed
        """
        try:
            file_path = self.workspace_root / finding.file_path
            if not file_path.exists():
                return None

            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
                lines = file_content.split("\n")

            # Get context around the finding
            start_line = max(0, finding.line_number - 5)
            end_line = min(len(lines), finding.line_number + 5)
            context = "\n".join(lines[start_line:end_line])

            patch_prompt = f"""
            Generate a security patch for this vulnerability:

            FINDING:
            - Title: {finding.title}
            - Description: {finding.description}
            - Severity: {finding.severity}
            - CWE: {finding.cwe_id}
            - File: {finding.file_path}
            - Line: {finding.line_number}

            CONTEXT (around line {finding.line_number}):
            ```
            {context}
            ```

            FULL FILE CONTENT:
            ```
            {file_content[:2000]}  # Limit content for token efficiency
            ```

            Generate a precise patch that fixes this security issue while maintaining functionality.
            Return the patch in unified diff format.
            
            Focus on:
            1. Fixing the specific vulnerability
            2. Maintaining code functionality  
            3. Following security best practices
            4. Adding appropriate validation/sanitization
            """

            response = await call_llm(
                message=patch_prompt, context={}, model="gpt-4", mode="security_patch"
            )

            return {
                "finding_id": finding.finding_id,
                "file_path": finding.file_path,
                "patch_content": response.strip(),
                "severity": finding.severity,
                "title": finding.title,
                "generated_at": datetime.utcnow().isoformat(),
                "patch_type": "security_fix",
            }

        except Exception as e:
            self.logger.warning(
                f"Patch generation failed for {finding.finding_id}: {e}"
            )
            return None

    async def _generate_security_recommendations(
        self, findings: List[SecurityFinding], summary: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate security recommendations based on findings.

        Args:
            findings: List of all findings
            summary: Scan summary statistics

        Returns:
            List of security recommendations
        """
        recommendations_prompt = f"""
        Based on this security scan, provide actionable security recommendations:

        SCAN SUMMARY:
        {json.dumps(summary, indent=2)}

        TOP FINDINGS:
        {json.dumps([f.to_dict() for f in findings[:10]], indent=2)}

        Generate prioritized recommendations focusing on:
        1. Critical security fixes
        2. Security process improvements  
        3. Development best practices
        4. Preventive measures
        5. Tool and configuration recommendations

        Return as JSON array:
        [
            {{
                "priority": "critical|high|medium|low",
                "category": "fixes|process|tools|training",
                "title": "short recommendation title",
                "description": "detailed recommendation",
                "implementation_steps": ["step 1", "step 2"],
                "impact": "expected security improvement",
                "effort": "small|medium|large"
            }}
        ]
        """

        try:
            response = await call_llm(
                message=recommendations_prompt,
                context={},
                model="gpt-4",
                mode="security_analysis",
            )

            recommendations = json.loads(response)

            # Add metadata
            for i, rec in enumerate(recommendations):
                rec["recommendation_id"] = f"sec_rec_{i+1}"
                rec["generated_at"] = datetime.utcnow().isoformat()

            return recommendations

        except Exception as e:
            self.logger.warning(f"Recommendation generation failed: {e}")
            return [
                {
                    "title": "Review security findings manually",
                    "description": "Manual review recommended due to analysis failure",
                    "priority": "high",
                }
            ]

    def _generate_scan_summary(self, findings: List[SecurityFinding]) -> Dict[str, Any]:
        """
        Generate summary statistics from security findings.

        Args:
            findings: List of security findings

        Returns:
            Summary statistics dictionary
        """
        summary = {
            "total_findings": len(findings),
            "by_severity": {},
            "by_confidence": {},
            "by_cwe": {},
            "risk_score": 0.0,
            "critical_issues": 0,
            "patchable_issues": 0,
        }

        # Count by severity
        for severity in ["critical", "high", "medium", "low", "info"]:
            count = len([f for f in findings if f.severity == severity])
            summary["by_severity"][severity] = count

        # Count by confidence
        for confidence in ["high", "medium", "low"]:
            count = len([f for f in findings if f.confidence == confidence])
            summary["by_confidence"][confidence] = count

        # Count by CWE
        cwe_counts = {}
        for finding in findings:
            if finding.cwe_id:
                cwe_counts[finding.cwe_id] = cwe_counts.get(finding.cwe_id, 0) + 1
        summary["by_cwe"] = dict(
            sorted(cwe_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        )

        # Calculate risk score (0-100)
        risk_score = 0.0
        for finding in findings:
            severity_weight = self.severity_scores.get(finding.severity, 1.0)
            confidence_weight = {"high": 1.0, "medium": 0.7, "low": 0.4}.get(
                finding.confidence, 0.5
            )
            risk_score += severity_weight * confidence_weight

        summary["risk_score"] = min(100.0, risk_score)
        summary["critical_issues"] = summary["by_severity"].get(
            "critical", 0
        ) + summary["by_severity"].get("high", 0)
        summary["patchable_issues"] = len(
            [f for f in findings if f.confidence in ["high", "medium"]]
        )

        return summary

    def _get_scannable_files(self) -> List[Path]:
        """
        Get list of files that should be scanned for security issues.

        Returns:
            List of file paths to scan
        """
        scannable_extensions = {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".java",
            ".php",
            ".rb",
            ".go",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".cs",
            ".vb",
            ".sql",
            ".xml",
            ".json",
            ".yaml",
            ".yml",
            ".sh",
            ".bat",
            ".ps1",
            ".config",
        }

        excluded_dirs = {
            ".git",
            ".svn",
            ".hg",
            "node_modules",
            "__pycache__",
            ".pytest_cache",
            "venv",
            ".venv",
            "env",
            ".env",
            "dist",
            "build",
            ".next",
            ".nuxt",
        }

        scannable_files = []

        def should_scan_dir(dir_path: Path) -> bool:
            return dir_path.name not in excluded_dirs

        def should_scan_file(file_path: Path) -> bool:
            return (
                file_path.suffix in scannable_extensions
                and file_path.stat().st_size < 1_000_000
            )  # Skip files > 1MB

        # Walk through workspace directory
        try:
            for item in self.workspace_root.rglob("*"):
                if item.is_file() and should_scan_file(item):
                    # Check if any parent directory should be excluded
                    if all(
                        should_scan_dir(parent)
                        for parent in item.parents
                        if self.workspace_root in parent.parents
                        or parent == self.workspace_root
                    ):
                        scannable_files.append(item)
        except Exception as e:
            self.logger.warning(f"Error walking directory tree: {e}")

        return scannable_files[:1000]  # Limit to 1000 files for performance

    def _map_cvss_to_severity(self, cvss_score: Union[float, List, None]) -> str:
        """
        Map CVSS score to severity level.

        Args:
            cvss_score: CVSS score (float) or list of scores

        Returns:
            Severity level string
        """
        if isinstance(cvss_score, list):
            cvss_score = max(cvss_score) if cvss_score else 0.0

        if cvss_score is None:
            return "medium"

        if cvss_score >= 9.0:
            return "critical"
        elif cvss_score >= 7.0:
            return "high"
        elif cvss_score >= 4.0:
            return "medium"
        else:
            return "low"

    async def _record_scan_in_memory(self, scan_results: Dict[str, Any]):
        """
        Record security scan results in episodic memory.

        Args:
            scan_results: Complete scan results
        """
        try:
            summary = scan_results.get("summary", {})

            await self.memory.record_event(
                event_type=MemoryEventType.SECURITY_SCAN,
                content=f"Security scan found {summary.get('total_findings', 0)} issues. Risk score: {summary.get('risk_score', 0):.1f}",
                metadata={
                    "scan_id": scan_results["scan_id"],
                    "findings_count": summary.get("total_findings", 0),
                    "critical_count": summary.get("critical_issues", 0),
                    "risk_score": summary.get("risk_score", 0),
                    "scan_duration": scan_results.get("scan_duration_seconds", 0),
                    "patches_generated": len(scan_results.get("patches", [])),
                    "scan_types": scan_results.get("scan_types", []),
                },
            )

            self.logger.debug(
                f"Recorded security scan {scan_results['scan_id']} in memory"
            )

        except Exception as e:
            self.logger.warning(f"Failed to record security scan in memory: {e}")
