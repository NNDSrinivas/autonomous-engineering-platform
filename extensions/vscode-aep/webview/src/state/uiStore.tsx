import React, { createContext, useContext, useReducer, ReactNode } from "react";
import type { ActivityEvent } from "../types/activity";

// Canonical types locked for Phase 4 baseline
export type AgentStatus = "idle" | "running" | "awaiting_approval" | "error";
export type StepStatus = "pending" | "active" | "completed" | "failed";
export type ArtifactKind = "changePlan" | "diffs" | "validation" | "apply" | "pr" | "ci" | "command" | "context";

export interface Attachment {
  kind: string;
  path: string;
  language?: string;
  content: string;
}

export interface ArtifactPayload {
  kind: ArtifactKind;
  title?: string;
  data: any;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  type?: 'text' | 'thinking' | 'step' | 'command' | 'result' | 'proposal' | 'plan' | 'error' | 'conversation';
  // Phase 4.1.2: Plan data
  plan?: any;
  reasoning?: string;
  session_id?: string;
  error?: string;
  planError?: string;
  // Phase 4.2.1: Conversation data
  conversationType?: 'greeting' | 'explanation' | 'capability' | 'clarification' | 'help';
  suggestions?: string[];
  // Phase 4.3: Artifact rendering
  artifact?: ArtifactPayload;
}

export interface TodoItem {
  id: string;
  text: string;
  status: 'pending' | 'active' | 'completed' | 'failed';
}

export interface FileChangeSummary {
  path: string;
  additions: number;
  deletions: number;
  status: 'added' | 'modified' | 'deleted';
}

export interface PermissionRequest {
  id: string;
  command: string;
  description: string;
}

export interface AgentWorkflowState {
  todos: TodoItem[];
  currentStep?: string;
  filesChanged: FileChangeSummary[];
  pendingPermission?: PermissionRequest;
  isActive: boolean;
}

export interface ActivityRunState {
  events: ActivityEvent[];
  collapsedPhaseIds: Record<string, boolean>;
  status: "running" | "done";
}

export interface StreamingMetrics {
  time_to_first_token_ms?: number;
  total_duration_ms?: number;
  total_tokens?: number;
  total_chars?: number;
  tokens_per_second?: number;
  activity_events?: number;
}

export interface UIState {
  // Chat state
  messages: Message[];
  // Attachments selected in the panel
  attachments: Attachment[];
  // Thinking state for input disabling
  isThinking: boolean;
  // Workflow state (starts as null - no default workflow!)
  workflow: WorkflowState | null;
  // Agent workflow (NEW - for Copilot-style behavior)
  agentWorkflow: AgentWorkflowState;
  // Phase 4.1.2: Tool approval state
  pendingToolApproval?: {
    tool_request: any;
    session_id: string;
  };
  // Activity panel state
  activeRunId: string | null;
  activityByRunId: Record<string, ActivityRunState>;
  activityRunOrder: string[];
  // Streaming state (Cline-style real-time)
  streamingContent: string;
  streamingMetrics?: StreamingMetrics;
}

export interface WorkflowState {
  agentStatus: AgentStatus;
  steps: Record<string, StepStatus>;
  currentStep?: string;
  showActionCard: boolean;
}

// Initial UI state - ZERO DEFAULTS (no fake context, todos, or workflows)
const initialUIState: UIState = {
  messages: [],
  attachments: [],
  isThinking: false,
  workflow: null, // ⭐ CRITICAL: No workflow by default
  agentWorkflow: {
    todos: [],
    filesChanged: [],
    isActive: false
  },
  pendingToolApproval: undefined,
  activeRunId: null,
  activityByRunId: {},
  activityRunOrder: [],
  // Streaming state
  streamingContent: "",
  streamingMetrics: undefined
};

// Workflow template for when workflow is actually started
const initialWorkflowState: WorkflowState = {
  agentStatus: "idle",
  steps: {
    scan: "pending",
    plan: "pending",
    diff: "pending",
    validate: "pending",
    apply: "pending",
    pr: "pending",
    ci: "pending",
    heal: "pending",
  },
  currentStep: undefined,
  showActionCard: false,
};

export type UIAction =
  | { type: "ADD_USER_MESSAGE"; content: string }
  | { type: "ADD_ASSISTANT_MESSAGE"; content: string; messageType?: 'text' | 'thinking' | 'step' | 'command' | 'result' | 'proposal' | 'error'; error?: string }
  | { type: "SET_THINKING"; thinking: boolean }
  | { type: "CLEAR_MESSAGES" }
  | { type: "ADD_ATTACHMENT"; attachment: Attachment }
  | { type: "REMOVE_ATTACHMENT"; attachmentKey: string }
  | { type: "CLEAR_ATTACHMENTS" }
  | { type: "ADD_ARTIFACT_MESSAGE"; artifact: ArtifactPayload }
  | { type: "CLEAR_WORKFLOW" }
  | { type: "START_WORKFLOW" }
  | { type: "STEP_ACTIVE"; step: string }
  | { type: "STEP_COMPLETE"; step: string }
  | { type: "STEP_FAIL"; step: string }
  | { type: "REQUEST_APPROVAL" }
  | { type: "APPROVE" }
  | { type: "REJECT" }
  | { type: "RESET" }
  // Phase 4.1.2: Plan-based actions
  | { type: "ADD_PLAN"; plan: any; reasoning?: string; session_id?: string }
  | { type: "REQUEST_TOOL_APPROVAL"; tool_request: any; session_id: string }
  | { type: "RESOLVE_TOOL_APPROVAL" }
  // Phase 4.2.1: Conversation actions
  | { type: "ADD_CONVERSATION"; content: string; conversationType: 'greeting' | 'explanation' | 'capability' | 'clarification' | 'help'; suggestions?: string[] }
  // Agent workflow actions (NEW)
  | { type: "AGENT_START" }
  | { type: "AGENT_ADD_TODO"; todo: TodoItem }
  | { type: "AGENT_UPDATE_TODO"; id: string; status: TodoItem['status'] }
  | { type: "AGENT_ADD_FILE_CHANGE"; fileChange: FileChangeSummary }
  | { type: "AGENT_REQUEST_PERMISSION"; permission: PermissionRequest }
  | { type: "AGENT_STOP" }
  // Activity actions
  | { type: "RUN_STARTED"; runId: string }
  | { type: "RUN_FINISHED"; runId: string }
  | { type: "ACTIVITY_APPEND"; event: ActivityEvent }
  | { type: "ACTIVITY_CLEAR"; runId?: string }
  | { type: "PHASE_TOGGLE_COLLAPSE"; runId: string; phaseId: string }
  | { type: "SET_ACTIVE_RUN"; runId: string | null }
  // Streaming actions (Cline-style real-time)
  | { type: "APPEND_STREAMING_CONTENT"; content: string }
  | { type: "CLEAR_STREAMING_CONTENT" }
  | { type: "UPDATE_STREAMING_METRICS"; metrics: StreamingMetrics };

const MAX_ACTIVITY_RUNS = 10;

function reducer(state: UIState, action: UIAction): UIState {
  switch (action.type) {
    case "ADD_USER_MESSAGE":
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: `user-${Date.now()}`,
            role: "user",
            content: action.content,
            timestamp: Date.now(),
          },
        ],
      };

    case "ADD_ASSISTANT_MESSAGE":
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: `assistant-${Date.now()}`,
            role: "assistant",
            content: action.content,
            timestamp: Date.now(),
            type: action.messageType || 'text',
            error: action.error
          },
        ],
      };

    case "SET_THINKING":
      return {
        ...state,
        isThinking: action.thinking
      };

    case "CLEAR_MESSAGES":
      return {
        ...state,
        messages: [],
        attachments: [],
        workflow: null, // Also clear workflow
        agentWorkflow: {
          todos: [],
          filesChanged: [],
          isActive: false
        },
        pendingToolApproval: undefined,
        activeRunId: null,
        activityByRunId: {},
        activityRunOrder: []
      };

    case "ADD_ATTACHMENT": {
      const key = `${action.attachment.kind}:${action.attachment.path}:${action.attachment.content.length}`;
      const existingIndex = state.attachments.findIndex(att =>
        `${att.kind}:${att.path}:${att.content.length}` === key
      );

      const nextAttachments = existingIndex >= 0
        ? state.attachments.map((att, idx) => idx === existingIndex ? action.attachment : att)
        : [...state.attachments, action.attachment];

      return {
        ...state,
        attachments: nextAttachments
      };
    }

    case "REMOVE_ATTACHMENT":
      return {
        ...state,
        attachments: state.attachments.filter(att =>
          `${att.kind}:${att.path}:${att.content.length}` !== action.attachmentKey
        )
      };

    case "CLEAR_ATTACHMENTS":
      return {
        ...state,
        attachments: []
      };

    case "ADD_ARTIFACT_MESSAGE": {
      // Don't create separate chat bubbles for context artifacts - they clutter the chat
      // Context info should be shown in the activity panel or merged with the response
      if (action.artifact.kind === "context") {
        // Skip creating a message for context - it will be shown in activity panel
        return state;
      }

      const artifactMessage: Message = {
        id: `artifact-${Date.now()}`,
        role: "assistant",
        content: action.artifact.title || "Artifact update",
        timestamp: Date.now(),
        type: 'proposal',
        artifact: action.artifact
      };
      return {
        ...state,
        messages: [...state.messages, artifactMessage]
      };
    }

    case "CLEAR_WORKFLOW":
      return {
        ...state,
        workflow: null
      };

    // Agent workflow cases
    case "AGENT_START":
      return {
        ...state,
        agentWorkflow: {
          ...state.agentWorkflow,
          isActive: true,
          todos: [],
          filesChanged: []
        }
      };

    case "AGENT_ADD_TODO":
      return {
        ...state,
        agentWorkflow: {
          ...state.agentWorkflow,
          todos: [...state.agentWorkflow.todos, action.todo]
        }
      };

    case "AGENT_UPDATE_TODO":
      return {
        ...state,
        agentWorkflow: {
          ...state.agentWorkflow,
          todos: state.agentWorkflow.todos.map(todo =>
            todo.id === action.id ? { ...todo, status: action.status } : todo
          )
        }
      };

    case "AGENT_ADD_FILE_CHANGE":
      // Check if file already exists to avoid duplicates
      const existingFileIndex = state.agentWorkflow.filesChanged.findIndex(
        f => f.path === action.fileChange.path
      );
      if (existingFileIndex >= 0) {
        // Update existing file change
        const updatedFiles = [...state.agentWorkflow.filesChanged];
        updatedFiles[existingFileIndex] = {
          ...updatedFiles[existingFileIndex],
          ...action.fileChange
        };
        return {
          ...state,
          agentWorkflow: {
            ...state.agentWorkflow,
            isActive: true, // Automatically activate when files are changed
            filesChanged: updatedFiles
          }
        };
      }
      // Add new file change
      return {
        ...state,
        agentWorkflow: {
          ...state.agentWorkflow,
          isActive: true, // Automatically activate when files are changed
          filesChanged: [...state.agentWorkflow.filesChanged, action.fileChange]
        }
      };

    case "AGENT_STOP":
      return {
        ...state,
        agentWorkflow: {
          ...state.agentWorkflow,
          isActive: false
        }
      };

    case "START_WORKFLOW":
      if (state.workflow) {
        return state;
      }
      return {
        ...state,
        workflow: {
          ...initialWorkflowState,
          agentStatus: "running",
          currentStep: "scan",
          steps: {
            ...initialWorkflowState.steps,
            scan: "active"
          },
          showActionCard: false,
        },
      };

    case "STEP_ACTIVE":
      if (!state.workflow) return state;
      return {
        ...state,
        workflow: {
          ...state.workflow,
          currentStep: action.step,
          steps: { ...state.workflow.steps, [action.step]: "active" },
        },
      };

    case "STEP_COMPLETE":
      if (!state.workflow) return state;
      return {
        ...state,
        workflow: {
          ...state.workflow,
          steps: { ...state.workflow.steps, [action.step]: "completed" },
        },
      };

    case "STEP_FAIL":
      if (!state.workflow) return state;
      return {
        ...state,
        workflow: {
          ...state.workflow,
          agentStatus: "error",
          steps: { ...state.workflow.steps, [action.step]: "failed" },
        },
      };

    case "REQUEST_APPROVAL":
      if (!state.workflow) return state;
      return {
        ...state,
        workflow: {
          ...state.workflow,
          agentStatus: "awaiting_approval",
          showActionCard: true,
        },
      };

    case "APPROVE":
      if (!state.workflow) return state;
      return {
        ...state,
        workflow: {
          ...state.workflow,
          agentStatus: "running",
          showActionCard: false,
        },
      };

    case "REJECT":
      if (!state.workflow) return state;
      return {
        ...state,
        workflow: {
          ...state.workflow,
          agentStatus: "idle",
          showActionCard: false,
          currentStep: undefined,
        },
      };

    case "RESET":
      return initialUIState;

    // Phase 4.1.2: Plan-based reducer cases
    case "ADD_PLAN":
      const newMessage = {
        id: `plan-${Date.now()}`,
        role: "assistant" as const,
        content: action.plan.goal || "Plan generated",
        timestamp: Date.now(),
        type: 'plan' as const,
        plan: action.plan,
        reasoning: action.reasoning,
        session_id: action.session_id
      };
      const newState = {
        ...state,
        messages: [
          ...state.messages,
          newMessage,
        ],
      };
      return newState;

    // Phase 4.2.1: Conversation-based reducer case
    case "ADD_CONVERSATION":
      const conversationMessage: Message = {
        id: `conversation-${Date.now()}`,
        role: "assistant",
        content: action.content,
        timestamp: Date.now(),
        type: 'conversation',
        conversationType: action.conversationType,
        suggestions: action.suggestions
      };
      return {
        ...state,
        messages: [...state.messages, conversationMessage],
        isThinking: false
      };

    case "REQUEST_TOOL_APPROVAL":
      return {
        ...state,
        pendingToolApproval: {
          tool_request: action.tool_request,
          session_id: action.session_id
        }
      };

    case "RESOLVE_TOOL_APPROVAL":
      return {
        ...state,
        pendingToolApproval: undefined
      };

    case "RUN_STARTED": {
      const runId = action.runId;
      const existing = state.activityByRunId[runId];
      const nextRun: ActivityRunState = existing || {
        events: [],
        collapsedPhaseIds: {},
        status: "running"
      };

      const runOrder = state.activityRunOrder.filter((id) => id !== runId);
      runOrder.push(runId);

      let nextByRun: Record<string, ActivityRunState> = {
        ...state.activityByRunId,
        [runId]: { ...nextRun, status: "running" as const }
      };

      let nextRunOrder = runOrder;
      if (runOrder.length > MAX_ACTIVITY_RUNS) {
        const toRemove = runOrder.slice(0, runOrder.length - MAX_ACTIVITY_RUNS);
        nextRunOrder = runOrder.slice(-MAX_ACTIVITY_RUNS);
        const pruned = { ...nextByRun };
        toRemove.forEach((id) => delete pruned[id]);
        nextByRun = pruned;
      }

      return {
        ...state,
        activeRunId: runId,
        activityByRunId: nextByRun,
        activityRunOrder: nextRunOrder
      };
    }

    case "RUN_FINISHED": {
      const runId = action.runId;
      const existing = state.activityByRunId[runId];
      if (!existing) return state;
      return {
        ...state,
        activityByRunId: {
          ...state.activityByRunId,
          [runId]: { ...existing, status: "done" }
        }
      };
    }

    case "ACTIVITY_APPEND": {
      const { event } = action;
      const runId = event.runId;
      const existing = state.activityByRunId[runId];
      const run: ActivityRunState = existing || {
        events: [],
        collapsedPhaseIds: {},
        status: "running"
      };

      const existingIndex = run.events.findIndex((e) => e.id === event.id);
      const nextEvents =
        existingIndex >= 0
          ? run.events.map((e, index) => (index === existingIndex ? event : e))
          : [...run.events, event];

      const runOrder = state.activityRunOrder.includes(runId)
        ? state.activityRunOrder
        : [...state.activityRunOrder, runId];

      let nextByRun = {
        ...state.activityByRunId,
        [runId]: { ...run, events: nextEvents }
      };

      let nextRunOrder = runOrder;
      if (runOrder.length > MAX_ACTIVITY_RUNS) {
        const toRemove = runOrder.slice(0, runOrder.length - MAX_ACTIVITY_RUNS);
        nextRunOrder = runOrder.slice(-MAX_ACTIVITY_RUNS);
        const pruned = { ...nextByRun };
        toRemove.forEach((id) => delete pruned[id]);
        nextByRun = pruned;
      }

      return {
        ...state,
        activeRunId: state.activeRunId ?? runId,
        activityByRunId: nextByRun,
        activityRunOrder: nextRunOrder
      };
    }

    case "ACTIVITY_CLEAR": {
      if (!action.runId) {
        return {
          ...state,
          activeRunId: null,
          activityByRunId: {},
          activityRunOrder: []
        };
      }

      const existing = state.activityByRunId[action.runId];
      if (!existing) return state;

      return {
        ...state,
        activityByRunId: {
          ...state.activityByRunId,
          [action.runId]: { ...existing, events: [], collapsedPhaseIds: {} }
        }
      };
    }

    case "PHASE_TOGGLE_COLLAPSE": {
      const { runId, phaseId } = action;
      const existing = state.activityByRunId[runId];
      if (!existing) return state;
      const current = Boolean(existing.collapsedPhaseIds[phaseId]);
      return {
        ...state,
        activityByRunId: {
          ...state.activityByRunId,
          [runId]: {
            ...existing,
            collapsedPhaseIds: {
              ...existing.collapsedPhaseIds,
              [phaseId]: !current
            }
          }
        }
      };
    }

    case "SET_ACTIVE_RUN":
      return {
        ...state,
        activeRunId: action.runId
      };

    // Streaming actions (Cline-style real-time)
    case "APPEND_STREAMING_CONTENT":
      return {
        ...state,
        streamingContent: state.streamingContent + action.content
      };

    case "CLEAR_STREAMING_CONTENT":
      return {
        ...state,
        streamingContent: "",
        streamingMetrics: undefined
      };

    case "UPDATE_STREAMING_METRICS":
      return {
        ...state,
        streamingMetrics: action.metrics
      };

    default:
      return state;
  }
}

interface UIContextType {
  state: UIState;
  dispatch: React.Dispatch<UIAction>;
}

const UIContext = createContext<UIContextType | null>(null);

export function UIProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialUIState);
  return (
    <UIContext.Provider value={{ state, dispatch }}>
      {children}
    </UIContext.Provider>
  );
}

export function useUIState() {
  const context = useContext(UIContext);
  if (!context) {
    throw new Error('useUIState must be used within a UIProvider');
  }
  return context;
}
