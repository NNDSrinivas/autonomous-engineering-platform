# backend/services/scan_command_guard.py

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import List, Optional, Literal, Dict, Any


ScanTool = Literal["find", "grep", "rg"]


@dataclass(frozen=True)
class ScanCommandInfo:
    """Info about detected scan command."""
    tool: ScanTool
    raw: str
    tokens: List[str]
    reason: str
    can_rewrite: bool
    rewrite_kind: Literal["filename_search", "blocked"]
    extracted_pattern: Optional[str] = None  # Only for find -name/-iname


_PIPE_CHAIN_RE = re.compile(r"\||&&|;|&\s*$|&\s+|`|\$\(|>|<|\bxargs\b|-exec\b")
# Used only to split out the "first command" in a pipeline/chain for detection.
_SPLIT_CHAIN_RE = re.compile(r"\||&&|;|&\s*$|&\s+|\bxargs\b")


def split_command(cmd: str) -> Optional[List[str]]:
    """Tokenize command with shlex (fail closed if parse error)."""
    try:
        return shlex.split(cmd)
    except ValueError:
        return None


def is_piped_or_chained(cmd: str) -> bool:
    """Detect pipes, chains, backgrounding, xargs, exec, redirection, subshell."""
    return bool(_PIPE_CHAIN_RE.search(cmd))


def _is_scoped_path(path: str) -> bool:
    """
    Return True if the user is clearly scoping to a subdir (safer).
    Examples treated as scoped:
      ./src, ../backend, backend/, src/components
    Not scoped:
      . , $PWD , ${PWD}
    """
    if path in [".", "$PWD", "${PWD}", '"$PWD"', "'$PWD'"]:
        return False
    if path.startswith(("./", "../")) and len(path) > 2:
        return True
    if "/" in path and not path.startswith("."):
        return True
    return False


def normalize_find_name_to_substring(pattern: str) -> str:
    """
    Normalize find -name/-iname pattern to substring for search_files.

    CRITICAL: Do NOT strip leading dots (".py" must stay ".py", not become "py").
    """
    pat = (pattern or "").strip().strip("'\"")
    has_wildcards = ("*" in pat) or ("?" in pat)

    if not has_wildcards:
        return pat  # exact filename intent (e.g., "Button.tsx")

    # substring semantics: remove wildcards but keep everything else
    s = pat.replace("*", "").replace("?", "").strip()

    # IMPORTANT: do NOT strip leading dots
    return s


def is_scan_command(cmd: str) -> Optional[ScanCommandInfo]:
    """
    Token-aware detection: fail closed if tokenization fails.

    Returns ScanCommandInfo only for unbounded *root* scans.
    """
    tokens = split_command(cmd)
    if not tokens:
        # Fail closed: if parse fails, we do NOT attempt to classify it as scan here.
        # (The existing dangerous-command system should still handle it.)
        return None

    tool_cmd = tokens[0]

    # -------------------------
    # find scans
    # -------------------------
    if tool_cmd == "find":
        search_root = tokens[1] if len(tokens) > 1 else "."
        if search_root in [".", "$PWD", "${PWD}", '"$PWD"', "'$PWD'"]:
            search_root = "."

        # If explicitly scoped or bounded by depth, treat as safe (pass-through)
        if _is_scoped_path(search_root):
            return None
        if "-maxdepth" in tokens or "-mindepth" in tokens:
            return None

        # Hard-block compound expressions
        if any(tok in tokens for tok in ["-o", "-or", "!", "("]):
            return ScanCommandInfo(
                tool="find",
                raw=cmd,
                tokens=tokens,
                reason="Compound find expression cannot be rewritten safely",
                can_rewrite=False,
                rewrite_kind="blocked",
            )

        # Only rewrite if there is exactly one -name/-iname
        name_flags = [i for i, tok in enumerate(tokens) if tok in ["-name", "-iname"]]
        if len(name_flags) > 1:
            return ScanCommandInfo(
                tool="find",
                raw=cmd,
                tokens=tokens,
                reason="Multiple -name/-iname patterns cannot be rewritten safely",
                can_rewrite=False,
                rewrite_kind="blocked",
            )

        if len(name_flags) == 1:
            idx = name_flags[0]
            pattern = tokens[idx + 1] if idx + 1 < len(tokens) else None
            if pattern:
                return ScanCommandInfo(
                    tool="find",
                    raw=cmd,
                    tokens=tokens,
                    reason="Unbounded find from repo root",
                    can_rewrite=True,
                    rewrite_kind="filename_search",
                    extracted_pattern=pattern.strip('"\''),
                )

        # find from root without -name/-iname (e.g., find . -type f)
        return ScanCommandInfo(
            tool="find",
            raw=cmd,
            tokens=tokens,
            reason="Unbounded find from repo root without -name/-iname",
            can_rewrite=False,
            rewrite_kind="blocked",
        )

    # -------------------------
    # grep scans
    # -------------------------
    if tool_cmd in ["grep", "egrep"]:
        if not any(tok in tokens for tok in ["-r", "-R", "--recursive"]):
            return None

        # If user provides an explicit scoped dir (not ".") treat as pass-through
        # Example: grep -R TODO backend/
        for tok in reversed(tokens):
            if tok.startswith("-"):
                continue
            if tok == ".":
                break
            # last non-flag argument might be a path; if it's scoped, allow
            if _is_scoped_path(tok):
                return None

        # Root scan
        if "." in tokens:
            return ScanCommandInfo(
                tool="grep",
                raw=cmd,
                tokens=tokens,
                reason="Recursive grep from repo root is a content search (not filename search)",
                can_rewrite=False,
                rewrite_kind="blocked",
            )
        return None

    # -------------------------
    # rg scans
    # -------------------------
    if tool_cmd == "rg":
        # If user adds bounds, allow
        has_bounds = any(tok in tokens for tok in ["--glob", "-g", "--iglob", "--type", "-t", "--type-add"])
        if has_bounds:
            return None

        # If user provides explicit non-root path, allow
        # (ripgrep: first positional is pattern, second+ are paths)
        positionals = [tok for tok in tokens[1:] if not tok.startswith("-")]
        if len(positionals) > 1:
            # Multiple positionals: pattern + path(s)
            # Check if path is explicit (not root)
            path = positionals[-1]
            if path not in [".", ""]:
                return None  # scoped path

        # No explicit path or path is root -> unbounded root scan
        return ScanCommandInfo(
            tool="rg",
            raw=cmd,
            tokens=tokens,
            reason="Unbounded ripgrep from repo root is a content search and can be very slow",
            can_rewrite=False,
            rewrite_kind="blocked",
        )

    return None


def rewrite_to_discovery(info: ScanCommandInfo) -> Dict[str, Any]:
    """
    Rewrite ONLY if semantics are preserved (filename → filename).

    Uses existing readonly discovery tool search_files (filename substring matching).
    """
    if info.tool == "find" and info.can_rewrite:
        if not info.extracted_pattern:
            return {"use_discovery": False, "alternative": "Use search_files with a filename pattern."}

        normalized = normalize_find_name_to_substring(info.extracted_pattern)

        # Safety: too broad after normalization
        if len(normalized) < 2:
            return {
                "use_discovery": False,
                "reason": f"Pattern '{info.extracted_pattern}' normalizes to '{normalized}' which is too broad",
                "alternative": "Use a more specific pattern (e.g., '.py', 'Dockerfile', 'Button.tsx').",
            }

        return {
            "use_discovery": True,
            "tool_name": "search_files",
            "arguments": {"pattern": normalized},
            "explanation": (
                f"Rewrote unbounded find -name '{info.extracted_pattern}' "
                f"to safe filename substring search: '{normalized}'"
            ),
        }

    if info.tool == "grep":
        return {
            "use_discovery": False,
            "workflow_suggestion": (
                "grep -R searches FILE CONTENT, not filenames. Safer workflow:\n"
                "1) search_files to narrow candidate files by name/extension\n"
                "2) read_file on candidates\n"
                "3) (future) add a budgeted search_content tool for ripgrep"
            ),
        }

    if info.tool == "rg":
        # Provide a bounded safe alternative template
        pattern = info.tokens[1] if len(info.tokens) > 1 else "PATTERN"
        return {
            "use_discovery": False,
            "alternative": f"rg {pattern!r} src -g'*.{{ts,tsx,js,py,go}}' --max-count 100",
            "workflow_suggestion": (
                "rg searches FILE CONTENT. Either:\n"
                "1) Add bounds: --glob/-g or --type/-t and explicit path\n"
                "2) Use search_files for filename search, then read_file for content"
            ),
        }

    return {"use_discovery": False}


def should_allow_scan_for_context(context: Any, info: ScanCommandInfo) -> bool:
    """
    Fail-closed allow policy. Scan commands are allowed only if:
      1) User explicitly asked to scan entire repo/codebase, AND
      2) The command is bounded/scoped, AND
      3) A confirmation flag is present on context (to prevent agent self-hanging).
    """
    # If your TaskContext differs, adjust these attribute reads accordingly.
    original_request = (getattr(context, "original_request", "") or "").lower()
    iteration = int(getattr(context, "iteration", 0) or 0)

    # Optional: require explicit confirmation flag (recommended)
    # Example: context.allow_unbounded_scans set by UI consent step
    confirmed = bool(getattr(context, "allow_repo_scans", False))

    # Block during early discovery iterations
    if iteration and iteration < 3:
        return False

    # Must be explicit
    explicit = any(
        phrase in original_request
        for phrase in [
            "search entire codebase",
            "search all files",
            "scan the repository",
            "scan the repo",
            "scan entire repo",
            "entire repository",
            "entire codebase",
        ]
    )
    if not explicit:
        return False

    # Require confirmation for any scan-class command
    if not confirmed:
        return False

    # Even with explicit + confirmed, require bounds
    if info.tool == "find":
        # bounded by -maxdepth/-mindepth or scoped root
        if "-maxdepth" in info.tokens or "-mindepth" in info.tokens:
            return True
        search_root = info.tokens[1] if len(info.tokens) > 1 else "."
        return _is_scoped_path(search_root)

    if info.tool == "rg":
        has_bounds = any(tok in info.tokens for tok in ["--glob", "-g", "--iglob", "--type", "-t"])
        if has_bounds:
            return True
        positionals = [tok for tok in info.tokens[1:] if not tok.startswith("-")]
        return bool(positionals and positionals[-1] not in [".", ""])

    if info.tool == "grep":
        # recursive grep allowed only if path scoped (not ".")
        for tok in reversed(info.tokens):
            if tok.startswith("-"):
                continue
            if tok == ".":
                return False
            return _is_scoped_path(tok)

    return False
