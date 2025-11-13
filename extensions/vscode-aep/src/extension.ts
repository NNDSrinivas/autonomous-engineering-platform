import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

export function activate(context: vscode.ExtensionContext) {
    const provider = new AEPViewProvider(context.extensionUri);

    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(
            'aepChat', 
            provider,
            {
                webviewOptions: {
                    retainContextWhenHidden: true
                }
            }
        )
    );
}

class AEPViewProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'aepChat';
    private _view?: vscode.WebviewView;

    constructor(private readonly _extensionUri: vscode.Uri) {}

    resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext<unknown>,
        token: vscode.CancellationToken
    ): void | Thenable<void> {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [
                this._extensionUri
            ]
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        webviewView.webview.onDidReceiveMessage(message => {
            switch (message.type) {
                case 'alert':
                    vscode.window.showInformationMessage(message.text);
                    return;
                case 'error':
                    vscode.window.showErrorMessage(message.text);
                    return;
                case 'sendMessage':
                    this._handleSendMessage(message.text);
                    return;
                case 'resetConversation':
                    this._handleResetConversation();
                    return;
                case 'newChat':
                    this._handleNewChat();
                    return;
                case 'focusMode':
                    this._handleFocusMode(message.enabled);
                    return;
                case 'openIntegrations':
                    this._handleOpenIntegrations();
                    return;
                case 'connectApiKey':
                    this._handleConnectApiKey();
                    return;
            }
        });
    }

    private _handleSendMessage(text: string) {
        // Simulate AI response for now
        setTimeout(() => {
            this._view?.webview.postMessage({
                type: 'response',
                text: `I received your message: "${text}". This is a simulated response from the AEP AI assistant.`
            });
        }, 1000);
    }

    private _handleResetConversation() {
        this._view?.webview.postMessage({
            type: 'clearChat'
        });
    }

    private _handleNewChat() {
        this._view?.webview.postMessage({
            type: 'clearChat'
        });
    }

    private _handleFocusMode(enabled: boolean) {
        vscode.window.showInformationMessage(`Focus mode ${enabled ? 'enabled' : 'disabled'}`);
    }

    private _handleOpenIntegrations() {
        vscode.window.showInformationMessage('Opening integrations panel...');
    }

    private _handleConnectApiKey() {
        vscode.window.showInformationMessage('Opening API key configuration...');
    }

    private _getHtmlForWebview(webview: vscode.Webview): string {
        const cssUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'panel.css'));
        const jsUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'panel.js'));

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="${cssUri}" rel="stylesheet">
    <title>AEP Chat</title>
</head>
<body>
    <div class="container">
        <!-- Header Section -->
        <div class="header">
            <div class="header-top">
                <div class="branding">
                    <svg class="navi-icon" width="20" height="20" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <!-- NAVI Fox Icon -->
                        <circle cx="100" cy="100" r="98" fill="#FF6B35" stroke="#E55A2B" stroke-width="4"/>
                        <circle cx="100" cy="100" r="85" fill="url(#foxGradient)"/>
                        <defs>
                            <radialGradient id="foxGradient" cx="0.3" cy="0.3">
                                <stop offset="0%" stop-color="#FFE5CC"/>
                                <stop offset="100%" stop-color="#FF8A50"/>
                            </radialGradient>
                        </defs>
                        <!-- Fox ears -->
                        <path d="M70 60 Q75 45 85 55 Q90 50 95 65 L90 75 Q85 70 80 72 Q75 70 70 75 Z" fill="#FF6B35"/>
                        <path d="M105 65 Q110 50 115 55 Q125 45 130 60 L125 75 Q120 70 115 72 Q110 70 105 75 Z" fill="#FF6B35"/>
                        <!-- Fox face -->
                        <ellipse cx="100" cy="110" rx="35" ry="25" fill="#FFE5CC"/>
                        <!-- Fox eyes -->
                        <circle cx="88" cy="105" r="6" fill="#2C3E50"/>
                        <circle cx="112" cy="105" r="6" fill="#2C3E50"/>
                        <circle cx="90" cy="103" r="2" fill="white"/>
                        <circle cx="114" cy="103" r="2" fill="white"/>
                        <!-- Fox nose and mouth -->
                        <path d="M98 115 Q100 113 102 115 Q100 117 98 115 Z" fill="#2C3E50"/>
                        <path d="M100 117 Q95 122 90 120 M100 117 Q105 122 110 120" stroke="#2C3E50" stroke-width="2" fill="none"/>
                    </svg>
                    <span class="title">AEP Assistant</span>
                </div>
                <div class="header-actions">
                    <button class="icon-btn" id="resetBtn" title="New Chat">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                            <path d="M12 5V2L8 6L12 10V7C15.31 7 18 9.69 18 13S15.31 19 12 19S6 16.31 6 13H4C4 17.42 7.58 21 12 21S20 17.42 20 13S16.42 5 12 5Z" fill="currentColor"/>
                        </svg>
                    </button>
                    <button class="icon-btn" id="focusBtn" title="Focus Mode">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                            <circle cx="12" cy="12" r="3" fill="currentColor"/>
                            <path d="M19.4 15C18.8 15.8 18.1 16.5 17.3 17.1L18.7 18.5L17.3 19.9L15.9 18.5C15.1 18.9 14.3 19.2 13.4 19.4V21H10.6V19.4C9.7 19.2 8.9 18.9 8.1 18.5L6.7 19.9L5.3 18.5L6.7 17.1C6.1 16.3 5.8 15.5 5.6 14.6H4V11.8H5.6C5.8 10.9 6.1 10.1 6.7 9.3L5.3 7.9L6.7 6.5L8.1 7.9C8.9 7.5 9.7 7.2 10.6 7V5.4H13.4V7C14.3 7.2 15.1 7.5 15.9 7.9L17.3 6.5L18.7 7.9L17.3 9.3C17.9 10.1 18.2 10.9 18.4 11.8H20V14.6H18.4C18.2 14.9 18.1 15.2 19.4 15Z" fill="currentColor"/>
                        </svg>
                    </button>
                    <button class="icon-btn" id="integrationsBtn" title="Integrations">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                            <path d="M12 2L13.09 8.26L20 9L13.09 9.74L12 16L10.91 9.74L4 9L10.91 8.26L12 2Z" fill="currentColor"/>
                            <path d="M19 15L20.09 18.26L24 19L20.09 19.74L19 23L17.91 19.74L14 19L17.91 18.26L19 15Z" fill="currentColor"/>
                            <path d="M5 15L6.09 18.26L10 19L6.09 19.74L5 23L3.91 19.74L0 19L3.91 18.26L5 15Z" fill="currentColor"/>
                        </svg>
                    </button>
                    <button class="icon-btn" id="apiKeyBtn" title="Connect API Key">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                            <path d="M7 14C5.9 14 5 13.1 5 12S5.9 10 7 10 9 10.9 9 12 8.1 14 7 14M12.6 10C11.8 7.7 9.6 6 7 6C3.7 6 1 8.7 1 12S3.7 18 7 18C9.6 18 11.8 16.3 12.6 14H16V18H20V14H23V10H12.6Z" fill="currentColor"/>
                        </svg>
                    </button>
                </div>
            </div>
            
            <div class="header-controls">
                <div class="select-group">
                    <div class="select-pill">
                        <select id="modelSelect">
                            <option value="gpt-4">GPT-4</option>
                            <option value="gpt-3.5">GPT-3.5 Turbo</option>
                            <option value="claude">Claude 3</option>
                            <option value="byok">BYOK</option>
                        </select>
                        <svg class="select-arrow" width="12" height="12" viewBox="0 0 24 24">
                            <path d="M7 10L12 15L17 10H7Z" fill="currentColor"/>
                        </svg>
                    </div>
                    
                    <div class="select-pill">
                        <select id="modeSelect">
                            <option value="chat">Chat</option>
                            <option value="plan">Plan</option>
                            <option value="code">Code</option>
                            <option value="review">Review</option>
                        </select>
                        <svg class="select-arrow" width="12" height="12" viewBox="0 0 24 24">
                            <path d="M7 10L12 15L17 10H7Z" fill="currentColor"/>
                        </svg>
                    </div>
                </div>
                
                <div class="attachments-menu">
                    <button class="attach-btn" id="attachBtn">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                            <path d="M16.5 6V17.5C16.5 19.43 14.93 21 13 21S9.5 19.43 9.5 17.5V5C9.5 3.62 10.62 2.5 12 2.5S14.5 3.62 14.5 5V15.5C14.5 16.05 14.05 16.5 13.5 16.5S12.5 16.05 12.5 15.5V6H11V15.5C11 16.88 12.12 18 13.5 18S16 16.88 16 15.5V5C16 2.79 14.21 1 12 1S8 2.79 8 5V17.5C8 20.26 10.24 22.5 13 22.5S18 20.26 18 17.5V6H16.5Z" fill="currentColor"/>
                        </svg>
                        <span>Attach</span>
                    </button>
                    <div class="attach-dropdown" id="attachDropdown">
                        <div class="attach-option" data-type="file">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                                <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z" fill="currentColor"/>
                            </svg>
                            <span>Upload File</span>
                        </div>
                        <div class="attach-option" data-type="code">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                                <path d="M8,3A2,2 0 0,0 6,5V9A2,2 0 0,1 4,11H3V13H4A2,2 0 0,1 6,15V19A2,2 0 0,0 8,21H10V19H8V14A2,2 0 0,0 6,12A2,2 0 0,0 8,10V5H10V3M16,3A2,2 0 0,1 18,5V9A2,2 0 0,0 20,11H21V13H20A2,2 0 0,0 18,15V19A2,2 0 0,1 16,21H14V19H16V14A2,2 0 0,1 18,12A2,2 0 0,1 16,10V5H14V3H16Z" fill="currentColor"/>
                            </svg>
                            <span>Code Selection</span>
                        </div>
                        <div class="attach-option" data-type="context">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                                <path d="M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M11,14H13V16H11V14M11,8H13V12H11V8Z" fill="currentColor"/>
                            </svg>
                            <span>Project Context</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Chat Area -->
        <div class="chat-area" id="chatArea">
            <div class="welcome-message">
                <div class="navi-avatar">
                    <svg width="32" height="32" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <circle cx="100" cy="100" r="98" fill="#FF6B35" stroke="#E55A2B" stroke-width="4"/>
                        <circle cx="100" cy="100" r="85" fill="url(#foxGradient2)"/>
                        <defs>
                            <radialGradient id="foxGradient2" cx="0.3" cy="0.3">
                                <stop offset="0%" stop-color="#FFE5CC"/>
                                <stop offset="100%" stop-color="#FF8A50"/>
                            </radialGradient>
                        </defs>
                        <path d="M70 60 Q75 45 85 55 Q90 50 95 65 L90 75 Q85 70 80 72 Q75 70 70 75 Z" fill="#FF6B35"/>
                        <path d="M105 65 Q110 50 115 55 Q125 45 130 60 L125 75 Q120 70 115 72 Q110 70 105 75 Z" fill="#FF6B35"/>
                        <ellipse cx="100" cy="110" rx="35" ry="25" fill="#FFE5CC"/>
                        <circle cx="88" cy="105" r="6" fill="#2C3E50"/>
                        <circle cx="112" cy="105" r="6" fill="#2C3E50"/>
                        <circle cx="90" cy="103" r="2" fill="white"/>
                        <circle cx="114" cy="103" r="2" fill="white"/>
                        <path d="M98 115 Q100 113 102 115 Q100 117 98 115 Z" fill="#2C3E50"/>
                        <path d="M100 117 Q95 122 90 120 M100 117 Q105 122 110 120" stroke="#2C3E50" stroke-width="2" fill="none"/>
                    </svg>
                </div>
                <p class="welcome-text">Hello! I'm NAVI, your autonomous engineering assistant. How can I help you today?</p>
            </div>
        </div>

        <!-- Input Area -->
        <div class="input-area">
            <div class="input-container">
                <textarea 
                    id="messageInput" 
                    placeholder="Ask NAVI anything about your code..."
                    rows="1"
                    maxlength="10000">
                </textarea>
                <button id="sendBtn" class="send-btn" disabled>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                        <path d="M2,21L23,12L2,3V10L17,12L2,14V21Z" fill="currentColor"/>
                    </svg>
                </button>
            </div>
        </div>
    </div>

    <script src="${jsUri}"></script>
</body>
</html>`;
    }
}

export function deactivate() {}
