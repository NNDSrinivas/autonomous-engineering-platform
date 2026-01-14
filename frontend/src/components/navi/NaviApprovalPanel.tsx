import React, { useState } from 'react';

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
  onShowDiff?: (actionIndex: number) => void;
}

export const NaviApprovalPanel: React.FC<NaviApprovalPanelProps> = ({
  planId,
  message,
  actionsWithRisk,
  onApprove,
  onReject,
  onShowDiff,
}) => {
  const [selectedActions, setSelectedActions] = useState<Set<number>>(
    new Set(actionsWithRisk.map((_, i) => i))
  );

  const toggleAction = (index: number) => {
    const newSelected = new Set(selectedActions);
    if (newSelected.has(index)) {
      newSelected.delete(index);
    } else {
      newSelected.add(index);
    }
    setSelectedActions(newSelected);
  };

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

  return (
    <div className="navi-approval-panel">
      <div className="approval-header">
        <h3>Review Proposed Changes</h3>
        <p className="user-message">{message}</p>
      </div>

      <div className="actions-list">
        {actionsWithRisk.map((action, index) => (
          <div
            key={index}
            className={`action-item risk-${action.risk}`}
            style={{
              borderLeftColor: getRiskColor(action.risk),
            }}
          >
            <div className="action-row">
              <div className="action-select">
                <input
                  type="checkbox"
                  checked={selectedActions.has(index)}
                  onChange={() => toggleAction(index)}
                  id={`action-${index}`}
                />
              </div>

              <div className="action-content">
                <div className="action-header">
                  <span
                    className="risk-indicator"
                    style={{ color: getRiskColor(action.risk) }}
                  >
                    <span className="risk-icon">{getRiskIcon(action.risk)}</span>
                    <span className="risk-text">{action.risk.toUpperCase()} RISK</span>
                  </span>
                  <span className="action-type">{getActionTypeLabel(action.type)}</span>
                </div>

                <div className="action-details">
                  {action.type === 'createFile' && action.path && (
                    <div>
                      <strong>Create:</strong> <code>{action.path}</code>
                      {action.preview && (
                        <details className="preview-details">
                          <summary>Show preview</summary>
                          <pre className="preview">{action.preview}</pre>
                        </details>
                      )}
                    </div>
                  )}

                  {action.type === 'editFile' && action.path && (
                    <div>
                      <strong>Edit:</strong> <code>{action.path}</code>
                      {onShowDiff && (
                        <button
                          className="show-diff-btn"
                          onClick={() => onShowDiff(index)}
                          title="Show diff preview"
                        >
                          Show Diff
                        </button>
                      )}
                    </div>
                  )}

                  {action.type === 'runCommand' && action.command && (
                    <div>
                      <strong>Run:</strong>
                      <pre className="command">{action.command}</pre>
                    </div>
                  )}
                </div>

                {action.warnings && action.warnings.length > 0 && (
                  <div className="warnings">
                    {action.warnings.map((warning, i) => (
                      <div key={i} className="warning">
                        ⚠ {warning}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="approval-actions">
        <button
          className="approve-btn"
          onClick={() => onApprove(Array.from(selectedActions))}
          disabled={selectedActions.size === 0}
        >
          Approve {selectedActions.size} Action{selectedActions.size !== 1 ? 's' : ''}
        </button>
        <button className="reject-btn" onClick={onReject}>
          Reject All
        </button>
      </div>

      <style jsx>{`
        .navi-approval-panel {
          border: 2px solid #2a2e38;
          border-radius: 8px;
          padding: 16px;
          margin: 16px 0;
          background: #1a1d24;
        }

        .approval-header h3 {
          margin: 0 0 8px 0;
          font-size: 16px;
          font-weight: 600;
          color: #e8eaed;
        }

        .user-message {
          font-size: 13px;
          color: #9aa0a6;
          margin: 0 0 16px 0;
          padding: 8px 12px;
          background: rgba(79, 192, 141, 0.08);
          border-left: 3px solid rgba(79, 192, 141, 0.5);
          border-radius: 4px;
          font-style: italic;
        }

        .actions-list {
          margin: 16px 0;
        }

        .action-item {
          padding: 12px;
          border: 1px solid #2a2e38;
          border-left-width: 4px;
          border-radius: 6px;
          margin-bottom: 8px;
          transition: all 0.2s;
          background: #1f2430;
        }

        .action-item:hover {
          border-color: #4FC08D;
          background: rgba(79, 192, 141, 0.05);
        }

        .action-row {
          display: flex;
          gap: 12px;
          align-items: flex-start;
        }

        .action-select input[type="checkbox"] {
          width: 18px;
          height: 18px;
          cursor: pointer;
          margin-top: 2px;
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
          color: #9aa0a6;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          background: #2a2e38;
          padding: 2px 6px;
          border-radius: 3px;
        }

        .action-details {
          font-size: 13px;
          line-height: 1.6;
          color: #e8eaed;
        }

        .action-details strong {
          color: #9aa0a6;
          font-weight: 500;
        }

        .action-details code {
          font-family: 'Fira Code', 'Courier New', monospace;
          font-size: 12px;
          background: #0d1117;
          padding: 2px 6px;
          border-radius: 3px;
          color: #58a6ff;
        }

        .preview-details {
          margin-top: 8px;
        }

        .preview-details summary {
          cursor: pointer;
          font-size: 12px;
          color: #58a6ff;
          user-select: none;
        }

        .preview-details summary:hover {
          text-decoration: underline;
        }

        .preview {
          margin-top: 8px;
          padding: 8px;
          background: #0d1117;
          border-radius: 4px;
          font-family: 'Fira Code', 'Courier New', monospace;
          font-size: 12px;
          overflow-x: auto;
          max-height: 200px;
          overflow-y: auto;
          border: 1px solid #2a2e38;
        }

        .command {
          margin: 4px 0 0 0;
          padding: 6px 8px;
          background: #0d1117;
          border-radius: 4px;
          font-family: 'Fira Code', 'Courier New', monospace;
          font-size: 12px;
          color: #79c0ff;
          border: 1px solid #2a2e38;
        }

        .show-diff-btn {
          margin-left: 8px;
          padding: 4px 10px;
          background: #238636;
          color: #ffffff;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 11px;
          font-weight: 500;
          transition: background 0.2s;
        }

        .show-diff-btn:hover {
          background: #2ea043;
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
          color: #f85149;
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
          border-top: 1px solid #2a2e38;
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
          background: #238636;
          color: #ffffff;
          flex: 1;
        }

        .approve-btn:hover:not(:disabled) {
          background: #2ea043;
        }

        .approve-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .reject-btn {
          background: transparent;
          border: 1px solid #f85149;
          color: #f85149;
          min-width: 120px;
        }

        .reject-btn:hover {
          background: rgba(248, 81, 73, 0.1);
        }
      `}</style>
    </div>
  );
};
