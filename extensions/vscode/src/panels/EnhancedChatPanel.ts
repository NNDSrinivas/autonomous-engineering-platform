/**
 * Enhanced Chat Panel - Cline-style autonomous coding interface
 * 
 * Features:
 * - Morning greeting with JIRA tasks
 * - Step-by-step coding workflow
 * - File preview and diff visualization
 * - Real-time progress tracking
 * - Enterprise context integration
 */

import * as vscode from 'vscode';
import * as path from 'path';

interface EnhancedChatMessage {
  id: string;
  type: 'user' | 'assistant' | 'system' | 'task-presentation' | 'step-approval' | 'progress';
  content: string;
  timestamp: Date;
  metadata?: {
    taskId?: string;
    stepId?: string;
    fileChanges?: FileChange[];
    diffPreview?: string;
    actions?: ActionButton[];
    jiraContext?: JiraTaskContext;
  };
}

interface JiraTaskContext {
  key: string;
  title: string;
  description: string;
  priority: string;
  assignee: string;
  meetingContext: string[];
  documentationLinks: string[];
  relatedFiles: string[];
}

interface FileChange {
  path: string;
  operation: 'create' | 'modify' | 'delete';
  preview: string;
  reasoning: string;
}

interface ActionButton {
  id: string;
  label: string;
  style: 'primary' | 'secondary' | 'danger';
  action: string;
}

interface CodingStep {
  id: string;
  description: string;
  status: 'pending' | 'in-progress' | 'completed' | 'failed';
  fileChanges: FileChange[];
  userApproved?: boolean;
}

export class EnhancedChatPanel {
  public static currentPanel: EnhancedChatPanel | undefined;
  private readonly _panel: vscode.WebviewPanel;
  private _disposables: vscode.Disposable[] = [];
  private _chatState: {
    messages: EnhancedChatMessage[];
    currentTask?: JiraTaskContext;
    currentSteps?: CodingStep[];
    userContext?: any;
  } = { messages: [] };
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
          case 'approveStep':
            await this._handleStepApproval(message.taskId, message.stepId, true);
            break;
          case 'rejectStep':
            await this._handleStepApproval(message.taskId, message.stepId, false);
            break;
          case 'selectJiraTask':
            await this._handleJiraTaskSelection(message.jiraKey);
            break;
          case 'viewFile':
            await this._openFilePreview(message.filePath);
            break;
          case 'viewDiff':
            await this._showDiffPreview(message.filePath, message.changes);
            break;
          case 'startDailyWorkflow':
            await this._initiateDailyWorkflow();
            break;
        }
      },
      null,
      this._disposables
    );

    // Initialize with smart greeting
    this._initializeWithGreeting();
  }

  public static createOrShow(extensionUri: vscode.Uri) {
    const column = vscode.ViewColumn.Beside;

    if (EnhancedChatPanel.currentPanel) {
      EnhancedChatPanel.currentPanel._panel.reveal(column);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      'aepEnhancedChat',
      'AEP Agent',
      column,
      {
        enableScripts: true,
        localResourceRoots: [extensionUri],
        retainContextWhenHidden: true
      }
    );

    EnhancedChatPanel.currentPanel = new EnhancedChatPanel(panel, extensionUri);
  }

  private async _initializeWithGreeting() {
    const timeOfDay = this._getTimeOfDay();
    const userName = await this._getUserName();
    
    // Show smart greeting
    const greetingMessage: EnhancedChatMessage = {
      id: `greeting-${Date.now()}`,
      type: 'system',
      content: `Good ${timeOfDay}, ${userName}! 🌟`,
      timestamp: new Date(),
      metadata: {
        actions: [
          {
            id: 'daily-workflow',
            label: 'Show My Tasks',
            style: 'primary',
            action: 'startDailyWorkflow'
          },
          {
            id: 'quick-help',
            label: 'Quick Help',
            style: 'secondary',
            action: 'showHelp'
          }
        ]
      }
    };

    this._addMessage(greetingMessage);
    
    // Auto-load JIRA tasks
    await this._loadJiraTasks();
  }

  private async _loadJiraTasks() {
    try {
      const response = await fetch(`${this._apiBase}/api/jira/tasks`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });

      if (response.ok) {
        const tasks = await response.json();
        await this._presentJiraTasks(tasks.items || []);
      }
    } catch (error) {
      console.error('Failed to load JIRA tasks:', error);
    }
  }

  private async _presentJiraTasks(tasks: any[]) {
    if (tasks.length === 0) {
      const noTasksMessage: EnhancedChatMessage = {
        id: `no-tasks-${Date.now()}`,
        type: 'system',
        content: 'You have no assigned tasks today. Great job staying on top of everything! 🎉',
        timestamp: new Date()
      };
      this._addMessage(noTasksMessage);
      return;
    }

    const tasksMessage: EnhancedChatMessage = {
      id: `tasks-${Date.now()}`,
      type: 'task-presentation',
      content: `You have ${tasks.length} assigned task${tasks.length > 1 ? 's' : ''} today:`,
      timestamp: new Date(),
      metadata: {
        actions: tasks.map(task => ({
          id: `select-${task.key}`,
          label: `${task.key}: ${task.summary}`,
          style: 'secondary' as const,
          action: 'selectJiraTask'
        }))
      }
    };

    this._addMessage(tasksMessage);
  }

  private async _handleJiraTaskSelection(jiraKey: string) {
    // Show loading indicator
    this._showTypingIndicator('Analyzing task and gathering context...');

    try {
      // Create task from JIRA with full context
      const response = await fetch(`${this._apiBase}/api/autonomous/create-from-jira`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jira_key: jiraKey,
          user_context: this._chatState.userContext
        })
      });

      if (!response.ok) {
        throw new Error(`Failed to create task: ${response.status}`);
      }

      const taskData = await response.json();
      
      // Present comprehensive task overview
      await this._presentTaskOverview(taskData);

    } catch (error) {
      this._hideTypingIndicator();
      this._addMessage({
        id: `error-${Date.now()}`,
        type: 'system',
        content: `Sorry, I couldn't analyze that task. Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        timestamp: new Date()
      });
    }
  }

  private async _presentTaskOverview(taskData: any) {
    this._hideTypingIndicator();

    const overviewMessage: EnhancedChatMessage = {
      id: `task-overview-${Date.now()}`,
      type: 'task-presentation',
      content: this._formatTaskOverview(taskData),
      timestamp: new Date(),
      metadata: {
        taskId: taskData.task.id,
        jiraContext: {
          key: taskData.task.jira_key,
          title: taskData.task.title,
          description: taskData.task.description,
          priority: taskData.context.priority || 'Medium',
          assignee: taskData.context.assignee || 'You',
          meetingContext: taskData.context.meeting_insights ? [taskData.context.meeting_insights] : [],
          documentationLinks: taskData.context.documentation_links || [],
          relatedFiles: taskData.context.related_files || []
        },
        actions: [
          {
            id: 'approve-plan',
            label: 'Start Implementation',
            style: 'primary',
            action: 'approvePlan'
          },
          {
            id: 'modify-plan',
            label: 'Modify Plan',
            style: 'secondary',
            action: 'modifyPlan'
          },
          {
            id: 'view-files',
            label: 'View Related Files',
            style: 'secondary',
            action: 'viewRelatedFiles'
          }
        ]
      }
    };

    this._addMessage(overviewMessage);
  }

  private _formatTaskOverview(taskData: any): string {
    const task = taskData.task;
    const context = taskData.context;
    const plan = taskData.implementation_plan;

    return `
## 📋 ${task.title}

**JIRA:** ${task.jira_key}  
**Type:** ${task.type}  
**Priority:** ${context.priority || 'Medium'}

### 📝 Description
${task.description}

### 🎯 Implementation Plan
- **Total Steps:** ${plan.total_steps}
- **Estimated Duration:** ${plan.estimated_duration}
- **Files to Modify:** ${plan.files_to_modify.length}
- **Git Branch:** \`${plan.git_branch}\`

### 📁 Related Files
${context.related_files.map((file: string) => `- \`${file}\``).join('\n')}

### 📚 Documentation
${context.documentation_links.map((link: string) => `- [Documentation](${link})`).join('\n')}

### 💬 Meeting Context
${context.meeting_insights || 'No recent discussions found'}

### 🔄 Next Steps Preview
${taskData.steps_preview.map((step: any, i: number) => `${i + 1}. **${step.operation}** \`${step.file}\` - ${step.description}`).join('\n')}

---

${taskData.next_action}
    `.trim();
  }

  private async _handleStepApproval(taskId: string, stepId: string, approved: boolean) {
    this._showTypingIndicator(`${approved ? 'Executing' : 'Skipping'} step...`);

    try {
      const response = await fetch(`${this._apiBase}/api/autonomous/execute-step`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_id: taskId,
          step_id: stepId,
          user_approved: approved
        })
      });

      const result = await response.json();
      this._hideTypingIndicator();

      if (result.status === 'completed') {
        this._addMessage({
          id: `step-result-${Date.now()}`,
          type: 'progress',
          content: `✅ Step completed: ${result.step}\n\nFile: \`${result.file_path}\`\n\n${result.next_step ? `**Next:** ${result.next_step.description}` : '🎉 All steps completed!'}`,
          timestamp: new Date(),
          metadata: {
            actions: result.next_step ? [
              {
                id: 'approve-next',
                label: 'Approve Next Step',
                style: 'primary',
                action: 'approveStep'
              },
              {
                id: 'review-changes',
                label: 'Review Changes',
                style: 'secondary',
                action: 'viewDiff'
              }
            ] : [
              {
                id: 'create-pr',
                label: 'Create Pull Request',
                style: 'primary',
                action: 'createPR'
              }
            ]
          }
        });
      } else {
        this._addMessage({
          id: `step-error-${Date.now()}`,
          type: 'system',
          content: `❌ Step failed: ${result.error}`,
          timestamp: new Date()
        });
      }

    } catch (error) {
      this._hideTypingIndicator();
      this._addMessage({
        id: `error-${Date.now()}`,
        type: 'system',
        content: `Error executing step: ${error instanceof Error ? error.message : 'Unknown error'}`,
        timestamp: new Date()
      });
    }
  }

  private async _openFilePreview(filePath: string) {
    try {
      const uri = vscode.Uri.file(filePath);
      await vscode.window.showTextDocument(uri, { viewColumn: vscode.ViewColumn.Beside });
    } catch (error) {
      vscode.window.showErrorMessage(`Could not open file: ${filePath}`);
    }
  }

  private async _showDiffPreview(filePath: string, changes: string) {
    try {
      // Create temporary diff file
      const tempUri = vscode.Uri.file(path.join(__dirname, 'temp-diff.diff'));
      const edit = new vscode.WorkspaceEdit();
      edit.createFile(tempUri, { overwrite: true });
      edit.insert(tempUri, new vscode.Position(0, 0), changes);
      
      await vscode.workspace.applyEdit(edit);
      await vscode.window.showTextDocument(tempUri, { viewColumn: vscode.ViewColumn.Beside });
    } catch (error) {
      vscode.window.showErrorMessage(`Could not show diff preview`);
    }
  }

  private _getTimeOfDay(): string {
    const hour = new Date().getHours();
    if (hour < 12) return 'morning';
    if (hour < 17) return 'afternoon';
    return 'evening';
  }

  private async _getUserName(): Promise<string> {
    // Try to get user name from git config or workspace
    try {
      const gitExtension = vscode.extensions.getExtension('vscode.git');
      if (gitExtension) {
        const git = gitExtension.exports.getAPI(1);
        const repo = git.repositories[0];
        if (repo) {
          const config = await repo.getConfig('user.name');
          if (config) {
            return config.split(' ')[0]; // First name only
          }
        }
      }
    } catch (error) {
      // Fallback to generic greeting
    }
    
    return 'Developer';
  }

  private async _initiateDailyWorkflow() {
    const workflowMessage: EnhancedChatMessage = {
      id: `workflow-${Date.now()}`,
      type: 'system',
      content: '🚀 Let me set up your daily workflow...',
      timestamp: new Date()
    };

    this._addMessage(workflowMessage);
    await this._loadJiraTasks();
  }

  private _addMessage(message: EnhancedChatMessage) {
    this._chatState.messages.push(message);
    this._updateWebview();
  }

  private _updateWebview() {
    this._panel.webview.postMessage({
      command: 'updateChat',
      chatState: this._chatState
    });
  }

  private _showTypingIndicator(message: string = 'Thinking...') {
    this._panel.webview.postMessage({ 
      command: 'showTyping',
      message 
    });
  }

  private _hideTypingIndicator() {
    this._panel.webview.postMessage({ command: 'hideTyping' });
  }

  private async _handleUserMessage(text: string) {
    // Add user message
    this._addMessage({
      id: `user-${Date.now()}`,
      type: 'user',
      content: text,
      timestamp: new Date()
    });

    // Show typing indicator
    this._showTypingIndicator();

    try {
      // Enhanced response generation with enterprise context
      const response = await this._generateEnhancedResponse(text);
      
      this._hideTypingIndicator();
      this._addMessage({
        id: `assistant-${Date.now()}`,
        type: 'assistant',
        content: response.content,
        timestamp: new Date(),
        metadata: response.metadata
      });

    } catch (error) {
      this._hideTypingIndicator();
      this._addMessage({
        id: `error-${Date.now()}`,
        type: 'system',
        content: 'Sorry, I encountered an error processing your request.',
        timestamp: new Date()
      });
    }
  }

  private async _generateEnhancedResponse(userInput: string): Promise<{content: string, metadata?: any}> {
    try {
      const response = await fetch(`${this._apiBase}/api/chat/enhanced-respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userInput,
          context: {
            currentTask: this._chatState.currentTask,
            userContext: this._chatState.userContext,
            conversationHistory: this._chatState.messages.slice(-5)
          }
        })
      });

      if (response.ok) {
        return await response.json();
      } else {
        throw new Error(`API error: ${response.status}`);
      }
    } catch (error) {
      // Fallback to basic response
      return {
        content: "I'm here to help with your development work. Try asking about your JIRA tasks or let me help you implement a feature!",
        metadata: {
          actions: [
            {
              id: 'show-tasks',
              label: 'Show My Tasks',
              style: 'primary',
              action: 'startDailyWorkflow'
            }
          ]
        }
      };
    }
  }

  public dispose() {
    EnhancedChatPanel.currentPanel = undefined;
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
    <title>AEP Agent - Enhanced</title>
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
            gap: 16px;
        }
        
        .message {
            max-width: 85%;
            padding: 16px;
            border-radius: 12px;
            word-wrap: break-word;
            position: relative;
        }
        
        .message.user {
            align-self: flex-end;
            background-color: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
        }
        
        .message.assistant, .message.system {
            align-self: flex-start;
            background-color: var(--vscode-input-background);
            border: 1px solid var(--vscode-input-border);
        }
        
        .message.task-presentation {
            align-self: stretch;
            max-width: 100%;
            background-color: var(--vscode-textBlockQuote-background);
            border-left: 4px solid var(--vscode-button-background);
        }
        
        .message.progress {
            align-self: stretch;
            max-width: 100%;
            background-color: var(--vscode-badge-background);
            color: var(--vscode-badge-foreground);
        }
        
        .actions {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 12px;
        }
        
        .action-button {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.9em;
            font-weight: 500;
            transition: all 0.2s;
        }
        
        .action-button.primary {
            background-color: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
        }
        
        .action-button.primary:hover {
            background-color: var(--vscode-button-hoverBackground);
        }
        
        .action-button.secondary {
            background-color: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
            border: 1px solid var(--vscode-button-border);
        }
        
        .action-button.secondary:hover {
            background-color: var(--vscode-button-secondaryHoverBackground);
        }
        
        .action-button.danger {
            background-color: var(--vscode-errorBackground);
            color: var(--vscode-errorForeground);
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
        
        .typing-indicator {
            align-self: flex-start;
            padding: 12px 16px;
            background-color: var(--vscode-input-background);
            border: 1px solid var(--vscode-input-border);
            border-radius: 12px;
            font-style: italic;
            opacity: 0.8;
            animation: pulse 1.5s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 0.8; }
            50% { opacity: 0.4; }
        }
        
        .markdown h2 {
            color: var(--vscode-textPreformat-foreground);
            margin-top: 16px;
            margin-bottom: 8px;
        }
        
        .markdown h3 {
            color: var(--vscode-textLink-foreground);
            margin-top: 12px;
            margin-bottom: 6px;
        }
        
        .markdown code {
            background-color: var(--vscode-textCodeBlock-background);
            padding: 2px 4px;
            border-radius: 3px;
            font-family: var(--vscode-editor-font-family);
        }
        
        .markdown ul {
            margin-left: 16px;
        }
        
        .markdown strong {
            font-weight: 600;
            color: var(--vscode-textPreformat-foreground);
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
            placeholder="Ask me about your tasks, or let me help you implement something..."
            rows="1"
        ></textarea>
        <button class="send-button" id="sendButton">Send</button>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        let chatState = { messages: [] };
        
        window.addEventListener('message', event => {
            const message = event.data;
            switch (message.command) {
                case 'updateChat':
                    chatState = message.chatState;
                    renderChat();
                    break;
                case 'showTyping':
                    showTypingIndicator(message.message || 'Thinking...');
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
            
            container.scrollTop = container.scrollHeight;
        }
        
        function createMessageElement(message) {
            const messageEl = document.createElement('div');
            messageEl.className = \`message \${message.type}\`;
            
            const contentEl = document.createElement('div');
            contentEl.className = 'markdown';
            contentEl.innerHTML = formatMarkdown(message.content);
            messageEl.appendChild(contentEl);
            
            if (message.metadata && message.metadata.actions) {
                const actionsEl = document.createElement('div');
                actionsEl.className = 'actions';
                
                message.metadata.actions.forEach(action => {
                    const buttonEl = document.createElement('button');
                    buttonEl.className = \`action-button \${action.style}\`;
                    buttonEl.textContent = action.label;
                    buttonEl.onclick = () => handleAction(action, message.metadata);
                    actionsEl.appendChild(buttonEl);
                });
                
                messageEl.appendChild(actionsEl);
            }
            
            return messageEl;
        }
        
        function handleAction(action, metadata) {
            switch (action.action) {
                case 'startDailyWorkflow':
                    vscode.postMessage({ command: 'startDailyWorkflow' });
                    break;
                case 'selectJiraTask':
                    const jiraKey = action.id.replace('select-', '');
                    vscode.postMessage({ command: 'selectJiraTask', jiraKey });
                    break;
                case 'approveStep':
                    vscode.postMessage({ 
                        command: 'approveStep', 
                        taskId: metadata.taskId, 
                        stepId: metadata.stepId 
                    });
                    break;
                case 'rejectStep':
                    vscode.postMessage({ 
                        command: 'rejectStep', 
                        taskId: metadata.taskId, 
                        stepId: metadata.stepId 
                    });
                    break;
                case 'viewFile':
                    vscode.postMessage({ 
                        command: 'viewFile', 
                        filePath: action.filePath 
                    });
                    break;
                case 'viewDiff':
                    vscode.postMessage({ 
                        command: 'viewDiff', 
                        filePath: action.filePath,
                        changes: action.changes 
                    });
                    break;
            }
        }
        
        function formatMarkdown(text) {
            return text
                .replace(/^### (.*$)/gm, '<h3>$1</h3>')
                .replace(/^## (.*$)/gm, '<h2>$1</h2>')
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\`(.*?)\`/g, '<code>$1</code>')
                .replace(/^- (.*$)/gm, '<li>$1</li>')
                .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
                .replace(/\\n/g, '<br>');
        }
        
        function showTypingIndicator(message) {
            hideTypingIndicator();
            const container = document.getElementById('chatContainer');
            const indicator = document.createElement('div');
            indicator.className = 'typing-indicator';
            indicator.id = 'typingIndicator';
            indicator.textContent = message;
            container.appendChild(indicator);
            container.scrollTop = container.scrollHeight;
        }
        
        function hideTypingIndicator() {
            const indicator = document.getElementById('typingIndicator');
            if (indicator) {
                indicator.remove();
            }
        }
        
        function sendMessage() {
            const input = document.getElementById('messageInput');
            const text = input.value.trim();
            if (text) {
                vscode.postMessage({ command: 'sendMessage', text });
                input.value = '';
                input.style.height = 'auto';
            }
        }
        
        document.getElementById('sendButton').onclick = sendMessage;
        
        const messageInput = document.getElementById('messageInput');
        messageInput.onkeydown = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        };
        
        messageInput.oninput = () => {
            messageInput.style.height = 'auto';
            messageInput.style.height = messageInput.scrollHeight + 'px';
        };
    </script>
</body>
</html>`;
  }
}