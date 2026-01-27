"""
Documentation generation tools for NAVI agent.

Provides tools to generate various types of documentation:
- README files
- API documentation (OpenAPI, Markdown)
- Component documentation
- Architecture documentation with diagrams
- Code comments
- Changelogs

Works dynamically for any project type without hardcoding.
"""

import os
import re
import json
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


def _get_command_env() -> dict:
    """
    Get environment for command execution with nvm compatibility fixes.
    Removes npm_config_prefix which conflicts with nvm.
    """
    env = os.environ.copy()
    env.pop("npm_config_prefix", None)  # Remove to fix nvm compatibility
    env["SHELL"] = env.get("SHELL", "/bin/bash")
    return env


# Documentation templates
README_TEMPLATE = '''# {project_name}

{badges}

{description}

## Table of Contents

{toc}

## Features

{features}

## Installation

{installation}

## Usage

{usage}

## Configuration

{configuration}

## API Reference

{api_reference}

## Development

{development}

## Testing

{testing}

## Deployment

{deployment}

## Contributing

{contributing}

## License

{license}
'''

API_DOC_TEMPLATE = '''# {api_name} API Documentation

{description}

## Base URL

```
{base_url}
```

## Authentication

{authentication}

## Endpoints

{endpoints}

## Error Handling

{error_handling}

## Rate Limiting

{rate_limiting}

## Examples

{examples}
'''

COMPONENT_DOC_TEMPLATE = '''# {component_name}

{description}

## Props

{props}

## Usage

{usage}

## Examples

{examples}

## Styling

{styling}

## Accessibility

{accessibility}

## Related Components

{related}
'''

ARCHITECTURE_DOC_TEMPLATE = '''# {project_name} Architecture

## Overview

{overview}

## System Components

{components}

## Data Flow

{data_flow}

## Technology Stack

{tech_stack}

## Infrastructure

{infrastructure}

## Security

{security}

## Scalability

{scalability}

## Diagrams

{diagrams}
'''


@dataclass
class ProjectInfo:
    """Information extracted from a project."""
    name: str
    description: Optional[str]
    language: str
    framework: Optional[str]
    version: Optional[str]
    dependencies: Dict[str, str]
    scripts: Dict[str, str]
    entry_points: List[str]
    has_tests: bool
    has_docker: bool
    has_ci: bool


async def generate_readme(
    context: Dict[str, Any],
    workspace_path: str,
    include_badges: bool = True,
    include_toc: bool = True,
    style: str = "standard",
) -> ToolResult:
    """
    Generate a comprehensive README.md for a project.

    Analyzes the project structure, dependencies, and scripts to generate
    relevant documentation.

    Args:
        workspace_path: Path to the project root
        include_badges: Include status badges (default True)
        include_toc: Include table of contents (default True)
        style: Documentation style (standard, minimal, detailed)

    Returns:
        ToolResult with generated README content
    """
    logger.info("generate_readme", workspace_path=workspace_path, style=style)

    if not os.path.exists(workspace_path):
        return ToolResult(output=f"Directory not found: {workspace_path}", sources=[])

    # Extract project information
    project_info = _extract_project_info(workspace_path)

    # Generate sections
    badges = _generate_badges(project_info) if include_badges else ""
    description = _generate_description(project_info)
    toc = _generate_toc(style) if include_toc else ""
    features = _generate_features_section(project_info)
    installation = _generate_installation(project_info)
    usage = _generate_usage(project_info)
    configuration = _generate_configuration(workspace_path)
    api_reference = _generate_api_reference_brief(workspace_path, project_info)
    development = _generate_development_section(project_info)
    testing = _generate_testing_section(project_info)
    deployment = _generate_deployment_section(workspace_path, project_info)
    contributing = _generate_contributing()
    license_section = _generate_license(workspace_path)

    # Build README
    readme_content = README_TEMPLATE.format(
        project_name=project_info.name,
        badges=badges,
        description=description,
        toc=toc,
        features=features,
        installation=installation,
        usage=usage,
        configuration=configuration,
        api_reference=api_reference,
        development=development,
        testing=testing,
        deployment=deployment,
        contributing=contributing,
        license=license_section,
    )

    # Clean up empty sections
    readme_content = _clean_empty_sections(readme_content)

    lines = ["## Generated README.md\n"]
    lines.append(f"**Project**: {project_info.name}")
    lines.append(f"**Language**: {project_info.language}")
    if project_info.framework:
        lines.append(f"**Framework**: {project_info.framework}")
    lines.append(f"\n**Generated Content**:")
    lines.append("```markdown")
    lines.append(readme_content)
    lines.append("```")

    lines.append(f"\n**Next Steps**:")
    lines.append("1. Save to `README.md`")
    lines.append("2. Review and customize content")
    lines.append("3. Add project-specific details")
    lines.append("4. Update badges with actual URLs")

    return ToolResult(output="\n".join(lines), sources=[])


async def generate_api_docs(
    context: Dict[str, Any],
    workspace_path: str,
    format: str = "markdown",
    output_path: Optional[str] = None,
) -> ToolResult:
    """
    Generate API documentation from source code.

    Supports Express, FastAPI, Django, NestJS, and other frameworks.

    Args:
        workspace_path: Path to the project root
        format: Output format (markdown, openapi, html)
        output_path: Optional path to save documentation

    Returns:
        ToolResult with generated API documentation
    """
    logger.info("generate_api_docs", workspace_path=workspace_path, format=format)

    if not os.path.exists(workspace_path):
        return ToolResult(output=f"Directory not found: {workspace_path}", sources=[])

    project_info = _extract_project_info(workspace_path)

    # Find API routes
    routes = _extract_api_routes(workspace_path, project_info)

    if not routes:
        return ToolResult(
            output="No API routes found.\n\n"
                   "Make sure your API follows standard patterns:\n"
                   "- Express: app.get(), router.post(), etc.\n"
                   "- FastAPI: @app.get(), @router.post(), etc.\n"
                   "- Next.js: app/api/*/route.ts",
            sources=[],
        )

    # Generate documentation based on format
    if format == "openapi":
        doc_content = _generate_openapi_spec(routes, project_info)
        content_type = "yaml"
    elif format == "html":
        doc_content = _generate_html_api_docs(routes, project_info)
        content_type = "html"
    else:
        doc_content = _generate_markdown_api_docs(routes, project_info)
        content_type = "markdown"

    lines = [f"## Generated API Documentation ({format})\n"]
    lines.append(f"**Endpoints Found**: {len(routes)}")
    lines.append(f"**Framework**: {project_info.framework or 'Unknown'}")
    lines.append(f"\n**Generated Content**:")
    lines.append(f"```{content_type}")
    lines.append(doc_content)
    lines.append("```")

    return ToolResult(output="\n".join(lines), sources=[])


async def generate_component_docs(
    context: Dict[str, Any],
    workspace_path: str,
    component_path: Optional[str] = None,
) -> ToolResult:
    """
    Generate documentation for React/Vue components.

    Extracts props, events, slots, and usage examples.

    Args:
        workspace_path: Path to the project root
        component_path: Optional path to specific component

    Returns:
        ToolResult with generated component documentation
    """
    logger.info("generate_component_docs", workspace_path=workspace_path)

    if not os.path.exists(workspace_path):
        return ToolResult(output=f"Directory not found: {workspace_path}", sources=[])

    # Find components
    if component_path:
        components = [component_path]
    else:
        components = _find_components(workspace_path)

    if not components:
        return ToolResult(
            output="No components found.\n\n"
                   "Looking for:\n"
                   "- React: .tsx files in components/ or src/components/\n"
                   "- Vue: .vue files in components/ or src/components/",
            sources=[],
        )

    docs = []
    for comp_path in components[:10]:  # Limit to 10 components
        full_path = os.path.join(workspace_path, comp_path) if not os.path.isabs(comp_path) else comp_path
        if os.path.exists(full_path):
            doc = _generate_single_component_doc(full_path)
            if doc:
                docs.append(doc)

    if not docs:
        return ToolResult(output="Could not extract documentation from components.", sources=[])

    lines = [f"## Generated Component Documentation\n"]
    lines.append(f"**Components Found**: {len(docs)}")
    for doc in docs:
        lines.append(f"\n---\n")
        lines.append(doc)

    return ToolResult(output="\n".join(lines), sources=[])


async def generate_architecture_doc(
    context: Dict[str, Any],
    workspace_path: str,
    include_diagrams: bool = True,
) -> ToolResult:
    """
    Generate architecture documentation for a project.

    Creates system overview, component diagrams, and data flow documentation.

    Args:
        workspace_path: Path to the project root
        include_diagrams: Include Mermaid diagrams (default True)

    Returns:
        ToolResult with generated architecture documentation
    """
    logger.info("generate_architecture_doc", workspace_path=workspace_path)

    if not os.path.exists(workspace_path):
        return ToolResult(output=f"Directory not found: {workspace_path}", sources=[])

    project_info = _extract_project_info(workspace_path)

    # Analyze project structure
    structure = _analyze_project_structure(workspace_path)

    # Generate documentation sections
    overview = _generate_architecture_overview(project_info, structure)
    components = _generate_components_section(structure)
    data_flow = _generate_data_flow_section(workspace_path, project_info)
    tech_stack = _generate_tech_stack_section(project_info)
    infrastructure = _generate_infrastructure_section(workspace_path)
    security = _generate_security_section(workspace_path)
    scalability = _generate_scalability_section(project_info)

    diagrams = ""
    if include_diagrams:
        diagrams = _generate_architecture_diagrams(structure, project_info)

    # Build documentation
    doc_content = ARCHITECTURE_DOC_TEMPLATE.format(
        project_name=project_info.name,
        overview=overview,
        components=components,
        data_flow=data_flow,
        tech_stack=tech_stack,
        infrastructure=infrastructure,
        security=security,
        scalability=scalability,
        diagrams=diagrams,
    )

    lines = ["## Generated Architecture Documentation\n"]
    lines.append(f"**Project**: {project_info.name}")
    lines.append(f"\n**Generated Content**:")
    lines.append("```markdown")
    lines.append(doc_content)
    lines.append("```")

    return ToolResult(output="\n".join(lines), sources=[])


async def generate_code_comments(
    context: Dict[str, Any],
    file_path: str,
    workspace_path: Optional[str] = None,
    style: str = "jsdoc",
) -> ToolResult:
    """
    Generate documentation comments for a code file.

    Args:
        file_path: Path to the source file
        workspace_path: Project root directory
        style: Comment style (jsdoc, docstring, rustdoc)

    Returns:
        ToolResult with suggested comments
    """
    logger.info("generate_code_comments", file_path=file_path, style=style)

    # Resolve path
    if workspace_path and not os.path.isabs(file_path):
        full_path = os.path.join(workspace_path, file_path)
    else:
        full_path = file_path

    if not os.path.exists(full_path):
        return ToolResult(output=f"File not found: {full_path}", sources=[])

    with open(full_path, "r") as f:
        source_code = f.read()

    # Detect language
    _, ext = os.path.splitext(full_path)
    language = _detect_language(ext)

    if not language:
        return ToolResult(output=f"Unsupported file type: {ext}", sources=[])

    # Generate comments
    comments = _generate_comments_for_file(source_code, language, style)

    lines = [f"## Generated Documentation Comments\n"]
    lines.append(f"**File**: {file_path}")
    lines.append(f"**Style**: {style}")
    lines.append(f"**Language**: {language}")
    lines.append(f"\n**Suggested Comments**:")

    for comment in comments:
        lines.append(f"\n### Line {comment['line']}: `{comment['name']}`")
        lines.append(f"```{language}")
        lines.append(comment['comment'])
        lines.append("```")

    return ToolResult(output="\n".join(lines), sources=[])


async def generate_changelog(
    context: Dict[str, Any],
    workspace_path: str,
    version: Optional[str] = None,
    since_tag: Optional[str] = None,
) -> ToolResult:
    """
    Generate a changelog from git history.

    Args:
        workspace_path: Path to the project root
        version: Version number for the release
        since_tag: Generate changes since this tag

    Returns:
        ToolResult with generated changelog
    """
    logger.info("generate_changelog", workspace_path=workspace_path)

    if not os.path.exists(workspace_path):
        return ToolResult(output=f"Directory not found: {workspace_path}", sources=[])

    # Get git log
    import subprocess

    try:
        if since_tag:
            cmd = ["git", "log", f"{since_tag}..HEAD", "--pretty=format:%s|%h|%an|%ad", "--date=short"]
        else:
            cmd = ["git", "log", "-50", "--pretty=format:%s|%h|%an|%ad", "--date=short"]

        result = subprocess.run(cmd, cwd=workspace_path, capture_output=True, text=True, env=_get_command_env())

        if result.returncode != 0:
            return ToolResult(
                output="Failed to read git history. Make sure you're in a git repository.",
                sources=[],
            )

        commits = result.stdout.strip().split("\n")
    except Exception as e:
        return ToolResult(output=f"Error reading git history: {e}", sources=[])

    # Categorize commits
    categories = {
        "Features": [],
        "Bug Fixes": [],
        "Performance": [],
        "Documentation": [],
        "Refactoring": [],
        "Tests": [],
        "Chores": [],
        "Other": [],
    }

    for commit_line in commits:
        if not commit_line:
            continue
        parts = commit_line.split("|")
        if len(parts) < 4:
            continue

        message, hash_val, author, date = parts[0], parts[1], parts[2], parts[3]

        # Categorize based on conventional commits
        msg_lower = message.lower()
        if msg_lower.startswith("feat"):
            categories["Features"].append((message, hash_val, author, date))
        elif msg_lower.startswith("fix"):
            categories["Bug Fixes"].append((message, hash_val, author, date))
        elif msg_lower.startswith("perf"):
            categories["Performance"].append((message, hash_val, author, date))
        elif msg_lower.startswith("docs"):
            categories["Documentation"].append((message, hash_val, author, date))
        elif msg_lower.startswith("refactor"):
            categories["Refactoring"].append((message, hash_val, author, date))
        elif msg_lower.startswith("test"):
            categories["Tests"].append((message, hash_val, author, date))
        elif msg_lower.startswith("chore"):
            categories["Chores"].append((message, hash_val, author, date))
        else:
            categories["Other"].append((message, hash_val, author, date))

    # Generate changelog
    version_str = version or "Unreleased"
    date_str = datetime.now().strftime("%Y-%m-%d")

    changelog = [f"# Changelog\n"]
    changelog.append(f"## [{version_str}] - {date_str}\n")

    for category, commits in categories.items():
        if commits:
            changelog.append(f"### {category}\n")
            for msg, hash_val, author, date in commits:
                # Clean up commit message
                clean_msg = re.sub(r"^(feat|fix|docs|perf|refactor|test|chore)(\(.+\))?:\s*", "", msg)
                changelog.append(f"- {clean_msg} ({hash_val})")
            changelog.append("")

    changelog_content = "\n".join(changelog)

    lines = ["## Generated Changelog\n"]
    lines.append(f"**Version**: {version_str}")
    lines.append(f"**Commits Analyzed**: {len(commits)}")
    lines.append(f"\n**Generated Content**:")
    lines.append("```markdown")
    lines.append(changelog_content)
    lines.append("```")

    return ToolResult(output="\n".join(lines), sources=[])


# Helper functions

def _extract_project_info(workspace_path: str) -> ProjectInfo:
    """Extract project information from configuration files."""
    name = os.path.basename(workspace_path)
    description = None
    language = "javascript"
    framework = None
    version = None
    dependencies = {}
    scripts = {}
    entry_points = []
    has_tests = False
    has_docker = False
    has_ci = False

    # Check package.json
    package_json_path = os.path.join(workspace_path, "package.json")
    if os.path.exists(package_json_path):
        try:
            with open(package_json_path, "r") as f:
                pkg = json.load(f)
                name = pkg.get("name", name)
                description = pkg.get("description")
                version = pkg.get("version")
                dependencies = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                scripts = pkg.get("scripts", {})

                # Detect framework
                if "next" in dependencies:
                    framework = "Next.js"
                elif "react" in dependencies:
                    framework = "React"
                elif "vue" in dependencies:
                    framework = "Vue.js"
                elif "express" in dependencies:
                    framework = "Express"
                elif "@nestjs/core" in dependencies:
                    framework = "NestJS"

                # Check for TypeScript
                if "typescript" in dependencies:
                    language = "typescript"

                # Check for tests
                has_tests = "jest" in dependencies or "vitest" in dependencies or "test" in scripts
        except (json.JSONDecodeError, IOError):
            pass

    # Check for Python
    requirements_path = os.path.join(workspace_path, "requirements.txt")
    pyproject_path = os.path.join(workspace_path, "pyproject.toml")

    if os.path.exists(requirements_path) or os.path.exists(pyproject_path):
        language = "python"
        if os.path.exists(requirements_path):
            try:
                with open(requirements_path, "r") as f:
                    content = f.read().lower()
                    if "fastapi" in content:
                        framework = "FastAPI"
                    elif "django" in content:
                        framework = "Django"
                    elif "flask" in content:
                        framework = "Flask"
                    has_tests = "pytest" in content
            except IOError:
                pass

    # Check for Docker
    has_docker = os.path.exists(os.path.join(workspace_path, "Dockerfile")) or \
                 os.path.exists(os.path.join(workspace_path, "docker-compose.yml"))

    # Check for CI
    has_ci = os.path.exists(os.path.join(workspace_path, ".github", "workflows")) or \
             os.path.exists(os.path.join(workspace_path, ".gitlab-ci.yml"))

    return ProjectInfo(
        name=name,
        description=description,
        language=language,
        framework=framework,
        version=version,
        dependencies=dependencies,
        scripts=scripts,
        entry_points=entry_points,
        has_tests=has_tests,
        has_docker=has_docker,
        has_ci=has_ci,
    )


def _generate_badges(project_info: ProjectInfo) -> str:
    """Generate status badges."""
    badges = []

    if project_info.version:
        badges.append(f"![Version](https://img.shields.io/badge/version-{project_info.version}-blue)")

    if project_info.language == "typescript":
        badges.append("![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?logo=typescript&logoColor=white)")
    elif project_info.language == "python":
        badges.append("![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)")

    if project_info.framework:
        badge_name = project_info.framework.replace(".", "").replace(" ", "")
        badges.append(f"![{project_info.framework}](https://img.shields.io/badge/{badge_name}-000000?logo={badge_name.lower()}&logoColor=white)")

    if project_info.has_tests:
        badges.append("![Tests](https://img.shields.io/badge/tests-passing-green)")

    return " ".join(badges)


def _generate_description(project_info: ProjectInfo) -> str:
    """Generate project description."""
    if project_info.description:
        return project_info.description

    return f"A {project_info.framework or project_info.language} project."


def _generate_toc(style: str) -> str:
    """Generate table of contents."""
    return """- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)"""


def _generate_features_section(project_info: ProjectInfo) -> str:
    """Generate features section."""
    features = []

    if project_info.framework:
        features.append(f"Built with {project_info.framework}")

    if project_info.language == "typescript":
        features.append("Full TypeScript support")

    if project_info.has_tests:
        features.append("Comprehensive test suite")

    if project_info.has_docker:
        features.append("Docker support for containerized deployment")

    if project_info.has_ci:
        features.append("CI/CD pipeline configured")

    if not features:
        features = ["TODO: Add features"]

    return "\n".join(f"- {f}" for f in features)


def _generate_installation(project_info: ProjectInfo) -> str:
    """Generate installation instructions."""
    if project_info.language in ("javascript", "typescript"):
        return """```bash
# Clone the repository
git clone <repository-url>
cd {name}

# Install dependencies
npm install
# or
yarn install
# or
pnpm install
```""".format(name=project_info.name)

    elif project_info.language == "python":
        return """```bash
# Clone the repository
git clone <repository-url>
cd {name}

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate

# Install dependencies
pip install -r requirements.txt
```""".format(name=project_info.name)

    return "TODO: Add installation instructions"


def _generate_usage(project_info: ProjectInfo) -> str:
    """Generate usage instructions."""
    if project_info.scripts:
        lines = []
        if "dev" in project_info.scripts:
            lines.append("```bash\n# Development server\nnpm run dev\n```")
        if "build" in project_info.scripts:
            lines.append("```bash\n# Build for production\nnpm run build\n```")
        if "start" in project_info.scripts:
            lines.append("```bash\n# Start production server\nnpm start\n```")
        return "\n\n".join(lines) if lines else "TODO: Add usage instructions"

    return "TODO: Add usage instructions"


def _generate_configuration(workspace_path: str) -> str:
    """Generate configuration section."""
    env_example = os.path.join(workspace_path, ".env.example")
    if os.path.exists(env_example):
        try:
            with open(env_example, "r") as f:
                content = f.read()
            return f"Create a `.env` file with the following variables:\n\n```env\n{content}\n```"
        except IOError:
            pass

    # Check for config files
    config_files = [".env.example", "config.json", "config.yaml", "settings.py"]
    found = [f for f in config_files if os.path.exists(os.path.join(workspace_path, f))]

    if found:
        return f"Configuration files: {', '.join(found)}\n\nSee the respective files for configuration options."

    return "TODO: Add configuration details"


def _generate_api_reference_brief(workspace_path: str, project_info: ProjectInfo) -> str:
    """Generate brief API reference."""
    if project_info.framework in ("Express", "FastAPI", "NestJS", "Next.js"):
        return "See [API Documentation](./docs/api.md) for detailed endpoint documentation."
    return "TODO: Add API reference"


def _generate_development_section(project_info: ProjectInfo) -> str:
    """Generate development section."""
    lines = ["### Prerequisites\n"]

    if project_info.language in ("javascript", "typescript"):
        lines.append("- Node.js 18+")
        lines.append("- npm/yarn/pnpm")
    elif project_info.language == "python":
        lines.append("- Python 3.9+")
        lines.append("- pip")

    lines.append("\n### Setup\n")
    lines.append("1. Clone the repository")
    lines.append("2. Install dependencies")
    lines.append("3. Copy `.env.example` to `.env` and configure")
    lines.append("4. Start development server")

    return "\n".join(lines)


def _generate_testing_section(project_info: ProjectInfo) -> str:
    """Generate testing section."""
    if "test" in project_info.scripts:
        return """```bash
# Run tests
npm test

# Run tests with coverage
npm run test:coverage
```"""
    elif project_info.language == "python":
        return """```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov
```"""
    return "TODO: Add testing instructions"


def _generate_deployment_section(workspace_path: str, project_info: ProjectInfo) -> str:
    """Generate deployment section."""
    lines = []

    if project_info.has_docker:
        lines.append("### Docker\n")
        lines.append("```bash")
        lines.append("docker build -t {name} .".format(name=project_info.name))
        lines.append("docker run -p 3000:3000 {name}".format(name=project_info.name))
        lines.append("```")

    if project_info.framework == "Next.js":
        lines.append("\n### Vercel (Recommended)\n")
        lines.append("Deploy with one click:\n")
        lines.append("[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new)")

    if not lines:
        lines.append("TODO: Add deployment instructions")

    return "\n".join(lines)


def _generate_contributing() -> str:
    """Generate contributing section."""
    return """1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request"""


def _generate_license(workspace_path: str) -> str:
    """Generate license section."""
    license_file = os.path.join(workspace_path, "LICENSE")
    if os.path.exists(license_file):
        try:
            with open(license_file, "r") as f:
                first_line = f.readline().strip()
            if "MIT" in first_line:
                return "This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details."
            elif "Apache" in first_line:
                return "This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details."
        except IOError:
            pass

    return "TODO: Add license"


def _clean_empty_sections(content: str) -> str:
    """Remove empty sections from generated content."""
    # Remove sections with only TODO content
    lines = content.split("\n")
    result = []
    skip_until_next_section = False

    for i, line in enumerate(lines):
        if line.startswith("## "):
            skip_until_next_section = False
            # Check if next non-empty line is TODO
            for j in range(i + 1, min(i + 5, len(lines))):
                if lines[j].strip():
                    if lines[j].strip().startswith("TODO:"):
                        skip_until_next_section = True
                    break

        if not skip_until_next_section:
            result.append(line)

    return "\n".join(result)


def _detect_language(ext: str) -> Optional[str]:
    """Detect programming language from file extension."""
    ext_map = {
        "_ts": "typescript",
        "_tsx": "typescript",
        "_js": "javascript",
        "_jsx": "javascript",
        "_py": "python",
        "_go": "go",
        "_rs": "rust",
    }
    return ext_map.get(ext.lower())


def _extract_api_routes(workspace_path: str, project_info: ProjectInfo) -> List[Dict]:
    """Extract API routes from source code."""
    routes = []

    if project_info.framework == "Next.js":
        # Look for app/api/**/*.ts routes
        api_dir = os.path.join(workspace_path, "app", "api")
        if os.path.exists(api_dir):
            for root, dirs, files in os.walk(api_dir):
                for f in files:
                    if f == "route.ts" or f == "route_js":
                        rel_path = os.path.relpath(root, api_dir)
                        route_path = f"/api/{rel_path}"
                        routes.append({
                            "path": route_path,
                            "methods": ["GET", "POST", "PUT", "DELETE"],
                            "file": os.path.join(root, f),
                        })

    elif project_info.framework in ("Express", "NestJS"):
        # Scan for router definitions
        for root, dirs, files in os.walk(workspace_path):
            dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "dist")]
            for f in files:
                if f.endswith((".ts", ".js")) and ("route" in f.lower() or "controller" in f.lower()):
                    full_path = os.path.join(root, f)
                    try:
                        with open(full_path, "r") as file:
                            content = file.read()
                        # Extract routes using regex
                        route_pattern = r"(app|router)\.(get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]"
                        for match in re.finditer(route_pattern, content, re.IGNORECASE):
                            routes.append({
                                "path": match.group(3),
                                "methods": [match.group(2).upper()],
                                "file": full_path,
                            })
                    except IOError:
                        continue

    elif project_info.framework == "FastAPI":
        # Scan for FastAPI decorators
        for root, dirs, files in os.walk(workspace_path):
            dirs[:] = [d for d in dirs if d not in ("venv", ".venv", "__pycache__", ".git")]
            for f in files:
                if f.endswith(".py"):
                    full_path = os.path.join(root, f)
                    try:
                        with open(full_path, "r") as file:
                            content = file.read()
                        route_pattern = r"@(app|router)\.(get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]"
                        for match in re.finditer(route_pattern, content, re.IGNORECASE):
                            routes.append({
                                "path": match.group(3),
                                "methods": [match.group(2).upper()],
                                "file": full_path,
                            })
                    except IOError:
                        continue

    return routes


def _generate_openapi_spec(routes: List[Dict], project_info: ProjectInfo) -> str:
    """Generate OpenAPI specification."""
    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": project_info.name,
            "version": project_info.version or "1.0.0",
            "description": project_info.description or "",
        },
        "paths": {},
    }

    for route in routes:
        path = route["path"]
        if path not in spec["paths"]:
            spec["paths"][path] = {}

        for method in route["methods"]:
            spec["paths"][path][method.lower()] = {
                "summary": f"{method} {path}",
                "responses": {
                    "200": {"description": "Successful response"},
                    "400": {"description": "Bad request"},
                    "500": {"description": "Internal server error"},
                },
            }

    import yaml
    try:
        return yaml.dump(spec, default_flow_style=False, sort_keys=False)
    except ImportError:
        return json.dumps(spec, indent=2)


def _generate_markdown_api_docs(routes: List[Dict], project_info: ProjectInfo) -> str:
    """Generate Markdown API documentation."""
    lines = [f"# {project_info.name} API\n"]
    lines.append(f"Version: {project_info.version or '1.0.0'}\n")

    for route in routes:
        lines.append(f"## `{' '.join(route['methods'])}` {route['path']}\n")
        lines.append("### Request\n")
        lines.append("```json\n// TODO: Add request body\n```\n")
        lines.append("### Response\n")
        lines.append("```json\n// TODO: Add response body\n```\n")

    return "\n".join(lines)


def _generate_html_api_docs(routes: List[Dict], project_info: ProjectInfo) -> str:
    """Generate HTML API documentation."""
    return f"<h1>{project_info.name} API Documentation</h1>\n<!-- TODO: Generate HTML docs -->"


def _find_components(workspace_path: str) -> List[str]:
    """Find React/Vue components in a project."""
    components = []

    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "dist", ".next")]

        for f in files:
            if f.endswith((".tsx", ".jsx", ".vue")):
                # Skip test files and stories
                if "test" not in f.lower() and "story" not in f.lower() and "spec" not in f.lower():
                    rel_path = os.path.relpath(os.path.join(root, f), workspace_path)
                    if "component" in rel_path.lower():
                        components.append(rel_path)

    return components


def _generate_single_component_doc(file_path: str) -> Optional[str]:
    """Generate documentation for a single component."""
    try:
        with open(file_path, "r") as f:
            content = f.read()

        component_name = os.path.splitext(os.path.basename(file_path))[0]

        # Extract props (simplified)
        props_pattern = r"interface\s+\w*Props\s*\{([^}]+)\}"
        props_match = re.search(props_pattern, content)
        props = props_match.group(1) if props_match else "No props defined"

        return f"""# {component_name}

## Props

```typescript
{props}
```

## Usage

```tsx
import {{ {component_name} }} from './{component_name}';

<{component_name} />
```
"""
    except IOError:
        return None


def _analyze_project_structure(workspace_path: str) -> Dict:
    """Analyze project directory structure."""
    structure = {
        "directories": [],
        "key_files": [],
        "layers": [],
    }

    for item in os.listdir(workspace_path):
        item_path = os.path.join(workspace_path, item)
        if os.path.isdir(item_path) and not item.startswith("."):
            structure["directories"].append(item)

            # Identify architectural layers
            if item in ("api", "routes", "controllers"):
                structure["layers"].append(("API Layer", item))
            elif item in ("services", "business"):
                structure["layers"].append(("Business Logic", item))
            elif item in ("models", "entities", "schemas"):
                structure["layers"].append(("Data Layer", item))
            elif item in ("components", "views", "pages"):
                structure["layers"].append(("Presentation Layer", item))

    # Key files
    key_file_patterns = [
        "package.json", "requirements.txt", "Dockerfile",
        "docker-compose.yml", "tsconfig.json", "pyproject.toml",
    ]
    for pattern in key_file_patterns:
        if os.path.exists(os.path.join(workspace_path, pattern)):
            structure["key_files"].append(pattern)

    return structure


def _generate_architecture_overview(project_info: ProjectInfo, structure: Dict) -> str:
    """Generate architecture overview."""
    return f"""{project_info.name} is a {project_info.framework or project_info.language} application
designed with a layered architecture pattern for maintainability and scalability."""


def _generate_components_section(structure: Dict) -> str:
    """Generate system components section."""
    if not structure["layers"]:
        return "TODO: Define system components"

    lines = []
    for layer_name, directory in structure["layers"]:
        lines.append(f"### {layer_name}")
        lines.append(f"Located in `{directory}/`")
        lines.append("")

    return "\n".join(lines)


def _generate_data_flow_section(workspace_path: str, project_info: ProjectInfo) -> str:
    """Generate data flow section."""
    return """1. Client sends request to API layer
2. API validates input and routes to appropriate service
3. Service executes business logic
4. Data layer handles persistence
5. Response flows back through layers to client"""


def _generate_tech_stack_section(project_info: ProjectInfo) -> str:
    """Generate technology stack section."""
    lines = [f"- **Language**: {project_info.language.title()}"]

    if project_info.framework:
        lines.append(f"- **Framework**: {project_info.framework}")

    # Add notable dependencies
    notable_deps = ["prisma", "typeorm", "sequelize", "mongoose", "redis", "postgresql", "mysql"]
    for dep in notable_deps:
        if dep in project_info.dependencies:
            lines.append(f"- **{dep.title()}**: Database/ORM")

    return "\n".join(lines)


def _generate_infrastructure_section(workspace_path: str) -> str:
    """Generate infrastructure section."""
    lines = []

    if os.path.exists(os.path.join(workspace_path, "Dockerfile")):
        lines.append("### Docker")
        lines.append("The application is containerized using Docker.")

    if os.path.exists(os.path.join(workspace_path, "docker-compose.yml")):
        lines.append("\n### Docker Compose")
        lines.append("Multi-container setup with Docker Compose.")

    if os.path.exists(os.path.join(workspace_path, "kubernetes")) or \
       os.path.exists(os.path.join(workspace_path, "k8s")):
        lines.append("\n### Kubernetes")
        lines.append("Kubernetes manifests available for orchestration.")

    if not lines:
        lines.append("TODO: Define infrastructure setup")

    return "\n".join(lines)


def _generate_security_section(workspace_path: str) -> str:
    """Generate security section."""
    return """### Authentication
TODO: Define authentication mechanism

### Authorization
TODO: Define authorization rules

### Data Protection
TODO: Define data protection measures"""


def _generate_scalability_section(project_info: ProjectInfo) -> str:
    """Generate scalability section."""
    return """### Horizontal Scaling
TODO: Define scaling strategy

### Caching
TODO: Define caching strategy

### Load Balancing
TODO: Define load balancing approach"""


def _generate_architecture_diagrams(structure: Dict, project_info: ProjectInfo) -> str:
    """Generate Mermaid architecture diagrams."""
    diagrams = []

    # System overview diagram
    diagrams.append("### System Overview")
    diagrams.append("```mermaid")
    diagrams.append("graph TD")
    diagrams.append("    Client[Client] --> API[API Layer]")
    diagrams.append("    API --> Services[Business Logic]")
    diagrams.append("    Services --> Data[Data Layer]")
    diagrams.append("    Data --> DB[(Database)]")
    diagrams.append("```")

    # Component diagram
    if structure["layers"]:
        diagrams.append("\n### Component Diagram")
        diagrams.append("```mermaid")
        diagrams.append("graph LR")
        for i, (layer_name, directory) in enumerate(structure["layers"]):
            safe_name = layer_name.replace(" ", "_")
            diagrams.append(f"    {safe_name}[{layer_name}]")
            if i > 0:
                prev_name = structure["layers"][i-1][0].replace(" ", "_")
                diagrams.append(f"    {prev_name} --> {safe_name}")
        diagrams.append("```")

    return "\n".join(diagrams)


def _generate_comments_for_file(source_code: str, language: str, style: str) -> List[Dict]:
    """Generate documentation comments for functions in a file."""
    comments = []

    if language == "python":
        import ast
        try:
            tree = ast.parse(source_code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not ast.get_docstring(node):
                        params = [arg.arg for arg in node.args.args if arg.arg != "self"]
                        comment = _generate_python_docstring(node.name, params)
                        comments.append({
                            "line": node.lineno,
                            "name": node.name,
                            "comment": comment,
                        })
        except SyntaxError:
            pass

    else:  # JavaScript/TypeScript
        func_pattern = r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)"
        for match in re.finditer(func_pattern, source_code):
            name = match.group(1)
            params = [p.strip().split(":")[0].strip() for p in match.group(2).split(",") if p.strip()]
            line = source_code[:match.start()].count("\n") + 1

            comment = _generate_jsdoc_comment(name, params)
            comments.append({
                "line": line,
                "name": name,
                "comment": comment,
            })

    return comments


def _generate_python_docstring(func_name: str, params: List[str]) -> str:
    """Generate Python docstring."""
    lines = ['"""']
    lines.append(f"TODO: Describe what {func_name} does.")
    lines.append("")

    if params:
        lines.append("Args:")
        for param in params:
            lines.append(f"    {param}: TODO: Describe {param}")
        lines.append("")

    lines.append("Returns:")
    lines.append("    TODO: Describe return value")
    lines.append('"""')

    return "\n".join(lines)


def _generate_jsdoc_comment(func_name: str, params: List[str]) -> str:
    """Generate JSDoc comment."""
    lines = ["/**"]
    lines.append(f" * TODO: Describe what {func_name} does.")
    lines.append(" *")

    for param in params:
        lines.append(f" * @param {param} - TODO: Describe {param}")

    lines.append(" * @returns TODO: Describe return value")
    lines.append(" */")

    return "\n".join(lines)


# Export tools for the agent dispatcher
DOCUMENTATION_TOOLS = {
    "docs_generate_readme": generate_readme,
    "docs_generate_api": generate_api_docs,
    "docs_generate_component": generate_component_docs,
    "docs_generate_architecture": generate_architecture_doc,
    "docs_generate_comments": generate_code_comments,
    "docs_generate_changelog": generate_changelog,
}
