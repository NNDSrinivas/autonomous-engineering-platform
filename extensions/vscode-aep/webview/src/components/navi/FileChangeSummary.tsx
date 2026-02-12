import React, { useState } from 'react';
import { ChevronDown, ChevronRight, FileText, File, FileCode, FileCog, FileJson, Check, RotateCcw, GitBranch, Eye } from 'lucide-react';

export interface FileChange {
  path: string;
  additions?: number;
  deletions?: number;
  originalContent?: string;
  wasCreated?: boolean; // True if file was newly created (undo = delete)
  wasDeleted?: boolean; // True if file was deleted (undo = restore)
  status?: "added" | "modified" | "deleted";
}

export interface FileChangeSummaryProps {
  files: FileChange[];
  totalAdditions?: number;
  totalDeletions?: number;
  onKeep: () => void;
  onUndo: () => void;
  onFileClick?: (filePath: string) => void;
  onPreviewAll?: () => void; // Opens diff view for all changed files
  expanded?: boolean;
  onToggle?: (expanded: boolean) => void;
}

// Get file icon based on extension
const getFileIcon = (filePath: string) => {
  const ext = filePath.split('.').pop()?.toLowerCase() || '';

  switch (ext) {
    case 'ts':
    case 'tsx':
      return <FileCode size={14} className="fcs-icon fcs-icon--ts" />;
    case 'js':
    case 'jsx':
    case 'mjs':
      return <FileCode size={14} className="fcs-icon fcs-icon--js" />;
    case 'py':
    case 'pyw':
      return <FileCode size={14} className="fcs-icon fcs-icon--py" />;
    case 'go':
      return <FileCode size={14} className="fcs-icon fcs-icon--go" />;
    case 'rs':
      return <FileCode size={14} className="fcs-icon fcs-icon--rs" />;
    case 'java':
    case 'kt':
      return <FileCode size={14} className="fcs-icon fcs-icon--java" />;
    case 'c':
    case 'cpp':
    case 'h':
    case 'cs':
      return <FileCode size={14} className="fcs-icon fcs-icon--c" />;
    case 'rb':
      return <FileCode size={14} className="fcs-icon fcs-icon--rb" />;
    case 'php':
      return <FileCode size={14} className="fcs-icon fcs-icon--php" />;
    case 'swift':
      return <FileCode size={14} className="fcs-icon fcs-icon--swift" />;
    case 'json':
    case 'jsonc':
      return <FileJson size={14} className="fcs-icon fcs-icon--json" />;
    case 'yaml':
    case 'yml':
    case 'toml':
      return <FileCog size={14} className="fcs-icon fcs-icon--yaml" />;
    case 'md':
    case 'mdx':
    case 'txt':
    case 'rst':
      return <FileText size={14} className="fcs-icon fcs-icon--md" />;
    case 'css':
    case 'scss':
    case 'less':
      return <FileCode size={14} className="fcs-icon fcs-icon--css" />;
    case 'html':
    case 'htm':
      return <FileCode size={14} className="fcs-icon fcs-icon--html" />;
    case 'config':
    case 'env':
    case 'gitignore':
    case 'dockerfile':
      return <FileCog size={14} className="fcs-icon fcs-icon--config" />;
    default:
      return <File size={14} className="fcs-icon" />;
  }
};

// Parse file path into filename and directory
const parseFilePath = (filePath: string): { filename: string; directory: string } => {
  if (!filePath) return { filename: 'Unknown file', directory: '' };
  const parts = filePath.split('/');
  const filename = parts.pop() || filePath;
  const directory = parts.length > 0 ? parts.join('/') : '';
  return { filename, directory };
};

export const FileChangeSummary: React.FC<FileChangeSummaryProps> = ({
  files,
  totalAdditions,
  totalDeletions,
  onKeep,
  onUndo,
  onFileClick,
  onPreviewAll,
  expanded,
  onToggle,
}) => {
  // Start collapsed by default for compact layout
  const [internalExpanded, setInternalExpanded] = useState(false);
  const isControlled = typeof expanded === 'boolean';
  const isExpanded = isControlled ? expanded : internalExpanded;

  const toggleExpanded = () => {
    const next = !isExpanded;
    if (isControlled) {
      onToggle?.(next);
    } else {
      setInternalExpanded(next);
    }
  };

  // Calculate totals if not provided
  const additions = totalAdditions ?? files.reduce((sum, f) => sum + (f.additions || 0), 0);
  const deletions = totalDeletions ?? files.reduce((sum, f) => sum + (f.deletions || 0), 0);
  const hasStats = additions > 0 || deletions > 0;

  if (files.length === 0) return null;

  return (
    <div className="fcs-container">
      {/* Header row */}
      <div
        className="fcs-header"
        onClick={toggleExpanded}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && toggleExpanded()}
      >
        <div className="fcs-header-left">
          <div className="fcs-expand-icon">
            {isExpanded ? (
              <ChevronDown size={14} />
            ) : (
              <ChevronRight size={14} />
            )}
          </div>
          <GitBranch size={14} className="fcs-git-icon" />
          <span className="fcs-count">
            {files.length} file{files.length !== 1 ? 's' : ''} changed
          </span>
          {hasStats && (
            <div className="fcs-stats">
              {additions > 0 && <span className="fcs-stat fcs-stat--add">+{additions}</span>}
              {deletions > 0 && <span className="fcs-stat fcs-stat--del">-{deletions}</span>}
            </div>
          )}
        </div>
        <div className="fcs-actions" onClick={(e) => e.stopPropagation()}>
          {onPreviewAll && (
            <button type="button" className="fcs-btn fcs-btn--preview" onClick={onPreviewAll}>
              <Eye size={12} />
              <span>Review</span>
            </button>
          )}
          <button type="button" className="fcs-btn fcs-btn--keep" onClick={onKeep}>
            <Check size={12} />
            <span>Keep</span>
          </button>
          <button type="button" className="fcs-btn fcs-btn--undo" onClick={onUndo}>
            <RotateCcw size={12} />
            <span>Undo</span>
          </button>
        </div>
      </div>

      {/* File list */}
      <div className={`fcs-file-list ${isExpanded ? 'fcs-file-list--expanded' : ''}`}>
        {isExpanded && files.map((file, index) => {
          const { filename, directory } = parseFilePath(file.path);
          const fileHasStats = typeof file.additions === 'number' || typeof file.deletions === 'number';
          const derivedStatus = file.status
            || (file.wasCreated ? "added" : file.wasDeleted ? "deleted" : undefined);
          const isDeleted = derivedStatus === "deleted";
          const isAdded = derivedStatus === "added";

          return (
            <button
              key={file.path || `file-${index}`}
              type="button"
              className={`fcs-file-row ${isDeleted ? 'fcs-file-row--deleted' : isAdded ? 'fcs-file-row--added' : ''}`}
              onClick={() => file.path && onFileClick?.(file.path)}
            >
              <div className="fcs-file-info">
                {getFileIcon(file.path)}
                <span className={`fcs-filename ${isDeleted ? 'fcs-filename--deleted' : ''}`}>{filename}</span>
                {directory && (
                  <span className="fcs-directory">{directory}</span>
                )}
              </div>
              <div className="fcs-file-stats">
                {isDeleted ? (
                  <span className="fcs-badge fcs-badge--deleted">deleted</span>
                ) : fileHasStats ? (
                  <>
                    {typeof file.additions === 'number' && file.additions > 0 && (
                      <span className="fcs-stat fcs-stat--add">+{file.additions}</span>
                    )}
                    {typeof file.deletions === 'number' && file.deletions > 0 && (
                      <span className="fcs-stat fcs-stat--del">-{file.deletions}</span>
                    )}
                    {file.additions === 0 && file.deletions === 0 && (
                      <span className="fcs-stat fcs-stat--zero">0</span>
                    )}
                  </>
                ) : (
                  <span className="fcs-stat fcs-stat--empty">modified</span>
                )}
              </div>
            </button>
          );
        })}
      </div>

      <style>{`
        .fcs-container {
          background: linear-gradient(135deg, rgba(30, 32, 40, 0.95), rgba(25, 27, 35, 0.98));
          border: 1px solid rgba(99, 102, 241, 0.2);
          border-radius: 12px;
          margin: 12px 0;
          overflow: hidden;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15), 0 0 0 1px rgba(255, 255, 255, 0.03);
        }

        .fcs-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 8px 12px;
          cursor: pointer;
          transition: background 0.15s ease;
          border-bottom: 1px solid transparent;
        }

        .fcs-header:hover {
          background: rgba(99, 102, 241, 0.08);
        }

        .fcs-header:focus {
          outline: none;
          background: rgba(99, 102, 241, 0.1);
        }

        .fcs-header-left {
          display: flex;
          align-items: center;
          gap: 8px;
          flex: 1;
          min-width: 0;
        }

        .fcs-expand-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          color: rgba(255, 255, 255, 0.5);
          transition: transform 0.2s ease;
        }

        .fcs-git-icon {
          color: #f97316;
          flex-shrink: 0;
        }

        .fcs-count {
          font-size: 12px;
          font-weight: 600;
          color: var(--vscode-foreground, #e2e8f0);
          white-space: nowrap;
        }

        .fcs-stats {
          display: flex;
          align-items: center;
          gap: 6px;
          margin-left: 4px;
        }

        .fcs-stat {
          font-family: "SF Mono", "Menlo", "Monaco", monospace;
          font-size: 10px;
          font-weight: 600;
          padding: 2px 6px;
          border-radius: 4px;
        }

        .fcs-stat--add {
          color: #4ade80;
          background: rgba(74, 222, 128, 0.12);
        }

        .fcs-stat--del {
          color: #f87171;
          background: rgba(248, 113, 113, 0.12);
        }

        .fcs-stat--zero {
          color: rgba(255, 255, 255, 0.4);
          background: rgba(255, 255, 255, 0.05);
        }

        .fcs-stat--empty {
          color: rgba(255, 255, 255, 0.4);
          font-size: 10px;
          font-weight: 500;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .fcs-badge {
          font-size: 10px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.4px;
          padding: 2px 6px;
          border-radius: 999px;
        }

        .fcs-badge--deleted {
          color: #fecaca;
          background: rgba(248, 113, 113, 0.2);
          border: 1px solid rgba(248, 113, 113, 0.35);
        }

        .fcs-actions {
          display: flex;
          align-items: center;
          gap: 6px;
          flex-shrink: 0;
        }

        .fcs-btn {
          display: flex;
          align-items: center;
          gap: 4px;
          padding: 6px 10px;
          font-size: 11px;
          font-weight: 600;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.15s ease;
          border: none;
          outline: none;
        }

        .fcs-btn span {
          line-height: 1;
        }

        .fcs-btn--keep {
          background: linear-gradient(135deg, #3b82f6, #2563eb);
          color: white;
          box-shadow: 0 2px 4px rgba(59, 130, 246, 0.25);
        }

        .fcs-btn--keep:hover {
          background: linear-gradient(135deg, #60a5fa, #3b82f6);
          transform: translateY(-1px);
          box-shadow: 0 4px 8px rgba(59, 130, 246, 0.35);
        }

        .fcs-btn--keep:active {
          transform: translateY(0);
        }

        .fcs-btn--preview {
          background: linear-gradient(135deg, #8b5cf6, #7c3aed);
          color: white;
          box-shadow: 0 2px 4px rgba(139, 92, 246, 0.25);
        }

        .fcs-btn--preview:hover {
          background: linear-gradient(135deg, #a78bfa, #8b5cf6);
          transform: translateY(-1px);
          box-shadow: 0 4px 8px rgba(139, 92, 246, 0.35);
        }

        .fcs-btn--preview:active {
          transform: translateY(0);
        }

        .fcs-btn--undo {
          background: rgba(255, 255, 255, 0.06);
          color: rgba(255, 255, 255, 0.8);
          border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .fcs-btn--undo:hover {
          background: rgba(255, 255, 255, 0.1);
          border-color: rgba(255, 255, 255, 0.15);
          color: white;
        }

        .fcs-file-list {
          max-height: 0;
          overflow: hidden;
          transition: max-height 0.25s ease, padding 0.25s ease;
          padding: 0 8px;
        }

        .fcs-file-list--expanded {
          max-height: 400px;
          overflow-y: auto;
          padding: 8px;
          border-top: 1px solid rgba(255, 255, 255, 0.06);
        }

        .fcs-file-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          width: 100%;
          padding: 6px 8px;
          margin-bottom: 4px;
          background: rgba(255, 255, 255, 0.02);
          border: 1px solid transparent;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.15s ease;
          text-align: left;
        }

        .fcs-file-row:last-child {
          margin-bottom: 0;
        }

        .fcs-file-row:hover {
          background: rgba(99, 102, 241, 0.1);
          border-color: rgba(99, 102, 241, 0.3);
          transform: translateX(2px);
        }

        .fcs-file-row--deleted {
          background: rgba(248, 113, 113, 0.08);
          border-color: rgba(248, 113, 113, 0.25);
        }

        .fcs-file-row--deleted:hover {
          background: rgba(248, 113, 113, 0.12);
          border-color: rgba(248, 113, 113, 0.35);
        }

        .fcs-file-row:focus {
          outline: none;
          border-color: rgba(99, 102, 241, 0.5);
        }

        .fcs-file-info {
          display: flex;
          align-items: center;
          gap: 8px;
          flex: 1;
          min-width: 0;
          overflow: hidden;
        }

        .fcs-icon {
          flex-shrink: 0;
          color: rgba(255, 255, 255, 0.5);
        }

        /* Language-specific icon colors */
        .fcs-icon--ts { color: #3178c6; }
        .fcs-icon--js { color: #f7df1e; }
        .fcs-icon--py { color: #3776ab; }
        .fcs-icon--go { color: #00add8; }
        .fcs-icon--rs { color: #dea584; }
        .fcs-icon--java { color: #f89820; }
        .fcs-icon--c { color: #a8b9cc; }
        .fcs-icon--rb { color: #cc342d; }
        .fcs-icon--php { color: #8892be; }
        .fcs-icon--swift { color: #fa7343; }
        .fcs-icon--json { color: #cbcb41; }
        .fcs-icon--yaml { color: #cb171e; }
        .fcs-icon--md { color: #519aba; }
        .fcs-icon--css { color: #563d7c; }
        .fcs-icon--html { color: #e34c26; }
        .fcs-icon--config { color: #6d8086; }

        .fcs-filename {
          font-size: 11px;
          font-weight: 500;
          color: var(--vscode-foreground, #e2e8f0);
          white-space: nowrap;
          flex-shrink: 0;
        }

        .fcs-filename--deleted {
          color: #f87171;
          text-decoration: line-through;
        }

        .fcs-directory {
          font-size: 11px;
          color: rgba(255, 255, 255, 0.35);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          margin-left: 4px;
        }

        .fcs-directory::before {
          content: "";
          margin-right: 0;
        }

        .fcs-file-stats {
          display: flex;
          align-items: center;
          gap: 6px;
          flex-shrink: 0;
          margin-left: 12px;
        }

        /* Scrollbar styling */
        .fcs-file-list--expanded::-webkit-scrollbar {
          width: 6px;
        }

        .fcs-file-list--expanded::-webkit-scrollbar-track {
          background: transparent;
        }

        .fcs-file-list--expanded::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.15);
          border-radius: 3px;
        }

        .fcs-file-list--expanded::-webkit-scrollbar-thumb:hover {
          background: rgba(255, 255, 255, 0.25);
        }

        /* VSCode light theme */
        :root.vscode-light .fcs-container,
        [data-vscode-theme-kind="vscode-light"] .fcs-container,
        :root.light .fcs-container {
          background: linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(248, 250, 252, 0.98));
          border-color: rgba(99, 102, 241, 0.15);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08), 0 0 0 1px rgba(0, 0, 0, 0.03);
        }

        :root.vscode-light .fcs-header:hover,
        [data-vscode-theme-kind="vscode-light"] .fcs-header:hover,
        :root.light .fcs-header:hover {
          background: rgba(99, 102, 241, 0.06);
        }

        :root.vscode-light .fcs-count,
        [data-vscode-theme-kind="vscode-light"] .fcs-count,
        :root.light .fcs-count {
          color: #1e293b;
        }

        :root.vscode-light .fcs-stat--add,
        [data-vscode-theme-kind="vscode-light"] .fcs-stat--add,
        :root.light .fcs-stat--add {
          color: #16a34a;
          background: rgba(22, 163, 74, 0.1);
        }

        :root.vscode-light .fcs-stat--del,
        [data-vscode-theme-kind="vscode-light"] .fcs-stat--del,
        :root.light .fcs-stat--del {
          color: #dc2626;
          background: rgba(220, 38, 38, 0.1);
        }

        :root.vscode-light .fcs-btn--undo,
        [data-vscode-theme-kind="vscode-light"] .fcs-btn--undo,
        :root.light .fcs-btn--undo {
          background: rgba(0, 0, 0, 0.04);
          color: rgba(0, 0, 0, 0.7);
          border-color: rgba(0, 0, 0, 0.1);
        }

        :root.vscode-light .fcs-btn--undo:hover,
        [data-vscode-theme-kind="vscode-light"] .fcs-btn--undo:hover,
        :root.light .fcs-btn--undo:hover {
          background: rgba(0, 0, 0, 0.08);
          color: rgba(0, 0, 0, 0.9);
        }

        :root.vscode-light .fcs-file-row,
        [data-vscode-theme-kind="vscode-light"] .fcs-file-row,
        :root.light .fcs-file-row {
          background: rgba(0, 0, 0, 0.02);
        }

        :root.vscode-light .fcs-file-row:hover,
        [data-vscode-theme-kind="vscode-light"] .fcs-file-row:hover,
        :root.light .fcs-file-row:hover {
          background: rgba(99, 102, 241, 0.08);
        }

        :root.vscode-light .fcs-file-row--deleted,
        [data-vscode-theme-kind="vscode-light"] .fcs-file-row--deleted,
        :root.light .fcs-file-row--deleted {
          background: rgba(220, 38, 38, 0.08);
          border-color: rgba(220, 38, 38, 0.25);
        }

        :root.vscode-light .fcs-file-row--deleted:hover,
        [data-vscode-theme-kind="vscode-light"] .fcs-file-row--deleted:hover,
        :root.light .fcs-file-row--deleted:hover {
          background: rgba(220, 38, 38, 0.12);
          border-color: rgba(220, 38, 38, 0.35);
        }

        :root.vscode-light .fcs-filename,
        [data-vscode-theme-kind="vscode-light"] .fcs-filename,
        :root.light .fcs-filename {
          color: #1e293b;
        }

        :root.vscode-light .fcs-filename--deleted,
        [data-vscode-theme-kind="vscode-light"] .fcs-filename--deleted,
        :root.light .fcs-filename--deleted {
          color: #dc2626;
        }

        :root.vscode-light .fcs-directory,
        [data-vscode-theme-kind="vscode-light"] .fcs-directory,
        :root.light .fcs-directory {
          color: rgba(0, 0, 0, 0.4);
        }

        :root.vscode-light .fcs-icon,
        [data-vscode-theme-kind="vscode-light"] .fcs-icon,
        :root.light .fcs-icon {
          color: rgba(0, 0, 0, 0.5);
        }

        :root.vscode-light .fcs-badge--deleted,
        [data-vscode-theme-kind="vscode-light"] .fcs-badge--deleted,
        :root.light .fcs-badge--deleted {
          color: #dc2626;
          background: rgba(220, 38, 38, 0.12);
          border-color: rgba(220, 38, 38, 0.3);
        }
      `}</style>
    </div>
  );
};

export default FileChangeSummary;
