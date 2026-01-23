import React, { useState, useEffect, useRef, useCallback } from 'react';
import { ChevronDown, Check, Loader2, AlertCircle } from 'lucide-react';

type TaskStep = {
  id: number;
  label: string;
  status: "pending" | "in_progress" | "completed" | "error";
};

interface NaviProgressBarProps {
  steps: TaskStep[];
  isVisible: boolean;
  onDismiss?: () => void;
}

export const NaviProgressBar: React.FC<NaviProgressBarProps> = ({
  steps,
  isVisible,
  onDismiss
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [manualOverride, setManualOverride] = useState(false);
  const prevCompletedRef = useRef(0);
  const autoCollapseTimeoutRef = useRef<number | null>(null);

  // Calculate progress metrics
  const currentStep = steps.find(s => s.status === 'in_progress');
  const completedCount = steps.filter(s => s.status === 'completed').length;
  const totalCount = steps.length;
  const allCompleted = completedCount === totalCount && totalCount > 0;
  const hasError = steps.some(s => s.status === 'error');
  const progressPercentage = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;

  // Auto-expand on step completion (if not manually overridden)
  useEffect(() => {
    if (manualOverride || !isVisible) return;

    // Check if a new step was completed
    if (completedCount > prevCompletedRef.current && !allCompleted) {
      setIsExpanded(true);

      // Clear any existing timeout
      if (autoCollapseTimeoutRef.current) {
        clearTimeout(autoCollapseTimeoutRef.current);
      }

      // Auto-collapse after 1.5 seconds
      autoCollapseTimeoutRef.current = window.setTimeout(() => {
        setIsExpanded(false);
      }, 1500);
    }

    prevCompletedRef.current = completedCount;

    return () => {
      if (autoCollapseTimeoutRef.current) {
        clearTimeout(autoCollapseTimeoutRef.current);
      }
    };
  }, [completedCount, allCompleted, manualOverride, isVisible]);

  // Reset state when task finishes or becomes invisible
  useEffect(() => {
    if (!isVisible) {
      setManualOverride(false);
      setIsExpanded(false);
      prevCompletedRef.current = 0;
    }
  }, [isVisible]);

  // Handle manual toggle
  const handleToggle = useCallback(() => {
    setManualOverride(true);
    setIsExpanded(prev => !prev);

    // Clear auto-collapse timeout on manual interaction
    if (autoCollapseTimeoutRef.current) {
      clearTimeout(autoCollapseTimeoutRef.current);
    }
  }, []);

  // Don't render if not visible or no steps
  if (!isVisible || steps.length === 0) {
    return null;
  }

  return (
    <div
      className={`navi-progress-bar ${isExpanded ? 'is-expanded' : ''} ${allCompleted ? 'is-completed' : ''} ${hasError ? 'has-error' : ''}`}
    >
      {/* Compact header - always visible, clickable to expand/collapse */}
      <button
        type="button"
        className="navi-progress-header"
        onClick={handleToggle}
        aria-expanded={isExpanded}
        aria-label={isExpanded ? 'Collapse progress' : 'Expand progress'}
      >
        {/* Progress indicator icon */}
        <span className="navi-progress-indicator">
          {allCompleted ? (
            <Check className="h-4 w-4" />
          ) : hasError ? (
            <AlertCircle className="h-4 w-4" />
          ) : (
            <Loader2 className="h-4 w-4 animate-spin" />
          )}
        </span>

        {/* Current step label or completion message */}
        <span className="navi-progress-label">
          {allCompleted
            ? 'All steps completed'
            : hasError
              ? 'An error occurred'
              : currentStep?.label || 'Processing...'}
        </span>

        {/* Step counter badge */}
        <span className="navi-progress-counter">
          {completedCount}/{totalCount}
        </span>

        {/* Expand/collapse chevron */}
        <span className={`navi-progress-chevron ${isExpanded ? 'rotated' : ''}`}>
          <ChevronDown className="h-4 w-4" />
        </span>
      </button>

      {/* Progress bar track */}
      <div className="navi-progress-track">
        <div
          className="navi-progress-fill"
          style={{ width: `${progressPercentage}%` }}
        />
      </div>

      {/* Expandable steps list */}
      <div className="navi-progress-steps">
        {steps.map((step, idx) => (
          <div
            key={step.id}
            className={`navi-progress-step navi-progress-step--${step.status}`}
          >
            <span className="navi-progress-step-icon">
              {step.status === 'completed' && <Check className="h-3 w-3" />}
              {step.status === 'in_progress' && <Loader2 className="h-3 w-3 animate-spin" />}
              {step.status === 'error' && <AlertCircle className="h-3 w-3" />}
              {step.status === 'pending' && (
                <span className="navi-progress-step-num">{idx + 1}</span>
              )}
            </span>
            <span className="navi-progress-step-label">{step.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default NaviProgressBar;
