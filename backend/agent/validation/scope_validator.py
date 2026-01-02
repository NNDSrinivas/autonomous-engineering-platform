from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Set, List

from backend.agent.codegen.types import CodeChange
from backend.agent.validation.result import (
    ValidationResult,
    ValidationIssue,
    ValidationStatus,
)


class ScopeValidator:
    """
    Validates that code changes stay within safe scope boundaries.
    
    Prevents:
    - Excessive file modification count
    - Edits outside repository root
    - Modifications to forbidden paths
    - System/security-sensitive file changes
    """
    
    # Default limits - can be overridden per workspace
    DEFAULT_MAX_FILES = 20
    
    # Forbidden paths that should never be modified by AI
    FORBIDDEN_PATHS = {
        ".git",
        ".github/workflows",  # CI/CD workflows are sensitive
        ".env",
        ".env.local",
        ".env.production",
        "node_modules",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        "dist",
        "build",
        ".next",
        "secrets",
        "keys",
        "certificates",
        "certs",
    }
    
    # Forbidden file extensions
    FORBIDDEN_EXTENSIONS = {
        ".key",
        ".pem",
        ".p12",
        ".pfx",
        ".keystore",
        ".jks",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
    }
    
    def __init__(
        self,
        *,
        repo_root: str,
        max_files: int = DEFAULT_MAX_FILES,
        additional_forbidden_paths: Set[str] = None,
    ) -> None:
        self._repo_root = os.path.abspath(repo_root)
        self._max_files = max_files
        self._forbidden_paths = self.FORBIDDEN_PATHS.copy()
        if additional_forbidden_paths:
            self._forbidden_paths.update(additional_forbidden_paths)
    
    def validate(self, changes: Iterable[CodeChange]) -> ValidationResult:
        """
        Validate that all changes are within safe scope boundaries.
        """
        issues = []
        changes_list = list(changes)
        
        # Check file count limit
        if len(changes_list) > self._max_files:
            issues.append(ValidationIssue(
                validator="ScopeValidator",
                message=f"Too many files to modify ({len(changes_list)} > {self._max_files}). "
                       f"Consider breaking into smaller changes."
            ))
        
        # Check each file
        for change in changes_list:
            file_path = getattr(change, 'file_path', None) or getattr(change, 'path', None)
            if not file_path:
                continue
                
            # Validate path safety
            path_issues = self._validate_file_path(file_path)
            issues.extend(path_issues)
        
        if issues:
            return ValidationResult(
                status=ValidationStatus.FAILED,
                issues=issues
            )
        
        return ValidationResult(
            status=ValidationStatus.PASSED,
            issues=[]
        )
    
    def _validate_file_path(self, file_path: str) -> List[ValidationIssue]:
        """
        Validate individual file path for safety violations.
        """
        issues = []
        
        try:
            # Resolve absolute path
            if os.path.isabs(file_path):
                abs_path = file_path
            else:
                abs_path = os.path.abspath(os.path.join(self._repo_root, file_path))
            
            # Check if path is within repository root
            if not abs_path.startswith(self._repo_root):
                issues.append(ValidationIssue(
                    validator="ScopeValidator",
                    message=f"Path traversal detected: {file_path} resolves outside repository root",
                    file_path=file_path
                ))
                return issues
            
            # Convert to Path for easier manipulation
            path_obj = Path(abs_path)
            relative_path = path_obj.relative_to(self._repo_root)
            
            # Check forbidden paths
            for forbidden in self._forbidden_paths:
                if str(relative_path).startswith(forbidden) or forbidden in path_obj.parts:
                    issues.append(ValidationIssue(
                        validator="ScopeValidator",
                        message=f"Forbidden path: {file_path} (matches {forbidden})",
                        file_path=file_path
                    ))
                    break
            
            # Check forbidden extensions
            if path_obj.suffix.lower() in self.FORBIDDEN_EXTENSIONS:
                issues.append(ValidationIssue(
                    validator="ScopeValidator",
                    message=f"Forbidden file type: {file_path} ({path_obj.suffix})",
                    file_path=file_path
                ))
            
            # Check for suspicious patterns
            suspicious_patterns = ["../", "..\\"]
            for pattern in suspicious_patterns:
                if pattern in file_path:
                    issues.append(ValidationIssue(
                        validator="ScopeValidator",
                        message=f"Suspicious path pattern detected: {file_path} contains {pattern}",
                        file_path=file_path
                    ))
                    break
        
        except Exception as e:
            issues.append(ValidationIssue(
                validator="ScopeValidator",
                message=f"Path validation error for {file_path}: {e}",
                file_path=file_path
            ))
        
        return issues