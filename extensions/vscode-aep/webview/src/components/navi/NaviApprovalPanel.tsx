import React, { useEffect, useMemo, useState } from 'react';
import * as vscodeApi from '../../utils/vscodeApi';

export type RiskLevel = 'low' | 'medium' | 'high';

export interface ActionWithRisk {
  type: 'createFile' | 'editFile' | 'runCommand';
  path?: string;
  command?: string;
  content?: string;
  risk: RiskLevel;
  warnings: string[];
  preview?: string;
}

interface NaviApprovalPanelProps {
  planId: string;
  message: string;
  actionsWithRisk: ActionWithRisk[];
  onApprove: (selectedIndices: number[]) => void;
  onReject: () => void;
  onShowDiff: (actionIndex: number) => void;
}

export const NaviApprovalPanel: React.FC<NaviApprovalPanelProps> = ({
  planId,
  message,
  actionsWithRisk,
  onApprove,
  onReject,
  onShowDiff,
}) => {
  const [completedActions, setCompletedActions] = useState<Set<number>>(new Set());
  const [inFlight, setInFlight] = useState(false);
  const [lastApprovedIndex, setLastApprovedIndex] = useState<number | null>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);

  useEffect(() => {
    setCompletedActions(new Set());
    setInFlight(false);
    setLastApprovedIndex(null);
    setExecutionError(null);
  }, [planId, actionsWithRisk]);

  useEffect(() => {
    const unsubscribe = vscodeApi.onMessage((msg) => {
      if (!msg || typeof msg !== 'object') return;
      if (msg.type === 'navi.execution.complete' && msg.planId === planId) {
        const indices = Array.isArray(msg.approvedActionIndices)
          ? msg.approvedActionIndices
          : lastApprovedIndex !== null
            ? [lastApprovedIndex]
            : [];
        if (indices.length > 0) {
          setCompletedActions((prev) => {
            const next = new Set(prev);
            indices.forEach((idx: number) => next.add(idx));
            return next;
          });
        }
        setInFlight(false);
        setLastApprovedIndex(null);
        setExecutionError(null);
      }
      if (msg.type === 'navi.execution.error' && msg.planId === planId) {
        setInFlight(false);
        setExecutionError(msg.error || 'Execution failed.');
      }
      if (msg.type === 'navi.plan.rejected' && msg.planId === planId) {
        setInFlight(false);
      }
    });

    return () => {
      unsubscribe();
    };
  }, [planId, lastApprovedIndex]);

  const pendingIndices = useMemo(
    () => actionsWithRisk.map((_, i) => i).filter((i) => !completedActions.has(i)),
    [actionsWithRisk, completedActions]
  );
  const currentIndex = pendingIndices.length > 0 ? pendingIndices[0] : null;
  const currentAction = currentIndex !== null ? actionsWithRisk[currentIndex] : null;
  const completedCount = actionsWithRisk.length - pendingIndices.length;

  const getRiskColor = (risk: RiskLevel) => {
    switch (risk) {
      case 'low':
        return '#4FC08D';
      case 'medium':
        return '#FFB454';
      case 'high':
        return '#FF6B6B';
      default:
        return '#888';
    }
  };

  const getRiskIcon = (risk: RiskLevel) => {
    switch (risk) {
      case 'low':
        return '✓';
      case 'medium':
        return '⚠';
      case 'high':
        return '⚠';
      default:
        return '•';
    }
  };

  const getActionTypeLabel = (type: string) => {
    switch (type) {
      case 'createFile':
        return 'CREATE FILE';
      case 'editFile':
        return 'EDIT FILE';
      case 'runCommand':
        return 'RUN COMMAND';
      default:
        return 'ACTION';
    }
  };

  const handleApproveCurrent = () => {
    if (currentIndex === null || inFlight) return;
    setInFlight(true);
    setExecutionError(null);
    setLastApprovedIndex(currentIndex);
    onApprove([currentIndex]);
  };

  return (
    <div className="navi-approval-panel">
      <div className="approval-header">
        <h3>Review Proposed Changes</h3>
        <p className="user-message">{message}</p>
      </div>

      <div className="approval-progress">
        {actionsWithRisk.length === 0
          ? 'No actions to approve.'
          : `Action ${Math.min(completedCount + 1, actionsWithRisk.length)} of ${actionsWithRisk.length} · ${pendingIndices.length} remaining`}
      </div>

      {executionError && (
        <div className="approval-error">
          ⚠ {executionError}
        </div>
      )}

      {currentAction ? (
        <div
          className={`action-item risk-${currentAction.risk}`}
          style={{
            borderLeftColor: getRiskColor(currentAction.risk),
          }}
        >
          <div className="action-row">
            <div className="action-content">
              <div className="action-header">
                <span
                  className="risk-indicator"
                  style={{ color: getRiskColor(currentAction.risk) }}
                >
                  <span className="risk-icon">{getRiskIcon(currentAction.risk)}</span>
                  <span className="risk-text">{currentAction.risk.toUpperCase()} RISK</span>
                </span>
                <span className="action-type">{getActionTypeLabel(currentAction.type)}</span>
              </div>

              <div className="action-details">
                {(currentAction.type === 'createFile' || currentAction.type === 'editFile') && currentAction.path && (
                  <div>
                    <strong>{currentAction.type === 'createFile' ? 'Create:' : 'Edit:'}</strong>{' '}
                    <code>{currentAction.path}</code>
                    <button
                      className="show-diff-btn"
                      onClick={() => {
                        if (currentIndex !== null) {
                          onShowDiff(currentIndex);
                        }
                      }}
                      title="Open diff view in VS Code"
                    >
                      Review Diff
                    </button>
                  </div>
                )}

                {currentAction.type === 'runCommand' && currentAction.command && (
                  <div>
                    <strong>Run:</strong>
                    <pre className="command">{currentAction.command}</pre>
                  </div>
                )}

                {currentAction.preview && (
                  <details className="preview-details">
                    <summary>Show preview</summary>
                    <pre className="preview">{currentAction.preview}</pre>
                  </details>
                )}
              </div>

              {currentAction.warnings && currentAction.warnings.length > 0 && (
                <div className="warnings">
                  {currentAction.warnings.map((warning, i) => (
                    <div key={i} className="warning">
                      ⚠ {warning}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="approval-complete">
          ✅ All approved actions have been processed.
        </div>
      )}

      <div className="approval-actions">
        <button
          className="approve-btn"
          onClick={handleApproveCurrent}
          disabled={currentIndex === null || inFlight}
        >
          {inFlight ? 'Running...' : 'Approve & Run'}
        </button>
        <button className="reject-btn" onClick={onReject}>
          Reject Plan
        </button>
      </div>

      <style>{`
        .navi-approval-panel {
          border: 2px solid var(--vscode-panel-border);
          border-radius: 8px;
          padding: 16px;
          margin: 16px 0;
          background: var(--vscode-editor-background);
        }

        .approval-header h3 {
          margin: 0 0 8px 0;
          font-size: 16px;
          font-weight: 600;
          color: var(--vscode-foreground);
        }

        .user-message {
          font-size: 13px;
          color: var(--vscode-descriptionForeground);
          margin: 0 0 16px 0;
          padding: 8px 12px;
          background: rgba(79, 192, 141, 0.08);
          border-left: 3px solid rgba(79, 192, 141, 0.5);
          border-radius: 4px;
          font-style: italic;
        }

        .approval-progress {
          margin: 8px 0 12px;
          font-size: 12px;
          color: var(--vscode-descriptionForeground);
        }

        .approval-error {
          margin: 8px 0 12px;
          padding: 8px 10px;
          border-radius: 6px;
          background: rgba(248, 113, 113, 0.12);
          border: 1px solid rgba(248, 113, 113, 0.35);
          color: #fecaca;
          font-size: 12px;
        }

        .approval-complete {
          margin: 12px 0;
          font-size: 12px;
          color: var(--vscode-descriptionForeground);
        }

        .action-item {
          padding: 12px;
          border: 1px solid var(--vscode-panel-border);
          border-left-width: 4px;
          border-radius: 6px;
          margin-bottom: 8px;
          transition: all 0.2s;
        }

        .action-item:hover {
          border-color: var(--vscode-focusBorder);
          background: rgba(79, 192, 141, 0.03);
        }

        .action-row {
          display: flex;
          gap: 12px;
          align-items: flex-start;
        }

        .action-content {
          flex: 1;
          min-width: 0;
        }

        .action-header {
          display: flex;
          gap: 12px;
          align-items: center;
          margin-bottom: 8px;
          flex-wrap: wrap;
        }

        .risk-indicator {
          display: flex;
          align-items: center;
          gap: 4px;
          font-size: 11px;
          font-weight: 600;
          letter-spacing: 0.5px;
        }

        .risk-icon {
          font-size: 14px;
        }

        .action-type {
          font-size: 11px;
          color: var(--vscode-descriptionForeground);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          background: var(--vscode-badge-background);
          padding: 2px 6px;
          border-radius: 3px;
        }

        .action-details {
          font-size: 13px;
          line-height: 1.6;
          color: var(--vscode-foreground);
        }

        .action-details strong {
          color: var(--vscode-descriptionForeground);
          font-weight: 500;
        }

        .action-details code {
          font-family: var(--vscode-editor-font-family);
          font-size: 12px;
          background: var(--vscode-textCodeBlock-background);
          padding: 2px 6px;
          border-radius: 3px;
          color: var(--vscode-textPreformat-foreground);
        }

        .preview-details {
          margin-top: 8px;
        }

        .preview-details summary {
          cursor: pointer;
          font-size: 12px;
          color: var(--vscode-textLink-foreground);
          user-select: none;
        }

        .preview-details summary:hover {
          text-decoration: underline;
        }

        .preview {
          margin-top: 8px;
          padding: 8px;
          background: var(--vscode-textCodeBlock-background);
          border-radius: 4px;
          font-family: var(--vscode-editor-font-family);
          font-size: 12px;
          overflow-x: auto;
          max-height: 200px;
          overflow-y: auto;
          border: 1px solid var(--vscode-panel-border);
        }

        .command {
          margin: 4px 0 0 0;
          padding: 6px 8px;
          background: var(--vscode-terminal-background);
          border-radius: 4px;
          font-family: var(--vscode-editor-font-family);
          font-size: 12px;
          color: var(--vscode-terminal-foreground);
          border: 1px solid var(--vscode-panel-border);
        }

        .show-diff-btn {
          margin-left: 8px;
          padding: 4px 10px;
          background: var(--vscode-button-background);
          color: var(--vscode-button-foreground);
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 11px;
          font-weight: 500;
          transition: background 0.2s;
        }

        .show-diff-btn:hover {
          background: var(--vscode-button-hoverBackground);
        }

        .warnings {
          margin-top: 8px;
          padding: 8px 10px;
          background: rgba(255, 107, 107, 0.1);
          border-left: 3px solid #FF6B6B;
          border-radius: 4px;
        }

        .warning {
          font-size: 12px;
          color: var(--vscode-errorForeground);
          margin-bottom: 4px;
          line-height: 1.4;
        }

        .warning:last-child {
          margin-bottom: 0;
        }

        .approval-actions {
          display: flex;
          gap: 12px;
          margin-top: 16px;
          padding-top: 16px;
          border-top: 1px solid var(--vscode-panel-border);
        }

        .approve-btn,
        .reject-btn {
          padding: 8px 16px;
          border-radius: 4px;
          border: none;
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
        }

        .approve-btn {
          background: var(--vscode-button-background);
          color: var(--vscode-button-foreground);
          flex: 1;
        }

        .approve-btn:hover:not(:disabled) {
          background: var(--vscode-button-hoverBackground);
        }

        .approve-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .reject-btn {
          background: transparent;
          border: 1px solid var(--vscode-button-border);
          color: var(--vscode-foreground);
          min-width: 120px;
        }

        .reject-btn:hover {
          background: rgba(255, 107, 107, 0.1);
          border-color: #FF6B6B;
        }
      `}</style>
    </div>
  );
};
