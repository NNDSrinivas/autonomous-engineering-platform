"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = require("vscode");
const nonce_1 = require("./nonce");
function activate(context) {
    console.log("🚀 AEP Extension activated");
    const provider = new AepChatViewProvider(context);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider("aep.chatView", provider, { webviewOptions: { retainContextWhenHidden: true } }));
    context.subscriptions.push(vscode.commands.registerCommand("aep.openPanel", () => {
        vscode.commands.executeCommand("workbench.view.extension.aep");
    }));
}
class AepChatViewProvider {
    constructor(context) {
        this.context = context;
    }
    resolveWebviewView(webviewView) {
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [
                this.context.extensionUri,
                vscode.Uri.joinPath(this.context.extensionUri, "media")
            ]
        };
        webviewView.webview.html = this.getHtml(webviewView.webview);
        // Handle messages
        webviewView.webview.onDidReceiveMessage(async (msg) => {
            if (msg.type === "sendMessage") {
                webviewView.webview.postMessage({
                    type: "botResponse",
                    text: `NAVI Received: ${msg.text}`
                });
            }
        });
    }
    getHtml(webview) {
        const nonce = (0, nonce_1.getNonce)();
        const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this.context.extensionUri, "media", "panel.js"));
        const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(this.context.extensionUri, "media", "panel.css"));
        const mascotUri = webview.asWebviewUri(vscode.Uri.joinPath(this.context.extensionUri, "media", "mascot-navi-fox.svg"));
        return /* html */ `
      <!DOCTYPE html>
      <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <meta http-equiv="Content-Security-Policy"
              content="default-src 'none';
                       img-src ${webview.cspSource} https:;
                       script-src 'nonce-${nonce}';
                       style-src ${webview.cspSource} 'unsafe-inline';
                       font-src ${webview.cspSource};
                       connect-src https:;
              ">
        <link rel="stylesheet" href="${styleUri}">
        <title>NAVI</title>
      </head>

      <body>
        <div id="app">

          <header class="header">
            <img src="${mascotUri}" class="logo" />
            <div class="header-title">NAVI — Autonomous Engineering Assistant</div>

            <div class="header-icons">
              <button class="icon-btn" data-tip="New Chat">🗎</button>
              <button class="icon-btn" data-tip="Connectors">🔌</button>
              <button class="icon-btn" data-tip="Settings">⚙️</button>
            </div>
          </header>

          <div id="chat-container"></div>

          <footer class="footer">
            <div class="footer-controls">
              <select id="modelSelect">
                <option>ChatGPT 5.1</option>
                <option>GPT-4.1</option>
                <option>Claude 3.7</option>
                <option>Gemini 2.0 Flash</option>
                <option>Local Model (LM Studio)</option>
                <option>Bring Your Own Key...</option>
              </select>

              <select id="modeSelect">
                <option>General</option>
                <option>Code</option>
                <option>Debug</option>
                <option>Explain</option>
              </select>
            </div>

            <div class="input-row">
              <button id="addAttachment">+</button>
              <input id="chatInput" placeholder="Ask NAVI anything…" />
              <button id="sendBtn">➤</button>
            </div>
          </footer>

        </div>

        <script nonce="${nonce}" src="${scriptUri}"></script>
      </body>
      </html>
    `;
    }
}
function deactivate() { }
//# sourceMappingURL=extension-old.js.map