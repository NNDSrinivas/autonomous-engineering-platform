import React, { useMemo } from "react";
import { Activity, CheckCircle2, Loader2, Trash2 } from "lucide-react";
import { useLiveProgressState } from "../../hooks/useLiveProgress";
import { useUIState } from "../../state/uiStore";
import type { ActivityEvent } from "../../types/activity";
import { postMessage } from "../../utils/vscodeApi";
import { ActivityEventRow } from "./ActivityEventRow";
import { PhaseGroup, type PhaseGroupData } from "./PhaseGroup";

function buildPhaseGroups(events: ActivityEvent[]): PhaseGroupData[] {
  const groups: PhaseGroupData[] = [];
  const stack: PhaseGroupData[] = [];
  let implicitGroup: PhaseGroupData | null = null;

  const getImplicit = () => {
    if (!implicitGroup) {
      implicitGroup = { id: "phase-implicit", title: "Working", events: [], isImplicit: true };
      groups.push(implicitGroup);
    }
    return implicitGroup;
  };

  events.forEach((event) => {
    if (event.type === "phase_start") {
      const group: PhaseGroupData = { id: event.id, title: event.title, events: [] };
      groups.push(group);
      stack.push(group);
      return;
    }

    if (event.type === "phase_end") {
      while (stack.length > 0) {
        const last = stack.pop();
        if (last?.id === event.phaseId) break;
      }
      return;
    }

    const target = stack[stack.length - 1] ?? getImplicit();
    target.events.push(event);
  });

  return groups;
}

export function ActivityPanel() {
  const { state, dispatch } = useUIState();
  const { activeStep, isActive, totalProgress } = useLiveProgressState();

  const runId =
    state.activeRunId ??
    (state.activityRunOrder.length > 0 ? state.activityRunOrder[state.activityRunOrder.length - 1] : null);
  const run = runId ? state.activityByRunId[runId] : null;
  const events = run?.events ?? [];
  const status = run?.status ?? "done";

  const groups = useMemo(() => buildPhaseGroups(events), [events]);
  const hasEvents = events.length > 0;

  const progressEvent = useMemo(() => {
    if (!runId && !activeStep) return null;
    const percent = activeStep?.progress ?? (totalProgress > 0 ? totalProgress : undefined);
    if (!activeStep && percent === undefined && !isActive) return null;
    return {
      id: `progress-${runId ?? "live"}`,
      ts: Date.now(),
      runId: runId ?? "live",
      type: "progress" as const,
      label: activeStep?.title ?? "Running",
      percent,
    };
  }, [runId, activeStep, totalProgress, isActive]);

  return (
    <div className="flex h-full w-full flex-col border-r border-border bg-background/70">
      <div className="sticky top-0 z-10 border-b border-border bg-background/90 px-4 py-3 backdrop-blur">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-secondary/50">
              <Activity className="h-4 w-4 text-primary" />
            </div>
            <div>
              <div className="text-sm font-semibold">Working</div>
              <div className="text-[11px] text-muted-foreground">
                {status === "running" ? "Running" : "Done"}
              </div>
            </div>
          </div>
          <button
            type="button"
            className="flex items-center gap-1 rounded-md border border-border/70 px-2 py-1 text-[11px] text-muted-foreground transition hover:text-foreground"
            onClick={() => {
              if (!runId) return;
              dispatch({ type: "ACTIVITY_CLEAR", runId });
              postMessage({ type: "CLEAR_ACTIVITY", runId });
            }}
            disabled={!runId}
          >
            <Trash2 className="h-3 w-3" />
            Clear
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {!hasEvents && (
          <div className="px-4 py-6 text-sm text-muted-foreground">No activity yet.</div>
        )}

        {groups.map((group) => (
          <PhaseGroup
            key={group.id}
            runId={runId ?? "live"}
            group={group}
            collapsed={Boolean(run?.collapsedPhaseIds[group.id])}
            onToggle={(id, phaseId) => dispatch({ type: "PHASE_TOGGLE_COLLAPSE", runId: id, phaseId })}
          />
        ))}

        {progressEvent && (
          <div className="px-3 py-3">
            <ActivityEventRow event={progressEvent} />
          </div>
        )}
      </div>

      {runId && (
        <div className="border-t border-border px-4 py-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            {status === "running" ? (
              <>
                <Loader2 className="h-3 w-3 animate-spin text-primary" />
                <span>Running</span>
              </>
            ) : (
              <>
                <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                <span>Done</span>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
