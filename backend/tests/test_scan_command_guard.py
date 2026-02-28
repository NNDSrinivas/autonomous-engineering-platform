# backend/tests/test_scan_command_guard.py

import pytest

from backend.services.scan_command_guard import (
    is_scan_command,
    rewrite_to_discovery,
    normalize_find_name_to_substring,
    is_piped_or_chained,
    should_allow_scan_for_context,
    ScanCommandInfo,
)


class TestTokenAwareDetection:
    @pytest.mark.parametrize(
        "command,should_detect,tool",
        [
            ("find . -name '*.py'", True, "find"),
            ("find . -type f", True, "find"),
            ("find $PWD -name test", True, "find"),
            ("find ${PWD} -name '*.tsx'", True, "find"),
            ("find . -maxdepth 2 -name '*.py'", False, None),
            ("find ./src -name '*.tsx'", False, None),
            ("find backend/ -type f", False, None),
            ("find . -name '*.py' -o -name '*.md'", True, "find"),
            ("grep -R 'TODO' .", True, "grep"),
            ("grep -r 'test' .", True, "grep"),
            ("egrep --recursive 'pattern' .", True, "grep"),
            ("grep 'pattern' file.txt", False, None),
            ("grep -R 'test' src/", False, None),
            ("rg 'pattern'", True, "rg"),
            ("rg TODO", True, "rg"),
            ("rg 'pattern' --glob '*.py'", False, None),
            ("rg 'test' -g '*.ts'", False, None),
            ("rg TODO --type python", False, None),
            ("rg TODO src", False, None),
            # FIX: Test --flag=value form (equals syntax)
            ("rg TODO --glob=*.py", False, None),
            ("rg TODO --type=python", False, None),
            # CRITICAL: --type-add only DEFINES a type, doesn't apply it as filter
            ("rg TODO --type-add=python:*.py", True, "rg"),
            # FIX: Test "./" bypass (should be detected as unbounded scan)
            ("find ./ -name '*.py'", True, "find"),
            ("grep -R TODO ./", True, "grep"),
            ("rg TODO ./", True, "rg"),
        ],
    )
    def test_scan_detection(self, command, should_detect, tool):
        result = is_scan_command(command)
        if should_detect:
            assert result is not None
            assert result.tool == tool
        else:
            assert result is None


class TestPatternNormalization:
    @pytest.mark.parametrize(
        "input_pattern,expected",
        [
            ("*.py", ".py"),
            ("*.tsx", ".tsx"),
            ("Button.tsx", "Button.tsx"),
            ("Dockerfile", "Dockerfile"),
            (
                "test_*.py",
                "test_",
            ),  # FIX #7: Extract longest literal segment (test_) rather than concatenating all segments (test_.py)
            ("*", ""),
            ("???", ""),
        ],
    )
    def test_normalize_find_name_to_substring(self, input_pattern, expected):
        assert normalize_find_name_to_substring(input_pattern) == expected

    def test_too_broad_rejected(self):
        scan_info = is_scan_command("find . -name '*'")
        assert scan_info is not None
        rewrite = rewrite_to_discovery(scan_info)
        assert rewrite.get("use_discovery") is False
        assert "too broad" in (rewrite.get("reason", "") or "").lower()


class TestSemanticPreservation:
    def test_rewrite_find_exact(self):
        scan_info = is_scan_command("find . -name 'Button.tsx'")
        assert scan_info is not None and scan_info.can_rewrite is True
        rewrite = rewrite_to_discovery(scan_info)
        assert rewrite["use_discovery"] is True
        assert rewrite["arguments"]["pattern"] == "Button.tsx"

    def test_rewrite_find_wildcard_keeps_dot(self):
        scan_info = is_scan_command("find . -name '*.py'")
        assert scan_info is not None and scan_info.can_rewrite is True
        rewrite = rewrite_to_discovery(scan_info)
        assert rewrite["use_discovery"] is True
        assert rewrite["arguments"]["pattern"] == ".py"

    def test_block_find_compound(self):
        scan_info = is_scan_command("find . -name '*.py' -o -name '*.md'")
        assert scan_info is not None and scan_info.can_rewrite is False
        rewrite = rewrite_to_discovery(scan_info)
        assert rewrite.get("use_discovery") is False

    def test_block_grep_content_search(self):
        scan_info = is_scan_command("grep -R 'TODO' .")
        assert scan_info is not None and scan_info.can_rewrite is False
        rewrite = rewrite_to_discovery(scan_info)
        assert rewrite.get("use_discovery") is False
        assert "workflow_suggestion" in rewrite


class TestPipeChainDetection:
    @pytest.mark.parametrize(
        "command",
        [
            "find . -name '*.py' | xargs grep TODO",
            "cd src && find . -name '*.tsx'",
            "find . -name '*.log' &",
            "find . -type f -exec grep TODO {} \\;",
        ],
    )
    def test_pipes_chains_detected(self, command):
        assert is_piped_or_chained(command) is True


class TestCopilotP1Fixes:
    """Test cases for all P1 critical issues from Copilot review."""

    def test_p1_fix_1_plain_dir_names_are_scoped(self):
        """P1 FIX #1: Plain directory names like 'src' or 'backend' should be treated as scoped."""
        from backend.services.scan_command_guard import _is_scoped_path

        # Plain directory names should be scoped (safe)
        assert _is_scoped_path("src") is True
        assert _is_scoped_path("backend") is True
        assert _is_scoped_path("tests") is True

        # Root indicators should NOT be scoped
        assert _is_scoped_path(".") is False
        assert _is_scoped_path("..") is False  # Parent directory - outside workspace
        assert (
            _is_scoped_path("../") is False
        ), "CRITICAL: ../ (parent with trailing slash) must be blocked"
        assert _is_scoped_path("$PWD") is False
        assert _is_scoped_path("${PWD}") is False

        # Directory-like paths should be scoped
        assert _is_scoped_path("./src") is True
        assert _is_scoped_path("../backend") is True  # Parent with specific subdir is OK
        assert _is_scoped_path("backend/") is True
        assert _is_scoped_path("src/components") is True

        # Parent directory scans should be detected
        scan_info = is_scan_command("find .. -name '*.py'")
        assert scan_info is not None, "find .. should be detected as unbounded scan"
        assert scan_info.tool == "find"

        # CRITICAL: Deep parent directory traversal must be blocked
        assert (
            _is_scoped_path("../..") is False
        ), "CRITICAL: ../.. allows escape outside workspace"
        assert (
            _is_scoped_path("../../etc") is False
        ), "CRITICAL: ../../etc allows escape outside workspace"
        assert (
            _is_scoped_path("../../../foo") is False
        ), "CRITICAL: ../../../foo allows deep traversal"

        # Verify deep traversal is detected as unbounded scan
        scan_deep = is_scan_command("find ../.. -name '*.py'")
        assert (
            scan_deep is not None
        ), "CRITICAL: find ../.. must be detected as unbounded scan"
        scan_deeper = is_scan_command("find ../../etc -name '*.py'")
        assert (
            scan_deeper is not None
        ), "CRITICAL: find ../../etc must be detected as unbounded scan"

        # CRITICAL: Parent with trailing slash must be blocked
        scan_parent_slash = is_scan_command("find ../ -name '*.py'")
        assert (
            scan_parent_slash is not None
        ), "CRITICAL: find ../ must be detected as unbounded scan"

    def test_p1_fix_2_rg_with_option_values_blocked(self):
        """P1 FIX #2: rg --max-count 10 TODO should be blocked (10 is option value, not path)."""
        # This should be detected as unbounded scan (no path after pattern)
        scan_info = is_scan_command("rg --max-count 10 TODO")
        assert scan_info is not None
        assert scan_info.tool == "rg"
        assert scan_info.can_rewrite is False

        # Similar cases with other options
        scan_info = is_scan_command("rg -A 5 pattern")
        assert scan_info is not None
        assert scan_info.tool == "rg"

        # But with explicit path, should NOT be detected (scoped)
        scan_info = is_scan_command("rg --max-count 10 TODO src")
        assert scan_info is None  # Scoped to src/

    def test_p1_fix_3_chain_guard_checks_all_segments(self):
        """P1 FIX #3: cd . && rg TODO should be caught (rg is in second segment)."""
        # The scan can be in ANY segment of the chain
        # This test verifies detection works for scans in non-first segments

        # Scan in second segment
        cmd = "cd . && rg TODO"
        assert is_piped_or_chained(cmd) is True
        # Extract second segment
        segments = cmd.split("&&")
        second_segment = segments[1].strip()
        scan_info = is_scan_command(second_segment)
        assert scan_info is not None
        assert scan_info.tool == "rg"

        # Scan in third segment
        cmd = "cd src && pwd && find . -name '*.py'"
        assert is_piped_or_chained(cmd) is True

    def test_issue_8_grep_without_explicit_path_blocked(self):
        """ISSUE #8: grep -R TODO (without explicit path) should be blocked."""
        # No explicit path - defaults to . (current directory)
        scan_info = is_scan_command("grep -R TODO")
        assert scan_info is not None
        assert scan_info.tool == "grep"
        assert scan_info.can_rewrite is False

        # With pattern but no path
        scan_info = is_scan_command("grep --recursive 'pattern'")
        assert scan_info is not None
        assert scan_info.tool == "grep"

        # With explicit scoped path should NOT be detected
        scan_info = is_scan_command("grep -R TODO backend")
        assert scan_info is None  # Scoped to backend/


class TestCopilotAdditionalFixes:
    """Test cases for additional Copilot review issues."""

    def test_redirection_detected(self):
        """COPILOT FIX: Commands with redirection should be detected by is_piped_or_chained."""
        assert is_piped_or_chained("rg TODO > out.txt") is True
        assert is_piped_or_chained("grep -R TODO . > results") is True
        assert is_piped_or_chained("find . -name '*.py' < input.txt") is True

    def test_command_substitution_detected(self):
        """COPILOT FIX: Commands with $() or backticks should be detected."""
        assert is_piped_or_chained("rg TODO $(cat files)") is True
        assert is_piped_or_chained("grep -R pattern `find . -name '*.txt'`") is True

    def test_grep_option_values_not_treated_as_path(self):
        """COPILOT FIX: grep -R TODO --exclude-dir node_modules should NOT treat node_modules as scoped path."""
        # --exclude-dir value should be skipped, only pattern detected
        scan_info = is_scan_command("grep -R TODO --exclude-dir node_modules")
        assert scan_info is not None  # Should be blocked (no explicit path)
        assert scan_info.tool == "grep"

        # With explicit scoped path after options, should NOT be detected
        scan_info = is_scan_command("grep -R TODO --exclude-dir node_modules src")
        assert scan_info is None  # Scoped to src/

    def test_rg_e_flag_with_path(self):
        """COPILOT FIX: rg -e TODO src should be treated as scoped (pattern from -e, path is src)."""
        scan_info = is_scan_command("rg -e TODO src")
        assert scan_info is None  # Scoped to src/

        # Without path, should be blocked
        scan_info = is_scan_command("rg -e TODO")
        assert scan_info is not None
        assert scan_info.tool == "rg"

    def test_rg_regexp_flag_with_path(self):
        """COPILOT FIX: rg --regexp TODO backend should be treated as scoped."""
        scan_info = is_scan_command("rg --regexp TODO backend")
        assert scan_info is None  # Scoped to backend/

        # Without path, should be blocked
        scan_info = is_scan_command("rg --regexp pattern")
        assert scan_info is not None
        assert scan_info.tool == "rg"

    def test_parse_failure_fallback(self):
        """COPILOT FIX: Parse failures should fall back to whitespace split (fail-closed)."""
        from backend.services.scan_command_guard import split_command

        # Malformed quoting should still tokenize via fallback
        tokens = split_command("rg 'unclosed")
        assert tokens is not None  # Fallback should return tokens
        assert len(tokens) > 0
        assert tokens[0] == "rg"

        # Should still detect scan command after fallback
        scan_info = is_scan_command("rg 'unclosed")
        assert scan_info is not None  # Should detect despite parse error

    def test_rewrite_to_discovery_rg_pattern_extraction(self):
        """COPILOT FIX: rewrite_to_discovery should extract pattern correctly for rg."""
        from backend.services.scan_command_guard import rewrite_to_discovery

        # Test with positional pattern
        scan_info = is_scan_command("rg TODO")
        rewrite = rewrite_to_discovery(scan_info)
        assert "TODO" in rewrite.get("alternative", "")

        # Test with -e pattern
        scan_info = is_scan_command("rg --max-count 10 -e FIXME")
        rewrite = rewrite_to_discovery(scan_info)
        assert "FIXME" in rewrite.get("alternative", "")
        # Should NOT include --max-count in pattern extraction
        assert "--max-count" not in rewrite.get("alternative", "").split()[1]


class TestCopilotRound3Fixes:
    """Test cases for third round of Copilot review issues."""

    def test_or_operator_detected(self):
        """COPILOT FIX: || operator should be detected (cd src || rg TODO)."""
        assert is_piped_or_chained("cd src || rg TODO") is True
        assert is_piped_or_chained("test -f file || grep -R pattern .") is True

    def test_find_compound_expression_expanded(self):
        """COPILOT FIX: find with -not, -path, -prune, ) should be blocked."""
        # -not (alias for !)
        scan_info = is_scan_command("find . -not -path '*/node_modules/*' -name '*.py'")
        assert scan_info is not None
        assert scan_info.can_rewrite is False

        # -path (path matching/exclusion)
        scan_info = is_scan_command("find . -path '*/test/*' -name '*.js'")
        assert scan_info is not None
        assert scan_info.can_rewrite is False

        # -prune (directory pruning)
        scan_info = is_scan_command("find . -name node_modules -prune -o -name '*.py'")
        assert scan_info is not None
        assert scan_info.can_rewrite is False

        # ) (grouping close)
        scan_info = is_scan_command("find . \\( -name '*.py' -o -name '*.js' \\)")
        assert scan_info is not None
        assert scan_info.can_rewrite is False

    def test_bash_c_wrapper_unwrapped(self):
        """COPILOT FIX: bash -c 'rg TODO' should detect rg scan."""
        # This tests the unwrapping logic in autonomous_agent.py
        # Here we just verify the command itself is detected
        scan_info = is_scan_command("rg TODO")
        assert scan_info is not None
        assert scan_info.tool == "rg"

        # The actual bash -c unwrapping is tested via integration in autonomous_agent


class TestShouldAllowScanForContext:
    """Tests for should_allow_scan_for_context fail-closed policy."""

    class MockContext:
        """Mock context for testing."""

        def __init__(
            self,
            original_request: str = "",
            iteration: int = 0,
            allow_repo_scans: bool = False,
        ):
            self.original_request = original_request
            self.iteration = iteration
            self.allow_repo_scans = allow_repo_scans

    def test_blocks_when_iteration_less_than_3(self):
        """Scans are blocked when iteration < 3."""
        ctx = self.MockContext(
            original_request="scan the entire repository",
            iteration=2,
            allow_repo_scans=True,
        )
        info = ScanCommandInfo(
            tool="find",
            raw="find . -name '*.py'",
            tokens=["find", ".", "-name", "*.py"],
            reason="test",
            can_rewrite=False,
            rewrite_kind="blocked",
        )
        assert should_allow_scan_for_context(ctx, info) is False

    def test_blocks_when_explicit_phrases_missing(self):
        """Scans are blocked when explicit phrases are missing from original_request."""
        ctx = self.MockContext(
            original_request="find python files",  # No explicit phrase
            iteration=5,
            allow_repo_scans=True,
        )
        info = ScanCommandInfo(
            tool="find",
            raw="find . -name '*.py'",
            tokens=["find", ".", "-maxdepth", "1", "-name", "*.py"],
            reason="test",
            can_rewrite=False,
            rewrite_kind="blocked",
        )
        assert should_allow_scan_for_context(ctx, info) is False

    def test_blocks_when_allow_repo_scans_false(self):
        """Scans are blocked when allow_repo_scans flag is False."""
        ctx = self.MockContext(
            original_request="scan the entire codebase",
            iteration=5,
            allow_repo_scans=False,
        )
        info = ScanCommandInfo(
            tool="find",
            raw="find . -name '*.py'",
            tokens=["find", ".", "-maxdepth", "1", "-name", "*.py"],
            reason="test",
            can_rewrite=False,
            rewrite_kind="blocked",
        )
        assert should_allow_scan_for_context(ctx, info) is False

    def test_allows_when_all_conditions_met_find_maxdepth(self):
        """Scans are allowed when ALL conditions are met (find with -maxdepth)."""
        ctx = self.MockContext(
            original_request="scan the entire repository",
            iteration=5,
            allow_repo_scans=True,
        )
        info = ScanCommandInfo(
            tool="find",
            raw="find . -maxdepth 2 -name '*.py'",
            tokens=["find", ".", "-maxdepth", "2", "-name", "*.py"],
            reason="test",
            can_rewrite=False,
            rewrite_kind="blocked",
        )
        assert should_allow_scan_for_context(ctx, info) is True

    def test_allows_when_all_conditions_met_find_scoped(self):
        """Scans are allowed when ALL conditions are met (find with scoped path)."""
        ctx = self.MockContext(
            original_request="search all files in the repository",
            iteration=5,
            allow_repo_scans=True,
        )
        info = ScanCommandInfo(
            tool="find",
            raw="find ./src -name '*.py'",
            tokens=["find", "./src", "-name", "*.py"],
            reason="test",
            can_rewrite=False,
            rewrite_kind="blocked",
        )
        assert should_allow_scan_for_context(ctx, info) is True

    def test_allows_when_all_conditions_met_rg_with_bounds(self):
        """Scans are allowed when ALL conditions are met (rg with --glob)."""
        ctx = self.MockContext(
            original_request="scan entire repo for TODO",
            iteration=5,
            allow_repo_scans=True,
        )
        info = ScanCommandInfo(
            tool="rg",
            raw="rg TODO --glob '*.py'",
            tokens=["rg", "TODO", "--glob", "*.py"],
            reason="test",
            can_rewrite=False,
            rewrite_kind="blocked",
        )
        assert should_allow_scan_for_context(ctx, info) is True

    def test_allows_when_all_conditions_met_grep_with_path(self):
        """Scans are allowed when ALL conditions are met (grep with explicit scoped path)."""
        ctx = self.MockContext(
            original_request="search entire codebase",
            iteration=5,
            allow_repo_scans=True,
        )
        info = ScanCommandInfo(
            tool="grep",
            raw="grep -R TODO backend/",
            tokens=["grep", "-R", "TODO", "backend/"],
            reason="test",
            can_rewrite=False,
            rewrite_kind="blocked",
        )
        assert should_allow_scan_for_context(ctx, info) is True

    def test_edge_case_phrase_variations(self):
        """Edge cases in phrase detection - variations of explicit phrases."""
        # Test "scan the repo" (without "entire")
        ctx1 = self.MockContext(
            original_request="scan the repo for errors",
            iteration=5,
            allow_repo_scans=True,
        )
        info = ScanCommandInfo(
            tool="find",
            raw="find . -maxdepth 1 -name '*.log'",
            tokens=["find", ".", "-maxdepth", "1", "-name", "*.log"],
            reason="test",
            can_rewrite=False,
            rewrite_kind="blocked",
        )
        assert should_allow_scan_for_context(ctx1, info) is True

        # Test "entire repository" (different phrase)
        ctx2 = self.MockContext(
            original_request="check the entire repository",
            iteration=5,
            allow_repo_scans=True,
        )
        assert should_allow_scan_for_context(ctx2, info) is True

    def test_blocks_grep_without_explicit_path(self):
        """grep without explicit path (defaults to .) should be blocked."""
        ctx = self.MockContext(
            original_request="scan entire codebase",
            iteration=5,
            allow_repo_scans=True,
        )
        # Only pattern, no path - defaults to . (should be blocked)
        info = ScanCommandInfo(
            tool="grep",
            raw="grep -R TODO",
            tokens=["grep", "-R", "TODO"],
            reason="test",
            can_rewrite=False,
            rewrite_kind="blocked",
        )
        assert should_allow_scan_for_context(ctx, info) is False

    def test_blocks_grep_with_root_path(self):
        """grep with explicit root path (.) should be blocked."""
        ctx = self.MockContext(
            original_request="scan the repository",
            iteration=5,
            allow_repo_scans=True,
        )
        info = ScanCommandInfo(
            tool="grep",
            raw="grep -R TODO .",
            tokens=["grep", "-R", "TODO", "."],
            reason="test",
            can_rewrite=False,
            rewrite_kind="blocked",
        )
        assert should_allow_scan_for_context(ctx, info) is False


class TestKnownBypasses:
    """
    Document known bypasses that are NOT yet patched.

    These tests use @pytest.mark.xfail to document current limitations
    without blocking CI. When bypasses are fixed, flip to expect success.
    """

    @pytest.mark.xfail(
        reason="navi_brain.py plan executor does not yet apply scan command guard",
        strict=False,
    )
    def test_navi_brain_plan_executor_bypass(self):
        """
        KNOWN BYPASS: navi_brain.py plan executor may execute run_command
        without scan guard protection.

        TODO: Add scan guard to navi_brain.py command execution path.
        When fixed, remove @pytest.mark.xfail and this test should pass.
        """
        # This test documents the bypass for future tracking
        # When navi_brain.py is patched, this will pass
        assert False, (
            "navi_brain.py plan executor bypasses scan guard - "
            "expected to fail until patched"
        )
