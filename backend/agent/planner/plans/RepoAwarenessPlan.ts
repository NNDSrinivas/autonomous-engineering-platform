import { PlanResult } from "../PlanResult";
import { IntentType } from "../../intents/IntentType";

export class RepoAwarenessPlan {
  static build({ context }: any): PlanResult {
    return {
      reasoning:
        "User is asking about the current repository context. This requires inspecting workspace metadata.",
      plan: {
        id: "repo-awareness",
        title: "Identify current repository",
        intent: IntentType.REPO_AWARENESS,
        requiresApproval: false,
        confidence: 0.95,
        steps: [
          {
            id: "inspect-workspace",
            type: "inspect",
            description: "Inspect VS Code workspace folders",
          },
          {
            id: "summarize-repo",
            type: "summarize",
            description: "Summarize repository name and purpose",
          },
        ],
      },
    };
  }
}