"""
Enterprise Failure-to-Fix Mapping Engine

Intelligent mapping system that translates CI failures into actionable
repair strategies with targeted file analysis and confidence scoring.
"""

import os
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

from .ci_types import FailureType, FailureContext, RepairPlan, RepairAction, RepairConfidence

logger = logging.getLogger(__name__)

@dataclass
class FileRepairStrategy:
    """Repair strategy for specific file types"""
    file_pattern: str
    failure_types: List[FailureType]
    repair_actions: List[str]
    confidence_modifier: float

class FailureMapper:
    """
    Enterprise failure-to-fix mapping engine
    
    Maps classified CI failures to specific files, code locations,
    and generates targeted repair plans with confidence scoring.
    """
    
    def __init__(self):
        self.repair_strategies = self._initialize_repair_strategies()
        self.file_type_confidence = self._initialize_file_confidence()
        self.common_fixes = self._initialize_common_fixes()
    
    def map_failure_to_repair_plan(
        self,
        failure_context: FailureContext,
        workspace_path: str
    ) -> RepairPlan:
        """
        Generate comprehensive repair plan from failure context
        
        Args:
            failure_context: Classified failure with rich context
            workspace_path: Path to code workspace for file analysis
            
        Returns:
            Detailed repair plan with actions and confidence
        """
        # Analyze target files
        target_files = self._identify_target_files(
            failure_context, workspace_path
        )
        
        # Determine repair strategy
        repair_strategy = self._select_repair_strategy(
            failure_context.failure_type,
            target_files,
            failure_context.error_messages
        )
        
        # Calculate confidence
        confidence = self._calculate_repair_confidence(
            failure_context, target_files, repair_strategy
        )
        
        # Determine action based on confidence
        action = self._determine_repair_action(confidence, failure_context)
        
        # Generate expected changes
        expected_changes = self._predict_changes(
            failure_context.failure_type,
            target_files,
            failure_context.error_messages
        )
        
        # Create rollback plan
        rollback_plan = self._create_rollback_plan(target_files)
        
        return RepairPlan(
            action=action,
            confidence=self._confidence_to_enum(confidence),
            target_files=target_files,
            repair_strategy=repair_strategy,
            expected_changes=expected_changes,
            rollback_plan=rollback_plan,
            estimated_duration_seconds=self._estimate_duration(action, len(target_files)),
            requires_approval=confidence < 0.8,
            safety_checks=self._generate_safety_checks(failure_context)
        )
    
    def _initialize_repair_strategies(self) -> Dict[FailureType, List[str]]:
        """Initialize repair strategies for each failure type"""
        return {
            FailureType.TEST_FAILURE: [
                "fix_assertion_logic",
                "update_test_expectations", 
                "fix_mock_configuration",
                "update_test_data",
                "fix_async_test_timing"
            ],
            
            FailureType.BUILD_ERROR: [
                "fix_import_statements",
                "resolve_module_dependencies",
                "fix_syntax_errors",
                "update_build_configuration",
                "fix_circular_dependencies"
            ],
            
            FailureType.TYPE_ERROR: [
                "add_type_annotations",
                "fix_null_checks",
                "update_interface_definitions", 
                "fix_type_assertions",
                "add_optional_chaining"
            ],
            
            FailureType.LINT_ERROR: [
                "fix_formatting",
                "remove_unused_imports",
                "fix_variable_naming",
                "add_missing_semicolons",
                "fix_indentation"
            ],
            
            FailureType.ENV_MISSING: [
                "add_environment_variables",
                "update_configuration_files",
                "add_default_values",
                "fix_secret_references"
            ],
            
            FailureType.DEPENDENCY_ERROR: [
                "install_missing_packages",
                "update_package_versions",
                "fix_package_lock_conflicts",
                "resolve_version_conflicts"
            ],
            
            FailureType.SECURITY_SCAN: [
                "update_vulnerable_packages",
                "fix_security_vulnerabilities",
                "add_security_headers",
                "sanitize_user_inputs"
            ],
            
            FailureType.PERFORMANCE_REGRESSION: [
                "optimize_algorithms",
                "add_caching_layers",
                "fix_memory_leaks",
                "optimize_database_queries"
            ],
            
            FailureType.DEPLOYMENT_ERROR: [
                "fix_docker_configuration",
                "update_infrastructure_config",
                "fix_environment_setup",
                "resolve_port_conflicts"
            ]
        }
    
    def _initialize_file_confidence(self) -> Dict[str, float]:
        """Initialize confidence modifiers based on file types"""
        return {
            # High confidence file types
            '.test.ts': 0.9,
            '.test.js': 0.9,
            '.spec.ts': 0.9,
            '.spec.js': 0.9,
            'test_*.py': 0.9,
            
            # Medium confidence
            '.ts': 0.8,
            '.js': 0.7,
            '.py': 0.8,
            '.java': 0.7,
            
            # Configuration files
            'package.json': 0.9,
            'tsconfig.json': 0.8,
            'requirements.txt': 0.9,
            'Dockerfile': 0.8,
            
            # Lower confidence for generated files
            '.d.ts': 0.4,
            'dist/': 0.2,
            'build/': 0.2,
            'node_modules/': 0.1
        }
    
    def _initialize_common_fixes(self) -> Dict[str, List[str]]:
        """Initialize common fix patterns"""
        return {
            'null_check': [
                'if (value != null) {',
                'value?.property',
                'value || defaultValue'
            ],
            
            'import_fix': [
                'import { function } from "module"',
                'import * as module from "module"',
                'const module = require("module")'
            ],
            
            'type_annotation': [
                'function name(param: Type): ReturnType',
                'const variable: Type = value',
                'interface Name { property: Type }'
            ],
            
            'test_assertion': [
                'expect(actual).toBe(expected)',
                'expect(actual).toEqual(expected)',
                'assert actual == expected'
            ]
        }
    
    def _identify_target_files(
        self, 
        failure_context: FailureContext,
        workspace_path: str
    ) -> List[str]:
        """Identify files that need repair based on failure context"""
        target_files = []
        
        # Start with files directly mentioned in failure
        mentioned_files = failure_context.affected_files or []
        
        # Validate and normalize file paths
        for file_path in mentioned_files:
            normalized = self._normalize_file_path(file_path, workspace_path)
            if normalized and os.path.exists(normalized):
                target_files.append(normalized)
        
        # If no direct files, use intelligent search
        if not target_files:
            target_files = self._search_relevant_files(
                failure_context, workspace_path
            )
        
        # Apply file filters based on failure type
        filtered_files = self._filter_files_by_type(
            target_files, failure_context.failure_type
        )
        
        return filtered_files[:10]  # Limit to manageable number
    
    def _normalize_file_path(self, file_path: str, workspace_path: str) -> Optional[str]:
        """Normalize and validate file path"""
        try:
            # Handle relative paths
            if not file_path.startswith('/'):
                file_path = os.path.join(workspace_path, file_path)
            
            # Resolve to absolute path
            normalized = os.path.abspath(file_path)
            
            # Ensure it's within workspace
            if not normalized.startswith(os.path.abspath(workspace_path)):
                return None
            
            return normalized
            
        except Exception as e:
            logger.warning(f"Could not normalize file path {file_path}: {e}")
            return None
    
    def _search_relevant_files(
        self,
        failure_context: FailureContext,
        workspace_path: str
    ) -> List[str]:
        """Search for relevant files using failure context"""
        relevant_files = []
        
        # Search patterns based on failure type
        search_patterns = self._get_search_patterns(failure_context.failure_type)
        
        try:
            for root, dirs, files in os.walk(workspace_path):
                # Skip common irrelevant directories
                dirs[:] = [d for d in dirs if not d.startswith('.') 
                          and d not in ['node_modules', 'dist', 'build', '__pycache__']]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    # Check if file matches any search pattern
                    if any(self._file_matches_pattern(file, pattern) 
                          for pattern in search_patterns):
                        relevant_files.append(file_path)
                        
                        if len(relevant_files) >= 20:  # Limit search results
                            break
                
                if len(relevant_files) >= 20:
                    break
                    
        except Exception as e:
            logger.warning(f"Error searching for relevant files: {e}")
        
        return relevant_files
    
    def _get_search_patterns(self, failure_type: FailureType) -> List[str]:
        """Get file search patterns for failure type"""
        patterns = {
            FailureType.TEST_FAILURE: ['*.test.ts', '*.test.js', '*.spec.ts', '*.spec.js', 'test_*.py'],
            FailureType.BUILD_ERROR: ['*.ts', '*.js', '*.py', 'package.json', 'tsconfig.json'],
            FailureType.TYPE_ERROR: ['*.ts', '*.tsx', '*.d.ts'],
            FailureType.LINT_ERROR: ['*.ts', '*.js', '*.py', '.eslintrc*', 'pyproject.toml'],
            FailureType.ENV_MISSING: ['.env*', 'config.*', '*.config.js', '*.config.ts'],
            FailureType.DEPENDENCY_ERROR: ['package.json', 'requirements.txt', 'Pipfile', 'poetry.lock'],
            FailureType.DEPLOYMENT_ERROR: ['Dockerfile', 'docker-compose.yml', '*.tf', '*.yml']
        }
        
        return patterns.get(failure_type, ['*.ts', '*.js', '*.py'])
    
    def _file_matches_pattern(self, filename: str, pattern: str) -> bool:
        """Check if filename matches pattern"""
        import fnmatch
        return fnmatch.fnmatch(filename, pattern)
    
    def _filter_files_by_type(
        self, 
        files: List[str], 
        failure_type: FailureType
    ) -> List[str]:
        """Filter files based on failure type relevance"""
        filtered = []
        
        for file_path in files:
            filename = os.path.basename(file_path)
            os.path.splitext(filename)[1]
            
            # Calculate relevance score
            relevance = self._calculate_file_relevance(
                file_path, failure_type
            )
            
            if relevance > 0.3:  # Threshold for relevance
                filtered.append(file_path)
        
        # Sort by relevance (higher relevance first)
        filtered.sort(key=lambda f: self._calculate_file_relevance(f, failure_type), 
                     reverse=True)
        
        return filtered
    
    def _calculate_file_relevance(self, file_path: str, failure_type: FailureType) -> float:
        """Calculate how relevant a file is to the failure type"""
        filename = os.path.basename(file_path)
        file_ext = os.path.splitext(filename)[1]
        
        base_score = 0.5
        
        # Type-specific scoring
        if failure_type == FailureType.TEST_FAILURE:
            if 'test' in filename.lower() or 'spec' in filename.lower():
                base_score = 0.9
        
        elif failure_type == FailureType.TYPE_ERROR:
            if file_ext in ['.ts', '.tsx']:
                base_score = 0.8
        
        elif failure_type == FailureType.DEPENDENCY_ERROR:
            if filename in ['package.json', 'requirements.txt', 'Pipfile']:
                base_score = 0.9
        
        # Apply file type confidence modifier
        for pattern, confidence in self.file_type_confidence.items():
            if pattern in filename:
                base_score *= confidence
                break
        
        return min(base_score, 1.0)
    
    def _select_repair_strategy(
        self,
        failure_type: FailureType,
        target_files: List[str],
        error_messages: List[str]
    ) -> str:
        """Select best repair strategy based on context"""
        strategies = self.repair_strategies.get(failure_type, ["generic_fix"])
        
        # Analyze error messages for specific strategy selection
        error_text = ' '.join(error_messages).lower()
        
        # Strategy selection logic
        if failure_type == FailureType.TYPE_ERROR:
            if 'cannot read property' in error_text or 'undefined' in error_text:
                return "add_null_checks"
            elif 'not assignable' in error_text:
                return "fix_type_assertions"
        
        elif failure_type == FailureType.TEST_FAILURE:
            if 'timeout' in error_text:
                return "fix_async_test_timing"
            elif 'expected' in error_text and 'received' in error_text:
                return "fix_assertion_logic"
        
        elif failure_type == FailureType.BUILD_ERROR:
            if 'cannot find module' in error_text:
                return "fix_import_statements"
            elif 'syntax error' in error_text:
                return "fix_syntax_errors"
        
        # Default to first strategy for the type
        return strategies[0] if strategies else "generic_fix"
    
    def _calculate_repair_confidence(
        self,
        failure_context: FailureContext,
        target_files: List[str],
        repair_strategy: str
    ) -> float:
        """Calculate confidence in repair success"""
        base_confidence = failure_context.confidence
        
        # Adjust based on number of files
        file_count_modifier = max(0.5, 1.0 - (len(target_files) - 1) * 0.1)
        
        # Adjust based on strategy complexity
        strategy_confidence = {
            "fix_formatting": 0.95,
            "remove_unused_imports": 0.9,
            "add_null_checks": 0.8,
            "fix_import_statements": 0.8,
            "fix_assertion_logic": 0.7,
            "optimize_algorithms": 0.4
        }
        
        strategy_modifier = strategy_confidence.get(repair_strategy, 0.6)
        
        # Combine factors
        final_confidence = base_confidence * file_count_modifier * strategy_modifier
        
        return min(final_confidence, 0.95)  # Cap at 95%
    
    def _determine_repair_action(
        self, 
        confidence: float,
        failure_context: FailureContext
    ) -> RepairAction:
        """Determine appropriate repair action based on confidence"""
        if confidence >= 0.8:
            return RepairAction.AUTO_FIX
        elif confidence >= 0.6:
            return RepairAction.SUGGEST_FIX
        elif failure_context.failure_type in [
            FailureType.SECURITY_SCAN,
            FailureType.DEPLOYMENT_ERROR
        ]:
            return RepairAction.ESCALATE
        else:
            return RepairAction.INVESTIGATE
    
    def _predict_changes(
        self,
        failure_type: FailureType,
        target_files: List[str],
        error_messages: List[str]
    ) -> List[str]:
        """Predict specific changes that will be made"""
        changes = []
        
        error_text = ' '.join(error_messages).lower()
        
        if failure_type == FailureType.TYPE_ERROR:
            if 'undefined' in error_text:
                changes.append("Add null/undefined checks")
            if 'not assignable' in error_text:
                changes.append("Fix type annotations")
        
        elif failure_type == FailureType.LINT_ERROR:
            changes.extend([
                "Fix code formatting",
                "Remove unused imports",
                "Fix naming conventions"
            ])
        
        elif failure_type == FailureType.TEST_FAILURE:
            changes.extend([
                "Update test assertions",
                "Fix test data/mocks"
            ])
        
        elif failure_type == FailureType.BUILD_ERROR:
            changes.extend([
                "Fix import statements", 
                "Resolve module dependencies"
            ])
        
        # Add file-specific changes
        for file_path in target_files:
            filename = os.path.basename(file_path)
            changes.append(f"Modify {filename}")
        
        return changes[:5]  # Limit to most important changes
    
    def _create_rollback_plan(self, target_files: List[str]) -> str:
        """Create rollback plan for the repair"""
        if not target_files:
            return "No files to rollback"
        
        file_count = len(target_files)
        if file_count == 1:
            return f"Rollback changes to {os.path.basename(target_files[0])}"
        else:
            return f"Rollback changes to {file_count} files using git reset"
    
    def _estimate_duration(self, action: RepairAction, file_count: int) -> int:
        """Estimate repair duration in seconds"""
        base_times = {
            RepairAction.AUTO_FIX: 30,
            RepairAction.SUGGEST_FIX: 60,
            RepairAction.INVESTIGATE: 120,
            RepairAction.ESCALATE: 300
        }
        
        base_time = base_times.get(action, 60)
        
        # Scale with file count
        file_multiplier = 1 + (file_count - 1) * 0.5
        
        return int(base_time * file_multiplier)
    
    def _generate_safety_checks(self, failure_context: FailureContext) -> List[str]:
        """Generate safety checks for the repair"""
        checks = [
            "Verify no syntax errors after changes",
            "Ensure tests still compile",
            "Check for breaking changes"
        ]
        
        if failure_context.failure_type == FailureType.SECURITY_SCAN:
            checks.extend([
                "Verify security fix doesn't introduce new vulnerabilities",
                "Check for proper input sanitization"
            ])
        
        elif failure_context.failure_type == FailureType.TYPE_ERROR:
            checks.extend([
                "Verify type safety is maintained",
                "Check for proper null handling"
            ])
        
        elif failure_context.failure_type == FailureType.DEPLOYMENT_ERROR:
            checks.extend([
                "Verify infrastructure changes are valid",
                "Check for environment compatibility"
            ])
        
        return checks
    
    def _confidence_to_enum(self, confidence: float) -> RepairConfidence:
        """Convert numeric confidence to enum"""
        if confidence >= 0.9:
            return RepairConfidence.HIGH
        elif confidence >= 0.6:
            return RepairConfidence.MEDIUM
        else:
            return RepairConfidence.LOW