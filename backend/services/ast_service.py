"""
AST Service for Execution Agent

Provides async AST-based refactoring operations for Python files.
This is a basic implementation that can be enhanced later with full AST manipulation.
"""

import logging
import asyncio
import os
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class ASTService:
    """
    Service for AST-based code refactoring operations.
    Provides methods for safe code transformations.
    """
    
    def __init__(self):
        """Initialize the AST service."""
        pass
    
    async def extract_method(
        self, 
        file_path: str, 
        method_name: str, 
        start_line: int, 
        end_line: int
    ) -> Dict[str, Any]:
        """
        Extract code lines into a new method.
        
        Args:
            file_path: Path to the Python file
            method_name: Name for the new method
            start_line: Starting line number (1-based)
            end_line: Ending line number (1-based)
            
        Returns:
            Dictionary with success status and details
        """
        try:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._sync_extract_method, file_path, method_name, start_line, end_line
            )
        except Exception as e:
            logger.error(f"Extract method error: {e}")
            return {
                'success': False,
                'message': f'Extract method failed: {str(e)}'
            }
    
    async def rename_variable(
        self, 
        file_path: str, 
        old_name: str, 
        new_name: str
    ) -> Dict[str, Any]:
        """
        Rename a variable throughout the file.
        
        Args:
            file_path: Path to the Python file
            old_name: Current variable name
            new_name: New variable name
            
        Returns:
            Dictionary with success status and details
        """
        try:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._sync_rename_variable, file_path, old_name, new_name
            )
        except Exception as e:
            logger.error(f"Rename variable error: {e}")
            return {
                'success': False,
                'message': f'Rename variable failed: {str(e)}'
            }
    
    async def move_class(
        self, 
        source_file: str, 
        target_file: str, 
        class_name: str
    ) -> Dict[str, Any]:
        """
        Move a class from one file to another.
        
        Args:
            source_file: Source file path
            target_file: Target file path
            class_name: Name of the class to move
            
        Returns:
            Dictionary with success status and details
        """
        try:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._sync_move_class, source_file, target_file, class_name
            )
        except Exception as e:
            logger.error(f"Move class error: {e}")
            return {
                'success': False,
                'message': f'Move class failed: {str(e)}'
            }
    
    async def add_imports(
        self, 
        file_path: str, 
        imports: List[str]
    ) -> Dict[str, Any]:
        """
        Add import statements to a file.
        
        Args:
            file_path: Path to the Python file
            imports: List of import statements to add
            
        Returns:
            Dictionary with success status and details
        """
        try:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._sync_add_imports, file_path, imports
            )
        except Exception as e:
            logger.error(f"Add imports error: {e}")
            return {
                'success': False,
                'message': f'Add imports failed: {str(e)}'
            }
    
    def _sync_extract_method(
        self, 
        file_path: str, 
        method_name: str, 
        start_line: int, 
        end_line: int
    ) -> Dict[str, Any]:
        """
        Synchronous extract method implementation.
        This is a basic implementation - can be enhanced with full AST manipulation.
        """
        try:
            if not os.path.exists(file_path):
                return {
                    'success': False,
                    'message': f'File not found: {file_path}'
                }
            
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            # Basic validation
            if start_line < 1 or end_line > len(lines) or start_line > end_line:
                return {
                    'success': False,
                    'message': f'Invalid line range: {start_line}-{end_line}'
                }
            
            # For now, just log what would be extracted
            extracted_code = ''.join(lines[start_line-1:end_line])
            logger.info(f"Would extract method '{method_name}' from lines {start_line}-{end_line}")
            logger.debug(f"Extracted code:\n{extracted_code}")
            
            return {
                'success': True,
                'message': f'Method extraction simulated for {method_name}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Extract method exception: {str(e)}'
            }
    
    def _sync_rename_variable(self, file_path: str, old_name: str, new_name: str) -> Dict[str, Any]:
        """
        Synchronous rename variable implementation.
        This is a basic implementation - can be enhanced with full AST analysis.
        """
        try:
            if not os.path.exists(file_path):
                return {
                    'success': False,
                    'message': f'File not found: {file_path}'
                }
            
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Simple text replacement (should be enhanced with AST analysis)
            import re
            
            # Replace whole word occurrences only
            pattern = r'\b' + re.escape(old_name) + r'\b'
            new_content = re.sub(pattern, new_name, content)
            
            if content != new_content:
                with open(file_path, 'w') as f:
                    f.write(new_content)
                
                return {
                    'success': True,
                    'message': f'Renamed variable {old_name} to {new_name}'
                }
            else:
                return {
                    'success': False,
                    'message': f'Variable {old_name} not found in {file_path}'
                }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Rename variable exception: {str(e)}'
            }
    
    def _sync_move_class(self, source_file: str, target_file: str, class_name: str) -> Dict[str, Any]:
        """
        Synchronous move class implementation.
        This is a basic implementation - can be enhanced with full AST manipulation.
        """
        try:
            if not os.path.exists(source_file):
                return {
                    'success': False,
                    'message': f'Source file not found: {source_file}'
                }
            
            # For now, just log what would be moved
            logger.info(f"Would move class '{class_name}' from {source_file} to {target_file}")
            
            return {
                'success': True,
                'message': f'Class move simulated for {class_name}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Move class exception: {str(e)}'
            }
    
    def _sync_add_imports(self, file_path: str, imports: List[str]) -> Dict[str, Any]:
        """
        Synchronous add imports implementation.
        """
        try:
            if not os.path.exists(file_path):
                return {
                    'success': False,
                    'message': f'File not found: {file_path}'
                }
            
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            # Find the position to insert imports (after existing imports)
            insert_pos = 0
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith('import ') or stripped.startswith('from '):
                    insert_pos = i + 1
                elif stripped and not stripped.startswith('#'):
                    break
            
            # Add imports that don't already exist
            new_imports = []
            for import_stmt in imports:
                # Check if import already exists
                import_line = import_stmt if import_stmt.endswith('\n') else import_stmt + '\n'
                if import_line not in lines:
                    new_imports.append(import_line)
            
            if new_imports:
                # Insert new imports
                lines[insert_pos:insert_pos] = new_imports
                
                with open(file_path, 'w') as f:
                    f.writelines(lines)
                
                return {
                    'success': True,
                    'message': f'Added {len(new_imports)} import(s)'
                }
            else:
                return {
                    'success': True,
                    'message': 'All imports already exist'
                }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Add imports exception: {str(e)}'
            }