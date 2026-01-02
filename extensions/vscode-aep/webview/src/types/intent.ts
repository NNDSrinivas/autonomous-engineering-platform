/**
 * NAVI Intent Schema for TypeScript Frontend
 * 
 * Phase 4.1.2: Intent → Plan → Tool → Verify Architecture
 * 
 * Canonical TypeScript equivalent of backend/agent/intent_schema.py
 * Supports the complete planner workflow with runtime enum access
 */

export enum IntentFamily {
  ENGINEERING = "engineering",
  PROJECT_MANAGEMENT = "project_management",
  AUTONOMOUS_ORCHESTRATION = "autonomous_orchestration"
}

/**
 * Phase 4.1.2 Canonical IntentKind
 * 
 * These are the core verbs of the NAVI platform.
 * Runtime accessible enum (not type-only) for plan generation.
 */
export enum IntentKind {
  // Repository discovery / understanding
  INSPECT_REPO = "inspect_repo",
  SUMMARIZE_FILE = "summarize_file",
  SUMMARIZE_DIFF = "summarize_diff",
  SEARCH_CODE = "search_code",

  // Code authoring / refactoring
  MODIFY_CODE = "modify_code",
  CREATE_FILE = "create_file",
  REFACTOR_CODE = "refactor_code",
  IMPLEMENT_FEATURE = "implement_feature",
  FIX_BUG = "fix_bug",
  FIX_DIAGNOSTICS = "fix_diagnostics", // Phase 4.1.2: First real workflow
  UPDATE_DEPENDENCIES = "update_dependencies",
  EDIT_INFRA = "edit_infra",

  // Testing / verification
  RUN_TESTS = "run_tests",
  GENERATE_TESTS = "generate_tests",
  RUN_LINT = "run_lint",
  RUN_BUILD = "run_build",
  RUN_CUSTOM_COMMAND = "run_custom_command",

  // Project management / collaboration
  CREATE_TICKET = "create_ticket",
  UPDATE_TICKET = "update_ticket",
  SUMMARIZE_TICKETS = "summarize_tickets",
  LIST_MY_ITEMS = "list_my_items",
  SUMMARIZE_CHANNEL = "summarize_channel",
  SHOW_ITEM_DETAILS = "show_item_details",
  JIRA_LIST_MY_ISSUES = "jira_list_my_issues",
  SLACK_SUMMARIZE_CHANNEL = "slack_summarize_channel",
  SUMMARIZE_PR = "summarize_pr",
  REVIEW_PR = "review_pr",
  GENERATE_RELEASE_NOTES = "generate_release_notes",

  // Knowledge & explanation
  EXPLAIN_CODE = "explain_code",
  EXPLAIN_ERROR = "explain_error",
  ARCHITECTURE_OVERVIEW = "architecture_overview",
  DESIGN_PROPOSAL = "design_proposal",
  GREET = "greet",

  // Autonomous orchestration
  AUTONOMOUS_SESSION = "autonomous_session",
  BACKGROUND_WORKFLOW = "background_workflow",
  SCHEDULED_TASK = "scheduled_task",
  CONTINUE_SESSION = "continue_session",
  CANCEL_WORKFLOW = "cancel_workflow",

  // Fallback / meta
  UNKNOWN = "unknown",
  CREATE = "create",
  IMPLEMENT = "implement",
  FIX = "fix",
  SEARCH = "search",
  EXPLAIN = "explain",
  DEPLOY = "deploy",
  SYNC = "sync",
  CONFIGURE = "configure",
  GENERIC = "generic"
}

export enum IntentPriority {
  LOW = "low",
  NORMAL = "normal",
  HIGH = "high",
  CRITICAL = "critical"
}

export enum IntentSource {
  CHAT = "chat",
  IDE = "ide",
  WEBHOOK = "webhook",
  API = "api"
}

export enum Provider {
  JIRA = "jira",
  SLACK = "slack",
  GITHUB = "github",
  TEAMS = "teams",
  ZOOM = "zoom",
  CONFLUENCE = "confluence",
  NOTION = "notion",
  LINEAR = "linear",
  ASANA = "asana",
  JENKINS = "jenkins",
  GENERIC = "generic"
}

export interface NaviIntent {
  id?: string;
  family: IntentFamily;
  kind: IntentKind;
  source: IntentSource;
  priority: IntentPriority;
  confidence: number;
  provider: Provider;
  raw_text: string;
  requires_approval: boolean;
  target?: string;
  parameters: Record<string, any>;
  time?: string;
  model_used?: string;
  provider_used?: string;
}

/**
 * Phase 4.1.4: Agent Response Contract
 * 
 * Structured response format that enables:
 * - Explainability
 * - Confidence scoring
 * - Human-in-the-loop gating
 */
export interface AgentResponse {
  intent: NaviIntent;
  reasoning?: string;
  plan?: string[];
  proposedActions?: AgentAction[];
  requiresApproval: boolean;
  message: string;
}

export interface AgentAction {
  id: string;
  description: string;
  tool: string;
  arguments: Record<string, any>;
  requiresApproval: boolean;
}

/**
 * Phase 4.1.2: Action Proposal Types
 */
export interface ActionProposal {
  id: string;
  title: string;
  description: string;
  actions: AgentAction[];
  estimatedRisk: 'low' | 'medium' | 'high';
  requiresUserApproval: boolean;
}

/**
 * Intent Classification Request/Response Types
 */
export interface IntentClassificationRequest {
  message: string;
  context?: {
    workspaceRoot?: string;
    currentFile?: string;
    selectedText?: string;
    metadata?: Record<string, any>;
  };
}

export interface IntentClassificationResponse {
  intent: NaviIntent;
  proposal?: ActionProposal;
  error?: string;
}