"""Real AI-Powered Code Review Service
Transforms Git diffs into structured review entries using LLM analysis
"""
import asyncio
import subprocess
import json
import logging
import os
import re
from typing import AsyncGenerator, Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

# Import LLM router for AI analysis
from backend.ai.llm_router import smart_auto_chat, LLMRouter
# Import auto-fix service for patch generation
from backend.services.auto_fix_service import register_fix
# Import new real services
from backend.services.git_service import GitService
from backend.services.repo_service import RepoService
from backend.models.review import ReviewEntry, ReviewIssue, ReviewProgress

logger = logging.getLogger(__name__)


class RealReviewService:
    """Service for analyzing real code changes from git with LLM-powered review"""
    
    def __init__(self, repo_path: Optional[str] = None, analysis_depth: str = 'standard'):
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        self.repo_service = RepoService(str(self.repo_path)) if repo_path else None
        self.git_service = GitService(str(self.repo_path))
        self.llm_router = LLMRouter()
        self.progress = ReviewProgress()
        self.analysis_depth = analysis_depth
        logger.info(f"[REAL REVIEW] Initialized for {self.repo_path} with depth={analysis_depth}")
    
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
        
    def set_repository(self, repo_path: str):
        """Set the repository path for analysis"""
        self.repo_path = Path(repo_path)
        self.repo_service = RepoService(repo_path)
        self.git_service = GitService(repo_path)
        
    async def analyze_working_tree(self) -> List[ReviewEntry]:
        """Analyze all working tree changes and return structured reviews"""
        if not self.repo_service:
            raise ValueError("Repository not set. Call set_repository() first.")
            
        changes = self.repo_service.get_working_tree_changes()
        self.progress.total_files = len(changes)
        self.progress.current_step = "Analyzing changes..."
        
        results = []
        
        for i, change in enumerate(changes):
            self.progress.current_file = change["path"]
            self.progress.files_processed = i
            
            logger.info(f"Analyzing file {i+1}/{len(changes)}: {change['path']}")
            
            entry = await self.analyze_file_change(change)
            results.append(entry)
            
        self.progress.files_processed = len(changes)
        self.progress.current_step = "Analysis complete"
        
        return results
        
    async def analyze_file_change(self, change: Dict[str, Any]) -> ReviewEntry:
        """Analyze a single file change and generate review issues"""
        filepath = change["path"]
        diff = change.get("diff", "")
        content = change.get("content", "")
        
        logger.info(f"[REAL REVIEW] Analyzing {filepath}")
        
        issues = []
        
        # Real pattern-based analysis first
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
        if len(diff) > 100 and self.analysis_depth in ['comprehensive', 'standard']:
            try:
                llm_issues = await self._analyze_with_llm(filepath, diff, content)
                issues.extend(llm_issues)
            except Exception as e:
                logger.error(f"LLM analysis failed for {filepath}: {e}")
        
        return ReviewEntry(
            id=f"real-review-{filepath.replace('/', '-').replace('.', '_')}",
            file=filepath,
            diff=diff,
            issues=issues[:10],  # Limit to 10 issues
            summary=f"Found {len(issues)} issues in {filepath}" if issues else f"No issues found in {filepath}",
            status=change.get("status")
        )
        
    async def _analyze_with_llm(self, file_path: str, diff: str, content: str) -> List[ReviewIssue]:
        """Use LLM to find complex issues in real code changes"""
        try:
            added_lines = [line[1:] for line in diff.split('\n') if line.startswith('+') and not line.startswith('+++')]
            
            prompt = f"""Analyze this REAL code change for issues:

File: {file_path}
Diff (first 1000 chars): {diff[:1000]}

Added lines:
{chr(10).join(added_lines[:20])}

Find REAL issues like:
- Security vulnerabilities
- Performance problems  
- Logic errors
- Code smell
- Best practice violations

Return JSON array of issues. If no issues found, return empty array []:
[{{"id": "issue-id", "title": "Issue title", "message": "Description", "severity": "error|warning|info", "line_number": 1, "suggestion": "How to fix"}}]

ONLY return valid JSON array, nothing else."""
            
            response = await self.llm_router.generate(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-3.5-turbo"
            )
            
            # Parse LLM response
            try:
                response_text = response.strip()
                # Try to extract JSON if wrapped in markdown
                if '```' in response_text:
                    response_text = response_text.split('```')[1].replace('json', '').strip()
                
                issues_data = json.loads(response_text)
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
                logger.warning(f"Failed to parse LLM response for {file_path}")
                return []
                
        except Exception as e:
            logger.error(f"LLM analysis error for {file_path}: {e}")
            return []
        try:
            prompt = f"""Analyze this git diff for potential issues. Focus on:

1. Syntax errors and bugs
2. Security vulnerabilities  
3. Performance issues
4. Code quality problems
5. Missing imports/dependencies

File: {file_path}

Diff:
{diff}

Current content (for context):
{content[:2000]}...

Provide specific, actionable feedback in JSON format:
{{
  "issues": [
    {{
      "severity": "error|warning|info",
      "title": "Brief title",
      "message": "Detailed description",
      "line_number": null,
      "can_auto_fix": false
    }}
  ]
}}"""
            
            response = await smart_auto_chat(prompt)
            
            # Parse LLM response
            try:
                result = json.loads(response.text)
                issues = []
                
                for issue_data in result.get("issues", []):
                    issue = ReviewIssue(
                        severity=issue_data.get("severity", "info"),
                        title=issue_data.get("title", "Issue found"),
                        message=issue_data.get("message", ""),
                        suggestion=issue_data.get("suggestion"),
                        line_number=issue_data.get("line_number"),
                        fix_patch=issue_data.get("fix_patch"),
                        can_auto_fix=issue_data.get("can_auto_fix", False)
                    )
                    issues.append(issue)
                    
                return issues
                
            except json.JSONDecodeError:
                # Fallback if LLM doesn't return valid JSON
                logger.warning(f"LLM returned invalid JSON for {file_path}")
                return [ReviewIssue(
                    severity="info",
                    title="Analysis completed",
                    message=response.text[:500] + "..." if len(response.text) > 500 else response.text,
                    suggestion=None,
                    line_number=None,
                    fix_patch=None
                )]
                
        except Exception as e:
            logger.error(f"Failed to analyze {file_path} with LLM: {e}")
            return [ReviewIssue(
                severity="error",
                title="Analysis failed",
                message=f"Could not analyze file: {str(e)}",
                suggestion=None,
                line_number=None,
                fix_patch=None
            )]

async def get_git_diff(workspace_path: str = ".") -> str:
    """
    Get the current working tree diff from Git
    
    Args:
        workspace_path: Path to Git repository (default: current directory)
    
    Returns:
        Git diff output as string
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--unified=3", "--no-color"],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Git diff error: {e}")
        return ""
    except Exception as e:
        print(f"Unexpected error getting git diff: {e}")
        return ""


async def get_staged_diff(workspace_path: str = ".") -> str:
    """
    Get staged changes diff from Git
    
    Args:
        workspace_path: Path to Git repository
    
    Returns:
        Git diff output for staged changes
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--unified=3", "--no-color"],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return ""
    except Exception:
        return ""


def parse_diff_hunks(diff_text: str) -> List[Dict[str, Any]]:
    """
    Parse Git diff into individual file hunks for focused AI analysis
    
    Args:
        diff_text: Raw Git diff output
    
    Returns:
        List of hunk dictionaries with file info and diff content
    """
    hunks = []
    current_file = None
    current_hunk = []
    
    lines = diff_text.split('\n')
    
    for line in lines:
        if line.startswith('diff --git'):
            # Save previous hunk if exists
            if current_file and current_hunk:
                hunks.append({
                    'file': current_file,
                    'hunk': '\n'.join(current_hunk),
                    'line_count': len([line for line in current_hunk if line.startswith('+') or line.startswith('-')])
                })
            
            # Start new file
            parts = line.split()
            if len(parts) >= 4:
                current_file = parts[3].replace('b/', '', 1)
            else:
                current_file = "unknown"
            current_hunk = [line]
            
        elif line.startswith('@@') and current_file:
            # Hunk header - continue building current hunk
            current_hunk.append(line)
            
        elif current_file and (line.startswith('+') or line.startswith('-') or line.startswith(' ') or line.startswith('\\')):
            # Diff content lines
            current_hunk.append(line)
            
        elif line.startswith('index ') or line.startswith('---') or line.startswith('+++'):
            # Metadata lines
            if current_file:
                current_hunk.append(line)
    
    # Don't forget the last hunk
    if current_file and current_hunk:
        hunks.append({
            'file': current_file,
            'hunk': '\n'.join(current_hunk),
            'line_count': len([line for line in current_hunk if line.startswith('+') or line.startswith('-')])
        })
    
    return hunks


async def analyze_hunk_with_ai(file_path: str, hunk: str, context: str = "") -> Dict[str, Any]:
    """
    Analyze a single diff hunk using AI and return structured review entry
    
    Args:
        file_path: Path to the file being analyzed
        hunk: Git diff hunk content
        context: Additional context about the codebase
    
    Returns:
        Structured review entry dictionary
    """
    
    # Get file extension for language context
    file_ext = Path(file_path).suffix.lower()
    language_map = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.ts': 'TypeScript',
        '.tsx': 'TypeScript React',
        '.jsx': 'JavaScript React',
        '.java': 'Java',
        '.cpp': 'C++',
        '.c': 'C',
        '.cs': 'C#',
        '.go': 'Go',
        '.rs': 'Rust',
        '.php': 'PHP',
        '.rb': 'Ruby',
        '.swift': 'Swift',
        '.kt': 'Kotlin',
        '.dart': 'Dart',
        '.css': 'CSS',
        '.scss': 'SCSS',
        '.less': 'LESS',
        '.html': 'HTML',
        '.xml': 'XML',
        '.json': 'JSON',
        '.yaml': 'YAML',
        '.yml': 'YAML',
        '.md': 'Markdown',
        '.sql': 'SQL',
        '.sh': 'Shell',
        '.bash': 'Bash',
        '.zsh': 'Zsh'
    }
    
    language = language_map.get(file_ext, 'Text')
    
    prompt = f"""You are NAVI - an expert code review agent analyzing {language} code changes.

Analyze this Git diff hunk and return a JSON object with exactly these fields:
- "file": string (the file path)
- "hunk": string (the complete diff hunk)  
- "severity": "low" | "medium" | "high"
- "title": string (concise issue summary)
- "body": string (detailed explanation in markdown)
- "fixId": string (unique identifier for potential fix)

Focus on:
- Code quality issues (performance, readability, maintainability)
- Potential bugs or logic errors  
- Security vulnerabilities
- Best practice violations
- Missing error handling
- Performance concerns
- Accessibility issues (for frontend code)

If the change looks good, still provide a "low" severity entry with positive feedback.

File: {file_path}
Language: {language}

Diff hunk:
{hunk}

Respond with ONLY valid JSON - no markdown, no explanations, just the JSON object:"""

    try:
        # Get OpenAI API key from environment
        import os
        openai_key = os.environ.get('OPENAI_API_KEY')
        
        ai_response = await smart_auto_chat(
            prompt,
            api_key=openai_key,
            allowed_providers=["openai", "anthropic", "gemini"],
            max_tokens=2048,
        )

        response_text = ai_response.text.strip()
        
        # Try to extract JSON from response
        if response_text.startswith('```'):
            # Remove markdown code blocks
            lines = response_text.split('\n')
            json_lines = []
            in_json = False
            for line in lines:
                if line.startswith('```'):
                    in_json = not in_json
                    continue
                if in_json:
                    json_lines.append(line)
            response_text = '\n'.join(json_lines)

        review_entry = json.loads(response_text)
        
        # Validate required fields
        required_fields = ['file', 'hunk', 'severity', 'title', 'body', 'fixId']
        for field in required_fields:
            if field not in review_entry:
                review_entry[field] = ""
        
        # Ensure severity is valid
        if review_entry['severity'] not in ['low', 'medium', 'high']:
            review_entry['severity'] = 'medium'
        
        # Ensure file path is set
        review_entry['file'] = file_path
        review_entry['hunk'] = hunk
        
        # Register fix for auto-fix system if issues were found
        if review_entry.get('title') and review_entry['title'] != "No Issues Found":
            try:
                # Extract issue description from body
                issue_desc = review_entry.get('body', review_entry.get('title', 'Code issue found'))
                
                # Register fix with auto-fix service
                fix_id = register_fix(
                    file=file_path,
                    hunk=hunk,
                    issue=issue_desc,
                    severity=review_entry['severity']
                )
                
                # Update fixId to match registered fix
                review_entry['fixId'] = fix_id
                
            except Exception as e:
                print(f"Warning: Failed to register fix for {file_path}: {e}")
                # Keep original fixId from AI if registration fails
        
        return review_entry

    except json.JSONDecodeError as e:
        print(f"AI returned invalid JSON for {file_path}: {e}")
        return {
            "file": file_path,
            "hunk": hunk,
            "severity": "low",
            "title": "AI Analysis Error",
            "body": f"Could not parse AI response as JSON: {ai_response.text[:200]}...",
            "fixId": f"error-{hash(file_path)}"
        }
    
    except Exception as e:
        print(f"Error analyzing hunk for {file_path}: {e}")
        return {
            "file": file_path,
            "hunk": hunk,
            "severity": "low", 
            "title": "Analysis Failed",
            "body": f"Failed to analyze changes: {str(e)}",
            "fixId": f"error-{hash(file_path)}"
        }


async def generate_review_stream(workspace_path: str = ".") -> AsyncGenerator[Dict[str, Any], None]:
    """
    Generate real-time code review stream using AI analysis
    Intelligently scans:
    - Git working tree changes (modified tracked files)
    - Staged changes
    - Untracked files (new files not in git)
    - All code files if no git changes found
    
    Args:
        workspace_path: Path to repository/directory to analyze
    
    Yields:
        Dictionary events for SSE streaming:
        - {"type": "live-progress", "data": "message"}
        - {"type": "review-entry", "data": review_entry}
        - {"type": "done", "data": "message"}
        - {"type": "error", "data": {"message": "error"}}
    """
    
    try:
        # Initial progress
        yield {"type": "live-progress", "data": "🔍 Scanning repository intelligently..."}
        await asyncio.sleep(0.3)
        
        # Get Git diff (working tree + staged)
        working_diff = await get_git_diff(workspace_path)
        staged_diff = await get_staged_diff(workspace_path)
        
        # Also check for untracked files
        max_scan_files = int(os.getenv("NAVI_SCAN_MAX_FILES", "500"))
        max_untracked = max_scan_files
        untracked_files = []
        try:
            import subprocess
            result = subprocess.run(
                ['git', 'ls-files', '--others', '--exclude-standard'],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                untracked_files = [f.strip() for f in result.stdout.split('\n') if f.strip()][:max_untracked]
        except Exception as e:
            logger.warning(f"Could not get untracked files: {e}")
        
        # Combine diffs if both exist
        full_diff = ""
        if staged_diff.strip():
            full_diff += "=== STAGED CHANGES ===\n" + staged_diff + "\n\n"
        if working_diff.strip():
            full_diff += "=== WORKING TREE CHANGES ===\n" + working_diff
        
        # If no git changes, but we have untracked files, scan those
        if not full_diff.strip() and untracked_files:
            yield {"type": "live-progress", "data": f"📄 No git changes found, analyzing {len(untracked_files)} untracked files..."}
            await asyncio.sleep(0.2)
            
            # Create synthetic diffs for untracked files
            for untracked_file in untracked_files:
                try:
                    file_path = os.path.join(workspace_path, untracked_file)
                    if os.path.isfile(file_path) and os.path.getsize(file_path) < 100000:  # < 100KB
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            full_diff += f"\ndiff --git a/{untracked_file} b/{untracked_file}\n"
                            full_diff += f"new file mode 100644\n--- /dev/null\n+++ b/{untracked_file}\n"
                            full_diff += "\n".join(f"+{line}" for line in content.split('\n')[:100])  # First 100 lines
                except Exception as e:
                    logger.warning(f"Could not read untracked file {untracked_file}: {e}")
        
        # If still no changes at all, scan entire repo for issues
        if not full_diff.strip():
            yield {"type": "live-progress", "data": "💡 No changes detected. Scanning all code files for issues..."}
            await asyncio.sleep(0.3)
            
            # Scan all code files in repo
            code_extensions = {'.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs', '.cpp', '.c', '.h'}
            code_files = []
            
            for root, dirs, files in os.walk(workspace_path):
                # Skip common ignore directories
                dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', '.venv', 'venv', 'dist', 'build', '__pycache__'}]
                for file in files:
                    if any(file.endswith(ext) for ext in code_extensions):
                        code_files.append(os.path.join(root, file))
                        if len(code_files) >= max_scan_files:
                            break
                if len(code_files) >= max_scan_files:
                    break
            
            if code_files:
                yield {"type": "live-progress", "data": f"🔎 Scanning {len(code_files)} code files for potential issues..."}
                
                files_scanned = 0
                issues_found = 0
                
                # Analyze each file for common issues  
                for file_path in code_files[:max_scan_files]:  # Scan up to max
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            rel_path = os.path.relpath(file_path, workspace_path)
                            
                            # Quick analysis for common issues
                            issues = []
                            if 'TODO' in content or 'FIXME' in content or 'HACK' in content:
                                issues.append("Contains TODO/FIXME/HACK comments")
                            if 'console.log' in content or 'console.error' in content:
                                issues.append("Contains console.log statements")
                            if 'import pdb' in content or 'breakpoint()' in content or 'debugger;' in content:
                                issues.append("Contains debug statements")
                            if 'any' in content.lower() and file_path.endswith(('.py', '.ts', '.tsx')):
                                # Could be type: Any or any issues
                                pass  # Light check
                            
                            files_scanned += 1
                            
                            # ALWAYS yield entry - even if no issues (clean file)
                            if issues:
                                issues_found += len(issues)
                                yield {
                                    "type": "review-entry",
                                    "data": {
                                        "file": rel_path,
                                        "hunk": content[:500],
                                        "severity": "low",
                                        "title": f"Found {len(issues)} potential issues",
                                        "body": "**Issues detected:**\n" + "\n".join(f"- {issue}" for issue in issues),
                                        "fixId": f"scan-{rel_path.replace('/', '-')}"
                                    }
                                }
                            else:
                                yield {
                                    "type": "review-entry",
                                    "data": {
                                        "file": rel_path,
                                        "hunk": content[:200],
                                        "severity": "info",
                                        "title": "✅ No issues detected",
                                        "body": f"File scanned successfully - looks good!",
                                        "fixId": f"clean-{rel_path.replace('/', '-')}"
                                    }
                                }
                    except Exception as e:
                        logger.warning(f"Could not scan file {file_path}: {e}")
                
                yield {"type": "done", "data": f"Quick scan complete - analyzed {files_scanned} files, found {issues_found} potential issues"}
                return
            else:
                yield {
                    "type": "review-entry",
                    "data": {
                        "file": "",
                        "hunk": "",
                        "severity": "low",
                        "title": "✅ Repository is Clean",
                        "body": "🎉 **No issues found!**\n\n- No uncommitted changes\n- No untracked files\n- No obvious code issues detected\n\nYour repository is in excellent shape!",
                        "fixId": "clean-repo"
                    }
                }
                yield {"type": "done", "data": "Repository analysis complete - no issues found"}
                return
        
        yield {"type": "live-progress", "data": "Parsing diff hunks for analysis…"}
        await asyncio.sleep(0.2)
        
        # Parse diff into hunks
        hunks = parse_diff_hunks(full_diff)
        
        if not hunks:
            yield {
                "type": "review-entry", 
                "data": {
                    "file": "",
                    "hunk": "",
                    "severity": "low",
                    "title": "No Parseable Changes",
                    "body": "Changes detected but could not be parsed for review. This might be binary files or very large changes.",
                    "fixId": "parse-error"
                }
            }
            yield {"type": "done", "data": "Review complete - no parseable changes"}
            return
        
        total_hunks = len(hunks)
        yield {"type": "live-progress", "data": f"Analyzing {total_hunks} file changes with AI…"}
        await asyncio.sleep(0.3)
        
        # Process in batches of 10 for speed (NO FILTERING - scan all files)
        BATCH_SIZE = 10
        completed = 0
        
        for batch_start in range(0, total_hunks, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_hunks)
            batch = hunks[batch_start:batch_end]
            
            # Show progress for this batch
            progress_pct = int((completed / total_hunks) * 100) if total_hunks > 0 else 0
            yield {"type": "live-progress", "data": f"Processing files {batch_start + 1}-{batch_end} of {total_hunks} ({progress_pct}%)"}
            
            # Analyze batch in parallel
            tasks = []
            for hunk_data in batch:
                file_path = hunk_data['file']
                hunk_content = hunk_data['hunk']
                tasks.append(analyze_hunk_with_ai(file_path, hunk_content))
            
            # Wait for all in batch to complete
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Yield results as they complete
            for i, review_entry in enumerate(batch_results):
                if isinstance(review_entry, Exception):
                    # Log error but continue
                    logger.warning(f"Error analyzing hunk: {review_entry}")
                    continue
                completed += 1
                # Stream the result
                yield {"type": "review-entry", "data": review_entry}
            
            # Small delay for realistic streaming
            await asyncio.sleep(0.1)
        
        yield {"type": "done", "data": f"Review complete - analyzed {completed} files"}
        
    except Exception as e:
        print(f"Error in review stream generation: {e}")
        yield {
            "type": "error", 
            "data": {
                "message": f"Review generation failed: {str(e)}",
                "code": "REVIEW_ERROR"
            }
        }


# Backwards compatibility function
async def generate_mock_review_stream() -> AsyncGenerator[Dict[str, Any], None]:
    """
    Fallback mock review stream for testing when Git/AI is not available
    """
    yield {"type": "live-progress", "data": "Mock review mode - generating test data…"}
    await asyncio.sleep(0.5)
    
    mock_entries = [
        {
            "file": "src/components/Button.tsx",
            "hunk": "@@ -10,6 +10,8 @@\n export function Button({ children, onClick, variant = 'primary' }) {\n+  // TODO: Add loading state\n   return (\n     <button\n       className={`btn btn-${variant}`}\n       onClick={onClick}\n+      disabled={false}\n     >",
            "severity": "medium",
            "title": "Missing prop validation and loading state",
            "body": "**Issues found:**\n\n1. **Missing TypeScript types** - Props should be properly typed\n2. **TODO comment** - Loading state implementation is incomplete\n3. **Hardcoded disabled prop** - Should be configurable\n\n**Recommendations:**\n- Add proper TypeScript interface for props\n- Implement loading state functionality\n- Make disabled prop configurable",
            "fixId": "button-props-fix"
        },
        {
            "file": "src/utils/api.js", 
            "hunk": "@@ -15,3 +15,7 @@\n   } catch (error) {\n     console.error('API Error:', error);\n+    throw error;\n   }\n+  \n+  return null;\n }",
            "severity": "high",
            "title": "Unreachable return statement after throw",
            "body": "**Critical Issue:** The `return null;` statement will never execute because it comes after `throw error;`.\n\n**Impact:**\n- Dead code that confuses intent\n- Potential logic error in error handling\n\n**Fix:** Remove the unreachable return statement or restructure the error handling logic.",
            "fixId": "unreachable-return-fix"
        }
    ]
    
    for entry in mock_entries:
        await asyncio.sleep(0.6)
        yield {"type": "review-entry", "data": entry}
    
    yield {"type": "done", "data": "Mock review complete"}
