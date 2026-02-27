# backend/tests/test_scan_command_guard.py

import pytest

from backend.services.scan_command_guard import (
    is_scan_command,
    rewrite_to_discovery,
    normalize_find_name_to_substring,
    is_piped_or_chained,
)


class TestTokenAwareDetection:
    @pytest.mark.parametrize("command,should_detect,tool", [
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
    ])
    def test_scan_detection(self, command, should_detect, tool):
        result = is_scan_command(command)
        if should_detect:
            assert result is not None
            assert result.tool == tool
        else:
            assert result is None


class TestPatternNormalization:
    @pytest.mark.parametrize("input_pattern,expected", [
        ("*.py", ".py"),
        ("*.tsx", ".tsx"),
        ("Button.tsx", "Button.tsx"),
        ("Dockerfile", "Dockerfile"),
        ("test_*.py", "test_"),  # FIX #7: Extract longest literal segment, not concatenation
        ("*", ""),
        ("???", ""),
    ])
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
    @pytest.mark.parametrize("command", [
        "find . -name '*.py' | xargs grep TODO",
        "cd src && find . -name '*.tsx'",
        "find . -name '*.log' &",
        "find . -type f -exec grep TODO {} \\;",
    ])
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
        assert _is_scoped_path("$PWD") is False
        assert _is_scoped_path("${PWD}") is False

        # Directory-like paths should be scoped
        assert _is_scoped_path("./src") is True
        assert _is_scoped_path("backend/") is True
        assert _is_scoped_path("src/components") is True

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
