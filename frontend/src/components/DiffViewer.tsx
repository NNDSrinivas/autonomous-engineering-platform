/**
 * Unified diff viewer component with syntax highlighting.
 * Displays git-format diffs with colored line prefixes.
 */
import React from "react";

interface DiffViewerProps {
  diff: string;
  className?: string;
}

/**
 * Get appropriate color class for a diff line based on its prefix.
 */
function getLineColor(line: string): string {
  // File headers
  if (
    line.startsWith("+++") ||
    line.startsWith("---") ||
    line.startsWith("diff ") ||
    line.startsWith("index ")
  ) {
    return "text-slate-400 dark:text-slate-500";
  }
  
  // Hunk headers
  if (line.startsWith("@@")) {
    return "text-amber-600 dark:text-amber-400 font-semibold";
  }
  
  // Additions
  if (line.startsWith("+")) {
    return "text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/20";
  }
  
  // Deletions
  if (line.startsWith("-")) {
    return "text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/20";
  }
  
  // Context lines
  return "text-slate-700 dark:text-slate-300";
}

export const DiffViewer: React.FC<DiffViewerProps> = ({ diff, className = "" }) => {
  if (!diff || !diff.trim()) {
    return (
      <div className={`text-slate-500 italic p-4 ${className}`}>
        No diff to display
      </div>
    );
  }

  const lines = React.useMemo(() => diff.split(/\r?\n/), [diff]);
  
  // Precompute keys for each line only when diff changes
  const linesWithKeys = React.useMemo(() => {
    return lines.map((line, index) => {
      // Use a simple hash of the line content for better uniqueness
      const hash = line.split('').reduce((a, b) => {
        a = ((a << 5) - a) + b.charCodeAt(0);
        return a | 0; // Convert to 32-bit integer
      }, 0);
      return {
        line,
        key: `${index}-${Math.abs(hash)}`
      };
    });
  }, [lines]);

  return (
    <pre
      className={`bg-slate-50 dark:bg-slate-900 rounded-lg p-4 overflow-auto text-sm leading-6 font-mono border border-slate-200 dark:border-slate-800 ${className}`}
    >
      {linesWithKeys.map(({ line, key }) => (
        <div key={key} className={`${getLineColor(line)} whitespace-pre`}>
          {line || " "}
        </div>
      ))}
    </pre>
  );
};

export default DiffViewer;
