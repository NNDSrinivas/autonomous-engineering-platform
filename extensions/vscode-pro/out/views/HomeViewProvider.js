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
exports.HomeViewProvider = void 0;
const vscode = __importStar(require("vscode"));
class HomeViewProvider {
    constructor(ctx, auth, api) {
        this.ctx = ctx;
        this.auth = auth;
        this.api = api;
    }
    resolveWebviewView(webviewView, context, token) {
        this._view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [
                vscode.Uri.joinPath(this.ctx.extensionUri, 'media')
            ]
        };
        webviewView.webview.html = this.getHtmlContent(webviewView.webview);
        // Set up message handling
        webviewView.webview.onDidReceiveMessage(async (message) => {
            try {
                console.log('AEP: Received message:', message);
                switch (message.type) {
                    case 'ready': {
                        const signedIn = await this.auth.isSignedIn();
                        const model = this.getCurrentModel();
                        webviewView.webview.postMessage({
                            type: 'state',
                            payload: { signedIn, model }
                        });
                        break;
                    }
                    case 'signin': {
                        await this.auth.signIn();
                        const signedIn = await this.auth.isSignedIn();
                        const model = this.getCurrentModel();
                        webviewView.webview.postMessage({
                            type: 'state',
                            payload: { signedIn, model }
                        });
                        break;
                    }
                    case 'signout': {
                        await this.auth.signOut();
                        webviewView.webview.postMessage({
                            type: 'state',
                            payload: { signedIn: false, model: this.getCurrentModel() }
                        });
                        break;
                    }
                    case 'chat:send': {
                        const token = await this.auth.getAccessToken();
                        if (!token) {
                            webviewView.webview.postMessage({
                                type: 'chat:error',
                                error: 'Not signed in. Please sign in first.'
                            });
                            return;
                        }
                        const model = this.getCurrentModel();
                        console.log(`AEP: Sending chat message with model ${model}`);
                        try {
                            const response = await this.api.chat(message.text, model, token);
                            webviewView.webview.postMessage({
                                type: 'chat:reply',
                                text: response?.text || 'No response from the AI assistant.'
                            });
                        }
                        catch (error) {
                            console.error('AEP: Chat API Error:', error);
                            webviewView.webview.postMessage({
                                type: 'chat:error',
                                error: error?.message || 'Failed to get AI response'
                            });
                        }
                        break;
                    }
                    case 'model:select': {
                        await vscode.commands.executeCommand('aep.model.select');
                        const signedIn = await this.auth.isSignedIn();
                        const model = this.getCurrentModel();
                        webviewView.webview.postMessage({
                            type: 'state',
                            payload: { signedIn, model }
                        });
                        break;
                    }
                    case 'settings': {
                        vscode.commands.executeCommand('aep.openSettings');
                        break;
                    }
                    case 'action': {
                        await this.handleAction(message.action);
                        break;
                    }
                    default:
                        console.log(`AEP: Unknown message type: ${message.type}`);
                }
            }
            catch (error) {
                console.error('AEP: Error handling message:', error);
                webviewView.webview.postMessage({
                    type: 'error',
                    error: error?.message || String(error)
                });
            }
        });
    }
    getCurrentModel() {
        const cfg = vscode.workspace.getConfiguration('aep');
        return cfg.get('model.current') || 'gpt-4o';
    }
    async handleAction(action) {
        const editor = vscode.window.activeTextEditor;
        switch (action) {
            case 'review':
                if (editor) {
                    const text = editor.document.getText();
                    if (this._view) {
                        this._view.webview.postMessage({
                            type: 'chat:prefill',
                            text: `Please review this code and provide feedback:\n\n\`\`\`${editor.document.languageId}\n${text}\n\`\`\``
                        });
                    }
                }
                else {
                    vscode.window.showWarningMessage('No active editor to review');
                }
                break;
            case 'debug':
                if (this._view) {
                    this._view.webview.postMessage({
                        type: 'chat:prefill',
                        text: 'I\'m having an issue with my code. Can you help me debug it?'
                    });
                }
                break;
            case 'explain':
                if (editor?.selection && !editor.selection.isEmpty) {
                    const selectedText = editor.document.getText(editor.selection);
                    if (this._view) {
                        this._view.webview.postMessage({
                            type: 'chat:prefill',
                            text: `Please explain this code:\n\n\`\`\`${editor.document.languageId}\n${selectedText}\n\`\`\``
                        });
                    }
                }
                else if (this._view) {
                    this._view.webview.postMessage({
                        type: 'chat:prefill',
                        text: 'Please explain how this code works'
                    });
                }
                break;
            case 'tests':
                if (editor) {
                    const text = editor.document.getText();
                    if (this._view) {
                        this._view.webview.postMessage({
                            type: 'chat:prefill',
                            text: `Generate comprehensive unit tests for this code:\n\n\`\`\`${editor.document.languageId}\n${text}\n\`\`\``
                        });
                    }
                }
                else {
                    vscode.window.showWarningMessage('No active editor to generate tests for');
                }
                break;
            default:
                console.log(`AEP: Unknown action: ${action}`);
        }
    }
    getHtmlContent(webview) {
        const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this.ctx.extensionUri, 'media', 'home.js'));
        const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(this.ctx.extensionUri, 'media', 'home.css'));
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src ${webview.cspSource}; font-src ${webview.cspSource};">
    <link rel="stylesheet" href="${styleUri}">
    <title>AEP Professional</title>
</head>
<body>
    <div class="container">
        <header class="header">
            <h2>AEP Professional</h2>
            <div class="spacer"></div>
            <button id="modelBtn" class="tertiary" title="Select AI Model">Model: Loading...</button>
            <button id="settingsBtn" class="tertiary" title="Open Settings (MCP, Models, etc.)">⚙️</button>
            <button id="signinBtn" class="primary">Sign in</button>
        </header>

        <div id="hero" class="hero-section card">
            <h3>Welcome to AEP Professional</h3>
            <p>Your AI-powered autonomous engineering assistant. I can help with code reviews, debugging, explanations, and more. Configure MCP servers and models in settings.</p>
            <div class="action-grid">
                <button class="action-btn" data-action="review">
                    <span>🔍</span>
                    <span>Review Code</span>
                </button>
                <button class="action-btn" data-action="debug">
                    <span>🐛</span>
                    <span>Debug Issue</span>
                </button>
                <button class="action-btn" data-action="explain">
                    <span>💡</span>
                    <span>Explain Code</span>
                </button>
                <button class="action-btn" data-action="tests">
                    <span>🧪</span>
                    <span>Generate Tests</span>
                </button>
            </div>
        </div>

        <div class="chat-container">
            <div id="chatLog" class="chat-log"></div>
            <div class="chat-input-container">
                <div class="input-wrapper">
                    <textarea id="chatInput" class="chat-input" placeholder="Ask AEP anything..." rows="1"></textarea>
                </div>
                <button id="chatSend" class="send-btn" title="Send message">→</button>
            </div>
        </div>
    </div>
    <script src="${scriptUri}"></script>
</body>
</html>`;
    }
}
exports.HomeViewProvider = HomeViewProvider;
//# sourceMappingURL=HomeViewProvider.js.map