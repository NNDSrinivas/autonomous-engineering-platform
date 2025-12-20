import { useReviewStream, ReviewEntry } from '../../hooks/useReviewStream';

export function SimpleLiveReview() {
  const { 
    isStreaming, 
    currentStep, 
    entries, 
    error,
    startReview
  } = useReviewStream();

  // All SSE logic is handled by the useReviewStream hook

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'high': return 'text-red-400';
      case 'medium': return 'text-yellow-400';
      case 'low': return 'text-blue-400';
      default: return 'text-gray-400';
    }
  };

  const getSeverityBg = (severity: string) => {
    switch (severity) {
      case 'high': return 'bg-red-900/20 border-red-500/30';
      case 'medium': return 'bg-yellow-900/20 border-yellow-500/30';
      case 'low': return 'bg-blue-900/20 border-blue-500/30';
      default: return 'bg-gray-900/20 border-gray-500/30';
    }
  };

  return (
    <div className="space-y-4 p-4 bg-gray-950 border border-gray-800 rounded-lg">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">⚡ Live Code Review</h3>
        <button
          onClick={startReview}
          disabled={isStreaming}
          className={`px-4 py-2 rounded-lg font-medium transition-all duration-200 ${isStreaming
              ? 'bg-gray-600 text-gray-300 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-500 text-white'
            }`}
        >
          {isStreaming ? (
            <span className="flex items-center space-x-2">
              <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></div>
              <span>Analyzing...</span>
            </span>
          ) : (
            <span>Start Review</span>
          )}
        </button>
      </div>

      {/* Progress */}
      {currentStep && (
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-3">
          <div className="flex items-center space-x-2 text-sm text-gray-300">
            <div className="animate-pulse h-2 w-2 bg-blue-500 rounded-full"></div>
            <span>{currentStep}</span>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-900/20 border border-red-500/30 rounded-lg p-3">
          <div className="flex items-center space-x-2 text-sm text-red-400">
            <span>❌</span>
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Results */}
      {entries.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-300 border-b border-gray-700 pb-1">
            📋 Review Results ({entries.length} files)
          </h4>

          {entries.map((entry: ReviewEntry, index: number) => (
            <div key={index} className="bg-gray-900 border border-gray-700 rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <h5 className="text-sm font-medium text-white">{entry.filePath}</h5>
                <span className={`text-xs px-2 py-1 rounded ${getSeverityBg(entry.severity)} ${getSeverityColor(entry.severity)}`}>
                  {entry.severity}
                </span>
              </div>

              {entry.issues.length > 0 ? (
                <div className="space-y-2">
                  {entry.issues.map((issue, issueIndex: number) => (
                    <div key={issueIndex} className={`p-2 rounded border ${getSeverityBg(issue.severity)}`}>
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <h6 className={`text-sm font-medium ${getSeverityColor(issue.severity)}`}>
                            {issue.title}
                          </h6>
                          <p className="text-xs text-gray-400 mt-1">{issue.description}</p>
                        </div>
                        {issue.canAutoFix && (
                          <button
                            className="ml-2 px-2 py-1 text-xs bg-green-600 hover:bg-green-500 text-white rounded transition-colors"
                            onClick={() => console.log('Auto-fix clicked:', issue.fixId)}
                          >
                            ✨ Auto-fix
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-gray-500 italic">No issues found</p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Summary */}
      {!isStreaming && entries.length > 0 && (
        <div className="text-xs text-gray-500 text-center pt-2 border-t border-gray-800">
          Analysis complete • {entries.reduce((sum: number, entry: ReviewEntry) => sum + entry.issues.length, 0)} total issues found
        </div>
      )}
    </div>
  );
}