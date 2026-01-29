"""
Monitoring and observability tools for NAVI agent.

Provides tools to set up monitoring infrastructure:
- Error tracking (Sentry, Rollbar)
- APM (Datadog, New Relic)
- Logging configuration
- Health checks
- Alerting

Works dynamically for any project type.
"""

import os
import json
from typing import Any, Dict, Optional
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


# Provider configurations
ERROR_TRACKING_PROVIDERS = {
    "sentry": {
        "js_package": "@sentry/nextjs",
        "py_package": "sentry-sdk",
        "js_init": """import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: 1.0,
  replaysSessionSampleRate: 0.1,
  replaysOnErrorSampleRate: 1.0,
});
""",
        "py_init": """import sentry_sdk
from sentry_sdk.integrations.{framework} import {Framework}Integration

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    environment=os.environ.get("ENVIRONMENT", "production"),
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
    integrations=[
        {Framework}Integration(),
    ],
)
""",
        "config_files": {
            "sentry.client.config.ts": """import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  tracesSampleRate: 1.0,
  debug: false,
  replaysOnErrorSampleRate: 1.0,
  replaysSessionSampleRate: 0.1,
  integrations: [
    Sentry.replayIntegration({
      maskAllText: true,
      blockAllMedia: true,
    }),
  ],
});
""",
            "sentry.server.config.ts": """import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  tracesSampleRate: 1.0,
  debug: false,
});
""",
        },
    },
    "rollbar": {
        "js_package": "rollbar",
        "py_package": "rollbar",
        "js_init": """import Rollbar from "rollbar";

const rollbar = new Rollbar({
  accessToken: process.env.ROLLBAR_ACCESS_TOKEN,
  environment: process.env.NODE_ENV,
  captureUncaught: true,
  captureUnhandledRejections: true,
});

export default rollbar;
""",
        "py_init": """import rollbar

rollbar.init(
    access_token=os.environ.get("ROLLBAR_ACCESS_TOKEN"),
    environment=os.environ.get("ENVIRONMENT", "production"),
    code_version="1.0.0",
)
""",
    },
}

APM_PROVIDERS = {
    "datadog": {
        "js_package": "dd-trace",
        "py_package": "ddtrace",
        "js_init": """// Must be imported first
import tracer from "dd-trace";

tracer.init({
  service: process.env.DD_SERVICE || "my-service",
  env: process.env.DD_ENV || "production",
  version: process.env.DD_VERSION || "1.0.0",
  logInjection: true,
  profiling: true,
  runtimeMetrics: true,
});

export default tracer;
""",
        "py_init": """from ddtrace import tracer, patch_all

# Patch all supported libraries
patch_all()

tracer.configure(
    hostname=os.environ.get("DD_AGENT_HOST", "localhost"),
    port=int(os.environ.get("DD_TRACE_AGENT_PORT", 8126)),
)
""",
        "env_vars": [
            "DD_AGENT_HOST",
            "DD_SERVICE",
            "DD_ENV",
            "DD_VERSION",
            "DD_LOGS_INJECTION",
            "DD_PROFILING_ENABLED",
        ],
    },
    "newrelic": {
        "js_package": "newrelic",
        "py_package": "newrelic",
        "js_init": """// newrelic.js - place in project root
"use strict";

exports.config = {
  app_name: [process.env.NEW_RELIC_APP_NAME || "My Application"],
  license_key: process.env.NEW_RELIC_LICENSE_KEY,
  logging: {
    level: "info",
  },
  distributed_tracing: {
    enabled: true,
  },
  transaction_tracer: {
    enabled: true,
    record_sql: "obfuscated",
  },
  error_collector: {
    enabled: true,
  },
};
""",
        "py_init": """import newrelic.agent

newrelic.agent.initialize("newrelic.ini")
""",
        "env_vars": [
            "NEW_RELIC_LICENSE_KEY",
            "NEW_RELIC_APP_NAME",
            "NEW_RELIC_LOG_LEVEL",
        ],
    },
}

LOGGING_TEMPLATES = {
    "pino": """import pino from "pino";

const logger = pino({
  level: process.env.LOG_LEVEL || "info",
  transport: {
    target: "pino-pretty",
    options: {
      colorize: process.env.NODE_ENV !== "production",
    },
  },
  base: {
    service: process.env.SERVICE_NAME || "my-service",
    env: process.env.NODE_ENV,
  },
});

export default logger;
""",
    "winston": """import winston from "winston";

const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || "info",
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  defaultMeta: {
    service: process.env.SERVICE_NAME || "my-service",
  },
  transports: [
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize(),
        winston.format.simple()
      ),
    }),
  ],
});

export default logger;
""",
    "structlog": """import structlog
import logging

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)
""",
}

HEALTH_CHECK_TEMPLATES = {
    "nextjs": """// app/api/health/route.ts
import { NextResponse } from "next/server";

export async function GET() {
  const healthCheck = {
    status: "healthy",
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    checks: {
      database: await checkDatabase(),
      cache: await checkCache(),
    },
  };

  const isHealthy = Object.values(healthCheck.checks).every(
    (check) => check.status === "healthy"
  );

  return NextResponse.json(healthCheck, {
    status: isHealthy ? 200 : 503,
  });
}

async function checkDatabase() {
  try {
    // Add your database health check
    // await prisma.$queryRaw`SELECT 1`;
    return { status: "healthy" };
  } catch (error) {
    return { status: "unhealthy", error: error.message };
  }
}

async function checkCache() {
  try {
    // Add your cache health check
    // await redis.ping();
    return { status: "healthy" };
  } catch (error) {
    return { status: "unhealthy", error: error.message };
  }
}
""",
    "express": """// routes/health.ts
import { Router, Request, Response } from "express";

const router = Router();

router.get("/health", async (req: Request, res: Response) => {
  const healthCheck = {
    status: "healthy",
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    checks: {
      database: await checkDatabase(),
      cache: await checkCache(),
    },
  };

  const isHealthy = Object.values(healthCheck.checks).every(
    (check: any) => check.status === "healthy"
  );

  res.status(isHealthy ? 200 : 503).json(healthCheck);
});

router.get("/ready", async (req: Request, res: Response) => {
  // Readiness check - is the app ready to receive traffic?
  res.json({ status: "ready" });
});

router.get("/live", (req: Request, res: Response) => {
  // Liveness check - is the app alive?
  res.json({ status: "alive" });
});

async function checkDatabase() {
  try {
    // await db.query("SELECT 1");
    return { status: "healthy" };
  } catch (error: any) {
    return { status: "unhealthy", error: error.message };
  }
}

async function checkCache() {
  try {
    // await redis.ping();
    return { status: "healthy" };
  } catch (error: any) {
    return { status: "unhealthy", error: error.message };
  }
}

export default router;
""",
    "fastapi": '''"""
Health check endpoints
"""
from fastapi import APIRouter, Response
from datetime import datetime
import time

router = APIRouter()

start_time = time.time()


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    Returns overall system health status.
    """
    checks = {
        "database": await check_database(),
        "cache": await check_cache(),
    }

    is_healthy = all(check["status"] == "healthy" for check in checks.values())

    health_response = {
        "status": "healthy" if is_healthy else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime": time.time() - start_time,
        "checks": checks,
    }

    return Response(
        content=str(health_response),
        status_code=200 if is_healthy else 503,
        media_type="application/json",
    )


@router.get("/ready")
async def readiness_check():
    """
    Readiness check - is the app ready to receive traffic?
    """
    return {"status": "ready"}


@router.get("/live")
async def liveness_check():
    """
    Liveness check - is the app alive?
    """
    return {"status": "alive"}


async def check_database():
    """Check database connectivity."""
    try:
        # await db.execute("SELECT 1")
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_cache():
    """Check cache connectivity."""
    try:
        # await redis.ping()
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
''',
}


async def setup_error_tracking(
    context: Dict[str, Any],
    workspace_path: str,
    provider: str = "sentry",
    dsn: Optional[str] = None,
) -> ToolResult:
    """
    Set up error tracking in a project.

    Installs SDK, adds initialization code, and configures source maps.

    Args:
        workspace_path: Path to the project root
        provider: Error tracking provider (sentry, rollbar)
        dsn: DSN/access token (optional, uses env var if not provided)

    Returns:
        ToolResult with setup instructions and code
    """
    logger.info(
        "setup_error_tracking",
        workspace_path=workspace_path,
        provider=provider,
    )

    provider = provider.lower()
    if provider not in ERROR_TRACKING_PROVIDERS:
        available = ", ".join(ERROR_TRACKING_PROVIDERS.keys())
        return ToolResult(
            output=f"Unsupported provider: {provider}\n\nAvailable: {available}",
            sources=[],
        )

    config = ERROR_TRACKING_PROVIDERS[provider]

    # Detect project type
    project_type = _detect_project_type(workspace_path)

    lines = [f"## Error Tracking Setup: {provider.title()}\n"]
    lines.append(f"**Provider**: {provider}")
    lines.append(f"**Project Type**: {project_type}")

    # Installation
    lines.append("\n### 1. Installation")
    if project_type in ("nextjs", "react", "express", "node"):
        lines.append("```bash")
        lines.append(f"npm install {config['js_package']}")
        lines.append("```")
    else:
        lines.append("```bash")
        lines.append(f"pip install {config['py_package']}")
        lines.append("```")

    # Configuration
    lines.append("\n### 2. Configuration")

    if project_type in ("nextjs", "react", "express", "node"):
        if provider == "sentry" and project_type == "nextjs":
            lines.append("\n**Next.js requires additional config files:**\n")
            for filename, content in config.get("config_files", {}).items():
                lines.append(f"**{filename}**:")
                lines.append("```typescript")
                lines.append(content)
                lines.append("```\n")
        else:
            lines.append("**Initialize in your entry point:**")
            lines.append("```typescript")
            lines.append(config["js_init"])
            lines.append("```")
    else:
        framework = {"fastapi": "fastapi", "flask": "flask"}.get(project_type, "django")
        init_code = config["py_init"].format(
            framework=framework, Framework=framework.title()
        )
        lines.append("**Initialize in your main app:**")
        lines.append("```python")
        lines.append(init_code)
        lines.append("```")

    # Environment variables
    lines.append("\n### 3. Environment Variables")
    lines.append("```env")
    if provider == "sentry":
        dsn_placeholder = dsn or "https://xxx@xxx.ingest.sentry.io/xxx"
        lines.append(f"SENTRY_DSN={dsn_placeholder}")
        if project_type == "nextjs":
            lines.append(f"NEXT_PUBLIC_SENTRY_DSN={dsn_placeholder}")
    elif provider == "rollbar":
        lines.append("ROLLBAR_ACCESS_TOKEN=your-access-token")
    lines.append("```")

    # Source maps (for JavaScript)
    if project_type in ("nextjs", "react", "node"):
        lines.append("\n### 4. Source Maps")
        if provider == "sentry":
            lines.append("Configure source map uploads for better stack traces:")
            lines.append("```bash")
            lines.append("npx @sentry/wizard@latest -i nextjs")
            lines.append("```")

    lines.append("\n### Next Steps")
    lines.append(f"1. Get your DSN from the {provider.title()} dashboard")
    lines.append("2. Add the environment variable to your deployment platform")
    lines.append("3. Deploy and verify errors are being captured")

    return ToolResult(output="\n".join(lines), sources=[])


async def setup_apm(
    context: Dict[str, Any],
    workspace_path: str,
    provider: str = "datadog",
) -> ToolResult:
    """
    Set up Application Performance Monitoring (APM).

    Args:
        workspace_path: Path to the project root
        provider: APM provider (datadog, newrelic)

    Returns:
        ToolResult with setup instructions and code
    """
    logger.info("setup_apm", workspace_path=workspace_path, provider=provider)

    provider = provider.lower()
    if provider not in APM_PROVIDERS:
        available = ", ".join(APM_PROVIDERS.keys())
        return ToolResult(
            output=f"Unsupported provider: {provider}\n\nAvailable: {available}",
            sources=[],
        )

    config = APM_PROVIDERS[provider]
    project_type = _detect_project_type(workspace_path)

    lines = [f"## APM Setup: {provider.title()}\n"]
    lines.append(f"**Provider**: {provider}")
    lines.append(f"**Project Type**: {project_type}")

    # Installation
    lines.append("\n### 1. Installation")
    if project_type in ("nextjs", "react", "express", "node"):
        lines.append("```bash")
        lines.append(f"npm install {config['js_package']}")
        lines.append("```")
    else:
        lines.append("```bash")
        lines.append(f"pip install {config['py_package']}")
        lines.append("```")

    # Configuration
    lines.append("\n### 2. Configuration")
    lines.append("\n**Important**: Import tracer before other modules!\n")

    if project_type in ("nextjs", "react", "express", "node"):
        lines.append("**Create `tracer.ts` and import it first:**")
        lines.append("```typescript")
        lines.append(config["js_init"])
        lines.append("```")
    else:
        lines.append("**Initialize at the start of your application:**")
        lines.append("```python")
        lines.append(config["py_init"])
        lines.append("```")

    # Environment variables
    lines.append("\n### 3. Environment Variables")
    lines.append("```env")
    for env_var in config.get("env_vars", []):
        lines.append(f"{env_var}=")
    lines.append("```")

    # Docker setup for Datadog
    if provider == "datadog":
        lines.append("\n### 4. Docker Agent Setup")
        lines.append("```yaml")
        lines.append("# docker-compose.yml")
        lines.append("services:")
        lines.append("  datadog-agent:")
        lines.append("    image: gcr.io/datadoghq/agent:latest")
        lines.append("    environment:")
        lines.append("      - DD_API_KEY=${DD_API_KEY}")
        lines.append("      - DD_SITE=datadoghq.com")
        lines.append("      - DD_APM_ENABLED=true")
        lines.append("      - DD_LOGS_ENABLED=true")
        lines.append("    volumes:")
        lines.append("      - /var/run/docker.sock:/var/run/docker.sock:ro")
        lines.append("      - /proc/:/host/proc/:ro")
        lines.append("      - /sys/fs/cgroup/:/host/sys/fs/cgroup:ro")
        lines.append("```")

    return ToolResult(output="\n".join(lines), sources=[])


async def setup_logging(
    context: Dict[str, Any],
    workspace_path: str,
    library: Optional[str] = None,
) -> ToolResult:
    """
    Set up structured logging in a project.

    Args:
        workspace_path: Path to the project root
        library: Logging library (pino, winston, structlog)

    Returns:
        ToolResult with logging configuration
    """
    logger.info("setup_logging", workspace_path=workspace_path)

    project_type = _detect_project_type(workspace_path)

    # Auto-select library
    if not library:
        if project_type in ("nextjs", "react", "express", "node"):
            library = "pino"
        else:
            library = "structlog"

    if library not in LOGGING_TEMPLATES:
        available = ", ".join(LOGGING_TEMPLATES.keys())
        return ToolResult(
            output=f"Unsupported library: {library}\n\nAvailable: {available}",
            sources=[],
        )

    lines = [f"## Logging Setup: {library}\n"]
    lines.append(f"**Library**: {library}")
    lines.append(f"**Project Type**: {project_type}")

    # Installation
    lines.append("\n### 1. Installation")
    if library == "pino":
        lines.append("```bash")
        lines.append("npm install pino pino-pretty")
        lines.append("```")
    elif library == "winston":
        lines.append("```bash")
        lines.append("npm install winston")
        lines.append("```")
    elif library == "structlog":
        lines.append("```bash")
        lines.append("pip install structlog")
        lines.append("```")

    # Configuration
    lines.append("\n### 2. Logger Configuration")
    lines.append("```" + ("typescript" if library in ("pino", "winston") else "python"))
    lines.append(LOGGING_TEMPLATES[library])
    lines.append("```")

    # Usage
    lines.append("\n### 3. Usage Example")
    if library in ("pino", "winston"):
        lines.append("```typescript")
        lines.append('import logger from "./lib/logger";')
        lines.append("")
        lines.append('logger.info("User logged in", { userId: 123 });')
        lines.append('logger.error("Payment failed", { orderId: 456, error });')
        lines.append("```")
    else:
        lines.append("```python")
        lines.append("import structlog")
        lines.append("")
        lines.append("logger = structlog.get_logger(__name__)")
        lines.append('logger.info("user_logged_in", user_id=123)')
        lines.append('logger.error("payment_failed", order_id=456, error=str(e))')
        lines.append("```")

    # Best practices
    lines.append("\n### 4. Best Practices")
    lines.append("- Use structured logging (key-value pairs)")
    lines.append("- Include request IDs for tracing")
    lines.append("- Log at appropriate levels (debug, info, warn, error)")
    lines.append("- Never log sensitive data (passwords, tokens)")
    lines.append("- Add context: user IDs, request IDs, operation names")

    return ToolResult(output="\n".join(lines), sources=[])


async def generate_health_checks(
    context: Dict[str, Any],
    workspace_path: str,
) -> ToolResult:
    """
    Generate health check endpoints for an application.

    Creates /health, /ready, and /live endpoints.

    Args:
        workspace_path: Path to the project root

    Returns:
        ToolResult with health check implementation
    """
    logger.info("generate_health_checks", workspace_path=workspace_path)

    project_type = _detect_project_type(workspace_path)

    if project_type not in HEALTH_CHECK_TEMPLATES:
        project_type = "express"  # Default to Express

    template = HEALTH_CHECK_TEMPLATES.get(
        project_type, HEALTH_CHECK_TEMPLATES["express"]
    )

    lines = ["## Health Check Endpoints\n"]
    lines.append(f"**Framework**: {project_type}")
    lines.append("\n**Endpoints**:")
    lines.append("- `GET /health` - Overall health status")
    lines.append("- `GET /ready` - Readiness probe")
    lines.append("- `GET /live` - Liveness probe")

    lines.append("\n### Implementation")
    lines.append(
        "```" + ("typescript" if project_type in ("nextjs", "express") else "python")
    )
    lines.append(template)
    lines.append("```")

    # Kubernetes configuration
    lines.append("\n### Kubernetes Probes Configuration")
    lines.append("```yaml")
    lines.append("livenessProbe:")
    lines.append("  httpGet:")
    lines.append("    path: /live")
    lines.append("    port: 8080")
    lines.append("  initialDelaySeconds: 30")
    lines.append("  periodSeconds: 10")
    lines.append("")
    lines.append("readinessProbe:")
    lines.append("  httpGet:")
    lines.append("    path: /ready")
    lines.append("    port: 8080")
    lines.append("  initialDelaySeconds: 5")
    lines.append("  periodSeconds: 5")
    lines.append("```")

    lines.append("\n### Health Check Best Practices")
    lines.append("1. Check all critical dependencies (database, cache, external APIs)")
    lines.append("2. Set appropriate timeouts")
    lines.append("3. Return 503 when unhealthy")
    lines.append("4. Include diagnostic information in the response")
    lines.append("5. Keep checks fast (< 1 second)")

    return ToolResult(output="\n".join(lines), sources=[])


async def setup_alerting(
    context: Dict[str, Any],
    workspace_path: str,
    provider: str = "pagerduty",
) -> ToolResult:
    """
    Set up alerting configuration.

    Args:
        workspace_path: Path to the project root
        provider: Alerting provider (pagerduty, opsgenie, slack)

    Returns:
        ToolResult with alerting setup instructions
    """
    logger.info("setup_alerting", workspace_path=workspace_path, provider=provider)

    lines = [f"## Alerting Setup: {provider.title()}\n"]

    if provider == "pagerduty":
        lines.append("### PagerDuty Integration")
        lines.append("\n**1. Create a PagerDuty Service**")
        lines.append("- Go to Services > Service Directory > New Service")
        lines.append("- Configure escalation policy")
        lines.append("- Get the Integration Key")

        lines.append("\n**2. Configure Alerts**")
        lines.append("```typescript")
        lines.append("// Example: Trigger alert from code")
        lines.append('import { trigger } from "@pagerduty/pdjs";')
        lines.append("")
        lines.append("await trigger({")
        lines.append("  routing_key: process.env.PAGERDUTY_ROUTING_KEY,")
        lines.append("  event_action: 'trigger',")
        lines.append("  payload: {")
        lines.append('    summary: "High error rate detected",')
        lines.append('    severity: "critical",')
        lines.append('    source: "my-service",')
        lines.append("  },")
        lines.append("});")
        lines.append("```")

    elif provider == "slack":
        lines.append("### Slack Alerts")
        lines.append("\n**1. Create Slack Webhook**")
        lines.append("- Go to Slack App Directory")
        lines.append("- Add Incoming Webhooks")
        lines.append("- Get the Webhook URL")

        lines.append("\n**2. Send Alerts**")
        lines.append("```typescript")
        lines.append("async function sendAlert(message: string, level: string) {")
        lines.append("  await fetch(process.env.SLACK_WEBHOOK_URL, {")
        lines.append('    method: "POST",')
        lines.append("    body: JSON.stringify({")
        lines.append("      text: `[${level.toUpperCase()}] ${message}`,")
        lines.append("      attachments: [{")
        lines.append('        color: level === "error" ? "danger" : "warning",')
        lines.append("        fields: [{")
        lines.append('          title: "Service",')
        lines.append("          value: process.env.SERVICE_NAME,")
        lines.append("        }],")
        lines.append("      }],")
        lines.append("    }),")
        lines.append("  });")
        lines.append("}")
        lines.append("```")

    # Alert thresholds
    lines.append("\n### Recommended Alert Thresholds")
    lines.append("| Metric | Warning | Critical |")
    lines.append("|--------|---------|----------|")
    lines.append("| Error Rate | > 1% | > 5% |")
    lines.append("| P99 Latency | > 1s | > 3s |")
    lines.append("| CPU Usage | > 70% | > 90% |")
    lines.append("| Memory Usage | > 70% | > 90% |")
    lines.append("| Disk Usage | > 80% | > 95% |")

    return ToolResult(output="\n".join(lines), sources=[])


def _detect_project_type(workspace_path: str) -> str:
    """Detect project type from files."""
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
                if "react" in deps:
                    return "react"
                return "node"
        except (json.JSONDecodeError, IOError):
            pass

    requirements_path = os.path.join(workspace_path, "requirements.txt")
    if os.path.exists(requirements_path):
        try:
            with open(requirements_path, "r") as f:
                content = f.read().lower()
                if "fastapi" in content:
                    return "fastapi"
                if "flask" in content:
                    return "flask"
                if "django" in content:
                    return "django"
                return "python"
        except IOError:
            pass

    if os.path.exists(os.path.join(workspace_path, "manage.py")):
        return "django"

    return "node"


# Export tools for the agent dispatcher
MONITORING_TOOLS = {
    "monitor_setup_errors": setup_error_tracking,
    "monitor_setup_apm": setup_apm,
    "monitor_setup_logging": setup_logging,
    "monitor_generate_health_checks": generate_health_checks,
    "monitor_setup_alerting": setup_alerting,
}
