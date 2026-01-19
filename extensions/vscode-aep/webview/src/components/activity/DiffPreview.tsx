import React, { useMemo, useState } from "react";

type DiffPreviewProps = {
  diffUnified: string;
  maxLines?: number;
};

function getLineClass(line: string) {
  if (line.startsWith("@@")) return "text-muted-foreground";
  if (line.startsWith("+") && !line.startsWith("+++")) return "text-emerald-300";
  if (line.startsWith("-") && !line.startsWith("---")) return "text-rose-300";
  if (line.startsWith("diff ") || line.startsWith("index ") || line.startsWith("+++")) {
    return "text-slate-400";
  }
  if (line.startsWith("---")) return "text-slate-500";
  return "text-slate-300";
}

export function DiffPreview({ diffUnified, maxLines = 80 }: DiffPreviewProps) {
  const [expanded, setExpanded] = useState(false);
  const lines = useMemo(() => diffUnified.split("\n"), [diffUnified]);
  const visibleLines = expanded ? lines : lines.slice(0, maxLines);
  const hasMore = lines.length > maxLines;

  return (
    <div className="mt-2 rounded-md border border-border/70 bg-slate-950/40">
      <div className="max-h-48 overflow-auto px-3 py-2 text-[11px] font-mono leading-relaxed">
        {visibleLines.map((line, index) => (
          <div key={`${index}-${line.slice(0, 12)}`} className={getLineClass(line)}>
            {line || " "}
          </div>
        ))}
      </div>
      {hasMore && (
        <button
          type="button"
          className="w-full border-t border-border/70 px-3 py-1.5 text-xs text-muted-foreground transition hover:text-foreground"
          onClick={() => setExpanded((prev) => !prev)}
        >
          {expanded ? "Show less" : `Show ${lines.length - maxLines} more lines`}
        </button>
      )}
    </div>
  );
}
