import React, { useState } from 'react';

interface PatchFile {
  path: string;
  diff?: string;
  modified?: string;
  original?: string;
  hasConflicts?: boolean;
}

interface PatchBundle {
  files: PatchFile[];
  description?: string;
  statistics?: {
    lines?: {
      added: number;
      removed: number;
    };
    files_modified: number;
  };
  ready_to_apply: boolean;
  timestamp?: number;
}

interface DiffApplyPanelProps {
  patchBundle: PatchBundle;
  onApplyAll?: (patchBundle: PatchBundle) => void;
  onApplyFile?: (filePath: string, content: string) => void;
  onUndo?: () => void;
  className?: string;
}

const getFileBasename = (filePath: string): string => {
  return filePath.split('/').pop() || filePath;
};

const formatFileSize = (content?: string): string => {
  if (!content) return '0 B';
  const bytes = new Blob([content]).size;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export const DiffApplyPanel: React.FC<DiffApplyPanelProps> = ({
  patchBundle,
  onApplyAll,
  onApplyFile,
  onUndo,
  className = ''
}) => {
  const [isApplying, setIsApplying] = useState(false);
  const [appliedFiles, setAppliedFiles] = useState<Set<string>>(new Set());

  const vscodeApi = (window as any).acquireVsCodeApi?.();

  const handleApplyAll = async () => {
    if (isApplying) return;

    setIsApplying(true);
    try {
      if (onApplyAll) {
        onApplyAll(patchBundle);
      } else if (vscodeApi) {
        vscodeApi.postMessage({
          type: 'applyAll',
          payload: patchBundle
        });
      }

      // Mark all files as applied
      setAppliedFiles(new Set(patchBundle.files.map(f => f.path)));
    } catch (error) {
      console.error('Error applying all patches:', error);
    } finally {
      setIsApplying(false);
    }
  };

  const handleApplyFile = async (file: PatchFile) => {
    if (isApplying || appliedFiles.has(file.path)) return;

    setIsApplying(true);
    try {
      const content = file.modified || file.diff || '';

      if (onApplyFile) {
        onApplyFile(file.path, content);
      } else if (vscodeApi) {
        vscodeApi.postMessage({
          type: 'applyFile',
          payload: {
            filePath: file.path,
            content
          }
        });
      }

      // Mark file as applied
      setAppliedFiles(prev => new Set([...prev, file.path]));
    } catch (error) {
      console.error(`Error applying patch to ${file.path}:`, error);
    } finally {
      setIsApplying(false);
    }
  };

  const handleUndo = () => {
    if (onUndo) {
      onUndo();
    } else if (vscodeApi) {
      vscodeApi.postMessage({ type: 'undo' });
    }

    // Clear applied files
    setAppliedFiles(new Set());
  };

  const conflictFiles = patchBundle.files.filter(f => f.hasConflicts);
  const totalFiles = patchBundle.files.length;
  const appliedCount = appliedFiles.size;
  const hasConflicts = conflictFiles.length > 0;

  return (
    <div className={`bg-white border border-gray-300 rounded-lg overflow-hidden ${className}`}>
      {/* Header */}
      <div className="bg-gray-50 border-b border-gray-200 p-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-800 flex items-center">
              📦 Patch Bundle
              {patchBundle.ready_to_apply ? (
                <span className="ml-2 text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full">
                  Ready
                </span>
              ) : (
                <span className="ml-2 text-xs bg-yellow-100 text-yellow-700 px-2 py-1 rounded-full">
                  Review Required
                </span>
              )}
            </h3>

            {patchBundle.description && (
              <p className="text-sm text-gray-600 mt-1">{patchBundle.description}</p>
            )}
          </div>

          <div className="text-right">
            <div className="text-sm text-gray-600">
              {appliedCount > 0 ? `${appliedCount}/${totalFiles}` : totalFiles} files
            </div>
            {patchBundle.statistics && (
              <div className="text-xs text-gray-500 flex space-x-3 mt-1">
                {patchBundle.statistics.lines?.added && (
                  <span className="text-green-600">
                    +{patchBundle.statistics.lines.added}
                  </span>
                )}
                {patchBundle.statistics.lines?.removed && (
                  <span className="text-red-600">
                    -{patchBundle.statistics.lines.removed}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Conflicts Warning */}
      {hasConflicts && (
        <div className="bg-yellow-50 border-b border-yellow-200 p-3">
          <div className="flex items-center space-x-2">
            <span className="text-yellow-600">⚠️</span>
            <div className="text-sm text-yellow-800">
              <strong>Merge conflicts detected</strong> in {conflictFiles.length} file{conflictFiles.length !== 1 ? 's' : ''}:
              <div className="mt-1 font-mono text-xs">
                {conflictFiles.slice(0, 3).map(f => getFileBasename(f.path)).join(', ')}
                {conflictFiles.length > 3 && ` and ${conflictFiles.length - 3} more`}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="p-4 space-y-3">
        <div className="flex flex-wrap gap-3">
          <button
            onClick={handleApplyAll}
            disabled={isApplying || !patchBundle.ready_to_apply}
            className={`
              px-4 py-2 rounded-lg font-medium text-sm flex items-center space-x-2
              ${patchBundle.ready_to_apply && !isApplying
                ? 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-2 focus:ring-blue-500'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
              }
              transition-colors
            `}
          >
            {isApplying ? (
              <>
                <div className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
                <span>Applying...</span>
              </>
            ) : (
              <>
                <span>🚀</span>
                <span>Apply All Changes</span>
              </>
            )}
          </button>

          <button
            onClick={handleUndo}
            disabled={isApplying || appliedFiles.size === 0}
            className="
              px-4 py-2 rounded-lg font-medium text-sm
              bg-gray-600 text-white hover:bg-gray-700 disabled:bg-gray-300 disabled:text-gray-500
              transition-colors flex items-center space-x-2
            "
          >
            <span>↩️</span>
            <span>Undo Last Changes</span>
          </button>

          <button
            onClick={() => {
              if (vscodeApi) {
                vscodeApi.postMessage({ type: 'showUndoHistory' });
              }
            }}
            className="
              px-3 py-2 rounded-lg font-medium text-sm
              bg-gray-100 text-gray-700 hover:bg-gray-200
              transition-colors flex items-center space-x-1
            "
          >
            <span>📋</span>
            <span>History</span>
          </button>
        </div>

        {/* Progress bar */}
        {appliedCount > 0 && (
          <div className="mt-3">
            <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
              <span>Progress</span>
              <span>{appliedCount}/{totalFiles} files applied</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-green-500 h-2 rounded-full transition-all duration-300"
                style={{ width: `${(appliedCount / totalFiles) * 100}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* File List */}
      <div className="border-t border-gray-200">
        <div className="max-h-64 overflow-y-auto">
          {patchBundle.files.map(file => {
            const isApplied = appliedFiles.has(file.path);

            return (
              <div
                key={file.path}
                className={`
                  flex items-center justify-between p-3 border-b border-gray-100 last:border-b-0
                  ${isApplied ? 'bg-green-50' : 'hover:bg-gray-50'}
                  ${file.hasConflicts ? 'bg-yellow-50' : ''}
                `}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-mono text-gray-800 truncate">
                      {getFileBasename(file.path)}
                    </span>

                    {isApplied && (
                      <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                        ✓ Applied
                      </span>
                    )}

                    {file.hasConflicts && (
                      <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full">
                        ⚠️ Conflict
                      </span>
                    )}
                  </div>

                  <div className="text-xs text-gray-500 mt-1">
                    {file.path} • {formatFileSize(file.modified || file.diff)}
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => {
                      if (vscodeApi) {
                        vscodeApi.postMessage({
                          type: 'viewFile',
                          payload: { filePath: file.path }
                        });
                      }
                    }}
                    className="
                      px-2 py-1 text-xs
                      bg-gray-100 text-gray-600 hover:bg-gray-200
                      rounded transition-colors
                    "
                  >
                    👁️ View
                  </button>

                  <button
                    onClick={() => handleApplyFile(file)}
                    disabled={isApplying || isApplied || file.hasConflicts}
                    className={`
                      px-2 py-1 text-xs rounded transition-colors
                      ${!isApplied && !file.hasConflicts && !isApplying
                        ? 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                        : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                      }
                    `}
                  >
                    {isApplied ? '✓' : '⚡'} Apply
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer */}
      <div className="bg-gray-50 border-t border-gray-200 px-4 py-3">
        <div className="text-xs text-gray-500">
          <p>
            💡 <strong>Tip:</strong> Review changes before applying.
            Undo is available for recent operations.
            {hasConflicts && ' Resolve conflicts before applying patches.'}
          </p>

          {patchBundle.timestamp && (
            <p className="mt-1">
              Generated: {new Date(patchBundle.timestamp).toLocaleString()}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default DiffApplyPanel;
