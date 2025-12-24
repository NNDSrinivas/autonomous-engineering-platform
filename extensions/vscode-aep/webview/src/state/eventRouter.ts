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

// Helper function for DOM fallback
function addPlanDirectToDOM(plan: any) {
  const planElement = document.createElement('div');
  planElement.innerHTML = `
    <div style="background: #1e2024; border: 1px solid #333; border-radius: 8px; padding: 16px; margin: 8px 0;">
      <div style="color: #9cc3ff; font-weight: bold; margin-bottom: 8px;">📋 ${plan.goal}</div>
      <div style="color: #7cc7a0; font-size: 12px; margin-bottom: 12px;">Confidence: ${Math.round(plan.confidence * 100)}%</div>
      <div style="color: #dfe2ea;">
        <strong>Plan Steps:</strong>
        <ol style="margin: 8px 0; padding-left: 20px;">
          ${plan.steps.map(step => `<li style="margin: 4px 0;">${step.title}</li>`).join('')}
        </ol>
      </div>
      <button style="background: #0078d4; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; margin-top: 8px;">
        Approve Plan
      </button>
    </div>
  `;

  const chatContainer = document.querySelector('.flex-1.overflow-y-auto.p-4.space-y-4') ||
    document.querySelector('[class*="chat"]') ||
    document.body;

  if (chatContainer) {
    chatContainer.appendChild(planElement);
    console.log('✅ Plan added directly to DOM');
  } else {
    console.error('❌ Could not find chat container');
  }
}

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

    // Phase 4.1.2: Plan-based responses
    case 'navi.assistant.plan':
      console.log('📋 Plan received:', event.plan);

      // PROPER APPROACH: Try React state management first
      console.log('🐛 Attempting React dispatch for ADD_PLAN...');
      console.log('🐛 Dispatch function type:', typeof dispatch);
      console.log('🐛 Dispatch function name:', dispatch.name);
      console.log('🐛 Dispatch function toString:', dispatch.toString());
      console.log('🐛 Plan data:', event.plan);

      try {
        console.log('🐛 About to call dispatch...');
        dispatch({ type: 'ADD_PLAN', plan: event.plan, reasoning: event.reasoning, session_id: event.session_id });
        console.log('✅ React dispatch called successfully');
        console.log('🐛 Dispatch call completed, waiting for render...');        // Give React a moment to render, then check if it worked
        setTimeout(() => {
          const planMessages = document.querySelectorAll('[data-plan-message]');
          console.log('🐛 Plan messages found after dispatch:', planMessages.length);

          if (planMessages.length === 0) {
            console.log('⚠️ React rendering failed, falling back to direct DOM...');
            addPlanDirectToDOM(event.plan);
          } else {
            console.log('✅ React rendering successful!');
          }
        }, 100);

      } catch (error) {
        console.error('❌ React dispatch failed:', error);
        console.log('⚠️ Falling back to direct DOM...');
        addPlanDirectToDOM(event.plan);
      }
      break;

    // Phase 4.1.2: Tool approval requests
    case 'navi.tool.approval':
      console.log('🔧 Tool approval required:', event.tool_request);
      dispatch({ type: 'REQUEST_TOOL_APPROVAL', tool_request: event.tool_request, session_id: event.session_id });
      break;

    case 'navi.assistant.error':
      console.log('❌ Assistant error:', event.content);
      dispatch({ type: 'ADD_ASSISTANT_MESSAGE', content: event.content, error: event.error });
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