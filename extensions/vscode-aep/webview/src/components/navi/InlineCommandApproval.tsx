import React, { useState, useRef, useEffect, useMemo } from 'react';
import { ChevronDown, ChevronRight, Terminal, ExternalLink, FileText } from 'lucide-react';

export interface InlineCommandApprovalProps {
  command: string;
  shell?: string;
  status?: 'pending' | 'running' | 'completed' | 'error';
  output?: string;
  onAllow: () => void;
  onSkip: () => void;
  onFocusTerminal?: () => void;
  onShowOutput?: () => void;
  onAlwaysAllowCommand?: (command: string) => void;
  onAlwaysAllowExact?: (command: string) => void;
  onEnableAutoApprove?: () => void;
  onConfigureAutoApprove?: () => void;
}

// Parse command into colored segments for syntax highlighting
function parseCommand(cmd: string): Array<{ text: string; type: 'command' | 'flag' | 'path' | 'operator' | 'string' | 'normal' }> {
  const segments: Array<{ text: string; type: 'command' | 'flag' | 'path' | 'operator' | 'string' | 'normal' }> = [];
  const tokens = cmd.split(/(\s+|&&|\|\||;|&|\|)/);
  let isFirstToken = true;

  for (const token of tokens) {
    if (!token) continue;

    // Whitespace
    if (/^\s+$/.test(token)) {
      segments.push({ text: token, type: 'normal' });
      continue;
    }

    // Operators
    if (['&&', '||', ';', '&', '|'].includes(token)) {
      segments.push({ text: token, type: 'operator' });
      isFirstToken = true;
      continue;
    }

    // First token after operator is a command
    if (isFirstToken) {
      // Check if it's a path-like command
      if (token.includes('/')) {
        segments.push({ text: token, type: 'path' });
      } else {
        segments.push({ text: token, type: 'command' });
      }
      isFirstToken = false;
      continue;
    }

    // Flags
    if (token.startsWith('-')) {
      segments.push({ text: token, type: 'flag' });
      continue;
    }

    // Paths
    if (token.includes('/') || token.startsWith('.')) {
      segments.push({ text: token, type: 'path' });
      continue;
    }

    // Strings (quoted)
    if (token.startsWith('"') || token.startsWith("'")) {
      segments.push({ text: token, type: 'string' });
      continue;
    }

    // Normal text
    segments.push({ text: token, type: 'normal' });
  }

  return segments;
}

export const InlineCommandApproval: React.FC<InlineCommandApprovalProps> = ({
  command,
  shell = 'zsh',
  status = 'pending',
  output,
  onAllow,
  onSkip,
  onFocusTerminal,
  onShowOutput,
  onAlwaysAllowCommand,
  onAlwaysAllowExact,
  onEnableAutoApprove,
  onConfigureAutoApprove,
}) => {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [outputExpanded, setOutputExpanded] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Extract base command (first word) for "Always Allow Command"
  const baseCommand = command.split(' ')[0];

  // Parse command for syntax highlighting
  const commandSegments = useMemo(() => parseCommand(command), [command]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const isPending = status === 'pending';
  const isCompleted = status === 'completed';
  const isRunning = status === 'running';
  const isError = status === 'error';
  const hasOutput = output && output.trim().length > 0;

  // After user clicks Allow/Skip, hide the approval buttons and show post-execution UI
  const showApprovalButtons = isPending;
  const showPostExecutionUI = isRunning || isCompleted || isError;

  return (
    <div className={`inline-command-approval ${isCompleted ? 'inline-command-approval--completed' : ''} ${isError ? 'inline-command-approval--error' : ''}`}>
      <div className="command-header">
        <Terminal size={14} className="command-icon" />
        <span className="command-label">
          {isPending && <>Run <code>{shell}</code> command?</>}
          {isRunning && <>Running <code>{shell}</code> command...</>}
          {isCompleted && (
            <>
              <span className="command-status command-status--completed">✓</span>
              Command completed
            </>
          )}
          {isError && (
            <>
              <span className="command-status command-status--error">✗</span>
              Command failed
            </>
          )}
        </span>

        {/* Post-execution action buttons on the right - shown after Allow is clicked */}
        {showPostExecutionUI && (
          <div className="command-header-actions">
            {onFocusTerminal && (
              <button
                className="command-action-btn"
                onClick={onFocusTerminal}
                title="Focus Terminal"
              >
                <ExternalLink size={12} />
                <span>Focus Terminal</span>
              </button>
            )}
            <button
              className="command-action-btn"
              onClick={() => setOutputExpanded(!outputExpanded)}
              title={outputExpanded ? "Hide Output" : "Show Output"}
            >
              <FileText size={12} />
              <span>{outputExpanded ? 'Hide Output' : 'Show Output'}</span>
            </button>
          </div>
        )}
      </div>

      <div className="command-content">
        <code className="command-text">
          {commandSegments.map((seg, idx) => (
            <span key={idx} className={`cmd-${seg.type}`}>{seg.text}</span>
          ))}
        </code>
      </div>

      {/* Expandable output section - shown when user clicks Show Output */}
      {outputExpanded && (
        <div className="command-output-section">
          {hasOutput ? (
            <pre className="command-output">{output}</pre>
          ) : (
            <div className="command-output command-output--empty">
              {isRunning ? 'Command is running...' : 'No output available'}
            </div>
          )}
        </div>
      )}

      {/* Approval buttons - only shown before user makes a choice */}
      {showApprovalButtons && (
        <div className="command-actions">
          <div className="allow-button-group" ref={dropdownRef}>
            <button
              className="allow-btn"
              onClick={onAllow}
            >
              Allow
            </button>
            <button
              className="allow-dropdown-btn"
              onClick={() => setDropdownOpen(!dropdownOpen)}
              aria-label="More options"
            >
              <ChevronDown size={14} />
            </button>

            {dropdownOpen && (
              <div className="allow-dropdown-menu">
                {onEnableAutoApprove && (
                  <button
                    className="dropdown-item"
                    onClick={() => {
                      setDropdownOpen(false);
                      onEnableAutoApprove();
                    }}
                  >
                    Enable Auto Approve...
                  </button>
                )}

                <div className="dropdown-divider" />

                {onAlwaysAllowCommand && (
                  <button
                    className="dropdown-item dropdown-item-disabled"
                    onClick={() => {
                      setDropdownOpen(false);
                      onAlwaysAllowCommand(baseCommand);
                    }}
                    disabled
                  >
                    Always Allow Command: {baseCommand}
                  </button>
                )}

                {onAlwaysAllowExact && (
                  <button
                    className="dropdown-item dropdown-item-disabled"
                    onClick={() => {
                      setDropdownOpen(false);
                      onAlwaysAllowExact(command);
                    }}
                    disabled
                  >
                    Always Allow Exact Command Line
                  </button>
                )}

                <div className="dropdown-divider" />

                {onConfigureAutoApprove && (
                  <button
                    className="dropdown-item dropdown-item-disabled"
                    onClick={() => {
                      setDropdownOpen(false);
                      onConfigureAutoApprove();
                    }}
                    disabled
                  >
                    Configure Auto Approve...
                  </button>
                )}
              </div>
            )}
          </div>

          <button
            className="skip-btn"
            onClick={onSkip}
          >
            Skip
          </button>
        </div>
      )}

      <style>{`
        .inline-command-approval {
          background: var(--vscode-editor-background, #1e1e1e);
          border: 1px solid var(--vscode-panel-border, #3c3c3c);
          border-radius: 8px;
          padding: 12px 16px;
          margin: 8px 0;
        }

        .inline-command-approval--completed {
          border-color: rgba(74, 222, 128, 0.3);
          background: rgba(74, 222, 128, 0.05);
        }

        .inline-command-approval--error {
          border-color: rgba(239, 68, 68, 0.3);
          background: rgba(239, 68, 68, 0.05);
        }

        .command-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 8px;
          color: var(--vscode-foreground, #cccccc);
          font-size: 13px;
        }

        .command-icon {
          color: var(--vscode-terminal-ansiYellow, #e5c07b);
          flex-shrink: 0;
        }

        .command-label {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .command-label code {
          background: var(--vscode-textCodeBlock-background, #2d2d2d);
          padding: 2px 6px;
          border-radius: 4px;
          font-family: var(--vscode-editor-font-family, monospace);
          font-size: 12px;
        }

        .command-status {
          font-size: 11px;
          padding: 2px 6px;
          border-radius: 4px;
        }

        .command-status--running {
          background: rgba(55, 148, 255, 0.2);
          color: #3794ff;
        }

        .command-status--completed {
          color: #4ade80;
        }

        .command-status--error {
          color: #ef4444;
        }

        .command-header-actions {
          margin-left: auto;
          display: flex;
          gap: 8px;
        }

        .command-action-btn {
          display: flex;
          align-items: center;
          gap: 4px;
          background: transparent;
          border: 1px solid var(--vscode-panel-border, #3c3c3c);
          color: var(--vscode-foreground, #cccccc);
          padding: 4px 8px;
          font-size: 11px;
          border-radius: 4px;
          cursor: pointer;
          transition: all 0.15s;
        }

        .command-action-btn:hover {
          background: var(--vscode-toolbar-hoverBackground, rgba(90, 93, 94, 0.31));
          border-color: var(--vscode-focusBorder, #007fd4);
        }

        .command-content {
          background: var(--vscode-textCodeBlock-background, #1a1a1a);
          padding: 10px 12px;
          border-radius: 6px;
          overflow-x: auto;
        }

        /* Only add bottom margin when there's content below (approval buttons or output) */
        .inline-command-approval:has(.command-actions) .command-content,
        .inline-command-approval:has(.command-output-section) .command-content {
          margin-bottom: 12px;
        }

        .command-text {
          display: block;
          font-family: var(--vscode-editor-font-family, 'SF Mono', 'Monaco', 'Menlo', monospace);
          font-size: 13px;
          line-height: 1.5;
          white-space: pre-wrap;
          word-break: break-word;
        }

        /* Syntax highlighting colors */
        .cmd-command {
          color: #c678dd; /* Purple for commands */
          font-weight: 500;
        }

        .cmd-flag {
          color: #56b6c2; /* Cyan for flags */
        }

        .cmd-path {
          color: #98c379; /* Green for paths */
        }

        .cmd-operator {
          color: #e5c07b; /* Yellow for operators */
          font-weight: 600;
        }

        .cmd-string {
          color: #d19a66; /* Orange for strings */
        }

        .cmd-normal {
          color: var(--vscode-foreground, #abb2bf);
        }

        .command-output-section {
          margin-bottom: 12px;
        }

        .command-output-toggle {
          display: flex;
          align-items: center;
          gap: 4px;
          background: transparent;
          border: none;
          color: var(--vscode-descriptionForeground, #6c6c6c);
          font-size: 11px;
          cursor: pointer;
          padding: 4px 0;
        }

        .command-output-toggle:hover {
          color: var(--vscode-foreground, #cccccc);
        }

        .command-output {
          margin-top: 8px;
          padding: 8px 12px;
          background: var(--vscode-textCodeBlock-background, #1a1a1a);
          border-radius: 4px;
          font-family: var(--vscode-editor-font-family, monospace);
          font-size: 11px;
          line-height: 1.4;
          color: var(--vscode-foreground, #cccccc);
          max-height: 200px;
          overflow-y: auto;
          white-space: pre-wrap;
        }

        .command-output--empty {
          color: var(--vscode-descriptionForeground, #6c6c6c);
          font-style: italic;
        }

        .command-actions {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .allow-button-group {
          display: flex;
          position: relative;
        }

        .allow-btn {
          background: #3794ff;
          color: white;
          border: none;
          padding: 6px 14px;
          font-size: 12px;
          font-weight: 500;
          border-radius: 4px 0 0 4px;
          cursor: pointer;
          transition: background 0.15s;
        }

        .allow-btn:hover:not(:disabled) {
          background: #2a7ed8;
        }

        .allow-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .allow-dropdown-btn {
          background: #3794ff;
          color: white;
          border: none;
          border-left: 1px solid rgba(255, 255, 255, 0.2);
          padding: 6px 8px;
          border-radius: 0 4px 4px 0;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: background 0.15s;
        }

        .allow-dropdown-btn:hover:not(:disabled) {
          background: #2a7ed8;
        }

        .allow-dropdown-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .allow-dropdown-menu {
          position: absolute;
          top: 100%;
          left: 0;
          margin-top: 4px;
          background: var(--vscode-menu-background, #252526);
          border: 1px solid var(--vscode-menu-border, #454545);
          border-radius: 6px;
          min-width: 240px;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
          z-index: 1000;
          overflow: hidden;
        }

        .dropdown-item {
          display: block;
          width: 100%;
          text-align: left;
          background: transparent;
          border: none;
          padding: 8px 12px;
          font-size: 12px;
          color: var(--vscode-menu-foreground, #cccccc);
          cursor: pointer;
          transition: background 0.1s;
        }

        .dropdown-item:hover:not(:disabled) {
          background: var(--vscode-menu-selectionBackground, #094771);
        }

        .dropdown-item-disabled {
          color: var(--vscode-disabledForeground, #6c6c6c);
          cursor: not-allowed;
        }

        .dropdown-item-disabled:hover {
          background: transparent;
        }

        .dropdown-divider {
          height: 1px;
          background: var(--vscode-menu-separatorBackground, #454545);
          margin: 4px 0;
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
          transition: background 0.15s;
        }

        .skip-btn:hover:not(:disabled) {
          background: var(--vscode-button-secondaryHoverBackground, #45494e);
        }

        .skip-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
      `}</style>
    </div>
  );
};

export default InlineCommandApproval;
