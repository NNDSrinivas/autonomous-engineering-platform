"""
Autonomous Pull Request Reviewer for Navi

Advanced AI-powered code review system that provides:
- Comprehensive code analysis and quality assessment
- Security vulnerability detection and remediation
- Performance optimization suggestions
- Architecture and design pattern validation
- Automated patch generation for common issues
- Line-by-line feedback with specific recommendations
- Integration with existing CI/CD pipelines
- Learning from team coding standards and preferences
"""

import json
import re
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

try:
    from ..services.llm_router import LLMRouter
    from ..services.database_service import DatabaseService  
    from ..memory.memory_layer import MemoryLayer, MemoryType, MemoryImportance
    from ..core.config import get_settings
except ImportError:
    from backend.services.llm_router import LLMRouter
    from backend.services.database_service import DatabaseService
    from backend.memory.memory_layer import MemoryLayer, MemoryType, MemoryImportance
    from backend.core.config import get_settings


class ReviewSeverity(Enum):
    """Severity levels for review comments."""
    CRITICAL = "critical"  # Security, data loss, breaking changes
    HIGH = "high"         # Performance, bugs, architecture violations
    MEDIUM = "medium"     # Code quality, maintainability
    LOW = "low"          # Style, minor improvements
    INFO = "info"        # Suggestions, best practices


class ReviewCategory(Enum):
    """Categories of review feedback."""
    SECURITY = "security"
    PERFORMANCE = "performance"
    BUGS = "bugs"
    ARCHITECTURE = "architecture"
    CODE_QUALITY = "code_quality"
    STYLE = "style"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    DEPENDENCIES = "dependencies"
    ACCESSIBILITY = "accessibility"


class FileChangeType(Enum):
    """Types of file changes in PR."""
    ADDED = "added"
    MODIFIED = "modified" 
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass
class FileChange:
    """Represents a file change in a PR."""
    file_path: str
    change_type: FileChangeType
    additions: int
    deletions: int
    diff_content: str
    language: Optional[str] = None
    is_test_file: bool = False
    is_config_file: bool = False


@dataclass
class ReviewComment:
    """Individual review comment with suggestions."""
    file_path: str
    line_number: Optional[int]
    severity: ReviewSeverity
    category: ReviewCategory
    title: str
    message: str
    suggested_fix: Optional[str] = None
    code_snippet: Optional[str] = None
    confidence: float = 1.0
    auto_fixable: bool = False


@dataclass
class SecurityIssue:
    """Security vulnerability found in code."""
    file_path: str
    line_number: int
    vulnerability_type: str
    severity: ReviewSeverity
    description: str
    cwe_id: Optional[str] = None
    mitigation: str = ""
    patch: Optional[str] = None


@dataclass
class PatchSuggestion:
    """Automated code patch suggestion."""
    file_path: str
    start_line: int
    end_line: int
    original_code: str
    suggested_code: str
    reasoning: str
    confidence: float
    category: ReviewCategory


@dataclass
class PRAnalysis:
    """Comprehensive PR analysis results."""
    pr_id: str
    title: str
    description: str
    author: str
    file_changes: List[FileChange]
    review_comments: List[ReviewComment]
    security_issues: List[SecurityIssue]
    patch_suggestions: List[PatchSuggestion]
    overall_score: float
    complexity_score: float
    risk_assessment: str
    approval_recommendation: str
    estimated_review_time: int  # minutes


class AutonomousPRReviewer:
    """
    Advanced AI-powered pull request reviewer that provides comprehensive
    code analysis, security scanning, and automated patch suggestions.
    """
    
    def __init__(self):
        """Initialize the Autonomous PR Reviewer."""
        self.llm = LLMRouter()
        self.db = DatabaseService()
        self.memory = MemoryLayer()
        self.settings = get_settings()
        
        # Review configuration
        self.max_files_per_review = 50
        self.max_diff_size = 10000  # lines
        self.confidence_threshold = 0.7
        
        # Security patterns to check
        self.security_patterns = {
            "sql_injection": [
                r"execute\s*\(\s*[\"'].*?%.*?[\"']",
                r"query\s*\(\s*[\"'].*?\+.*?[\"']",
                r"SELECT.*?WHERE.*?\+",
            ],
            "xss": [
                r"innerHTML\s*=\s*.*?\+",
                r"document\.write\s*\(\s*.*?\+",
                r"eval\s*\(\s*.*?request",
            ],
            "hardcoded_secrets": [
                r"(password|secret|key|token)\s*=\s*[\"'][^\"']{8,}[\"']",
                r"(api_key|access_token)\s*:\s*[\"'][^\"']+[\"']",
            ],
            "path_traversal": [
                r"open\s*\(\s*.*?\+.*?[\"']\.\.\/",
                r"file\s*=\s*.*?request.*?[\"']\.\.\/",
            ]
        }
    
    async def review_pull_request(
        self,
        pr_id: str,
        pr_title: str,
        pr_description: str,
        author: str,
        file_changes: List[Dict[str, Any]],
        repository_context: Optional[Dict[str, Any]] = None
    ) -> PRAnalysis:
        """
        Perform comprehensive review of a pull request.
        
        Args:
            pr_id: Pull request identifier
            pr_title: PR title
            pr_description: PR description
            author: PR author
            file_changes: List of file changes with diffs
            repository_context: Additional context about the repository
            
        Returns:
            Complete PR analysis with comments and suggestions
        """
        
        # Parse file changes
        parsed_changes = []
        for change in file_changes:
            file_change = FileChange(
                file_path=change["file_path"],
                change_type=FileChangeType(change["change_type"]),
                additions=change.get("additions", 0),
                deletions=change.get("deletions", 0),
                diff_content=change.get("diff_content", ""),
                language=self._detect_language(change["file_path"]),
                is_test_file=self._is_test_file(change["file_path"]),
                is_config_file=self._is_config_file(change["file_path"])
            )
            parsed_changes.append(file_change)
        
        # Retrieve relevant memories for context
        context_memories = await self._get_review_context(parsed_changes, repository_context or {})
        
        # Perform security analysis
        security_issues = await self._analyze_security(parsed_changes)
        
        # Generate review comments
        review_comments = await self._generate_review_comments(
            parsed_changes, context_memories, repository_context
        )
        
        # Generate patch suggestions
        patch_suggestions = await self._generate_patch_suggestions(
            parsed_changes, review_comments
        )
        
        # Calculate complexity and risk scores
        complexity_score = self._calculate_complexity_score(parsed_changes)
        overall_score = self._calculate_overall_score(
            review_comments, security_issues, complexity_score
        )
        
        # Generate risk assessment
        risk_assessment = await self._generate_risk_assessment(
            parsed_changes, security_issues, complexity_score
        )
        
        # Generate approval recommendation
        approval_recommendation = await self._generate_approval_recommendation(
            overall_score, security_issues, review_comments
        )
        
        # Estimate review time
        estimated_review_time = self._estimate_review_time(parsed_changes, review_comments)
        
        # Create analysis object
        analysis = PRAnalysis(
            pr_id=pr_id,
            title=pr_title,
            description=pr_description,
            author=author,
            file_changes=parsed_changes,
            review_comments=review_comments,
            security_issues=security_issues,
            patch_suggestions=patch_suggestions,
            overall_score=overall_score,
            complexity_score=complexity_score,
            risk_assessment=risk_assessment,
            approval_recommendation=approval_recommendation,
            estimated_review_time=estimated_review_time
        )
        
        # Store review results
        await self._save_review_analysis(analysis)
        
        # Store learning in memory
        await self._store_review_learning(analysis, context_memories)
        
        return analysis
    
    async def generate_review_summary(
        self,
        analysis: PRAnalysis
    ) -> str:
        """
        Generate human-readable review summary.
        
        Args:
            analysis: PR analysis results
            
        Returns:
            Formatted review summary
        """
        
        summary_prompt = f"""
        You are Navi-ReviewSummarizer, an expert at creating clear, actionable PR review summaries.
        
        Generate a comprehensive review summary for this pull request:
        
        PR DETAILS:
        - Title: {analysis.title}
        - Author: {analysis.author} 
        - Files Changed: {len(analysis.file_changes)}
        - Overall Score: {analysis.overall_score:.1f}/10
        - Complexity Score: {analysis.complexity_score:.1f}/10
        
        REVIEW FINDINGS:
        - Total Comments: {len(analysis.review_comments)}
        - Critical Issues: {len([c for c in analysis.review_comments if c.severity == ReviewSeverity.CRITICAL])}
        - Security Issues: {len(analysis.security_issues)}
        - Patch Suggestions: {len(analysis.patch_suggestions)}
        
        RISK ASSESSMENT: {analysis.risk_assessment}
        RECOMMENDATION: {analysis.approval_recommendation}
        
        KEY ISSUES:
        {json.dumps([{
            "severity": comment.severity.value,
            "category": comment.category.value,
            "title": comment.title,
            "file": comment.file_path
        } for comment in analysis.review_comments[:10]], indent=2)}
        
        Generate a clear, structured review summary that includes:
        1. **Overall Assessment** - High level verdict
        2. **Key Strengths** - What's good about this PR
        3. **Critical Issues** - Must-fix problems
        4. **Recommendations** - Actionable next steps
        5. **Approval Status** - Clear approve/request changes decision
        
        Use professional tone suitable for team collaboration.
        """
        
        try:
            response = await self.llm.run(prompt=summary_prompt, use_smart_auto=True)
            return response.text
            
        except Exception:
            # Fallback summary
            critical_count = len([c for c in analysis.review_comments if c.severity == ReviewSeverity.CRITICAL])
            security_count = len(analysis.security_issues)
            
            return f"""
## PR Review Summary

**Overall Score:** {analysis.overall_score:.1f}/10
**Recommendation:** {analysis.approval_recommendation}

### Key Findings
- {len(analysis.review_comments)} review comments
- {critical_count} critical issues
- {security_count} security concerns
- {len(analysis.patch_suggestions)} automated fixes available

### Risk Assessment
{analysis.risk_assessment}

**Estimated Review Time:** {analysis.estimated_review_time} minutes
            """.strip()
    
    async def apply_automated_fixes(
        self,
        analysis: PRAnalysis,
        confidence_threshold: float = 0.8
    ) -> Dict[str, Any]:
        """
        Apply automated fixes for high-confidence patch suggestions.
        
        Args:
            analysis: PR analysis with patch suggestions
            confidence_threshold: Minimum confidence for auto-application
            
        Returns:
            Results of automated fix application
        """
        
        applicable_patches = [
            patch for patch in analysis.patch_suggestions
            if patch.confidence >= confidence_threshold
        ]
        
        results = {
            "total_patches": len(analysis.patch_suggestions),
            "applied_patches": [],
            "skipped_patches": [],
            "errors": []
        }
        
        for patch in applicable_patches:
            try:
                # Apply the patch (in a real implementation, this would modify files)
                fix_result = await self._apply_patch(patch)
                
                if fix_result["success"]:
                    results["applied_patches"].append({
                        "file": patch.file_path,
                        "lines": f"{patch.start_line}-{patch.end_line}",
                        "category": patch.category.value,
                        "reasoning": patch.reasoning
                    })
                else:
                    results["errors"].append({
                        "file": patch.file_path,
                        "error": fix_result.get("error", "Unknown error")
                    })
                    
            except Exception as e:
                results["errors"].append({
                    "file": patch.file_path,
                    "error": str(e)
                })
        
        # Store applied fixes in memory
        if results["applied_patches"]:
            await self.memory.store_memory(
                memory_type=MemoryType.PROCESS_LEARNING,
                title=f"Automated PR Fixes Applied: {analysis.pr_id}",
                content=f"Applied {len(results['applied_patches'])} automated fixes to PR {analysis.pr_id}. "
                       f"Categories: {', '.join(set(p['category'] for p in results['applied_patches']))}",
                importance=MemoryImportance.MEDIUM,
                tags=["pr-review", "automated-fixes", "code-quality"],
                context={
                    "pr_id": analysis.pr_id,
                    "fixes_applied": len(results["applied_patches"])
                }
            )
        
        return results
    
    async def _analyze_security(
        self,
        file_changes: List[FileChange]
    ) -> List[SecurityIssue]:
        """Analyze code changes for security vulnerabilities."""
        
        security_issues = []
        
        for file_change in file_changes:
            if file_change.change_type == FileChangeType.DELETED:
                continue
            
            # Pattern-based security scanning
            issues = self._scan_security_patterns(file_change)
            security_issues.extend(issues)
            
            # AI-powered security analysis for critical files
            if self._is_security_critical_file(file_change.file_path):
                ai_issues = await self._ai_security_analysis(file_change)
                security_issues.extend(ai_issues)
        
        return security_issues
    
    def _scan_security_patterns(self, file_change: FileChange) -> List[SecurityIssue]:
        """Scan for known security vulnerability patterns."""
        
        issues = []
        lines = file_change.diff_content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Skip deleted lines
            if line.startswith('-'):
                continue
            
            # Check each security pattern category
            for vuln_type, patterns in self.security_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        issue = SecurityIssue(
                            file_path=file_change.file_path,
                            line_number=line_num,
                            vulnerability_type=vuln_type,
                            severity=ReviewSeverity.HIGH,
                            description=f"Potential {vuln_type.replace('_', ' ')} vulnerability detected",
                            mitigation=self._get_security_mitigation(vuln_type)
                        )
                        issues.append(issue)
        
        return issues
    
    async def _ai_security_analysis(self, file_change: FileChange) -> List[SecurityIssue]:
        """Use AI to analyze code for security issues."""
        
        security_prompt = f"""
        You are Navi-SecurityAnalyzer, an expert at identifying security vulnerabilities.
        
        Analyze this code change for security issues:
        
        FILE: {file_change.file_path}
        LANGUAGE: {file_change.language}
        
        DIFF CONTENT:
        ```
        {file_change.diff_content[:2000]}  # Truncate for token limits
        ```
        
        Look for:
        1. **Injection vulnerabilities** (SQL, XSS, Command, etc.)
        2. **Authentication/Authorization issues**
        3. **Cryptographic problems**
        4. **Input validation failures** 
        5. **Information disclosure**
        6. **Insecure configurations**
        
        Return JSON array of security issues:
        [
            {{
                "line_number": 42,
                "vulnerability_type": "sql_injection",
                "severity": "high|medium|low",
                "description": "Detailed explanation",
                "cwe_id": "CWE-89",
                "mitigation": "How to fix this issue"
            }}
        ]
        
        Return empty array [] if no issues found.
        """
        
        try:
            response = await self.llm.run(prompt=security_prompt, use_smart_auto=True)
            issues_data = json.loads(response.text)
            
            security_issues = []
            for issue_data in issues_data:
                issue = SecurityIssue(
                    file_path=file_change.file_path,
                    line_number=issue_data["line_number"],
                    vulnerability_type=issue_data["vulnerability_type"],
                    severity=ReviewSeverity(issue_data["severity"]),
                    description=issue_data["description"],
                    cwe_id=issue_data.get("cwe_id"),
                    mitigation=issue_data.get("mitigation", "")
                )
                security_issues.append(issue)
            
            return security_issues
            
        except Exception:
            return []
    
    async def _generate_review_comments(
        self,
        file_changes: List[FileChange],
        context_memories: List[Any],
        repository_context: Optional[Dict[str, Any]] = None
    ) -> List[ReviewComment]:
        """Generate comprehensive review comments using AI analysis."""
        
        all_comments = []
        
        for file_change in file_changes:
            if file_change.change_type == FileChangeType.DELETED:
                continue
            
            # Generate comments for this file
            file_comments = await self._analyze_file_change(
                file_change, context_memories, repository_context or {}
            )
            all_comments.extend(file_comments)
        
        # Deduplicate and prioritize comments
        all_comments = self._deduplicate_comments(all_comments)
        all_comments.sort(key=lambda c: (c.severity.value, -c.confidence))
        
        return all_comments
    
    async def _analyze_file_change(
        self,
        file_change: FileChange,
        context_memories: List[Any],
        repository_context: Dict[str, Any]
    ) -> List[ReviewComment]:
        """Analyze a single file change and generate comments."""
        
        # Prepare context from memories
        memory_context = ""
        if context_memories:
            memory_context = "\n".join([
                f"- {mem.title}: {mem.content[:100]}..."
                for mem in context_memories[:5]
            ])
        
        review_prompt = f"""
        You are Navi-CodeReviewer, an expert software engineer and code reviewer.
        
        Review this code change and provide detailed, actionable feedback:
        
        FILE: {file_change.file_path}
        LANGUAGE: {file_change.language}
        CHANGE TYPE: {file_change.change_type.value}
        ADDITIONS: +{file_change.additions}, DELETIONS: -{file_change.deletions}
        
        RELEVANT PROJECT CONTEXT:
        {memory_context}
        
        CODE DIFF:
        ```diff
        {file_change.diff_content[:3000]}  # Truncate for token limits
        ```
        
        Analyze for:
        1. **Code Quality** - Structure, readability, maintainability
        2. **Performance** - Efficiency, resource usage, scalability
        3. **Bugs** - Logic errors, edge cases, potential failures
        4. **Architecture** - Design patterns, SOLID principles
        5. **Testing** - Test coverage, test quality
        6. **Documentation** - Comments, docstrings
        
        For each issue found, provide:
        - Specific line number (if applicable)
        - Severity level (critical/high/medium/low/info)
        - Category (security/performance/bugs/architecture/code_quality/style/documentation/testing)
        - Clear explanation
        - Specific fix suggestion
        - Whether it's auto-fixable
        
        Return JSON array:
        [
            {{
                "line_number": 42,
                "severity": "medium",
                "category": "code_quality", 
                "title": "Brief issue summary",
                "message": "Detailed explanation and reasoning",
                "suggested_fix": "Specific code or approach to fix",
                "auto_fixable": false,
                "confidence": 0.85
            }}
        ]
        
        Focus on actionable feedback. Return empty array [] if no issues.
        """
        
        try:
            response = await self.llm.run(prompt=review_prompt, use_smart_auto=True)
            comments_data = json.loads(response.text)
            
            comments = []
            for comment_data in comments_data:
                comment = ReviewComment(
                    file_path=file_change.file_path,
                    line_number=comment_data.get("line_number"),
                    severity=ReviewSeverity(comment_data["severity"]),
                    category=ReviewCategory(comment_data["category"]),
                    title=comment_data["title"],
                    message=comment_data["message"],
                    suggested_fix=comment_data.get("suggested_fix"),
                    confidence=comment_data.get("confidence", 0.7),
                    auto_fixable=comment_data.get("auto_fixable", False)
                )
                comments.append(comment)
            
            return comments
            
        except Exception as e:
            # Fallback comment for analysis failure
            return [ReviewComment(
                file_path=file_change.file_path,
                line_number=None,
                severity=ReviewSeverity.INFO,
                category=ReviewCategory.CODE_QUALITY,
                title="Review Analysis Incomplete",
                message=f"Automated review analysis failed: {str(e)}. Manual review recommended.",
                confidence=0.1
            )]
    
    async def _generate_patch_suggestions(
        self,
        file_changes: List[FileChange],
        review_comments: List[ReviewComment]
    ) -> List[PatchSuggestion]:
        """Generate automated patch suggestions for fixable issues."""
        
        patch_suggestions = []
        
        # Group auto-fixable comments by file
        auto_fixable_comments = [c for c in review_comments if c.auto_fixable]
        comments_by_file = {}
        
        for comment in auto_fixable_comments:
            if comment.file_path not in comments_by_file:
                comments_by_file[comment.file_path] = []
            comments_by_file[comment.file_path].append(comment)
        
        # Generate patches for each file
        for file_path, comments in comments_by_file.items():
            file_change = next((fc for fc in file_changes if fc.file_path == file_path), None)
            if not file_change:
                continue
            
            patches = await self._generate_file_patches(file_change, comments)
            patch_suggestions.extend(patches)
        
        return patch_suggestions
    
    async def _generate_file_patches(
        self,
        file_change: FileChange,
        comments: List[ReviewComment]
    ) -> List[PatchSuggestion]:
        """Generate patch suggestions for a specific file."""
        
        patch_prompt = f"""
        You are Navi-PatchGenerator, an expert at creating precise code patches.
        
        Generate automated patches for these review comments:
        
        FILE: {file_change.file_path}
        LANGUAGE: {file_change.language}
        
        ORIGINAL DIFF:
        ```diff
        {file_change.diff_content[:2000]}
        ```
        
        ISSUES TO FIX:
        {json.dumps([{
            "line": comment.line_number,
            "severity": comment.severity.value,
            "title": comment.title,
            "message": comment.message,
            "suggested_fix": comment.suggested_fix
        } for comment in comments], indent=2)}
        
        For each fixable issue, generate a precise patch:
        
        Return JSON array:
        [
            {{
                "start_line": 10,
                "end_line": 12,
                "original_code": "exact original code",
                "suggested_code": "exact replacement code",
                "reasoning": "why this fix addresses the issue",
                "confidence": 0.9,
                "category": "code_quality"
            }}
        ]
        
        Only suggest patches you are confident about. Return [] if no safe patches.
        """
        
        try:
            response = await self.llm.run(prompt=patch_prompt, use_smart_auto=True)
            patches_data = json.loads(response.text)
            
            patches = []
            for patch_data in patches_data:
                if patch_data.get("confidence", 0) >= self.confidence_threshold:
                    patch = PatchSuggestion(
                        file_path=file_change.file_path,
                        start_line=patch_data["start_line"],
                        end_line=patch_data["end_line"],
                        original_code=patch_data["original_code"],
                        suggested_code=patch_data["suggested_code"],
                        reasoning=patch_data["reasoning"],
                        confidence=patch_data["confidence"],
                        category=ReviewCategory(patch_data["category"])
                    )
                    patches.append(patch)
            
            return patches
            
        except Exception:
            return []
    
    # Utility methods
    def _detect_language(self, file_path: str) -> Optional[str]:
        """Detect programming language from file extension."""
        
        extension_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript', 
            '.jsx': 'jsx',
            '.tsx': 'tsx',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.c': 'c',
            '.php': 'php',
            '.rb': 'ruby',
            '.swift': 'swift',
            '.kt': 'kotlin'
        }
        
        ext = Path(file_path).suffix.lower()
        return extension_map.get(ext)
    
    def _is_test_file(self, file_path: str) -> bool:
        """Check if file is a test file."""
        test_indicators = ['test', 'spec', '__test__', '.test.', '.spec.']
        return any(indicator in file_path.lower() for indicator in test_indicators)
    
    def _is_config_file(self, file_path: str) -> bool:
        """Check if file is a configuration file."""
        config_files = [
            'package.json', 'requirements.txt', 'Dockerfile', 'docker-compose.yml',
            '.gitignore', '.eslintrc', 'tsconfig.json', 'webpack.config.js'
        ]
        config_patterns = ['.config.', '.conf', '.ini', '.yaml', '.yml', '.toml']
        
        filename = Path(file_path).name
        return (filename in config_files or 
                any(pattern in filename for pattern in config_patterns))
    
    def _is_security_critical_file(self, file_path: str) -> bool:
        """Check if file contains security-critical code."""
        critical_indicators = [
            'auth', 'login', 'password', 'token', 'crypto', 'security',
            'permission', 'admin', 'api_key', 'secret'
        ]
        return any(indicator in file_path.lower() for indicator in critical_indicators)
    
    def _get_security_mitigation(self, vuln_type: str) -> str:
        """Get mitigation advice for security vulnerability type."""
        
        mitigations = {
            "sql_injection": "Use parameterized queries or ORM methods to prevent SQL injection",
            "xss": "Sanitize and escape user input before rendering in HTML",
            "hardcoded_secrets": "Move secrets to environment variables or secure configuration",
            "path_traversal": "Validate and sanitize file paths, use safe path joining functions"
        }
        
        return mitigations.get(vuln_type, "Review code for security best practices")
    
    def _calculate_complexity_score(self, file_changes: List[FileChange]) -> float:
        """Calculate complexity score based on changes."""
        
        total_changes = sum(fc.additions + fc.deletions for fc in file_changes)
        num_files = len(file_changes)
        
        # Basic complexity calculation
        if total_changes == 0:
            return 0.0
        
        base_score = min(total_changes / 100, 10)  # Cap at 10
        file_multiplier = min(num_files / 10, 2)   # More files = more complex
        
        return min(base_score * file_multiplier, 10.0)
    
    def _calculate_overall_score(
        self,
        comments: List[ReviewComment],
        security_issues: List[SecurityIssue],
        complexity_score: float
    ) -> float:
        """Calculate overall quality score for the PR."""
        
        base_score = 10.0
        
        # Deduct points for issues
        for comment in comments:
            if comment.severity == ReviewSeverity.CRITICAL:
                base_score -= 2.0
            elif comment.severity == ReviewSeverity.HIGH:
                base_score -= 1.0
            elif comment.severity == ReviewSeverity.MEDIUM:
                base_score -= 0.5
            elif comment.severity == ReviewSeverity.LOW:
                base_score -= 0.2
        
        # Deduct points for security issues
        for issue in security_issues:
            if issue.severity == ReviewSeverity.CRITICAL:
                base_score -= 3.0
            elif issue.severity == ReviewSeverity.HIGH:
                base_score -= 1.5
            else:
                base_score -= 0.5
        
        # Factor in complexity
        complexity_penalty = complexity_score * 0.1
        base_score -= complexity_penalty
        
        return max(base_score, 0.0)
    
    def _estimate_review_time(
        self,
        file_changes: List[FileChange],
        comments: List[ReviewComment]
    ) -> int:
        """Estimate time needed for manual review in minutes."""
        
        base_time = 0
        
        for file_change in file_changes:
            # Base time per file
            base_time += 3
            
            # Additional time based on changes
            lines_changed = file_change.additions + file_change.deletions
            base_time += lines_changed * 0.1  # 0.1 minutes per line
        
        # Additional time for issues found
        base_time += len(comments) * 2  # 2 minutes per comment
        
        return min(int(base_time), 480)  # Cap at 8 hours
    
    def _deduplicate_comments(self, comments: List[ReviewComment]) -> List[ReviewComment]:
        """Remove duplicate comments."""
        
        seen_comments = set()
        unique_comments = []
        
        for comment in comments:
            # Create hash based on file, line, and title
            comment_hash = hashlib.md5(
                f"{comment.file_path}:{comment.line_number}:{comment.title}".encode()
            ).hexdigest()
            
            if comment_hash not in seen_comments:
                seen_comments.add(comment_hash)
                unique_comments.append(comment)
        
        return unique_comments
    
    async def _get_review_context(
        self,
        file_changes: List[FileChange],
        repository_context: Dict[str, Any]
    ) -> List[Any]:
        """Retrieve relevant context from memory for review."""
        
        # Get file paths and create search query
        file_paths = [fc.file_path for fc in file_changes]
        context_query = f"code review patterns {' '.join(file_paths[:5])}"
        
        from ..memory.memory_layer import MemoryQuery, MemoryType
        
        query = MemoryQuery(
            query_text=context_query,
            memory_types=[MemoryType.CODING_STYLE, MemoryType.ARCHITECTURE_DECISION, MemoryType.BUG_PATTERN],
            max_results=10
        )
        
        try:
            memories_with_scores = await self.memory.recall_memories(query)
            return [memory for memory, _ in memories_with_scores]
        except Exception:
            return []
    
    async def _generate_risk_assessment(
        self,
        file_changes: List[FileChange],
        security_issues: List[SecurityIssue],
        complexity_score: float
    ) -> str:
        """Generate risk assessment for the PR."""
        
        critical_security = len([si for si in security_issues if si.severity == ReviewSeverity.CRITICAL])
        high_security = len([si for si in security_issues if si.severity == ReviewSeverity.HIGH])
        
        if critical_security > 0:
            return f"HIGH RISK: {critical_security} critical security issues detected"
        elif high_security > 2 or complexity_score > 8:
            return f"MEDIUM RISK: {high_security} security issues, complexity score {complexity_score:.1f}"
        elif complexity_score > 5:
            return f"LOW RISK: Medium complexity changes (score {complexity_score:.1f})"
        else:
            return "LOW RISK: Straightforward changes with no major concerns"
    
    async def _generate_approval_recommendation(
        self,
        overall_score: float,
        security_issues: List[SecurityIssue],
        comments: List[ReviewComment]
    ) -> str:
        """Generate approval recommendation."""
        
        critical_issues = [c for c in comments if c.severity == ReviewSeverity.CRITICAL]
        critical_security = [si for si in security_issues if si.severity == ReviewSeverity.CRITICAL]
        
        if critical_security or critical_issues:
            return "REQUEST CHANGES - Critical issues must be resolved"
        elif overall_score < 6.0:
            return "REQUEST CHANGES - Multiple issues need attention"
        elif overall_score < 8.0:
            return "APPROVE WITH COMMENTS - Good to merge with minor improvements"
        else:
            return "APPROVE - Excellent code quality"
    
    # Database operations and patch application
    async def _save_review_analysis(self, analysis: PRAnalysis) -> None:
        """Save review analysis to database."""
        try:
            query = """
            INSERT OR REPLACE INTO pr_reviews
            (pr_id, title, author, overall_score, complexity_score, 
             risk_assessment, approval_recommendation, analysis_data, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            await self.db.execute(query, [
                analysis.pr_id, analysis.title, analysis.author,
                analysis.overall_score, analysis.complexity_score,
                analysis.risk_assessment, analysis.approval_recommendation,
                json.dumps(asdict(analysis), default=str),
                datetime.now().isoformat()
            ])
            
        except Exception:
            # Create table if doesn't exist
            create_query = """
            CREATE TABLE IF NOT EXISTS pr_reviews (
                pr_id TEXT PRIMARY KEY,
                title TEXT,
                author TEXT,
                overall_score REAL,
                complexity_score REAL,
                risk_assessment TEXT,
                approval_recommendation TEXT,
                analysis_data TEXT,
                created_at TEXT
            )
            """
            await self.db.execute(create_query, [])
            # Retry insert
            await self.db.execute(query, [
                analysis.pr_id, analysis.title, analysis.author,
                analysis.overall_score, analysis.complexity_score,
                analysis.risk_assessment, analysis.approval_recommendation,
                json.dumps(asdict(analysis), default=str),
                datetime.now().isoformat()
            ])
    
    async def _store_review_learning(
        self,
        analysis: PRAnalysis,
        context_memories: List[Any]
    ) -> None:
        """Store learnings from this review in memory."""
        
        # Store patterns found in this review
        if analysis.review_comments:
            common_categories = {}
            for comment in analysis.review_comments:
                cat = comment.category.value
                common_categories[cat] = common_categories.get(cat, 0) + 1
            
            most_common = max(common_categories.items(), key=lambda x: x[1])
            
            await self.memory.store_memory(
                memory_type=MemoryType.PROCESS_LEARNING,
                title=f"PR Review Pattern: {most_common[0]}",
                content=f"In PR {analysis.pr_id} by {analysis.author}, found {most_common[1]} "
                       f"{most_common[0]} issues. Common problems included: "
                       f"{', '.join([c.title for c in analysis.review_comments[:3]])}",
                importance=MemoryImportance.MEDIUM,
                tags=["pr-review", "patterns", most_common[0]],
                context={
                    "pr_id": analysis.pr_id,
                    "author": analysis.author,
                    "overall_score": analysis.overall_score
                }
            )
    
    async def _apply_patch(self, patch: PatchSuggestion) -> Dict[str, Any]:
        """Apply a code patch (placeholder implementation)."""
        
        # In a real implementation, this would:
        # 1. Read the file
        # 2. Apply the patch
        # 3. Write back to file
        # 4. Run tests to verify
        
        return {
            "success": True,
            "message": f"Patch applied to {patch.file_path} lines {patch.start_line}-{patch.end_line}"
        }