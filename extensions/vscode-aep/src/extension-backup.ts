// src/extension.ts
import * as vscode from 'vscode';

class NaviWebviewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'aep.chatView';

  constructor(private readonly _extensionUri: vscode.Uri) { }

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ) {
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri],
    };

    webviewView.webview.html = getWebviewContent(
      webviewView.webview,
      this._extensionUri
    );

    webviewView.webview.onDidReceiveMessage(async (msg: any) => {
      try {
        switch (msg.type) {
          case 'ready': {
            webviewView.webview.postMessage({
              type: 'botMessage',
              text: `Hello! I'm NAVI, your autonomous engineering assistant. How can I help you today?`,
            });
            break;
          }

          case 'sendMessage': {
            const text = String(msg.text || '').trim();
            if (!text) return;

            console.log('[AEP] User message:', text);

            await callNaviBackend({
              webview: webviewView.webview,
              message: text,
              modelLabel: msg.modelLabel,
              modeLabel: msg.modeLabel,
            });

            break;
          }

          case 'newChat': {
            webviewView.webview.postMessage({ type: 'clearChat' });
            webviewView.webview.postMessage({
              type: 'botMessage',
              text: 'New chat started! How can I help you?',
            });
            break;
          }

          case 'openConnectors': {
            vscode.window.showInformationMessage(
              'Connect your repos & tools – coming soon!'
            );
            break;
          }

          case 'openSettings': {
            // Open the AEP NAVI settings section
            vscode.commands.executeCommand(
              'workbench.action.openSettings',
              '@ext:navralabs.aep-professional navi backend'
            );
            break;
          }

          case 'modelChanged': {
            const label = String(msg.value || '').trim();
            if (!label) return;
            webviewView.webview.postMessage({
              type: 'botMessage',
              text: `🧠 **Model**: ${label}`,
            });
            break;
          }

          case 'modeChanged': {
            const label = String(msg.value || '').trim();
            if (!label) return;
            webviewView.webview.postMessage({
              type: 'botMessage',
              text: `🛠 **Mode**: ${label}`,
            });
            break;
          }

          case 'attachTypeSelected': {
            const type = String(msg.value || '').trim();
            if (!type) return;
            vscode.window.showInformationMessage(
              `Attachment flow for "${type}" is not wired yet – this will open the real picker soon.`
            );
            break;
          }

          default:
            console.warn('[AEP] Unknown message type from webview:', msg);
        }
      } catch (err) {
        console.error('[AEP] Error handling webview message:', err);
        webviewView.webview.postMessage({
          type: 'botMessage',
          text: `⚠️ NAVI internal error handling message: ${String(err)}`,
        });
      }
    });
  }
}

/**
 * Call the NAVI backend with robust streaming support.
 * - Accumulates the full response and sends exactly ONE botMessage
 * - Handles terminated/aborted streams gracefully
 * - Never sends empty messages to avoid phantom bubbles
 */
async function callNaviBackend(opts: {
  webview: vscode.Webview;
  message: string;
  modelLabel?: string;
  modeLabel?: string;
}) {
  const { webview, message, modelLabel, modeLabel } = opts;

  const config = vscode.workspace.getConfiguration('aep');
  const backendUrl =
    config.get<string>('navi.backendUrl') ||
    'http://127.0.0.1:8787/chat';

  const payload = {
    message,
    model: modelLabel || 'ChatGPT 5.1',
    mode: modeLabel || 'Agent (full access)',
    editor: getEditorContext(),
    conversationId: null,
  };

  console.log('[AEP] Calling NAVI backend', backendUrl, payload);

  let assistantText = '';

  try {
    const res = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        accept: 'text/event-stream, application/json, text/plain;q=0.8, */*;q=0.5',
      },
      body: JSON.stringify(payload),
    });

    const contentType = (res.headers.get('content-type') || '').toLowerCase();

    if (!res.ok) {
      const errorText = await res.text().catch(() => '');
      const msg = `⚠️ NAVI backend error: HTTP ${res.status} ${res.statusText}${errorText ? ': ' + errorText : ''}`;
      console.warn('[AEP]', msg);
      webview.postMessage({ type: 'botMessage', text: msg });
      return;
    }

    // --- SSE Streaming Response ---
    if (contentType.startsWith('text/event-stream')) {
      console.log('[AEP] Using streaming response from NAVI backend');

      const reader = res.body?.getReader();
      if (!reader) {
        const msg = '⚠️ NAVI backend stream had no body.';
        webview.postMessage({ type: 'botMessage', text: msg });
        return;
      }

      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let streamDone = false;

      try {
        while (!streamDone) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Process complete lines; keep trailing partial in buffer
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const rawLine of lines) {
            const line = rawLine.trim();
            if (!line || line.startsWith(':')) continue;

            if (!line.toLowerCase().startsWith('data:')) continue;
            const data = line.slice(5).trim();
            if (!data) continue;
            if (data === '[DONE]') {
              streamDone = true;
              break;
            }

            try {
              // Try parsing as JSON first
              const parsed = JSON.parse(data);
              const delta =
                parsed.delta ??
                parsed.message ??
                parsed.text ??
                parsed.content ??
                '';
              if (delta) assistantText += String(delta);
            } catch {
              // Fallback: treat as raw text
              assistantText += data;
            }
          }
        }
      } catch (streamErr: any) {
        // Handle stream termination gracefully
        const errMsg = String(streamErr?.message ?? streamErr ?? 'unknown stream error');
        if (errMsg.includes('aborted') || errMsg.includes('terminated')) {
          console.warn('[AEP] NAVI stream terminated naturally:', errMsg);
          // Don't show error if we got some content
        } else {
          console.error('[AEP] NAVI stream error:', streamErr);
          if (!assistantText.trim()) {
            webview.postMessage({
              type: 'botMessage',
              text: `⚠️ Stream error: ${errMsg}`,
            });
            return;
          }
        }
      } finally {
        reader.releaseLock();
      }

      assistantText = assistantText.trimEnd();

      if (!assistantText.trim()) {
        webview.postMessage({
          type: 'botMessage',
          text: '⚠️ NAVI backend stream completed, but no content was received.',
        });
      } else {
        webview.postMessage({
          type: 'botMessage',
          text: assistantText,
        });
      }

      return;
    }

    // --- Non-streaming JSON/Text Response ---
    console.log('[AEP] Backend returned non-streaming response:', contentType);
    const raw = await res.text();
    let answer = raw;

    try {
      const json = JSON.parse(raw);
      answer =
        json.reply ??
        json.message ??
        json.content ??
        JSON.stringify(json, null, 2);
    } catch {
      // raw text is fine
    }

    if (!String(answer).trim()) {
      webview.postMessage({
        type: 'botMessage',
        text: '⚠️ NAVI backend returned an empty response.',
      });
    } else {
      webview.postMessage({
        type: 'botMessage',
        text: String(answer),
      });
    }

  } catch (err: any) {
    const msg = String(err?.message ?? err ?? 'unknown error');

    // These are expected when a stream is manually cancelled/closed.
    if (msg.includes('aborted') || msg.includes('terminated')) {
      console.warn('[AEP] NAVI connection aborted/terminated:', msg);
      // Only show a user-visible error if we never got content
      if (!assistantText.trim()) {
        webview.postMessage({
          type: 'botMessage',
          text: `⚠️ Error while streaming response from NAVI backend: ${msg}`,
        });
      }
      return;
    }

    console.error('[AEP] NAVI backend unreachable:', err);
    webview.postMessage({
      type: 'botMessage',
      text: `⚠️ Could not reach NAVI backend: ${msg}`,
    });
  }
}

/**
 * Get current editor context for NAVI
 */
function getEditorContext() {
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

export function activate(context: vscode.ExtensionContext) {
  console.log('[AEP] NAVI extension activating…');

  const provider = new NaviWebviewProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      NaviWebviewProvider.viewType,
      provider
    )
  );

  const openCommand = vscode.commands.registerCommand(
    'aep.openNavi',
    () => {
      vscode.commands.executeCommand('aep.chatView.focus');
    }
  );

  context.subscriptions.push(openCommand);
}

export function deactivate() {
  console.log('[AEP] NAVI extension deactivated');
}

function getWebviewContent(
  webview: vscode.Webview,
  extensionUri: vscode.Uri
): string {
  const nonce = getNonce();

  const scriptUri = webview.asWebviewUri(
    vscode.Uri.joinPath(extensionUri, 'media', 'panel.js')
  );
  const styleUri = webview.asWebviewUri(
    vscode.Uri.joinPath(extensionUri, 'media', 'panel.css')
  );
  const mascotUri = webview.asWebviewUri(
    vscode.Uri.joinPath(extensionUri, 'media', 'mascot-navi-fox.svg')
  );

  const cspSource = webview.cspSource;

  return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta
    http-equiv="Content-Security-Policy"
    content="default-src 'none'; style-src ${cspSource}; script-src 'nonce-${nonce}'; img-src ${cspSource} data:; connect-src http://127.0.0.1:8787 ws://127.0.0.1:8787;">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link href="${styleUri}" rel="stylesheet">
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