import React, { createContext, useContext, useReducer, ReactNode } from "react";
import { createElement } from "react";

// Canonical types locked for Phase 4 baseline
export type AgentStatus = "idle" | "running" | "awaiting_approval" | "error";
export type StepStatus = "pending" | "active" | "completed" | "failed";

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

export interface WorkflowState {
  agentStatus: AgentStatus;
  steps: Record<string, StepStatus>;
  currentStep?: string;
  showActionCard: boolean;
  messages: Message[];
}

// Frozen workflow step names - backend events will map to these
const initialState: WorkflowState = {
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
  messages: [],
};

export type UIAction =
  | { type: "START_WORKFLOW" }
  | { type: "STEP_ACTIVE"; step: string }
  | { type: "STEP_COMPLETE"; step: string }
  | { type: "STEP_FAIL"; step: string }
  | { type: "REQUEST_APPROVAL" }
  | { type: "APPROVE" }
  | { type: "REJECT" }
  | { type: "RESET" }
  | { type: "ADD_USER_MESSAGE"; content: string }
  | { type: "ADD_ASSISTANT_MESSAGE"; content: string }
  | { type: "CLEAR_MESSAGES" };

function reducer(state: WorkflowState, action: UIAction): WorkflowState {
  switch (action.type) {
    case "START_WORKFLOW":
      return {
        ...state,
        agentStatus: "running",
        currentStep: "scan",
        steps: { 
          ...initialState.steps, // Reset all steps
          scan: "active" 
        },
        showActionCard: false,
      };

    case "STEP_ACTIVE":
      return {
        ...state,
        currentStep: action.step,
        steps: { ...state.steps, [action.step]: "active" },
      };

    case "STEP_COMPLETE":
      return {
        ...state,
        steps: { ...state.steps, [action.step]: "completed" },
      };

    case "STEP_FAIL":
      return {
        ...state,
        agentStatus: "error",
        steps: { ...state.steps, [action.step]: "failed" },
      };

    case "REQUEST_APPROVAL":
      return {
        ...state,
        agentStatus: "awaiting_approval",
        showActionCard: true,
      };

    case "APPROVE":
      return {
        ...state,
        agentStatus: "running",
        showActionCard: false,
      };

    case "REJECT":
      return {
        ...state,
        agentStatus: "idle",
        showActionCard: false,
        currentStep: undefined,
      };

    case "RESET":
      return initialState;
      
    case "ADD_USER_MESSAGE":
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: crypto.randomUUID(),
            role: 'user',
            content: action.content,
            timestamp: Date.now()
          }
        ]
      };
      
    case "ADD_ASSISTANT_MESSAGE":
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: action.content,
            timestamp: Date.now()
          }
        ]
      };
      
    case "CLEAR_MESSAGES":
      return {
        ...state,
        messages: []
      };

    default:
      return state;
  }
}

interface UIContextType {
  state: WorkflowState;
  dispatch: React.Dispatch<UIAction>;
}

const UIContext = createContext<UIContextType | null>(null);

export function UIProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  
  return createElement(UIContext.Provider, { value: { state, dispatch } }, children);
}

export function useUIState() {
  const context = useContext(UIContext);
  if (!context) {
    throw new Error('useUIState must be used within a UIProvider');
  }
  return context;
}