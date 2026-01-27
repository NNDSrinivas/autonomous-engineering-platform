"""
Secrets management tools for NAVI agent.

Provides tools for managing secrets and environment variables:
- Generate .env templates
- Sync secrets to deployment platforms
- Audit for exposed secrets
- Setup secrets providers (Vault, AWS Secrets Manager)

Works dynamically across platforms.
"""

import os
import re
import json
from typing import Any, Dict, List, Optional, Set
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


# Common secret patterns to detect
SECRET_PATTERNS = [
    (r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?([a-zA-Z0-9_-]{20,})["\']?', "API_KEY"),
    (r'(?i)(secret[_-]?key|secretkey)\s*[:=]\s*["\']?([a-zA-Z0-9_-]{20,})["\']?', "SECRET_KEY"),
    (r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']?([^\s"\']{8,})["\']?', "PASSWORD"),
    (r'(?i)(token|auth[_-]?token)\s*[:=]\s*["\']?([a-zA-Z0-9_.-]{20,})["\']?', "TOKEN"),
    (r'(?i)(aws[_-]?access[_-]?key[_-]?id)\s*[:=]\s*["\']?(AKIA[0-9A-Z]{16})["\']?', "AWS_ACCESS_KEY"),
    (r'(?i)(aws[_-]?secret[_-]?access[_-]?key)\s*[:=]\s*["\']?([a-zA-Z0-9/+=]{40})["\']?', "AWS_SECRET_KEY"),
    (r'(?i)(database[_-]?url|db[_-]?url)\s*[:=]\s*["\']?(postgres|mysql|mongodb)://[^\s"\']+["\']?', "DATABASE_URL"),
    (r'(?i)(private[_-]?key)\s*[:=]\s*["\']?-----BEGIN[^\s"\']+["\']?', "PRIVATE_KEY"),
    (r'sk_live_[a-zA-Z0-9]{24,}', "STRIPE_SECRET_KEY"),
    (r'sk_test_[a-zA-Z0-9]{24,}', "STRIPE_TEST_KEY"),
    (r'ghp_[a-zA-Z0-9]{36}', "GITHUB_TOKEN"),
    (r'glpat-[a-zA-Z0-9\-_]{20,}', "GITLAB_TOKEN"),
    (r'xox[baprs]-[a-zA-Z0-9-]+', "SLACK_TOKEN"),
]

# Platform CLI commands for setting secrets
PLATFORM_SECRET_COMMANDS = {
    "vercel": {
        "set": "vercel env add {key} {environment}",
        "list": "vercel env ls",
        "remove": "vercel env rm {key} {environment}",
        "pull": "vercel env pull .env.local",
    },
    "railway": {
        "set": "railway variables set {key}={value}",
        "list": "railway variables",
        "remove": "railway variables unset {key}",
    },
    "fly": {
        "set": "fly secrets set {key}={value}",
        "list": "fly secrets list",
        "remove": "fly secrets unset {key}",
    },
    "netlify": {
        "set": "netlify env:set {key} {value}",
        "list": "netlify env:list",
        "remove": "netlify env:unset {key}",
    },
    "heroku": {
        "set": "heroku config:set {key}={value}",
        "list": "heroku config",
        "remove": "heroku config:unset {key}",
    },
    "render": {
        "set": "# Use Render dashboard to set environment variables",
        "list": "# Use Render dashboard",
        "remove": "# Use Render dashboard",
    },
    "aws": {
        "set": "aws secretsmanager create-secret --name {key} --secret-string {value}",
        "list": "aws secretsmanager list-secrets",
        "remove": "aws secretsmanager delete-secret --secret-id {key}",
    },
    "gcp": {
        "set": "echo -n {value} | gcloud secrets create {key} --data-file=-",
        "list": "gcloud secrets list",
        "remove": "gcloud secrets delete {key}",
    },
}

# Common environment variables by framework
FRAMEWORK_ENV_VARS = {
    "nextjs": {
        "required": [
            ("NEXT_PUBLIC_API_URL", "Public API URL for frontend", "https://api.example.com"),
            ("DATABASE_URL", "PostgreSQL connection string", "postgresql://user:pass@host:5432/db"),
        ],
        "optional": [
            ("NEXT_PUBLIC_SENTRY_DSN", "Sentry DSN for error tracking", ""),
            ("NEXTAUTH_SECRET", "NextAuth.js secret", ""),
            ("NEXTAUTH_URL", "NextAuth.js callback URL", "http://localhost:3000"),
        ],
    },
    "express": {
        "required": [
            ("PORT", "Server port", "3000"),
            ("NODE_ENV", "Environment", "development"),
            ("DATABASE_URL", "Database connection string", ""),
        ],
        "optional": [
            ("JWT_SECRET", "JWT signing secret", ""),
            ("REDIS_URL", "Redis connection URL", ""),
            ("CORS_ORIGIN", "CORS allowed origins", "*"),
        ],
    },
    "fastapi": {
        "required": [
            ("DATABASE_URL", "Database connection string", "postgresql://user:pass@host:5432/db"),
            ("SECRET_KEY", "Application secret key", ""),
        ],
        "optional": [
            ("REDIS_URL", "Redis connection URL", ""),
            ("SENTRY_DSN", "Sentry DSN", ""),
            ("DEBUG", "Debug mode", "false"),
        ],
    },
    "django": {
        "required": [
            ("SECRET_KEY", "Django secret key", ""),
            ("DATABASE_URL", "Database connection string", ""),
            ("ALLOWED_HOSTS", "Allowed hosts", "localhost,127.0.0.1"),
        ],
        "optional": [
            ("DEBUG", "Debug mode", "false"),
            ("REDIS_URL", "Redis URL for caching", ""),
            ("EMAIL_HOST", "SMTP server", ""),
        ],
    },
}


async def generate_env_template(
    context: Dict[str, Any],
    workspace_path: str,
) -> ToolResult:
    """
    Generate .env.example file by scanning code for environment variables.

    Scans source files and configuration for env var references and
    generates a template with descriptions.

    Args:
        workspace_path: Path to the project root

    Returns:
        ToolResult with generated .env.example content
    """
    logger.info("generate_env_template", workspace_path=workspace_path)

    if not os.path.exists(workspace_path):
        return ToolResult(output=f"Directory not found: {workspace_path}", sources=[])

    # Detect framework
    framework = _detect_framework(workspace_path)

    # Scan for env var usage
    found_vars = _scan_for_env_vars(workspace_path)

    # Merge with framework defaults
    framework_vars = FRAMEWORK_ENV_VARS.get(framework, {})
    all_vars = {}

    # Add framework required vars
    for name, desc, default in framework_vars.get("required", []):
        all_vars[name] = {"description": desc, "default": default, "required": True}

    # Add found vars
    for var in found_vars:
        if var not in all_vars:
            all_vars[var] = {"description": "", "default": "", "required": False}

    # Add framework optional vars
    for name, desc, default in framework_vars.get("optional", []):
        if name not in all_vars:
            all_vars[name] = {"description": desc, "default": default, "required": False}

    # Generate .env.example content
    env_content = [
        "# Environment Variables",
        "# Copy this file to .env and fill in your values",
        "#",
        f"# Generated for: {framework or 'generic'} project",
        "",
    ]

    # Required section
    required_vars = {k: v for k, v in all_vars.items() if v.get("required")}
    if required_vars:
        env_content.append("# === Required ===")
        for name, config in sorted(required_vars.items()):
            if config.get("description"):
                env_content.append(f"# {config['description']}")
            env_content.append(f"{name}={config.get('default', '')}")
            env_content.append("")

    # Optional section
    optional_vars = {k: v for k, v in all_vars.items() if not v.get("required")}
    if optional_vars:
        env_content.append("# === Optional ===")
        for name, config in sorted(optional_vars.items()):
            if config.get("description"):
                env_content.append(f"# {config['description']}")
            env_content.append(f"# {name}={config.get('default', '')}")
            env_content.append("")

    # Build output
    lines = ["## Generated Environment Template\n"]
    lines.append(f"**Framework**: {framework or 'generic'}")
    lines.append(f"**Variables Found**: {len(found_vars)}")
    lines.append(f"**Total Variables**: {len(all_vars)}")

    lines.append("\n### .env.example")
    lines.append("```env")
    lines.append("\n".join(env_content))
    lines.append("```")

    lines.append("\n### Security Notes")
    lines.append("- Never commit `.env` to version control")
    lines.append("- Use different values for each environment")
    lines.append("- Rotate secrets regularly")
    lines.append("- Use a secrets manager in production")

    return ToolResult(output="\n".join(lines), sources=[])


async def setup_secrets_provider(
    context: Dict[str, Any],
    workspace_path: str,
    provider: str = "vault",
) -> ToolResult:
    """
    Set up a secrets management provider.

    Args:
        workspace_path: Path to the project root
        provider: Secrets provider (vault, aws_secrets_manager, gcp_secret_manager)

    Returns:
        ToolResult with setup instructions
    """
    logger.info("setup_secrets_provider", provider=provider)

    lines = [f"## Secrets Provider Setup: {provider.replace('_', ' ').title()}\n"]

    if provider == "vault":
        lines.append("### HashiCorp Vault Setup")
        lines.append("\n**1. Install Vault CLI**")
        lines.append("```bash")
        lines.append("brew install vault  # macOS")
        lines.append("# or")
        lines.append("sudo apt-get install vault  # Ubuntu")
        lines.append("```")

        lines.append("\n**2. Configure Vault Address**")
        lines.append("```bash")
        lines.append("export VAULT_ADDR='https://vault.example.com:8200'")
        lines.append("vault login")
        lines.append("```")

        lines.append("\n**3. Store Secrets**")
        lines.append("```bash")
        lines.append("vault kv put secret/myapp/production \\")
        lines.append("  DATABASE_URL='postgresql://...' \\")
        lines.append("  API_KEY='...'")
        lines.append("```")

        lines.append("\n**4. Read in Application**")
        lines.append("```typescript")
        lines.append('import Vault from "node-vault";')
        lines.append("")
        lines.append("const vault = Vault({")
        lines.append("  endpoint: process.env.VAULT_ADDR,")
        lines.append("  token: process.env.VAULT_TOKEN,")
        lines.append("});")
        lines.append("")
        lines.append('const secrets = await vault.read("secret/data/myapp/production");')
        lines.append("const dbUrl = secrets.data.data.DATABASE_URL;")
        lines.append("```")

    elif provider == "aws_secrets_manager":
        lines.append("### AWS Secrets Manager Setup")
        lines.append("\n**1. Create Secret**")
        lines.append("```bash")
        lines.append("aws secretsmanager create-secret \\")
        lines.append('  --name "myapp/production" \\')
        lines.append('  --secret-string \'{"DATABASE_URL":"postgresql://...","API_KEY":"..."}\'')
        lines.append("```")

        lines.append("\n**2. Read in Application (Node.js)**")
        lines.append("```typescript")
        lines.append('import { SecretsManagerClient, GetSecretValueCommand } from "@aws-sdk/client-secrets-manager";')
        lines.append("")
        lines.append("const client = new SecretsManagerClient({ region: 'us-east-1' });")
        lines.append("")
        lines.append("async function getSecrets() {")
        lines.append("  const response = await client.send(")
        lines.append("    new GetSecretValueCommand({ SecretId: 'myapp/production' })")
        lines.append("  );")
        lines.append("  return JSON.parse(response.SecretString!);")
        lines.append("}")
        lines.append("```")

        lines.append("\n**3. Read in Application (Python)**")
        lines.append("```python")
        lines.append("import boto3")
        lines.append("import json")
        lines.append("")
        lines.append("def get_secrets():")
        lines.append("    client = boto3.client('secretsmanager', region_name='us-east-1')")
        lines.append("    response = client.get_secret_value(SecretId='myapp/production')")
        lines.append("    return json.loads(response['SecretString'])")
        lines.append("```")

    elif provider == "gcp_secret_manager":
        lines.append("### GCP Secret Manager Setup")
        lines.append("\n**1. Enable API**")
        lines.append("```bash")
        lines.append("gcloud services enable secretmanager.googleapis.com")
        lines.append("```")

        lines.append("\n**2. Create Secret**")
        lines.append("```bash")
        lines.append('echo -n "postgresql://..." | gcloud secrets create DATABASE_URL --data-file=-')
        lines.append("```")

        lines.append("\n**3. Read in Application**")
        lines.append("```python")
        lines.append("from google.cloud import secretmanager")
        lines.append("")
        lines.append("def get_secret(secret_id: str, version: str = 'latest'):")
        lines.append("    client = secretmanager.SecretManagerServiceClient()")
        lines.append("    name = f'projects/{project_id}/secrets/{secret_id}/versions/{version}'")
        lines.append("    response = client.access_secret_version(name=name)")
        lines.append("    return response.payload.data.decode('UTF-8')")
        lines.append("```")

    lines.append("\n### Best Practices")
    lines.append("- Use IAM roles/service accounts instead of static credentials")
    lines.append("- Enable audit logging")
    lines.append("- Rotate secrets regularly")
    lines.append("- Use different secrets per environment")
    lines.append("- Cache secrets appropriately (with TTL)")

    return ToolResult(output="\n".join(lines), sources=[])


async def sync_env_to_platform(
    context: Dict[str, Any],
    env_file: str,
    platform: str,
    environment: str = "production",
) -> ToolResult:
    """
    Generate commands to sync environment variables to a deployment platform.

    Args:
        env_file: Path to .env file
        platform: Deployment platform (vercel, railway, fly, etc.)
        environment: Target environment (production, preview, development)

    Returns:
        ToolResult with sync commands
    """
    logger.info(
        "sync_env_to_platform",
        env_file=env_file,
        platform=platform,
        environment=environment,
    )

    platform = platform.lower()
    if platform not in PLATFORM_SECRET_COMMANDS:
        available = ", ".join(PLATFORM_SECRET_COMMANDS.keys())
        return ToolResult(
            output=f"Unsupported platform: {platform}\n\nAvailable: {available}",
            sources=[],
        )

    # Parse env file
    env_vars = {}
    if os.path.exists(env_file):
        try:
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        env_vars[key.strip()] = value.strip()
        except IOError:
            pass

    commands = PLATFORM_SECRET_COMMANDS[platform]

    lines = [f"## Sync Environment Variables to {platform.title()}\n"]
    lines.append(f"**Platform**: {platform}")
    lines.append(f"**Environment**: {environment}")
    lines.append(f"**Variables**: {len(env_vars)}")

    # Generate set commands
    lines.append("\n### Set Environment Variables")
    lines.append("```bash")

    if env_vars:
        for key, value in env_vars.items():
            # Mask sensitive values in output
            display_value = "*****" if _is_sensitive(key) else value
            cmd = commands["set"].format(key=key, value=value, environment=environment)
            lines.append(f"# {key}={display_value}")
            lines.append(cmd)
            lines.append("")
    else:
        lines.append("# No variables found in env file")
        lines.append(commands["set"].format(key="KEY", value="VALUE", environment=environment))

    lines.append("```")

    # List command
    lines.append("\n### Verify Variables")
    lines.append("```bash")
    lines.append(commands["list"])
    lines.append("```")

    # Platform-specific notes
    lines.append(f"\n### Notes for {platform.title()}")
    if platform == "vercel":
        lines.append("- Variables with `NEXT_PUBLIC_` prefix are exposed to the browser")
        lines.append("- Redeploy after changing environment variables")
        lines.append("- Use `vercel env pull .env.local` to sync from Vercel")
    elif platform == "railway":
        lines.append("- Changes take effect immediately")
        lines.append("- Use Railway dashboard for bulk import")
    elif platform == "fly":
        lines.append("- Secrets are encrypted at rest")
        lines.append("- App restarts automatically after secret changes")

    return ToolResult(output="\n".join(lines), sources=[])


async def audit_secrets_exposure(
    context: Dict[str, Any],
    workspace_path: str,
) -> ToolResult:
    """
    Audit a codebase for exposed secrets.

    Scans for:
    - Hardcoded API keys, tokens, passwords
    - .env files in git history
    - Configuration files with sensitive data

    Args:
        workspace_path: Path to the project root

    Returns:
        ToolResult with audit findings
    """
    logger.info("audit_secrets_exposure", workspace_path=workspace_path)

    if not os.path.exists(workspace_path):
        return ToolResult(output=f"Directory not found: {workspace_path}", sources=[])

    findings = []

    # Check if .env is in gitignore
    gitignore_path = os.path.join(workspace_path, ".gitignore")
    env_ignored = False
    if os.path.exists(gitignore_path):
        try:
            with open(gitignore_path, "r") as f:
                content = f.read()
                env_ignored = ".env" in content or "*.env" in content
        except IOError:
            pass

    if not env_ignored:
        findings.append({
            "severity": "high",
            "type": "configuration",
            "message": ".env is not in .gitignore - secrets may be committed",
            "file": ".gitignore",
            "fix": "Add '.env' and '.env.*' to .gitignore",
        })

    # Check for .env files
    for env_file in [".env", ".env.local", ".env.production"]:
        env_path = os.path.join(workspace_path, env_file)
        if os.path.exists(env_path):
            findings.append({
                "severity": "warning",
                "type": "file",
                "message": f"{env_file} exists - ensure it's not committed",
                "file": env_file,
                "fix": f"Ensure {env_file} is in .gitignore",
            })

    # Scan source files for hardcoded secrets
    for root, dirs, files in os.walk(workspace_path):
        # Skip common non-source directories
        dirs[:] = [d for d in dirs if d not in (
            "node_modules", ".git", "dist", "build", "__pycache__",
            ".next", "venv", ".venv", "coverage"
        )]

        for filename in files:
            if not _is_source_file(filename):
                continue

            filepath = os.path.join(root, filename)
            rel_path = os.path.relpath(filepath, workspace_path)

            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                for pattern, secret_type in SECRET_PATTERNS:
                    matches = re.finditer(pattern, content)
                    for match in matches:
                        # Skip if it's an env var reference
                        if "process.env" in content[max(0, match.start()-20):match.start()]:
                            continue
                        if "os.environ" in content[max(0, match.start()-20):match.start()]:
                            continue

                        line_num = content[:match.start()].count("\n") + 1
                        findings.append({
                            "severity": "critical",
                            "type": "hardcoded",
                            "message": f"Potential {secret_type} found",
                            "file": rel_path,
                            "line": line_num,
                            "fix": "Move to environment variable",
                        })
            except IOError:
                continue

    # Build output
    lines = ["## Secrets Audit Report\n"]

    critical = [f for f in findings if f["severity"] == "critical"]
    high = [f for f in findings if f["severity"] == "high"]
    warning = [f for f in findings if f["severity"] == "warning"]

    lines.append(f"**Total Issues**: {len(findings)}")
    lines.append(f"- Critical: {len(critical)}")
    lines.append(f"- High: {len(high)}")
    lines.append(f"- Warning: {len(warning)}")

    if critical:
        lines.append("\n### Critical Issues")
        for finding in critical:
            lines.append(f"\n**{finding['message']}**")
            lines.append(f"- File: `{finding['file']}`" + (f":{finding.get('line', '')}" if finding.get('line') else ""))
            lines.append(f"- Fix: {finding['fix']}")

    if high:
        lines.append("\n### High Priority Issues")
        for finding in high:
            lines.append(f"\n**{finding['message']}**")
            lines.append(f"- File: `{finding['file']}`")
            lines.append(f"- Fix: {finding['fix']}")

    if warning:
        lines.append("\n### Warnings")
        for finding in warning:
            lines.append(f"- {finding['message']} (`{finding['file']}`)")

    if not findings:
        lines.append("\nNo issues found! Your secrets appear to be properly managed.")

    lines.append("\n### Recommendations")
    lines.append("1. Never commit secrets to version control")
    lines.append("2. Use environment variables for all sensitive values")
    lines.append("3. Use a secrets manager in production")
    lines.append("4. Rotate any exposed secrets immediately")
    lines.append("5. Consider using git-secrets or similar tools for pre-commit checks")

    return ToolResult(output="\n".join(lines), sources=[])


async def rotate_secrets(
    context: Dict[str, Any],
    workspace_path: str,
    secrets: List[str],
) -> ToolResult:
    """
    Generate a secret rotation plan.

    Args:
        workspace_path: Path to the project root
        secrets: List of secret names to rotate

    Returns:
        ToolResult with rotation plan
    """
    logger.info("rotate_secrets", secrets=secrets)

    lines = ["## Secret Rotation Plan\n"]
    lines.append(f"**Secrets to Rotate**: {len(secrets)}")

    for secret in secrets:
        lines.append(f"\n### {secret}")

        if "DATABASE" in secret.upper():
            lines.append("**Type**: Database Credentials")
            lines.append("\n**Rotation Steps**:")
            lines.append("1. Create new database user with same permissions")
            lines.append("2. Update application with new credentials")
            lines.append("3. Deploy and verify connection")
            lines.append("4. Disable old user")
            lines.append("5. Delete old user after grace period")

        elif "API" in secret.upper() or "KEY" in secret.upper():
            lines.append("**Type**: API Key")
            lines.append("\n**Rotation Steps**:")
            lines.append("1. Generate new API key in provider dashboard")
            lines.append("2. Update application configuration")
            lines.append("3. Deploy changes")
            lines.append("4. Verify API calls succeed")
            lines.append("5. Revoke old API key")

        elif "JWT" in secret.upper() or "SECRET" in secret.upper():
            lines.append("**Type**: Signing Secret")
            lines.append("\n**Rotation Steps**:")
            lines.append("1. Generate new secret (minimum 256 bits)")
            lines.append("2. Support both old and new secrets temporarily")
            lines.append("3. Deploy with dual-key support")
            lines.append("4. Wait for old tokens to expire")
            lines.append("5. Remove old secret")

        else:
            lines.append("**Type**: Generic Secret")
            lines.append("\n**Rotation Steps**:")
            lines.append("1. Generate new secret value")
            lines.append("2. Update in secrets manager")
            lines.append("3. Deploy application")
            lines.append("4. Verify functionality")
            lines.append("5. Remove old secret")

        lines.append("\n**Commands**:")
        lines.append("```bash")
        lines.append("# Generate new secret")
        lines.append("openssl rand -base64 32")
        lines.append("")
        lines.append("# Update in Vercel")
        lines.append(f"vercel env add {secret} production")
        lines.append("")
        lines.append("# Update in Railway")
        lines.append(f"railway variables set {secret}=$NEW_VALUE")
        lines.append("```")

    lines.append("\n### Post-Rotation Checklist")
    lines.append("- [ ] All services restarted with new secrets")
    lines.append("- [ ] Monitoring shows no errors")
    lines.append("- [ ] Old secrets revoked/deleted")
    lines.append("- [ ] Rotation documented in security log")
    lines.append("- [ ] Next rotation date scheduled")

    return ToolResult(output="\n".join(lines), sources=[])


# Helper functions

def _detect_framework(workspace_path: str) -> Optional[str]:
    """Detect project framework."""
    package_json_path = os.path.join(workspace_path, "package.json")

    if os.path.exists(package_json_path):
        try:
            with open(package_json_path, "r") as f:
                pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                if "next" in deps:
                    return "nextjs"
                if "express" in deps:
                    return "express"
        except (json.JSONDecodeError, IOError):
            pass

    requirements_path = os.path.join(workspace_path, "requirements.txt")
    if os.path.exists(requirements_path):
        try:
            with open(requirements_path, "r") as f:
                content = f.read().lower()
                if "fastapi" in content:
                    return "fastapi"
                if "django" in content:
                    return "django"
        except IOError:
            pass

    if os.path.exists(os.path.join(workspace_path, "manage.py")):
        return "django"

    return None


def _scan_for_env_vars(workspace_path: str) -> Set[str]:
    """Scan source files for environment variable references."""
    env_vars = set()

    # Patterns to match env var usage
    patterns = [
        r'process\.env\.([A-Z][A-Z0-9_]+)',
        r'process\.env\[["\']([A-Z][A-Z0-9_]+)["\']\]',
        r'os\.environ\.get\(["\']([A-Z][A-Z0-9_]+)["\']',
        r'os\.environ\[["\']([A-Z][A-Z0-9_]+)["\']\]',
        r'os\.getenv\(["\']([A-Z][A-Z0-9_]+)["\']',
        r'env\(["\']([A-Z][A-Z0-9_]+)["\']',
    ]

    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [d for d in dirs if d not in (
            "node_modules", ".git", "dist", "build", "__pycache__",
            ".next", "venv", ".venv"
        )]

        for filename in files:
            if not _is_source_file(filename):
                continue

            filepath = os.path.join(root, filename)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                for pattern in patterns:
                    matches = re.findall(pattern, content)
                    env_vars.update(matches)
            except IOError:
                continue

    return env_vars


def _is_source_file(filename: str) -> bool:
    """Check if a file is a source code file."""
    extensions = {
        ".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rs",
        ".java", ".rb", ".php", ".env", ".yaml", ".yml",
        ".json", ".toml"
    }
    _, ext = os.path.splitext(filename)
    return ext.lower() in extensions


def _is_sensitive(key: str) -> bool:
    """Check if a key name indicates sensitive data."""
    sensitive_patterns = [
        "password", "secret", "key", "token", "auth",
        "credential", "private", "api_key", "apikey"
    ]
    key_lower = key.lower()
    return any(pattern in key_lower for pattern in sensitive_patterns)


# Export tools for the agent dispatcher
SECRETS_TOOLS = {
    "secrets_generate_env": generate_env_template,
    "secrets_setup_provider": setup_secrets_provider,
    "secrets_sync_to_platform": sync_env_to_platform,
    "secrets_audit": audit_secrets_exposure,
    "secrets_rotate": rotate_secrets,
}
