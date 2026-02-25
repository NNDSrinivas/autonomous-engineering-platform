"""
GitHub Actions tools for NAVI agent.

Provides tools to query and manage GitHub Actions workflows and runs.
"""

from typing import Any, Dict, Optional
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


async def list_github_actions_workflows(
    context: Dict[str, Any],
    owner: str,
    repo: str,
) -> ToolResult:
    """List GitHub Actions workflows for a repository."""
    from backend.services.github_actions_service import GitHubActionsService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "github")

        if not connection:
            return ToolResult(
                output="GitHub is not connected. Please connect your GitHub account first.",
                sources=[],
            )

        workflows = await GitHubActionsService.list_workflows(
            db=db, connection=connection, owner=owner, repo=repo
        )

        if not workflows:
            return ToolResult(
                output=f"No workflows found in {owner}/{repo}.",
                sources=[],
            )

        lines = [f"Found {len(workflows)} workflow(s) in `{owner}/{repo}`:\n"]
        sources = []

        state_emoji = {
            "active": "✅",
            "disabled_fork": "⏸️",
            "disabled_inactivity": "⏸️",
            "disabled_manually": "⏸️",
        }

        for wf in workflows:
            name = wf.get("name", "Untitled")
            state = wf.get("state", "unknown")
            path = wf.get("path", "")
            url = wf.get("url", "")

            emoji = state_emoji.get(state, "❓")
            lines.append(f"- {emoji} **{name}**")
            lines.append(f"  - State: {state}")
            if path:
                lines.append(f"  - Path: `{path}`")
            if url:
                lines.append(f"  - [View Workflow]({url})")
            lines.append("")

            if url:
                sources.append({"type": "github_workflow", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_github_actions_workflows.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def list_github_actions_runs(
    context: Dict[str, Any],
    owner: str,
    repo: str,
    workflow_id: Optional[str] = None,
    status: Optional[str] = None,
    max_results: int = 10,
) -> ToolResult:
    """List recent GitHub Actions workflow runs."""
    from backend.services.github_actions_service import GitHubActionsService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "github")

        if not connection:
            return ToolResult(output="GitHub is not connected.", sources=[])

        runs = await GitHubActionsService.list_workflow_runs(
            db=db,
            connection=connection,
            owner=owner,
            repo=repo,
            workflow_id=workflow_id,
            status=status,
            max_results=max_results,
        )

        if not runs:
            return ToolResult(
                output=f"No workflow runs found in {owner}/{repo}.",
                sources=[],
            )

        lines = [f"Found {len(runs)} workflow run(s) in `{owner}/{repo}`:\n"]
        sources = []

        conclusion_emoji = {
            "success": "✅",
            "failure": "❌",
            "cancelled": "🚫",
            "skipped": "⏭️",
            "timed_out": "⏰",
            "pending": "🔄",
        }

        for run in runs:
            name = run.get("name", "Untitled")
            run_number = run.get("run_number", "")
            status_val = run.get("status", "unknown")
            conclusion = run.get("conclusion", "pending")
            branch = run.get("branch", "")
            actor = run.get("actor", "")
            url = run.get("url", "")

            emoji = conclusion_emoji.get(conclusion, "❓")
            lines.append(f"- {emoji} **{name}** #{run_number}")
            lines.append(f"  - Status: {status_val} / {conclusion}")
            lines.append(f"  - Branch: `{branch}` | By: {actor}")
            if url:
                lines.append(f"  - [View Run]({url})")
            lines.append("")

            if url:
                sources.append(
                    {"type": "github_run", "name": f"{name} #{run_number}", "url": url}
                )

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_github_actions_runs.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def get_github_actions_run_status(
    context: Dict[str, Any],
    owner: str,
    repo: str,
    run_id: int,
) -> ToolResult:
    """Get status of a specific GitHub Actions workflow run."""
    from backend.services.github_actions_service import GitHubActionsService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "github")

        if not connection:
            return ToolResult(output="GitHub is not connected.", sources=[])

        run = await GitHubActionsService.get_run_status(
            db=db, connection=connection, owner=owner, repo=repo, run_id=run_id
        )

        if not run:
            return ToolResult(
                output=f"Could not find workflow run {run_id} in {owner}/{repo}.",
                sources=[],
            )

        name = run.get("name", "Untitled")
        run_number = run.get("run_number", "")
        status = run.get("status", "unknown")
        conclusion = run.get("conclusion", "pending")
        branch = run.get("branch", "")
        event = run.get("event", "")
        actor = run.get("actor", "")
        url = run.get("url", "")
        created_at = run.get("created_at", "")[:10] if run.get("created_at") else ""

        conclusion_emoji = {
            "success": "✅",
            "failure": "❌",
            "cancelled": "🚫",
            "pending": "🔄",
        }
        emoji = conclusion_emoji.get(conclusion, "❓")

        lines = [
            f"# {emoji} {name} #{run_number}\n",
            f"**Status:** {status}",
            f"**Conclusion:** {conclusion}",
            f"**Branch:** `{branch}`",
            f"**Event:** {event}",
            f"**Triggered by:** {actor}",
            f"**Created:** {created_at}",
        ]

        if url:
            lines.append(f"\n[View in GitHub]({url})")

        sources = []
        if url:
            sources.append(
                {"type": "github_run", "name": f"{name} #{run_number}", "url": url}
            )

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("get_github_actions_run_status.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def trigger_github_actions_workflow(
    context: Dict[str, Any],
    owner: str,
    repo: str,
    workflow_id: str,
    ref: str = "main",
) -> ToolResult:
    """Trigger a GitHub Actions workflow (requires approval)."""
    from backend.services.github_actions_service import GitHubActionsService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "github")

        if not connection:
            return ToolResult(output="GitHub is not connected.", sources=[])

        result = await GitHubActionsService.write_item(
            db=db,
            connection=connection,
            operation="trigger_workflow",
            owner=owner,
            repo=repo,
            workflow_id=workflow_id,
            ref=ref,
        )

        if result.get("success"):
            url = f"https://github.com/{owner}/{repo}/actions"
            return ToolResult(
                output=f"Workflow triggered successfully on branch `{ref}`.\n\n[View Actions]({url})",
                sources=[
                    {"type": "github_actions", "name": f"{owner}/{repo}", "url": url}
                ],
            )
        else:
            return ToolResult(output="Failed to trigger workflow.", sources=[])

    except Exception as e:
        logger.error("trigger_github_actions_workflow.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def generate_github_actions(
    context: Dict[str, Any],
    workflow_name: str = "CI",
    triggers: Optional[list] = None,
    include_deploy: bool = False,
) -> ToolResult:
    """
    Generate GitHub Actions workflow files for CI/CD.

    Args (from context):
        workflow_name: Name for the workflow
        triggers: List of trigger events (push, pull_request, etc.)
        include_deploy: Whether to include deployment job
    """
    import os

    workspace_path = context.get("workspace_path", ".")
    if triggers is None:
        triggers = ["push", "pull_request"]

    # Detect project type
    project_info = await _detect_project_type(workspace_path)
    project_type = project_info["type"]
    package_manager = project_info.get("package_manager", "npm")

    # Build the workflow configuration
    workflow = {
        "name": workflow_name,
        "on": _build_triggers(triggers),
        "env": _build_env_vars(project_type),
        "jobs": {},
    }

    # Add lint job
    workflow["jobs"]["lint"] = _build_lint_job(project_type, package_manager)

    # Add test job
    workflow["jobs"]["test"] = _build_test_job(project_type, package_manager)

    # Add build job
    workflow["jobs"]["build"] = _build_build_job(project_type, package_manager)

    # Add deploy job if requested
    if include_deploy:
        workflow["jobs"]["deploy"] = _build_deploy_job(project_type)

    # Convert to YAML
    yaml_content = _dict_to_github_yaml(workflow)

    # Output path
    output_path = os.path.join(
        workspace_path,
        ".github",
        "workflows",
        f"{workflow_name.lower().replace(' ', '-')}.yml",
    )

    output = f"""# GitHub Actions Workflow Configuration
# Generated by NAVI - Autonomous Engineering Platform
# Project Type: {project_type}

## Workflow Overview
- **Name**: {workflow_name}
- **Triggers**: {", ".join(triggers)}
- **Jobs**: lint, test, build{", deploy" if include_deploy else ""}

## Generated Configuration

```yaml
{yaml_content}
```

## File Location
- Path: `{output_path}`

## Next Steps
1. Create the directory: `mkdir -p .github/workflows`
2. Save the workflow file
3. Configure repository secrets if needed:
   - `DOCKER_USERNAME` / `DOCKER_PASSWORD` for container registry
   - `DEPLOY_KEY` for deployment authentication
   - `CODECOV_TOKEN` for coverage reporting
4. Push to trigger the workflow
"""

    return ToolResult(output=output, sources=[output_path])


async def _detect_project_type(workspace_path: str) -> Dict[str, Any]:
    """Detect project type from workspace files."""
    import os

    project_info = {"type": "node", "package_manager": "npm"}

    # Check for Node.js
    if os.path.exists(os.path.join(workspace_path, "package.json")):
        project_info["type"] = "node"
        if os.path.exists(os.path.join(workspace_path, "yarn.lock")):
            project_info["package_manager"] = "yarn"
        elif os.path.exists(os.path.join(workspace_path, "pnpm-lock.yaml")):
            project_info["package_manager"] = "pnpm"

    # Check for Python
    elif os.path.exists(os.path.join(workspace_path, "pyproject.toml")):
        project_info["type"] = "python"
        project_info["package_manager"] = "poetry"
    elif os.path.exists(os.path.join(workspace_path, "requirements.txt")):
        project_info["type"] = "python"
        project_info["package_manager"] = "pip"

    # Check for Go
    elif os.path.exists(os.path.join(workspace_path, "go.mod")):
        project_info["type"] = "go"
        project_info["package_manager"] = "go"

    return project_info


def _build_triggers(triggers: list) -> Dict[str, Any]:
    """Build trigger configuration."""
    on_config = {}

    for trigger in triggers:
        if trigger == "push":
            on_config["push"] = {"branches": ["main", "master"]}
        elif trigger == "pull_request":
            on_config["pull_request"] = {"branches": ["main", "master"]}
        elif trigger == "schedule":
            on_config["schedule"] = [{"cron": "0 0 * * *"}]
        elif trigger == "workflow_dispatch":
            on_config["workflow_dispatch"] = {}
        else:
            on_config[trigger] = {}

    return on_config


def _build_env_vars(project_type: str) -> Dict[str, str]:
    """Build environment variables."""
    if project_type in ["node", "nextjs", "react"]:
        return {"NODE_ENV": "test", "CI": "true"}
    elif project_type == "python":
        return {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"}
    elif project_type == "go":
        return {"GO111MODULE": "on"}
    return {"CI": "true"}


def _build_lint_job(project_type: str, package_manager: str) -> Dict[str, Any]:
    """Build lint job configuration."""
    job = {
        "runs-on": "ubuntu-latest",
        "steps": [
            {"uses": "actions/checkout@v4"},
        ],
    }

    if project_type in ["node", "nextjs", "react", "vue"]:
        job["steps"].extend(
            [
                {
                    "name": "Setup Node.js",
                    "uses": "actions/setup-node@v4",
                    "with": {"node-version": "20", "cache": package_manager},
                },
                {
                    "name": "Install dependencies",
                    "run": f"{package_manager} {'install' if package_manager != 'npm' else 'ci'}",
                },
                {"name": "Run linter", "run": f"{package_manager} run lint"},
            ]
        )
    elif project_type == "python":
        job["steps"].extend(
            [
                {
                    "name": "Setup Python",
                    "uses": "actions/setup-python@v5",
                    "with": {"python-version": "3.11"},
                },
                {"name": "Install dependencies", "run": "pip install ruff black mypy"},
                {"name": "Run ruff", "run": "ruff check ."},
                {"name": "Run black", "run": "black --check ."},
            ]
        )
    elif project_type == "go":
        job["steps"].extend(
            [
                {
                    "name": "Setup Go",
                    "uses": "actions/setup-go@v5",
                    "with": {"go-version": "1.21"},
                },
                {
                    "name": "Run golangci-lint",
                    "uses": "golangci/golangci-lint-action@v4",
                },
            ]
        )

    return job


def _build_test_job(project_type: str, package_manager: str) -> Dict[str, Any]:
    """Build test job configuration."""
    job = {
        "runs-on": "ubuntu-latest",
        "needs": "lint",
        "steps": [
            {"uses": "actions/checkout@v4"},
        ],
    }

    if project_type in ["node", "nextjs", "react", "vue"]:
        job["steps"].extend(
            [
                {
                    "name": "Setup Node.js",
                    "uses": "actions/setup-node@v4",
                    "with": {"node-version": "20", "cache": package_manager},
                },
                {
                    "name": "Install dependencies",
                    "run": f"{package_manager} {'install' if package_manager != 'npm' else 'ci'}",
                },
                {
                    "name": "Run tests",
                    "run": f"{package_manager} run test -- --coverage",
                },
                {
                    "name": "Upload coverage",
                    "uses": "codecov/codecov-action@v4",
                    "with": {"fail_ci_if_error": False},
                },
            ]
        )
    elif project_type == "python":
        job["steps"].extend(
            [
                {
                    "name": "Setup Python",
                    "uses": "actions/setup-python@v5",
                    "with": {"python-version": "3.11"},
                },
                {
                    "name": "Install dependencies",
                    "run": "pip install pytest pytest-cov pytest-asyncio -r requirements.txt",
                },
                {"name": "Run tests", "run": "pytest --cov=. --cov-report=xml"},
                {"name": "Upload coverage", "uses": "codecov/codecov-action@v4"},
            ]
        )
    elif project_type == "go":
        job["steps"].extend(
            [
                {
                    "name": "Setup Go",
                    "uses": "actions/setup-go@v5",
                    "with": {"go-version": "1.21"},
                },
                {
                    "name": "Run tests",
                    "run": "go test -v -race -coverprofile=coverage.out ./...",
                },
                {
                    "name": "Upload coverage",
                    "uses": "codecov/codecov-action@v4",
                    "with": {"files": "coverage.out"},
                },
            ]
        )

    return job


def _build_build_job(project_type: str, package_manager: str) -> Dict[str, Any]:
    """Build build job configuration."""
    job = {
        "runs-on": "ubuntu-latest",
        "needs": "test",
        "steps": [
            {"uses": "actions/checkout@v4"},
        ],
    }

    if project_type in ["node", "nextjs", "react", "vue"]:
        job["steps"].extend(
            [
                {
                    "name": "Setup Node.js",
                    "uses": "actions/setup-node@v4",
                    "with": {"node-version": "20", "cache": package_manager},
                },
                {
                    "name": "Install dependencies",
                    "run": f"{package_manager} {'install' if package_manager != 'npm' else 'ci'}",
                },
                {"name": "Build", "run": f"{package_manager} run build"},
                {
                    "name": "Upload artifact",
                    "uses": "actions/upload-artifact@v4",
                    "with": {"name": "build", "path": "dist/ .next/ build/"},
                },
            ]
        )
    elif project_type == "python":
        job["steps"].extend(
            [
                {
                    "name": "Setup Python",
                    "uses": "actions/setup-python@v5",
                    "with": {"python-version": "3.11"},
                },
                {"name": "Install build tools", "run": "pip install build"},
                {"name": "Build package", "run": "python -m build"},
                {
                    "name": "Upload artifact",
                    "uses": "actions/upload-artifact@v4",
                    "with": {"name": "dist", "path": "dist/"},
                },
            ]
        )
    elif project_type == "go":
        job["steps"].extend(
            [
                {
                    "name": "Setup Go",
                    "uses": "actions/setup-go@v5",
                    "with": {"go-version": "1.21"},
                },
                {"name": "Build", "run": "go build -o bin/ ./..."},
                {
                    "name": "Upload artifact",
                    "uses": "actions/upload-artifact@v4",
                    "with": {"name": "bin", "path": "bin/"},
                },
            ]
        )

    return job


def _build_deploy_job(project_type: str) -> Dict[str, Any]:
    """Build deploy job configuration."""
    return {
        "runs-on": "ubuntu-latest",
        "needs": "build",
        "if": "github.ref == 'refs/heads/main'",
        "environment": {"name": "production", "url": "${{ steps.deploy.outputs.url }}"},
        "steps": [
            {"uses": "actions/checkout@v4"},
            {
                "name": "Download artifact",
                "uses": "actions/download-artifact@v4",
                "with": {"name": "build"},
            },
            {
                "name": "Deploy",
                "id": "deploy",
                "run": "echo 'Deploying to production...'",
            },
        ],
    }


def _dict_to_github_yaml(data: Dict[str, Any], indent: int = 0) -> str:
    """Convert dictionary to YAML string for GitHub Actions."""
    lines = []
    prefix = "  " * indent

    for key, value in data.items():
        if isinstance(value, dict):
            if not value:  # Empty dict
                lines.append(f"{prefix}{key}:")
            else:
                lines.append(f"{prefix}{key}:")
                lines.append(_dict_to_github_yaml(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value:
                if isinstance(item, dict):
                    first = True
                    for k, v in item.items():
                        if first:
                            if isinstance(v, dict):
                                lines.append(f"{prefix}  - {k}:")
                                lines.append(_dict_to_github_yaml(v, indent + 3))
                            else:
                                lines.append(
                                    f"{prefix}  - {k}: {_format_yaml_value(v)}"
                                )
                            first = False
                        else:
                            if isinstance(v, dict):
                                lines.append(f"{prefix}    {k}:")
                                lines.append(_dict_to_github_yaml(v, indent + 3))
                            else:
                                lines.append(
                                    f"{prefix}    {k}: {_format_yaml_value(v)}"
                                )
                else:
                    lines.append(f"{prefix}  - {_format_yaml_value(item)}")
        else:
            lines.append(f"{prefix}{key}: {_format_yaml_value(value)}")

    return "\n".join(lines)


def _format_yaml_value(value: Any) -> str:
    """Format a value for YAML output."""
    if isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, str):
        if any(
            c in value
            for c in [
                ":",
                "#",
                "{",
                "}",
                "[",
                "]",
                ",",
                "&",
                "*",
                "?",
                "|",
                "-",
                "<",
                ">",
                "=",
                "!",
                "%",
                "@",
                "`",
                "$",
            ]
        ):
            return f"'{value}'"
        elif value == "":
            return "''"
        return value
    elif value is None:
        return "null"
    else:
        return str(value)


GITHUB_ACTIONS_TOOLS = {
    "github_actions_list_workflows": list_github_actions_workflows,
    "github_actions_list_runs": list_github_actions_runs,
    "github_actions_get_run_status": get_github_actions_run_status,
    "github_actions_trigger_workflow": trigger_github_actions_workflow,
    "github_actions_generate": generate_github_actions,
}
