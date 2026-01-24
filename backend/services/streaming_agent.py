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
import re
import uuid
from typing import AsyncGenerator, Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


# Give-up detection patterns - LLM responses that indicate premature termination
GIVE_UP_PATTERNS = [
    r"I was unable to",
    r"I couldn'?t",
    r"I encountered several issues",
    r"Here'?s a summary",
    r"manual intervention",
    r"you can try",
    r"you might want to",
    r"I suggest",
    r"please check",
    r"you may need to",
    r"unfortunately",
    r"I'?m unable to",
    r"could not complete",
    r"failed to complete",
    # Patterns for giving manual instructions instead of executing
    r"try running",
    r"you should run",
    r"run the following",
    r"you need to run",
    r"execute the following",
    r"you can run",
    r"you'll need to",
    r"you would need to",
    r"here's how",
    r"here is how",
    r"steps to follow",
    r"follow these steps",
    r"Then,.*:",  # "Then, start the development server:" pattern
]


def is_giving_up(text: str, max_retries: int = 3, retry_count: int = 0) -> bool:
    """
    Detect if the LLM is giving up instead of persisting.
    Returns True if give-up patterns are detected and we haven't exceeded max retries.
    """
    if retry_count >= max_retries:
        return False  # Don't force retry indefinitely

    text_lower = text.lower()
    for pattern in GIVE_UP_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            logger.info(f"[StreamingAgent] Give-up pattern detected: {pattern}")
            return True
    return False


FORCE_CONTINUE_MESSAGE = """DO NOT GIVE UP. You have more tool calls available.

You said you would try 5-10 DIFFERENT alternatives before stopping. Try a COMPLETELY DIFFERENT approach now.

What else can you try? Use a different tool, different command, different strategy.
DO NOT output a summary or suggest manual steps. TAKE ACTION with your tools."""


# ========== EXECUTION PLAN DETECTION ==========
# Regex patterns to detect when LLM outputs a numbered execution plan
# This enables the visual step-by-step progress UI in the frontend

# Matches phrases that introduce a plan followed by numbered steps
PLAN_INTRO_PATTERN = re.compile(
    r"(?:let'?s|I'?ll|I will|here'?s|proceed|steps?|following steps)[^:]*:\s*\n?"
    r"((?:\s*\d+[\.\)]\s*\*{0,2}[^\n]+\n?)+)",
    re.IGNORECASE | re.MULTILINE
)

# Extracts individual steps: number, title, and optional detail after colon
STEP_PATTERN = re.compile(
    r"(\d+)[\.\)]\s*\*{0,2}([^:\*\n]+?)\*{0,2}(?:[:\s]+([^\n]*))?$",
    re.MULTILINE
)


def parse_execution_plan(text: str) -> Optional[Dict[str, Any]]:
    """
    Parse an execution plan from LLM text output.
    Returns plan dict with steps if found, None otherwise.
    """
    match = PLAN_INTRO_PATTERN.search(text)
    if not match:
        return None

    steps_text = match.group(1)
    steps = []

    for step_match in STEP_PATTERN.finditer(steps_text):
        step_num = int(step_match.group(1))
        title = step_match.group(2).strip()
        detail = (step_match.group(3) or "").strip()

        if title:  # Only add if we have a title
            steps.append({
                "index": step_num,
                "title": title,
                "detail": detail
            })

    if len(steps) >= 2:  # Only return if we have at least 2 steps
        return {
            "plan_id": f"plan-{uuid.uuid4().hex[:8]}",
            "steps": steps
        }

    return None


class StreamEventType(Enum):
    """Types of events in the streaming response."""
    TEXT = "text"           # Narrative text from LLM
    THINKING = "thinking"   # Extended thinking/reasoning from LLM
    TOOL_CALL = "tool_call" # LLM wants to call a tool
    TOOL_RESULT = "tool_result"  # Result of tool execution
    DONE = "done"           # Stream complete
    # Execution Plan Events - for visual step-by-step progress UI
    PLAN_START = "plan_start"       # Detected execution plan with steps
    STEP_UPDATE = "step_update"     # Step status changed (running/completed/error)
    PLAN_COMPLETE = "plan_complete" # All steps completed


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
        elif self.type == StreamEventType.THINKING:
            result["thinking"] = self.content
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
        # Execution Plan Events
        elif self.type == StreamEventType.PLAN_START:
            result["data"] = self.content  # {plan_id, steps: [{index, title, detail}]}
        elif self.type == StreamEventType.STEP_UPDATE:
            result["data"] = self.content  # {plan_id, step_index, status}
        elif self.type == StreamEventType.PLAN_COMPLETE:
            result["data"] = self.content  # {plan_id}
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
    },
    {
        "name": "start_server",
        "description": "Start a dev server or long-running process in background. Returns immediately after starting, then verifies the server is responding. Use this instead of run_command for 'npm run dev', 'python app.py', etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to start the server (e.g., 'npm run dev', 'python app.py')"
                },
                "port": {
                    "type": "integer",
                    "description": "The port the server will listen on (for verification)"
                },
                "health_path": {
                    "type": "string",
                    "description": "Optional: path to check for health (default: '/')"
                },
                "startup_time": {
                    "type": "integer",
                    "description": "Optional: seconds to wait for server to start (default: 10)"
                }
            },
            "required": ["command", "port"]
        }
    },
    {
        "name": "check_endpoint",
        "description": "Check if an HTTP endpoint is responding. Use to verify servers, APIs, or services are running.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to check (e.g., 'http://localhost:3000')"
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "HEAD"],
                    "description": "HTTP method (default: GET)"
                },
                "expected_status": {
                    "type": "integer",
                    "description": "Expected HTTP status code (default: 200)"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "stop_server",
        "description": "Stop a running server by killing processes on a specific port.",
        "input_schema": {
            "type": "object",
            "properties": {
                "port": {
                    "type": "integer",
                    "description": "The port the server is running on"
                }
            },
            "required": ["port"]
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
- "start server", "run dev", "start the project" → Use `start_server` (NOT run_command!)
- "install", "add package", "run tests", "build" → Use `run_command` with npm/pip/etc
- "create", "make", "generate" → Use `write_file`
- "fix", "update", "change" → Use `edit_file` or `write_file`
- "delete", "remove" → Use appropriate tool
- "check if running", "verify server" → Use `check_endpoint`
- "stop server", "kill server" → Use `stop_server`

### CRITICAL: Use start_server for Dev Servers
**NEVER use `run_command` for starting dev servers.** They run forever and will timeout!

✅ CORRECT: `start_server` with command="npm run dev", port=3000
❌ WRONG: `run_command` with command="npm run dev" (will timeout after 2 min!)

The `start_server` tool:
1. Kills any existing process on the port
2. Removes lock files (e.g., .next/dev/lock)
3. Starts the server in background
4. Automatically verifies the server is responding
5. Returns success only if the server is actually running and responding

## PERSISTENCE - CRITICAL RULES (NEVER VIOLATE)

When a task fails, you MUST try alternative approaches. You have 10+ tool calls available - USE THEM ALL.

### NEVER DO:
- Output a summary of what went wrong (that's giving up)
- List manual steps for the user to try
- Say "I was unable to...", "I couldn't...", "I encountered several issues..."
- Say "you can try...", "you might want to...", "I suggest..."
- Say "manual intervention needed" or "please check..."
- Stop before the task is ACTUALLY COMPLETE (server running, tests passing, etc.)
- Give up after one failure or even multiple failures

### ALWAYS DO:
- Try at least 5-10 DIFFERENT approaches before considering stopping
- Each attempt must be GENUINELY DIFFERENT from previous attempts
- Track what you've tried and explicitly avoid repeating it
- Analyze errors and adapt your strategy based on what you learn
- Keep going until you succeed or have truly exhausted all options

## CRITICAL: Shell State Does NOT Persist Between Commands

**IMPORTANT**: Each `run_command` starts a NEW shell. Environment variables, nvm sessions, virtualenvs do NOT persist.

### WRONG (environment is lost):
```
run_command: source ~/.nvm/nvm.sh && nvm use 18   # Sets up nvm
run_command: npm install                          # FAILS - nvm not sourced, npm not found!
run_command: npm run dev                          # FAILS - same reason
```

### CORRECT (include setup in EVERY command):
```
run_command: export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" && nvm use 18 && npm install
run_command: export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" && nvm use 18 && npm run dev
```

### Key Rules:
1. **Include nvm/pyenv/etc sourcing in EVERY command that needs it**
2. **Once you find a working Node version, STICK WITH IT** - don't keep switching versions
3. **Chain all related commands together**: `source nvm && nvm use 18 && npm install && npm run dev`
4. If a specific version isn't installed, install it ONCE then use it: `nvm install 18 && nvm use 18 && npm run dev`

## Specific Fallback Strategies

### For Node.js/npm Setup Failures:
If nvm fails or node isn't found, try these IN ORDER (don't skip any):
1. Check if node already exists: `which node && node --version && npm --version`
2. Try full nvm with default: `export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" && nvm use default && npm install && npm run dev`
3. Try nvm with Node 18 (LTS): `export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" && nvm install 18 && nvm use 18 && npm install && npm run dev`
4. Try nvm with Node 20 (LTS): `export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" && nvm install 20 && nvm use 20 && npm install && npm run dev`
5. Try homebrew node: `/opt/homebrew/bin/npm install && /opt/homebrew/bin/npm run dev`
6. Try /usr/local node: `/usr/local/bin/npm install && /usr/local/bin/npm run dev`
7. Install via brew: `brew install node && npm install && npm run dev`
8. Try volta: `volta install node && npm install && npm run dev`
9. Try fnm: `eval "$(fnm env)" && fnm use && npm install && npm run dev`

**IMPORTANT**: Once ONE of these works, use that SAME approach for all subsequent commands. Don't keep switching!

### For Port-in-Use Errors:
The `start_server` tool automatically handles this! It kills existing processes on the port before starting.
If you still need manual control:
1. Use `stop_server` tool with the port number
2. Or try different port: `start_server` with command="PORT=3001 npm run dev", port=3001
3. Check what's using it: `run_command` with `lsof -i :<port>`

### For Dependency Errors:
1. Install first: `npm install && npm run dev`
2. Clear and reinstall: `rm -rf node_modules && npm install && npm run dev`
3. Clear cache: `npm cache clean --force && rm -rf node_modules package-lock.json && npm install`
4. Try yarn: `yarn install && yarn dev`
5. Try pnpm: `pnpm install && pnpm dev`

### For Python/pip Setup Failures:
1. Check python: `which python3 && python3 --version`
2. Create venv: `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
3. Try pip3: `pip3 install -r requirements.txt`
4. Use poetry: `poetry install && poetry run python ...`

## Environment & Project Setup Tasks

For tasks like "start the project", "restart", "run dev server":
1. First check package.json for available scripts
2. Try the most common approach first
3. When it fails, TRY THE NEXT ALTERNATIVE - do NOT repeat the same command
4. KEEP TRYING different approaches until the server is actually running
5. Verify success by checking output or hitting the endpoint

## Important Guidelines

- **ACTION WITH NARRATIVE**: When user wants something done, DO IT with tools AND explain what you're doing
- **BEFORE each tool**: Brief explanation of intent (e.g., "Let me check...", "I'll create...", "Since that failed, let me try a different approach...")
- **AFTER each tool result**: Explain what happened and what it means
- If a command fails, analyze stderr, explain the error, and TRY A DIFFERENT APPROACH immediately
- Only skip narrative for pure information requests ("what is...", "explain...")
- Complete tasks end-to-end without asking permission
- **NEVER mark a task complete until it's ACTUALLY done** - Running commands is not "complete", the actual result must be achieved

Example of WRONG behavior:
User: "start the project"
❌ "I tried npm run dev but it failed. I encountered several issues with nvm. You can try: 1) Check nvm installation..."
❌ Using `run_command` for `npm run dev` (will timeout!)

Example of CORRECT behavior:
User: "start the project"
✅ "Let me start the development server. [start_server: command='npm run dev', port=3000] ... Server verified and responding at http://localhost:3000!"

If start_server fails:
✅ "Server didn't start. Let me check the logs... [The log shows missing dependencies]. Installing dependencies first... [run_command: npm install] Done. Now starting server... [start_server: command='npm run dev', port=3000] ... Server verified and responding!"

## VERIFICATION BEFORE COMPLETION (CRITICAL)

**ALWAYS verify your work BEFORE claiming success or asking the user to verify.**

### Rules:
1. **Server tasks**: Use `start_server` tool - it automatically verifies the server responds!
   - ✅ CORRECT: `start_server` with port=3000 - it verifies automatically
   - ✅ ALSO OK: After starting, use `check_endpoint` to verify: `check_endpoint` url="http://localhost:3000"
   - ❌ WRONG: Start server, assume it worked, ask user to "check if it's working"

2. **File changes**: ALWAYS re-read modified files or run tests to verify changes worked
   - ✅ CORRECT: Edit file, run `npm run build` or `npm test` to verify, report result
   - ❌ WRONG: Edit file, ask user to "try building and let me know if it works"

3. **NEVER ask user to verify what you can verify yourself**:
   - ❌ "Please check if the server is running"
   - ❌ "Let me know if this fixed the issue"
   - ❌ "Try building and see if it works"
   - ✅ "Let me verify with check_endpoint... Confirmed working!"
   - ✅ "Server started but check_endpoint failed. Let me investigate..."

### Verification Tools:
- `start_server`: Starts AND verifies server is responding (use for dev servers)
- `check_endpoint`: Check if any URL is responding (use to verify APIs, services)
- `run_command`: For tests/builds, check exit code and output for errors

### NEVER make false claims about continuing work:
**Your response ENDS when you stop responding. You do NOT continue working in the background.**

NEVER say:
- ❌ "I will continue attempting to resolve this..."
- ❌ "In the meantime, I will keep working on..."
- ❌ "I'll continue investigating..."
- ❌ "Let me know and I'll continue..."

These are LIES because you stop working when the response ends. Instead:
- ✅ Be honest: "I was unable to resolve this. The issue appears to be X. Would you like me to try Y approach?"
- ✅ Summarize what you tried and what failed
- ✅ Suggest specific next steps the USER can take if you truly cannot solve it

## DEPLOYMENT CAPABILITIES

You can deploy projects to ANY cloud platform using their official CLIs.

### Deployment Workflow
1. **Detect Project Type**: Read package.json/requirements.txt/Dockerfile to determine type
2. **Check CLI**: Verify if platform CLI is installed (`which vercel`)
3. **Install CLI if needed**: Run the install command
4. **Login**: Run login command - tell user "Please complete authentication in your browser. I'll wait..."
5. **Deploy**: Run deploy command (may take 5-30 minutes)
6. **Verify**: Check deployment status and report URL

### Platform CLI Reference

| Platform | Install | Login | Deploy | Verify |
|----------|---------|-------|--------|--------|
| Vercel | `npm i -g vercel` | `vercel login` | `vercel --prod` | `vercel ls` |
| Railway | `npm i -g @railway/cli` | `railway login` | `railway up` | `railway status` |
| Fly.io | `curl -L https://fly.io/install.sh \| sh` | `fly auth login` | `fly deploy` | `fly status` |
| Netlify | `npm i -g netlify-cli` | `netlify login` | `netlify deploy --prod` | `netlify status` |
| Render | `pip install render-cli` | `render login` | `render deploy` | `render services` |
| Heroku | `curl https://cli-assets.heroku.com/install.sh \| sh` | `heroku login` | `git push heroku main` | `heroku ps` |
| Cloudflare | `npm i -g wrangler` | `wrangler login` | `wrangler publish` | `wrangler whoami` |
| AWS | Download from aws.amazon.com/cli | `aws configure` | `sam deploy` / `cdk deploy` | `aws sts get-caller-identity` |
| GCP | `curl https://sdk.cloud.google.com \| bash` | `gcloud auth login` | `gcloud run deploy` | `gcloud auth list` |
| Azure | `curl -sL https://aka.ms/InstallAzureCLIDeb \| sudo bash` | `az login` | `az webapp up` | `az account show` |

### Project Type → Platform Recommendations
- **Next.js/React**: Vercel (optimal), Netlify, Railway
- **Python/FastAPI/Django**: Railway, Render, Fly.io, Heroku
- **Node.js API**: Railway, Render, Fly.io, Heroku
- **Static Site**: Netlify, Vercel, Cloudflare Pages
- **Docker/Container**: Fly.io, Railway, Render, AWS ECS
- **Full-Stack with DB**: Railway (includes Postgres), Render, Fly.io

### Authentication Flow
When a CLI requires OAuth login:
1. Run the login command (e.g., `vercel login`)
2. Tell user: "Please complete authentication in your browser. The CLI will open a browser window."
3. The command will complete automatically once browser auth finishes
4. Verify authentication worked with a status command

### Deployment Commands are Long-Running
- Deployments can take 5-30 minutes - this is normal
- After starting deployment, report progress
- Poll status periodically if needed
- Report final deployment URL when complete

### Example Deployment Workflow
User: "Deploy this to Vercel"
✅ "Let me deploy to Vercel. First, checking if CLI is installed... [run_command: which vercel] Found at /usr/local/bin/vercel. Checking auth... [run_command: vercel whoami] Authenticated as user@example.com. Deploying to production... [run_command: vercel --prod] Deployment complete! Your app is live at: https://my-app.vercel.app"

Remember: You are an AUTONOMOUS agent that COMMUNICATES clearly AND PERSISTS until success. Use tools to take action, explain what you're doing, and NEVER give up until the task is truly complete."""


class StreamingToolExecutor:
    """Executes tools and returns results. Tracks files accessed for summary."""

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        # Track files for task summary
        self.files_read: set = set()
        self.files_modified: set = set()
        self.files_created: set = set()
        self.commands_run: list = []
        self.failed_commands: list = []  # Track failed commands to prevent repetition

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
            "failed_commands": len(self.failed_commands),
        }

    def get_failed_commands_context(self) -> str:
        """Get context about failed commands to inject into LLM messages."""
        if not self.failed_commands:
            return ""

        context = "\n\n**FAILED COMMANDS (DO NOT REPEAT THESE):**\n"
        for fc in self.failed_commands[-5:]:  # Last 5 failures
            cmd = fc.get("command", "Unknown")[:80]
            error = fc.get("error", "Unknown error")[:100]
            context += f"- `{cmd}`: {error}\n"
        context += "\nTry a COMPLETELY DIFFERENT approach.\n"
        return context

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

                command = arguments["command"]

                # Extended timeout for deployment commands (30 minutes)
                deployment_indicators = [
                    "vercel", "railway", "fly deploy", "fly launch",
                    "netlify deploy", "render deploy", "heroku",
                    "gcloud run deploy", "gcloud app deploy",
                    "aws deploy", "sam deploy", "cdk deploy",
                    "az webapp", "docker push", "docker build",
                    "wrangler publish", "wrangler deploy"
                ]
                is_deployment = any(ind in command.lower() for ind in deployment_indicators)
                timeout = 1800 if is_deployment else 120  # 30 min for deployments, 2 min default

                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )

                # Track command run
                self.commands_run.append(arguments["command"])

                # Track failed commands for context injection
                if result.returncode != 0:
                    error_msg = result.stderr[:200] if result.stderr else result.stdout[:200] if result.stdout else "Command failed"
                    self.failed_commands.append({
                        "command": arguments["command"],
                        "error": error_msg,
                        "exit_code": result.returncode
                    })

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

            elif tool_name == "start_server":
                import time
                import urllib.request
                import urllib.error

                command = arguments["command"]
                port = arguments["port"]
                health_path = arguments.get("health_path", "/")
                startup_time = arguments.get("startup_time", 10)

                # First, kill any existing process on the port
                try:
                    subprocess.run(
                        f"lsof -ti :{port} | xargs kill -9 2>/dev/null || true",
                        shell=True,
                        capture_output=True,
                        timeout=10
                    )
                except Exception:
                    pass

                # Also remove any lock files for Next.js
                try:
                    lock_path = os.path.join(self.workspace_path, ".next", "dev", "lock")
                    if os.path.exists(lock_path):
                        os.remove(lock_path)
                except Exception:
                    pass

                # Start the server in background using nohup
                # Redirect output to a log file so we can check it
                log_file = os.path.join(self.workspace_path, ".navi-server.log")
                bg_command = f"cd {self.workspace_path} && nohup {command} > {log_file} 2>&1 &"

                try:
                    subprocess.run(bg_command, shell=True, timeout=5)
                except subprocess.TimeoutExpired:
                    pass  # Expected - we're running in background

                # Wait for server to start, checking periodically
                url = f"http://localhost:{port}{health_path}"
                server_started = False
                last_error = ""

                for i in range(startup_time * 2):  # Check every 0.5 seconds
                    time.sleep(0.5)
                    try:
                        req = urllib.request.Request(url, method='HEAD')
                        with urllib.request.urlopen(req, timeout=2) as response:
                            if response.status < 500:
                                server_started = True
                                break
                    except urllib.error.HTTPError as e:
                        # Even a 404 means server is running
                        if e.code < 500:
                            server_started = True
                            break
                        last_error = f"HTTP {e.code}"
                    except urllib.error.URLError as e:
                        last_error = str(e.reason)
                    except Exception as e:
                        last_error = str(e)

                # Get any log output
                log_content = ""
                try:
                    with open(log_file, 'r') as f:
                        log_content = f.read()[-1000:]  # Last 1000 chars
                except Exception:
                    pass

                if server_started:
                    return {
                        "success": True,
                        "message": f"Server started successfully on port {port}",
                        "url": url,
                        "verified": True,
                        "log_preview": log_content[:500] if log_content else None
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Server did not respond after {startup_time} seconds",
                        "last_error": last_error,
                        "url": url,
                        "log_preview": log_content if log_content else "No log output captured",
                        "suggestion": "Check the log output for errors. Common issues: port already in use, missing dependencies, build errors."
                    }

            elif tool_name == "check_endpoint":
                import urllib.request
                import urllib.error

                url = arguments["url"]
                method = arguments.get("method", "GET")
                expected_status = arguments.get("expected_status", 200)

                try:
                    req = urllib.request.Request(url, method=method)
                    with urllib.request.urlopen(req, timeout=10) as response:
                        body_preview = response.read(500).decode('utf-8', errors='ignore')
                        return {
                            "success": response.status == expected_status,
                            "status": response.status,
                            "responding": True,
                            "body_preview": body_preview,
                            "headers": dict(response.headers)
                        }
                except urllib.error.HTTPError as e:
                    return {
                        "success": e.code == expected_status,
                        "status": e.code,
                        "responding": True,
                        "error": f"HTTP {e.code}: {e.reason}"
                    }
                except urllib.error.URLError as e:
                    return {
                        "success": False,
                        "responding": False,
                        "error": f"Connection failed: {e.reason}"
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "responding": False,
                        "error": str(e)
                    }

            elif tool_name == "stop_server":
                port = arguments["port"]

                try:
                    # Find and kill processes on the port
                    result = subprocess.run(
                        f"lsof -ti :{port} | xargs kill -9 2>/dev/null",
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )

                    # Verify the port is free
                    check = subprocess.run(
                        f"lsof -ti :{port}",
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )

                    port_is_free = not check.stdout.strip()

                    return {
                        "success": port_is_free,
                        "message": f"Port {port} is now free" if port_is_free else f"Processes still running on port {port}",
                        "port": port
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": str(e)
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
            context_parts.append("\n=== SOURCE FILE CONTENTS (for detailed analysis) ===")
            context_parts.append(context["source_files_preview"])

        if context_parts:
            user_content = "\n".join(context_parts) + "\n\n=== USER REQUEST ===\n" + message

    messages.append({"role": "user", "content": user_content})

    # Track give-up retry count to prevent infinite loops
    give_up_retry_count = 0
    max_give_up_retries = 3
    accumulated_text = ""  # Track full response text for give-up detection

    # Execution plan tracking for visual step-by-step UI
    current_plan: Optional[Dict[str, Any]] = None
    plan_emitted = False
    current_step_index = 0

    async with aiohttp.ClientSession() as session:
        while True:  # Loop for tool use continuation
            # Enable extended thinking for supported models (Claude 3.5 Sonnet, Claude 3 Opus)
            # Extended thinking requires higher max_tokens (budget_tokens + response tokens)
            use_extended_thinking = "claude-3" in model.lower() and ("sonnet" in model.lower() or "opus" in model.lower())

            payload = {
                "model": model,
                "max_tokens": 16000 if use_extended_thinking else 4096,
                "system": STREAMING_SYSTEM_PROMPT,
                "messages": messages,
                "tools": NAVI_TOOLS,
                "stream": True,
            }

            # Add extended thinking configuration if supported
            if use_extended_thinking:
                payload["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": 10000
                }

            headers = {
                "x-api-key": api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
                "anthropic-beta": "interleaved-thinking-2025-05-14",
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
                thinking_buffer = ""  # Buffer for extended thinking content
                tool_calls = []
                current_tool_input = ""
                current_tool_id = None
                current_tool_name = None
                in_tool_input = False
                in_thinking_block = False  # Track if we're in a thinking block
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
                            block_type = block.get("type")

                            if block_type == "thinking":
                                # Starting a thinking block
                                in_thinking_block = True
                                # Flush any pending text before thinking
                                if text_buffer:
                                    yield StreamEvent(StreamEventType.TEXT, text_buffer)
                                    text_buffer = ""

                            elif block_type == "tool_use":
                                # Starting a tool call
                                current_tool_id = block.get("id")
                                current_tool_name = block.get("name")
                                current_tool_input = ""
                                in_tool_input = True
                                in_thinking_block = False

                                # Flush any pending text and thinking
                                if text_buffer:
                                    yield StreamEvent(StreamEventType.TEXT, text_buffer)
                                    text_buffer = ""
                                if thinking_buffer:
                                    yield StreamEvent(StreamEventType.THINKING, thinking_buffer)
                                    thinking_buffer = ""

                            elif block_type == "text":
                                # Starting a text block - flush thinking if pending
                                in_thinking_block = False
                                if thinking_buffer:
                                    yield StreamEvent(StreamEventType.THINKING, thinking_buffer)
                                    thinking_buffer = ""

                        elif event_type == "content_block_delta":
                            delta = data.get("delta", {})
                            delta_type = delta.get("type")

                            if delta_type == "thinking_delta":
                                # Extended thinking content
                                thinking_text = delta.get("thinking", "")
                                if thinking_text:
                                    thinking_buffer += thinking_text
                                    # Yield thinking in chunks for smoother streaming
                                    if len(thinking_buffer) >= 100 or thinking_text.endswith((".", "!", "?", "\n")):
                                        yield StreamEvent(StreamEventType.THINKING, thinking_buffer)
                                        thinking_buffer = ""

                            elif delta_type == "text_delta":
                                text = delta.get("text", "")
                                if text:
                                    text_buffer += text
                                    accumulated_text += text  # Track for plan detection
                                    # Yield text in chunks for smoother streaming
                                    if len(text_buffer) >= 20 or text.endswith((".", "!", "?", "\n")):
                                        yield StreamEvent(StreamEventType.TEXT, text_buffer)
                                        text_buffer = ""

                                        # Check for execution plan in accumulated text (only once)
                                        if not plan_emitted and len(accumulated_text) > 50:
                                            detected_plan = parse_execution_plan(accumulated_text)
                                            if detected_plan:
                                                current_plan = detected_plan
                                                plan_emitted = True
                                                current_step_index = 0
                                                yield StreamEvent(
                                                    StreamEventType.PLAN_START,
                                                    detected_plan
                                                )
                                                logger.info(f"[StreamingAgent] Detected execution plan with {len(detected_plan['steps'])} steps")

                            elif delta_type == "input_json_delta":
                                # Building tool input
                                current_tool_input += delta.get("partial_json", "")

                        elif event_type == "content_block_stop":
                            # Flush thinking buffer when thinking block ends
                            if in_thinking_block and thinking_buffer:
                                yield StreamEvent(StreamEventType.THINKING, thinking_buffer)
                                thinking_buffer = ""
                            in_thinking_block = False

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

                                # Emit step_update for execution plan (running)
                                if current_plan and current_step_index < len(current_plan.get("steps", [])):
                                    yield StreamEvent(
                                        StreamEventType.STEP_UPDATE,
                                        {
                                            "plan_id": current_plan["plan_id"],
                                            "step_index": current_step_index,
                                            "status": "running"
                                        }
                                    )

                                # Execute the tool
                                result = await executor.execute(current_tool_name, args)

                                # Yield tool result event
                                yield StreamEvent(
                                    StreamEventType.TOOL_RESULT,
                                    result,
                                    tool_id=current_tool_id
                                )

                                # Emit step_update for execution plan (completed)
                                if current_plan and current_step_index < len(current_plan.get("steps", [])):
                                    # Determine if step succeeded or failed
                                    step_status = "completed"
                                    if isinstance(result, dict) and result.get("error"):
                                        step_status = "error"
                                    elif isinstance(result, str) and "error" in result.lower():
                                        step_status = "error"

                                    yield StreamEvent(
                                        StreamEventType.STEP_UPDATE,
                                        {
                                            "plan_id": current_plan["plan_id"],
                                            "step_index": current_step_index,
                                            "status": step_status
                                        }
                                    )
                                    current_step_index += 1

                                    # Check if plan is complete
                                    if current_step_index >= len(current_plan.get("steps", [])):
                                        yield StreamEvent(
                                            StreamEventType.PLAN_COMPLETE,
                                            {"plan_id": current_plan["plan_id"]}
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

                # Flush remaining thinking and text
                if thinking_buffer:
                    yield StreamEvent(StreamEventType.THINKING, thinking_buffer)
                if text_buffer:
                    accumulated_text += text_buffer
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

                    # Add tool results with failed commands context
                    tool_results = []
                    for tc in tool_calls:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tc["id"],
                            "content": json.dumps(tc["result"])
                        })

                    # Inject failed commands context if any
                    failed_context = executor.get_failed_commands_context()
                    if failed_context:
                        tool_results.append({
                            "type": "text",
                            "text": failed_context
                        })

                    messages.append({"role": "user", "content": tool_results})

                    # Reset for next iteration
                    tool_calls = []
                    accumulated_text = ""  # Reset for next response
                    continue
                else:
                    # No more tool calls - check if LLM is giving up prematurely
                    if is_giving_up(accumulated_text, max_give_up_retries, give_up_retry_count):
                        give_up_retry_count += 1
                        logger.info(f"[StreamingAgent] Give-up detected, forcing retry {give_up_retry_count}/{max_give_up_retries}")

                        # Add assistant's response to messages
                        messages.append({"role": "assistant", "content": accumulated_text})

                        # Add force-continue message with failed commands context
                        retry_message = FORCE_CONTINUE_MESSAGE
                        failed_context = executor.get_failed_commands_context()
                        if failed_context:
                            retry_message += failed_context

                        messages.append({"role": "user", "content": retry_message})

                        # Reset and continue the loop
                        accumulated_text = ""
                        tool_calls = []
                        continue

                    # Truly done - emit summary
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
            context_parts.append("\n=== SOURCE FILE CONTENTS (for detailed analysis) ===")
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
                has_seen_tool_call = False  # Track if we've started tool calls

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

                            # NOTE: We no longer capture OpenAI text as "thinking" because:
                            # 1. OpenAI doesn't have extended thinking like Anthropic
                            # 2. Capturing text as thinking causes duplicate display
                            # The frontend shows a "Thinking..." animation during streaming anyway

                            if len(text_buffer) >= 20 or text.endswith((".", "!", "?", "\n")):
                                yield StreamEvent(StreamEventType.TEXT, text_buffer)
                                text_buffer = ""

                        # Handle tool calls
                        if delta.get("tool_calls"):
                            # Mark that we've seen tool calls
                            if not has_seen_tool_call:
                                has_seen_tool_call = True
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
