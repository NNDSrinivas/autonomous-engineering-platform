import React from "react";
import Hunk from "./Hunk";

interface SplitViewProps {
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

export default function SplitView({ file, onApplyHunk, onExplainHunk }: SplitViewProps) {
  return (
    <div className="split-root">
      {file.hunks.map(h => (
        <Hunk
          key={h.id}
          hunk={h}
          mode="split"
          filePath={file.path}
          onApplyHunk={onApplyHunk}
          onExplainHunk={onExplainHunk}
        />
      ))}
    </div>
  );
}
