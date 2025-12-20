import React, { useState } from 'react';
import SyntaxHighlighter from 'react-syntax-highlighter/dist/esm/light';
import { atomOneDark } from 'react-syntax-highlighter/dist/esm/styles/hljs';
import diff from 'react-syntax-highlighter/dist/esm/languages/hljs/diff';

// Register diff language
SyntaxHighlighter.registerLanguage('diff', diff);

interface DiffViewerProps {
  hunk: string;
  fileName?: string;
  className?: string;
}

export function DiffViewer({ hunk, fileName, className = '' }: DiffViewerProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  if (!hunk || !hunk.trim()) {
    return (
      <div className={`border bg-gray-50 rounded p-3 text-sm text-gray-500 ${className}`}>
        No diff content available
      </div>
    );
  }

  // Parse diff statistics
  const lines = hunk.split('\n');
  const addedLines = lines.filter(line => line.startsWith('+')).length;
  const removedLines = lines.filter(line => line.startsWith('-')).length;
  const contextLines = lines.filter(line => line.startsWith(' ')).length;

  return (
    <div className={`border bg-gray-50 rounded overflow-hidden ${className}`}>
      {/* Header */}
      <div 
        className="px-4 py-2 bg-gray-100 cursor-pointer flex items-center justify-between hover:bg-gray-200 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center space-x-3">
          <span className="text-sm font-medium text-gray-700">
            {isExpanded ? '▼' : '▶'} View Diff
          </span>
          {fileName && (
            <span className="text-xs text-gray-500 font-mono">
              {fileName}
            </span>
          )}
        </div>
        
        <div className="flex items-center space-x-4 text-xs">
          {addedLines > 0 && (
            <span className="text-green-600 font-medium">
              +{addedLines}
            </span>
          )}
          {removedLines > 0 && (
            <span className="text-red-600 font-medium">
              -{removedLines}
            </span>
          )}
          <span className="text-gray-500">
            {lines.length} lines
          </span>
        </div>
      </div>

      {/* Diff Content */}
      {isExpanded && (
        <div className="relative">
          <SyntaxHighlighter
            language="diff"
            style={atomOneDark}
            customStyle={{
              margin: 0,
              padding: '16px',
              fontSize: '12px',
              lineHeight: '1.4',
              fontFamily: 'Monaco, Menlo, "Ubuntu Mono", monospace'
            }}
            showLineNumbers={false}
            wrapLines={true}
            lineProps={(lineNumber) => {
              const line = lines[lineNumber - 1];
              const style: React.CSSProperties = { display: 'block' };
              
              if (line?.startsWith('+')) {
                style.backgroundColor = 'rgba(34, 197, 94, 0.15)';
              } else if (line?.startsWith('-')) {
                style.backgroundColor = 'rgba(239, 68, 68, 0.15)';
              } else if (line?.startsWith('@@')) {
                style.backgroundColor = 'rgba(59, 130, 246, 0.15)';
                style.fontWeight = 'bold';
              }
              
              return { style };
            }}
          >
            {hunk}
          </SyntaxHighlighter>
          
          {/* Copy button */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              navigator.clipboard.writeText(hunk);
            }}
            className="absolute top-2 right-2 px-2 py-1 bg-gray-700 text-gray-200 text-xs rounded hover:bg-gray-600 transition-colors"
            title="Copy diff to clipboard"
          >
            Copy
          </button>
        </div>
      )}

      {/* Quick Stats (when collapsed) */}
      {!isExpanded && (
        <div className="px-4 py-2 text-xs text-gray-600 bg-white border-t">
          <div className="flex justify-between items-center">
            <span>
              {addedLines + removedLines} changes in {lines.filter(l => l.startsWith('@@')).length} hunk(s)
            </span>
            <span className="text-gray-400">
              Click to expand
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

export default DiffViewer;