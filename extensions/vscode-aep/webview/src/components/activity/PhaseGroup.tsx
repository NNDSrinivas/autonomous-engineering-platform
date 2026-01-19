import React from "react";
import { ChevronDown } from "lucide-react";
import type { ActivityEvent } from "../../types/activity";
import { ActivityEventRow } from "./ActivityEventRow";

export type PhaseGroupData = {
  id: string;
  title: string;
  events: ActivityEvent[];
  isImplicit?: boolean;
};

type PhaseGroupProps = {
  runId: string;
  group: PhaseGroupData;
  collapsed: boolean;
  onToggle: (runId: string, phaseId: string) => void;
};

export function PhaseGroup({ runId, group, collapsed, onToggle }: PhaseGroupProps) {
  return (
    <div className="border-b border-border/60 py-3">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 px-3 text-left"
        onClick={() => onToggle(runId, group.id)}
      >
        <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <ChevronDown className={`h-4 w-4 transition ${collapsed ? "-rotate-90" : "rotate-0"}`} />
          <span>{group.title}</span>
          <span className="rounded-full border border-border/60 px-2 py-0.5 text-[11px] text-muted-foreground">
            {group.events.length}
          </span>
        </div>
      </button>

      {!collapsed && (
        <div className="mt-2 flex flex-col gap-2 px-3">
          {group.events.map((event) => (
            <ActivityEventRow key={event.id} event={event} />
          ))}
        </div>
      )}
    </div>
  );
}
