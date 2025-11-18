"""
Intent Schema for NAVI Agent

Defines all possible user intent categories that NAVI can recognize.
These are UNIVERSAL across all engineering tasks and behaviors.

This is the foundation of NAVI's decision-making brain.
"""

# ==============================================================================
# INTENT TYPE DEFINITIONS
# ==============================================================================

INTENT_TYPES = {
    "jira_query",           # User wants to explore/understand a Jira ticket
    "jira_execution",       # User wants to implement/work on a Jira ticket
    "code_explain",         # User wants to understand code
    "code_modify",          # User wants to refactor/fix/optimize code
    "code_generate",        # User wants to generate new code
    "repo_navigation",      # User wants to navigate/search workspace
    "debugging",            # User wants to debug/fix errors
    "planning",             # User wants architecture/design/steps
    "documentation",        # User wants to find/read docs
    "meeting_summary",      # User wants to understand past discussions
    "task_continue",        # User confirms/continues previous action
    "workflow_start",       # User initiates multi-step workflow
    "personal",             # Conversational/personal questions
    "ambiguous"             # Intent unclear, needs clarification
}

# ==============================================================================
# INTENT DESCRIPTIONS (For LLM Prompt)
# ==============================================================================

INTENT_DESCRIPTIONS = {
    "jira_query": {
        "description": "User wants to explore, understand, or get info about a Jira ticket",
        "examples": [
            "open Jira ticket",
            "tell me more about SCRUM-1",
            "what's the status of ENG-54?",
            "summarize this Jira",
            "find related discussions"
        ],
        "entities": ["jira_keys"],
        "triggers_tools": False
    },
    
    "jira_execution": {
        "description": "User wants to actively work on/implement a Jira ticket",
        "examples": [
            "start working on SCRUM-1",
            "implement this Jira",
            "generate code for this task",
            "create acceptance criteria",
            "what's the next step?"
        ],
        "entities": ["jira_keys", "files"],
        "triggers_tools": True
    },
    
    "code_explain": {
        "description": "User wants to understand existing code",
        "examples": [
            "explain this file",
            "what does this function do?",
            "explain this error",
            "why is this failing?"
        ],
        "entities": ["files", "functions", "errors"],
        "triggers_tools": False
    },
    
    "code_modify": {
        "description": "User wants to refactor, fix, or optimize existing code",
        "examples": [
            "refactor this",
            "fix this bug",
            "optimize this",
            "migrate this to TypeScript",
            "add logging"
        ],
        "entities": ["files", "functions", "modifications"],
        "triggers_tools": True
    },
    
    "code_generate": {
        "description": "User wants to generate new code from scratch",
        "examples": [
            "write a hello world",
            "generate a React component",
            "create an Express API",
            "write a unit test for this function"
        ],
        "entities": ["language", "framework", "component_type"],
        "triggers_tools": True
    },
    
    "repo_navigation": {
        "description": "User wants to navigate, search, or explore the workspace",
        "examples": [
            "open this file",
            "search for usages",
            "find references",
            "show me folder structure"
        ],
        "entities": ["files", "directories", "symbols"],
        "triggers_tools": True
    },
    
    "debugging": {
        "description": "User wants to debug or fix runtime errors",
        "examples": [
            "why is this error happening?",
            "explain the stack trace",
            "fix the crash"
        ],
        "entities": ["errors", "stack_traces", "files"],
        "triggers_tools": True
    },
    
    "planning": {
        "description": "User wants architectural design or implementation steps",
        "examples": [
            "how should I implement this?",
            "design a flow",
            "create an architecture diagram",
            "what are the steps?"
        ],
        "entities": ["features", "requirements"],
        "triggers_tools": False
    },
    
    "documentation": {
        "description": "User wants to retrieve documentation or wiki pages",
        "examples": [
            "find confluence page for X",
            "fetch documentation",
            "is there wiki for this?"
        ],
        "entities": ["topics", "pages"],
        "triggers_tools": True
    },
    
    "meeting_summary": {
        "description": "User wants to understand past meetings or discussions",
        "examples": [
            "what did we discuss last sprint?",
            "summarize standup",
            "what was said in the zoom meeting?"
        ],
        "entities": ["meetings", "dates", "topics"],
        "triggers_tools": True
    },
    
    "task_continue": {
        "description": "User confirms or continues previous action (affirmative responses)",
        "examples": [
            "yes",
            "sure",
            "go ahead",
            "do it",
            "continue",
            "ok",
            "please",
            "sounds good"
        ],
        "entities": [],
        "triggers_tools": True,
        "requires_state": True
    },
    
    "workflow_start": {
        "description": "User initiates a multi-step autonomous workflow",
        "examples": [
            "help me debug this",
            "help me finish this Jira",
            "let's build this feature"
        ],
        "entities": ["workflow_type", "target"],
        "triggers_tools": True
    },
    
    "personal": {
        "description": "Conversational or personal questions",
        "examples": [
            "how are you?",
            "what do you think?",
            "give me suggestions"
        ],
        "entities": [],
        "triggers_tools": False
    },
    
    "ambiguous": {
        "description": "Intent is unclear and needs clarification",
        "examples": [
            "fix it",
            "do that",
            "the thing"
        ],
        "entities": [],
        "triggers_tools": False,
        "requires_clarification": True
    }
}

# ==============================================================================
# AFFIRMATIVE PATTERNS (For quick task_continue detection)
# ==============================================================================

AFFIRMATIVE_PATTERNS = {
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay",
    "go ahead", "do it", "continue", "proceed", "please",
    "sounds good", "looks good", "perfect", "great",
    "👍", "✓", "✔", "✅"
}

# ==============================================================================
# ENTITY EXTRACTION HINTS
# ==============================================================================

ENTITY_HINTS = {
    "jira_keys": r"[A-Z]+-\d+",  # SCRUM-123, ENG-45
    "files": r"\.(py|js|ts|java|go|md|yaml|json)$",
    "functions": r"def |function |async |class ",
    "errors": r"Error:|Exception:|Traceback:",
    "urls": r"https?://[^\s]+"
}
