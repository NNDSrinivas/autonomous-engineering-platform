import { Intent, IntentType } from './Intent';
import { ExecutionPlan, WorkspaceContext } from './AgentContext';

export class Planner {
    classifyIntent(text: string, _ctx: WorkspaceContext): Intent {
        if (/review\s+(my\s+)?(working\s+tree|changes|diff)/i.test(text)) {
            return { type: IntentType.ReviewWorkingTree, confidence: 0.9 };
        }
        return { type: IntentType.Unknown, confidence: 0.3 };
    }

    createPlan(intent: Intent, ctx: WorkspaceContext): ExecutionPlan {
        if (intent.type === IntentType.ReviewWorkingTree) {
            return {
                goal: 'Review working tree changes',
                steps: [
                    { executor: 'git', action: 'collectDiff' },
                    { executor: 'diagnostics', action: 'analyze' },
                    { executor: 'git', action: 'summarizeChanges' }
                ]
            };
        }

        throw new Error(`No plan available for intent: ${intent.type}`);
    }
}
