import * as vscode from 'vscode';

class NaviWebviewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'aep.chatView';

  constructor(private readonly _extensionUri: vscode.Uri) { }

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken,
  ) {
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri],
    };

    webviewView.webview.html = getWebviewContent(webviewView.webview, this._extensionUri);

    webviewView.webview.onDidReceiveMessage(async (msg: any) => {
      switch (msg.type) {
        case 'ready': {
          const hasHistory = !!msg.hasHistory;
          if (!hasHistory) {
            webviewView.webview.postMessage({
              type: 'botMessage',
              text: `Hello! I'm NAVI, your autonomous engineering assistant. How can I help you today?`,
            });
          }
          break;
        }

        case 'sendMessage': {
          const text = String(msg.text || '').trim();
          if (!text) return;

          console.log('[AEP] User message:', text);
          this.callNaviBackend(text, webviewView);
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

        case 'openMcp': {
          vscode.window.showInformationMessage(
            'MCP servers & connectors configuration will live here (coming soon).',
          );
          break;
        }

        case 'openSettings': {
          vscode.window.showInformationMessage(
            'NAVI settings: configuration panel coming soon!',
          );
          break;
        }

        case 'modelChanged': {
          const label = String(msg.value || '').trim();
          if (!label) return;
          webviewView.webview.postMessage({
            type: 'botMessage',
            text: `Switched model to **${label}** (demo-only selector for now).`,
          });
          break;
        }

        case 'modeChanged': {
          const label = String(msg.value || '').trim();
          if (!label) return;
          webviewView.webview.postMessage({
            type: 'botMessage',
            text: `Mode updated to **${label}** (demo-only for now).`,
          });
          break;
        }

        case 'attachTypeSelected': {
          const type = String(msg.value || '').trim();
          if (!type) return;
          vscode.window.showInformationMessage(
            `Attachment flow for "${type}" is not wired yet – this will open the real picker later.`,
          );
          break;
        }

        default:
          console.warn('[AEP] Unknown message type:', msg?.type);
      }
    });
  }

  private async callNaviBackend(message: string, webviewView: vscode.WebviewView) {
    try {
      // Show typing indicator
      webviewView.webview.postMessage({ type: 'showTyping' });

      // Get backend URL from configuration
      const config = vscode.workspace.getConfiguration('aep');
      const backendUrl = config.get<string>('naviBackendUrl', 'http://localhost:8000');

      console.log('[AEP] Calling NAVI backend:', backendUrl);

      // Make HTTP request to backend
      const response = await fetch(`${backendUrl}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message }),
      });

      if (!response.ok) {
        throw new Error(`Backend responded with ${response.status}: ${response.statusText}`);
      }

      const data = await response.json() as { reply?: string };
      const reply = data.reply || 'No response received from backend';

      // Hide typing indicator and send response
      webviewView.webview.postMessage({ type: 'hideTyping' });
      webviewView.webview.postMessage({
        type: 'botMessage',
        text: reply,
      });

    } catch (error) {
      console.error('[AEP] Backend call failed:', error);

      // Hide typing indicator and send error
      webviewView.webview.postMessage({ type: 'hideTyping' });
      webviewView.webview.postMessage({
        type: 'botMessage',
        text: `⚠️ **Backend Error**: ${error instanceof Error ? error.message : 'Unknown error'}\n\nMake sure your NAVI backend is running at the configured URL (check VS Code Settings → AEP → NAVI Backend URL).`,
      });
    }
  }
}

export function activate(context: vscode.ExtensionContext) {
  console.log('[AEP] NAVI extension activating…');

  const provider = new NaviWebviewProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(NaviWebviewProvider.viewType, provider),
  );

  const openCommand = vscode.commands.registerCommand('aep.openNavi', () => {
    vscode.commands.executeCommand('aep.chatView.focus');
  });

  context.subscriptions.push(openCommand);
}

function getWebviewContent(webview: vscode.Webview, extensionUri: vscode.Uri): string {
  const nonce = getNonce();

  const scriptUri = webview.asWebviewUri(
    vscode.Uri.joinPath(extensionUri, 'media', 'panel.js'),
  );
  const styleUri = webview.asWebviewUri(
    vscode.Uri.joinPath(extensionUri, 'media', 'panel.css'),
  );

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'none'; style-src ${webview.cspSource}; script-src 'nonce-${nonce}'; img-src ${webview.cspSource} data:;">
  <link href="${styleUri}" rel="stylesheet" />
  <title>NAVI Assistant</title>
</head>
<body>
  <div id="root"></div>
  <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
}

function getNonce(): string {
  let text = '';
  const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  for (let i = 0; i < 32; i++) {
    text += possible.charAt(Math.floor(Math.random() * possible.length));
  }
  return text;
}

export function deactivate() {
  console.log('[AEP] NAVI extension deactivated');
}