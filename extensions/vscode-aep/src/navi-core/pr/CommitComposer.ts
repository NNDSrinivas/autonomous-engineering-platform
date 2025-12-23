import { ChangePlan } from '../generation/ChangePlan';
import { ValidationResult } from '../validation/ValidationEngine';

export interface CommitContext {
    taskId: string;
    summary: string;
    changePlan: ChangePlan;
    validationResult?: ValidationResult;
    filesChanged: string[];
    jiraTicket?: string;
    featurePlan?: any;
}

export interface CommitMessage {
    message: string;
    body: string;
    footer?: string;
}

export class CommitComposer {
    /**
     * Composes human-quality commit messages following conventional commits
     */
    compose(context: CommitContext): CommitMessage {
        const { taskId, summary, changePlan, filesChanged, jiraTicket } = context;

        // Generate commit type and scope
        const { type, scope } = this.analyzeChangeType(changePlan, filesChanged);
        
        // Create main commit message
        const message = this.createCommitMessage(type, scope, taskId, summary);
        
        // Create detailed body
        const body = this.createCommitBody(context);
        
        // Create footer with references
        const footer = this.createCommitFooter(context);

        return {
            message,
            body,
            footer
        };
    }

    /**
     * Analyzes the type of changes to determine commit type and scope
     */
    private analyzeChangeType(changePlan: ChangePlan, filesChanged: string[]): { type: string; scope?: string } {
        const changes = changePlan.steps;
        
        // Determine commit type based on changes
        let type = 'feat'; // default
        
        if (changes.some((c: any) => c.operation === 'delete' || c.description.toLowerCase().includes('fix'))) {
            type = 'fix';
        } else if (changes.some((c: any) => c.operation === 'modify' || c.description.toLowerCase().includes('refactor'))) {
            type = 'refactor';
        } else if (changes.some((c: any) => c.filePath.includes('test'))) {
            type = 'test';
        } else if (changes.some((c: any) => c.filePath.includes('README'))) {
            type = 'docs';
        } else if (changes.some((c: any) => c.description.toLowerCase().includes('chore'))) {
            type = 'chore';
        }

        // Determine scope based on file paths
        const scope = this.determineScope(filesChanged);

        return { type, scope };
    }

    /**
     * Determines the scope based on changed files
     */
    private determineScope(filesChanged: string[]): string | undefined {
        const commonPrefixes = new Map<string, number>();
        
        filesChanged.forEach(file => {
            const parts = file.split('/');
            if (parts.length > 1) {
                const prefix = parts[0];
                commonPrefixes.set(prefix, (commonPrefixes.get(prefix) || 0) + 1);
            }
        });

        // Find most common directory prefix
        const mostCommon = Array.from(commonPrefixes.entries())
            .sort(([,a], [,b]) => b - a)[0];

        if (mostCommon && mostCommon[1] > 1) {
            return mostCommon[0];
        }

        // Special scope detection
        if (filesChanged.some(f => f.includes('backend'))) return 'backend';
        if (filesChanged.some(f => f.includes('frontend'))) return 'frontend';
        if (filesChanged.some(f => f.includes('extension'))) return 'extension';
        if (filesChanged.some(f => f.includes('api'))) return 'api';
        if (filesChanged.some(f => f.includes('ui'))) return 'ui';

        return undefined;
    }

    /**
     * Creates the main commit message line
     */
    private createCommitMessage(type: string, scope: string | undefined, taskId: string, summary: string): string {
        const scopePart = scope ? `(${scope})` : '';
        const taskPart = taskId ? `${taskId}: ` : '';
        
        // Keep message under 72 characters
        const maxLength = 72;
        const prefix = `${type}${scopePart}: ${taskPart}`;
        const availableLength = maxLength - prefix.length;
        
        const truncatedSummary = summary.length > availableLength
            ? summary.substring(0, availableLength - 3) + '...'
            : summary;

        return `${prefix}${truncatedSummary}`;
    }

    /**
     * Creates detailed commit body
     */
    private createCommitBody(context: CommitContext): string {
        const { changePlan, validationResult, filesChanged } = context;
        const lines: string[] = [];

        // Add change description
        if (changePlan.description) {
            lines.push(changePlan.description);
            lines.push('');
        }

        // Add bullet points for main changes
        const mainChanges = changePlan.steps
            .filter((c: any) => c.operation !== 'create')
            .map((c: any) => `- ${c.description}`)
            .slice(0, 5); // Limit to 5 main points

        if (mainChanges.length > 0) {
            lines.push('Changes:');
            lines.push(...mainChanges);
            lines.push('');
        }

        // Add validation info if available
        if (validationResult) {
            const { passed, issues = [] } = validationResult;
            if (passed) {
                lines.push('✅ All validations passed');
            } else {
                const failedValidators = issues
                    .filter((r: any) => !r.success)
                    .map((r: any) => r.validatorName);
                lines.push(`⚠️  Validation issues: ${failedValidators.join(', ')}`);
            }
            lines.push('');
        }

        // Add file statistics
        if (filesChanged.length > 0) {
            lines.push(`Files changed: ${filesChanged.length}`);
            if (filesChanged.length <= 10) {
                lines.push(...filesChanged.map(f => `  ${f}`));
            }
        }

        return lines.join('\n').trim();
    }

    /**
     * Creates commit footer with references
     */
    private createCommitFooter(context: CommitContext): string | undefined {
        const { jiraTicket, taskId } = context;
        const footerLines: string[] = [];

        if (jiraTicket && jiraTicket !== taskId) {
            footerLines.push(`Closes: ${jiraTicket}`);
        }

        if (taskId) {
            footerLines.push(`Task-ID: ${taskId}`);
        }

        return footerLines.length > 0 ? footerLines.join('\n') : undefined;
    }

    /**
     * Formats the complete commit message for git
     */
    formatForGit(commitMessage: CommitMessage): string {
        const parts = [commitMessage.message];
        
        if (commitMessage.body) {
            parts.push('', commitMessage.body);
        }
        
        if (commitMessage.footer) {
            parts.push('', commitMessage.footer);
        }
        
        return parts.join('\n');
    }
}