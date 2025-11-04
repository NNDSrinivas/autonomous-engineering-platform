"""
AI-powered code generation service with repo-aware prompting.
Generates unified diffs based on plan intent and file context.
"""

from __future__ import annotations
import json
import os
import logging
from typing import List, Dict, Any

from .repo_context import repo_snapshot, list_neighbors
from backend.core.ai_service import AIService

logger = logging.getLogger(__name__)

# Configuration from environment
MODEL = os.getenv("CODEGEN_MODEL", "gpt-4o-mini")
MAX_TOKENS = int(os.getenv("CODEGEN_MAX_TOKENS", "1200"))
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
            ctx_parts.append(f"NEIGHBORING FILES IN SAME DIRECTORY:")
            ctx_parts.append(", ".join(neighbors[:10]))  # Limit to 10 for brevity
            ctx_parts.append("")

    # Add output format reminder
    ctx_parts.append("OUTPUT FORMAT:")
    ctx_parts.append("Return ONLY a unified diff beginning with 'diff --git' lines.")
    ctx_parts.append("No prose, no markdown blocks, no explanations - just the diff.")
    ctx_parts.append("")

    return "\n".join(ctx_parts)


async def call_model(prompt: str) -> str:
    """
    Call AI model to generate diff based on prompt.

    Args:
        prompt: The formatted prompt with intent and context

    Returns:
        Generated diff text

    Raises:
        Exception: If AI service fails
    """
    ai_service = AIService()

    if not ai_service.client:
        raise Exception(
            "AI service not configured. Set OPENAI_API_KEY environment variable."
        )

    try:
        # Use OpenAI API directly for better control
        response = ai_service.client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            timeout=60,  # 60 second timeout
        )

        content = response.choices[0].message.content
        if not content:
            raise Exception("Model returned empty response")

        logger.info(f"Model generated {len(content)} chars of diff")
        return content.strip()

    except Exception as e:
        logger.error(f"Failed to call AI model: {e}")
        raise Exception(f"AI generation failed: {str(e)}")


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
