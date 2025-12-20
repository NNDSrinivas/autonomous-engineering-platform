"""
Self-Healing Agent - Autonomous Error Detection and Recovery
Implements detect → diagnose → fix → validate → retry cycle for autonomous engineering.
"""

import logging
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

try:
    from ..analysis.rca_agent import RCAAgent
    from ..sandbox.navios_sandbox import NaviOSSandbox
    from ..security.security_agent import SecurityAgent, SecurityFinding
    from ...memory.episodic_memory import EpisodicMemory, MemoryEventType
    from ...services.llm import call_llm
except ImportError:
    from backend.agents.analysis.rca_agent import RCAAgent
    from backend.agents.sandbox.navios_sandbox import NaviOSSandbox
    from backend.agents.security.security_agent import SecurityAgent, SecurityFinding
    from backend.memory.episodic_memory import EpisodicMemory, MemoryEventType
    from backend.services.llm import call_llm

class HealingState(Enum):
    """States of the self-healing process."""
    IDLE = "idle"
    DETECTING = "detecting"
    DIAGNOSING = "diagnosing"
    GENERATING_FIX = "generating_fix"
    APPLYING_FIX = "applying_fix"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"

class FailureType(Enum):
    """Types of failures that can be healed."""
    SYNTAX_ERROR = "syntax_error"
    RUNTIME_ERROR = "runtime_error"
    TEST_FAILURE = "test_failure"
    SECURITY_VULNERABILITY = "security_vulnerability"
    PERFORMANCE_ISSUE = "performance_issue"
    DEPENDENCY_ERROR = "dependency_error"
    DEPLOYMENT_ERROR = "deployment_error"
    INTEGRATION_ERROR = "integration_error"

@dataclass
@dataclass
@dataclass
class FailureContext:
    """Context information about a detected failure."""
    failure_id: str
    failure_type: FailureType
    error_message: str
    stack_trace: Optional[str]
    affected_files: List[str]
    environment_info: Dict[str, Any]
    reproduction_steps: List[str]
    severity: str  # critical, high, medium, low
    detected_at: datetime
    metadata: Dict[str, Any]

@dataclass
class HealingResult:
    """Result of a self-healing attempt."""
    healing_id: str
    failure_context: FailureContext
    success: bool
    healing_steps: List[Dict[str, Any]]
    final_state: HealingState
    patches_applied: List[str]
    tests_passed: bool
    rollback_performed: bool
    healing_time_seconds: float
    error_message: Optional[str]
    confidence_score: float
    metadata: Dict[str, Any]

class PatchService:
    """
    Service for applying and validating patches during self-healing.
    """
    
    def __init__(self, workspace_root: str, sandbox: NaviOSSandbox):
        self.workspace_root = Path(workspace_root)
        self.sandbox = sandbox
        self.logger = logging.getLogger(__name__)
    
    async def apply_patch(self, patch_content: str, target_file: str) -> Dict[str, Any]:
        """
        Apply a patch to a target file.
        
        Args:
            patch_content: Patch content (unified diff or direct content)
            target_file: Target file path
            
        Returns:
            Application result
        """
        try:
            # Apply patch using sandbox for safety
            operation_code = f"""
import os
from pathlib import Path

target_file = Path(r"{target_file}")
patch_content = '''
{patch_content}
'''

# Apply patch (simplified - production would use proper patch parsing)
if patch_content.strip():
    target_file.write_text(patch_content, encoding='utf-8')
    print(f"Applied patch to {{target_file}}")
else:
    print("No patch content provided")
"""
            
            result = await self.sandbox.safe_execute(
                operation_code=operation_code,
                operation_description=f"Apply patch to {target_file}",
                auto_rollback_on_error=True
            )
            
            return {
                'success': result.success,
                'output': result.output,
                'errors': result.errors,
                'snapshot_id': result.snapshot_id
            }
            
        except Exception as e:
            return {
                'success': False,
                'errors': [str(e)],
                'output': None,
                'snapshot_id': None
            }
    
    async def run_tests(self, test_pattern: Optional[str] = None) -> Dict[str, Any]:
        """
        Run tests to validate patches.
        
        Args:
            test_pattern: Pattern to match test files
            
        Returns:
            Test results
        """
        try:
            # Run tests using sandbox
            test_code = """
import subprocess
import sys
from pathlib import Path

# Try different test runners
test_commands = [
    ['python', '-m', 'pytest', '-v'],
    ['npm', 'test'],
    ['python', '-m', 'unittest', 'discover'],
    ['node', '--test']
]

results = []

for cmd in test_commands:
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=120,
            cwd=str(Path.cwd())
        )
        
        results.append({
            'command': ' '.join(cmd),
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr
        })
        
        # If tests pass, break
        if result.returncode == 0:
            break
            
    except FileNotFoundError:
        # Command not available
        continue
    except Exception as e:
        results.append({
            'command': ' '.join(cmd),
            'error': str(e)
        })

print("Test results:")
for result in results:
    print(f"Command: {result.get('command', 'unknown')}")
    print(f"Return code: {result.get('returncode', 'error')}")
    if result.get('stdout'):
        print(f"STDOUT: {result['stdout'][:500]}")
    if result.get('stderr'):
        print(f"STDERR: {result['stderr'][:500]}")
    print("---")
"""
            
            result = await self.sandbox.safe_execute(
                operation_code=test_code,
                operation_description="Run validation tests",
                auto_rollback_on_error=False
            )
            
            # Parse test results from output
            test_passed = result.success and "failed" not in result.output.lower()
            
            return {
                'success': result.success,
                'tests_passed': test_passed,
                'output': result.output,
                'errors': result.errors
            }
            
        except Exception as e:
            return {
                'success': False,
                'tests_passed': False,
                'errors': [str(e)],
                'output': None
            }

class SelfHealingAgent:
    """
    Main self-healing agent that implements autonomous error detection and recovery.
    
    Capabilities:
    - Automatic failure detection from logs, tests, and runtime errors
    - Root cause analysis using RCA agent
    - Patch generation and application
    - Validation through testing
    - Automatic rollback on failure
    - Learning from healing attempts
    """
    
    def __init__(self, 
                 workspace_root: str,
                 memory: Optional[EpisodicMemory] = None,
                 sandbox: Optional[NaviOSSandbox] = None):
        """
        Initialize self-healing agent.
        
        Args:
            workspace_root: Root directory of the workspace
            memory: Episodic memory for learning
            sandbox: Execution sandbox for safe operations
        """
        self.workspace_root = Path(workspace_root)
        self.memory = memory or EpisodicMemory()
        self.sandbox = sandbox or NaviOSSandbox(str(workspace_root))
        self.logger = logging.getLogger(__name__)
        
        # Initialize sub-agents
        self.rca_agent = RCAAgent(str(workspace_root), self.memory)
        self.security_agent = SecurityAgent(str(workspace_root), self.memory)
        self.patch_service = PatchService(str(workspace_root), self.sandbox)
        
        # Healing state
        self.state = HealingState.IDLE
        self.active_healings: Dict[str, HealingResult] = {}
        self.healing_history: List[HealingResult] = []
        
        # Configuration
        self.config = {
            'max_healing_attempts': 3,
            'healing_timeout_seconds': 600,  # 10 minutes
            'auto_rollback_on_failure': True,
            'confidence_threshold': 0.7,
            'max_concurrent_healings': 2
        }
        
        self.logger.info(f"SelfHealingAgent initialized for workspace: {workspace_root}")
    
    async def detect_and_heal(self, 
                            trigger_source: str = "manual",
                            context: Optional[Dict[str, Any]] = None) -> HealingResult:
        """
        Main entry point for detection and healing cycle.
        
        Args:
            trigger_source: Source that triggered healing (manual, automated, etc.)
            context: Additional context information
            
        Returns:
            Healing result
        """
        healing_start = datetime.utcnow()
        healing_id = f"heal_{healing_start.strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(trigger_source.encode()).hexdigest()[:8]}"
        
        self.logger.info(f"Starting healing cycle: {healing_id}")
        self.state = HealingState.DETECTING
        
        # Create failure context
        failure_context = FailureContext(
            failure_id=healing_id,
            failure_type=FailureType.RUNTIME_ERROR,
            error_message=context.get('error_message', 'Unknown failure') if context else 'Unknown failure',
            stack_trace=context.get('stack_trace') if context else None,
            affected_files=context.get('affected_files', []) if context else [],
            environment_info=context.get('environment_info', {}) if context else {},
            reproduction_steps=context.get('reproduction_steps', []) if context else [],
            severity=context.get('severity', 'medium') if context else 'medium',
            detected_at=healing_start,
            metadata=context if context else {}
        )
        
        # Initialize healing result
        healing_result = HealingResult(
            healing_id=healing_id,
            failure_context=failure_context,
            success=False,
            healing_steps=[],
            final_state=HealingState.FAILED,
            patches_applied=[],
            tests_passed=False,
            rollback_performed=False,
            healing_time_seconds=0.0,
            error_message=None,
            confidence_score=0.0,
            metadata={
                'trigger_source': trigger_source,
                'context': context or {}
            }
        )
        
        try:
            # Step 1: Detect failures
            failures = await self._detect_failures(context)
            healing_result.healing_steps.append({
                'step': 'detection',
                'timestamp': datetime.utcnow().isoformat(),
                'result': f"Detected {len(failures)} failures"
            })
            
            if not failures:
                healing_result.success = True
                healing_result.final_state = HealingState.COMPLETED
                healing_result.error_message = "No failures detected"
                return healing_result
            
            # Process the most critical failure
            failure_context = max(failures, key=lambda f: self._get_severity_score(f.severity))
            healing_result.failure_context = failure_context
            
            # Step 2: Diagnose and generate fix
            self.state = HealingState.DIAGNOSING
            diagnosis = await self._diagnose_failure(failure_context)
            healing_result.healing_steps.append({
                'step': 'diagnosis',
                'timestamp': datetime.utcnow().isoformat(),
                'result': diagnosis
            })
            
            # Step 3: Generate and apply patches
            self.state = HealingState.GENERATING_FIX
            patches = await self._generate_healing_patches(failure_context, diagnosis)
            
            if not patches:
                healing_result.error_message = "No patches could be generated"
                return healing_result
            
            healing_result.healing_steps.append({
                'step': 'patch_generation',
                'timestamp': datetime.utcnow().isoformat(),
                'result': f"Generated {len(patches)} patches"
            })
            
            # Step 4: Apply patches with validation
            self.state = HealingState.APPLYING_FIX
            application_results = await self._apply_patches_safely(patches)
            healing_result.patches_applied = [p['file_path'] for p in patches]
            
            # Step 5: Validate healing
            self.state = HealingState.VALIDATING
            validation_result = await self._validate_healing(failure_context)
            healing_result.tests_passed = validation_result['tests_passed']
            
            healing_result.healing_steps.append({
                'step': 'validation',
                'timestamp': datetime.utcnow().isoformat(),
                'result': validation_result
            })
            
            # Determine final success
            healing_result.success = (
                application_results['success'] and 
                validation_result['tests_passed'] and
                validation_result['issue_resolved']
            )
            
            if healing_result.success:
                healing_result.final_state = HealingState.COMPLETED
                healing_result.confidence_score = self._calculate_healing_confidence(
                    failure_context, patches, validation_result
                )
            else:
                # Rollback if configured
                if self.config['auto_rollback_on_failure']:
                    rollback_success = await self._perform_rollback(application_results.get('snapshot_id'))
                    healing_result.rollback_performed = rollback_success
                    healing_result.final_state = HealingState.ROLLED_BACK
                else:
                    healing_result.final_state = HealingState.FAILED
            
        except Exception as e:
            healing_result.error_message = str(e)
            healing_result.final_state = HealingState.FAILED
            self.logger.error(f"Healing cycle failed: {e}")
        
        finally:
            # Calculate total healing time
            healing_result.healing_time_seconds = (datetime.utcnow() - healing_start).total_seconds()
            
            # Record healing attempt
            self.healing_history.append(healing_result)
            self.state = HealingState.IDLE
            
            # Record in memory
            await self._record_healing_in_memory(healing_result)
        
        self.logger.info(f"Healing cycle completed: {healing_id}, Success: {healing_result.success}")
        return healing_result
    
    async def _detect_failures(self, context: Optional[Dict[str, Any]] = None) -> List[FailureContext]:
        """
        Detect failures in the workspace.
        
        Args:
            context: Detection context
            
        Returns:
            List of detected failures
        """
        failures = []
        
        try:
            # 1. Check for syntax errors
            syntax_failures = await self._detect_syntax_errors()
            failures.extend(syntax_failures)
            
            # 2. Check for test failures
            test_failures = await self._detect_test_failures()
            failures.extend(test_failures)
            
            # 3. Check for security vulnerabilities
            security_failures = await self._detect_security_issues()
            failures.extend(security_failures)
            
            # 4. Check runtime errors from logs
            if context and context.get('error_logs'):
                runtime_failures = await self._detect_runtime_errors(context['error_logs'])
                failures.extend(runtime_failures)
            
            # 5. Check for dependency issues
            dependency_failures = await self._detect_dependency_issues()
            failures.extend(dependency_failures)
            
        except Exception as e:
            self.logger.warning(f"Failure detection error: {e}")
        
        return failures
    
    async def _detect_syntax_errors(self) -> List[FailureContext]:
        """Detect syntax errors in code files."""
        failures = []
        
        try:
            # Check Python files
            python_files = list(self.workspace_root.rglob('*.py'))
            for py_file in python_files[:20]:  # Limit to avoid performance issues
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    import ast
                    ast.parse(content)
                    
                except SyntaxError as e:
                    failure = FailureContext(
                        failure_id=f"syntax_{hashlib.md5(str(py_file).encode()).hexdigest()[:8]}",
                        failure_type=FailureType.SYNTAX_ERROR,
                        error_message=str(e),
                        stack_trace=None,
                        affected_files=[str(py_file.relative_to(self.workspace_root))],
                        environment_info={'file_type': 'python'},
                        reproduction_steps=[f"Parse file {py_file}"],
                        severity='high',
                        detected_at=datetime.utcnow(),
                        metadata={'line_number': e.lineno, 'column': e.offset}
                    )
                    failures.append(failure)
                
                except Exception:
                    continue  # Skip files that can't be parsed
            
        except Exception as e:
            self.logger.warning(f"Syntax error detection failed: {e}")
        
        return failures
    
    async def _detect_test_failures(self) -> List[FailureContext]:
        """Detect test failures."""
        failures = []
        
        try:
            # Run tests and capture failures
            test_result = await self.patch_service.run_tests()
            
            if not test_result['tests_passed']:
                failure = FailureContext(
                    failure_id=f"test_failure_{datetime.utcnow().strftime('%H%M%S')}",
                    failure_type=FailureType.TEST_FAILURE,
                    error_message="Tests are failing",
                    stack_trace=test_result.get('output'),
                    affected_files=[],  # Would parse from test output
                    environment_info={'test_runner': 'pytest'},
                    reproduction_steps=['Run test suite'],
                    severity='medium',
                    detected_at=datetime.utcnow(),
                    metadata={'test_output': test_result.get('output', '')[:1000]}
                )
                failures.append(failure)
            
        except Exception as e:
            self.logger.warning(f"Test failure detection failed: {e}")
        
        return failures
    
    async def _detect_security_issues(self) -> List[FailureContext]:
        """Detect security vulnerabilities."""
        failures = []
        
        try:
            # Run security scan
            security_scan = await self.security_agent.comprehensive_scan(
                scan_types=['sast', 'secrets'],
                include_dependencies=False,  # Quick scan
                generate_patches=False
            )
            
            # Convert high-severity findings to failures
            for finding in security_scan.get('findings', []):
                if finding.severity in ['critical', 'high']:
                    failure = FailureContext(
                        failure_id=f"security_{finding.finding_id}",
                        failure_type=FailureType.SECURITY_VULNERABILITY,
                        error_message=finding.title,
                        stack_trace=finding.description,
                        affected_files=[finding.file_path],
                        environment_info={'scanner': 'security_agent'},
                        reproduction_steps=[f"Scan file {finding.file_path}"],
                        severity=finding.severity,
                        detected_at=datetime.utcnow(),
                        metadata={'cwe_id': finding.cwe_id, 'line_number': finding.line_number}
                    )
                    failures.append(failure)
            
        except Exception as e:
            self.logger.warning(f"Security issue detection failed: {e}")
        
        return failures
    
    async def _detect_runtime_errors(self, error_logs: List[str]) -> List[FailureContext]:
        """Detect runtime errors from logs."""
        failures = []
        
        try:
            for i, log_entry in enumerate(error_logs[:10]):  # Limit processing
                if any(keyword in log_entry.lower() for keyword in ['error', 'exception', 'traceback']):
                    failure = FailureContext(
                        failure_id=f"runtime_error_{i}",
                        failure_type=FailureType.RUNTIME_ERROR,
                        error_message=log_entry[:200],
                        stack_trace=log_entry,
                        affected_files=[],
                        environment_info={'source': 'logs'},
                        reproduction_steps=['Check application logs'],
                        severity='medium',
                        detected_at=datetime.utcnow(),
                        metadata={'log_entry': log_entry[:500]}
                    )
                    failures.append(failure)
            
        except Exception as e:
            self.logger.warning(f"Runtime error detection failed: {e}")
        
        return failures
    
    async def _detect_dependency_issues(self) -> List[FailureContext]:
        """Detect dependency-related issues."""
        failures = []
        
        try:
            # Check for missing imports, outdated packages, etc.
            # This would be more sophisticated in production
            
            package_files = [
                self.workspace_root / 'package.json',
                self.workspace_root / 'requirements.txt',
                self.workspace_root / 'pyproject.toml'
            ]
            
            for pkg_file in package_files:
                if pkg_file.exists():
                    # Simple check for dependency issues
                    # Production would use proper dependency analyzers
                    pass
            
        except Exception as e:
            self.logger.warning(f"Dependency issue detection failed: {e}")
        
        return failures
    
    async def _diagnose_failure(self, failure_context: FailureContext) -> Dict[str, Any]:
        """
        Diagnose a failure using RCA agent.
        
        Args:
            failure_context: Context of the failure
            
        Returns:
            Diagnosis results
        """
        try:
            # Use RCA agent for detailed analysis
            rca_result = await self.rca_agent.analyze_failure(
                error=failure_context.error_message,
                error_context={
                    'stack_trace': failure_context.stack_trace,
                    'affected_files': failure_context.affected_files,
                    **failure_context.metadata
                }
            )
            
            return {
                'root_cause': rca_result.get('root_cause', 'Unknown'),
                'confidence': rca_result.get('confidence', 0.5),
                'recommendations': rca_result.get('recommendations', []),
                'similar_cases': rca_result.get('similar_cases', []),
                'dependency_chain': rca_result.get('dependency_chain', [])
            }
            
        except Exception as e:
            self.logger.warning(f"Failure diagnosis failed: {e}")
            return {
                'root_cause': f"Diagnosis failed: {str(e)}",
                'confidence': 0.1,
                'recommendations': [],
                'similar_cases': [],
                'dependency_chain': []
            }
    
    async def _generate_healing_patches(self, 
                                      failure_context: FailureContext,
                                      diagnosis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate patches to fix the failure.
        
        Args:
            failure_context: Context of the failure
            diagnosis: Diagnosis results
            
        Returns:
            List of patches to apply
        """
        patches = []
        
        try:
            # Generate patches based on failure type and diagnosis
            if failure_context.failure_type == FailureType.SYNTAX_ERROR:
                patches = await self._generate_syntax_fix_patches(failure_context, diagnosis)
            elif failure_context.failure_type == FailureType.SECURITY_VULNERABILITY:
                patches = await self._generate_security_fix_patches(failure_context, diagnosis)
            elif failure_context.failure_type == FailureType.TEST_FAILURE:
                patches = await self._generate_test_fix_patches(failure_context, diagnosis)
            else:
                patches = await self._generate_generic_fix_patches(failure_context, diagnosis)
            
        except Exception as e:
            self.logger.warning(f"Patch generation failed: {e}")
        
        return patches
    
    async def _generate_syntax_fix_patches(self, 
                                         failure_context: FailureContext,
                                         diagnosis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate patches for syntax errors."""
        patches = []
        
        if failure_context.affected_files:
            file_path = failure_context.affected_files[0]
            
            try:
                full_path = self.workspace_root / file_path
                if full_path.exists():
                    content = full_path.read_text(encoding='utf-8')
                    
                    # Use LLM to fix syntax error
                    fix_prompt = f"""
                    Fix this Python syntax error:
                    
                    Error: {failure_context.error_message}
                    Line: {failure_context.metadata.get('line_number', 'unknown')}
                    
                    File content:
                    {content}
                    
                    Return the corrected file content.
                    """
                    
                    fixed_content = await call_llm(
                        message=fix_prompt,
                        context={},
                        model="gpt-4",
                        mode="code_fix"
                    )
                    
                    patches.append({
                        'file_path': file_path,
                        'patch_type': 'syntax_fix',
                        'content': fixed_content.strip(),
                        'description': f"Fix syntax error: {failure_context.error_message}"
                    })
                
            except Exception as e:
                self.logger.warning(f"Syntax patch generation failed: {e}")
        
        return patches
    
    async def _generate_security_fix_patches(self, 
                                           failure_context: FailureContext,
                                           diagnosis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate patches for security vulnerabilities."""
        # Delegate to security agent for patch generation
        try:
            security_patches = await self.security_agent._generate_security_patches([
                SecurityFinding(
                    finding_id=failure_context.failure_id,
                    severity=failure_context.severity,
                    confidence='high',
                    title=failure_context.error_message,
                    description=failure_context.stack_trace or failure_context.error_message,
                    file_path=failure_context.affected_files[0] if failure_context.affected_files else 'unknown',
                    line_number=failure_context.metadata.get('line_number', 1)
                )
            ])
            
            return [
                {
                    'file_path': patch['file_path'],
                    'patch_type': 'security_fix',
                    'content': patch['patch_content'],
                    'description': patch['title']
                }
                for patch in security_patches
            ]
            
        except Exception as e:
            self.logger.warning(f"Security patch generation failed: {e}")
            return []
    
    async def _generate_test_fix_patches(self, 
                                       failure_context: FailureContext,
                                       diagnosis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate patches for test failures."""
        # Analyze test failure and generate fixes
        patches = []
        
        try:
            test_output = failure_context.metadata.get('test_output', '')
            
            fix_prompt = f"""
            Analyze this test failure and suggest fixes:
            
            Test Output:
            {test_output}
            
            Error: {failure_context.error_message}
            
            Provide specific file changes to fix the failing tests.
            """
            
            fix_suggestions = await call_llm(
                message=fix_prompt,
                context={},
                model="gpt-4",
                mode="test_fix"
            )
            
            # Parse fix suggestions and create patches
            # This would be more sophisticated in production
            patches.append({
                'file_path': 'test_fixes.md',
                'patch_type': 'test_fix',
                'content': fix_suggestions,
                'description': 'Generated test fixes'
            })
            
        except Exception as e:
            self.logger.warning(f"Test patch generation failed: {e}")
        
        return patches
    
    async def _generate_generic_fix_patches(self, 
                                          failure_context: FailureContext,
                                          diagnosis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate generic patches for other failure types."""
        patches = []
        
        try:
            # Use RCA agent's patch generation capability
            if hasattr(self.rca_agent, '_generate_patches'):
                rca_patches = await self.rca_agent._generate_patches(
                    diagnosis.get('recommendations', []),
                    {
                        'error_message': failure_context.error_message,
                        'affected_files': failure_context.affected_files,
                        'stack_trace': failure_context.stack_trace
                    }
                )
                
                patches.extend([
                    {
                        'file_path': patch.get('file_path', ''),
                        'patch_type': 'generic_fix',
                        'content': patch.get('content', ''),
                        'description': patch.get('description', 'Generic fix')
                    }
                    for patch in rca_patches
                ])
            
        except Exception as e:
            self.logger.warning(f"Generic patch generation failed: {e}")
        
        return patches
    
    async def _apply_patches_safely(self, patches: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Apply patches safely with rollback capability.
        
        Args:
            patches: List of patches to apply
            
        Returns:
            Application results
        """
        results = {
            'success': True,
            'applied_patches': [],
            'failed_patches': [],
            'snapshot_id': None
        }
        
        try:
            # Create snapshot before applying patches
            snapshot = self.sandbox.snapshot_manager.create_snapshot("Pre-healing snapshot")
            results['snapshot_id'] = snapshot.snapshot_id
            
            # Apply each patch
            for patch in patches:
                try:
                    patch_result = await self.patch_service.apply_patch(
                        patch['content'],
                        patch['file_path']
                    )
                    
                    if patch_result['success']:
                        results['applied_patches'].append(patch)
                    else:
                        results['failed_patches'].append({
                            'patch': patch,
                            'error': patch_result.get('errors', ['Unknown error'])
                        })
                        results['success'] = False
                        
                except Exception as e:
                    results['failed_patches'].append({
                        'patch': patch,
                        'error': [str(e)]
                    })
                    results['success'] = False
            
        except Exception as e:
            results['success'] = False
            results['error'] = str(e)
        
        return results
    
    async def _validate_healing(self, failure_context: FailureContext) -> Dict[str, Any]:
        """
        Validate that the healing was successful.
        
        Args:
            failure_context: Original failure context
            
        Returns:
            Validation results
        """
        validation_result = {
            'tests_passed': False,
            'issue_resolved': False,
            'validation_details': {}
        }
        
        try:
            # Run tests
            test_result = await self.patch_service.run_tests()
            validation_result['tests_passed'] = test_result['tests_passed']
            validation_result['validation_details']['test_result'] = test_result
            
            # Check if original issue is resolved
            if failure_context.failure_type == FailureType.SYNTAX_ERROR:
                # Re-check syntax
                syntax_check = await self._detect_syntax_errors()
                validation_result['issue_resolved'] = len(syntax_check) == 0
            elif failure_context.failure_type == FailureType.SECURITY_VULNERABILITY:
                # Re-run security scan
                security_check = await self._detect_security_issues()
                validation_result['issue_resolved'] = len(security_check) == 0
            else:
                # Generic validation - assume resolved if tests pass
                validation_result['issue_resolved'] = validation_result['tests_passed']
            
        except Exception as e:
            validation_result['validation_details']['error'] = str(e)
        
        return validation_result
    
    async def _perform_rollback(self, snapshot_id: Optional[str]) -> bool:
        """
        Perform rollback to a snapshot.
        
        Args:
            snapshot_id: Snapshot to rollback to
            
        Returns:
            True if rollback was successful
        """
        if not snapshot_id:
            return False
        
        try:
            return self.sandbox.manual_rollback(snapshot_id)
        except Exception as e:
            self.logger.error(f"Rollback failed: {e}")
            return False
    
    def _get_severity_score(self, severity: str) -> int:
        """Convert severity to numeric score for prioritization."""
        scores = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
        return scores.get(severity.lower(), 0)
    
    def _calculate_healing_confidence(self, 
                                    failure_context: FailureContext,
                                    patches: List[Dict[str, Any]],
                                    validation_result: Dict[str, Any]) -> float:
        """Calculate confidence score for healing success."""
        confidence = 0.0
        
        # Base confidence from tests passing
        if validation_result['tests_passed']:
            confidence += 0.4
        
        # Confidence from issue resolution
        if validation_result['issue_resolved']:
            confidence += 0.3
        
        # Confidence from number of patches (fewer is better)
        patch_confidence = max(0.2, 0.3 - (len(patches) * 0.05))
        confidence += patch_confidence
        
        # Confidence from failure type (some are easier to fix)
        type_confidence = {
            FailureType.SYNTAX_ERROR: 0.1,
            FailureType.SECURITY_VULNERABILITY: 0.05,
            FailureType.TEST_FAILURE: 0.08,
            FailureType.RUNTIME_ERROR: 0.03
        }.get(failure_context.failure_type, 0.05)
        confidence += type_confidence
        
        return min(1.0, confidence)
    
    async def _record_healing_in_memory(self, healing_result: HealingResult):
        """Record healing attempt in episodic memory."""
        try:
            event_content = f"Self-healing attempt: {healing_result.healing_id}"
            if healing_result.success:
                event_content += " (SUCCESS)"
            else:
                event_content += " (FAILED)"
            
            if healing_result.failure_context:
                event_content += f" - {healing_result.failure_context.failure_type.value}"
            
            await self.memory.record_event(
                event_type=MemoryEventType.BUG_FIX,
                content=event_content,
                metadata={
                    'healing_id': healing_result.healing_id,
                    'success': healing_result.success,
                    'healing_time': healing_result.healing_time_seconds,
                    'patches_applied': len(healing_result.patches_applied),
                    'confidence_score': healing_result.confidence_score,
                    'rollback_performed': healing_result.rollback_performed,
                    'failure_type': healing_result.failure_context.failure_type.value if healing_result.failure_context else None
                }
            )
            
        except Exception as e:
            self.logger.warning(f"Failed to record healing in memory: {e}")
    
    def get_healing_status(self) -> Dict[str, Any]:
        """
        Get current healing agent status.
        
        Returns:
            Status information
        """
        recent_healings = [h for h in self.healing_history if 
                          datetime.utcnow() - datetime.fromisoformat(h.metadata.get('timestamp', '2024-01-01T00:00:00')) < timedelta(hours=24)]
        
        success_rate = 0.0
        if self.healing_history:
            successful = len([h for h in self.healing_history if h.success])
            success_rate = successful / len(self.healing_history) * 100
        
        return {
            'state': self.state.value,
            'total_healings': len(self.healing_history),
            'recent_healings_24h': len(recent_healings),
            'success_rate_percent': success_rate,
            'active_healings': len(self.active_healings),
            'configuration': self.config,
            'workspace_root': str(self.workspace_root)
        }
