import React, { useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronRight,
  Eye,
  File,
  FileCode,
  FileCog,
  FileJson,
  FileText,
  GitBranch,
  Undo2,
} from "lucide-react";

export interface FileChange {
  path: string;
  displayPath?: string;
  hoverPath?: string;
  additions?: number;
  deletions?: number;
  originalContent?: string;
  wasCreated?: boolean;
  wasDeleted?: boolean;
  status?: "added" | "modified" | "deleted";
}

export interface FileChangeSummaryProps {
  files: FileChange[];
  totalAdditions?: number;
  totalDeletions?: number;
  onKeep: () => void;
  onUndo: () => void;
  onFileClick?: (filePath: string) => void;
  onPreviewAll?: () => void;
  onKeepFile?: (file: FileChange) => void;
  onUndoFile?: (file: FileChange) => void;
  onOpenFileDiff?: (file: FileChange) => void;
  expanded?: boolean;
  onToggle?: (expanded: boolean) => void;
}

const getFileIcon = (filePath: string) => {
  const ext = filePath.split(".").pop()?.toLowerCase() || "";
  switch (ext) {
    case "ts":
    case "tsx":
      return <FileCode size={14} className="fcs-icon fcs-icon--ts" />;
    case "js":
    case "jsx":
    case "mjs":
      return <FileCode size={14} className="fcs-icon fcs-icon--js" />;
    case "py":
    case "pyw":
      return <FileCode size={14} className="fcs-icon fcs-icon--py" />;
    case "go":
      return <FileCode size={14} className="fcs-icon fcs-icon--go" />;
    case "rs":
      return <FileCode size={14} className="fcs-icon fcs-icon--rs" />;
    case "java":
    case "kt":
      return <FileCode size={14} className="fcs-icon fcs-icon--java" />;
    case "c":
    case "cpp":
    case "h":
    case "cs":
      return <FileCode size={14} className="fcs-icon fcs-icon--c" />;
    case "rb":
      return <FileCode size={14} className="fcs-icon fcs-icon--rb" />;
    case "php":
      return <FileCode size={14} className="fcs-icon fcs-icon--php" />;
    case "swift":
      return <FileCode size={14} className="fcs-icon fcs-icon--swift" />;
    case "json":
    case "jsonc":
      return <FileJson size={14} className="fcs-icon fcs-icon--json" />;
    case "yaml":
    case "yml":
    case "toml":
      return <FileCog size={14} className="fcs-icon fcs-icon--yaml" />;
    case "md":
    case "mdx":
    case "txt":
    case "rst":
      return <FileText size={14} className="fcs-icon fcs-icon--md" />;
    case "css":
    case "scss":
    case "less":
      return <FileCode size={14} className="fcs-icon fcs-icon--css" />;
    case "html":
    case "htm":
      return <FileCode size={14} className="fcs-icon fcs-icon--html" />;
    case "config":
    case "env":
    case "gitignore":
    case "dockerfile":
      return <FileCog size={14} className="fcs-icon fcs-icon--config" />;
    default:
      return <File size={14} className="fcs-icon" />;
  }
};

const parseFilePath = (filePath: string): { filename: string; directory: string } => {
  if (!filePath) return { filename: "Unknown file", directory: "" };
  const parts = filePath.split("/");
  const filename = parts.pop() || filePath;
  const directory = parts.length > 0 ? parts.join("/") : "";
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
  onKeepFile,
  onUndoFile,
  onOpenFileDiff,
  expanded,
  onToggle,
}) => {
  const [internalExpanded, setInternalExpanded] = useState(false);
  const isControlled = typeof expanded === "boolean";
  const isExpanded = isControlled ? Boolean(expanded) : internalExpanded;

  const toggleExpanded = () => {
    const next = !isExpanded;
    if (!isControlled) {
      setInternalExpanded(next);
    }
    onToggle?.(next);
  };

  const additions =
    typeof totalAdditions === "number"
      ? totalAdditions
      : files.reduce((sum, file) => sum + (typeof file.additions === "number" ? file.additions : 0), 0);
  const deletions =
    typeof totalDeletions === "number"
      ? totalDeletions
      : files.reduce((sum, file) => sum + (typeof file.deletions === "number" ? file.deletions : 0), 0);
  const hasAnyFileStats = files.some(
    (file) =>
      typeof file.additions === "number" || typeof file.deletions === "number"
  );
  const hasHeaderStats = hasAnyFileStats && (additions > 0 || deletions > 0);

  if (files.length === 0) return null;

  const openFileDiff = (file: FileChange) => {
    if (onOpenFileDiff) {
      onOpenFileDiff(file);
      return;
    }
    if (onFileClick && file.path) {
      onFileClick(file.path);
    }
  };

  return (
    <div className="fcs-container">
      <div
        className="fcs-header"
        role="button"
        tabIndex={0}
        onClick={toggleExpanded}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            toggleExpanded();
          }
        }}
      >
        <div className="fcs-header-left">
          <span className="fcs-expand-icon">
            {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </span>
          <GitBranch size={14} className="fcs-git-icon" />
          <span className="fcs-count">
            {files.length} file{files.length !== 1 ? "s" : ""} changed
          </span>
          {hasHeaderStats && (
            <div className="fcs-stats">
              {additions > 0 && <span className="fcs-stat fcs-stat--add">+{additions}</span>}
              {deletions > 0 && <span className="fcs-stat fcs-stat--del">-{deletions}</span>}
            </div>
          )}
        </div>
        <div className="fcs-actions" onClick={(event) => event.stopPropagation()}>
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
            <Undo2 size={12} />
            <span>Undo</span>
          </button>
        </div>
      </div>

      <div className={`fcs-file-list ${isExpanded ? "fcs-file-list--expanded" : ""}`}>
        {isExpanded &&
          files.map((file, index) => {
            const effectiveDisplayPath = file.displayPath || file.path;
            const effectiveHoverPath = file.hoverPath || effectiveDisplayPath;
            const { filename, directory } = parseFilePath(effectiveDisplayPath);
            const hasStats =
              typeof file.additions === "number" || typeof file.deletions === "number";
            const additionsCount =
              typeof file.additions === "number" ? file.additions : undefined;
            const deletionsCount =
              typeof file.deletions === "number" ? file.deletions : undefined;
            const derivedStatus =
              file.status ||
              (file.wasCreated ? "added" : file.wasDeleted ? "deleted" : undefined);
            const isDeleted = derivedStatus === "deleted";
            const isAdded = derivedStatus === "added";
            const canOpenDiff = Boolean((onOpenFileDiff || onFileClick) && file.path);

            return (
              <div
                key={file.path || `file-${index}`}
                className={`fcs-file-row ${isDeleted ? "fcs-file-row--deleted" : ""}`}
              >
                <button
                  type="button"
                  className={`fcs-file-main ${!canOpenDiff ? "fcs-file-main--disabled" : ""}`}
                  onClick={() => canOpenDiff && openFileDiff(file)}
                  title={effectiveHoverPath}
                >
                  <div className="fcs-file-info">
                    {getFileIcon(file.path)}
                    <span className={`fcs-filename ${isDeleted ? "fcs-filename--deleted" : ""}`}>
                      {filename}
                    </span>
                    {directory && (
                      <span className="fcs-directory">
                        {directory}
                      </span>
                    )}
                  </div>
                  <div className="fcs-file-stats">
                    {isDeleted ? (
                      <span className="fcs-badge fcs-badge--deleted">deleted</span>
                    ) : (
                      <>
                        {isAdded && <span className="fcs-badge fcs-badge--added">new</span>}
                        {hasStats && additionsCount !== undefined && additionsCount > 0 && (
                          <span className="fcs-stat fcs-stat--add">+{additionsCount}</span>
                        )}
                        {hasStats && deletionsCount !== undefined && deletionsCount > 0 && (
                          <span className="fcs-stat fcs-stat--del">-{deletionsCount}</span>
                        )}
                      </>
                    )}
                  </div>
                </button>

                <div className="fcs-file-actions">
                  {canOpenDiff && (
                    <button
                      type="button"
                      className="fcs-file-icon-btn"
                      title={`Open in diff editor: ${effectiveHoverPath}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        openFileDiff(file);
                      }}
                    >
                      <Eye size={13} />
                    </button>
                  )}
                  {onUndoFile && (
                    <button
                      type="button"
                      className="fcs-file-icon-btn"
                      title={`Undo this file change: ${effectiveHoverPath}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        onUndoFile(file);
                      }}
                    >
                      <Undo2 size={13} />
                    </button>
                  )}
                  {onKeepFile && (
                    <button
                      type="button"
                      className="fcs-file-icon-btn fcs-file-icon-btn--keep"
                      title={`Keep this file change: ${effectiveHoverPath}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        onKeepFile(file);
                      }}
                    >
                      <Check size={13} />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
      </div>

      <style>{`
        .fcs-container {
          margin: 10px 0;
          border-radius: 12px;
          border: 1px solid rgba(99, 102, 241, 0.24);
          background:
            radial-gradient(120% 140% at 0% 0%, rgba(59, 130, 246, 0.1), transparent 46%),
            linear-gradient(150deg, rgba(17, 24, 39, 0.92), rgba(13, 20, 34, 0.98));
          overflow: hidden;
          box-shadow: 0 4px 14px rgba(0, 0, 0, 0.26);
        }

        .fcs-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
          padding: 8px 12px;
          cursor: pointer;
          border-bottom: 1px solid transparent;
          transition: background 140ms ease;
        }

        .fcs-header:hover {
          background: rgba(59, 130, 246, 0.08);
        }

        .fcs-header:focus {
          outline: none;
          background: rgba(59, 130, 246, 0.1);
        }

        .fcs-header-left {
          display: flex;
          align-items: center;
          gap: 8px;
          min-width: 0;
          flex: 1;
        }

        .fcs-expand-icon {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          color: rgba(255, 255, 255, 0.54);
        }

        .fcs-git-icon {
          color: #f97316;
          flex-shrink: 0;
        }

        .fcs-count {
          font-size: 12px;
          font-weight: 650;
          color: var(--vscode-foreground, #e5e7eb);
          white-space: nowrap;
        }

        .fcs-stats {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          margin-left: 4px;
        }

        .fcs-stat {
          display: inline-flex;
          align-items: center;
          font-family: "SF Mono", "Menlo", "Monaco", monospace;
          font-size: 10px;
          line-height: 1;
          font-weight: 650;
          padding: 3px 6px;
          border-radius: 5px;
        }

        .fcs-stat--add {
          color: #4ade80;
          background: rgba(74, 222, 128, 0.14);
        }

        .fcs-stat--del {
          color: #f87171;
          background: rgba(248, 113, 113, 0.14);
        }

        .fcs-badge {
          font-size: 10px;
          line-height: 1;
          font-weight: 650;
          letter-spacing: 0.04em;
          text-transform: uppercase;
          padding: 3px 6px;
          border-radius: 999px;
          border: 1px solid transparent;
        }

        .fcs-badge--deleted {
          color: #fecaca;
          background: rgba(248, 113, 113, 0.16);
          border-color: rgba(248, 113, 113, 0.34);
        }

        .fcs-badge--added {
          color: #bbf7d0;
          background: rgba(22, 163, 74, 0.22);
          border-color: rgba(22, 163, 74, 0.36);
        }

        .fcs-actions {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          flex-shrink: 0;
        }

        .fcs-btn {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          border: none;
          outline: none;
          border-radius: 7px;
          padding: 6px 10px;
          font-size: 11px;
          font-weight: 640;
          cursor: pointer;
          transition: transform 120ms ease, filter 120ms ease, background 120ms ease;
        }

        .fcs-btn:active {
          transform: translateY(1px);
        }

        .fcs-btn--preview {
          color: #ffffff;
          background: linear-gradient(135deg, #8b5cf6, #7c3aed);
        }

        .fcs-btn--keep {
          color: #ffffff;
          background: linear-gradient(135deg, #3b82f6, #2563eb);
        }

        .fcs-btn--undo {
          color: rgba(255, 255, 255, 0.84);
          background: rgba(255, 255, 255, 0.08);
          border: 1px solid rgba(255, 255, 255, 0.13);
        }

        .fcs-btn:hover {
          filter: brightness(1.08);
        }

        .fcs-file-list {
          max-height: 0;
          overflow: hidden;
          padding: 0 8px;
          transition: max-height 220ms ease, padding 220ms ease;
        }

        .fcs-file-list--expanded {
          max-height: 430px;
          overflow-y: auto;
          border-top: 1px solid rgba(255, 255, 255, 0.07);
          padding: 8px;
        }

        .fcs-file-row {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 5px;
          padding: 2px 4px;
          border: 1px solid rgba(255, 255, 255, 0.05);
          border-radius: 8px;
          background: rgba(255, 255, 255, 0.018);
        }

        .fcs-file-row:last-child {
          margin-bottom: 0;
        }

        .fcs-file-row:hover {
          border-color: rgba(96, 165, 250, 0.35);
          background: linear-gradient(90deg, rgba(30, 64, 175, 0.18), rgba(30, 64, 175, 0.03));
        }

        .fcs-file-row--deleted {
          border-color: rgba(248, 113, 113, 0.22);
          background: rgba(127, 29, 29, 0.13);
        }

        .fcs-file-main {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          flex: 1;
          min-width: 0;
          border: none;
          background: transparent;
          cursor: pointer;
          padding: 3px 4px;
          border-radius: 6px;
          text-align: left;
        }

        .fcs-file-main--disabled {
          cursor: default;
        }

        .fcs-file-main:focus {
          outline: 1px solid rgba(96, 165, 250, 0.45);
          outline-offset: 1px;
        }

        .fcs-file-info {
          display: inline-flex;
          align-items: flex-start;
          gap: 8px;
          flex: 1;
          min-width: 0;
          overflow: hidden;
        }

        .fcs-icon {
          color: rgba(255, 255, 255, 0.45);
          flex-shrink: 0;
        }

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
          font-size: 12px;
          font-weight: 540;
          line-height: 1.2;
          color: var(--vscode-foreground, #e5e7eb);
          white-space: normal;
          overflow: visible;
          text-overflow: clip;
          overflow-wrap: anywhere;
          word-break: break-word;
          max-width: none;
          flex-shrink: 0;
        }

        .fcs-filename--deleted {
          color: #fda4af;
          text-decoration: line-through;
        }

        .fcs-directory {
          font-size: 11px;
          line-height: 1.2;
          color: rgba(255, 255, 255, 0.4);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          min-width: 0;
          flex: 1;
        }

        .fcs-file-stats {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          margin-left: 10px;
          flex-shrink: 0;
        }

        .fcs-file-actions {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          opacity: 0;
          transform: translateX(4px);
          pointer-events: none;
          transition: opacity 120ms ease, transform 120ms ease;
        }

        .fcs-file-row:hover .fcs-file-actions,
        .fcs-file-row:focus-within .fcs-file-actions {
          opacity: 1;
          transform: translateX(0);
          pointer-events: auto;
        }

        .fcs-file-icon-btn {
          width: 25px;
          height: 25px;
          border-radius: 6px;
          border: 1px solid rgba(255, 255, 255, 0.14);
          background: rgba(15, 23, 42, 0.7);
          color: rgba(255, 255, 255, 0.82);
          display: inline-flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
        }

        .fcs-file-icon-btn:hover {
          border-color: rgba(96, 165, 250, 0.45);
          background: rgba(30, 64, 175, 0.34);
          color: #ffffff;
        }

        .fcs-file-icon-btn--keep:hover {
          border-color: rgba(74, 222, 128, 0.55);
          background: rgba(21, 128, 61, 0.34);
        }

        .fcs-file-list--expanded::-webkit-scrollbar {
          width: 6px;
        }

        .fcs-file-list--expanded::-webkit-scrollbar-thumb {
          background: rgba(148, 163, 184, 0.35);
          border-radius: 999px;
        }

        :root.vscode-light .fcs-container,
        [data-vscode-theme-kind="vscode-light"] .fcs-container,
        :root.light .fcs-container {
          background:
            radial-gradient(120% 140% at 0% 0%, rgba(37, 99, 235, 0.1), transparent 46%),
            linear-gradient(150deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.98));
          border-color: rgba(59, 130, 246, 0.2);
          box-shadow: 0 3px 12px rgba(15, 23, 42, 0.09);
        }

        :root.vscode-light .fcs-count,
        [data-vscode-theme-kind="vscode-light"] .fcs-count,
        :root.light .fcs-count,
        :root.vscode-light .fcs-filename,
        [data-vscode-theme-kind="vscode-light"] .fcs-filename,
        :root.light .fcs-filename {
          color: #0f172a;
        }

        :root.vscode-light .fcs-directory,
        [data-vscode-theme-kind="vscode-light"] .fcs-directory,
        :root.light .fcs-directory {
          color: rgba(15, 23, 42, 0.45);
        }

        :root.vscode-light .fcs-file-row,
        [data-vscode-theme-kind="vscode-light"] .fcs-file-row,
        :root.light .fcs-file-row {
          background: rgba(148, 163, 184, 0.08);
          border-color: rgba(100, 116, 139, 0.2);
        }

        :root.vscode-light .fcs-btn--undo,
        [data-vscode-theme-kind="vscode-light"] .fcs-btn--undo,
        :root.light .fcs-btn--undo {
          color: rgba(15, 23, 42, 0.85);
          background: rgba(148, 163, 184, 0.16);
          border-color: rgba(100, 116, 139, 0.28);
        }
      `}</style>
    </div>
  );
};

export default FileChangeSummary;
