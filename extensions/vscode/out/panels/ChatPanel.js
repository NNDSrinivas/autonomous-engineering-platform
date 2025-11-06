"use strict";
/**
 * Chat Panel - Rich conversational interface for AEP Agent
 *
 * Provides Cline-like chat experience with:
 * - Persistent conversation history
 * - Context-aware responses
 * - Proactive suggestions
 * - Team intelligence integration
 */
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
exports.ChatPanel = void 0;
const vscode = __importStar(require("vscode"));
class ChatPanel {
    constructor(panel, extensionUri) {
        this._disposables = [];
        this._chatState = { messages: [] };
        this._messageCounter = 0;
        this._panel = panel;
        this._apiBase = vscode.workspace.getConfiguration('aep').get('coreApi') || 'http://localhost:8002';
        // Set webview content
        this._panel.webview.html = this._getWebviewContent(this._panel.webview, extensionUri);
        // Handle messages from webview
        this._panel.webview.onDidReceiveMessage(async (message) => {
            switch (message.command) {
                case 'sendMessage':
                    await this._handleUserMessage(message.text);
                    break;
                case 'acceptSuggestion':
                    await this._handleSuggestionAccepted(message.suggestion);
                    break;
                case 'requestContext':
                    await this._loadTeamContext();
                    break;
                case 'selectTask':
                    await this._selectTask(message.taskKey);
                    break;
            }
        }, null, this._disposables);
        // Clean up on dispose
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
        // Initialize with welcome message
        this._initializeChat();
    }
    static createOrShow(extensionUri) {
        const column = vscode.ViewColumn.Beside;
        // If panel already exists, reveal it
        if (ChatPanel.currentPanel) {
            ChatPanel.currentPanel._panel.reveal(column);
            return;
        }
        // Create new panel
        const panel = vscode.window.createWebviewPanel('aepChat', 'AEP Agent Chat', column, {
            enableScripts: true,
            localResourceRoots: [extensionUri],
            retainContextWhenHidden: true
        });
        ChatPanel.currentPanel = new ChatPanel(panel, extensionUri);
    }
    _generateMessageId(prefix) {
        try {
            // Single crypto require with nested fallback methods
            const crypto = require('crypto');
            try {
                // Use crypto.randomUUID() as primary method (available in Node.js 14.17+)
                return `${prefix}-${crypto.randomUUID()}`;
            }
            catch {
                // Fallback: use timestamp and cryptographically secure random bytes
                const timestamp = Date.now();
                const randomHex = crypto.randomBytes(8).toString('hex'); // 8 random bytes (64 bits) as 16 hex characters
                this._messageCounter = (this._messageCounter + 1) % (ChatPanel.MAX_COUNTER_VALUE + 1);
                return `${prefix}-${timestamp}-${randomHex}-${this._messageCounter}`;
            }
        }
        catch {
            // If crypto module fails entirely, fallback to Math.random (last resort)
            const timestamp = Date.now();
            const randomHex = Math.floor(Math.random() * Number.MAX_SAFE_INTEGER).toString(36);
            this._messageCounter = (this._messageCounter + 1) % (ChatPanel.MAX_COUNTER_VALUE + 1);
            return `${prefix}-${timestamp}-${randomHex}-${this._messageCounter}`;
        }
    }
    async _initializeChat() {
        // Load previous chat history if exists
        await this._loadChatHistory();
        // Add welcome message with team context
        const welcomeMessage = await this._generateWelcomeMessage();
        this._addMessage({
            id: this._generateMessageId('msg'),
            type: 'assistant',
            content: welcomeMessage.text,
            timestamp: new Date(),
            context: {
                suggestions: welcomeMessage.suggestions
            }
        });
        // Load proactive suggestions
        await this._loadProactiveSuggestions();
    }
    async _generateWelcomeMessage() {
        try {
            // Get current time context
            const name = process.env.USER || 'Developer';
            const hr = new Date().getHours();
            const timeOfDay = hr < 12 ? 'morning' : hr < 18 ? 'afternoon' : 'evening';
            // Fetch team context
            const teamContext = await this._fetchTeamContext();
            const activeTasks = teamContext.tasks?.slice(0, 3) || [];
            const recentActivity = teamContext.recentActivity || [];
            let text = `Good ${timeOfDay}, ${name}! 👋\n\n`;
            if (activeTasks.length > 0) {
                text += `You have ${activeTasks.length} active tasks:\n`;
                activeTasks.forEach((task, idx) => {
                    text += `${idx + 1}. **${task.key}**: ${task.summary}\n`;
                });
                text += '\n';
            }
            if (recentActivity.length > 0) {
                text += `🔄 Recent team activity:\n`;
                recentActivity.slice(0, 2).forEach((activity) => {
                    text += `• ${activity.summary}\n`;
                });
                text += '\n';
            }
            text += `What would you like to work on today?`;
            const suggestions = [
                'Show me my highest priority task',
                'What are my teammates working on?',
                'Help me resolve merge conflicts',
                'Generate a plan for my next task',
                'Review recent changes and suggest improvements'
            ];
            return { text, suggestions };
        }
        catch (error) {
            const hr = new Date().getHours();
            const timeOfDay = hr < 12 ? 'morning' : hr < 18 ? 'afternoon' : 'evening';
            return {
                text: `Good ${timeOfDay}! I'm your autonomous engineering assistant. How can I help you today?`,
                suggestions: ['Show me my tasks', 'Help me with current work', 'Generate a plan']
            };
        }
    }
    async _handleUserMessage(text) {
        // Add user message to chat
        const userMessage = {
            id: this._generateMessageId('msg'),
            type: 'user',
            content: text,
            timestamp: new Date()
        };
        this._addMessage(userMessage);
        // Show typing indicator
        this._showTypingIndicator();
        try {
            // Generate context-aware response
            const response = await this._generateResponse(text);
            // Add assistant response
            const assistantMessage = {
                id: this._generateMessageId('msg'),
                type: 'assistant',
                content: response.content,
                timestamp: new Date(),
                context: response.context
            };
            this._addMessage(assistantMessage);
            // Add proactive suggestions if any
            if (response.suggestions && response.suggestions.length > 0) {
                const suggestionMessage = {
                    id: this._generateMessageId('msg'),
                    type: 'suggestion',
                    content: 'Here are some things I can help with next:',
                    timestamp: new Date(),
                    context: { suggestions: response.suggestions }
                };
                this._addMessage(suggestionMessage);
            }
        }
        catch (error) {
            const errorMessage = error instanceof Error ? error.message : String(error);
            this._addMessage({
                id: this._generateMessageId('msg'),
                type: 'assistant',
                content: `I encountered an error: ${errorMessage}. Let me try a different approach.`,
                timestamp: new Date()
            });
        }
        finally {
            this._hideTypingIndicator();
        }
    }
    async _generateResponse(userInput) {
        try {
            // Call enhanced LLM endpoint with conversation context
            const response = await fetch(`${this._apiBase}/api/chat/respond`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: userInput,
                    conversationHistory: this._chatState.messages.slice(-10), // Last 10 messages for context
                    currentTask: this._chatState.currentTask,
                    teamContext: this._chatState.teamContext
                })
            });
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            return await response.json();
        }
        catch (error) {
            // Fallback to rule-based responses
            return this._generateFallbackResponse(userInput);
        }
    }
    _generateFallbackResponse(userInput) {
        const input = userInput.toLowerCase();
        if (input.includes('task') || input.includes('jira')) {
            return {
                content: 'I can help you with your tasks! Let me fetch your current assignments.',
                suggestions: ['Show highest priority task', 'Create a plan for next task', 'Show task dependencies']
            };
        }
        if (input.includes('team') || input.includes('colleague')) {
            return {
                content: 'Let me show you what your team is working on and how it connects to your work.',
                suggestions: ['Show team activity', 'Find related work', 'Check for blockers']
            };
        }
        if (input.includes('plan') || input.includes('how')) {
            return {
                content: 'I can generate a detailed plan for your work. What specific task or goal would you like me to help with?',
                suggestions: ['Generate implementation plan', 'Break down complex task', 'Show dependencies']
            };
        }
        return {
            content: 'I\'m here to help with your engineering work! I can assist with tasks, team coordination, code planning, and more.',
            suggestions: ['Show my tasks', 'Generate a plan', 'Check team status', 'Help with current work']
        };
    }
    async _fetchTeamContext() {
        try {
            const [tasksResponse, activityResponse] = await Promise.all([
                fetch(`${this._apiBase}/api/jira/tasks`),
                fetch(`${this._apiBase}/api/activity/recent`)
            ]);
            const tasks = tasksResponse.ok ? await tasksResponse.json() : { items: [] };
            const activity = activityResponse.ok ? await activityResponse.json() : { items: [] };
            return {
                tasks: tasks.items || [],
                recentActivity: activity.items || []
            };
        }
        catch (error) {
            return { tasks: [], recentActivity: [] };
        }
    }
    async _loadProactiveSuggestions() {
        try {
            // Use memory graph to generate proactive suggestions via chat endpoint
            const response = await fetch(`${this._apiBase}/api/chat/proactive`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    context: {
                        currentFiles: await this._getCurrentWorkspaceFiles(),
                        recentChanges: await this._getRecentChanges(),
                        activeTask: this._chatState.currentTask
                    }
                })
            });
            if (response.ok) {
                const suggestions = await response.json();
                if (suggestions.items && suggestions.items.length > 0) {
                    this._addMessage({
                        id: this._generateMessageId('proactive'),
                        type: 'suggestion',
                        content: '💡 Based on your recent work, I noticed:',
                        timestamp: new Date(),
                        context: { suggestions: suggestions.items }
                    });
                }
            }
        }
        catch (error) {
            // Silently fail for proactive suggestions
        }
    }
    async _getCurrentWorkspaceFiles() {
        try {
            // Read file patterns and maxFiles from VS Code settings, with defaults
            const config = vscode.workspace.getConfiguration('aepAgent');
            const patterns = config.get('fileDiscovery.patterns', [
                '**/*.py', '**/*.js', '**/*.ts', '**/*.jsx', '**/*.tsx'
            ]);
            const maxFiles = config.get('fileDiscovery.maxFiles', 20);
            const allFiles = [];
            // Search patterns until we reach the limit
            for (const pattern of patterns) {
                if (allFiles.length >= maxFiles)
                    break;
                const remainingSlots = maxFiles - allFiles.length;
                const files = await vscode.workspace.findFiles(pattern, '**/node_modules/**', remainingSlots);
                allFiles.push(...files);
            }
            // Deduplicate and return
            const uniquePaths = Array.from(new Set(allFiles.map(file => file.fsPath)));
            return uniquePaths.slice(0, maxFiles);
        }
        catch {
            return [];
        }
    }
    async _getRecentChanges() {
        try {
            // TODO: Implement git integration to get recent changes
            // This would use vscode.extensions.getExtension('vscode.git') API
            // or execute git commands via vscode.workspace.workspaceFolders
            // NOTE: Accessing the git extension or executing git commands may require user consent or workspace trust.
            // Ensure appropriate security and permission checks are implemented before accessing these resources.
            return [];
        }
        catch {
            return [];
        }
    }
    _addMessage(message) {
        this._chatState.messages.push(message);
        this._updateWebview();
        // TODO: Implement chat history persistence.
        //       Persist chat history using VS Code workspace storage (vscode.workspaceState or vscode.globalState).
        //       Serialize messages as JSON for storage and retrieval.
        // this._saveChatHistory();
    }
    _updateWebview() {
        this._panel.webview.postMessage({
            command: 'updateChat',
            chatState: this._chatState
        });
    }
    _showTypingIndicator() {
        this._panel.webview.postMessage({ command: 'showTyping' });
    }
    _hideTypingIndicator() {
        this._panel.webview.postMessage({ command: 'hideTyping' });
    }
    async _loadChatHistory() {
        // Load from workspace state or file
        // Implementation would depend on persistence strategy
    }
    async _saveChatHistory() {
        // Save to workspace state or file
        // Implementation would depend on persistence strategy
    }
    async _loadTeamContext() {
        this._chatState.teamContext = await this._fetchTeamContext();
        this._updateWebview();
    }
    async _selectTask(taskKey) {
        this._chatState.currentTask = taskKey;
        // Fetch context pack for selected task
        try {
            const response = await fetch(`${this._apiBase}/api/context/task/${encodeURIComponent(taskKey)}`);
            const contextPack = await response.json();
            this._addMessage({
                id: this._generateMessageId('task-selected'),
                type: 'assistant',
                content: `Great! I've loaded context for **${taskKey}**. Here's what I understand:\n\n${contextPack.explain?.what || 'Task details loading...'}\n\nHow would you like to proceed?`,
                timestamp: new Date(),
                context: {
                    taskKey,
                    suggestions: [
                        'Generate implementation plan',
                        'Show related files',
                        'Check dependencies',
                        'Start working on this task'
                    ]
                }
            });
        }
        catch (error) {
            this._addMessage({
                id: this._generateMessageId('task-error'),
                type: 'assistant',
                content: `I've selected task ${taskKey}, but couldn't load all details. How would you like to proceed?`,
                timestamp: new Date(),
                context: { taskKey }
            });
        }
    }
    async _handleSuggestionAccepted(suggestion) {
        // Handle when user clicks on a suggestion
        await this._handleUserMessage(suggestion);
    }
    dispose() {
        ChatPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const disposable = this._disposables.pop();
            if (disposable) {
                disposable.dispose();
            }
        }
    }
    _getWebviewContent(webview, extensionUri) {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AEP Agent Chat</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            padding: 0;
            margin: 0;
            height: 100vh;
            display: flex;
            flex-direction: column;
            background-color: var(--vscode-editor-background);
            color: var(--vscode-editor-foreground);
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
            max-width: 80%;
            padding: 12px 16px;
            border-radius: 12px;
            word-wrap: break-word;
        }
        
        .message.user {
            align-self: flex-end;
            background-color: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
        }
        
        .message.assistant {
            align-self: flex-start;
            background-color: var(--vscode-input-background);
            border: 1px solid var(--vscode-input-border);
        }
        
        .message.system {
            align-self: center;
            background-color: var(--vscode-badge-background);
            color: var(--vscode-badge-foreground);
            font-size: 0.9em;
            text-align: center;
        }
        
        .suggestions {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-top: 8px;
        }
        
        .suggestion-chip {
            padding: 8px 12px;
            background-color: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
            border: 1px solid var(--vscode-button-border);
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.9em;
            transition: background-color 0.2s;
        }
        
        .suggestion-chip:hover {
            background-color: var(--vscode-button-secondaryHoverBackground);
        }
        
        .input-container {
            padding: 16px;
            border-top: 1px solid var(--vscode-panel-border);
            display: flex;
            gap: 8px;
        }
        
        .message-input {
            flex: 1;
            padding: 12px;
            border: 1px solid var(--vscode-input-border);
            border-radius: 6px;
            background-color: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            font-family: var(--vscode-font-family);
            resize: vertical;
            min-height: 20px;
            max-height: 120px;
        }
        
        .send-button {
            padding: 12px 20px;
            background-color: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
        }
        
        .send-button:hover {
            background-color: var(--vscode-button-hoverBackground);
        }
        
        .send-button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .typing-indicator {
            align-self: flex-start;
            padding: 12px 16px;
            background-color: var(--vscode-input-background);
            border: 1px solid var(--vscode-input-border);
            border-radius: 12px;
            font-style: italic;
            opacity: 0.7;
        }
        
        .timestamp {
            font-size: 0.8em;
            opacity: 0.6;
            margin-top: 4px;
        }
        
        .context-info {
            font-size: 0.9em;
            opacity: 0.8;
            margin-top: 8px;
            padding: 8px;
            background-color: var(--vscode-textBlockQuote-background);
            border-left: 3px solid var(--vscode-textBlockQuote-border);
            border-radius: 0 4px 4px 0;
        }
        
        .task-selector {
            display: flex;
            flex-direction: column;
            gap: 4px;
            margin-top: 8px;
        }
        
        .task-item {
            padding: 8px 12px;
            background-color: var(--vscode-list-inactiveSelectionBackground);
            border: 1px solid var(--vscode-list-inactiveSelectionForeground);
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9em;
        }
        
        .task-item:hover {
            background-color: var(--vscode-list-hoverBackground);
        }
        
        strong {
            font-weight: 600;
        }
        
        code {
            background-color: var(--vscode-textCodeBlock-background);
            padding: 2px 4px;
            border-radius: 3px;
            font-family: var(--vscode-editor-font-family);
        }
    </style>
</head>
<body>
    <div class="chat-container" id="chatContainer">
        <!-- Messages will be inserted here -->
    </div>
    
    <div class="input-container">
        <textarea 
            class="message-input" 
            id="messageInput" 
            placeholder="Ask me anything about your work, tasks, or team..."
            rows="1"
        ></textarea>
        <button class="send-button" id="sendButton">Send</button>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        let chatState = { messages: [] };
        
        // Handle messages from extension
        window.addEventListener('message', event => {
            const message = event.data;
            switch (message.command) {
                case 'updateChat':
                    chatState = message.chatState;
                    renderChat();
                    break;
                case 'showTyping':
                    showTypingIndicator();
                    break;
                case 'hideTyping':
                    hideTypingIndicator();
                    break;
            }
        });

        function escapeHtml(value) {
            return (value ?? '')
                .toString()
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function renderMarkdown(text) {
            const escaped = escapeHtml(text);
            return escaped
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\`(.*?)\`/g, '<code>$1</code>')
                .replace(/\\n/g, '<br>');
        }
        
        function renderChat() {
            const container = document.getElementById('chatContainer');
            container.innerHTML = '';
            
            chatState.messages.forEach(message => {
                const messageEl = createMessageElement(message);
                container.appendChild(messageEl);
            });
            
            // Scroll to bottom
            container.scrollTop = container.scrollHeight;
        }
        
        function createMessageElement(message) {
            const messageEl = document.createElement('div');
            messageEl.className = \`message \${message.type}\`;
            
            // Format content with escaped markdown rendering
            const contentHtml = renderMarkdown(message.content);
            messageEl.innerHTML = contentHtml;
            
            // Add timestamp
            const timestamp = document.createElement('div');
            timestamp.className = 'timestamp';
            timestamp.textContent = new Date(message.timestamp).toLocaleTimeString();
            messageEl.appendChild(timestamp);
            
            // Add context info
            if (message.context) {
                if (message.context.taskKey) {
                    const contextEl = document.createElement('div');
                    contextEl.className = 'context-info';
                    const labelEl = document.createElement('strong');
                    labelEl.textContent = 'Task:';
                    const valueEl = document.createElement('span');
                    valueEl.textContent = \` \${message.context.taskKey}\`;
                    contextEl.appendChild(labelEl);
                    contextEl.appendChild(valueEl);
                    messageEl.appendChild(contextEl);
                }
                
                if (message.context.suggestions) {
                    const suggestionsEl = document.createElement('div');
                    suggestionsEl.className = 'suggestions';
                    
                    message.context.suggestions.forEach(suggestion => {
                        const chipEl = document.createElement('div');
                        chipEl.className = 'suggestion-chip';
                        chipEl.textContent = suggestion;
                        chipEl.onclick = () => {
                            vscode.postMessage({ command: 'acceptSuggestion', suggestion });
                        };
                        suggestionsEl.appendChild(chipEl);
                    });
                    
                    messageEl.appendChild(suggestionsEl);
                }
            }
            
            return messageEl;
        }
        
        function showTypingIndicator() {
            const container = document.getElementById('chatContainer');
            const existing = document.getElementById('typingIndicator');
            if (existing) return;
            
            const typingEl = document.createElement('div');
            typingEl.id = 'typingIndicator';
            typingEl.className = 'typing-indicator';
            typingEl.textContent = 'AEP Agent is thinking...';
            container.appendChild(typingEl);
            container.scrollTop = container.scrollHeight;
        }
        
        function hideTypingIndicator() {
            const typingEl = document.getElementById('typingIndicator');
            if (typingEl) {
                typingEl.remove();
            }
        }
        
        function sendMessage() {
            const input = document.getElementById('messageInput');
            const text = input.value.trim();
            if (!text) return;
            
            vscode.postMessage({ command: 'sendMessage', text });
            input.value = '';
            input.style.height = 'auto';
        }
        
        // Set up event listeners
        document.getElementById('sendButton').onclick = sendMessage;
        
        const messageInput = document.getElementById('messageInput');
        messageInput.onkeydown = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        };
        
        // Auto-resize textarea
        messageInput.oninput = () => {
            messageInput.style.height = 'auto';
            messageInput.style.height = messageInput.scrollHeight + 'px';
        };
        
        // Request initial context
        vscode.postMessage({ command: 'requestContext' });
    </script>
</body>
</html>`;
    }
}
exports.ChatPanel = ChatPanel;
// Counter wrapping constant for 32-bit unsigned integer overflow protection
ChatPanel.MAX_COUNTER_VALUE = 0xFFFFFFFF;
//# sourceMappingURL=ChatPanel.js.map