import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, FileEdit, FilePlus, Eye, ExternalLink } from 'lucide-react';

export type FileActionType = 'edit' | 'create';

export interface InlineFileApprovalProps {
  type: FileActionType;
  filePath: string;
  status?: 'pending' | 'running' | 'completed' | 'error';
  linesChanged?: { added: number; removed: number };
  onAllow: () => void;
  onSkip: () => void;
  onShowDiff?: () => void;
  onAlwaysAllowFile?: (filePath: string) => void;
  onAlwaysAllowPattern?: (pattern: string) => void;
}

export const InlineFileApproval: React.FC<InlineFileApprovalProps> = ({
  type,
  filePath,
  status = 'pending',
  linesChanged,
  onAllow,
  onSkip,
  onShowDiff,
  onAlwaysAllowFile,
  onAlwaysAllowPattern,
}) => {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Extract file extension for "Always Allow Pattern"
  const fileExt = filePath.split('.').pop() || '';
  const pattern = `*.${fileExt}`;

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
  const isRunning = status === 'running';
  const isCompleted = status === 'completed';
  const isError = status === 'error';

  const showApprovalButtons = isPending;
  const showPostExecutionUI = isRunning || isCompleted || isError;

  const Icon = type === 'edit' ? FileEdit : FilePlus;
  const actionLabel = type === 'edit' ? 'Edit' : 'Create';
  const iconColor = type === 'edit' ? '#e5c07b' : '#98c379';

  return (
    <div className={`inline-file-approval ${isCompleted ? 'inline-file-approval--completed' : ''} ${isError ? 'inline-file-approval--error' : ''}`}>
      <div className="file-header">
        <Icon size={14} className="file-icon" style={{ color: isCompleted ? '#4ade80' : isError ? '#ef4444' : iconColor }} />
        <span className="file-label">
          {isPending && <>{actionLabel} file?</>}
          {isRunning && <>{actionLabel === 'Edit' ? 'Editing' : 'Creating'} file...</>}
          {isCompleted && (
            <>
              <span className="file-status file-status--completed">✓</span>
              File {type === 'edit' ? 'edited' : 'created'}
            </>
          )}
          {isError && (
            <>
              <span className="file-status file-status--error">✗</span>
              {actionLabel} failed
            </>
          )}
        </span>

        {/* Post-execution action buttons on the right */}
        {showPostExecutionUI && onShowDiff && (
          <div className="file-header-actions">
            <button
              className="file-action-btn"
              onClick={onShowDiff}
              title="View Diff"
            >
              <Eye size={12} />
              <span>View Diff</span>
            </button>
          </div>
        )}
      </div>

      <div className="file-content">
        <code className="file-path">{filePath}</code>
        {linesChanged && (
          <span className="lines-changed">
            <span className="lines-added">+{linesChanged.added}</span>
            <span className="lines-removed">-{linesChanged.removed}</span>
          </span>
        )}
      </div>

      {/* Approval buttons - only shown before user makes a choice */}
      {showApprovalButtons && (
        <div className="file-actions">
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
                {onAlwaysAllowFile && (
                  <button
                    className="dropdown-item dropdown-item-disabled"
                    onClick={() => {
                      setDropdownOpen(false);
                      onAlwaysAllowFile(filePath);
                    }}
                    disabled
                  >
                    Always Allow This File
                  </button>
                )}

                {onAlwaysAllowPattern && fileExt && (
                  <button
                    className="dropdown-item dropdown-item-disabled"
                    onClick={() => {
                      setDropdownOpen(false);
                      onAlwaysAllowPattern(pattern);
                    }}
                    disabled
                  >
                    Always Allow Pattern: {pattern}
                  </button>
                )}
              </div>
            )}
          </div>

          {onShowDiff && (
            <button
              className="diff-btn"
              onClick={onShowDiff}
            >
              <Eye size={12} />
              View Diff
            </button>
          )}

          <button
            className="skip-btn"
            onClick={onSkip}
          >
            Skip
          </button>
        </div>
      )}

      <style>{`
        .inline-file-approval {
          background: var(--vscode-editor-background, #1e1e1e);
          border: 1px solid var(--vscode-panel-border, #3c3c3c);
          border-radius: 8px;
          padding: 12px 16px;
          margin: 8px 0;
        }

        .inline-file-approval--completed {
          border-color: rgba(74, 222, 128, 0.3);
          background: rgba(74, 222, 128, 0.05);
        }

        .inline-file-approval--error {
          border-color: rgba(239, 68, 68, 0.3);
          background: rgba(239, 68, 68, 0.05);
        }

        .file-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 8px;
          color: var(--vscode-foreground, #cccccc);
          font-size: 13px;
        }

        .file-icon {
          flex-shrink: 0;
        }

        .file-label {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .file-status {
          font-size: 14px;
        }

        .file-status--completed {
          color: #4ade80;
        }

        .file-status--error {
          color: #ef4444;
        }

        .file-header-actions {
          margin-left: auto;
          display: flex;
          gap: 8px;
        }

        .file-action-btn {
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

        .file-action-btn:hover {
          background: var(--vscode-toolbar-hoverBackground, rgba(90, 93, 94, 0.31));
          border-color: var(--vscode-focusBorder, #007fd4);
        }

        .file-content {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }

        /* Only add bottom margin when there's content below */
        .inline-file-approval:has(.file-actions) .file-content {
          margin-bottom: 12px;
        }

        .file-path {
          display: block;
          background: transparent;
          color: #61afef;
          font-family: var(--vscode-editor-font-family, monospace);
          font-size: 13px;
          line-height: 1.5;
          word-break: break-all;
        }

        .lines-changed {
          display: flex;
          gap: 8px;
          font-family: var(--vscode-editor-font-family, monospace);
          font-size: 12px;
          flex-shrink: 0;
        }

        .lines-added {
          color: #98c379;
        }

        .lines-removed {
          color: #e06c75;
        }

        .file-actions {
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

        .allow-btn:hover {
          background: #2a7ed8;
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

        .allow-dropdown-btn:hover {
          background: #2a7ed8;
        }

        .allow-dropdown-menu {
          position: absolute;
          top: 100%;
          left: 0;
          margin-top: 4px;
          background: var(--vscode-menu-background, #252526);
          border: 1px solid var(--vscode-menu-border, #454545);
          border-radius: 6px;
          min-width: 200px;
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

        .diff-btn {
          display: flex;
          align-items: center;
          gap: 4px;
          background: transparent;
          color: var(--vscode-textLink-foreground, #3794ff);
          border: 1px solid var(--vscode-textLink-foreground, #3794ff);
          padding: 5px 10px;
          font-size: 12px;
          font-weight: 500;
          border-radius: 4px;
          cursor: pointer;
          transition: all 0.15s;
        }

        .diff-btn:hover {
          background: rgba(55, 148, 255, 0.1);
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

        .skip-btn:hover {
          background: var(--vscode-button-secondaryHoverBackground, #45494e);
        }
      `}</style>
    </div>
  );
};

export default InlineFileApproval;
