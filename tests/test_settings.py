"""Tests for settings validation."""

import os
import subprocess
import sys
import tempfile


def test_jwt_enabled_requires_secret():
    """Test that JWT_ENABLED=true requires JWT_SECRET to be set."""
    # Run in subprocess with a temp directory to avoid .env file loading
    code = """
import sys
import os
os.environ['JWT_ENABLED'] = 'true'
if 'JWT_SECRET' in os.environ:
    del os.environ['JWT_SECRET']
try:
    from backend.core.settings import settings
    sys.exit(1)  # Should not reach here
except ValueError as e:
    if 'JWT_SECRET must be set when JWT_ENABLED=true' in str(e):
        sys.exit(0)  # Expected error
    sys.exit(2)  # Wrong error
"""
    # Run in temp directory to avoid loading .env file, but keep PYTHONPATH
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = os.environ.copy()
    env["JWT_ENABLED"] = "true"
    env["PYTHONPATH"] = project_root
    # Note: subprocess code will delete JWT_SECRET if present

    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, cwd=tmpdir, env=env
        )
    assert (
        result.returncode == 0
    ), f"Expected ValueError was not raised. stderr: {result.stderr.decode()}"


def test_jwt_enabled_with_secret_succeeds():
    """Test that JWT_ENABLED=true with JWT_SECRET succeeds."""
    # Run in subprocess with a temp directory to avoid .env file loading
    code = """
import sys
import os
os.environ['JWT_ENABLED'] = 'true'
os.environ['JWT_SECRET'] = 'test-secret-key'
try:
    from backend.core.settings import settings
    assert settings.JWT_ENABLED is True
    assert settings.JWT_SECRET == 'test-secret-key'
    sys.exit(0)
except Exception as e:
    print(f"Unexpected error: {e}", file=sys.stderr)
    sys.exit(1)
"""
    # Run in temp directory to avoid loading .env file, but keep PYTHONPATH
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = os.environ.copy()
    env["JWT_ENABLED"] = "true"
    env["JWT_SECRET"] = "test-secret-key"
    env["PYTHONPATH"] = project_root

    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, cwd=tmpdir, env=env
        )
    assert (
        result.returncode == 0
    ), f"Settings validation failed. stderr: {result.stderr.decode()}"


def test_jwt_disabled_without_secret_succeeds():
    """Test that JWT_ENABLED=false works without JWT_SECRET."""
    # Run in subprocess with a temp directory to avoid .env file loading
    code = """
import sys
import os
os.environ['JWT_ENABLED'] = 'false'
if 'JWT_SECRET' in os.environ:
    del os.environ['JWT_SECRET']
try:
    from backend.core.settings import settings
    assert settings.JWT_ENABLED is False
    sys.exit(0)
except Exception as e:
    print(f"Unexpected error: {e}", file=sys.stderr)
    sys.exit(1)
"""
    # Run in temp directory to avoid loading .env file, but keep PYTHONPATH
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = os.environ.copy()
    env["JWT_ENABLED"] = "false"
    env["PYTHONPATH"] = project_root
    # Note: subprocess code will delete JWT_SECRET if present

    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, cwd=tmpdir, env=env
        )
    assert (
        result.returncode == 0
    ), f"Settings validation failed. stderr: {result.stderr.decode()}"
