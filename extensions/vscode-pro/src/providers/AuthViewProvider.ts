import * as vscode from 'vscode';
import { AuthService } from '../services/AuthService';

export class AuthViewProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'aep.authView';
    private _view?: vscode.WebviewView;

    constructor(
        private readonly context: vscode.ExtensionContext,
        private readonly authService: AuthService
    ) { }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        token: vscode.CancellationToken
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this.context.extensionUri]
        };

        webviewView.webview.html = this.getWebviewContent();

        // Handle messages from webview
        webviewView.webview.onDidReceiveMessage(async (message) => {
            switch (message.type) {
                case 'signIn':
                    await this.handleSignIn();
                    break;
                case 'signOut':
                    await this.handleSignOut();
                    break;
                case 'refresh':
                    await this.refreshAuthStatus();
                    break;
            }
        });

        // Update auth status when webview becomes visible
        webviewView.onDidChangeVisibility(() => {
            if (webviewView.visible) {
                this.refreshAuthStatus();
            }
        });

        // Listen for auth state changes
        this.authService.onAuthStateChanged(() => {
            this.refreshAuthStatus();
        });

        // Initial load
        this.refreshAuthStatus();
    }

    private async handleSignIn(): Promise<void> {
        try {
            await this.authService.signIn();
            vscode.window.showInformationMessage('✅ Successfully signed in to AEP');
        } catch (error) {
            console.error('Sign in error:', error);
            vscode.window.showErrorMessage(`❌ Sign in failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }

    private async handleSignOut(): Promise<void> {
        try {
            await this.authService.signOut();
            vscode.window.showInformationMessage('👋 Signed out of AEP');
        } catch (error) {
            console.error('Sign out error:', error);
            vscode.window.showErrorMessage(`❌ Sign out failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }

    private async refreshAuthStatus(): Promise<void> {
        if (!this._view) { return; }

        try {
            const isAuthenticated = await this.authService.isAuthenticated();
            const userInfo = isAuthenticated ? this.authService.getUser() : null;

            this._view.webview.postMessage({
                type: 'updateAuth',
                authenticated: isAuthenticated,
                user: userInfo
            });
        } catch (error) {
            console.error('Error refreshing auth status:', error);
            this._view.webview.postMessage({
                type: 'error',
                message: error instanceof Error ? error.message : 'Failed to check authentication status'
            });
        }
    }

    private getWebviewContent(): string {
        return `
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Authentication</title>
            <style>
                body {
                    font-family: var(--vscode-font-family);
                    font-size: var(--vscode-font-size);
                    color: var(--vscode-foreground);
                    background-color: var(--vscode-editor-background);
                    margin: 0;
                    padding: 16px;
                }

                .auth-container {
                    text-align: center;
                    min-height: 100vh;
                    background: linear-gradient(135deg, var(--vscode-editor-background) 0%, var(--vscode-sideBar-background) 100%);
                }

                .auth-status {
                    padding: 32px 16px;
                    margin-bottom: 32px;
                }

                .auth-status h2 {
                    margin: 16px 0 8px 0;
                    font-size: 28px;
                    font-weight: 700;
                    background: linear-gradient(45deg, #007ACC, #00A2ED);
                    -webkit-background-clip: text;
                    background-clip: text;
                    color: transparent;
                }

                .tagline {
                    font-size: 14px;
                    color: var(--vscode-descriptionForeground);
                    font-weight: 500;
                    letter-spacing: 1px;
                    text-transform: uppercase;
                }

                .status-icon {
                    font-size: 48px;
                    margin-bottom: 16px;
                    animation: pulse 2s infinite;
                }

                @keyframes pulse {
                    0%, 100% { transform: scale(1); opacity: 1; }
                    50% { transform: scale(1.1); opacity: 0.8; }
                }

                .hero-section {
                    margin: 32px 0;
                    padding: 24px;
                }

                .hero-gradient {
                    font-size: 18px;
                    font-weight: 600;
                    background: linear-gradient(45deg, #007ACC, #00A2ED, #40E0D0);
                    -webkit-background-clip: text;
                    background-clip: text;
                    color: transparent;
                    line-height: 1.4;
                }

                .capability-grid {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 16px;
                    margin: 32px 0;
                    padding: 0 8px;
                }

                .capability-card {
                    padding: 20px 16px;
                    background: var(--vscode-sideBarSectionHeader-background);
                    border: 1px solid var(--vscode-panel-border);
                    border-radius: 8px;
                    text-align: center;
                    transition: all 0.3s ease;
                }

                .capability-card:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 12px rgba(0, 122, 204, 0.15);
                    border-color: var(--vscode-focusBorder);
                }

                .capability-icon {
                    font-size: 32px;
                    margin-bottom: 12px;
                }

                .capability-card h4 {
                    margin: 0 0 8px 0;
                    font-size: 14px;
                    font-weight: 600;
                    color: var(--vscode-foreground);
                }

                .capability-card p {
                    margin: 0;
                    font-size: 12px;
                    line-height: 1.4;
                    color: var(--vscode-descriptionForeground);
                }

                .connection-section {
                    margin-top: 40px;
                    padding: 24px 16px;
                }

                .user-info {
                    margin: 16px 0;
                    padding: 12px;
                    background: var(--vscode-textBlockQuote-background);
                    border-left: 3px solid var(--vscode-textBlockQuote-border);
                    border-radius: 2px;
                    text-align: left;
                }

                .user-info h4 {
                    margin: 0 0 8px 0;
                    color: var(--vscode-foreground);
                }

                .user-info p {
                    margin: 4px 0;
                    color: var(--vscode-descriptionForeground);
                    font-size: 13px;
                }

                .connect-btn {
                    border: none;
                    padding: 16px 32px;
                    border-radius: 8px;
                    cursor: pointer;
                    font-size: 14px;
                    font-weight: 600;
                    margin: 8px;
                    min-width: 200px;
                    transition: all 0.3s ease;
                    position: relative;
                    overflow: hidden;
                }

                .connect-btn.primary {
                    background: linear-gradient(45deg, #007ACC, #00A2ED);
                    color: white;
                    box-shadow: 0 4px 15px rgba(0, 122, 204, 0.4);
                }

                .connect-btn.primary:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 6px 20px rgba(0, 122, 204, 0.6);
                }

                .connect-btn.primary::before {
                    content: '';
                    position: absolute;
                    top: 0;
                    left: -100%;
                    width: 100%;
                    height: 100%;
                    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
                    transition: left 0.5s;
                }

                .connect-btn.primary:hover::before {
                    left: 100%;
                }

                .connect-btn.secondary {
                    background: var(--vscode-button-secondaryBackground);
                    color: var(--vscode-button-secondaryForeground);
                    border: 1px solid var(--vscode-panel-border);
                }

                .connect-btn.secondary:hover {
                    background: var(--vscode-button-secondaryHoverBackground);
                    border-color: var(--vscode-focusBorder);
                }

                .error-message {
                    color: var(--vscode-errorForeground);
                    background: var(--vscode-inputValidation-errorBackground);
                    border: 1px solid var(--vscode-inputValidation-errorBorder);
                    padding: 12px;
                    border-radius: 4px;
                    margin-bottom: 16px;
                }

                .loading {
                    color: var(--vscode-descriptionForeground);
                    font-style: italic;
                }

                .description {
                    color: var(--vscode-descriptionForeground);
                    font-size: 13px;
                    line-height: 1.4;
                    margin-bottom: 24px;
                }

                .features {
                    text-align: left;
                    margin: 24px 0;
                    padding: 16px;
                    background: var(--vscode-editor-background);
                    border: 1px solid var(--vscode-panel-border);
                    border-radius: 4px;
                }

                .features h4 {
                    margin: 0 0 12px 0;
                    color: var(--vscode-foreground);
                }

                .features ul {
                    margin: 0;
                    padding-left: 20px;
                }

                .features li {
                    margin: 8px 0;
                    color: var(--vscode-descriptionForeground);
                    font-size: 13px;
                }
            </style>
        </head>
        <body>
            <div class="auth-container">
                <div id="content">
                    <div class="loading">Loading authentication status...</div>
                </div>
            </div>

            <script>
                const vscode = acquireVsCodeApi();

                window.addEventListener('message', event => {
                    const message = event.data;
                    
                    switch (message.type) {
                        case 'updateAuth':
                            renderAuthStatus(message.authenticated, message.user);
                            break;
                        case 'error':
                            showError(message.message);
                            break;
                    }
                });

                function renderAuthStatus(authenticated, user) {
                    const content = document.getElementById('content');
                    
                    if (authenticated) {
                        let html = '<div class="auth-status authenticated">';
                        html += '<div class="status-icon">✅</div>';
                        html += '<h3>Connected to AEP</h3>';
                        html += '<p>You are successfully authenticated</p>';
                        html += '</div>';

                        if (user) {
                            html += '<div class="user-info">';
                            html += '<h4>Account Information</h4>';
                            if (user.name) html += '<p><strong>Name:</strong> ' + escapeHtml(user.name) + '</p>';
                            if (user.email) html += '<p><strong>Email:</strong> ' + escapeHtml(user.email) + '</p>';
                            if (user.picture) html += '<p><img src="' + escapeHtml(user.picture) + '" width="32" height="32" style="border-radius: 16px; vertical-align: middle; margin-right: 8px;">';
                            html += '</div>';
                        }

                        html += '<div class="features">';
                        html += '<h4>Available Features</h4>';
                        html += '<ul>';
                        html += '<li>🤖 AI-powered chat assistance</li>';
                        html += '<li>📋 Execution plan review & approval</li>';
                        html += '<li>🔄 Real-time workspace integration</li>';
                        html += '<li>📊 Advanced code analysis</li>';
                        html += '</ul>';
                        html += '</div>';

                        html += '<button class="auth-btn secondary-btn" onclick="signOut()">Sign Out</button>';
                        html += '<button class="auth-btn secondary-btn" onclick="refresh()">Refresh</button>';
                        
                        content.innerHTML = html;
                    } else {
                        let html = '<div class="auth-status not-authenticated">';
                        html += '<div class="status-icon">�</div>';
                        html += '<h2>Welcome to AEP</h2>';
                        html += '<p class="tagline">Autonomous Engineering Platform</p>';
                        html += '</div>';

                        html += '<div class="hero-section">';
                        html += '<div class="hero-gradient">Connect to unlock the future of autonomous software engineering</div>';
                        html += '</div>';

                        html += '<div class="capability-grid">';
                        html += '<div class="capability-card">';
                        html += '<div class="capability-icon">🧠</div>';
                        html += '<h4>AI Engineering Assistant</h4>';
                        html += '<p>Advanced code analysis, intelligent suggestions, and automated problem-solving</p>';
                        html += '</div>';
                        html += '<div class="capability-card">';
                        html += '<div class="capability-icon">⚡</div>';
                        html += '<h4>Autonomous Execution</h4>';
                        html += '<p>Step-by-step execution plans with approval workflows and change management</p>';
                        html += '</div>';
                        html += '<div class="capability-card">';
                        html += '<div class="capability-icon">🔄</div>';
                        html += '<h4>Workflow Intelligence</h4>';
                        html += '<p>Real-time workspace analysis, pattern recognition, and optimization recommendations</p>';
                        html += '</div>';
                        html += '<div class="capability-card">';
                        html += '<div class="capability-icon">🛡️</div>';
                        html += '<div class="capability-icon">🛡️</div>';
                        html += '<h4>Enterprise Security</h4>';
                        html += '<p>OAuth 2.0 authentication, encrypted communications, and audit logging</p>';
                        html += '</div>';
                        html += '</div>';

                        html += '<div class="connection-section">';
                        html += '<button class="connect-btn primary" onclick="signIn()">🚀 Connect to AEP Platform</button>';
                        html += '<button class="connect-btn secondary" onclick="refresh()">🔄 Check Connection Status</button>';
                        html += '</div>';
                        
                        content.innerHTML = html;
                    }
                }

                function showError(message) {
                    const content = document.getElementById('content');
                    content.innerHTML = '<div class="error-message">Error: ' + escapeHtml(message) + '</div>' +
                                     '<button class="auth-btn secondary-btn" onclick="refresh()">Retry</button>';
                }

                function signIn() {
                    vscode.postMessage({ type: 'signIn' });
                }

                function signOut() {
                    vscode.postMessage({ type: 'signOut' });
                }

                function refresh() {
                    vscode.postMessage({ type: 'refresh' });
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
}