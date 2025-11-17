"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
// src/extension.ts
const vscode = require("vscode");
const path = require("path");
const diffUtils_1 = require("./diffUtils");
// PR-4: Storage keys for persistent model/mode selection
const STORAGE_KEYS = {
    modelId: 'aep.navi.modelId',
    modelLabel: 'aep.navi.modelLabel',
    modeId: 'aep.navi.modeId',
    modeLabel: 'aep.navi.modeLabel',
};
// Defaults if nothing stored yet
const DEFAULT_MODEL = {
    id: 'gpt-5.1',
    label: 'ChatGPT 5.1',
};
const DEFAULT_MODE = {
    id: 'agent-full',
    label: 'Agent (full access)',
};
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
        this._agentActions = new Map(); // PR-6: Track agent actions
        this._currentModelId = DEFAULT_MODEL.id;
        this._currentModelLabel = DEFAULT_MODEL.label;
        this._currentModeId = DEFAULT_MODE.id;
        this._currentModeLabel = DEFAULT_MODE.label;
        this._extensionUri = extensionUri;
        this._context = context;
        this._conversationId = generateConversationId();
        // PR-4: Load persisted model/mode from storage
        this._currentModelId = context.globalState.get(STORAGE_KEYS.modelId) ?? DEFAULT_MODEL.id;
        this._currentModelLabel = context.globalState.get(STORAGE_KEYS.modelLabel) ?? DEFAULT_MODEL.label;
        this._currentModeId = context.globalState.get(STORAGE_KEYS.modeId) ?? DEFAULT_MODE.id;
        this._currentModeLabel = context.globalState.get(STORAGE_KEYS.modeLabel) ?? DEFAULT_MODE.label;
    }
    resolveWebviewView(webviewView, _context, _token) {
        this._view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri]
        };
        webviewView.webview.html = this.getWebviewHtml(webviewView.webview);
        // PR-4: Hydrate model/mode state from storage after webview loads
        webviewView.webview.onDidReceiveMessage(async (msg) => {
            try {
                switch (msg.type) {
                    case 'ready': {
                        // Send hydration message first
                        this.postToWebview({
                            type: 'hydrateState',
                            modelId: this._currentModelId,
                            modelLabel: this._currentModelLabel,
                            modeId: this._currentModeId,
                            modeLabel: this._currentModeLabel,
                        });
                        // Then send welcome message
                        this.postToWebview({
                            type: 'botMessage',
                            text: "Hello! I'm **NAVI**, your autonomous engineering assistant.\n\nI can help you with:\n\n- Code explanations and reviews\n- Refactoring and testing\n- Documentation generation\n- Engineering workflow automation\n\nHow can I help you today?"
                        });
                        break;
                    }
                    case 'sendMessage': {
                        const text = String(msg.text || '').trim();
                        if (!text) {
                            return;
                        }
                        // PR-4: Use modelId and modeId from the message (coming from pills)
                        const modelId = msg.modelId || this._currentModelId;
                        const modeId = msg.modeId || this._currentModeId;
                        // PR-5: Extract attachments if present
                        const attachments = msg.attachments || [];
                        console.log('[Extension Host] [AEP] User message:', text, 'model:', modelId, 'mode:', modeId, 'attachments:', attachments.length);
                        // Update local state
                        this._messages.push({ role: 'user', content: text });
                        // Show thinking state
                        this.postToWebview({ type: 'botThinking', value: true });
                        await this.callNaviBackend(text, modelId, modeId, attachments);
                        break;
                    }
                    case 'requestAttachment': {
                        // PR-5: Handle file attachment requests
                        await this.handleAttachmentRequest(webviewView.webview, msg.kind);
                        break;
                    }
                    case 'agent.applyAction': {
                        // PR-7: Apply agent-proposed action (create/edit/run)
                        await this.handleAgentApplyAction(msg);
                        break;
                    }
                    case 'agent.applyEdit': {
                        // PR-6: Apply agent-proposed edit (legacy support)
                        await this.handleApplyAgentEdit(msg);
                        break;
                    }
                    case 'agent.rejectEdit': {
                        // PR-6: User rejected agent edit (no-op for now, could log or notify)
                        console.log('[Extension Host] [AEP] User rejected agent edit:', msg);
                        break;
                    }
                    case 'setModel': {
                        // PR-4: Persist model selection
                        const { modelId, modelLabel } = msg;
                        if (!modelId || !modelLabel)
                            return;
                        this._currentModelId = modelId;
                        this._currentModelLabel = modelLabel;
                        this._context.globalState.update(STORAGE_KEYS.modelId, modelId);
                        this._context.globalState.update(STORAGE_KEYS.modelLabel, modelLabel);
                        console.log('[Extension Host] [AEP] Model changed to:', modelId, modelLabel);
                        break;
                    }
                    case 'setMode': {
                        // PR-4: Persist mode selection
                        const { modeId, modeLabel } = msg;
                        if (!modeId || !modeLabel)
                            return;
                        this._currentModeId = modeId;
                        this._currentModeLabel = modeLabel;
                        this._context.globalState.update(STORAGE_KEYS.modeId, modeId);
                        this._context.globalState.update(STORAGE_KEYS.modeLabel, modeLabel);
                        console.log('[Extension Host] [AEP] Mode changed to:', modeId, modeLabel);
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
                    case 'pickAttachment':
                    case 'attachBtnClicked': {
                        console.log('[Extension Host] [AEP] Attachment button clicked - showing not implemented message');
                        // For now, just tell the webview this is not implemented yet.
                        this.postToWebview({ type: 'attachmentNotImplemented' });
                        break;
                    }
                    /* Keep the old attachment handling code commented out for future implementation
                    case 'pickAttachment_FUTURE': {
                      console.log('[Extension Host] [AEP] Webview requested attachment picker');
          
                      // Open file picker for attachments
                      const uris = await vscode.window.showOpenDialog({
                        openLabel: 'Attach to NAVI chat',
                        canSelectMany: true,
                        canSelectFiles: true,
                        canSelectFolders: false,
                        filters: {
                          'Code & Text': ['ts', 'tsx', 'js', 'jsx', 'java', 'cs', 'py', 'go', 'rb', 'php', 'cpp', 'c', 'h', 'json', 'yml', 'yaml', 'md', 'txt'],
                          'All Files': ['*']
                        }
                      });
          
                      if (!uris || uris.length === 0) {
                        console.log('[Extension Host] [AEP] Attachment picker canceled');
                        this.postToWebview({ type: 'attachmentsCanceled' });
                        return;
                      }
          
                      // Map to lightweight metadata objects the webview can render as chips
                      const files = await Promise.all(
                        uris.map(async (uri) => {
                          let size = 0;
                          try {
                            const stat = await vscode.workspace.fs.stat(uri);
                            size = stat.size ?? 0;
                          } catch {
                            // ignore stat failures, size stays 0
                          }
          
                          return {
                            name: path.basename(uri.fsPath),
                            uri: uri.toString(),
                            size
                          };
                        })
                      );
          
                      console.log('[Extension Host] [AEP] Selected attachments:', files);
          
                      this.postToWebview({
                        type: 'attachmentsSelected',
                        files
                      });
                      break;
                    }
                    */
                    case 'commandSelected': {
                        // Map the menu item -> suggested prompt
                        const cmd = String(msg.command || '');
                        let prompt = '';
                        switch (cmd) {
                            case 'jira-task-brief':
                                // Fetch Jira tasks from backend
                                await this.handleJiraTaskBriefCommand();
                                return;
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
                    case 'jiraTaskSelected': {
                        // User selected a Jira task - fetch full brief
                        const jiraKey = String(msg.jiraKey || '').trim();
                        if (!jiraKey)
                            return;
                        await this.handleJiraTaskSelected(jiraKey);
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
    // --- Jira task brief handlers ----------------------------------------------
    async handleJiraTaskBriefCommand() {
        if (!this._view) {
            return;
        }
        try {
            const config = vscode.workspace.getConfiguration('aep');
            const baseUrl = config.get('navi.backendUrl') || 'http://127.0.0.1:8787';
            const userId = config.get('navi.userId') || 'srinivas@example.com';
            // Remove /api/navi/chat suffix if present
            const cleanBaseUrl = baseUrl.replace(/\/api\/navi\/chat$/, '');
            const url = `${cleanBaseUrl}/api/navi/jira-tasks?user_id=${encodeURIComponent(userId)}&limit=20`;
            console.log('[Extension Host] [AEP] Fetching Jira tasks from:', url);
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            if (!response.ok) {
                vscode.window.showErrorMessage(`NAVI: Failed to load Jira tasks (${response.status})`);
                return;
            }
            const data = await response.json();
            // Send tasks to webview
            this.postToWebview({
                type: 'showJiraTasks',
                tasks: data.tasks || []
            });
        }
        catch (error) {
            console.error('[Extension Host] [AEP] Error fetching Jira tasks:', error);
            vscode.window.showErrorMessage('NAVI: Error loading Jira tasks');
        }
    }
    async handleJiraTaskSelected(jiraKey) {
        if (!this._view) {
            return;
        }
        try {
            const config = vscode.workspace.getConfiguration('aep');
            const baseUrl = config.get('navi.backendUrl') || 'http://127.0.0.1:8787';
            const userId = config.get('navi.userId') || 'srinivas@example.com';
            // Remove /api/navi/chat suffix if present
            const cleanBaseUrl = baseUrl.replace(/\/api\/navi\/chat$/, '');
            const url = `${cleanBaseUrl}/api/navi/task-brief`;
            console.log('[Extension Host] [AEP] Fetching task brief for:', jiraKey);
            // Show thinking state
            this.postToWebview({ type: 'botThinking', value: true });
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    user_id: userId,
                    jira_key: jiraKey
                })
            });
            if (!response.ok) {
                vscode.window.showErrorMessage(`NAVI: Failed to load brief for ${jiraKey} (${response.status})`);
                this.postToWebview({ type: 'botThinking', value: false });
                return;
            }
            const data = await response.json();
            // Extract the brief markdown from the sections
            const briefMd = data.sections?.[0]?.content || data.summary || 'No brief content available';
            // Send as a bot message
            this.postToWebview({
                type: 'botMessage',
                text: briefMd,
                actions: []
            });
            this.postToWebview({ type: 'botThinking', value: false });
        }
        catch (error) {
            console.error('[Extension Host] [AEP] Error fetching task brief:', error);
            vscode.window.showErrorMessage('NAVI: Error fetching task brief');
            this.postToWebview({ type: 'botThinking', value: false });
        }
    }
    // --- Core: call NAVI backend ------------------------------------------------
    async callNaviBackend(latestUserText, modelId, modeId, attachments) {
        if (!this._view) {
            return;
        }
        // PR-6B: New simplified request format
        const payload = {
            message: latestUserText,
            model: modelId || this._currentModelId,
            mode: modeId || this._currentModeId,
            attachments: attachments && attachments.length > 0 ? attachments : []
        };
        let response;
        try {
            // Read backend URL from configuration with fallback
            const config = vscode.workspace.getConfiguration('aep');
            const backendUrl = config.get('navi.backendUrl') || 'http://127.0.0.1:8787/api/navi/chat';
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
                // PR-6B: Handle new response format
                const json = (await response.json());
                const content = (json.content || '').trim();
                if (!content) {
                    console.warn('[Extension Host] [AEP] Empty content from NAVI backend.');
                    this.postToWebview({
                        type: 'error',
                        text: '⚠️ NAVI backend returned empty content.'
                    });
                    return;
                }
                this._messages.push({ role: 'assistant', content: content });
                // PR-6C: Handle agent actions if present
                const messageId = `msg-${Date.now()}`;
                if (json.actions && json.actions.length > 0) {
                    this._agentActions.set(messageId, { actions: json.actions });
                    this.postToWebview({
                        type: 'botMessage',
                        text: content,
                        messageId: messageId,
                        actions: json.actions
                    });
                }
                else {
                    this.postToWebview({ type: 'botMessage', text: content });
                }
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
            text: "🔄 **New chat started!**\n\nHow can I help you today?"
        });
    }
    // PR-5: Handle attachment requests from the webview
    async handleAttachmentRequest(webview, kind) {
        const editor = vscode.window.activeTextEditor;
        try {
            if (kind === 'selection' && editor && !editor.selection.isEmpty) {
                // Read selected text
                const selectedText = editor.document.getText(editor.selection);
                const filePath = editor.document.uri.fsPath;
                this.postToWebview({
                    type: 'addAttachment',
                    attachment: {
                        kind: 'selection',
                        path: filePath,
                        content: selectedText,
                    },
                });
            }
            else if (kind === 'current-file' && editor) {
                // Read entire active file
                const content = editor.document.getText();
                const filePath = editor.document.uri.fsPath;
                this.postToWebview({
                    type: 'addAttachment',
                    attachment: {
                        kind: 'file',
                        path: filePath,
                        content: content,
                    },
                });
            }
            else if (kind === 'pick-file') {
                // Show file picker
                const uris = await vscode.window.showOpenDialog({
                    canSelectFiles: true,
                    canSelectFolders: false,
                    canSelectMany: false,
                    openLabel: 'Attach File',
                });
                if (uris && uris.length > 0) {
                    const uri = uris[0];
                    const content = await vscode.workspace.fs.readFile(uri);
                    const textContent = new TextDecoder('utf-8').decode(content);
                    this.postToWebview({
                        type: 'addAttachment',
                        attachment: {
                            kind: 'file',
                            path: uri.fsPath,
                            content: textContent,
                        },
                    });
                }
            }
        }
        catch (err) {
            console.error('[Extension Host] [AEP] Error reading attachment:', err);
            vscode.window.showErrorMessage('Failed to read file for attachment.');
        }
    }
    // PR-7: Apply agent action from new unified message format
    async handleAgentApplyAction(message) {
        const { decision, actionIndex, actions } = message;
        if (decision !== 'approve') {
            // For now we don't need to do anything on reject
            console.log('[Extension Host] [AEP] User rejected action');
            return;
        }
        if (!actions || actionIndex == null || !Number.isInteger(actionIndex) || actionIndex < 0 || actionIndex >= actions.length) {
            console.warn('[Extension Host] [AEP] Invalid action data:', { actionIndex, actionsLength: actions?.length });
            return;
        }
        const action = actions[actionIndex];
        if (!action || !action.type) {
            console.warn('[Extension Host] [AEP] Invalid action object:', action);
            return;
        }
        try {
            console.log('[Extension Host] [AEP] Applying agent action:', action);
            // 1) Create new file
            if (action.type === 'createFile') {
                await this.applyCreateFileAction(action);
                return;
            }
            // 2) Edit existing file with diff
            if (action.type === 'editFile') {
                await this.applyEditFileAction(action);
                return;
            }
            // 3) Run terminal command
            if (action.type === 'runCommand') {
                await this.applyRunCommandAction(action);
                return;
            }
            console.warn('[Extension Host] [AEP] Unknown action type:', action.type);
        }
        catch (error) {
            console.error('[Extension Host] [AEP] Error applying action:', error);
            vscode.window.showErrorMessage(`Failed to apply action: ${error.message}`);
        }
    }
    async applyCreateFileAction(action) {
        const fileName = action.filePath ?? 'sample.js';
        const content = action.content ?? '// Sample generated by NAVI\nconsole.log("Hello, World!");\n';
        const folders = vscode.workspace.workspaceFolders;
        const editor = vscode.window.activeTextEditor;
        // 1) Best case: have a workspace folder → create under that root
        if (folders && folders.length > 0) {
            const root = folders[0].uri;
            await this.createFileUnderRoot(root, fileName, content);
            return;
        }
        // 2) No workspace, but we DO have a saved active file → ask to use its folder
        if (editor && !editor.document.isUntitled) {
            this.postBotStatus("I don't see a workspace folder open. I can still create the sample file if you tell me where it should live.");
            const choice = await vscode.window.showQuickPick([
                {
                    label: '$(file) Create next to current file',
                    description: editor.document.uri.fsPath,
                    id: 'here',
                },
                {
                    label: '$(folder) Choose another folder…',
                    id: 'pick',
                },
                {
                    label: '$(x) Cancel',
                    id: 'cancel',
                },
            ], {
                placeHolder: 'Where should I create the sample file?',
                title: 'NAVI - Create Sample File',
            });
            if (!choice || choice.id === 'cancel') {
                this.postBotStatus('No problem! Let me know if you need anything else.');
                return;
            }
            if (choice.id === 'here') {
                const dir = vscode.Uri.joinPath(editor.document.uri, '..');
                await this.createFileUnderRoot(dir, fileName, content);
                return;
            }
            // fall through to folder picker below
        }
        // 3) No workspace AND no saved active file → let user pick any folder
        this.postBotStatus("I don't see a workspace folder open. Please pick a folder where I should create the sample file.");
        const picked = await vscode.window.showOpenDialog({
            canSelectFolders: true,
            canSelectFiles: false,
            canSelectMany: false,
            openLabel: 'Use this folder for the sample file',
            title: 'NAVI - Choose Folder for Sample File',
        });
        if (!picked || picked.length === 0) {
            this.postBotStatus('No problem! Let me know if you need anything else.');
            return;
        }
        const targetRoot = picked[0];
        await this.createFileUnderRoot(targetRoot, fileName, content);
    }
    async createFileUnderRoot(root, relPath, content) {
        // Security: Validate path to prevent traversal attacks
        const path = require('path');
        if (path.isAbsolute(relPath)) {
            vscode.window.showErrorMessage('NAVI: Cannot create file with absolute path');
            return;
        }
        if (relPath.split(/[\\\\/]/).includes('..')) {
            vscode.window.showErrorMessage('NAVI: Cannot create file with path traversal (..)');
            return;
        }
        const fileUri = vscode.Uri.joinPath(root, relPath);
        const resolvedPath = fileUri.fsPath;
        const rootPath = root.fsPath;
        // Ensure the resolved path is within the workspace root
        if (!resolvedPath.startsWith(rootPath)) {
            vscode.window.showErrorMessage('NAVI: Cannot create file outside workspace');
            return;
        }
        // Ensure parent folders exist (best effort)
        const dir = vscode.Uri.joinPath(fileUri, '..');
        try {
            await vscode.workspace.fs.createDirectory(dir);
        }
        catch {
            // ignore if it already exists
        }
        await vscode.workspace.fs.writeFile(fileUri, Buffer.from(content, 'utf8'));
        const doc = await vscode.workspace.openTextDocument(fileUri);
        await vscode.window.showTextDocument(doc);
        vscode.window.setStatusBarMessage(`✅ NAVI: Created ${relPath}`, 3000);
        this.postBotStatus(`✅ Done! I've created \`${relPath}\` at ${fileUri.fsPath}`);
    }
    postBotStatus(text) {
        if (!this._view)
            return;
        this._view.webview.postMessage({
            type: 'botMessage',
            text,
            actions: [],
            messageId: new Date().toISOString(),
        });
    }
    async applyRunCommandAction(action) {
        const command = action.command;
        if (!command)
            return;
        // Security: Show command and ask for confirmation before executing
        const confirmed = await vscode.window.showWarningMessage(`NAVI wants to run the following command:\\n\\n${command}\\n\\nAre you sure?`, { modal: true }, 'Run Command');
        if (confirmed !== 'Run Command')
            return;
        const terminal = vscode.window.createTerminal('NAVI Agent');
        terminal.show();
        terminal.sendText(command);
        vscode.window.showInformationMessage(`🚀 Running: ${command}`);
    }
    // ---- editFile with diff view & apply (PR-10) -------------------------------
    async applyEditFileAction(action) {
        // Backend contract: editFile provides either:
        // - filePath + content (full new file text)   ✅
        // - optionally diff (for explanation), but we don't parse it
        const filePath = action.filePath;
        const newContent = action.content;
        if (!newContent) {
            vscode.window.showWarningMessage('NAVI: editFile action is missing "content"; nothing to apply.');
            return;
        }
        // Resolve target document: use filePath if present, otherwise active editor
        let targetDoc;
        if (filePath) {
            const uri = vscode.Uri.file(filePath);
            try {
                targetDoc = await vscode.workspace.openTextDocument(uri);
            }
            catch {
                vscode.window.showWarningMessage(`NAVI: Target file "${filePath}" does not exist.`);
                return;
            }
        }
        else {
            targetDoc = vscode.window.activeTextEditor?.document;
            if (!targetDoc) {
                vscode.window.showWarningMessage('NAVI: No active file to apply edit to.');
                return;
            }
        }
        const originalText = targetDoc.getText();
        const languageId = targetDoc.languageId;
        // Create a virtual doc for the new content and show a diff
        const newDoc = await vscode.workspace.openTextDocument({
            language: languageId,
            content: newContent,
        });
        const title = `NAVI proposed edit: ${targetDoc.fileName.split(/[\\/]/).pop()}`;
        await vscode.commands.executeCommand('vscode.diff', targetDoc.uri, newDoc.uri, title);
        // Ask user if we should apply the changes to the real file now
        const choice = await vscode.window.showQuickPick([
            { label: '✅ Apply edit to file', id: 'apply' },
            { label: '👁️ Keep diff only', id: 'keep' },
            { label: '❌ Cancel', id: 'cancel' },
        ], {
            placeHolder: 'NAVI has proposed an edit. Do you want to apply it to the real file?',
        });
        if (!choice || choice.id === 'cancel' || choice.id === 'keep') {
            if (choice?.id === 'keep') {
                this.postBotStatus('Diff view kept open for your review.');
            }
            return;
        }
        if (choice.id === 'apply') {
            const edit = new vscode.WorkspaceEdit();
            const fullRange = new vscode.Range(targetDoc.positionAt(0), targetDoc.positionAt(originalText.length));
            edit.replace(targetDoc.uri, fullRange, newContent);
            const success = await vscode.workspace.applyEdit(edit);
            if (success) {
                await targetDoc.save();
                vscode.window.setStatusBarMessage('✅ NAVI: Edit applied.', 3000);
                this.postBotStatus(`✅ Edit applied to ${targetDoc.fileName.split(/[\\/]/).pop()}`);
            }
            else {
                vscode.window.showErrorMessage('NAVI: Failed to apply edit.');
            }
        }
    }
    // PR-6C: Apply agent-proposed edit with diff view support
    async handleApplyAgentEdit(msg) {
        const { messageId, actionIndex } = msg;
        const agentState = this._agentActions.get(messageId);
        if (!agentState) {
            console.warn('[Extension Host] [AEP] No agent actions found for message:', messageId);
            return;
        }
        const action = agentState.actions[actionIndex];
        if (!action) {
            console.warn('[Extension Host] [AEP] Invalid action index:', actionIndex);
            return;
        }
        try {
            console.log('[Extension Host] [AEP] Applying agent action:', action);
            // Get workspace folder for resolving relative paths
            const workspaceFolders = vscode.workspace.workspaceFolders;
            if (!workspaceFolders || workspaceFolders.length === 0) {
                throw new Error('No workspace folder open');
            }
            const workspaceRoot = workspaceFolders[0].uri;
            // Handle different action types
            if (action.type === 'editFile' && action.filePath && action.diff) {
                // PR-6C: Show diff preview for editFile
                await this.showDiffPreviewAndApply(workspaceRoot, action.filePath, action.diff);
            }
            else if (action.type === 'createFile' && action.filePath && action.content) {
                // Create new file
                const fileUri = vscode.Uri.joinPath(workspaceRoot, action.filePath);
                await vscode.workspace.fs.writeFile(fileUri, Buffer.from(action.content, 'utf-8'));
                vscode.window.showInformationMessage(`✅ Created ${action.filePath}`);
                // Open the new file
                const document = await vscode.workspace.openTextDocument(fileUri);
                await vscode.window.showTextDocument(document, { preview: false });
            }
            else if (action.type === 'runCommand' && action.command) {
                // PR-6C: Run terminal command
                const terminal = vscode.window.createTerminal('NAVI Agent');
                terminal.show();
                terminal.sendText(action.command);
                vscode.window.showInformationMessage(`🔧 Running: ${action.command}`);
            }
            else {
                vscode.window.showWarningMessage(`Unknown or incomplete action type: ${action.type}`);
            }
        }
        catch (err) {
            console.error('[Extension Host] [AEP] Error applying agent action:', err);
            vscode.window.showErrorMessage(`Failed to apply action: ${err.message}`);
        }
    }
    // PR-6C: Show diff preview and apply on confirmation
    async showDiffPreviewAndApply(workspaceRoot, filePath, diff) {
        const fileUri = vscode.Uri.joinPath(workspaceRoot, filePath);
        // Read original file
        let originalDoc;
        try {
            originalDoc = await vscode.workspace.openTextDocument(fileUri);
        }
        catch {
            vscode.window.showErrorMessage(`File not found: ${filePath}`);
            return;
        }
        const original = originalDoc.getText();
        // Apply diff to get new content
        let newContent;
        try {
            newContent = (0, diffUtils_1.applyUnifiedDiff)(original, diff);
        }
        catch (error) {
            vscode.window.showErrorMessage(`Failed to apply diff: ${error.message}`);
            return;
        }
        // Create temp file with new content for preview
        const fileName = path.basename(filePath);
        const tempUri = vscode.Uri.parse(`untitled:${fileName} (NAVI Proposed)`);
        const tempDoc = await vscode.workspace.openTextDocument(tempUri);
        const edit = new vscode.WorkspaceEdit();
        edit.insert(tempUri, new vscode.Position(0, 0), newContent);
        await vscode.workspace.applyEdit(edit);
        // Show diff view
        await vscode.commands.executeCommand('vscode.diff', fileUri, tempUri, `NAVI: ${fileName} (Original ↔ Proposed)`);
        // Ask user to confirm
        const choice = await vscode.window.showInformationMessage(`Apply proposed changes to ${fileName}?`, { modal: true }, 'Apply', 'Cancel');
        if (choice === 'Apply') {
            // Apply the changes
            const fullRange = new vscode.Range(originalDoc.positionAt(0), originalDoc.positionAt(original.length));
            const finalEdit = new vscode.WorkspaceEdit();
            finalEdit.replace(fileUri, fullRange, newContent);
            await vscode.workspace.applyEdit(finalEdit);
            await originalDoc.save();
            vscode.window.showInformationMessage(`✅ Applied changes to ${fileName}`);
        }
        else {
            vscode.window.showInformationMessage('Changes discarded');
        }
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