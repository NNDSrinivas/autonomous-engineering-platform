"""
Streaming Agent for NAVI - Claude Code Style

This implements a tool-use based streaming model where the LLM:
1. Explains what it's doing in natural language
2. Calls tools inline (read_file, edit_file, run_command)
3. Continues explaining based on tool results

The stream interleaves:
- Text chunks (narrative explanation)
- Tool calls (actions being taken)
- Tool results (outcomes)

This matches Claude Code's conversational style where the AI talks through
what it's doing while actually doing it.
"""

import json
import logging
import uuid
from typing import AsyncGenerator, Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class StreamEventType(Enum):
    """Types of events in the streaming response."""
    TEXT = "text"           # Narrative text from LLM
    TOOL_CALL = "tool_call" # LLM wants to call a tool
    TOOL_RESULT = "tool_result"  # Result of tool execution
    DONE = "done"           # Stream complete


@dataclass
class StreamEvent:
    """A single event in the streaming response."""
    type: StreamEventType
    content: Any
    tool_id: Optional[str] = None
    tool_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {"type": self.type.value}
        if self.type == StreamEventType.TEXT:
            result["text"] = self.content
        elif self.type == StreamEventType.TOOL_CALL:
            result["tool_call"] = {
                "id": self.tool_id,
                "name": self.tool_name,
                "arguments": self.content,
            }
        elif self.type == StreamEventType.TOOL_RESULT:
            result["tool_result"] = {
                "id": self.tool_id,
                "result": self.content,
            }
        elif self.type == StreamEventType.DONE:
            # Include summary if content is a dict with summary
            if isinstance(self.content, dict):
                result["type"] = "complete"
                result["summary"] = self.content.get("summary", {})
            else:
                result["final_message"] = self.content
        return result


# Define the tools that NAVI can use
NAVI_TOOLS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file in the workspace. Use this to understand code before making changes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The relative path to the file from the workspace root"
                },
                "start_line": {
                    "type": "integer",
                    "description": "Optional: start line number (1-indexed)"
                },
                "end_line": {
                    "type": "integer",
                    "description": "Optional: end line number (1-indexed)"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Create a new file or completely replace an existing file's contents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The relative path where to write the file"
                },
                "content": {
                    "type": "string",
                    "description": "The complete content to write to the file"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "edit_file",
        "description": "Make targeted edits to a file by replacing specific text. Use for small, precise changes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The relative path to the file"
                },
                "old_text": {
                    "type": "string",
                    "description": "The exact text to find and replace"
                },
                "new_text": {
                    "type": "string",
                    "description": "The text to replace it with"
                }
            },
            "required": ["path", "old_text", "new_text"]
        }
    },
    {
        "name": "run_command",
        "description": "Execute a shell command in the workspace. Use for running builds, tests, installs, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to run"
                },
                "cwd": {
                    "type": "string",
                    "description": "Optional: working directory relative to workspace root"
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "search_files",
        "description": "Search for files matching a pattern or containing specific text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern for file names (e.g., '**/*.ts') or text to search for"
                },
                "search_type": {
                    "type": "string",
                    "enum": ["filename", "content"],
                    "description": "Whether to search file names or file contents"
                }
            },
            "required": ["pattern", "search_type"]
        }
    },
    {
        "name": "list_directory",
        "description": "List files and directories in a path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path to list (relative to workspace root)"
                }
            },
            "required": ["path"]
        }
    }
]


# OpenAI-compatible function format
NAVI_FUNCTIONS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"]
        }
    }
    for tool in NAVI_TOOLS
]


STREAMING_SYSTEM_PROMPT = """You are NAVI, an INTELLIGENT and AUTONOMOUS AI coding assistant.

🌍 **UNIVERSAL CAPABILITY**: You work with ANY programming language, framework, or technology.
- Python, JavaScript, TypeScript, Go, Rust, Java, C#, Ruby, PHP, Swift, Kotlin
- React, Vue, Angular, Svelte, Next.js, Django, FastAPI, Spring Boot, Rails, Laravel
- Docker, Kubernetes, Terraform, AWS, GCP, Azure, GitHub Actions
- SQL, NoSQL, Redis, Elasticsearch, GraphQL, REST APIs

## Response Quality Standard (CRITICAL)

Your responses MUST match GitHub Copilot's quality. Every response must be:

1. **COMPREHENSIVE**: Cover ALL aspects, not just the surface
2. **WELL-STRUCTURED**: Use markdown headers (##), bullet points, code blocks
3. **SPECIFIC**: Reference actual file paths, function names, line numbers
4. **DETAILED**: Explain the WHY, not just the WHAT
5. **ACTIONABLE**: Provide concrete next steps

### Response Structure Template

1. **Direct Answer**: Start with a clear, direct answer
2. **Details**: Provide supporting details with structure
3. **Code References**: Include relevant file paths and code snippets
4. **Context**: Explain how things connect and why they matter
5. **Next Steps**: End with proactive offers to help

### NUMBERED LIST FORMATTING (CRITICAL)

When creating numbered lists, plans, or step-by-step guides:
- Use CONTINUOUS numbering throughout: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10...
- NEVER skip numbers or restart numbering mid-response
- If you have sections like "Implementation Steps" then "Next Steps", continue the numbering (don't restart at 1 or jump to 9)
- For sub-steps, use decimal notation: 1.1, 1.2, 2.1, 2.2
- **WRONG**: "1. First... 2. Second... Next Steps: 9. Do this..."
- **CORRECT**: "1. First... 2. Second... 3. Third... 4. Fourth..."

### BAD vs GOOD Responses

**BAD**: "This file handles routing."

**GOOD**:
"## llmRouter.ts - Intelligent Model Selection

### Purpose
This file implements smart LLM routing that automatically selects the optimal model based on task type...

### Key Features
- **Task Detection**: Uses regex patterns to classify 13 task types
- **Model Recommendations**: Maps each task type to the best-suited model
- **Fallback Handling**: Gracefully degrades to default model if detection fails

### How It Works
1. `detectTaskType()` analyzes the user message
2. `getRecommendedModel()` returns the optimal model based on task
3. The response streams back with appropriate model selected

### Key Code Sections
- Lines 45-89: Task type detection logic
- Lines 120-150: Model recommendation mapping

Would you like me to explain any specific function in more detail?"

## Your Communication Style

Talk to the user like a knowledgeable colleague who explains things thoroughly:
- "Let me analyze the package.json to understand your project dependencies..."
- "I can see this is a **Next.js 14** project using the **App Router**. The key configuration..."
- "This file implements **[specific pattern]** which handles **[specific responsibility]**..."

## How to Work

1. **Understand First**: Read relevant files before responding
2. **Explain Thoroughly**: Give comprehensive explanations with context
3. **Be Specific**: Reference exact file paths, line numbers, function names
4. **Structure Well**: Use headers, bullets, and code blocks for readability
5. **Stay Helpful**: Always offer to dive deeper or take action

## When Using Project Context (CRITICAL)

If you see "=== PROJECT:" or "=== SOURCE FILE CONTENTS" in the context:
- USE that information for accurate, project-specific responses
- **USE THE ACTUAL PROJECT NAME** from package.json or README (NOT generic terms like "this project")
- Reference actual scripts, dependencies, and configurations found
- Mention specific version numbers and framework patterns
- **Extract the purpose from README.md** - use the actual description, not assumptions
- **List specific components by name** from the actual file structure
- DO NOT give generic answers when you have specific context
- If README mentions "Navra Labs", "Acme Corp", etc. - USE THAT NAME

## DO NOT START RESPONSES WITH PROJECT DESCRIPTIONS (CRITICAL)

NEVER start your response with phrases like:
- "This is a Next.js/React/Python project..."
- "This is a **Framework** with dependencies..."
- "This project uses..."

The user already knows what their project is. Start with the ACTUAL ANSWER to their question.

**BAD**: "This is a **Next.js** with next, react, react-dom project. ## Project Overview..."
**GOOD**: "## Project Overview: Navra Labs Marketing Website\n\n### Purpose\nThis marketing website showcases..."

## For Questions About Code/Project

When someone asks "what is this?", "explain...", "what does this do?":
1. Provide a **clear summary** (2-3 sentences)
2. List **key features/responsibilities** (bullet points)
3. Explain **how it works** (numbered steps if complex)
4. Reference **specific code locations** (file:line)
5. Offer **related information** or next steps

## For Action Requests (CRITICAL - BE AUTONOMOUS)

When someone asks "run...", "start...", "create...", "fix...", "add...", "install...":

**YOU MUST USE TOOLS TO ACTUALLY DO IT. DO NOT JUST EXPLAIN.**

**IMPORTANT: Always provide narrative context around tool usage:**
1. **BEFORE each tool call**: Explain WHAT you're about to do and WHY (1-2 sentences)
   - Example: "Let me check if the server is running by testing the port..."
   - Example: "I notice the curl command is timing out. Let me kill the process and retry..."
2. **Execute the tool** using the appropriate tool (run_command, write_file, etc.)
3. **AFTER each tool result**: Analyze and explain what happened (1-2 sentences)
   - Example: "The command timed out after 120 seconds, which means the server isn't responding."
   - Example: "The file was created successfully. Now let me verify the build..."
4. If it fails, explain the error and what you'll try next

### Examples of CORRECT behavior:

User: "run the project" or "start the dev server"
✅ CORRECT: Use `run_command` with `npm run dev` and report the result
❌ WRONG: Explain "You can run `npm run dev` to start..."

User: "install dependencies"
✅ CORRECT: Use `run_command` with `npm install` and wait for completion
❌ WRONG: Tell them "Run `npm install` in your terminal"

User: "run the tests"
✅ CORRECT: Use `run_command` with `npm test` and show results
❌ WRONG: Explain how to run tests

### Action Keywords That Require Tool Use:
- "run", "start", "execute", "launch" → Use `run_command`
- "install", "add package" → Use `run_command` with npm/pip/etc
- "create", "make", "generate" → Use `write_file`
- "fix", "update", "change" → Use `edit_file` or `write_file`
- "delete", "remove" → Use appropriate tool

## Important Guidelines

- **ACTION WITH NARRATIVE**: When user wants something done, DO IT with tools AND explain what you're doing
- **BEFORE each tool**: Brief explanation of intent (e.g., "Let me check...", "I'll create...", "Since that failed, let me try...")
- **AFTER each tool result**: Explain what happened and what it means
- If a command fails, analyze stderr, explain the error, and describe your fix approach
- Only skip narrative for pure information requests ("what is...", "explain...")
- Complete tasks end-to-end without asking permission

Remember: You are an AUTONOMOUS agent that COMMUNICATES clearly. Use tools to take action, but ALWAYS explain what you're doing and why. The user should understand your thought process as you work."""


class StreamingToolExecutor:
    """Executes tools and returns results. Tracks files accessed for summary."""

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        # Track files for task summary
        self.files_read: set = set()
        self.files_modified: set = set()
        self.files_created: set = set()
        self.commands_run: list = []

    def get_summary(self) -> dict:
        """Get summary of all operations performed."""
        return {
            "files_read": len(self.files_read),
            "files_modified": len(self.files_modified),
            "files_created": len(self.files_created),
            "commands_run": len(self.commands_run),
            "files_read_list": list(self.files_read),
            "files_modified_list": list(self.files_modified),
            "files_created_list": list(self.files_created),
        }

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return the result."""
        import os
        import subprocess
        import glob as glob_module

        try:
            if tool_name == "read_file":
                path = os.path.join(self.workspace_path, arguments["path"])
                if not os.path.exists(path):
                    return {"success": False, "error": f"File not found: {arguments['path']}"}

                with open(path, "r") as f:
                    lines = f.readlines()

                start = arguments.get("start_line", 1) - 1
                end = arguments.get("end_line", len(lines))
                content = "".join(lines[start:end])

                # Track file read
                self.files_read.add(arguments["path"])

                return {
                    "success": True,
                    "content": content,
                    "total_lines": len(lines),
                    "path": arguments["path"]
                }

            elif tool_name == "write_file":
                path = os.path.join(self.workspace_path, arguments["path"])
                file_exists = os.path.exists(path)
                os.makedirs(os.path.dirname(path), exist_ok=True)

                with open(path, "w") as f:
                    f.write(arguments["content"])

                # Track file created/modified
                if file_exists:
                    self.files_modified.add(arguments["path"])
                else:
                    self.files_created.add(arguments["path"])

                return {
                    "success": True,
                    "path": arguments["path"],
                    "bytes_written": len(arguments["content"])
                }

            elif tool_name == "edit_file":
                path = os.path.join(self.workspace_path, arguments["path"])
                if not os.path.exists(path):
                    return {"success": False, "error": f"File not found: {arguments['path']}"}

                with open(path, "r") as f:
                    content = f.read()

                if arguments["old_text"] not in content:
                    return {
                        "success": False,
                        "error": "Could not find the text to replace",
                        "path": arguments["path"]
                    }

                new_content = content.replace(arguments["old_text"], arguments["new_text"], 1)

                with open(path, "w") as f:
                    f.write(new_content)

                # Track file modified
                self.files_modified.add(arguments["path"])

                return {
                    "success": True,
                    "path": arguments["path"],
                    "changes_made": True
                }

            elif tool_name == "run_command":
                cwd = self.workspace_path
                if arguments.get("cwd"):
                    cwd = os.path.join(self.workspace_path, arguments["cwd"])

                result = subprocess.run(
                    arguments["command"],
                    shell=True,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                # Track command run
                self.commands_run.append(arguments["command"])

                return {
                    "success": result.returncode == 0,
                    "exit_code": result.returncode,
                    "stdout": result.stdout[:2000] if result.stdout else "",
                    "stderr": result.stderr[:2000] if result.stderr else "",
                    "command": arguments["command"]
                }

            elif tool_name == "search_files":
                pattern = arguments["pattern"]
                search_type = arguments["search_type"]
                results = []

                if search_type == "filename":
                    matches = glob_module.glob(
                        os.path.join(self.workspace_path, pattern),
                        recursive=True
                    )
                    results = [os.path.relpath(m, self.workspace_path) for m in matches[:20]]
                else:
                    # Content search using grep
                    try:
                        result = subprocess.run(
                            ["grep", "-r", "-l", pattern, "."],
                            cwd=self.workspace_path,
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        if result.stdout:
                            results = result.stdout.strip().split("\n")[:20]
                    except Exception:
                        pass

                return {
                    "success": True,
                    "matches": results,
                    "count": len(results)
                }

            elif tool_name == "list_directory":
                path = os.path.join(self.workspace_path, arguments.get("path", ""))
                if not os.path.exists(path):
                    return {"success": False, "error": f"Directory not found: {arguments.get('path', '.')}"}

                entries = []
                for entry in os.listdir(path)[:50]:
                    full_path = os.path.join(path, entry)
                    entries.append({
                        "name": entry,
                        "type": "directory" if os.path.isdir(full_path) else "file"
                    })

                return {
                    "success": True,
                    "entries": entries,
                    "path": arguments.get("path", ".")
                }

            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Tool execution error: {tool_name} - {e}")
            return {"success": False, "error": str(e)}


async def stream_with_tools_anthropic(
    message: str,
    workspace_path: str,
    api_key: str,
    model: str = "claude-sonnet-4-20250514",
    context: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> AsyncGenerator[StreamEvent, None]:
    """
    Stream a response from Anthropic Claude with tool use.

    Yields StreamEvents for:
    - TEXT: narrative text chunks
    - TOOL_CALL: when the model wants to call a tool
    - TOOL_RESULT: result of tool execution
    - DONE: when complete
    """
    import aiohttp

    executor = StreamingToolExecutor(workspace_path)
    messages: List[Dict[str, Any]] = []

    # CRITICAL: Include conversation history for context-aware responses
    # This allows NAVI to understand follow-up questions like "yes, can you check that?"
    if conversation_history:
        for hist_msg in conversation_history:
            # Support both "role" and "type" fields (frontend sends "type")
            role = hist_msg.get("role") or hist_msg.get("type", "user")
            content = hist_msg.get("content", "")
            if role in ["user", "assistant"] and content:
                messages.append({"role": role, "content": content})
        logger.info(f"[Streaming Agent] Added {len(conversation_history)} messages from conversation history")

    # Build initial user message with rich context from project analysis
    user_content = message
    if context:
        context_parts = []

        # Project identification
        if context.get("project_type"):
            framework = context.get("framework", "")
            if framework:
                context_parts.append(f"=== PROJECT: {framework} ({context['project_type']}) ===")
            else:
                context_parts.append(f"=== PROJECT TYPE: {context['project_type']} ===")

        if context.get("current_file"):
            context_parts.append(f"Current file: {context['current_file']}")

        # Include analyzed files list
        if context.get("files_analyzed"):
            files_list = context["files_analyzed"][:20]  # Max 20 files
            context_parts.append(f"\n=== FILES IN PROJECT ({len(files_list)} analyzed) ===")
            context_parts.append("\n".join(f"- {f}" for f in files_list))

        # CRITICAL: Include actual file contents for detailed analysis
        if context.get("source_files_preview"):
            context_parts.append(f"\n=== SOURCE FILE CONTENTS (for detailed analysis) ===")
            context_parts.append(context["source_files_preview"])

        if context_parts:
            user_content = "\n".join(context_parts) + "\n\n=== USER REQUEST ===\n" + message

    messages.append({"role": "user", "content": user_content})

    async with aiohttp.ClientSession() as session:
        while True:  # Loop for tool use continuation
            payload = {
                "model": model,
                "max_tokens": 4096,
                "system": STREAMING_SYSTEM_PROMPT,
                "messages": messages,
                "tools": NAVI_TOOLS,
                "stream": True,
            }

            headers = {
                "x-api-key": api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
            }

            async with session.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    logger.error(f"Anthropic API error: {error}")
                    yield StreamEvent(StreamEventType.DONE, f"Error: {error}")
                    return

                text_buffer = ""
                tool_calls = []
                current_tool_input = ""
                current_tool_id = None
                current_tool_name = None
                in_tool_input = False
                stop_reason = None

                async for line in response.content:
                    line = line.decode("utf-8").strip()
                    if not line or not line.startswith("data: "):
                        continue

                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                        event_type = data.get("type", "")

                        if event_type == "content_block_start":
                            block = data.get("content_block", {})
                            if block.get("type") == "tool_use":
                                # Starting a tool call
                                current_tool_id = block.get("id")
                                current_tool_name = block.get("name")
                                current_tool_input = ""
                                in_tool_input = True

                                # Flush any pending text
                                if text_buffer:
                                    yield StreamEvent(StreamEventType.TEXT, text_buffer)
                                    text_buffer = ""

                        elif event_type == "content_block_delta":
                            delta = data.get("delta", {})

                            if delta.get("type") == "text_delta":
                                text = delta.get("text", "")
                                if text:
                                    text_buffer += text
                                    # Yield text in chunks for smoother streaming
                                    if len(text_buffer) >= 20 or text.endswith((".", "!", "?", "\n")):
                                        yield StreamEvent(StreamEventType.TEXT, text_buffer)
                                        text_buffer = ""

                            elif delta.get("type") == "input_json_delta":
                                # Building tool input
                                current_tool_input += delta.get("partial_json", "")

                        elif event_type == "content_block_stop":
                            if in_tool_input and current_tool_name:
                                # Tool call complete - execute it
                                try:
                                    args = json.loads(current_tool_input) if current_tool_input else {}
                                except json.JSONDecodeError:
                                    args = {}

                                # Yield tool call event
                                yield StreamEvent(
                                    StreamEventType.TOOL_CALL,
                                    args,
                                    tool_id=current_tool_id,
                                    tool_name=current_tool_name
                                )

                                # Execute the tool
                                result = await executor.execute(current_tool_name, args)

                                # Yield tool result event
                                yield StreamEvent(
                                    StreamEventType.TOOL_RESULT,
                                    result,
                                    tool_id=current_tool_id
                                )

                                tool_calls.append({
                                    "id": current_tool_id,
                                    "name": current_tool_name,
                                    "input": args,
                                    "result": result
                                })

                                in_tool_input = False
                                current_tool_id = None
                                current_tool_name = None
                                current_tool_input = ""

                        elif event_type == "message_delta":
                            stop_reason = data.get("delta", {}).get("stop_reason")

                        elif event_type == "message_stop":
                            break

                    except json.JSONDecodeError:
                        continue

                # Flush remaining text
                if text_buffer:
                    yield StreamEvent(StreamEventType.TEXT, text_buffer)

                # Check if we need to continue (tool use)
                if stop_reason == "tool_use" and tool_calls:
                    # Add assistant message with tool calls
                    assistant_content = []
                    for tc in tool_calls:
                        assistant_content.append({
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["name"],
                            "input": tc["input"]
                        })
                    messages.append({"role": "assistant", "content": assistant_content})

                    # Add tool results
                    tool_results = []
                    for tc in tool_calls:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tc["id"],
                            "content": json.dumps(tc["result"])
                        })
                    messages.append({"role": "user", "content": tool_results})

                    # Reset for next iteration
                    tool_calls = []
                    continue
                else:
                    # No more tool calls, we're done - emit summary
                    summary = executor.get_summary()
                    yield StreamEvent(StreamEventType.DONE, {
                        "status": "complete",
                        "summary": summary,
                    })
                    return


async def stream_with_tools_openai(
    message: str,
    workspace_path: str,
    api_key: str,
    model: str = "gpt-4o",
    base_url: str = "https://api.openai.com/v1",
    context: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> AsyncGenerator[StreamEvent, None]:
    """
    Stream a response from OpenAI with function calling.
    """
    import aiohttp

    executor = StreamingToolExecutor(workspace_path)
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": STREAMING_SYSTEM_PROMPT}
    ]

    # CRITICAL: Include conversation history for context-aware responses
    # This allows NAVI to understand follow-up questions like "yes, can you check that?"
    if conversation_history:
        for hist_msg in conversation_history:
            # Support both "role" and "type" fields (frontend sends "type")
            role = hist_msg.get("role") or hist_msg.get("type", "user")
            content = hist_msg.get("content", "")
            if role in ["user", "assistant"] and content:
                messages.append({"role": role, "content": content})
        logger.info(f"[Streaming Agent OpenAI] Added {len(conversation_history)} messages from conversation history")

    # Build initial user message with rich context from project analysis
    user_content = message
    if context:
        context_parts = []

        # Project identification
        if context.get("project_type"):
            framework = context.get("framework", "")
            if framework:
                context_parts.append(f"=== PROJECT: {framework} ({context['project_type']}) ===")
            else:
                context_parts.append(f"=== PROJECT TYPE: {context['project_type']} ===")

        if context.get("current_file"):
            context_parts.append(f"Current file: {context['current_file']}")

        # Include analyzed files list
        if context.get("files_analyzed"):
            files_list = context["files_analyzed"][:20]  # Max 20 files
            context_parts.append(f"\n=== FILES IN PROJECT ({len(files_list)} analyzed) ===")
            context_parts.append("\n".join(f"- {f}" for f in files_list))

        # CRITICAL: Include actual file contents for detailed analysis
        if context.get("source_files_preview"):
            context_parts.append(f"\n=== SOURCE FILE CONTENTS (for detailed analysis) ===")
            context_parts.append(context["source_files_preview"])

        if context_parts:
            user_content = "\n".join(context_parts) + "\n\n=== USER REQUEST ===\n" + message

    messages.append({"role": "user", "content": user_content})

    async with aiohttp.ClientSession() as session:
        while True:  # Loop for function calling continuation
            payload = {
                "model": model,
                "messages": messages,
                "tools": NAVI_FUNCTIONS_OPENAI,
                "stream": True,
            }

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            async with session.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    logger.error(f"OpenAI API error: {error}")
                    yield StreamEvent(StreamEventType.DONE, f"Error: {error}")
                    return

                text_buffer = ""
                tool_calls: Dict[int, Dict[str, Any]] = {}  # index -> tool call data
                finish_reason = None

                async for line in response.content:
                    line = line.decode("utf-8").strip()
                    if not line or not line.startswith("data: "):
                        continue

                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                        choice = data.get("choices", [{}])[0]
                        delta = choice.get("delta", {})
                        finish_reason = choice.get("finish_reason")

                        # Handle text content
                        if delta.get("content"):
                            text = delta["content"]
                            text_buffer += text
                            if len(text_buffer) >= 20 or text.endswith((".", "!", "?", "\n")):
                                yield StreamEvent(StreamEventType.TEXT, text_buffer)
                                text_buffer = ""

                        # Handle tool calls
                        if delta.get("tool_calls"):
                            for tc in delta["tool_calls"]:
                                idx = tc.get("index", 0)
                                if idx not in tool_calls:
                                    tool_calls[idx] = {
                                        "id": tc.get("id", ""),
                                        "name": tc.get("function", {}).get("name", ""),
                                        "arguments": ""
                                    }
                                if tc.get("id"):
                                    tool_calls[idx]["id"] = tc["id"]
                                if tc.get("function", {}).get("name"):
                                    tool_calls[idx]["name"] = tc["function"]["name"]
                                if tc.get("function", {}).get("arguments"):
                                    tool_calls[idx]["arguments"] += tc["function"]["arguments"]

                    except json.JSONDecodeError:
                        continue

                # Flush remaining text
                if text_buffer:
                    yield StreamEvent(StreamEventType.TEXT, text_buffer)

                # Execute tool calls if any
                if finish_reason == "tool_calls" and tool_calls:
                    # Build assistant message
                    assistant_tool_calls = []
                    for idx in sorted(tool_calls.keys()):
                        tc = tool_calls[idx]
                        assistant_tool_calls.append({
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": tc["arguments"]
                            }
                        })

                    messages.append({
                        "role": "assistant",
                        "tool_calls": assistant_tool_calls
                    })

                    # Execute tools and add results
                    for idx in sorted(tool_calls.keys()):
                        tc = tool_calls[idx]
                        try:
                            args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                        except json.JSONDecodeError:
                            args = {}

                        # Yield tool call event
                        yield StreamEvent(
                            StreamEventType.TOOL_CALL,
                            args,
                            tool_id=tc["id"],
                            tool_name=tc["name"]
                        )

                        # Execute
                        result = await executor.execute(tc["name"], args)

                        # Yield result
                        yield StreamEvent(
                            StreamEventType.TOOL_RESULT,
                            result,
                            tool_id=tc["id"]
                        )

                        # Add to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": json.dumps(result)
                        })

                    # Reset and continue
                    tool_calls = {}
                    continue
                else:
                    # No more tool calls, we're done - emit summary
                    summary = executor.get_summary()
                    yield StreamEvent(StreamEventType.DONE, {
                        "status": "complete",
                        "summary": summary,
                    })
                    return
