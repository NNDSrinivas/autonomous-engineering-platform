import difflib
import uuid
from typing import List, Dict, Any


class DiffMetadataBuilder:
    """Builds structured patch metadata for the Cursor-grade diff viewer."""

    def build(
        self, base_lines: List[str], target_lines: List[str], file_path: str
    ) -> Dict[str, Any]:
        """Build structured diff metadata from base and target file content.

        Args:
            base_lines: Original file lines
            target_lines: Modified file lines
            file_path: Path to the file being diffed

        Returns:
            Structured diff metadata with hunks and line information
        """
        diff = list(difflib.unified_diff(base_lines, target_lines, lineterm=""))

        hunks = []
        current_hunk = None

        for line in diff:
            if line.startswith("@@"):
                # Save previous hunk if exists
                if current_hunk:
                    hunks.append(current_hunk)

                # Start new hunk
                current_hunk = {
                    "id": f"hunk_{uuid.uuid4().hex}",
                    "header": line,
                    "lines": [],
                    "explainable": True,
                    "canAutoApply": True,
                }
            else:
                # Add line to current hunk
                if current_hunk:
                    line_type = "context"
                    if line.startswith("+"):
                        line_type = "added"
                    elif line.startswith("-"):
                        line_type = "removed"

                    current_hunk["lines"].append({"type": line_type, "content": line})

        # Don't forget the last hunk
        if current_hunk:
            hunks.append(current_hunk)

        return {"path": file_path, "hunks": hunks}

    def build_from_patch(self, patch_content: str, file_path: str) -> Dict[str, Any]:
        """Build metadata from existing unified diff patch content.

        Args:
            patch_content: Unified diff patch string
            file_path: Path to the file being patched

        Returns:
            Structured diff metadata
        """
        lines = patch_content.strip().split("\n")
        hunks = []
        current_hunk = None

        for line in lines:
            if line.startswith("@@"):
                # Save previous hunk
                if current_hunk:
                    hunks.append(current_hunk)

                # Start new hunk
                current_hunk = {
                    "id": f"hunk_{uuid.uuid4().hex}",
                    "header": line,
                    "lines": [],
                    "explainable": True,
                    "canAutoApply": self._assess_auto_apply_safety(line),
                }
            elif current_hunk:  # Skip file headers (---, +++)
                line_type = "context"
                if line.startswith("+"):
                    line_type = "added"
                elif line.startswith("-"):
                    line_type = "removed"
                elif line.startswith(" "):
                    line_type = "context"
                else:
                    continue  # Skip other lines

                current_hunk["lines"].append({"type": line_type, "content": line})

        # Add final hunk
        if current_hunk:
            hunks.append(current_hunk)

        return {"path": file_path, "hunks": hunks}

    def _assess_auto_apply_safety(self, hunk_header: str) -> bool:
        """Assess if a hunk is safe for auto-application.

        Args:
            hunk_header: The @@ hunk header line

        Returns:
            True if safe for auto-apply, False otherwise
        """
        # Simple heuristic: small hunks are generally safer
        # Extract line count from header like @@ -1,4 +1,6 @@
        try:
            parts = hunk_header.split()
            if len(parts) >= 3:
                # Parse added lines count
                added_part = parts[2]  # +1,6
                if "," in added_part:
                    added_count = int(added_part.split(",")[1])
                    # Auto-apply if adding <= 10 lines
                    return added_count <= 10
        except (ValueError, IndexError):
            pass

        # Default to safe
        return True

    def build_multi_file_metadata(
        self, file_diffs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build metadata for multiple files.

        Args:
            file_diffs: List of file diff data with 'path', 'base_lines', 'target_lines'

        Returns:
            Multi-file diff metadata
        """
        files = []

        for file_diff in file_diffs:
            file_metadata = self.build(
                file_diff["base_lines"], file_diff["target_lines"], file_diff["path"]
            )
            files.append(file_metadata)

        return {
            "files": files,
            "total_hunks": sum(len(f["hunks"]) for f in files),
            "total_files": len(files),
        }
