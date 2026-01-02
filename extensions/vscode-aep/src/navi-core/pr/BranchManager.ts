import * as vscode from 'vscode';
import { simpleGit, SimpleGit } from 'simple-git';

export interface BranchInfo {
    name: string;
    created: boolean;
    switched: boolean;
}

export class BranchManager {
    private git: SimpleGit;
    private workspaceRoot: string;

    constructor(workspaceRoot: string) {
        this.workspaceRoot = workspaceRoot;
        this.git = simpleGit(workspaceRoot);
    }

    /**
     * Creates a new branch with NAVI naming convention
     */
    async createBranch(taskId: string, description?: string): Promise<BranchInfo> {
        try {
            const branchName = this.generateBranchName(taskId, description);
            
            // Ensure we're on main/master before creating branch
            await this.ensureMainBranch();
            
            // Create and checkout new branch
            await this.git.checkoutLocalBranch(branchName);
            
            return {
                name: branchName,
                created: true,
                switched: true
            };
        } catch (error) {
            throw new Error(`Failed to create branch: ${error}`);
        }
    }

    /**
     * Generates NAVI branch name with task ID and timestamp
     */
    private generateBranchName(taskId: string, description?: string): string {
        const timestamp = Date.now();
        const cleanDescription = description
            ? description.toLowerCase().replace(/[^a-z0-9]+/g, '-').substring(0, 30)
            : '';
        
        if (cleanDescription) {
            return `navi/${taskId}-${cleanDescription}-${timestamp}`;
        }
        return `navi/${taskId}-${timestamp}`;
    }

    /**
     * Ensures we're on main/master branch before creating new branch
     */
    private async ensureMainBranch(): Promise<void> {
        const branches = await this.git.branch();
        const mainBranch = branches.all.find(b => b === 'main' || b === 'master') || 'main';
        
        if (branches.current !== mainBranch) {
            await this.git.checkout(mainBranch);
            await this.git.pull('origin', mainBranch);
        }
    }

    /**
     * Switches to existing branch
     */
    async checkout(branchName: string): Promise<void> {
        try {
            await this.git.checkout(branchName);
        } catch (error) {
            throw new Error(`Failed to checkout branch ${branchName}: ${error}`);
        }
    }

    /**
     * Gets current branch name
     */
    async getCurrentBranch(): Promise<string> {
        const status = await this.git.status();
        return status.current || 'unknown';
    }

    /**
     * Checks if branch exists locally
     */
    async branchExists(branchName: string): Promise<boolean> {
        try {
            const branches = await this.git.branch();
            return branches.all.includes(branchName);
        } catch (error) {
            return false;
        }
    }

    /**
     * Deletes a branch safely (with checks)
     */
    async deleteBranch(branchName: string, force: boolean = false): Promise<void> {
        try {
            // Don't delete main branches
            if (['main', 'master', 'develop'].includes(branchName)) {
                throw new Error(`Cannot delete protected branch: ${branchName}`);
            }

            // Switch away from branch if currently on it
            const currentBranch = await this.getCurrentBranch();
            if (currentBranch === branchName) {
                await this.ensureMainBranch();
            }

            // Delete branch
            if (force) {
                await this.git.branch(['-D', branchName]);
            } else {
                await this.git.branch(['-d', branchName]);
            }
        } catch (error) {
            throw new Error(`Failed to delete branch ${branchName}: ${error}`);
        }
    }
}