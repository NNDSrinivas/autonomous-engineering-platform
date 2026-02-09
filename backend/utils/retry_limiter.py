"""
Smart Retry Limiter for NAVI

Prevents infinite loops by detecting repetitive failing actions, while allowing
NAVI to continue trying different approaches to solve problems.

Key principle: Block repeating the SAME failing action, not solving the problem.
"""

from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import hashlib
import re


@dataclass
class ActionAttempt:
    """Tracks attempts for a specific action + error combination"""

    action_signature: str  # Unique signature of the action (what NAVI tried)
    error_signature: str  # Signature of the error that resulted
    attempt_count: int = 0
    first_attempt: datetime = field(default_factory=datetime.now)
    last_attempt: datetime = field(default_factory=datetime.now)
    error_messages: List[str] = field(default_factory=list)


class IntelligentRetryLimiter:
    """
    Smart retry limiter that detects infinite loops while allowing NAVI
    to continue solving problems with different approaches.

    Philosophy:
    - NEVER give up on a task
    - Only prevent repeating the EXACT same failing action
    - Encourage trying alternative approaches
    - Learn from what doesn't work
    """

    # Maximum total attempts (initial attempt + retries) for the EXACT same
    # failing action+error signature within the tracking/memory windows.
    #
    # Example: With MAX_TOTAL_ATTEMPTS = 2:
    #   - 1st attempt: Fails, increment counter to 1, allowed to continue
    #   - 2nd attempt: Fails, increment counter to 2, check (2 >= 2) blocks further attempts
    #   - Result: 2 total attempts allowed (initial + 1 retry)
    #
    # Set this value based on how many times you want to allow the same action
    # to fail before blocking it. A value of 2 allows one retry; 3 allows two retries.
    MAX_TOTAL_ATTEMPTS = 2

    # Time window for tracking action patterns (10 minutes)
    TRACKING_WINDOW = timedelta(minutes=10)

    # How long to remember that an action failed (30 minutes)
    MEMORY_WINDOW = timedelta(minutes=30)

    def __init__(self):
        self._action_attempts: Dict[str, ActionAttempt] = {}
        self._successful_approaches: Dict[str, datetime] = {}

    def _generate_action_signature(
        self, action: str, target: str, approach: Optional[str] = None
    ) -> str:
        """
        Generate signature for a specific action.

        Args:
            action: Type of action (e.g., "edit_file", "run_command")
            target: What the action is targeting (file path, command, etc.)
            approach: Optional description of the approach being used
        """
        components = [action, target]
        if approach:
            components.append(approach)
        combined = ":".join(components)
        # Using SHA-256 for bucketing/signatures (non-cryptographic purpose)
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _generate_error_signature(self, error: str) -> str:
        """Generate signature for an error message (normalized)"""
        # Normalize error: remove line numbers, timestamps, etc.
        normalized = error.lower().strip()
        # Remove common variable parts
        for pattern in [r"\d+", r"at \d+:\d+", r"line \d+"]:
            normalized = re.sub(pattern, "", normalized)
        # Using SHA-256 for bucketing/signatures (non-cryptographic purpose)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _get_attempt_key(self, action_sig: str, error_sig: str) -> str:
        """Combine action and error signatures into a unique key"""
        return f"{action_sig}:{error_sig}"

    def should_allow_action(
        self,
        action: str,
        target: str,
        error: Optional[str] = None,
        approach: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if NAVI should be allowed to try this action.

        Args:
            action: Type of action (e.g., "edit_file", "run_command")
            target: What the action targets (file path, command, etc.)
            error: The error that occurred (if checking after a failure)
            approach: Description of the approach being used

        Returns:
            Tuple of (should_allow: bool, suggestion: Optional[str])
            - should_allow: True if NAVI should try this action
            - suggestion: If False, provides alternative approach suggestion
        """
        self._cleanup_old_attempts()

        # If no error provided, this is a check before attempting - allow it
        if not error:
            return True, None

        action_sig = self._generate_action_signature(action, target, approach)
        error_sig = self._generate_error_signature(error)
        key = self._get_attempt_key(action_sig, error_sig)

        attempt = self._action_attempts.get(key)

        if not attempt:
            # First time seeing this action + error combination - allow it
            return True, None

        # Check if we're within the tracking window
        if datetime.now() - attempt.last_attempt > self.TRACKING_WINDOW:
            # It's been a while - reset and allow trying again
            del self._action_attempts[key]
            return True, None

        # Check if we've hit the limit for this specific failing action
        # Note: attempt_count is incremented AFTER each failure, so this check
        # happens before the increment. With MAX_TOTAL_ATTEMPTS=2, we block when
        # attempt_count reaches 2 (meaning 2 failures have already occurred).
        if attempt.attempt_count >= self.MAX_TOTAL_ATTEMPTS:
            # We've tried this exact action too many times with the same error
            suggestion = self._generate_alternative_suggestion(action, target, error)
            return False, suggestion

        # Still below limit - allow it
        return True, None

    def record_attempt(
        self, action: str, target: str, error: str, approach: Optional[str] = None
    ):
        """
        Record that NAVI attempted an action and got an error.

        Args:
            action: Type of action
            target: What was targeted
            error: The error that resulted
            approach: Optional description of approach used
        """
        action_sig = self._generate_action_signature(action, target, approach)
        error_sig = self._generate_error_signature(error)
        key = self._get_attempt_key(action_sig, error_sig)

        if key not in self._action_attempts:
            self._action_attempts[key] = ActionAttempt(
                action_signature=action_sig, error_signature=error_sig
            )

        attempt = self._action_attempts[key]
        attempt.attempt_count += 1
        attempt.last_attempt = datetime.now()
        attempt.error_messages.append(error[:200])  # Store truncated error

    def record_success(self, action: str, target: str, approach: Optional[str] = None):
        """
        Record that NAVI successfully completed an action.
        This helps learn which approaches work.

        Args:
            action: Type of action
            target: What was targeted
            approach: Optional description of approach used
        """
        action_sig = self._generate_action_signature(action, target, approach)
        self._successful_approaches[action_sig] = datetime.now()

        # Clear any failed attempts for this action
        to_remove = [
            key
            for key, attempt in self._action_attempts.items()
            if attempt.action_signature == action_sig
        ]
        for key in to_remove:
            del self._action_attempts[key]

    def _generate_alternative_suggestion(
        self, action: str, target: str, error: str
    ) -> str:
        """
        Generate a suggestion for an alternative approach when an action keeps failing.

        Args:
            action: The action that keeps failing
            target: What it's targeting
            error: The error it's getting

        Returns:
            A helpful suggestion for trying a different approach
        """
        suggestions = {
            "edit_file": [
                "Try reading the file first to understand its current structure",
                "Consider creating a backup before editing",
                "Try editing a smaller section of the file",
                "Check if the file has the correct permissions",
                "Verify the file path exists and is correct",
            ],
            "run_command": [
                "Try breaking the command into smaller steps",
                "Check if required dependencies are installed",
                "Try running with different flags or options",
                "Verify the environment variables are set correctly",
                "Check if you need different permissions",
            ],
            "create_file": [
                "Ensure the parent directory exists first",
                "Check if a file with that name already exists",
                "Try creating the file in a different location",
                "Verify you have write permissions in that directory",
            ],
            "read_file": [
                "Check if the file path is correct",
                "Verify the file exists at that location",
                "Try listing the directory contents first",
                "Check if you need different permissions to access the file",
            ],
        }

        action_suggestions = suggestions.get(
            action,
            [
                "Try a completely different approach to solve this problem",
                "Consider breaking the task into smaller steps",
                "Look for alternative tools or methods",
            ],
        )

        # Pick a deterministic suggestion based on the action/target/error combination
        # This ensures consistent UX and makes debugging easier
        key = f"{action}|{target}|{error}"
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        index = int(digest[:8], 16) % len(action_suggestions)
        suggestion = action_suggestions[index]

        return (
            f"This action has been tried {self.MAX_TOTAL_ATTEMPTS} times with the same error. "
            f"Suggestion: {suggestion}"
        )

    def get_repeated_failures(self) -> List[Dict]:
        """Get list of actions that have been failing repeatedly"""
        failures = []
        for key, attempt in self._action_attempts.items():
            if attempt.attempt_count >= self.MAX_TOTAL_ATTEMPTS:
                failures.append(
                    {
                        "action_signature": attempt.action_signature,
                        "attempts": attempt.attempt_count,
                        "last_error": (
                            attempt.error_messages[-1]
                            if attempt.error_messages
                            else None
                        ),
                        "first_attempted": attempt.first_attempt.isoformat(),
                        "last_attempted": attempt.last_attempt.isoformat(),
                    }
                )
        return failures

    def _cleanup_old_attempts(self):
        """Remove attempts outside the memory window"""
        now = datetime.now()
        to_remove = [
            key
            for key, attempt in self._action_attempts.items()
            if now - attempt.last_attempt > self.MEMORY_WINDOW
        ]
        for key in to_remove:
            del self._action_attempts[key]

        # Also cleanup old successes
        to_remove_success = [
            key
            for key, timestamp in self._successful_approaches.items()
            if now - timestamp > self.MEMORY_WINDOW
        ]
        for key in to_remove_success:
            del self._successful_approaches[key]

    def reset(self):
        """Clear all tracked attempts (useful for starting fresh)"""
        self._action_attempts.clear()
        self._successful_approaches.clear()

    def get_summary(self) -> Dict:
        """Get summary of current retry state"""
        return {
            "active_failed_attempts": len(self._action_attempts),
            "successful_approaches": len(self._successful_approaches),
            "max_identical_retries": self.MAX_TOTAL_ATTEMPTS,
            "tracking_window_minutes": self.TRACKING_WINDOW.total_seconds() / 60,
            "memory_window_minutes": self.MEMORY_WINDOW.total_seconds() / 60,
            "repeated_failures": self.get_repeated_failures(),
        }


# Global intelligent retry limiter instance
intelligent_retry_limiter = IntelligentRetryLimiter()
