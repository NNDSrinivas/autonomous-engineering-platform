# backend/services/git_service.py
import subprocess
import os
from pathlib import Path
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class GitService:
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        if not self._is_git_repo():
            raise ValueError(f"Path {repo_path} is not a Git repository")

    def _is_git_repo(self) -> bool:
        """Check if the path is a valid Git repository"""
        try:
            self._run(["git", "rev-parse", "--git-dir"], check_errors=False)
            return True
        except:
            return False

    def _run(self, cmd: List[str], check_errors: bool = True) -> str:
        """Run git command and return stdout"""
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30
            )
            if check_errors and result.returncode != 0:
                logger.error(f"Git command failed: {' '.join(cmd)}, stderr: {result.stderr}")
                raise RuntimeError(f"Git command failed: {result.stderr}")
            return result.stdout
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Git command timed out: {' '.join(cmd)}")

    def has_head(self) -> bool:
        """
        Check whether the repository has at least one commit (HEAD exists).
        """
        try:
            output = self._run(["git", "rev-parse", "--verify", "HEAD"], check_errors=False)
            return bool(output.strip())
        except Exception:
            return False

    def execute_safe_command(self, command: List[str], description: str = "") -> Dict[str, Any]:
        """Execute a git command with safety checks"""
        try:
            # Safety check - only allow safe git commands
            if not command or command[0] != "git":
                return {"success": False, "error": "Not a git command"}
            
            # Whitelist of safe git commands
            safe_commands = {
                "status", "log", "diff", "show", "branch", "remote", 
                "add", "commit", "push", "pull", "fetch", "checkout",
                "merge", "rebase", "stash", "reset", "clean"
            }
            
            if len(command) < 2 or command[1] not in safe_commands:
                return {"success": False, "error": f"Command '{command[1]}' not allowed"}
            
            # Block dangerous operations
            dangerous_patterns = ["--force", "-f", "--hard", "rm", "clean -fd"]
            command_str = " ".join(command)
            for pattern in dangerous_patterns:
                if pattern in command_str.lower():
                    return {"success": False, "error": f"Dangerous operation blocked: {pattern}"}
            
            # Execute the command
            logger.info(f"[GIT EXEC] Running: {' '.join(command)}")
            output = self._run(command)
            
            return {
                "success": True,
                "output": output,
                "command": " ".join(command),
                "description": description or f"Execute {command[1]}"
            }
            
        except subprocess.CalledProcessError as e:
            return {
                "success": False,
                "error": f"Command failed: {e.stderr or e.stdout}",
                "exit_code": e.returncode
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_file(self, filepath: str, content: str) -> Dict[str, Any]:
        """Create a new file with content"""
        try:
            full_path = os.path.join(self.repo_root, filepath)
            
            # Create directory if needed
            dir_path = os.path.dirname(full_path)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
            
            # Create the file
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                "success": True,
                "message": f"Created file: {filepath}",
                "path": filepath
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def edit_file(self, filepath: str, new_content: str) -> Dict[str, Any]:
        """Edit an existing file"""
        try:
            full_path = os.path.join(self.repo_root, filepath)
            
            # Backup original content
            backup_content = ""
            if os.path.exists(full_path):
                with open(full_path, 'r', encoding='utf-8') as f:
                    backup_content = f.read()
            
            # Write new content
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return {
                "success": True,
                "message": f"Modified file: {filepath}",
                "path": filepath,
                "backup": backup_content
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def delete_file(self, filepath: str) -> Dict[str, Any]:
        """Delete a file"""
        try:
            full_path = os.path.join(self.repo_root, filepath)
            
            if not os.path.exists(full_path):
                return {"success": False, "error": f"File does not exist: {filepath}"}
            
            os.remove(full_path)
            
            return {
                "success": True,
                "message": f"Deleted file: {filepath}",
                "path": filepath
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        """
        Returns staged + unstaged files with their modification status
        """
        try:
            output = self._run(["git", "status", "--porcelain"])
            files = []

            for line in output.splitlines():
                if len(line) < 3:
                    continue
                    
                status = line[:2]
                path = line[3:].strip()
                
                # Skip if path is empty or invalid
                if not path:
                    continue
                    
                files.append({
                    "path": path,
                    "staged": status[0] not in [' ', '?'],
                    "unstaged": status[1] not in [' ', '?'],
                    "status": status,
                    "is_new": status[0] == 'A' or status == '??',
                    "is_deleted": status[0] == 'D' or status[1] == 'D'
                })
            return files
        except Exception as e:
            logger.error(f"Failed to get git status: {e}")
            return []

    def get_diff(self, staged: bool = False) -> str:
        """
        Get full repository diff (staged or unstaged)
        """
        try:
            if staged:
                return self._run(["git", "diff", "--cached", "--unified=3"])
            if self.has_head():
                return self._run(["git", "diff", "HEAD", "--unified=3"])
            return self._run(["git", "diff", "--unified=3"])
        except Exception as e:
            logger.error(f"Failed to get diff: {e}")
            return ""

    def get_file_diff(self, file_path: str, staged: bool = False) -> str:
        """
        Get diff for a specific file
        """
        try:
            cmd = ["git", "diff"]
            if staged:
                cmd.append("--cached")
            else:
                if self.has_head():
                    cmd.append("HEAD")
            cmd.extend(["--unified=3", "--", file_path])
            return self._run(cmd)
        except Exception as e:
            logger.error(f"Failed to get file diff for {file_path}: {e}")
            return ""

    def get_file_content(self, file_path: str) -> str:
        """
        Get current file content from working directory
        """
        try:
            full_path = self.repo_path / file_path
            if not full_path.exists():
                return ""
            # Skip directories
            if full_path.is_dir():
                return ""
            return full_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return ""

    def get_file_content_at_revision(self, revision: str, file_path: str) -> str:
        """
        Get file content at a specific git revision (e.g., HEAD).

        Falls back to empty string if the file does not exist at the revision.
        """
        try:
            result = self._run(
                ["git", "show", f"{revision}:{file_path}"],
                check_errors=False,
            )
            return result
        except Exception as e:
            logger.warning(
                "Failed to read %s at %s: %s", file_path, revision, e, exc_info=False
            )
            return ""

    def get_repo_root(self) -> str:
        """
        Get the root directory of the git repository
        """
        try:
            output = self._run(["git", "rev-parse", "--show-toplevel"])
            return output.strip()
        except Exception as e:
            logger.error(f"Failed to get repo root: {e}")
            return str(self.repo_path)

    def get_current_branch(self) -> str:
        """
        Get current branch name
        """
        try:
            output = self._run(["git", "branch", "--show-current"])
            return output.strip()
        except Exception as e:
            logger.error(f"Failed to get current branch: {e}")
            return "unknown"
