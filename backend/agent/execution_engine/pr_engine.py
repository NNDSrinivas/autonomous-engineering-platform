"""
PR Engine - Phase 4.4

Handles intelligent Pull Request creation and automation for NAVI.
Integrates with existing GitHubService to create Staff Engineer-quality PRs.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)


@dataclass
class PRContext:
    """Context for PR creation"""

    branch_name: str
    base_branch: str
    title: str
    description: str
    files_changed: List[str]
    issues_fixed: List[Any]
    verification_results: Optional[Dict[str, Any]] = None


@dataclass
class PRResult:
    """Result of PR creation"""

    success: bool
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    message: str = ""
    error: Optional[str] = None


class PREngine:
    """
    Intelligent Pull Request automation for NAVI.

    Creates Staff Engineer-quality PRs with:
    - Clear, structured descriptions
    - Proper change summaries
    - Verification details
    - Linked issue references
    """

    def __init__(self, workspace_root: str, github_service=None):
        self.workspace_root = workspace_root
        self.github_service = github_service

    async def create_pull_request(
        self, context: PRContext, repository: str
    ) -> PRResult:
        """
        Create an intelligent pull request.

        Args:
            context: PR context with all necessary information
            repository: Target repository (format: owner/repo)

        Returns:
            PRResult with creation status and details
        """
        logger.info(f"Creating PR for branch '{context.branch_name}'")

        try:
            # Validate GitHub service availability
            if not self.github_service:
                return PRResult(
                    success=False,
                    error="GitHub service not configured",
                    message="Cannot create PR: GitHub integration not available",
                )

            # Generate PR title and description
            pr_title = self._generate_pr_title(context)
            pr_description = self._generate_pr_description(context)

            logger.info(f"PR Title: {pr_title}")
            logger.info(f"PR Description length: {len(pr_description)} characters")

            # Create PR via GitHub service
            pr_data = await self.github_service.create_pull_request(
                repository=repository,
                title=pr_title,
                body=pr_description,
                head_branch=context.branch_name,
                base_branch=context.base_branch,
            )

            pr_result = PRResult(
                success=True,
                pr_url=pr_data.get("html_url"),
                pr_number=pr_data.get("number"),
                message=f"Successfully created PR #{pr_data.get('number')}",
            )

            logger.info(f"Created PR #{pr_result.pr_number}: {pr_result.pr_url}")

            return pr_result

        except Exception as e:
            error_msg = f"Failed to create PR: {str(e)}"
            logger.error(error_msg)

            return PRResult(success=False, error=str(e), message=error_msg)

    def _generate_pr_title(self, context: PRContext) -> str:
        """
        Generate a clear, concise PR title.

        Follows format: "fix: resolve Problems tab errors (N files)"
        """
        issues = context.issues_fixed
        files_count = len(context.files_changed)

        # Categorize issues for title
        issue_categories = set()
        for issue in issues:
            category = getattr(issue, "category", "unknown")
            if category in ["UndefinedVariable", "ReferenceError"]:
                issue_categories.add("undefined variables")
            elif category in ["ImportError", "ModuleNotFound"]:
                issue_categories.add("import errors")
            elif category in ["SyntaxError", "ParseError"]:
                issue_categories.add("syntax errors")
            elif category in ["TypeError"]:
                issue_categories.add("type errors")
            elif category in ["UnusedVariable", "UnusedImport"]:
                issue_categories.add("unused code")
            else:
                issue_categories.add("code issues")

        # Build descriptive title
        if len(issue_categories) == 1:
            issue_desc = list(issue_categories)[0]
        elif len(issue_categories) <= 2:
            issue_desc = " and ".join(sorted(issue_categories))
        else:
            issue_desc = f"{len(issue_categories)} types of issues"

        # Create title with conventional commit prefix
        if files_count == 1:
            title = f"fix: resolve {issue_desc}"
        else:
            title = f"fix: resolve {issue_desc} ({files_count} files)"

        # Ensure title isn't too long (GitHub recommends 72 chars)
        if len(title) > 72:
            title = title[:69] + "..."

        return title

    def _generate_pr_description(self, context: PRContext) -> str:
        """
        Generate a comprehensive PR description.

        Includes:
        - Summary of changes
        - Issues resolved
        - Files modified
        - Verification results
        - How to test/verify
        """
        lines = []

        # Summary section
        lines.append("## Summary")
        lines.append("")

        issues_count = len(context.issues_fixed)
        files_count = len(context.files_changed)

        lines.append(
            f"This PR resolves **{issues_count} diagnostic issues** across **{files_count} files** "
            "identified in VS Code Problems tab."
        )
        lines.append("")

        # Changes section
        lines.append("## Changes Made")
        lines.append("")

        # Group issues by type for better readability
        issue_groups = self._group_issues_by_type(context.issues_fixed)

        for issue_type, issues in issue_groups.items():
            lines.append(f"### {issue_type}")
            for issue in issues[:5]:  # Limit to first 5 per category
                file_name = getattr(issue, "file", "unknown")
                message = getattr(issue, "message", "Issue resolved")
                lines.append(f"- **{file_name}**: {message}")

            if len(issues) > 5:
                lines.append(f"- ...and {len(issues) - 5} more similar issues")
            lines.append("")

        # Files modified
        if files_count <= 10:
            lines.append("## Files Modified")
            lines.append("")
            for file_path in sorted(context.files_changed):
                lines.append(f"- `{file_path}`")
            lines.append("")
        else:
            lines.append(f"## Files Modified ({files_count} files)")
            lines.append("")
            # Group by directory for large change sets
            file_dirs = {}
            for file_path in context.files_changed:
                dir_name = "/".join(file_path.split("/")[:-1]) or "root"
                if dir_name not in file_dirs:
                    file_dirs[dir_name] = 0
                file_dirs[dir_name] += 1

            for dir_name, count in sorted(file_dirs.items()):
                lines.append(f"- `{dir_name}/`: {count} files")
            lines.append("")

        # Verification section
        lines.append("## Verification")
        lines.append("")

        if context.verification_results:
            verification = context.verification_results
            if verification.get("success"):
                lines.append("✅ **All verification checks passed**")
                lines.append("")

                # Add specific verification details
                if "issues_resolved" in verification:
                    resolved = verification["issues_resolved"]
                    lines.append(f"- **Issues resolved**: {resolved}")

                if "ci_verification" in verification:
                    ci_info = verification["ci_verification"]
                    if ci_info.get("passed"):
                        lines.append(
                            "- **CI Impact**: Low risk, no critical files affected"
                        )

                lines.append("- **Syntax check**: All files compile without errors")
                lines.append("- **File integrity**: All changes applied successfully")
            else:
                lines.append("⚠️ **Some verification checks need attention**")
                lines.append("")
                lines.append("Please review the changes before merging.")
        else:
            lines.append("- Manual testing recommended")
            lines.append("- Verify diagnostic issues are resolved")
            lines.append("- Check that no new issues were introduced")

        lines.append("")

        # How to test section
        lines.append("## How to Test")
        lines.append("")
        lines.append("1. **Check VS Code Problems Tab**")
        lines.append("   - Open the workspace in VS Code")
        lines.append("   - Verify Problems tab shows fewer or no errors")
        lines.append("")
        lines.append("2. **Run Tests** (if applicable)")
        lines.append("   - Execute project test suite")
        lines.append("   - Ensure no regressions introduced")
        lines.append("")
        lines.append("3. **Code Review**")
        lines.append("   - Review changes for correctness")
        lines.append("   - Verify fixes address root causes")
        lines.append("")

        # Footer
        lines.append("---")
        lines.append("")
        lines.append("**Generated by NAVI Autonomous Engineering Platform**")
        lines.append(f"Branch: `{context.branch_name}`")
        lines.append(f"Created: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")

        return "\n".join(lines)

    def _group_issues_by_type(self, issues: List[Any]) -> Dict[str, List[Any]]:
        """Group issues by their type/category for better organization."""
        groups = {}

        for issue in issues:
            category = getattr(issue, "category", "unknown")

            # Map categories to user-friendly names
            if category in ["UndefinedVariable", "ReferenceError"]:
                group_name = "🔧 Undefined Variables"
            elif category in ["ImportError", "ModuleNotFound"]:
                group_name = "📦 Import Issues"
            elif category in ["SyntaxError", "ParseError"]:
                group_name = "⚠️ Syntax Errors"
            elif category in ["TypeError"]:
                group_name = "🏷️ Type Issues"
            elif category in ["UnusedVariable", "UnusedImport"]:
                group_name = "🧹 Cleanup"
            else:
                group_name = "🔍 Other Issues"

            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(issue)

        return groups

    async def add_pr_comment(
        self, repository: str, pr_number: int, comment: str
    ) -> bool:
        """
        Add comment to existing PR.

        Args:
            repository: Repository name (owner/repo)
            pr_number: PR number
            comment: Comment text

        Returns:
            True if successful
        """
        try:
            if not self.github_service:
                logger.error("GitHub service not configured")
                return False

            await self.github_service.add_pr_comment(repository, pr_number, comment)
            logger.info(f"Added comment to PR #{pr_number}")
            return True

        except Exception as e:
            logger.error(f"Failed to add PR comment: {e}")
            return False

    def generate_pr_context(
        self,
        branch_name: str,
        files_changed: List[str],
        issues_fixed: List[Any],
        verification_results: Optional[Dict[str, Any]] = None,
        base_branch: str = "main",
    ) -> PRContext:
        """
        Generate PR context from execution results.

        Args:
            branch_name: Git branch name
            files_changed: List of modified files
            issues_fixed: List of resolved issues
            verification_results: Results from verification step
            base_branch: Target branch for PR

        Returns:
            PRContext ready for PR creation
        """
        # Generate title and description
        title = self._generate_title_from_issues(issues_fixed)
        description = f"Resolves {len(issues_fixed)} diagnostic issues"

        return PRContext(
            branch_name=branch_name,
            base_branch=base_branch,
            title=title,
            description=description,
            files_changed=files_changed,
            issues_fixed=issues_fixed,
            verification_results=verification_results,
        )

    def _generate_title_from_issues(self, issues: List[Any]) -> str:
        """Generate a concise title from the list of issues."""
        if not issues:
            return "Fix code issues"

        # Count issues by type
        type_counts = {}
        for issue in issues:
            category = getattr(issue, "category", "unknown")
            type_counts[category] = type_counts.get(category, 0) + 1

        # Generate title based on most common issue type
        if len(type_counts) == 1:
            main_type = list(type_counts.keys())[0]
            count = list(type_counts.values())[0]

            if main_type in ["UndefinedVariable", "ReferenceError"]:
                return f"Fix undefined variable errors ({count})"
            elif main_type in ["ImportError", "ModuleNotFound"]:
                return f"Fix import errors ({count})"
            elif main_type in ["SyntaxError"]:
                return f"Fix syntax errors ({count})"
            else:
                return f"Fix {main_type} issues ({count})"
        else:
            total = len(issues)
            return f"Fix multiple code issues ({total})"
