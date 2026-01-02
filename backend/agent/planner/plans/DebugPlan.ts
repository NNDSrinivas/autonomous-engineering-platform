import { PlanResult } from "../PlanResult";
import { IntentType } from "../../intents/IntentType";

export class DebugPlan {
  static build({ userMessage }: any): PlanResult {
    return {
      reasoning:
        "User is reporting a bug or asking for debugging help. This requires systematic analysis.",
      plan: {
        id: "debug-issue",
        title: "Debug and fix issue",
        intent: IntentType.DEBUGGING,
        requiresApproval: true,
        confidence: 0.85,
        steps: [
          {
            id: "analyze-error",
            type: "analyze",
            description: "Analyze error logs and stack traces",
          },
          {
            id: "identify-cause",
            type: "inspect",
            description: "Identify root cause and affected components",
          },
          {
            id: "propose-fix",
            type: "propose",
            description: "Propose specific code changes to fix the issue",
          },
        ],
      },
    };
  }
}