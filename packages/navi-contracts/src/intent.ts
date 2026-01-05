/**
 * Intent classification contracts
 * Defines the standardized intent types and validation logic
 */

/**
 * Broad category of what NAVI is doing
 */
export enum IntentFamily {
  ENGINEERING = "engineering",
  PROJECT_MANAGEMENT = "project_management", 
  AUTONOMOUS_ORCHESTRATION = "autonomous_orchestration"
}

/**
 * Fine-grained intent type.
 * 
 * These are the core verbs of the NAVI platform and should be stable.
 * Single source of truth for all intent classification.
 */
export enum IntentKind {
  // --- Repository discovery / understanding --------------------------------
  INSPECT_REPO = "inspect_repo",  // high-level overview of repo
  SUMMARIZE_FILE = "summarize_file",  // explain one file
  SUMMARIZE_DIFF = "summarize_diff",  // explain a patch or diff
  SEARCH_CODE = "search_code",  // semantic or text search

  // --- Code authoring / refactoring ----------------------------------------
  MODIFY_CODE = "modify_code",  // edit existing code
  CREATE_FILE = "create_file",  // add new source/test/config
  REFACTOR_CODE = "refactor_code",  // structural improvements
  IMPLEMENT_FEATURE = "implement_feature",  // end-to-end change
  FIX_BUG = "fix_bug",  // debug + patch
  FIX_DIAGNOSTICS = "fix_diagnostics",  // Fix Problems tab errors
  UPDATE_DEPENDENCIES = "update_dependencies",
  EDIT_INFRA = "edit_infra",  // Dockerfile, CI, infra-as-code

  // --- Testing / verification ----------------------------------------------
  RUN_TESTS = "run_tests",
  GENERATE_TESTS = "generate_tests",
  RUN_LINT = "run_lint",
  RUN_BUILD = "run_build",
  RUN_CUSTOM_COMMAND = "run_custom_command",

  // --- Project management / collaboration ----------------------------------
  CREATE_TICKET = "create_ticket",  // Jira / GitHub issue, etc.
  UPDATE_TICKET = "update_ticket",
  SUMMARIZE_TICKETS = "summarize_tickets",

  // Cross-app general intents (provider-agnostic)
  LIST_MY_ITEMS = "list_my_items",  // general: Jira issues, GitHub issues, tasks
  SUMMARIZE_CHANNEL = "summarize_channel",  // general: Slack, Teams, Discord channels
  SHOW_ITEM_DETAILS = "show_item_details",  // general: show details of any item (issue, PR, doc)

  // Provider-specific intents (for backward compatibility)
  JIRA_LIST_MY_ISSUES = "jira_list_my_issues",  // list Jira issues assigned to user
  SLACK_SUMMARIZE_CHANNEL = "slack_summarize_channel",  // summarize Slack channel messages
  SUMMARIZE_PR = "summarize_pr",
  REVIEW_PR = "review_pr",
  GENERATE_RELEASE_NOTES = "generate_release_notes",

  // --- Knowledge & explanation ---------------------------------------------
  EXPLAIN_CODE = "explain_code",
  EXPLAIN_ERROR = "explain_error",
  ARCHITECTURE_OVERVIEW = "architecture_overview",
  DESIGN_PROPOSAL = "design_proposal",
  GREET = "greet",  // simple greeting/hello

  // --- Autonomous orchestration --------------------------------------------
  AUTONOMOUS_SESSION = "autonomous_session",  // multi-step agent run
  BACKGROUND_WORKFLOW = "background_workflow",
  SCHEDULED_TASK = "scheduled_task",
  CONTINUE_SESSION = "continue_session",  // resume previous run
  CANCEL_WORKFLOW = "cancel_workflow",

  // --- Fallback / meta -----------------------------------------------------
  UNKNOWN = "unknown",  // classifier unsure

  // --- Additional core kinds to fix planner errors -----
  CREATE = "create",  // generic create operation
  IMPLEMENT = "implement",  // generic implementation
  FIX = "fix",  // generic fix operation
  SEARCH = "search",  // generic search
  EXPLAIN = "explain",  // generic explanation
  DEPLOY = "deploy",  // deployment operations
  SYNC = "sync",  // synchronization operations
  CONFIGURE = "configure",  // configuration operations
  GENERIC = "generic"  // fallback generic
}

/**
 * Intent classification request
 */
export interface IntentRequest {
  message: string;
  context?: {
    activeFile?: string;
    diagnosticsCount?: number;
    hasGitChanges?: boolean;
  };
}

/**
 * Intent classification response
 */
export interface IntentResponse {
  kind: IntentKind;
  confidence: number;
  reasoning?: string;
  fallbackApplied?: boolean;
}

/**
 * Fallback handler for unknown or ambiguous intents
 */
export function getFallbackIntent(message?: string): IntentResponse {
  // Simple heuristics for fallback - never let "hi" break anything
  if (!message) {
    return {
      kind: IntentKind.GREET,
      confidence: 0.8,
      reasoning: 'No message provided, defaulting to greeting',
      fallbackApplied: true
    };
  }
  
  const lowerMessage = message.toLowerCase().trim();
  
  if (lowerMessage.includes('fix') || lowerMessage.includes('error') || lowerMessage.includes('problem')) {
    return {
      kind: IntentKind.FIX_DIAGNOSTICS,
      confidence: 0.6,
      reasoning: 'Detected problem-solving keywords in fallback analysis',
      fallbackApplied: true
    };
  }
  
  if (lowerMessage.includes('deploy') || lowerMessage.includes('build')) {
    return {
      kind: IntentKind.DEPLOY,
      confidence: 0.6,
      reasoning: 'Detected deployment keywords in fallback analysis',
      fallbackApplied: true
    };
  }
  
  if (lowerMessage.includes('analyze') || lowerMessage.includes('explain') || lowerMessage.includes('what')) {
    return {
      kind: IntentKind.EXPLAIN_CODE,
      confidence: 0.6,
      reasoning: 'Detected analysis keywords in fallback analysis',
      fallbackApplied: true
    };
  }

  if (lowerMessage.includes('hello') || lowerMessage.includes('hi') || lowerMessage.includes('hey')) {
    return {
      kind: IntentKind.GREET,
      confidence: 0.8,
      reasoning: 'Detected greeting keywords',
      fallbackApplied: true
    };
  }
  
  // Default fallback to generic - never breaks
  return {
    kind: IntentKind.GENERIC,
    confidence: 0.5,
    reasoning: 'Default fallback to generic intent',
    fallbackApplied: true
  };
}

/**
 * Validates that an intent kind is supported
 */
export function isValidIntentKind(kind: string): kind is IntentKind {
  return Object.values(IntentKind).includes(kind as IntentKind);
}

/**
 * Safe intent kind parser with fallback
 */
export function parseIntentKind(kind: unknown): IntentKind {
  if (typeof kind === 'string' && isValidIntentKind(kind)) {
    return kind;
  }
  return IntentKind.GENERIC; // Safe fallback
}