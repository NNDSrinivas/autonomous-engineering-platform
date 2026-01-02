import React, { useState } from "react";
import ExplainModal from "./ExplainModal";

type Mode = "split" | "inline";

interface HunkLine {
  type: string;
  content: string;
}

interface HunkData {
  id: string;
  header: string;
  lines: HunkLine[];
  explainable?: boolean;
}

interface HunkProps {
  hunk: HunkData;
  mode: Mode;
  filePath: string;
  onApplyHunk: (hunkId: string, filePath: string) => void;
  onExplainHunk: (hunkId: string, filePath: string, onMessage: (msg: string) => void) => void;
}

export default function Hunk({
  hunk,
  mode,
  filePath,
  onApplyHunk,
  onExplainHunk
}: HunkProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [explainOpen, setExplainOpen] = useState(false);

  return (
    <div className="hunk">
      <div className="hunk-header" onClick={() => setCollapsed(!collapsed)}>
        <span className="hunk-arrow">{collapsed ? "▶" : "▼"}</span>
        <span className="hunk-header-text">{hunk.header}</span>

        <div className="hunk-actions">
          <button onClick={() => onApplyHunk(hunk.id, filePath)}>Apply</button>
          {hunk.explainable && (
            <button onClick={() => setExplainOpen(true)}>Explain</button>
          )}
        </div>
      </div>

      {!collapsed && (
        <div className={mode === "split" ? "hunk-body-split" : "hunk-body-inline"}>
          {hunk.lines.map((line, i) => (
            <pre key={i} className={`line-${line.type}`}>
              {line.content}
            </pre>
          ))}
        </div>
      )}

      {explainOpen && (
        <ExplainModal
          hunkId={hunk.id}
          filePath={filePath}
          onClose={() => setExplainOpen(false)}
          onExplain={onExplainHunk}
        />
      )}
    </div>
  );
}
