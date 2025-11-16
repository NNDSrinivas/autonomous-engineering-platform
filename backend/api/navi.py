"""
NAVI Chat API - Autonomous Engineering Assistant for VS Code Extension
PR-6A/B/C: Complete agent implementation with OpenAI, diffs, multi-file ops
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
import logging
import json
import os

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


class NaviChatResponse(BaseModel):
    """Response to VS Code extension"""

    role: str = "assistant"
    content: str
    actions: Optional[List[AgentAction]] = None


# ============================================================================
# MAIN ENDPOINT (PR-6B)
# ============================================================================


@router.post("/chat", response_model=NaviChatResponse)
async def navi_chat(request: NaviChatRequest) -> NaviChatResponse:
    """
    Handle NAVI chat from VS Code extension

    PR-5B: Uses attachments to build file context
    PR-6A/B: Returns agent actions (editFile, createFile, runCommand)
    PR-6C: Supports unified diffs for clean edits
    """
    try:
        logger.info(
            f"[NAVI] Request - model: {request.model}, mode: {request.mode}, "
            f"message: {request.message[:100]}, attachments: {len(request.attachments)}"
        )

        # Build system prompt with file context and agent instructions
        system_prompt = _build_system_prompt(request)

        # Build messages for LLM
        messages = [{"role": "system", "content": system_prompt}]

        # Add file context if attachments exist
        if request.attachments:
            files_context = _build_files_context(request.attachments)
            messages.append({"role": "system", "content": files_context})

        # Add user message
        messages.append({"role": "user", "content": request.message})

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
# PR-8: HELLO WORLD / SAMPLE PROGRAM HELPERS
# ============================================================================


def _infer_language(request: NaviChatRequest) -> str:
    """
    Guess the target language for a sample/hello-world request.

    Priority:
    1. Active editor language (context.activeFileLanguage)
    2. First attachment language
    3. Fallback to 'javascript'
    """
    ctx = request.context
    if ctx and ctx.activeFileLanguage:
        return ctx.activeFileLanguage.lower()

    if request.attachments:
        lang = request.attachments[0].language
        if lang:
            return lang.lower()

    return "javascript"


def _hello_world_template(lang: str) -> dict:
    """
    Return {filename, content} for a full Hello World PROGRAM in the given language.
    """
    lang_lower = (lang or "").lower()

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

        # PR-8: Upgrade Hello World / sample-program actions
        data = _strengthen_sample_program(request, data)

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


def _build_system_prompt(request: NaviChatRequest) -> str:
    """Build system prompt with agent instructions and editor context (PR-7)"""

    prompt_parts = [
        "You are NAVI, a friendly, highly skilled senior engineer embedded inside VS Code.",
        "You talk like a human teammate: warm, direct, and practical.",
        'Never say things like "I\'m just a program" or "I\'m just an AI language model".',
        "Never downplay yourself by saying you don't have feelings.",
        'Instead, speak as a collaborator: "I\'m here with you", "we can do", "let\'s try".',
        "",
        # How to answer 'How are you?'
        'When the user asks things like "how are you" or "how\'s it going", respond briefly and warmly, as a teammate would, for example:',
        '- "I\'m doing well and excited to dig into your code with you."',
        '- "Pretty good! I\'m here with you in this workspace—what are we building today?"',
        "Then quickly pivot to their work or question so it stays productive and personal.",
        "",
        # PR-8: Hello World / Sample Program guidance
        'When the user asks for a "hello world" or "sample program":',
        "- Prefer to create a full, canonical program for the current language (not just a one-line print).",
        "- Include an entry point (main function or equivalent) where it makes sense.",
        "- Use the createFile action with the complete program content.",
        "- Choose appropriate filename based on language conventions.",
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
