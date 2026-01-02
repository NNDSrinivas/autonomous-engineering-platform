import { PRStatus, CIStatus } from './PRMonitor';

export interface PRStatusSummary {
    prNumber: number;
    prUrl: string;
    htmlUrl: string;
    title: string;
    state: string;
    ciSummary: string;
    reviewSummary: string;
    mergeSummary: string;
    overallStatus: 'ready' | 'pending' | 'blocked' | 'failed';
    nextActions: string[];
    blockers: string[];
    lastUpdated: Date;
}

export interface StatusReport {
    summary: PRStatusSummary;
    details: {
        ci: CIStatus[];
        reviews: any;
        conflicts: boolean;
    };
    humanReadable: string;
    markdown: string;
    recommendations: string[];
}

export class PRStatusReporter {
    /**
     * Generates a comprehensive status report for a PR
     */
    generateReport(
        prNumber: number,
        prUrl: string,
        htmlUrl: string,
        title: string,
        status: PRStatus
    ): StatusReport {
        const summary = this.createSummary(prNumber, prUrl, htmlUrl, title, status);
        const humanReadable = this.createHumanReadableReport(summary, status);
        const markdown = this.createMarkdownReport(summary, status);
        const recommendations = this.generateRecommendations(status);

        return {
            summary,
            details: {
                ci: status.ciStatuses,
                reviews: status.reviewStatus,
                conflicts: status.conflicts
            },
            humanReadable,
            markdown,
            recommendations
        };
    }

    /**
     * Creates a summary of the PR status
     */
    private createSummary(
        prNumber: number,
        prUrl: string,
        htmlUrl: string,
        title: string,
        status: PRStatus
    ): PRStatusSummary {
        const ciSummary = this.summarizeCI(status.ciStatuses);
        const reviewSummary = this.summarizeReviews(status.reviewStatus);
        const mergeSummary = this.summarizeMerge(status);
        const overallStatus = this.determineOverallStatus(status);
        const nextActions = this.getNextActions(status);
        const blockers = this.getBlockers(status);

        return {
            prNumber,
            prUrl,
            htmlUrl,
            title,
            state: status.state,
            ciSummary,
            reviewSummary,
            mergeSummary,
            overallStatus,
            nextActions,
            blockers,
            lastUpdated: status.lastUpdated
        };
    }

    /**
     * Summarizes CI status
     */
    private summarizeCI(ciStatuses: CIStatus[]): string {
        if (ciStatuses.length === 0) {
            return 'No CI checks configured';
        }

        const failed = ciStatuses.filter(ci => ci.state === 'failure').length;
        const pending = ciStatuses.filter(ci => ci.state === 'pending').length;
        const success = ciStatuses.filter(ci => ci.state === 'success').length;
        const error = ciStatuses.filter(ci => ci.state === 'error').length;

        if (failed > 0 || error > 0) {
            return `❌ ${failed + error}/${ciStatuses.length} checks failed`;
        } else if (pending > 0) {
            return `⏳ ${pending}/${ciStatuses.length} checks pending`;
        } else {
            return `✅ All ${success} checks passed`;
        }
    }

    /**
     * Summarizes review status
     */
    private summarizeReviews(reviewStatus: any): string {
        const { approved, required, changesRequested, pending } = reviewStatus;

        if (changesRequested > 0) {
            return `🔄 ${changesRequested} reviewer(s) requested changes`;
        } else if (approved >= required) {
            return `✅ Approved (${approved}/${required})`;
        } else {
            return `👀 Awaiting reviews (${approved}/${required})`;
        }
    }

    /**
     * Summarizes merge status
     */
    private summarizeMerge(status: PRStatus): string {
        if (status.conflicts) {
            return '⚠️ Merge conflicts detected';
        } else if (!status.mergeable) {
            return '⚠️ Not mergeable';
        } else {
            return '✅ Ready to merge';
        }
    }

    /**
     * Determines overall PR status
     */
    private determineOverallStatus(status: PRStatus): 'ready' | 'pending' | 'blocked' | 'failed' {
        const ciFailures = status.ciStatuses.filter(ci => 
            ci.state === 'failure' || ci.state === 'error'
        ).length;

        const ciPending = status.ciStatuses.filter(ci => ci.state === 'pending').length;

        if (ciFailures > 0 || status.conflicts || !status.mergeable) {
            return 'failed';
        }

        if (status.reviewStatus.changesRequested > 0) {
            return 'blocked';
        }

        if (ciPending > 0 || status.reviewStatus.approved < status.reviewStatus.required) {
            return 'pending';
        }

        return 'ready';
    }

    /**
     * Gets next recommended actions
     */
    private getNextActions(status: PRStatus): string[] {
        const actions: string[] = [];

        // CI actions
        const failedCI = status.ciStatuses.filter(ci => 
            ci.state === 'failure' || ci.state === 'error'
        );

        if (failedCI.length > 0) {
            actions.push(`Fix ${failedCI.length} failing CI check(s)`);
        }

        // Review actions
        if (status.reviewStatus.changesRequested > 0) {
            actions.push('Address requested changes');
        } else if (status.reviewStatus.approved < status.reviewStatus.required) {
            const needed = status.reviewStatus.required - status.reviewStatus.approved;
            actions.push(`Request ${needed} more review(s)`);
        }

        // Merge actions
        if (status.conflicts) {
            actions.push('Resolve merge conflicts');
        }

        // Ready actions
        if (actions.length === 0 && status.mergeable && 
            status.reviewStatus.approved >= status.reviewStatus.required) {
            actions.push('Ready to merge!');
        }

        return actions;
    }

    /**
     * Gets current blockers
     */
    private getBlockers(status: PRStatus): string[] {
        const blockers: string[] = [];

        // CI blockers
        const failedCI = status.ciStatuses.filter(ci => 
            ci.state === 'failure' || ci.state === 'error'
        );

        failedCI.forEach(ci => {
            blockers.push(`CI: ${ci.context} - ${ci.description}`);
        });

        // Review blockers
        if (status.reviewStatus.changesRequested > 0) {
            blockers.push(`Reviews: ${status.reviewStatus.changesRequested} change request(s)`);
        }

        // Merge blockers
        if (status.conflicts) {
            blockers.push('Merge conflicts');
        }

        return blockers;
    }

    /**
     * Creates human-readable status report
     */
    private createHumanReadableReport(summary: PRStatusSummary, status: PRStatus): string {
        const lines: string[] = [];

        lines.push(`PR #${summary.prNumber}: ${summary.title}`);
        lines.push(`Status: ${summary.overallStatus.toUpperCase()}`);
        lines.push(`Link: ${summary.htmlUrl}`);
        lines.push('');

        // CI Status
        lines.push('🔧 Continuous Integration:');
        lines.push(`   ${summary.ciSummary}`);
        
        const failedCI = status.ciStatuses.filter(ci => 
            ci.state === 'failure' || ci.state === 'error'
        );

        if (failedCI.length > 0) {
            lines.push('   Failed checks:');
            failedCI.forEach(ci => {
                lines.push(`   - ${ci.context}: ${ci.description}`);
                if (ci.targetUrl) {
                    lines.push(`     Details: ${ci.targetUrl}`);
                }
            });
        }

        lines.push('');

        // Review Status
        lines.push('👥 Code Reviews:');
        lines.push(`   ${summary.reviewSummary}`);
        lines.push('');

        // Merge Status
        lines.push('🔀 Merge Status:');
        lines.push(`   ${summary.mergeSummary}`);
        lines.push('');

        // Next Actions
        if (summary.nextActions.length > 0) {
            lines.push('📋 Next Actions:');
            summary.nextActions.forEach(action => {
                lines.push(`   • ${action}`);
            });
        }

        // Blockers
        if (summary.blockers.length > 0) {
            lines.push('');
            lines.push('🚫 Current Blockers:');
            summary.blockers.forEach(blocker => {
                lines.push(`   • ${blocker}`);
            });
        }

        lines.push('');
        lines.push(`Last updated: ${summary.lastUpdated.toLocaleString()}`);

        return lines.join('\n');
    }

    /**
     * Creates markdown status report
     */
    private createMarkdownReport(summary: PRStatusSummary, status: PRStatus): string {
        const statusIcon = {
            ready: '✅',
            pending: '⏳',
            blocked: '🚫',
            failed: '❌'
        }[summary.overallStatus];

        const lines: string[] = [];

        lines.push(`# PR #${summary.prNumber} Status Report`);
        lines.push('');
        lines.push(`**Title:** ${summary.title}`);
        lines.push(`**Status:** ${statusIcon} ${summary.overallStatus.toUpperCase()}`);
        lines.push(`**Link:** [View PR](${summary.htmlUrl})`);
        lines.push('');

        // Status Table
        lines.push('| Component | Status |');
        lines.push('|-----------|--------|');
        lines.push(`| CI/CD | ${summary.ciSummary} |`);
        lines.push(`| Reviews | ${summary.reviewSummary} |`);
        lines.push(`| Merge | ${summary.mergeSummary} |`);
        lines.push('');

        // Failed CI Details
        const failedCI = status.ciStatuses.filter(ci => 
            ci.state === 'failure' || ci.state === 'error'
        );

        if (failedCI.length > 0) {
            lines.push('## ❌ Failed CI Checks');
            lines.push('');
            failedCI.forEach(ci => {
                lines.push(`- **${ci.context}**: ${ci.description}`);
                if (ci.targetUrl) {
                    lines.push(`  - [View Details](${ci.targetUrl})`);
                }
            });
            lines.push('');
        }

        // Next Actions
        if (summary.nextActions.length > 0) {
            lines.push('## 📋 Next Actions');
            lines.push('');
            summary.nextActions.forEach(action => {
                lines.push(`- [ ] ${action}`);
            });
            lines.push('');
        }

        // Blockers
        if (summary.blockers.length > 0) {
            lines.push('## 🚫 Current Blockers');
            lines.push('');
            summary.blockers.forEach(blocker => {
                lines.push(`- ${blocker}`);
            });
            lines.push('');
        }

        lines.push('---');
        lines.push(`*Last updated: ${summary.lastUpdated.toLocaleString()}*`);

        return lines.join('\n');
    }

    /**
     * Generates actionable recommendations
     */
    private generateRecommendations(status: PRStatus): string[] {
        const recommendations: string[] = [];

        // CI Recommendations
        const failedCI = status.ciStatuses.filter(ci => 
            ci.state === 'failure' || ci.state === 'error'
        );

        if (failedCI.length > 0) {
            const testFailures = failedCI.filter(ci => 
                ci.context.toLowerCase().includes('test')
            );
            
            const buildFailures = failedCI.filter(ci => 
                ci.context.toLowerCase().includes('build') ||
                ci.context.toLowerCase().includes('compile')
            );

            const lintFailures = failedCI.filter(ci => 
                ci.context.toLowerCase().includes('lint') ||
                ci.context.toLowerCase().includes('style')
            );

            if (testFailures.length > 0) {
                recommendations.push('Run tests locally to identify and fix failing test cases');
            }

            if (buildFailures.length > 0) {
                recommendations.push('Check for compilation errors and fix build issues');
            }

            if (lintFailures.length > 0) {
                recommendations.push('Run linter locally and fix code style issues');
            }
        }

        // Review Recommendations
        if (status.reviewStatus.changesRequested > 0) {
            recommendations.push('Review and address all requested changes from reviewers');
        } else if (status.reviewStatus.approved < status.reviewStatus.required) {
            recommendations.push('Request additional code reviews from team members');
        }

        // Merge Recommendations
        if (status.conflicts) {
            recommendations.push('Rebase on latest main branch and resolve merge conflicts');
        }

        // General Recommendations
        if (recommendations.length === 0) {
            recommendations.push('PR looks good! Consider merging when ready');
        }

        return recommendations;
    }

    /**
     * Creates a simple status badge text
     */
    createStatusBadge(status: PRStatus): string {
        const overallStatus = this.determineOverallStatus(status);
        const icons = {
            ready: '✅ Ready',
            pending: '⏳ Pending',
            blocked: '🚫 Blocked',
            failed: '❌ Failed'
        };

        return icons[overallStatus];
    }

    /**
     * Creates a one-line status summary
     */
    createOneLineSummary(summary: PRStatusSummary): string {
        return `PR #${summary.prNumber} [${summary.overallStatus.toUpperCase()}]: ${summary.ciSummary} • ${summary.reviewSummary} • ${summary.mergeSummary}`;
    }
}