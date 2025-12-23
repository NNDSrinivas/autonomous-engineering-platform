import * as vscode from 'vscode';
import { Octokit } from '@octokit/rest';
import { ChangePlan } from '../generation/ChangePlan';
import { ValidationResult } from '../validation/ValidationEngine';

export interface PRInput {
    title: string;
    body: string;
    branch: string;
    baseBranch?: string;
    taskId?: string;
    jiraTicket?: string;
    changePlan?: ChangePlan;
    validationResult?: ValidationResult;
    draft?: boolean;
    assignees?: string[];
    reviewers?: string[];
    labels?: string[];
}

export interface PRResult {
    prNumber: number;
    prUrl: string;
    created: boolean;
    htmlUrl: string;
}

export interface GitProvider {
    name: 'github' | 'gitlab' | 'bitbucket' | 'azure';
    apiUrl?: string;
    token: string;
}

export class PRCreator {
    private provider: GitProvider;
    private repoOwner: string;
    private repoName: string;
    private octokit?: Octokit;

    constructor(
        provider: GitProvider,
        repoOwner: string,
        repoName: string
    ) {
        this.provider = provider;
        this.repoOwner = repoOwner;
        this.repoName = repoName;
        
        if (provider.name === 'github') {
            this.octokit = new Octokit({
                auth: provider.token,
                baseUrl: provider.apiUrl || 'https://api.github.com'
            });
        }
    }

    /**
     * Creates a pull request
     */
    async create(input: PRInput): Promise<PRResult> {
        switch (this.provider.name) {
            case 'github':
                return this.createGitHubPR(input);
            case 'gitlab':
                return this.createGitLabPR(input);
            case 'bitbucket':
                return this.createBitbucketPR(input);
            case 'azure':
                return this.createAzurePR(input);
            default:
                throw new Error(`Unsupported provider: ${this.provider.name}`);
        }
    }

    /**
     * Creates GitHub pull request
     */
    private async createGitHubPR(input: PRInput): Promise<PRResult> {
        if (!this.octokit) {
            throw new Error('GitHub client not initialized');
        }

        try {
            const response = await this.octokit.pulls.create({
                owner: this.repoOwner,
                repo: this.repoName,
                title: input.title,
                body: input.body,
                head: input.branch,
                base: input.baseBranch || 'main',
                draft: input.draft || false
            });

            const pr = response.data;

            // Add assignees if specified
            if (input.assignees && input.assignees.length > 0) {
                await this.octokit.issues.addAssignees({
                    owner: this.repoOwner,
                    repo: this.repoName,
                    issue_number: pr.number,
                    assignees: input.assignees
                });
            }

            // Add reviewers if specified
            if (input.reviewers && input.reviewers.length > 0) {
                await this.octokit.pulls.requestReviewers({
                    owner: this.repoOwner,
                    repo: this.repoName,
                    pull_number: pr.number,
                    reviewers: input.reviewers
                });
            }

            // Add labels if specified
            if (input.labels && input.labels.length > 0) {
                await this.octokit.issues.addLabels({
                    owner: this.repoOwner,
                    repo: this.repoName,
                    issue_number: pr.number,
                    labels: input.labels
                });
            }

            return {
                prNumber: pr.number,
                prUrl: pr.url,
                created: true,
                htmlUrl: pr.html_url
            };
        } catch (error: any) {
            throw new Error(`Failed to create GitHub PR: ${error.message}`);
        }
    }

    /**
     * Creates GitLab merge request
     */
    private async createGitLabPR(input: PRInput): Promise<PRResult> {
        // TODO: Implement GitLab support
        throw new Error('GitLab support not yet implemented');
    }

    /**
     * Creates Bitbucket pull request
     */
    private async createBitbucketPR(input: PRInput): Promise<PRResult> {
        // TODO: Implement Bitbucket support
        throw new Error('Bitbucket support not yet implemented');
    }

    /**
     * Creates Azure DevOps pull request
     */
    private async createAzurePR(input: PRInput): Promise<PRResult> {
        // TODO: Implement Azure DevOps support
        throw new Error('Azure DevOps support not yet implemented');
    }

    /**
     * Generates comprehensive PR description
     */
    generatePRDescription(
        taskId: string,
        changePlan?: ChangePlan,
        validationResult?: ValidationResult,
        jiraTicket?: string,
        featurePlan?: any
    ): string {
        const sections: string[] = [];

        // Header with task reference
        if (jiraTicket) {
            sections.push(`## ${jiraTicket}`);
        } else if (taskId) {
            sections.push(`## Task: ${taskId}`);
        }

        // Overview from feature plan
        if (featurePlan?.summary) {
            sections.push(`## Overview\n${featurePlan.summary}`);
        }

        // Changes section from change plan
        if (changePlan) {
            sections.push('## Changes');
            const mainChanges = changePlan.steps
                .filter((c: any) => c.operation !== 'create')
                .map((c: any) => `- **${c.filePath}**: ${c.description}`)
                .slice(0, 10);
            
            if (mainChanges.length > 0) {
                sections.push(mainChanges.join('\n'));
            }

            if (changePlan.steps.length > 10) {
                sections.push(`\n_...and ${changePlan.steps.length - 10} more files_`);
            }
        }

        // Validation status
        if (validationResult) {
            sections.push('## Validation Results');
            const { passed, issues = [] } = validationResult;
            
            if (passed) {
                sections.push('✅ All validations passed successfully');
                
                const successfulValidators = issues
                    .filter((r: any) => r.success)
                    .map((r: any) => `- ✅ ${r.validatorName}`)
                    .join('\n');
                
                if (successfulValidators) {
                    sections.push('\n' + successfulValidators);
                }
            } else {
                sections.push('⚠️ Some validation issues detected:');
                
                issues.forEach((result: any) => {
                    if (!result.success) {
                        sections.push(`- ❌ **${result.validatorName}**: ${result.errors.join(', ')}`);
                    }
                });
            }
        }

        // Testing section
        sections.push('## Testing');
        sections.push('- [ ] Manual testing completed');
        sections.push('- [ ] Unit tests passing');
        sections.push('- [ ] Integration tests passing');

        // Footer
        sections.push('---');
        sections.push('_Generated by NAVI Autonomous Engineering Platform_');

        if (jiraTicket) {
            sections.push(`\nCloses: ${jiraTicket}`);
        }

        return sections.join('\n\n');
    }

    /**
     * Generates PR title from task and summary
     */
    generatePRTitle(taskId: string, summary: string, jiraTicket?: string): string {
        const maxLength = 72; // GitHub's recommended limit
        
        const prefix = jiraTicket || taskId;
        const titlePrefix = prefix ? `${prefix}: ` : '';
        const availableLength = maxLength - titlePrefix.length;
        
        const truncatedSummary = summary.length > availableLength
            ? summary.substring(0, availableLength - 3) + '...'
            : summary;
        
        return `${titlePrefix}${truncatedSummary}`;
    }
}