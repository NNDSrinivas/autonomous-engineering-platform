import { execFile } from 'child_process';
import { promisify } from 'util';
import { Executor } from './Executor';
import { PlanStep, WorkspaceContext } from '../agent/AgentContext';

const exec = promisify(execFile);

function extractFilesFromDiff(diff: string): string[] {
    const files = new Set<string>();
    for (const line of diff.split('\n')) {
        if (line.startsWith('+++ b/')) {
            files.add(line.replace('+++ b/', '').trim());
        }
    }
    return Array.from(files);
}

function summarizeDiff(diff: string): { summary: string } {
    if (!diff || diff.trim().length === 0) {
        return { summary: 'No changes detected.' };
    }
    const lines = diff.split('\n').length;
    const files = extractFilesFromDiff(diff).length;
    return { summary: `Diff spans ${files} file(s), ${lines} line(s).` };
}

export class GitExecutor implements Executor {
    async execute(step: PlanStep, ctx: WorkspaceContext): Promise<any> {
        switch (step.action) {
            case 'collectDiff': {
                const { stdout } = await exec('git', ['diff'], { cwd: ctx.repo.root });
                const diff = stdout || '';
                return {
                    diff,
                    files: extractFilesFromDiff(diff)
                };
            }
            case 'summarizeChanges': {
                return summarizeDiff(ctx.diff);
            }
            default:
                throw new Error(`Unknown git action: ${step.action}`);
        }
    }
}
