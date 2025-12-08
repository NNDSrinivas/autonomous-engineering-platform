import * as vscode from 'vscode';

class NaviWebviewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'aep.chatView';

  constructor(private readonly _extensionUri: vscode.Uri) { }

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken,
  ) {
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri]
    };

    webviewView.webview.html = getWebviewContent(webviewView.webview, this._extensionUri);

    // Handle messages from the webview
    webviewView.webview.onDidReceiveMessage(async (msg: any) => {
      switch (msg.type) {
        case 'ready': {
          // Initial welcome
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

          // Echo back for now - this is where you'd integrate with your backend
          setTimeout(() => {
            webviewView.webview.postMessage({
              type: 'botMessage',
              text: `I received your message: "${text}". I'm currently in demo mode - backend integration coming soon!`,
            });
          }, 500);
          break;
        }

        // 🔽 NEW: handle header buttons directly
        case 'newChat': {
          webviewView.webview.postMessage({ type: 'clearChat' });
          webviewView.webview.postMessage({
            type: 'botMessage',
            text: 'New chat started! How can I help you?',
          });
          break;
        }

        case 'openConnectors': {
          vscode.window.showInformationMessage('NAVI connectors: repo + tool integrations coming soon!');
          break;
        }

        case 'openSettings': {
          vscode.window.showInformationMessage('NAVI settings panel coming soon!');
          break;
        }

        default:
          console.warn('[AEP] Unknown message type:', msg.type);
      }
    });
  }
}

export function activate(context: vscode.ExtensionContext) {
  console.log('[AEP] NAVI extension activating…');

  // Register the webview view provider
  const provider = new NaviWebviewProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(NaviWebviewProvider.viewType, provider)
  );

  // Register the command to open NAVI (for command palette access)
  const openCommand = vscode.commands.registerCommand('aep.openNavi', () => {
    vscode.commands.executeCommand('aep.chatView.focus');
  });

  context.subscriptions.push(openCommand);
}

function getWebviewContent(webview: vscode.Webview, extensionUri: vscode.Uri): string {
  // Generate a nonce for CSP
  const nonce = getNonce();

  // Get URIs for resources
  const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, 'media', 'panel.js'));
  const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, 'media', 'panel.css'));
  const mascotUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, 'media', 'mascot-navi-fox.svg'));

  return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource}; script-src 'nonce-${nonce}'; img-src ${webview.cspSource} data:;">
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
  const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  for (let i = 0; i < 32; i++) {
    text += possible.charAt(Math.floor(Math.random() * possible.length));
  }
  return text;
}

export function deactivate() {
  console.log('[AEP] NAVI extension deactivated');
}