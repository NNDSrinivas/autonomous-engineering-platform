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
  const collapsedLabel = operation === 'create'
    ? `Created ${fileName}`
    : operation === 'delete'
      ? `Deleted ${fileName}`
      : `Edited ${fileName}`;
  const collapsedPrefix = operation === 'create'
    ? 'Created'
    : operation === 'delete'
      ? 'Deleted'
      : 'Edited';

  return (
    <div className="fdv-container">
      {/* Header */}
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
            <span className="fdv-badge fdv-badge--create fdv-badge--collapsed">+{diff.additions} -{diff.deletions}</span>
          )}
          {!isExpanded && operation === 'edit' && (diff.additions > 0 || diff.deletions > 0) && (
            <span className="fdv-badge fdv-badge--edit fdv-badge--collapsed">+{diff.additions} -{diff.deletions}</span>
          )}
          {!isExpanded && operation === 'delete' && diff.deletions > 0 && (
            <span className="fdv-badge fdv-badge--delete fdv-badge--collapsed">-{diff.deletions}</span>
          )}
        </div>
        <button className="fdv-copy-btn" onClick={handleCopy} title="Copy changes">
          {copied ? <Check size={14} /> : <Copy size={14} />}
        </button>
      </div>

      {/* File info bar */}
      {isExpanded && (
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
      {isExpanded && (
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
          background: #0d1117;
          border: 1px solid rgba(99, 102, 241, 0.15);
          border-radius: 10px;
          overflow: hidden;
          margin: 8px 0;
          font-family: "Inter", "SF Pro Display", -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
        }

        .fdv-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 10px 14px;
          background: rgba(255, 255, 255, 0.03);
          border-bottom: 1px solid rgba(255, 255, 255, 0.06);
          cursor: pointer;
          user-select: none;
          transition: background 0.15s ease;
        }

        .fdv-header:hover {
          background: rgba(255, 255, 255, 0.05);
        }

        .fdv-header-left {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .fdv-chevron {
          color: rgba(255, 255, 255, 0.5);
          display: flex;
          align-items: center;
        }

        .fdv-label {
          font-size: 13px;
          font-weight: 500;
          color: rgba(255, 255, 255, 0.8);
          letter-spacing: -0.01em;
        }

        .fdv-file-link {
          background: none;
          border: none;
          padding: 0;
          margin: 0;
          color: #60a5fa;
          font-weight: 600;
          cursor: pointer;
        }

        .fdv-file-link:hover {
          text-decoration: underline;
        }

        .fdv-badge {
          margin-left: 8px;
          padding: 2px 8px;
          border-radius: 4px;
          font-size: 11px;
          font-weight: 600;
          font-family: "SF Mono", "Fira Code", Consolas, monospace;
          letter-spacing: -0.02em;
        }

        .fdv-badge--collapsed {
          font-size: 10px;
          padding: 2px 6px;
        }

        .fdv-badge--create {
          background-color: rgba(74, 222, 128, 0.15);
          color: #4ade80;
          border: 1px solid rgba(74, 222, 128, 0.3);
        }

        .fdv-badge--edit {
          background-color: rgba(96, 165, 250, 0.15);
          color: #60a5fa;
          border: 1px solid rgba(96, 165, 250, 0.3);
        }

        .fdv-badge--delete {
          background-color: rgba(248, 113, 113, 0.15);
          color: #f87171;
          border: 1px solid rgba(248, 113, 113, 0.3);
        }

        .fdv-copy-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 6px;
          border: none;
          background: rgba(255, 255, 255, 0.05);
          border-radius: 6px;
          color: rgba(255, 255, 255, 0.5);
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .fdv-copy-btn:hover {
          background: rgba(255, 255, 255, 0.1);
          color: rgba(255, 255, 255, 0.8);
        }

        .fdv-file-bar {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px 14px;
          background: rgba(30, 41, 59, 0.5);
          border-bottom: 1px solid rgba(255, 255, 255, 0.06);
          cursor: pointer;
          transition: background 0.15s ease;
        }

        .fdv-file-bar:hover {
          background: rgba(30, 41, 59, 0.7);
        }

        .fdv-file-icon {
          color: #60a5fa;
          flex-shrink: 0;
        }

        .fdv-filename {
          font-family: "SF Mono", "Fira Code", "JetBrains Mono", Consolas, monospace;
          font-size: 13px;
          font-weight: 500;
          color: #e2e8f0;
          flex: 1;
        }

        .fdv-stats {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .fdv-stat {
          font-family: "SF Mono", "Fira Code", Consolas, monospace;
          font-size: 12px;
          font-weight: 600;
          letter-spacing: -0.02em;
        }

        .fdv-stat--add {
          color: #4ade80;
        }

        .fdv-stat--del {
          color: #f87171;
        }

        .fdv-content {
          max-height: 400px;
          overflow-y: auto;
          overflow-x: auto;
          background: #0d1117;
        }

        .fdv-line {
          display: flex;
          align-items: stretch;
          min-height: 22px;
          font-family: "SF Mono", "Fira Code", "JetBrains Mono", Consolas, monospace;
          font-size: 13px;
          line-height: 22px;
        }

        .fdv-line--addition {
          background: rgba(46, 160, 67, 0.15);
        }

        .fdv-line--deletion {
          background: rgba(248, 81, 73, 0.15);
        }

        .fdv-line--context {
          background: transparent;
        }

        .fdv-line-number {
          display: inline-block;
          min-width: 40px;
          padding: 0 8px;
          text-align: right;
          color: rgba(255, 255, 255, 0.3);
          font-size: 12px;
          user-select: none;
          flex-shrink: 0;
        }

        .fdv-line--addition .fdv-line-number--new {
          background: rgba(46, 160, 67, 0.25);
          color: rgba(255, 255, 255, 0.5);
        }

        .fdv-line--deletion .fdv-line-number--old {
          background: rgba(248, 81, 73, 0.25);
          color: rgba(255, 255, 255, 0.5);
        }

        .fdv-line-marker {
          display: inline-block;
          width: 20px;
          text-align: center;
          color: rgba(255, 255, 255, 0.4);
          flex-shrink: 0;
          user-select: none;
        }

        .fdv-line--addition .fdv-line-marker {
          color: #4ade80;
          font-weight: 600;
        }

        .fdv-line--deletion .fdv-line-marker {
          color: #f87171;
          font-weight: 600;
        }

        .fdv-line-content {
          flex: 1;
          padding-right: 16px;
          white-space: pre;
        }

        .fdv-line-content code {
          font-family: inherit;
          color: #e2e8f0;
        }

        .fdv-empty {
          padding: 16px;
          font-size: 12px;
          color: rgba(255, 255, 255, 0.6);
        }

        .fdv-line--addition .fdv-line-content code {
          color: #7ee787;
        }

        .fdv-line--deletion .fdv-line-content code {
          color: #ffa198;
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

        /* Light theme */
        @media (prefers-color-scheme: light) {
          .fdv-container {
            background: #ffffff;
            border-color: rgba(0, 0, 0, 0.1);
          }

          .fdv-header {
            background: rgba(0, 0, 0, 0.02);
            border-bottom-color: rgba(0, 0, 0, 0.06);
          }

          .fdv-header:hover {
            background: rgba(0, 0, 0, 0.04);
          }

          .fdv-chevron, .fdv-label {
            color: rgba(0, 0, 0, 0.7);
          }

          .fdv-badge--create {
            background-color: rgba(74, 222, 128, 0.1);
            color: #16a34a;
            border-color: rgba(74, 222, 128, 0.25);
          }

          .fdv-badge--edit {
            background-color: rgba(96, 165, 250, 0.1);
            color: #2563eb;
            border-color: rgba(96, 165, 250, 0.25);
          }

          .fdv-badge--delete {
            background-color: rgba(248, 113, 113, 0.1);
            color: #dc2626;
            border-color: rgba(248, 113, 113, 0.25);
          }

          .fdv-copy-btn {
            background: rgba(0, 0, 0, 0.04);
            color: rgba(0, 0, 0, 0.5);
          }

          .fdv-copy-btn:hover {
            background: rgba(0, 0, 0, 0.08);
            color: rgba(0, 0, 0, 0.8);
          }

          .fdv-file-bar {
            background: rgba(0, 0, 0, 0.02);
          }

          .fdv-filename {
            color: #1e293b;
          }

          .fdv-stat--add {
            color: #16a34a;
          }

          .fdv-stat--del {
            color: #dc2626;
          }

          .fdv-content {
            background: #fafafa;
          }

          .fdv-line--addition {
            background: rgba(46, 160, 67, 0.1);
          }

          .fdv-line--deletion {
            background: rgba(248, 81, 73, 0.1);
          }

          .fdv-line-number {
            color: rgba(0, 0, 0, 0.3);
          }

          .fdv-line-content code {
            color: #1e293b;
          }

          .fdv-line--addition .fdv-line-content code {
            color: #166534;
          }

          .fdv-line--deletion .fdv-line-content code {
            color: #991b1b;
          }
        }

        :root.vscode-light .fdv-container,
        [data-vscode-theme-kind="vscode-light"] .fdv-container {
          background: #ffffff;
          border-color: rgba(0, 0, 0, 0.1);
        }
      `}</style>
    </div>
  );
};

export default FileDiffView;
