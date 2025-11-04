"""
AI-powered code generation service with repo-aware prompting.
Generates unified diffs based on plan intent and file context.
"""

from __future__ import annotations
import asyncio
import os
import logging
from typing import List, Dict

from .repo_context import repo_snapshot, list_neighbors
from backend.core.ai_service import AIService

logger = logging.getLogger(__name__)

# Configuration from environment
MODEL = os.getenv("CODEGEN_MODEL", "gpt-4o-mini")
# Maximum token limit for code generation (from environment)
# After max_tokens, the model stops generating - diffs may be incomplete
# For complex changes involving multiple files, consider increasing further
MAX_TOKENS = int(os.getenv("CODEGEN_MAX_TOKENS", "4096"))
# Maximum token limit for retry attempts - set to double MAX_TOKENS by default
# This ensures retries have a higher token budget for more comprehensive outputs
MAX_RETRY_TOKEN_LIMIT = 2 * MAX_TOKENS
# Minimum character count to consider a diff salvageable after truncation
MIN_SALVAGEABLE_DIFF_LENGTH = 50
TEMPERATURE = float(os.getenv("CODEGEN_TEMPERATURE", "0.2"))

SYSTEM_PROMPT = """You are a senior software engineer generating code changes for a production repository.

Your task is to generate a minimal, buildable unified diff (git format) that satisfies the given intent.

Guidelines:
- Generate ONLY the changes needed to implement the intent
- Maintain consistency with existing code style and patterns
- Include proper error handling and validation
- Keep changes minimal - prefer editing over rewriting entire files
- Only modify files that are listed in TARGET_FILES unless explicitly required
- If creating a new file, keep it small and focused
- Follow the repository's existing patterns and conventions

Output format:
- Return ONLY a unified diff starting with 'diff --git' lines
- No explanatory prose before or after the diff
- No markdown code blocks or formatting
- Just the raw unified diff text
"""


def build_prompt(intent: str, files: List[str], snapshot: Dict[str, str]) -> str:
    """
    Build a comprehensive prompt with intent, files, and context.

    Args:
        intent: User's description of what to implement
        files: List of target file paths
        snapshot: Dict mapping file paths to their contents

    Returns:
        Formatted prompt string
    """
    ctx_parts: List[str] = []

    # Add intent section
    ctx_parts.append("INTENT:")
    ctx_parts.append(intent)
    ctx_parts.append("")

    # Add target files list
    if files:
        ctx_parts.append("TARGET_FILES:")
        ctx_parts.append("\n".join(f"  - {f}" for f in files))
        ctx_parts.append("")

    # Add each file's content and neighbors
    for file_path in files:
        body = snapshot.get(file_path, "# File not found or empty")

        ctx_parts.append(f"FILE: {file_path}")
        ctx_parts.append("─" * 60)
        ctx_parts.append(body)
        ctx_parts.append("")

        # Add neighbor files for context
        neighbors = list_neighbors(file_path)
        if neighbors:
            ctx_parts.append("NEIGHBORING FILES IN SAME DIRECTORY:")
            ctx_parts.append(", ".join(neighbors[:10]))  # Limit to 10 for brevity
            ctx_parts.append("")

    # Add output format reminder
    ctx_parts.append("OUTPUT FORMAT:")
    ctx_parts.append("Return ONLY a unified diff beginning with 'diff --git' lines.")
    ctx_parts.append("No prose, no markdown blocks, no explanations - just the diff.")
    ctx_parts.append("")

    return "\n".join(ctx_parts)


async def call_model(prompt: str, max_retries: int = 2) -> str:
    """
    Call AI model to generate diff with intelligent fallback strategies.

    Args:
        prompt: The formatted prompt with intent and context
        max_retries: Number of fallback attempts if truncation occurs

    Returns:
        Generated diff text

    Raises:
        Exception: If AI service fails or all strategies exhausted
    """
    ai_service = AIService()

    if not ai_service.client:
        raise Exception(
            "AI service not configured. Set OPENAI_API_KEY environment variable."
        )

    current_max_tokens = MAX_TOKENS
    current_prompt = prompt

    for attempt in range(max_retries + 1):
        try:
            logger.info(
                f"Generation attempt {attempt + 1}/{max_retries + 1}, max_tokens: {current_max_tokens}"
            )

            # Use OpenAI API directly for better control
            response = ai_service.client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": current_prompt},
                ],
                temperature=TEMPERATURE,
                max_tokens=current_max_tokens,
                timeout=60,  # 60 second timeout
            )

            content = response.choices[0].message.content
            if not content:
                raise Exception("Model returned empty response")

            finish_reason = response.choices[0].finish_reason
            logger.info(
                f"Generation completed, finish_reason: {finish_reason}, length: {len(content)} chars"
            )

            # Check if generation was truncated
            if finish_reason == "length":
                logger.warning(f"Generation truncated at {current_max_tokens} tokens")

                if attempt < max_retries:
                    # Strategy 1: Increase token limit for retry
                    if attempt == 0:
                        new_token_limit = min(
                            current_max_tokens * 2, MAX_RETRY_TOKEN_LIMIT
                        )
                        if new_token_limit > current_max_tokens:
                            current_max_tokens = new_token_limit
                            logger.info(
                                f"Retrying with increased token limit: {current_max_tokens}"
                            )
                            continue
                        else:
                            logger.info(
                                f"Already at max token limit ({MAX_RETRY_TOKEN_LIMIT}), moving to next strategy"
                            )

                    # Strategy 2: Reduce context and ask for focused diff
                    if attempt == 1 or (
                        attempt == 0 and current_max_tokens >= MAX_RETRY_TOKEN_LIMIT
                    ):
                        current_prompt = _create_focused_prompt(prompt)
                        current_max_tokens = MAX_TOKENS
                        logger.info(
                            "Retrying with reduced context for focused generation"
                        )
                        continue
                else:
                    # Final attempt failed - check if diff is salvageable
                    if _is_diff_salvageable(content):
                        logger.warning("Using truncated but potentially valid diff")
                        return content.strip()
                    else:
                        raise Exception(
                            f"Generation consistently truncated after {max_retries + 1} attempts. "
                            "Try breaking your request into smaller, more focused changes."
                        )

            # Generation completed successfully
            return content.strip()

        except Exception as e:
            if "API" in str(e) or "rate" in str(e).lower():
                logger.error(f"API error on attempt {attempt + 1}: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2**attempt)  # Exponential backoff
                    continue
            logger.error(f"Failed to call AI model: {e}")
            raise Exception(f"AI generation failed: {str(e)}")

    raise Exception("All generation attempts failed")


def _create_focused_prompt(original_prompt: str) -> str:
    """
    Create a more focused prompt by reducing context when hitting token limits.
    """
    lines = original_prompt.split("\n")

    # Find key sections
    files_start = next(
        (i for i, line in enumerate(lines) if "TARGET_FILES:" in line), 0
    )
    content_start = next((i for i, line in enumerate(lines) if "FILE:" in line), 0)

    # Keep intent and file list, but reduce file content
    focused_lines = (
        lines[:content_start] if content_start > 0 else lines[: files_start + 2]
    )

    # Add instruction for focused generation
    focused_lines.extend(
        [
            "",
            "Note: Generate a focused diff for the most critical changes only.",
            "If multiple files need changes, prioritize the main file mentioned in the intent.",
            "",
            "OUTPUT FORMAT:",
            "Return only a valid unified diff in git format.",
        ]
    )

    return "\n".join(focused_lines)


def _is_diff_salvageable(diff: str) -> bool:
    """
    Check if a truncated diff might still be valid/useful.
    """
    if not diff or len(diff.strip()) < MIN_SALVAGEABLE_DIFF_LENGTH:
        return False

    # Check for basic diff structure
    if not diff.strip().startswith("diff --git"):
        return False

    # Check if it ends abruptly in the middle of a line
    lines = diff.split("\n")
    last_line = lines[-1] if lines else ""

    # If last line looks incomplete (no proper line prefix), it's probably truncated
    if last_line and not any(
        last_line.startswith(prefix)
        for prefix in ["+", "-", " ", "diff", "index", "---", "+++", "@@"]
    ):
        return False

    # If we have at least one complete diff block, it might be salvageable
    if "@@" in diff and any(line.startswith(("+", "-")) for line in lines):
        return True

    return False


async def generate_unified_diff(intent: str, files: List[str]) -> str:
    """
    Generate a unified diff for the given intent and target files.

    Args:
        intent: Description of what to implement
        files: List of relative file paths to modify

    Returns:
        Unified diff text in git format

    Raises:
        Exception: If generation fails
    """
    if not intent or not intent.strip():
        raise ValueError("Intent cannot be empty")

    if not files:
        raise ValueError("At least one target file must be specified")

    # Security: Limit number of files
    if len(files) > 5:
        raise ValueError(f"Too many files ({len(files)}), maximum is 5")

    logger.info(
        f"Generating diff for {len(files)} files with intent: {intent[:100]}..."
    )

    # Gather file contents
    snapshot = repo_snapshot(files)

    # Build prompt with context
    prompt = build_prompt(intent, files, snapshot)

    # Log prompt size for monitoring
    prompt_size = len(prompt.encode("utf-8"))
    logger.info(f"Prompt size: {prompt_size / 1024:.1f}KB")

    # Call model to generate diff
    diff = await call_model(prompt)

    return diff.strip()
