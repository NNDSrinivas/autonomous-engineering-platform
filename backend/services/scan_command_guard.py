# backend/services/scan_command_guard.py

from __future__ import annotations

import os
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


# COPILOT FIX: Include || operator for bash fallback chains (cmd1 || cmd2)
# Pattern order matters: \|\| must come before \| to match two-char operator first
# Match background operator & (but not &&) regardless of following whitespace
_PIPE_CHAIN_RE = re.compile(r"\|\||\||&&|;|&(?!&)|`|\$\(|>|<|\bxargs\b|-exec\b")


def split_command(cmd: str) -> Optional[List[str]]:
    """
    Tokenize command with shlex, with conservative fallback on parse error.

    COPILOT FIX: Returning None on parse error is fail-open for scan detection.
    Instead, fall back to simple whitespace split to maintain fail-closed posture.

    We try to use shlex for accurate shell-like tokenization. If shlex raises
    ValueError (e.g., due to malformed quoting), we fall back to a simple
    whitespace-based split. This ensures that scan detection still has tokens
    to inspect and does not silently treat parse errors as "not a scan",
    maintaining a fail-closed posture for scan-specific safeguards.
    """
    try:
        return shlex.split(cmd)
    except ValueError:
        # Best-effort fallback: basic whitespace split. This may be less precise
        # than shlex, but it preserves the ability to recognize scan tools like
        # find/grep/rg in the first token and apply appropriate safeguards.
        fallback_tokens = cmd.strip().split()
        if not fallback_tokens:
            return None
        return fallback_tokens


def is_piped_or_chained(cmd: str) -> bool:
    """Detect pipes, chains, backgrounding, xargs, exec, redirection, subshell."""
    return bool(_PIPE_CHAIN_RE.search(cmd))


def _extract_grep_positionals(tokens: List[str]) -> List[str]:
    """
    Extract positional arguments from grep command, skipping option values.

    COPILOT FIX: grep -R TODO --exclude-dir node_modules incorrectly treats
    'node_modules' as search path. Must skip option values like --exclude-dir.

    grep options that take values:
    - Long options with =: --exclude=*.log (single token)
    - Long options with space: --exclude *.log (two tokens)
    - Short options: -A 5, -m 10
    """
    # Options that take a value as the next token
    # Based on GNU grep and BSD grep common options
    # IMPORTANT: Keep this list up-to-date with new grep options to avoid
    # false negatives (unbounded scans being allowed due to misidentified paths)
    opts_with_values = {
        "-e",
        "--regexp",
        "-f",
        "--file",
        "--include",
        "--exclude",
        "--include-dir",
        "--exclude-dir",
        "-A",
        "-B",
        "-C",  # context lines
        "--after-context",
        "--before-context",
        "--context",
        "-m",
        "--max-count",
        "--label",
        "-d",
        "--directories",
        "-D",
        "--devices",
        "--color",
        "--colour",  # color output control (always, never, auto)
        "--binary-files",  # binary file handling (binary, text, without-match)
    }

    positionals = []
    skip_next = False

    for i, tok in enumerate(tokens[1:], start=1):  # Skip command name (grep)
        if skip_next:
            skip_next = False
            continue

        if tok.startswith("-"):
            # Check if it's an option that takes a value
            # Handle both --option=value and --option value
            if "=" in tok:
                continue  # --exclude=*.log is a single token
            if tok in opts_with_values:
                skip_next = True  # Skip next token (the value)
            continue

        # Non-flag, non-skipped token is a positional
        positionals.append(tok)

    return positionals


def _extract_rg_positionals(tokens: List[str]) -> List[str]:
    """
    Extract positional arguments from rg command, skipping option values.

    P1 FIX #2: rg --max-count 10 TODO should extract ["TODO"], not ["10", "TODO"]

    rg options that take values:
    - Long options with =: --max-count=10 (single token)
    - Long options with space: --max-count 10 (two tokens)
    - Short options: -A 5, -m 10, -g '*.py'
    """
    # Options that take a value as the next token
    # Best-effort list covering common ripgrep options (ripgrep 13+)
    # IMPORTANT: Keep this list up-to-date with new rg options to avoid
    # false negatives (unbounded scans being allowed due to misidentified paths)
    opts_with_values = {
        "--max-count",
        "-m",
        "--max-depth",
        "--type",
        "-t",
        "--type-not",
        "-T",
        "--glob",
        "-g",
        "--iglob",
        "-A",
        "-B",
        "-C",  # context lines
        "--after-context",
        "--before-context",
        "--context",
        "-f",
        "--file",
        "-e",
        "--regexp",
        "--encoding",
        "--max-filesize",
        "--path-separator",
        "--color",
        "--colour",  # color output control (always, never, auto)
        "-j",
        "--threads",  # thread count
        "--sort",  # sort results (path, modified, accessed, created)
        "--sortr",  # reverse sort
        "-M",
        "--max-columns",  # max columns per line
        "--max-columns-preview",  # preview for long lines
    }

    positionals = []
    skip_next = False

    for i, tok in enumerate(tokens[1:], start=1):  # Skip command name (rg)
        if skip_next:
            skip_next = False
            continue

        if tok.startswith("-"):
            # Check if it's an option that takes a value
            # Handle both --option=value and --option value
            if "=" in tok:
                continue  # --max-count=10 is a single token
            if tok in opts_with_values:
                skip_next = True  # Skip next token (the value)
            continue

        # Non-flag, non-skipped token is a positional
        positionals.append(tok)

    return positionals


def _is_scoped_path(path: str) -> bool:
    """
    Return True if the user is clearly scoping to a subdir (safer).
    Examples treated as scoped:
      ./src, ../backend, backend/, src/components, src, backend
    Not scoped:
      . , .. , $PWD , ${PWD}, absolute paths (/, /usr), home paths (~, ~/dir)
    """
    if path in [".", "..", "$PWD", "${PWD}", '"$PWD"', "'$PWD'"]:
        return False
    # Reject absolute paths and home expansions (unbounded)
    if path.startswith(("/", "~")):
        return False

    # Normalize path to detect hidden parent directory escapes
    # Examples: ./.., src/../../etc (but ../backend is OK per docstring)
    normalized = os.path.normpath(path)
    # Reject if path doesn't start with ../ but normalizes to parent escape
    # (e.g., ./.., src/../../etc) OR if it becomes absolute
    if not path.startswith("../") and (
        normalized.startswith("..") or os.path.isabs(normalized)
    ):
        return False

    if path.startswith(("./", "../")) and len(path) > 2:
        return True
    if "/" in path and not path.startswith("."):
        return True
    # P1 FIX: Treat plain directory names (src, backend, etc.) as scoped, but
    # require at least two characters to avoid surprising behavior for
    # single-character tokens like "a" or "1" that may be user mistakes.
    # Avoid treating shell constructs (globs, vars, home shortcuts), shell
    # metacharacters (parentheses, pipes, redirections, etc.), or flags
    # (e.g., "-name", "-type") as directory names.
    if (
        path
        and len(path) > 1
        and not path.startswith("-")
        and not re.search(r"[*?\[\]{}`$~()<>;&|]", path)
    ):
        return True
    return False


def normalize_find_name_to_substring(pattern: str) -> str:
    """
    Normalize find -name/-iname pattern to substring for search_files.

    CRITICAL: Do NOT strip leading dots (".py" must stay ".py", not become "py").

    FIX #7: Extract longest literal segment for patterns like test_*.py
    - test_*.py → test_ (prefix match)
    - *.py → .py (suffix match, keep leading dot)
    - *foo* → foo (substring match)
    """
    pat = (pattern or "").strip().strip("'\"")
    has_wildcards = ("*" in pat) or ("?" in pat)

    if not has_wildcards:
        return pat  # exact filename intent (e.g., "Button.tsx")

    # Split by wildcards and find longest literal segment
    # For test_*.py, segments are ["test_", "", ".py"]
    # We want the longest meaningful segment
    segments = re.split(r"[*?]+", pat)
    segments = [s for s in segments if s]  # Remove empty strings

    if not segments:
        return ""  # Pattern was all wildcards

    # Find longest segment (most specific)
    longest = max(segments, key=len)

    # IMPORTANT: Preserve leading dots if present in any segment
    # For *.py, segments = [".py"], longest = ".py" (correct)
    # For test_*.py, segments = ["test_", ".py"], longest = "test_" (good prefix)
    # For *test*.py, segments = ["test", ".py"], longest could be either

    return longest


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
        # Determine the search root, accounting for global options before the path.
        # POSIX find allows -H, -L, -P before any path operands.
        # GNU find also supports -O (optimization), -D (debug), -- (end of options)
        search_root = "."
        idx = 1
        global_opts_with_values = {"-O", "-D"}
        while idx < len(tokens):
            tok = tokens[idx]
            if tok in ("-H", "-L", "-P", "--"):
                idx += 1
            elif tok in global_opts_with_values:
                idx += 2  # Skip option and its value
            elif tok.startswith(("-O", "-D")):
                # Handle combined form like -O3 or -Dhelp
                idx += 1
            else:
                break
        if idx < len(tokens) and not tokens[idx].startswith("-"):
            search_root = tokens[idx]

        if search_root in [".", "$PWD", "${PWD}", '"$PWD"', "'$PWD'"]:
            search_root = "."

        # If explicitly scoped or bounded by an upper depth limit, treat as safe (pass-through)
        if _is_scoped_path(search_root):
            return None
        if "-maxdepth" in tokens:
            return None

        # COPILOT FIX: Hard-block compound expressions and semantic-changing predicates
        # Expanded to include -not, -path, -prune, -a/-and, ) to prevent semantic violations
        # Example: find . -not -path '*/node_modules/*' -name '*.py' should NOT be rewritten
        if any(
            tok in tokens
            for tok in [
                "-o",
                "-or",  # OR operator
                "!",
                "-not",  # NOT operator
                "(",
                ")",  # Grouping
                "-a",
                "-and",  # AND operator (explicit)
                "-path",  # Path matching (can exclude subtrees)
                "-prune",  # Prune directories (changes traversal)
            ]
        ):
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
            # Guard against malformed commands (e.g., "find . -name" with missing pattern).
            # If pattern is None, we fall through to return can_rewrite=False below.
            pattern = tokens[idx + 1] if idx + 1 < len(tokens) else None
            if pattern:
                return ScanCommandInfo(
                    tool="find",
                    raw=cmd,
                    tokens=tokens,
                    reason="Unbounded find from repo root",
                    can_rewrite=True,
                    rewrite_kind="filename_search",
                    extracted_pattern=pattern.strip("\"'"),
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
        # Check for recursive flag: -r, -R, --recursive, or combined like -rl, -Rn
        def _has_recursive_flag(tokens: List[str]) -> bool:
            for tok in tokens:
                if tok == "--recursive":
                    return True
                if tok.startswith("-") and not tok.startswith("--"):
                    if "r" in tok or "R" in tok:
                        return True
            return False

        if not _has_recursive_flag(tokens):
            return None

        # COPILOT FIX: Use proper positional extraction to avoid option value bypass
        # grep -R TODO --exclude-dir node_modules should NOT treat node_modules as path
        # grep syntax: grep [OPTIONS] PATTERN [FILE...]
        # - If pattern from -e/--regexp or -f/--file: all positionals are paths
        # - Otherwise: first positional is PATTERN, rest are FILE path(s)
        positionals = _extract_grep_positionals(tokens)

        # Check if pattern comes from -e/--regexp or -f/--file
        pattern_from_option = any(
            tok in tokens for tok in ["-e", "--regexp", "-f", "--file"]
        )

        # Determine if path is provided
        # - If pattern from option: any positionals are paths
        # - Otherwise: need 2+ positionals (first is pattern, rest are paths)
        has_explicit_path = (
            len(positionals) >= 1
            if pattern_from_option
            else len(positionals) >= 2
        )

        # No path provided -> defaults to "."
        if not has_explicit_path:
            return ScanCommandInfo(
                tool="grep",
                raw=cmd,
                tokens=tokens,
                reason="Recursive grep without explicit path defaults to root (content search)",
                can_rewrite=False,
                rewrite_kind="blocked",
            )

        # Determine which positionals are path operands:
        # - If pattern comes from an option: all positionals are paths.
        # - Otherwise: first positional is the pattern, remaining are paths.
        if pattern_from_option:
            path_operands = positionals
        else:
            path_operands = positionals[1:]

        # Validate all explicit path operands:
        # - If any is ".", this is effectively a repo-root recursive scan -> block.
        # - If any is not a scoped path, treat scope as ambiguous -> block.
        for path in path_operands:
            if path == ".":
                return ScanCommandInfo(
                    tool="grep",
                    raw=cmd,
                    tokens=tokens,
                    reason="Recursive grep from repo root is a content search (not filename search)",
                    can_rewrite=False,
                    rewrite_kind="blocked",
                )
            if not _is_scoped_path(path):
                return ScanCommandInfo(
                    tool="grep",
                    raw=cmd,
                    tokens=tokens,
                    reason="Recursive grep with ambiguous scope",
                    can_rewrite=False,
                    rewrite_kind="blocked",
                )

        # All explicit paths are scoped -> allow
        return None

    # -------------------------
    # rg scans
    # -------------------------
    if tool_cmd == "rg":
        # If user adds bounds, allow
        has_bounds = any(
            tok in tokens
            for tok in ["--glob", "-g", "--iglob", "--type", "-t", "--type-add"]
        )
        if has_bounds:
            return None

        # COPILOT FIX: Handle -e/--regexp pattern form
        # rg -e TODO src should NOT be blocked (pattern from -e, path is src)
        # If pattern comes from -e/--regexp/-f/--file, ALL positionals are paths
        pattern_from_option = any(
            tok in tokens for tok in ["-e", "--regexp", "-f", "--file"]
        )

        # P1 FIX #2: Use proper positional extraction (skip option values)
        positionals = _extract_rg_positionals(tokens)

        # Determine which positionals are paths based on where the pattern comes from.
        if pattern_from_option:
            # Pattern comes from -e/--regexp/-f/--file -> all positionals are paths.
            paths = positionals
        else:
            # Positional pattern: first positional is pattern, second+ are paths.
            # If there is only one positional, then there are no explicit paths.
            paths = positionals[1:] if len(positionals) > 1 else []

        # When PATH arguments are present, evaluate all of them:
        # if any is "."/empty/unscoped, treat as an unbounded scan and block.
        if paths:
            if all(
                (path not in [".", ""]) and _is_scoped_path(path) for path in paths
            ):
                return None  # all paths are scoped

        # No explicit path or at least one unscoped/root path -> unbounded root scan
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
            return {
                "use_discovery": False,
                "alternative": "Use search_files with a filename pattern.",
            }

        normalized = normalize_find_name_to_substring(info.extracted_pattern)

        # Safety: too broad after normalization.
        # PRODUCTION RULE: min_len=3 to avoid "py", "js" substring blasts,
        # but allow 2-char patterns if they start with "." (e.g., ".py", ".ts", ".go").
        # Single-char extensions like ".c" or ".r" are also allowed.
        MIN_PATTERN_LEN = 3
        ALLOW_LEN2_IF_LEADING_DOT = True
        # Explicit whitelist of common single-char extensions
        SINGLE_CHAR_EXTENSIONS = {".c", ".h", ".r", ".m", ".d", ".v"}

        if len(normalized) < MIN_PATTERN_LEN:
            # Exception 1: 2-char patterns starting with "." (e.g., .py, .ts, .go)
            # Rationale: file extensions are highly discriminative
            if (
                len(normalized) == 2
                and ALLOW_LEN2_IF_LEADING_DOT
                and normalized.startswith(".")
            ):
                pass  # Allow .py, .ts, .go, etc.
            # Exception 2: single-char from whitelisted extensions (e.g., .c, .r, .h)
            # Rationale: common in systems programming (C, R, Objective-C, Verilog)
            elif len(normalized) == 1 and f".{normalized}" in SINGLE_CHAR_EXTENSIONS:
                pass  # Allow .c → c, .r → r, .h → h
            # Exception 3: single-char IF original pattern was a dot-extension
            # Catches edge cases not in whitelist but clearly extension-based
            elif len(normalized) == 1:
                is_single_char_extension = (
                    info.extracted_pattern is not None
                    and re.match(r"^\.\w$", info.extracted_pattern.strip()) is not None
                )
                if is_single_char_extension:
                    pass  # Allow non-whitelisted dot-extensions (.e, .o, etc.)
                else:
                    return {
                        "use_discovery": False,
                        "reason": f"Pattern '{info.extracted_pattern}' normalizes to '{normalized}' which is too broad (min {MIN_PATTERN_LEN}, except dot-extensions)",
                        "alternative": "Use a more specific pattern (e.g., '.py', 'Dockerfile', 'Button.tsx').",
                    }
            else:
                # Patterns with len < 3 that don't meet exceptions
                return {
                    "use_discovery": False,
                    "reason": f"Pattern '{info.extracted_pattern}' normalizes to '{normalized}' which is too broad (min {MIN_PATTERN_LEN}, except dot-extensions)",
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
            "reason_code": "SCAN_BLOCKED_CONTENT_SEARCH",  # Machine-readable code
            "workflow_suggestion": (
                "grep -R searches FILE CONTENT, not filenames. Safer workflow:\n"
                "1) search_files to narrow candidate files by name/extension\n"
                "2) read_file on candidates\n"
                "3) (future) add a budgeted search_content tool for ripgrep"
            ),
            "suggested_next_tool": "search_files",
            "alternative_commands": [
                "# First find files by extension:",
                "search_files --pattern .py",
                "# Then read candidates:",
                "read_file path/to/candidate.py",
            ],
        }

    if info.tool == "rg":
        # COPILOT FIX: Extract pattern properly from positionals or -e flag
        # info.tokens[1] could be a flag, not the pattern
        pattern = "PATTERN"

        # Check if pattern comes from -e/--regexp
        for i, tok in enumerate(info.tokens):
            if tok in ["-e", "--regexp"] and i + 1 < len(info.tokens):
                pattern = info.tokens[i + 1]
                break

        # Otherwise, pattern is first positional
        if pattern == "PATTERN":
            positionals = _extract_rg_positionals(info.tokens)
            if positionals:
                pattern = positionals[0]

        # If extraction failed entirely, fall back to a clear placeholder
        if pattern == "PATTERN":
            pattern = "<search-pattern>"

        return {
            "use_discovery": False,
            "reason_code": "SCAN_BLOCKED_UNBOUNDED_RG",  # Machine-readable code
            "alternative": f"rg {pattern!r} src -g'*.{{ts,tsx,js,py,go}}' --max-count 100",
            "workflow_suggestion": (
                "rg searches FILE CONTENT. Either:\n"
                "1) Add bounds: --glob/-g or --type/-t and explicit path\n"
                "2) Use search_files for filename search, then read_file for content"
            ),
            "suggested_next_tool": "search_files",
            "alternative_commands": [
                "# Bounded rg with glob and path:",
                f"rg {pattern!r} src/ -g'*.py' --max-count 100",
                "# Or use type filter:",
                f"rg {pattern!r} backend/ --type python --max-count 100",
            ],
        }

    # Fallback for blocked find commands (compound expressions, -type f without -name, etc.)
    return {
        "use_discovery": False,
        "reason_code": "SCAN_BLOCKED_UNREWRITEABLE_FIND",
        "workflow_suggestion": (
            "This scan command cannot be safely rewritten. Instead of running an "
            "unbounded or complex `find` over the repository, use:\n"
            "1) search_files with a filename pattern to locate relevant files\n"
            "2) list_directory to inspect directory contents if you just need a listing\n"
            "3) read_file on specific files you want to inspect"
        ),
        "suggested_next_tool": "search_files",
        "alternative_commands": [
            "# Example: search for Python files by name:",
            "search_files --pattern '*.py'",
            "# Example: list the contents of a directory:",
            "list_directory --path .",
        ],
    }


def should_allow_scan_for_context(context: Any, info: ScanCommandInfo) -> bool:
    """
    Fail-closed allow policy. Scan commands are allowed only if ALL conditions met:
      1) User explicitly asked to scan entire repo/codebase, AND
      2) The command is bounded/scoped, AND
      3) A confirmation flag is present on context (to prevent agent self-hanging).

    FIX #5 CLARIFICATION: This policy is intentionally strict to prevent autonomous
    agents from hanging on expensive scans. The confirmation flag (allow_repo_scans)
    must be explicitly set by the UI/consent system when the user confirms they want
    a repo-wide scan. This flag is NOT set by default, making this path rarely reached
    in practice - which is by design for safety.

    In most cases, scans are either:
    - Rewritten to discovery tools (find -name → search_files)
    - Blocked with safe alternatives (grep -R → workflow suggestion)
    - Allowed automatically if scoped (find ./src, grep -R pattern backend/)
    """
    # If your TaskContext differs, adjust these attribute reads accordingly.
    original_request = (getattr(context, "original_request", "") or "").lower()
    iteration = int(getattr(context, "iteration", 0) or 0)

    # Require explicit confirmation flag (recommended for production)
    # Example: context.allow_repo_scans set by UI consent step
    # This flag prevents the agent from autonomously running expensive scans
    confirmed = bool(getattr(context, "allow_repo_scans", False))

    # Block during early discovery iterations (prevent premature expensive scans)
    # Note: iteration 0 is also an early iteration and should be blocked
    if iteration < 3:
        return False

    # Must be explicit user request for repo-wide scan
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

    # Require confirmation for any scan-class command (fail-closed)
    if not confirmed:
        return False

    # Even with explicit + confirmed, require bounds for safety
    if info.tool == "find":
        # bounded by upper depth limit (-maxdepth) or scoped root
        # Note: -mindepth only sets lower bound, doesn't limit scan depth
        if "-maxdepth" in info.tokens:
            return True

        # Extract search root, skipping global options like -H, -L, -P, -O, -D
        # (same logic as is_scan_command to avoid false negatives)
        tokens = info.tokens
        idx = 1
        global_opts_with_values = {"-O", "-D"}
        while idx < len(tokens):
            tok = tokens[idx]
            if tok in ("-H", "-L", "-P", "--"):
                idx += 1
            elif tok in global_opts_with_values:
                idx += 2
            elif tok.startswith(("-O", "-D")):
                idx += 1
            else:
                break
        search_root = tokens[idx] if idx < len(tokens) else "."
        return _is_scoped_path(search_root)

    if info.tool == "rg":
        has_bounds = any(
            tok in info.tokens for tok in ["--glob", "-g", "--iglob", "--type", "-t"]
        )
        if has_bounds:
            return True
        # Use proper positional extraction (skip option values)
        positionals = _extract_rg_positionals(info.tokens)
        if positionals:
            path = positionals[-1] if len(positionals) > 1 else None
            return path and path not in [".", ""] and _is_scoped_path(path)
        return False

    if info.tool == "grep":
        # COPILOT FIX: Use proper positional parsing to avoid misclassifying
        # option values (--exclude-dir node_modules) or PATTERN as PATH
        # Require at least PATTERN + explicit PATH (2+ positionals)
        positionals = _extract_grep_positionals(info.tokens)
        if len(positionals) < 2:
            return False  # No explicit path (defaults to .)
        path = positionals[-1]
        # Do not allow unbounded scans of root
        if not path or path == ".":
            return False
        return _is_scoped_path(path)

    return False
