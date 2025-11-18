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
exports.AgentHomeViewProvider = void 0;
const vscode = __importStar(require("vscode"));
const getUri_1 = require("../webview/getUri");
class AgentHomeViewProvider {
    constructor(ctx) {
        this.ctx = ctx;
        this._isAuthenticated = false;
    }
    refresh() {
        if (this._view) {
            this._view.webview.html = this.getHtmlContent(this._view.webview);
        }
    }
    resolveWebviewView(view) {
        this._view = view;
        view.webview.options = { enableScripts: true, localResourceRoots: [this.ctx.extensionUri] };
        view.webview.html = this.getHtmlContent(view.webview);
        view.webview.onDidReceiveMessage(async (message) => {
            try {
                console.log('Received message:', message);
                vscode.window.showInformationMessage(`Button clicked: ${message.command}`);
                switch (message.command) {
                    case 'signin':
                        await this.handleSignIn();
                        break;
                    case 'signout':
                        await this.handleSignOut();
                        break;
                    case 'settings':
                        await vscode.commands.executeCommand('workbench.action.openSettings', '@ext:navralabs-dev.aep-professional-dev');
                        break;
                    case 'startSession':
                        await this.handleStartSession();
                        break;
                    case 'openDocs':
                        await vscode.env.openExternal(vscode.Uri.parse('https://github.com/NNDSrinivas/autonomous-engineering-platform'));
                        break;
                    default:
                        vscode.window.showWarningMessage(`Unknown command: ${message.command}`);
                }
            }
            catch (error) {
                vscode.window.showErrorMessage(`Error: ${error}`);
            }
        });
    }
    async handleSignIn() {
        try {
            vscode.window.showInformationMessage('🔐 Authenticating with Auth0...');
            // Simulate auth process
            await new Promise(resolve => setTimeout(resolve, 1500));
            // Set authenticated state
            this._isAuthenticated = true;
            await vscode.commands.executeCommand('setContext', 'aep.authenticated', true);
            // Store mock profile
            await this.ctx.globalState.update('aep.token', 'auth_token_' + Date.now());
            await this.ctx.globalState.update('aep.profile', {
                name: 'Developer User',
                email: 'user@navralabs.com',
                organization: 'Navra Labs'
            });
            vscode.window.showInformationMessage('✅ Successfully authenticated!');
            this.refresh();
        }
        catch (error) {
            vscode.window.showErrorMessage('Authentication failed');
        }
    }
    async handleSignOut() {
        this._isAuthenticated = false;
        await vscode.commands.executeCommand('setContext', 'aep.authenticated', false);
        await this.ctx.globalState.update('aep.token', undefined);
        await this.ctx.globalState.update('aep.profile', undefined);
        vscode.window.showInformationMessage('👋 Signed out successfully');
        this.refresh();
    }
    async handleStartSession() {
        if (!this._isAuthenticated) {
            vscode.window.showWarningMessage('Please sign in first to start a session');
            return;
        }
        vscode.window.showInformationMessage('🚀 Starting AI engineering session...');
    }
    getHtmlContent(webview) {
        const toolkitUri = (0, getUri_1.getUri)(webview, this.ctx.extensionUri, ['node_modules', '@vscode', 'webview-ui-toolkit', 'dist', 'toolkit.js']);
        const profile = this.ctx.globalState.get('aep.profile');
        return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src ${webview.cspSource}; font-src ${webview.cspSource};">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AEP Professional</title>
  <script type="module" src="${toolkitUri}"></script>
  <style>
    :root {
      --container-padding: 20px;
      --border-radius: 8px;
      --section-spacing: 16px;
    }
    
    body {
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size);
      font-weight: var(--vscode-font-weight);
      color: var(--vscode-foreground);
      background-color: var(--vscode-sideBar-background);
      margin: 0;
      padding: 0;
    }
    
    .container {
      padding: var(--container-padding);
      max-width: 100%;
    }
    
    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: var(--section-spacing);
      padding: 12px 16px;
      background: var(--vscode-editor-background);
      border: 1px solid var(--vscode-panel-border);
      border-radius: var(--border-radius);
    }
    
    .brand {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    
    .logo {
      width: 24px;
      height: 24px;
      background: linear-gradient(45deg, #007ACC, #1177BB);
      border-radius: 4px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-weight: bold;
      font-size: 12px;
    }
    
    .brand-text {
      font-weight: 600;
      color: var(--vscode-foreground);
    }
    
    .status-badge {
      background: var(--vscode-statusBar-background);
      color: var(--vscode-statusBar-foreground);
      padding: 4px 8px;
      border-radius: 12px;
      font-size: 11px;
      font-weight: 500;
    }
    
    .main-content {
      background: var(--vscode-editor-background);
      border: 1px solid var(--vscode-panel-border);
      border-radius: var(--border-radius);
      padding: 20px;
      margin-bottom: var(--section-spacing);
    }
    
    .welcome-section h2 {
      margin: 0 0 8px 0;
      font-size: 18px;
      font-weight: 600;
      color: var(--vscode-foreground);
    }
    
    .welcome-section p {
      margin: 0 0 16px 0;
      color: var(--vscode-descriptionForeground);
      line-height: 1.4;
    }
    
    .button-group {
      display: flex;
      gap: 8px;
      margin: 16px 0;
      flex-wrap: wrap;
    }
    
    .feature-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-top: 20px;
    }
    
    @media (max-width: 400px) {
      .feature-grid {
        grid-template-columns: 1fr;
      }
    }
    
    .feature-card {
      background: var(--vscode-sideBar-background);
      border: 1px solid var(--vscode-panel-border);
      border-radius: var(--border-radius);
      padding: 12px;
    }
    
    .feature-card h4 {
      margin: 0 0 6px 0;
      font-size: 13px;
      font-weight: 600;
      color: var(--vscode-foreground);
    }
    
    .feature-card p {
      margin: 0;
      font-size: 12px;
      color: var(--vscode-descriptionForeground);
      line-height: 1.3;
    }
    
    .user-info {
      background: var(--vscode-statusBarItem-hoverBackground);
      border-radius: var(--border-radius);
      padding: 12px;
      margin-bottom: 16px;
    }
    
    .user-info h3 {
      margin: 0 0 4px 0;
      font-size: 16px;
      color: var(--vscode-foreground);
    }
    
    .user-info p {
      margin: 0;
      font-size: 12px;
      color: var(--vscode-descriptionForeground);
    }
    
    .footer {
      margin-top: 20px;
      padding-top: 16px;
      border-top: 1px solid var(--vscode-panel-border);
      font-size: 11px;
      color: var(--vscode-descriptionForeground);
      text-align: center;
    }
    
    /* Custom Button Styles */
    .primary-btn, .secondary-btn {
      border: none;
      border-radius: 2px;
      padding: 8px 14px;
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size);
      font-weight: 500;
      cursor: pointer;
      transition: background-color 0.1s ease;
      display: inline-block;
      text-align: center;
      text-decoration: none;
      outline: none;
    }
    
    .primary-btn {
      background-color: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
    }
    
    .primary-btn:hover {
      background-color: var(--vscode-button-hoverBackground);
    }
    
    .primary-btn:active {
      background-color: var(--vscode-button-background);
      transform: translateY(1px);
    }
    
    .secondary-btn {
      background-color: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
      border: 1px solid var(--vscode-button-border, transparent);
    }
    
    .secondary-btn:hover {
      background-color: var(--vscode-button-secondaryHoverBackground);
    }
    
    .secondary-btn:active {
      transform: translateY(1px);
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="brand">
        <div class="logo">A</div>
        <span class="brand-text">AEP Professional</span>
      </div>
      <div class="status-badge">● Connected</div>
    </div>
    
    <div class="main-content">
      ${this._isAuthenticated ? this.getAuthenticatedContent(profile) : this.getUnauthenticatedContent()}
    </div>
    
    <div class="footer">
      <p>Powered by Navra Labs • <vscode-link href="#" id="docsLink">Documentation</vscode-link></p>
    </div>
  </div>

  <script>
    (function() {
      const vscode = acquireVsCodeApi();
      console.log('AEP Extension script loaded');
      
      function sendMessage(command, data = {}) {
        console.log('Sending message:', command, data);
        vscode.postMessage({ command, ...data });
      }
      
      // Wait for DOM to be ready
      function initializeButtons() {
        // Button event listeners with delegation
        document.addEventListener('click', (e) => {
          const target = e.target.closest('[data-command]');
          if (target) {
            e.preventDefault();
            e.stopPropagation();
            const command = target.getAttribute('data-command');
            console.log('Button clicked:', command);
            sendMessage(command);
          }
        });
        
        // Documentation link
        const docsLink = document.getElementById('docsLink');
        if (docsLink) {
          docsLink.addEventListener('click', (e) => {
            e.preventDefault();
            sendMessage('openDocs');
          });
        }
        
        console.log('Button listeners initialized');
      }
      
      // Initialize when DOM is ready
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeButtons);
      } else {
        initializeButtons();
      }
    })();
  </script>
</body>
</html>`;
    }
    getUnauthenticatedContent() {
        return `
      <div class="welcome-section">
        <h2>Welcome to AEP Professional</h2>
        <p>Your AI engineering partner for autonomous development workflows. Sign in to access intelligent code assistance, automated planning, and secure execution capabilities.</p>
        
        <div class="button-group">
          <button class="primary-btn" data-command="signin">
            🔐 Sign in with Auth0
          </button>
          <button class="secondary-btn" data-command="settings">
            ⚙️ Settings
          </button>
        </div>
      </div>
      
      <div class="feature-grid">
        <div class="feature-card">
          <h4>🧠 Intelligent Assistant</h4>
          <p>Context-aware AI that understands your codebase and provides targeted assistance.</p>
        </div>
        <div class="feature-card">
          <h4>🛡️ Safe Execution</h4>
          <p>All changes require approval. Review every step before execution.</p>
        </div>
      </div>`;
    }
    getAuthenticatedContent(profile) {
        const name = profile?.name || 'Developer';
        const email = profile?.email || '';
        const org = profile?.organization || 'Your Organization';
        return `
      <div class="user-info">
        <h3>Welcome back, ${name}! 👋</h3>
        <p>${email} • ${org}</p>
      </div>
      
      <div class="welcome-section">
        <h2>Ready for AI Engineering</h2>
        <p>Your workspace is connected and ready for intelligent assistance. Start a session to begin collaborative development with your AI partner.</p>
        
        <div class="button-group">
          <button class="primary-btn" data-command="startSession">
            🚀 Start Session
          </button>
          <button class="secondary-btn" data-command="settings">
            ⚙️ Settings
          </button>
          <button class="secondary-btn" data-command="signout">
            🚪 Sign Out
          </button>
        </div>
      </div>
      
      <div class="feature-grid">
        <div class="feature-card">
          <h4>📊 Session Analytics</h4>
          <p>Track your AI collaboration metrics and productivity insights.</p>
        </div>
        <div class="feature-card">
          <h4>🔗 Integrations</h4>
          <p>Connected to GitHub, JIRA, and your development workflow.</p>
        </div>
      </div>`;
    }
    html(webview, toolkitUri) {
        const csp = webview.cspSource;
        return /* html */ `
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta http-equiv="Content-Security-Policy"
  content="default-src 'none'; img-src ${csp} https: data:;
           style-src ${csp} 'unsafe-inline';
           script-src ${csp};
           font-src ${csp} https:;">
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>AEP Agent</title>
<script type="module" src="${toolkitUri}"></script>
<style>
  :root{
    --panel: var(--vscode-editor-background);
    --card: var(--vscode-sideBar-background);
    --border: var(--vscode-panel-border);
    --fg: var(--vscode-foreground);
    --muted: var(--vscode-descriptionForeground);
    --primary: var(--vscode-button-background);
    --primary-fg: var(--vscode-button-foreground);
    --link: var(--vscode-textLink-foreground);
  }
  body{margin:0;background:var(--panel);color:var(--fg);font-family: var(--vscode-font-family);}
  .wrap{padding:16px 16px 12px}
  .hero{
    display:flex;flex-direction:column;gap:14px;
    background:var(--card);border:1px solid var(--border);padding:16px;border-radius:10px;
    box-shadow: 0 0 0 1px rgba(0,0,0,.03) inset;
  }
  .headerRow{display:flex;align-items:center;gap:12px}
  .title{font-size:16px;font-weight:600}
  .spacer{flex:1}
  .chips{display:flex;gap:8px}
  .chip{padding:2px 8px;border:1px solid var(--border);border-radius:999px;color:var(--muted);font-size:11px}
  .desc{color:var(--muted);font-size:12.5px;margin-top:-2px}
  .ctaRow{display:flex;gap:10px;flex-wrap:wrap}
  .grid{margin-top:12px;display:grid;grid-template-columns:1fr 1fr;gap:12px}
  .card{
    background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:12px;
  }
  .card h4{margin:0 0 6px;font-size:13px}
  .card p{margin:0;color:var(--muted);font-size:12px;line-height:1.45}
  .foot{margin-top:12px;color:var(--muted);font-size:11.5px}
  .mono{font-family: var(--vscode-editor-font-family, monospace)}
  @media (max-width: 880px){ .grid{grid-template-columns:1fr}}
</style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="headerRow">
        <vscode-badge appearance="secondary">AEP Agent</vscode-badge>
        <div class="chips">
          <span class="chip">Agent online</span>
          <span class="chip mono">org: <span id="org">Not connected</span></span>
        </div>
        <div class="spacer"></div>
        <vscode-button id="settingsBtn" appearance="secondary">Settings</vscode-button>
        <vscode-button id="signInBtn">Sign in</vscode-button>
      </div>

      <div class="title">Welcome to your AI Engineering Partner</div>
      <div class="desc">
        Connect your org to unlock context packs, plans, and step-safe live coding help.
        The agent never applies changes without your approval.
      </div>

      <div class="ctaRow">
        <vscode-button id="authBtn">🔐 Sign in with Auth0</vscode-button>
        <vscode-button id="learnBtn" appearance="secondary">Learn more / Settings</vscode-button>
        <vscode-button id="startBtn" appearance="secondary">Start Session</vscode-button>
      </div>

      <div class="grid">
        <div class="card">
          <h4>JIRA & GitHub context</h4>
          <p>Issues, commits, and PRs are inlined where you work. The agent prepares links and snippets automatically.</p>
        </div>
        <div class="card">
          <h4>Plan → Act</h4>
          <p>Approve each step. The agent proposes diffs and runs tools only after explicit permission.</p>
        </div>
      </div>

      <div class="foot">
        Questions? <a style="color:var(--link)" href="#" id="docsLink">Docs</a> •
        <span class="mono">auth: auth.navralabs.com</span>
      </div>
    </section>
  </div>

<script>
  const vscode = acquireVsCodeApi();
  const on = (id, t) => document.getElementById(id)?.addEventListener('click', t);

  on('settingsBtn', () => vscode.postMessage({type:'settings'}));
  on('signInBtn',   () => vscode.postMessage({type:'signin'}));
  on('authBtn',     () => vscode.postMessage({type:'signin'}));
  on('learnBtn',    () => vscode.postMessage({type:'learn'}));
  on('startBtn',    () => vscode.postMessage({type:'startSession'}));
  on('docsLink',    (e) => { e.preventDefault(); vscode.postMessage({type:'learn'}) });

  // Example: you can later post org info back via webview.postMessage from extension side.
</script>
</body>
</html>`;
    }
}
exports.AgentHomeViewProvider = AgentHomeViewProvider;
AgentHomeViewProvider.viewId = 'aep.home';
//# sourceMappingURL=AgentHomeViewProvider-broken.js.map