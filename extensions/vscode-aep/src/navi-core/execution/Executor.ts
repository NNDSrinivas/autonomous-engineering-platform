import { WorkspaceContext, PlanStep } from '../agent/AgentContext';

export interface Executor {
    execute(step: PlanStep, ctx: WorkspaceContext): Promise<any>;
}
