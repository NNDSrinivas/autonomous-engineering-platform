# backend/services/real_review_service.py
"""
REAL Git-Based Review Service - NO FAKE/SYNTHETIC ANALYSIS
Provides ACTUAL git diff analysis with LLM-powered issue detection
"""
import logging
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass

from backend.services.git_service import GitService
from backend.models.review import ReviewEntry, ReviewIssue
from backend.ai.llm_router import LLMRouter

logger = logging.getLogger(__name__)

class RealReviewService:
    """REAL git-based review service - NO SYNTHETIC/FAKE DATA"""
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.git_service = GitService(repo_path)
        self.llm_router = LLMRouter()
        
        logger.info(f"[REAL REVIEW] Initialized for {repo_path}")
    
    def get_working_tree_changes(self) -> List[Dict[str, Any]]:
        """Get REAL working tree changes from git"""
        try:
            # Run git status to get actual changes
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=self.repo_path,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"Git status failed: {result.stderr}")
                return []
            
            changes = []
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                    
                status = line[:2]
                filepath = line[3:].strip()
                
                if status.strip() in ['M', 'A', 'D', 'MM', 'AM', '??']:
                    change_data = {
                        "path": filepath,
                        "status": status.strip(),
                        "diff": self._get_real_diff(filepath, status),
                        "content": self._get_file_content(filepath) if status != 'D' else ""
                    }
                    changes.append(change_data)
            
            logger.info(f"[REAL REVIEW] Found {len(changes)} actual changes")
            return changes
            
        except Exception as e:
            logger.error(f"Failed to get working tree changes: {e}")
            return []
    
    def _get_real_diff(self, filepath: str, status: str) -> str:
        """Get REAL git diff for a file"""
        try:
            if status == '??':
                # New untracked file - show content as additions
                content = self._get_file_content(filepath)
                if content:
                    lines = content.split('\n')
                    diff_lines = [f"+{line}" for line in lines[:50]]  # Limit to 50 lines
                    return f"--- /dev/null\n+++ b/{filepath}\n" + '\n'.join(diff_lines)
                return f"--- /dev/null\n+++ b/{filepath}\n(New empty file)"
            
            elif status == 'D':
                return f"--- a/{filepath}\n+++ /dev/null\n(File deleted)"
            
            else:
                # Get actual git diff
                result = subprocess.run(
                    ["git", "diff", "HEAD", "--", filepath],
                    capture_output=True,
                    text=True,
                    cwd=self.repo_path,
                    timeout=30
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
                
                # Try staged diff
                result = subprocess.run(
                    ["git", "diff", "--cached", "--", filepath],
                    capture_output=True,
                    text=True,  
                    cwd=self.repo_path,
                    timeout=30
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
                
                return f"--- a/{filepath}\n+++ b/{filepath}\n(Modified - no diff available)"
                
        except Exception as e:
            logger.error(f"Failed to get diff for {filepath}: {e}")
            return f"--- a/{filepath}\n+++ b/{filepath}\n(Diff error: {str(e)})"
    
    def _get_file_content(self, filepath: str) -> str:
        """Get REAL file content from filesystem"""
        try:
            full_path = self.repo_path / filepath
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read {filepath}: {e}")
            return f"(Error reading file: {str(e)})"
    
    async def analyze_file_change(self, change: Dict[str, Any]) -> ReviewEntry:
        """Analyze a file change with REAL issue detection"""
        filepath = change["path"]
        diff = change.get("diff", "")
        change.get("content", "")
        
        logger.info(f"[REAL REVIEW] Analyzing {filepath}")
        
        issues = []
        
        # Real pattern-based analysis
        if diff:
            added_lines = [line[1:] for line in diff.split('\n') if line.startswith('+') and not line.startswith('+++')]
            
            for i, line in enumerate(added_lines):
                line_clean = line.strip()
                
                # JavaScript/TypeScript real issues
                if filepath.endswith(('.js', '.ts', '.jsx', '.tsx')):
                    if 'console.log(' in line_clean:
                        issues.append(ReviewIssue(
                            id=f"console-{i}",
                            title="Debug logging detected",
                            message=f"console.log() in added code: {line_clean[:60]}",
                            severity="warning",
                            line_number=i + 1,
                            suggestion="Remove console.log before production"
                        ))
                    
                    if 'debugger;' in line_clean:
                        issues.append(ReviewIssue(
                            id=f"debugger-{i}",
                            title="Debugger statement",
                            message="debugger; statement should be removed",
                            severity="error",
                            line_number=i + 1,
                            suggestion="Remove debugger statement"
                        ))
                
                # Python real issues
                elif filepath.endswith('.py'):
                    if 'print(' in line_clean and not line_clean.startswith('#'):
                        issues.append(ReviewIssue(
                            id=f"print-{i}",
                            title="Debug print statement",
                            message=f"print() in added code: {line_clean[:60]}",
                            severity="warning",
                            line_number=i + 1,
                            suggestion="Replace with proper logging"
                        ))
        
        # LLM-powered analysis for complex issues
        if len(added_lines) > 0 and len(str(diff)) > 100:
            try:
                llm_analysis = await self._analyze_with_llm(filepath, diff, added_lines)
                issues.extend(llm_analysis)
            except Exception as e:
                logger.error(f"LLM analysis failed for {filepath}: {e}")
        
        return ReviewEntry(
            id=f"real-review-{filepath.replace('/', '-').replace('.', '_')}",
            file=filepath,
            diff=diff,
            issues=issues,
            summary=f"Found {len(issues)} real issues in {filepath}" if issues else f"No issues found in {filepath}"
        )
    
    async def _analyze_with_llm(self, filepath: str, diff: str, added_lines: List[str]) -> List[ReviewIssue]:
        """Use LLM to find complex issues in real code changes"""
        try:
            prompt = f"""Analyze this REAL code change for issues:

File: {filepath}
Diff: {diff[:1000]}

Added lines:
{chr(10).join(added_lines[:20])}

Find REAL issues like:
- Security vulnerabilities
- Performance problems  
- Logic errors
- Code smell
- Best practice violations

Return JSON array of issues:
[{{"id": "issue-id", "title": "Issue title", "message": "Description", "severity": "error|warning|info", "line_number": 1, "suggestion": "How to fix"}}]
"""
            
            response = await self.llm_router.generate(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-3.5-turbo"
            )
            
            # Parse LLM response
            try:
                issues_data = json.loads(response.strip())
                issues = []
                for issue_data in issues_data:
                    issues.append(ReviewIssue(
                        id=issue_data.get("id", f"llm-{len(issues)}"),
                        title=issue_data.get("title", "LLM detected issue"),
                        message=issue_data.get("message", ""),
                        severity=issue_data.get("severity", "info"),
                        line_number=issue_data.get("line_number", 1),
                        suggestion=issue_data.get("suggestion", "")
                    ))
                return issues[:5]  # Limit to 5 LLM issues per file
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM response for {filepath}")
                return []
                
        except Exception as e:
            logger.error(f"LLM analysis error for {filepath}: {e}")
            return []

# Keep alias for backward compatibility but use REAL implementation
AdvancedRealReviewService = RealReviewService
class ArchitectureInsight:
    """Architectural pattern or design insight"""
    pattern_type: str  # design_pattern, anti_pattern, refactoring_opportunity
    title: str
    description: str
    impact: str
    recommendation: str
    files_affected: List[str]

@dataclass
class TechnicalDebt:
    """Technical debt identification"""
    debt_type: str  # code_smell, complexity, duplication, etc.
# Keep alias for backward compatibility but use REAL implementation
AdvancedRealReviewService = RealReviewService
