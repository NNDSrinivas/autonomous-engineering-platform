import React, { useEffect, useMemo, useState } from 'react';
import * as vscodeApi from '../../utils/vscodeApi';
import { InlineCommandApproval } from './InlineCommandApproval';
import { InlineFileApproval } from './InlineFileApproval';

interface NaviAction {
  id?: string;
  title?: string;
  description?: string;
  intent_kind?: string;
  type?: string;
  filePath?: string;
  command?: string;
  content?: string;
  diff?: string;
  cwd?: string;
  meta?: {
    kind?: string;
    threshold?: number;
    [key: string]: any;
  };
}

// Activity event for inline display with each action
interface ActionActivity {
  id: string;
  kind: string;
  label: string;
  detail?: string;
  status?: 'running' | 'done' | 'error';
  timestamp: string;
  actionIndex?: number;  // Which action this activity belongs to
}

// Streaming narrative text for conversational output
interface StreamingNarrative {
  id: string;
  text: string;
  actionIndex?: number;
  timestamp: string;
}

interface NaviActionRunnerProps {
  actions: NaviAction[];
  messageId: string;
  onRunAction: (action: NaviAction, actionIndex: number) => void;
  onAllComplete?: () => void;  // Called when all actions are completed or skipped
  // New: activities grouped by action index
  actionActivities?: Map<number, ActionActivity[]>;
  // New: streaming narrative text per action
  narratives?: Map<number, StreamingNarrative[]>;
}

type ActionStatus = 'pending' | 'running' | 'completed' | 'skipped' | 'error';

export function NaviActionRunner({
  actions,
  messageId,
  onRunAction,
  onAllComplete,
  actionActivities = new Map(),
  narratives = new Map()
}: NaviActionRunnerProps) {
  if (!actions || actions.length === 0) {
    return null;
  }

  // Track status for each action by index
  const [actionStatuses, setActionStatuses] = useState<Map<number, ActionStatus>>(new Map());

  const actionSignatures = useMemo(
    () =>
      actions.map((action) => {
        const type = action.type || action.intent_kind || '';
        const path = action.filePath || '';
        const command = action.command || '';
        return `${type}|${path}|${command}|${action.title || ''}`;
      }),
    [actions]
  );

  // Reset state when message or actions change
  useEffect(() => {
    setActionStatuses(new Map());
  }, [messageId, actions]);

  // Listen for action completion messages
  useEffect(() => {
    const unsubscribe = vscodeApi.onMessage((msg) => {
      if (!msg || typeof msg !== 'object') return;
      if (msg.type !== 'action.complete') return;
      const actionIndex = typeof msg.actionIndex === 'number' ? msg.actionIndex : undefined;
      if (actionIndex === undefined) return;
      if (!actions[actionIndex]) return;

      const incoming = msg.action || {};
      const incomingSignature = `${incoming.type || incoming.intent_kind || ''}|${incoming.filePath || ''}|${incoming.command || ''}|${incoming.title || ''}`;
      const expectedSignature = actionSignatures[actionIndex];

      if (incomingSignature !== expectedSignature && incoming.id && actions[actionIndex].id !== incoming.id) {
        return;
      }

      // Mark action as completed or error based on success flag
      const newStatus: ActionStatus = msg.success === false ? 'error' : 'completed';
      setActionStatuses((prev) => {
        const next = new Map(prev);
        next.set(actionIndex, newStatus);
        return next;
      });
    });

    return () => {
      unsubscribe();
    };
  }, [actions, actionSignatures]);

  // Find the current action index (first one that's not completed or skipped)
  const currentIndex = actions.findIndex((_, index) => {
    const status = actionStatuses.get(index);
    return !status || status === 'pending' || status === 'running';
  });

  // Calculate completion status
  const completedCount = Array.from(actionStatuses.values()).filter(s => s === 'completed').length;
  const skippedCount = Array.from(actionStatuses.values()).filter(s => s === 'skipped').length;
  const errorCount = Array.from(actionStatuses.values()).filter(s => s === 'error').length;
  const allDone = completedCount + skippedCount + errorCount === actions.length;

  // Notify parent when all actions are done
  useEffect(() => {
    if (allDone && onAllComplete) {
      onAllComplete();
    }
  }, [allDone, onAllComplete]);

  const isCommandAction = (action: NaviAction): boolean => {
    const type = action.type || action.intent_kind || '';
    return type === 'runCommand' || type === 'command';
  };

  const isFileAction = (action: NaviAction): 'edit' | 'create' | null => {
    const type = action.type || action.intent_kind || '';
    if (type === 'editFile' || type === 'edit') return 'edit';
    if (type === 'createFile' || type === 'create') return 'create';
    return null;
  };

  const handleAllow = (action: NaviAction, index: number) => {
    // Mark as running
    setActionStatuses((prev) => {
      const next = new Map(prev);
      next.set(index, 'running');
      return next;
    });
    onRunAction(action, index);
  };

  const handleSkip = (index: number) => {
    setActionStatuses((prev) => {
      const next = new Map(prev);
      next.set(index, 'skipped');
      return next;
    });
  };

  const handleShowDiff = (action: NaviAction) => {
    vscodeApi.postMessage({
      type: 'showDiff',
      filePath: action.filePath,
      content: action.content,
      diff: action.diff,
    });
  };

  const getActionStatus = (index: number): ActionStatus => {
    return actionStatuses.get(index) || 'pending';
  };

  // Convert our status to InlineCommandApproval status
  const toApprovalStatus = (status: ActionStatus): 'pending' | 'running' | 'completed' | 'error' => {
    if (status === 'skipped') return 'completed';
    return status;
  };

  // Render inline activities and narratives for an action (shown during and after execution)
  const renderActionActivities = (index: number, action: NaviAction, status: ActionStatus) => {
    const activities = actionActivities.get(index) || [];
    const actionNarratives = narratives.get(index) || [];

    // Show the action's description as a narrative if:
    // 1. Action is running and we have no explicit narratives yet
    // 2. The action has a description from the LLM
    const showDescriptionAsNarrative = status === 'running' &&
      actionNarratives.length === 0 &&
      action.description;

    if (activities.length === 0 && actionNarratives.length === 0 && !showDescriptionAsNarrative) {
      return null;
    }

    return (
      <div className={`action-inline-activities ${status === 'running' ? 'action-inline-activities--running' : ''}`}>
        {/* Show action description as narrative while running if no explicit narratives */}
        {showDescriptionAsNarrative && (
          <div className="action-narrative action-narrative--streaming">
            <div className="narrative-spinner" />
            <span className="narrative-text">{action.description}</span>
          </div>
        )}
        {/* Show streaming narratives for this action */}
        {actionNarratives.map((narrative) => (
          <div key={narrative.id} className={`action-narrative ${status === 'running' ? 'action-narrative--streaming' : ''}`}>
            {status === 'running' && <div className="narrative-spinner" />}
            <span className="narrative-text">{narrative.text}</span>
          </div>
        ))}
        {/* Show activity events for this action */}
        {activities.map((activity) => (
          <div
            key={activity.id}
            className={`action-activity action-activity--${activity.status || 'done'}`}
          >
            {activity.status === 'running' ? (
              <div className="activity-spinner-sm" />
            ) : activity.status === 'error' ? (
              <span className="activity-icon activity-icon--error">✗</span>
            ) : (
              <span className="activity-icon activity-icon--done">✓</span>
            )}
            <span className="activity-label">{activity.label}</span>
            {activity.detail && (
              <span className="activity-detail">{activity.detail}</span>
            )}
          </div>
        ))}
      </div>
    );
  };

  const renderAction = (action: NaviAction, index: number) => {
    const status = getActionStatus(index);
    const approvalStatus = toApprovalStatus(status);

    // For skipped actions, show a minimal indicator
    if (status === 'skipped') {
      return (
        <div key={index} className="action-item-wrapper">
          <div className="action-skipped">
            <span className="action-skipped-icon">⊘</span>
            <span className="action-skipped-label">Skipped: {action.command || action.filePath || 'action'}</span>
          </div>
        </div>
      );
    }

    if (isCommandAction(action)) {
      return (
        <div key={index} className="action-item-wrapper">
          <InlineCommandApproval
            command={action.command || ''}
            shell="zsh"
            status={approvalStatus}
            onAllow={() => handleAllow(action, index)}
            onSkip={() => handleSkip(index)}
            onFocusTerminal={() => {
              vscodeApi.postMessage({
                type: 'focusTerminal',
                command: action.command,
              });
            }}
            onShowOutput={() => {
              vscodeApi.postMessage({
                type: 'showOutput',
                command: action.command,
              });
            }}
            onAlwaysAllowCommand={(cmd) => {
              console.log('Always allow command:', cmd);
            }}
            onAlwaysAllowExact={(cmd) => {
              console.log('Always allow exact:', cmd);
            }}
            onEnableAutoApprove={() => {
              console.log('Enable auto approve');
            }}
            onConfigureAutoApprove={() => {
              console.log('Configure auto approve');
            }}
          />
          {/* Show activities/narratives inline during and after action execution */}
          {(status === 'running' || status === 'completed' || status === 'error') && renderActionActivities(index, action, status)}
        </div>
      );
    }

    const fileActionType = isFileAction(action);
    if (fileActionType) {
      return (
        <div key={index} className="action-item-wrapper">
          <InlineFileApproval
            type={fileActionType}
            filePath={action.filePath || 'unknown'}
            status={approvalStatus}
            onAllow={() => handleAllow(action, index)}
            onSkip={() => handleSkip(index)}
            onShowDiff={() => handleShowDiff(action)}
            onAlwaysAllowFile={(path) => {
              console.log('Always allow file:', path);
            }}
            onAlwaysAllowPattern={(pattern) => {
              console.log('Always allow pattern:', pattern);
            }}
          />
          {/* Show activities/narratives inline during and after action execution */}
          {(status === 'running' || status === 'completed' || status === 'error') && renderActionActivities(index, action, status)}
        </div>
      );
    }

    // Fallback for other action types
    const getActionIcon = (): string => {
      const type = action.type || action.intent_kind || '';
      switch (type) {
        case 'deleteFile':
        case 'delete':
          return '🗑️';
        default:
          return '▶️';
      }
    };

    const getActionLabel = (): string => {
      if (action.title) return action.title;
      return action.description || 'Run action';
    };

    return (
      <div key={index} className="action-item-wrapper">
        <div className={`generic-action-approval ${status === 'completed' ? 'generic-action-approval--completed' : ''}`}>
          <div className="action-header">
            <span className="action-icon">
              {status === 'completed' ? '✓' : status === 'error' ? '✗' : getActionIcon()}
            </span>
            <span className="action-label">{getActionLabel()}</span>
          </div>
          {status === 'pending' && (
            <div className="action-buttons">
              <button
                className="allow-btn"
                onClick={() => handleAllow(action, index)}
              >
                Allow
              </button>
              <button
                className="skip-btn"
                onClick={() => handleSkip(index)}
              >
                Skip
              </button>
            </div>
          )}
          {status === 'running' && (
            <div className="action-running-indicator">
              <div className="action-spinner" /> Running...
            </div>
          )}
        </div>
        {/* Show activities/narratives inline during and after action execution */}
        {(status === 'running' || status === 'completed' || status === 'error') && renderActionActivities(index, action, status)}
      </div>
    );
  };

  // Get actions to render: completed/skipped ones + current one only
  const actionsToRender: number[] = [];
  for (let i = 0; i < actions.length; i++) {
    const status = getActionStatus(i);
    if (status === 'completed' || status === 'skipped' || status === 'error') {
      // Always show completed/skipped/error actions
      actionsToRender.push(i);
    } else if (i === currentIndex) {
      // Show the current pending/running action
      actionsToRender.push(i);
      break; // Don't show any actions after the current one
    }
  }

  return (
    <div className="navi-action-runner">
      {actions.length > 1 && (
        <div className="action-progress">
          {completedCount + skippedCount} of {actions.length} actions completed
        </div>
      )}

      <div className="actions-list">
        {actionsToRender.map((index) => renderAction(actions[index], index))}
      </div>

      <style>{`
        .navi-action-runner {
          margin-top: 8px;
        }
        .action-progress {
          font-size: 11px;
          color: var(--vscode-descriptionForeground);
          margin-bottom: 8px;
        }
        .actions-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .action-skipped {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 12px;
          background: var(--vscode-editor-background, #1e1e1e);
          border: 1px solid var(--vscode-panel-border, #3c3c3c);
          border-radius: 6px;
          opacity: 0.6;
          font-size: 12px;
        }
        .action-skipped-icon {
          color: var(--vscode-descriptionForeground);
        }
        .action-skipped-label {
          color: var(--vscode-descriptionForeground);
        }
        .generic-action-approval {
          background: var(--vscode-editor-background, #1e1e1e);
          border: 1px solid var(--vscode-panel-border, #3c3c3c);
          border-radius: 8px;
          padding: 12px 16px;
        }
        .generic-action-approval--completed {
          border-color: rgba(74, 222, 128, 0.3);
          background: rgba(74, 222, 128, 0.05);
        }
        .action-header {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 13px;
        }
        .action-icon {
          font-size: 14px;
        }
        .action-label {
          color: var(--vscode-foreground);
        }
        .action-buttons {
          display: flex;
          gap: 8px;
          margin-top: 12px;
        }
        .allow-btn {
          background: #3794ff;
          color: white;
          border: none;
          padding: 6px 14px;
          font-size: 12px;
          font-weight: 500;
          border-radius: 4px;
          cursor: pointer;
        }
        .allow-btn:hover:not(:disabled) {
          background: #2a7ed8;
        }
        .allow-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
        .skip-btn {
          background: var(--vscode-button-secondaryBackground, #3a3d41);
          color: var(--vscode-button-secondaryForeground, #cccccc);
          border: none;
          padding: 6px 14px;
          font-size: 12px;
          font-weight: 500;
          border-radius: 4px;
          cursor: pointer;
        }
        .skip-btn:hover {
          background: var(--vscode-button-secondaryHoverBackground, #45494e);
        }
        .action-running-indicator {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 12px;
          color: var(--vscode-descriptionForeground);
          margin-top: 8px;
        }
        .action-spinner {
          width: 12px;
          height: 12px;
          border: 2px solid rgba(55, 148, 255, 0.3);
          border-top-color: #3794ff;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        /* Action item wrapper for grouping action + its activities */
        .action-item-wrapper {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        /* Inline activities shown after each completed action */
        .action-inline-activities {
          display: flex;
          flex-direction: column;
          gap: 4px;
          margin-left: 16px;
          padding-left: 12px;
          border-left: 2px solid rgba(74, 222, 128, 0.3);
        }

        .action-activity {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 4px 8px;
          font-size: 12px;
          color: var(--vscode-foreground, #cccccc);
          background: transparent;
        }

        .action-activity--done {
          color: var(--vscode-foreground, #cccccc);
        }

        .action-activity--running {
          color: var(--vscode-textLink-foreground, #3794ff);
        }

        .action-activity--error {
          color: #ef4444;
        }

        .activity-spinner-sm {
          width: 10px;
          height: 10px;
          border: 2px solid rgba(55, 148, 255, 0.3);
          border-top-color: #3794ff;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
          flex-shrink: 0;
        }

        .activity-icon {
          flex-shrink: 0;
          font-size: 11px;
        }

        .activity-icon--done {
          color: #4ade80;
        }

        .activity-icon--error {
          color: #ef4444;
        }

        .activity-label {
          font-weight: 500;
          color: var(--vscode-foreground, #cccccc);
        }

        .activity-detail {
          color: var(--vscode-descriptionForeground, #8b8b8b);
          font-size: 11px;
          margin-left: 4px;
        }

        /* Running state for activities container */
        .action-inline-activities--running {
          border-left-color: rgba(55, 148, 255, 0.5);
        }

        /* Streaming narrative text (like Cline/Claude conversational output) */
        .action-narrative {
          display: flex;
          align-items: flex-start;
          gap: 8px;
          padding: 8px 12px;
          font-size: 13px;
          line-height: 1.5;
          color: var(--vscode-foreground, #cccccc);
          background: var(--vscode-textCodeBlock-background, rgba(30, 30, 30, 0.5));
          border-radius: 6px;
        }

        .action-narrative--streaming {
          background: linear-gradient(135deg, rgba(55, 148, 255, 0.08) 0%, rgba(55, 148, 255, 0.03) 100%);
          border: 1px solid rgba(55, 148, 255, 0.2);
        }

        .narrative-spinner {
          width: 12px;
          height: 12px;
          border: 2px solid rgba(55, 148, 255, 0.3);
          border-top-color: #3794ff;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
          flex-shrink: 0;
          margin-top: 3px;
        }

        .narrative-text {
          color: var(--vscode-foreground, #cccccc);
          flex: 1;
        }
      `}</style>
    </div>
  );
}

export default NaviActionRunner;
