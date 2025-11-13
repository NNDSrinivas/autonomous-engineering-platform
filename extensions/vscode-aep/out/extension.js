"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = require("vscode");
const VIEW_ID = 'aep.sidebar';
function activate(context) {
    const provider = new AepSidebarProvider(context);
    // Register the sidebar webview
    context.subscriptions.push(vscode.window.registerWebviewViewProvider(VIEW_ID, provider));
    // Command: AEP: Open Panel – just focuses the sidebar view
    context.subscriptions.push(vscode.commands.registerCommand('aep.openPanel', async () => {
        // Reveal our view container
        await vscode.commands.executeCommand('workbench.view.extension.aep');
        // Ask provider to reveal the webview itself if it's already resolved
        provider.reveal();
    }));
}
function deactivate() { }
class AepSidebarProvider {
    constructor(ctx) {
        this.ctx = ctx;
    }
    resolveWebviewView(webviewView, _context, _token) {
        this.view = webviewView;
        const webview = webviewView.webview;
        webview.options = {
            enableScripts: true,
            localResourceRoots: [vscode.Uri.joinPath(this.ctx.extensionUri, 'media')],
        };
        webview.html = this.getHtml(webview);
        webview.onDidReceiveMessage((msg) => {
            switch (msg.type) {
                case 'ready':
                    webview.postMessage({
                        type: 'bot',
                        text: "Hi! I'm NAVI, your AI engineering partner. I can help with code analysis, debugging, design decisions, and more. What would you like to work on today?",
                        time: now()
                    });
                    break;
                case 'send':
                    // Simple echo for now
                    webview.postMessage({
                        type: 'bot',
                        text: "Got it! This is a demo reply for now — soon I'll be wired into the AEP backend so I can actually reason about your code and tasks.",
                        time: now()
                    });
                    break;
                case 'attach':
                    vscode.window.showInformationMessage(`Attachment action: ${msg.action}`);
                    break;
                case 'openSettings':
                    vscode.commands.executeCommand('workbench.action.openSettings', 'aep');
                    break;
                default:
                    break;
            }
        });
    }
    // Called from the command to bring the view into focus
    reveal() {
        if (this.view) {
            try {
                // @ts-ignore
                this.view.show?.(true);
            }
            catch {
                // ignore – the container command already brought it into view
            }
        }
    }
    getHtml(webview) {
        const mediaRoot = vscode.Uri.joinPath(this.ctx.extensionUri, 'media');
        const cssUri = webview.asWebviewUri(vscode.Uri.joinPath(mediaRoot, 'panel.css'));
        const jsUri = webview.asWebviewUri(vscode.Uri.joinPath(mediaRoot, 'panel.js'));
        const mascotUri = webview.asWebviewUri(vscode.Uri.joinPath(mediaRoot, 'mascot-navi-fox.svg'));
        const nonce = makeNonce();
        const csp = [
            "default-src 'none'",
            `img-src ${webview.cspSource} data:`,
            `style-src ${webview.cspSource} 'unsafe-inline'`,
            `script-src 'nonce-${nonce}'`,
            `font-src ${webview.cspSource}`,
            `connect-src ${webview.cspSource}`,
        ].join('; ');
        return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="${csp}">
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="stylesheet" href="${cssUri}" />
  <title>AEP Professional</title>
</head>
<body>
  <div id="root">
    <header class="topbar">
      <div class="brand">
        <!-- Inline NAVI fox so we never depend on paths -->
        <svg class="mascot" viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg" aria-label="NAVI fox">
          <defs>
            <linearGradient id="p" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#FF8A3D"/>
              <stop offset="100%" stop-color="#FF5E7E"/>
            </linearGradient>

            <style>
              @keyframes nod {0%{transform:rotate(0)}50%{transform:rotate(-2.5deg)}100%{transform:rotate(0)}}
              @keyframes blink {0%,92%,100%{transform:scaleY(1)}96%{transform:scaleY(.1)}}
              @keyframes pulse {0%{r:22;opacity:.55}70%{r:28;opacity:0}100%{r:28;opacity:0}}
              @keyframes earFlick {0%{transform:rotate(0)}40%{transform:rotate(-12deg)}80%{transform:rotate(10deg)}100%{transform:rotate(0)}}
              @keyframes tailWave {0%{transform:rotate(0)}50%{transform:rotate(12deg)}100%{transform:rotate(0)}}

              #head{transform-origin:22px 22px;animation:nod 5s ease-in-out infinite}
              .eye{animation:blink 6s ease-in-out infinite;transform-origin:50% 50%}
              .pulse-ring{fill:none;stroke:url(#p);stroke-width:2.4;opacity:0}
            </style>
          </defs>

          <circle class="pulse-ring" cx="22" cy="22" r="22"/>

          <g id="tail" transform="translate(33,29)">
            <path d="M0 0 C7 0 9 7 3 10 C-1 12 -2 7 0 0 Z" fill="url(#p)" opacity=".85"/>
          </g>

          <g id="head">
            <path d="M22 5 L36 16 33 34 22 39 11 34 8 16Z" fill="url(#p)"/>

            <g id="earL" transform="translate(12,14)">
              <path d="M0 3 L6 -1 4 6 Z" fill="#fff" opacity=".95"/>
            </g>
            <g id="earR" transform="translate(26,14)">
              <path d="M6 3 L0 -1 2 6 Z" fill="#fff" opacity=".95"/>
            </g>

            <ellipse cx="18" cy="24" rx="1.6" ry="1.6" class="eye" fill="#0F172A"/>
            <ellipse cx="26" cy="24" rx="1.6" ry="1.6" class="eye" fill="#0F172A"/>
            <rect x="20.3" y="26.5" width="3.4" height="1.2" rx=".6" fill="#0F172A" opacity=".75"/>
          </g>
        </svg>

        <div class="titles">
          <div class="title">AEP Professional</div>
          <div class="subtitle">Your AI engineering partner</div>
        </div>
      </div>
      <div class="header-right">
        <button class="top-icon" data-action="refresh" title="Restart chat">
          <span class="icon-symbol">↻</span>
        </button>
        <button class="top-icon" data-action="new" title="New conversation">
          <span class="icon-symbol">✚</span>
        </button>
        <button class="top-icon" data-action="focus-code" title="Code focus">
          <span class="icon-symbol">◎</span>
        </button>
        <button class="top-icon" data-action="sources" title="Connections · MCP, Slack, Git…">
          <span class="icon-symbol">⛓</span>
        </button>
        <button class="top-icon" data-action="settings" title="Settings">
          <span class="icon-symbol">⚙</span>
        </button>
      </div>
    </header>

    <main id="messages" class="messages" aria-live="polite"></main>

    <footer class="composer">
      <div class="bar">
        <button id="attachBtn" class="attach-btn" aria-label="Attach">+</button>
        <textarea id="input" rows="1" placeholder="Ask NAVI about your code or task..."></textarea>
        <button id="sendBtn" class="send" aria-label="Send">Send</button>

        <div id="attachMenu" class="menu attach-menu" role="menu" aria-hidden="true">
          <button data-action="file" role="menuitem">Attach files…</button>
          <button data-action="image" role="menuitem">Add image…</button>
          <button data-action="code" role="menuitem">Insert code…</button>
          <button data-action="screenshot" role="menuitem">Screenshot window…</button>
          <button data-action="repo" role="menuitem">Connect repo…</button>
        </div>
      </div>

      <div class="bottom-row">
        <div class="chip-with-menu">
          <button class="small-pill" id="modelChip">
            <span class="chip-label">MODEL</span>
            <span class="chip-value" id="modelValBottom">OpenAI GPT-4o — Flagship</span>
            <span class="chip-caret">▾</span>
          </button>
          <div class="chip-menu" id="modelMenu" aria-hidden="true">
            <button data-model="OpenAI GPT-4o — Flagship">OpenAI GPT-4o — Flagship</button>
            <button data-model="OpenAI GPT-4o-mini">OpenAI GPT-4o-mini</button>
            <button data-model="Anthropic Claude 3.5 Sonnet">Anthropic Claude 3.5 Sonnet</button>
            <button data-model="Anthropic Claude 3.5 Haiku">Anthropic Claude 3.5 Haiku</button>
            <button data-model="Llama 3.1 405B (API)">Llama 3.1 405B (API)</button>
            <button data-model="Bring your own API key…">Bring your own API key…</button>
          </div>
        </div>

        <div class="chip-with-menu">
          <button class="small-pill" id="modeChip">
            <span class="chip-label">MODE</span>
            <span class="chip-value" id="modeValBottom">Agent (full access)</span>
            <span class="chip-caret">▾</span>
          </button>
          <div class="chip-menu" id="modeMenu" aria-hidden="true">
            <button data-mode="Agent (full access)">Agent (full access)</button>
            <button data-mode="Lightweight inline hints">Lightweight inline hints</button>
            <button data-mode="Explain only">Explain only</button>
          </div>
        </div>
      </div>
    </footer>
  </div>
  <script nonce="${nonce}" src="${jsUri}"></script>
</body>
</html>`;
    }
}
function makeNonce() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    return Array.from({ length: 32 }, () => chars.charAt(Math.floor(Math.random() * chars.length))).join('');
}
function now() {
    return new Date().toTimeString().slice(0, 5);
}
//# sourceMappingURL=extension.js.map