/**
 * CheckpointResumeDialog - Shows checkpoint details and resume options
 *
 * When resuming from a checkpoint, shows the user:
 * - What task was being done
 * - What progress was made (steps, files, commands)
 * - Options to handle the resume:
 *   1. Continue - Re-send with context about what was done
 *   2. Revert - Undo file changes, then retry
 *   3. Start Fresh - Clear checkpoint, keep changes, start new message
 */

import React, { useState } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  FileText,
  Play,
  RotateCcw,
  Terminal,
  Trash2,
  X,
} from 'lucide-react';
import { TaskCheckpoint } from '../../utils/chatSessions';

interface CheckpointResumeDialogProps {
  checkpoint: TaskCheckpoint;
  onContinue: (includeContext: boolean) => void;
  onRevert: () => void;
  onStartFresh: () => void;
  onDismiss: () => void;
}

export const CheckpointResumeDialog: React.FC<CheckpointResumeDialogProps> = ({
  checkpoint,
  onContinue,
  onRevert,
  onStartFresh,
  onDismiss,
}) => {
  const [filesExpanded, setFilesExpanded] = useState(true);
  const [commandsExpanded, setCommandsExpanded] = useState(false);

  const completedSteps = checkpoint.steps.filter(s => s.status === 'completed').length;
  const hasFileChanges = checkpoint.modifiedFiles.length > 0;
  const hasCommands = checkpoint.executedCommands.length > 0;

  // Format time ago
  const formatTimeAgo = (dateStr?: string) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  return (
    <div className="checkpoint-resume-dialog-overlay">
      <div className="checkpoint-resume-dialog">
        {/* Header */}
        <div className="checkpoint-resume-header">
          <div className="checkpoint-resume-header-icon">
            <AlertTriangle size={24} />
          </div>
          <div className="checkpoint-resume-header-content">
            <h3 className="checkpoint-resume-title">Resume Interrupted Task</h3>
            <p className="checkpoint-resume-subtitle">
              Interrupted {formatTimeAgo(checkpoint.interruptedAt)}
              {checkpoint.interruptReason && ` - ${checkpoint.interruptReason}`}
            </p>
          </div>
          <button
            className="checkpoint-resume-close"
            onClick={onDismiss}
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        {/* Original Message */}
        <div className="checkpoint-resume-section">
          <h4 className="checkpoint-resume-section-title">Original Request</h4>
          <div className="checkpoint-resume-message">
            {checkpoint.userMessage}
          </div>
        </div>

        {/* Progress */}
        {checkpoint.totalSteps > 0 && (
          <div className="checkpoint-resume-section">
            <h4 className="checkpoint-resume-section-title">Progress</h4>
            <div className="checkpoint-resume-progress">
              <div className="checkpoint-resume-progress-bar">
                <div
                  className="checkpoint-resume-progress-fill"
                  style={{ width: `${(completedSteps / checkpoint.totalSteps) * 100}%` }}
                />
              </div>
              <span className="checkpoint-resume-progress-text">
                {completedSteps} of {checkpoint.totalSteps} steps completed
              </span>
            </div>
          </div>
        )}

        {/* Files Modified */}
        {hasFileChanges && (
          <div className="checkpoint-resume-section">
            <button
              className="checkpoint-resume-section-header"
              onClick={() => setFilesExpanded(!filesExpanded)}
            >
              {filesExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              <FileText size={16} />
              <span>Files Modified ({checkpoint.modifiedFiles.length})</span>
            </button>
            {filesExpanded && (
              <div className="checkpoint-resume-list">
                {checkpoint.modifiedFiles.map((file, idx) => (
                  <div key={idx} className={`checkpoint-resume-list-item ${file.success ? '' : 'is-failed'}`}>
                    <span className={`checkpoint-file-op checkpoint-file-op--${file.operation}`}>
                      {file.operation === 'create' ? '+' : file.operation === 'delete' ? '-' : '~'}
                    </span>
                    <span className="checkpoint-file-path">{file.path}</span>
                    {file.success ? (
                      <CheckCircle size={14} className="checkpoint-success-icon" />
                    ) : (
                      <X size={14} className="checkpoint-fail-icon" />
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Commands Executed */}
        {hasCommands && (
          <div className="checkpoint-resume-section">
            <button
              className="checkpoint-resume-section-header"
              onClick={() => setCommandsExpanded(!commandsExpanded)}
            >
              {commandsExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              <Terminal size={16} />
              <span>Commands Executed ({checkpoint.executedCommands.length})</span>
            </button>
            {commandsExpanded && (
              <div className="checkpoint-resume-list">
                {checkpoint.executedCommands.map((cmd, idx) => (
                  <div key={idx} className={`checkpoint-resume-list-item ${cmd.success ? '' : 'is-failed'}`}>
                    <code className="checkpoint-command">{cmd.command}</code>
                    {cmd.exitCode !== undefined && (
                      <span className={`checkpoint-exit-code ${cmd.exitCode === 0 ? 'is-success' : 'is-error'}`}>
                        exit {cmd.exitCode}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Warning about changes */}
        {hasFileChanges && (
          <div className="checkpoint-resume-warning">
            <AlertTriangle size={16} />
            <span>
              {checkpoint.modifiedFiles.filter(f => f.success).length} file(s) were modified before the interruption.
              Choose how to proceed:
            </span>
          </div>
        )}

        {/* Actions */}
        <div className="checkpoint-resume-actions">
          <button
            className="checkpoint-resume-action checkpoint-resume-action--continue"
            onClick={() => onContinue(true)}
            title="Continue with context about what was already done"
          >
            <Play size={16} />
            <div className="checkpoint-action-text">
              <span className="checkpoint-action-title">Continue</span>
              <span className="checkpoint-action-desc">Keep changes, retry with context</span>
            </div>
          </button>

          {hasFileChanges && (
            <button
              className="checkpoint-resume-action checkpoint-resume-action--revert"
              onClick={onRevert}
              title="Undo file changes, then retry from scratch"
            >
              <RotateCcw size={16} />
              <div className="checkpoint-action-text">
                <span className="checkpoint-action-title">Revert & Retry</span>
                <span className="checkpoint-action-desc">Undo changes, start fresh</span>
              </div>
            </button>
          )}

          <button
            className="checkpoint-resume-action checkpoint-resume-action--fresh"
            onClick={onStartFresh}
            title="Clear checkpoint, keep any changes made"
          >
            <Trash2 size={16} />
            <div className="checkpoint-action-text">
              <span className="checkpoint-action-title">Discard</span>
              <span className="checkpoint-action-desc">Clear checkpoint, keep changes</span>
            </div>
          </button>
        </div>
      </div>

      <style>{`
        .checkpoint-resume-dialog-overlay {
          position: fixed;
          inset: 0;
          background: rgba(0, 0, 0, 0.7);
          backdrop-filter: blur(4px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          padding: 20px;
        }

        .checkpoint-resume-dialog {
          background: linear-gradient(135deg, rgba(30, 41, 59, 0.98) 0%, rgba(15, 23, 42, 0.98) 100%);
          border: 1px solid rgba(148, 163, 184, 0.2);
          border-radius: 16px;
          width: 100%;
          max-width: 520px;
          max-height: 80vh;
          overflow-y: auto;
          box-shadow: 0 25px 50px rgba(0, 0, 0, 0.5);
        }

        .checkpoint-resume-header {
          display: flex;
          align-items: flex-start;
          gap: 12px;
          padding: 20px;
          border-bottom: 1px solid rgba(148, 163, 184, 0.1);
        }

        .checkpoint-resume-header-icon {
          color: #f59e0b;
          flex-shrink: 0;
          margin-top: 2px;
        }

        .checkpoint-resume-header-content {
          flex: 1;
          min-width: 0;
        }

        .checkpoint-resume-title {
          margin: 0;
          font-size: 16px;
          font-weight: 600;
          color: #f1f5f9;
        }

        .checkpoint-resume-subtitle {
          margin: 4px 0 0;
          font-size: 13px;
          color: rgba(148, 163, 184, 0.8);
        }

        .checkpoint-resume-close {
          background: transparent;
          border: none;
          color: rgba(148, 163, 184, 0.6);
          cursor: pointer;
          padding: 4px;
          border-radius: 6px;
          transition: all 0.2s;
        }

        .checkpoint-resume-close:hover {
          background: rgba(255, 255, 255, 0.1);
          color: #f1f5f9;
        }

        .checkpoint-resume-section {
          padding: 16px 20px;
          border-bottom: 1px solid rgba(148, 163, 184, 0.1);
        }

        .checkpoint-resume-section-title {
          margin: 0 0 10px;
          font-size: 12px;
          font-weight: 600;
          color: rgba(148, 163, 184, 0.7);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .checkpoint-resume-section-header {
          display: flex;
          align-items: center;
          gap: 8px;
          width: 100%;
          background: transparent;
          border: none;
          color: #f1f5f9;
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          padding: 0;
          text-align: left;
        }

        .checkpoint-resume-section-header:hover {
          color: #60a5fa;
        }

        .checkpoint-resume-message {
          background: rgba(0, 0, 0, 0.3);
          border-radius: 8px;
          padding: 12px;
          font-size: 13px;
          color: #e2e8f0;
          line-height: 1.5;
          max-height: 100px;
          overflow-y: auto;
        }

        .checkpoint-resume-progress {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .checkpoint-resume-progress-bar {
          height: 8px;
          background: rgba(0, 0, 0, 0.3);
          border-radius: 4px;
          overflow: hidden;
        }

        .checkpoint-resume-progress-fill {
          height: 100%;
          background: linear-gradient(90deg, #8b5cf6, #22d3ee);
          border-radius: 4px;
          transition: width 0.3s;
        }

        .checkpoint-resume-progress-text {
          font-size: 12px;
          color: rgba(148, 163, 184, 0.8);
        }

        .checkpoint-resume-list {
          margin-top: 10px;
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .checkpoint-resume-list-item {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 10px;
          background: rgba(0, 0, 0, 0.2);
          border-radius: 6px;
          font-size: 12px;
        }

        .checkpoint-resume-list-item.is-failed {
          background: rgba(239, 68, 68, 0.1);
          border: 1px solid rgba(239, 68, 68, 0.2);
        }

        .checkpoint-file-op {
          width: 18px;
          height: 18px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 4px;
          font-weight: 700;
          font-size: 14px;
        }

        .checkpoint-file-op--create {
          background: rgba(74, 222, 128, 0.2);
          color: #4ade80;
        }

        .checkpoint-file-op--edit {
          background: rgba(96, 165, 250, 0.2);
          color: #60a5fa;
        }

        .checkpoint-file-op--delete {
          background: rgba(248, 113, 113, 0.2);
          color: #f87171;
        }

        .checkpoint-file-path {
          flex: 1;
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          color: #e2e8f0;
          font-family: 'Fira Code', 'Consolas', monospace;
        }

        .checkpoint-success-icon {
          color: #4ade80;
          flex-shrink: 0;
        }

        .checkpoint-fail-icon {
          color: #f87171;
          flex-shrink: 0;
        }

        .checkpoint-command {
          flex: 1;
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          color: #e2e8f0;
          font-family: 'Fira Code', 'Consolas', monospace;
          font-size: 11px;
        }

        .checkpoint-exit-code {
          font-size: 10px;
          padding: 2px 6px;
          border-radius: 4px;
          font-weight: 500;
        }

        .checkpoint-exit-code.is-success {
          background: rgba(74, 222, 128, 0.2);
          color: #4ade80;
        }

        .checkpoint-exit-code.is-error {
          background: rgba(248, 113, 113, 0.2);
          color: #f87171;
        }

        .checkpoint-resume-warning {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 12px 20px;
          background: rgba(245, 158, 11, 0.1);
          border-top: 1px solid rgba(245, 158, 11, 0.2);
          border-bottom: 1px solid rgba(245, 158, 11, 0.2);
          color: #fbbf24;
          font-size: 12px;
          line-height: 1.4;
        }

        .checkpoint-resume-actions {
          display: flex;
          flex-direction: column;
          gap: 10px;
          padding: 20px;
        }

        .checkpoint-resume-action {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 14px 16px;
          border-radius: 10px;
          border: 1px solid transparent;
          cursor: pointer;
          transition: all 0.2s;
          text-align: left;
        }

        .checkpoint-action-text {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }

        .checkpoint-action-title {
          font-size: 14px;
          font-weight: 600;
        }

        .checkpoint-action-desc {
          font-size: 11px;
          opacity: 0.7;
        }

        .checkpoint-resume-action--continue {
          background: linear-gradient(135deg, rgba(139, 92, 246, 0.2) 0%, rgba(124, 58, 237, 0.1) 100%);
          border-color: rgba(139, 92, 246, 0.3);
          color: #a78bfa;
        }

        .checkpoint-resume-action--continue:hover {
          background: linear-gradient(135deg, rgba(139, 92, 246, 0.3) 0%, rgba(124, 58, 237, 0.2) 100%);
          border-color: rgba(139, 92, 246, 0.5);
          transform: translateY(-1px);
        }

        .checkpoint-resume-action--revert {
          background: linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(251, 191, 36, 0.05) 100%);
          border-color: rgba(245, 158, 11, 0.25);
          color: #fbbf24;
        }

        .checkpoint-resume-action--revert:hover {
          background: linear-gradient(135deg, rgba(245, 158, 11, 0.25) 0%, rgba(251, 191, 36, 0.15) 100%);
          border-color: rgba(245, 158, 11, 0.4);
          transform: translateY(-1px);
        }

        .checkpoint-resume-action--fresh {
          background: rgba(255, 255, 255, 0.05);
          border-color: rgba(148, 163, 184, 0.2);
          color: rgba(148, 163, 184, 0.8);
        }

        .checkpoint-resume-action--fresh:hover {
          background: rgba(255, 255, 255, 0.1);
          border-color: rgba(148, 163, 184, 0.3);
          color: #f1f5f9;
        }
      `}</style>
    </div>
  );
};

export default CheckpointResumeDialog;
