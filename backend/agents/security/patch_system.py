"""
Patch Validation and Application System for Security Agent
Validates and safely applies security patches with rollback capability.
"""

import ast
import logging
import shutil
import re
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
import json
import hashlib


class PatchValidator:
    """
    Validates security patches before application to ensure safety.

    Validates:
    - Syntax correctness
    - Semantic consistency
    - Security improvement
    - No functionality regression
    """

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self.logger = logging.getLogger(__name__)

    def validate_patch(self, patch_content: str, target_file: str) -> Dict[str, Any]:
        """
        Validate a security patch before application.

        Args:
            patch_content: Unified diff patch content
            target_file: Target file path relative to workspace root

        Returns:
            Validation results with safety assessment
        """
        validation_result = {
            "is_safe": False,
            "syntax_valid": False,
            "semantic_valid": False,
            "security_improvement": False,
            "regression_risk": "unknown",
            "validation_errors": [],
            "warnings": [],
            "confidence_score": 0.0,
        }

        try:
            target_path = self.workspace_root / target_file

            if not target_path.exists():
                validation_result["validation_errors"].append(
                    f"Target file does not exist: {target_file}"
                )
                return validation_result

            # Parse patch and apply to temporary file
            patched_content = self._apply_patch_to_string(target_path, patch_content)
            if patched_content is None:
                validation_result["validation_errors"].append("Failed to apply patch")
                return validation_result

            # Syntax validation
            syntax_valid = self._validate_syntax(patched_content, target_file)
            validation_result["syntax_valid"] = syntax_valid

            if not syntax_valid:
                validation_result["validation_errors"].append(
                    "Patched code has syntax errors"
                )
                return validation_result

            # Semantic validation
            semantic_result = self._validate_semantics(target_path, patched_content)
            validation_result.update(semantic_result)

            # Security improvement check
            security_improvement = self._validate_security_improvement(
                target_path.read_text(encoding="utf-8"), patched_content
            )
            validation_result["security_improvement"] = security_improvement

            # Calculate overall confidence
            validation_result["confidence_score"] = self._calculate_confidence_score(
                validation_result
            )
            validation_result["is_safe"] = (
                validation_result["syntax_valid"]
                and validation_result["semantic_valid"]
                and validation_result["confidence_score"] > 0.7
            )

        except Exception as e:
            validation_result["validation_errors"].append(
                f"Validation failed: {str(e)}"
            )
            self.logger.error(f"Patch validation error: {e}")

        return validation_result

    def _apply_patch_to_string(
        self, target_path: Path, patch_content: str
    ) -> Optional[str]:
        """
        Apply unified diff patch to file content and return result.

        Args:
            target_path: Path to target file
            patch_content: Unified diff content

        Returns:
            Patched file content or None if patch failed
        """
        try:
            original_content = target_path.read_text(encoding="utf-8")
            original_lines = original_content.splitlines(keepends=True)

            # Parse unified diff
            patch_lines = patch_content.splitlines()

            # Simple patch application (basic implementation)
            # For production, would use more robust patch library
            result_lines = original_lines.copy()

            # This is a simplified patch parser - production would need robust implementation
            current_line = 0
            for line in patch_lines:
                if line.startswith("@@"):
                    # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
                    import re

                    match = re.match(
                        r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line
                    )
                    if match:
                        current_line = int(match.group(1)) - 1  # Convert to 0-based
                elif line.startswith("-"):
                    # Remove line
                    if current_line < len(result_lines):
                        result_lines.pop(current_line)
                elif line.startswith("+"):
                    # Add line
                    new_line = (
                        line[1:] + "\n" if not line[1:].endswith("\n") else line[1:]
                    )
                    result_lines.insert(current_line, new_line)
                    current_line += 1
                elif line.startswith(" "):
                    # Context line - advance
                    current_line += 1

            return "".join(result_lines)

        except Exception as e:
            self.logger.warning(f"Patch application failed: {e}")
            return None

    def _validate_syntax(self, content: str, file_path: str) -> bool:
        """
        Validate syntax of patched content.

        Args:
            content: File content to validate
            file_path: File path for language detection

        Returns:
            True if syntax is valid
        """
        try:
            file_ext = Path(file_path).suffix.lower()

            if file_ext == ".py":
                # Python syntax validation
                ast.parse(content)
                return True
            elif file_ext in [".js", ".ts"]:
                # JavaScript/TypeScript validation (simplified)
                # Would use proper JS parser in production
                return self._basic_js_syntax_check(content)
            else:
                # For other files, assume valid
                return True

        except SyntaxError as e:
            self.logger.warning(f"Syntax error in patched content: {e}")
            return False
        except Exception as e:
            self.logger.warning(f"Syntax validation failed: {e}")
            return False

    def _basic_js_syntax_check(self, content: str) -> bool:
        """
        Basic JavaScript syntax validation.

        Args:
            content: JavaScript content

        Returns:
            True if basic syntax appears valid
        """
        # Very basic JS syntax checks
        open_braces = content.count("{")
        close_braces = content.count("}")
        open_parens = content.count("(")
        close_parens = content.count(")")
        open_brackets = content.count("[")
        close_brackets = content.count("]")

        return (
            open_braces == close_braces
            and open_parens == close_parens
            and open_brackets == close_brackets
        )

    def _validate_semantics(
        self, original_path: Path, patched_content: str
    ) -> Dict[str, Any]:
        """
        Validate semantic consistency of the patch.

        Args:
            original_path: Path to original file
            patched_content: Patched file content

        Returns:
            Semantic validation results
        """
        result = {"semantic_valid": True, "regression_risk": "low", "warnings": []}

        try:
            original_content = original_path.read_text(encoding="utf-8")

            # Check for removed functions/classes
            removed_functions = self._find_removed_functions(
                original_content, patched_content
            )
            if removed_functions:
                result["warnings"].append(f"Removed functions: {removed_functions}")
                result["regression_risk"] = "medium"

            # Check for major structural changes
            original_lines = original_content.splitlines()
            patched_lines = patched_content.splitlines()

            line_change_ratio = abs(len(patched_lines) - len(original_lines)) / max(
                len(original_lines), 1
            )
            if line_change_ratio > 0.3:
                result["warnings"].append(
                    f"Large structural change: {line_change_ratio:.2%} line difference"
                )
                result["regression_risk"] = "high"

        except Exception as e:
            result["semantic_valid"] = False
            result["regression_risk"] = "high"
            self.logger.warning(f"Semantic validation failed: {e}")

        return result

    def _find_removed_functions(self, original: str, patched: str) -> List[str]:
        """
        Find functions that were removed in the patch.

        Args:
            original: Original file content
            patched: Patched file content

        Returns:
            List of removed function names
        """
        import re

        # Simple function detection (Python and JavaScript)
        function_pattern = r"(?:def|function|class)\s+(\w+)"

        original_functions = set(re.findall(function_pattern, original))
        patched_functions = set(re.findall(function_pattern, patched))

        return list(original_functions - patched_functions)

    def _validate_security_improvement(self, original: str, patched: str) -> bool:
        """
        Validate that the patch actually improves security.

        Args:
            original: Original file content
            patched: Patched file content

        Returns:
            True if security appears to be improved
        """
        # Check for security pattern improvements
        security_improvements = [
            # SQL injection fixes
            (r"%s|%d|\+.*\+", r"parameterized|bind|prepare"),
            # XSS fixes
            (r"innerHTML\s*=", r"textContent\s*=|innerHTML\s*=.*escape"),
            # Command injection fixes
            (r"shell=True", r"shell=False|shlex\.quote"),
            # Hardcoded credentials removal
            (
                r'password\s*=\s*["\'][^"\']+["\']',
                r"password\s*=.*input|environ|config",
            ),
        ]

        improvements_found = 0

        for vulnerable_pattern, secure_pattern in security_improvements:
            original_vulnerable = len(
                re.findall(vulnerable_pattern, original, re.IGNORECASE)
            )
            patched_vulnerable = len(
                re.findall(vulnerable_pattern, patched, re.IGNORECASE)
            )
            patched_secure = len(re.findall(secure_pattern, patched, re.IGNORECASE))

            if patched_vulnerable < original_vulnerable or patched_secure > 0:
                improvements_found += 1

        return improvements_found > 0

    def _calculate_confidence_score(self, validation_result: Dict[str, Any]) -> float:
        """
        Calculate confidence score for patch safety.

        Args:
            validation_result: Validation results

        Returns:
            Confidence score 0.0-1.0
        """
        score = 0.0

        # Syntax validity (30%)
        if validation_result["syntax_valid"]:
            score += 0.3

        # Semantic validity (25%)
        if validation_result["semantic_valid"]:
            score += 0.25

        # Security improvement (25%)
        if validation_result["security_improvement"]:
            score += 0.25

        # Regression risk (20%)
        risk_scores = {"low": 0.2, "medium": 0.1, "high": 0.0, "unknown": 0.05}
        score += risk_scores.get(validation_result["regression_risk"], 0.0)

        return min(1.0, score)


class PatchApplicator:
    """
    Safely applies validated security patches with backup and rollback capability.
    """

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self.backup_dir = self.workspace_root / ".navi_security_backups"
        self.logger = logging.getLogger(__name__)

        # Ensure backup directory exists
        self.backup_dir.mkdir(exist_ok=True)

    def apply_patch(
        self, patch_content: str, target_file: str, validation_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply a validated security patch with backup.

        Args:
            patch_content: Unified diff patch content
            target_file: Target file path relative to workspace
            validation_result: Patch validation results

        Returns:
            Application results with rollback information
        """
        application_result = {
            "success": False,
            "applied_at": datetime.utcnow().isoformat(),
            "backup_path": None,
            "rollback_id": None,
            "error": None,
        }

        if not validation_result.get("is_safe", False):
            application_result["error"] = "Patch failed safety validation"
            return application_result

        try:
            target_path = self.workspace_root / target_file

            if not target_path.exists():
                application_result["error"] = (
                    f"Target file does not exist: {target_file}"
                )
                return application_result

            # Create backup
            backup_info = self._create_backup(target_path)
            application_result["backup_path"] = backup_info["backup_path"]
            application_result["rollback_id"] = backup_info["rollback_id"]

            # Apply patch
            validator = PatchValidator(str(self.workspace_root))
            patched_content = validator._apply_patch_to_string(
                target_path, patch_content
            )

            if patched_content is None:
                application_result["error"] = "Failed to apply patch content"
                return application_result

            # Write patched content
            target_path.write_text(patched_content, encoding="utf-8")

            application_result["success"] = True
            self.logger.info(f"Successfully applied security patch to {target_file}")

        except Exception as e:
            application_result["error"] = str(e)
            self.logger.error(f"Patch application failed: {e}")

            # Attempt rollback on error
            if application_result.get("rollback_id"):
                try:
                    self.rollback_patch(application_result["rollback_id"])
                    self.logger.info("Rollback completed after patch failure")
                except Exception as rollback_error:
                    self.logger.error(f"Rollback also failed: {rollback_error}")

        return application_result

    def _create_backup(self, file_path: Path) -> Dict[str, str]:
        """
        Create backup of file before patching.

        Args:
            file_path: Path to file to backup

        Returns:
            Backup information
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        file_hash = hashlib.md5(str(file_path).encode()).hexdigest()[:8]
        rollback_id = f"{timestamp}_{file_hash}"

        backup_filename = f"{file_path.name}_{rollback_id}.bak"
        backup_path = self.backup_dir / backup_filename

        # Copy original file to backup
        shutil.copy2(file_path, backup_path)

        # Store backup metadata
        metadata = {
            "original_path": str(file_path),
            "backup_path": str(backup_path),
            "created_at": timestamp,
            "file_size": file_path.stat().st_size,
            "file_hash": hashlib.md5(file_path.read_bytes()).hexdigest(),
        }

        metadata_path = backup_path.with_suffix(".bak.json")
        metadata_path.write_text(json.dumps(metadata, indent=2))

        return {
            "rollback_id": rollback_id,
            "backup_path": str(backup_path),
            "metadata_path": str(metadata_path),
        }

    def rollback_patch(self, rollback_id: str) -> Dict[str, Any]:
        """
        Rollback a patch using backup.

        Args:
            rollback_id: Rollback identifier from patch application

        Returns:
            Rollback results
        """
        rollback_result = {
            "success": False,
            "rollback_id": rollback_id,
            "restored_file": None,
            "error": None,
        }

        try:
            # Find backup files
            backup_files = list(self.backup_dir.glob(f"*_{rollback_id}.bak"))
            metadata_files = list(self.backup_dir.glob(f"*_{rollback_id}.bak.json"))

            if not backup_files or not metadata_files:
                rollback_result["error"] = (
                    f"Backup files not found for rollback_id: {rollback_id}"
                )
                return rollback_result

            backup_file = backup_files[0]
            metadata_file = metadata_files[0]

            # Load metadata
            metadata = json.loads(metadata_file.read_text())
            original_path = Path(metadata["original_path"])

            # Restore original file
            shutil.copy2(backup_file, original_path)

            rollback_result["success"] = True
            rollback_result["restored_file"] = str(original_path)

            self.logger.info(f"Successfully rolled back patch for {original_path}")

        except Exception as e:
            rollback_result["error"] = str(e)
            self.logger.error(f"Rollback failed: {e}")

        return rollback_result

    def cleanup_old_backups(self, days_old: int = 30):
        """
        Clean up backup files older than specified days.

        Args:
            days_old: Number of days after which to remove backups
        """
        try:
            cutoff_time = datetime.utcnow().timestamp() - (days_old * 24 * 60 * 60)

            cleaned_count = 0
            for backup_file in self.backup_dir.glob("*.bak"):
                if backup_file.stat().st_mtime < cutoff_time:
                    backup_file.unlink()
                    # Remove corresponding metadata file
                    metadata_file = backup_file.with_suffix(".bak.json")
                    if metadata_file.exists():
                        metadata_file.unlink()
                    cleaned_count += 1

            self.logger.info(f"Cleaned up {cleaned_count} old backup files")

        except Exception as e:
            self.logger.warning(f"Backup cleanup failed: {e}")
