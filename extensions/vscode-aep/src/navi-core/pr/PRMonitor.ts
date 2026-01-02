import { Octokit } from '@octokit/rest';
import { GitProvider, PRResult } from './PRCreator';

export interface CIStatus {
    state: 'success' | 'failure' | 'pending' | 'error';
    description: string;
    targetUrl?: string;
    context: string;
    updatedAt: Date;
}

export interface PRStatus {
    prNumber: number;
    prUrl: string;
    state: 'open' | 'closed' | 'merged' | 'draft';
    ciStatuses: CIStatus[];
    reviewStatus: {
        required: number;
        approved: number;
        changesRequested: number;
        pending: number;
    };
    mergeable: boolean;
    conflicts: boolean;
    lastUpdated: Date;
}

export interface PRComment {
    id: number;
    author: string;
    body: string;
    createdAt: Date;
    updatedAt: Date;
    filePath?: string;
    line?: number;
    isReviewComment: boolean;
    resolved?: boolean;
}

export class PRMonitor {
    private provider: GitProvider;
    private repoOwner: string;
    private repoName: string;
    private octokit?: Octokit;
    private watchIntervals: Map<number, NodeJS.Timeout> = new Map();

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
     * Gets current status of a pull request
     */
    async getStatus(prNumber: number): Promise<PRStatus> {
        switch (this.provider.name) {
            case 'github':
                return this.getGitHubStatus(prNumber);
            case 'gitlab':
                return this.getGitLabStatus(prNumber);
            default:
                throw new Error(`Unsupported provider: ${this.provider.name}`);
        }
    }

    /**
     * Starts watching a PR for changes
     */
    async startWatching(prNumber: number, callback: (status: PRStatus) => void, intervalMs: number = 30000): Promise<void> {
        // Stop existing watch if any
        this.stopWatching(prNumber);

        // Start new watch
        const interval = setInterval(async () => {
            try {
                const status = await this.getStatus(prNumber);
                callback(status);
            } catch (error) {
                console.error(`Error monitoring PR ${prNumber}:`, error);
            }
        }, intervalMs);

        this.watchIntervals.set(prNumber, interval);
    }

    /**
     * Stops watching a PR
     */
    stopWatching(prNumber: number): void {
        const interval = this.watchIntervals.get(prNumber);
        if (interval) {
            clearInterval(interval);
            this.watchIntervals.delete(prNumber);
        }
    }

    /**
     * Gets PR comments (both issue and review comments)
     */
    async getComments(prNumber: number): Promise<PRComment[]> {
        switch (this.provider.name) {
            case 'github':
                return this.getGitHubComments(prNumber);
            case 'gitlab':
                return this.getGitLabComments(prNumber);
            default:
                throw new Error(`Unsupported provider: ${this.provider.name}`);
        }
    }

    /**
     * Gets GitHub PR status
     */
    private async getGitHubStatus(prNumber: number): Promise<PRStatus> {
        if (!this.octokit) {
            throw new Error('GitHub client not initialized');
        }

        try {
            // Get PR info
            const prResponse = await this.octokit.pulls.get({
                owner: this.repoOwner,
                repo: this.repoName,
                pull_number: prNumber
            });

            const pr = prResponse.data;

            // Get CI status
            const statusResponse = await this.octokit.repos.getCombinedStatusForRef({
                owner: this.repoOwner,
                repo: this.repoName,
                ref: pr.head.sha
            });

            const ciStatuses: CIStatus[] = statusResponse.data.statuses.map(status => ({
                state: status.state as 'success' | 'failure' | 'pending' | 'error',
                description: status.description || '',
                targetUrl: status.target_url || undefined,
                context: status.context,
                updatedAt: new Date(status.updated_at)
            }));

            // Get review status
            const reviewsResponse = await this.octokit.pulls.listReviews({
                owner: this.repoOwner,
                repo: this.repoName,
                pull_number: prNumber
            });

            const reviews = reviewsResponse.data;
            const reviewStatus = this.analyzeReviewStatus(reviews);

            return {
                prNumber,
                prUrl: pr.url,
                state: pr.state as 'open' | 'closed',
                ciStatuses,
                reviewStatus,
                mergeable: pr.mergeable || false,
                conflicts: pr.mergeable === false,
                lastUpdated: new Date(pr.updated_at)
            };
        } catch (error: any) {
            throw new Error(`Failed to get GitHub PR status: ${error.message}`);
        }
    }

    /**
     * Gets GitHub PR comments
     */
    private async getGitHubComments(prNumber: number): Promise<PRComment[]> {
        if (!this.octokit) {
            throw new Error('GitHub client not initialized');
        }

        try {
            const comments: PRComment[] = [];

            // Get issue comments
            const issueCommentsResponse = await this.octokit.issues.listComments({
                owner: this.repoOwner,
                repo: this.repoName,
                issue_number: prNumber
            });

            comments.push(...issueCommentsResponse.data.map(comment => ({
                id: comment.id,
                author: comment.user?.login || 'unknown',
                body: comment.body || '',
                createdAt: new Date(comment.created_at),
                updatedAt: new Date(comment.updated_at),
                isReviewComment: false
            })));

            // Get review comments
            const reviewCommentsResponse = await this.octokit.pulls.listReviewComments({
                owner: this.repoOwner,
                repo: this.repoName,
                pull_number: prNumber
            });

            comments.push(...reviewCommentsResponse.data.map(comment => ({
                id: comment.id,
                author: comment.user?.login || 'unknown',
                body: comment.body || '',
                createdAt: new Date(comment.created_at),
                updatedAt: new Date(comment.updated_at),
                filePath: comment.path,
                line: comment.line || undefined,
                isReviewComment: true
            })));

            return comments.sort((a, b) => a.createdAt.getTime() - b.createdAt.getTime());
        } catch (error: any) {
            throw new Error(`Failed to get GitHub PR comments: ${error.message}`);
        }
    }

    /**
     * Analyzes review status from GitHub reviews
     */
    private analyzeReviewStatus(reviews: any[]) {
        const latestReviews = new Map<string, any>();
        
        // Get latest review from each reviewer
        reviews.forEach(review => {
            const author = review.user.login;
            if (!latestReviews.has(author) || 
                new Date(review.submitted_at) > new Date(latestReviews.get(author).submitted_at)) {
                latestReviews.set(author, review);
            }
        });

        let approved = 0;
        let changesRequested = 0;
        let pending = 0;

        latestReviews.forEach(review => {
            switch (review.state) {
                case 'APPROVED':
                    approved++;
                    break;
                case 'CHANGES_REQUESTED':
                    changesRequested++;
                    break;
                case 'COMMENTED':
                case 'PENDING':
                    pending++;
                    break;
            }
        });

        return {
            required: Math.max(1, latestReviews.size), // Assume at least 1 required
            approved,
            changesRequested,
            pending
        };
    }

    /**
     * Gets GitLab MR status
     */
    private async getGitLabStatus(prNumber: number): Promise<PRStatus> {
        // TODO: Implement GitLab support
        throw new Error('GitLab support not yet implemented');
    }

    /**
     * Gets GitLab MR comments
     */
    private async getGitLabComments(prNumber: number): Promise<PRComment[]> {
        // TODO: Implement GitLab support
        throw new Error('GitLab support not yet implemented');
    }

    /**
     * Checks if PR is ready to merge
     */
    isReadyToMerge(status: PRStatus): boolean {
        const ciPassed = status.ciStatuses.length === 0 || 
            status.ciStatuses.every(ci => ci.state === 'success');
        
        const reviewsApproved = status.reviewStatus.approved >= status.reviewStatus.required &&
            status.reviewStatus.changesRequested === 0;
        
        return ciPassed && reviewsApproved && status.mergeable && !status.conflicts;
    }

    /**
     * Gets human-readable status summary
     */
    getStatusSummary(status: PRStatus): string {
        const parts: string[] = [];
        
        // CI Status
        const failedCI = status.ciStatuses.filter(ci => ci.state === 'failure');
        const pendingCI = status.ciStatuses.filter(ci => ci.state === 'pending');
        
        if (failedCI.length > 0) {
            parts.push(`❌ ${failedCI.length} CI check(s) failed`);
        } else if (pendingCI.length > 0) {
            parts.push(`⏳ ${pendingCI.length} CI check(s) pending`);
        } else if (status.ciStatuses.length > 0) {
            parts.push(`✅ All CI checks passed`);
        }
        
        // Review Status
        const { approved, required, changesRequested, pending } = status.reviewStatus;
        if (changesRequested > 0) {
            parts.push(`🔄 ${changesRequested} reviewer(s) requested changes`);
        } else if (approved < required) {
            parts.push(`👀 ${approved}/${required} approvals received`);
        } else {
            parts.push(`✅ All reviews approved`);
        }
        
        // Merge Status
        if (status.conflicts) {
            parts.push(`⚠️ Merge conflicts detected`);
        }
        
        return parts.join(' • ');
    }

    /**
     * Cleanup method
     */
    dispose(): void {
        this.watchIntervals.forEach(interval => clearInterval(interval));
        this.watchIntervals.clear();
    }
}