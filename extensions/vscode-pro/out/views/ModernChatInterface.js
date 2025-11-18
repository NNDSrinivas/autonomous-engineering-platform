"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ModernChatInterface = void 0;
class ModernChatInterface {
    static getHTML(webview, profile) {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src ${webview.cspSource} 'unsafe-inline'; font-src ${webview.cspSource};">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AEP Professional - AI Assistant</title>
    <style>
        :root {
            --header-height: 44px;
            --input-height: 44px;
            --border-radius: 8px;
            --border-radius-sm: 4px;
            --spacing-xs: 4px;
            --spacing-sm: 8px;
            --spacing-md: 12px;
            --spacing-lg: 16px;
            --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        
        * {
            box-sizing: border-box;
        }
        
        body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            color: var(--vscode-foreground);
            background-color: var(--vscode-sideBar-background);
            margin: 0;
            padding: 0;
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        /* Header with modern controls */
        .header {
            height: var(--header-height);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 var(--spacing-md);
            background: var(--vscode-tab-activeBackground);
            border-bottom: 1px solid var(--vscode-panel-border);
            flex-shrink: 0;
        }
        
        .header-left {
            display: flex;
            align-items: center;
            gap: var(--spacing-sm);
        }
        
        .agent-icon {
            width: 24px;
            height: 24px;
            background: linear-gradient(135deg, #007ACC 0%, #0099CC 100%);
            border-radius: var(--border-radius-sm);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 600;
            font-size: 12px;
        }
        
        .agent-info {
            display: flex;
            flex-direction: column;
        }
        
        .agent-name {
            font-size: 13px;
            font-weight: 600;
            line-height: 1;
        }
        
        .agent-status {
            font-size: 11px;
            color: var(--vscode-descriptionForeground);
            line-height: 1;
        }
        
        .header-controls {
            display: flex;
            align-items: center;
            gap: var(--spacing-xs);
        }
        
        .control-btn {
            width: 28px;
            height: 28px;
            border: none;
            border-radius: var(--border-radius-sm);
            background: transparent;
            color: var(--vscode-icon-foreground);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            transition: background-color 0.2s;
        }
        
        .control-btn:hover {
            background: var(--vscode-toolbar-hoverBackground);
        }
        
        /* Context and model info bar */
        .info-bar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: var(--spacing-xs) var(--spacing-md);
            background: var(--vscode-editor-background);
            border-bottom: 1px solid var(--vscode-panel-border);
            font-size: 11px;
            color: var(--vscode-descriptionForeground);
            flex-shrink: 0;
        }
        
        .context-info {
            display: flex;
            align-items: center;
            gap: var(--spacing-md);
        }
        
        .context-item {
            display: flex;
            align-items: center;
            gap: var(--spacing-xs);
        }
        
        .context-indicator {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: var(--vscode-charts-green);
        }
        
        .context-indicator.inactive {
            background: var(--vscode-charts-gray);
        }
        
        /* Model selector styles */
        .model-info {
            display: flex;
            align-items: center;
            gap: var(--spacing-sm);
        }
        
        .model-selector {
            position: relative;
        }
        
        .model-dropdown-btn {
            background: none;
            border: 1px solid var(--vscode-panel-border);
            border-radius: var(--border-radius-sm);
            color: var(--vscode-foreground);
            padding: 2px var(--spacing-xs);
            font-size: 11px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: var(--spacing-xs);
        }
        
        .model-dropdown-btn:hover {
            background: var(--vscode-toolbar-hoverBackground);
        }
        
        .dropdown-arrow {
            font-size: 8px;
        }
        
        .dropdown-menu {
            position: absolute;
            top: 100%;
            right: 0;
            background: var(--vscode-dropdown-background);
            border: 1px solid var(--vscode-dropdown-border);
            border-radius: var(--border-radius-sm);
            box-shadow: var(--shadow-md);
            min-width: 160px;
            z-index: 1000;
            display: none;
        }
        
        .dropdown-menu.active {
            display: block;
        }
        
        .dropdown-item {
            padding: var(--spacing-xs) var(--spacing-sm);
            cursor: pointer;
            font-size: 12px;
            border-bottom: 1px solid var(--vscode-panel-border);
        }
        
        .dropdown-item:last-child {
            border-bottom: none;
        }
        
        .dropdown-item:hover {
            background: var(--vscode-list-hoverBackground);
        }
        
        .dropdown-item.selected {
            background: var(--vscode-list-activeSelectionBackground);
            color: var(--vscode-list-activeSelectionForeground);
        }
        
        .mcp-btn {
            background: none;
            border: 1px solid var(--vscode-panel-border);
            border-radius: var(--border-radius-sm);
            color: var(--vscode-foreground);
            padding: 2px 4px;
            font-size: 11px;
            cursor: pointer;
            width: 24px;
            height: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .mcp-btn:hover {
            background: var(--vscode-toolbar-hoverBackground);
        }
        
        /* Main chat area */
        .chat-container {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        .messages-container {
            flex: 1;
            overflow-y: auto;
            padding: var(--spacing-md);
            display: flex;
            flex-direction: column;
            gap: var(--spacing-lg);
        }
        
        /* Message styling */
        .message {
            display: flex;
            flex-direction: column;
            max-width: 100%;
        }
        
        .message.user {
            align-items: flex-end;
        }
        
        .message.assistant {
            align-items: flex-start;
        }
        
        .message-header {
            display: flex;
            align-items: center;
            gap: var(--spacing-xs);
            margin-bottom: var(--spacing-xs);
            font-size: 11px;
            color: var(--vscode-descriptionForeground);
        }
        
        .message-avatar {
            width: 16px;
            height: 16px;
            border-radius: 50%;
            font-size: 8px;
            font-weight: 600;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .message.user .message-avatar {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
        }
        
        .message.assistant .message-avatar {
            background: linear-gradient(135deg, #007ACC 0%, #0099CC 100%);
            color: white;
        }
        
        .message-content {
            max-width: 85%;
            padding: var(--spacing-md);
            border-radius: var(--border-radius);
            font-size: 13px;
            line-height: 1.5;
            word-wrap: break-word;
            white-space: pre-wrap;
        }
        
        .message.user .message-content {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border-top-right-radius: var(--spacing-xs);
        }
        
        .message.assistant .message-content {
            background: var(--vscode-editor-background);
            border: 1px solid var(--vscode-panel-border);
            border-top-left-radius: var(--spacing-xs);
        }
        
        /* Code blocks */
        .code-block {
            margin: var(--spacing-sm) 0;
            border-radius: var(--border-radius-sm);
            overflow: hidden;
            background: var(--vscode-textCodeBlock-background);
            border: 1px solid var(--vscode-panel-border);
        }
        
        .code-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: var(--spacing-xs) var(--spacing-md);
            background: var(--vscode-tab-inactiveBackground);
            border-bottom: 1px solid var(--vscode-panel-border);
            font-size: 11px;
        }
        
        .code-content {
            padding: var(--spacing-md);
            font-family: var(--vscode-editor-font-family);
            font-size: 12px;
            overflow-x: auto;
        }
        
        /* Action buttons */
        .message-actions {
            display: flex;
            align-items: center;
            gap: var(--spacing-xs);
            margin-top: var(--spacing-xs);
        }
        
        .action-btn {
            padding: var(--spacing-xs) var(--spacing-sm);
            border: 1px solid var(--vscode-button-border);
            border-radius: var(--border-radius-sm);
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
            font-size: 11px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .action-btn:hover {
            background: var(--vscode-button-secondaryHoverBackground);
        }
        
        .action-btn.approve {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
        }
        
        .action-btn.reject {
            background: var(--vscode-inputValidation-errorBackground);
            border-color: var(--vscode-inputValidation-errorBorder);
            color: var(--vscode-inputValidation-errorForeground);
        }
        
        /* Empty state */
        .empty-state {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: var(--spacing-lg);
            color: var(--vscode-descriptionForeground);
        }
        
        .empty-icon {
            font-size: 48px;
            margin-bottom: var(--spacing-lg);
            opacity: 0.6;
        }
        
        .empty-title {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: var(--spacing-sm);
            color: var(--vscode-foreground);
        }
        
        .empty-subtitle {
            font-size: 13px;
            line-height: 1.5;
            max-width: 300px;
        }
        
        .suggested-prompts {
            margin-top: var(--spacing-lg);
            display: flex;
            flex-direction: column;
            gap: var(--spacing-xs);
            width: 100%;
            max-width: 350px;
        }
        
        .suggested-prompt {
            padding: var(--spacing-sm) var(--spacing-md);
            border: 1px solid var(--vscode-panel-border);
            border-radius: var(--border-radius);
            background: var(--vscode-editor-background);
            cursor: pointer;
            transition: all 0.2s;
            font-size: 12px;
            text-align: left;
        }
        
        .suggested-prompt:hover {
            border-color: var(--vscode-focusBorder);
            background: var(--vscode-list-hoverBackground);
        }
        
        /* Thinking indicator */
        .thinking-indicator {
            display: flex;
            align-items: center;
            gap: var(--spacing-sm);
            padding: var(--spacing-md);
            font-size: 12px;
            color: var(--vscode-descriptionForeground);
            font-style: italic;
        }
        
        .typing-animation {
            display: flex;
            gap: 2px;
        }
        
        .typing-dot {
            width: 4px;
            height: 4px;
            background: var(--vscode-descriptionForeground);
            border-radius: 50%;
            animation: typing 1.4s infinite;
        }
        
        .typing-dot:nth-child(2) { animation-delay: 0.2s; }
        .typing-dot:nth-child(3) { animation-delay: 0.4s; }
        
        @keyframes typing {
            0%, 60%, 100% { opacity: 0.3; }
            30% { opacity: 1; }
        }
        
        /* Input area */
        .input-container {
            border-top: 1px solid var(--vscode-panel-border);
            background: var(--vscode-editor-background);
            padding: var(--spacing-md);
            flex-shrink: 0;
        }
        
        .input-wrapper {
            display: flex;
            align-items: flex-end;
            gap: var(--spacing-sm);
            min-height: var(--input-height);
        }
        
        .input-field {
            flex: 1;
            min-height: var(--input-height);
            max-height: 120px;
            padding: var(--spacing-md);
            border: 1px solid var(--vscode-input-border);
            border-radius: var(--border-radius);
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            font-family: var(--vscode-font-family);
            font-size: 13px;
            resize: none;
            outline: none;
            line-height: 1.4;
        }
        
        .input-field:focus {
            border-color: var(--vscode-focusBorder);
        }
        
        .input-field::placeholder {
            color: var(--vscode-input-placeholderForeground);
        }
        
        .input-controls {
            display: flex;
            flex-direction: column;
            gap: var(--spacing-xs);
        }
        
        .send-btn {
            width: var(--input-height);
            height: var(--input-height);
            border: none;
            border-radius: var(--border-radius);
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
            transition: all 0.2s;
        }
        
        .send-btn:hover:not(:disabled) {
            background: var(--vscode-button-hoverBackground);
        }
        
        .send-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            background: var(--vscode-button-secondaryBackground);
        }
        
        .context-btn {
            width: var(--input-height);
            height: 24px;
            border: 1px solid var(--vscode-button-border);
            border-radius: var(--border-radius-sm);
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            transition: all 0.2s;
        }
        
        .context-btn:hover {
            background: var(--vscode-button-secondaryHoverBackground);
        }
        
        .context-btn.active {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
        }
        
        /* Scrollbar styling */
        .messages-container::-webkit-scrollbar {
            width: 8px;
        }
        
        .messages-container::-webkit-scrollbar-track {
            background: transparent;
        }
        
        .messages-container::-webkit-scrollbar-thumb {
            background: var(--vscode-scrollbarSlider-background);
            border-radius: 4px;
        }
        
        .messages-container::-webkit-scrollbar-thumb:hover {
            background: var(--vscode-scrollbarSlider-hoverBackground);
        }
        
        /* Responsive adjustments */
        @media (max-width: 300px) {
            .message-content {
                max-width: 95%;
            }
            
            .header {
                padding: 0 var(--spacing-sm);
            }
            
            .info-bar {
                padding: var(--spacing-xs) var(--spacing-sm);
            }
        }
    </style>
</head>
<body>
    <!-- Header -->
    <div class="header">
        <div class="header-left">
            <div class="agent-icon">A</div>
            <div class="agent-info">
                <div class="agent-name">AEP Professional</div>
                <div class="agent-status">Claude Sonnet 3.5</div>
            </div>
        </div>
        <div class="header-controls">
            <button class="control-btn" id="newSessionBtn" title="New Session">✨</button>
            <button class="control-btn" id="settingsBtn" title="Settings">⚙️</button>
            <button class="control-btn" id="signOutBtn" title="Sign Out">↗️</button>
        </div>
    </div>
    
    <!-- Context Info Bar -->
    <div class="info-bar">
        <div class="context-info">
            <div class="context-item">
                <div class="context-indicator" id="workspaceIndicator"></div>
                <span>Workspace</span>
            </div>
            <div class="context-item">
                <div class="context-indicator inactive" id="contextIndicator"></div>
                <span id="contextCount">Auto Context</span>
            </div>
        </div>
        <div class="model-info">
            <div class="model-selector">
                <button class="model-dropdown-btn" id="modelDropdownBtn">
                    <span id="modelName">Claude Sonnet 3.5</span>
                    <span class="dropdown-arrow">▼</span>
                </button>
                <div class="dropdown-menu" id="modelDropdown">
                    <div class="dropdown-item" data-model="claude-3.5-sonnet">Claude 3.5 Sonnet</div>
                    <div class="dropdown-item" data-model="claude-3-haiku">Claude 3 Haiku</div>
                    <div class="dropdown-item" data-model="gpt-4">GPT-4</div>
                    <div class="dropdown-item" data-model="gpt-4-turbo">GPT-4 Turbo</div>
                    <div class="dropdown-item" data-model="gpt-3.5-turbo">GPT-3.5 Turbo</div>
                </div>
            </div>
            <button class="mcp-btn" id="mcpBtn" title="MCP Servers">🔌</button>
        </div>
    </div>
    
    <!-- Chat Container -->
    <div class="chat-container">
        <div class="messages-container" id="messagesContainer">
            <div class="empty-state" id="emptyState">
                <div class="empty-icon">🤖</div>
                <div class="empty-title">Welcome to AEP Professional</div>
                <div class="empty-subtitle">I'm your AI engineering assistant. I can help with code reviews, debugging, architecture decisions, and development workflows.</div>
                <div class="suggested-prompts">
                    <div class="suggested-prompt" data-prompt="Review the current file for potential improvements">📝 Review current file for improvements</div>
                    <div class="suggested-prompt" data-prompt="Help me debug an issue">🐛 Debug an issue</div>
                    <div class="suggested-prompt" data-prompt="Explain this code">💡 Explain code</div>
                    <div class="suggested-prompt" data-prompt="Suggest tests for this function">🧪 Generate tests</div>
                </div>
            </div>
        </div>
        
        <div class="thinking-indicator" id="thinkingIndicator" style="display: none;">
            <span>AEP is thinking</span>
            <div class="typing-animation">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    </div>
    
    <!-- Input Area -->
    <div class="input-container">
        <div class="input-wrapper">
            <textarea 
                class="input-field" 
                id="messageInput" 
                placeholder="Ask AEP anything about your code..."
                rows="1"
            ></textarea>
            <div class="input-controls">
                <button class="context-btn" id="contextBtn" title="Toggle Auto Context">@</button>
                <button class="send-btn" id="sendBtn" disabled title="Send message">→</button>
            </div>
        </div>
    </div>

    <script>
        // Safely acquire vscode API (handle potential redeclaration)
        window.vscode = window.vscode || acquireVsCodeApi();
        const vscode = window.vscode;
        
        // DOM elements
        const messageInput = document.getElementById('messageInput');
        const sendBtn = document.getElementById('sendBtn');
        const messagesContainer = document.getElementById('messagesContainer');
        const emptyState = document.getElementById('emptyState');
        const thinkingIndicator = document.getElementById('thinkingIndicator');
        const contextBtn = document.getElementById('contextBtn');
        const newSessionBtn = document.getElementById('newSessionBtn');
        const settingsBtn = document.getElementById('settingsBtn');
        const signOutBtn = document.getElementById('signOutBtn');
        const workspaceIndicator = document.getElementById('workspaceIndicator');
        const contextIndicator = document.getElementById('contextIndicator');
        const contextCount = document.getElementById('contextCount');
        const modelSelector = document.getElementById('modelSelector');
        const mcpBtn = document.getElementById('mcpBtn');
        
        // State
        let isSessionActive = false;
        let autoContextEnabled = true;
        let messageCount = 0;
        let currentModel = 'claude-3.5-sonnet';
        
        // Initialize
        updateContextUI();
        updateModelDisplay();
        
        // Auto-resize textarea
        messageInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
            updateSendButton();
        });
        
        // Send on Enter (Shift+Enter for new line)
        messageInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
        
        // Button handlers
        sendBtn.addEventListener('click', sendMessage);
        newSessionBtn.addEventListener('click', () => startNewSession());
        settingsBtn.addEventListener('click', () => vscode.postMessage({ command: 'settings' }));
        signOutBtn.addEventListener('click', () => vscode.postMessage({ command: 'signout' }));
        contextBtn.addEventListener('click', toggleAutoContext);
        
        // Model selector handler
        modelSelector.addEventListener('change', function(e) {
            currentModel = e.target.value;
            vscode.postMessage({ 
                command: 'modelChanged', 
                data: { model: currentModel }
            });
            // Update UI to show selected model
            updateModelDisplay();
        });
        
        // MCP button handler
        mcpBtn.addEventListener('click', function() {
            vscode.postMessage({ command: 'openMCPSettings' });
        });
        
        // Suggested prompts
        document.addEventListener('click', function(e) {
            if (e.target.classList.contains('suggested-prompt')) {
                const prompt = e.target.getAttribute('data-prompt');
                messageInput.value = prompt;
                messageInput.focus();
                updateSendButton();
            }
        });
        
        function updateSendButton() {
            sendBtn.disabled = !messageInput.value.trim();
        }
        
        function sendMessage() {
            const message = messageInput.value.trim();
            if (!message) return;
            
            // Add user message
            addMessage('user', message);
            
            // Clear input
            messageInput.value = '';
            messageInput.style.height = 'auto';
            updateSendButton();
            
            // Hide empty state
            if (emptyState) {
                emptyState.style.display = 'none';
            }
            
            // Show thinking indicator
            showThinking();
            
            // Start session if not active
            if (!isSessionActive) {
                startSession();
            }
            
            // Send to extension
            vscode.postMessage({
                command: 'sendMessage',
                data: { 
                    message: message, 
                    sessionActive: isSessionActive,
                    autoContext: autoContextEnabled
                }
            });
        }
        
        function addMessage(type, content, time = null, actions = null) {
            messageCount++;
            
            const messageEl = document.createElement('div');
            messageEl.className = 'message ' + type;
            
            const avatar = document.createElement('div');
            avatar.className = 'message-avatar';
            avatar.textContent = type === 'user' ? 'U' : 'A';
            
            const header = document.createElement('div');
            header.className = 'message-header';
            header.appendChild(avatar);
            
            const timeEl = document.createElement('span');
            timeEl.textContent = time || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            header.appendChild(timeEl);
            
            const contentEl = document.createElement('div');
            contentEl.className = 'message-content';
            
            // Process content for code blocks and formatting
            if (content.includes('\`\`\`')) {
                contentEl.innerHTML = formatContent(content);
            } else {
                contentEl.textContent = content;
            }
            
            messageEl.appendChild(header);
            messageEl.appendChild(contentEl);
            
            // Add action buttons for assistant messages
            if (type === 'assistant' && actions) {
                const actionsEl = document.createElement('div');
                actionsEl.className = 'message-actions';
                
                actions.forEach(action => {
                    const btn = document.createElement('button');
                    btn.className = 'action-btn ' + action.type;
                    btn.textContent = action.label;
                    btn.onclick = () => handleAction(action);
                    actionsEl.appendChild(btn);
                });
                
                messageEl.appendChild(actionsEl);
            }
            
            messagesContainer.appendChild(messageEl);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
        
        function formatContent(content) {
            // Basic markdown-like formatting for code blocks
            return content
                .replace(/\`\`\`(\w+)?\n([\s\S]*?)\`\`\`/g, (match, lang, code) => {
                    return '<div class="code-block"><div class="code-header"><span>' + (lang || 'Code') + '</span><button class="action-btn" onclick="copyCode(this)">Copy</button></div><div class="code-content">' + escapeHtml(code.trim()) + '</div></div>';
                })
                .replace(/\`([^\`]+)\`/g, '<code>$1</code>');
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function copyCode(btn) {
            const codeContent = btn.closest('.code-block').querySelector('.code-content').textContent;
            navigator.clipboard.writeText(codeContent);
            
            const originalText = btn.textContent;
            btn.textContent = 'Copied!';
            setTimeout(() => {
                btn.textContent = originalText;
            }, 2000);
        }
        
        function showThinking() {
            thinkingIndicator.style.display = 'flex';
        }
        
        function hideThinking() {
            thinkingIndicator.style.display = 'none';
        }
        
        function startSession() {
            isSessionActive = true;
            workspaceIndicator.classList.remove('inactive');
        }
        
        function startNewSession() {
            messagesContainer.innerHTML = '';
            emptyState.style.display = 'flex';
            messagesContainer.appendChild(emptyState);
            isSessionActive = false;
            messageCount = 0;
            workspaceIndicator.classList.add('inactive');
            vscode.postMessage({ command: 'newSession' });
        }
        
        function toggleAutoContext() {
            autoContextEnabled = !autoContextEnabled;
            updateContextUI();
            vscode.postMessage({ command: 'toggleContext', data: { enabled: autoContextEnabled } });
        }
        
        function updateContextUI() {
            if (autoContextEnabled) {
                contextBtn.classList.add('active');
                contextIndicator.classList.remove('inactive');
                contextCount.textContent = 'Auto Context';
            } else {
                contextBtn.classList.remove('active');
                contextIndicator.classList.add('inactive');
                contextCount.textContent = 'Manual Context';
            }
        }
        
        function handleAction(action) {
            vscode.postMessage({
                command: 'messageAction',
                data: action
            });
        }
        
        function updateModelDisplay() {
            // Update the model selector display to show current model
            const selectedOption = modelSelector.querySelector('option[value="' + currentModel + '"]');
            if (selectedOption) {
                modelSelector.value = currentModel;
            }
        }
        
        // Handle messages from extension
        window.addEventListener('message', event => {
            const message = event.data;
            
            switch (message.command) {
                case 'addMessage':
                    hideThinking();
                    addMessage('assistant', message.data.content, message.data.time, message.data.actions);
                    break;
                    
                case 'error':
                    hideThinking();
                    addMessage('assistant', '❌ ' + message.data.error);
                    break;
                    
                case 'updateContext':
                    contextCount.textContent = message.data.count + ' files';
                    break;
                    
                case 'sessionStarted':
                    startSession();
                    break;
            }
        });
    </script>
</body>
</html>`;
    }
}
exports.ModernChatInterface = ModernChatInterface;
//# sourceMappingURL=ModernChatInterface.js.map