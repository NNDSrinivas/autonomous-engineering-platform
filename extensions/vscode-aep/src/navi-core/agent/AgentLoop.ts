import { AgentEventBus } from '../events/AgentEventBus';
import { PlanStep, WorkspaceContext } from './AgentContext';
import { IntentType } from './Intent';
import { Planner } from './Planner';
import { Perception } from './Perception';
import { ExecutorRegistry } from '../execution/ExecutorRegistry';
import { ApprovalManager } from '../approvals/ApprovalManager';
import { SessionMemory } from '../memory/SessionMemory';

export class AgentLoop {
    constructor(
        private perception: Perception,
        private planner: Planner,
        private executors: ExecutorRegistry,
        private approvals: ApprovalManager,
        private events: AgentEventBus,
        private memory: SessionMemory
    ) { }

    async run(userInput: string): Promise<void> {
        // 1. Observe environment
        const context = await this.perception.observe();
        this.events.emit({ type: 'perceptionComplete', context });

        // 2. Intent
        const intent = this.planner.classifyIntent(userInput, context);
        this.events.emit({ type: 'intentDetected', intent: intent.type, confidence: intent.confidence });

        if (intent.type === IntentType.Unknown) {
            this.events.emit({ type: 'aborted', reason: 'Unknown intent' });
            return;
        }

        // 3. Plan
        const plan = this.planner.createPlan(intent, context);
        this.events.emit({ type: 'planCreated', plan });

        // 4. Approval (Phase 1.2: auto-approve)
        const approved = await this.approvals.request(plan);
        if (!approved) {
            this.events.emit({ type: 'aborted', reason: 'User declined approval' });
            return;
        }

        // 5. Execute steps sequentially
        let workingContext: WorkspaceContext = { ...context };
        for (const step of plan.steps) {
            this.events.emit({ type: 'stepStart', step });
            const executor = this.executors.get(step.executor);
            const result = await executor.execute(step, workingContext);
            workingContext = this.updateContextFromStep(workingContext, step, result);
            this.events.emit({ type: 'stepComplete', step, result });
        }

        // 6. Memory
        this.memory.record({ intent, plan });
        this.events.emit({ type: 'done', message: 'Agent loop completed' });
    }

    private updateContextFromStep(ctx: WorkspaceContext, step: PlanStep, result: any): WorkspaceContext {
        if (step.executor === 'git' && step.action === 'collectDiff') {
            return {
                ...ctx,
                diff: result?.diff ?? ctx.diff,
                files: Array.isArray(result?.files) ? result.files : ctx.files
            };
        }
        return ctx;
    }
}
