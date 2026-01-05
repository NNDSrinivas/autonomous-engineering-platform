import { IntentType } from "../intents/IntentType";
import { PlanStep } from "./PlanStep";

export interface Plan {
  id: string;
  title: string;
  intent: IntentType;
  steps: PlanStep[];
  requiresApproval: boolean;
  confidence: number; // 0 → 1
}