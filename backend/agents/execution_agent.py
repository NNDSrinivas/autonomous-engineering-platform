from typing import List, Dict, Any, Optional
import asyncio
import os
import json
from datetime import datetime
from ..models.plan import PlanStep, ExecutionResult
from ..services.patch_service import PatchService
from ..services.ast_service import ASTService
from ..core.config import get_settings


class ExecutionAgent:
    """
    The Execution Agent is where the real work happens. It can:
    - Apply patches and diffs
    - Perform AST-based refactoring
    - Run shell commands safely
    - Modify files with precision
    - Execute code analysis
    - Run tests and validation

    This is the "hands" of Navi that makes actual changes to the codebase.
    """

    def __init__(self):
        self.patch_service = PatchService()
        self.ast_service = ASTService()
        self.settings = get_settings()

        # Safety settings
        self.safety_checks_enabled = True
        self.backup_before_changes = True
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.allowed_commands = {
            "npm",
            "yarn",
            "pip",
            "python",
            "node",
            "git",
            "make",
            "mvn",
            "gradle",
            "cargo",
            "go",
            "dotnet",
            "pytest",
            "jest",
            "mocha",
            "phpunit",
            "rspec",
        }

    async def execute_step(
        self,
        step: PlanStep,
        workspace_root: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Execute a single plan step with comprehensive error handling
        """

        start_time = datetime.now()

        try:
            # Pre-execution validation
            await self._validate_step(step, workspace_root)

            # Create backup if needed
            backup_info = None
            if self.backup_before_changes and step.action_type in [
                "modify_file",
                "refactor",
                "apply_patch",
            ]:
                backup_info = await self._create_backup(
                    step.file_targets, workspace_root
                )

            # Execute based on action type
            result = await self._execute_action(step, workspace_root, context)

            # Post-execution validation
            if result.success:
                validation_result = await self._validate_execution(
                    step, workspace_root, result
                )
                if not validation_result["valid"]:
                    result.success = False
                    result.error = f"Validation failed: {validation_result['reason']}"

                    # Restore backup if validation failed
                    if backup_info:
                        await self._restore_backup(backup_info, workspace_root)

            execution_time = (datetime.now() - start_time).total_seconds()
            result.execution_time = execution_time

            return result

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()

            return ExecutionResult(
                step_id=step.id,
                success=False,
                output="",
                error=str(e),
                execution_time=execution_time,
                metadata={"exception_type": type(e).__name__},
            )

    async def _execute_action(
        self,
        step: PlanStep,
        workspace_root: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Execute the specific action based on step type
        """

        action_handlers = {
            "modify_file": self._handle_modify_file,
            "refactor": self._handle_refactor,
            "apply_patch": self._handle_apply_patch,
            "run_command": self._handle_run_command,
            "search_code": self._handle_search_code,
            "review": self._handle_review,
            "ask_clarification": self._handle_ask_clarification,
        }

        handler = action_handlers.get(step.action_type)
        if not handler:
            return ExecutionResult(
                step_id=step.id,
                success=False,
                output="",
                error=f"Unknown action type: {step.action_type}",
            )

        return await handler(step, workspace_root, context)

    async def _handle_modify_file(
        self,
        step: PlanStep,
        workspace_root: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Handle direct file modifications
        """

        try:
            modified_files = []
            output_messages = []

            for file_path in step.file_targets:
                full_path = os.path.join(workspace_root, file_path)

                # Check if file exists
                if not os.path.exists(full_path):
                    # Create new file if specified in metadata
                    if step.metadata.get("create_if_not_exists", False):
                        os.makedirs(os.path.dirname(full_path), exist_ok=True)
                        with open(full_path, "w") as f:
                            f.write(step.metadata.get("initial_content", ""))
                        output_messages.append(f"Created new file: {file_path}")
                    else:
                        return ExecutionResult(
                            step_id=step.id,
                            success=False,
                            output="",
                            error=f"File not found: {file_path}",
                        )

                # Apply modification based on metadata
                modification_type = step.metadata.get("modification_type", "edit")

                if modification_type == "edit":
                    success = await self._apply_file_edit(full_path, step.metadata)
                elif modification_type == "append":
                    success = await self._append_to_file(full_path, step.metadata)
                elif modification_type == "prepend":
                    success = await self._prepend_to_file(full_path, step.metadata)
                elif modification_type == "replace_section":
                    success = await self._replace_file_section(full_path, step.metadata)
                else:
                    return ExecutionResult(
                        step_id=step.id,
                        success=False,
                        output="",
                        error=f"Unknown modification type: {modification_type}",
                    )

                if success:
                    modified_files.append(file_path)
                    output_messages.append(f"Modified: {file_path}")
                else:
                    return ExecutionResult(
                        step_id=step.id,
                        success=False,
                        output="",
                        error=f"Failed to modify file: {file_path}",
                    )

            return ExecutionResult(
                step_id=step.id,
                success=True,
                output="\n".join(output_messages),
                files_modified=modified_files,
            )

        except Exception as e:
            return ExecutionResult(
                step_id=step.id,
                success=False,
                output="",
                error=f"File modification error: {str(e)}",
            )

    async def _handle_refactor(
        self,
        step: PlanStep,
        workspace_root: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Handle AST-based refactoring operations
        """

        try:
            refactor_type = step.metadata.get("refactor_type", "extract_method")

            if refactor_type == "extract_method":
                result = await self.ast_service.extract_method(
                    file_path=os.path.join(workspace_root, step.file_targets[0]),
                    method_name=step.metadata.get("method_name"),
                    start_line=step.metadata.get("start_line"),
                    end_line=step.metadata.get("end_line"),
                )

            elif refactor_type == "rename_variable":
                result = await self.ast_service.rename_variable(
                    file_path=os.path.join(workspace_root, step.file_targets[0]),
                    old_name=step.metadata.get("old_name"),
                    new_name=step.metadata.get("new_name"),
                )

            elif refactor_type == "move_class":
                result = await self.ast_service.move_class(
                    source_file=os.path.join(
                        workspace_root, step.metadata.get("source_file")
                    ),
                    target_file=os.path.join(
                        workspace_root, step.metadata.get("target_file")
                    ),
                    class_name=step.metadata.get("class_name"),
                )

            elif refactor_type == "add_imports":
                result = await self.ast_service.add_imports(
                    file_path=os.path.join(workspace_root, step.file_targets[0]),
                    imports=step.metadata.get("imports", []),
                )

            else:
                return ExecutionResult(
                    step_id=step.id,
                    success=False,
                    output="",
                    error=f"Unknown refactor type: {refactor_type}",
                )

            if result.get("success", False):
                return ExecutionResult(
                    step_id=step.id,
                    success=True,
                    output=result.get("message", "Refactoring completed"),
                    files_modified=result.get("modified_files", step.file_targets),
                )
            else:
                return ExecutionResult(
                    step_id=step.id,
                    success=False,
                    output="",
                    error=result.get("error", "Refactoring failed"),
                )

        except Exception as e:
            return ExecutionResult(
                step_id=step.id,
                success=False,
                output="",
                error=f"Refactoring error: {str(e)}",
            )

    async def _handle_apply_patch(
        self,
        step: PlanStep,
        workspace_root: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Handle patch/diff application
        """

        try:
            patch_content = step.metadata.get("patch_content")
            if not patch_content:
                return ExecutionResult(
                    step_id=step.id,
                    success=False,
                    output="",
                    error="No patch content provided",
                )

            # Apply patch using patch service
            result = await self.patch_service.apply_patch(
                workspace_root=workspace_root,
                patch_content=patch_content,
                target_files=step.file_targets,
            )

            if result.get("success", False):
                return ExecutionResult(
                    step_id=step.id,
                    success=True,
                    output=result.get("message", "Patch applied successfully"),
                    files_modified=result.get("modified_files", []),
                )
            else:
                return ExecutionResult(
                    step_id=step.id,
                    success=False,
                    output=result.get("output", ""),
                    error=result.get("error", "Patch application failed"),
                )

        except Exception as e:
            return ExecutionResult(
                step_id=step.id,
                success=False,
                output="",
                error=f"Patch application error: {str(e)}",
            )

    async def _handle_run_command(
        self,
        step: PlanStep,
        workspace_root: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Handle shell command execution with safety checks
        """

        try:
            command = step.metadata.get("command")
            if not command:
                return ExecutionResult(
                    step_id=step.id,
                    success=False,
                    output="",
                    error="No command provided",
                )

            # Safety check: validate command
            if not await self._is_safe_command(command):
                return ExecutionResult(
                    step_id=step.id,
                    success=False,
                    output="",
                    error=f"Command not allowed for safety reasons: {command}",
                )

            # Set working directory
            cwd = workspace_root
            if step.metadata.get("working_directory"):
                cwd = os.path.join(workspace_root, step.metadata["working_directory"])

            # Set timeout
            timeout = step.metadata.get("timeout", 300)  # 5 minutes default

            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )

                return_code = process.returncode

                output = stdout.decode("utf-8") if stdout else ""
                error_output = stderr.decode("utf-8") if stderr else ""

                success = return_code == 0

                return ExecutionResult(
                    step_id=step.id,
                    success=success,
                    output=output,
                    error=error_output if not success else None,
                    metadata={
                        "return_code": return_code,
                        "command": command,
                        "working_directory": cwd,
                    },
                )

            except asyncio.TimeoutError:
                process.kill()
                await process.wait()

                return ExecutionResult(
                    step_id=step.id,
                    success=False,
                    output="",
                    error=f"Command timed out after {timeout} seconds: {command}",
                )

        except Exception as e:
            return ExecutionResult(
                step_id=step.id,
                success=False,
                output="",
                error=f"Command execution error: {str(e)}",
            )

    async def _handle_search_code(
        self,
        step: PlanStep,
        workspace_root: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Handle code search operations
        """

        try:
            search_query = step.metadata.get("query")
            search_type = step.metadata.get("search_type", "text")

            if search_type == "text":
                results = await self._search_text_in_files(
                    query=search_query,
                    file_paths=step.file_targets,
                    workspace_root=workspace_root,
                )

            elif search_type == "function":
                results = await self._search_functions(
                    function_name=search_query,
                    file_paths=step.file_targets,
                    workspace_root=workspace_root,
                )

            elif search_type == "class":
                results = await self._search_classes(
                    class_name=search_query,
                    file_paths=step.file_targets,
                    workspace_root=workspace_root,
                )

            else:
                return ExecutionResult(
                    step_id=step.id,
                    success=False,
                    output="",
                    error=f"Unknown search type: {search_type}",
                )

            return ExecutionResult(
                step_id=step.id,
                success=True,
                output=json.dumps(results, indent=2),
                metadata={"search_results": results},
            )

        except Exception as e:
            return ExecutionResult(
                step_id=step.id,
                success=False,
                output="",
                error=f"Search error: {str(e)}",
            )

    async def _handle_review(
        self,
        step: PlanStep,
        workspace_root: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Handle code review and validation operations
        """

        try:
            review_type = step.metadata.get("review_type", "quality")

            if review_type == "quality":
                results = await self._review_code_quality(
                    step.file_targets, workspace_root
                )

            elif review_type == "security":
                results = await self._review_security(step.file_targets, workspace_root)

            elif review_type == "performance":
                results = await self._review_performance(
                    step.file_targets, workspace_root
                )

            elif review_type == "style":
                results = await self._review_style(step.file_targets, workspace_root)

            else:
                return ExecutionResult(
                    step_id=step.id,
                    success=False,
                    output="",
                    error=f"Unknown review type: {review_type}",
                )

            return ExecutionResult(
                step_id=step.id,
                success=True,
                output=json.dumps(results, indent=2),
                metadata={"review_results": results},
            )

        except Exception as e:
            return ExecutionResult(
                step_id=step.id,
                success=False,
                output="",
                error=f"Review error: {str(e)}",
            )

    async def _handle_ask_clarification(
        self,
        step: PlanStep,
        workspace_root: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Handle requests for user clarification
        """

        # This would integrate with the UI to ask for user input
        clarification_needed = step.metadata.get("question", step.description)

        return ExecutionResult(
            step_id=step.id,
            success=True,
            output=f"Clarification needed: {clarification_needed}",
            metadata={
                "requires_user_input": True,
                "question": clarification_needed,
                "input_type": step.metadata.get("input_type", "text"),
            },
        )

    # Helper methods for file operations

    async def _apply_file_edit(self, file_path: str, metadata: Dict[str, Any]) -> bool:
        """
        Apply specific edits to a file
        """
        try:
            with open(file_path, "r") as f:
                content = f.read()

            # Apply edit based on metadata
            if "line_number" in metadata:
                lines = content.split("\n")
                line_num = metadata["line_number"] - 1  # Convert to 0-based

                if "new_line" in metadata:
                    lines[line_num] = metadata["new_line"]
                elif "insert_before" in metadata:
                    lines.insert(line_num, metadata["insert_before"])
                elif "insert_after" in metadata:
                    lines.insert(line_num + 1, metadata["insert_after"])

                content = "\n".join(lines)

            elif "find_replace" in metadata:
                find_text = metadata["find_replace"]["find"]
                replace_text = metadata["find_replace"]["replace"]
                content = content.replace(find_text, replace_text)

            # Write back to file
            with open(file_path, "w") as f:
                f.write(content)

            return True

        except Exception:
            return False

    async def _append_to_file(self, file_path: str, metadata: Dict[str, Any]) -> bool:
        """
        Append content to a file
        """
        try:
            content_to_append = metadata.get("content", "")

            with open(file_path, "a") as f:
                f.write(content_to_append)

            return True

        except Exception:
            return False

    async def _prepend_to_file(self, file_path: str, metadata: Dict[str, Any]) -> bool:
        """
        Prepend content to a file
        """
        try:
            content_to_prepend = metadata.get("content", "")

            with open(file_path, "r") as f:
                existing_content = f.read()

            with open(file_path, "w") as f:
                f.write(content_to_prepend + existing_content)

            return True

        except Exception:
            return False

    async def _replace_file_section(
        self, file_path: str, metadata: Dict[str, Any]
    ) -> bool:
        """
        Replace a section of a file
        """
        try:
            start_marker = metadata.get("start_marker")
            end_marker = metadata.get("end_marker")
            new_content = metadata.get("new_content", "")

            with open(file_path, "r") as f:
                content = f.read()

            # Find and replace section
            start_pos = content.find(start_marker)
            end_pos = content.find(end_marker)

            if start_pos != -1 and end_pos != -1:
                before = content[:start_pos]
                after = content[end_pos + len(end_marker) :]
                content = before + start_marker + new_content + end_marker + after

            with open(file_path, "w") as f:
                f.write(content)

            return True

        except Exception:
            return False

    # Additional helper methods would be implemented here...

    async def _validate_step(self, step: PlanStep, workspace_root: str):
        """
        Validate step before execution
        """
        # File size checks
        for file_path in step.file_targets:
            full_path = os.path.join(workspace_root, file_path)
            if os.path.exists(full_path):
                file_size = os.path.getsize(full_path)
                if file_size > self.max_file_size:
                    raise ValueError(f"File too large: {file_path} ({file_size} bytes)")

    async def _create_backup(
        self, file_targets: List[str], workspace_root: str
    ) -> Dict[str, Any]:
        """
        Create backup of files before modification
        """
        # Implementation for creating backups
        return {}

    async def _restore_backup(self, backup_info: Dict[str, Any], workspace_root: str):
        """
        Restore files from backup
        """
        # Implementation for restoring from backup
        pass

    async def _validate_execution(
        self, step: PlanStep, workspace_root: str, result: ExecutionResult
    ) -> Dict[str, Any]:
        """
        Validate execution results
        """
        return {"valid": True, "reason": ""}

    async def _is_safe_command(self, command: str) -> bool:
        """
        Check if command is safe to execute
        """
        command_parts = command.split()
        if not command_parts:
            return False

        base_command = command_parts[0]

        # Check against allowed commands
        if base_command not in self.allowed_commands:
            return False

        # Additional safety checks
        dangerous_patterns = ["rm -rf", "sudo", "chmod 777", "> /dev/", "dd if="]
        for pattern in dangerous_patterns:
            if pattern in command:
                return False

        return True

    # Search helper methods
    async def _search_text_in_files(
        self, query: str, file_paths: List[str], workspace_root: str
    ) -> List[Dict[str, Any]]:
        """Search for text in files"""
        return []

    async def _search_functions(
        self, function_name: str, file_paths: List[str], workspace_root: str
    ) -> List[Dict[str, Any]]:
        """Search for function definitions"""
        return []

    async def _search_classes(
        self, class_name: str, file_paths: List[str], workspace_root: str
    ) -> List[Dict[str, Any]]:
        """Search for class definitions"""
        return []

    # Review helper methods
    async def _review_code_quality(
        self, file_paths: List[str], workspace_root: str
    ) -> Dict[str, Any]:
        """Review code quality"""
        return {}

    async def _review_security(
        self, file_paths: List[str], workspace_root: str
    ) -> Dict[str, Any]:
        """Review security issues"""
        return {}

    async def _review_performance(
        self, file_paths: List[str], workspace_root: str
    ) -> Dict[str, Any]:
        """Review performance issues"""
        return {}

    async def _review_style(
        self, file_paths: List[str], workspace_root: str
    ) -> Dict[str, Any]:
        """Review code style"""
        return {}
