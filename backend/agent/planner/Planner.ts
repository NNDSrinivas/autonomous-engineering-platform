import { IntentType } from "../intents/IntentType";
import { PlanResult } from "./PlanResult";
import { RepoAwarenessPlan } from "./plans/RepoAwarenessPlan";
import { ExplainPlan } from "./plans/ExplainPlan";
import { DebugPlan } from "./plans/DebugPlan";
import { TaskPlan } from "./plans/TaskPlan";

export class Planner {
  static createPlan(params: {
    intent: IntentType;
    userMessage: string;
    context: any;
  }): PlanResult {
    switch (params.intent) {
      case IntentType.REPO_AWARENESS:
        return RepoAwarenessPlan.build(params);

      case IntentType.DEBUGGING:
        return DebugPlan.build(params);

      case IntentType.TASK_PLANNING:
        return TaskPlan.build(params);

      case IntentType.GREETING:
        return ExplainPlan.build(params);

      default:
        return ExplainPlan.build(params);
    }
  }
}