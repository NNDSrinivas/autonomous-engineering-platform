import { PlanResult } from "../PlanResult";
import { IntentType } from "../../intents/IntentType";

export class TaskPlan {
  static build({ userMessage }: any): PlanResult {
    return {
      reasoning:
        "User wants help planning a task. This requires understanding requirements and breaking down work.",
      plan: {
        id: "task-planning",
        title: "Create task plan",
        intent: IntentType.TASK_PLANNING,
        requiresApproval: false,
        confidence: 0.75,
        steps: [
          {
            id: "understand-requirements",
            type: "analyze",
            description: "Analyze and understand task requirements",
          },
          {
            id: "break-down-work",
            type: "propose",
            description: "Break down work into actionable steps",
          },
          {
            id: "estimate-effort",
            type: "summarize",
            description: "Provide time estimates and priority recommendations",
          },
        ],
      },
    };
  }
}