import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Copy, Check, FileCode } from 'lucide-react';

export interface DiffLine {
  type: 'addition' | 'deletion' | 'context';
  content: string;
  oldLineNumber?: number;
  newLineNumber?: number;
}

export interface FileDiff {
  path: string;
  additions: number;
  deletions: number;
  lines: DiffLine[];
}

export interface FileDiffViewProps {
  diff: FileDiff;
  defaultExpanded?: boolean;
  onFileClick?: (path: string) => void;
  operation?: 'create' | 'edit' | 'delete';
  embedded?: boolean;
}

// Get file extension for syntax highlighting class
const getLanguageClass = (filePath: string): string => {
  const ext = filePath.split('.').pop()?.toLowerCase() || '';
  const langMap: Record<string, string> = {
    ts: 'typescript', tsx: 'typescript',
    js: 'javascript', jsx: 'javascript', mjs: 'javascript',
    py: 'python', pyw: 'python',
    go: 'go', rs: 'rust',
    java: 'java', kt: 'kotlin',
    c: 'c', cpp: 'cpp', h: 'c', cs: 'csharp',
    rb: 'ruby', php: 'php', swift: 'swift',
    json: 'json', yaml: 'yaml', yml: 'yaml',
    css: 'css', scss: 'scss', less: 'less',
    html: 'html', htm: 'html', xml: 'xml',
    md: 'markdown', sql: 'sql', sh: 'bash',
  };
  return langMap[ext] || 'plaintext';
};

// Extract filename from path
const getFileName = (path: string): string => {
  return path.split('/').pop() || path;
};

export const FileDiffView: React.FC<FileDiffViewProps> = ({
  diff,
  defaultExpanded = false,
  onFileClick,
  operation = 'edit',
  embedded = false,
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const content = diff.lines
      .filter(l => l.type !== 'deletion')
      .map(l => l.content)
      .join('\n');

    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleHeaderClick = () => {
    if (embedded) return;
    setIsExpanded(!isExpanded);
  };

  const handleFileNameClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onFileClick?.(diff.path);
  };

  const headerLabel = operation === 'create' ? 'New file' :
                     operation === 'delete' ? 'Deleted file' :
                     'Edited file';
  const fileName = getFileName(diff.path);
  const collapsedPrefix = operation === 'create'
    ? 'Created'
    : operation === 'delete'
      ? 'Deleted'
      : 'Edited';

  const isOpen = embedded ? true : isExpanded;

  return (
    <div className={`fdv-container ${embedded ? 'fdv-container--embedded' : ''}`}>
      {/* Header */}
      {!embedded && (
        <div className="fdv-header" onClick={handleHeaderClick}>
          <div className="fdv-header-left">
            <span className="fdv-chevron">
              {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </span>
            {isExpanded ? (
              <span className="fdv-label">{headerLabel}</span>
            ) : (
              <span className="fdv-label">
                {collapsedPrefix}{' '}
                <button
                  className="fdv-file-link"
                  onClick={handleFileNameClick}
                  title={`Open ${fileName}`}
                  type="button"
                >
                  {fileName}
                </button>
              </span>
            )}
            {!isExpanded && operation === 'create' && diff.additions > 0 && (
              <span className="fdv-badge fdv-badge--create fdv-badge--collapsed">
                <span className="fdv-badge-stat fdv-badge-stat--add">+{diff.additions}</span>
                {diff.deletions > 0 && <span className="fdv-badge-stat fdv-badge-stat--del">-{diff.deletions}</span>}
              </span>
            )}
            {!isExpanded && operation === 'edit' && (diff.additions > 0 || diff.deletions > 0) && (
              <span className="fdv-badge fdv-badge--edit fdv-badge--collapsed">
                {diff.additions > 0 && <span className="fdv-badge-stat fdv-badge-stat--add">+{diff.additions}</span>}
                {diff.deletions > 0 && <span className="fdv-badge-stat fdv-badge-stat--del">-{diff.deletions}</span>}
              </span>
            )}
            {!isExpanded && operation === 'delete' && diff.deletions > 0 && (
              <span className="fdv-badge fdv-badge--delete fdv-badge--collapsed">
                <span className="fdv-badge-stat fdv-badge-stat--del">-{diff.deletions}</span>
              </span>
            )}
          </div>
          <button className="fdv-copy-btn" onClick={handleCopy} title="Copy changes">
            {copied ? <Check size={14} /> : <Copy size={14} />}
          </button>
        </div>
      )}

      {/* File info bar */}
      {!embedded && isExpanded && (
        <div
          className="fdv-file-bar"
          onClick={handleFileNameClick}
          role="button"
          tabIndex={0}
        >
          <FileCode size={14} className="fdv-file-icon" />
          <span className="fdv-filename">{fileName}</span>
          <span className="fdv-stats">
            {diff.additions > 0 && <span className="fdv-stat fdv-stat--add">+{diff.additions}</span>}
            {diff.deletions > 0 && <span className="fdv-stat fdv-stat--del">-{diff.deletions}</span>}
          </span>
        </div>
      )}

      {/* Diff content */}
      {isOpen && (
        <div className={`fdv-content fdv-lang-${getLanguageClass(diff.path)}`}>
          {diff.lines.length === 0 && (
            <div className="fdv-empty">
              {operation === 'create' ? 'New file (no diff)' : 'No diff available'}
            </div>
          )}
          {diff.lines.map((line, idx) => (
            <div
              key={idx}
              className={`fdv-line fdv-line--${line.type}`}
            >
              <span className="fdv-line-number fdv-line-number--old">
                {line.type !== 'addition' ? (line.oldLineNumber || '') : ''}
              </span>
              <span className="fdv-line-number fdv-line-number--new">
                {line.type !== 'deletion' ? (line.newLineNumber || '') : ''}
              </span>
              <span className="fdv-line-marker">
                {line.type === 'addition' ? '+' : line.type === 'deletion' ? '-' : ' '}
              </span>
              <span className="fdv-line-content">
                <code>{line.content || ' '}</code>
              </span>
            </div>
          ))}
        </div>
      )}

      <style>{`
        .fdv-container {
          background: var(--vscode-editor-background);
          color: var(--vscode-editor-foreground);
          border: 1px solid var(--vscode-editorWidget-border, rgba(99, 102, 241, 0.15));
          border-radius: 10px;
          overflow: hidden;
          margin: 8px 0;
          font-family: var(--navi-code-font, var(--vscode-editor-font-family, "SF Mono", Menlo, monospace));
        }

        .fdv-container--embedded {
          margin-top: 6px;
        }

        .fdv-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 10px 14px;
          background: var(--vscode-editorWidget-background, rgba(255, 255, 255, 0.03));
          border-bottom: 1px solid var(--vscode-editorWidget-border, rgba(255, 255, 255, 0.06));
          cursor: pointer;
          user-select: none;
          transition: background 0.15s ease;
        }

        .fdv-header:hover {
          background: var(--vscode-list-hoverBackground, rgba(255, 255, 255, 0.05));
        }

        .fdv-header-left {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .fdv-chevron {
          color: var(--vscode-icon-foreground, rgba(255, 255, 255, 0.6));
          display: flex;
          align-items: center;
        }

        .fdv-label {
          font-size: 13px;
          font-weight: 500;
          color: var(--vscode-editor-foreground, rgba(255, 255, 255, 0.8));
          letter-spacing: -0.01em;
        }

        .fdv-file-link {
          background: none;
          border: none;
          padding: 0;
          margin: 0;
          color: var(--navi-link-color, var(--vscode-textLink-foreground, #6aaeff));
          font-weight: 600;
          cursor: pointer;
        }

        .fdv-file-link:hover {
          text-decoration: underline;
          color: var(--navi-link-color-active, var(--vscode-textLink-activeForeground, #8cc2ff));
        }

        .fdv-badge {
          margin-left: 8px;
          padding: 2px 8px;
          border-radius: 4px;
          font-size: 11px;
          font-weight: 600;
          font-family: var(--navi-code-font, var(--vscode-editor-font-family, "SF Mono", Menlo, monospace));
          letter-spacing: -0.02em;
          display: inline-flex;
          align-items: center;
          gap: 6px;
        }

        .fdv-badge--collapsed {
          font-size: 10px;
          padding: 2px 6px;
        }

        .fdv-badge--create {
          background-color: rgba(15, 23, 42, 0.55);
          border: 1px solid rgba(148, 163, 184, 0.35);
        }

        .fdv-badge--edit {
          background-color: rgba(15, 23, 42, 0.55);
          border: 1px solid rgba(148, 163, 184, 0.35);
        }

        .fdv-badge--delete {
          background-color: rgba(15, 23, 42, 0.55);
          border: 1px solid rgba(148, 163, 184, 0.35);
        }

        .fdv-badge-stat {
          font-family: inherit;
          font-size: 10px;
          font-weight: 600;
        }

        .fdv-badge-stat--add {
          color: var(--vscode-gitDecoration-addedResourceForeground, #4ade80);
        }

        .fdv-badge-stat--del {
          color: var(--vscode-gitDecoration-deletedResourceForeground, #f87171);
        }

        .fdv-copy-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 6px;
          border: none;
          background: var(--vscode-toolbar-background, rgba(255, 255, 255, 0.05));
          border-radius: 6px;
          color: var(--vscode-icon-foreground, rgba(255, 255, 255, 0.6));
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .fdv-copy-btn:hover {
          background: var(--vscode-toolbar-hoverBackground, rgba(255, 255, 255, 0.1));
          color: var(--vscode-foreground, rgba(255, 255, 255, 0.85));
        }

        .fdv-file-bar {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px 14px;
          background: var(--vscode-editorWidget-background, rgba(30, 41, 59, 0.5));
          border-bottom: 1px solid var(--vscode-editorWidget-border, rgba(255, 255, 255, 0.06));
          cursor: pointer;
          transition: background 0.15s ease;
        }

        .fdv-file-bar:hover {
          background: var(--vscode-list-hoverBackground, rgba(30, 41, 59, 0.7));
        }

        .fdv-file-icon {
          color: var(--navi-link-color, var(--vscode-symbolIcon-fileForeground, #6aaeff));
          flex-shrink: 0;
        }

        .fdv-filename {
          font-family: var(--navi-code-font, var(--vscode-editor-font-family, "SF Mono", Menlo, monospace));
          font-size: 13px;
          font-weight: 500;
          color: var(--vscode-editor-foreground, #e2e8f0);
          flex: 1;
        }

        .fdv-stats {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .fdv-stat {
          font-family: var(--navi-code-font, var(--vscode-editor-font-family, "SF Mono", Menlo, monospace));
          font-size: 12px;
          font-weight: 600;
          letter-spacing: -0.02em;
        }

        .fdv-stat--add {
          color: var(--vscode-gitDecoration-addedResourceForeground, #4ade80);
        }

        .fdv-stat--del {
          color: var(--vscode-gitDecoration-deletedResourceForeground, #f87171);
        }

        .fdv-content {
          max-height: 400px;
          overflow-y: auto;
          overflow-x: auto;
          background: var(--vscode-editor-background);
        }

        .fdv-line {
          display: flex;
          align-items: stretch;
          min-height: 22px;
          font-family: var(--navi-code-font, var(--vscode-editor-font-family, "SF Mono", Menlo, monospace));
          font-size: var(--navi-code-size, 12px);
          line-height: var(--navi-code-line-height, 1.5);
        }

        .fdv-line--addition {
          background: var(--vscode-diffEditor-insertedLineBackground, rgba(46, 160, 67, 0.14));
        }

        .fdv-line--deletion {
          background: var(--vscode-diffEditor-removedLineBackground, rgba(248, 81, 73, 0.14));
        }

        .fdv-line--context {
          background: transparent;
        }

        .fdv-line-number {
          display: inline-block;
          min-width: 40px;
          padding: 0 8px;
          text-align: right;
          color: var(--vscode-editorLineNumber-foreground, rgba(255, 255, 255, 0.4));
          font-size: 12px;
          user-select: none;
          flex-shrink: 0;
        }

        .fdv-line--addition .fdv-line-number--new {
          background: var(--vscode-diffEditor-insertedLineBackground, rgba(46, 160, 67, 0.14));
          color: var(--vscode-editorLineNumber-foreground, rgba(255, 255, 255, 0.6));
        }

        .fdv-line--deletion .fdv-line-number--old {
          background: var(--vscode-diffEditor-removedLineBackground, rgba(248, 81, 73, 0.14));
          color: var(--vscode-editorLineNumber-foreground, rgba(255, 255, 255, 0.6));
        }

        .fdv-line-marker {
          display: inline-block;
          width: 20px;
          text-align: center;
          color: var(--vscode-editor-foreground, rgba(255, 255, 255, 0.6));
          flex-shrink: 0;
          user-select: none;
        }

        .fdv-line--addition .fdv-line-marker {
          color: var(--vscode-gitDecoration-addedResourceForeground, #4ade80);
          font-weight: 600;
        }

        .fdv-line--deletion .fdv-line-marker {
          color: var(--vscode-gitDecoration-deletedResourceForeground, #f87171);
          font-weight: 600;
        }

        .fdv-line-content {
          flex: 1;
          padding-right: 16px;
          white-space: pre;
          color: var(--vscode-editor-foreground, #e2e8f0);
          min-width: 0;
        }

        .fdv-line-content code {
          font-family: inherit;
          font-size: inherit;
          line-height: inherit;
          color: var(--vscode-editor-foreground, #e2e8f0);
          background: transparent !important;
          padding: 0 !important;
          margin: 0;
          border-radius: 0;
          display: block;
          white-space: pre;
        }

        .fdv-empty {
          padding: 16px;
          font-size: 12px;
          color: var(--vscode-descriptionForeground, rgba(255, 255, 255, 0.6));
        }

        .fdv-line--addition .fdv-line-content code {
          background: transparent !important;
        }

        .fdv-line--deletion .fdv-line-content code {
          background: transparent !important;
          color: var(--vscode-diffEditor-removedTextForeground, #fca5a5);
        }

        /* Scrollbar styling */
        .fdv-content::-webkit-scrollbar {
          width: 8px;
          height: 8px;
        }

        .fdv-content::-webkit-scrollbar-track {
          background: rgba(255, 255, 255, 0.03);
        }

        .fdv-content::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.15);
          border-radius: 4px;
        }

        .fdv-content::-webkit-scrollbar-thumb:hover {
          background: rgba(255, 255, 255, 0.25);
        }

        .fdv-content::-webkit-scrollbar-corner {
          background: transparent;
        }

        /* Theme-aware colors are driven by VS Code CSS variables */
      `}</style>
    </div>
  );
};

export default FileDiffView;
