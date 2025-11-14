import * as vscode from 'vscode';

const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8787/api/chat';
const CONFIG_SECTION = 'aep';
const CONFIG_BACKEND_KEY = 'naviBackendUrl';

interface NaviBackendRequest {
  message: string;
  model?: string;
  mode?: string;
  editor?: {
    fileName?: string | null;
    languageId?: string | null;
    selection?: string | null;
  };
  conversationId?: string | null;
  history?: Array<{
    role: 'user' | 'assistant' | 'system';
    content: string;
  }>;
}

interface NaviBackendResponse {
  reply?: string;
  meta?: {
    model_used?: string;
    finish_reason?: string | null;
    usage?: {
      input_tokens?: number;
      output_tokens?: number;
      total_tokens?: number;
    };
  };
}

/**
 * NAVI chat webview provider
 */
class NaviWebviewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'aep.chatView';

  private _view: vscode.WebviewView | undefined;

  constructor(private readonly _extensionUri: vscode.Uri) { }

  // ---------- Backend helpers ----------

  private getBackendUrl(): string {
    const config = vscode.workspace.getConfiguration(CONFIG_SECTION);
    const configured = config.get<string>(CONFIG_BACKEND_KEY);
    return (configured && configured.trim()) || DEFAULT_BACKEND_URL;
  }

  private getEditorContext() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      return {
        fileName: null,
        languageId: null,
        selection: null,
      };
    }

    const { document, selection } = editor;
    const selectedText = selection.isEmpty
      ? null
      : document.getText(selection) || null;

    return {
      fileName: document.fileName,
      languageId: document.languageId,
      selection: selectedText,
    };
  }

  /**
   * Call the NAVI backend in non-streaming mode.
   * Expects JSON `{ reply: string, meta?: {...} }`.
   */
  private async callNaviBackend(payload: NaviBackendRequest): Promise<string> {
    const endpoint = this.getBackendUrl();
    console.log('[AEP] Calling NAVI backend:', endpoint, payload);

    let response: Response;
    try {
      response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
    } catch (err: any) {
      console.error('[AEP] NAVI backend unreachable:', err);
      return `⚠️ Could not reach NAVI backend: ${err?.message ?? String(err)}`;
    }

    if (!response.ok) {
      const text = await response.text().catch(() => '');
      console.error(
        '[AEP] NAVI backend HTTP error:',
        response.status,
        response.statusText,
        text,
      );
      return `⚠️ NAVI backend error (${response.status} ${response.statusText}): ${text}`;
    }

    let data: NaviBackendResponse;
    try {
      data = (await response.json()) as NaviBackendResponse;
    } catch (err: any) {
      console.error('[AEP] NAVI backend JSON parse error:', err);
      const fallback = await response.text().catch(() => '');
      return fallback || '⚠️ NAVI backend returned an unreadable response.';
    }

    if (typeof data.reply === 'string' && data.reply.trim().length > 0) {
      return data.reply;
    }

    // Fallback: stringify whatever we got
    return (
      '⚠️ NAVI backend did not include a `reply`. Raw response:\n' +
      '```json\n' +
      JSON.stringify(data, null, 2) +
      '\n```'
    );
  }

  /**
   * Streaming scaffolding (client-side progressive reveal).
   * For now we keep it unused so existing UI still sees a single `botMessage`.
   * Later, when we want real streaming, we can:
   *  - change the backend to stream tokens
   *  - or call OpenAI directly here
   *  - use `botStreamStart` / `botStreamChunk` / `botStreamEnd` message types.
   */
  private async streamReplyToWebview(
    reply: string,
    webview: vscode.Webview,
  ): Promise<void> {
    // NOTE: not actively used yet – infrastructure only.
    const CHUNK_SIZE = 40;
    const chunks: string[] = [];

    for (let i = 0; i < reply.length; i += CHUNK_SIZE) {
      chunks.push(reply.slice(i, i + CHUNK_SIZE));
    }

    if (!chunks.length) {
      return;
    }

    webview.postMessage({ type: 'botStreamStart' });

    for (const chunk of chunks) {
      webview.postMessage({ type: 'botStreamChunk', text: chunk });
      await new Promise((resolve) => setTimeout(resolve, 25));
    }

    webview.postMessage({ type: 'botStreamEnd' });
  }

  // ---------- Webview lifecycle ----------

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken,
  ) {
    this._view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri],
    };

    webviewView.webview.html = getWebviewContent(
      webviewView.webview,
      this._extensionUri,
    );

    // Handle messages from the webview
    webviewView.webview.onDidReceiveMessage(async (msg: any) => {
      switch (msg.type) {
        case 'ready': {
          // Initial welcome
          webviewView.webview.postMessage({
            type: 'botMessage',
            text: `New chat started! How can I help you?`,
          });
          break;
        }

        case 'sendMessage': {
          const text = String(msg.text || '').trim();
          const modelLabel = msg.model ? String(msg.model) : 'ChatGPT 5.1';
          const modeLabel =
            msg.mode ?? msg.modeLabel ?? 'Agent (full access)';

          if (!text) {
            return;
          }

          console.log('[AEP] User message:', text);

          // Show typing indicator
          webviewView.webview.postMessage({ type: 'showTyping' });

          const payload: NaviBackendRequest = {
            message: text,
            model: modelLabel,
            mode: modeLabel,
            editor: this.getEditorContext(),
            conversationId: null, // TODO: wire real thread ids
            history: undefined, // TODO: send prior exchanges here
          };

          try {
            const reply = await this.callNaviBackend(payload);

            // Hide typing indicator and send response
            webviewView.webview.postMessage({ type: 'hideTyping' });

            // For now we send as a single message.
            // Later we can switch to streamReplyToWebview() once the webview implements streaming.
            webviewView.webview.postMessage({
              type: 'botMessage',
              text: reply,
            });
          } catch (error) {
            // Hide typing indicator and send error
            webviewView.webview.postMessage({ type: 'hideTyping' });
            webviewView.webview.postMessage({
              type: 'botMessage',
              text: `⚠️ **Backend Error**: ${error instanceof Error ? error.message : 'Unknown error'}`,
            });
          }
          break;
        }

        case 'modelChanged': {
          const label = String(msg.value || '').trim();
          if (!label) {
            return;
          }
          console.log('[AEP] Model changed:', label);
          webviewView.webview.postMessage({
            type: 'botMessage',
            text: `Switched model to **${label}** (demo-only selector for now).`,
          });
          break;
        }

        case 'modeChanged': {
          const label = String(msg.value || '').trim();
          if (!label) {
            return;
          }
          console.log('[AEP] Mode changed:', label);
          webviewView.webview.postMessage({
            type: 'botMessage',
            text: `Mode updated to **${label}** (demo-only for now).`,
          });
          break;
        }

        case 'attachTypeSelected': {
          const type = String(msg.value || '').trim();
          if (!type) {
            return;
          }
          console.log('[AEP] Attach type selected:', type);
          vscode.window.showInformationMessage(
            `Attachment flow for "${type}" is not wired yet – this will open the real picker soon.`,
          );
          break;
        }

        case 'buttonAction': {
          const action = msg.action;
          console.log('[AEP] Button action:', action);

          if (action === 'newChat') {
            // Clear chat + send fresh welcome
            webviewView.webview.postMessage({ type: 'clearChat' });
            webviewView.webview.postMessage({
              type: 'botMessage',
              text: 'New chat started! How can I help you?',
            });
          } else if (action === 'connectors') {
            vscode.window.showInformationMessage(
              'NAVI Connectors – MCP servers & repo tools coming soon.',
            );
          } else if (action === 'settings') {
            vscode.commands.executeCommand(
              'workbench.action.openSettings',
              '@ext:navralabs.aep-professional aep.naviBackendUrl',
            );
          }
          break;
        }

        default:
          console.warn('[AEP] Unknown message type from webview:', msg);
      }
    });
  }
}

// ---------- Extension activation ----------

export function activate(context: vscode.ExtensionContext) {
  console.log('[AEP] NAVI extension activating…');

  const provider = new NaviWebviewProvider(context.extensionUri);

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      NaviWebviewProvider.viewType,
      provider,
    ),
  );

  // Command palette entry to focus the NAVI view
  const openCommand = vscode.commands.registerCommand('aep.openNavi', () => {
    vscode.commands.executeCommand('aep.chatView.focus');
  });

  context.subscriptions.push(openCommand);
}

export function deactivate() {
  console.log('[AEP] NAVI extension deactivated');
}

// ---------- HTML for webview ----------

function getWebviewContent(
  webview: vscode.Webview,
  extensionUri: vscode.Uri,
): string {
  const nonce = getNonce();

  const scriptUri = webview.asWebviewUri(
    vscode.Uri.joinPath(extensionUri, 'media', 'panel.js'),
  );
  const styleUri = webview.asWebviewUri(
    vscode.Uri.joinPath(extensionUri, 'media', 'panel.css'),
  );
  const mascotUri = webview.asWebviewUri(
    vscode.Uri.joinPath(extensionUri, 'media', 'mascot-navi-fox.svg'),
  );

  const cspSource = webview.cspSource;

  return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta
    http-equiv="Content-Security-Policy"
    content="default-src 'none'; style-src ${cspSource}; img-src ${cspSource} data:; script-src 'nonce-${nonce}';"
  />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <link href="${styleUri}" rel="stylesheet" />
  <title>NAVI Assistant</title>
</head>
<body>
  <div id="root" data-mascot-src="${mascotUri}"></div>
  <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
}

function getNonce(): string {
  let text = '';
  const possible =
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  for (let i = 0; i < 32; i++) {
    text += possible.charAt(Math.floor(Math.random() * possible.length));
  }
  return text;
}