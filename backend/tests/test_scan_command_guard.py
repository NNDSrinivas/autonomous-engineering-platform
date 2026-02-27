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
        ("test_*.py", "test_.py"),
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
