"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.PlanViewProvider = void 0;
const vscode = __importStar(require("vscode"));
class PlanViewProvider {
    constructor(context, authService, apiClient) {
        this.context = context;
        this.authService = authService;
        this.apiClient = apiClient;
    }
    resolveWebviewView(webviewView, context, token) {
        this._view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this.context.extensionUri]
        };
        webviewView.webview.html = this.getWebviewContent();
        // Handle messages from webview
        webviewView.webview.onDidReceiveMessage(async (message) => {
            await this.handleMessage(message);
        });
        // Update plan when webview becomes visible
        webviewView.onDidChangeVisibility(() => {
            if (webviewView.visible) {
                this.refreshPlan();
            }
        });
        // Initial load
        this.refreshPlan();
    }
    async handleMessage(message) {
        try {
            switch (message.type) {
                case 'approveStep':
                    await this.apiClient.approveStep(message.stepId);
                    await this.refreshPlan();
                    vscode.window.showInformationMessage('Step approved successfully');
                    break;
                case 'rejectStep':
                    await this.apiClient.rejectStep(message.stepId, message.reason);
                    await this.refreshPlan();
                    vscode.window.showInformationMessage('Step rejected');
                    break;
                case 'refresh':
                    await this.refreshPlan();
                    break;
                case 'showFile':
                    if (message.filePath) {
                        const uri = vscode.Uri.file(message.filePath);
                        await vscode.window.showTextDocument(uri);
                    }
                    break;
                default:
                    console.warn('Unknown message type:', message.type);
            }
        }
        catch (error) {
            console.error('Error handling plan view message:', error);
            vscode.window.showErrorMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }
    async refreshPlan() {
        if (!this._view) {
            return;
        }
        try {
            const isAuthenticated = await this.authService.isAuthenticated();
            if (!isAuthenticated) {
                this._view.webview.postMessage({
                    type: 'authRequired'
                });
                return;
            }
            const plan = await this.apiClient.getCurrentPlan();
            this._view.webview.postMessage({
                type: 'updatePlan',
                plan: plan
            });
        }
        catch (error) {
            console.error('Error refreshing plan:', error);
            this._view.webview.postMessage({
                type: 'error',
                message: error instanceof Error ? error.message : 'Failed to load plan'
            });
        }
    }
    getWebviewContent() {
        return `
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Execution Plan</title>
            <style>
                body {
                    font-family: var(--vscode-font-family);
                    font-size: var(--vscode-font-size);
                    color: var(--vscode-foreground);
                    background-color: var(--vscode-editor-background);
                    margin: 0;
                    padding: 16px;
                }

                .header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 16px;
                    padding-bottom: 8px;
                    border-bottom: 1px solid var(--vscode-panel-border);
                }

                .refresh-btn {
                    background: var(--vscode-button-background);
                    color: var(--vscode-button-foreground);
                    border: none;
                    padding: 4px 8px;
                    border-radius: 2px;
                    cursor: pointer;
                    font-size: 12px;
                }

                .refresh-btn:hover {
                    background: var(--vscode-button-hoverBackground);
                }

                .plan-container {
                    margin-bottom: 16px;
                }

                .plan-title {
                    font-size: 16px;
                    font-weight: bold;
                    margin-bottom: 8px;
                }

                .plan-description {
                    color: var(--vscode-descriptionForeground);
                    margin-bottom: 16px;
                    font-size: 14px;
                }

                .step {
                    margin-bottom: 16px;
                    padding: 12px;
                    border: 1px solid var(--vscode-panel-border);
                    border-radius: 4px;
                    background: var(--vscode-editor-background);
                }

                .step-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 8px;
                }

                .step-title {
                    font-weight: bold;
                    font-size: 14px;
                }

                .step-status {
                    padding: 2px 6px;
                    border-radius: 2px;
                    font-size: 11px;
                    text-transform: uppercase;
                }

                .status-pending {
                    background: var(--vscode-notificationWarning);
                    color: var(--vscode-notificationWarningIcon-foreground);
                }

                .status-approved {
                    background: var(--vscode-notificationSuccess);
                    color: var(--vscode-notificationSuccessIcon-foreground);
                }

                .status-rejected {
                    background: var(--vscode-notificationError);
                    color: var(--vscode-notificationErrorIcon-foreground);
                }

                .status-executing {
                    background: var(--vscode-notificationInfo);
                    color: var(--vscode-notificationInfoIcon-foreground);
                }

                .status-completed {
                    background: var(--vscode-charts-green);
                    color: white;
                }

                .step-description {
                    color: var(--vscode-descriptionForeground);
                    margin-bottom: 12px;
                    font-size: 13px;
                    line-height: 1.4;
                }

                .step-actions {
                    display: flex;
                    gap: 8px;
                    margin-top: 8px;
                }

                .step-btn {
                    padding: 4px 8px;
                    border: none;
                    border-radius: 2px;
                    cursor: pointer;
                    font-size: 11px;
                    text-transform: uppercase;
                }

                .approve-btn {
                    background: var(--vscode-button-background);
                    color: var(--vscode-button-foreground);
                }

                .approve-btn:hover {
                    background: var(--vscode-button-hoverBackground);
                }

                .reject-btn {
                    background: var(--vscode-inputValidation-errorBackground);
                    color: var(--vscode-inputValidation-errorForeground);
                }

                .reject-btn:hover {
                    opacity: 0.8;
                }

                .file-list {
                    margin-top: 8px;
                    padding: 8px;
                    background: var(--vscode-textBlockQuote-background);
                    border-left: 3px solid var(--vscode-textBlockQuote-border);
                    border-radius: 2px;
                }

                .file-item {
                    color: var(--vscode-textLink-foreground);
                    cursor: pointer;
                    text-decoration: underline;
                    font-size: 12px;
                    margin: 2px 0;
                }

                .file-item:hover {
                    color: var(--vscode-textLink-activeForeground);
                }

                .empty-state {
                    text-align: center;
                    color: var(--vscode-descriptionForeground);
                    padding: 32px;
                }

                .auth-required {
                    text-align: center;
                    color: var(--vscode-descriptionForeground);
                    padding: 32px;
                }

                .error-state {
                    color: var(--vscode-errorForeground);
                    padding: 16px;
                    background: var(--vscode-inputValidation-errorBackground);
                    border: 1px solid var(--vscode-inputValidation-errorBorder);
                    border-radius: 4px;
                    margin-bottom: 16px;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h3>Execution Plan</h3>
                <button class="refresh-btn" onclick="refresh()">Refresh</button>
            </div>

            <div id="content">
                <div class="empty-state">
                    <p>Loading plan...</p>
                </div>
            </div>

            <script>
                const vscode = acquireVsCodeApi();

                window.addEventListener('message', event => {
                    const message = event.data;
                    
                    switch (message.type) {
                        case 'updatePlan':
                            renderPlan(message.plan);
                            break;
                        case 'authRequired':
                            showAuthRequired();
                            break;
                        case 'error':
                            showError(message.message);
                            break;
                    }
                });

                function renderPlan(plan) {
                    const content = document.getElementById('content');
                    
                    if (!plan || !plan.steps || plan.steps.length === 0) {
                        content.innerHTML = '<div class="empty-state"><p>No active plan</p></div>';
                        return;
                    }

                    let html = '<div class="plan-container">';
                    html += '<div class="plan-title">' + escapeHtml(plan.title || 'Execution Plan') + '</div>';
                    
                    if (plan.description) {
                        html += '<div class="plan-description">' + escapeHtml(plan.description) + '</div>';
                    }

                    plan.steps.forEach(step => {
                        html += '<div class="step">';
                        html += '<div class="step-header">';
                        html += '<div class="step-title">' + escapeHtml(step.title) + '</div>';
                        html += '<div class="step-status status-' + step.status + '">' + step.status + '</div>';
                        html += '</div>';
                        
                        if (step.description) {
                            html += '<div class="step-description">' + escapeHtml(step.description) + '</div>';
                        }

                        if (step.metadata?.files && step.metadata.files.length > 0) {
                            html += '<div class="file-list">';
                            html += '<strong>Files:</strong><br>';
                            step.metadata.files.forEach(file => {
                                html += '<div class="file-item" onclick="showFile(\'' + escapeHtml(file) + '\')">' + escapeHtml(file) + '</div>';
                            });
                            html += '</div>';
                        }

                        if (step.status === 'pending') {
                            html += '<div class="step-actions">';
                            html += '<button class="step-btn approve-btn" onclick="approveStep(\'' + step.id + '\')">Approve</button>';
                            html += '<button class="step-btn reject-btn" onclick="rejectStep(\'' + step.id + '\')">Reject</button>';
                            html += '</div>';
                        }

                        if (step.status === 'rejected' && step.metadata?.reason) {
                            html += '<div class="file-list" style="border-left-color: var(--vscode-inputValidation-errorBorder);">';
                            html += '<strong>Rejection Reason:</strong><br>' + escapeHtml(step.metadata.reason);
                            html += '</div>';
                        }

                        html += '</div>';
                    });

                    html += '</div>';
                    content.innerHTML = html;
                }

                function showAuthRequired() {
                    const content = document.getElementById('content');
                    content.innerHTML = '<div class="auth-required"><p>Please sign in to view execution plans</p></div>';
                }

                function showError(message) {
                    const content = document.getElementById('content');
                    content.innerHTML = '<div class="error-state">Error: ' + escapeHtml(message) + '</div>';
                }

                function approveStep(stepId) {
                    vscode.postMessage({
                        type: 'approveStep',
                        stepId: stepId
                    });
                }

                function rejectStep(stepId) {
                    const reason = prompt('Reason for rejection (optional):');
                    vscode.postMessage({
                        type: 'rejectStep',
                        stepId: stepId,
                        reason: reason
                    });
                }

                function showFile(filePath) {
                    vscode.postMessage({
                        type: 'showFile',
                        filePath: filePath
                    });
                }

                function refresh() {
                    vscode.postMessage({
                        type: 'refresh'
                    });
                }

                function escapeHtml(text) {
                    const div = document.createElement('div');
                    div.textContent = text;
                    return div.innerHTML;
                }

                // Initial load
                refresh();
            </script>
        </body>
        </html>`;
    }
    refresh() {
        this.refreshPlan();
    }
    async approveCurrentStep() {
        // This would need to be enhanced to track which step is "current"
        // For now, we'll just trigger a refresh to show available actions
        await this.refreshPlan();
        vscode.window.showInformationMessage('Use the approve buttons in the Plan view to approve individual steps');
    }
    async rejectCurrentStep() {
        // This would need to be enhanced to track which step is "current"
        // For now, we'll just trigger a refresh to show available actions
        await this.refreshPlan();
        vscode.window.showInformationMessage('Use the reject buttons in the Plan view to reject individual steps');
    }
}
exports.PlanViewProvider = PlanViewProvider;
PlanViewProvider.viewType = 'aep.planView';
//# sourceMappingURL=PlanViewProvider-old.js.map