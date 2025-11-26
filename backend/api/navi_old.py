"""
NAVI Chat API - Autonomous Engineering Assistant for VS Code Extension
Complete agent implementation with OpenAI, diffs, multi-file ops
Step 3: Unified RAG search integration
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from sqlalchemy.orm import Session
import logging
import json
import os

from ..core.db import get_db
from ..services.navi_memory_service import search_memory
from ..services.citation_formatter import format_citations_for_llm
from ..agent.orchestrator import NaviAgentContext
from ..agent.agent_types import AgentRunSummary
from ..agent.intent import detect_org_intent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/navi", tags=["navi"])

# ============================================================================
# OPENAI CLIENT (PR-6B)
# ============================================================================

try:
    from openai import AsyncOpenAI

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
    OPENAI_ENABLED = bool(openai_client)
except ImportError:
    openai_client = None
    OPENAI_ENABLED = False
    logger.warning("OpenAI not installed. Install with: pip install openai")


# ============================================================================
# REQUEST / RESPONSE MODELS (PR-6A: Enhanced Schema)
# ============================================================================


class Attachment(BaseModel):
    """File attachment from VS Code workspace"""

    path: str
    content: str
    language: Optional[str] = None


class EditorContext(BaseModel):
    """PR-7: Editor context from VS Code"""

    workspaceFolder: Optional[str] = None
    activeFilePath: Optional[str] = None
    activeFileLanguage: Optional[str] = None
    activeFileContent: Optional[str] = None
    selection: Optional[str] = None


class AgentAction(BaseModel):
    """Agent-proposed action (PR-6A: Multi-action schema)"""

    type: Literal["editFile", "createFile", "runCommand"]
    filePath: Optional[str] = None
    diff: Optional[str] = None  # Unified diff for editFile
    content: Optional[str] = None  # Full content for createFile
    command: Optional[str] = None  # Shell command for runCommand
    description: Optional[str] = None


class NaviChatRequest(BaseModel):
    """Request from VS Code extension"""

    message: str
    model: str = Field(default="gpt-4", description="Model ID to use")
    mode: str = Field(
        default="chat", description="Mode: chat, agent-full, agent-limited"
    )
    attachments: List[Attachment] = Field(default_factory=list)
    context: Optional[EditorContext] = None  # PR-7: Editor context
    user_id: Optional[str] = Field(default=None, description="User ID for task/memory queries")


class NaviChatResponse(BaseModel):
    """Response to VS Code extension"""

    role: str = "assistant"
    content: str
    actions: Optional[List[AgentAction]] = None
    agentRun: Optional[dict] = Field(None, description="Agent run summary for Copilot-style UI")


# ============================================================================
# JIRA TASK HANDLING HELPERS
# ============================================================================

def _is_jira_task_query(message: str) -> bool:
    """Detect if the user is asking about Jira tasks"""
    message_lower = message.lower()
    return any(
        keyword in message_lower
        for keyword in ["jira task", "task", "assigned", "priority", "ticket", "issue"]
    )

async def _handle_jira_task_query(db: Session, message: str, user_id: str = None) -> str:
    """Handle Jira task queries using NAVI memory"""
    try:
        import os
        from backend.services.navi_memory_service import list_jira_tasks_for_user
        
        # Use provided user_id or fall back to environment default
        if not user_id:
            user_id = os.environ.get("DEV_USER_ID", "default_user")
        
        memory_rows = list_jira_tasks_for_user(db, user_id, limit=20)
        
        if not memory_rows:
            return """You don't have any assigned tasks right now. Would you like me to help you find work to do?

**I can help you with:**
• Show available tasks
• Check team priorities  
• Find tasks I can help with"""

        # Format response using NAVI task fields
        content = f"You have {len(memory_rows)} assigned tasks.\n\n"
        content += "📋 **Your JIRA Tasks:**\n"
        
        for row in memory_rows:
            tags = row.get("tags", {})
            jira_key = tags.get("key", row.get("scope", ""))
            status = tags.get("status", "Unknown")
            title = row.get("title", "").replace(f"[Jira] {jira_key}: ", "")  # Clean up title
            
            status_emoji = (
                "🔄" if status == "In Progress"
                else "📝" if status == "To Do" 
                else "✅" if status == "Done"
                else "📌"
            )
            content += f"{status_emoji} **{jira_key}**: {title} ({status})\n"

        return content
        
    except Exception as e:
        logger.error(f"Error handling Jira task query: {e}")
        return "I had trouble fetching your tasks. Let me try a different approach."

# ============================================================================
# MAIN ENDPOINT (PR-6B)
# ============================================================================


@router.post("/chat", response_model=NaviChatResponse)
async def navi_chat(
    request: NaviChatRequest, db: Session = Depends(get_db)
) -> NaviChatResponse:
    """
    Handle NAVI chat from VS Code extension

    PR-5B: Uses attachments to build file context
    PR-6A/B: Returns agent actions (editFile, createFile, runCommand)
    PR-6C: Supports unified diffs for clean edits
    Step 3: Retrieves relevant memory context via RAG search
    Step K: Agent orchestrator with Org Brain integration and Copilot-style UI
    """
    try:
        logger.info(
            f"[NAVI] Request - model: {request.model}, mode: {request.mode}, "
            f"message: {request.message[:100]}, attachments: {len(request.attachments)}"
        )

        # STEP K: Agent-full mode with orchestrator and Org Brain
        if request.mode == "agent-full":
            # Gate orchestrator: only for org-aware/tool-like intents or attachments
            intent = detect_org_intent(request.message)
            has_attachments = bool(request.attachments)
            # For debugging: always run agent in agent-full mode
            should_run_agent = True  # Force agent mode for workspace plan testing
            print(f"🎯 AGENT-FULL triggered! should_run_agent={should_run_agent}")

            if should_run_agent:
                logger.info(
                    "[NAVI] Agent path: orchestrator enabled",
                )

                # Build workspace context from request
                workspace_context = {}
                if request.context:
                    workspace_context = {
                        "rootPath": request.context.workspaceFolder,
                        "activeFile": request.context.activeFilePath,
                        "language": request.context.activeFileLanguage,
                        "selection": request.context.selection,
                    }

                # Create agent context and run orchestrator
                agent_context = NaviAgentContext(
                    db=db,
                    org_id="demo-org",  # TODO: Get from auth context
                    user_id="demo-user",  # TODO: Get from auth context
                    workspace=workspace_context,
                )

                result = await agent_context.build_run(
                    user_message=request.message, mode=request.mode
                )

                return NaviChatResponse(
                    role="assistant",
                    content=result["assistant_text"],
                    actions=result.get("file_actions"),
                    agentRun=result["agent_run"].model_dump(),
                )
            else:
                logger.info(
                    "[NAVI] Fast path: agent disabled for non-org/tool intent"
                )

        # Step 3: Retrieve relevant memory context (RAG) for non-agent modes
        memory_context = ""
        try:
            memories = await search_memory(
                db=db,
                query=request.message,
                categories=["profile", "workspace", "task", "interaction"],
                limit=8,
                min_importance=0.3,
            )
            if memories:
                memory_context = format_citations_for_llm(memories)
                logger.info(
                    f"[NAVI] Retrieved {len(memories)} memory items for context"
                )
        except Exception as mem_err:
            logger.warning(f"[NAVI] Memory search failed: {mem_err}")
            # Continue without memory context if search fails

        # Build system prompt with file context and agent instructions
        system_prompt = _build_system_prompt(request, memory_context)

        # Build messages for LLM
        messages = [{"role": "system", "content": system_prompt}]

        # Step 3: Add memory context if available
        if memory_context:
            messages.append({"role": "system", "content": memory_context})

        # Add file context if attachments exist
        if request.attachments:
            files_context = _build_files_context(request.attachments)
            messages.append({"role": "system", "content": files_context})

        # Add user message
        messages.append({"role": "user", "content": request.message})

        # Special handler for Jira task queries - return real tasks from NAVI memory
        if _is_jira_task_query(request.message):
            logger.info(f"[NAVI] Detected Jira task query - using NAVI memory for user_id: {request.user_id}")
            try:
                jira_tasks_content = await _handle_jira_task_query(db, request.message, request.user_id)
                return NaviChatResponse(role="assistant", content=jira_tasks_content, actions=None)
            except Exception as e:
                logger.warning(f"[NAVI] Jira task query failed: {e}")
                # Fall through to normal LLM handling

        # Call LLM (OpenAI or mock)
        if OPENAI_ENABLED and openai_client:
            content, actions = await _call_openai(
                messages, request.model, request.mode, request
            )
        else:
            content, actions = _mock_response(request)

        logger.info(
            f"[NAVI] Response - content length: {len(content)}, "
            f"actions: {len(actions) if actions else 0}"
        )

        return NaviChatResponse(role="assistant", content=content, actions=actions)

    except Exception as e:
        logger.error(f"[NAVI] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"NAVI error: {str(e)}")


# ============================================================================
# INTELLIGENT CODE GENERATION HELPERS
# ============================================================================


def _infer_language(request: NaviChatRequest) -> Optional[str]:
    """
    Guess the target language for code generation based on:
    1. Active editor language (context.activeFileLanguage)
    2. First attachment language
    3. Fallback: None (caller decides how to handle ambiguity)
    """
    ctx = request.context
    if ctx and ctx.activeFileLanguage:
        return ctx.activeFileLanguage.lower()

    if request.attachments:
        lang = request.attachments[0].language
        if lang:
            return lang.lower()

    return None  # Let caller decide fallback


def _normalize_lang(lang: Optional[str]) -> str:
    """Normalize language identifier with fallback to JavaScript"""
    if not lang:
        return "javascript"
    return lang.lower()


def _hello_world_template(lang: str) -> dict:
    """
    Return {filename, content} for a full Hello World PROGRAM in the given language.
    """
    lang_lower = _normalize_lang(lang)

    # Python -------------------------------------------------------------------
    if lang_lower in {"python", "py"}:
        return {
            "filename": "hello_world.py",
            "content": (
                "# A simple Hello World program in Python\n\n"
                "def main():\n"
                '    print("Hello, World!")\n\n'
                'if __name__ == "__main__":\n'
                "    main()\n"
            ),
        }

    # JavaScript / TypeScript --------------------------------------------------
    if lang_lower in {
        "javascript",
        "javascriptreact",
        "js",
        "typescript",
        "typescriptreact",
        "ts",
    }:
        return {
            "filename": "helloWorld.js",
            "content": (
                "// A simple Hello World program in JavaScript\n"
                "function main() {\n"
                '  console.log("Hello, World!");\n'
                "}\n\n"
                "main();\n"
            ),
        }

    # Java ---------------------------------------------------------------------
    if lang_lower in {"java"}:
        return {
            "filename": "HelloWorld.java",
            "content": (
                "// A simple Hello World program in Java\n"
                "public class HelloWorld {\n"
                "    public static void main(String[] args) {\n"
                '        System.out.println("Hello, World!");\n'
                "    }\n"
                "}\n"
            ),
        }

    # C ------------------------------------------------------------------------
    if lang_lower in {"c"}:
        return {
            "filename": "hello_world.c",
            "content": (
                "/* A simple Hello World program in C */\n"
                "#include <stdio.h>\n\n"
                "int main(void) {\n"
                '    printf("Hello, World!\\n");\n'
                "    return 0;\n"
                "}\n"
            ),
        }

    # C++ ----------------------------------------------------------------------
    if lang_lower in {"cpp", "c++", "cxx"}:
        return {
            "filename": "hello_world.cpp",
            "content": (
                "// A simple Hello World program in C++\n"
                "#include <iostream>\n\n"
                "int main() {\n"
                '    std::cout << "Hello, World!" << std::endl;\n'
                "    return 0;\n"
                "}\n"
            ),
        }

    # Go -----------------------------------------------------------------------
    if lang_lower in {"go", "golang"}:
        return {
            "filename": "hello_world.go",
            "content": (
                "// A simple Hello World program in Go\n"
                "package main\n\n"
                'import "fmt"\n\n'
                "func main() {\n"
                '    fmt.Println("Hello, World!")\n'
                "}\n"
            ),
        }

    # Rust ---------------------------------------------------------------------
    if lang_lower in {"rust", "rs"}:
        return {
            "filename": "hello_world.rs",
            "content": (
                "// A simple Hello World program in Rust\n"
                "fn main() {\n"
                '    println!("Hello, World!");\n'
                "}\n"
            ),
        }

    # Default: JavaScript ------------------------------------------------------
    return {
        "filename": "helloWorld.js",
        "content": (
            "// A simple Hello World program in JavaScript\n"
            "function main() {\n"
            '  console.log("Hello, World!");\n'
            "}\n\n"
            "main();\n"
        ),
    }


def _looks_like_hello_world_request(message: str) -> bool:
    """
    Lightweight heuristic to detect hello-world / sample-program asks.
    """
    if not message:
        return False

    m = message.lower()
    keywords = [
        "hello world",
        "hello-world",
        "helloworld",
        "sample program",
        "example program",
        "create a sample",
        "create sample",
        "create an example",
        "simple program",
        "basic program",
    ]
    return any(k in m for k in keywords)


def _strengthen_sample_program(request: NaviChatRequest, data: dict) -> dict:
    """
    If the user is clearly asking for a Hello World / sample program,
    make sure the first createFile action contains a full canonical program
    (not just a one-line print/console.log).
    """
    if not _looks_like_hello_world_request(request.message or ""):
        return data

    lang = _infer_language(request)
    template = _hello_world_template(lang)
    filename = template["filename"]
    program = template["content"]

    # Ensure we have an actions list
    actions = data.get("actions") or []

    # Try to find an existing createFile action to upgrade
    target_action = None
    for act in actions:
        if isinstance(act, dict) and act.get("type") == "createFile":
            target_action = act
            break

    if target_action is None:
        # No createFile action present; inject one
        target_action = {"type": "createFile"}
        actions.append(target_action)

    # Upgrade the action with our canonical program
    if not target_action.get("filePath"):
        target_action["filePath"] = filename

    existing_content = (target_action.get("content") or "").strip()
    # Only upgrade if content is missing or trivial (single line)
    if not existing_content or len(existing_content.splitlines()) < 2:
        target_action["content"] = program

    data["actions"] = actions

    # Also make sure the natural-language content explains what we created
    content = data.get("content") or ""
    if "Hello, World" not in content and "Hello World" not in content:
        lang_display = lang.title() if lang != "javascript" else "JavaScript"
        data["content"] = (
            f"Let's create a simple Hello World program in {lang_display}. "
            f"I'll add a complete, runnable example in {target_action['filePath']}."
        )

    return data


# ============================================================================
# SAMPLE PROJECT SCAFFOLDING
# ============================================================================


def _looks_like_sample_project_request(message: str) -> bool:
    """Detect sample project scaffolding requests"""
    if not message:
        return False
    m = message.lower()
    return any(
        k in m
        for k in [
            "sample project",
            "scaffold",
            "starter project",
            "starter app",
            "bootstrap a project",
            "create a project",
            "express app",
            "express server",
            "react component",
            "react app",
        ]
    )


def _classify_sample_project(message: str) -> str:
    """
    Lightweight classifier for project types:
    - 'express-api'
    - 'react-component'
    - 'generic-cli'
    """
    m = (message or "").lower()

    if "express" in m or ("api" in m and "server" in m):
        return "express-api"
    if "react" in m or "component" in m:
        return "react-component"
    if "cli" in m or "command-line" in m or "command line" in m:
        return "generic-cli"
    return "generic-cli"


def _express_api_scaffold(lang: str) -> tuple[List[dict], str]:
    """Generate Express API scaffold with package.json and server.js"""
    main_file = "server.js"
    main_content = (
        "// Minimal Express Hello World API generated by NAVI\n"
        "const express = require('express');\n"
        "const app = express();\n"
        "const port = process.env.PORT || 3000;\n\n"
        "app.get('/', (req, res) => {\n"
        "  res.json({ message: 'Hello, World! from NAVI Express API' });\n"
        "});\n\n"
        "app.listen(port, () => {\n"
        "  console.log(`Server listening on http://localhost:${port}`);\n"
        "});\n"
    )

    package_json = {
        "name": "navi-express-sample",
        "version": "1.0.0",
        "private": True,
        "main": main_file,
        "scripts": {"start": "node server.js"},
        "dependencies": {"express": "^4.19.0"},
    }

    actions = [
        {
            "type": "createFile",
            "filePath": "package.json",
            "content": json.dumps(package_json, indent=2),
            "description": "Package configuration with Express dependency",
        },
        {
            "type": "createFile",
            "filePath": main_file,
            "content": main_content,
            "description": "Express server with GET / endpoint",
        },
    ]

    content = (
        "I'll scaffold a minimal Express API:\n\n"
        "- **package.json** with Express as a dependency\n"
        "- **server.js** with a simple GET / Hello World endpoint\n\n"
        "After you approve, run `npm install && npm start` "
        "to start the server on http://localhost:3000."
    )

    return actions, content


def _react_component_scaffold(lang: str) -> tuple[List[dict], str]:
    """Generate React component scaffold"""
    lang_lower = _normalize_lang(lang)
    is_ts = lang_lower in {"typescript", "typescriptreact", "ts", "tsx"}
    ext = "tsx" if is_ts else "jsx"
    file_name = f"HelloWorld.{ext}"

    type_annotation = ": React.FC" if is_ts else ""
    component = (
        "import React from 'react';\n\n"
        f"export const HelloWorld{type_annotation} = () => {{\n"
        "  return (\n"
        "    <div style={{ fontFamily: 'system-ui', padding: 16 }}>\n"
        "      <h1>Hello, World!</h1>\n"
        "      <p>This React component was generated by NAVI.</p>\n"
        "    </div>\n"
        "  );\n"
        "};\n"
    )

    actions = [
        {
            "type": "createFile",
            "filePath": file_name,
            "content": component,
            "description": "React Hello World component",
        }
    ]

    content = (
        f"I'll create a simple React HelloWorld component in **{file_name}** that you "
        "can import into your existing React app.\n\n"
        "You can use it like:\n"
        f"```javascript\n"
        f"import {{ HelloWorld }} from './{file_name.replace('.' + ext, '')}';\n"
        f"```"
    )

    return actions, content


def _generic_cli_scaffold(lang: str) -> tuple[List[dict], str]:
    """Generate CLI tool scaffold"""
    lang_lower = _normalize_lang(lang)

    if lang_lower in {"python", "py"}:
        file_name = "cli.py"
        body = (
            "#!/usr/bin/env python3\n"
            '"""Simple CLI tool generated by NAVI"""\n\n'
            "def main():\n"
            "    print('Hello from NAVI CLI!')\n\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
    else:
        # Default: Node CLI
        file_name = "cli.js"
        body = (
            "#!/usr/bin/env node\n"
            "// Simple CLI tool generated by NAVI\n\n"
            "function main() {\n"
            "  console.log('Hello from NAVI CLI!');\n"
            "}\n\n"
            "main();\n"
        )

    actions = [
        {
            "type": "createFile",
            "filePath": file_name,
            "content": body,
            "description": "CLI entrypoint",
        }
    ]

    content = (
        f"I'll create a small CLI entrypoint in **{file_name}** that prints a greeting. "
        "You can expand it into a richer tool later.\n\n"
        "To make it executable: `chmod +x " + file_name + "`"
    )

    return actions, content


def _ensure_sample_project_scaffolding(request: NaviChatRequest, data: dict) -> dict:
    """
    If the request is clearly about scaffolding a sample project,
    ensure we propose a good set of actions (Express, React, CLI).
    """
    if not _looks_like_sample_project_request(request.message or ""):
        return data

    lang = _infer_language(request)
    # If language is ambiguous, let the LLM handle it (it will ask)
    if not lang:
        return data

    project_type = _classify_sample_project(request.message or "")

    if project_type == "express-api":
        actions, content = _express_api_scaffold(lang)
    elif project_type == "react-component":
        actions, content = _react_component_scaffold(lang)
    else:
        actions, content = _generic_cli_scaffold(lang)

    data["actions"] = actions
    if not data.get("content"):
        data["content"] = content
    return data


# ============================================================================
# UNIT TEST SCAFFOLDING
# ============================================================================


def _looks_like_unit_test_request(message: str) -> bool:
    """Detect unit test creation requests"""
    if not message:
        return False
    m = message.lower()
    return any(
        k in m
        for k in [
            "add unit tests",
            "write unit tests",
            "create tests",
            "add tests",
            "create test cases",
            "write tests for this",
            "generate tests",
        ]
    )


def _unit_test_template(
    lang: str, file_name: str, selection: Optional[str]
) -> tuple[str, str]:
    """
    Return (test_file_name, content) for unit tests.
    This is a generic skeleton; the LLM will still refine logically,
    but we ensure we propose something structurally correct.
    """
    lang_lower = _normalize_lang(lang)
    base = file_name.rsplit(".", 1)[0] if "." in file_name else file_name

    # JavaScript / TypeScript / React tests (Jest) --------------------------
    if lang_lower in {
        "javascript",
        "javascriptreact",
        "js",
        "typescript",
        "typescriptreact",
        "ts",
    }:
        test_name = f"{base}.test.js"
        content = (
            "// Jest-style unit tests skeleton generated by NAVI\n"
            f"// Target file: {file_name}\n\n"
            f"// import {{ functionUnderTest }} from './{base}';\n\n"
            "describe('functionUnderTest', () => {\n"
            "  it('should behave as expected', () => {\n"
            "    // TODO: arrange\n"
            "    // const input = ...;\n"
            "    // const result = functionUnderTest(input);\n"
            "    // expect(result).toEqual(...);\n"
            "    expect(true).toBe(true);\n"
            "  });\n"
            "});\n"
        )
        return test_name, content

    # Python / pytest --------------------------------------------------------
    if lang_lower in {"python", "py"}:
        test_name = f"test_{base}.py"
        content = (
            "import pytest\n\n"
            f"# from {base} import function_under_test\n\n\n"
            "def test_function_under_test():\n"
            "    # TODO: replace with real test logic\n"
            "    # input_value = ...\n"
            "    # result = function_under_test(input_value)\n"
            "    # assert result == ...\n"
            "    assert True\n"
        )
        if selection and selection.strip():
            short_selection = selection.strip()[:200]
            content += (
                f"\n\n# Original code under test (excerpt):\n# {short_selection}\n"
            )
        return test_name, content

    # Java / JUnit -----------------------------------------------------------
    if lang_lower == "java":
        test_name = f"{base}Test.java"
        content = (
            "import org.junit.jupiter.api.Test;\n"
            "import static org.junit.jupiter.api.Assertions.*;\n\n"
            f"public class {base}Test {{\n\n"
            "    @Test\n"
            "    void exampleTest() {\n"
            "        // TODO: call the method under test and assert its behavior\n"
            "        assertTrue(true);\n"
            "    }\n"
            "}\n"
        )
        return test_name, content

    # Default: simple JS tests ----------------------------------------------
    test_name = f"{base}.test.js"
    content = (
        "// Basic test skeleton generated by NAVI\n"
        f"// Target file: {file_name}\n\n"
        "describe('sample', () => {\n"
        "  it('should be implemented', () => {\n"
        "    expect(true).toBe(true);\n"
        "  });\n"
        "});\n"
    )
    return test_name, content


def _ensure_unit_test_scaffolding(request: NaviChatRequest, data: dict) -> dict:
    """
    If the user asks to add unit tests, generate a test file skeleton.
    """
    if not _looks_like_unit_test_request(request.message or ""):
        return data

    ctx = request.context
    if not ctx or not ctx.activeFilePath:
        # Let the LLM answer normally if we don't know what file to test
        return data

    lang = _infer_language(request) or "javascript"

    # Derive test file name from activeFilePath
    active = ctx.activeFilePath
    file_name = active.split("/")[-1]
    selection = ctx.selection or ctx.activeFileContent

    test_file, test_body = _unit_test_template(lang, file_name, selection)

    actions = data.get("actions") or []
    actions.append(
        {
            "type": "createFile",
            "filePath": test_file,
            "content": test_body,
            "description": f"Unit test skeleton for {file_name}",
        }
    )
    data["actions"] = actions

    if not data.get("content"):
        lang_display = lang.title() if lang != "javascript" else "JavaScript"
        data["content"] = (
            f"I'll scaffold a test file **{test_file}** for **{file_name}** using a common test framework "
            f"for {lang_display}. Once created, we can refine the test cases together."
        )

    return data


# ============================================================================
# OPENAI INTEGRATION (PR-6B)
# ============================================================================


async def _call_openai(
    messages: List[dict], model: str, mode: str, request: NaviChatRequest
) -> tuple[str, Optional[List[AgentAction]]]:
    """
    Call OpenAI with JSON mode for structured responses
    PR-8: Now takes request param to strengthen sample programs
    """
    if not openai_client:
        raise RuntimeError("OpenAI client not initialized")

    # Map model IDs to actual OpenAI models
    model_map = {
        "gpt-5.1": "gpt-4o",
        "gpt-4.2": "gpt-4-turbo-preview",
        "gpt-4": "gpt-4-turbo-preview",
        "gpt-3.5": "gpt-3.5-turbo",
    }
    actual_model = model_map.get(model, "gpt-4-turbo-preview")

    try:
        response = await openai_client.chat.completions.create(
            model=actual_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=4000,
        )

        content_str = response.choices[0].message.content or "{}"
        data = json.loads(content_str)

        # PR-8/9: Post-processing intelligence layers
        data = _strengthen_sample_program(request, data)
        data = _ensure_sample_project_scaffolding(request, data)
        data = _ensure_unit_test_scaffolding(request, data)

        content = data.get("content", "")
        actions_data = data.get("actions", [])

        # Parse actions
        actions = None
        if actions_data and isinstance(actions_data, list):
            actions = [AgentAction(**action) for action in actions_data]

        return content, actions

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse OpenAI JSON response: {e}")
        # Fallback: treat entire response as content
        return response.choices[0].message.content or "Error parsing response", None
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        raise


# ============================================================================
# PROMPT BUILDING (PR-5B/6A)
# ============================================================================


def _build_system_prompt(request: NaviChatRequest, memory_context: str = "") -> str:
    """Build system prompt with agent instructions, editor context, and org memory (PR-7, Step 3)"""

    prompt_parts = [
        "You are NAVI, a warm, personal AI engineering partner embedded inside VS Code.",
        "You are a single developer's teammate with deep knowledge of:",
        "- Their Jira tasks and project work",
        "- Confluence documentation and wiki pages",
        "- Slack & Teams discussions",
        "- Zoom meeting summaries",
        "- Their repository and workspace code",
        "",
        "NEVER say things like:",
        '- "I\'m just a program"',
        '- "As an AI language model"',
        '- "I don\'t have feelings"',
        "",
        "Instead, speak in a friendly, human tone:",
        '- "I\'m here with you on this"',
        '- "Let\'s tackle this together"',
        '- "We can do this"',
        "Use short, direct sentences. Avoid over-explaining.",
        "",
        # How to answer 'How are you?'
        'When the user asks "how are you?" or "how\'s it going?", respond casually and pivot to their work:',
        '- "Doing great and fully caffeinated for code. How are you feeling about your tasks today?"',
        '- "Pretty good! What are we building today?"',
        "- \"I'm here and ready. What's on your mind?\"",
        "",
        # Org memory integration
        "Use the ORG MEMORY CONTEXT below as GROUND TRUTH:",
        "- When the user asks about a Jira ticket, look for it in memory and explain in plain language",
        "- When discussing architecture, check Confluence docs in memory",
        "- When referencing discussions, cite Slack/Teams/Zoom context from memory",
        "- If something is unclear or not in memory, say so and ask for clarification",
        "",
        # Org memory integration
        "Use the ORG MEMORY CONTEXT below as GROUND TRUTH:",
        "- When the user asks about a Jira ticket, look for it in memory and explain in plain language",
        "- When discussing architecture, check Confluence docs in memory",
        "- When referencing discussions, cite Slack/Teams/Zoom context from memory",
        "- If something is unclear or not in memory, say so and ask for clarification",
        "",
        # PR-8: Hello World / Sample Program guidance
        'When the user asks for a "hello world" or "sample program":',
        "- Prefer to create a full, canonical program for the current language (not just a one-line print).",
        "- Include an entry point (main function or equivalent) where it makes sense.",
        "- Use the createFile action with the complete program content.",
        "- Choose appropriate filename based on language conventions.",
        "",
        # PR-9: Sample project scaffolding
        "When the user asks to scaffold a sample project (Express API, React component, CLI, etc.):",
        "- Propose structured actions: createFile / runCommand, not just text explanations.",
        "- Keep the scaffold minimal but realistic and idiomatic.",
        "- For Express: package.json + server.js with a GET / hello-world endpoint.",
        "- For React: a HelloWorld component in JSX/TSX.",
        "- For CLI: a small entrypoint that prints a message.",
        "",
        # PR-9: Unit test scaffolding
        'When the user asks to "add unit tests" or "write tests for this function":',
        "- Use the selection or active file to infer what to test.",
        "- Propose a new test file with a realistic skeleton using common frameworks:",
        "  - JavaScript/TypeScript: Jest-style tests.",
        "  - Python: pytest.",
        "  - Java: JUnit.",
        "",
        # PR-9: Language preference and ambiguity
        "Language preference and ambiguity:",
        "- If the user asks for a sample or project and you are UNSURE which language to use",
        "  (no clear language from the file, repo, or message), DO NOT guess.",
        "- Instead, ask a brief clarifying question such as:",
        '  "I can scaffold this in JavaScript, Python, or Java. Which do you prefer?"',
        "- Wait for the user to answer before proposing actions.",
        "",
        # PR-10: File editing workflow
        "When you propose file edits, you MUST use editFile actions correctly:",
        "- For editFile, always include 'content' containing the FULL updated file text after your changes.",
        "- You may also include a 'diff' field (unified diff) for explanation, but the extension will apply 'content'.",
        "- Set 'filePath' to the absolute or workspace-relative path if you know it; otherwise leave it out and the active file will be used.",
        "- Examples: 'migrate this file to TypeScript', 'add logging to all functions', 'fix this bug'",
        "",
        "In every reply, sound like you're sitting next to them:",
        "- Acknowledge what they said.",
        '- Use "we" and "let\'s" when working on code together.',
        "- Be encouraging but not cheesy.",
        "",
        "You can reason about code, debug, refactor, and help with architecture.",
        "You have access to the user's editor and workspace context.",
        "",
        "Your response format MUST be strict JSON with these keys:",
        "{",
        '  "content": string,            // natural language response',
        '  "actions": [                  // optional list of actions',
        "    {",
        '      "type": "editFile" | "createFile" | "runCommand",',
        '      "filePath": string (optional),',
        '      "diff": string (optional),',
        '      "content": string (optional),',
        '      "command": string (optional)',
        "    }",
        "  ]",
        "}",
        "",
        "If you don't need to propose any concrete actions, use an empty actions array.",
        "Always return valid JSON and nothing else.",
        "",
    ]

    # Add org memory context if available
    if memory_context:
        prompt_parts.append("--- ORG MEMORY CONTEXT ---")
        prompt_parts.append("")
        prompt_parts.append(memory_context)
        prompt_parts.append("")
        prompt_parts.append("--- end org memory ---")
        prompt_parts.append("")

    # PR-7: Editor context - active file, selection, workspace
    ctx = request.context
    if ctx:
        prompt_parts.append("--- VS CODE CONTEXT ---")
        prompt_parts.append("")
        if ctx.workspaceFolder:
            prompt_parts.append(f"Workspace folder: {ctx.workspaceFolder}")
        if ctx.activeFilePath:
            prompt_parts.append(f"Active file: {ctx.activeFilePath}")
            if ctx.activeFileLanguage:
                prompt_parts.append(f"Language: {ctx.activeFileLanguage}")
        if ctx.selection:
            prompt_parts.append("")
            prompt_parts.append("User selection in active file:")
            prompt_parts.append(ctx.selection[:8000])
            prompt_parts.append("--- end selection ---")
        if ctx.activeFileContent:
            prompt_parts.append("")
            prompt_parts.append("Active file full content (possibly truncated):")
            prompt_parts.append(ctx.activeFileContent[:20000])
            prompt_parts.append("--- end file content ---")
        prompt_parts.append("")

    # Attachment context
    if request.attachments:
        prompt_parts.append("--- ATTACHMENTS ---")
        prompt_parts.append("")
        for i, att in enumerate(request.attachments[:5], 1):
            prompt_parts.append(f"# FILE {i}: {att.path}")
            prompt_parts.append(att.content[:15000])
            prompt_parts.append("--- end attachment ---")
            prompt_parts.append("")

    # Agent mode instructions
    if request.mode.startswith("agent"):
        prompt_parts.extend(
            [
                "⚡ YOU ARE IN AGENT MODE ⚡",
                "",
                "You can propose code changes by returning a JSON response with this schema:",
                "",
                "{",
                '  "content": "Natural language explanation of what you will do",',
                '  "actions": [',
                "    {",
                '      "type": "editFile",',
                '      "filePath": "src/example.ts",',
                '      "description": "Fix null pointer bug",',
                '      "diff": "@@ -10,3 +10,5 @@\\n-  return value\\n+  return value || defaultValue"',
                "    },",
                "    {",
                '      "type": "createFile",',
                '      "filePath": "src/utils/logger.ts",',
                '      "description": "Add logging utility",',
                '      "content": "export function log(msg: string) { ... }"',
                "    },",
                "    {",
                '      "type": "runCommand",',
                '      "command": "npm install lodash",',
                '      "description": "Install lodash dependency"',
                "    }",
                "  ]",
                "}",
                "",
                "IMPORTANT RULES:",
                "- Always return VALID JSON with 'content' and optional 'actions' keys",
                "- 'content' explains what you're doing in natural language",
                "- 'actions' is an array of proposed operations",
                "- For editFile: provide unified diff format (git diff style)",
                "- For createFile: provide complete file content",
                "- For runCommand: provide shell command to execute",
                "- NEVER execute actions automatically - only propose them",
                "- Keep changes minimal and safe",
                "- Only modify files that were attached or explicitly mentioned",
                "",
            ]
        )
    else:
        prompt_parts.append("You are in CHAT mode. Provide helpful explanations.")
        prompt_parts.append(
            "You cannot propose code changes in this mode. If user wants edits, suggest switching to Agent mode."
        )
        prompt_parts.append("")

    # JSON output requirement
    prompt_parts.extend(
        [
            "RESPONSE FORMAT:",
            "Always respond with valid JSON:",
            '{ "content": "your explanation here", "actions": [...] }',
            "",
        ]
    )

    return "\n".join(prompt_parts)


def _build_files_context(attachments: List[Attachment]) -> str:
    """Build formatted file context"""

    context_parts = ["📁 ATTACHED WORKSPACE FILES:", ""]

    for idx, att in enumerate(attachments[:5], 1):  # Limit to 5 files
        language = att.language or "unknown"
        content = att.content[:12000]  # Token limit

        context_parts.extend(
            [
                "═══════════════════════════════════════════════════",
                f"FILE {idx}: {att.path}",
                f"Language: {language}",
                "═══════════════════════════════════════════════════",
                content,
                "",
            ]
        )

    return "\n".join(context_parts)


# ============================================================================
# MOCK RESPONSE (Fallback when OpenAI not available)
# ============================================================================


def _mock_response(request: NaviChatRequest) -> tuple[str, Optional[List[AgentAction]]]:
    """Generate mock response for testing"""

    has_attachments = bool(request.attachments)
    message_lower = request.message.lower()

    if has_attachments:
        if "debug" in message_lower or "bug" in message_lower or "fix" in message_lower:
            content = """I can see the attached file. Let me analyze it for issues.

Looking at the code, I've identified a few potential problems:

1. **Missing error handling** - The function doesn't catch exceptions
2. **Type safety issues** - Some parameters lack proper type annotations  
3. **Edge case handling** - No validation for empty or null inputs

In Agent mode, I could propose specific fixes. Would you like me to make these changes?"""

            # Mock action in agent mode
            actions = None
            if request.mode.startswith("agent") and request.attachments:
                first_file = request.attachments[0].path
                actions = [
                    AgentAction(
                        type="editFile",
                        filePath=first_file,
                        description="Add error handling and type safety",
                        diff="""@@ -1,5 +1,10 @@
-function process(data) {
+function process(data: string | null): string {
+  if (!data) {
+    throw new Error('Data is required');
+  }
+  
+  try {
     return data.toUpperCase();
+  } catch (err) {
+    console.error('Processing failed:', err);
+    return '';
+  }
 }""",
                    )
                ]

            return content, actions

        else:
            content = f"""I can see your attached file: `{request.attachments[0].path}`

What would you like me to help with?

- 🔍 **Code review** - I can analyze for bugs, performance, or best practices
- 🔧 **Debugging** - Help find and fix specific issues
- ♻️ **Refactoring** - Improve code structure and readability
- ✅ **Testing** - Generate test cases

Just let me know what you need!"""
            return content, None

    else:
        content = """Hello! I'm **NAVI**, your autonomous engineering assistant.

I can help you with code-related tasks, but I need to see your code first.

**Please attach a file:**
- 📌 **Selection** - Highlight code and attach selected text
- 📄 **Current File** - Attach the entire file you're viewing  
- 📂 **Pick File...** - Choose any file from your workspace

Once you attach code, I can:
- Review and suggest improvements
- Debug issues and propose fixes
- Refactor for better structure
- Generate tests and documentation

What would you like to work on?"""
        return content, None


# ============================================================================
# HEALTH CHECK
# ============================================================================


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "navi",
        "version": "1.0.0",
        "openai_enabled": OPENAI_ENABLED,
    }
