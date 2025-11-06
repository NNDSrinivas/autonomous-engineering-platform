import * as vscode from 'vscode';
import { AEPApiClient, MorningBriefData, JiraTask } from '../api/AEPApiClient';

/**
 * Agent Panel - Main AEP interface showing morning brief and task selection
 * 
 * This is the primary user interface that provides:
 * - Morning briefing with context
 * - Jira task selection
 * - Team activity overview
 * - Quick action buttons
 * - Enterprise intelligence summary
 */

export class AgentPanel {
    public static currentPanel: AgentPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];
    private _apiClient: AEPApiClient;
    private _morningBriefData: MorningBriefData | undefined;

    public static createOrShow(extensionUri: vscode.Uri, apiClient: AEPApiClient) {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;

        // If we already have a panel, show it
        if (AgentPanel.currentPanel) {
            AgentPanel.currentPanel._panel.reveal(column);
            return AgentPanel.currentPanel;
        }

        // Otherwise, create a new panel
        const panel = vscode.window.createWebviewPanel(
            'aep.agent',
            'AEP Agent',
            column || vscode.ViewColumn.One,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [
                    vscode.Uri.joinPath(extensionUri, 'media'),
                    vscode.Uri.joinPath(extensionUri, 'out')
                ]
            }
        );

        AgentPanel.currentPanel = new AgentPanel(panel, extensionUri, apiClient);
        return AgentPanel.currentPanel;
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
                    case 'loadMorningBrief':
                        await this.loadMorningBrief();
                        break;
                    case 'selectJiraTask':
                        await this.selectJiraTask(message.taskKey);
                        break;
                    case 'openChat':
                        vscode.commands.executeCommand('aep.openChat');
                        break;
                    case 'planAndAct':
                        vscode.commands.executeCommand('aep.planAndAct');
                        break;
                    case 'refreshData':
                        await this.refreshData();
                        break;
                    case 'viewTeamActivity':
                        await this.viewTeamActivity();
                        break;
                }
            },
            null,
            this._disposables
        );
    }

    /**
     * Show morning brief immediately
     */
    async showMorningBrief() {
        this._panel.reveal();
        await this.loadMorningBrief();
    }

    /**
     * Focus on tasks section
     */
    focusOnTasks() {
        this._panel.reveal();
        this._panel.webview.postMessage({ type: 'focusOnTasks' });
    }

    /**
     * Dispose panel resources
     */
    public dispose() {
        AgentPanel.currentPanel = undefined;

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
     * Load morning brief data from API
     */
    private async loadMorningBrief() {
        try {
            this._panel.webview.postMessage({ type: 'showLoading', message: 'Loading your morning brief...' });
            
            this._morningBriefData = await this._apiClient.getMorningBrief();
            
            this._panel.webview.postMessage({ 
                type: 'morningBriefLoaded', 
                data: this._morningBriefData 
            });
        } catch (error) {
            this._panel.webview.postMessage({ 
                type: 'showError', 
                message: `Failed to load morning brief: ${error instanceof Error ? error.message : 'Unknown error'}` 
            });
        }
    }

    /**
     * Handle Jira task selection
     */
    private async selectJiraTask(taskKey: string) {
        try {
            // Get detailed context for the task
            const taskContext = await this._apiClient.getJiraTaskContext(taskKey);
            
            // Show task selection confirmation
            const result = await vscode.window.showInformationMessage(
                `Selected ${taskKey}: ${taskContext.task.summary}`,
                'Start Planning',
                'View Details',
                'Open Chat'
            );

            switch (result) {
                case 'Start Planning':
                    vscode.commands.executeCommand('aep.planAndAct');
                    // Pass task context to plan panel
                    this._panel.webview.postMessage({
                        type: 'taskSelected',
                        task: taskContext.task,
                        context: taskContext
                    });
                    break;
                case 'View Details':
                    // Show task details in panel
                    this._panel.webview.postMessage({
                        type: 'showTaskDetails',
                        task: taskContext.task,
                        context: taskContext
                    });
                    break;
                case 'Open Chat':
                    vscode.commands.executeCommand('aep.openChat');
                    break;
            }
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to load task details: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }

    /**
     * Refresh all data
     */
    private async refreshData() {
        await this.loadMorningBrief();
    }

    /**
     * View team activity
     */
    private async viewTeamActivity() {
        try {
            const activity = await this._apiClient.getTeamActivity();
            this._panel.webview.postMessage({
                type: 'teamActivityLoaded',
                data: activity
            });
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to load team activity: ${error instanceof Error ? error.message : 'Unknown error'}`);
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
        // Get nonce for security
        const nonce = getNonce();

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
    <title>AEP Agent</title>
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
        
        .greeting {
            font-size: 1.5em;
            font-weight: bold;
            color: var(--vscode-textLink-foreground);
        }
        
        .refresh-btn {
            background-color: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9em;
        }
        
        .refresh-btn:hover {
            background-color: var(--vscode-button-hoverBackground);
        }
        
        .section {
            margin-bottom: 30px;
            padding: 15px;
            background-color: var(--vscode-editor-inactiveSelectionBackground);
            border-radius: 8px;
            border-left: 4px solid var(--vscode-textLink-foreground);
        }
        
        .section-title {
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .task-item {
            background-color: var(--vscode-list-inactiveSelectionBackground);
            padding: 12px;
            margin-bottom: 8px;
            border-radius: 6px;
            cursor: pointer;
            border: 1px solid transparent;
            transition: all 0.2s ease;
        }
        
        .task-item:hover {
            background-color: var(--vscode-list-hoverBackground);
            border-color: var(--vscode-textLink-foreground);
        }
        
        .task-key {
            font-weight: bold;
            color: var(--vscode-textLink-foreground);
        }
        
        .task-summary {
            margin: 4px 0;
            font-size: 0.95em;
        }
        
        .task-meta {
            font-size: 0.8em;
            color: var(--vscode-descriptionForeground);
            display: flex;
            gap: 16px;
        }
        
        .priority-high { color: #ff6b6b; }
        .priority-medium { color: #ffa726; }
        .priority-low { color: #66bb6a; }
        
        .activity-item {
            padding: 8px 12px;
            margin-bottom: 6px;
            background-color: var(--vscode-list-inactiveSelectionBackground);
            border-radius: 4px;
            font-size: 0.9em;
        }
        
        .activity-author {
            font-weight: bold;
            color: var(--vscode-textLink-foreground);
        }
        
        .activity-time {
            color: var(--vscode-descriptionForeground);
            font-size: 0.8em;
        }
        
        .suggestions {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
        }
        
        .suggestion-item {
            padding: 12px;
            background-color: var(--vscode-list-inactiveSelectionBackground);
            border-radius: 6px;
            cursor: pointer;
            border: 1px solid transparent;
            transition: all 0.2s ease;
        }
        
        .suggestion-item:hover {
            border-color: var(--vscode-textLink-foreground);
        }
        
        .suggestion-title {
            font-weight: bold;
            margin-bottom: 4px;
        }
        
        .suggestion-desc {
            font-size: 0.85em;
            color: var(--vscode-descriptionForeground);
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
        
        .quick-actions {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        
        .quick-action-btn {
            background-color: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9em;
        }
        
        .quick-action-btn:hover {
            background-color: var(--vscode-button-secondaryHoverBackground);
        }
        
        .empty-state {
            text-align: center;
            padding: 40px;
            color: var(--vscode-descriptionForeground);
        }

        .icon {
            margin-right: 8px;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="greeting">🤖 AEP Agent</div>
        <button class="refresh-btn" onclick="refreshData()">↻ Refresh</button>
    </div>

    <div id="content">
        <div class="loading">
            <div>Loading your morning brief...</div>
            <div style="margin-top: 10px;">
                <button class="refresh-btn" onclick="loadMorningBrief()">Load Morning Brief</button>
            </div>
        </div>
    </div>

    <script nonce="${nonce}">
        const vscode = acquireVsCodeApi();

        // Message handlers
        window.addEventListener('message', event => {
            const message = event.data;
            
            switch (message.type) {
                case 'morningBriefLoaded':
                    showMorningBrief(message.data);
                    break;
                case 'showLoading':
                    showLoading(message.message);
                    break;
                case 'showError':
                    showError(message.message);
                    break;
                case 'teamActivityLoaded':
                    updateTeamActivity(message.data);
                    break;
                case 'focusOnTasks':
                    focusOnTasks();
                    break;
            }
        });

        function loadMorningBrief() {
            vscode.postMessage({ type: 'loadMorningBrief' });
        }

        function refreshData() {
            vscode.postMessage({ type: 'refreshData' });
        }

        function selectTask(taskKey) {
            vscode.postMessage({ type: 'selectJiraTask', taskKey });
        }

        function openChat() {
            vscode.postMessage({ type: 'openChat' });
        }

        function planAndAct() {
            vscode.postMessage({ type: 'planAndAct' });
        }

        function viewTeamActivity() {
            vscode.postMessage({ type: 'viewTeamActivity' });
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
                    <div style="margin-top: 10px;">
                        <button class="refresh-btn" onclick="refreshData()">Try Again</button>
                    </div>
                </div>
            \`;
        }

        function showMorningBrief(data) {
            const tasksHtml = data.jiraTasks?.length ? 
                data.jiraTasks.map(task => \`
                    <div class="task-item" onclick="selectTask('\${task.key}')">
                        <div class="task-key">\${task.key}</div>
                        <div class="task-summary">\${task.summary}</div>
                        <div class="task-meta">
                            <span class="priority-\${task.priority.toLowerCase()}">\${task.priority}</span>
                            <span>\${task.status}</span>
                        </div>
                    </div>
                \`).join('') :
                '<div class="empty-state">No tasks assigned</div>';

            const activityHtml = data.recentActivity?.length ?
                data.recentActivity.slice(0, 5).map(item => \`
                    <div class="activity-item">
                        <span class="activity-author">\${item.author}</span>
                        \${item.title}
                        <div class="activity-time">\${formatTime(item.timestamp)}</div>
                    </div>
                \`).join('') :
                '<div class="empty-state">No recent activity</div>';

            const suggestionsHtml = data.suggestions?.length ?
                \`<div class="suggestions">
                    \${data.suggestions.map(suggestion => \`
                        <div class="suggestion-item" onclick="handleSuggestion('\${suggestion.id}')">
                            <div class="suggestion-title">\${suggestion.title}</div>
                            <div class="suggestion-desc">\${suggestion.description}</div>
                        </div>
                    \`).join('')}
                </div>\` :
                '<div class="empty-state">No suggestions available</div>';

            document.getElementById('content').innerHTML = \`
                <div class="section">
                    <div class="section-title">
                        <span class="icon">☀️</span>
                        Morning Brief
                    </div>
                    <div>\${data.greeting}</div>
                    <div class="quick-actions">
                        <button class="quick-action-btn" onclick="openChat()">💬 Open Chat</button>
                        <button class="quick-action-btn" onclick="planAndAct()">⚡ Plan & Act</button>
                        <button class="quick-action-btn" onclick="viewTeamActivity()">👥 Team Activity</button>
                    </div>
                </div>

                <div class="section" id="tasks-section">
                    <div class="section-title">
                        <span class="icon">📋</span>
                        Your Jira Tasks (\${data.jiraTasks?.length || 0})
                    </div>
                    \${tasksHtml}
                </div>

                <div class="section">
                    <div class="section-title">
                        <span class="icon">🔄</span>
                        Recent Activity
                    </div>
                    \${activityHtml}
                </div>

                <div class="section">
                    <div class="section-title">
                        <span class="icon">💡</span>
                        Smart Suggestions
                    </div>
                    \${suggestionsHtml}
                </div>
            \`;
        }

        function formatTime(timestamp) {
            const date = new Date(timestamp);
            const now = new Date();
            const diff = now.getTime() - date.getTime();
            const hours = Math.floor(diff / (1000 * 60 * 60));
            
            if (hours < 1) return 'Just now';
            if (hours < 24) return \`\${hours}h ago\`;
            return date.toLocaleDateString();
        }

        function focusOnTasks() {
            const tasksSection = document.getElementById('tasks-section');
            if (tasksSection) {
                tasksSection.scrollIntoView({ behavior: 'smooth' });
                tasksSection.style.backgroundColor = 'var(--vscode-list-focusBackground)';
                setTimeout(() => {
                    tasksSection.style.backgroundColor = 'var(--vscode-editor-inactiveSelectionBackground)';
                }, 2000);
            }
        }

        function handleSuggestion(suggestionId) {
            // Handle suggestion clicks
            console.log('Suggestion clicked:', suggestionId);
        }

        // Auto-load morning brief on startup
        loadMorningBrief();
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