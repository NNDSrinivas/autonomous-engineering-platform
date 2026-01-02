// extensions/vscode-aep/src/navi-core/perception/RepoDiffDetailPerception.ts
/**
 * Phase 1.3: Diff Detail Perception
 * 
 * Extracts real git diff content for individual files.
 * READ-ONLY, TRUSTED, NO OPINIONS.
 * 
 * Rules:
 * - No parsing beyond diff
 * - No AST
 * - No writes
 * - No fixes
 */

import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

export interface FileDiffDetail {
    path: string;
    additions: number;
    deletions: number;
    diff: string;
}

/**
 * Collect git diff for a single file.
 * 
 * @param workspaceRoot - Absolute path to the git repository
 * @param filePath - Relative path to the file
 * @returns Diff detail with additions/deletions count and raw diff
 */
export async function collectDiffForFile(
    workspaceRoot: string,
    filePath: string
): Promise<FileDiffDetail> {
    try {
        // Get unstaged diff for the file
        const { stdout } = await execAsync(
            `git diff -- "${filePath}"`,
            { cwd: workspaceRoot, maxBuffer: 10 * 1024 * 1024 }
        );

        // Count additions (lines starting with + but not +++)
        const additions = stdout
            .split("\n")
            .filter(l => l.startsWith("+") && !l.startsWith("+++")).length;

        // Count deletions (lines starting with - but not ---)
        const deletions = stdout
            .split("\n")
            .filter(l => l.startsWith("-") && !l.startsWith("---")).length;

        return {
            path: filePath,
            additions,
            deletions,
            diff: stdout
        };
    } catch (error) {
        // If git diff fails, return empty diff
        console.error(`[RepoDiffDetail] Failed to get diff for ${filePath}:`, error);
        return {
            path: filePath,
            additions: 0,
            deletions: 0,
            diff: ""
        };
    }
}

/**
 * Collect diff for staged file.
 * 
 * @param workspaceRoot - Absolute path to the git repository
 * @param filePath - Relative path to the file
 * @returns Diff detail for staged changes
 */
export async function collectStagedDiffForFile(
    workspaceRoot: string,
    filePath: string
): Promise<FileDiffDetail> {
    try {
        // Get staged diff for the file
        const { stdout } = await execAsync(
            `git diff --cached -- "${filePath}"`,
            { cwd: workspaceRoot, maxBuffer: 10 * 1024 * 1024 }
        );

        const additions = stdout
            .split("\n")
            .filter(l => l.startsWith("+") && !l.startsWith("+++")).length;

        const deletions = stdout
            .split("\n")
            .filter(l => l.startsWith("-") && !l.startsWith("---")).length;

        return {
            path: filePath,
            additions,
            deletions,
            diff: stdout
        };
    } catch (error) {
        console.error(`[RepoDiffDetail] Failed to get staged diff for ${filePath}:`, error);
        return {
            path: filePath,
            additions: 0,
            deletions: 0,
            diff: ""
        };
    }
}
