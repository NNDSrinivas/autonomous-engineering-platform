import * as vscode from 'vscode';
import { simpleGit, SimpleGit } from 'simple-git';
import { BranchManager, BranchInfo } from './BranchManager';
import { CommitComposer, CommitContext, CommitMessage } from './CommitComposer';
import { PRCreator, PRInput, PRResult, GitProvider } from './PRCreator';
import { PRMonitor, PRStatus, PRComment } from './PRMonitor';
import { PRCommentResolver, ResolveContext, ResolutionResult } from './PRCommentResolver';
import { PRStatusReporter, StatusReport } from './PRStatusReporter';
import { ChangePlan } from '../generation/ChangePlan';
import { ValidationResult } from '../validation/ValidationEngine';
import { ApprovalEngine } from '../safety/ApprovalEngine';
import { CodeSynthesizer } from '../generation/CodeSynthesizer';
import { LLMProvider } from '../llm/LLMProvider';

export interface PRLifecycleConfig {
    provider: GitProvider;
    repoOwner: string;
    repoName: string;
    workspaceRoot: string;
    defaultBaseBranch?: string;
    autoWatch?: boolean;
    autoResolveComments?: boolean;
}

export interface PRTask {
    taskId: string;
    summary: string;
    description: string;
    changePlan: ChangePlan;
    validationResult?: ValidationResult;
    jiraTicket?: string;
    featurePlan?: any;
    assignees?: string[];
    reviewers?: string[];
    labels?: string[];
}

export interface PRLifecycleResult {
    branch: BranchInfo;
    commitHash?: string;
    pr: PRResult;
    monitoring: boolean;
}

export class PRLifecycleEngine {
    private config: PRLifecycleConfig;
    private git: SimpleGit;
    private branchManager: BranchManager;
    private commitComposer: CommitComposer;
    private prCreator: PRCreator;
    private prMonitor: PRMonitor;
    private prCommentResolver: PRCommentResolver;
    private prStatusReporter: PRStatusReporter;
    private approvalEngine: ApprovalEngine;

    constructor(
        config: PRLifecycleConfig,
        approvalEngine: ApprovalEngine,
        codeSynthesizer: CodeSynthesizer,
        llmProvider: LLMProvider
    ) {
        this.config = config;
        this.git = simpleGit(config.workspaceRoot);
        
        // Initialize components
        this.branchManager = new BranchManager(config.workspaceRoot);
        this.commitComposer = new CommitComposer();
        this.prCreator = new PRCreator(config.provider, config.repoOwner, config.repoName);
        this.prMonitor = new PRMonitor(config.provider, config.repoOwner, config.repoName);
        this.prCommentResolver = new PRCommentResolver(
            config.provider, 
            config.repoOwner, 
            config.repoName,
            codeSynthesizer,
            llmProvider
        );
        this.prStatusReporter = new PRStatusReporter();
        this.approvalEngine = approvalEngine;
    }

    /**
     * Complete PR lifecycle: branch → commit → PR → monitor
     */
    async executeFullLifecycle(task: PRTask): Promise<PRLifecycleResult> {
        try {
            // Step 1: Create branch
            vscode.window.showInformationMessage(`Creating branch for ${task.taskId}...`);
            const branch = await this.branchManager.createBranch(task.taskId, task.summary);

            // Step 2: Apply changes and commit
            const commitHash = await this.commitChanges(task, branch.name);

            // Step 3: Push branch
            await this.git.push('origin', branch.name);

            // Step 4: Create PR
            vscode.window.showInformationMessage(`Creating pull request...`);
            const pr = await this.createPullRequest(task, branch.name);

            // Step 5: Start monitoring if enabled
            let monitoring = false;
            if (this.config.autoWatch) {
                await this.startMonitoring(pr.prNumber);
                monitoring = true;
            }

            vscode.window.showInformationMessage(
                `PR #${pr.prNumber} created successfully!`,
                'Open PR',
                'View Status'
            ).then(selection => {
                if (selection === 'Open PR') {
                    vscode.env.openExternal(vscode.Uri.parse(pr.htmlUrl));
                } else if (selection === 'View Status') {
                    this.showPRStatus(pr.prNumber);
                }
            });

            return {
                branch,
                commitHash,
                pr,
                monitoring
            };
        } catch (error) {
            vscode.window.showErrorMessage(`PR lifecycle failed: ${error}`);
            throw error;
        }
    }

    /**
     * Creates and commits changes
     */
    private async commitChanges(task: PRTask, branchName: string): Promise<string> {
        // Get list of changed files
        const status = await this.git.status();
        const filesChanged = [
            ...status.modified,
            ...status.created,
            ...status.deleted
        ];

        if (filesChanged.length === 0) {
            throw new Error('No changes to commit');
        }

        // Stage all changes
        await this.git.add('.');

        // Compose commit message
        const commitContext: CommitContext = {
            taskId: task.taskId,
            summary: task.summary,
            changePlan: task.changePlan,
            validationResult: task.validationResult,
            filesChanged,
            jiraTicket: task.jiraTicket,
            featurePlan: task.featurePlan
        };

        const commitMessage = this.commitComposer.compose(commitContext);
        const fullMessage = this.commitComposer.formatForGit(commitMessage);

        // Commit changes
        const result = await this.git.commit(fullMessage);
        return result.commit;
    }

    /**
     * Creates pull request
     */
    private async createPullRequest(task: PRTask, branchName: string): Promise<PRResult> {
        const title = this.prCreator.generatePRTitle(
            task.taskId,
            task.summary,
            task.jiraTicket
        );

        const body = this.prCreator.generatePRDescription(
            task.taskId,
            task.changePlan,
            task.validationResult,
            task.jiraTicket,
            task.featurePlan
        );

        const prInput: PRInput = {
            title,
            body,
            branch: branchName,
            baseBranch: this.config.defaultBaseBranch || 'main',
            taskId: task.taskId,
            jiraTicket: task.jiraTicket,
            changePlan: task.changePlan,
            validationResult: task.validationResult,
            assignees: task.assignees,
            reviewers: task.reviewers,
            labels: ['navi-generated', ...(task.labels || [])]
        };

        return await this.prCreator.create(prInput);
    }

    /**
     * Starts monitoring a PR
     */
    async startMonitoring(prNumber: number): Promise<void> {
        await this.prMonitor.startWatching(prNumber, (status: PRStatus) => {
            this.handleStatusUpdate(prNumber, status);
        });

        vscode.window.showInformationMessage(`Now monitoring PR #${prNumber} for updates`);
    }

    /**
     * Stops monitoring a PR
     */
    stopMonitoring(prNumber: number): void {
        this.prMonitor.stopWatching(prNumber);
        vscode.window.showInformationMessage(`Stopped monitoring PR #${prNumber}`);
    }

    /**
     * Handles PR status updates
     */
    private async handleStatusUpdate(prNumber: number, status: PRStatus): Promise<void> {
        const report = this.prStatusReporter.generateReport(
            prNumber,
            status.prUrl,
            status.prUrl, // TODO: Get actual HTML URL
            `PR #${prNumber}`, // TODO: Get actual title
            status
        );

        // Show status update in output channel
        console.log(`PR #${prNumber} Status Update:`, report.humanReadable);

        // Handle failed CI
        const failedCI = status.ciStatuses.filter(ci => 
            ci.state === 'failure' || ci.state === 'error'
        );

        if (failedCI.length > 0) {
            const action = await vscode.window.showWarningMessage(
                `PR #${prNumber}: ${failedCI.length} CI check(s) failed`,
                'View Details',
                'Auto-Fix'
            );

            if (action === 'Auto-Fix') {
                await this.attemptCIFix(prNumber, failedCI);
            }
        }

        // Handle review comments
        if (this.config.autoResolveComments) {
            await this.checkAndResolveComments(prNumber);
        }

        // Check if ready to merge
        if (this.prMonitor.isReadyToMerge(status)) {
            vscode.window.showInformationMessage(
                `PR #${prNumber} is ready to merge!`,
                'Merge Now',
                'View PR'
            ).then(async selection => {
                if (selection === 'Merge Now') {
                    // TODO: Implement auto-merge with approval
                }
            });
        }
    }

    /**
     * Attempts to automatically fix CI failures
     */
    private async attemptCIFix(prNumber: number, failedCI: any[]): Promise<void> {
        try {
            for (const ci of failedCI) {
                // Analyze CI failure and suggest fixes
                console.log(`Attempting to fix CI failure: ${ci.context} - ${ci.description}`);
                
                // TODO: Implement intelligent CI failure analysis and fixing
                // This would integrate with the validation engine to identify and fix issues
            }
        } catch (error) {
            console.error('Failed to auto-fix CI issues:', error);
        }
    }

    /**
     * Checks for new comments and attempts to resolve them
     */
    private async checkAndResolveComments(prNumber: number): Promise<void> {
        try {
            const actionableComments = await this.prCommentResolver.getActionableComments(prNumber);
            
            for (const comment of actionableComments) {
                const context: ResolveContext = {
                    comment,
                    prNumber
                };

                const resolution = await this.prCommentResolver.resolve(context);
                
                if (resolution.understood && resolution.confidence > 80) {
                    // Ask for approval before applying automatic fixes
                    const approval = this.approvalEngine.requiresApproval({
                        id: Math.random().toString(36).substring(7),
                        type: 'MODIFY_FILE',
                        description: `Auto-resolve comment: "${comment.body.substring(0, 100)}..."`,
                        filesAffected: resolution.changePlan?.steps.map(s => s.filePath) || [],
                        metadata: { 
                            reason: 'PR comment resolution',
                            estimatedImpact: 'low'
                        },
                        riskLevel: 'low' as const,
                        reversible: true,
                    });

                    if (!approval.requiresApproval) {
                        await this.prCommentResolver.applyResolution(prNumber, resolution, comment);
                        
                        vscode.window.showInformationMessage(
                            `Automatically resolved comment from @${comment.author}`
                        );
                    }
                }
            }
        } catch (error) {
            console.error('Failed to auto-resolve comments:', error);
        }
    }

    /**
     * Shows comprehensive PR status
     */
    async showPRStatus(prNumber: number): Promise<void> {
        try {
            const status = await this.prMonitor.getStatus(prNumber);
            const report = this.prStatusReporter.generateReport(
                prNumber,
                status.prUrl,
                status.prUrl, // TODO: Get actual HTML URL
                `PR #${prNumber}`, // TODO: Get actual title
                status
            );

            // Show in a new document
            const doc = await vscode.workspace.openTextDocument({
                content: report.markdown,
                language: 'markdown'
            });

            await vscode.window.showTextDocument(doc);
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to get PR status: ${error}`);
        }
    }

    /**
     * Lists all PRs created by NAVI
     */
    async listNaviPRs(): Promise<void> {
        // TODO: Implement PR listing functionality
        vscode.window.showInformationMessage('PR listing not yet implemented');
    }

    /**
     * Cleanup method
     */
    dispose(): void {
        this.prMonitor.dispose();
    }

    /**
     * Gets configuration for git provider
     */
    static async detectGitProvider(workspaceRoot: string): Promise<GitProvider> {
        try {
            const git = simpleGit(workspaceRoot);
            const remotes = await git.getRemotes(true);
            const origin = remotes.find(r => r.name === 'origin');

            if (!origin) {
                throw new Error('No origin remote found');
            }

            const url = origin.refs.fetch;
            
            if (url.includes('github.com')) {
                const token = await vscode.window.showInputBox({
                    prompt: 'Enter GitHub Personal Access Token',
                    password: true,
                    placeHolder: 'ghp_...'
                });

                if (!token) {
                    throw new Error('GitHub token required');
                }

                return {
                    name: 'github',
                    token,
                    apiUrl: 'https://api.github.com'
                };
            }
            
            // TODO: Add support for other providers
            throw new Error('Unsupported git provider');
        } catch (error) {
            throw new Error(`Failed to detect git provider: ${error}`);
        }
    }

    /**
     * Parses repository info from git remote
     */
    static async parseRepoInfo(workspaceRoot: string): Promise<{ owner: string; name: string }> {
        try {
            const git = simpleGit(workspaceRoot);
            const remotes = await git.getRemotes(true);
            const origin = remotes.find(r => r.name === 'origin');

            if (!origin) {
                throw new Error('No origin remote found');
            }

            const url = origin.refs.fetch;
            
            // Parse GitHub URL
            const githubMatch = url.match(/github\.com[\/:](.+)\/(.+)\.git$/);
            if (githubMatch) {
                return {
                    owner: githubMatch[1],
                    name: githubMatch[2]
                };
            }

            throw new Error('Could not parse repository info from remote URL');
        } catch (error) {
            throw new Error(`Failed to parse repo info: ${error}`);
        }
    }
}