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
try:
    from backend.core.settings import settings
    sys.exit(1)  # Should not reach here
except ValueError as e:
    # Check for the expected error message (with or without JWKS mention)
    error_msg = str(e)
    if 'JWT_SECRET' in error_msg and 'JWT_ENABLED=true' in error_msg:
        sys.exit(0)  # Expected error
    print(f"Wrong error: {e}", file=sys.stderr)
    sys.exit(2)  # Wrong error
"""
    # Run in temp directory to avoid loading .env file, but keep PYTHONPATH
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = os.environ.copy()
    env["JWT_ENABLED"] = "true"
    env.pop("JWT_SECRET", None)  # Ensure JWT_SECRET is not set
    env.pop("JWT_SECRET_PREVIOUS", None)  # Ensure JWT_SECRET_PREVIOUS is not set
    env.pop("JWT_JWKS_URL", None)  # Ensure JWT_JWKS_URL is not set
    env["PYTHONPATH"] = project_root

    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, cwd=tmpdir, env=env
        )
    assert result.returncode == 0, (
        f"Expected ValueError was not raised. stderr: {result.stderr.decode()}"
    )


def test_jwt_enabled_with_secret_succeeds():
    """Test that JWT_ENABLED=true with JWT_SECRET succeeds."""
    # Run in subprocess with a temp directory to avoid .env file loading
    code = """
import sys
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
    assert result.returncode == 0, (
        f"Settings validation failed. stderr: {result.stderr.decode()}"
    )


def test_jwt_disabled_without_secret_succeeds():
    """Test that JWT_ENABLED=false works without JWT_SECRET."""
    # Run in subprocess with a temp directory to avoid .env file loading
    code = """
import sys
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
    env.pop("JWT_SECRET", None)  # Ensure JWT_SECRET is not set
    env["PYTHONPATH"] = project_root

    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, cwd=tmpdir, env=env
        )
    assert result.returncode == 0, (
        f"Settings validation failed. stderr: {result.stderr.decode()}"
    )
