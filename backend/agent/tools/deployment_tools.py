"""
Deployment tools for NAVI agent.

Provides tools to detect project type and manage deployments across
multiple platforms (Vercel, Railway, Fly.io, Netlify, Heroku, AWS, GCP, Azure, etc.)
using CLI-based deployment workflow.
"""

from typing import Any, Dict, Optional
import subprocess
import shutil
import os
import json
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


# Platform CLI configurations for all major deployment platforms
PLATFORM_CLIS = {
    "vercel": {
        "cli": "vercel",
        "install": "npm i -g vercel",
        "login": "vercel login",
        "deploy": "vercel --prod --yes",
        "status": "vercel whoami",
        "env_set": "vercel env add {key} production",
        "description": "Frontend/fullstack deployment, optimized for Next.js/React",
    },
    "railway": {
        "cli": "railway",
        "install": "npm i -g @railway/cli",
        "login": "railway login",
        "deploy": "railway up",
        "status": "railway whoami",
        "env_set": "railway variables set {key}={value}",
        "description": "Backend/fullstack deployment with built-in databases",
    },
    "fly": {
        "cli": "flyctl",
        "install": "curl -L https://fly.io/install.sh | sh",
        "login": "fly auth login",
        "deploy": "fly deploy",
        "status": "fly auth whoami",
        "env_set": "fly secrets set {key}={value}",
        "description": "Container-based edge deployment",
    },
    "netlify": {
        "cli": "netlify",
        "install": "npm i -g netlify-cli",
        "login": "netlify login",
        "deploy": "netlify deploy --prod",
        "status": "netlify status",
        "env_set": "netlify env:set {key} {value}",
        "description": "JAMstack/static site deployment",
    },
    "heroku": {
        "cli": "heroku",
        "install": "curl https://cli-assets.heroku.com/install.sh | sh",
        "login": "heroku login",
        "deploy": "git push heroku main",
        "status": "heroku auth:whoami",
        "env_set": "heroku config:set {key}={value}",
        "description": "Classic PaaS deployment",
    },
    "render": {
        "cli": "render",
        "install": "pip install render-cli",
        "login": "render login",
        "deploy": "render deploy",
        "status": "render whoami",
        "description": "Modern cloud platform with auto-deploy",
    },
    "cloudflare": {
        "cli": "wrangler",
        "install": "npm i -g wrangler",
        "login": "wrangler login",
        "deploy": "wrangler publish",
        "status": "wrangler whoami",
        "env_set": "wrangler secret put {key}",
        "description": "Cloudflare Workers/Pages edge deployment",
    },
    "aws": {
        "cli": "aws",
        "install": "pip install awscli",
        "login": "aws configure",
        "deploy": "sam deploy --guided",
        "status": "aws sts get-caller-identity",
        "description": "AWS serverless/container deployment",
    },
    "gcloud": {
        "cli": "gcloud",
        "install": "curl https://sdk.cloud.google.com | bash",
        "login": "gcloud auth login",
        "deploy": "gcloud run deploy",
        "status": "gcloud auth list",
        "description": "Google Cloud Run/App Engine deployment",
    },
    "azure": {
        "cli": "az",
        "install": "curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash",
        "login": "az login",
        "deploy": "az webapp up",
        "status": "az account show",
        "description": "Azure App Service deployment",
    },
}


async def detect_project_type(
    context: Dict[str, Any],
    workspace_path: Optional[str] = None,
) -> ToolResult:
    """
    Detect project type and recommend deployment platforms.

    Analyzes the workspace to determine:
    - Project type (frontend, backend, fullstack, static, container)
    - Framework (Next.js, React, Django, FastAPI, Express, etc.)
    - Language (JavaScript, Python, Go, etc.)
    - Recommended deployment platforms
    """
    if not workspace_path:
        workspace_path = os.getcwd()

    detected = {
        "type": "unknown",
        "framework": None,
        "language": None,
        "recommended_platforms": [],
        "detected_files": [],
        "has_dockerfile": False,
        "has_database": False,
    }

    # Check for common project files
    file_checks = [
        ("package.json", "node"),
        ("requirements.txt", "python"),
        ("pyproject.toml", "python"),
        ("go.mod", "go"),
        ("Cargo.toml", "rust"),
        ("Gemfile", "ruby"),
        ("pom.xml", "java"),
        ("build.gradle", "java"),
        ("Dockerfile", "docker"),
        ("docker-compose.yml", "docker"),
        ("fly.toml", "fly_config"),
        ("vercel.json", "vercel_config"),
        ("netlify.toml", "netlify_config"),
        ("railway.json", "railway_config"),
        ("render.yaml", "render_config"),
        ("Procfile", "heroku_config"),
    ]

    for filename, indicator in file_checks:
        filepath = os.path.join(workspace_path, filename)
        if os.path.exists(filepath):
            detected["detected_files"].append(filename)

            if indicator == "docker":
                detected["has_dockerfile"] = True

            # Parse package.json for more details
            if filename == "package.json":
                try:
                    with open(filepath, "r") as f:
                        pkg = json.load(f)
                        deps = {
                            **pkg.get("dependencies", {}),
                            **pkg.get("devDependencies", {})
                        }

                        # Detect framework
                        if "next" in deps:
                            detected["framework"] = "Next.js"
                            detected["type"] = "fullstack"
                            detected["recommended_platforms"] = ["vercel", "netlify", "railway", "fly"]
                        elif "nuxt" in deps:
                            detected["framework"] = "Nuxt.js"
                            detected["type"] = "fullstack"
                            detected["recommended_platforms"] = ["vercel", "netlify", "railway"]
                        elif "gatsby" in deps:
                            detected["framework"] = "Gatsby"
                            detected["type"] = "static"
                            detected["recommended_platforms"] = ["netlify", "vercel", "cloudflare"]
                        elif "express" in deps or "fastify" in deps or "koa" in deps:
                            detected["framework"] = "Express" if "express" in deps else "Fastify" if "fastify" in deps else "Koa"
                            detected["type"] = "backend"
                            detected["recommended_platforms"] = ["railway", "render", "fly", "heroku"]
                        elif "react" in deps and "next" not in deps:
                            detected["framework"] = "React"
                            detected["type"] = "frontend"
                            detected["recommended_platforms"] = ["vercel", "netlify", "cloudflare"]
                        elif "vue" in deps:
                            detected["framework"] = "Vue.js"
                            detected["type"] = "frontend"
                            detected["recommended_platforms"] = ["vercel", "netlify", "cloudflare"]
                        elif "svelte" in deps:
                            detected["framework"] = "Svelte"
                            detected["type"] = "frontend"
                            detected["recommended_platforms"] = ["vercel", "netlify", "cloudflare"]
                        elif "angular" in deps or "@angular/core" in deps:
                            detected["framework"] = "Angular"
                            detected["type"] = "frontend"
                            detected["recommended_platforms"] = ["vercel", "netlify", "cloudflare"]
                        else:
                            detected["type"] = "node"
                            detected["recommended_platforms"] = ["railway", "render", "fly", "heroku"]

                        detected["language"] = "javascript"

                        # Check for database dependencies
                        db_deps = ["prisma", "typeorm", "sequelize", "mongoose", "pg", "mysql2", "mongodb"]
                        if any(db in deps for db in db_deps):
                            detected["has_database"] = True
                            # Prioritize platforms with DB support
                            detected["recommended_platforms"] = ["railway", "render", "fly", "heroku"]

                except (json.JSONDecodeError, IOError) as e:
                    logger.warning("detect_project_type.package_json_error", error=str(e))

            # Parse requirements.txt/pyproject.toml for Python projects
            elif filename in ("requirements.txt", "pyproject.toml"):
                detected["language"] = "python"

                try:
                    if filename == "requirements.txt":
                        with open(filepath, "r") as f:
                            content = f.read().lower()
                    else:
                        content = ""

                    if "django" in content or os.path.exists(os.path.join(workspace_path, "manage.py")):
                        detected["framework"] = "Django"
                        detected["type"] = "backend"
                    elif "fastapi" in content:
                        detected["framework"] = "FastAPI"
                        detected["type"] = "backend"
                    elif "flask" in content:
                        detected["framework"] = "Flask"
                        detected["type"] = "backend"
                    elif "streamlit" in content:
                        detected["framework"] = "Streamlit"
                        detected["type"] = "frontend"
                    else:
                        detected["type"] = "python"

                    detected["recommended_platforms"] = ["railway", "render", "fly", "heroku"]

                    # Check for database
                    if any(db in content for db in ["psycopg", "sqlalchemy", "django", "pymongo"]):
                        detected["has_database"] = True

                except IOError as e:
                    logger.warning("detect_project_type.requirements_error", error=str(e))

            # Go project
            elif filename == "go.mod":
                detected["language"] = "go"
                detected["type"] = "backend"
                detected["recommended_platforms"] = ["fly", "railway", "render"]

            # Rust project
            elif filename == "Cargo.toml":
                detected["language"] = "rust"
                detected["type"] = "backend"
                detected["recommended_platforms"] = ["fly", "railway"]

    # If only Dockerfile, it's a containerized app
    if detected["has_dockerfile"] and detected["type"] == "unknown":
        detected["type"] = "container"
        detected["recommended_platforms"] = ["fly", "railway", "render", "aws", "gcloud"]

    # Check for static site (just HTML)
    if detected["type"] == "unknown":
        if os.path.exists(os.path.join(workspace_path, "index.html")):
            detected["type"] = "static"
            detected["recommended_platforms"] = ["netlify", "vercel", "cloudflare"]
            detected["detected_files"].append("index.html")

    # Build output message
    lines = ["## Project Analysis\n"]
    lines.append(f"**Type**: {detected['type']}")
    if detected["framework"]:
        lines.append(f"**Framework**: {detected['framework']}")
    if detected["language"]:
        lines.append(f"**Language**: {detected['language']}")
    if detected["has_database"]:
        lines.append("**Database**: Yes (detected ORM/database dependencies)")
    if detected["has_dockerfile"]:
        lines.append("**Docker**: Dockerfile found")

    lines.append(f"\n**Detected Files**: {', '.join(detected['detected_files']) or 'None'}")

    if detected["recommended_platforms"]:
        lines.append("\n**Recommended Platforms**:")
        for platform in detected["recommended_platforms"][:4]:
            config = PLATFORM_CLIS.get(platform, {})
            desc = config.get("description", "")
            lines.append(f"- **{platform.title()}**: {desc}")

    return ToolResult(output="\n".join(lines), sources=[])


async def check_deployment_cli(
    context: Dict[str, Any],
    platform: str,
) -> ToolResult:
    """
    Check if a deployment platform's CLI is installed and authenticated.

    Returns:
    - Installation status
    - Authentication status
    - Commands to install/login if needed
    """
    platform = platform.lower()

    if platform not in PLATFORM_CLIS:
        available = ", ".join(PLATFORM_CLIS.keys())
        return ToolResult(
            output=f"Unknown platform: {platform}\n\nAvailable platforms: {available}",
            sources=[],
        )

    config = PLATFORM_CLIS[platform]
    cli_name = config["cli"]
    cli_path = shutil.which(cli_name)

    lines = [f"## {platform.title()} CLI Status\n"]

    # Check if CLI is installed
    if not cli_path:
        lines.append("**Installed**: No")
        lines.append("\n**To install**, run:")
        lines.append(f"```bash\n{config['install']}\n```")
        lines.append("\n**Then login** with:")
        lines.append(f"```bash\n{config['login']}\n```")
        return ToolResult(output="\n".join(lines), sources=[])

    lines.append("**Installed**: Yes")
    lines.append(f"**Path**: {cli_path}")

    # Try to get version
    try:
        version_result = subprocess.run(
            [cli_name, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if version_result.returncode == 0:
            version = version_result.stdout.strip() or version_result.stderr.strip()
            lines.append(f"**Version**: {version[:100]}")
    except Exception:
        pass

    # Check authentication
    status_cmd = config.get("status")
    if status_cmd:
        try:
            result = subprocess.run(
                status_cmd.split(),
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                lines.append("**Authenticated**: Yes")
                # Show who's logged in (first line of output usually)
                if result.stdout:
                    who = result.stdout.strip().split("\n")[0][:100]
                    lines.append(f"**User**: {who}")
                lines.append("\n**Ready to deploy!** Use:")
                lines.append(f"```bash\n{config['deploy']}\n```")
            else:
                lines.append("**Authenticated**: No")
                lines.append("\n**To login**, run:")
                lines.append(f"```bash\n{config['login']}\n```")
                lines.append("\n(This will open your browser for OAuth authentication)")

        except subprocess.TimeoutExpired:
            lines.append("**Authenticated**: Unknown (timeout)")
            lines.append(f"\nTry running `{status_cmd}` manually to check.")
        except Exception as e:
            lines.append(f"**Authenticated**: Unknown ({e})")

    return ToolResult(output="\n".join(lines), sources=[])


async def get_deployment_info(
    context: Dict[str, Any],
    platform: str,
) -> ToolResult:
    """
    Get deployment commands and configuration for a platform.
    """
    platform = platform.lower()

    if platform not in PLATFORM_CLIS:
        return ToolResult(
            output=f"Unknown platform: {platform}",
            sources=[],
        )

    config = PLATFORM_CLIS[platform]

    lines = [f"## Deploying to {platform.title()}\n"]
    lines.append(f"**Description**: {config.get('description', 'Cloud deployment platform')}\n")

    lines.append("### Prerequisites")
    lines.append(f"1. Install CLI: `{config['install']}`")
    lines.append(f"2. Login: `{config['login']}`\n")

    lines.append("### Deploy Command")
    lines.append(f"```bash\n{config['deploy']}\n```\n")

    if config.get("env_set"):
        lines.append("### Set Environment Variables")
        lines.append(f"```bash\n{config['env_set']}\n```\n")

    lines.append("### Check Status")
    status_cmd = config.get('status', f"{config['cli']} status")
    lines.append(f"```bash\n{status_cmd}\n```")

    return ToolResult(output="\n".join(lines), sources=[])


async def list_supported_platforms(
    context: Dict[str, Any],
) -> ToolResult:
    """
    List all supported deployment platforms.
    """
    lines = ["## Supported Deployment Platforms\n"]

    for platform, config in PLATFORM_CLIS.items():
        lines.append(f"### {platform.title()}")
        lines.append(f"- **CLI**: `{config['cli']}`")
        lines.append(f"- **Description**: {config.get('description', 'N/A')}")
        lines.append(f"- **Install**: `{config['install']}`")
        lines.append("")

    return ToolResult(output="\n".join(lines), sources=[])


# Export tools for the agent dispatcher
DEPLOYMENT_TOOLS = {
    "deploy.detect_project": detect_project_type,
    "deploy.check_cli": check_deployment_cli,
    "deploy.get_info": get_deployment_info,
    "deploy.list_platforms": list_supported_platforms,
}
