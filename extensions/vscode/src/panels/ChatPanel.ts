/**
 * Chat Panel - Rich conversational interface for AEP Agent
 * 
 * Provides Cline-like chat experience with:
 * - Persistent conversation history
 * - Context-aware responses
 * - Proactive suggestions
 * - Team intelligence integration
 */

import * as vscode from 'vscode';

interface ChatMessage {
  id: string;
  type: 'user' | 'assistant' | 'system' | 'suggestion';
  content: string;
  timestamp: Date;
  context?: {
    taskKey?: string;
    files?: string[];
    suggestions?: string[];
  };
}

interface ChatState {
  messages: ChatMessage[];
  currentTask?: string;
  teamContext?: any;
  proactiveSuggestions?: string[];
}

export class ChatPanel {
  public static currentPanel: ChatPanel | undefined;
  private readonly _panel: vscode.WebviewPanel;
  private _disposables: vscode.Disposable[] = [];
  private _chatState: ChatState = { messages: [] };
  private _apiBase: string;

  private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
    this._panel = panel;
    this._apiBase = vscode.workspace.getConfiguration('aep').get('coreApi') || 'http://localhost:8002';

    // Set webview content
    this._panel.webview.html = this._getWebviewContent(this._panel.webview, extensionUri);

    // Handle messages from webview
    this._panel.webview.onDidReceiveMessage(
      async message => {
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
      },
      null,
      this._disposables
    );

    // Clean up on dispose
    this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

    // Initialize with welcome message
    this._initializeChat();
  }

  public static createOrShow(extensionUri: vscode.Uri) {
    const column = vscode.ViewColumn.Beside;

    // If panel already exists, reveal it
    if (ChatPanel.currentPanel) {
      ChatPanel.currentPanel._panel.reveal(column);
      return;
    }

    // Create new panel
    const panel = vscode.window.createWebviewPanel(
      'aepChat',
      'AEP Agent Chat',
      column,
      {
        enableScripts: true,
        localResourceRoots: [extensionUri],
        retainContextWhenHidden: true
      }
    );

    ChatPanel.currentPanel = new ChatPanel(panel, extensionUri);
  }

  private async _initializeChat() {
    // Load previous chat history if exists
    await this._loadChatHistory();
    
    // Add welcome message with team context
    const welcomeMessage = await this._generateWelcomeMessage();
    this._addMessage({
      id: `msg-${Date.now()}`,
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

  private async _generateWelcomeMessage(): Promise<{ text: string; suggestions: string[] }> {
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
        activeTasks.forEach((task: any, idx: number) => {
          text += `${idx + 1}. **${task.key}**: ${task.summary}\n`;
        });
        text += '\n';
      }

      if (recentActivity.length > 0) {
        text += `🔄 Recent team activity:\n`;
        recentActivity.slice(0, 2).forEach((activity: any) => {
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
    } catch (error) {
      const hr = new Date().getHours();
      const timeOfDay = hr < 12 ? 'morning' : hr < 18 ? 'afternoon' : 'evening';
      return {
        text: `Good ${timeOfDay}! I'm your autonomous engineering assistant. How can I help you today?`,
        suggestions: ['Show me my tasks', 'Help me with current work', 'Generate a plan']
      };
    }
  }

  private async _handleUserMessage(text: string) {
    // Add user message to chat
    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
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
      const assistantMessage: ChatMessage = {
        id: `msg-${Date.now() + 1}`,
        type: 'assistant',
        content: response.content,
        timestamp: new Date(),
        context: response.context
      };
      this._addMessage(assistantMessage);

      // Add proactive suggestions if any
      if (response.suggestions && response.suggestions.length > 0) {
        const suggestionMessage: ChatMessage = {
          id: `msg-${Date.now() + 2}`,
          type: 'suggestion',
          content: 'Here are some things I can help with next:',
          timestamp: new Date(),
          context: { suggestions: response.suggestions }
        };
        this._addMessage(suggestionMessage);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      this._addMessage({
        id: `msg-${Date.now() + 1}`,
        type: 'assistant',
        content: `I encountered an error: ${errorMessage}. Let me try a different approach.`,
        timestamp: new Date()
      });
    } finally {
      this._hideTypingIndicator();
    }
  }

  private async _generateResponse(userInput: string): Promise<{
    content: string;
    context?: any;
    suggestions?: string[];
  }> {
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
    } catch (error) {
      // Fallback to rule-based responses
      return this._generateFallbackResponse(userInput);
    }
  }

  private _generateFallbackResponse(userInput: string): {
    content: string;
    context?: any;
    suggestions?: string[];
  } {
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

  private async _fetchTeamContext(): Promise<any> {
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
    } catch (error) {
      return { tasks: [], recentActivity: [] };
    }
  }

  private async _loadProactiveSuggestions() {
    try {
      // Use memory graph to generate proactive suggestions
      const response = await fetch(`${this._apiBase}/api/suggestions/proactive`, {
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
            id: `proactive-${Date.now()}`,
            type: 'suggestion',
            content: '💡 Based on your recent work, I noticed:',
            timestamp: new Date(),
            context: { suggestions: suggestions.items }
          });
        }
      }
    } catch (error) {
      // Silently fail for proactive suggestions
    }
  }

  private async _getCurrentWorkspaceFiles(): Promise<string[]> {
    try {
      // Use separate patterns for better compatibility
      const patterns = ['**/*.py', '**/*.js', '**/*.ts', '**/*.jsx', '**/*.tsx'];
      const fileArrays = await Promise.all(
        patterns.map(pattern =>
          vscode.workspace.findFiles(pattern, '**/node_modules/**', 10)
        )
      );
      
      // Flatten the arrays and deduplicate
      const files = Array.from(new Set(fileArrays.flat().map(file => file.fsPath)));
      
      // Apply final limit to ensure predictable behavior (max 20 files total)
      return files.slice(0, 20);
    } catch {
      return [];
    }
  }

  private async _getRecentChanges(): Promise<any[]> {
    try {
      // TODO: Implement git integration to get recent changes
      // This would use vscode.extensions.getExtension('vscode.git') API
      // or execute git commands via vscode.workspace.workspaceFolders
      return [];
    } catch {
      return [];
    }
  }

  private _addMessage(message: ChatMessage) {
    this._chatState.messages.push(message);
    this._updateWebview();
    // TODO: Implement chat history persistence
    // this._saveChatHistory();
  }

  private _updateWebview() {
    this._panel.webview.postMessage({
      command: 'updateChat',
      chatState: this._chatState
    });
  }

  private _showTypingIndicator() {
    this._panel.webview.postMessage({ command: 'showTyping' });
  }

  private _hideTypingIndicator() {
    this._panel.webview.postMessage({ command: 'hideTyping' });
  }

  private async _loadChatHistory() {
    // Load from workspace state or file
    // Implementation would depend on persistence strategy
  }

  private async _saveChatHistory() {
    // Save to workspace state or file
    // Implementation would depend on persistence strategy
  }

  private async _loadTeamContext() {
    this._chatState.teamContext = await this._fetchTeamContext();
    this._updateWebview();
  }

  private async _selectTask(taskKey: string) {
    this._chatState.currentTask = taskKey;
    
    // Fetch context pack for selected task
    try {
      const response = await fetch(`${this._apiBase}/api/context/task/${encodeURIComponent(taskKey)}`);
      const contextPack = await response.json();
      
      this._addMessage({
        id: `task-selected-${Date.now()}`,
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
    } catch (error) {
      this._addMessage({
        id: `task-error-${Date.now()}`,
        type: 'assistant',
        content: `I've selected task ${taskKey}, but couldn't load all details. How would you like to proceed?`,
        timestamp: new Date(),
        context: { taskKey }
      });
    }
  }

  private async _handleSuggestionAccepted(suggestion: string) {
    // Handle when user clicks on a suggestion
    await this._handleUserMessage(suggestion);
  }

  public dispose() {
    ChatPanel.currentPanel = undefined;
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
            
            // Format content with basic markdown support
            let content = message.content
                .replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>')
                .replace(/\`(.*?)\`/g, '<code>$1</code>')
                .replace(/\\n/g, '<br>');
            
            messageEl.innerHTML = content;
            
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
                    contextEl.innerHTML = \`<strong>Task:</strong> \${message.context.taskKey}\`;
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