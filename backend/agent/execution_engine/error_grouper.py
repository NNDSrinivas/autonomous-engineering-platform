"""
Error Grouper - Phase 4.3

Smart grouping and analysis of diagnostics to handle multi-file, cascading errors.
This is what makes NAVI handle real-world codebases with interconnected issues.
"""

import logging
from typing import Dict, Any, List
from collections import defaultdict

from .types import DiagnosticIssue

logger = logging.getLogger(__name__)


class ErrorGrouper:
    """
    Groups diagnostics by file and detects cascading error patterns.

    Real repos have:
    - Cascading errors (one missing import causes 10 undefined errors)
    - Shared root causes (same typo in multiple files)
    - Cross-file dependencies (import/export chains)

    This grouper detects these patterns to minimize fix operations.
    """

    def __init__(self):
        self.import_patterns = [
            r"Cannot find module ['\"]([^'\"]+)['\"]",
            r"Module ['\"]([^'\"]+)['\"] not found",
            r"Cannot resolve module ['\"]([^'\"]+)['\"]",
            r"['\"]([^'\"]+)['\"] is not exported from",
        ]

        self.reference_patterns = [
            r"'(\w+)' is not defined",
            r"ReferenceError: (\w+) is not defined",
            r"Cannot find name '(\w+)'",
            r"Identifier '(\w+)' has already been declared",
        ]

    def group_diagnostics(self, issues: List[DiagnosticIssue]) -> Dict[str, Any]:
        """
        Group diagnostics by file and detect patterns.

        Returns:
        {
            "by_file": {"file.ts": [issues...]},
            "by_category": {"ReferenceError": [issues...]},
            "cascading_errors": [root_cause_analysis...],
            "shared_causes": [shared_pattern_analysis...],
            "fix_order": ["file1.ts", "file2.ts", ...],  # Optimal fix order
            "batch_groups": [[related_issues...], ...]   # Can be fixed together
        }
        """

        # Group by file
        by_file = defaultdict(list)
        for issue in issues:
            by_file[issue.file].append(issue)

        # Group by category
        by_category = defaultdict(list)
        for issue in issues:
            by_category[issue.category].append(issue)

        # Detect cascading errors
        cascading_errors = self._detect_cascading_errors(issues)

        # Detect shared root causes
        shared_causes = self._detect_shared_causes(issues)

        # Determine optimal fix order
        fix_order = self._calculate_fix_order(by_file, cascading_errors)

        # Create batch groups for parallel fixing
        batch_groups = self._create_batch_groups(issues, cascading_errors)

        return {
            "by_file": dict(by_file),
            "by_category": dict(by_category),
            "cascading_errors": cascading_errors,
            "shared_causes": shared_causes,
            "fix_order": fix_order,
            "batch_groups": batch_groups,
            "total_files": len(by_file),
            "total_issues": len(issues),
            "complexity_score": self._calculate_complexity_score(
                by_file, cascading_errors
            ),
        }

    def _detect_cascading_errors(
        self, issues: List[DiagnosticIssue]
    ) -> List[Dict[str, Any]]:
        """
        Detect cascading errors where one root cause creates multiple symptoms.

        Example: Missing import causes 5 "undefined variable" errors
        """
        cascading = []

        # Group undefined/reference errors by variable name
        reference_errors = defaultdict(list)
        import_errors = []

        for issue in issues:
            if issue.category in ["ReferenceError", "ImportError"]:
                if (
                    "not defined" in issue.message
                    or "Cannot find name" in issue.message
                ):
                    # Extract variable name
                    import re

                    for pattern in self.reference_patterns:
                        match = re.search(pattern, issue.message)
                        if match:
                            var_name = match.group(1)
                            reference_errors[var_name].append(issue)
                            break
                elif (
                    "module" in issue.message.lower()
                    or "import" in issue.message.lower()
                ):
                    import_errors.append(issue)

        # If we have import errors and reference errors, they might be cascading
        for import_error in import_errors:
            affected_references = []

            # Look for reference errors that could be caused by this missing import
            for var_name, ref_issues in reference_errors.items():
                # Heuristic: if variable name matches something in the import path
                if var_name.lower() in import_error.message.lower():
                    affected_references.extend(ref_issues)

            if affected_references:
                cascading.append(
                    {
                        "root_cause": import_error,
                        "symptoms": affected_references,
                        "fix_priority": "high",  # Fix import first
                        "expected_resolution": f"Fixing {import_error.message} should resolve {len(affected_references)} reference errors",
                    }
                )

        return cascading

    def _detect_shared_causes(
        self, issues: List[DiagnosticIssue]
    ) -> List[Dict[str, Any]]:
        """
        Detect when the same error pattern appears across multiple files.

        Example: Same typo in variable name across 3 files
        """
        shared = []

        # Group by normalized message (ignore file-specific details)
        message_groups = defaultdict(list)

        for issue in issues:
            # Normalize message - remove file-specific parts
            normalized = issue.message
            normalized = normalized.replace(issue.file, "[FILE]")
            # Remove line numbers, character positions etc
            import re

            normalized = re.sub(r"\d+", "[NUM]", normalized)

            message_groups[normalized].append(issue)

        # Find groups with multiple files
        for normalized_msg, group_issues in message_groups.items():
            files_affected = set(issue.file for issue in group_issues)
            if len(files_affected) > 1:
                shared.append(
                    {
                        "pattern": normalized_msg,
                        "issues": group_issues,
                        "files_affected": list(files_affected),
                        "occurrences": len(group_issues),
                        "fix_strategy": "batch_replace",  # Can fix all at once
                    }
                )

        return shared

    def _calculate_fix_order(
        self, by_file: Dict[str, List], cascading_errors: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Calculate optimal order to fix files to minimize cascading issues.

        Strategy:
        1. Fix files with root causes first
        2. Then files with symptoms
        3. Then independent files by issue count (most issues first)
        """
        fix_order = []
        processed_files = set()

        # Step 1: Files with root causes (imports, dependencies)
        for cascading in cascading_errors:
            root_file = cascading["root_cause"].file
            if root_file not in processed_files:
                fix_order.append(root_file)
                processed_files.add(root_file)

        # Step 2: Files with symptoms (will be cleaner after root fixes)
        for cascading in cascading_errors:
            for symptom in cascading["symptoms"]:
                if symptom.file not in processed_files:
                    fix_order.append(symptom.file)
                    processed_files.add(symptom.file)

        # Step 3: Remaining files by issue count (highest first)
        remaining_files = [
            (file, len(issues))
            for file, issues in by_file.items()
            if file not in processed_files
        ]
        remaining_files.sort(key=lambda x: x[1], reverse=True)

        for file, _ in remaining_files:
            fix_order.append(file)

        return fix_order

    def _create_batch_groups(
        self, issues: List[DiagnosticIssue], cascading_errors: List[Dict[str, Any]]
    ) -> List[List[DiagnosticIssue]]:
        """
        Create groups of issues that can be fixed in parallel (no dependencies).
        """
        batch_groups = []
        processed_issues = set()

        # Group 1: Root cause issues (fix first, in sequence)
        root_causes = []
        for cascading in cascading_errors:
            if id(cascading["root_cause"]) not in processed_issues:
                root_causes.append(cascading["root_cause"])
                processed_issues.add(id(cascading["root_cause"]))

        if root_causes:
            batch_groups.append(root_causes)

        # Group 2: Independent issues (can be fixed in parallel)
        independent_issues = []
        cascading_issue_ids = set()
        for cascading in cascading_errors:
            cascading_issue_ids.add(id(cascading["root_cause"]))
            for symptom in cascading["symptoms"]:
                cascading_issue_ids.add(id(symptom))

        for issue in issues:
            if (
                id(issue) not in cascading_issue_ids
                and id(issue) not in processed_issues
            ):
                independent_issues.append(issue)
                processed_issues.add(id(issue))

        if independent_issues:
            batch_groups.append(independent_issues)

        # Group 3: Cascading symptoms (fix after root causes)
        symptoms = []
        for cascading in cascading_errors:
            for symptom in cascading["symptoms"]:
                if id(symptom) not in processed_issues:
                    symptoms.append(symptom)
                    processed_issues.add(id(symptom))

        if symptoms:
            batch_groups.append(symptoms)

        return batch_groups

    def _calculate_complexity_score(
        self, by_file: Dict[str, List], cascading_errors: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate overall complexity score for the diagnostic set.

        Factors:
        - Number of files affected
        - Number of cascading relationships
        - Average issues per file
        - Issue categories (syntax errors = higher complexity)

        Returns: 0.0 to 1.0 (1.0 = highest complexity)
        """
        if not by_file:
            return 0.0

        file_count = len(by_file)
        total_issues = sum(len(issues) for issues in by_file.values())
        cascading_count = len(cascading_errors)

        # Base complexity from file count (more files = more complex)
        file_complexity = min(file_count / 10.0, 0.4)  # Cap at 40%

        # Issue density complexity
        avg_issues_per_file = total_issues / file_count
        issue_complexity = min(avg_issues_per_file / 20.0, 0.3)  # Cap at 30%

        # Cascading complexity (interdependencies make it harder)
        cascading_complexity = min(cascading_count / 5.0, 0.3)  # Cap at 30%

        return file_complexity + issue_complexity + cascading_complexity
