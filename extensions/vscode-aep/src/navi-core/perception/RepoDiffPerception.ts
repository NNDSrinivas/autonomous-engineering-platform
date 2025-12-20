import { exec as _exec } from 'child_process';
import { promisify } from 'util';

const exec = promisify(_exec);

export interface DiffFile {
  path: string;
  status: 'M' | 'A' | 'D' | 'R' | '?';
}

export interface RepoDiffSummary {
  base: string;
  unstagedCount: number;
  stagedCount: number;
  unstaged: DiffFile[];
  staged: DiffFile[];
}

/**
 * Collect real git diff data for the workspace.
 * Single source of truth for working tree state.
 */
export async function collectRepoDiff(workspaceRoot: string): Promise<RepoDiffSummary> {
  const run = async (cmd: string): Promise<string> => {
    try {
      const { stdout } = await exec(cmd, { cwd: workspaceRoot });
      return stdout.trim();
    } catch (e) {
      console.log(`[RepoDiffPerception] Git command failed: ${cmd}`, e);
      return '';
    }
  };

  // Get unstaged changes (modified but not staged)
  const unstagedRaw = await run('git diff --name-status');
  const unstaged = parseGitStatus(unstagedRaw);

  // Get staged changes (staged but not committed)
  const stagedRaw = await run('git diff --cached --name-status');
  const staged = parseGitStatus(stagedRaw);

  // Detect base branch
  let baseBranch = 'HEAD';
  try {
    await exec('git rev-parse --verify main', { cwd: workspaceRoot });
    baseBranch = 'main';
  } catch {
    try {
      await exec('git rev-parse --verify master', { cwd: workspaceRoot });
      baseBranch = 'master';
    } catch {
      baseBranch = 'HEAD';
    }
  }

  console.log(`[RepoDiffPerception] 📊 Repo diff collection complete:`);
  console.log(`  Base: ${baseBranch}`);
  console.log(`  Unstaged: ${unstaged.length} files`);
  console.log(`  Staged: ${staged.length} files`);
  console.log(`  Unstaged files:`, unstaged);
  console.log(`  Staged files:`, staged);

  return {
    base: baseBranch,
    unstagedCount: unstaged.length,
    stagedCount: staged.length,
    unstaged,
    staged
  };
}

/**
 * Parse git status output (name-status format)
 * Format: "M  path/to/file" or "A  path/to/file" etc.
 */
function parseGitStatus(output: string): DiffFile[] {
  if (!output) return [];

  return output
    .split('\n')
    .filter(Boolean)
    .map(line => {
      const parts = line.split(/\s+/);
      if (parts.length < 2) return null;
      const [status, ...pathParts] = parts;
      return {
        path: pathParts.join(' '),
        status: (status as any) || 'M'
      };
    })
    .filter((f): f is DiffFile => f !== null);
}
