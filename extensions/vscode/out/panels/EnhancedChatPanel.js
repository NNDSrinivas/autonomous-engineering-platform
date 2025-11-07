"use strict";
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
exports.EnhancedChatPanel = void 0;
const vscode = __importStar(require("vscode"));
const http_1 = require("../utils/http");
class EnhancedChatPanel {
    constructor(panel, extensionUri) {
        this._disposables = [];
        this._chatState = { messages: [] };
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
                case 'approveStep':
                    await this._handleStepApproval(message.taskId, message.stepId, true);
                    break;
                case 'rejectStep':
                    await this._handleStepApproval(message.taskId, message.stepId, false);
                    break;
                case 'selectJiraTask':
                    await this.startAutonomousCoding(message.jiraKey);
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
        }, null, this._disposables);
        // Initialize with smart greeting
        this._initializeWithGreeting();
    }
    /**
     * Creates a new panel or shows the existing one
     * @param extensionUri - VS Code extension URI for resource loading
     * @returns The EnhancedChatPanel instance (either new or existing)
     */
    static createOrShow(extensionUri) {
        const column = vscode.ViewColumn.Beside;
        if (EnhancedChatPanel.currentPanel) {
            EnhancedChatPanel.currentPanel._panel.reveal(column);
            return EnhancedChatPanel.currentPanel;
        }
        const panel = vscode.window.createWebviewPanel('aepEnhancedChat', 'AEP Agent', column, {
            enableScripts: true,
            localResourceRoots: [extensionUri],
            retainContextWhenHidden: true
        });
        EnhancedChatPanel.currentPanel = new EnhancedChatPanel(panel, extensionUri);
        return EnhancedChatPanel.currentPanel;
    }
    async startAutonomousCoding(jiraKey) {
        // Show loading indicator
        this._showTypingIndicator('Analyzing task and gathering context...');
        try {
            // Create task from JIRA with full context
            const response = await (0, http_1.compatibleFetch)(`${this._apiBase}/api/autonomous/create-from-jira`, {
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
        }
        catch (error) {
            this._hideTypingIndicator();
            this._addMessage({
                id: `error-${Date.now()}`,
                type: 'system',
                content: `Sorry, I couldn't analyze that task. Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
                timestamp: new Date()
            });
        }
    }
    async _initializeWithGreeting() {
        const timeOfDay = this._getTimeOfDay();
        const userName = await this._getUserName();
        // Show smart greeting
        const greetingMessage = {
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
    async _loadJiraTasks() {
        try {
            const response = await (0, http_1.compatibleFetch)(`${this._apiBase}/api/jira/tasks`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            if (response.ok) {
                const tasksResponse = await response.json();
                // TODO: Standardize API response format on backend to use single property name
                // Currently supporting both 'tasks' and 'items' for backward compatibility
                const tasksList = 'tasks' in tasksResponse ? tasksResponse.tasks : tasksResponse.items;
                await this._presentJiraTasks(tasksList);
            }
        }
        catch (error) {
            console.error('Failed to load JIRA tasks:', error);
        }
    }
    async _presentJiraTasks(tasks) {
        if (tasks.length === 0) {
            const noTasksMessage = {
                id: `no-tasks-${Date.now()}`,
                type: 'system',
                content: 'You have no assigned tasks today. Great job staying on top of everything! 🎉',
                timestamp: new Date()
            };
            this._addMessage(noTasksMessage);
            return;
        }
        const tasksMessage = {
            id: `tasks-${Date.now()}`,
            type: 'task-presentation',
            content: `You have ${tasks.length} assigned task${tasks.length > 1 ? 's' : ''} today:`,
            timestamp: new Date(),
            metadata: {
                actions: tasks.map(task => ({
                    id: `select-${task.key}`,
                    label: `${task.key}: ${task.summary}`,
                    style: 'secondary',
                    action: 'selectJiraTask'
                }))
            }
        };
        this._addMessage(tasksMessage);
    }
    async _presentTaskOverview(taskData) {
        this._hideTypingIndicator();
        const overviewMessage = {
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
    _formatTaskOverview(taskData) {
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
${context.related_files.map((file) => `- \`${file}\``).join('\n')}

### 📚 Documentation
${context.documentation_links.map((link) => `- [Documentation](${link})`).join('\n')}

### 💬 Meeting Context
${context.meeting_insights || 'No recent discussions found'}

### 🔄 Next Steps Preview
${taskData.steps_preview.map((step, i) => `${i + 1}. **${step.operation}** \`${step.file}\` - ${step.description}`).join('\n')}

---

${taskData.next_action}
    `.trim();
    }
    async _handleStepApproval(taskId, stepId, approved) {
        this._showTypingIndicator(`${approved ? 'Executing' : 'Skipping'} step...`);
        try {
            const response = await (0, http_1.compatibleFetch)(`${this._apiBase}/api/autonomous/execute-step`, {
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
            }
            else {
                this._addMessage({
                    id: `step-error-${Date.now()}`,
                    type: 'system',
                    content: `❌ Step failed: ${result.error}`,
                    timestamp: new Date()
                });
            }
        }
        catch (error) {
            this._hideTypingIndicator();
            this._addMessage({
                id: `error-${Date.now()}`,
                type: 'system',
                content: `Error executing step: ${error instanceof Error ? error.message : 'Unknown error'}`,
                timestamp: new Date()
            });
        }
    }
    async _openFilePreview(filePath) {
        try {
            const uri = vscode.Uri.file(filePath);
            await vscode.window.showTextDocument(uri, { viewColumn: vscode.ViewColumn.Beside });
        }
        catch (error) {
            vscode.window.showErrorMessage(`Could not open file: ${filePath}`);
        }
    }
    async _showDiffPreview(filePath, changes) {
        try {
            // Use workspace storage for temp files to avoid permission issues
            const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
            if (!workspaceFolder) {
                vscode.window.showErrorMessage('No workspace folder found for diff preview');
                return;
            }
            // Create temp file in workspace's .vscode directory
            const tempUri = vscode.Uri.joinPath(workspaceFolder.uri, '.vscode', 'temp-diff.diff');
            const edit = new vscode.WorkspaceEdit();
            edit.createFile(tempUri, { overwrite: true });
            edit.insert(tempUri, new vscode.Position(0, 0), changes);
            await vscode.workspace.applyEdit(edit);
            await vscode.window.showTextDocument(tempUri, { viewColumn: vscode.ViewColumn.Beside });
        }
        catch (error) {
            vscode.window.showErrorMessage(`Could not show diff preview: ${error}`);
        }
    }
    _getTimeOfDay() {
        const hour = new Date().getHours();
        if (hour < 12)
            return 'morning';
        if (hour < 17)
            return 'afternoon';
        return 'evening';
    }
    async _getUserName() {
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
        }
        catch (error) {
            // Fallback to generic greeting
        }
        return 'Developer';
    }
    async _initiateDailyWorkflow() {
        const workflowMessage = {
            id: `workflow-${Date.now()}`,
            type: 'system',
            content: '🚀 Let me set up your daily workflow...',
            timestamp: new Date()
        };
        this._addMessage(workflowMessage);
        await this._loadJiraTasks();
    }
    _addMessage(message) {
        this._chatState.messages.push(message);
        this._updateWebview();
    }
    _updateWebview() {
        this._panel.webview.postMessage({
            command: 'updateChat',
            chatState: this._chatState
        });
    }
    _showTypingIndicator(message = 'Thinking...') {
        this._panel.webview.postMessage({
            command: 'showTyping',
            message
        });
    }
    _hideTypingIndicator() {
        this._panel.webview.postMessage({ command: 'hideTyping' });
    }
    async _handleUserMessage(text) {
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
        }
        catch (error) {
            this._hideTypingIndicator();
            this._addMessage({
                id: `error-${Date.now()}`,
                type: 'system',
                content: 'Sorry, I encountered an error processing your request.',
                timestamp: new Date()
            });
        }
    }
    async _generateEnhancedResponse(userInput) {
        try {
            const response = await (0, http_1.compatibleFetch)(`${this._apiBase}/api/chat/enhanced-respond`, {
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
            }
            else {
                throw new Error(`API error: ${response.status}`);
            }
        }
        catch (error) {
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
    dispose() {
        EnhancedChatPanel.currentPanel = undefined;
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
    <title>AEP Agent - Autonomous Engineering Platform</title>
    <style>
        :root {
            --aep-primary: #007ACC;
            --aep-primary-hover: #005A9E;
            --aep-accent: #0D7377;
            --aep-success: #28A745;
            --aep-warning: #FFC107;
            --aep-danger: #DC3545;
            --aep-gradient: linear-gradient(135deg, #007ACC 0%, #0D7377 100%);
            --aep-card-bg: rgba(255, 255, 255, 0.05);
            --aep-border-radius: 12px;
            --aep-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
            --aep-shadow-hover: 0 8px 24px rgba(0, 0, 0, 0.25);
        }

        * {
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
            padding: 0;
            margin: 0;
            height: 100vh;
            display: flex;
            flex-direction: column;
            background: var(--vscode-editor-background);
            color: var(--vscode-editor-foreground);
            line-height: 1.6;
            overflow: hidden;
        }

        .header {
            background: var(--aep-gradient);
            padding: 16px 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: var(--aep-shadow);
            position: relative;
            overflow: hidden;
        }

        .header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse"><path d="M 10 0 L 0 0 0 10" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="0.5"/></pattern></defs><rect width="100" height="100" fill="url(%23grid)"/></svg>');
            pointer-events: none;
        }

        .header-content {
            position: relative;
            z-index: 1;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo {
            width: 32px;
            height: 32px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: white;
            font-size: 14px;
            backdrop-filter: blur(10px);
        }

        .header-title {
            flex: 1;
        }

        .header-title h1 {
            margin: 0;
            font-size: 18px;
            font-weight: 600;
            color: white;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
        }

        .header-title p {
            margin: 0;
            font-size: 12px;
            color: rgba(255, 255, 255, 0.8);
            font-weight: 400;
        }

        .status-indicator {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--aep-success);
            animation: pulse 2s infinite;
            box-shadow: 0 0 0 0 rgba(40, 167, 69, 0.7);
        }

        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(40, 167, 69, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(40, 167, 69, 0); }
            100% { box-shadow: 0 0 0 0 rgba(40, 167, 69, 0); }
        }

        .welcome-screen {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 40px 20px;
            text-align: center;
            background: radial-gradient(ellipse at center, rgba(0, 122, 204, 0.05) 0%, transparent 70%);
        }

        .welcome-icon {
            width: 80px;
            height: 80px;
            background: var(--aep-gradient);
            border-radius: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 24px;
            box-shadow: var(--aep-shadow);
            animation: float 3s ease-in-out infinite;
        }

        .welcome-icon::after {
            content: '🤖';
            font-size: 36px;
        }

        @keyframes float {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-10px); }
        }

        .welcome-title {
            font-size: 28px;
            font-weight: 700;
            margin: 0 0 12px 0;
            background: var(--aep-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .welcome-subtitle {
            font-size: 16px;
            color: var(--vscode-descriptionForeground);
            margin: 0 0 32px 0;
            max-width: 400px;
            line-height: 1.5;
        }

        .feature-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
            width: 100%;
            max-width: 600px;
        }

        .feature-card {
            background: var(--aep-card-bg);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: var(--aep-border-radius);
            padding: 20px;
            text-align: left;
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
        }

        .feature-card:hover {
            transform: translateY(-2px);
            box-shadow: var(--aep-shadow-hover);
            border-color: var(--aep-primary);
        }

        .feature-icon {
            font-size: 24px;
            margin-bottom: 12px;
            display: block;
        }

        .feature-title {
            font-size: 14px;
            font-weight: 600;
            margin: 0 0 8px 0;
            color: var(--vscode-editor-foreground);
        }

        .feature-desc {
            font-size: 12px;
            color: var(--vscode-descriptionForeground);
            margin: 0;
            line-height: 1.4;
        }

        .chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            display: none;
            flex-direction: column;
            gap: 16px;
        }

        .chat-container.active {
            display: flex;
        }

        .message {
            max-width: 85%;
            padding: 16px 20px;
            border-radius: 18px;
            word-wrap: break-word;
            position: relative;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            animation: messageSlide 0.3s ease-out;
        }

        @keyframes messageSlide {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .message.user {
            align-self: flex-end;
            background: var(--aep-gradient);
            color: white;
            border-bottom-right-radius: 6px;
        }

        .message.assistant, .message.system {
            align-self: flex-start;
            background: var(--aep-card-bg);
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-bottom-left-radius: 6px;
        }

        .message.task-presentation {
            align-self: stretch;
            max-width: 100%;
            background: linear-gradient(135deg, rgba(0, 122, 204, 0.1) 0%, rgba(13, 115, 119, 0.1) 100%);
            border: 1px solid var(--aep-primary);
            border-left: 4px solid var(--aep-primary);
        }

        .message.progress {
            align-self: stretch;
            max-width: 100%;
            background: linear-gradient(135deg, rgba(40, 167, 69, 0.1) 0%, rgba(255, 193, 7, 0.1) 100%);
            border: 1px solid var(--aep-success);
            color: var(--aep-success);
        }

        .actions {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 16px;
        }

        .action-button {
            padding: 10px 16px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
            transition: all 0.2s ease;
            backdrop-filter: blur(10px);
            position: relative;
            overflow: hidden;
        }

        .action-button::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
            transition: left 0.5s;
        }

        .action-button:hover::before {
            left: 100%;
        }

        .action-button.primary {
            background: var(--aep-gradient);
            color: white;
            box-shadow: 0 2px 8px rgba(0, 122, 204, 0.3);
        }

        .action-button.primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0, 122, 204, 0.4);
        }

        .action-button.secondary {
            background: var(--aep-card-bg);
            color: var(--vscode-editor-foreground);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        .action-button.secondary:hover {
            background: rgba(255, 255, 255, 0.1);
            border-color: var(--aep-primary);
        }

        .action-button.danger {
            background: linear-gradient(135deg, var(--aep-danger), #c82333);
            color: white;
        }

        .cta-button {
            background: var(--aep-gradient);
            color: white;
            border: none;
            border-radius: 12px;
            padding: 16px 32px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: var(--aep-shadow);
            position: relative;
            overflow: hidden;
        }

        .cta-button::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
            transition: left 0.5s;
        }

        .cta-button:hover {
            transform: translateY(-2px);
            box-shadow: var(--aep-shadow-hover);
        }

        .cta-button:hover::before {
            left: 100%;
        }

        .input-container {
            padding: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            background: var(--aep-card-bg);
            backdrop-filter: blur(10px);
            display: none;
        }

        .input-container.active {
            display: block;
        }

        .input-wrapper {
            display: flex;
            gap: 12px;
            align-items: flex-end;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 4px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: all 0.3s ease;
        }

        .input-wrapper:focus-within {
            border-color: var(--aep-primary);
            box-shadow: 0 0 0 2px rgba(0, 122, 204, 0.2);
        }

        .message-input {
            flex: 1;
            padding: 12px 16px;
            border: none;
            background: transparent;
            color: var(--vscode-editor-foreground);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            font-size: 14px;
            resize: none;
            min-height: 20px;
            max-height: 120px;
            outline: none;
            line-height: 1.4;
        }

        .message-input::placeholder {
            color: rgba(255, 255, 255, 0.5);
        }

        .send-button {
            padding: 12px 16px;
            background: var(--aep-gradient);
            color: white;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            font-weight: 600;
            font-size: 14px;
            transition: all 0.2s ease;
            box-shadow: 0 2px 8px rgba(0, 122, 204, 0.3);
        }

        .send-button:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0, 122, 204, 0.4);
        }

        .send-button:disabled {
            opacity: 0.5;
            transform: none;
            cursor: not-allowed;
        }

        .typing-indicator {
            align-self: flex-start;
            padding: 16px 20px;
            background: var(--aep-card-bg);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 18px;
            font-style: italic;
            opacity: 0.9;
            animation: pulse 1.5s infinite;
            backdrop-filter: blur(10px);
        }

        .typing-indicator::before {
            content: '💭 ';
            margin-right: 8px;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 0.8; }
            50% { opacity: 0.4; }
        }
        
        .markdown h2 {
            color: var(--aep-primary);
            margin: 20px 0 12px 0;
            font-weight: 600;
            font-size: 18px;
        }
        
        .markdown h3 {
            color: var(--vscode-textLink-foreground);
            margin: 16px 0 8px 0;
            font-weight: 500;
            font-size: 16px;
        }
        
        .markdown code {
            background: rgba(255, 255, 255, 0.1);
            padding: 3px 6px;
            border-radius: 6px;
            font-family: 'SF Mono', 'Monaco', 'Cascadia Code', monospace;
            font-size: 13px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .markdown pre {
            background: rgba(0, 0, 0, 0.3);
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .markdown ul {
            margin-left: 20px;
            padding: 0;
        }
        
        .markdown li {
            margin: 4px 0;
            padding-left: 4px;
        }
        
        .markdown strong {
            font-weight: 600;
            color: var(--aep-primary);
        }
        
        .markdown a {
            color: var(--aep-primary);
            text-decoration: none;
            border-bottom: 1px solid transparent;
            transition: border-color 0.2s ease;
        }
        
        .markdown a:hover {
            border-bottom-color: var(--aep-primary);
        }
        
        .quick-actions {
            margin-top: 20px;
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            justify-content: center;
        }
        
        .quick-action {
            background: var(--aep-card-bg);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 12px 20px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 14px;
            font-weight: 500;
            backdrop-filter: blur(10px);
            min-width: 140px;
            text-align: center;
        }
        
        .quick-action:hover {
            transform: translateY(-2px);
            border-color: var(--aep-primary);
            box-shadow: 0 4px 16px rgba(0, 122, 204, 0.2);
        }
        
        .quick-action .icon {
            display: block;
            font-size: 20px;
            margin-bottom: 8px;
        }
        
        .scrollbar-container {
            scrollbar-width: thin;
            scrollbar-color: rgba(255, 255, 255, 0.2) transparent;
        }
        
        .scrollbar-container::-webkit-scrollbar {
            width: 6px;
        }
        
        .scrollbar-container::-webkit-scrollbar-track {
            background: transparent;
        }
        
        .scrollbar-container::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 3px;
        }
        
        .scrollbar-container::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.3);
        }
        
        .beta-badge {
            background: linear-gradient(135deg, var(--aep-warning), #e0a800);
            color: white;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 10px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .fade-in {
            animation: fadeIn 0.5s ease-out;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .shimmer {
            background: linear-gradient(90deg, rgba(255,255,255,0.1) 25%, rgba(255,255,255,0.2) 50%, rgba(255,255,255,0.1) 75%);
            background-size: 200% 100%;
            animation: shimmer 2s infinite;
        }
        
        @keyframes shimmer {
            0% { background-position: -200% 0; }
            100% { background-position: 200% 0; }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <div class="logo">AEP</div>
            <div class="header-title">
                <h1>Autonomous Engineering Platform</h1>
                <p>AI-Powered Development Assistant <span class="beta-badge">Beta</span></p>
            </div>
            <div class="status-indicator"></div>
        </div>
    </div>

    <div class="welcome-screen" id="welcomeScreen">
        <div class="welcome-icon"></div>
        <h1 class="welcome-title">Good morning! Welcome to AEP Agent</h1>
        <p class="welcome-subtitle">
            Your AI-powered development assistant is ready to help with enterprise-grade tasks, 
            intelligent code generation, and seamless JIRA integration.
        </p>

        <div class="feature-grid">
            <div class="feature-card">
                <span class="feature-icon">🎯</span>
                <h3 class="feature-title">Smart Task Management</h3>
                <p class="feature-desc">Seamlessly integrate with JIRA and track your development tasks with AI assistance</p>
            </div>
            <div class="feature-card">
                <span class="feature-icon">⚡</span>
                <h3 class="feature-title">Autonomous Coding</h3>
                <p class="feature-desc">Generate, review, and implement code changes with intelligent planning and execution</p>
            </div>
            <div class="feature-card">
                <span class="feature-icon">🔍</span>
                <h3 class="feature-title">Context-Aware Analysis</h3>
                <p class="feature-desc">Deep understanding of your codebase with enterprise-level security and compliance</p>
            </div>
        </div>

        <div class="quick-actions">
            <div class="quick-action" onclick="startChat()">
                <span class="icon">💬</span>
                <span>Start Conversation</span>
            </div>
            <div class="quick-action" onclick="loadJiraTasks()">
                <span class="icon">📋</span>
                <span>Load JIRA Tasks</span>
            </div>
            <div class="quick-action" onclick="showPlanMode()">
                <span class="icon">🚀</span>
                <span>Plan & Execute</span>
            </div>
        </div>

        <button class="cta-button" onclick="startChat()">
            Get Started →
        </button>
    </div>

    <div class="chat-container scrollbar-container" id="chatContainer">
        <!-- Messages will be inserted here -->
    </div>

    <div class="input-container" id="inputContainer">
        <div class="input-wrapper">
            <textarea 
                class="message-input" 
                id="messageInput" 
                placeholder="Describe what you'd like me to help you with..."
                rows="1"
            ></textarea>
            <button class="send-button" id="sendButton">
                <span id="sendButtonText">Send</span>
            </button>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        let chatState = { messages: [] };
        let isTyping = false;
        
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

            chatState.messages.forEach((message, index) => {
                setTimeout(() => {
                    const messageEl = createMessageElement(message);
                    messageEl.classList.add('fade-in');
                    container.appendChild(messageEl);
                    container.scrollTop = container.scrollHeight;
                }, index * 100);
            });
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
                case 'loadJira':
                    vscode.postMessage({ command: 'loadJiraTasks' });
                    break;
                case 'startPlanning':
                    vscode.postMessage({ command: 'startPlanning' });
                    break;
                case 'analyzeCode':
                    vscode.postMessage({ command: 'analyzeCode' });
                    break;
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
                .replace(/\`\`\`([\s\S]*?)\`\`\`/g, '<pre><code>$1</code></pre>')
                .replace(/\`(.*?)\`/g, '<code>$1</code>')
                .replace(/^- (.*$)/gm, '<li>$1</li>')
                .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
                .replace(/\\n/g, '<br>');
        }
        
        function showTypingIndicator(message) {
            hideTypingIndicator();
            const container = document.getElementById('chatContainer');
            const indicator = document.createElement('div');
            indicator.className = 'typing-indicator fade-in';
            indicator.id = 'typingIndicator';
            indicator.textContent = message;
            container.appendChild(indicator);
            container.scrollTop = container.scrollHeight;
            isTyping = true;
            updateSendButton();
        }
        
        function hideTypingIndicator() {
            const indicator = document.getElementById('typingIndicator');
            if (indicator) {
                indicator.remove();
            }
            isTyping = false;
            updateSendButton();
        }
        
        function sendMessage() {
            const input = document.getElementById('messageInput');
            const text = input.value.trim();
            if (text && !isTyping) {
                vscode.postMessage({ command: 'sendMessage', text });
                input.value = '';
                autoResize();
            }
        }

        function autoResize() {
            const input = document.getElementById('messageInput');
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 120) + 'px';
        }

        function updateSendButton() {
            const button = document.getElementById('sendButton');
            const text = document.getElementById('sendButtonText');
            if (isTyping) {
                button.disabled = true;
                text.textContent = '...';
            } else {
                button.disabled = false;
                text.textContent = 'Send';
            }
        }

        function startChat() {
            document.getElementById('welcomeScreen').style.display = 'none';
            document.getElementById('chatContainer').classList.add('active');
            document.getElementById('inputContainer').classList.add('active');
            
            // Add welcome message
            if (chatState.messages.length === 0) {
                const welcomeMessage = {
                    id: 'welcome',
                    type: 'assistant',
                    content: \`## 👋 Hello! I'm your AEP Agent

I'm here to help you with:
- **JIRA task management** and intelligent planning
- **Autonomous coding** with step-by-step execution  
- **Code analysis** and enterprise-grade solutions
- **Architecture decisions** and best practices

What would you like to work on today?\`,
                    timestamp: new Date(),
                    metadata: {
                        actions: [
                            { id: 'jira', label: '📋 Load JIRA Tasks', style: 'primary', action: 'loadJira' },
                            { id: 'plan', label: '🚀 Plan & Execute', style: 'secondary', action: 'startPlanning' },
                            { id: 'analyze', label: '🔍 Analyze Code', style: 'secondary', action: 'analyzeCode' }
                        ]
                    }
                };
                chatState.messages = [welcomeMessage];
                renderChat();
            }
            
            document.getElementById('messageInput').focus();
        }

        function loadJiraTasks() {
            vscode.postMessage({ command: 'loadJiraTasks' });
            startChat();
        }

        function showPlanMode() {
            vscode.postMessage({ command: 'showPlanMode' });
            startChat();
        }

        // Event listeners
        document.getElementById('sendButton').onclick = sendMessage;

        const messageInput = document.getElementById('messageInput');
        messageInput.onkeydown = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        };

        messageInput.oninput = autoResize;

        // Initialize
        window.addEventListener('load', () => {
            document.getElementById('messageInput').focus();
        });
    </script>
</body>
</html>`;
    }
}
exports.EnhancedChatPanel = EnhancedChatPanel;
//# sourceMappingURL=EnhancedChatPanel.js.map