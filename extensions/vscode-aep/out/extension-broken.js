"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.deactivate = deactivate;
const vscode = require("vscode");
class NaviWebviewProvider {
    constructor(_extensionUri) {
        this._extensionUri = _extensionUri;
    }
    resolveWebviewView(webviewView, context, _token) {
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri]
        };
        webviewView.webview.html = getWebviewContent(webviewView.webview, this._extensionUri);
        // 🔌 Handle messages from the webview
        panel.webview.onDidReceiveMessage(async (msg) => {
            switch (msg.type) {
                case 'ready': {
                    // Initial welcome
                    panel.webview.postMessage({
                        type: 'botMessage',
                        text: `Hello! I'm NAVI, your autonomous engineering assistant. How can I help you today?`,
                    });
                    break;
                }
                case 'sendMessage': {
                    const text = String(msg.text || '').trim();
                    if (!text) {
                        return;
                    }
                    // TODO: wire this into real AEP backend later.
                    // For now, send a friendly demo reply.
                    const demoReply = `Got it! (demo mode) You said:\n\n` +
                        `> ${text}\n\n` +
                        `Soon I'll be wired into your AEP backend so I can run code analysis, ` +
                        `debugging, and architecture checks directly from here.`;
                    panel.webview.postMessage({
                        type: 'botMessage',
                        text: demoReply,
                    });
                    break;
                }
                case 'openSettings': {
                    vscode.commands.executeCommand('workbench.action.openSettings', '@ext:navralabs.aep-professional');
                    break;
                }
                case 'openConnectors': {
                    // Placeholder – later this can open a custom view / config page
                    vscode.window.showInformationMessage('Connectors coming soon: GitHub, Bitbucket, Jira, Slack, Teams, Confluence, cloud, and more.');
                    break;
                }
                case 'newChat': {
                    panel.webview.postMessage({ type: 'clearChat' });
                    panel.webview.postMessage({
                        type: 'botMessage',
                        text: `New chat started. What would you like to work on?`,
                    });
                    break;
                }
                default:
                    console.log('[AEP] Unknown message from webview:', msg);
            }
        });
    }
    ;
}
NaviWebviewProvider.viewType = 'aep.chatView';
function deactivate() {
    console.log('[AEP] NAVI extension deactivated.');
}
function getWebviewContent(webview, extensionUri) {
    const nonce = makeNonce();
    const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, 'media', 'panel.js'));
    const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, 'media', 'panel.css'));
    const mascotUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, 'media', 'mascot-navi-fox.svg'));
    const csp = [
        "default-src 'none'",
        `img-src ${webview.cspSource} data:`,
        `style-src ${webview.cspSource} 'unsafe-inline'`,
        `script-src 'nonce-${nonce}'`,
        `font-src ${webview.cspSource}`,
        `connect-src ${webview.cspSource}`,
    ].join('; ');
    return /* html */ `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Security-Policy" content="${csp}">
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>NAVI Assistant</title>
    <link rel="stylesheet" href="${styleUri}">
  </head>
  <body>
    <div id="root" data-mascot-src="${mascotUri}"></div>
    <script nonce="${nonce}" src="${scriptUri}"></script>
  </body>
</html>`;
}
function makeNonce() {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}
//# sourceMappingURL=extension-broken.js.map