"""
Message Formatter for NAVI Responses

Provides utilities to format NAVI messages with proper markdown structure,
separating concise user-facing messages from verbose thinking/reasoning.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class FormattedMessage:
    """Structured message with proper markdown formatting"""

    main_message: str  # Concise, actionable message for user
    thinking_steps: List[str]  # Detailed reasoning (collapsible)
    details: Optional[str] = None  # Additional context (collapsible)


class MarkdownFormatter:
    """Utilities for creating well-structured markdown messages"""

    @staticmethod
    def heading(text: str, level: int = 2) -> str:
        """Create a markdown heading"""
        return f"{'#' * level} {text}\n\n"

    @staticmethod
    def bold(text: str) -> str:
        """Make text bold"""
        return f"**{text}**"

    @staticmethod
    def code_inline(text: str) -> str:
        """Inline code formatting"""
        return f"`{text}`"

    @staticmethod
    def code_block(code: str, language: str = "") -> str:
        """Code block formatting"""
        return f"```{language}\n{code}\n```\n\n"

    @staticmethod
    def bullet_list(items: List[str]) -> str:
        """Create a bulleted list"""
        return "\n".join(f"- {item}" for item in items) + "\n\n"

    @staticmethod
    def numbered_list(items: List[str]) -> str:
        """Create a numbered list"""
        return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items)) + "\n\n"

    @staticmethod
    def blockquote(text: str) -> str:
        """Create a blockquote"""
        lines = text.split("\n")
        return "\n".join(f"> {line}" for line in lines) + "\n\n"

    @staticmethod
    def collapsible_section(title: str, content: str) -> str:
        """Create a collapsible details section"""
        return f"""<details>
<summary>{title}</summary>

{content}
</details>

"""

    @staticmethod
    def info_box(message: str, emoji: str = "ℹ️") -> str:
        """Create an info box"""
        return f"{emoji} {message}\n\n"

    @staticmethod
    def warning_box(message: str) -> str:
        """Create a warning box"""
        return f"⚠️ **Warning:** {message}\n\n"

    @staticmethod
    def success_box(message: str) -> str:
        """Create a success box"""
        return f"✅ {message}\n\n"

    @staticmethod
    def error_box(message: str) -> str:
        """Create an error box"""
        return f"❌ **Error:** {message}\n\n"


class NaviMessageBuilder:
    """Builder for constructing well-formatted NAVI messages"""

    def __init__(self):
        self.sections: List[str] = []
        self.thinking: List[str] = []

    def add_section(self, content: str) -> "NaviMessageBuilder":
        """Add a section to the main message"""
        self.sections.append(content)
        return self

    def add_heading(self, text: str, level: int = 2) -> "NaviMessageBuilder":
        """Add a heading"""
        self.sections.append(MarkdownFormatter.heading(text, level))
        return self

    def add_paragraph(self, text: str) -> "NaviMessageBuilder":
        """Add a paragraph"""
        self.sections.append(f"{text}\n\n")
        return self

    def add_bullet_list(self, items: List[str]) -> "NaviMessageBuilder":
        """Add a bulleted list"""
        self.sections.append(MarkdownFormatter.bullet_list(items))
        return self

    def add_numbered_list(self, items: List[str]) -> "NaviMessageBuilder":
        """Add a numbered list"""
        self.sections.append(MarkdownFormatter.numbered_list(items))
        return self

    def add_code_block(self, code: str, language: str = "") -> "NaviMessageBuilder":
        """Add a code block"""
        self.sections.append(MarkdownFormatter.code_block(code, language))
        return self

    def add_info(self, message: str, emoji: str = "ℹ️") -> "NaviMessageBuilder":
        """Add an info message"""
        self.sections.append(MarkdownFormatter.info_box(message, emoji))
        return self

    def add_warning(self, message: str) -> "NaviMessageBuilder":
        """Add a warning"""
        self.sections.append(MarkdownFormatter.warning_box(message))
        return self

    def add_success(self, message: str) -> "NaviMessageBuilder":
        """Add a success message"""
        self.sections.append(MarkdownFormatter.success_box(message))
        return self

    def add_thinking_step(self, step: str) -> "NaviMessageBuilder":
        """Add a thinking/reasoning step (will be collapsible)"""
        self.thinking.append(step)
        return self

    def build(self) -> FormattedMessage:
        """Build the final formatted message"""
        main_message = "".join(self.sections).strip()
        return FormattedMessage(
            main_message=main_message,
            thinking_steps=self.thinking
        )


class MessageTemplates:
    """Common message templates for NAVI responses"""

    @staticmethod
    def port_conflict(
        port: int,
        process_name: str,
        process_cmd: str,
        alternative_port: int,
        framework: str
    ) -> FormattedMessage:
        """Format a port conflict message with proper structure"""
        builder = NaviMessageBuilder()

        # Concise main message
        builder.add_info(
            f"Port {port} is currently in use. Starting on port {alternative_port} instead.",
            "🚀"
        )

        builder.add_paragraph(
            f"I'll start your {MarkdownFormatter.bold(framework)} project on "
            f"{MarkdownFormatter.bold(f'port {alternative_port}')}."
        )

        # Details in collapsible section (via thinking)
        builder.add_thinking_step(
            f"Detected port {port} is occupied by: {process_name}"
        )
        builder.add_thinking_step(
            f"Process command: {process_cmd[:80]}..."
        )
        builder.add_thinking_step(
            f"Selected alternative port: {alternative_port}"
        )

        return builder.build()

    @staticmethod
    def run_instructions(
        project_name: str,
        framework: str,
        install_cmd: str,
        run_cmd: str,
        port: Optional[int] = None
    ) -> FormattedMessage:
        """Format project run instructions"""
        builder = NaviMessageBuilder()

        builder.add_heading(f"Running {project_name}", 3)

        builder.add_paragraph(
            f"This is a {MarkdownFormatter.bold(framework)} project."
        )

        builder.add_heading("Setup", 4)
        builder.add_numbered_list([
            f"Install dependencies: {MarkdownFormatter.code_inline(install_cmd)}",
            f"Start the server: {MarkdownFormatter.code_inline(run_cmd)}"
        ])

        if port:
            builder.add_info(
                f"Server will be available at http://localhost:{port}",
                "🌐"
            )

        return builder.build()

    @staticmethod
    def error_with_context(
        error_message: str,
        context: Optional[str] = None,
        suggestions: Optional[List[str]] = None
    ) -> FormattedMessage:
        """Format an error message with context and suggestions"""
        builder = NaviMessageBuilder()

        builder.add_section(MarkdownFormatter.error_box(error_message))

        if context:
            builder.add_paragraph(context)

        if suggestions:
            builder.add_heading("Suggestions", 4)
            builder.add_bullet_list(suggestions)

        # Add technical details to thinking
        if context:
            builder.add_thinking_step(f"Error context: {context}")

        return builder.build()
