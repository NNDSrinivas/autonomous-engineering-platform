import { Dispatch } from "react";
import { UIAction } from "./uiStore";

/**
 * Central Event Router - Maps extension events to UI state machine
 * 
 * Phase 4.0.4: Replaces mockConversation.ts as the driver of UI state.
 * All extension → webview communication flows through this single router.
 * 
 * Canonical Event Contract (FROZEN):
 * - navi.workflow.started
 * - navi.workflow.step
 * - navi.workflow.completed  
 * - navi.workflow.failed
 * - navi.approval.required
 * - navi.approval.resolved
 * - navi.changePlan.generated
 * - navi.diffs.generated
 * - navi.validation.result
 */

export function routeEventToUI(
  event: any,
  dispatch: Dispatch<UIAction>
) {
  console.log('🔄 Extension Event → UI:', event);

  switch (event.type) {
    case 'navi.workflow.started':
      dispatch({ type: 'START_WORKFLOW' });
      break;

    case 'navi.workflow.step':
      if (event.status === 'active') {
        dispatch({ type: 'STEP_ACTIVE', step: event.step });
      }
      if (event.status === 'completed') {
        dispatch({ type: 'STEP_COMPLETE', step: event.step });
      }
      if (event.status === 'failed') {
        dispatch({ type: 'STEP_FAIL', step: event.step });
      }
      break;

    case 'navi.approval.required':
      dispatch({ type: 'REQUEST_APPROVAL' });
      break;

    case 'navi.workflow.completed':
      dispatch({ type: 'RESET' });
      break;

    case 'navi.workflow.failed':
      dispatch({ type: 'STEP_FAIL', step: event.step || 'unknown' });
      break;

    // Future artifact events (already prepared)
    case 'navi.changePlan.generated':
      // TODO: Add change plan to state when artifacts are implemented
      console.log('📋 Change plan generated:', event.plan);
      break;

    case 'navi.diffs.generated':
      // TODO: Add diffs to state when artifacts are implemented  
      console.log('📝 Diffs generated:', event.diffs);
      break;

    case 'navi.validation.result':
      // TODO: Add validation results to state when artifacts are implemented
      console.log('✅ Validation result:', event.result);
      break;

    case 'navi.assistant.message':
      dispatch({ type: 'ADD_ASSISTANT_MESSAGE', content: event.content });
      break;

    case 'navi.assistant.thinking':
      // Handle thinking state for backend API calls
      console.log(event.thinking ? '🤔 Assistant thinking...' : '✅ Assistant ready');
      dispatch({ type: 'SET_THINKING', thinking: !!event.thinking });
      break;

    default:
      console.warn('⚠️ Unknown event type:', event.type);
      break;
  }
}

// Event type definitions for TypeScript
export interface WorkflowStartedEvent {
  type: 'navi.workflow.started';
}

export interface WorkflowStepEvent {
  type: 'navi.workflow.step';
  step: string;
  status: 'active' | 'completed' | 'failed';
}

export interface ApprovalRequiredEvent {
  type: 'navi.approval.required';
  reason?: string;
}

export interface WorkflowCompletedEvent {
  type: 'navi.workflow.completed';
}

export interface WorkflowFailedEvent {
  type: 'navi.workflow.failed';
  step?: string;
  error?: string;
}

export interface ApprovalResolvedEvent {
  type: 'navi.approval.resolved';
  decision: 'approve' | 'reject';
}

export type ExtensionEvent = 
  | WorkflowStartedEvent
  | WorkflowStepEvent  
  | ApprovalRequiredEvent
  | WorkflowCompletedEvent
  | WorkflowFailedEvent
  | ApprovalResolvedEvent;