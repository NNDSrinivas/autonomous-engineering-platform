import { execFile } from 'child_process';
import { promisify } from 'util';
import { WorkspaceContext } from './AgentContext';

const exec = promisify(execFile);

async function runGit(args: string[], cwd: string): Promise<string> {
    try {
        const { stdout } = await exec('git', args, { cwd });
        return stdout.trim();
    } catch (err) {
        console.warn('[NAVI][Perception] git command failed', { args, error: err });
        return '';
    }
}

export class Perception {
    constructor(private workspaceRoot: string) { }

    async observe(): Promise<WorkspaceContext> {
        const repoRoot = this.workspaceRoot;
        const branch = await runGit(['rev-parse', '--abbrev-ref', 'HEAD'], repoRoot);
        const diff = await runGit(['diff'], repoRoot);

        return {
            repo: {
                root: repoRoot,
                branch: branch || 'unknown'
            },
            diff,
            files: [],
            diagnostics: [],
            timestamp: Date.now()
        };
    }
}
