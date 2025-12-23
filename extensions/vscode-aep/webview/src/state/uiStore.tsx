import React, { createContext, useContext, useReducer, ReactNode } from "react";

// Canonical types locked for Phase 4 baseline
export type AgentStatus = "idle" | "running" | "awaiting_approval" | "error";
export type StepStatus = "pending" | "active" | "completed" | "failed";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  type?: 'text' | 'thinking' | 'step' | 'command' | 'result' | 'proposal';
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

export interface UIState {
  // Chat state
  messages: Message[];
  // Thinking state for input disabling
  isThinking: boolean;
  // Workflow state (starts as null - no default workflow!)
  workflow: WorkflowState | null;
  // Agent workflow (NEW - for Copilot-style behavior)
  agentWorkflow: AgentWorkflowState;
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
  isThinking: false,
  workflow: null, // ⭐ CRITICAL: No workflow by default
  agentWorkflow: {
    todos: [],
    filesChanged: [],
    isActive: false
  }
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
  | { type: "ADD_ASSISTANT_MESSAGE"; content: string; messageType?: 'text' | 'thinking' | 'step' | 'command' | 'result' | 'proposal' }
  | { type: "SET_THINKING"; thinking: boolean }
  | { type: "CLEAR_MESSAGES" }
  | { type: "START_WORKFLOW" }
  | { type: "STEP_ACTIVE"; step: string }
  | { type: "STEP_COMPLETE"; step: string }
  | { type: "STEP_FAIL"; step: string }
  | { type: "REQUEST_APPROVAL" }
  | { type: "APPROVE" }
  | { type: "REJECT" }
  | { type: "RESET" }
  // Agent workflow actions (NEW)
  | { type: "AGENT_START" }
  | { type: "AGENT_ADD_TODO"; todo: TodoItem }
  | { type: "AGENT_UPDATE_TODO"; id: string; status: TodoItem['status'] }
  | { type: "AGENT_ADD_FILE_CHANGE"; fileChange: FileChangeSummary }
  | { type: "AGENT_REQUEST_PERMISSION"; permission: PermissionRequest }
  | { type: "AGENT_STOP" };

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
            type: action.messageType || 'text'
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
        workflow: null, // Also clear workflow
        agentWorkflow: {
          todos: [],
          filesChanged: [],
          isActive: false
        }
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

    case "AGENT_STOP":
      return {
        ...state,
        agentWorkflow: {
          ...state.agentWorkflow,
          isActive: false
        }
      };

    case "START_WORKFLOW":
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