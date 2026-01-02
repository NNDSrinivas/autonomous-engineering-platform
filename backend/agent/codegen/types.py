from typing import Dict, Any, List, Optional, Literal
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


# ============================================================================
# Phase 3.3 Core Types - AEI-Grade Code Generation Engine
# ============================================================================

class ChangeType(Enum):
    """Types of code changes supported by the engine."""
    CREATE_FILE = "create_file"
    MODIFY_FILE = "modify_file"
    DELETE_FILE = "delete_file"
    RENAME_FILE = "rename_file"
    CREATE_DIRECTORY = "create_directory"
    DELETE_DIRECTORY = "delete_directory"


class ChangeIntent(Enum):
    """High-level intent classification for changes."""
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
    IMPLEMENT_FEATURE = "implement_feature"
    FIX_BUG = "fix_bug"
    REFACTOR = "refactor"
    ADD_TESTS = "add_tests"
    UPDATE_DEPENDENCIES = "update_dependencies"
    IMPROVE_PERFORMANCE = "improve_performance"
    ENHANCE_SECURITY = "enhance_security"
    ADD_DOCUMENTATION = "add_documentation"


class ValidationLevel(Enum):
    """Validation strictness levels."""
    NONE = "none"
    SYNTAX_ONLY = "syntax_only"
    TYPE_CHECK = "type_check"
    LINT = "lint"
    FULL = "full"  # Syntax + Type + Lint + Tests


@dataclass
class CodeChange:
    """Represents a single code modification within a file."""
    line_start: int
    line_end: int
    original_code: str
    new_code: str
    change_type: Literal["insert", "replace", "delete"]
    reasoning: str
    confidence: float = field(default=0.8)  # 0.0 - 1.0
    
    # Phase 3.3 - Diff Generator fields
    diff: Optional[str] = field(default=None)  # Unified diff content
    file_path: Optional[str] = field(default=None)  # File being modified
    change_intent: Optional[ChangeIntent] = field(default=None)  # High-level intent
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "line_start": self.line_start,
            "line_end": self.line_end,
            "original_code": self.original_code,
            "new_code": self.new_code,
            "change_type": self.change_type,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "diff": self.diff,
            "file_path": self.file_path,
            "change_intent": self.change_intent.value if self.change_intent else None
        }


@dataclass
class PlannedFileChange:
    """
    Represents a planned change to a file in the codebase.
    Used by ContextAssembler and DiffGenerator.
    """
    path: str
    intent: ChangeIntent  # CREATE, MODIFY, DELETE
    reasoning: str
    dependencies: List[str] = field(default_factory=list)
    priority: int = 1  # 1=high, 2=medium, 3=low
    
    # Legacy compatibility - keep existing fields
    file_path: Optional[str] = field(default=None)
    change_type: Optional[ChangeType] = field(default=None)
    changes: List[CodeChange] = field(default_factory=list)
    new_file_content: Optional[str] = None  # For CREATE operations
    rename_to: Optional[str] = None  # For RENAME_FILE
    estimated_complexity: float = field(default=0.5)  # 0.0 - 1.0
    risk_level: Literal["low", "medium", "high"] = "medium"
    requires_review: bool = True
    
    def __post_init__(self):
        # Ensure backward compatibility - use proper initialization patterns
        # Note: For frozen dataclasses, consider using default_factory or 
        # restructuring to avoid post_init mutations
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "change_type": self.change_type.value,
            "changes": [change.to_dict() for change in self.changes],
            "new_file_content": self.new_file_content,
            "rename_to": self.rename_to,
            "reasoning": self.reasoning,
            "dependencies": self.dependencies,
            "estimated_complexity": self.estimated_complexity,
            "risk_level": self.risk_level,
            "requires_review": self.requires_review
        }
    
    @property
    def total_changes(self) -> int:
        """Total number of code changes in this file."""
        return len(self.changes)
    
    @property
    def lines_affected(self) -> int:
        """Total number of lines affected by changes."""
        return sum(change.line_end - change.line_start + 1 for change in self.changes)


@dataclass
class ChangePlan:
    """Complete plan for implementing a user request via code changes."""
    
    # Core identification
    plan_id: str
    intent: ChangeIntent
    description: str
    user_request: str
    
    # File changes
    file_changes: List[PlannedFileChange] = field(default_factory=list)
    
    # Execution ordering
    execution_order: List[str] = field(default_factory=list)  # File paths in execution order
    
    # Validation settings
    validation_level: ValidationLevel = ValidationLevel.FULL
    skip_files: List[str] = field(default_factory=list)  # Files to skip validation
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    estimated_duration_minutes: int = 5
    total_complexity: float = field(default=0.0)
    overall_risk: Literal["low", "medium", "high"] = "medium"
    reasoning: str = ""  # Phase 4.1.2 compatibility
    complexity: str = "medium"  # Phase 4.1.2 compatibility
    
    # Context
    workspace_root: str = ""
    repo_context: Dict[str, Any] = field(default_factory=dict)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived metrics after initialization."""
        if self.file_changes:
            # Calculate total complexity as average of file complexities
            complexities = [fc.estimated_complexity for fc in self.file_changes]
            self.total_complexity = sum(complexities) / len(complexities)
            
            # Determine overall risk
            high_risk_files = [fc for fc in self.file_changes if fc.risk_level == "high"]
            medium_risk_files = [fc for fc in self.file_changes if fc.risk_level == "medium"]
            
            if high_risk_files or len(medium_risk_files) > 3:
                self.overall_risk = "high"
            elif medium_risk_files:
                self.overall_risk = "medium"
            else:
                self.overall_risk = "low"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "intent": self.intent.value,
            "description": self.description,
            "user_request": self.user_request,
            "file_changes": [fc.to_dict() for fc in self.file_changes],
            "execution_order": self.execution_order,
            "validation_level": self.validation_level.value,
            "skip_files": self.skip_files,
            "created_at": self.created_at.isoformat(),
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "total_complexity": self.total_complexity,
            "overall_risk": self.overall_risk,
            "workspace_root": self.workspace_root,
            "repo_context": self.repo_context,
            "user_preferences": self.user_preferences
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChangePlan":
        """Reconstruct ChangePlan from dictionary."""
        # Parse file changes
        file_changes = []
        for fc_data in data.get("file_changes", []):
            changes = []
            for change_data in fc_data.get("changes", []):
                changes.append(CodeChange(
                    line_start=change_data["line_start"],
                    line_end=change_data["line_end"],
                    original_code=change_data["original_code"],
                    new_code=change_data["new_code"],
                    change_type=change_data["change_type"],
                    reasoning=change_data["reasoning"],
                    confidence=change_data.get("confidence", 0.8)
                ))
            
            file_changes.append(PlannedFileChange(
                file_path=fc_data["file_path"],
                change_type=ChangeType(fc_data["change_type"]),
                changes=changes,
                new_file_content=fc_data.get("new_file_content"),
                rename_to=fc_data.get("rename_to"),
                reasoning=fc_data.get("reasoning", ""),
                dependencies=fc_data.get("dependencies", []),
                estimated_complexity=fc_data.get("estimated_complexity", 0.5),
                risk_level=fc_data.get("risk_level", "medium"),
                requires_review=fc_data.get("requires_review", True)
            ))
        
        return cls(
            plan_id=data["plan_id"],
            intent=ChangeIntent(data["intent"]),
            description=data["description"],
            user_request=data["user_request"],
            file_changes=file_changes,
            execution_order=data.get("execution_order", []),
            validation_level=ValidationLevel(data.get("validation_level", "full")),
            skip_files=data.get("skip_files", []),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            estimated_duration_minutes=data.get("estimated_duration_minutes", 5),
            total_complexity=data.get("total_complexity", 0.0),
            overall_risk=data.get("overall_risk", "medium"),
            workspace_root=data.get("workspace_root", ""),
            repo_context=data.get("repo_context", {}),
            user_preferences=data.get("user_preferences", {})
        )
    
    # Utility methods
    
    @property
    def total_files_affected(self) -> int:
        """Total number of files that will be changed."""
        return len(self.file_changes)
    
    @property
    def total_lines_affected(self) -> int:
        """Total number of lines across all files that will be changed."""
        return sum(fc.lines_affected for fc in self.file_changes)
    
    @property
    def new_files_count(self) -> int:
        """Number of new files to be created."""
        return len([fc for fc in self.file_changes if fc.change_type == ChangeType.CREATE_FILE])
    
    @property
    def modified_files_count(self) -> int:
        """Number of existing files to be modified."""
        return len([fc for fc in self.file_changes if fc.change_type == ChangeType.MODIFY_FILE])
    
    @property
    def deleted_files_count(self) -> int:
        """Number of files to be deleted."""
        return len([fc for fc in self.file_changes if fc.change_type == ChangeType.DELETE_FILE])
    
    def get_file_change(self, file_path: str) -> Optional[PlannedFileChange]:
        """Get the planned changes for a specific file."""
        for fc in self.file_changes:
            if fc.file_path == file_path:
                return fc
        return None
    
    def add_file_change(self, file_change: PlannedFileChange) -> None:
        """Add a new file change to the plan."""
        # Remove existing change for the same file if present
        self.file_changes = [fc for fc in self.file_changes if fc.file_path != file_change.file_path]
        self.file_changes.append(file_change)
        
        # Update execution order if not already present
        if file_change.file_path not in self.execution_order:
            self.execution_order.append(file_change.file_path)
    
    def remove_file_change(self, file_path: str) -> bool:
        """Remove a file change from the plan. Returns True if removed."""
        original_count = len(self.file_changes)
        self.file_changes = [fc for fc in self.file_changes if fc.file_path != file_path]
        
        # Remove from execution order
        if file_path in self.execution_order:
            self.execution_order.remove(file_path)
        
        return len(self.file_changes) < original_count
    
    def validate_dependencies(self) -> List[str]:
        """Validate that all file dependencies are satisfied. Returns list of issues."""
        issues = []
        file_paths = {fc.file_path for fc in self.file_changes}
        
        for fc in self.file_changes:
            for dep in fc.dependencies:
                if dep not in file_paths:
                    issues.append(f"File {fc.file_path} depends on {dep}, but {dep} is not in the plan")
        
        return issues
    
    def optimize_execution_order(self) -> None:
        """Optimize the execution order based on file dependencies."""
        # Simple topological sort based on dependencies
        ordered = []
        remaining = {fc.file_path: fc for fc in self.file_changes}
        
        while remaining:
            # Find files with no unresolved dependencies
            ready = []
            for file_path, fc in remaining.items():
                deps_satisfied = all(dep in ordered or dep not in remaining for dep in fc.dependencies)
                if deps_satisfied:
                    ready.append(file_path)
            
            if not ready:
                # Circular dependency - just take the first remaining
                ready = [next(iter(remaining.keys()))]
            
            # Add ready files to order and remove from remaining
            for file_path in ready:
                ordered.append(file_path)
                del remaining[file_path]
        
        self.execution_order = ordered


# ============================================================================
# Result Types
# ============================================================================

@dataclass
class ChangeResult:
    """Result of executing a single file change."""
    file_path: str
    success: bool
    changes_applied: int = 0
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    execution_time_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "success": self.success,
            "changes_applied": self.changes_applied,
            "error_message": self.error_message,
            "warnings": self.warnings,
            "execution_time_ms": self.execution_time_ms
        }


@dataclass
class PlanExecutionResult:
    """Result of executing a complete ChangePlan."""
    plan_id: str
    success: bool
    file_results: List[ChangeResult] = field(default_factory=list)
    total_execution_time_ms: int = 0
    validation_results: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def files_changed_successfully(self) -> int:
        return len([r for r in self.file_results if r.success])
    
    @property
    def files_failed(self) -> int:
        return len([r for r in self.file_results if not r.success])
    
    @property
    def total_changes_applied(self) -> int:
        return sum(r.changes_applied for r in self.file_results)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "success": self.success,
            "file_results": [r.to_dict() for r in self.file_results],
            "total_execution_time_ms": self.total_execution_time_ms,
            "validation_results": self.validation_results,
            "summary": {
                "files_changed_successfully": self.files_changed_successfully,
                "files_failed": self.files_failed,
                "total_changes_applied": self.total_changes_applied
            }
        }