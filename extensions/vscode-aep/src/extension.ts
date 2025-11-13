import * as vscode from 'vscode';

const VIEW_ID = 'aep.sidebar';

export function activate(context: vscode.ExtensionContext) {
  const provider = new AepSidebarProvider(context);

  // Sidebar webview
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(VIEW_ID, provider)
  );

  // Command palette entry – focuses the sidebar
  context.subscriptions.push(
    vscode.commands.registerCommand('aep.openPanel', async () => {
      await vscode.commands.executeCommand('workbench.view.extension.aep');
      provider.reveal();
    })
  );
}

export function deactivate() { }

class AepSidebarProvider implements vscode.WebviewViewProvider {
  private view: vscode.WebviewView | undefined;

  constructor(private readonly ctx: vscode.ExtensionContext) { }

  resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ) {
    this.view = webviewView;

    const webview = webviewView.webview;
    webview.options = {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.joinPath(this.ctx.extensionUri, 'media')],
    };

    webview.html = this.getHtml(webview);

    webview.onDidReceiveMessage((msg) => {
      switch (msg.type) {
        case 'ready': {
          this.sendWelcome(webview);
          break;
        }

        case 'send': {
          // Demo reply – later this will call the real backend
          webview.postMessage({
            type: 'bot',
            text:
              "Got it! This is a demo reply for now — soon I'll be wired into the AEP backend so I can actually reason about your code and tasks.",
            time: now(),
          });
          break;
        }

        case 'attach': {
          vscode.window.showInformationMessage(
            `Attachment action: ${msg.action}`
          );
          break;
        }

        case 'toolbar': {
          this.handleToolbar(msg.action, webview);
          break;
        }

        case 'setModel': {
          // later: persist + forward to backend
          vscode.window.setStatusBarMessage(`AEP model: ${msg.value}`, 2000);
          break;
        }

        case 'setMode': {
          vscode.window.setStatusBarMessage(`AEP mode: ${msg.value}`, 2000);
          break;
        }

        case 'openSettings': {
          vscode.commands.executeCommand('workbench.action.openSettings', 'aep');
          break;
        }
      }
    });
  }

  reveal() {
    if (this.view) {
      try {
        // @ts-ignore
        this.view.show?.(true);
      } catch {
        // noop
      }
    }
  }

  private sendWelcome(webview: vscode.Webview) {
    webview.postMessage({
      type: 'reset',
    });

    webview.postMessage({
      type: 'bot',
      text:
        "Hi! I'm NAVI, your AI engineering partner. I can help with code analysis, debugging, design decisions, and more. What would you like to work on today?",
      time: now(),
    });
  }

  private handleToolbar(action: string, webview: vscode.Webview) {
    switch (action) {
      case 'refresh':
        this.sendWelcome(webview);
        break;

      case 'new':
        webview.postMessage({ type: 'reset' });
        this.sendWelcome(webview);
        break;

      case 'focus':
        vscode.window.showInformationMessage(
          'Focus on current file/selection will be wired up soon.'
        );
        break;

      case 'settings':
        vscode.commands.executeCommand('workbench.action.openSettings', 'aep');
        break;

      case 'connect':
        vscode.window.showInformationMessage(
          'Connections hub (Slack, Jira, GitHub, MCP servers, etc.) will live here.'
        );
        break;
    }
  }

  private getHtml(webview: vscode.Webview): string {
    const mediaRoot = vscode.Uri.joinPath(this.ctx.extensionUri, 'media');

    const cssUri = webview.asWebviewUri(
      vscode.Uri.joinPath(mediaRoot, 'panel.css')
    );
    const jsUri = webview.asWebviewUri(
      vscode.Uri.joinPath(mediaRoot, 'panel.js')
    );
    const mascotUri = webview.asWebviewUri(
      vscode.Uri.joinPath(mediaRoot, 'navi-fox.svg')
    );

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
        <img src="${mascotUri}" alt="NAVI" class="mascot" />
        <div class="titles">
          <div class="title">AEP Professional</div>
          <div class="subtitle">Your AI engineering partner</div>
        </div>
      </div>
      <div class="header-right">
        <button class="ctrl" data-action="refresh" title="Restart conversation">⟳</button>
        <button class="ctrl" data-action="new" title="New chat">＋</button>
        <button class="ctrl" data-action="focus" title="Focus current file / selection">◎</button>
        <button class="ctrl" data-action="settings" title="Settings">⚙</button>
        <button class="ctrl" data-action="connect" title="Connections / MCP / Apps">⇄</button>
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
        <button class="small-pill dropdown" id="modelPill">
          <span class="label">MODEL</span>
          <span class="value" id="modelValBottom">OpenAI GPT-4o — Flagship</span>
          <span class="caret">▾</span>
        </button>

        <button class="small-pill dropdown" id="modePill">
          <span class="label">MODE</span>
          <span class="value" id="modeValBottom">Agent (full access)</span>
          <span class="caret">▾</span>
        </button>

        <div id="modelMenu" class="menu floating" aria-hidden="true"></div>
        <div id="modeMenu" class="menu floating" aria-hidden="true"></div>
      </div>
    </footer>
  </div>
  <script nonce="${nonce}" src="${jsUri}"></script>
</body>
</html>`;
  }
}

function makeNonce(): string {
  const chars =
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  return Array.from({ length: 32 }, () =>
    chars.charAt(Math.floor(Math.random() * chars.length))
  ).join('');
}

function now(): string {
  return new Date().toTimeString().slice(0, 5);
}
