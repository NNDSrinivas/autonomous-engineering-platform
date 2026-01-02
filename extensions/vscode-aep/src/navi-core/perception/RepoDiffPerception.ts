// extensions/vscode-aep/src/navi-core/perception/RepoDiffPerception.ts
/**
 * Phase 1.2: Repo Diff Perception
 * 
 * Collects real git working tree state: unstaged and staged changes vs base branch.
 * Single source of truth for repo status.
 */

import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

export interface DiffFile {
    path: string;
    status: string; // M, A, D, R, etc.
}

export interface RepoDiffSummary {
    base: string;
    unstagedCount: number;
    stagedCount: number;
    unstaged: DiffFile[];
    staged: DiffFile[];
}

/**
 * Parse git status output to extract file status.
 */
function parseGitStatus(output: string): DiffFile[] {
    const files: DiffFile[] = [];
    const lines = output.trim().split("\n").filter(Boolean);

    for (const raw of lines) {
        // git diff --name-status emits lines like:
        //  - "M\tpath/to/file"
        //  - "A\tpath/to/file"
        //  - "D\tpath/to/file"
        //  - "R100\told/path\tnew/path" (rename with score)
        const parts = raw.split(/\s+/).filter(Boolean);
        if (parts.length === 0) continue;

        const status = parts[0];

        // For rename, the last segment is the new path; otherwise second segment is the path
        const path = parts.length > 2 ? parts[parts.length - 1] : parts[1];

        if (path) {
            files.push({ path, status: status.replace(/[^A-Z]/g, "") });
        }
    }

    return files;
}

/**
 * Detect the base branch (main, master, or HEAD).
 */
async function detectBaseBranch(workspaceRoot: string): Promise<string> {
    try {
        const { stdout: mainCheck } = await execAsync(
            `git rev-parse --verify main`,
            { cwd: workspaceRoot }
        );
        if (mainCheck.trim()) return "main";
    } catch {
        // main doesn't exist, try master
    }

    try {
        const { stdout: masterCheck } = await execAsync(
            `git rev-parse --verify master`,
            { cwd: workspaceRoot }
        );
        if (masterCheck.trim()) return "master";
    } catch {
        // master doesn't exist either, use HEAD
    }

    return "HEAD";
}

/**
 * Collect real working tree diff summary (Phase 1.2).
 * 
 * @param workspaceRoot - Absolute path to git repository
 * @returns Summary of unstaged and staged changes
 */
export async function collectRepoDiff(
    workspaceRoot: string
): Promise<RepoDiffSummary> {
    try {
        // Detect base branch
        const base = await detectBaseBranch(workspaceRoot);

        // Get unstaged changes (working tree vs index)
        const { stdout: unstagedOutput } = await execAsync(
            `git diff --name-status`,
            { cwd: workspaceRoot, maxBuffer: 10 * 1024 * 1024 }
        );

        // Get staged changes (index vs HEAD)
        const { stdout: stagedOutput } = await execAsync(
            `git diff --cached --name-status`,
            { cwd: workspaceRoot, maxBuffer: 10 * 1024 * 1024 }
        );

        const unstaged = parseGitStatus(unstagedOutput);
        const staged = parseGitStatus(stagedOutput);

        return {
            base,
            unstagedCount: unstaged.length,
            stagedCount: staged.length,
            unstaged,
            staged
        };
    } catch (error) {
        console.error("[RepoDiffPerception] Failed to collect diff:", error);
        throw error;
    }
}
