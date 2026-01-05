export type PlanStepType =
  | "inspect"
  | "analyze"
  | "summarize"
  | "propose"
  | "execute";

export interface PlanStep {
  id: string;
  type: PlanStepType;
  description: string;
}