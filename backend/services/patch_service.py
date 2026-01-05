"""
Patch Service for Execution Agent

Provides async patch application functionality.
"""

import logging
import asyncio
import tempfile
from typing import List, Dict, Any, Optional
import os

logger = logging.getLogger(__name__)


class PatchService:
    """
    Service for applying patches safely to code repositories.
    Wraps the existing PatchRunner functionality for async use.
    """

    def __init__(self):
        """Initialize the patch service."""
        pass

    async def apply_patch(
        self,
        workspace_root: str,
        patch_content: str,
        target_files: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Apply a patch to the workspace.

        Args:
            workspace_root: Root directory of the workspace
            patch_content: The patch content (diff format)
            target_files: Optional list of specific files to target

        Returns:
            Dictionary with success status and details
        """
        try:
            # For now, implement a basic patch application
            # This can be enhanced later with the full PatchRunner integration

            # Run the patch application in a thread pool to avoid blocking
            return await asyncio.get_event_loop().run_in_executor(
                None,
                self._sync_apply_patch,
                workspace_root,
                patch_content,
                target_files,
            )

        except Exception as e:
            logger.error(f"Patch application error: {e}")
            return {
                "success": False,
                "message": f"Patch application failed: {str(e)}",
                "modified_files": [],
            }

    def _sync_apply_patch(
        self,
        workspace_root: str,
        patch_content: str,
        target_files: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Synchronous patch application implementation.

        Args:
            workspace_root: Root directory of the workspace
            patch_content: The patch content (diff format)
            target_files: Optional list of specific files to target

        Returns:
            Dictionary with success status and details
        """
        try:
            # Create a temporary patch file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".patch", delete=False
            ) as patch_file:
                patch_file.write(patch_content)
                patch_file_path = patch_file.name

            try:
                # Change to workspace directory
                original_cwd = os.getcwd()
                os.chdir(workspace_root)

                # Apply patch using git apply (safer than patch command)
                import subprocess

                # First try dry run to check if patch can be applied
                dry_run_result = subprocess.run(
                    ["git", "apply", "--check", patch_file_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if dry_run_result.returncode != 0:
                    return {
                        "success": False,
                        "message": f"Patch dry run failed: {dry_run_result.stderr}",
                        "modified_files": [],
                    }

                # Apply the patch
                apply_result = subprocess.run(
                    ["git", "apply", patch_file_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if apply_result.returncode == 0:
                    # Extract modified files from patch content
                    modified_files = self._extract_modified_files(patch_content)

                    return {
                        "success": True,
                        "message": "Patch applied successfully",
                        "modified_files": modified_files,
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Patch application failed: {apply_result.stderr}",
                        "modified_files": [],
                    }

            finally:
                # Restore original directory
                os.chdir(original_cwd)
                # Clean up temporary patch file
                if os.path.exists(patch_file_path):
                    os.unlink(patch_file_path)

        except Exception as e:
            logger.error(f"Sync patch application error: {e}")
            return {
                "success": False,
                "message": f"Patch application exception: {str(e)}",
                "modified_files": [],
            }

    def _extract_modified_files(self, patch_content: str) -> List[str]:
        """
        Extract the list of modified files from patch content.

        Args:
            patch_content: The patch content in diff format

        Returns:
            List of file paths that would be modified
        """
        modified_files = []

        lines = patch_content.split("\n")
        for line in lines:
            # Look for diff headers that indicate file paths
            if line.startswith("diff --git"):
                # Extract file path from "diff --git a/path b/path"
                parts = line.split(" ")
                if len(parts) >= 4:
                    file_path = parts[3][2:]  # Remove "b/" prefix
                    modified_files.append(file_path)
            elif line.startswith("+++"):
                # Alternative: extract from "+++ b/path"
                if line.startswith("+++ b/"):
                    file_path = line[6:]  # Remove "+++ b/" prefix
                    if file_path not in modified_files:
                        modified_files.append(file_path)

        return modified_files
