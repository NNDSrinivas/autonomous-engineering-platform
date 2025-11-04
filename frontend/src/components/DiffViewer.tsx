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

  const lines = diff.split(/\r?\n/);

  return (
    <pre
      className={`bg-slate-50 dark:bg-slate-900 rounded-lg p-4 overflow-auto text-sm leading-6 font-mono border border-slate-200 dark:border-slate-800 ${className}`}
    >
      {lines.map((line, i) => (
        <div key={`${i}-${line.slice(0, 20)}`} className={`${getLineColor(line)} whitespace-pre`}>
          {line || " "}
        </div>
      ))}
    </pre>
  );
};

export default DiffViewer;
