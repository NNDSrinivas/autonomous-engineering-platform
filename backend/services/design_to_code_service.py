"""
Design-to-Code Pipeline Service

Converts visual designs (images, Figma, screenshots) into React components
using multi-modal vision AI.

Capabilities:
- Parse design images to extract components, layout, colors
- Generate React/Next.js components with Tailwind CSS
- Extract color palettes and create theme configurations
- Generate responsive layouts from design specifications
- Support for all vision-capable LLMs (GPT-4V, Claude, Gemini)

Supports BYOK (Bring Your Own Key) for all providers.
"""

import os
import re
import json
import base64
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from pathlib import Path

import httpx


logger = logging.getLogger(__name__)


class DesignFormat(Enum):
    """Supported design input formats"""
    IMAGE = "image"  # PNG, JPG, WebP
    FIGMA = "figma"  # Figma URL
    SCREENSHOT = "screenshot"  # Screenshot file
    SKETCH = "sketch"  # Sketch file
    XD = "xd"  # Adobe XD file


class ComponentFramework(Enum):
    """Target component frameworks"""
    REACT = "react"
    NEXTJS = "nextjs"
    VUE = "vue"
    SVELTE = "svelte"
    HTML = "html"


class StylingApproach(Enum):
    """CSS styling approaches"""
    TAILWIND = "tailwind"
    CSS_MODULES = "css_modules"
    STYLED_COMPONENTS = "styled_components"
    EMOTION = "emotion"
    PLAIN_CSS = "plain_css"


@dataclass
class ColorPalette:
    """Extracted color palette from design"""
    primary: str
    secondary: str
    accent: str
    background: str
    surface: str
    text_primary: str
    text_secondary: str
    success: str
    warning: str
    error: str
    additional: List[str] = field(default_factory=list)


@dataclass
class ComponentSpec:
    """Specification for a generated component"""
    name: str
    description: str
    props: Dict[str, str]  # prop_name -> type
    children: List[str]  # Child component names
    responsive_breakpoints: Dict[str, str]  # breakpoint -> layout
    accessibility: Dict[str, str]  # aria labels, roles


@dataclass
class DesignAnalysis:
    """Complete analysis of a design"""
    components: List[ComponentSpec]
    color_palette: ColorPalette
    typography: Dict[str, Any]
    layout: Dict[str, Any]
    spacing: Dict[str, str]
    breakpoints: Dict[str, int]
    assets: List[Dict[str, str]]  # icons, images
    interactions: List[Dict[str, Any]]  # hover, click states


@dataclass
class GeneratedComponent:
    """A generated component with code"""
    name: str
    filename: str
    code: str
    styles: Optional[str] = None
    test: Optional[str] = None
    story: Optional[str] = None  # Storybook story


DESIGN_ANALYSIS_PROMPT = """You are an expert UI/UX designer and frontend developer. Analyze this design image and extract:

1. **Components**: Identify all UI components (buttons, cards, forms, navigation, etc.)
2. **Color Palette**: Extract all colors used (primary, secondary, accent, background, text, etc.)
3. **Typography**: Font families, sizes, weights, line heights
4. **Layout**: Grid system, spacing, alignment
5. **Breakpoints**: Responsive behavior hints
6. **Interactions**: Hover states, animations, transitions

Output Format (JSON):
{
    "components": [
        {
            "name": "HeroSection",
            "description": "Full-width hero with background image and CTA",
            "type": "section",
            "children": ["Heading", "Paragraph", "Button"],
            "props": {"backgroundImage": "string", "title": "string"},
            "layout": "flex-col items-center justify-center"
        }
    ],
    "color_palette": {
        "primary": "#3B82F6",
        "secondary": "#10B981",
        "accent": "#F59E0B",
        "background": "#FFFFFF",
        "surface": "#F3F4F6",
        "text_primary": "#111827",
        "text_secondary": "#6B7280",
        "success": "#10B981",
        "warning": "#F59E0B",
        "error": "#EF4444"
    },
    "typography": {
        "font_family": "Inter, sans-serif",
        "heading_sizes": {"h1": "48px", "h2": "36px", "h3": "24px"},
        "body_sizes": {"lg": "18px", "base": "16px", "sm": "14px"}
    },
    "layout": {
        "max_width": "1280px",
        "columns": 12,
        "gutter": "24px",
        "padding": {"desktop": "64px", "mobile": "24px"}
    },
    "spacing": {
        "xs": "4px", "sm": "8px", "md": "16px", "lg": "24px", "xl": "48px"
    }
}"""

COMPONENT_GENERATION_PROMPT = """You are an expert React developer. Generate a complete, production-ready React component based on this design analysis.

Requirements:
1. Use TypeScript with proper type definitions
2. Use Tailwind CSS for styling
3. Make it fully responsive
4. Include accessibility (ARIA labels, keyboard navigation)
5. Include prop types and default values
6. Follow React best practices (hooks, functional components)

Component to generate: {component_name}
Design specification: {component_spec}
Color palette: {color_palette}
Typography: {typography}

Generate the complete component code with:
1. TypeScript interface for props
2. Functional component with proper hooks
3. Tailwind classes for all styles
4. Responsive variants (sm, md, lg, xl)
5. Accessibility attributes

Output only the code, no explanations."""


class DesignToCodeService:
    """
    Service for converting designs to React components.

    Supports all vision-capable LLMs with BYOK:
    - OpenAI GPT-4 Vision
    - Anthropic Claude 3 Vision
    - Google Gemini Pro Vision
    """

    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        framework: ComponentFramework = ComponentFramework.NEXTJS,
        styling: StylingApproach = StylingApproach.TAILWIND,
    ):
        """
        Initialize the design-to-code service.

        Args:
            provider: Vision LLM provider (openai, anthropic, google)
            model: Model name (defaults to provider's vision model)
            api_key: Optional BYOK API key
            framework: Target component framework
            styling: CSS styling approach
        """
        self.provider = provider.lower()
        self.api_key = api_key or self._get_api_key()
        self.framework = framework
        self.styling = styling

        # Set default vision models
        self.model = model or self._get_default_model()

        self.client = httpx.AsyncClient(timeout=120)

    def _get_api_key(self) -> str:
        """Get API key from environment"""
        env_vars = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GOOGLE_API_KEY",
        }
        return os.environ.get(env_vars.get(self.provider, "OPENAI_API_KEY"), "")

    def _get_default_model(self) -> str:
        """Get default vision model for provider"""
        defaults = {
            "openai": "gpt-4o",
            "anthropic": "claude-sonnet-4-20250514",
            "google": "gemini-2.0-flash-exp",
        }
        return defaults.get(self.provider, "gpt-4o")

    async def analyze_design(
        self,
        image_source: str,
        source_type: DesignFormat = DesignFormat.IMAGE,
    ) -> DesignAnalysis:
        """
        Analyze a design image to extract components and styles.

        Args:
            image_source: Path to image, URL, or base64 data
            source_type: Type of design source

        Returns:
            DesignAnalysis with extracted information
        """
        logger.info(f"Analyzing design from {source_type.value}...")

        # Get image data
        image_data = await self._get_image_data(image_source, source_type)

        # Call vision AI
        response = await self._call_vision_api(
            prompt=DESIGN_ANALYSIS_PROMPT,
            image_data=image_data,
        )

        # Parse the response
        analysis = self._parse_analysis_response(response)

        logger.info(f"Extracted {len(analysis.components)} components from design")

        return analysis

    async def generate_component(
        self,
        component_spec: ComponentSpec,
        color_palette: ColorPalette,
        typography: Dict[str, Any],
    ) -> GeneratedComponent:
        """
        Generate a React component from specification.

        Args:
            component_spec: The component specification
            color_palette: Color palette to use
            typography: Typography configuration

        Returns:
            GeneratedComponent with code
        """
        logger.info(f"Generating component: {component_spec.name}")

        prompt = COMPONENT_GENERATION_PROMPT.format(
            component_name=component_spec.name,
            component_spec=json.dumps({
                "name": component_spec.name,
                "description": component_spec.description,
                "props": component_spec.props,
                "children": component_spec.children,
            }),
            color_palette=json.dumps({
                "primary": color_palette.primary,
                "secondary": color_palette.secondary,
                "accent": color_palette.accent,
                "background": color_palette.background,
                "text_primary": color_palette.text_primary,
            }),
            typography=json.dumps(typography),
        )

        # Call LLM for code generation
        code = await self._call_text_api(prompt)

        # Extract component code from response
        code = self._extract_code(code)

        # Generate filename
        filename = self._to_filename(component_spec.name)

        return GeneratedComponent(
            name=component_spec.name,
            filename=filename,
            code=code,
        )

    async def design_to_components(
        self,
        image_source: str,
        output_dir: str,
        source_type: DesignFormat = DesignFormat.IMAGE,
    ) -> List[GeneratedComponent]:
        """
        Complete pipeline: analyze design and generate all components.

        Args:
            image_source: Path to design image
            output_dir: Directory to write components
            source_type: Type of design source

        Returns:
            List of generated components
        """
        logger.info("Starting design-to-code pipeline...")

        # Step 1: Analyze design
        analysis = await self.analyze_design(image_source, source_type)

        # Step 2: Generate each component
        components = []
        for spec in analysis.components:
            component = await self.generate_component(
                spec,
                analysis.color_palette,
                analysis.typography,
            )
            components.append(component)

            # Write to file
            output_path = Path(output_dir) / component.filename
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(component.code)

            logger.info(f"Generated: {component.filename}")

        # Step 3: Generate theme configuration
        theme_config = self._generate_theme_config(analysis)
        theme_path = Path(output_dir) / "theme.ts"
        theme_path.write_text(theme_config)

        logger.info(f"Generated {len(components)} components and theme config")

        return components

    async def extract_color_palette(
        self,
        image_source: str,
    ) -> ColorPalette:
        """
        Extract just the color palette from a design.

        Args:
            image_source: Path to design image

        Returns:
            ColorPalette extracted from design
        """
        image_data = await self._get_image_data(image_source, DesignFormat.IMAGE)

        prompt = """Analyze this design and extract the complete color palette.

Output a JSON object with these exact keys:
{
    "primary": "#hex",
    "secondary": "#hex",
    "accent": "#hex",
    "background": "#hex",
    "surface": "#hex",
    "text_primary": "#hex",
    "text_secondary": "#hex",
    "success": "#hex",
    "warning": "#hex",
    "error": "#hex"
}

Only output the JSON, nothing else."""

        response = await self._call_vision_api(prompt, image_data)

        # Parse colors
        json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
        if json_match:
            colors = json.loads(json_match.group())
            return ColorPalette(**colors)

        # Default palette if extraction fails
        return ColorPalette(
            primary="#3B82F6",
            secondary="#10B981",
            accent="#F59E0B",
            background="#FFFFFF",
            surface="#F3F4F6",
            text_primary="#111827",
            text_secondary="#6B7280",
            success="#10B981",
            warning="#F59E0B",
            error="#EF4444",
        )

    async def _get_image_data(
        self,
        source: str,
        source_type: DesignFormat,
    ) -> str:
        """Get base64 image data from various sources"""

        if source_type == DesignFormat.FIGMA:
            # Fetch from Figma API
            return await self._fetch_figma_image(source)

        if source.startswith("data:"):
            # Already base64
            return source.split(",")[1] if "," in source else source

        if source.startswith("http"):
            # Fetch from URL
            response = await self.client.get(source)
            response.raise_for_status()
            return base64.b64encode(response.content).decode()

        # Local file
        path = Path(source)
        if path.exists():
            return base64.b64encode(path.read_bytes()).decode()

        raise ValueError(f"Cannot load image from: {source}")

    async def _fetch_figma_image(self, figma_url: str) -> str:
        """Fetch design image from Figma API"""
        figma_token = os.environ.get("FIGMA_ACCESS_TOKEN", "")
        if not figma_token:
            raise ValueError("FIGMA_ACCESS_TOKEN not set")

        # Parse Figma URL to get file key and node ID
        # Example: https://www.figma.com/file/abc123/Design?node-id=1-2
        match = re.search(r'/file/([^/]+)', figma_url)
        if not match:
            raise ValueError("Invalid Figma URL")

        file_key = match.group(1)
        node_match = re.search(r'node-id=([^&]+)', figma_url)
        node_id = node_match.group(1).replace('-', ':') if node_match else ""

        # Get image from Figma
        headers = {"X-Figma-Token": figma_token}
        params = {"ids": node_id, "format": "png", "scale": 2}

        response = await self.client.get(
            f"https://api.figma.com/v1/images/{file_key}",
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        data = response.json()

        # Get the image URL and fetch it
        image_url = data.get("images", {}).get(node_id)
        if not image_url:
            raise ValueError("Could not get image from Figma")

        image_response = await self.client.get(image_url)
        return base64.b64encode(image_response.content).decode()

    async def _call_vision_api(self, prompt: str, image_data: str) -> str:
        """Call vision API based on provider"""

        if self.provider == "openai":
            return await self._call_openai_vision(prompt, image_data)
        elif self.provider == "anthropic":
            return await self._call_anthropic_vision(prompt, image_data)
        elif self.provider == "google":
            return await self._call_google_vision(prompt, image_data)
        else:
            raise ValueError(f"Unsupported vision provider: {self.provider}")

    async def _call_openai_vision(self, prompt: str, image_data: str) -> str:
        """Call OpenAI GPT-4 Vision API"""
        response = await self.client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_data}",
                                },
                            },
                        ],
                    }
                ],
                "max_tokens": 4096,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def _call_anthropic_vision(self, prompt: str, image_data: str) -> str:
        """Call Anthropic Claude Vision API"""
        response = await self.client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 4096,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_data,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]

    async def _call_google_vision(self, prompt: str, image_data: str) -> str:
        """Call Google Gemini Vision API"""
        response = await self.client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            params={"key": self.api_key},
            json={
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": "image/png",
                                    "data": image_data,
                                },
                            },
                        ],
                    }
                ],
                "generationConfig": {"maxOutputTokens": 4096},
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    async def _call_text_api(self, prompt: str) -> str:
        """Call text generation API (for code generation)"""
        from backend.services.llm_client import LLMClient

        client = LLMClient(
            provider=self.provider,
            model=self.model,
            api_key=self.api_key,
            temperature=0.3,
            max_tokens=4096,
        )

        response = await client.complete(prompt)
        return response.content

    def _parse_analysis_response(self, response: str) -> DesignAnalysis:
        """Parse vision API response into DesignAnalysis"""

        # Extract JSON from response
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            json_str = response[json_start:json_end]

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # Return minimal analysis if parsing fails
            return DesignAnalysis(
                components=[],
                color_palette=ColorPalette(
                    primary="#3B82F6", secondary="#10B981", accent="#F59E0B",
                    background="#FFFFFF", surface="#F3F4F6",
                    text_primary="#111827", text_secondary="#6B7280",
                    success="#10B981", warning="#F59E0B", error="#EF4444",
                ),
                typography={},
                layout={},
                spacing={},
                breakpoints={},
                assets=[],
                interactions=[],
            )

        # Parse components
        components = []
        for comp_data in data.get("components", []):
            components.append(ComponentSpec(
                name=comp_data.get("name", "Component"),
                description=comp_data.get("description", ""),
                props=comp_data.get("props", {}),
                children=comp_data.get("children", []),
                responsive_breakpoints=comp_data.get("responsive_breakpoints", {}),
                accessibility=comp_data.get("accessibility", {}),
            ))

        # Parse color palette
        colors = data.get("color_palette", {})
        color_palette = ColorPalette(
            primary=colors.get("primary", "#3B82F6"),
            secondary=colors.get("secondary", "#10B981"),
            accent=colors.get("accent", "#F59E0B"),
            background=colors.get("background", "#FFFFFF"),
            surface=colors.get("surface", "#F3F4F6"),
            text_primary=colors.get("text_primary", "#111827"),
            text_secondary=colors.get("text_secondary", "#6B7280"),
            success=colors.get("success", "#10B981"),
            warning=colors.get("warning", "#F59E0B"),
            error=colors.get("error", "#EF4444"),
        )

        return DesignAnalysis(
            components=components,
            color_palette=color_palette,
            typography=data.get("typography", {}),
            layout=data.get("layout", {}),
            spacing=data.get("spacing", {}),
            breakpoints=data.get("breakpoints", {}),
            assets=data.get("assets", []),
            interactions=data.get("interactions", []),
        )

    def _extract_code(self, response: str) -> str:
        """Extract code from LLM response"""
        # Try to extract from code block
        code_match = re.search(r'```(?:tsx?|jsx?|typescript|javascript)?\s*(.*?)\s*```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        return response.strip()

    def _to_filename(self, component_name: str) -> str:
        """Convert component name to filename"""
        return f"{component_name}.tsx"

    def _generate_theme_config(self, analysis: DesignAnalysis) -> str:
        """Generate Tailwind/theme configuration"""
        palette = analysis.color_palette

        return f'''// Generated theme configuration
export const colors = {{
  primary: "{palette.primary}",
  secondary: "{palette.secondary}",
  accent: "{palette.accent}",
  background: "{palette.background}",
  surface: "{palette.surface}",
  text: {{
    primary: "{palette.text_primary}",
    secondary: "{palette.text_secondary}",
  }},
  status: {{
    success: "{palette.success}",
    warning: "{palette.warning}",
    error: "{palette.error}",
  }},
}};

export const typography = {json.dumps(analysis.typography, indent=2)};

export const spacing = {json.dumps(analysis.spacing, indent=2)};

export const breakpoints = {json.dumps(analysis.breakpoints, indent=2)};

// Tailwind extend configuration
export const tailwindExtend = {{
  colors,
  fontFamily: {{
    sans: [typography.font_family || "Inter", "sans-serif"],
  }},
}};
'''


async def design_to_code(
    image_path: str,
    output_dir: str,
    provider: str = "openai",
    api_key: Optional[str] = None,
) -> List[GeneratedComponent]:
    """
    Convenience function for design-to-code conversion.

    Args:
        image_path: Path to design image
        output_dir: Directory for generated components
        provider: Vision AI provider
        api_key: Optional BYOK key

    Returns:
        List of generated components
    """
    service = DesignToCodeService(
        provider=provider,
        api_key=api_key,
    )
    return await service.design_to_components(image_path, output_dir)
