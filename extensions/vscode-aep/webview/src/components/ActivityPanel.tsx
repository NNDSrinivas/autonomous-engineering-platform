import React, { useState, useEffect } from 'react';
import { Check, Clock, FileCode, Loader2, AlertCircle, ChevronDown, ChevronRight } from 'lucide-react';

export interface FileChange {
  path: string;
  operation: 'create' | 'modify' | 'delete';
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  additions?: number;
  deletions?: number;
  error?: string;
}

export interface ActivityStep {
  id: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  fileChanges: FileChange[];
  startTime?: number;
  endTime?: number;
}

interface ActivityPanelProps {
  steps: ActivityStep[];
  currentStep?: number;
  onFileClick?: (filePath: string) => void;
  onAcceptAll?: () => void;
  onRejectAll?: () => void;
}

export function ActivityPanel({ steps, currentStep, onFileClick, onAcceptAll, onRejectAll }: ActivityPanelProps) {
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());

  // Auto-expand current step
  useEffect(() => {
    if (currentStep !== undefined && steps[currentStep]) {
      setExpandedSteps(prev => new Set(prev).add(steps[currentStep].id));
    }
  }, [currentStep, steps]);

  const toggleStep = (stepId: string) => {
    setExpandedSteps(prev => {
      const next = new Set(prev);
      if (next.has(stepId)) {
        next.delete(stepId);
      } else {
        next.add(stepId);
      }
      return next;
    });
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <Check className="w-4 h-4 text-green-500" />;
      case 'in_progress':
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-400" />;
    }
  };

  const getOperationColor = (operation: string) => {
    switch (operation) {
      case 'create':
        return 'text-green-600 dark:text-green-400';
      case 'modify':
        return 'text-yellow-600 dark:text-yellow-400';
      case 'delete':
        return 'text-red-600 dark:text-red-400';
      default:
        return 'text-gray-600 dark:text-gray-400';
    }
  };

  const totalChanges = steps.reduce((acc, step) => acc + step.fileChanges.length, 0);
  const completedSteps = steps.filter(s => s.status === 'completed').length;

  return (
    <div className="activity-panel flex flex-col h-full bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-800">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          Activity
        </h2>
        <div className="mt-2 text-sm text-gray-600 dark:text-gray-400">
          {completedSteps} of {steps.length} steps • {totalChanges} file changes
        </div>

        {/* Progress bar */}
        <div className="mt-3 h-1 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 transition-all duration-300"
            style={{ width: `${(completedSteps / steps.length) * 100}%` }}
          />
        </div>
      </div>

      {/* Steps list */}
      <div className="flex-1 overflow-y-auto">
        {steps.map((step, index) => {
          const isExpanded = expandedSteps.has(step.id);
          const isCurrent = index === currentStep;

          return (
            <div
              key={step.id}
              className={`border-b border-gray-200 dark:border-gray-800 ${
                isCurrent ? 'bg-blue-50 dark:bg-blue-900/10' : ''
              }`}
            >
              {/* Step header */}
              <button
                onClick={() => toggleStep(step.id)}
                className="w-full p-4 flex items-start gap-3 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
              >
                <div className="mt-0.5">{getStatusIcon(step.status)}</div>

                <div className="flex-1 text-left">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900 dark:text-gray-100">
                      Step {index + 1}
                    </span>
                    {isCurrent && (
                      <span className="px-2 py-0.5 text-xs bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded">
                        Current
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                    {step.description}
                  </p>
                  {step.fileChanges.length > 0 && (
                    <div className="mt-2 text-xs text-gray-500 dark:text-gray-500">
                      {step.fileChanges.length} file{step.fileChanges.length !== 1 ? 's' : ''}
                    </div>
                  )}
                </div>

                {isExpanded ? (
                  <ChevronDown className="w-4 h-4 text-gray-400" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-gray-400" />
                )}
              </button>

              {/* Expanded file changes */}
              {isExpanded && step.fileChanges.length > 0 && (
                <div className="px-4 pb-4 space-y-2">
                  {step.fileChanges.map((change, idx) => (
                    <div
                      key={idx}
                      className="flex items-center gap-3 p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer group"
                      onClick={() => onFileClick?.(change.path)}
                    >
                      <FileCode className="w-4 h-4 text-gray-400" />

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-gray-900 dark:text-gray-100 truncate">
                            {change.path}
                          </span>
                          <span className={`text-xs ${getOperationColor(change.operation)}`}>
                            {change.operation}
                          </span>
                        </div>

                        {(change.additions !== undefined || change.deletions !== undefined) && (
                          <div className="mt-1 flex items-center gap-2 text-xs">
                            {change.additions !== undefined && (
                              <span className="text-green-600 dark:text-green-400">
                                +{change.additions}
                              </span>
                            )}
                            {change.deletions !== undefined && (
                              <span className="text-red-600 dark:text-red-400">
                                -{change.deletions}
                              </span>
                            )}
                          </div>
                        )}

                        {change.error && (
                          <div className="mt-1 text-xs text-red-600 dark:text-red-400">
                            {change.error}
                          </div>
                        )}
                      </div>

                      <div className="opacity-0 group-hover:opacity-100 transition-opacity">
                        {getStatusIcon(change.status)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer actions */}
      {completedSteps === steps.length && completedSteps > 0 && (
        <div className="p-4 border-t border-gray-200 dark:border-gray-800 flex gap-2">
          <button
            onClick={onAcceptAll}
            className="flex-1 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors text-sm font-medium"
          >
            Accept All Changes
          </button>
          <button
            onClick={onRejectAll}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-lg transition-colors text-sm font-medium"
          >
            Reject
          </button>
        </div>
      )}
    </div>
  );
}
