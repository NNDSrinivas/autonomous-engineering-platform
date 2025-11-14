"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
// src/extension.ts
const vscode = require("vscode");
function activate(context) {
    const provider = new NaviWebviewProvider(context.extensionUri, context);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider(
    // Make sure this matches the view id in package.json
    'aep.chatView', provider));
}
function deactivate() {
    // nothing yet
}
class NaviWebviewProvider {
    constructor(extensionUri, context) {
        this._messages = [];
        this._currentModel = 'ChatGPT 5.1';
        this._currentMode = 'Agent (full access)';
        this._extensionUri = extensionUri;
        this._context = context;
        this._conversationId = generateConversationId();
    }
    resolveWebviewView(webviewView, _context, _token) {
        this._view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri]
        };
        webviewView.webview.html = this.getWebviewHtml(webviewView.webview);
        webviewView.webview.onDidReceiveMessage(async (msg) => {
            try {
                switch (msg.type) {
                    case 'ready': {
                        // Panel is ready, send initial welcome message
                        this.postToWebview({
                            type: 'botMessage',
                            text: "Hello! I'm NAVI, your autonomous engineering assistant. How can I help you today?"
                        });
                        break;
                    }
                    case 'sendMessage': {
                        const text = String(msg.text || '').trim();
                        if (!text) {
                            return;
                        }
                        console.log('[Extension Host] [AEP] User message:', text);
                        // Update local state
                        this._messages.push({ role: 'user', content: text });
                        // Show thinking state
                        this.postToWebview({ type: 'botThinking', value: true });
                        await this.callNaviBackend(text);
                        break;
                    }
                    case 'modelChanged': {
                        const label = String(msg.value || '').trim();
                        if (!label)
                            return;
                        this._currentModel = label;
                        console.log('[Extension Host] [AEP] Model changed to:', label);
                        this.postToWebview({
                            type: 'botMessage',
                            text: `Model switched to **${label}** (demo-only selector for now).`
                        });
                        break;
                    }
                    case 'modeChanged': {
                        const label = String(msg.value || '').trim();
                        if (!label)
                            return;
                        this._currentMode = label;
                        console.log('[Extension Host] [AEP] Mode changed to:', label);
                        this.postToWebview({
                            type: 'botMessage',
                            text: `Mode updated to **${label}** (demo-only for now).`
                        });
                        break;
                    }
                    case 'newChat': {
                        // Clear current conversation state (so backend can start fresh)
                        this._conversationId = generateConversationId();
                        this._messages = [];
                        // Tell the webview to reset its UI
                        this.postToWebview({
                            type: 'resetChat',
                        });
                        break;
                    }
                    case 'attachClicked': {
                        // For now just show that the wiring works.
                        // Later we can open a real file/folder pick flow.
                        vscode.window.showInformationMessage('Attachment flow is not implemented yet – coming soon in a future release.');
                        break;
                    }
                    case 'pickAttachment': {
                        // Open file picker for attachments
                        const uris = await vscode.window.showOpenDialog({
                            canSelectMany: true,
                            openLabel: 'Attach to NAVI chat',
                            filters: {
                                'Code & Text': ['ts', 'tsx', 'js', 'jsx', 'java', 'py', 'cs', 'go', 'rb', 'kt', 'c', 'cpp', 'h', 'sql', 'yml', 'yaml', 'json', 'md', 'txt'],
                                'All Files': ['*'],
                            },
                        });
                        if (!uris || uris.length === 0) {
                            this.postToWebview({ type: 'attachmentsCanceled' });
                            return;
                        }
                        this.postToWebview({
                            type: 'attachmentsSelected',
                            files: uris.map((u) => ({
                                path: u.fsPath,
                                name: vscode.workspace.asRelativePath(u.fsPath),
                            })),
                        });
                        break;
                    }
                    case 'commandSelected': {
                        // Map the menu item -> suggested prompt
                        const cmd = String(msg.command || '');
                        let prompt = '';
                        switch (cmd) {
                            case 'explain-code':
                                prompt =
                                    'Explain this code step-by-step, including what it does, time/space complexity, and any potential bugs or edge cases:';
                                break;
                            case 'refactor-code':
                                prompt =
                                    'Refactor this code for readability and maintainability, without changing behaviour:';
                                break;
                            case 'add-tests':
                                prompt =
                                    'Generate unit tests for this code. Include edge cases and failure paths:';
                                break;
                            case 'review-diff':
                                prompt =
                                    'Do a code review: highlight bugs, smells, and design/style issues, and suggest improvements:';
                                break;
                            case 'document-code':
                                prompt =
                                    'Add great documentation for this code: docstrings, comments where helpful, and a short summary of behaviour and constraints:';
                                break;
                            default:
                                // Fallback – just echo the command id
                                prompt = `Run NAVI action: ${cmd}`;
                        }
                        this.postToWebview({
                            type: 'insertCommandPrompt',
                            prompt,
                        });
                        break;
                    }
                    case 'attachTypeSelected': {
                        const type = String(msg.value || '').trim();
                        if (!type)
                            return;
                        vscode.window.showInformationMessage(`Attachment flow for "${type}" is not wired yet – this will open the real picker in a later PR.`);
                        break;
                    }
                    default:
                        console.warn('[Extension Host] [AEP] Unknown message from webview:', msg);
                }
            }
            catch (err) {
                console.error('[Extension Host] [AEP] Error handling webview message:', err);
                this.postToWebview({
                    type: 'error',
                    text: '⚠️ Unexpected error in NAVI extension. Check developer tools for more details.'
                });
            }
        });
        // Welcome message will be sent when panel sends 'ready'
    }
    // --- Core: call NAVI backend ------------------------------------------------
    async callNaviBackend(latestUserText) {
        if (!this._view) {
            return;
        }
        const payload = {
            id: this._conversationId,
            model: this._currentModel,
            mode: this._currentMode,
            messages: this._messages,
            // PR1: we keep stream=false by default for reliability.
            // You can flip this to true once your backend supports SSE.
            stream: false
        };
        let response;
        try {
            // Read backend URL from configuration with fallback
            const config = vscode.workspace.getConfiguration('aep');
            const backendUrl = config.get('navi.backendUrl') || 'http://127.0.0.1:8787/api/chat';
            console.log('[Extension Host] [AEP] Calling NAVI backend', backendUrl, payload);
            response = await fetch(backendUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });
        }
        catch (error) {
            console.error('[Extension Host] [AEP] NAVI backend unreachable:', error);
            this.postToWebview({ type: 'botThinking', value: false });
            this.postToWebview({
                type: 'error',
                text: `⚠️ NAVI backend error: ${(error && error.message) || 'fetch failed'}`
            });
            return;
        }
        const contentType = (response.headers.get('content-type') || '').toLowerCase();
        // Non-2xx: show a clean error bubble, no empty reply above it.
        if (!response.ok) {
            console.error('[Extension Host] [AEP] NAVI backend non-OK response:', response.status, response.statusText);
            this.postToWebview({ type: 'botThinking', value: false });
            this.postToWebview({
                type: 'error',
                text: `⚠️ NAVI backend error: HTTP ${response.status} ${response.statusText || ''}`.trim()
            });
            return;
        }
        try {
            if (contentType.includes('application/json')) {
                // 🚀 Normal JSON reply (recommended for PR1)
                const json = (await response.json());
                const reply = (json.reply || '').trim();
                if (!reply) {
                    console.warn('[Extension Host] [AEP] Empty reply from NAVI backend JSON.');
                    this.postToWebview({
                        type: 'error',
                        text: '⚠️ NAVI backend returned an empty reply.'
                    });
                    return;
                }
                this._messages.push({ role: 'assistant', content: reply });
                this.postToWebview({ type: 'botMessage', text: reply });
                return;
            }
            if (contentType.includes('text/event-stream')) {
                // ⚡ Streaming path (SSE) – we still send a single final botMessage for now
                const fullText = await this.readSseStream(response);
                const reply = fullText.trim();
                if (!reply) {
                    this.postToWebview({
                        type: 'error',
                        text: '⚠️ NAVI backend returned an empty streamed reply.'
                    });
                    return;
                }
                this._messages.push({ role: 'assistant', content: reply });
                this.postToWebview({ type: 'botMessage', text: reply });
                return;
            }
            // Fallback: treat as plain text
            const text = (await response.text()).trim();
            if (!text) {
                this.postToWebview({
                    type: 'error',
                    text: '⚠️ NAVI backend returned an empty reply (unknown content-type).'
                });
                return;
            }
            this._messages.push({ role: 'assistant', content: text });
            this.postToWebview({ type: 'botMessage', text });
        }
        catch (err) {
            console.error('[Extension Host] [AEP] Error handling NAVI backend response:', err);
            this.postToWebview({
                type: 'error',
                text: '⚠️ Error while processing response from NAVI backend.'
            });
        }
    }
    // --- SSE reader (streaming support baked in for later) ----------------------
    /**
     * Reads a text/event-stream response and returns concatenated text.
     * For PR1 we **do not** stream partial chunks into the UI yet, to keep
     * the panel logic simple and avoid duplicated bubbles.
     */
    async readSseStream(response) {
        const reader = response.body?.getReader();
        if (!reader) {
            console.warn('[Extension Host] [AEP] SSE response had no body.');
            return '';
        }
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        let accumulated = '';
        try {
            // eslint-disable-next-line no-constant-condition
            while (true) {
                const { done, value } = await reader.read();
                if (done)
                    break;
                buffer += decoder.decode(value, { stream: true });
                let newlineIndex;
                // Process line by line
                while ((newlineIndex = buffer.indexOf('\n')) >= 0) {
                    const line = buffer.slice(0, newlineIndex).trim();
                    buffer = buffer.slice(newlineIndex + 1);
                    if (!line || !line.startsWith('data:')) {
                        continue;
                    }
                    const data = line.slice('data:'.length).trim();
                    if (!data)
                        continue;
                    if (data === '[DONE]') {
                        // End of stream
                        return accumulated;
                    }
                    let chunk = data;
                    // If backend wraps data as JSON { delta: "..." }, unpack it
                    try {
                        const parsed = JSON.parse(data);
                        if (typeof parsed.delta === 'string') {
                            chunk = parsed.delta;
                        }
                        else if (typeof parsed.reply === 'string') {
                            chunk = parsed.reply;
                        }
                    }
                    catch {
                        // If not JSON, treat as raw text
                    }
                    accumulated += chunk;
                }
            }
        }
        catch (err) {
            // In PR1 we just log SSE errors and let the caller decide what to show
            console.error('[Extension Host] [AEP] Error while reading SSE stream:', err);
        }
        return accumulated;
    }
    // --- Helpers ---------------------------------------------------------------
    postToWebview(message) {
        if (!this._view)
            return;
        this._view.webview.postMessage(message);
    }
    startNewChat() {
        // Reset conversation state, keep current model/mode
        this._conversationId = generateConversationId();
        this._messages = [];
        this.postToWebview({ type: 'clearChat' });
        this.postToWebview({
            type: 'botMessage',
            text: "New chat started! How can I help you?"
        });
    }
    getWebviewHtml(webview) {
        const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'panel.js'));
        const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'panel.css'));
        const naviLogoUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'mascot-navi-fox.svg'));
        const nonce = getNonce();
        return /* html */ `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta
      http-equiv="Content-Security-Policy"
      content="default-src 'none'; img-src ${webview.cspSource} https: data:; style-src 'unsafe-inline' ${webview.cspSource}; script-src 'nonce-${nonce}';"
    />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link href="${styleUri}" rel="stylesheet" />
    <title>AEP: NAVI Assistant</title>
  </head>
  <body>
    <div id="root" data-mascot-src="${naviLogoUri}"></div>
    <script nonce="${nonce}" src="${scriptUri}"></script>
  </body>
</html>`;
    }
}
// Simple conversation id – you can switch to UUID later
function generateConversationId() {
    return `navi-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}
function getNonce() {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}
//# sourceMappingURL=extension.js.map