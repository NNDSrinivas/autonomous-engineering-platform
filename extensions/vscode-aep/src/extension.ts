// src/extension.ts
import * as vscode from 'vscode';
import * as path from 'path';
import { applyUnifiedDiff } from './diffUtils';
import { ConnectorsPanel } from './connectorsPanel';

// Perfect Workspace Context Collection
async function collectWorkspaceContext(): Promise<any> {
  const editor = vscode.window.activeTextEditor;

  const workspaceFolders = vscode.workspace.workspaceFolders?.map(f => f.uri.fsPath) ?? [];
  const rootFolder = workspaceFolders.length > 0 ? workspaceFolders[0] : null;

  const activeFile = editor?.document?.fileName ?? null;
  const selectedText = editor?.selection ? editor.document.getText(editor.selection) : null;

  const recentFiles = vscode.workspace.textDocuments.slice(0, 10).map(doc => doc.fileName);

  return {
    workspace_root: rootFolder,
    active_file: activeFile,
    selected_text: selectedText,
    recent_files: recentFiles,
  };
}

type Role = 'user' | 'assistant' | 'system';

interface NaviMessage {
  role: Role;
  content: string;
}

// Intent classification types
type NaviIntent =
  | 'greeting'
  | 'jira_list'
  | 'jira_ticket'
  | 'jira_priority'
  | 'code'
  | 'workspace'
  | 'general'
  | 'other';

// interface IntentResponse {
//   intent: NaviIntent;
// }

// PR-5: File attachment interface for type safety
interface FileAttachment {
  kind: 'selection' | 'currentFile' | 'pickedFile' | 'file';
  path: string;
  language?: string;
  content: string;
}

// interface NaviChatRequest {
//   id: string;
//   model: string;
//   mode: string;
//   messages: NaviMessage[];
//   stream: boolean;
//   attachments?: FileAttachment[]; // PR-5: Strongly-typed file attachments
// }

interface AgentAction {
  type: 'editFile' | 'createFile' | 'runCommand';
  filePath?: string;
  description?: string;
  content?: string;  // For createFile
  diff?: string;     // For editFile
  command?: string;  // For runCommand
}

interface NaviChatResponseJson {
  role: string;
  content: string;
  actions?: AgentAction[]; // PR-6C: Agent-proposed actions
  agentRun?: any; // Present only when real multi-step agent ran
  sources?: Array<{ name: string; type: string; url: string; connector?: string }>; // Sources for provenance
}

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
  id: 'chat-only',
  label: 'Agent (full access)',
};

export function activate(context: vscode.ExtensionContext) {
  const provider = new NaviWebviewProvider(context.extensionUri, context);

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      // Make sure this matches the view id in package.json
      'aep.chatView',
      provider
    )
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('aep.attachSelection', async () => {
      await provider.attachSelectionCommand();
    }),
    vscode.commands.registerCommand('aep.attachCurrentFile', async () => {
      await provider.attachCurrentFileCommand();
    })
  );
}

export function deactivate() {
  // nothing yet
}

class NaviWebviewProvider implements vscode.WebviewViewProvider {
  private _view?: vscode.WebviewView;
  private _extensionUri: vscode.Uri;
  private _context: vscode.ExtensionContext;

  // Conversation state
  private _conversationId: string;
  private _messages: NaviMessage[] = [];
  private _agentActions = new Map<string, { actions: AgentAction[] }>(); // PR-6: Track agent actions
  private _currentModelId: string = DEFAULT_MODEL.id;
  private _currentModelLabel: string = DEFAULT_MODEL.label;
  private _currentModeId: string = DEFAULT_MODE.id;
  private _currentModeLabel: string = DEFAULT_MODE.label;

  // Attachment state
  private _attachments: FileAttachment[] = [];

  constructor(extensionUri: vscode.Uri, context: vscode.ExtensionContext) {
    this._extensionUri = extensionUri;
    this._context = context;
    this._conversationId = generateConversationId();

    // PR-4: Load persisted model/mode from storage
    this._currentModelId = context.globalState.get<string>(STORAGE_KEYS.modelId) ?? DEFAULT_MODEL.id;
    this._currentModelLabel = context.globalState.get<string>(STORAGE_KEYS.modelLabel) ?? DEFAULT_MODEL.label;
    this._currentModeId = context.globalState.get<string>(STORAGE_KEYS.modeId) ?? DEFAULT_MODE.id;
    this._currentModeLabel = context.globalState.get<string>(STORAGE_KEYS.modeLabel) ?? DEFAULT_MODE.label;
  }

  private getBackendBaseUrl(): string {
    const config = vscode.workspace.getConfiguration('aep');
    const raw = (config.get<string>('navi.backendUrl') || 'http://127.0.0.1:8000/api/navi/chat').trim();

    // Turn http://127.0.0.1:8000/api/navi/chat → http://127.0.0.1:8000
    try {
      const url = new URL(raw);
      url.pathname = url.pathname.replace(/\/api\/navi\/chat\/?$/, '');
      url.search = '';
      url.hash = '';
      return url.toString().replace(/\/$/, '');
    } catch {
      return 'http://127.0.0.1:8000';
    }
  }

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ) {
    this._view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri]
    };

    webviewView.webview.html = this.getWebviewHtml(webviewView.webview);

    // PR-4: Hydrate model/mode state from storage after webview loads
    webviewView.webview.onDidReceiveMessage(async (msg: any) => {
      console.log('[AEP] Extension received message:', msg.type);
      try {
        switch (msg.type) {
          case 'openExternal': {
            const url = String(msg.url || '').trim();
            if (!url) return;
            try {
              await vscode.env.openExternal(vscode.Uri.parse(url));
            } catch (e) {
              vscode.window.showErrorMessage('Failed to open external URL');
            }
            break;
          }
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

            // NOTE: Removed automatic Jira sync - now only triggered when user explicitly asks about Jira tasks
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

            // PR-5: Use extension's internal attachments (the authoritative source)
            const attachments = this.getCurrentAttachments();

            console.log('[Extension Host] [AEP] User message:', text, 'model:', modelId, 'mode:', modeId, 'attachments:', attachments.length);
            console.log('[Extension Host] [AEP] About to process message with smart routing:', text);

            // Update local state
            this._messages.push({ role: 'user', content: text });

            // Show thinking state
            this.postToWebview({ type: 'botThinking', value: true });

            console.log('[Extension Host] [AEP] Using smart intent-based routing...');
            await this.handleSmartRouting(text, modelId, modeId, attachments);
            console.log('[Extension Host] [AEP] Smart routing completed');
            break;
          }

          case 'requestAttachment': {
            await this.handleAttachmentRequest(webviewView.webview, msg.kind);
            break;
          }

          case 'agent.applyAction': {
            // PR-7: Apply agent-proposed action (create/edit/run)
            await this.handleAgentApplyAction(msg);
            break;
          }

          case 'agent.applyWorkspacePlan': {
            // New: Apply a full workspace plan (array of AgentAction)
            const actions: AgentAction[] = Array.isArray(msg.actions) ? msg.actions : [];
            await this.applyWorkspacePlan(actions);
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
            if (!modelId || !modelLabel) return;

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
            if (!modeId || !modeLabel) return;

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
            this.clearAttachments();

            // Tell the webview to reset its UI
            this.postToWebview({
              type: 'resetChat',
            });
            break;
          }

          case 'attachClicked': {
            // For now just show that the wiring works.
            // Later we can open a real file/folder pick flow.
            vscode.window.showInformationMessage(
              'Attachment flow is not implemented yet – coming soon in a future release.'
            );
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
            if (!type) return;
            vscode.window.showInformationMessage(
              `Attachment flow for "${type}" is not wired yet – this will open the real picker in a later PR.`
            );
            break;
          }

          case 'jiraTaskSelected': {
            // User selected a Jira task - fetch full brief
            const jiraKey = String(msg.jiraKey || '').trim();
            if (!jiraKey) return;
            await this.handleJiraTaskSelected(jiraKey);
            break;
          }

          case 'showToast': {
            // Display toast notification from webview
            const message = String(msg.message || '').trim();
            const level = String(msg.level || 'info');
            if (!message) return;

            switch (level) {
              case 'error':
                vscode.window.showErrorMessage(`NAVI: ${message}`);
                break;
              case 'warning':
                vscode.window.showWarningMessage(`NAVI: ${message}`);
                break;
              default:
                vscode.window.showInformationMessage(`NAVI: ${message}`);
            }
            break;
          }

          case 'openConnectors': {
            console.log('[AEP] openConnectors message received');
            try {
              // Open the Connectors Hub
              const config = vscode.workspace.getConfiguration('aep');
              const backendUrl = config.get<string>('navi.backendUrl') || 'http://127.0.0.1:8787';
              const cleanBaseUrl = backendUrl.replace(/\/api\/navi\/chat$/, '');

              console.log('[AEP] Opening ConnectorsPanel with baseUrl:', cleanBaseUrl);
              ConnectorsPanel.createOrShow(this._extensionUri);
              console.log('[AEP] ConnectorsPanel.createOrShow completed');
            } catch (err) {
              console.error('[AEP] Error opening ConnectorsPanel:', err);
              vscode.window.showErrorMessage(`Failed to open Connectors: ${err}`);
            }
            break;
          }

          case 'connectors.getStatus': {
            // Proxy connector status request to backend
            try {
              const baseUrl = this.getBackendBaseUrl();
              const response = await fetch(`${baseUrl}/api/connectors/status`, {
                headers: {
                  'X-Org-Id': 'org_aep_platform_4538597546e6fec6',
                },
              });
              if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
              }
              const data = await response.json();
              this.postToWebview({ type: 'connectors.status', data });
            } catch (err: any) {
              console.error('[Extension Host] [AEP] Connectors status error:', err);
              this.postToWebview({
                type: 'connectors.statusError',
                error: err?.message || String(err),
              });
            }
            break;
          }

          case 'connectors.jiraConnect': {
            // Proxy Jira connection request to backend
            try {
              const baseUrl = this.getBackendBaseUrl();
              const endpoint = `${baseUrl}/api/connectors/jira/connect`;

              console.log('[AEP] Jira connect - Backend base URL:', baseUrl);
              console.log('[AEP] Jira connect - Full endpoint:', endpoint);
              console.log('[AEP] Jira connect - Request payload:', {
                base_url: msg.baseUrl,
                email: msg.email || undefined,
                api_token: msg.apiToken ? '***' : undefined
              });

              const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 
                  'Content-Type': 'application/json',
                  'X-Org-Id': 'org_aep_platform_4538597546e6fec6',
                },
                body: JSON.stringify({
                  base_url: msg.baseUrl,
                  email: msg.email || undefined,
                  api_token: msg.apiToken,
                }),
              });

              console.log('[AEP] Jira connect - Response status:', response.status);

              if (!response.ok) {
                const errorText = await response.text().catch(() => '');
                console.error('[AEP] Jira connect - Error response:', errorText);
                throw new Error(errorText || `HTTP ${response.status}: ${response.statusText}`);
              }

              const data = await response.json() as { status?: string;[key: string]: any };
              console.log('[AEP] Jira connect - Success response:', data);

              // Send proper result message
              this.postToWebview({
                type: 'connectors.jiraConnect.result',
                ok: true,
                provider: 'jira',
                status: data.status || 'connected',
                data
              });
            } catch (err: any) {
              console.error('[Extension Host] [AEP] Jira connect error:', err);
              console.error('[AEP] Error stack:', err.stack);

              // Send proper error result message
              this.postToWebview({
                type: 'connectors.jiraConnect.result',
                ok: false,
                provider: 'jira',
                error: err?.message || String(err),
              });

              // Also show a user-friendly error message
              vscode.window.showErrorMessage(
                `NAVI: Jira connection failed: ${err?.message || 'fetch failed'}. Check that backend is running on http://127.0.0.1:8000`
              );
            }
            break;
          }

          case 'connectors.close': {
            console.log('[AEP] Connectors close message received');
            // Hide the connectors modal in the webview
            this.postToWebview({
              type: 'connectors.hide'
            });
            break;
          }

          case 'connectors.jiraSyncNow': {
            try {
              const baseUrl = this.getBackendBaseUrl();
              const endpoint = `${baseUrl}/api/org/sync/jira`;

              console.log('[AEP] Jira sync-now – calling enhanced endpoint', endpoint);

              const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 
                  'Content-Type': 'application/json',
                  'X-Org-Id': 'org_aep_platform_4538597546e6fec6',
                },
                body: JSON.stringify({
                  user_id: 'default_user',
                  max_issues: 20
                })
              });

              if (!response.ok) {
                const errorText = await response.text().catch(() => '');
                console.error('[AEP] Jira sync-now failed', response.status, errorText);
                vscode.window.showErrorMessage(
                  `NAVI: Jira sync failed (${response.status}). Check backend logs.`
                );
                this.postToWebview({
                  type: 'connectors.jiraSyncResult',
                  ok: false,
                  error: `HTTP ${response.status}`,
                });
                return;
              }

              const data = await response.json() as {
                processed_keys?: string[];
                total?: number;
                snapshot_ts?: string;
                success?: boolean;
                [key: string]: any
              };
              console.log('[AEP] Jira sync-now success', data);

              const syncedCount = data.total ?? data.processed_keys?.length ?? 0;
              vscode.window.showInformationMessage(
                `NAVI: Jira sync complete – ${syncedCount} issues synced at ${new Date().toLocaleTimeString()}`
              );

              this.postToWebview({
                type: 'connectors.jiraSyncResult',
                ok: true,
                synced: syncedCount,
                snapshot_ts: data.snapshot_ts,
                processed_keys: data.processed_keys ?? []
              });
            } catch (err: any) {
              console.error('[AEP] Jira sync-now error', err);
              vscode.window.showErrorMessage(
                `NAVI: Jira sync error – ${err?.message ?? String(err)}`
              );
              this.postToWebview({
                type: 'connectors.jiraSyncResult',
                ok: false,
                error: 'fetch_failed',
              });
            }
            break;
          }

          case 'aep.intent.classify': {
            // Handle intent classification request
            const text = String(msg.text || '').trim();
            const modelId = msg.modelId || this._currentModelId;

            if (!text) {
              console.warn('[AEP] Intent classification requested but no text provided');
              return;
            }

            try {
              console.log('[AEP] Classifying intent for text:', text, 'with model:', modelId);

              // Call FastAPI backend for intent classification
              const baseUrl = this.getBackendBaseUrl();
              const response = await fetch(`${baseUrl}/api/agent/intent/preview`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  message: text,
                  model_id: modelId
                })
              });

              if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
              }

              const result = await response.json();
              console.log('[AEP] Intent classification result:', result);

              // Send result back to webview
              this.postToWebview({
                type: 'aep.intent.result',
                intent: (result as any).intent || 'Unknown',
                confidence: (result as any).confidence || 0.0,
                model: (result as any).model || modelId
              });

            } catch (err) {
              console.error('[AEP] Intent classification failed:', err);
              this.postToWebview({
                type: 'aep.intent.result',
                intent: 'Error',
                confidence: 0.0,
                model: modelId,
                error: String(err)
              });
            }
            break;
          }

          default:
            console.warn('[Extension Host] [AEP] Unknown message from webview:', msg);
        }
      } catch (err) {
        console.error('[Extension Host] [AEP] Error handling webview message:', err);
        this.postToWebview({
          type: 'error',
          text: '⚠️ Unexpected error in NAVI extension. Check developer tools for more details.'
        });
      }
    });

    // Welcome message will be sent when panel sends 'ready'
  }

  // --- Intent classification and smart routing --------------------------------

  // --- Intent classification and smart routing --------------------------------

  private async classifyIntent(message: string): Promise<NaviIntent> {
    const text = (message || '').trim();
    if (!text) {
      return 'general';
    }

    try {
      const baseUrl = this.getBackendBaseUrl();
      const endpoint = `${baseUrl}/api/agent/intent/preview`;

      console.log('[AEP] Calling intent preview endpoint:', endpoint);

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          model_id: this._currentModelId,
        }),
      });

      if (!response.ok) {
        const body = await response.text().catch(() => '');
        console.warn(
          '[AEP] Intent preview HTTP error:',
          response.status,
          response.statusText,
          body,
        );
        return 'general';
      }

      const result = await response.json() as {
        family?: string;
        kind?: string;
        intent?: string;
        confidence?: number;
        model?: string;
      };

      const family = (result.family || '').toLowerCase();
      const kind = (result.kind || '').toLowerCase();
      const confidence = typeof result.confidence === 'number'
        ? result.confidence
        : 0;

      console.log('[AEP] Intent preview result:', { family, kind, confidence });

      // Map backend families/kinds → NaviIntent union
      if (family === 'jira') {
        if (kind === 'list') return 'jira_list';
        if (kind === 'priority') return 'jira_priority';
        return 'jira_ticket';
      }

      if (family === 'workspace') {
        return 'workspace';
      }

      if (family === 'code') {
        return 'code';
      }

      if (family === 'greeting') {
        return 'greeting';
      }

      return 'general';
    } catch (err) {
      console.warn('[AEP] Intent classification failed, falling back to general:', err);
      return 'general';
    }
  }

  private async handleSmartRouting(
    text: string,
    modelId: string,
    modeId: string,
    attachments: FileAttachment[],
  ): Promise<void> {
    // 1) Classify intent
    const intent = await this.classifyIntent(text);
    console.log('[AEP] Detected intent:', intent, 'for message:', text);

    // We may add attachments automatically (workspace snapshot)
    let effectiveAttachments = attachments;

    // 2) If this is a workspace question and there is no context yet,
    //    build and attach a lightweight workspace snapshot.
    if (
      intent === 'workspace' &&
      (!effectiveAttachments || effectiveAttachments.length === 0)
    ) {
      console.log('[AEP] Workspace intent with no attachments → auto-attaching snapshot');
      await this.autoAttachWorkspaceSnapshot();
      effectiveAttachments = this.getCurrentAttachments();
    }

    // 3) Route based on intent
    try {
      switch (intent) {
        case 'jira_list': {
          await this.handleJiraListIntent(text);
          break;
        }

        case 'jira_priority':
        case 'jira_ticket': {
          await this.callNaviBackend(text, modelId, modeId, effectiveAttachments);
          break;
        }

        case 'greeting':
        case 'code':
        case 'workspace':
        case 'general':
        case 'other':
        default: {
          await this.callNaviBackend(text, modelId, modeId, effectiveAttachments);
          break;
        }
      }
    } catch (err) {
      console.error('[AEP] Error handling message with intent:', intent, err);
      this.postToWebview({
        type: 'botMessage',
        text: 'Sorry, something went wrong while processing this message.',
      });
    }
  }

  private async handleJiraListIntent(originalMessage: string): Promise<void> {
    try {
      const res = await fetch(`${this.getBackendBaseUrl()}/api/navi/jira-tasks?user_id=default_user&limit=20`);

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }

      const data = await res.json();
      const assistantText = this.formatJiraTaskListForChat(data, originalMessage);

      this._messages.push({ role: 'assistant', content: assistantText });
      this.postToWebview({ type: 'botThinking', value: false });
      this.postToWebview({ type: 'botMessage', text: assistantText });
    } catch (err) {
      console.error('[AEP] Error fetching Jira tasks:', err);
      await this.callNaviBackend(
        originalMessage,
        this._currentModelId,
        this._currentModeId,
        this.getCurrentAttachments()
      );
    }
  }

  private formatJiraTaskListForChat(data: any, _originalMessage: string): string {
    if (!data.tasks || data.tasks.length === 0) {
      return "I don't see any Jira tasks in your synced memory yet. Try running a Jira sync and ask me again.";
    }

    const lines: string[] = [];
    lines.push("Here's what I have in your Jira queue right now:\n");

    for (const t of data.tasks) {
      const key = t.jira_key || t.scope || 'UNKNOWN';
      const title = t.title || key;
      const status = t.status || 'Unknown';
      const updated = t.updated_at ? new Date(t.updated_at).toLocaleDateString() : 'Unknown';

      lines.push(`- **${key}** — ${title} — **Status:** ${status} — *Last updated:* ${updated}`);
    }

    lines.push("\n---");
    lines.push("**I can also:**");
    lines.push("* Explain what a specific ticket is about in simple language");
    lines.push("* Help you prioritize which ticket to pick next");
    lines.push("* Break down a ticket into an implementation plan");
    lines.push("* Pull related context from Slack, Confluence, or meeting notes");
    lines.push("* Draft a message to your team about progress");

    return lines.join('\n');
  }



  // --- Jira task brief handlers ----------------------------------------------

  private async triggerBackgroundJiraSync(): Promise<void> {
    // Non-blocking background sync of Jira tasks
    const config = vscode.workspace.getConfiguration('aep');
    const baseUrl = config.get<string>('navi.backendUrl') || 'http://127.0.0.1:8000';
    const userId = config.get<string>('navi.userId') || 'srinivas@example.com';

    const cleanBaseUrl = baseUrl.replace(/\/api\/navi\/chat$/, '');
    const syncUrl = `${cleanBaseUrl}/api/org/sync/jira`;

    console.log('[Extension Host] [AEP] Triggering background Jira sync...');

    // Fire and forget - don't await
    fetch(syncUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        max_issues: 20
      })
    })
      .then(async (response) => {
        if (response.ok) {
          const data = await response.json();
          console.log('[Extension Host] [AEP] Jira sync completed:', data);

          // Show subtle notification
          if ((data as any).total > 0) {
            vscode.window.showInformationMessage(
              `NAVI: Synced ${(data as any).total} Jira tasks`
            );
          }
        } else {
          const text = await response.text().catch(() => '');
          console.log('[Extension Host] [AEP] Jira sync failed:', response.status, text);
          vscode.window.showWarningMessage(
            `NAVI: Jira sync failed (HTTP ${response.status})`
          );
        }
      })
      .catch((error) => {
        console.log('[Extension Host] [AEP] Jira sync error (non-critical):', error.message);
        vscode.window.showWarningMessage('NAVI: Jira sync error – backend unreachable or misconfigured');
      });
  }

  private async handleJiraTaskBriefCommand(): Promise<void> {
    if (!this._view) {
      return;
    }

    try {
      const config = vscode.workspace.getConfiguration('aep');
      const baseUrl = config.get<string>('navi.backendUrl') || 'http://127.0.0.1:8000';
      const userId = config.get<string>('navi.userId') || 'srinivas@example.com';

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
        vscode.window.showErrorMessage(
          `NAVI: Failed to load Jira tasks (${response.status})`
        );
        return;
      }

      const data = await response.json();

      // Send tasks to webview
      this.postToWebview({
        type: 'showJiraTasks',
        tasks: (data as any).tasks || []
      });
    } catch (error: any) {
      console.error('[Extension Host] [AEP] Error fetching Jira tasks:', error);
      vscode.window.showErrorMessage('NAVI: Error loading Jira tasks');
    }
  }

  private async handleJiraTaskSelected(jiraKey: string): Promise<void> {
    if (!this._view) {
      return;
    }

    try {
      const config = vscode.workspace.getConfiguration('aep');
      const baseUrl = config.get<string>('navi.backendUrl') || 'http://127.0.0.1:8000';
      const userId = config.get<string>('navi.userId') || 'srinivas@example.com';

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
        vscode.window.showErrorMessage(
          `NAVI: Failed to load brief for ${jiraKey} (${response.status})`
        );
        this.postToWebview({ type: 'botThinking', value: false });
        return;
      }

      const data = await response.json();

      // Extract the brief markdown from the sections
      const briefMd = (data as any).sections?.[0]?.content || (data as any).summary || 'No brief content available';

      // Send as a bot message
      this.postToWebview({
        type: 'botMessage',
        text: briefMd,
        actions: []
      });

      this.postToWebview({ type: 'botThinking', value: false });
    } catch (error: any) {
      console.error('[Extension Host] [AEP] Error fetching task brief:', error);
      vscode.window.showErrorMessage('NAVI: Error fetching task brief');
      this.postToWebview({ type: 'botThinking', value: false });
    }
  }

  // --- Core: call NAVI backend ------------------------------------------------

  private async callNaviBackend(
    latestUserText: string,
    modelId?: string,
    modeId?: string,
    attachments?: FileAttachment[]
  ): Promise<void> {
    if (!this._view) {
      return;
    }

    // Merge attachments into the plain-text message for the LLM
    const messageWithContext = this.buildMessageWithAttachments(
      latestUserText,
      attachments
    );

    // Perfect Workspace Context Collection
    const workspaceContext = await collectWorkspaceContext();

    // NEW: detect workspace root from VS Code
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? undefined;

    const payload = {
      message: messageWithContext,
      model: modelId || this._currentModelId,
      mode: modeId || this._currentModeId,
      user_id: 'default_user',
      workspace: workspaceContext,  // 🚀 Perfect workspace awareness
      workspace_root: workspaceRoot, // NEW: VS Code workspace root path
      // Map attachment kinds to match backend expectations
      attachments: (attachments ?? []).map(att => ({
        ...att,
        kind: att.kind === 'currentFile' || att.kind === 'pickedFile' ? 'file' : 'selection'
      })),
    };

    let response: Response;
    try {
      // Read backend URL from configuration with fallback
      const config = vscode.workspace.getConfiguration('aep');
      const configValue = config.get<string>('navi.backendUrl');
      const backendUrl = configValue || 'http://127.0.0.1:8787/api/navi/chat';

      console.log('[Extension Host] [AEP] Configuration debug:');
      console.log('[Extension Host] [AEP] - Raw config value:', configValue);
      console.log('[Extension Host] [AEP] - Final backend URL:', backendUrl);
      console.log('[Extension Host] [AEP] - Payload:', {
        ...payload,
        // don't spam the log with the whole file
        attachmentsCount: payload.attachments.length,
        firstAttachmentPath: payload.attachments[0]?.path,
        firstAttachmentChars: payload.attachments[0]?.content?.length,
      });
      console.log('[Extension Host] [AEP] Calling NAVI backend now...');

      response = await fetch(backendUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Org-Id': 'org_aep_platform_4538597546e6fec6',
        },
        body: JSON.stringify(payload)
      });
    } catch (error: any) {
      console.error('[Extension Host] [AEP] NAVI backend unreachable:', error);
      console.error('[Extension Host] [AEP] Error details:', {
        name: error.name,
        message: error.message,
        stack: error.stack
      });
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
      console.error(
        '[Extension Host] [AEP] NAVI backend non-OK response:',
        response.status,
        response.statusText
      );
      this.postToWebview({ type: 'botThinking', value: false });
      this.postToWebview({
        type: 'error',
        text: `⚠️ NAVI backend error: HTTP ${response.status} ${response.statusText || ''}`.trim()
      });
      return;
    }

    try {
      console.log('[Extension Host] [AEP] Response received. Status:', response.status, 'Content-Type:', contentType);

      if (contentType.includes('application/json')) {
        // PR-6B: Handle new response format
        const json = (await response.json()) as NaviChatResponseJson;
        console.log('[Extension Host] [AEP] JSON response:', json);
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
        const sources = json.sources || [];

        if (json.actions && json.actions.length > 0) {
          this._agentActions.set(messageId, { actions: json.actions });
          this.postToWebview({
            type: 'botMessage',
            text: content,
            messageId: messageId,
            actions: json.actions,
            sources: sources,
            agentRun: json.agentRun || null
          });
        } else {
          this.postToWebview({
            type: 'botMessage',
            text: content,
            sources: sources,
            agentRun: json.agentRun || null
          });
        }
        return;
      } if (contentType.includes('text/event-stream')) {
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
    } catch (err) {
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
  private async readSseStream(response: Response): Promise<string> {
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
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let newlineIndex: number;
        // Process line by line
        while ((newlineIndex = buffer.indexOf('\n')) >= 0) {
          const line = buffer.slice(0, newlineIndex).trim();
          buffer = buffer.slice(newlineIndex + 1);

          if (!line || !line.startsWith('data:')) {
            continue;
          }

          const data = line.slice('data:'.length).trim();
          if (!data) continue;

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
            } else if (typeof parsed.reply === 'string') {
              chunk = parsed.reply;
            }
          } catch {
            // If not JSON, treat as raw text
          }

          accumulated += chunk;
        }
      }
    } catch (err: any) {
      // In PR1 we just log SSE errors and let the caller decide what to show
      console.error('[Extension Host] [AEP] Error while reading SSE stream:', err);
    }

    return accumulated;
  }

  // --- Helpers ---------------------------------------------------------------

  private postToWebview(message: any) {
    if (!this._view) return;
    this._view.webview.postMessage(message);
  }

  private startNewChat() {
    // Reset conversation state, keep current model/mode
    this._conversationId = generateConversationId();
    this._messages = [];

    this.postToWebview({ type: 'clearChat' });
    this.postToWebview({
      type: 'botMessage',
      text: "🔄 **New chat started!**\n\nHow can I help you today?"
    });
  }

  // --- Attachment Helper Methods ---

  private addAttachment(attachment: FileAttachment) {
    // Simple upsert: dedupe by kind+path+length
    const key = `${attachment.kind}:${attachment.path}:${attachment.content.length}`;
    const existingIndex = this._attachments.findIndex(a =>
      `${a.kind}:${a.path}:${a.content.length}` === key
    );

    if (existingIndex >= 0) {
      this._attachments[existingIndex] = attachment;
    } else {
      this._attachments.push(attachment);
    }

    // Tell the webview so it can render chips (panel already listens for this)
    this.postToWebview({
      type: 'addAttachment',
      attachment,
    });
  }

  /**
   * Automatically attach a lightweight workspace snapshot to help answer workspace-related questions.
   * This includes key project files like package.json, README.md, etc.
   */
  private async autoAttachWorkspaceSnapshot(): Promise<void> {
    console.log('[AEP] Collecting workspace snapshot...');

    // Get workspace folders
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders || workspaceFolders.length === 0) {
      console.log('[AEP] No workspace folders found');
      return;
    }

    // Use the first workspace folder
    const wsRoot = workspaceFolders[0].uri.fsPath;
    console.log('[AEP] Workspace root:', wsRoot);

    // Key files that provide project context
    const keyFiles = [
      'package.json',
      'README.md',
      'readme.md',
      'pyproject.toml',
      'requirements.txt',
      'Cargo.toml',
      'go.mod',
      'pom.xml',
      'build.gradle',
      '.gitignore',
    ];

    let attachedCount = 0;
    const maxFiles = 5; // Limit to avoid overwhelming the context

    for (const fileName of keyFiles) {
      if (attachedCount >= maxFiles) break;

      try {
        const filePath = path.join(wsRoot, fileName);
        const uri = vscode.Uri.file(filePath);

        // Check if file exists
        try {
          await vscode.workspace.fs.stat(uri);
        } catch {
          continue; // File doesn't exist, skip
        }

        // Read file content
        const fileData = await vscode.workspace.fs.readFile(uri);
        const content = new TextDecoder().decode(fileData);

        // Truncate if too large
        const truncatedContent = this.truncateForAttachment(content, fileName);

        // Add as attachment
        this.addAttachment({
          kind: 'file',
          path: filePath,
          content: truncatedContent,
        });

        attachedCount++;
        console.log(`[AEP] Added workspace file: ${fileName}`);
      } catch (error) {
        console.warn(`[AEP] Failed to read ${fileName}:`, error);
      }
    }

    if (attachedCount > 0) {
      console.log(`[AEP] Workspace snapshot complete: ${attachedCount} files attached`);
    } else {
      console.log('[AEP] No key workspace files found');
    }
  }

  private getCurrentAttachments(): FileAttachment[] {
    return this._attachments.slice();
  }

  private clearAttachments() {
    this._attachments = [];
    this.postToWebview({ type: 'clearAttachments' });
  }

  private truncateForAttachment(text: string, source: string): string {
    const maxChars = 120_000; // ~700–1000 lines is fine
    if (text.length <= maxChars) return text;

    vscode.window.showWarningMessage(
      `NAVI: ${source} is very large; truncating to ${maxChars.toLocaleString()} characters for this request.`
    );
    return text.slice(0, maxChars);
  }

  private showWebviewToast(message: string, level: 'info' | 'warning' | 'error' = 'info') {
    this.postToWebview({
      type: 'ephemeralToast',
      level,
      text: message,
    });
  }

  // Helper: merge attachments into the plain-text message we send to the backend
  private buildMessageWithAttachments(
    latestUserText: string,
    attachments?: FileAttachment[]
  ): string {
    if (!attachments || attachments.length === 0) {
      return latestUserText;
    }

    const chunks: string[] = [];

    chunks.push(
      'I have attached some code context from VS Code below. ' +
      'Please use that code as the primary context when answering my request.\n'
    );

    for (const att of attachments) {
      const fileLabel = att.path ? path.basename(att.path) : '(untitled)';
      const kindLabel =
        att.kind === 'selection'
          ? 'selected code'
          : att.kind === 'currentFile'
            ? 'current file'
            : 'attached file';

      const lang = att.language ?? ''; // ok to be empty
      const fenceHeader = lang ? `\`\`\`${lang}` : '```';

      chunks.push(
        `\n\nFile: \`${fileLabel}\` (${kindLabel})\n` +
        `${fenceHeader}\n` +
        `${att.content}\n` +
        `\`\`\``
      );
    }

    chunks.push('\n\nUser request:\n');
    chunks.push(latestUserText);

    return chunks.join('');
  }

  // PR-5: Handle attachment requests from the webview
  private async handleAttachmentRequest(webview: vscode.Webview, kind: string): Promise<void> {
    const editor = vscode.window.activeTextEditor;

    try {
      // 1) Attach SELECTION
      if (kind === 'selection') {
        if (!editor || editor.selection.isEmpty) {
          const msg = 'Select some code in the active editor before attaching.';
          vscode.window.showInformationMessage(`NAVI: ${msg}`);

          // Also show a short-lived toast inside the panel
          this.postToWebview({
            type: 'toast',
            level: 'warning',
            message: msg,
          });
          return;
        }

        const selectedText = editor.document.getText(editor.selection);
        const filePath = editor.document.uri.fsPath;
        const language = editor.document.languageId;

        const attachment: FileAttachment = {
          kind: 'selection',
          path: filePath,
          language,
          content: selectedText,
        };

        // Update internal state + tell panel
        this.addAttachment(attachment);
        return;
      }

      // 2) Attach CURRENT FILE
      if (kind === 'current-file' && editor) {
        const content = editor.document.getText();
        const filePath = editor.document.uri.fsPath;
        const language = editor.document.languageId;

        const attachment: FileAttachment = {
          kind: 'currentFile',
          path: filePath,
          language,
          content,
        };

        this.addAttachment(attachment);
        return;
      }

      // 3) Pick FILE via file picker
      if (kind === 'pick-file') {
        const uris = await vscode.window.showOpenDialog({
          canSelectFiles: true,
          canSelectFolders: false,
          canSelectMany: false,
          openLabel: 'Attach File to NAVI',
        });

        if (!uris || uris.length === 0) {
          return;
        }

        const uri = uris[0];
        const bytes = await vscode.workspace.fs.readFile(uri);
        const textContent = new TextDecoder('utf-8').decode(bytes);

        const attachment: FileAttachment = {
          kind: 'pickedFile',
          path: uri.fsPath,
          content: textContent,
        };

        this.addAttachment(attachment);
        return;
      }

    } catch (err) {
      console.error('[Extension Host] [AEP] Error reading attachment:', err);
      vscode.window.showErrorMessage('NAVI: Failed to read file for attachment.');
    }
  }

  // PR-7: Apply agent action from new unified message format
  private async handleAgentApplyAction(message: any): Promise<void> {
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
    } catch (error: any) {
      console.error('[Extension Host] [AEP] Error applying action:', error);
      vscode.window.showErrorMessage(`Failed to apply action: ${error.message}`);
    }
  }

  // NEW: Apply a full workspace plan (array of AgentAction)
  private async applyWorkspacePlan(actions: AgentAction[]): Promise<void> {
    if (!actions || actions.length === 0) {
      vscode.window.showInformationMessage('NAVI: No workspace actions to apply.');
      return;
    }

    console.log('[Extension Host] [AEP] Applying workspace plan with', actions.length, 'actions');

    let appliedCount = 0;

    for (const action of actions) {
      try {
        if (!action || !action.type) {
          console.warn('[Extension Host] [AEP] Skipping invalid action in workspace plan:', action);
          continue;
        }

        if (action.type === 'createFile') {
          await this.applyCreateFileAction(action);
          appliedCount += 1;
        } else if (action.type === 'editFile') {
          await this.applyEditFileAction(action);
          appliedCount += 1;
        } else if (action.type === 'runCommand') {
          await this.applyRunCommandAction(action);
          appliedCount += 1;
        } else {
          console.warn('[Extension Host] [AEP] Unknown action type in workspace plan:', action.type);
        }
      } catch (err: any) {
        console.error('[Extension Host] [AEP] Failed to apply action in workspace plan:', err);
        vscode.window.showErrorMessage(`NAVI: Failed to apply one of the workspace actions: ${err.message ?? String(err)}`);
      }
    }

    this.postBotStatus(`✅ Applied ${appliedCount}/${actions.length} workspace actions.`);
  }

  private async applyCreateFileAction(action: any): Promise<void> {
    const fileName: string = action.filePath ?? 'sample.js';
    const content: string = action.content ?? '// Sample generated by NAVI\nconsole.log("Hello, World!");\n';

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
      this.postBotStatus(
        "I don't see a workspace folder open. I can still create the sample file if you tell me where it should live."
      );

      const choice = await vscode.window.showQuickPick(
        [
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
        ],
        {
          placeHolder: 'Where should I create the sample file?',
          title: 'NAVI - Create Sample File',
        }
      );

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
    this.postBotStatus(
      "I don't see a workspace folder open. Please pick a folder where I should create the sample file."
    );

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

  private async createFileUnderRoot(root: vscode.Uri, relPath: string, content: string): Promise<void> {
    // Security: Validate path to prevent traversal attacks
    const path = require('path');
    // Normalize path and check for absolute paths
    const normalizedPath = path.normalize(relPath);
    if (path.isAbsolute(normalizedPath)) {
      vscode.window.showErrorMessage('NAVI: Cannot create file with absolute path');
      return;
    }
    // Check for path traversal attempts (including encoded variants)
    if (normalizedPath.includes('..') || /\%2e\%2e|\.\./.test(relPath)) {
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
    } catch {
      // ignore if it already exists
    }

    await vscode.workspace.fs.writeFile(fileUri, Buffer.from(content, 'utf8'));

    const doc = await vscode.workspace.openTextDocument(fileUri);
    await vscode.window.showTextDocument(doc);

    vscode.window.setStatusBarMessage(`✅ NAVI: Created ${relPath}`, 3000);

    this.postBotStatus(`✅ Done! I've created \`${relPath}\` at ${fileUri.fsPath}`);
  }

  private postBotStatus(text: string): void {
    if (!this._view) return;
    this._view.webview.postMessage({
      type: 'botMessage',
      text,
      actions: [],
      messageId: new Date().toISOString(),
    });
  }

  private async applyRunCommandAction(action: any): Promise<void> {
    const command = action.command;
    if (!command) return;

    // Security: Sanitize, truncate, and show command for confirmation before executing
    const sanitizedCommand = command.replace(/[\r\n]/g, ' ').substring(0, 200);
    const displayCommand = command.length > 200 ? sanitizedCommand + '...' : sanitizedCommand;

    const confirmed = await vscode.window.showWarningMessage(
      `NAVI wants to run the following command:\\n\\n${displayCommand}\\n\\nAre you sure?`,
      { modal: true },
      'Run Command'
    );
    if (confirmed !== 'Run Command') return;

    const terminal = vscode.window.createTerminal('NAVI Agent');
    terminal.show();
    terminal.sendText(command);

    vscode.window.showInformationMessage(`🚀 Running: ${command}`);
  }

  // ---- editFile with diff view & apply (PR-10) -------------------------------
  private async applyEditFileAction(action: any): Promise<void> {
    // Backend contract: editFile provides either:
    // - filePath + content (full new file text)   ✅
    // - optionally diff (for explanation), but we don't parse it
    const filePath: string | undefined = action.filePath;
    const newContent: string | undefined = action.content;

    if (!newContent) {
      vscode.window.showWarningMessage(
        'NAVI: editFile action is missing "content"; nothing to apply.'
      );
      return;
    }

    // Resolve target document: use filePath if present, otherwise active editor
    let targetDoc: vscode.TextDocument | undefined;
    if (filePath) {
      const uri = vscode.Uri.file(filePath);
      try {
        targetDoc = await vscode.workspace.openTextDocument(uri);
      } catch {
        vscode.window.showWarningMessage(
          `NAVI: Target file "${filePath}" does not exist.`
        );
        return;
      }
    } else {
      targetDoc = vscode.window.activeTextEditor?.document;
      if (!targetDoc) {
        vscode.window.showWarningMessage(
          'NAVI: No active file to apply edit to.'
        );
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
    await vscode.commands.executeCommand(
      'vscode.diff',
      targetDoc.uri,
      newDoc.uri,
      title
    );

    // Ask user if we should apply the changes to the real file now
    const choice = await vscode.window.showQuickPick(
      [
        { label: '✅ Apply edit to file', id: 'apply' },
        { label: '👁️ Keep diff only', id: 'keep' },
        { label: '❌ Cancel', id: 'cancel' },
      ],
      {
        placeHolder:
          'NAVI has proposed an edit. Do you want to apply it to the real file?',
      }
    );

    if (!choice || choice.id === 'cancel' || choice.id === 'keep') {
      if (choice?.id === 'keep') {
        this.postBotStatus('Diff view kept open for your review.');
      }
      return;
    }

    if (choice.id === 'apply') {
      const edit = new vscode.WorkspaceEdit();
      const fullRange = new vscode.Range(
        targetDoc.positionAt(0),
        targetDoc.positionAt(originalText.length)
      );
      edit.replace(targetDoc.uri, fullRange, newContent);
      const success = await vscode.workspace.applyEdit(edit);
      if (success) {
        await targetDoc.save();
        vscode.window.setStatusBarMessage('✅ NAVI: Edit applied.', 3000);
        this.postBotStatus(`✅ Edit applied to ${targetDoc.fileName.split(/[\\/]/).pop()}`);
      } else {
        vscode.window.showErrorMessage('NAVI: Failed to apply edit.');
      }
    }
  }

  // PR-6C: Apply agent-proposed edit with diff view support
  private async handleApplyAgentEdit(msg: { messageId: string; actionIndex: number }): Promise<void> {
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

      } else if (action.type === 'createFile' && action.filePath && action.content) {
        // Create new file
        const fileUri = vscode.Uri.joinPath(workspaceRoot, action.filePath);
        await vscode.workspace.fs.writeFile(fileUri, Buffer.from(action.content, 'utf-8'));
        vscode.window.showInformationMessage(`✅ Created ${action.filePath}`);

        // Open the new file
        const document = await vscode.workspace.openTextDocument(fileUri);
        await vscode.window.showTextDocument(document, { preview: false });

      } else if (action.type === 'runCommand' && action.command) {
        // PR-6C: Run terminal command
        const terminal = vscode.window.createTerminal('NAVI Agent');
        terminal.show();
        terminal.sendText(action.command);
        vscode.window.showInformationMessage(`🔧 Running: ${action.command}`);

      } else {
        vscode.window.showWarningMessage(`Unknown or incomplete action type: ${action.type}`);
      }

    } catch (err: any) {
      console.error('[Extension Host] [AEP] Error applying agent action:', err);
      vscode.window.showErrorMessage(`Failed to apply action: ${err.message}`);
    }
  }

  // PR-6C: Show diff preview and apply on confirmation
  private async showDiffPreviewAndApply(
    workspaceRoot: vscode.Uri,
    filePath: string,
    diff: string
  ): Promise<void> {
    const fileUri = vscode.Uri.joinPath(workspaceRoot, filePath);

    // Read original file
    let originalDoc: vscode.TextDocument;
    try {
      originalDoc = await vscode.workspace.openTextDocument(fileUri);
    } catch {
      vscode.window.showErrorMessage(`File not found: ${filePath}`);
      return;
    }

    const original = originalDoc.getText();

    // Apply diff to get new content
    let newContent: string;
    try {
      newContent = applyUnifiedDiff(original, diff);
    } catch (error: any) {
      vscode.window.showErrorMessage(`Failed to apply diff: ${error.message}`);
      return;
    }

    // Create temp file with new content for preview
    const fileName = path.basename(filePath);
    const tempUri = vscode.Uri.parse(`untitled:${fileName} (NAVI Proposed)`);

    await vscode.workspace.openTextDocument(tempUri);
    const edit = new vscode.WorkspaceEdit();
    edit.insert(tempUri, new vscode.Position(0, 0), newContent);
    await vscode.workspace.applyEdit(edit);

    // Show diff view
    await vscode.commands.executeCommand(
      'vscode.diff',
      fileUri,
      tempUri,
      `NAVI: ${fileName} (Original ↔ Proposed)`
    );

    // Ask user to confirm
    const choice = await vscode.window.showInformationMessage(
      `Apply proposed changes to ${fileName}?`,
      { modal: true },
      'Apply',
      'Cancel'
    );

    if (choice === 'Apply') {
      // Apply the changes
      const fullRange = new vscode.Range(
        originalDoc.positionAt(0),
        originalDoc.positionAt(original.length)
      );

      const finalEdit = new vscode.WorkspaceEdit();
      finalEdit.replace(fileUri, fullRange, newContent);
      await vscode.workspace.applyEdit(finalEdit);
      await originalDoc.save();

      vscode.window.showInformationMessage(`✅ Applied changes to ${fileName}`);
    } else {
      vscode.window.showInformationMessage('Changes discarded');
    }
  } private getWebviewHtml(webview: vscode.Webview): string {
    const cfg = vscode.workspace.getConfiguration('aep');
    const rawBase = cfg.get<string>('navi.backendUrl') || 'http://127.0.0.1:8787';
    const backendBaseUrl = rawBase.replace(/\/$/, '');
    
    // NAVI uses React Vite dev server for all UI
    // Development: http://localhost:3000
    // Production: will use bundled React app
    const isDevelopment = cfg.get<boolean>('development.useReactDevServer') ?? false;
    const devServerUrl = 'http://localhost:3000';
    
    return /* html */ `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta http-equiv="X-UA-Compatible" content="IE=edge" />
    <title>NAVI — Autonomous Engineering Assistant</title>
    <script>
      // Expose backend URL and workspace context to React app
      window.__AEP_BACKEND_BASE_URL__ = ${JSON.stringify(backendBaseUrl)};
      window.__WORKSPACE_CONTEXT__ = null;
      window.__WORKSPACE_ROOT__ = null;
    </script>
  </head>
  <body>
    <div id="root"></div>
    ${isDevelopment 
      ? `<script type="module" src="${devServerUrl}/src/main.tsx"></script>`
      : `<script type="module" src="file:///VITE_BUILD_PATH/main.js"></script>`
    }
  </body>
</html>`;
  }

  // --- Command Methods ---

  public async attachSelectionCommand(): Promise<void> {
    if (this._view) {
      await this.handleAttachmentRequest(this._view.webview, 'selection');
    }
  }

  public async attachCurrentFileCommand(): Promise<void> {
    if (this._view) {
      await this.handleAttachmentRequest(this._view.webview, 'current-file');
    }
  }


}

// Simple conversation id – you can switch to UUID later
function generateConversationId(): string {
  return `navi-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

function getNonce() {
  let text = '';
  const possible =
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  for (let i = 0; i < 32; i++) {
    text += possible.charAt(Math.floor(Math.random() * possible.length));
  }
  return text;
}
