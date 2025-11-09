import * as vscode from 'vscode';
import { AuthService } from '../services/AuthService';
import { ApiClient } from '../services/ApiClient';

export interface ChatMessage {
    id: string;
    type: 'user' | 'assistant' | 'system' | 'error';
    content: string;
    timestamp: number;
    metadata?: {
        thinking?: boolean;
        actions?: Array<{
            type: 'file' | 'diff' | 'approve' | 'reject';
            label: string;
            data?: any;
        }>;
    };
}

export class ChatViewProvider implements vscode.WebviewViewProvider {
    private _view?: vscode.WebviewView;
    private _messages: ChatMessage[] = [];
    private _sessionId: string = this.generateSessionId();

    constructor(
        private context: vscode.ExtensionContext,
        private authService: AuthService,
        private apiClient: ApiClient
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
                case 'sendMessage':
                    await this.handleUserMessage(message.content);
                    break;
                case 'executeAction':
                    await this.executeAction(message.action);
                    break;
                case 'ready':
                    await this.initializeChat();
                    break;
            }
        });
    }

    public async newSession() {
        this._messages = [];
        this._sessionId = this.generateSessionId();
        await this.updateWebview();
        await this.initializeChat();
    }

    private async initializeChat() {
        if (!await this.authService.isAuthenticated()) {
            this.addMessage({
                id: this.generateMessageId(),
                type: 'system',
                content: '🔐 Please sign in to start chatting with AEP Agent',
                timestamp: Date.now()
            });
            return;
        }

        // Add welcome message
        this.addMessage({
            id: this.generateMessageId(),
            type: 'assistant',
            content: `👋 Hello! I'm your AEP Agent. I can help you with:

• **Code generation** and refactoring
• **Task automation** and workflow planning  
• **Architecture decisions** and best practices
• **Bug fixes** and performance optimization

What would you like to work on today?`,
            timestamp: Date.now(),
            metadata: {
                actions: [
                    { type: 'file', label: 'Analyze current file', data: { action: 'analyze_file' } },
                    { type: 'diff', label: 'Review recent changes', data: { action: 'review_changes' } }
                ]
            }
        });
    }

    private async handleUserMessage(content: string) {
        // Add user message
        this.addMessage({
            id: this.generateMessageId(),
            type: 'user',
            content,
            timestamp: Date.now()
        });

        // Show thinking indicator
        const thinkingId = this.generateMessageId();
        this.addMessage({
            id: thinkingId,
            type: 'assistant',
            content: '🤔 Thinking...',
            timestamp: Date.now(),
            metadata: { thinking: true }
        });

        try {
            // Get AI response
            const response = await this.apiClient.chat({
                message: content,
                sessionId: this._sessionId,
                context: await this.gatherContext()
            });

            // Remove thinking message
            this.removeMessage(thinkingId);

            // Add AI response
            this.addMessage({
                id: this.generateMessageId(),
                type: 'assistant',
                content: response.content,
                timestamp: Date.now(),
                metadata: response.metadata
            });

        } catch (error) {
            // Remove thinking message
            this.removeMessage(thinkingId);

            // Add error message
            this.addMessage({
                id: this.generateMessageId(),
                type: 'error',
                content: `❌ Sorry, I encountered an error: ${error}`,
                timestamp: Date.now()
            });
        }
    }

    private async executeAction(action: any) {
        switch (action.action) {
            case 'analyze_file':
                await this.analyzeCurrentFile();
                break;
            case 'review_changes':
                await this.reviewRecentChanges();
                break;
            case 'view_file':
                if (action.filePath) {
                    await vscode.window.showTextDocument(vscode.Uri.file(action.filePath));
                }
                break;
            case 'show_diff':
                if (action.changes) {
                    await this.showDiff(action.changes);
                }
                break;
        }
    }

    private async analyzeCurrentFile() {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('No file is currently open');
            return;
        }

        const content = editor.document.getText();
        const fileName = editor.document.fileName;

        await this.handleUserMessage(`Please analyze this ${fileName.split('.').pop()} file:\n\n\`\`\`\n${content}\n\`\`\``);
    }

    private async reviewRecentChanges() {
        // TODO: Implement git integration to get recent changes
        await this.handleUserMessage('Please help me review my recent code changes');
    }

    private async showDiff(changes: any) {
        // TODO: Implement diff viewer
        vscode.window.showInformationMessage('Diff viewing coming soon!');
    }

    private async gatherContext() {
        const workspace = vscode.workspace.workspaceFolders?.[0];
        const activeFile = vscode.window.activeTextEditor?.document;

        return {
            workspace: workspace?.name,
            activeFile: activeFile?.fileName,
            language: activeFile?.languageId,
            selection: vscode.window.activeTextEditor?.selection
        };
    }

    private addMessage(message: ChatMessage) {
        this._messages.push(message);
        this.updateWebview();
    }

    private removeMessage(id: string) {
        this._messages = this._messages.filter(m => m.id !== id);
        this.updateWebview();
    }

    private async updateWebview() {
        if (this._view) {
            await this._view.webview.postMessage({
                type: 'updateMessages',
                messages: this._messages
            });
        }
    }

    private generateSessionId(): string {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    private generateMessageId(): string {
        return 'msg_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    private getWebviewContent(): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AEP Agent Chat</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            background: var(--vscode-sideBar-background);
            color: var(--vscode-sideBar-foreground);
            height: 100vh;
            display: flex;
            flex-direction: column;
        }

        .chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .message {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .message-content {
            padding: 12px 16px;
            border-radius: 12px;
            max-width: 85%;
            word-wrap: break-word;
            line-height: 1.4;
        }

        .message.user .message-content {
            align-self: flex-end;
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
        }

        .message.assistant .message-content,
        .message.system .message-content {
            align-self: flex-start;
            background: var(--vscode-input-background);
            border: 1px solid var(--vscode-input-border);
        }

        .message.error .message-content {
            align-self: flex-start;
            background: var(--vscode-inputValidation-errorBackground);
            border: 1px solid var(--vscode-inputValidation-errorBorder);
            color: var(--vscode-inputValidation-errorForeground);
        }

        .thinking {
            opacity: 0.7;
            font-style: italic;
            animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 0.7; }
            50% { opacity: 0.4; }
        }

        .message-actions {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 8px;
            align-self: flex-start;
        }

        .action-btn {
            padding: 6px 12px;
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
            border: 1px solid var(--vscode-button-border);
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
        }

        .action-btn:hover {
            background: var(--vscode-button-secondaryHoverBackground);
        }

        .input-container {
            padding: 16px;
            border-top: 1px solid var(--vscode-panel-border);
            background: var(--vscode-sideBar-background);
        }

        .input-wrapper {
            display: flex;
            gap: 8px;
            align-items: flex-end;
        }

        .message-input {
            flex: 1;
            min-height: 36px;
            max-height: 120px;
            padding: 8px 12px;
            border: 1px solid var(--vscode-input-border);
            border-radius: 6px;
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            font-family: inherit;
            font-size: inherit;
            resize: none;
            outline: none;
        }

        .message-input:focus {
            border-color: var(--vscode-focusBorder);
        }

        .send-btn {
            padding: 8px 16px;
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
            transition: background 0.2s;
        }

        .send-btn:hover:not(:disabled) {
            background: var(--vscode-button-hoverBackground);
        }

        .send-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .timestamp {
            font-size: 10px;
            opacity: 0.6;
            align-self: flex-start;
            margin-top: 2px;
        }

        /* Markdown styling */
        .message-content h1, .message-content h2, .message-content h3 {
            margin: 8px 0 4px 0;
            color: var(--vscode-textPreformat-foreground);
        }

        .message-content p {
            margin: 4px 0;
        }

        .message-content ul, .message-content ol {
            margin: 4px 0 4px 16px;
        }

        .message-content li {
            margin: 2px 0;
        }

        .message-content code {
            background: var(--vscode-textCodeBlock-background);
            padding: 2px 4px;
            border-radius: 3px;
            font-family: var(--vscode-editor-font-family);
        }

        .message-content pre {
            background: var(--vscode-textCodeBlock-background);
            padding: 12px;
            border-radius: 6px;
            overflow-x: auto;
            margin: 8px 0;
        }

        .message-content pre code {
            background: none;
            padding: 0;
        }

        .message-content strong {
            font-weight: 600;
        }

        .message-content em {
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="chat-container" id="chatContainer">
        <!-- Messages will be rendered here -->
    </div>
    
    <div class="input-container">
        <div class="input-wrapper">
            <textarea 
                id="messageInput" 
                class="message-input"
                placeholder="Ask me anything about your code..."
                rows="1"
            ></textarea>
            <button id="sendBtn" class="send-btn">Send</button>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        let messages = [];

        // Handle messages from extension
        window.addEventListener('message', event => {
            const message = event.data;
            
            switch (message.type) {
                case 'updateMessages':
                    messages = message.messages;
                    renderMessages();
                    break;
            }
        });

        // DOM elements
        const chatContainer = document.getElementById('chatContainer');
        const messageInput = document.getElementById('messageInput');
        const sendBtn = document.getElementById('sendBtn');

        // Send message
        function sendMessage() {
            const content = messageInput.value.trim();
            if (!content) return;

            vscode.postMessage({
                type: 'sendMessage',
                content: content
            });

            messageInput.value = '';
            adjustTextareaHeight();
        }

        // Event listeners
        sendBtn.addEventListener('click', sendMessage);

        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        messageInput.addEventListener('input', adjustTextareaHeight);

        // Auto-resize textarea
        function adjustTextareaHeight() {
            messageInput.style.height = 'auto';
            messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
        }

        // Render messages
        function renderMessages() {
            chatContainer.innerHTML = '';
            
            messages.forEach(message => {
                const messageEl = createMessageElement(message);
                chatContainer.appendChild(messageEl);
            });
            
            // Scroll to bottom
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

        // Create message element
        function createMessageElement(message) {
            const messageEl = document.createElement('div');
            messageEl.className = \`message \${message.type}\`;
            
            const contentEl = document.createElement('div');
            contentEl.className = 'message-content';
            if (message.metadata?.thinking) {
                contentEl.className += ' thinking';
            }
            
            contentEl.innerHTML = formatMarkdown(message.content);
            messageEl.appendChild(contentEl);
            
            // Add actions if present
            if (message.metadata?.actions?.length) {
                const actionsEl = document.createElement('div');
                actionsEl.className = 'message-actions';
                
                message.metadata.actions.forEach(action => {
                    const btn = document.createElement('button');
                    btn.className = 'action-btn';
                    btn.textContent = action.label;
                    btn.onclick = () => {
                        vscode.postMessage({
                            type: 'executeAction',
                            action: action.data
                        });
                    };
                    actionsEl.appendChild(btn);
                });
                
                messageEl.appendChild(actionsEl);
            }
            
            // Add timestamp
            const timestampEl = document.createElement('div');
            timestampEl.className = 'timestamp';
            timestampEl.textContent = new Date(message.timestamp).toLocaleTimeString();
            messageEl.appendChild(timestampEl);
            
            return messageEl;
        }

        // Basic markdown formatting
        function formatMarkdown(text) {
            return text
                .replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>')
                .replace(/\\*(.+?)\\*/g, '<em>$1</em>')
                .replace(/\`(.+?)\`/g, '<code>$1</code>')
                .replace(/###\\s(.+)/g, '<h3>$1</h3>')
                .replace(/##\\s(.+)/g, '<h2>$1</h2>')
                .replace /#\\s(.+)/g, '<h1>$1</h1>')
                .replace(/^•\\s(.+)$/gm, '<li>$1</li>')
                .replace(/(<li>.*<\\/li>)/s, '<ul>$1</ul>')
                .replace(/\\n\\n/g, '</p><p>')
                .replace(/^(?!<[hul])/gm, '<p>')
                .replace(/(?<![>])$/gm, '</p>')
                .replace(/<p><\\/p>/g, '')
                .replace(/\\n/g, '<br>');
        }

        // Initialize
        vscode.postMessage({ type: 'ready' });
    </script>
</body>
</html>`;
    }
}