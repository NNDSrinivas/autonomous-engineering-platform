import * as vscode from 'vscode';
import { ModernChatInterface } from './ModernChatInterface';

export class AgentHomeViewProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'aep.agentHomeView';

    private _view?: vscode.WebviewView;
    private _isAuthenticated: boolean = false;
    private _userProfile: any = null;

    constructor(private readonly _extensionUri: vscode.Uri) { }

    public updateAuthenticationState(isAuthenticated: boolean, userProfile: any = null) {
        console.log('AEP: updateAuthenticationState called', { isAuthenticated, userProfile });
        this._isAuthenticated = isAuthenticated;
        this._userProfile = userProfile;
        if (this._view) {
            this._view.webview.html = this.getHtmlContent(this._view.webview);
        }
    }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri]
        };

        webviewView.webview.html = this.getHtmlContent(webviewView.webview);

        webviewView.webview.onDidReceiveMessage(
            message => {
                console.log('AEP: Message received in webview:', message);
                switch (message.command) {
                    case 'signin':
                        // Directly trigger modern UI for demo purposes
                        this.forceModernUI();
                        vscode.window.showInformationMessage('✅ Signed in successfully! Welcome to AEP Professional.');
                        break;
                    case 'signout':
                        this.resetState();
                        vscode.window.showInformationMessage('👋 Signed out successfully.');
                        break;
                    case 'settings':
                        vscode.commands.executeCommand('workbench.action.openSettings', '@ext:aep.aep-professional');
                        break;
                    case 'sendMessage':
                        this.handleSendMessage(message.data.message);
                        break;
                    case 'newSession':
                        this.handleNewSession();
                        break;
                    case 'exportChat':
                        this.handleExportChat();
                        break;
                    case 'clearHistory':
                        this.handleClearHistory();
                        break;
                    case 'contextMenu':
                        this.handleContextMenu(message.data);
                        break;
                    case 'toggleContext':
                        console.log('AEP: Toggle context:', message.data);
                        break;
                    case 'modelChanged':
                        this.handleModelChanged(message.data.model);
                        break;
                    case 'openMCPSettings':
                        this.handleMCPSettings();
                        break;
                }
            },
            undefined,
            []
        );
    }

    private getHtmlContent(webview: vscode.Webview): string {
        console.log('AEP: getHtmlContent called, authenticated:', this._isAuthenticated);

        if (this._isAuthenticated) {
            return ModernChatInterface.getHTML(webview, this._userProfile);
        } else {
            return this.getUnauthenticatedContent();
        }
    }

    private getUnauthenticatedContent(): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AEP Professional</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: var(--vscode-font-family);
            color: var(--vscode-foreground);
            background-color: var(--vscode-sideBar-background);
            margin: 0;
            padding: 20px;
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .signin-container {
            text-align: center;
            max-width: 300px;
            padding: 30px;
            background: var(--vscode-editor-background);
            border-radius: 8px;
            border: 1px solid var(--vscode-panel-border);
        }
        .logo {
            width: 60px;
            height: 60px;
            background: linear-gradient(135deg, #007ACC, #005a9e);
            color: white;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            font-weight: bold;
            margin: 0 auto 20px;
        }
        .signin-title {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 8px;
        }
        .signin-subtitle {
            font-size: 13px;
            color: var(--vscode-descriptionForeground);
            margin-bottom: 24px;
            line-height: 1.4;
        }
        .btn {
            display: block;
            width: 100%;
            padding: 10px 16px;
            border: none;
            border-radius: 4px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            margin-bottom: 8px;
            transition: all 0.2s ease;
        }
        .btn-primary {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
        }
        .btn-secondary {
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
        }
    </style>
</head>
<body>
    <div class="signin-container">
        <div class="logo">A</div>
        <div class="signin-title">AEP Professional</div>
        <div class="signin-subtitle">Your AI engineering partner for autonomous development workflows. Sign in to access intelligent assistance.</div>
        <button class="btn btn-primary" data-command="signin">🔐 Sign In</button>
        <button class="btn btn-secondary" data-command="settings">⚙️ Settings</button>
    </div>
    <script>
        const vscode = acquireVsCodeApi();
        document.addEventListener('click', function(event) {
            const command = event.target.getAttribute('data-command');
            if (command) {
                event.preventDefault();
                vscode.postMessage({ command: command });
            }
        });
    </script>
</body>
</html>`;
    }

    private handleSendMessage(text: string) {
        console.log('AEP: Sending message:', text);
        // The UI will show thinking indicator automatically
        setTimeout(() => {
            const response = this.generateAIResponse(text);
            this.addMessageToChat('assistant', response.message, response.actions);
        }, 1500);
    }

    private handleNewSession() {
        console.log('AEP: Starting new session');
        if (this._view) {
            this._view.webview.postMessage({ command: 'clearMessages' });
        }
    }

    private handleExportChat() {
        console.log('AEP: Exporting chat');
        vscode.window.showInformationMessage('Chat export functionality will be implemented soon.');
    }

    private handleClearHistory() {
        console.log('AEP: Clearing history');
        if (this._view) {
            this._view.webview.postMessage({ command: 'clearMessages' });
        }
    }

    private handleContextMenu(data: any) {
        console.log('AEP: Context menu action:', data);
    }

    private handleModelChanged(model: string) {
        console.log('AEP: Model changed to:', model);
        vscode.window.showInformationMessage(`✅ Switched to ${model} model`);
        // Store the selected model in workspace configuration or global state
        // For now, just log it
    }

    private handleMCPSettings() {
        console.log('AEP: Opening MCP settings');
        vscode.window.showInformationMessage('🔧 MCP Server management will be available soon. This will allow you to configure Model Context Protocol servers for enhanced functionality.');
        // TODO: Implement MCP server configuration dialog
    }

    private addMessageToChat(sender: 'user' | 'assistant', message: string, actions?: any[]) {
        if (this._view) {
            this._view.webview.postMessage({
                command: 'addMessage',
                data: {
                    content: message,
                    time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                    actions: actions
                }
            });
        }
    }

    private showThinking(show: boolean) {
        if (this._view) {
            this._view.webview.postMessage({
                command: 'showThinking',
                data: { show }
            });
        }
    }

    private generateAIResponse(userMessage: string): { message: string; actions: any[] } {
        const lowerMessage = userMessage.toLowerCase();

        if (lowerMessage.includes('hello') || lowerMessage.includes('hi')) {
            return {
                message: "Hello! 👋 I'm your AEP Professional assistant. I'm here to help you with development tasks, code reviews, architecture decisions, and more. What would you like to work on today?",
                actions: [
                    { label: "Analyze Project", action: "analyzeProject" },
                    { label: "Code Review", action: "codeReview" },
                    { label: "Generate Tests", action: "generateTests" }
                ]
            };
        }

        if (lowerMessage.includes('test') || lowerMessage.includes('testing')) {
            return {
                message: "I can help you with testing! I can generate unit tests, integration tests, review existing test coverage, and suggest testing strategies for your project.",
                actions: [
                    { label: "Generate Unit Tests", action: "generateUnitTests" },
                    { label: "Check Coverage", action: "checkCoverage" },
                    { label: "Test Strategy", action: "testStrategy" }
                ]
            };
        }

        if (lowerMessage.includes('bug') || lowerMessage.includes('error') || lowerMessage.includes('debug')) {
            return {
                message: "Let me help you debug that issue. I can analyze error logs, review your code for potential bugs, and suggest debugging strategies.",
                actions: [
                    { label: "Analyze Logs", action: "analyzeLogs" },
                    { label: "Code Analysis", action: "codeAnalysis" },
                    { label: "Debug Tips", action: "debugTips" }
                ]
            };
        }

        if (lowerMessage.includes('code') || lowerMessage.includes('review')) {
            return {
                message: "I'd be happy to help with code review! I can check for best practices, performance issues, security concerns, and maintainability.",
                actions: [
                    { label: "Security Check", action: "securityCheck" },
                    { label: "Performance Review", action: "performanceReview" },
                    { label: "Best Practices", action: "bestPractices" }
                ]
            };
        }

        // Default response
        return {
            message: "I understand you'd like help with your development workflow. I can assist with code reviews, architecture decisions, debugging, testing, and more. Could you tell me more about what you're working on?",
            actions: [
                { label: "Project Analysis", action: "projectAnalysis" },
                { label: "Code Review", action: "codeReview" },
                { label: "Architecture Help", action: "architecture" }
            ]
        };
    }

    public forceModernUI() {
        console.log('AEP: Forcing modern UI display');
        this._isAuthenticated = true;
        this._userProfile = { name: 'User', email: 'user@example.com' };
        if (this._view) {
            this._view.webview.html = this.getHtmlContent(this._view.webview);
        }
    }

    public resetState() {
        console.log('AEP: Resetting extension state');
        this._isAuthenticated = false;
        this._userProfile = null;
        if (this._view) {
            this._view.webview.html = this.getHtmlContent(this._view.webview);
        }
    }
}
