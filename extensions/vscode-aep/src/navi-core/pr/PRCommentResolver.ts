import * as vscode from 'vscode';
import { Octokit } from '@octokit/rest';
import { GitProvider, PRResult } from './PRCreator';
import { PRComment } from './PRMonitor';
import { CodeSynthesizer } from '../generation/CodeSynthesizer';
import { LLMProvider } from '../llm/LLMProvider';
import { ChangePlan } from '../generation/ChangePlan';

export interface ResolveContext {
    comment: PRComment;
    prNumber: number;
    fileContent?: string;
    surroundingCode?: string;
    commitSha?: string;
}

export interface ResolutionResult {
    understood: boolean;
    intent: string;
    changePlan?: ChangePlan;
    responseComment?: string;
    confidence: number;
}

export class PRCommentResolver {
    private provider: GitProvider;
    private repoOwner: string;
    private repoName: string;
    private octokit?: Octokit;
    private codeSynthesizer: CodeSynthesizer;
    private llmProvider: LLMProvider;

    constructor(
        provider: GitProvider,
        repoOwner: string,
        repoName: string,
        codeSynthesizer: CodeSynthesizer,
        llmProvider: LLMProvider
    ) {
        this.provider = provider;
        this.repoOwner = repoOwner;
        this.repoName = repoName;
        this.codeSynthesizer = codeSynthesizer;
        this.llmProvider = llmProvider;
        
        if (provider.name === 'github') {
            this.octokit = new Octokit({
                auth: provider.token,
                baseUrl: provider.apiUrl || 'https://api.github.com'
            });
        }
    }

    /**
     * Analyzes and resolves a PR comment
     */
    async resolve(context: ResolveContext): Promise<ResolutionResult> {
        try {
            // First, understand the intent of the comment
            const intent = await this.analyzeIntent(context);
            
            if (!intent.understood) {
                return {
                    understood: false,
                    intent: intent.description,
                    confidence: intent.confidence
                };
            }

            // Get additional context if needed
            const enhancedContext = await this.enhanceContext(context);

            // Generate fix plan
            const changePlan = await this.generateFixPlan(intent, enhancedContext);

            // Generate professional response
            const responseComment = this.generateResponse(intent, changePlan);

            return {
                understood: true,
                intent: intent.description,
                changePlan,
                responseComment,
                confidence: intent.confidence
            };
        } catch (error) {
            console.error('Error resolving PR comment:', error);
            return {
                understood: false,
                intent: 'Failed to analyze comment',
                confidence: 0
            };
        }
    }

    /**
     * Applies the resolution (makes code changes and replies)
     */
    async applyResolution(
        prNumber: number, 
        resolution: ResolutionResult,
        originalComment: PRComment
    ): Promise<void> {
        if (!resolution.understood || !resolution.changePlan) {
            throw new Error('Cannot apply unresolved comment');
        }

        try {
            // Apply code changes
            await this.codeSynthesizer.synthesize(resolution.changePlan);

            // Reply to comment
            if (resolution.responseComment) {
                await this.replyToComment(prNumber, originalComment, resolution.responseComment);
            }

            // Commit changes
            await this.commitResolution(resolution, originalComment);
        } catch (error) {
            throw new Error(`Failed to apply resolution: ${error}`);
        }
    }

    /**
     * Analyzes the intent behind a PR comment
     */
    private async analyzeIntent(context: ResolveContext): Promise<{
        understood: boolean;
        description: string;
        confidence: number;
        category: 'fix' | 'improvement' | 'question' | 'style' | 'test' | 'docs' | 'other';
        actionable: boolean;
    }> {
        const prompt = `
You are an expert code reviewer analyzing a pull request comment. Determine the intent and actionability.

PR Comment: "${context.comment.body}"
File: ${context.comment.filePath || 'General comment'}
Line: ${context.comment.line || 'N/A'}

Context:
${context.surroundingCode || 'No code context available'}

Analyze this comment and respond with JSON:
{
  "understood": boolean,
  "description": "Brief description of what the reviewer wants",
  "confidence": number (0-100),
  "category": "fix|improvement|question|style|test|docs|other",
  "actionable": boolean,
  "specificLocation": boolean,
  "suggestedAction": "What specific action to take"
}

Focus on:
1. Is this a request for code changes?
2. Is it specific enough to act on?
3. What exactly does the reviewer want changed?
4. How confident are you in this interpretation?
`;

        try {
            const response = await this.llmProvider.generateCode({
                prompt: prompt,
                maxTokens: 500,
                temperature: 0.1
            });

            const parsed = JSON.parse(response.content);
            return {
                understood: parsed.understood && parsed.actionable,
                description: parsed.description,
                confidence: parsed.confidence,
                category: parsed.category,
                actionable: parsed.actionable
            };
        } catch (error) {
            return {
                understood: false,
                description: 'Could not parse comment intent',
                confidence: 0,
                category: 'other',
                actionable: false
            };
        }
    }

    /**
     * Enhances context by getting more file information
     */
    private async enhanceContext(context: ResolveContext): Promise<ResolveContext> {
        if (!context.comment.filePath || !this.octokit) {
            return context;
        }

        try {
            // Get full file content
            const fileResponse = await this.octokit.repos.getContent({
                owner: this.repoOwner,
                repo: this.repoName,
                path: context.comment.filePath,
                ref: context.commitSha
            });

            if ('content' in fileResponse.data) {
                const fileContent = Buffer.from(fileResponse.data.content, 'base64').toString('utf8');
                
                // Get surrounding code context (20 lines before and after)
                const lines = fileContent.split('\n');
                const lineNumber = context.comment.line || 0;
                const startLine = Math.max(0, lineNumber - 20);
                const endLine = Math.min(lines.length, lineNumber + 20);
                const surroundingCode = lines.slice(startLine, endLine).join('\n');

                return {
                    ...context,
                    fileContent,
                    surroundingCode
                };
            }
        } catch (error) {
            console.error('Failed to enhance context:', error);
        }

        return context;
    }

    /**
     * Generates a fix plan based on the comment intent
     */
    private async generateFixPlan(
        intent: any, 
        context: ResolveContext
    ): Promise<ChangePlan> {
        const prompt = `
You are an expert developer fixing code based on a PR review comment.

Review Comment: "${context.comment.body}"
Intent: ${intent.description}
Category: ${intent.category}

File: ${context.comment.filePath}
Line: ${context.comment.line || 'General'}

Current Code Context:
\`\`\`
${context.surroundingCode || 'No context available'}
\`\`\`

Generate a precise fix plan to address this review comment. Respond with JSON:
{
  "summary": "Brief description of the fix",
  "reasoning": "Why this fix addresses the comment",
  "changes": [
    {
      "filePath": "path/to/file.ts",
      "type": "modify|create|delete",
      "description": "What will be changed",
      "lineStart": number,
      "lineEnd": number,
      "newCode": "The exact new code to insert"
    }
  ]
}

Make sure the fix is:
1. Minimal and targeted
2. Maintains existing functionality
3. Follows the codebase style
4. Directly addresses the reviewer's concern
`;

        const response = await this.llmProvider.generateCode({
            prompt: prompt,
            maxTokens: 1000,
            temperature: 0.2
        });

        const parsed = JSON.parse(response.content);
        
        return {
            id: Math.random().toString(36).substring(7),
            intent: intent.description,
            description: intent.description,
            timestamp: new Date(),
            steps: parsed.changes.map((change: any) => ({
                id: Math.random().toString(36).substring(7),
                filePath: change.filePath,
                operation: change.type || 'modify',
                description: change.description,
                content: change.newCode,
                reasoning: change.reasoning || 'Address PR feedback'
            })),
            dependencies: [],
            executionOrder: 'sequential' as const,
            riskLevel: 'low' as const,
            reversible: true,
            expectedOutcome: parsed.summary,
            testableConditions: []
        };
    }

    /**
     * Generates a professional response to the reviewer
     */
    private generateResponse(intent: any, changePlan: ChangePlan): string {
        const responses = {
            fix: `Thanks for catching this! I've implemented the suggested fix:

${changePlan.description}

The changes ensure ${intent.description.toLowerCase()} while maintaining backward compatibility.`,

            improvement: `Great suggestion! I've made the following improvements:

${changePlan.description}

This change ${intent.description.toLowerCase()} and should improve the overall code quality.`,

            style: `Good point on code style. I've updated the formatting to align with the project standards:

${changePlan.description}`,

            test: `You're absolutely right about test coverage. I've added:

${changePlan.description}`,

            docs: `Thanks for pointing that out! I've updated the documentation:

${changePlan.description}`
        };

        return responses[intent.category as keyof typeof responses] || 
               `Thanks for the feedback! I've addressed your comment with the following changes:\n\n${changePlan.description}`;
    }

    /**
     * Replies to a PR comment
     */
    private async replyToComment(
        prNumber: number,
        originalComment: PRComment,
        response: string
    ): Promise<void> {
        if (!this.octokit) {
            throw new Error('GitHub client not initialized');
        }

        if (originalComment.isReviewComment) {
            // Reply to review comment
            await this.octokit.pulls.createReplyForReviewComment({
                owner: this.repoOwner,
                repo: this.repoName,
                pull_number: prNumber,
                comment_id: originalComment.id,
                body: response
            });
        } else {
            // Reply to issue comment
            await this.octokit.issues.createComment({
                owner: this.repoOwner,
                repo: this.repoName,
                issue_number: prNumber,
                body: `@${originalComment.author} ${response}`
            });
        }
    }

    /**
     * Commits the resolution changes
     */
    private async commitResolution(
        resolution: ResolutionResult,
        originalComment: PRComment
    ): Promise<void> {
        const commitMessage = `Address PR feedback: ${resolution.intent}

Resolves comment by @${originalComment.author}:
"${originalComment.body}"

${resolution.changePlan?.description || 'Applied requested changes'}`;

        // The actual git commit would be handled by the PR lifecycle engine
        console.log('Commit message generated:', commitMessage);
    }

    /**
     * Checks if a comment has already been resolved
     */
    async isCommentResolved(comment: PRComment): Promise<boolean> {
        // For now, we'll consider review comments as resolved if they have replies
        // In the future, we could track resolution status more formally
        return false;
    }

    /**
     * Gets all unresolved actionable comments for a PR
     */
    async getActionableComments(prNumber: number): Promise<PRComment[]> {
        if (!this.octokit) {
            throw new Error('GitHub client not initialized');
        }

        try {
            // Get all comments
            const issueComments = await this.octokit.issues.listComments({
                owner: this.repoOwner,
                repo: this.repoName,
                issue_number: prNumber
            });

            const reviewComments = await this.octokit.pulls.listReviewComments({
                owner: this.repoOwner,
                repo: this.repoName,
                pull_number: prNumber
            });

            const allComments: PRComment[] = [
                ...issueComments.data.map(c => ({
                    id: c.id,
                    author: c.user?.login || 'unknown',
                    body: c.body || '',
                    createdAt: new Date(c.created_at),
                    updatedAt: new Date(c.updated_at),
                    isReviewComment: false
                })),
                ...reviewComments.data.map(c => ({
                    id: c.id,
                    author: c.user?.login || 'unknown',
                    body: c.body || '',
                    createdAt: new Date(c.created_at),
                    updatedAt: new Date(c.updated_at),
                    filePath: c.path,
                    line: c.line || undefined,
                    isReviewComment: true
                }))
            ];

            // Filter for potentially actionable comments
            const actionableComments = [];
            for (const comment of allComments) {
                // Skip bot comments
                if (comment.author.includes('bot') || comment.author.includes('NAVI')) {
                    continue;
                }

                // Skip very short comments
                if (comment.body.length < 10) {
                    continue;
                }

                // Check if already resolved
                const resolved = await this.isCommentResolved(comment);
                if (!resolved) {
                    actionableComments.push(comment);
                }
            }

            return actionableComments;
        } catch (error) {
            throw new Error(`Failed to get actionable comments: ${error}`);
        }
    }
}