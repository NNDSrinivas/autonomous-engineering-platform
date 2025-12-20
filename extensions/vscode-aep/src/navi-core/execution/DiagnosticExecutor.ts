import { Executor } from './Executor';
import { PlanStep, WorkspaceContext } from '../agent/AgentContext';

export class DiagnosticExecutor implements Executor {
    async execute(_step: PlanStep, ctx: WorkspaceContext): Promise<any> {
        const issues: Array<{ type: string; message: string }> = [];

        if (!ctx.diff || ctx.diff.trim().length === 0) {
            issues.push({ type: 'info', message: 'No uncommitted changes detected.' });
        }

        return { issues };
    }
}
