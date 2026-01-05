import type { IntentKind } from "./intent.js";

export type PlanToolName =
  | "getDiagnostics"
  | "readFile"
  | "applyEdits"
  | "runCommand";

export type PlanStep = {
  id: string;
  title: string;
  description: string;
  tool?: PlanToolName;
  inputs?: Record<string, unknown>;
  successCriteria: string[];
};

export type Plan = {
  id: string;
  intentKind: IntentKind;
  goal: string;
  rationale: string;
  steps: PlanStep[];
};