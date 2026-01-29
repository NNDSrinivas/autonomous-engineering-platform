import React, { useState } from 'react';
import './NaviInlineCommand.css';

// =============================================================================
// NAVI INLINE COMMAND
// =============================================================================
// Sleek, professional inline command block for chat messages
// Replaces the old "Bash" blocks with a modern design
// =============================================================================

interface NaviInlineCommandProps {
  commandId?: string;
  command: string;
  output?: string;
  status: 'running' | 'done' | 'error';
  showOutput?: boolean;
  purpose?: string;
  explanation?: string;
  nextAction?: string;
  exitCode?: number;
  onOpenActivity?: (commandId: string) => void;
  highlighted?: boolean;
}

export const NaviInlineCommand: React.FC<NaviInlineCommandProps> = ({
  commandId,
  command,
  output,
  status,
  showOutput = false,
  purpose,
  explanation,
  nextAction,
  exitCode,
  onOpenActivity,
  highlighted = false,
}) => {
  // Auto-expand when running, has output, or has error
  const [expanded, setExpanded] = useState(
    status === 'running' || status === 'error' || (showOutput && !!output)
  );
  const hasOutput = Boolean(output && output.trim());
  const allowOutput = showOutput || status === 'error';

  const getStatusIcon = () => {
    switch (status) {
      case 'running':
        return <span className="nic-spinner" />;
      case 'done':
        return <span className="nic-check">✓</span>;
      case 'error':
        return <span className="nic-error">✕</span>;
    }
  };

  const formatOutput = () => {
    if (!output) return status === 'running' ? 'Executing...' : 'No output';
    const lines = output.split('\n').filter(l => l.trim());
    return lines.slice(-12).join('\n') || 'No output';
  };

  return (
    <div className={`nic nic--${status} ${highlighted ? 'nic--highlight' : ''}`} data-command-id={commandId}>
      <div className="nic-header" onClick={() => setExpanded(!expanded)}>
        <div className="nic-status">
          {getStatusIcon()}
        </div>
        <code className="nic-command">{command}</code>
        {commandId && onOpenActivity && (
          <button
            className="nic-activity-btn"
            title="Open in Activity"
            onClick={(event) => {
              event.stopPropagation();
              onOpenActivity(commandId);
            }}
          >
            Activity ↗
          </button>
        )}
        <span className={`nic-expand ${expanded ? 'is-open' : ''}`}>
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <path d="M2.5 3.75L5 6.25L7.5 3.75" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </span>
      </div>

      {expanded && (
        <div className="nic-body">
          {purpose && (
            <div className="nic-meta nic-purpose">
              <span className="nic-meta-label">Purpose</span>
              <span className="nic-meta-text">{purpose}</span>
            </div>
          )}

          {allowOutput ? (
            <div className="nic-output">
              <pre>{formatOutput()}</pre>
            </div>
          ) : (
            <div className="nic-output-hint">
              <span>Output available in Activity panel.</span>
              {commandId && onOpenActivity && (
                <button
                  className="nic-output-link"
                  onClick={(event) => {
                    event.stopPropagation();
                    onOpenActivity(commandId);
                  }}
                >
                  View output
                </button>
              )}
            </div>
          )}

          {status === 'error' && exitCode !== undefined && (
            <div className="nic-exit">Exit code: {exitCode}</div>
          )}

          {explanation && (
            <div className="nic-meta nic-explanation">
              <span className="nic-meta-label">Result</span>
              <span className="nic-meta-text">{explanation}</span>
            </div>
          )}

          {nextAction && (
            <div className="nic-meta nic-next">
              <span className="nic-meta-label">Next</span>
              <span className="nic-meta-text">{nextAction}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default NaviInlineCommand;
