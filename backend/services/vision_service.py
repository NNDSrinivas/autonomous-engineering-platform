"""
Vision Service - UI Screenshot Analysis with Vision LLMs

Provides:
1. Multi-provider vision support (Claude, GPT-4V, Gemini)
2. UI component detection
3. Layout analysis
4. Code generation from screenshots
5. Design-to-code conversion

NAVI uses this to understand UI mockups and generate matching code.
"""

import os
import httpx
from typing import Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

class VisionProvider(Enum):
    ANTHROPIC = "anthropic"  # Claude 3.5 Sonnet
    OPENAI = "openai"        # GPT-4 Vision
    GOOGLE = "google"        # Gemini Pro Vision


# Provider configurations
PROVIDER_CONFIG = {
    VisionProvider.ANTHROPIC: {
        "url": "https://api.anthropic.com/v1/messages",
        "model": "claude-3-5-sonnet-20241022",
        "env_key": "ANTHROPIC_API_KEY",
        "max_tokens": 4096,
    },
    VisionProvider.OPENAI: {
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o",
        "env_key": "OPENAI_API_KEY",
        "max_tokens": 4096,
    },
    VisionProvider.GOOGLE: {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent",
        "model": "gemini-1.5-pro",
        "env_key": "GOOGLE_API_KEY",
        "max_tokens": 4096,
    },
}


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class UIComponent:
    """A detected UI component"""
    component_type: str  # button, input, card, table, nav, etc.
    description: str
    position: str  # relative position in layout
    properties: Dict[str, Any] = field(default_factory=dict)
    children: List['UIComponent'] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.component_type,
            "description": self.description,
            "position": self.position,
            "properties": self.properties,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class LayoutAnalysis:
    """Analysis of UI layout structure"""
    layout_type: str  # grid, flex, sidebar, stack, etc.
    columns: int = 1
    rows: int = 1
    responsive: bool = True
    breakpoints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layout_type": self.layout_type,
            "columns": self.columns,
            "rows": self.rows,
            "responsive": self.responsive,
            "breakpoints": self.breakpoints,
        }


@dataclass
class UIAnalysis:
    """Complete analysis of a UI screenshot"""
    description: str
    layout: LayoutAnalysis
    components: List[UIComponent] = field(default_factory=list)
    color_scheme: Dict[str, str] = field(default_factory=dict)
    typography: Dict[str, str] = field(default_factory=dict)
    suggested_framework: str = "react"
    suggested_css: str = "tailwind"
    accessibility_notes: List[str] = field(default_factory=list)
    implementation_hints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "layout": self.layout.to_dict(),
            "components": [c.to_dict() for c in self.components],
            "color_scheme": self.color_scheme,
            "typography": self.typography,
            "suggested_framework": self.suggested_framework,
            "suggested_css": self.suggested_css,
            "accessibility_notes": self.accessibility_notes,
            "implementation_hints": self.implementation_hints,
        }

    def to_context_string(self) -> str:
        """Convert to a string that can be used as LLM context"""
        parts = [
            "=== UI ANALYSIS FROM SCREENSHOT ===",
            f"\n**Description**: {self.description}",
            f"\n**Layout**: {self.layout.layout_type} layout",
        ]

        if self.components:
            parts.append("\n**Components Detected**:")
            for comp in self.components:
                parts.append(f"  - {comp.component_type}: {comp.description}")

        if self.color_scheme:
            parts.append(f"\n**Colors**: {', '.join(f'{k}: {v}' for k, v in self.color_scheme.items())}")

        if self.implementation_hints:
            parts.append("\n**Implementation Hints**:")
            for hint in self.implementation_hints:
                parts.append(f"  - {hint}")

        parts.append(f"\n**Suggested Stack**: {self.suggested_framework} + {self.suggested_css}")

        return "\n".join(parts)


# ============================================================
# VISION API CLIENTS
# ============================================================

class VisionClient:
    """Base class for vision API clients"""

    @classmethod
    async def analyze_image(
        cls,
        image_data: str,
        prompt: str,
        provider: VisionProvider = VisionProvider.ANTHROPIC,
        timeout: int = 60,
    ) -> str:
        """
        Send an image to a vision model for analysis.

        Args:
            image_data: Base64-encoded image data
            prompt: The analysis prompt
            provider: Which vision provider to use
            timeout: Request timeout in seconds

        Returns:
            The model's text response
        """
        config = PROVIDER_CONFIG[provider]
        api_key = os.environ.get(config["env_key"])

        if not api_key:
            logger.warning(f"No API key for {provider.value}, using fallback analysis")
            return cls._fallback_analysis(prompt)

        try:
            if provider == VisionProvider.ANTHROPIC:
                return await cls._call_anthropic(image_data, prompt, api_key, config, timeout)
            elif provider == VisionProvider.OPENAI:
                return await cls._call_openai(image_data, prompt, api_key, config, timeout)
            elif provider == VisionProvider.GOOGLE:
                return await cls._call_google(image_data, prompt, api_key, config, timeout)
        except Exception as e:
            logger.error(f"Vision API error ({provider.value}): {e}")
            return cls._fallback_analysis(prompt)

        return cls._fallback_analysis(prompt)

    @classmethod
    async def _call_anthropic(
        cls,
        image_data: str,
        prompt: str,
        api_key: str,
        config: Dict,
        timeout: int,
    ) -> str:
        """Call Anthropic Claude Vision API"""
        # Detect image type
        media_type = "image/png"
        if image_data.startswith("/9j/"):
            media_type = "image/jpeg"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                config["url"],
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": config["model"],
                    "max_tokens": config["max_tokens"],
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": image_data,
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": prompt,
                                },
                            ],
                        }
                    ],
                },
                timeout=timeout,
            )

            if response.status_code == 200:
                data = response.json()
                return data["content"][0]["text"]
            else:
                logger.error(f"Anthropic API error: {response.status_code} - {response.text}")
                raise Exception(f"API error: {response.status_code}")

    @classmethod
    async def _call_openai(
        cls,
        image_data: str,
        prompt: str,
        api_key: str,
        config: Dict,
        timeout: int,
    ) -> str:
        """Call OpenAI GPT-4 Vision API"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config["url"],
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config["model"],
                    "max_tokens": config["max_tokens"],
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": prompt,
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{image_data}",
                                    },
                                },
                            ],
                        }
                    ],
                },
                timeout=timeout,
            )

            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                raise Exception(f"API error: {response.status_code}")

    @classmethod
    async def _call_google(
        cls,
        image_data: str,
        prompt: str,
        api_key: str,
        config: Dict,
        timeout: int,
    ) -> str:
        """Call Google Gemini Vision API"""
        url = f"{config['url']}?key={api_key}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [
                        {
                            "parts": [
                                {"text": prompt},
                                {
                                    "inline_data": {
                                        "mime_type": "image/png",
                                        "data": image_data,
                                    }
                                },
                            ]
                        }
                    ],
                    "generationConfig": {
                        "maxOutputTokens": config["max_tokens"],
                    },
                },
                timeout=timeout,
            )

            if response.status_code == 200:
                data = response.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            else:
                logger.error(f"Google API error: {response.status_code} - {response.text}")
                raise Exception(f"API error: {response.status_code}")

    @classmethod
    def _fallback_analysis(cls, prompt: str) -> str:
        """Provide a fallback analysis when API is unavailable"""
        return """
UI Screenshot Analysis (Fallback - No Vision API Available):

Based on standard UI patterns, here's a general analysis:

**Layout Structure:**
- Main container with responsive layout
- Header section with navigation
- Content area with potential sidebar
- Footer with secondary navigation/info

**Common Components:**
- Navigation bar (header)
- Cards for content display
- Buttons for actions
- Forms for user input
- Tables for data display

**Suggested Implementation:**
- Use CSS Grid or Flexbox for layout
- Implement responsive breakpoints
- Use semantic HTML elements
- Add ARIA labels for accessibility

For accurate analysis, please configure a vision API key:
- ANTHROPIC_API_KEY for Claude Vision
- OPENAI_API_KEY for GPT-4 Vision
- GOOGLE_API_KEY for Gemini Vision
"""


# ============================================================
# UI ANALYZER
# ============================================================

class UIAnalyzer:
    """Analyze UI screenshots and extract structured information"""

    UI_ANALYSIS_PROMPT = """Analyze this UI screenshot and provide a detailed breakdown for implementing it in code.

Please respond in JSON format with the following structure:
{
    "description": "Brief overall description of the UI",
    "layout": {
        "type": "grid|flex|sidebar|stack|split",
        "columns": number,
        "rows": number,
        "responsive": true|false
    },
    "components": [
        {
            "type": "button|input|card|nav|table|form|modal|dropdown|etc",
            "description": "What this component does",
            "position": "header|sidebar|main|footer|modal",
            "properties": {
                "variant": "primary|secondary|outline",
                "size": "sm|md|lg",
                "icon": true|false
            }
        }
    ],
    "colors": {
        "primary": "#hex",
        "secondary": "#hex",
        "background": "#hex",
        "text": "#hex",
        "accent": "#hex"
    },
    "typography": {
        "headingFont": "font name",
        "bodyFont": "font name",
        "sizes": "description of text sizes"
    },
    "framework": "react|vue|angular|svelte",
    "cssFramework": "tailwind|css-modules|styled-components|scss",
    "accessibility": ["list of accessibility considerations"],
    "implementationHints": ["list of implementation suggestions"]
}

Be specific about:
1. Component hierarchy and nesting
2. Spacing and alignment patterns
3. Interactive states (hover, active, disabled)
4. Responsive behavior clues
5. Data requirements (what data each component needs)"""

    @classmethod
    async def analyze_screenshot(
        cls,
        image_data: str,
        additional_context: str = "",
        provider: VisionProvider = VisionProvider.ANTHROPIC,
    ) -> UIAnalysis:
        """
        Analyze a UI screenshot and return structured analysis.

        Args:
            image_data: Base64-encoded image
            additional_context: Extra context about the desired UI
            provider: Vision API provider to use

        Returns:
            Structured UI analysis
        """
        prompt = cls.UI_ANALYSIS_PROMPT
        if additional_context:
            prompt += f"\n\nAdditional context from user: {additional_context}"

        # Call vision API
        raw_response = await VisionClient.analyze_image(
            image_data,
            prompt,
            provider=provider,
        )

        # Parse response
        return cls._parse_analysis(raw_response)

    @classmethod
    def _parse_analysis(cls, raw_response: str) -> UIAnalysis:
        """Parse the vision model's response into structured data"""
        # Try to extract JSON from response
        try:
            # Find JSON in response
            json_match = None
            if "{" in raw_response:
                start = raw_response.index("{")
                # Find matching closing brace
                depth = 0
                for i, char in enumerate(raw_response[start:], start):
                    if char == "{":
                        depth += 1
                    elif char == "}":
                        depth -= 1
                        if depth == 0:
                            json_match = raw_response[start:i+1]
                            break

            if json_match:
                data = json.loads(json_match)
                return cls._build_analysis_from_json(data)

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse JSON from vision response: {e}")

        # Fall back to text parsing
        return cls._build_analysis_from_text(raw_response)

    @classmethod
    def _build_analysis_from_json(cls, data: Dict) -> UIAnalysis:
        """Build UIAnalysis from parsed JSON"""
        # Parse layout
        layout_data = data.get("layout", {})
        layout = LayoutAnalysis(
            layout_type=layout_data.get("type", "flex"),
            columns=layout_data.get("columns", 1),
            rows=layout_data.get("rows", 1),
            responsive=layout_data.get("responsive", True),
        )

        # Parse components
        components = []
        for comp_data in data.get("components", []):
            components.append(UIComponent(
                component_type=comp_data.get("type", "unknown"),
                description=comp_data.get("description", ""),
                position=comp_data.get("position", "main"),
                properties=comp_data.get("properties", {}),
            ))

        return UIAnalysis(
            description=data.get("description", "UI Screenshot"),
            layout=layout,
            components=components,
            color_scheme=data.get("colors", {}),
            typography=data.get("typography", {}),
            suggested_framework=data.get("framework", "react"),
            suggested_css=data.get("cssFramework", "tailwind"),
            accessibility_notes=data.get("accessibility", []),
            implementation_hints=data.get("implementationHints", []),
        )

    @classmethod
    def _build_analysis_from_text(cls, text: str) -> UIAnalysis:
        """Build UIAnalysis from plain text response"""
        return UIAnalysis(
            description=text[:500] if len(text) > 500 else text,
            layout=LayoutAnalysis(layout_type="flex"),
            components=[],
            implementation_hints=[text] if text else [],
        )


# ============================================================
# CODE GENERATOR FROM UI
# ============================================================

class UICodeGenerator:
    """Generate code from UI analysis"""

    CODE_GENERATION_PROMPT = """Based on this UI analysis, generate the React component code:

{analysis}

Requirements:
1. Use React functional components with hooks
2. Use Tailwind CSS for styling
3. Make it responsive
4. Include TypeScript types
5. Add proper accessibility attributes (ARIA)
6. Include comments explaining the structure

Generate a complete, working component that matches the UI design."""

    @classmethod
    async def generate_component(
        cls,
        analysis: UIAnalysis,
        framework: str = "react",
        css_framework: str = "tailwind",
        llm_client: Any = None,
    ) -> str:
        """
        Generate component code from UI analysis.

        This uses a regular LLM (not vision) to generate code
        based on the structured analysis.
        """
        context = analysis.to_context_string()
        prompt = cls.CODE_GENERATION_PROMPT.format(analysis=context)

        if llm_client:
            # Use provided LLM client
            return await llm_client.generate(prompt)

        # Fallback: return a template
        return cls._generate_template(analysis, framework, css_framework)

    @classmethod
    def _generate_template(
        cls,
        analysis: UIAnalysis,
        framework: str,
        css_framework: str,
    ) -> str:
        """Generate a basic template from analysis"""
        components_jsx = []

        for comp in analysis.components:
            if comp.component_type == "button":
                components_jsx.append(
                    f'<button className="px-4 py-2 bg-blue-500 text-white rounded">{comp.description}</button>'
                )
            elif comp.component_type == "input":
                components_jsx.append(
                    f'<input type="text" className="border rounded px-3 py-2" placeholder="{comp.description}" />'
                )
            elif comp.component_type == "card":
                components_jsx.append(
                    f'<div className="bg-white rounded-lg shadow p-4">{comp.description}</div>'
                )
            elif comp.component_type == "nav":
                components_jsx.append(
                    '<nav className="flex gap-4">{/* Navigation items */}</nav>'
                )
            else:
                components_jsx.append(
                    f'<div className="p-4">{comp.description}</div>'
                )

        components_code = "\n        ".join(components_jsx) if components_jsx else "{/* Add components here */}"

        return f'''import React from 'react';

interface Props {{
  // Add props as needed
}}

/**
 * {analysis.description}
 *
 * Layout: {analysis.layout.layout_type}
 * Generated from UI screenshot analysis
 */
export const Component: React.FC<Props> = () => {{
  return (
    <div className="min-h-screen bg-gray-50">
      {{/* Header */}}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="text-2xl font-bold">Title</h1>
        </div>
      </header>

      {{/* Main Content */}}
      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 md:grid-cols-{analysis.layout.columns} gap-6">
          {components_code}
        </div>
      </main>

      {{/* Footer */}}
      <footer className="bg-gray-800 text-white py-8">
        <div className="max-w-7xl mx-auto px-4">
          Footer content
        </div>
      </footer>
    </div>
  );
}};

export default Component;
'''


# ============================================================
# PUBLIC API
# ============================================================

async def analyze_ui_screenshot(
    image_data: str,
    context: str = "",
    provider: str = "anthropic",
) -> Dict[str, Any]:
    """
    Analyze a UI screenshot and return structured information.

    Args:
        image_data: Base64-encoded image data
        context: Additional context about the UI
        provider: Vision provider (anthropic, openai, google)

    Returns:
        Structured UI analysis
    """
    provider_enum = VisionProvider(provider.lower())

    analysis = await UIAnalyzer.analyze_screenshot(
        image_data,
        additional_context=context,
        provider=provider_enum,
    )

    return analysis.to_dict()


async def generate_code_from_ui(
    image_data: str,
    framework: str = "react",
    css_framework: str = "tailwind",
    provider: str = "anthropic",
) -> Dict[str, Any]:
    """
    Generate component code from a UI screenshot.

    Args:
        image_data: Base64-encoded image
        framework: Target framework (react, vue, etc.)
        css_framework: CSS framework (tailwind, etc.)
        provider: Vision provider

    Returns:
        Generated code and analysis
    """
    provider_enum = VisionProvider(provider.lower())

    # First analyze the UI
    analysis = await UIAnalyzer.analyze_screenshot(
        image_data,
        provider=provider_enum,
    )

    # Then generate code
    code = await UICodeGenerator.generate_component(
        analysis,
        framework=framework,
        css_framework=css_framework,
    )

    return {
        "analysis": analysis.to_dict(),
        "code": code,
        "framework": framework,
        "css_framework": css_framework,
    }


def get_ui_context_for_llm(analysis: UIAnalysis) -> str:
    """
    Convert UI analysis to context string for LLM prompts.

    This is what NAVI injects into its prompts when UI screenshots
    are provided.
    """
    return analysis.to_context_string()
