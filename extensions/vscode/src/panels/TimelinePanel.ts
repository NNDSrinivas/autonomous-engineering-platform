/**
 * Timeline Panel - Memory Graph visualization for VS Code
 * 
 * Displays related timeline and mini-graph for the active entity (JIRA issue, file, etc.)
 * Calls /api/memory/graph/node and /api/memory/timeline endpoints
 */

import * as vscode from 'vscode';

export class TimelinePanel {
    public static currentPanel: TimelinePanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private _disposables: vscode.Disposable[] = [];

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
        this._panel = panel;

        // Set webview content
        this._panel.webview.html = this._getWebviewContent(this._panel.webview, extensionUri);

        // Handle messages from webview
        this._panel.webview.onDidReceiveMessage(
            message => {
                switch (message.command) {
                    case 'openLink':
                        vscode.env.openExternal(vscode.Uri.parse(message.url));
                        break;
                    case 'openFile':
                        this._openFile(message.path);
                        break;
                }
            },
            null,
            this._disposables
        );

        // Clean up on dispose
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
    }

    public static createOrShow(extensionUri: vscode.Uri, entityId: string) {
        const column = vscode.ViewColumn.Beside;

        // If panel already exists, reveal it
        if (TimelinePanel.currentPanel) {
            TimelinePanel.currentPanel._panel.reveal(column);
            TimelinePanel.currentPanel.loadTimeline(entityId);
            return;
        }

        // Create new panel
        const panel = vscode.window.createWebviewPanel(
            'aepTimeline',
            'Timeline: ' + entityId,
            column,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media')]
            }
        );

        TimelinePanel.currentPanel = new TimelinePanel(panel, extensionUri);
        TimelinePanel.currentPanel.loadTimeline(entityId);
    }

    public async loadTimeline(entityId: string) {
        this._panel.title = 'Timeline: ' + entityId;

        try {
            // Get config for API endpoint
            const config = vscode.workspace.getConfiguration('aep');
            const apiUrl = config.get<string>('apiUrl', 'http://localhost:8000');
            const orgId = config.get<string>('orgId', 'default');

            // Fetch node neighborhood
            const nodeResponse = await fetch(`${apiUrl}/api/memory/graph/node/${entityId}`, {
                headers: {
                    'X-Org-Id': orgId
                }
            });

            if (!nodeResponse.ok) {
                throw new Error(`Node API returned ${nodeResponse.status}`);
            }

            const nodeData = await nodeResponse.json();

            // Fetch timeline (note: 'issue' param works for any entity type: JIRA issues, PRs, files, etc.)
            const timelineResponse = await fetch(`${apiUrl}/api/memory/timeline?issue=${entityId}&window=30d`, {
                headers: {
                    'X-Org-Id': orgId
                }
            });

            if (!timelineResponse.ok) {
                throw new Error(`Timeline API returned ${timelineResponse.status}`);
            }

            const timelineData = await timelineResponse.json();

            // Send data to webview
            this._panel.webview.postMessage({
                command: 'updateData',
                node: nodeData,
                timeline: timelineData
            });

        } catch (error) {
            vscode.window.showErrorMessage(`Failed to load timeline: ${error}`);
            this._panel.webview.postMessage({
                command: 'error',
                message: String(error)
            });
        }
    }

    private _openFile(path: string) {
        vscode.workspace.openTextDocument(path).then(doc => {
            vscode.window.showTextDocument(doc);
        }).catch(error => {
            vscode.window.showErrorMessage(`Failed to open file: ${error}`);
        });
    }

    public dispose() {
        TimelinePanel.currentPanel = undefined;

        this._panel.dispose();

        while (this._disposables.length) {
            const disposable = this._disposables.pop();
            if (disposable) {
                disposable.dispose();
            }
        }
    }

    private _getWebviewContent(webview: vscode.Webview, extensionUri: vscode.Uri): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Timeline</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            color: var(--vscode-foreground);
            background-color: var(--vscode-editor-background);
            padding: 20px;
            margin: 0;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: var(--vscode-descriptionForeground);
        }
        
        .error {
            color: var(--vscode-errorForeground);
            background: var(--vscode-inputValidation-errorBackground);
            border: 1px solid var(--vscode-inputValidation-errorBorder);
            padding: 10px;
            border-radius: 4px;
            margin-bottom: 20px;
        }
        
        .graph-container {
            border: 1px solid var(--vscode-panel-border);
            border-radius: 4px;
            padding: 20px;
            margin-bottom: 20px;
            background: var(--vscode-editor-background);
            min-height: 200px;
        }
        
        .timeline-container {
            margin-top: 20px;
        }
        
        .timeline-item {
            border-left: 2px solid var(--vscode-textLink-foreground);
            padding-left: 20px;
            margin-bottom: 20px;
            position: relative;
        }
        
        .timeline-item::before {
            content: '';
            position: absolute;
            left: -6px;
            top: 0;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--vscode-textLink-foreground);
        }
        
        .timeline-timestamp {
            color: var(--vscode-descriptionForeground);
            font-size: 0.9em;
            margin-bottom: 5px;
        }
        
        .timeline-title {
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .timeline-kind {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 0.85em;
            background: var(--vscode-badge-background);
            color: var(--vscode-badge-foreground);
            margin-right: 8px;
        }
        
        .timeline-links {
            margin-top: 10px;
        }
        
        .link-button {
            display: inline-block;
            padding: 4px 12px;
            margin-right: 8px;
            margin-top: 4px;
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            border-radius: 3px;
            cursor: pointer;
            text-decoration: none;
            font-size: 0.9em;
        }
        
        .link-button:hover {
            background: var(--vscode-button-hoverBackground);
        }
        
        .graph-node {
            display: inline-block;
            padding: 8px 12px;
            margin: 5px;
            border: 1px solid var(--vscode-panel-border);
            border-radius: 4px;
            background: var(--vscode-input-background);
        }
        
        .graph-edge {
            color: var(--vscode-descriptionForeground);
            font-size: 0.85em;
            margin: 5px 0;
        }
        
        h2 {
            border-bottom: 1px solid var(--vscode-panel-border);
            padding-bottom: 8px;
            margin-top: 0;
        }
    </style>
</head>
<body>
    <div id="content">
        <div class="loading">Loading timeline...</div>
    </div>
    
    <script>
        const vscode = acquireVsCodeApi();
        
        window.addEventListener('message', event => {
            const message = event.data;
            
            switch (message.command) {
                case 'updateData':
                    renderTimeline(message.node, message.timeline);
                    break;
                case 'error':
                    showError(message.message);
                    break;
            }
        });
        
        function showError(message) {
            document.getElementById('content').innerHTML = 
                '<div class="error">Error: ' + escapeHtml(message) + '</div>';
        }
        
        function renderTimeline(nodeData, timelineData) {
            let html = '';
            
            // Render mini-graph
            html += '<h2>Related Entities</h2>';
            html += '<div class="graph-container">';
            html += '<div class="graph-node"><strong>' + escapeHtml(nodeData.node.foreign_id) + '</strong> - ' + 
                    escapeHtml(nodeData.node.title || 'Untitled') + '</div>';
            html += '<div style="margin-top: 15px;"><strong>Connections:</strong></div>';
            
            if (nodeData.edges && nodeData.edges.length > 0) {
                nodeData.edges.forEach(edge => {
                    const neighbor = nodeData.neighbors.find(n => n.id === edge.dst_id || n.id === edge.src_id);
                    if (neighbor) {
                        html += '<div class="graph-edge">→ ' + escapeHtml(edge.relation) + ' → ' + 
                                escapeHtml(neighbor.foreign_id) + '</div>';
                    }
                });
            } else {
                html += '<div class="graph-edge">No connections found</div>';
            }
            
            html += '</div>';
            
            // Render timeline
            html += '<h2>Timeline</h2>';
            html += '<div class="timeline-container">';
            
            if (timelineData.timeline && timelineData.timeline.length > 0) {
                timelineData.timeline.forEach(item => {
                    const node = item.node;
                    const timestamp = new Date(item.timestamp).toLocaleString();
                    
                    html += '<div class="timeline-item">';
                    html += '<div class="timeline-timestamp">' + timestamp + '</div>';
                    html += '<span class="timeline-kind">' + escapeHtml(node.kind) + '</span>';
                    html += '<div class="timeline-title">' + escapeHtml(node.foreign_id) + ': ' + 
                            escapeHtml(node.title || 'Untitled') + '</div>';
                    
                    if (node.meta && node.meta.url) {
                        html += '<div class="timeline-links">';
                        html += '<button class="link-button" data-url="' + 
                                escapeAttribute(node.meta.url) + '">Open</button>';
                        html += '</div>';
                    }
                    
                    html += '</div>';
                });
            } else {
                html += '<div class="loading">No timeline events found</div>';
            }
            
            html += '</div>';
            
            document.getElementById('content').innerHTML = html;
            
            // Attach event listeners to buttons after DOM is updated
            document.querySelectorAll('.link-button').forEach(button => {
                button.addEventListener('click', function() {
                    const url = this.getAttribute('data-url');
                    if (url) {
                        openLink(url);
                    }
                });
            });
        }
        
        function openLink(url) {
            vscode.postMessage({
                command: 'openLink',
                url: url
            });
        }
        
        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Properly escape attribute values to prevent XSS in attribute context
        function escapeAttribute(text) {
            if (!text) return '';
            return String(text)
                .replace(/&/g, '&amp;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/`/g, '&#96;');
        }
    </script>
</body>
</html>`;
    }
}
