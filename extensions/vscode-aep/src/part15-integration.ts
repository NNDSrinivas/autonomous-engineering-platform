/*
VS Code Extension Integration for Part 15 Autonomous Engineering Features

This module provides the command handlers and integration points for all
Part 15 features in the Navi VS Code extension.

Commands added:
- navi.sprint.plan - Plan new sprint with AI assistance
- navi.sprint.monitor - Monitor current sprint progress
- navi.backlog.analyze - Analyze and prioritize backlog
- navi.kpi.dashboard - Show engineering KPI dashboard
- navi.memory.search - Search long-term project memory
- navi.memory.store - Store new memory/learning
- navi.multirepo.sync - Synchronize multi-repo dependencies
- navi.multirepo.plan - Plan multi-repo operation
- navi.pr.review - Review PR with AI analysis
- navi.pr.fix - Apply automated PR fixes
*/

import * as vscode from 'vscode';
import axios from 'axios';

interface BackendResponse {
    success: boolean;
    data?: any;
    error?: string;
}

interface SprintPlan {
    sprint_id: string;
    goals: string[];
    selected_items: any[];
    timeline: any;
    capacity_analysis: any;
}

interface BacklogAnalysis {
    total_items: number;
    priority_distribution: Record<string, number>;
    recommendations: string[];
    ranked_items: any[];
}

interface KPIMetrics {
    velocity: number;
    mttr_hours: number;
    pr_throughput: number;
    bug_density: number;
    trends: Record<string, number>;
}

interface MemorySearchResult {
    memories: Array<{
        title: string;
        content: string;
        importance: string;
        tags: string[];
        created_at: string;
    }>;
}

interface PRAnalysis {
    pr_id: string;
    overall_score: number;
    review_comments: any[];
    security_issues: any[];
    patch_suggestions: any[];
    approval_recommendation: string;
}

class NaviPart15Integration {
    private backendUrl: string;
    private outputChannel: vscode.OutputChannel;

    constructor(context: vscode.ExtensionContext) {
        this.backendUrl = vscode.workspace.getConfiguration('navi').get('backendUrl', 'http://localhost:8787');
        this.outputChannel = vscode.window.createOutputChannel('Navi Autonomous Engineering');

        this.registerCommands(context);
    }

    private registerCommands(context: vscode.ExtensionContext) {
        // Sprint Planning Commands
        context.subscriptions.push(
            vscode.commands.registerCommand('navi.sprint.plan', () => this.planSprint())
        );

        context.subscriptions.push(
            vscode.commands.registerCommand('navi.sprint.monitor', () => this.monitorSprint())
        );

        // Backlog Management Commands  
        context.subscriptions.push(
            vscode.commands.registerCommand('navi.backlog.analyze', () => this.analyzeBacklog())
        );

        context.subscriptions.push(
            vscode.commands.registerCommand('navi.backlog.add', () => this.addBacklogItem())
        );

        // KPI Dashboard Commands
        context.subscriptions.push(
            vscode.commands.registerCommand('navi.kpi.dashboard', () => this.showKPIDashboard())
        );

        context.subscriptions.push(
            vscode.commands.registerCommand('navi.kpi.report', () => this.generateKPIReport())
        );

        // Memory Management Commands
        context.subscriptions.push(
            vscode.commands.registerCommand('navi.memory.search', () => this.searchMemory())
        );

        context.subscriptions.push(
            vscode.commands.registerCommand('navi.memory.store', () => this.storeMemory())
        );

        context.subscriptions.push(
            vscode.commands.registerCommand('navi.memory.insights', () => this.getMemoryInsights())
        );

        // Multi-Repo Commands
        context.subscriptions.push(
            vscode.commands.registerCommand('navi.multirepo.sync', () => this.syncRepositories())
        );

        context.subscriptions.push(
            vscode.commands.registerCommand('navi.multirepo.plan', () => this.planMultiRepoOperation())
        );

        context.subscriptions.push(
            vscode.commands.registerCommand('navi.multirepo.ecosystem', () => this.showEcosystemMap())
        );

        // PR Review Commands
        context.subscriptions.push(
            vscode.commands.registerCommand('navi.pr.review', () => this.reviewPullRequest())
        );

        context.subscriptions.push(
            vscode.commands.registerCommand('navi.pr.fix', () => this.applyAutomatedFixes())
        );

        // Autonomous Organization Commands
        context.subscriptions.push(
            vscode.commands.registerCommand('navi.autonomous.status', () => this.showAutonomousStatus())
        );
    }

    // Sprint Planning Implementation
    private async planSprint(): Promise<void> {
        try {
            this.outputChannel.appendLine('🚀 Starting autonomous sprint planning...');

            // Get sprint parameters from user
            const sprintGoals = await vscode.window.showInputBox({
                prompt: 'Enter sprint goals (comma-separated)',
                placeHolder: 'Improve performance, Fix critical bugs, Add new features'
            });

            if (!sprintGoals) {
                return;
            }

            const capacityHours = await vscode.window.showInputBox({
                prompt: 'Enter team capacity in hours for this sprint',
                placeHolder: '160'
            });

            const capacity = parseInt(capacityHours || '160');

            // Call backend sprint planner
            const response = await this.callBackend('/api/sprint/plan', {
                goals: sprintGoals.split(',').map(g => g.trim()),
                capacity_hours: capacity,
                team_size: 4
            });

            if (response.success && response.data) {
                const sprintPlan: SprintPlan = response.data;

                // Show sprint plan in webview
                this.showSprintPlanWebview(sprintPlan);

                this.outputChannel.appendLine(`✅ Sprint planned successfully: ${sprintPlan.sprint_id}`);
                vscode.window.showInformationMessage(
                    `Sprint planned with ${sprintPlan.selected_items.length} items. Check output for details.`
                );
            } else {
                throw new Error(response.error || 'Failed to plan sprint');
            }

        } catch (error) {
            this.handleError('Sprint Planning', error);
        }
    }

    private async monitorSprint(): Promise<void> {
        try {
            this.outputChannel.appendLine('📊 Monitoring current sprint progress...');

            const response = await this.callBackend('/api/sprint/current', {});

            if (response.success && response.data) {
                const progress = response.data;

                // Show progress in webview
                this.showSprintProgressWebview(progress);

                this.outputChannel.appendLine(`📈 Current sprint progress: ${progress.completion_percentage}%`);
            } else {
                vscode.window.showWarningMessage('No active sprint found');
            }

        } catch (error) {
            this.handleError('Sprint Monitoring', error);
        }
    }

    // Backlog Management Implementation  
    private async analyzeBacklog(): Promise<void> {
        try {
            this.outputChannel.appendLine('🎯 Analyzing and prioritizing backlog...');

            const response = await this.callBackend('/api/backlog/analyze', {});

            if (response.success && response.data) {
                const analysis: BacklogAnalysis = response.data;

                // Show analysis results
                this.showBacklogAnalysisWebview(analysis);

                this.outputChannel.appendLine(`📋 Analyzed ${analysis.total_items} backlog items`);
                vscode.window.showInformationMessage(
                    `Backlog analyzed: ${analysis.total_items} items prioritized. Check output for recommendations.`
                );
            } else {
                throw new Error(response.error || 'Failed to analyze backlog');
            }

        } catch (error) {
            this.handleError('Backlog Analysis', error);
        }
    }

    private async addBacklogItem(): Promise<void> {
        try {
            const title = await vscode.window.showInputBox({
                prompt: 'Enter backlog item title',
                placeHolder: 'Fix login authentication bug'
            });

            if (!title) return;

            const description = await vscode.window.showInputBox({
                prompt: 'Enter item description',
                placeHolder: 'Users cannot login with valid credentials...'
            });

            const itemType = await vscode.window.showQuickPick(
                ['FEATURE', 'BUG', 'IMPROVEMENT', 'CHORE'],
                { placeHolder: 'Select item type' }
            );

            if (!itemType) return;

            const response = await this.callBackend('/api/backlog/add', {
                title,
                description: description || '',
                item_type: itemType.toLowerCase()
            });

            if (response.success) {
                vscode.window.showInformationMessage(`Added backlog item: ${title}`);
                this.outputChannel.appendLine(`➕ Added backlog item: ${title} (${itemType})`);
            } else {
                throw new Error(response.error || 'Failed to add backlog item');
            }

        } catch (error) {
            this.handleError('Add Backlog Item', error);
        }
    }

    // KPI Dashboard Implementation
    private async showKPIDashboard(): Promise<void> {
        try {
            this.outputChannel.appendLine('📊 Loading engineering KPI dashboard...');

            const response = await this.callBackend('/api/kpi/dashboard', {});

            if (response.success && response.data) {
                const metrics: KPIMetrics = response.data;

                // Show KPI dashboard in webview
                this.showKPIDashboardWebview(metrics);

                this.outputChannel.appendLine(`📈 KPI Dashboard loaded - Velocity: ${metrics.velocity}, MTTR: ${metrics.mttr_hours}h`);
            } else {
                throw new Error(response.error || 'Failed to load KPI dashboard');
            }

        } catch (error) {
            this.handleError('KPI Dashboard', error);
        }
    }

    private async generateKPIReport(): Promise<void> {
        try {
            const period = await vscode.window.showQuickPick(
                ['last_week', 'last_month', 'last_quarter'],
                { placeHolder: 'Select reporting period' }
            );

            if (!period) return;

            this.outputChannel.appendLine(`📊 Generating KPI report for ${period}...`);

            const response = await this.callBackend('/api/kpi/report', { period });

            if (response.success && response.data) {
                // Save report to file
                const report = response.data.report;
                const workspaceFolder = vscode.workspace.workspaceFolders?.[0];

                if (workspaceFolder) {
                    const reportPath = vscode.Uri.joinPath(workspaceFolder.uri, `kpi-report-${period}.md`);
                    await vscode.workspace.fs.writeFile(reportPath, Buffer.from(report, 'utf8'));

                    // Open the report
                    const doc = await vscode.workspace.openTextDocument(reportPath);
                    await vscode.window.showTextDocument(doc);

                    vscode.window.showInformationMessage(`KPI report generated: ${reportPath.fsPath}`);
                }
            } else {
                throw new Error(response.error || 'Failed to generate KPI report');
            }

        } catch (error) {
            this.handleError('KPI Report', error);
        }
    }

    // Memory Management Implementation
    private async searchMemory(): Promise<void> {
        try {
            const query = await vscode.window.showInputBox({
                prompt: 'Search project memory',
                placeHolder: 'authentication patterns, API design decisions...'
            });

            if (!query) return;

            this.outputChannel.appendLine(`🧠 Searching project memory for: "${query}"`);

            const response = await this.callBackend('/api/memory/search', { query });

            if (response.success && response.data) {
                const results: MemorySearchResult = response.data;

                if (results.memories.length > 0) {
                    // Show memory search results
                    this.showMemorySearchWebview(results, query);

                    this.outputChannel.appendLine(`🔍 Found ${results.memories.length} relevant memories`);
                } else {
                    vscode.window.showInformationMessage('No relevant memories found for your search');
                }
            } else {
                throw new Error(response.error || 'Failed to search memory');
            }

        } catch (error) {
            this.handleError('Memory Search', error);
        }
    }

    private async storeMemory(): Promise<void> {
        try {
            const memoryType = await vscode.window.showQuickPick([
                'architecture_decision',
                'api_contract',
                'business_rule',
                'technical_debt',
                'bug_pattern',
                'coding_style',
                'user_preference'
            ], { placeHolder: 'Select memory type' });

            if (!memoryType) return;

            const title = await vscode.window.showInputBox({
                prompt: 'Enter memory title',
                placeHolder: 'Database connection pooling decision'
            });

            if (!title) return;

            const content = await vscode.window.showInputBox({
                prompt: 'Enter memory content',
                placeHolder: 'We decided to use connection pooling with max 20 connections because...'
            });

            if (!content) return;

            const importance = await vscode.window.showQuickPick([
                'critical', 'high', 'medium', 'low'
            ], { placeHolder: 'Select importance level' });

            if (!importance) return;

            const response = await this.callBackend('/api/memory/store', {
                memory_type: memoryType,
                title,
                content,
                importance
            });

            if (response.success) {
                vscode.window.showInformationMessage(`Memory stored: ${title}`);
                this.outputChannel.appendLine(`💾 Stored ${importance} importance memory: ${title}`);
            } else {
                throw new Error(response.error || 'Failed to store memory');
            }

        } catch (error) {
            this.handleError('Store Memory', error);
        }
    }

    private async getMemoryInsights(): Promise<void> {
        try {
            this.outputChannel.appendLine('🧠 Generating insights from project memory...');

            const response = await this.callBackend('/api/memory/insights', {
                context: 'current project analysis'
            });

            if (response.success && response.data) {
                const insights = response.data.insights;

                // Show insights in webview
                this.showMemoryInsightsWebview(insights);

                this.outputChannel.appendLine(`💡 Generated ${insights.length} insights from project memory`);
            } else {
                throw new Error(response.error || 'Failed to generate insights');
            }

        } catch (error) {
            this.handleError('Memory Insights', error);
        }
    }

    // Multi-Repository Management
    private async syncRepositories(): Promise<void> {
        try {
            this.outputChannel.appendLine('🔄 Synchronizing multi-repository dependencies...');

            const response = await this.callBackend('/api/multirepo/sync', {});

            if (response.success && response.data) {
                const syncResults = response.data;

                this.outputChannel.appendLine(`✅ Synced ${syncResults.synced_repos.length} repositories`);

                if (syncResults.conflicts.length > 0) {
                    vscode.window.showWarningMessage(
                        `Sync completed with ${syncResults.conflicts.length} conflicts. Check output for details.`
                    );

                    syncResults.conflicts.forEach((conflict: any) => {
                        this.outputChannel.appendLine(`⚠️  Conflict in ${conflict.repo}: ${conflict.description}`);
                    });
                } else {
                    vscode.window.showInformationMessage('All repositories synchronized successfully');
                }
            } else {
                throw new Error(response.error || 'Failed to sync repositories');
            }

        } catch (error) {
            this.handleError('Repository Sync', error);
        }
    }

    private async planMultiRepoOperation(): Promise<void> {
        try {
            const operationType = await vscode.window.showQuickPick([
                'dependency_update',
                'api_contract_change',
                'shared_component_update',
                'cross_repo_refactor',
                'security_patch',
                'release_coordination'
            ], { placeHolder: 'Select operation type' });

            if (!operationType) return;

            const title = await vscode.window.showInputBox({
                prompt: 'Enter operation title',
                placeHolder: 'Update shared authentication library'
            });

            if (!title) return;

            const description = await vscode.window.showInputBox({
                prompt: 'Enter operation description',
                placeHolder: 'Update to version 2.0 with breaking changes in auth API...'
            });

            const affectedRepos = await vscode.window.showInputBox({
                prompt: 'Enter affected repositories (comma-separated)',
                placeHolder: 'frontend, backend, mobile-app'
            });

            if (!affectedRepos) return;

            this.outputChannel.appendLine(`🎯 Planning multi-repo operation: ${title}`);

            const response = await this.callBackend('/api/multirepo/plan', {
                operation_type: operationType,
                title,
                description: description || '',
                affected_repos: affectedRepos.split(',').map(r => r.trim())
            });

            if (response.success && response.data) {
                const operation = response.data;

                // Show operation plan
                this.showMultiRepoOperationWebview(operation);

                this.outputChannel.appendLine(`📋 Multi-repo operation planned: ${operation.id}`);
                vscode.window.showInformationMessage(
                    `Operation planned: ${title}. Estimated duration: ${operation.estimated_duration}`
                );
            } else {
                throw new Error(response.error || 'Failed to plan multi-repo operation');
            }

        } catch (error) {
            this.handleError('Multi-Repo Planning', error);
        }
    }

    private async showEcosystemMap(): Promise<void> {
        try {
            this.outputChannel.appendLine('🗺️  Loading repository ecosystem map...');

            const response = await this.callBackend('/api/multirepo/ecosystem', {});

            if (response.success && response.data) {
                const ecosystemMap = response.data;

                // Show ecosystem visualization
                this.showEcosystemMapWebview(ecosystemMap);

                this.outputChannel.appendLine(`🏗️  Loaded ecosystem with ${ecosystemMap.metrics.total_repositories} repositories`);
            } else {
                throw new Error(response.error || 'Failed to load ecosystem map');
            }

        } catch (error) {
            this.handleError('Ecosystem Map', error);
        }
    }

    // PR Review Implementation
    private async reviewPullRequest(): Promise<void> {
        try {
            const prId = await vscode.window.showInputBox({
                prompt: 'Enter Pull Request ID or URL',
                placeHolder: '#123 or https://github.com/user/repo/pull/123'
            });

            if (!prId) return;

            this.outputChannel.appendLine(`🔍 Analyzing pull request: ${prId}`);

            // Show progress
            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: 'Analyzing Pull Request',
                cancellable: false
            }, async (progress) => {
                progress.report({ increment: 0, message: 'Loading PR details...' });

                const response = await this.callBackend('/api/pr/review', { pr_id: prId });

                progress.report({ increment: 50, message: 'Analyzing code changes...' });

                if (response.success && response.data) {
                    const analysis: PRAnalysis = response.data;

                    progress.report({ increment: 100, message: 'Review complete!' });

                    // Show review results
                    this.showPRReviewWebview(analysis);

                    this.outputChannel.appendLine(`✅ PR review complete - Score: ${analysis.overall_score}/10`);

                    const message = analysis.security_issues.length > 0
                        ? `Review complete with ${analysis.security_issues.length} security issues. Recommendation: ${analysis.approval_recommendation}`
                        : `Review complete. Score: ${analysis.overall_score}/10. Recommendation: ${analysis.approval_recommendation}`;

                    vscode.window.showInformationMessage(message);
                } else {
                    throw new Error(response.error || 'Failed to review PR');
                }
            });

        } catch (error) {
            this.handleError('PR Review', error);
        }
    }

    private async applyAutomatedFixes(): Promise<void> {
        try {
            const prId = await vscode.window.showInputBox({
                prompt: 'Enter Pull Request ID to apply fixes',
                placeHolder: '#123'
            });

            if (!prId) return;

            this.outputChannel.appendLine(`🔧 Applying automated fixes to PR: ${prId}`);

            const response = await this.callBackend('/api/pr/fix', { pr_id: prId });

            if (response.success && response.data) {
                const results = response.data;

                this.outputChannel.appendLine(`✅ Applied ${results.applied_patches.length} automated fixes`);

                results.applied_patches.forEach((patch: any) => {
                    this.outputChannel.appendLine(`  🔧 Fixed ${patch.category} in ${patch.file} (${patch.lines})`);
                });

                if (results.errors.length > 0) {
                    this.outputChannel.appendLine(`⚠️  ${results.errors.length} fixes failed:`);
                    results.errors.forEach((error: any) => {
                        this.outputChannel.appendLine(`    ❌ ${error.file}: ${error.error}`);
                    });
                }

                vscode.window.showInformationMessage(
                    `Applied ${results.applied_patches.length} automated fixes. Check output for details.`
                );
            } else {
                throw new Error(response.error || 'Failed to apply fixes');
            }

        } catch (error) {
            this.handleError('Apply PR Fixes', error);
        }
    }

    // Autonomous Organization Status
    private async showAutonomousStatus(): Promise<void> {
        try {
            this.outputChannel.appendLine('🤖 Loading autonomous engineering organization status...');

            // Call all status endpoints
            const [sprintStatus, backlogStatus, kpiStatus, memoryStatus, multiRepoStatus] = await Promise.all([
                this.callBackend('/api/sprint/status', {}),
                this.callBackend('/api/backlog/status', {}),
                this.callBackend('/api/kpi/status', {}),
                this.callBackend('/api/memory/status', {}),
                this.callBackend('/api/multirepo/status', {})
            ]);

            const statusData = {
                sprint: sprintStatus.success ? sprintStatus.data : { status: 'unavailable' },
                backlog: backlogStatus.success ? backlogStatus.data : { status: 'unavailable' },
                kpi: kpiStatus.success ? kpiStatus.data : { status: 'unavailable' },
                memory: memoryStatus.success ? memoryStatus.data : { status: 'unavailable' },
                multirepo: multiRepoStatus.success ? multiRepoStatus.data : { status: 'unavailable' }
            };

            // Show comprehensive status
            this.showAutonomousStatusWebview(statusData);

            this.outputChannel.appendLine('🤖 Autonomous engineering organization status loaded');

        } catch (error) {
            this.handleError('Autonomous Status', error);
        }
    }

    // Webview Implementations (simplified - would need full HTML/CSS/JS)
    private showSprintPlanWebview(sprintPlan: SprintPlan): void {
        const panel = vscode.window.createWebviewPanel(
            'sprintPlan',
            'Sprint Plan',
            vscode.ViewColumn.Two,
            {}
        );

        panel.webview.html = `
        <!DOCTYPE html>
        <html>
        <head>
            <title>Sprint Plan</title>
            <style>
                body { font-family: Arial, sans-serif; padding: 20px; }
                .header { color: #0066cc; margin-bottom: 20px; }
                .section { margin: 15px 0; }
                .item { background: #f5f5f5; padding: 10px; margin: 5px 0; border-radius: 5px; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🚀 Sprint Plan: ${sprintPlan.sprint_id}</h1>
            </div>
            
            <div class="section">
                <h2>Goals</h2>
                ${sprintPlan.goals.map(goal => `<div class="item">• ${goal}</div>`).join('')}
            </div>
            
            <div class="section">
                <h2>Selected Items (${sprintPlan.selected_items.length})</h2>
                ${sprintPlan.selected_items.map(item =>
            `<div class="item">
                        <strong>${item.title || 'Untitled'}</strong>
                        <br>Estimated: ${item.estimated_hours || 'TBD'} hours
                    </div>`
        ).join('')}
            </div>
            
            <div class="section">
                <h2>Capacity Analysis</h2>
                <div class="item">
                    Total Capacity: ${sprintPlan.capacity_analysis?.total_hours || 'TBD'} hours<br>
                    Allocated: ${sprintPlan.capacity_analysis?.allocated_hours || 'TBD'} hours<br>
                    Utilization: ${sprintPlan.capacity_analysis?.utilization_percentage || 'TBD'}%
                </div>
            </div>
        </body>
        </html>`;
    }

    private showKPIDashboardWebview(metrics: KPIMetrics): void {
        const panel = vscode.window.createWebviewPanel(
            'kpiDashboard',
            'Engineering KPI Dashboard',
            vscode.ViewColumn.Two,
            {}
        );

        panel.webview.html = `
        <!DOCTYPE html>
        <html>
        <head>
            <title>KPI Dashboard</title>
            <style>
                body { font-family: Arial, sans-serif; padding: 20px; }
                .header { color: #0066cc; margin-bottom: 20px; }
                .metric { 
                    background: #f8f9fa; 
                    border: 1px solid #e9ecef;
                    padding: 15px; 
                    margin: 10px 0; 
                    border-radius: 8px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                .metric-value { font-size: 24px; font-weight: bold; color: #28a745; }
                .metric-label { color: #6c757d; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 Engineering KPI Dashboard</h1>
            </div>
            
            <div class="metric">
                <div>
                    <div class="metric-label">Team Velocity</div>
                    <div>Story points per sprint</div>
                </div>
                <div class="metric-value">${metrics.velocity}</div>
            </div>
            
            <div class="metric">
                <div>
                    <div class="metric-label">Mean Time to Recovery (MTTR)</div>
                    <div>Hours to resolve incidents</div>
                </div>
                <div class="metric-value">${metrics.mttr_hours}h</div>
            </div>
            
            <div class="metric">
                <div>
                    <div class="metric-label">PR Throughput</div>
                    <div>Pull requests per week</div>
                </div>
                <div class="metric-value">${metrics.pr_throughput}</div>
            </div>
            
            <div class="metric">
                <div>
                    <div class="metric-label">Bug Density</div>
                    <div>Bugs per 1000 lines of code</div>
                </div>
                <div class="metric-value">${metrics.bug_density}</div>
            </div>
        </body>
        </html>`;
    }

    private showPRReviewWebview(analysis: PRAnalysis): void {
        const panel = vscode.window.createWebviewPanel(
            'prReview',
            `PR Review: ${analysis.pr_id}`,
            vscode.ViewColumn.Two,
            {}
        );

        const criticalComments = analysis.review_comments.filter(c => c.severity === 'critical');
        const highComments = analysis.review_comments.filter(c => c.severity === 'high');

        panel.webview.html = `
        <!DOCTYPE html>
        <html>
        <head>
            <title>PR Review</title>
            <style>
                body { font-family: Arial, sans-serif; padding: 20px; }
                .header { color: #0066cc; margin-bottom: 20px; }
                .score { 
                    font-size: 32px; 
                    font-weight: bold; 
                    color: ${analysis.overall_score >= 8 ? '#28a745' : analysis.overall_score >= 6 ? '#ffc107' : '#dc3545'};
                }
                .recommendation { 
                    padding: 15px; 
                    border-radius: 8px; 
                    margin: 15px 0;
                    background: ${analysis.approval_recommendation.includes('APPROVE') ? '#d4edda' : '#f8d7da'};
                    border: 1px solid ${analysis.approval_recommendation.includes('APPROVE') ? '#c3e6cb' : '#f5c6cb'};
                }
                .issue { 
                    background: #fff3cd; 
                    border: 1px solid #ffeaa7;
                    padding: 10px; 
                    margin: 8px 0; 
                    border-radius: 5px; 
                }
                .critical { background: #f8d7da; border-color: #f5c6cb; }
                .security { background: #d1ecf1; border-color: #bee5eb; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🔍 PR Review Results</h1>
                <div>PR: ${analysis.pr_id}</div>
            </div>
            
            <div class="score">Score: ${analysis.overall_score}/10</div>
            
            <div class="recommendation">
                <strong>Recommendation:</strong> ${analysis.approval_recommendation}
            </div>
            
            ${analysis.security_issues.length > 0 ? `
                <h2>🔒 Security Issues (${analysis.security_issues.length})</h2>
                ${analysis.security_issues.map(issue => `
                    <div class="issue security">
                        <strong>${issue.vulnerability_type}</strong> in ${issue.file_path}:${issue.line_number}
                        <br>${issue.description}
                    </div>
                `).join('')}
            ` : ''}
            
            ${criticalComments.length > 0 ? `
                <h2>🚨 Critical Issues (${criticalComments.length})</h2>
                ${criticalComments.map(comment => `
                    <div class="issue critical">
                        <strong>${comment.title}</strong> in ${comment.file_path}
                        ${comment.line_number ? `:${comment.line_number}` : ''}
                        <br>${comment.message}
                    </div>
                `).join('')}
            ` : ''}
            
            ${highComments.length > 0 ? `
                <h2>⚠️ High Priority Issues (${highComments.length})</h2>
                ${highComments.slice(0, 5).map(comment => `
                    <div class="issue">
                        <strong>${comment.title}</strong> in ${comment.file_path}
                        ${comment.line_number ? `:${comment.line_number}` : ''}
                        <br>${comment.message}
                    </div>
                `).join('')}
            ` : ''}
            
            ${analysis.patch_suggestions.length > 0 ? `
                <h2>🔧 Automated Fixes Available (${analysis.patch_suggestions.length})</h2>
                <p>Run <code>navi.pr.fix</code> to apply high-confidence fixes automatically.</p>
            ` : ''}
        </body>
        </html>`;
    }

    // Utility methods
    private async callBackend(endpoint: string, data: any): Promise<BackendResponse> {
        try {
            const response = await axios.post(`${this.backendUrl}${endpoint}`, data, {
                timeout: 30000,
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            return { success: true, data: response.data };
        } catch (error: any) {
            return {
                success: false,
                error: error.response?.data?.detail || error.message
            };
        }
    }

    private handleError(operation: string, error: any): void {
        const message = `${operation} failed: ${error.message || error}`;
        this.outputChannel.appendLine(`❌ ${message}`);
        vscode.window.showErrorMessage(message);
    }

    // Placeholder methods for other webviews
    private showSprintProgressWebview(progress: any): void { /* Implementation */ }
    private showBacklogAnalysisWebview(analysis: BacklogAnalysis): void { /* Implementation */ }
    private showMemorySearchWebview(results: MemorySearchResult, query: string): void { /* Implementation */ }
    private showMemoryInsightsWebview(insights: any[]): void { /* Implementation */ }
    private showMultiRepoOperationWebview(operation: any): void { /* Implementation */ }
    private showEcosystemMapWebview(ecosystemMap: any): void { /* Implementation */ }
    private showAutonomousStatusWebview(statusData: any): void { /* Implementation */ }
}

export default NaviPart15Integration;