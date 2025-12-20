# backend/services/repo_service.py
from typing import List, Dict, Any, Optional
import os
import logging
from pathlib import Path
from .git_service import GitService

logger = logging.getLogger(__name__)

class RepoService:
    """Service for repository operations combining git and file system access"""
    
    def __init__(self, repo_path: str):
        self.git = GitService(repo_path)
        self.repo_path = repo_path
        self.last_skip_summary: Dict[str, Any] = {}

    def get_working_tree_changes(self, max_files: int | None = None) -> List[Dict[str, Any]]:
        """
        Get all working tree changes with diffs and content
        """
        try:
            files = self.git.get_status()
            total_seen = len(files)
            result = []

            limit = max_files if max_files and max_files > 0 else None
            max_file_bytes = int(os.getenv("NAVI_REVIEW_MAX_FILE_BYTES", "200000"))

            skip_dirs = {
                ".git",
                "node_modules",
                ".next",
                ".turbo",
                "dist",
                "build",
                "coverage",
                ".cache",
                ".vscode",
                "__pycache__",
                ".venv",
                "venv",
            }
            skip_exts = {
                ".png",
                ".jpg",
                ".jpeg",
                ".gif",
                ".ico",
                ".svg",
                ".map",
                ".zip",
                ".tar",
                ".gz",
                ".mp4",
                ".mov",
                ".mp3",
                ".pdf",
            }

            skipped_files: List[str] = []
            skipped_large = 0
            skipped_ignored = 0

            for file_info in files if limit is None else files[:limit]:
                path = file_info["path"]
                
                # Skip directories
                full_path = Path(self.repo_path) / path
                if full_path.exists() and full_path.is_dir():
                    continue

                parts = Path(path).parts
                if any(part in skip_dirs for part in parts):
                    skipped_ignored += 1
                    if len(skipped_files) < 25:
                        skipped_files.append(path)
                    continue

                if full_path.suffix.lower() in skip_exts:
                    skipped_ignored += 1
                    if len(skipped_files) < 25:
                        skipped_files.append(path)
                    continue

                if full_path.exists() and full_path.is_file() and max_file_bytes > 0:
                    try:
                        if full_path.stat().st_size > max_file_bytes:
                            skipped_large += 1
                            if len(skipped_files) < 25:
                                skipped_files.append(path)
                            continue
                    except Exception:
                        # If stat fails, continue with best-effort diff/content
                        pass
                
                # Get the appropriate diff (staged vs unstaged)
                if file_info["staged"]:
                    diff = self.git.get_file_diff(path, staged=True)
                else:
                    diff = self.git.get_file_diff(path, staged=False)
                
                # Get current file content
                content = self.git.get_file_content(path)
                
                # Determine file type for better analysis
                file_ext = path.split('.')[-1] if '.' in path else ''
                
                entry = {
                    "path": path,
                    "staged": file_info["staged"],
                    "unstaged": file_info["unstaged"],
                    "status": file_info["status"],
                    "is_new": file_info["is_new"],
                    "is_deleted": file_info["is_deleted"],
                    "diff": diff,
                    "content": content,
                    "file_type": file_ext,
                    "size": len(content) if content else 0
                }
                
                result.append(entry)
                logger.debug(
                    "Processed file: %s, diff_length: %s, content_length: %s",
                    path,
                    len(diff),
                    len(content),
                )

            skipped_total = skipped_large + skipped_ignored
            skipped_limit = 0
            if limit is not None and total_seen > limit:
                skipped_limit = max(0, total_seen - limit)
            self.last_skip_summary = {
                "total": total_seen,
                "skipped_total": skipped_total,
                "skipped_large": skipped_large,
                "skipped_ignored": skipped_ignored,
                "skipped_limit": skipped_limit,
                "skipped_files": skipped_files,
                "max_file_bytes": max_file_bytes,
            }

            logger.info(f"Found {len(result)} modified files in working tree")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get working tree changes: {e}")
            return []

    def get_repo_info(self) -> Dict[str, Any]:
        """
        Get basic repository information
        """
        try:
            return {
                "root": self.git.get_repo_root(),
                "current_branch": self.git.get_current_branch(),
                "repo_path": self.repo_path
            }
        except Exception as e:
            logger.error(f"Failed to get repo info: {e}")
            return {
                "root": self.repo_path,
                "current_branch": "unknown",
                "repo_path": self.repo_path
            }

    def get_file_analysis_context(self, file_path: str) -> Dict[str, Any]:
        """
        Get context needed for analyzing a specific file
        """
        try:
            return {
                "path": file_path,
                "content": self.git.get_file_content(file_path),
                "diff": self.git.get_file_diff(file_path),
                "staged_diff": self.git.get_file_diff(file_path, staged=True),
                "file_type": file_path.split('.')[-1] if '.' in file_path else 'unknown'
            }
        except Exception as e:
            logger.error(f"Failed to get analysis context for {file_path}: {e}")
            return {
                "path": file_path,
                "content": "",
                "diff": "",
                "staged_diff": "",
                "file_type": "unknown"
            }
