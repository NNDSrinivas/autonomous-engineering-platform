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
exports.HomePanel = void 0;
const vscode = __importStar(require("vscode"));
class HomePanel {
    constructor(ctx) {
        this.ctx = ctx;
    }
    resolveWebviewView(view) {
        this.view = view;
        view.webview.options = {
            enableScripts: true,
            localResourceRoots: [this.ctx.extensionUri]
        };
        view.webview.html = this.html(this.state());
        // messages from webview -> extension
        view.webview.onDidReceiveMessage(async (msg) => {
            switch (msg.type) {
                case 'cmd:newPlan':
                    vscode.commands.executeCommand('aep.newTask');
                    break;
                case 'cmd:history':
                    vscode.commands.executeCommand('aep.openHistory');
                    break;
                case 'cmd:settings':
                    vscode.commands.executeCommand('aep.openSettings');
                    break;
                case 'cmd:account':
                    vscode.commands.executeCommand('aep.openAccount');
                    break;
                case 'cmd:workspace':
                    vscode.commands.executeCommand('aep.openWorkspace');
                    break;
                case 'cmd:contexts':
                    vscode.commands.executeCommand('aep.openContexts');
                    break;
                case 'auth:signin':
                    await vscode.commands.executeCommand('aep.signIn');
                    this.refresh();
                    break;
                case 'auth:setApiKey':
                    await vscode.commands.executeCommand('aep.setApiKey');
                    this.refresh();
                    break;
                case 'model:set':
                    await this.save({ model: msg.value });
                    this.post({ type: 'state:update', state: this.state() });
                    break;
                case 'mcp:add':
                    if (msg.value?.trim()) {
                        const s = this.state();
                        s.mcpServers.push(msg.value.trim());
                        await this.save({ mcpServers: s.mcpServers });
                        this.post({ type: 'state:update', state: this.state() });
                    }
                    break;
                case 'mcp:remove':
                    {
                        const s = this.state();
                        await this.save({ mcpServers: s.mcpServers.filter(x => x !== msg.value) });
                        this.post({ type: 'state:update', state: this.state() });
                    }
                    break;
                case 'quick:review':
                    vscode.commands.executeCommand('aep.reviewFile');
                    break;
                case 'quick:debug':
                    vscode.commands.executeCommand('aep.debugIssue');
                    break;
                case 'quick:explain':
                    vscode.commands.executeCommand('aep.explainCode');
                    break;
                case 'quick:tests':
                    vscode.commands.executeCommand('aep.generateTests');
                    break;
                case 'connect:jira':
                    vscode.commands.executeCommand('aep.connectJira');
                    break;
                case 'connect:github':
                    vscode.commands.executeCommand('aep.connectGithub');
                    break;
                case 'refresh':
                    vscode.commands.executeCommand('aep.refreshFeed');
                    break;
            }
        });
    }
    refresh() {
        if (!this.view)
            return;
        this.view.webview.postMessage({ type: 'state:update', state: this.state() });
    }
    postMessage(message) {
        if (!this.view)
            return;
        this.view.webview.postMessage(message);
    }
    post(payload) {
        this.view?.webview.postMessage(payload);
    }
    state() {
        const s = this.ctx.globalState.get('aep.state');
        return s ?? {
            model: 'gpt-4o',
            apiKeySet: false,
            signedIn: false,
            mcpServers: [],
            jiraConnected: false,
            githubConnected: false
        };
    }
    async save(partial) {
        const next = { ...this.state(), ...partial };
        await this.ctx.globalState.update('aep.state', next);
    }
    html(state) {
        const nonce = String(Date.now());
        const css = this.resourceUri('media/home.css');
        const logo = this.resourceUri('media/aep-mark.svg');
        return /* html */ `
      <!doctype html>
      <html>
      <head>
        <meta charset="utf-8"/>
        <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${this.view?.webview.cspSource} https:; style-src ${this.view?.webview.cspSource}; script-src 'nonce-${nonce}';">
        <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
        <link rel="stylesheet" href="${css}">
        <title>AEP Professional</title>
      </head>
      <body class="aep">
        <!-- Aurora Bar -->
        <header class="aurora">
          <div class="brand">
            <img src="${logo}" alt="" class="mark"/>
            <div class="titles">
              <strong>AEP</strong><span class="sep">•</span><span>Navra Labs</span>
            </div>
          </div>

          <div class="rail">
            <button class="chip ghost" data-cmd="cmd:history" aria-label="Open history">History</button>
            <button class="chip ghost" data-cmd="cmd:workspace" aria-label="Workspace">Workspace</button>
            <button class="chip ghost" data-cmd="cmd:contexts" aria-label="Contexts (MCP)">Contexts</button>
            <button class="primary xl" data-cmd="cmd:newPlan" aria-label="Create new plan">New Plan</button>

            <!-- Account button + popover -->
            <div class="account">
              <button class="avatar" data-js="account-toggle" aria-haspopup="menu" aria-expanded="false" aria-label="Account">NL</button>
              <div class="account-menu" role="menu" aria-hidden="true">
                <div class="account-head">
                  <div class="initial">NL</div>
                  <div class="who">
                    <strong id="acctName">Navra Labs</strong>
                    <span id="acctMail">user@navralabs.com</span>
                  </div>
                </div>
                <button role="menuitem" class="menu-item" data-cmd="cmd:account.profile">Profile</button>
                <button role="menuitem" class="menu-item" data-cmd="cmd:account.billing">Billing</button>
                <hr/>
                <button role="menuitem" class="menu-item danger" data-cmd="cmd:account.signout">Sign out</button>
              </div>
            </div>

            <button class="icon" data-cmd="cmd:settings" aria-label="Settings">⚙️</button>
          </div>
          <div class="glow"></div>
        </header>

        <!-- Workspace quick-connect rail (unique to AEP) -->
        <section class="workspace-rail" aria-label="Workspace connections">
          <div class="chip-group">
            <span class="label">Workspace</span>
            <button class="chip connect" data-cmd="cmd:connect.jira" aria-pressed="${state.jiraConnected ? 'true' : 'false'}">Jira</button>
            <button class="chip connect" data-cmd="cmd:connect.github" aria-pressed="${state.githubConnected ? 'true' : 'false'}">GitHub</button>
            <button class="chip connect" data-cmd="cmd:connect.confluence" aria-pressed="false">Confluence</button>
          </div>
        </section>

        <!-- Hero -->
        <section class="hero">
          <div class="hero-main">
            <h1>Welcome to your AI engineering partner</h1>
            <p>Code reviews, debugging, architecture help — with your approval at every step.</p>
            <div class="cta">
              <button class="primary" data-cmd="auth:signin">Get started free</button>
              <button class="ghost" data-cmd="auth:setApiKey">Use your own API key</button>
            </div>
            <div class="inline-controls">
              <label>Model
                <select id="model">
                  <option value="gpt-4o">OpenAI GPT-4o</option>
                  <option value="gpt-4o-mini">OpenAI GPT-4o Mini</option>
                  <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
                  <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
                </select>
              </label>
              <span class="status">
                ${state.signedIn ? 'Signed in' : 'Not signed in'} •
                ${state.apiKeySet ? 'API key set' : 'No API key'}
              </span>
            </div>
          </div>
        </section>

        <!-- Connection Status -->
        <section class="connections">
          <div class="conn-item">
            <span class="label">JIRA</span>
            <span class="status ${state.jiraConnected ? 'connected' : 'disconnected'}">
              ${state.jiraConnected ? '✓ Connected' : '○ Disconnected'}
            </span>
            <button class="ghost small" data-cmd="connect:jira">
              ${state.jiraConnected ? 'Manage' : 'Connect'}
            </button>
          </div>
          <div class="conn-item">
            <span class="label">GitHub</span>
            <span class="status ${state.githubConnected ? 'connected' : 'disconnected'}">
              ${state.githubConnected ? '✓ Connected' : '○ Disconnected'}
            </span>
            <button class="ghost small" data-cmd="connect:github">
              ${state.githubConnected ? 'Manage' : 'Connect'}
            </button>
          </div>
          <button class="refresh-btn" data-cmd="refresh">🔄</button>
        </section>

        <!-- Today's Work (Live Feeds) -->
        <section class="panel">
          <details open>
            <summary>📋 Today for You</summary>
            <div class="feed-grid">
              <div class="feed-card">
                <h4>🗂️ My Sprint</h4>
                <ul id="sprint-list" class="feed-items">
                  <li class="empty">Connect JIRA to see your sprint items</li>
                </ul>
              </div>
              <div class="feed-card">
                <h4>🔎 PRs Needing Review</h4>
                <ul id="review-list" class="feed-items">
                  <li class="empty">Connect GitHub to see review requests</li>
                </ul>
              </div>
            </div>
          </details>
        </section>

        <!-- Quick actions -->
        <section class="grid">
          <button class="card" data-cmd="quick:review">🔎 Review code</button>
          <button class="card" data-cmd="quick:debug">🪲 Debug issue</button>
          <button class="card" data-cmd="quick:explain">💡 Explain code</button>
          <button class="card" data-cmd="quick:tests">✍️ Generate tests</button>
        </section>

        <!-- MCP accordion -->
        <section class="panel">
          <details>
            <summary>🧩 MCP Servers</summary>
            <ul id="mcp-list" class="chips"></ul>
            <div class="row">
              <input id="mcp-name" placeholder="e.g. Local MCP Server"/>
              <button id="mcp-add" class="ghost">Add</button>
            </div>
          </details>
        </section>

        <script nonce="${nonce}">
          const vscode = acquireVsCodeApi();

          // hydrate state pushed from extension
          window.addEventListener('message', (e) => {
            if (e.data?.type === 'state:update') render(e.data.state);
            if (e.data?.type === 'feed:update') renderFeeds(e.data);
            if (e.data?.type === 'workspace:state') updateWorkspaceState(e.data);
          });

          // wire all buttons with data-cmd
          document.querySelectorAll('[data-cmd]').forEach(btn=>{
            btn.addEventListener('click', () => {
              vscode.postMessage({ type: btn.getAttribute('data-cmd') });
            });
          });

          // model selector
          const modelEl = document.getElementById('model');
          modelEl.addEventListener('change', () => {
            vscode.postMessage({ type:'model:set', value: modelEl.value });
          });

          // MCP
          const addBtn = document.getElementById('mcp-add');
          const nameInput = document.getElementById('mcp-name');
          addBtn.addEventListener('click', () => {
            const v = nameInput.value.trim();
            if (v) {
              vscode.postMessage({ type:'mcp:add', value: v });
              nameInput.value = '';
            }
          });

          // Enter key for MCP input
          nameInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') addBtn.click();
          });

          // Account menu functionality
          (function accountMenu(){
            const btn = document.querySelector('[data-js="account-toggle"]');
            const menu = document.querySelector('.account-menu');
            if(!btn || !menu) return;

            const open = (yes) => {
              menu.setAttribute('aria-hidden', yes ? 'false' : 'true');
              btn.setAttribute('aria-expanded', yes ? 'true' : 'false');
            };

            btn.addEventListener('click', (e) => {
              e.stopPropagation();
              const isOpen = menu.getAttribute('aria-hidden') === 'false';
              open(!isOpen);
            });

            document.addEventListener('click', (e) => {
              // close if clicking outside
              if(!menu.contains(e.target) && e.target !== btn) open(false);
            });

            // ESC to close
            document.addEventListener('keydown', (e) => {
              if(e.key === 'Escape') open(false);
            });
          })();

          function render(state) {
            modelEl.value = state.model;
            
            // Update connection status
            updateConnectionStatus('jira', state.jiraConnected);
            updateConnectionStatus('github', state.githubConnected);
            
            // Update MCP servers
            const list = document.getElementById('mcp-list');
            list.innerHTML = '';
            (state.mcpServers || []).forEach(s=>{
              const li = document.createElement('li');
              li.className = 'chip';
              li.innerHTML = \`\${s} <button onclick="removeMcp('\${s}')">✕</button>\`;
              list.appendChild(li);
            });
          }

          function updateConnectionStatus(service, connected) {
            const item = document.querySelector(\`.conn-item:has(.label:contains('\${service.toUpperCase()}'))\`);
            if (!item) return;
            
            const status = item.querySelector('.status');
            const button = item.querySelector('button');
            
            status.className = \`status \${connected ? 'connected' : 'disconnected'}\`;
            status.textContent = connected ? '✓ Connected' : '○ Disconnected';
            button.textContent = connected ? 'Manage' : 'Connect';
          }

          function removeMcp(server) {
            vscode.postMessage({ type:'mcp:remove', value: server });
          }

          function renderFeeds(data) {
            // Update sprint items
            const sprintList = document.getElementById('sprint-list');
            sprintList.innerHTML = '';
            if (data.sprint?.length) {
              data.sprint.forEach(item => {
                const li = document.createElement('li');
                li.innerHTML = \`
                  <a href="\${item.url}" onclick="openExternal('\${item.url}')">\${item.key}</a>
                  <span>\${escapeHtml(item.summary || '')}</span>
                  <em>\${item.status || ''}</em>
                \`;
                sprintList.appendChild(li);
              });
            } else {
              sprintList.innerHTML = '<li class="empty">No sprint items found</li>';
            }

            // Update review items
            const reviewList = document.getElementById('review-list');
            reviewList.innerHTML = '';
            if (data.review?.length) {
              data.review.forEach(item => {
                const li = document.createElement('li');
                li.innerHTML = \`
                  <a href="\${item.url}" onclick="openExternal('\${item.url}')">\${escapeHtml(item.repo)}</a>
                  <span>\${escapeHtml(item.title || '')}</span>
                \`;
                reviewList.appendChild(li);
              });
            } else {
              reviewList.innerHTML = '<li class="empty">No reviews waiting</li>';
            }
          }

          function updateWorkspaceState(data) {
            const btn = document.querySelector(\`[data-cmd="cmd:connect.\${data.id}"]\`);
            if(btn) btn.setAttribute('aria-pressed', data.connected ? 'true' : 'false');
          }

          function openExternal(url) {
            vscode.postMessage({ type: 'open:external', url: url });
          }

          function escapeHtml(s) {
            if (!s) return '';
            return s.replace(/[&<>"]/g, c => ({ 
              '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' 
            }[c] || c));
          }

          // initial paint
          render(${JSON.stringify(state)});

          // Request initial feed data
          vscode.postMessage({ type: 'refresh' });
        </script>
      </body>
      </html>`;
    }
    resourceUri(rel) {
        return this.view?.webview.asWebviewUri(vscode.Uri.joinPath(this.ctx.extensionUri, rel));
    }
}
exports.HomePanel = HomePanel;
HomePanel.viewType = 'aep.professional.home';
//# sourceMappingURL=HomePanel.js.map