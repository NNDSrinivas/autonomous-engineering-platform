/**
 * ExecutionPlanStepper - Visual step-by-step execution progress UI
 *
 * Displays execution plans parsed from NAVI's narrative output with real-time
 * status tracking (pending, running, completed, error) for each step.
 *
 * Supports both controlled and uncontrolled expansion modes:
 * - Controlled: Pass `isExpanded` and `onToggle` props
 * - Uncontrolled: Component manages its own expanded state
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Check,
  Loader2,
  AlertCircle,
  Zap,
} from 'lucide-react';

export interface ExecutionPlanStep {
  index: number;
  title: string;
  detail?: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  output?: string;
  error?: string;
}

interface ExecutionPlanStepperProps {
  planId: string;
  steps: ExecutionPlanStep[];
  isExecuting: boolean;
  /** Controlled expansion state (optional) */
  isExpanded?: boolean;
  /** Callback when expansion is toggled (optional) */
  onToggle?: (expanded: boolean) => void;
  /** Auto-collapse after step transition (default: 4000ms, 0 to disable) */
  autoCollapseMs?: number;
}

export const ExecutionPlanStepper: React.FC<ExecutionPlanStepperProps> = ({
  planId,
  steps,
  isExecuting,
  isExpanded: controlledExpanded,
  onToggle,
  autoCollapseMs = 4000,
}) => {
  // Support both controlled and uncontrolled modes
  const [internalExpanded, setInternalExpanded] = useState(true);
  const isControlled = controlledExpanded !== undefined;
  const isExpanded = isControlled ? controlledExpanded : internalExpanded;

  // Track previous step statuses for detecting transitions
  const prevStepsRef = useRef<ExecutionPlanStep[]>([]);
  const autoCollapseTimerRef = useRef<NodeJS.Timeout | null>(null);

  const completedCount = steps.filter((s) => s.status === 'completed').length;
  const errorCount = steps.filter((s) => s.status === 'error').length;
  const progressPercent =
    steps.length > 0 ? (completedCount / steps.length) * 100 : 0;
  const currentStep = steps.find((s) => s.status === 'running');
  const allCompleted = completedCount === steps.length && steps.length > 0;
  const hasError = errorCount > 0;

  // Handle toggle - support both controlled and uncontrolled modes
  const handleToggle = () => {
    const newExpanded = !isExpanded;
    if (onToggle) {
      onToggle(newExpanded);
    }
    if (!isControlled) {
      setInternalExpanded(newExpanded);
    }
  };

  // Auto-expand on step status changes, then auto-collapse after delay
  useEffect(() => {
    if (autoCollapseMs <= 0) return;

    const prevSteps = prevStepsRef.current;
    const hasStepTransition = steps.some((step, i) => {
      const prevStep = prevSteps[i];
      if (!prevStep) return false;
      // Detect when a step completes or starts running
      return (
        (prevStep.status !== 'completed' && step.status === 'completed') ||
        (prevStep.status === 'pending' && step.status === 'running')
      );
    });

    if (hasStepTransition && !isExpanded) {
      // Expand briefly to show the transition
      if (onToggle) {
        onToggle(true);
      }
      if (!isControlled) {
        setInternalExpanded(true);
      }
    }

    // Schedule auto-collapse after step transition
    if (hasStepTransition) {
      // Clear any existing timer
      if (autoCollapseTimerRef.current) {
        clearTimeout(autoCollapseTimerRef.current);
      }

      autoCollapseTimerRef.current = setTimeout(() => {
        // Only collapse if still executing (not at the end)
        if (!allCompleted && !hasError) {
          if (onToggle) {
            onToggle(false);
          }
          if (!isControlled) {
            setInternalExpanded(false);
          }
        }
      }, autoCollapseMs);
    }

    // Update previous steps reference
    prevStepsRef.current = [...steps];

    return () => {
      if (autoCollapseTimerRef.current) {
        clearTimeout(autoCollapseTimerRef.current);
      }
    };
  }, [steps, autoCollapseMs, isExpanded, allCompleted, hasError, isControlled, onToggle]);

  // Determine header display text
  const headerText = allCompleted
    ? 'All steps completed'
    : hasError
    ? `Error at step ${steps.findIndex((s) => s.status === 'error') + 1}`
    : currentStep
    ? currentStep.title
    : 'Execution Plan';

  return (
    <div
      className={`navi-plan-stepper ${
        !isExpanded ? 'navi-plan-stepper--collapsed' : ''
      } ${allCompleted ? 'navi-plan-stepper--completed' : ''} ${
        hasError ? 'navi-plan-stepper--error' : ''
      }`}
      data-plan-id={planId}
    >
      {/* Collapsible Header */}
      <button
        type="button"
        className="navi-plan-header"
        onClick={handleToggle}
        aria-expanded={isExpanded}
        aria-label={isExpanded ? 'Collapse execution plan' : 'Expand execution plan'}
      >
        <span className="navi-plan-icon">
          {allCompleted ? (
            <Check className="h-4 w-4" />
          ) : hasError ? (
            <AlertCircle className="h-4 w-4" />
          ) : isExecuting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Zap className="h-4 w-4" />
          )}
        </span>
        <span className="navi-plan-title">{headerText}</span>
        <span className="navi-plan-progress-badge">
          {completedCount}/{steps.length}
        </span>
        <span className={`navi-plan-chevron ${isExpanded ? 'rotated' : ''}`}>
          {isExpanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </span>
      </button>

      {/* Progress Bar */}
      <div className="navi-plan-progress-track">
        <div
          className={`navi-plan-progress-fill ${hasError ? 'has-error' : ''}`}
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Step List */}
      {isExpanded && (
        <div className="navi-plan-steps">
          {steps.map((step, idx) => (
            <div
              key={`${planId}-step-${idx}`}
              className={`navi-plan-step navi-plan-step--${step.status}`}
            >
              <span className="navi-plan-step-icon">
                {step.status === 'completed' && (
                  <Check className="h-3.5 w-3.5" />
                )}
                {step.status === 'running' && (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                )}
                {step.status === 'error' && (
                  <AlertCircle className="h-3.5 w-3.5" />
                )}
                {step.status === 'pending' && <span>{step.index}</span>}
              </span>
              <div className="navi-plan-step-content">
                <div className="navi-plan-step-title">{step.title}</div>
                {step.detail && (
                  <div className="navi-plan-step-detail">{step.detail}</div>
                )}
                {step.output && (
                  <div className="navi-plan-step-output">{step.output}</div>
                )}
                {step.error && (
                  <div className="navi-plan-step-error">{step.error}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ExecutionPlanStepper;
