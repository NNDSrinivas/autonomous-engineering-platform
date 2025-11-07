import * as vscode from 'vscode';
import { AEPApiClient, JiraTask, ExecutionPlan, PlanStep } from '../api/AEPApiClient';

/**
 * Plan & Act Panel - Cline-style step-by-step execution interface
 * 
 * Provides the core "Plan & Act" workflow:
 * - Generate execution plan from task description
 * - Show step-by-step breakdown with approval checkboxes
 * - Execute approved steps with progress tracking
 * - Handle errors and provide retry mechanisms
 * - Real-time file preview and diff visualization
 */

export class PlanActPanel {
    public static currentPanel: PlanActPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];
    private _apiClient: AEPApiClient;
    private _currentPlan: ExecutionPlan | undefined;
    private _currentTask: JiraTask | undefined;

    public static createOrShow(extensionUri: vscode.Uri, apiClient: AEPApiClient) {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;

        // If we already have a panel, show it
        if (PlanActPanel.currentPanel) {
            PlanActPanel.currentPanel._panel.reveal(column);
            return PlanActPanel.currentPanel;
        }

        // Otherwise, create a new panel
        const panel = vscode.window.createWebviewPanel(
            'aep.planAct',
            'AEP Plan & Act',
            column || vscode.ViewColumn.Two,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [
                    vscode.Uri.joinPath(extensionUri, 'media'),
                    vscode.Uri.joinPath(extensionUri, 'out')
                ]
            }
        );

        PlanActPanel.currentPanel = new PlanActPanel(panel, extensionUri, apiClient);
        return PlanActPanel.currentPanel;
    }

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri, apiClient: AEPApiClient) {
        this._panel = panel;
        this._extensionUri = extensionUri;
        this._apiClient = apiClient;

        // Set the webview's initial html content
        this._update();

        // Listen for when the panel is disposed
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

        // Handle messages from the webview
        this._panel.webview.onDidReceiveMessage(
            async (message) => {
                switch (message.type) {
                    case 'createPlan':
                        await this.createPlan(message.description, message.context);
                        break;
                    case 'approveStep':
                        await this.approveStep(message.stepId);
                        break;
                    case 'executeStep':
                        await this.executeStep(message.stepId);
                        break;
                    case 'executeAllApproved':
                        await this.executeAllApprovedSteps();
                        break;
                    case 'rejectStep':
                        await this.rejectStep(message.stepId);
                        break;
                    case 'modifyStep':
                        await this.modifyStep(message.stepId, message.newDetails);
                        break;
                }
            },
            null,
            this._disposables
        );
    }

    /**
     * Start workflow for a specific Jira task
     */
    async startTaskWorkflow(task: JiraTask) {
        this._currentTask = task;
        this._panel.reveal();
        
        // Update panel title
        this._panel.title = `Plan & Act - ${task.key}`;
        
        // Send task data to webview
        this._panel.webview.postMessage({
            type: 'taskLoaded',
            task: task
        });

        // Auto-generate initial plan
        const planDescription = `Implement solution for ${task.key}: ${task.summary}\n\nDescription: ${task.description}`;
        await this.createPlan(planDescription, { jiraTaskKey: task.key });
    }

    /**
     * Reveal the panel
     */
    reveal() {
        this._panel.reveal();
    }

    /**
     * Dispose panel resources
     */
    public dispose() {
        PlanActPanel.currentPanel = undefined;

        // Clean up our resources
        this._panel.dispose();

        while (this._disposables.length) {
            const x = this._disposables.pop();
            if (x) {
                x.dispose();
            }
        }
    }

    /**
     * Create execution plan
     */
    private async createPlan(description: string, context?: any) {
        try {
            this._panel.webview.postMessage({ 
                type: 'showLoading', 
                message: 'Creating execution plan...' 
            });

            // Get workspace context
            const workspaceContext = await this._apiClient.getWorkspaceContext();
            
            this._currentPlan = await this._apiClient.createPlan({
                description,
                jiraTaskKey: this._currentTask?.key,
                context: { ...context, workspace: workspaceContext },
                files: [] // TODO: Get relevant files from workspace
            });

            this._panel.webview.postMessage({
                type: 'planCreated',
                plan: this._currentPlan
            });
        } catch (error) {
            this._panel.webview.postMessage({
                type: 'showError',
                message: `Failed to create plan: ${error instanceof Error ? error.message : 'Unknown error'}`
            });
        }
    }

    /**
     * Approve a specific step
     */
    private async approveStep(stepId: string) {
        if (!this._currentPlan) return;

        const step = this._currentPlan.steps.find(s => s.id === stepId);
        if (step) {
            step.status = 'approved';
            this._panel.webview.postMessage({
                type: 'stepStatusChanged',
                stepId,
                status: 'approved'
            });
        }
    }

    /**
     * Execute a specific step
     */
    private async executeStep(stepId: string) {
        if (!this._currentPlan) return;

        try {
            const step = this._currentPlan.steps.find(s => s.id === stepId);
            if (!step) return;

            // Update UI to show execution in progress
            this._panel.webview.postMessage({
                type: 'stepStatusChanged',
                stepId,
                status: 'executing'
            });

            const result = await this._apiClient.executeStep(this._currentPlan.id, stepId);

            if (result.success) {
                step.status = 'completed';
                this._panel.webview.postMessage({
                    type: 'stepCompleted',
                    stepId,
                    result: result.result
                });
            } else {
                step.status = 'error';
                this._panel.webview.postMessage({
                    type: 'stepFailed',
                    stepId,
                    error: result.error
                });
            }
        } catch (error) {
            this._panel.webview.postMessage({
                type: 'stepFailed',
                stepId,
                error: error instanceof Error ? error.message : 'Unknown error'
            });
        }
    }

    /**
     * Execute all approved steps in sequence
     */
    private async executeAllApprovedSteps() {
        if (!this._currentPlan) return;

        const approvedSteps = this._currentPlan.steps.filter(s => s.status === 'approved');
        
        for (const step of approvedSteps) {
            await this.executeStep(step.id);
            
            // Wait a bit between steps to avoid overwhelming the UI
            await new Promise(resolve => setTimeout(resolve, 500));
        }
    }

    /**
     * Reject a specific step
     */
    private async rejectStep(stepId: string) {
        if (!this._currentPlan) return;

        const step = this._currentPlan.steps.find(s => s.id === stepId);
        if (step) {
            step.status = 'rejected';
            this._panel.webview.postMessage({
                type: 'stepStatusChanged',
                stepId,
                status: 'rejected'
            });
        }
    }

    /**
     * Modify step details
     */
    private async modifyStep(stepId: string, newDetails: any) {
        if (!this._currentPlan) return;

        const step = this._currentPlan.steps.find(s => s.id === stepId);
        if (step) {
            step.details = { ...step.details, ...newDetails };
            this._panel.webview.postMessage({
                type: 'stepModified',
                stepId,
                details: step.details
            });
        }
    }

    /**
     * Update the webview content
     */
    private _update() {
        const webview = this._panel.webview;
        this._panel.webview.html = this._getHtmlForWebview(webview);
    }

    /**
     * Generate HTML content for the webview
     */
    private _getHtmlForWebview(webview: vscode.Webview) {
        const nonce = getNonce();

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
    <title>AEP Plan & Act</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            color: var(--vscode-foreground);
            background-color: var(--vscode-editor-background);
            padding: 20px;
            margin: 0;
        }
        
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--vscode-panel-border);
        }
        
        .title {
            font-size: 1.5em;
            font-weight: bold;
            color: var(--vscode-textLink-foreground);
        }
        
        .task-info {
            background-color: var(--vscode-editor-inactiveSelectionBackground);
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid var(--vscode-textLink-foreground);
        }
        
        .plan-container {
            margin-top: 20px;
        }
        
        .step {
            background-color: var(--vscode-list-inactiveSelectionBackground);
            margin-bottom: 12px;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid var(--vscode-panel-border);
        }
        
        .step-header {
            padding: 12px 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background-color: var(--vscode-editor-inactiveSelectionBackground);
        }
        
        .step-content {
            padding: 16px;
            border-top: 1px solid var(--vscode-panel-border);
        }
        
        .step-status {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: bold;
        }
        
        .status-pending { background-color: #ffa726; color: white; }
        .status-approved { background-color: #66bb6a; color: white; }
        .status-rejected { background-color: #ef5350; color: white; }
        .status-executing { background-color: #42a5f5; color: white; }
        .status-completed { background-color: #4caf50; color: white; }
        .status-error { background-color: #f44336; color: white; }
        
        .step-actions {
            display: flex;
            gap: 8px;
            margin-top: 12px;
        }
        
        .btn {
            padding: 6px 12px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.85em;
        }
        
        .btn-approve { background-color: #4caf50; color: white; }
        .btn-reject { background-color: #f44336; color: white; }
        .btn-execute { background-color: #2196f3; color: white; }
        .btn-modify { background-color: #ff9800; color: white; }
        
        .btn:hover { opacity: 0.8; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        
        .global-actions {
            position: sticky;
            bottom: 20px;
            background-color: var(--vscode-editor-background);
            padding: 16px;
            border-top: 1px solid var(--vscode-panel-border);
            display: flex;
            gap: 12px;
            justify-content: center;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: var(--vscode-descriptionForeground);
        }
        
        .error {
            color: var(--vscode-errorForeground);
            background-color: var(--vscode-inputValidation-errorBackground);
            padding: 12px;
            border-radius: 4px;
            border-left: 4px solid var(--vscode-errorForeground);
        }
        
        .plan-description {
            background-color: var(--vscode-textBlockQuote-background);
            padding: 12px;
            border-radius: 4px;
            margin-bottom: 20px;
            border-left: 3px solid var(--vscode-textBlockQuote-border);
        }
        
        .progress-bar {
            width: 100%;
            height: 8px;
            background-color: var(--vscode-progressBar-background);
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 16px;
        }
        
        .progress-fill {
            height: 100%;
            background-color: var(--vscode-progressBar-foreground);
            transition: width 0.3s ease;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">⚡ Plan & Act</div>
    </div>

    <div id="content">
        <div class="loading">
            <div>Ready to create execution plan</div>
            <div style="margin-top: 20px;">
                <textarea id="planInput" placeholder="Describe what you want to implement..." style="width: 100%; height: 100px; padding: 12px; border-radius: 4px; border: 1px solid var(--vscode-input-border); background-color: var(--vscode-input-background); color: var(--vscode-input-foreground);"></textarea>
                <div style="margin-top: 10px;">
                    <button class="btn btn-approve" onclick="createPlanFromInput()">Create Plan</button>
                </div>
            </div>
        </div>
    </div>

    <script nonce="${nonce}">
        const vscode = acquireVsCodeApi();
        let currentPlan = null;

        // Message handlers
        window.addEventListener('message', event => {
            const message = event.data;
            
            switch (message.type) {
                case 'taskLoaded':
                    showTaskInfo(message.task);
                    break;
                case 'planCreated':
                    showPlan(message.plan);
                    break;
                case 'stepStatusChanged':
                    updateStepStatus(message.stepId, message.status);
                    break;
                case 'stepCompleted':
                    handleStepCompleted(message.stepId, message.result);
                    break;
                case 'stepFailed':
                    handleStepFailed(message.stepId, message.error);
                    break;
                case 'showLoading':
                    showLoading(message.message);
                    break;
                case 'showError':
                    showError(message.message);
                    break;
            }
        });

        function createPlanFromInput() {
            const input = document.getElementById('planInput');
            const description = input.value.trim();
            
            if (!description) {
                alert('Please enter a description for what you want to implement.');
                return;
            }

            vscode.postMessage({ 
                type: 'createPlan', 
                description,
                context: {}
            });
        }

        function showTaskInfo(task) {
            const taskInfoHtml = \`
                <div class="task-info">
                    <h3>\${task.key}: \${task.summary}</h3>
                    <p>\${task.description}</p>
                    <div style="margin-top: 8px; font-size: 0.9em; color: var(--vscode-descriptionForeground);">
                        Status: \${task.status} • Priority: \${task.priority} • Assignee: \${task.assignee}
                    </div>
                </div>
            \`;
            
            document.getElementById('content').innerHTML = taskInfoHtml + document.getElementById('content').innerHTML;
        }

        function showLoading(message = 'Loading...') {
            document.getElementById('content').innerHTML = \`
                <div class="loading">\${message}</div>
            \`;
        }

        function showError(message) {
            document.getElementById('content').innerHTML = \`
                <div class="error">
                    <strong>Error:</strong> \${message}
                </div>
            \`;
        }

        function showPlan(plan) {
            currentPlan = plan;
            
            const completedSteps = plan.steps.filter(s => s.status === 'completed').length;
            const totalSteps = plan.steps.length;
            const progressPercent = totalSteps > 0 ? (completedSteps / totalSteps) * 100 : 0;
            
            const planHtml = \`
                <div class="plan-description">
                    <h3>\${plan.title}</h3>
                    <p>\${plan.description}</p>
                </div>
                
                <div class="progress-bar">
                    <div class="progress-fill" style="width: \${progressPercent}%"></div>
                </div>
                
                <div class="plan-container">
                    \${plan.steps.map((step, index) => \`
                        <div class="step" id="step-\${step.id}">
                            <div class="step-header">
                                <span><strong>Step \${index + 1}:</strong> \${step.description}</span>
                                <span class="step-status status-\${step.status}">\${step.status.toUpperCase()}</span>
                            </div>
                            <div class="step-content">
                                <div><strong>Type:</strong> \${step.type}</div>
                                \${step.details ? \`<div><strong>Details:</strong> <pre>\${JSON.stringify(step.details, null, 2)}</pre></div>\` : ''}
                                <div class="step-actions">
                                    <button class="btn btn-approve" onclick="approveStep('\${step.id}')" \${step.status !== 'pending' ? 'disabled' : ''}>
                                        ✓ Approve
                                    </button>
                                    <button class="btn btn-reject" onclick="rejectStep('\${step.id}')" \${step.status !== 'pending' && step.status !== 'approved' ? 'disabled' : ''}>
                                        ✗ Reject
                                    </button>
                                    <button class="btn btn-execute" onclick="executeStep('\${step.id}')" \${step.status !== 'approved' ? 'disabled' : ''}>
                                        ▶ Execute
                                    </button>
                                    <button class="btn btn-modify" onclick="modifyStep('\${step.id}')">
                                        ✏ Modify
                                    </button>
                                </div>
                            </div>
                        </div>
                    \`).join('')}
                </div>
                
                <div class="global-actions">
                    <button class="btn btn-approve" onclick="executeAllApproved()">▶ Execute All Approved</button>
                    <button class="btn btn-modify" onclick="createNewPlan()">🔄 Create New Plan</button>
                </div>
            \`;
            
            document.getElementById('content').innerHTML = planHtml;
        }

        function approveStep(stepId) {
            vscode.postMessage({ type: 'approveStep', stepId });
        }

        function rejectStep(stepId) {
            vscode.postMessage({ type: 'rejectStep', stepId });
        }

        function executeStep(stepId) {
            vscode.postMessage({ type: 'executeStep', stepId });
        }

        function executeAllApproved() {
            vscode.postMessage({ type: 'executeAllApproved' });
        }

        function modifyStep(stepId) {
            // TODO: Implement step modification UI
            console.log('Modify step:', stepId);
        }

        function createNewPlan() {
            document.getElementById('content').innerHTML = \`
                <div style="text-align: center; padding: 20px;">
                    <textarea id="planInput" placeholder="Describe what you want to implement..." style="width: 100%; height: 100px; padding: 12px; border-radius: 4px; border: 1px solid var(--vscode-input-border); background-color: var(--vscode-input-background); color: var(--vscode-input-foreground);"></textarea>
                    <div style="margin-top: 10px;">
                        <button class="btn btn-approve" onclick="createPlanFromInput()">Create Plan</button>
                    </div>
                </div>
            \`;
        }

        function updateStepStatus(stepId, status) {
            const stepElement = document.getElementById(\`step-\${stepId}\`);
            if (stepElement) {
                const statusElement = stepElement.querySelector('.step-status');
                statusElement.className = \`step-status status-\${status}\`;
                statusElement.textContent = status.toUpperCase();
                
                // Update button states
                const buttons = stepElement.querySelectorAll('.btn');
                buttons.forEach(btn => {
                    btn.disabled = true; // Disable all by default
                });
                
                // Enable appropriate buttons based on status
                if (status === 'pending') {
                    stepElement.querySelector('.btn-approve').disabled = false;
                    stepElement.querySelector('.btn-reject').disabled = false;
                } else if (status === 'approved') {
                    stepElement.querySelector('.btn-execute').disabled = false;
                    stepElement.querySelector('.btn-reject').disabled = false;
                }
                
                // Always enable modify
                stepElement.querySelector('.btn-modify').disabled = false;
            }
        }

        function handleStepCompleted(stepId, result) {
            updateStepStatus(stepId, 'completed');
            console.log('Step completed:', stepId, result);
        }

        function handleStepFailed(stepId, error) {
            updateStepStatus(stepId, 'error');
            console.error('Step failed:', stepId, error);
        }
    </script>
</body>
</html>`;
    }
}

function getNonce() {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}