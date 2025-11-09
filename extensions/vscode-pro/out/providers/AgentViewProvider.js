"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.AgentViewProvider = void 0;
const vscode = __importStar(require("vscode"));
class AgentViewProvider {
    constructor(ctx, state) {
        this.ctx = ctx;
        this.state = state;
    }
    resolveWebviewView(view) {
        view.webview.options = { enableScripts: true };
        view.webview.html = this.render(view.webview);
        view.webview.onDidReceiveMessage(msg => {
            switch (msg.t) {
                case 'signin':
                    vscode.commands.executeCommand('aep.connect');
                    break;
                case 'signout':
                    vscode.commands.executeCommand('aep.disconnect');
                    break;
                case 'start':
                    vscode.commands.executeCommand('aep.ai.newSession');
                    break;
                case 'settings':
                    vscode.commands.executeCommand('workbench.action.openSettings', '@ext:navralabs-dev.aep-professional-dev');
                    break;
            }
        });
    }
    refresh() {
        // VS Code will re-call resolveWebviewView when the view is shown again.
        // For immediate refresh, ask the user to toggle the view if needed.
        vscode.commands.executeCommand('workbench.action.webview.reloadWebviewAction').then(() => { }, () => { });
    }
    render(webview) {
        const signedIn = !!this.state.token;
        const profile = this.state.profile || {};
        const name = profile.name || profile.email || 'Developer';
        const initials = (profile.name || profile.email || '?')
            .split('@')[0]
            .split(/[.\s_-]+/)
            .slice(0, 2)
            .map((p) => p.charAt(0).toUpperCase())
            .join('');
        const css = `
      <style>
        :root {
          --bg: #0f1115;
          --panel: #141720;
          --border: #202534;
          --fg: #e7eaf0;
          --muted: #8a93a5;
          --primary: #6e8cff;
          --accent: #22c55e;
          --danger: #ff6b6b;
          --button: #2a2f40;
        }
        * { box-sizing: border-box; }
        body {
          margin: 0; padding: 0; font-family: var(--vscode-font-family);
          color: var(--fg); background: radial-gradient(1200px 600px at 80% -10%, #1b2140 0%, #0f1115 60%);
        }
        .wrap { padding: 14px; }
        .card {
          background: var(--panel);
          border: 1px solid var(--border);
          border-radius: 10px;
          padding: 14px;
          box-shadow: 0 0 0 1px rgba(255,255,255,0.02) inset;
        }
        .top {
          display: flex; align-items: center; justify-content: space-between;
          margin-bottom: 12px;
        }
        .brand { display: flex; align-items: center; gap: 10px; }
        .logo {
          width: 26px; height: 26px;
          background: linear-gradient(135deg, #7c5cff, #4db9ff);
          border-radius: 6px;
        }
        .title { font-weight: 600; letter-spacing: .3px; }
        .actions { display: flex; gap: 8px; }
        button {
          appearance: none; border: 1px solid var(--border);
          background: var(--button); color: var(--fg);
          padding: 6px 10px; border-radius: 8px; cursor: pointer; font-size: 12px;
        }
        .primary { background: var(--primary); border-color: transparent; }
        .danger { background: var(--danger); border-color: transparent; }
        .accent { background: var(--accent); border-color: transparent; color: #0a0c12; }
        .row { display: grid; gap: 10px; }
        .hero {
          display: grid; gap: 10px; margin-top: 6px;
          grid-template-columns: 1fr;
        }
        .welcome h2 { margin: 4px 0 4px; font-size: 16px; }
        .welcome p { margin: 0; color: var(--muted); font-size: 12px; }
        .btns { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
        .status {
          display: inline-flex; gap: 6px; align-items: center;
          padding: 2px 8px; border-radius: 999px; font-size: 11px;
          border: 1px solid var(--border); background: #192033;
          color: #b7c1d9;
        }
        .grid { display: grid; gap: 10px; grid-template-columns: 1fr 1fr; }
        .tile { background: #101420; border: 1px dashed var(--border); border-radius: 8px; padding: 10px; min-height: 70px; }
        .tile h4 { margin: 0 0 6px; font-size: 12px; color: #cfd6e6; }
        .tile p { margin: 0; font-size: 12px; color: var(--muted); }
        .avatar {
          width: 26px; height: 26px; border-radius: 999px;
          background: #2b3045; color:#cfe2ff; display:flex; align-items:center; justify-content:center;
          font-weight: 700; font-size: 12px; border:1px solid var(--border);
        }
        .toolbar { display:flex; align-items:center; gap:10px; }
        .link { color:#9fb6ff; text-decoration: underline; cursor: pointer; }
      </style>
    `;
        const header = `
      <div class="top">
        <div class="brand">
          <div class="logo"></div>
          <div class="title">AEP Agent</div>
          <span class="status">Agent online</span>
        </div>
        <div class="toolbar">
          ${signedIn ? `<div class="avatar" title="${this.escape(name)}">${initials}</div>` : ''}
          <button onclick="post('settings')">Settings</button>
          ${signedIn
            ? `<button class="danger" onclick="post('signout')">Sign out</button>`
            : `<button class="primary" onclick="post('signin')">Sign in</button>`}
        </div>
      </div>
    `;
        const preLogin = `
      <div class="row">
        <div class="welcome">
          <h2>Welcome to your AI Engineering Partner</h2>
          <p>Sign in to connect your org and unlock plans, context packs, and live coding help.</p>
          <div class="btns">
            <button class="primary" onclick="post('signin')">🔐 Sign in with Auth0</button>
            <button onclick="post('settings')">Learn more / Settings</button>
          </div>
        </div>
        <div class="grid">
          <div class="tile">
            <h4>JIRA & GitHub context</h4>
            <p>See issues, commits, and PRs inline while you work.</p>
          </div>
          <div class="tile">
            <h4>Plan → Act</h4>
            <p>Approve steps; agent applies changes with your permission.</p>
          </div>
        </div>
      </div>
    `;
        const postLogin = `
      <div class="row">
        <div class="welcome">
          <h2>Hi ${this.escape(name)} 👋</h2>
          <p>Everything's set. Start a session to load issues, plans, and live collaboration.</p>
          <div class="btns">
            <button class="accent" onclick="post('start')">🚀 Start Session</button>
            <button onclick="post('settings')">⚙️ Settings</button>
          </div>
        </div>
        <div class="grid">
          <div class="tile">
            <h4>Recent activity</h4>
            <p>Plans executed, last 24h: <strong>3</strong> • Cursor sync: <strong>enabled</strong></p>
          </div>
          <div class="tile">
            <h4>Org & Role</h4>
            <p>${this.escape(profile.org || 'Your Organization')} • ${this.escape(profile.role || 'developer')}</p>
          </div>
        </div>
      </div>
    `;
        return `<!DOCTYPE html><html><head>
      <meta charset="UTF-8" />
      ${css}
    </head>
    <body>
      <div class="wrap">
        <div class="card">
          ${header}
          <div class="hero">${signedIn ? postLogin : preLogin}</div>
        </div>
      </div>
      <script>
        const vscode = acquireVsCodeApi();
        function post(t){ vscode.postMessage({t}); }
      </script>
    </body></html>`;
    }
    escape(s) {
        return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }
}
exports.AgentViewProvider = AgentViewProvider;
//# sourceMappingURL=AgentViewProvider.js.map