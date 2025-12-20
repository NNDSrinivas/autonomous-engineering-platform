import React from "react";
import Hunk from "./Hunk";

interface InlineViewProps {
  file: {
    path: string;
    hunks: Array<{
      id: string;
      header: string;
      lines: Array<{ type: string; content: string }>;
      explainable?: boolean;
    }>;
  };
  onApplyHunk: (hunkId: string, filePath: string) => void;
  onExplainHunk: (hunkId: string, filePath: string, onMessage: (msg: string) => void) => void;
}

export default function InlineView({ file, onApplyHunk, onExplainHunk }: InlineViewProps) {
  return (
    <div className="inline-root">
      {file.hunks.map(h => (
        <Hunk
          key={h.id}
          hunk={h}
          mode="inline"
          filePath={file.path}
          onApplyHunk={onApplyHunk}
          onExplainHunk={onExplainHunk}
        />
      ))}
    </div>
  );
}
