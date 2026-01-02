"""
CI Failure Engine - Phase 4.3

Extends FIX_PROBLEMS intelligence to CI/CD pipeline failures.
This is where NAVI transcends workspace issues to fix build failures.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CIFailure:
    """Represents a CI/CD pipeline failure"""
    job: str
    step: str 
    error_message: str
    log_snippet: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    failure_type: str = "unknown"  # build, test, lint, deploy
    suggested_fix: Optional[str] = None


class CIFailureAnalyzer:
    """
    Analyzes CI failures and converts them to diagnostic-like issues.
    
    This bridges CI logs → structured diagnostics → FIX_PROBLEMS workflow.
    """
    
    def __init__(self):
        self.failure_patterns = self._initialize_failure_patterns()
    
    def _initialize_failure_patterns(self) -> Dict[str, Dict]:
        """Common CI failure patterns and their fixes."""
        return {
            "missing_dependency": {
                "patterns": [
                    r"Cannot find module ['\"]([^'\"]+)['\"]",
                    r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]",
                    r"Error: Cannot resolve dependency ['\"]([^'\"]+)['\"]",
                    r"Package ['\"]([^'\"]+)['\"] not found"
                ],
                "fix_type": "install_dependency",
                "severity": "error"
            },
            "build_failure": {
                "patterns": [
                    r"Build failed with errors",
                    r"Compilation failed",
                    r"npm run build.*failed",
                    r"webpack.*compilation failed"
                ],
                "fix_type": "fix_build_error",
                "severity": "error"
            },
            "test_failure": {
                "patterns": [
                    r"(\d+) failing",
                    r"Test suite failed to run",
                    r"expect.*received.*AssertionError",
                    r"FAIL.*test.*"
                ],
                "fix_type": "fix_test",
                "severity": "warning"  # Tests can be fixed separately
            },
            "lint_failure": {
                "patterns": [
                    r"ESLint found (\d+) error",
                    r"TSLint found (\d+) error", 
                    r"Linting failed",
                    r"prettier.*failed"
                ],
                "fix_type": "fix_lint",
                "severity": "warning"
            },
            "type_error": {
                "patterns": [
                    r"TS\d+:.*error",
                    r"Type.*is not assignable to type",
                    r"Property.*does not exist on type"
                ],
                "fix_type": "fix_types",
                "severity": "error"
            }
        }
    
    def analyze_ci_failure(self, ci_log: str, job_name: str, step_name: str) -> List[CIFailure]:
        """
        Analyze CI log and extract structured failures.
        
        Returns list of CIFailure objects that can be processed like diagnostics.
        """
        failures = []
        
        # Split log into chunks for analysis
        log_lines = ci_log.split('\n')
        
        # Look for error patterns
        for i, line in enumerate(log_lines):
            for failure_type, pattern_info in self.failure_patterns.items():
                for pattern in pattern_info["patterns"]:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        failure = self._extract_failure_details(
                            line, log_lines, i, job_name, step_name, 
                            failure_type, pattern_info, match
                        )
                        if failure:
                            failures.append(failure)
        
        # Deduplicate similar failures
        return self._deduplicate_failures(failures)
    
    def _extract_failure_details(
        self, 
        error_line: str, 
        log_lines: List[str], 
        line_index: int,
        job_name: str, 
        step_name: str, 
        failure_type: str, 
        pattern_info: Dict,
        match: re.Match
    ) -> Optional[CIFailure]:
        """Extract detailed information about a specific failure."""
        
        # Get surrounding context
        context_start = max(0, line_index - 3)
        context_end = min(len(log_lines), line_index + 3)
        log_snippet = '\n'.join(log_lines[context_start:context_end])
        
        # Extract file path and line number if present
        file_path, line_number = self._extract_file_reference(error_line, log_lines, line_index)
        
        # Generate suggested fix
        suggested_fix = self._generate_suggested_fix(failure_type, match, error_line)
        
        return CIFailure(
            job=job_name,
            step=step_name,
            error_message=error_line.strip(),
            log_snippet=log_snippet,
            file_path=file_path,
            line_number=line_number,
            failure_type=failure_type,
            suggested_fix=suggested_fix
        )
    
    def _extract_file_reference(self, error_line: str, log_lines: List[str], line_index: int) -> Tuple[Optional[str], Optional[int]]:
        """Extract file path and line number from error context."""
        # Look for file references in current and nearby lines
        search_lines = log_lines[max(0, line_index-2):line_index+3]
        
        for line in search_lines:
            # Common file reference patterns
            file_patterns = [
                r"([^/\s]+\.(?:js|ts|tsx|jsx|py|json)):(\d+)",
                r"at ([^/\s]+\.(?:js|ts|tsx|jsx|py)):(\d+)",
                r"in ([^/\s]+\.(?:js|ts|tsx|jsx|py))",
                r"([^/\s]+\.(?:js|ts|tsx|jsx|py)).*line (\d+)"
            ]
            
            for pattern in file_patterns:
                match = re.search(pattern, line)
                if match:
                    file_path = match.group(1)
                    line_num = int(match.group(2)) if len(match.groups()) > 1 else None
                    return file_path, line_num
        
        return None, None
    
    def _generate_suggested_fix(self, failure_type: str, match: re.Match, error_line: str) -> Optional[str]:
        """Generate a suggested fix for the failure."""
        if failure_type == "missing_dependency" and match:
            module_name = match.group(1) if match.groups() else "unknown"
            return f"Install missing dependency: npm install {module_name}"
        
        elif failure_type == "build_failure":
            return "Review build configuration and fix compilation errors"
        
        elif failure_type == "test_failure":
            return "Fix failing tests or update test expectations"
        
        elif failure_type == "lint_failure":
            return "Fix linting errors with: npm run lint --fix"
        
        elif failure_type == "type_error":
            return "Fix TypeScript type errors"
        
        return None
    
    def _deduplicate_failures(self, failures: List[CIFailure]) -> List[CIFailure]:
        """Remove duplicate failures based on error message and type."""
        seen = set()
        unique_failures = []
        
        for failure in failures:
            # Create a signature for the failure
            signature = (failure.failure_type, failure.error_message[:100])
            
            if signature not in seen:
                seen.add(signature)
                unique_failures.append(failure)
        
        return unique_failures
    
    def convert_to_diagnostic_issues(self, failures: List[CIFailure]) -> List[Dict[str, Any]]:
        """
        Convert CI failures to diagnostic-like issues for FIX_PROBLEMS workflow.
        
        This allows CI failures to be processed by the same execution engine.
        """
        diagnostic_issues = []
        
        for failure in failures:
            # Map CI failure to diagnostic format
            diagnostic = {
                "file": failure.file_path or "build",
                "line": failure.line_number or 1,
                "character": 1,
                "message": failure.error_message,
                "severity": 1 if failure.failure_type in ["missing_dependency", "build_failure", "type_error"] else 2,
                "source": f"ci-{failure.job}",
                "code": failure.failure_type,
                "category": self._map_failure_to_category(failure.failure_type),
                "confidence": 0.8,  # High confidence for CI failures
                "fixable": failure.failure_type in ["missing_dependency", "lint_failure"],
                # CI-specific metadata
                "ci_metadata": {
                    "job": failure.job,
                    "step": failure.step,
                    "log_snippet": failure.log_snippet,
                    "suggested_fix": failure.suggested_fix
                }
            }
            
            diagnostic_issues.append(diagnostic)
        
        return diagnostic_issues
    
    def _map_failure_to_category(self, failure_type: str) -> str:
        """Map CI failure types to diagnostic categories."""
        mapping = {
            "missing_dependency": "ImportError",
            "build_failure": "SyntaxError", 
            "test_failure": "TestError",
            "lint_failure": "LintError",
            "type_error": "TypeError"
        }
        return mapping.get(failure_type, "CIError")


class CIFailureFetcher:
    """
    Fetches CI failure information from various CI systems.
    
    Phase 4.3 implementation focuses on GitHub Actions.
    Future: Jenkins, GitLab CI, CircleCI, etc.
    """
    
    def __init__(self):
        self.analyzer = CIFailureAnalyzer()
    
    async def fetch_latest_failures(self, repo_context: Dict[str, Any]) -> List[CIFailure]:
        """
        Fetch latest CI failures for the repository.
        
        For Phase 4.3, this simulates CI failures.
        Production implementation would integrate with GitHub API, etc.
        """
        # Phase 4.3: Simulated CI failures for testing
        simulated_failures = [
            {
                "job": "build", 
                "step": "npm test",
                "log": """
npm ERR! Test failed.  See above for more details.
Error: Cannot find module 'axios'
    at test/api.test.js:5:1
npm test exited with code 1
                """,
            },
            {
                "job": "lint",
                "step": "eslint",
                "log": """
/src/components/Button.tsx
  15:7  error  'React' is not defined  no-undef
  23:10 error  Unexpected token '=>'   no-unexpected-arrow
ESLint found 2 errors
                """
            }
        ]
        
        all_failures = []
        for sim_failure in simulated_failures:
            failures = self.analyzer.analyze_ci_failure(
                sim_failure["log"], 
                sim_failure["job"], 
                sim_failure["step"]
            )
            all_failures.extend(failures)
        
        return all_failures
    
    async def fetch_github_actions_failures(self, repo: str, run_id: str) -> List[CIFailure]:
        """
        Fetch failures from GitHub Actions (future implementation).
        
        Would use GitHub API to:
        1. Get workflow run details
        2. Download job logs
        3. Parse failures
        4. Return structured failures
        """
        # TODO: Implement GitHub API integration
        logger.info(f"GitHub Actions integration not yet implemented for {repo}:{run_id}")
        return []


# Integration with existing FIX_PROBLEMS workflow
class CIFailureTaskGrounder:
    """
    Extends task grounding to handle CI failures as a FIX_PROBLEMS source.
    """
    
    def __init__(self):
        self.fetcher = CIFailureFetcher()
        self.analyzer = CIFailureAnalyzer()
    
    async def ground_ci_fix_task(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ground "fix build failures" type requests.
        
        Returns grounded task with CI failures as diagnostic input.
        """
        # Check if this is a CI-related request
        ci_keywords = ["build", "ci", "pipeline", "failing", "test", "deploy"]
        if not any(keyword in user_input.lower() for keyword in ci_keywords):
            return {
                "type": "rejected",
                "reason": "Not a CI-related request"
            }
        
        # Fetch latest CI failures
        ci_failures = await self.fetcher.fetch_latest_failures(context)
        
        if not ci_failures:
            return {
                "type": "rejected",
                "reason": "No CI failures found to fix"
            }
        
        # Convert to diagnostic format
        diagnostic_issues = self.analyzer.convert_to_diagnostic_issues(ci_failures)
        
        # Create grounded task
        return {
            "type": "ready",
            "task": {
                "intent": "FIX_PROBLEMS",
                "scope": "repository",
                "target": "ci_pipeline", 
                "inputs": {
                    "diagnostics": [{"path": issue["file"], "diagnostics": [issue]} 
                                   for issue in diagnostic_issues],
                    "total_count": len(diagnostic_issues),
                    "source": "ci_failure"
                },
                "confidence": 0.9,
                "requires_approval": True,
                "metadata": {
                    "ci_failures": ci_failures,
                    "jobs_affected": list(set(f.job for f in ci_failures))
                }
            }
        }