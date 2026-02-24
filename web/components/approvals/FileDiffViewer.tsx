/**
 * FileDiffViewer Component
 * Displays file changes with syntax highlighting using react-diff-view
 */

import React, { useMemo } from 'react';
import { Diff, Hunk, parseDiff } from 'react-diff-view';
import * as diffLib from 'diff';
import { FileCode, FilePlus, FileX, Minus, Plus } from 'lucide-react';
import 'react-diff-view/style/index.css';

export interface FileDiff {
  oldPath?: string;
  newPath?: string;
  oldContent?: string;
  newContent: string;
  type: 'modify' | 'add' | 'delete';
}

export interface FileDiffViewerProps {
  diffs: FileDiff[];
  className?: string;
}

function generateUnifiedDiff(fileDiff: FileDiff): string {
  const { oldPath = 'file', newPath = 'file', oldContent = '', newContent, type } = fileDiff;

  // Ensure content has consistent newline handling
  // diffLib expects content to end with newline for proper patch generation
  const normalizeContent = (content: string) => {
    if (!content) return '';
    return content.endsWith('\n') ? content : content + '\n';
  };

  const normalizedOldContent = normalizeContent(oldContent);
  const normalizedNewContent = normalizeContent(newContent);

  // Use diff library for all cases to ensure consistent, valid unified diff format
  if (type === 'add') {
    // New file - generate patch from empty string to new content
    const patch = diffLib.createPatch(
      newPath,
      '',
      normalizedNewContent,
      '',
      ''
    );
    return patch;
  }

  if (type === 'delete') {
    // Deleted file - generate patch from old content to empty string
    const patch = diffLib.createPatch(
      oldPath,
      normalizedOldContent,
      '',
      '',
      ''
    );
    return patch;
  }

  // Modified file
  const patch = diffLib.createPatch(
    newPath,
    normalizedOldContent,
    normalizedNewContent,
    '',
    ''
  );

  return patch;
}

function FileDiffItem({ fileDiff }: { fileDiff: FileDiff }) {
  const diffText = useMemo(() => generateUnifiedDiff(fileDiff), [fileDiff]);
  const files = useMemo(() => {
    try {
      const parsed = parseDiff(diffText);
      // Validate that parsed result has expected structure
      if (!Array.isArray(parsed) || parsed.length === 0) {
        if (typeof window !== 'undefined') {
          console.warn('parseDiff returned empty or invalid result');
        }
        return [];
      }
      return parsed;
    } catch (error) {
      // Only log errors in browser, not during SSR build
      if (typeof window !== 'undefined') {
        console.error('Error parsing diff:', error);
        console.debug('Diff text that failed to parse:', diffText);
      }
      return [];
    }
  }, [diffText]);

  const fileName = fileDiff.newPath || fileDiff.oldPath || 'Unknown file';
  const fileType = fileDiff.type;

  const getFileIcon = () => {
    switch (fileType) {
      case 'add':
        return <FilePlus className="text-green-600" size={16} />;
      case 'delete':
        return <FileX className="text-red-600" size={16} />;
      default:
        return <FileCode className="text-blue-600" size={16} />;
    }
  };

  const getFileLabel = () => {
    switch (fileType) {
      case 'add':
        return 'New file';
      case 'delete':
        return 'Deleted file';
      default:
        return 'Modified file';
    }
  };

  // Count additions and deletions
  let additions = 0;
  let deletions = 0;

  files.forEach((file) => {
    if (file?.hunks) {
      file.hunks.forEach((hunk) => {
        if (hunk?.changes) {
          hunk.changes.forEach((change) => {
            if (change.type === 'insert') additions++;
            if (change.type === 'delete') deletions++;
          });
        }
      });
    }
  });

  return (
    <div className="border rounded-lg overflow-hidden mb-4">
      {/* File Header */}
      <div className="bg-muted/50 px-4 py-2 border-b flex items-center justify-between">
        <div className="flex items-center gap-2">
          {getFileIcon()}
          <span className="font-mono text-sm font-medium">{fileName}</span>
          <span className="text-xs text-muted-foreground">({getFileLabel()})</span>
        </div>

        <div className="flex items-center gap-3 text-xs">
          {additions > 0 && (
            <span className="flex items-center gap-1 text-green-600 dark:text-green-400">
              <Plus size={12} />
              {additions}
            </span>
          )}
          {deletions > 0 && (
            <span className="flex items-center gap-1 text-red-600 dark:text-red-400">
              <Minus size={12} />
              {deletions}
            </span>
          )}
        </div>
      </div>

      {/* Diff Content */}
      <div className="overflow-x-auto">
        {files.map((file, i) => (
          <Diff
            key={i}
            viewType="unified"
            diffType={file.type}
            hunks={file.hunks}
          >
            {(hunks) =>
              hunks.map((hunk) => <Hunk key={hunk.content} hunk={hunk} />)
            }
          </Diff>
        ))}
      </div>
    </div>
  );
}

export function FileDiffViewer({ diffs, className }: FileDiffViewerProps) {
  if (diffs.length === 0) {
    return (
      <div className="text-center text-muted-foreground py-8">
        No file changes to display
      </div>
    );
  }

  return (
    <div className={className}>
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-medium">
          File Changes ({diffs.length} {diffs.length === 1 ? 'file' : 'files'})
        </h4>
      </div>

      {diffs.map((diff, index) => (
        <FileDiffItem key={index} fileDiff={diff} />
      ))}
    </div>
  );
}

export default FileDiffViewer;
