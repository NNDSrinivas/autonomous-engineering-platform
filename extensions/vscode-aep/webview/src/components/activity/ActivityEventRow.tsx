import React, { useMemo, useState } from "react";
import {
  AlertCircle,
  BookOpen,
  ChevronDown,
  FileSearch,
  Loader2,
  PenSquare,
  Search,
} from "lucide-react";
import type { ActivityEvent } from "../../types/activity";
import { postMessage } from "../../utils/vscodeApi";
import { DiffPreview } from "./DiffPreview";

type ActivityEventRowProps = {
  event: ActivityEvent;
};

function formatRange(range?: { startLine: number; endLine: number }) {
  if (!range) return "";
  if (range.startLine === range.endLine) return ` (line ${range.startLine})`;
  return ` (lines ${range.startLine}-${range.endLine})`;
}

function formatStats(stats?: { added: number; removed: number }) {
  if (!stats) return "";
  const parts = [];
  if (stats.added > 0) parts.push(`+${stats.added}`);
  if (stats.removed > 0) parts.push(`-${stats.removed}`);
  return parts.length > 0 ? parts.join(" ") : "";
}

export function ActivityEventRow({ event }: ActivityEventRowProps) {
  const [expanded, setExpanded] = useState(false);
  const statsLabel = useMemo(() => formatStats(event.type === "edit" ? event.stats : undefined), [event]);

  if (event.type === "analysis") {
    return (
      <div className="rounded-lg border border-border/60 bg-secondary/20 p-3 text-xs text-muted-foreground">
        {event.text}
      </div>
    );
  }

  if (event.type === "progress") {
    const percent = typeof event.percent === "number" ? Math.max(0, Math.min(100, event.percent)) : null;
    return (
      <div className="rounded-lg border border-border/70 bg-secondary/30 p-3 text-xs">
        <div className="flex items-center gap-2 text-sm text-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
          <span>{event.label}</span>
          {percent !== null && (
            <span className="ml-auto text-[11px] text-muted-foreground">{percent}%</span>
          )}
        </div>
        {percent !== null && (
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
            <div className="h-full bg-primary/80" style={{ width: `${percent}%` }} />
          </div>
        )}
      </div>
    );
  }

  if (event.type === "error") {
    return (
      <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 p-3 text-xs text-rose-200">
        <div className="flex items-center gap-2 text-sm">
          <AlertCircle className="h-4 w-4" />
          <span>{event.message}</span>
        </div>
        {event.details && (
          <button
            type="button"
            className="mt-2 text-[11px] text-rose-200/80 underline-offset-2 hover:underline"
            onClick={() => setExpanded((prev) => !prev)}
          >
            {expanded ? "Hide details" : "Show details"}
          </button>
        )}
        {event.details && expanded && (
          <pre className="mt-2 whitespace-pre-wrap text-[11px] text-rose-100/80">{event.details}</pre>
        )}
      </div>
    );
  }

  if (event.type === "tool_search") {
    return (
      <div className="rounded-lg border border-border/70 bg-secondary/30 p-3 text-xs">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-sm text-foreground">
            <Search className="h-4 w-4 text-sky-300" />
            <span>
              Searched for <span className="text-sky-200">"{event.query}"</span>
            </span>
          </div>
          <button
            type="button"
            className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
            onClick={() => setExpanded((prev) => !prev)}
          >
            Details
            <ChevronDown className={`h-3 w-3 transition ${expanded ? "rotate-180" : ""}`} />
          </button>
        </div>
        {expanded && (
          <div className="mt-2 rounded-md border border-border/60 bg-slate-950/40 px-3 py-2 text-[11px] font-mono text-slate-300">
            <div>{event.query}</div>
            {event.cwd && <div className="mt-1 text-slate-500">cwd: {event.cwd}</div>}
            {event.files && event.files.length > 0 && (
              <div className="mt-1 text-slate-500">files: {event.files.join(", ")}</div>
            )}
          </div>
        )}
      </div>
    );
  }

  if (event.type === "file_read") {
    return (
      <div className="rounded-lg border border-border/70 bg-secondary/30 p-3 text-xs">
        <div className="flex items-center gap-2 text-sm text-foreground">
          <BookOpen className="h-4 w-4 text-indigo-300" />
          <span>
            Read <span className="font-mono text-indigo-200">{event.path}</span>
            <span className="text-muted-foreground">{formatRange(event.range)}</span>
          </span>
        </div>
      </div>
    );
  }

  if (event.type === "edit") {
    const label = event.summary || `Edited ${event.path}`;
    return (
      <div className="rounded-lg border border-border/70 bg-secondary/30 p-3 text-xs">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm text-foreground">
            <PenSquare className="h-4 w-4 text-emerald-300" />
            <span className="truncate">{label}</span>
            {statsLabel && (
              <span className="rounded-full border border-emerald-500/40 px-2 py-0.5 text-[11px] text-emerald-200">
                {statsLabel}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="rounded-md border border-border/70 px-2 py-1 text-[11px] text-muted-foreground transition hover:text-foreground"
              onClick={() => postMessage({ type: "OPEN_FILE", path: event.path })}
            >
              Open file
            </button>
            <button
              type="button"
              className="rounded-md border border-border/70 px-2 py-1 text-[11px] text-muted-foreground transition hover:text-foreground"
              onClick={() =>
                postMessage(
                  event.diffUnified
                    ? { type: "aep.file.diff", file: event.path }
                    : { type: "OPEN_FILE", path: event.path }
                )
              }
            >
              Review changes
            </button>
          </div>
        </div>
        {event.diffUnified && <DiffPreview diffUnified={event.diffUnified} />}
      </div>
    );
  }

  if (event.type === "phase_start" || event.type === "phase_end") {
    return null;
  }

  return (
    <div className="rounded-lg border border-border/70 bg-secondary/30 p-3 text-xs text-muted-foreground">
      <div className="flex items-center gap-2 text-sm text-foreground">
        <FileSearch className="h-4 w-4" />
        <span>Activity event</span>
      </div>
    </div>
  );
}
