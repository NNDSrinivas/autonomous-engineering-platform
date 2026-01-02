import { PlanResult } from "../PlanResult";
import { IntentType } from "../../intents/IntentType";

export class ExplainPlan {
  static build(): PlanResult {
    return {
      reasoning: "User intent is unclear. Respond calmly and ask a clarifying question.",
      plan: {
        id: "explain",
        title: "Clarify request",
        intent: IntentType.UNKNOWN,
        requiresApproval: false,
        confidence: 0.4,
        steps: [
          {
            id: "ask-clarification",
            type: "propose",
            description: "Ask user what they want to do next",
          },
        ],
      },
    };
  }
}