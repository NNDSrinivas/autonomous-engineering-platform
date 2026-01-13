import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import { promisify } from 'util';

const execAsync = promisify(cp.exec);

export interface GitStatus {
    branch: string;
    ahead: number;
    behind: number;
    modified: string[];
    added: string[];
    deleted: string[];
    untracked: string[];
    conflicted: string[];
}

export interface GitCommit {
    hash: string;
    author: string;
    date: string;
    message: string;
}

export interface GitDiff {
    filePath: string;
    additions: number;
    deletions: number;
    patch: string;
}

export interface GitBranch {
    name: string;
    current: boolean;
    remote?: string;
}

export class GitService {
    private workspaceRoot: string;
    private gitApi: any;

    constructor(workspaceRoot: string) {
        this.workspaceRoot = workspaceRoot;
        this.initializeGitApi();
    }

    /**
     * Initialize VS Code Git API if available
     */
    private async initializeGitApi() {
        try {
            const gitExtension = vscode.extensions.getExtension('vscode.git');
            if (gitExtension) {
                if (!gitExtension.isActive) {
                    await gitExtension.activate();
                }
                const git = gitExtension.exports;
                const api = git.getAPI(1);

                if (api.repositories.length > 0) {
                    this.gitApi = api.repositories[0];
                }
            }
        } catch (error) {
            console.error('Failed to initialize Git API:', error);
        }
    }

    /**
     * Execute git command
     */
    private async exec(command: string): Promise<string> {
        try {
            const { stdout, stderr } = await execAsync(command, {
                cwd: this.workspaceRoot,
                maxBuffer: 10 * 1024 * 1024 // 10MB buffer
            });

            if (stderr && !stderr.includes('warning')) {
                console.warn('Git command warning:', stderr);
            }

            return stdout.trim();
        } catch (error: any) {
            throw new Error(`Git command failed: ${error.message}`);
        }
    }

    /**
     * Get current git status
     */
    async getStatus(): Promise<GitStatus> {
        try {
            // Try using VS Code Git API first
            if (this.gitApi) {
                const state = this.gitApi.state;
                return {
                    branch: state.HEAD?.name || 'unknown',
                    ahead: state.HEAD?.ahead || 0,
                    behind: state.HEAD?.behind || 0,
                    modified: state.workingTreeChanges
                        .filter((c: any) => c.status === 0)
                        .map((c: any) => c.uri.fsPath),
                    added: state.indexChanges
                        .filter((c: any) => c.status === 1)
                        .map((c: any) => c.uri.fsPath),
                    deleted: state.workingTreeChanges
                        .filter((c: any) => c.status === 6)
                        .map((c: any) => c.uri.fsPath),
                    untracked: state.workingTreeChanges
                        .filter((c: any) => c.status === 7)
                        .map((c: any) => c.uri.fsPath),
                    conflicted: state.mergeChanges.map((c: any) => c.uri.fsPath)
                };
            }

            // Fallback to git CLI
            const branch = await this.getCurrentBranch();
            const statusOutput = await this.exec('git status --porcelain=v1');

            const modified: string[] = [];
            const added: string[] = [];
            const deleted: string[] = [];
            const untracked: string[] = [];
            const conflicted: string[] = [];

            statusOutput.split('\n').forEach(line => {
                if (!line) {return;}

                const status = line.substring(0, 2);
                const filePath = line.substring(3);

                if (status.includes('M')) {modified.push(filePath);}
                else if (status.includes('A')) {added.push(filePath);}
                else if (status.includes('D')) {deleted.push(filePath);}
                else if (status.includes('?')) {untracked.push(filePath);}
                else if (status.includes('U')) {conflicted.push(filePath);}
            });

            // Get ahead/behind counts
            let ahead = 0;
            let behind = 0;
            try {
                const remoteBranch = await this.getRemoteBranch(branch);
                if (remoteBranch) {
                    const aheadBehind = await this.exec(`git rev-list --left-right --count ${remoteBranch}...HEAD`);
                    const [behindStr, aheadStr] = aheadBehind.split('\t');
                    ahead = parseInt(aheadStr, 10) || 0;
                    behind = parseInt(behindStr, 10) || 0;
                }
            } catch {
                // Remote branch doesn't exist or can't be compared
            }

            return {
                branch,
                ahead,
                behind,
                modified,
                added,
                deleted,
                untracked,
                conflicted
            };
        } catch (error) {
            console.error('Failed to get git status:', error);
            throw error;
        }
    }

    /**
     * Get current branch name
     */
    async getCurrentBranch(): Promise<string> {
        try {
            if (this.gitApi) {
                return this.gitApi.state.HEAD?.name || 'unknown';
            }

            return await this.exec('git rev-parse --abbrev-ref HEAD');
        } catch (error) {
            console.error('Failed to get current branch:', error);
            return 'unknown';
        }
    }

    /**
     * Get remote branch for a local branch
     */
    async getRemoteBranch(branch: string): Promise<string | null> {
        try {
            const remote = await this.exec(`git config branch.${branch}.remote`);
            if (!remote) {return null;}

            const merge = await this.exec(`git config branch.${branch}.merge`);
            if (!merge) {return null;}

            const remoteBranchName = merge.replace('refs/heads/', '');
            return `${remote}/${remoteBranchName}`;
        } catch {
            return null;
        }
    }

    /**
     * Get list of all branches
     */
    async getBranches(): Promise<GitBranch[]> {
        try {
            const output = await this.exec('git branch -a');
            const branches: GitBranch[] = [];

            output.split('\n').forEach(line => {
                if (!line) {return;}

                const current = line.startsWith('*');
                const name = line.replace('*', '').trim();

                if (name.startsWith('remotes/')) {
                    const remoteName = name.replace('remotes/', '');
                    branches.push({ name: remoteName, current: false, remote: remoteName });
                } else {
                    branches.push({ name, current });
                }
            });

            return branches;
        } catch (error) {
            console.error('Failed to get branches:', error);
            return [];
        }
    }

    /**
     * Create new branch
     */
    async createBranch(branchName: string, checkout: boolean = true): Promise<void> {
        try {
            if (checkout) {
                await this.exec(`git checkout -b ${branchName}`);
            } else {
                await this.exec(`git branch ${branchName}`);
            }
        } catch (error) {
            console.error('Failed to create branch:', error);
            throw error;
        }
    }

    /**
     * Checkout branch
     */
    async checkout(branchName: string): Promise<void> {
        try {
            await this.exec(`git checkout ${branchName}`);
        } catch (error) {
            console.error('Failed to checkout branch:', error);
            throw error;
        }
    }

    /**
     * Get recent commits
     */
    async getCommits(count: number = 10): Promise<GitCommit[]> {
        try {
            const output = await this.exec(
                `git log --pretty=format:"%H|%an|%ai|%s" -n ${count}`
            );

            const commits: GitCommit[] = [];
            output.split('\n').forEach(line => {
                if (!line) {return;}

                const [hash, author, date, message] = line.split('|');
                commits.push({ hash, author, date, message });
            });

            return commits;
        } catch (error) {
            console.error('Failed to get commits:', error);
            return [];
        }
    }

    /**
     * Get diff for a file or commit
     */
    async getDiff(filePath?: string, staged: boolean = false): Promise<GitDiff[]> {
        try {
            let command = 'git diff --numstat';
            if (staged) {
                command += ' --cached';
            }
            if (filePath) {
                command += ` -- "${filePath}"`;
            }

            const numstatOutput = await this.exec(command);
            const diffs: GitDiff[] = [];

            for (const line of numstatOutput.split('\n')) {
                if (!line) {continue;}

                const [additionsStr, deletionsStr, path] = line.split('\t');
                const additions = parseInt(additionsStr, 10) || 0;
                const deletions = parseInt(deletionsStr, 10) || 0;

                // Get actual patch
                let patchCommand = 'git diff';
                if (staged) {
                    patchCommand += ' --cached';
                }
                patchCommand += ` -- "${path}"`;

                const patch = await this.exec(patchCommand);

                diffs.push({
                    filePath: path,
                    additions,
                    deletions,
                    patch
                });
            }

            return diffs;
        } catch (error) {
            console.error('Failed to get diff:', error);
            return [];
        }
    }

    /**
     * Stage files
     */
    async stage(files: string[]): Promise<void> {
        try {
            if (this.gitApi) {
                const uris = files.map(f => vscode.Uri.file(path.join(this.workspaceRoot, f)));
                await this.gitApi.add(uris);
                return;
            }

            // Fallback to CLI
            for (const file of files) {
                await this.exec(`git add "${file}"`);
            }
        } catch (error) {
            console.error('Failed to stage files:', error);
            throw error;
        }
    }

    /**
     * Unstage files
     */
    async unstage(files: string[]): Promise<void> {
        try {
            if (this.gitApi) {
                const uris = files.map(f => vscode.Uri.file(path.join(this.workspaceRoot, f)));
                await this.gitApi.revert(uris);
                return;
            }

            // Fallback to CLI
            for (const file of files) {
                await this.exec(`git reset HEAD "${file}"`);
            }
        } catch (error) {
            console.error('Failed to unstage files:', error);
            throw error;
        }
    }

    /**
     * Commit changes
     */
    async commit(message: string, amend: boolean = false): Promise<string> {
        try {
            let command = `git commit -m "${message.replace(/"/g, '\\"')}"`;
            if (amend) {
                command += ' --amend';
            }

            const output = await this.exec(command);

            // Extract commit hash
            const hash = await this.exec('git rev-parse HEAD');
            return hash;
        } catch (error) {
            console.error('Failed to commit:', error);
            throw error;
        }
    }

    /**
     * Push changes
     */
    async push(remote: string = 'origin', branch?: string, force: boolean = false): Promise<void> {
        try {
            let command = `git push ${remote}`;

            if (branch) {
                command += ` ${branch}`;
            }

            if (force) {
                command += ' --force-with-lease';
            }

            await this.exec(command);
        } catch (error) {
            console.error('Failed to push:', error);
            throw error;
        }
    }

    /**
     * Pull changes
     */
    async pull(remote: string = 'origin', branch?: string): Promise<void> {
        try {
            let command = `git pull ${remote}`;

            if (branch) {
                command += ` ${branch}`;
            }

            await this.exec(command);
        } catch (error) {
            console.error('Failed to pull:', error);
            throw error;
        }
    }

    /**
     * Get remote URL
     */
    async getRemoteUrl(remote: string = 'origin'): Promise<string | null> {
        try {
            return await this.exec(`git remote get-url ${remote}`);
        } catch {
            return null;
        }
    }

    /**
     * Check if repository has uncommitted changes
     */
    async hasUncommittedChanges(): Promise<boolean> {
        try {
            const status = await this.getStatus();
            return (
                status.modified.length > 0 ||
                status.added.length > 0 ||
                status.deleted.length > 0 ||
                status.untracked.length > 0
            );
        } catch {
            return false;
        }
    }

    /**
     * Get repository root
     */
    async getRepositoryRoot(): Promise<string> {
        try {
            return await this.exec('git rev-parse --show-toplevel');
        } catch (error) {
            return this.workspaceRoot;
        }
    }

    /**
     * Check if path is a git repository
     */
    async isGitRepository(): Promise<boolean> {
        try {
            await this.exec('git rev-parse --git-dir');
            return true;
        } catch {
            return false;
        }
    }

    /**
     * Get file history
     */
    async getFileHistory(filePath: string, count: number = 10): Promise<GitCommit[]> {
        try {
            const output = await this.exec(
                `git log --pretty=format:"%H|%an|%ai|%s" -n ${count} -- "${filePath}"`
            );

            const commits: GitCommit[] = [];
            output.split('\n').forEach(line => {
                if (!line) {return;}

                const [hash, author, date, message] = line.split('|');
                commits.push({ hash, author, date, message });
            });

            return commits;
        } catch (error) {
            console.error('Failed to get file history:', error);
            return [];
        }
    }

    /**
     * Discard changes for files
     */
    async discardChanges(files: string[]): Promise<void> {
        try {
            for (const file of files) {
                await this.exec(`git checkout -- "${file}"`);
            }
        } catch (error) {
            console.error('Failed to discard changes:', error);
            throw error;
        }
    }

    /**
     * Create stash
     */
    async stash(message?: string): Promise<void> {
        try {
            let command = 'git stash';
            if (message) {
                command += ` push -m "${message}"`;
            }
            await this.exec(command);
        } catch (error) {
            console.error('Failed to stash changes:', error);
            throw error;
        }
    }

    /**
     * Apply stash
     */
    async stashPop(): Promise<void> {
        try {
            await this.exec('git stash pop');
        } catch (error) {
            console.error('Failed to pop stash:', error);
            throw error;
        }
    }

    dispose(): void {
        // Cleanup if needed
    }
}
