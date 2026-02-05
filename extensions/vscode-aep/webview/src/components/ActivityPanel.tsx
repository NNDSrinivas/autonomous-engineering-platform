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
    <div
      className="activity-panel relative flex flex-col h-full border-l border-white/10 bg-[#0c1117] text-slate-100 overflow-hidden"
      style={{
        backgroundImage:
          "linear-gradient(rgba(148,163,184,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.06) 1px, transparent 1px)",
        backgroundSize: "20px 20px, 20px 20px",
        backgroundPosition: "0 0, 0 0",
      }}
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-20"
        style={{
          backgroundImage:
            "linear-gradient(transparent 0%, rgba(56,189,248,0.12) 48%, transparent 100%)",
          backgroundSize: "100% 120px",
        }}
      />
      {/* Header */}
      <div className="relative px-5 py-4 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold tracking-wide text-slate-100">
              Activity
            </h2>
            <div className="mt-1 text-xs uppercase tracking-[0.2em] text-slate-400/70">
              Execution Feed
            </div>
          </div>
          <div className="flex items-center gap-2">
            {onViewHistory && (
              <button
                onClick={onViewHistory}
                className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200 hover:bg-white/10 transition-colors"
              >
                History
              </button>
            )}
            <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200">
              {completedSteps}/{steps.length} steps
            </div>
          </div>
        </div>
        <div className="mt-3 text-sm text-slate-300/80">
          {totalChanges} file changes • {totalCommands} command{totalCommands !== 1 ? 's' : ''}
        </div>
        {!showCommands && !showFileChanges && (
          <div className="mt-2 text-xs text-slate-400/80">
            Filters hide commands and file changes.
          </div>
        )}

        {/* Progress bar */}
        <div className="mt-4 h-2 rounded-full bg-white/5 p-[1px]">
          <div
            className="h-full rounded-full bg-gradient-to-r from-sky-400 via-blue-500 to-cyan-300 transition-all duration-300"
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
              className={`border-b border-white/5 ${isCurrent ? 'bg-white/5 shadow-[inset_0_0_0_1px_rgba(56,189,248,0.2)]' : ''}`}
            >
              {/* Step header */}
              <button
                onClick={() => toggleStep(step.id)}
                className="w-full p-4 flex items-start gap-3 transition-colors hover:bg-white/5"
              >
                <div className="mt-0.5">{getStatusIcon(step.status)}</div>

                <div className="flex-1 text-left">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-100">
                      Step {index + 1}
                    </span>
                    {isCurrent && (
                      <span className="px-2 py-0.5 text-xs rounded-full border border-sky-400/40 bg-sky-400/10 text-sky-100">
                        Live
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-sm text-slate-300/80">
                    {step.description}
                  </p>
                  {(stepFileChanges.length > 0 || stepCommands.length > 0) && (
                    <div className="mt-2 text-xs text-slate-400/70">
                      {stepFileChanges.length} file{stepFileChanges.length !== 1 ? 's' : ''}
                      {stepCommands.length > 0 ? ` • ${stepCommands.length} command${stepCommands.length !== 1 ? 's' : ''}` : ''}
                    </div>
                  )}
                </div>

                {isExpanded ? (
                  <ChevronDown className="w-4 h-4 text-gray-400" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-gray-400" />
                )}
              </button>

              {/* Expanded details */}
              {isExpanded && (
                <div className="px-4 pb-5 space-y-4">
                  {stepFileChanges.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-xs uppercase tracking-[0.2em] text-slate-400/70">File Changes</div>
                      {stepFileChanges.map((change, idx) => (
                        <div
                          key={idx}
                          className="flex items-center gap-3 rounded-lg border border-white/5 bg-white/5 p-2 hover:bg-white/10 cursor-pointer group"
                          onClick={() => onFileClick?.(change.path)}
                        >
                          <FileCode className="w-4 h-4 text-slate-200" />

                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-slate-100 truncate">
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
                          <div className="mt-1 text-xs text-rose-400">
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

                  {stepCommands.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-xs uppercase tracking-[0.2em] text-slate-400/70">
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
                          className={`rounded-lg border border-white/10 bg-[#0b1118] p-3 ${isHighlighted ? 'ring-1 ring-sky-400/60 bg-sky-500/5' : ''}`}
                        >
                          <div className="flex items-start gap-2">
                            <Terminal className="w-4 h-4 text-slate-200 mt-0.5" />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between gap-2">
                                <span className="text-sm text-slate-100 truncate font-mono">
                                  $ {command.command}
                                </span>
                                <div className="flex items-center gap-2">
                                  {onViewInChat && (
                                    <button
                                      className="text-[11px] text-slate-300 hover:text-slate-100"
                                      onClick={() => onViewInChat(command.id)}
                                    >
                                      View in chat
                                    </button>
                                  )}
                                  {typeof command.exitCode === 'number' && (
                                    <span className="text-xs text-slate-400">
                                      exit {command.exitCode}
                                    </span>
                                  )}
                                  {getStatusIcon(command.status)}
                                </div>
                              </div>
                              {shouldShowOutput && (
                                <div className="mt-2 rounded-md border border-white/5 bg-[#0e1622] px-3 py-2 text-xs">
                                  {hasOutput ? (
                                    <div className={`space-y-2 ${isCommandExpanded ? 'max-h-56 overflow-auto' : 'max-h-20 overflow-hidden'}`}>
                                      {command.stdout && (
                                        <pre className="whitespace-pre-wrap text-slate-200">
                                          {command.stdout}
                                        </pre>
                                      )}
                                      {command.stderr && (
                                        <pre className="whitespace-pre-wrap text-rose-400">
                                          {command.stderr}
                                        </pre>
                                      )}
                                    </div>
                                  ) : (
                                    <div className="text-slate-400">No output</div>
                                  )}
                                  {command.truncated && (
                                    <div className="mt-2 text-[11px] text-slate-400">Output truncated</div>
                                  )}
                                </div>
                              )}
                              {hasOutput && (
                                <button
                                  onClick={() => toggleCommand(command.id)}
                                  className="mt-2 inline-flex items-center text-xs text-slate-300 hover:text-slate-100"
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
                    <div className="rounded-lg border border-white/5 bg-white/5 p-3 text-xs text-slate-400">
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
