"""
Action Marketplace - Extensible Skill System for Navi
Plugin registry with sandboxed execution for developer actions.
Like VS Code extensions but for autonomous engineering tasks.
"""

import json
import logging
import shutil
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
import asyncio
from dataclasses import dataclass, asdict
from enum import Enum

try:
    from ...memory.episodic_memory import EpisodicMemory, MemoryEventType
except ImportError:
    from backend.memory.episodic_memory import EpisodicMemory, MemoryEventType

class ActionCategory(Enum):
    """Categories for marketplace actions."""
    DEPLOYMENT = "deployment"
    TESTING = "testing"
    OPTIMIZATION = "optimization"
    SECURITY = "security"
    DOCUMENTATION = "documentation"
    REFACTORING = "refactoring"
    ANALYTICS = "analytics"
    INTEGRATION = "integration"
    UTILITY = "utility"

class ActionPermission(Enum):
    """Permission levels for actions."""
    FILESYSTEM_READ = "filesystem_read"
    FILESYSTEM_WRITE = "filesystem_write"
    NETWORK_ACCESS = "network_access"
    SUBPROCESS_EXECUTION = "subprocess_execution"
    ENVIRONMENT_VARIABLES = "environment_variables"
    SYSTEM_COMMANDS = "system_commands"

@dataclass
class ActionMetadata:
    """Metadata for marketplace action."""
    action_id: str
    name: str
    version: str
    description: str
    category: ActionCategory
    author: str
    permissions: List[ActionPermission]
    dependencies: List[str]
    parameters: Dict[str, Any]
    examples: List[Dict[str, Any]]
    install_size_bytes: int
    created_at: str
    updated_at: str
    downloads: int
    rating: float
    verified: bool

@dataclass
class ActionResult:
    """Result of action execution."""
    success: bool
    output: Any
    logs: List[str]
    errors: List[str]
    execution_time_seconds: float
    resources_used: Dict[str, Any]
    metadata: Dict[str, Any]

class ActionSandbox:
    """
    Secure sandbox for executing marketplace actions.
    Provides isolated filesystem, network, and process controls.
    """
    
    def __init__(self, workspace_root: str, sandbox_config: Optional[Dict[str, Any]] = None):
        self.workspace_root = Path(workspace_root)
        self.config = sandbox_config or {}
        self.logger = logging.getLogger(__name__)
        
        # Sandbox limits
        self.limits = {
            'max_execution_time': self.config.get('max_execution_time', 300),  # 5 minutes
            'max_memory_mb': self.config.get('max_memory_mb', 512),
            'max_disk_mb': self.config.get('max_disk_mb', 100),
            'max_network_requests': self.config.get('max_network_requests', 50),
            'allowed_hosts': self.config.get('allowed_hosts', ['api.github.com', 'pypi.org'])
        }
        
        # Create sandbox directory
        self.sandbox_dir = self.workspace_root / '.navi_sandbox'
        self.sandbox_dir.mkdir(exist_ok=True)
    
    async def execute_action(self, 
                           action_code: str,
                           action_metadata: ActionMetadata,
                           parameters: Dict[str, Any],
                           context: Dict[str, Any]) -> ActionResult:
        """
        Execute an action within the sandbox environment.
        
        Args:
            action_code: Python code for the action
            action_metadata: Action metadata with permissions
            parameters: Execution parameters
            context: Execution context (workspace info, etc.)
            
        Returns:
            Action execution result
        """
        start_time = datetime.utcnow()
        execution_logs = []
        execution_errors = []
        
        result = ActionResult(
            success=False,
            output=None,
            logs=execution_logs,
            errors=execution_errors,
            execution_time_seconds=0.0,
            resources_used={},
            metadata={'action_id': action_metadata.action_id}
        )
        
        try:
            # Create isolated execution environment
            execution_id = f"action_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(action_metadata.action_id.encode()).hexdigest()[:8]}"
            execution_dir = self.sandbox_dir / execution_id
            execution_dir.mkdir()
            
            execution_logs.append(f"Created sandbox environment: {execution_id}")
            
            # Prepare execution environment
            env_setup = await self._setup_execution_environment(
                execution_dir, action_metadata, parameters, context
            )
            
            if not env_setup['success']:
                execution_errors.extend(env_setup['errors'])
                return result
            
            # Execute action with resource monitoring
            execution_result = await self._execute_with_monitoring(
                execution_dir, action_code, action_metadata, parameters, context
            )
            
            result.success = execution_result['success']
            result.output = execution_result['output']
            result.logs.extend(execution_result['logs'])
            result.errors.extend(execution_result['errors'])
            result.resources_used = execution_result['resources_used']
            
        except Exception as e:
            execution_errors.append(f"Action execution failed: {str(e)}")
            self.logger.error(f"Sandbox execution error: {e}")
        
        finally:
            # Calculate execution time
            result.execution_time_seconds = (datetime.utcnow() - start_time).total_seconds()
            
            # Cleanup sandbox environment
            try:
                if 'execution_dir' in locals():
                    shutil.rmtree(execution_dir, ignore_errors=True)
                    execution_logs.append("Cleaned up sandbox environment")
            except Exception as cleanup_error:
                execution_logs.append(f"Cleanup warning: {cleanup_error}")
        
        return result
    
    async def _setup_execution_environment(self, 
                                         execution_dir: Path,
                                         action_metadata: ActionMetadata,
                                         parameters: Dict[str, Any],
                                         context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Set up isolated execution environment for action.
        
        Args:
            execution_dir: Directory for execution
            action_metadata: Action metadata
            parameters: Execution parameters  
            context: Execution context
            
        Returns:
            Setup result
        """
        setup_result = {
            'success': False,
            'errors': [],
            'environment_path': str(execution_dir)
        }
        
        try:
            # Create workspace link (read-only if no write permission)
            workspace_link = execution_dir / 'workspace'
            
            if ActionPermission.FILESYSTEM_WRITE in action_metadata.permissions:
                # Full workspace access
                workspace_link.symlink_to(self.workspace_root)
            elif ActionPermission.FILESYSTEM_READ in action_metadata.permissions:
                # Read-only workspace copy (for small workspaces)
                if self._get_workspace_size() < self.limits['max_disk_mb'] * 1024 * 1024:
                    shutil.copytree(self.workspace_root, workspace_link, dirs_exist_ok=True)
                else:
                    workspace_link.symlink_to(self.workspace_root)
            
            # Create parameters file
            params_file = execution_dir / 'parameters.json'
            params_file.write_text(json.dumps(parameters, indent=2))
            
            # Create context file
            context_file = execution_dir / 'context.json'
            context_file.write_text(json.dumps(context, indent=2))
            
            # Install dependencies if any
            if action_metadata.dependencies:
                deps_result = await self._install_dependencies(
                    execution_dir, action_metadata.dependencies
                )
                
                if not deps_result['success']:
                    setup_result['errors'].extend(deps_result['errors'])
                    return setup_result
            
            setup_result['success'] = True
            
        except Exception as e:
            setup_result['errors'].append(f"Environment setup failed: {str(e)}")
        
        return setup_result
    
    async def _execute_with_monitoring(self, 
                                     execution_dir: Path,
                                     action_code: str,
                                     action_metadata: ActionMetadata,
                                     parameters: Dict[str, Any],
                                     context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute action code with resource monitoring.
        
        Args:
            execution_dir: Execution directory
            action_code: Python code to execute
            action_metadata: Action metadata
            parameters: Parameters
            context: Context
            
        Returns:
            Execution result
        """
        result = {
            'success': False,
            'output': None,
            'logs': [],
            'errors': [],
            'resources_used': {
                'peak_memory_mb': 0,
                'disk_used_mb': 0,
                'network_requests': 0,
                'subprocess_calls': 0
            }
        }
        
        try:
            # Create action script
            action_script = execution_dir / 'action.py'
            
            # Wrap action code with monitoring and security
            wrapped_code = self._wrap_action_code(action_code, action_metadata, parameters, context)
            action_script.write_text(wrapped_code)
            
            # Execute with timeout and monitoring
            process = await asyncio.create_subprocess_exec(
                'python', str(action_script),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(execution_dir)
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.limits['max_execution_time']
                )
                
                if process.returncode == 0:
                    result['success'] = True
                    result['output'] = stdout.decode('utf-8')
                else:
                    result['errors'].append(f"Action failed with return code {process.returncode}")
                    result['errors'].append(stderr.decode('utf-8'))
                
                result['logs'].append(f"Action completed with return code {process.returncode}")
                
            except asyncio.TimeoutError:
                process.kill()
                result['errors'].append(f"Action timed out after {self.limits['max_execution_time']} seconds")
            
            # Collect resource usage
            result['resources_used'] = self._collect_resource_usage(execution_dir)
            
        except Exception as e:
            result['errors'].append(f"Execution failed: {str(e)}")
        
        return result
    
    def _wrap_action_code(self, 
                         action_code: str,
                         action_metadata: ActionMetadata,
                         parameters: Dict[str, Any],
                         context: Dict[str, Any]) -> str:
        """
        Wrap action code with security and monitoring.
        
        Args:
            action_code: Original action code
            action_metadata: Action metadata
            parameters: Parameters
            context: Context
            
        Returns:
            Wrapped Python code
        """
        security_imports = """
import sys
import os
import json
import time
from pathlib import Path
import subprocess
import functools

# Load parameters and context
with open('parameters.json', 'r') as f:
    PARAMETERS = json.load(f)

with open('context.json', 'r') as f:
    CONTEXT = json.load(f)
"""
        
        # Add permission-based restrictions
        permission_code = ""
        
        if ActionPermission.SUBPROCESS_EXECUTION not in action_metadata.permissions:
            permission_code += """
# Restrict subprocess execution
original_subprocess_run = subprocess.run
def restricted_subprocess_run(*args, **kwargs):
    raise PermissionError("Subprocess execution not permitted for this action")
subprocess.run = restricted_subprocess_run
"""
        
        if ActionPermission.NETWORK_ACCESS not in action_metadata.permissions:
            permission_code += """
# Restrict network access
import socket
original_socket = socket.socket
def restricted_socket(*args, **kwargs):
    raise PermissionError("Network access not permitted for this action")
socket.socket = restricted_socket
"""
        
        # Resource monitoring code
        monitoring_code = """
import psutil
import threading

# Resource monitoring
resource_stats = {'peak_memory': 0, 'network_requests': 0}

def monitor_resources():
    while True:
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            resource_stats['peak_memory'] = max(resource_stats['peak_memory'], memory_mb)
            time.sleep(0.1)
        except:
            break

# Start monitoring thread
monitor_thread = threading.Thread(target=monitor_resources, daemon=True)
monitor_thread.start()
"""
        
        # Execution wrapper
        execution_wrapper = f"""
try:
    # Action execution starts here
    print("=== ACTION EXECUTION START ===")
    
{action_code}
    
    print("=== ACTION EXECUTION END ===")
    print(f"Peak memory usage: {{resource_stats['peak_memory']:.2f}} MB")
    
except Exception as e:
    print(f"ACTION ERROR: {{e}}")
    sys.exit(1)
"""
        
        return security_imports + permission_code + monitoring_code + execution_wrapper
    
    async def _install_dependencies(self, execution_dir: Path, dependencies: List[str]) -> Dict[str, Any]:
        """
        Install dependencies for action execution.
        
        Args:
            execution_dir: Execution directory
            dependencies: List of dependency strings
            
        Returns:
            Installation result
        """
        result = {
            'success': False,
            'errors': []
        }
        
        try:
            # Create virtual environment
            venv_dir = execution_dir / 'venv'
            
            # Create venv
            venv_process = await asyncio.create_subprocess_exec(
                'python', '-m', 'venv', str(venv_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await venv_process.communicate()
            
            if venv_process.returncode != 0:
                result['errors'].append("Failed to create virtual environment")
                return result
            
            # Install dependencies
            pip_executable = venv_dir / 'bin' / 'pip'
            if not pip_executable.exists():
                pip_executable = venv_dir / 'Scripts' / 'pip.exe'  # Windows
            
            for dependency in dependencies[:10]:  # Limit to 10 deps
                install_process = await asyncio.create_subprocess_exec(
                    str(pip_executable), 'install', dependency,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                await install_process.communicate()
                
                if install_process.returncode != 0:
                    result['errors'].append(f"Failed to install dependency: {dependency}")
                    return result
            
            result['success'] = True
            
        except Exception as e:
            result['errors'].append(f"Dependency installation failed: {str(e)}")
        
        return result
    
    def _get_workspace_size(self) -> int:
        """Get workspace size in bytes."""
        try:
            total_size = 0
            for file_path in self.workspace_root.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            return total_size
        except Exception:
            return 2**63 - 1  # Large int value if can't calculate
    
    def _collect_resource_usage(self, execution_dir: Path) -> Dict[str, Any]:
        """Collect resource usage statistics."""
        return {
            'peak_memory_mb': 0,  # Would collect from monitoring
            'disk_used_mb': self._get_directory_size(execution_dir) / 1024 / 1024,
            'network_requests': 0,  # Would monitor network calls
            'subprocess_calls': 0   # Would count subprocess executions
        }
    
    def _get_directory_size(self, directory: Path) -> int:
        """Get directory size in bytes."""
        try:
            total_size = 0
            for file_path in directory.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            return total_size
        except Exception:
            return 0

class ActionRegistry:
    """
    Registry for managing marketplace actions.
    Handles installation, updates, and metadata management.
    """
    
    def __init__(self, registry_path: str, memory: Optional[EpisodicMemory] = None):
        self.registry_path = Path(registry_path)
        self.registry_path.mkdir(exist_ok=True)
        self.memory = memory or EpisodicMemory()
        self.logger = logging.getLogger(__name__)
        
        # Registry structure
        self.actions_dir = self.registry_path / 'actions'
        self.metadata_file = self.registry_path / 'registry.json'
        self.installed_file = self.registry_path / 'installed.json'
        
        self.actions_dir.mkdir(exist_ok=True)
        
        # Load registry
        self.registry_data = self._load_registry()
        self.installed_actions = self._load_installed_actions()
    
    def search_actions(self, 
                      query: str,
                      category: Optional[ActionCategory] = None,
                      max_results: int = 20) -> List[ActionMetadata]:
        """
        Search for actions in the marketplace.
        
        Args:
            query: Search query
            category: Filter by category
            max_results: Maximum results to return
            
        Returns:
            List of matching action metadata
        """
        results = []
        
        # Search in registry data
        for action_id, metadata_dict in self.registry_data.get('actions', {}).items():
            try:
                metadata = ActionMetadata(**metadata_dict)
                
                # Category filter
                if category and metadata.category != category:
                    continue
                
                # Text search
                searchable_text = f"{metadata.name} {metadata.description} {metadata.author}".lower()
                if query.lower() in searchable_text:
                    results.append(metadata)
                
                if len(results) >= max_results:
                    break
                    
            except Exception as e:
                self.logger.warning(f"Invalid action metadata for {action_id}: {e}")
        
        # Sort by rating and downloads
        results.sort(key=lambda x: (x.rating, x.downloads), reverse=True)
        
        return results
    
    async def install_action(self, action_id: str) -> Dict[str, Any]:
        """
        Install an action from the marketplace.
        
        Args:
            action_id: Action identifier
            
        Returns:
            Installation result
        """
        install_result = {
            'success': False,
            'action_id': action_id,
            'installed_at': datetime.utcnow().isoformat(),
            'error': None
        }
        
        try:
            # Check if action exists in registry
            if action_id not in self.registry_data.get('actions', {}):
                install_result['error'] = f"Action {action_id} not found in registry"
                return install_result
            
            # Check if already installed
            if action_id in self.installed_actions:
                install_result['error'] = f"Action {action_id} is already installed"
                return install_result
            
            metadata_dict = self.registry_data['actions'][action_id]
            metadata = ActionMetadata(**metadata_dict)
            
            # Download and install action
            download_result = await self._download_action(action_id, metadata)
            
            if not download_result['success']:
                install_result['error'] = download_result['error']
                return install_result
            
            # Add to installed actions
            self.installed_actions[action_id] = {
                'metadata': metadata_dict,
                'installed_at': install_result['installed_at'],
                'installation_path': download_result['installation_path']
            }
            
            self._save_installed_actions()
            
            # Record in memory
            await self.memory.record_event(
                event_type=MemoryEventType.SYSTEM_EVENT,
                content=f"Installed marketplace action: {metadata.name}",
                metadata={
                    'action_id': action_id,
                    'action_name': metadata.name,
                    'category': metadata.category.value,
                    'author': metadata.author
                }
            )
            
            install_result['success'] = True
            self.logger.info(f"Successfully installed action: {action_id}")
            
        except Exception as e:
            install_result['error'] = str(e)
            self.logger.error(f"Action installation failed: {e}")
        
        return install_result
    
    async def _download_action(self, action_id: str, metadata: ActionMetadata) -> Dict[str, Any]:
        """
        Download action code and install it.
        
        Args:
            action_id: Action identifier
            metadata: Action metadata
            
        Returns:
            Download result
        """
        result = {
            'success': False,
            'installation_path': None,
            'error': None
        }
        
        try:
            # Create action directory
            action_dir = self.actions_dir / action_id
            action_dir.mkdir(exist_ok=True)
            
            # For now, create placeholder action (would download from actual marketplace)
            action_code = self._generate_placeholder_action(metadata)
            
            action_file = action_dir / 'action.py'
            action_file.write_text(action_code)
            
            # Save metadata
            metadata_file = action_dir / 'metadata.json'
            metadata_file.write_text(json.dumps(asdict(metadata), indent=2, default=str))
            
            result['success'] = True
            result['installation_path'] = str(action_dir)
            
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def get_installed_actions(self) -> List[ActionMetadata]:
        """
        Get list of installed actions.
        
        Returns:
            List of installed action metadata
        """
        installed = []
        
        for action_id, install_info in self.installed_actions.items():
            try:
                metadata = ActionMetadata(**install_info['metadata'])
                installed.append(metadata)
            except Exception as e:
                self.logger.warning(f"Invalid installed action metadata for {action_id}: {e}")
        
        return installed
    
    def uninstall_action(self, action_id: str) -> Dict[str, Any]:
        """
        Uninstall an action.
        
        Args:
            action_id: Action identifier
            
        Returns:
            Uninstallation result
        """
        result = {
            'success': False,
            'action_id': action_id,
            'error': None
        }
        
        try:
            if action_id not in self.installed_actions:
                result['error'] = f"Action {action_id} is not installed"
                return result
            
            # Remove action files
            action_dir = self.actions_dir / action_id
            if action_dir.exists():
                shutil.rmtree(action_dir)
            
            # Remove from installed actions
            del self.installed_actions[action_id]
            self._save_installed_actions()
            
            result['success'] = True
            self.logger.info(f"Uninstalled action: {action_id}")
            
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"Action uninstallation failed: {e}")
        
        return result
    
    def _load_registry(self) -> Dict[str, Any]:
        """Load registry data from file."""
        if self.metadata_file.exists():
            try:
                return json.loads(self.metadata_file.read_text())
            except Exception:
                pass
        
        # Return default registry with sample actions
        return self._create_default_registry()
    
    def _load_installed_actions(self) -> Dict[str, Any]:
        """Load installed actions data."""
        if self.installed_file.exists():
            try:
                return json.loads(self.installed_file.read_text())
            except Exception:
                pass
        
        return {}
    
    def _save_installed_actions(self):
        """Save installed actions data."""
        self.installed_file.write_text(json.dumps(self.installed_actions, indent=2))
    
    def _create_default_registry(self) -> Dict[str, Any]:
        """Create default registry with sample actions."""
        default_actions = {
            "optimize_images": {
                "action_id": "optimize_images",
                "name": "Image Optimizer",
                "version": "1.0.0",
                "description": "Optimize images in the project for web usage",
                "category": "optimization",
                "author": "Navi Team",
                "permissions": ["filesystem_read", "filesystem_write"],
                "dependencies": ["Pillow"],
                "parameters": {
                    "quality": {"type": "int", "default": 85, "min": 1, "max": 100},
                    "max_width": {"type": "int", "default": 1920},
                    "formats": {"type": "list", "default": [".jpg", ".png", ".webp"]}
                },
                "examples": [
                    {
                        "description": "Optimize all images to 85% quality",
                        "parameters": {"quality": 85}
                    }
                ],
                "install_size_bytes": 2048000,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "downloads": 1250,
                "rating": 4.8,
                "verified": True
            },
            "generate_tests": {
                "action_id": "generate_tests",
                "name": "Test Generator",
                "version": "1.2.0",
                "description": "Generate comprehensive unit tests for your code",
                "category": "testing",
                "author": "Navi Team",
                "permissions": ["filesystem_read", "filesystem_write"],
                "dependencies": ["ast"],
                "parameters": {
                    "test_framework": {"type": "string", "default": "pytest", "options": ["pytest", "unittest"]},
                    "coverage_target": {"type": "int", "default": 90, "min": 50, "max": 100}
                },
                "examples": [
                    {
                        "description": "Generate pytest tests with 90% coverage",
                        "parameters": {"test_framework": "pytest", "coverage_target": 90}
                    }
                ],
                "install_size_bytes": 1024000,
                "created_at": "2024-01-15T00:00:00Z",
                "updated_at": "2024-02-01T00:00:00Z",
                "downloads": 890,
                "rating": 4.6,
                "verified": True
            },
            "deploy_aws": {
                "action_id": "deploy_aws",
                "name": "AWS Deployer",
                "version": "2.0.0", 
                "description": "Deploy applications to AWS with best practices",
                "category": "deployment",
                "author": "CloudOps Team",
                "permissions": ["filesystem_read", "network_access", "subprocess_execution", "environment_variables"],
                "dependencies": ["boto3", "aws-cli"],
                "parameters": {
                    "region": {"type": "string", "default": "us-east-1"},
                    "service_type": {"type": "string", "options": ["lambda", "ecs", "ec2"]},
                    "auto_scaling": {"type": "boolean", "default": True}
                },
                "examples": [
                    {
                        "description": "Deploy to Lambda with auto-scaling",
                        "parameters": {"service_type": "lambda", "auto_scaling": True}
                    }
                ],
                "install_size_bytes": 5120000,
                "created_at": "2024-02-01T00:00:00Z",
                "updated_at": "2024-02-15T00:00:00Z",
                "downloads": 2100,
                "rating": 4.9,
                "verified": True
            }
        }
        
        registry = {
            'version': '1.0.0',
            'updated_at': datetime.utcnow().isoformat(),
            'actions': default_actions
        }
        
        # Save default registry
        self.metadata_file.write_text(json.dumps(registry, indent=2))
        
        return registry
    
    def _generate_placeholder_action(self, metadata: ActionMetadata) -> str:
        """Generate placeholder action code."""
        return f'''"""
{metadata.name} - {metadata.description}
Auto-generated action for Navi Marketplace
"""

def main():
    """Main action execution function."""
    print(f"Executing {metadata.name}")
    print(f"Parameters: {{PARAMETERS}}")
    print(f"Context: {{CONTEXT}}")
    
    # Placeholder implementation
    print("Action executed successfully!")
    
    return {{
        "status": "success",
        "message": "Action completed",
        "results": {{}}
    }}

if __name__ == "__main__":
    result = main()
    print(f"Result: {{result}}")
'''

class ActionMarketplace:
    """
    Main marketplace interface combining registry, sandbox, and execution.
    """
    
    def __init__(self, workspace_root: str, registry_path: Optional[str] = None):
        self.workspace_root = Path(workspace_root)
        self.registry_path = registry_path or str(self.workspace_root / '.navi_marketplace')
        
        # Initialize components
        self.registry = ActionRegistry(self.registry_path)
        self.sandbox = ActionSandbox(str(self.workspace_root))
        self.memory = EpisodicMemory()
        self.logger = logging.getLogger(__name__)
    
    async def execute_action(self, 
                           action_id: str,
                           parameters: Dict[str, Any],
                           context: Optional[Dict[str, Any]] = None) -> ActionResult:
        """
        Execute an installed marketplace action.
        
        Args:
            action_id: Action identifier
            parameters: Action parameters
            context: Execution context
            
        Returns:
            Action execution result
        """
        # Check if action is installed
        if action_id not in self.registry.installed_actions:
            return ActionResult(
                success=False,
                output=None,
                logs=[],
                errors=[f"Action {action_id} is not installed"],
                execution_time_seconds=0.0,
                resources_used={},
                metadata={}
            )
        
        try:
            # Get action metadata and code
            install_info = self.registry.installed_actions[action_id]
            metadata = ActionMetadata(**install_info['metadata'])
            
            action_file = Path(install_info['installation_path']) / 'action.py'
            action_code = action_file.read_text()
            
            # Prepare context
            execution_context = context or {}
            execution_context.update({
                'workspace_root': str(self.workspace_root),
                'action_id': action_id,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Execute in sandbox
            result = await self.sandbox.execute_action(
                action_code, metadata, parameters, execution_context
            )
            
            # Record execution in memory
            await self.memory.record_event(
                event_type=MemoryEventType.SYSTEM_EVENT,
                content=f"Executed marketplace action: {metadata.name}",
                metadata={
                    'action_id': action_id,
                    'success': result.success,
                    'execution_time': result.execution_time_seconds,
                    'parameters': parameters
                }
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Action execution failed: {e}")
            return ActionResult(
                success=False,
                output=None,
                logs=[],
                errors=[f"Execution failed: {str(e)}"],
                execution_time_seconds=0.0,
                resources_used={},
                metadata={}
            )
    
    def list_categories(self) -> List[Dict[str, Any]]:
        """
        List all available action categories.
        
        Returns:
            List of category information
        """
        categories = []
        
        for category in ActionCategory:
            # Count actions in category
            count = len([
                action for action in self.registry.registry_data.get('actions', {}).values()
                if action.get('category') == category.value
            ])
            
            categories.append({
                'category': category.value,
                'name': category.value.replace('_', ' ').title(),
                'action_count': count
            })
        
        return categories
    
    async def recommend_actions(self, workspace_analysis: Dict[str, Any]) -> List[ActionMetadata]:
        """
        Recommend actions based on workspace analysis.
        
        Args:
            workspace_analysis: Analysis of the current workspace
            
        Returns:
            List of recommended action metadata
        """
        recommendations = []
        
        # Simple recommendation logic based on workspace characteristics
        if workspace_analysis.get('has_images'):
            image_optimizer = self.registry.search_actions("optimize images")
            recommendations.extend(image_optimizer)
        
        if workspace_analysis.get('lacks_tests'):
            test_generator = self.registry.search_actions("generate tests")
            recommendations.extend(test_generator)
        
        if workspace_analysis.get('deployment_ready'):
            deployers = self.registry.search_actions("deploy", ActionCategory.DEPLOYMENT)
            recommendations.extend(deployers)
        
        # Remove duplicates and limit
        seen_ids = set()
        unique_recommendations = []
        
        for action in recommendations:
            if action.action_id not in seen_ids:
                seen_ids.add(action.action_id)
                unique_recommendations.append(action)
        
        return unique_recommendations[:5]
