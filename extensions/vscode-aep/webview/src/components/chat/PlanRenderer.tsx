/**
 * Phase 4.1.2a - Plan Renderer Component
 * 
 * Replaces raw LLM text with structured plan visualization.
 * Shows reasoning, plan steps, confidence, and approval state.
 */

import React, { useState } from 'react';
import type { Plan } from '../../types/plan';
import { postMessage } from '../../utils/vscodeApi';

// Design tokens consistent with ChatArea
const DESIGN_TOKENS = {
  plan: {
    bg: 'rgba(18, 19, 23, 0.65)',
    border: 'rgba(255, 255, 255, 0.06)',
    text: '#dfe2ea',
    accent: '#9cc3ff',
    success: '#7cc7a0',
    warning: '#f4c467',
    error: '#ff7a7a'
  },
  fonts: {
    ui: 'Inter, SF Pro Text, Segoe UI, system-ui, sans-serif',
    mono: 'JetBrains Mono, SF Mono, Consolas, monospace',
    title: '14px',
    body: '13px',
    meta: '11px'
  }
};

// System-grade icons
const ChevronDownIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="6,9 12,15 18,9"></polyline>
  </svg>
);

const ChevronRightIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="9,18 15,12 9,6"></polyline>
  </svg>
);

const CheckCircleIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
    <polyline points="22,4 12,14.01 9,11.01"></polyline>
  </svg>
);

const AlertCircleIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="10"></circle>
    <line x1="12" y1="8" x2="12" y2="12"></line>
    <line x1="12" y1="16" x2="12.01" y2="16"></line>
  </svg>
);

interface PlanRendererProps {
  plan: Plan;
  reasoning?: string;
  session_id?: string;
}

export function PlanRenderer({ plan, reasoning, session_id }: PlanRendererProps) {
  const [showReasoning, setShowReasoning] = useState(false);
  const [approvalState, setApprovalState] = useState<'idle' | 'approved' | 'rejected'>('idle');
  const taskId = plan?.execution?.task_id || plan?.task_id || plan?.id;

  // Safety check
  if (!plan) {
    return <div>Error: No plan provided</div>;
  }

  if (!plan.goal) {
    return <div>Error: Plan missing goal</div>;
  }

  const getConfidenceColor = (confidence: number): string => {
    if (confidence >= 0.8) return DESIGN_TOKENS.plan.success;
    if (confidence >= 0.6) return DESIGN_TOKENS.plan.warning;
    return DESIGN_TOKENS.plan.error;
  };

  const getStepIcon = (tool: string) => {
    switch (tool) {
      case 'scanProblems': return '🔍';
      case 'analyzeProblems': return '🧩';
      case 'applyFixes': return '💡';
      case 'verifyProblems': return '✅';
      case 'inspect': return '🔍';
      case 'analyze': return '🧩';
      case 'propose': return '💡';
      case 'summarize': return '📋';
      default: return '⚡';
    }
  };

  return (
    <div
      className="plan-renderer rounded-lg p-4 mb-3"
      data-plan-message="true"
      style={{
        background: DESIGN_TOKENS.plan.bg,
        backdropFilter: 'blur(14px)',
        border: `1px solid ${DESIGN_TOKENS.plan.border}`,
        fontFamily: DESIGN_TOKENS.fonts.ui,
      }}
    >
      {/* Plan Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-blue-400"></div>
          <h3
            className="font-medium"
            style={{
              fontSize: DESIGN_TOKENS.fonts.title,
              color: DESIGN_TOKENS.plan.text,
            }}
          >
            {plan.goal}
          </h3>
        </div>

        {/* Confidence Indicator */}
        <div className="flex items-center gap-2">
          <div
            className="px-2 py-1 rounded text-xs font-medium"
            style={{
              backgroundColor: `${getConfidenceColor(plan.confidence)}20`,
              color: getConfidenceColor(plan.confidence),
              fontSize: DESIGN_TOKENS.fonts.meta,
            }}
          >
            {Math.round(plan.confidence * 100)}% confident
          </div>

          {plan.requires_approval && (
            <div
              className="flex items-center gap-1 px-2 py-1 rounded text-xs"
              style={{
                backgroundColor: `${DESIGN_TOKENS.plan.warning}20`,
                color: DESIGN_TOKENS.plan.warning,
                fontSize: DESIGN_TOKENS.fonts.meta,
              }}
            >
              <AlertCircleIcon />
              <span>Requires approval</span>
            </div>
          )}
        </div>
      </div>

      {/* Plan Steps */}
      <div className="space-y-2 mb-3">
        {(plan.steps || []).map((step, index) => (
          <div
            key={step.id}
            className="flex items-start gap-3 p-2 rounded"
            style={{
              backgroundColor: 'rgba(255, 255, 255, 0.02)',
            }}
          >
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <span className="text-lg" role="img" aria-label={step.tool || 'step'}>
                {getStepIcon(step.tool || 'default')}
              </span>
              <span
                className="flex-1"
                style={{
                  fontSize: DESIGN_TOKENS.fonts.body,
                  color: DESIGN_TOKENS.plan.text,
                  lineHeight: '1.4',
                }}
              >
                {index + 1}. {step.title}
              </span>
            </div>

            {step.requires_approval && (
              <AlertCircleIcon />
            )}
          </div>
        ))}
      </div>

      {/* Collapsible Reasoning */}
      <div>
        <button
          onClick={() => setShowReasoning(!showReasoning)}
          className="flex items-center gap-2 text-sm opacity-70 hover:opacity-100 transition-opacity"
          style={{
            color: DESIGN_TOKENS.plan.text,
            fontSize: DESIGN_TOKENS.fonts.meta,
          }}
        >
          {showReasoning ? <ChevronDownIcon /> : <ChevronRightIcon />}
          <span>Reasoning</span>
        </button>

        {showReasoning && (
          <div
            className="mt-2 p-3 rounded"
            style={{
              backgroundColor: 'rgba(255, 255, 255, 0.02)',
              fontSize: DESIGN_TOKENS.fonts.body,
              color: 'rgba(223, 226, 234, 0.8)',
              lineHeight: '1.5',
            }}
          >
            {reasoning || plan.reasoning || "No reasoning provided"}
          </div>
        )}
      </div>

      {plan.requires_approval && (
        <div className="mt-4 flex items-center gap-2">
          <button
            className="px-3 py-1.5 rounded text-xs font-medium bg-[var(--vscode-button-background)] text-[var(--vscode-button-foreground)] hover:bg-[var(--vscode-button-hoverBackground)] transition-colors disabled:opacity-50"
            disabled={approvalState !== 'idle' || !taskId}
            onClick={() => {
              if (!taskId) {
                return;
              }
              setApprovalState('approved');
              postMessage({
                type: 'navi.plan.approval',
                approved: true,
                task_id: taskId,
                session_id: session_id
              });
            }}
          >
            Approve & Execute
          </button>
          <button
            className="px-3 py-1.5 rounded text-xs font-medium text-[var(--vscode-descriptionForeground)] hover:text-[var(--vscode-foreground)] hover:bg-[var(--vscode-toolbar-hoverBackground)] transition-colors disabled:opacity-50"
            disabled={approvalState !== 'idle'}
            onClick={() => {
              setApprovalState('rejected');
              postMessage({
                type: 'navi.plan.approval',
                approved: false,
                task_id: taskId,
                session_id: session_id
              });
            }}
          >
            Cancel
          </button>
          {!taskId && (
            <span className="text-xs text-red-400">
              Missing task id - regenerate plan.
            </span>
          )}
        </div>
      )}

      {/* Intent Kind (for debugging) */}
      <div
        className="mt-3 pt-2 border-t border-opacity-20"
        style={{
          borderColor: DESIGN_TOKENS.plan.border,
        }}
      >
        <span
          style={{
            fontSize: DESIGN_TOKENS.fonts.meta,
            color: 'rgba(223, 226, 234, 0.5)',
            fontFamily: DESIGN_TOKENS.fonts.mono,
          }}
        >
          {plan.intent_kind && `Intent: ${plan.intent_kind}`}
        </span>
      </div>
    </div>
  );
}
