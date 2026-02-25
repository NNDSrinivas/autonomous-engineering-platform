"""
Project Scaffolding Service

Handles creation of new projects using various scaffolding tools:
- Next.js (npx create-next-app)
- React (npx create-react-app)
- Vite (npm create vite@latest)
- Python (poetry new, pip)
- Express.js
- Static HTML sites
"""

import asyncio
import os
import shutil
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
import structlog

logger = structlog.get_logger(__name__)


class ProjectType(Enum):
    """Supported project types for scaffolding"""

    NEXTJS = "nextjs"
    REACT = "react"
    VITE_REACT = "vite-react"
    VITE_VUE = "vite-vue"
    EXPRESS = "express"
    PYTHON = "python"
    STATIC_HTML = "static-html"
    UNKNOWN = "unknown"


@dataclass
class ProjectScaffoldRequest:
    """Request to scaffold a new project"""

    project_name: str
    project_type: ProjectType
    parent_directory: str
    description: Optional[str] = None
    typescript: bool = True
    git_init: bool = True
    install_dependencies: bool = True
    template: Optional[str] = None


@dataclass
class ProjectScaffoldResult:
    """Result of project scaffolding"""

    success: bool
    project_path: str
    project_type: ProjectType
    message: str
    commands_run: List[str]
    error: Optional[str] = None


class ProjectScaffolder:
    """Service for scaffolding new projects"""

    def __init__(self):
        self.supported_tools = self._check_available_tools()
        logger.info(
            f"Project scaffolder initialized with tools: {self.supported_tools}"
        )

    def _check_available_tools(self) -> Dict[str, bool]:
        """Check which scaffolding tools are available"""
        tools = {}

        # Check npm/npx
        tools["npm"] = shutil.which("npm") is not None
        tools["npx"] = shutil.which("npx") is not None

        # Check node
        tools["node"] = shutil.which("node") is not None

        # Check python
        tools["python"] = (
            shutil.which("python") is not None or shutil.which("python3") is not None
        )
        tools["poetry"] = shutil.which("poetry") is not None
        tools["pip"] = (
            shutil.which("pip") is not None or shutil.which("pip3") is not None
        )

        # Check git
        tools["git"] = shutil.which("git") is not None

        return tools

    def detect_project_type(self, description: str) -> ProjectType:
        """
        Detect project type from natural language description

        Examples:
        - "Create a Next.js marketing website" -> NEXTJS
        - "Create a React app for dashboard" -> REACT
        - "Build a Python API server" -> PYTHON
        """
        description_lower = description.lower()

        # Next.js detection
        if any(
            keyword in description_lower for keyword in ["next.js", "nextjs", "next"]
        ):
            return ProjectType.NEXTJS

        # React detection
        if any(keyword in description_lower for keyword in ["react", "react app"]):
            # Check if Vite is mentioned
            if "vite" in description_lower:
                return ProjectType.VITE_REACT
            return ProjectType.REACT

        # Vue detection
        if any(keyword in description_lower for keyword in ["vue", "vue.js"]):
            return ProjectType.VITE_VUE

        # Express detection
        if any(
            keyword in description_lower
            for keyword in ["express", "express.js", "node server", "api server"]
        ):
            return ProjectType.EXPRESS

        # Python detection
        if any(
            keyword in description_lower
            for keyword in ["python", "fastapi", "flask", "django"]
        ):
            return ProjectType.PYTHON

        # Static HTML detection
        if any(
            keyword in description_lower
            for keyword in ["html", "static site", "landing page", "simple website"]
        ):
            return ProjectType.STATIC_HTML

        return ProjectType.UNKNOWN

    async def scaffold_project(
        self, request: ProjectScaffoldRequest
    ) -> ProjectScaffoldResult:
        """
        Scaffold a new project based on the request

        Args:
            request: ProjectScaffoldRequest with project details

        Returns:
            ProjectScaffoldResult with success status and details
        """
        logger.info(
            f"Scaffolding project: {request.project_name} ({request.project_type.value})"
        )

        project_path = os.path.join(request.parent_directory, request.project_name)
        commands_run = []

        # Check if directory already exists
        if os.path.exists(project_path):
            return ProjectScaffoldResult(
                success=False,
                project_path=project_path,
                project_type=request.project_type,
                message=f"Directory already exists: {project_path}",
                commands_run=commands_run,
                error="Directory already exists",
            )

        try:
            # Create parent directory if it doesn't exist
            os.makedirs(request.parent_directory, exist_ok=True)

            # Scaffold based on project type
            if request.project_type == ProjectType.NEXTJS:
                result = await self._scaffold_nextjs(request, commands_run)
            elif request.project_type == ProjectType.REACT:
                result = await self._scaffold_react(request, commands_run)
            elif request.project_type == ProjectType.VITE_REACT:
                result = await self._scaffold_vite(request, "react", commands_run)
            elif request.project_type == ProjectType.VITE_VUE:
                result = await self._scaffold_vite(request, "vue", commands_run)
            elif request.project_type == ProjectType.EXPRESS:
                result = await self._scaffold_express(request, commands_run)
            elif request.project_type == ProjectType.PYTHON:
                result = await self._scaffold_python(request, commands_run)
            elif request.project_type == ProjectType.STATIC_HTML:
                result = await self._scaffold_static_html(request, commands_run)
            else:
                result = await self._scaffold_generic(request, commands_run)

            return result

        except Exception as e:
            logger.error(f"Error scaffolding project: {e}", exc_info=True)
            return ProjectScaffoldResult(
                success=False,
                project_path=project_path,
                project_type=request.project_type,
                message=f"Error scaffolding project: {str(e)}",
                commands_run=commands_run,
                error=str(e),
            )

    async def _run_command(
        self, command: List[str], cwd: str, commands_run: List[str]
    ) -> tuple[bool, str]:
        """Run a shell command and return success status and output"""
        cmd_str = " ".join(command)
        commands_run.append(cmd_str)
        logger.info(f"Running command: {cmd_str} in {cwd}")

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return True, stdout.decode()
            else:
                error_msg = stderr.decode()
                logger.error(f"Command failed: {error_msg}")
                return False, error_msg

        except Exception as e:
            logger.error(f"Error running command: {e}", exc_info=True)
            return False, str(e)

    async def _scaffold_nextjs(
        self, request: ProjectScaffoldRequest, commands_run: List[str]
    ) -> ProjectScaffoldResult:
        """Scaffold a Next.js project"""
        if not self.supported_tools.get("npx"):
            return ProjectScaffoldResult(
                success=False,
                project_path=os.path.join(
                    request.parent_directory, request.project_name
                ),
                project_type=request.project_type,
                message="npx is not available. Please install Node.js and npm.",
                commands_run=commands_run,
                error="npx not found",
            )

        project_path = os.path.join(request.parent_directory, request.project_name)

        # Build create-next-app command
        command = [
            "npx",
            "create-next-app@latest",
            request.project_name,
            "--typescript" if request.typescript else "--js",
            "--tailwind",
            "--app",
            "--no-src-dir",
            "--import-alias",
            "@/*",
        ]

        if not request.install_dependencies:
            command.append("--no-install")

        success, output = await self._run_command(
            command, request.parent_directory, commands_run
        )

        if success:
            # Initialize git if requested
            if request.git_init and self.supported_tools.get("git"):
                await self._run_command(["git", "init"], project_path, commands_run)
                await self._run_command(["git", "add", "."], project_path, commands_run)
                await self._run_command(
                    ["git", "commit", "-m", "Initial commit from NAVI"],
                    project_path,
                    commands_run,
                )

            return ProjectScaffoldResult(
                success=True,
                project_path=project_path,
                project_type=request.project_type,
                message=f"Next.js project created successfully at {project_path}",
                commands_run=commands_run,
            )
        else:
            return ProjectScaffoldResult(
                success=False,
                project_path=project_path,
                project_type=request.project_type,
                message=f"Failed to create Next.js project: {output}",
                commands_run=commands_run,
                error=output,
            )

    async def _scaffold_react(
        self, request: ProjectScaffoldRequest, commands_run: List[str]
    ) -> ProjectScaffoldResult:
        """Scaffold a React project using create-react-app"""
        if not self.supported_tools.get("npx"):
            return ProjectScaffoldResult(
                success=False,
                project_path=os.path.join(
                    request.parent_directory, request.project_name
                ),
                project_type=request.project_type,
                message="npx is not available. Please install Node.js and npm.",
                commands_run=commands_run,
                error="npx not found",
            )

        project_path = os.path.join(request.parent_directory, request.project_name)

        command = ["npx", "create-react-app", request.project_name]
        if request.typescript:
            command.append("--template")
            command.append("typescript")

        success, output = await self._run_command(
            command, request.parent_directory, commands_run
        )

        if success:
            if request.git_init and self.supported_tools.get("git"):
                # CRA already initializes git, just add initial commit
                await self._run_command(
                    [
                        "git",
                        "commit",
                        "--allow-empty",
                        "-m",
                        "Initial commit from NAVI",
                    ],
                    project_path,
                    commands_run,
                )

            return ProjectScaffoldResult(
                success=True,
                project_path=project_path,
                project_type=request.project_type,
                message=f"React project created successfully at {project_path}",
                commands_run=commands_run,
            )
        else:
            return ProjectScaffoldResult(
                success=False,
                project_path=project_path,
                project_type=request.project_type,
                message=f"Failed to create React project: {output}",
                commands_run=commands_run,
                error=output,
            )

    async def _scaffold_vite(
        self, request: ProjectScaffoldRequest, framework: str, commands_run: List[str]
    ) -> ProjectScaffoldResult:
        """Scaffold a Vite project (React or Vue)"""
        if not self.supported_tools.get("npm"):
            return ProjectScaffoldResult(
                success=False,
                project_path=os.path.join(
                    request.parent_directory, request.project_name
                ),
                project_type=request.project_type,
                message="npm is not available. Please install Node.js and npm.",
                commands_run=commands_run,
                error="npm not found",
            )

        project_path = os.path.join(request.parent_directory, request.project_name)

        # Vite requires interactive input, so we use a template approach
        template = f"{framework}-ts" if request.typescript else framework

        command = [
            "npm",
            "create",
            "vite@latest",
            request.project_name,
            "--",
            "--template",
            template,
        ]

        success, output = await self._run_command(
            command, request.parent_directory, commands_run
        )

        if success:
            # Install dependencies
            if request.install_dependencies:
                await self._run_command(["npm", "install"], project_path, commands_run)

            # Initialize git
            if request.git_init and self.supported_tools.get("git"):
                await self._run_command(["git", "init"], project_path, commands_run)
                await self._run_command(["git", "add", "."], project_path, commands_run)
                await self._run_command(
                    ["git", "commit", "-m", "Initial commit from NAVI"],
                    project_path,
                    commands_run,
                )

            return ProjectScaffoldResult(
                success=True,
                project_path=project_path,
                project_type=request.project_type,
                message=f"Vite {framework} project created successfully at {project_path}",
                commands_run=commands_run,
            )
        else:
            return ProjectScaffoldResult(
                success=False,
                project_path=project_path,
                project_type=request.project_type,
                message=f"Failed to create Vite project: {output}",
                commands_run=commands_run,
                error=output,
            )

    async def _scaffold_express(
        self, request: ProjectScaffoldRequest, commands_run: List[str]
    ) -> ProjectScaffoldResult:
        """Scaffold an Express.js project"""
        project_path = os.path.join(request.parent_directory, request.project_name)
        os.makedirs(project_path, exist_ok=True)

        # Create package.json
        package_json = {
            "name": request.project_name,
            "version": "1.0.0",
            "description": request.description or "Express.js API server",
            "main": "index.js" if not request.typescript else "dist/index.js",
            "scripts": {
                "start": (
                    "node index.js" if not request.typescript else "node dist/index.js"
                ),
                "dev": (
                    "nodemon index.js"
                    if not request.typescript
                    else "nodemon src/index.ts"
                ),
            },
            "dependencies": {
                "express": "^4.18.2",
                "cors": "^2.8.5",
                "dotenv": "^16.0.3",
            },
            "devDependencies": {"nodemon": "^3.0.1"},
        }

        if request.typescript:
            package_json["devDependencies"].update(
                {
                    "typescript": "^5.0.0",
                    "@types/node": "^20.0.0",
                    "@types/express": "^4.17.17",
                    "@types/cors": "^2.8.13",
                    "ts-node": "^10.9.1",
                }
            )
            package_json["scripts"]["build"] = "tsc"

        # Write package.json
        import json

        with open(os.path.join(project_path, "package.json"), "w") as f:
            json.dump(package_json, f, indent=2)

        # Create basic Express server
        server_code = self._get_express_template(request.typescript)
        server_file = "src/index.ts" if request.typescript else "index.js"

        if request.typescript:
            os.makedirs(os.path.join(project_path, "src"), exist_ok=True)

        with open(os.path.join(project_path, server_file), "w") as f:
            f.write(server_code)

        # Create .env
        with open(os.path.join(project_path, ".env"), "w") as f:
            f.write("PORT=3000\n")

        # Create .gitignore
        with open(os.path.join(project_path, ".gitignore"), "w") as f:
            f.write("node_modules/\n.env\ndist/\n")

        # Install dependencies
        if request.install_dependencies and self.supported_tools.get("npm"):
            await self._run_command(["npm", "install"], project_path, commands_run)

        # Initialize git
        if request.git_init and self.supported_tools.get("git"):
            await self._run_command(["git", "init"], project_path, commands_run)
            await self._run_command(["git", "add", "."], project_path, commands_run)
            await self._run_command(
                ["git", "commit", "-m", "Initial commit from NAVI"],
                project_path,
                commands_run,
            )

        return ProjectScaffoldResult(
            success=True,
            project_path=project_path,
            project_type=request.project_type,
            message=f"Express.js project created successfully at {project_path}",
            commands_run=commands_run,
        )

    async def _scaffold_python(
        self, request: ProjectScaffoldRequest, commands_run: List[str]
    ) -> ProjectScaffoldResult:
        """Scaffold a Python project"""
        project_path = os.path.join(request.parent_directory, request.project_name)
        os.makedirs(project_path, exist_ok=True)

        # Create project structure
        os.makedirs(
            os.path.join(project_path, request.project_name.replace("-", "_")),
            exist_ok=True,
        )

        # Create requirements.txt
        with open(os.path.join(project_path, "requirements.txt"), "w") as f:
            f.write("# Add your dependencies here\n")

        # Create main.py
        main_code = '''"""
Main application module
"""

def main():
    """Main entry point"""
    print("Hello from NAVI!")

if __name__ == "__main__":
    main()
'''
        with open(
            os.path.join(
                project_path, request.project_name.replace("-", "_"), "__init__.py"
            ),
            "w",
        ) as f:
            f.write("")

        with open(
            os.path.join(
                project_path, request.project_name.replace("-", "_"), "main.py"
            ),
            "w",
        ) as f:
            f.write(main_code)

        # Create .gitignore
        with open(os.path.join(project_path, ".gitignore"), "w") as f:
            f.write("__pycache__/\n*.py[cod]\n*$py.class\n.venv/\nvenv/\nENV/\n.env\n")

        # Create README
        with open(os.path.join(project_path, "README.md"), "w") as f:
            f.write(
                f"# {request.project_name}\n\n{request.description or 'A Python project created by NAVI'}\n"
            )

        # Initialize git
        if request.git_init and self.supported_tools.get("git"):
            await self._run_command(["git", "init"], project_path, commands_run)
            await self._run_command(["git", "add", "."], project_path, commands_run)
            await self._run_command(
                ["git", "commit", "-m", "Initial commit from NAVI"],
                project_path,
                commands_run,
            )

        return ProjectScaffoldResult(
            success=True,
            project_path=project_path,
            project_type=request.project_type,
            message=f"Python project created successfully at {project_path}",
            commands_run=commands_run,
        )

    async def _scaffold_static_html(
        self, request: ProjectScaffoldRequest, commands_run: List[str]
    ) -> ProjectScaffoldResult:
        """Scaffold a static HTML website"""
        project_path = os.path.join(request.parent_directory, request.project_name)
        os.makedirs(project_path, exist_ok=True)

        # Create index.html
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{request.project_name}</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <header>
        <h1>{request.project_name}</h1>
        <p>{request.description or "A static website created by NAVI"}</p>
    </header>
    <main>
        <section>
            <h2>Welcome</h2>
            <p>This is your new website. Start editing to customize it!</p>
        </section>
    </main>
    <footer>
        <p>Created with NAVI</p>
    </footer>
    <script src="script.js"></script>
</body>
</html>
"""

        # Create styles.css
        css_content = """* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    line-height: 1.6;
    color: #333;
    background: #f4f4f4;
}

header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 2rem;
    text-align: center;
}

main {
    max-width: 1200px;
    margin: 2rem auto;
    padding: 0 1rem;
}

section {
    background: white;
    padding: 2rem;
    margin-bottom: 1rem;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

footer {
    text-align: center;
    padding: 1rem;
    background: #333;
    color: white;
    margin-top: 2rem;
}
"""

        # Create script.js
        js_content = """// Add your JavaScript here
console.log('Website loaded!');
"""

        with open(os.path.join(project_path, "index.html"), "w") as f:
            f.write(html_content)

        with open(os.path.join(project_path, "styles.css"), "w") as f:
            f.write(css_content)

        with open(os.path.join(project_path, "script.js"), "w") as f:
            f.write(js_content)

        # Create .gitignore
        with open(os.path.join(project_path, ".gitignore"), "w") as f:
            f.write(".DS_Store\n")

        # Initialize git
        if request.git_init and self.supported_tools.get("git"):
            await self._run_command(["git", "init"], project_path, commands_run)
            await self._run_command(["git", "add", "."], project_path, commands_run)
            await self._run_command(
                ["git", "commit", "-m", "Initial commit from NAVI"],
                project_path,
                commands_run,
            )

        return ProjectScaffoldResult(
            success=True,
            project_path=project_path,
            project_type=request.project_type,
            message=f"Static HTML website created successfully at {project_path}",
            commands_run=commands_run,
        )

    async def _scaffold_generic(
        self, request: ProjectScaffoldRequest, commands_run: List[str]
    ) -> ProjectScaffoldResult:
        """Scaffold a generic project structure"""
        project_path = os.path.join(request.parent_directory, request.project_name)
        os.makedirs(project_path, exist_ok=True)

        # Create basic README
        with open(os.path.join(project_path, "README.md"), "w") as f:
            f.write(
                f"# {request.project_name}\n\n{request.description or 'A project created by NAVI'}\n"
            )

        # Create .gitignore
        with open(os.path.join(project_path, ".gitignore"), "w") as f:
            f.write(".DS_Store\n")

        # Initialize git
        if request.git_init and self.supported_tools.get("git"):
            await self._run_command(["git", "init"], project_path, commands_run)
            await self._run_command(["git", "add", "."], project_path, commands_run)
            await self._run_command(
                ["git", "commit", "-m", "Initial commit from NAVI"],
                project_path,
                commands_run,
            )

        return ProjectScaffoldResult(
            success=True,
            project_path=project_path,
            project_type=request.project_type,
            message=f"Generic project created successfully at {project_path}",
            commands_run=commands_run,
        )

    def _get_express_template(self, typescript: bool) -> str:
        """Get Express.js server template"""
        if typescript:
            return """import express, { Request, Response } from 'express';
import cors from 'cors';
import dotenv from 'dotenv';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());

// Routes
app.get('/', (req: Request, res: Response) => {
  res.json({ message: 'Hello from NAVI Express server!' });
});

app.get('/api/health', (req: Request, res: Response) => {
  res.json({ status: 'ok' });
});

// Start server
app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});
"""
        else:
            return """const express = require('express');
const cors = require('cors');
const dotenv = require('dotenv');

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());

// Routes
app.get('/', (req, res) => {
  res.json({ message: 'Hello from NAVI Express server!' });
});

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok' });
});

// Start server
app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});
"""
