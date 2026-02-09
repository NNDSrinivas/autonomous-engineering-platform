import React, { useState, useEffect, useRef } from 'react';
import { Check, Clock, FileCode, Loader2, AlertCircle, ChevronDown, ChevronRight, Terminal } from 'lucide-react';
import { useActivityPanelPreferences } from '../hooks/useActivityPanelPreferences';

export interface FileChange {
  path: string;
  operation: 'create' | 'modify' | 'delete';
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  additions?: number;
  deletions?: number;
  error?: string;
}

export interface CommandPreview {
  id: string;
  command: string;
  status: 'running' | 'done' | 'error';
  stdout?: string;
  stderr?: string;
  truncated?: boolean;
  exitCode?: number;
  updatedAt?: number;
}

export interface ActivityStep {
  id: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  fileChanges: FileChange[];
  commands: CommandPreview[];
  startTime?: number;
  endTime?: number;
}

interface ActivityPanelProps {
  steps: ActivityStep[];
  currentStep?: number;
  highlightCommandId?: string | null;
  onFileClick?: (filePath: string) => void;
  onAcceptAll?: () => void;
  onRejectAll?: () => void;
  onViewHistory?: () => void;
  onViewInChat?: (commandId: string) => void;
}

export function ActivityPanel({
  steps,
  currentStep,
  highlightCommandId,
  onFileClick,
  onAcceptAll,
  onRejectAll,
  onViewHistory,
  onViewInChat,
}: ActivityPanelProps) {
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());
  const [expandedCommands, setExpandedCommands] = useState<Set<string>>(new Set());
  const lastAutoExpandedStepRef = useRef<string | null>(null);
  const [activityPreferences] = useActivityPanelPreferences();
  const showCommands = activityPreferences.showCommands;
  const showCommandOutput = activityPreferences.showCommandOutput;
  const showFileChanges = activityPreferences.showFileChanges;

  // Auto-expand current step
  useEffect(() => {
    if (currentStep !== undefined && steps[currentStep]) {
      const stepId = steps[currentStep].id;
      if (lastAutoExpandedStepRef.current !== stepId) {
        setExpandedSteps(prev => new Set(prev).add(stepId));
        lastAutoExpandedStepRef.current = stepId;
      }
    }
  }, [currentStep, steps]);

  useEffect(() => {
    if (!highlightCommandId) return;
    setExpandedCommands(prev => new Set(prev).add(highlightCommandId));
    const el = document.querySelector(
      `[data-command-id="${highlightCommandId}"]`
    ) as HTMLElement | null;
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [highlightCommandId]);

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

  const toggleCommand = (commandId: string) => {
    setExpandedCommands(prev => {
      const next = new Set(prev);
      if (next.has(commandId)) {
        next.delete(commandId);
      } else {
        next.add(commandId);
      }
      return next;
    });
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <Check className="activity-status-icon activity-status-icon--completed" />;
      case 'in_progress':
        return <Loader2 className="activity-status-icon activity-status-icon--progress" />;
      case 'failed':
        return <AlertCircle className="activity-status-icon activity-status-icon--error" />;
      default:
        return <Clock className="activity-status-icon activity-status-icon--pending" />;
    }
  };

  const getOperationColor = (operation: string) => {
    switch (operation) {
      case 'create':
        return 'activity-op activity-op--create';
      case 'modify':
        return 'activity-op activity-op--modify';
      case 'delete':
        return 'activity-op activity-op--delete';
      default:
        return 'activity-op';
    }
  };

  const totalChanges = showFileChanges
    ? steps.reduce((acc, step) => acc + step.fileChanges.length, 0)
    : 0;
  const totalCommands = showCommands
    ? steps.reduce((acc, step) => acc + (step.commands?.length || 0), 0)
    : 0;
  const completedSteps = steps.filter(s => s.status === 'completed').length;
  const emptyLabel = showCommands && showFileChanges
    ? 'No command output or file changes yet.'
    : showCommands
      ? 'No commands yet.'
      : showFileChanges
        ? 'No file changes yet.'
        : 'Nothing to show with current filters.';

  return (
    <div className="activity-panel relative flex flex-col h-full overflow-hidden">
      <div className="activity-panel-grid" aria-hidden="true" />
      <div className="activity-panel-sheen" aria-hidden="true" />
      {/* Header */}
      <div className="activity-panel__header relative px-5 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="activity-panel__title text-lg font-semibold tracking-wide">
              Activity
            </h2>
            <div className="activity-panel__subtitle mt-1 text-xs uppercase tracking-[0.2em]">
              Execution Feed
            </div>
          </div>
          <div className="flex items-center gap-2">
            {onViewHistory && (
              <button
                onClick={onViewHistory}
                className="activity-pill activity-pill--ghost"
              >
                History
              </button>
            )}
            <div className="activity-pill activity-pill--stat">
              {completedSteps}/{steps.length} steps
            </div>
          </div>
        </div>
        <div className="activity-panel__meta mt-3 text-sm">
          {totalChanges} file changes • {totalCommands} command{totalCommands !== 1 ? 's' : ''}
        </div>
        {!showCommands && !showFileChanges && (
          <div className="activity-panel__note mt-2 text-xs">
            Filters hide commands and file changes.
          </div>
        )}

        {/* Progress bar */}
        <div className="activity-progress mt-4 h-2 rounded-full p-[1px]">
          <div
            className="activity-progress__bar h-full rounded-full transition-all duration-300"
            style={{ width: `${(completedSteps / Math.max(steps.length, 1)) * 100}%` }}
          />
        </div>
      </div>

      {/* Steps list */}
      <div className="flex-1 overflow-y-auto">
        {steps.map((step, index) => {
          const isExpanded = expandedSteps.has(step.id);
          const isCurrent = index === currentStep;
          const stepCommands = showCommands ? (step.commands || []) : [];
          const stepFileChanges = showFileChanges ? step.fileChanges : [];

          return (
            <div
              key={step.id}
              className={`activity-step ${isCurrent ? 'activity-step--current' : ''}`}
            >
              {/* Step header */}
              <button
                onClick={() => toggleStep(step.id)}
                className="activity-step-toggle w-full p-4 flex items-start gap-3 transition-colors"
              >
                <div className="mt-0.5">{getStatusIcon(step.status)}</div>

                <div className="flex-1 text-left">
                  <div className="flex items-center gap-2">
                    <span className="activity-step-title font-medium">
                      Step {index + 1}
                    </span>
                    {isCurrent && (
                      <span className="activity-step-badge px-2 py-0.5 text-xs rounded-full">
                        Live
                      </span>
                    )}
                  </div>
                  <p className="activity-step-desc mt-1 text-sm">
                    {step.description}
                  </p>
                  {(stepFileChanges.length > 0 || stepCommands.length > 0) && (
                    <div className="activity-step-meta mt-2 text-xs">
                      {stepFileChanges.length} file{stepFileChanges.length !== 1 ? 's' : ''}
                      {stepCommands.length > 0 ? ` • ${stepCommands.length} command${stepCommands.length !== 1 ? 's' : ''}` : ''}
                    </div>
                  )}
                </div>

                {isExpanded ? (
                  <ChevronDown className="activity-step-chevron w-4 h-4" />
                ) : (
                  <ChevronRight className="activity-step-chevron w-4 h-4" />
                )}
              </button>

              {/* Expanded details */}
              {isExpanded && (
                <div className="activity-step-details px-4 pb-5 space-y-4">
                  {stepFileChanges.length > 0 && (
                    <div className="space-y-2">
                      <div className="activity-section-label text-xs uppercase tracking-[0.2em]">File Changes</div>
                      {stepFileChanges.map((change, idx) => (
                        <div
                          key={idx}
                          className="activity-change-card flex items-center gap-3 rounded-lg p-2 cursor-pointer group"
                          onClick={() => onFileClick?.(change.path)}
                        >
                          <FileCode className="activity-change-icon w-4 h-4" />

                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="activity-change-path text-sm truncate">
                                {change.path}
                              </span>
                              <span className={`text-xs ${getOperationColor(change.operation)}`}>
                                {change.operation}
                              </span>
                            </div>

                            {(change.additions !== undefined || change.deletions !== undefined) && (
                              <div className="activity-change-stats mt-1 flex items-center gap-2 text-xs">
                                {change.additions !== undefined && (
                                  <span className="activity-change-add">
                                    +{change.additions}
                                  </span>
                                )}
                                {change.deletions !== undefined && (
                                  <span className="activity-change-del">
                                    -{change.deletions}
                                  </span>
                                )}
                              </div>
                            )}

                            {change.error && (
                              <div className="activity-change-error mt-1 text-xs">
                                {change.error}
                              </div>
                            )}
                          </div>

                          <div className="activity-change-status opacity-0 group-hover:opacity-100 transition-opacity">
                            {getStatusIcon(change.status)}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {stepCommands.length > 0 && (
                    <div className="space-y-2">
                      <div className="activity-section-label text-xs uppercase tracking-[0.2em]">
                        {showCommandOutput ? 'Command Output' : 'Commands'}
                      </div>
                      {stepCommands.map((command) => {
                        const isCommandExpanded = expandedCommands.has(command.id);
                        const hasOutput = Boolean(command.stdout || command.stderr);
                        const outputVisibleByDefault = Boolean(showCommandOutput || command.status === 'error');
                        const shouldShowOutput = Boolean(outputVisibleByDefault || isCommandExpanded);
                        const outputToggleLabel = outputVisibleByDefault
                          ? (isCommandExpanded ? 'Collapse output' : 'Expand output')
                          : (isCommandExpanded ? 'Hide output' : 'Show output');
                        const isHighlighted = command.id === highlightCommandId;
                        return (
                        <div
                          key={command.id}
                          data-command-id={command.id}
                          className={`activity-command-card rounded-lg p-3 ${isHighlighted ? 'activity-command-card--highlighted' : ''}`}
                        >
                          <div className="flex items-start gap-2">
                            <Terminal className="activity-command-icon w-4 h-4 mt-0.5" />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between gap-2">
                                <span className="activity-command-text text-sm truncate font-mono">
                                  $ {command.command}
                                </span>
                                <div className="flex items-center gap-2">
                                  {onViewInChat && (
                                    <button
                                      className="activity-link-btn text-[11px]"
                                      onClick={() => onViewInChat(command.id)}
                                    >
                                      View in chat
                                    </button>
                                  )}
                                  {typeof command.exitCode === 'number' && (
                                    <span className="activity-command-exit text-xs">
                                      exit {command.exitCode}
                                    </span>
                                  )}
                                  {getStatusIcon(command.status)}
                                </div>
                              </div>
                              {shouldShowOutput && (
                                <div className="activity-command-output mt-2 rounded-md px-3 py-2 text-xs">
                                  {hasOutput ? (
                                    <div className={`activity-command-output-body space-y-2 ${isCommandExpanded ? 'max-h-56 overflow-auto' : 'max-h-20 overflow-hidden'}`}>
                                      {command.stdout && (
                                        <pre className="activity-command-stdout whitespace-pre-wrap">
                                          {command.stdout}
                                        </pre>
                                      )}
                                      {command.stderr && (
                                        <pre className="activity-command-stderr whitespace-pre-wrap">
                                          {command.stderr}
                                        </pre>
                                      )}
                                    </div>
                                  ) : (
                                    <div className="activity-command-empty">No output</div>
                                  )}
                                  {command.truncated && (
                                    <div className="activity-command-truncated mt-2 text-[11px]">Output truncated</div>
                                  )}
                                </div>
                              )}
                              {hasOutput && (
                                <button
                                  onClick={() => toggleCommand(command.id)}
                                  className="activity-link-btn mt-2 inline-flex items-center text-xs"
                                >
                                  {outputToggleLabel}
                                </button>
                              )}
                            </div>
                          </div>
                        </div>
                      )})}
                    </div>
                  )}

                  {stepFileChanges.length === 0 && stepCommands.length === 0 && (
                    <div className="activity-empty-card rounded-lg p-3 text-xs">
                      {emptyLabel}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer actions - only show if there are actual file changes */}
      {completedSteps === steps.length && completedSteps > 0 && totalChanges > 0 && (
        <div className="activity-footer-actions p-4 flex gap-2">
          <button
            onClick={onAcceptAll}
            className="activity-footer-btn activity-footer-btn--accept flex-1 px-4 py-2 rounded-lg transition-colors text-sm font-medium"
          >
            Accept All Changes
          </button>
          <button
            onClick={onRejectAll}
            className="activity-footer-btn activity-footer-btn--reject px-4 py-2 rounded-lg transition-colors text-sm font-medium"
          >
            Reject
          </button>
        </div>
      )}
    </div>
  );
}
