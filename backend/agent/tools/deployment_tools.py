"""
Deployment tools for NAVI agent.

Provides tools to detect project type and manage deployments across
multiple platforms (Vercel, Railway, Fly.io, Netlify, Heroku, AWS, GCP, Azure, etc.)
using CLI-based deployment workflow.

Now with REAL EXECUTION capabilities - deployments actually run!
"""

from typing import Any, Dict, Optional
import subprocess
import shutil
import os
import json
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


# Import execution services
try:
    from backend.services.execution_confirmation_service import (
        execution_confirmation_service,
        RiskLevel,
        OperationCategory,
    )
    from backend.services.deployment_executor_service import (
        deployment_executor_service,
        DeploymentConfig,
        DeploymentPlatform,
    )

    EXECUTION_SERVICES_AVAILABLE = True
except ImportError:
    EXECUTION_SERVICES_AVAILABLE = False
    logger.warning("Execution services not available - running in dry-run mode")


# Platform CLI configurations for all major deployment platforms
PLATFORM_CLIS = {
    # ============================================================================
    # MODERN PAAS PLATFORMS
    # ============================================================================
    "vercel": {
        "cli": "vercel",
        "install": "npm i -g vercel",
        "login": "vercel login",
        "deploy": "vercel --prod --yes",
        "status": "vercel whoami",
        "env_set": "vercel env add {key} production",
        "rollback": "vercel rollback",
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
        "rollback": "fly releases rollback",
        "description": "Container-based edge deployment",
    },
    "netlify": {
        "cli": "netlify",
        "install": "npm i -g netlify-cli",
        "login": "netlify login",
        "deploy": "netlify deploy --prod",
        "status": "netlify status",
        "env_set": "netlify env:set {key} {value}",
        "rollback": "netlify rollback",
        "description": "JAMstack/static site deployment",
    },
    "heroku": {
        "cli": "heroku",
        "install": "curl https://cli-assets.heroku.com/install.sh | sh",
        "login": "heroku login",
        "deploy": "git push heroku main",
        "status": "heroku auth:whoami",
        "env_set": "heroku config:set {key}={value}",
        "rollback": "heroku rollback",
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
    "deno_deploy": {
        "cli": "deployctl",
        "install": "deno install -A --no-check -r -f https://deno.land/x/deploy/deployctl.ts",
        "login": "deployctl login",
        "deploy": "deployctl deploy --prod",
        "status": "deployctl whoami",
        "description": "Deno-native edge runtime deployment",
    },
    # ============================================================================
    # CLOUDFLARE
    # ============================================================================
    "cloudflare_workers": {
        "cli": "wrangler",
        "install": "npm i -g wrangler",
        "login": "wrangler login",
        "deploy": "wrangler deploy",
        "status": "wrangler whoami",
        "env_set": "wrangler secret put {key}",
        "description": "Cloudflare Workers edge functions",
    },
    "cloudflare_pages": {
        "cli": "wrangler",
        "install": "npm i -g wrangler",
        "login": "wrangler login",
        "deploy": "wrangler pages deploy ./dist",
        "status": "wrangler whoami",
        "description": "Cloudflare Pages static site hosting",
    },
    # ============================================================================
    # AWS - AMAZON WEB SERVICES
    # ============================================================================
    "aws_ecs": {
        "cli": "aws",
        "install": "pip install awscli",
        "login": "aws configure",
        "deploy": "aws ecs update-service --cluster {cluster} --service {service} --force-new-deployment",
        "status": "aws sts get-caller-identity",
        "description": "AWS ECS container orchestration",
    },
    "aws_lambda": {
        "cli": "sam",
        "install": "pip install aws-sam-cli",
        "login": "aws configure",
        "deploy": "sam deploy --guided",
        "status": "aws sts get-caller-identity",
        "description": "AWS Lambda serverless functions",
    },
    "aws_amplify": {
        "cli": "amplify",
        "install": "npm i -g @aws-amplify/cli",
        "login": "amplify configure",
        "deploy": "amplify publish",
        "status": "amplify status",
        "description": "AWS Amplify fullstack platform",
    },
    "aws_app_runner": {
        "cli": "aws",
        "install": "pip install awscli",
        "login": "aws configure",
        "deploy": "aws apprunner create-service --service-name {name} --source-configuration '{config}'",
        "status": "aws sts get-caller-identity",
        "description": "AWS App Runner container deployment",
    },
    "aws_elastic_beanstalk": {
        "cli": "eb",
        "install": "pip install awsebcli",
        "login": "eb init",
        "deploy": "eb deploy",
        "status": "eb status",
        "rollback": "eb restore {version}",
        "description": "AWS Elastic Beanstalk managed platform",
    },
    "aws_lightsail": {
        "cli": "aws",
        "install": "pip install awscli",
        "login": "aws configure",
        "deploy": "aws lightsail create-container-service-deployment",
        "status": "aws lightsail get-container-services",
        "description": "AWS Lightsail simple container deployment",
    },
    # ============================================================================
    # GOOGLE CLOUD PLATFORM
    # ============================================================================
    "gcp_cloud_run": {
        "cli": "gcloud",
        "install": "curl https://sdk.cloud.google.com | bash",
        "login": "gcloud auth login",
        "deploy": "gcloud run deploy {service} --source .",
        "status": "gcloud auth list",
        "rollback": "gcloud run services update-traffic {service} --to-revisions={revision}=100",
        "description": "Google Cloud Run serverless containers",
    },
    "gcp_app_engine": {
        "cli": "gcloud",
        "install": "curl https://sdk.cloud.google.com | bash",
        "login": "gcloud auth login",
        "deploy": "gcloud app deploy",
        "status": "gcloud app describe",
        "rollback": "gcloud app versions migrate {version}",
        "description": "Google App Engine managed platform",
    },
    "gcp_cloud_functions": {
        "cli": "gcloud",
        "install": "curl https://sdk.cloud.google.com | bash",
        "login": "gcloud auth login",
        "deploy": "gcloud functions deploy {name} --runtime {runtime} --trigger-http",
        "status": "gcloud functions list",
        "description": "Google Cloud Functions serverless",
    },
    "firebase_hosting": {
        "cli": "firebase",
        "install": "npm i -g firebase-tools",
        "login": "firebase login",
        "deploy": "firebase deploy --only hosting",
        "status": "firebase projects:list",
        "rollback": "firebase hosting:rollback",
        "description": "Firebase static hosting",
    },
    "firebase_functions": {
        "cli": "firebase",
        "install": "npm i -g firebase-tools",
        "login": "firebase login",
        "deploy": "firebase deploy --only functions",
        "status": "firebase projects:list",
        "description": "Firebase Cloud Functions",
    },
    # ============================================================================
    # MICROSOFT AZURE
    # ============================================================================
    "azure_app_service": {
        "cli": "az",
        "install": "curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash",
        "login": "az login",
        "deploy": "az webapp up --name {name} --resource-group {rg}",
        "status": "az account show",
        "rollback": "az webapp deployment slot swap --slot staging",
        "description": "Azure App Service web apps",
    },
    "azure_functions": {
        "cli": "func",
        "install": "npm i -g azure-functions-core-tools@4",
        "login": "az login",
        "deploy": "func azure functionapp publish {name}",
        "status": "az account show",
        "description": "Azure Functions serverless",
    },
    "azure_container_apps": {
        "cli": "az",
        "install": "curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash && az extension add --name containerapp",
        "login": "az login",
        "deploy": "az containerapp up --name {name} --source .",
        "status": "az containerapp list",
        "description": "Azure Container Apps serverless containers",
    },
    "azure_static_webapps": {
        "cli": "swa",
        "install": "npm i -g @azure/static-web-apps-cli",
        "login": "swa login",
        "deploy": "swa deploy",
        "status": "az account show",
        "description": "Azure Static Web Apps",
    },
    # ============================================================================
    # ORACLE CLOUD INFRASTRUCTURE
    # ============================================================================
    "oracle_cloud": {
        "cli": "oci",
        "install": "pip install oci-cli",
        "login": "oci session authenticate",
        "deploy": "oci fn function invoke --function-id {id}",
        "status": "oci session validate",
        "description": "Oracle Cloud Infrastructure deployment",
    },
    "oracle_container_engine": {
        "cli": "oci",
        "install": "pip install oci-cli",
        "login": "oci session authenticate",
        "deploy": "kubectl apply -f deployment.yaml",
        "status": "oci ce cluster list",
        "description": "Oracle Container Engine for Kubernetes (OKE)",
    },
    "oracle_functions": {
        "cli": "fn",
        "install": "curl -LSs https://raw.githubusercontent.com/fnproject/cli/master/install | sh",
        "login": "fn use context {context}",
        "deploy": "fn deploy --app {app}",
        "status": "fn list apps",
        "description": "Oracle Functions (Fn Project)",
    },
    # ============================================================================
    # IBM CLOUD
    # ============================================================================
    "ibm_code_engine": {
        "cli": "ibmcloud",
        "install": "curl -fsSL https://clis.cloud.ibm.com/install/linux | sh",
        "login": "ibmcloud login",
        "deploy": "ibmcloud ce application create --name {name} --image {image}",
        "status": "ibmcloud account show",
        "description": "IBM Cloud Code Engine serverless",
    },
    "ibm_cloud_functions": {
        "cli": "ibmcloud",
        "install": "curl -fsSL https://clis.cloud.ibm.com/install/linux | sh && ibmcloud plugin install cloud-functions",
        "login": "ibmcloud login",
        "deploy": "ibmcloud fn action create {name} {file}",
        "status": "ibmcloud fn namespace list",
        "description": "IBM Cloud Functions (OpenWhisk)",
    },
    # ============================================================================
    # ALIBABA CLOUD
    # ============================================================================
    "alibaba_serverless": {
        "cli": "aliyun",
        "install": "curl -fsSL https://aliyuncli.alicdn.com/aliyun-cli-linux-latest-amd64.tgz | tar -xz",
        "login": "aliyun configure",
        "deploy": "aliyun fc CreateFunction",
        "status": "aliyun fc ListServices",
        "description": "Alibaba Cloud Function Compute",
    },
    "alibaba_container_service": {
        "cli": "aliyun",
        "install": "curl -fsSL https://aliyuncli.alicdn.com/aliyun-cli-linux-latest-amd64.tgz | tar -xz",
        "login": "aliyun configure",
        "deploy": "kubectl apply -f deployment.yaml",
        "status": "aliyun cs DescribeClusters",
        "description": "Alibaba Container Service for Kubernetes (ACK)",
    },
    # ============================================================================
    # DIGITALOCEAN
    # ============================================================================
    "digitalocean_app_platform": {
        "cli": "doctl",
        "install": "snap install doctl",
        "login": "doctl auth init",
        "deploy": "doctl apps create --spec .do/app.yaml",
        "status": "doctl account get",
        "rollback": "doctl apps create-deployment {app-id} --force-rebuild",
        "description": "DigitalOcean App Platform",
    },
    "digitalocean_kubernetes": {
        "cli": "doctl",
        "install": "snap install doctl",
        "login": "doctl auth init",
        "deploy": "doctl kubernetes cluster kubeconfig save {cluster} && kubectl apply -f deployment.yaml",
        "status": "doctl kubernetes cluster list",
        "description": "DigitalOcean Kubernetes (DOKS)",
    },
    "digitalocean_functions": {
        "cli": "doctl",
        "install": "snap install doctl",
        "login": "doctl auth init",
        "deploy": "doctl serverless deploy",
        "status": "doctl serverless status",
        "description": "DigitalOcean Functions serverless",
    },
    # ============================================================================
    # EDGE/CDN PLATFORMS
    # ============================================================================
    "fastly_compute": {
        "cli": "fastly",
        "install": "brew install fastly/tap/fastly",
        "login": "fastly configure",
        "deploy": "fastly compute publish",
        "status": "fastly whoami",
        "description": "Fastly Compute@Edge",
    },
    "akamai_edgeworkers": {
        "cli": "akamai",
        "install": "pip install edgegrid-python akamai-edgerc",
        "login": "akamai config",
        "deploy": "akamai edgeworkers upload --bundle {file}",
        "status": "akamai edgeworkers list",
        "description": "Akamai EdgeWorkers",
    },
    # ============================================================================
    # VPS PROVIDERS
    # ============================================================================
    "linode": {
        "cli": "linode-cli",
        "install": "pip install linode-cli",
        "login": "linode-cli configure",
        "deploy": "linode-cli lke kubeconfig-view {cluster-id} > ~/.kube/config && kubectl apply -f deployment.yaml",
        "status": "linode-cli account view",
        "description": "Linode/Akamai cloud VPS and Kubernetes",
    },
    "vultr": {
        "cli": "vultr-cli",
        "install": "brew install vultr/vultr-cli/vultr-cli",
        "login": "export VULTR_API_KEY={key}",
        "deploy": "vultr-cli kubernetes config {cluster-id} && kubectl apply -f deployment.yaml",
        "status": "vultr-cli account",
        "description": "Vultr cloud VPS and Kubernetes",
    },
    "hetzner": {
        "cli": "hcloud",
        "install": "brew install hcloud",
        "login": "hcloud context create {name}",
        "deploy": "kubectl apply -f deployment.yaml",
        "status": "hcloud server list",
        "description": "Hetzner Cloud servers",
    },
    # ============================================================================
    # STATIC HOSTING
    # ============================================================================
    "github_pages": {
        "cli": "gh",
        "install": "brew install gh",
        "login": "gh auth login",
        "deploy": "gh-pages -d dist",
        "status": "gh auth status",
        "description": "GitHub Pages static hosting",
    },
    "gitlab_pages": {
        "cli": "glab",
        "install": "brew install glab",
        "login": "glab auth login",
        "deploy": "git push origin main",  # Uses .gitlab-ci.yml
        "status": "glab auth status",
        "description": "GitLab Pages static hosting",
    },
    "surge": {
        "cli": "surge",
        "install": "npm i -g surge",
        "login": "surge login",
        "deploy": "surge ./dist {domain}.surge.sh",
        "status": "surge whoami",
        "description": "Surge.sh simple static hosting",
    },
    # ============================================================================
    # CONTAINER ORCHESTRATION
    # ============================================================================
    "kubernetes": {
        "cli": "kubectl",
        "install": "curl -LO https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl",
        "login": "kubectl config use-context {context}",
        "deploy": "kubectl apply -f deployment.yaml",
        "status": "kubectl cluster-info",
        "rollback": "kubectl rollout undo deployment/{name}",
        "description": "Kubernetes container orchestration",
    },
    "docker": {
        "cli": "docker",
        "install": "curl -fsSL https://get.docker.com | sh",
        "login": "docker login",
        "deploy": "docker compose up -d",
        "status": "docker info",
        "description": "Docker container deployment",
    },
    "docker_swarm": {
        "cli": "docker",
        "install": "curl -fsSL https://get.docker.com | sh",
        "login": "docker swarm init",
        "deploy": "docker stack deploy -c docker-compose.yml {stack}",
        "status": "docker node ls",
        "description": "Docker Swarm orchestration",
    },
    "nomad": {
        "cli": "nomad",
        "install": "brew install nomad",
        "login": "export NOMAD_ADDR={addr}",
        "deploy": "nomad job run {job}.nomad",
        "status": "nomad status",
        "description": "HashiCorp Nomad orchestration",
    },
    # ============================================================================
    # SELF-HOSTED PAAS
    # ============================================================================
    "coolify": {
        "cli": "coolify",
        "install": "curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash",
        "login": "coolify login",
        "deploy": "coolify deploy",
        "status": "coolify status",
        "description": "Self-hosted Heroku/Vercel alternative",
    },
    "dokku": {
        "cli": "dokku",
        "install": "wget https://raw.githubusercontent.com/dokku/dokku/master/bootstrap.sh && sudo bash bootstrap.sh",
        "login": "git remote add dokku dokku@{host}:{app}",
        "deploy": "git push dokku main",
        "status": "dokku apps:list",
        "description": "Self-hosted Heroku alternative",
    },
    "caprover": {
        "cli": "caprover",
        "install": "npm i -g caprover",
        "login": "caprover login",
        "deploy": "caprover deploy",
        "status": "caprover list",
        "description": "Self-hosted PaaS with web UI",
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
                            **pkg.get("devDependencies", {}),
                        }

                        # Detect framework
                        if "next" in deps:
                            detected["framework"] = "Next.js"
                            detected["type"] = "fullstack"
                            detected["recommended_platforms"] = [
                                "vercel",
                                "netlify",
                                "railway",
                                "fly",
                            ]
                        elif "nuxt" in deps:
                            detected["framework"] = "Nuxt.js"
                            detected["type"] = "fullstack"
                            detected["recommended_platforms"] = [
                                "vercel",
                                "netlify",
                                "railway",
                            ]
                        elif "gatsby" in deps:
                            detected["framework"] = "Gatsby"
                            detected["type"] = "static"
                            detected["recommended_platforms"] = [
                                "netlify",
                                "vercel",
                                "cloudflare",
                            ]
                        elif "express" in deps or "fastify" in deps or "koa" in deps:
                            detected["framework"] = (
                                "Express"
                                if "express" in deps
                                else "Fastify" if "fastify" in deps else "Koa"
                            )
                            detected["type"] = "backend"
                            detected["recommended_platforms"] = [
                                "railway",
                                "render",
                                "fly",
                                "heroku",
                            ]
                        elif "react" in deps and "next" not in deps:
                            detected["framework"] = "React"
                            detected["type"] = "frontend"
                            detected["recommended_platforms"] = [
                                "vercel",
                                "netlify",
                                "cloudflare",
                            ]
                        elif "vue" in deps:
                            detected["framework"] = "Vue.js"
                            detected["type"] = "frontend"
                            detected["recommended_platforms"] = [
                                "vercel",
                                "netlify",
                                "cloudflare",
                            ]
                        elif "svelte" in deps:
                            detected["framework"] = "Svelte"
                            detected["type"] = "frontend"
                            detected["recommended_platforms"] = [
                                "vercel",
                                "netlify",
                                "cloudflare",
                            ]
                        elif "angular" in deps or "@angular/core" in deps:
                            detected["framework"] = "Angular"
                            detected["type"] = "frontend"
                            detected["recommended_platforms"] = [
                                "vercel",
                                "netlify",
                                "cloudflare",
                            ]
                        else:
                            detected["type"] = "node"
                            detected["recommended_platforms"] = [
                                "railway",
                                "render",
                                "fly",
                                "heroku",
                            ]

                        detected["language"] = "javascript"

                        # Check for database dependencies
                        db_deps = [
                            "prisma",
                            "typeorm",
                            "sequelize",
                            "mongoose",
                            "pg",
                            "mysql2",
                            "mongodb",
                        ]
                        if any(db in deps for db in db_deps):
                            detected["has_database"] = True
                            # Prioritize platforms with DB support
                            detected["recommended_platforms"] = [
                                "railway",
                                "render",
                                "fly",
                                "heroku",
                            ]

                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(
                        "detect_project_type.package_json_error", error=str(e)
                    )

            # Parse requirements.txt/pyproject.toml for Python projects
            elif filename in ("requirements.txt", "pyproject.toml"):
                detected["language"] = "python"

                try:
                    if filename == "requirements.txt":
                        with open(filepath, "r") as f:
                            content = f.read().lower()
                    else:
                        content = ""

                    if "django" in content or os.path.exists(
                        os.path.join(workspace_path, "manage.py")
                    ):
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

                    detected["recommended_platforms"] = [
                        "railway",
                        "render",
                        "fly",
                        "heroku",
                    ]

                    # Check for database
                    if any(
                        db in content
                        for db in ["psycopg", "sqlalchemy", "django", "pymongo"]
                    ):
                        detected["has_database"] = True

                except IOError as e:
                    logger.warning(
                        "detect_project_type.requirements_error", error=str(e)
                    )

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
        detected["recommended_platforms"] = [
            "fly",
            "railway",
            "render",
            "aws",
            "gcloud",
        ]

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

    lines.append(
        f"\n**Detected Files**: {', '.join(detected['detected_files']) or 'None'}"
    )

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
            env=_get_command_env(),
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
                env=_get_command_env(),
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
    lines.append(
        f"**Description**: {config.get('description', 'Cloud deployment platform')}\n"
    )

    lines.append("### Prerequisites")
    lines.append(f"1. Install CLI: `{config['install']}`")
    lines.append(f"2. Login: `{config['login']}`\n")

    lines.append("### Deploy Command")
    lines.append(f"```bash\n{config['deploy']}\n```\n")

    if config.get("env_set"):
        lines.append("### Set Environment Variables")
        lines.append(f"```bash\n{config['env_set']}\n```\n")

    lines.append("### Check Status")
    status_cmd = config.get("status", f"{config['cli']} status")
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


# ============================================================================
# REAL EXECUTION TOOLS - These actually deploy!
# ============================================================================


async def execute_deployment(
    context: Dict[str, Any],
    platform: str,
    workspace_path: Optional[str] = None,
    environment: str = "production",
    env_vars: Optional[Dict[str, str]] = None,
    dry_run: bool = False,
    skip_confirmation: bool = False,
) -> ToolResult:
    """
    Execute a REAL deployment to the specified platform.

    ⚠️ WARNING: This will actually deploy your application!

    Args:
        platform: Target platform (vercel, railway, fly, netlify, heroku, etc.)
        workspace_path: Path to the project to deploy
        environment: Target environment (production, staging, preview)
        env_vars: Environment variables to set
        dry_run: If True, only show what would be done
        skip_confirmation: If True, skip the confirmation dialog (dangerous!)

    Returns:
        Deployment result with URL and status
    """
    if not EXECUTION_SERVICES_AVAILABLE:
        return ToolResult(
            output="⚠️ Execution services not available. Running in information-only mode.\n\n"
            f"To deploy to {platform}, run:\n```bash\n{PLATFORM_CLIS.get(platform, {}).get('deploy', 'Unknown platform')}\n```",
            sources=[],
        )

    platform = platform.lower()
    workspace_path = workspace_path or os.getcwd()
    env_vars = env_vars or {}

    # Map platform string to enum
    platform_map = {
        "vercel": DeploymentPlatform.VERCEL,
        "railway": DeploymentPlatform.RAILWAY,
        "fly": DeploymentPlatform.FLY,
        "netlify": DeploymentPlatform.NETLIFY,
        "heroku": DeploymentPlatform.HEROKU,
        "aws_ecs": DeploymentPlatform.AWS_ECS,
        "aws_lambda": DeploymentPlatform.AWS_LAMBDA,
        "gcp_cloud_run": DeploymentPlatform.GCP_CLOUD_RUN,
        "kubernetes": DeploymentPlatform.KUBERNETES,
        "docker": DeploymentPlatform.DOCKER,
    }

    deployment_platform = platform_map.get(platform)
    if not deployment_platform:
        available = ", ".join(platform_map.keys())
        return ToolResult(
            output=f"Unknown platform: {platform}\n\nAvailable platforms for execution: {available}",
            sources=[],
        )

    # Check prerequisites
    prereq_ok, prereq_msg = await deployment_executor_service.check_prerequisites(
        deployment_platform
    )
    if not prereq_ok:
        config = PLATFORM_CLIS.get(platform, {})
        return ToolResult(
            output=f"## ❌ Prerequisites Not Met\n\n{prereq_msg}\n\n"
            f"**To fix:**\n"
            f"1. Install CLI: `{config.get('install', 'See platform docs')}`\n"
            f"2. Login: `{config.get('login', 'See platform docs')}`",
            sources=[],
        )

    # Create execution request for confirmation
    if not skip_confirmation and not dry_run:
        request = execution_confirmation_service.create_execution_request(
            operation_name="deploy.execute",
            description=f"Deploy application to {platform.title()} ({environment} environment)",
            parameters={
                "platform": platform,
                "workspace_path": workspace_path,
                "environment": environment,
                "env_vars": list(env_vars.keys()),  # Don't expose values
            },
            environment=environment,
            affected_resources=[f"{platform} deployment", workspace_path],
            estimated_duration="2-10 minutes",
        )

        # Format the confirmation request for the frontend
        ui_data = execution_confirmation_service.format_request_for_ui(request)

        return ToolResult(
            output=f"## ⚠️ Deployment Confirmation Required\n\n"
            f"**Operation**: Deploy to {platform.title()}\n"
            f"**Environment**: {environment}\n"
            f"**Risk Level**: {request.risk_level.value.upper()}\n\n"
            f"### Warnings\n"
            + "\n".join([f"- {w.message}" for w in request.warnings])
            + f"\n\n**Request ID**: `{request.id}`\n\n"
            f"To approve, call `deploy.confirm` with this request ID."
            f"\n\n```json\n{json.dumps(ui_data, indent=2)}\n```",
            sources=[{"type": "execution_request", "data": ui_data}],
        )

    # Execute the deployment
    config = DeploymentConfig(
        platform=deployment_platform,
        workspace_path=workspace_path,
        environment=environment,
        env_vars=env_vars,
        dry_run=dry_run,
    )

    if dry_run:
        return ToolResult(
            output=f"## 🔍 Dry Run - Deployment Preview\n\n"
            f"**Platform**: {platform.title()}\n"
            f"**Environment**: {environment}\n"
            f"**Workspace**: {workspace_path}\n"
            f"**Environment Variables**: {len(env_vars)} configured\n\n"
            f"✅ Prerequisites checked and passed\n"
            f"✅ Would execute: `{PLATFORM_CLIS.get(platform, {}).get('deploy', 'platform deploy')}`\n\n"
            f"To actually deploy, set `dry_run=False`",
            sources=[],
        )

    # Actually execute the deployment
    result = await deployment_executor_service.execute_deployment(config)

    if result.success:
        output = "## ✅ Deployment Successful!\n\n"
        output += f"**Platform**: {platform.title()}\n"
        output += f"**Environment**: {environment}\n"
        output += f"**Duration**: {result.duration_seconds:.1f}s\n"

        if result.deployment_url:
            output += f"\n### 🌐 Deployment URL\n{result.deployment_url}\n"

        if result.deployment_id:
            output += f"\n**Deployment ID**: `{result.deployment_id}`\n"

        if result.rollback_id:
            output += f"\n### 🔄 Rollback\nTo rollback, use deployment ID: `{result.rollback_id}`\n"

        return ToolResult(
            output=output,
            sources=[{"type": "deployment", "url": result.deployment_url}],
        )
    else:
        output = "## ❌ Deployment Failed\n\n"
        output += f"**Platform**: {platform.title()}\n"
        output += f"**Error**: {result.error}\n\n"

        if result.build_logs:
            output += "### Build Logs\n```\n"
            output += "\n".join(result.build_logs[-20:])  # Last 20 lines
            output += "\n```\n"

        return ToolResult(output=output, sources=[])


async def confirm_deployment(
    context: Dict[str, Any],
    request_id: str,
    confirmation_phrase: Optional[str] = None,
) -> ToolResult:
    """
    Confirm and execute a pending deployment request.

    Args:
        request_id: The execution request ID from deploy.execute
        confirmation_phrase: Required phrase for critical operations
    """
    if not EXECUTION_SERVICES_AVAILABLE:
        return ToolResult(
            output="⚠️ Execution services not available.",
            sources=[],
        )

    user_id = context.get("user_id", "unknown")

    # Approve the request
    approved, message = await execution_confirmation_service.approve_execution(
        request_id=request_id,
        user_id=user_id,
        confirmation_input=confirmation_phrase,
    )

    if not approved:
        return ToolResult(
            output=f"## ❌ Approval Failed\n\n{message}",
            sources=[],
        )

    # Get the request details
    pending = execution_confirmation_service.get_pending_requests()
    request = next((r for r in pending if r.id == request_id), None)

    if not request:
        return ToolResult(
            output="## ❌ Request Not Found\n\nThe request may have expired or already been executed.",
            sources=[],
        )

    # Execute the deployment
    params = request.parameters
    platform_map = {
        "vercel": DeploymentPlatform.VERCEL,
        "railway": DeploymentPlatform.RAILWAY,
        "fly": DeploymentPlatform.FLY,
        "netlify": DeploymentPlatform.NETLIFY,
        "heroku": DeploymentPlatform.HEROKU,
    }

    config = DeploymentConfig(
        platform=platform_map.get(
            params.get("platform", ""), DeploymentPlatform.VERCEL
        ),
        workspace_path=params.get("workspace_path", "."),
        environment=params.get("environment", "production"),
        dry_run=False,
    )

    async def executor(p):
        return await deployment_executor_service.execute_deployment(config)

    result = await execution_confirmation_service.execute_approved_request(
        request_id=request_id,
        executor=executor,
    )

    if result.success:
        return ToolResult(
            output=f"## ✅ Deployment Executed Successfully!\n\n"
            f"**Duration**: {result.duration_seconds:.1f}s\n"
            f"**Output**:\n{result.output}",
            sources=[],
        )
    else:
        return ToolResult(
            output=f"## ❌ Deployment Failed\n\n{result.error}",
            sources=[],
        )


async def rollback_deployment(
    context: Dict[str, Any],
    platform: str,
    deployment_id: str,
    workspace_path: Optional[str] = None,
) -> ToolResult:
    """
    Rollback to a previous deployment.

    Args:
        platform: The deployment platform
        deployment_id: The deployment ID to rollback to
        workspace_path: Path to the project
    """
    if not EXECUTION_SERVICES_AVAILABLE:
        return ToolResult(
            output="⚠️ Execution services not available.",
            sources=[],
        )

    platform = platform.lower()
    workspace_path = workspace_path or os.getcwd()

    platform_map = {
        "vercel": DeploymentPlatform.VERCEL,
        "railway": DeploymentPlatform.RAILWAY,
        "fly": DeploymentPlatform.FLY,
        "kubernetes": DeploymentPlatform.KUBERNETES,
    }

    deployment_platform = platform_map.get(platform)
    if not deployment_platform:
        return ToolResult(
            output=f"Rollback not supported for platform: {platform}",
            sources=[],
        )

    result = await deployment_executor_service.rollback_deployment(
        platform=deployment_platform,
        deployment_id=deployment_id,
        workspace_path=workspace_path,
    )

    if result.success:
        return ToolResult(
            output=f"## ✅ Rollback Successful\n\n"
            f"**Platform**: {platform.title()}\n"
            f"**Rolled back to**: {deployment_id}\n"
            f"**Duration**: {result.duration_seconds:.1f}s",
            sources=[],
        )
    else:
        return ToolResult(
            output=f"## ❌ Rollback Failed\n\n{result.error}",
            sources=[],
        )


async def get_deployment_status(
    context: Dict[str, Any],
    platform: str,
    deployment_id: str,
) -> ToolResult:
    """
    Get the status of a deployment.

    Args:
        platform: The deployment platform
        deployment_id: The deployment ID to check
    """
    if not EXECUTION_SERVICES_AVAILABLE:
        return ToolResult(
            output="⚠️ Execution services not available.",
            sources=[],
        )

    platform = platform.lower()

    platform_map = {
        "vercel": DeploymentPlatform.VERCEL,
        "railway": DeploymentPlatform.RAILWAY,
        "fly": DeploymentPlatform.FLY,
    }

    deployment_platform = platform_map.get(platform)
    if not deployment_platform:
        return ToolResult(
            output=f"Status check not supported for platform: {platform}",
            sources=[],
        )

    status = await deployment_executor_service.get_deployment_status(
        platform=deployment_platform,
        deployment_id=deployment_id,
    )

    return ToolResult(
        output=f"## Deployment Status\n\n```json\n{json.dumps(status, indent=2)}\n```",
        sources=[],
    )


# Export tools for the agent dispatcher
DEPLOYMENT_TOOLS = {
    "deploy_detect_project": detect_project_type,
    "deploy_check_cli": check_deployment_cli,
    "deploy_get_info": get_deployment_info,
    "deploy_list_platforms": list_supported_platforms,
    # Real execution tools
    "deploy_execute": execute_deployment,
    "deploy_confirm": confirm_deployment,
    "deploy_rollback": rollback_deployment,
    "deploy_status": get_deployment_status,
}
