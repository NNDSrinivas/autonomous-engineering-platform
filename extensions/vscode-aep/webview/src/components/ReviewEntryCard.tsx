import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useVSCodeAPI } from '../hooks/useVSCodeAPI';
import SeverityBadge from './SeverityBadge';
import DiffViewer from './DiffViewer';

// Standardized ReviewEntry schema matching backend
export interface ReviewEntry {
  file: string;
  hunk: string;
  severity: 'low' | 'medium' | 'high';
  title: string;
  body: string;
  fixId: string;
}

interface ReviewEntryCardProps {
  entry: ReviewEntry;
}

export default function ReviewEntryCard({ entry }: ReviewEntryCardProps) {
  const vscode = useVSCodeAPI();
  const [isExpanded, setIsExpanded] = useState(false);
  const [isFixing, setIsFixing] = useState(false);

  const handleGoToFile = () => {
    if (entry.file) {
      vscode.postMessage({
        type: 'aep.file.open',
        file: entry.file,
        line: 1 // Default to line 1 since we have hunk instead of specific line
      });
    }
  };

  const handleOpenDiff = () => {
    if (entry.file) {
      vscode.postMessage({
        type: 'aep.file.diff',
        file: entry.file
      });
    }
  };

  const handleAutoFix = async () => {
    setIsFixing(true);
    try {
      vscode.postMessage({
        type: 'review.applyFix',
        entry: entry
      });
    } finally {
      // Reset fixing state after a delay
      setTimeout(() => setIsFixing(false), 2000);
    }
  };

  const getSeverityIcon = () => {
    switch (entry.severity) {
      case 'high': return '🚫';
      case 'medium': return '⚠️';
      case 'low': return '💡';
      default: return '📝';
    }
  };

  const getSeverityColor = () => {
    switch (entry.severity) {
      case 'high': return 'bg-red-100 text-red-700 border-red-200';
      case 'medium': return 'bg-yellow-100 text-yellow-700 border-yellow-200';
      case 'low': return 'bg-green-100 text-green-700 border-green-200';
      default: return 'bg-gray-100 text-gray-700 border-gray-200';
    }
  };

  return (
    <div className="border rounded-lg p-4 bg-white shadow-sm hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-start space-x-3 flex-1">
          <span className="text-xl">{getSeverityIcon()}</span>
          <div className="flex-1">
            <div className="font-semibold text-base text-gray-900 mb-1">
              {entry.title}
            </div>
            {entry.file && (
              <button
                onClick={handleGoToFile}
                className="text-sm text-blue-600 hover:text-blue-800 hover:underline font-mono"
              >
                📁 {entry.file}
              </button>
            )}
          </div>
        </div>
        <span className={`px-3 py-1 text-xs font-semibold rounded-full border ${getSeverityColor()}`}>
          {entry.severity.toUpperCase()}
        </span>
      </div>
      
      {/* Description */}
      <div className="mb-4">
        <ReactMarkdown
          className="prose prose-sm max-w-none text-gray-700"
          remarkPlugins={[remarkGfm]}
          components={{
            // Customize markdown rendering
            p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
            ul: ({ children }) => <ul className="list-disc ml-4 mb-2">{children}</ul>,
            ol: ({ children }) => <ol className="list-decimal ml-4 mb-2">{children}</ol>,
            li: ({ children }) => <li className="mb-1">{children}</li>,
            code: ({ children }) => (
              <code className="bg-gray-100 px-1 py-0.5 rounded text-xs font-mono">
                {children}
              </code>
            ),
            pre: ({ children }) => (
              <pre className="bg-gray-100 p-2 rounded text-xs overflow-x-auto">
                {children}
              </pre>
            )
          }}
        >
          {entry.body}
        </ReactMarkdown>
      </div>
      
      {/* Diff Viewer */}
      {entry.hunk && (
        <div className="mb-4">
          <DiffViewer 
            hunk={entry.hunk} 
            fileName={entry.file}
            className="text-xs"
          />
        </div>
      )}
      
      {/* Actions */}
      <div className="flex flex-wrap gap-2 pt-3 border-t border-gray-100">
        {entry.file && (
          <button
            onClick={handleGoToFile}
            className="text-xs px-3 py-2 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors"
          >
            📁 Open File
          </button>
        )}
        {entry.file && (
          <button
            onClick={handleOpenDiff}
            className="text-xs px-3 py-2 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors"
          >
            🧾 Open Diff
          </button>
        )}
        
        {entry.fixId && entry.fixId !== 'none' && (
          <button
            onClick={handleAutoFix}
            disabled={isFixing}
            className="text-xs px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isFixing ? '⚙️ Applying...' : '🔧 Auto-fix'}
          </button>
        )}
        
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-xs px-3 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors"
        >
          {isExpanded ? '🔼 Less' : '🔽 More'}
        </button>

        <div className="ml-auto text-xs text-gray-500 flex items-center">
          Fix ID: <code className="ml-1 bg-gray-100 px-1 rounded">{entry.fixId}</code>
        </div>
      </div>
    </div>
  );
}
