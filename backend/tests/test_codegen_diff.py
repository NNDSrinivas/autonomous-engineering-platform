"""
Tests for AI code generation diff utilities.
"""

import pytest
from backend.core.ai.diff_utils import (
    validate_unified_diff,
    count_diff_stats,
    DiffValidationError,
)

# Minimal valid unified diff
MINIMAL_DIFF = """diff --git a/file.txt b/file.txt
index e69de29..4b825dc 100644
--- a/file.txt
+++ b/file.txt
@@ -0,0 +1,1 @@
+hello
"""

# Multi-file diff
MULTI_FILE_DIFF = """diff --git a/a.txt b/a.txt
index e69de29..5626abf 100644
--- a/a.txt
+++ b/a.txt
@@ -0,0 +1 @@
+one
diff --git a/b.txt b/b.txt
index e69de29..f719efd 100644
--- a/b.txt
+++ b/b.txt
@@ -0,0 +1 @@
+two
"""


def test_validate_minimal_diff():
    """Valid minimal diff should pass validation."""
    validate_unified_diff(MINIMAL_DIFF)


def test_validate_multi_file_diff():
    """Valid multi-file diff should pass validation."""
    validate_unified_diff(MULTI_FILE_DIFF)


def test_count_diff_stats():
    """Should correctly count files, additions, and deletions."""
    files, additions, deletions = count_diff_stats(MINIMAL_DIFF)
    assert files == 1
    assert additions == 1
    assert deletions == 0


def test_count_multi_file_stats():
    """Should correctly count stats for multi-file diff."""
    files, additions, deletions = count_diff_stats(MULTI_FILE_DIFF)
    assert files == 2
    assert additions == 2
    assert deletions == 0


@pytest.mark.parametrize(
    "bad_input",
    [
        "",  # Empty
        "   ",  # Whitespace only
        "not a diff at all",  # No diff headers
        "@@ -1 +1 @@\n+hello",  # Missing diff --git header
        "diff --git a/f b/f\n+hello",  # Missing hunk header
        "diff --git a/f b/f\nindex 123..456\n@@ -1 +1 @@\nINVALID LINE",  # Invalid line prefix
    ],
)
def test_validate_bad_diffs(bad_input):
    """Invalid diffs should raise DiffValidationError."""
    with pytest.raises(DiffValidationError):
        validate_unified_diff(bad_input)


def test_validate_too_many_files():
    """Diff with too many files should fail validation."""
    # Generate a diff with 6 files (limit is 5)
    many_files = "\n".join(
        [
            f"diff --git a/file{i}.txt b/file{i}.txt\n"
            f"index e69de29..5626abf 100644\n"
            f"--- a/file{i}.txt\n"
            f"+++ b/file{i}.txt\n"
            f"@@ -0,0 +1 @@\n"
            f"+content\n"
            for i in range(6)
        ]
    )

    with pytest.raises(DiffValidationError, match="exceeds limit"):
        validate_unified_diff(many_files, max_files=5)


def test_validate_too_many_additions():
    """Diff with too many additions should fail validation."""
    # Generate a diff with 2001 additions (limit is 2000)
    many_lines = "diff --git a/big.txt b/big.txt\n"
    many_lines += "index e69de29..123 100644\n"
    many_lines += "--- a/big.txt\n"
    many_lines += "+++ b/big.txt\n"
    many_lines += "@@ -0,0 +1,2001 @@\n"
    many_lines += "\n".join([f"+line {i}" for i in range(2001)])

    with pytest.raises(DiffValidationError, match="exceeds limit"):
        validate_unified_diff(many_lines, max_additions=2000)


def test_validate_too_large():
    """Diff exceeding size limit should fail validation."""
    # Generate a diff > 256KB
    huge_diff = "diff --git a/huge.txt b/huge.txt\n"
    huge_diff += "index e69de29..123 100644\n"
    huge_diff += "--- a/huge.txt\n"
    huge_diff += "+++ b/huge.txt\n"
    huge_diff += "@@ -0,0 +1,1 @@\n"
    huge_diff += "+\n" + ("x" * 300000)  # > 256KB

    with pytest.raises(DiffValidationError, match="exceeds 256KB"):
        validate_unified_diff(huge_diff)
