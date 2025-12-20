import { useState } from 'react';
import { useReviewStream, ReviewEntry } from '../../hooks/useReviewStream';
import { AutoFixButton } from './AutoFixButton';

export function SimpleLiveReview() {
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set());
  const [showDiffs, setShowDiffs] = useState<Set<string>>(new Set());
  
  const {
    isStreaming,
    currentStep,
    entries,
    error,
    isComplete,
    startReview,
    stopReview,
    resetReview,
  } = useReviewStream();

  const toggleFileExpansion = (filePath: string) => {
    setExpandedFiles(prev => {
      const newSet = new Set(prev);
      if (newSet.has(filePath)) {
        newSet.delete(filePath);
      } else {
        newSet.add(filePath);
      }
      return newSet;
    });
  };

  const toggleDiffView = (filePath: string) => {
    setShowDiffs(prev => {
      const newSet = new Set(prev);
      if (newSet.has(filePath)) {
        newSet.delete(filePath);
      } else {
        newSet.add(filePath);
      }
      return newSet;
    });
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'high': return 'border-red-500 bg-red-500/10';
      case 'medium': return 'border-yellow-500 bg-yellow-500/10';
      case 'low': return 'border-blue-500 bg-blue-500/10';
      default: return 'border-gray-500 bg-gray-500/10';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'high': return '🔴';
      case 'medium': return '🟡';
      case 'low': return '🔵';
      default: return '⚪';
    }
  };

  const generateDiffView = (entry: ReviewEntry) => {
    // Simple diff visualization
    const baseLines = entry.baseContent.split('\n');
    const updatedLines = entry.updatedContent.split('\n');
    
    const diffLines: Array<{ type: 'context' | 'added' | 'removed'; content: string; lineNum?: number }> = [];
    
    // Basic line-by-line diff (simplified)
    const maxLines = Math.max(baseLines.length, updatedLines.length);
    
    for (let i = 0; i < maxLines; i++) {
      const baseLine = baseLines[i] || '';
      const updatedLine = updatedLines[i] || '';
      
      if (baseLine !== updatedLine) {
        if (baseLine && !updatedLine) {
          diffLines.push({ type: 'removed', content: baseLine, lineNum: i + 1 });
        } else if (!baseLine && updatedLine) {
          diffLines.push({ type: 'added', content: updatedLine, lineNum: i + 1 });
        } else {
          diffLines.push({ type: 'removed', content: baseLine, lineNum: i + 1 });
          diffLines.push({ type: 'added', content: updatedLine, lineNum: i + 1 });
        }
      } else if (diffLines.length > 0 && diffLines.length < 20) {
        // Show some context around changes
        diffLines.push({ type: 'context', content: baseLine, lineNum: i + 1 });
      }
    }
    
    return diffLines.slice(0, 50); // Limit to 50 lines
  };

  return (
    <div className="p-4 space-y-4">
      {/* Header Controls */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-100">⚡ Live Code Review</h3>
        <div className="flex gap-2">
          {!isStreaming && !isComplete && (
            <button
              onClick={startReview}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              Start Review
            </button>
          )}
          {isStreaming && (
            <button
              onClick={stopReview}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              Stop Review
            </button>
          )}
          {(isComplete || error) && (
            <button
              onClick={resetReview}
              className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              Reset
            </button>
          )}
        </div>
      </div>

      {/* Progress Indicator */}
      {isStreaming && currentStep && (
        <div className="flex items-center gap-3 p-3 bg-blue-600/20 border border-blue-500/50 rounded-lg">
          <div className="animate-spin w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full"></div>
          <span className="text-blue-100 text-sm">{currentStep}</span>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="p-3 bg-red-600/20 border border-red-500/50 rounded-lg">
          <span className="text-red-100 text-sm">❌ {error}</span>
        </div>
      )}

      {/* Completion Status */}
      {isComplete && !error && (
        <div className="p-3 bg-green-600/20 border border-green-500/50 rounded-lg">
          <span className="text-green-100 text-sm">✅ Review complete! Found {entries.length} files to review.</span>
        </div>
      )}

      {/* Review Results */}
      <div className="space-y-3">
        {entries.map((entry, index) => (
          <div
            key={`${entry.filePath}-${index}`}
            className={`border rounded-lg overflow-hidden ${getSeverityColor(entry.severity)}`}
          >
            {/* File Header */}
            <div
              className="flex items-center justify-between p-3 cursor-pointer hover:bg-black/20 transition-colors"
              onClick={() => toggleFileExpansion(entry.filePath)}
            >
              <div className="flex items-center gap-3">
                <span className="text-lg">{getSeverityIcon(entry.severity)}</span>
                <div>
                  <div className="font-mono text-sm text-gray-100">{entry.filePath}</div>
                  <div className="text-xs text-gray-400">
                    {entry.issues.length} issue{entry.issues.length !== 1 ? 's' : ''} • {entry.severity} severity
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400">
                  {expandedFiles.has(entry.filePath) ? '▼' : '▶'}
                </span>
              </div>
            </div>

            {/* Expanded Content */}
            {expandedFiles.has(entry.filePath) && (
              <div className="border-t border-current/20">
                {/* Issues List */}
                <div className="p-3 space-y-2">
                  <h4 className="text-sm font-medium text-gray-200">Issues Found:</h4>
                  {entry.issues.map((issue) => (
                    <div key={issue.id} className="flex items-start gap-2 p-2 bg-black/20 rounded">
                      <span className="text-xs mt-1">{getSeverityIcon(issue.severity)}</span>
                      <div className="flex-1">
                        <div className="text-sm font-medium text-gray-100">{issue.title}</div>
                        <div className="text-xs text-gray-300 mt-1">{issue.description}</div>
                        {issue.canAutoFix && issue.fixId && (
                          <div className="mt-2">
                            <AutoFixButton 
                              filePath={entry.filePath}
                              fixId={issue.fixId} 
                              fixTitle={issue.title}
                              onFixApplied={(result) => {
                                console.log(`Fix applied for ${issue.id}:`, result);
                                // Optionally refresh the review
                              }}
                              onFixFailed={(error) => {
                                console.error(`Fix failed for ${issue.id}:`, error);
                              }}
                            />
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Diff View Toggle */}
                {(entry.baseContent || entry.updatedContent) && (
                  <div className="px-3 pb-3">
                    <button
                      onClick={() => toggleDiffView(entry.filePath)}
                      className="text-xs text-blue-400 hover:text-blue-300 underline"
                    >
                      {showDiffs.has(entry.filePath) ? 'Hide Diff' : 'Show Diff'}
                    </button>
                  </div>
                )}

                {/* Diff Display */}
                {showDiffs.has(entry.filePath) && (entry.baseContent || entry.updatedContent) && (
                  <div className="border-t border-current/20 bg-black/30">
                    <div className="p-3">
                      <h4 className="text-sm font-medium text-gray-200 mb-2">Code Changes:</h4>
                      <div className="bg-gray-900 rounded border font-mono text-xs overflow-x-auto">
                        {generateDiffView(entry).map((line, lineIndex) => (
                          <div
                            key={lineIndex}
                            className={`px-2 py-1 ${
                              line.type === 'added'
                                ? 'bg-green-900/50 text-green-100'
                                : line.type === 'removed'
                                ? 'bg-red-900/50 text-red-100'
                                : 'text-gray-300'
                            }`}
                          >
                            <span className="text-gray-500 w-8 inline-block text-right mr-2">
                              {line.lineNum}
                            </span>
                            <span className="text-gray-400 mr-1">
                              {line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' '}
                            </span>
                            <span>{line.content}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Empty State */}
      {!isStreaming && !error && entries.length === 0 && (
        <div className="text-center py-8 text-gray-400">
          <div className="text-4xl mb-2">🔍</div>
          <div className="text-sm">No review data yet. Click "Start Review" to analyze your code.</div>
        </div>
      )}
    </div>
  );
}

export default SimpleLiveReview;