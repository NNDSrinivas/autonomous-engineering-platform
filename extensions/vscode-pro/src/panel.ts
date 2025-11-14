import * as vscode from 'vscode';
import { signIn, getAccessToken } from './auth';
import { JiraClient, GithubClient, JiraIssue, GhPr } from './services';
import { HistoryStore, AepSession } from './history';

export class AepPanel {
    public static current: AepPanel | undefined;
    private panel: vscode.WebviewPanel;
    private ctx: vscode.ExtensionContext;
    private jiraClient: JiraClient;
    private githubClient: GithubClient;
    private history: HistoryStore;

    static show(ctx: vscode.ExtensionContext) {
        if (AepPanel.current) {
            AepPanel.current.panel.reveal();
            return;
        }
        AepPanel.current = new AepPanel(ctx);
    }

    private constructor(ctx: vscode.ExtensionContext) {
        this.ctx = ctx;
        this.jiraClient = new JiraClient(ctx);
        this.githubClient = new GithubClient();
        this.history = new HistoryStore(ctx);

        this.panel = vscode.window.createWebviewPanel(
            'aepPro',
            'AEP Professional',
            vscode.ViewColumn.One,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [vscode.Uri.joinPath(ctx.extensionUri, 'media')]
            }
        );

        this.render();
        this.panel.onDidDispose(() => AepPanel.current = undefined);

        this.panel.webview.onDidReceiveMessage(async (msg) => {
            try {
                switch (msg.type) {
                    case 'signin':
                        await signIn(this.ctx);
                        this.render(); // Refresh view after sign in
                        break;
                    case 'selectModel':
                        await this.ctx.globalState.update('aep.model', msg.value);
                        this.post({ type: 'modelChanged', value: msg.value });
                        vscode.window.showInformationMessage(`Model changed to: ${msg.value}`);
                        break;
                    case 'addMcp':
                        await this.addMcp(msg.value);
                        break;
                    case 'action':
                        await vscode.commands.executeCommand(msg.command);
                        break;
                    case 'ready':
                        // Send initial state when webview is ready
                        await this.sendInitialState();
                        break;
                    case 'connectJira':
                        await vscode.commands.executeCommand('aep.connectJira');
                        break;
                    case 'connectGithub':
                        await vscode.commands.executeCommand('aep.connectGithub');
                        break;
                    case 'openSession':
                        await this.openSession(msg.id);
                        break;
                    case 'historyAdd':
                        this.history.upsertMessage(msg.sessionId, msg.message, msg.title);
                        this.post({ type: 'historyData', value: this.history.list().slice(0, 8) });
                        break;
                }
            } catch (error) {
                vscode.window.showErrorMessage(`Action failed: ${error}`);
            }
        });
    }

    private post(payload: any) {
        this.panel.webview.postMessage(payload);
    }

    private async addMcp(name: string) {
        const mcps = this.ctx.globalState.get<string[]>('aep.mcp', []);
        if (name && !mcps.includes(name)) {
            mcps.push(name);
            await this.ctx.globalState.update('aep.mcp', mcps);
            this.post({ type: 'mcpList', value: mcps });
            vscode.window.showInformationMessage(`MCP server added: ${name}`);
        }
    }

    private async openSession(sessionId: string) {
        const session = this.history.getSession(sessionId);
        if (session) {
            vscode.window.showInformationMessage(`Opening session: ${session.title}`);
            // Here you could open a new chat panel or restore the conversation
        }
    }

    private async sendInitialState() {
        const model = this.ctx.globalState.get('aep.model', 'gpt-4o');
        const mcp = this.ctx.globalState.get<string[]>('aep.mcp', []);
        const sessions = this.history.list().slice(0, 8);

        this.post({
            type: 'init',
            model,
            mcp,
            sessions
        });
    }

    private async render() {
        const webview = this.panel.webview;
        const model = this.ctx.globalState.get('aep.model', 'gpt-4o');
        const mcp = this.ctx.globalState.get<string[]>('aep.mcp', []);
        const isSignedIn = await getAccessToken(this.ctx) !== undefined;

        // Get connection states
        const jiraConnected = await this.jiraClient.connected();
        const githubConnected = await this.githubClient.connected();

        // Get feed data
        const issues = await this.jiraClient.myAssigned(5);
        const prs = await this.githubClient.myOpenPRs(5);
        const sessions = this.history.list().slice(0, 8);

        webview.html = this.getHtml(model, mcp, isSignedIn, jiraConnected, githubConnected, issues, prs, sessions);
    }

    private getHtml(
        model: string,
        mcp: string[],
        isSignedIn: boolean,
        jiraConnected: boolean,
        githubConnected: boolean,
        issues: JiraIssue[],
        prs: GhPr[],
        sessions: AepSession[]
    ) {
        const mcpItems = mcp.length > 0
            ? mcp.map(n => `<li class="mcp-item">${this.escapeHtml(n)}</li>`).join('')
            : `<li class="muted">No MCP servers configured</li>`;

        const signInButton = isSignedIn
            ? `<div class="chip success">✓ Signed In</div>`
            : `<button id="signin">Sign in</button>`;

        const issueList = issues.length > 0
            ? issues.map(i => `<li><a href="${i.url}" target="_blank">${this.escapeHtml(i.key)}</a> — ${this.escapeHtml(i.summary)} <span class="muted">(${this.escapeHtml(i.status || 'Open')})</span></li>`).join('')
            : '<li class="muted">No assigned issues</li>';

        const prList = prs.length > 0
            ? prs.map(p => `<li><a href="${p.url}" target="_blank">${this.escapeHtml(p.title)}</a> <span class="muted">(${this.escapeHtml(p.repo)})</span></li>`).join('')
            : '<li class="muted">No open PRs</li>';

        const sessionList = sessions.length > 0
            ? sessions.map(s => `<li data-id="${s.id}" class="hist"><span>${this.escapeHtml(s.title)}</span><span class="muted">${this.timeAgo(s.updatedAt)}</span></li>`).join('')
            : '<li class="muted">No history yet</li>';

        return /*html*/`
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8" />
      <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src https: data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
      <style>
        :root { 
          --bg: var(--vscode-editor-background, #0f1116); 
          --panel: var(--vscode-panel-background, #11131a); 
          --border: var(--vscode-panel-border, #1b1f2a); 
          --text: var(--vscode-editor-foreground, #e5e7eb); 
          --sub: var(--vscode-descriptionForeground, #9aa3b2); 
          --btn: var(--vscode-button-background, #2563eb); 
          --btnHover: var(--vscode-button-hoverBackground, #1d4ed8); 
          --muted: var(--vscode-disabledForeground, #6b7280);
          --success: var(--vscode-testing-iconPassed, #22c55e);
          --warning: var(--vscode-editorWarning-foreground, #f59e0b);
        }
        body { 
          background: var(--bg); 
          color: var(--text); 
          font: 13px/1.6 var(--vscode-font-family, system-ui, -apple-system, Segoe UI, Roboto, sans-serif); 
          margin: 0; 
          padding: 0;
        }
        .wrap { padding: 16px 20px; }
        .row { 
          display: flex; 
          align-items: center; 
          gap: 8px; 
          margin-bottom: 12px;
          flex-wrap: wrap;
        }
        .chip { 
          background: var(--panel); 
          border: 1px solid var(--border); 
          padding: 6px 10px; 
          border-radius: 8px;
          font-weight: 500;
          font-size: 12px;
        }
        .chip.success {
          background: var(--success);
          color: white;
          border-color: var(--success);
        }
        .pill {
          padding: 2px 6px;
          border-radius: 4px;
          font-size: 11px;
          font-weight: 600;
        }
        .pill.ok { color: var(--success); }
        .pill.off { color: var(--warning); }
        select, input { 
          background: var(--panel); 
          color: var(--text); 
          border: 1px solid var(--border); 
          border-radius: 6px; 
          padding: 6px 8px;
          min-width: 120px;
        }
        button { 
          background: var(--btn); 
          color: white; 
          border: 0; 
          border-radius: 8px; 
          padding: 6px 12px; 
          cursor: pointer;
          font-size: 12px;
          transition: background-color 0.2s;
        }
        button:hover { 
          background: var(--btnHover); 
        }
        button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        button.small {
          padding: 4px 8px;
          font-size: 11px;
        }
        .grid { 
          display: grid; 
          grid-template-columns: 2fr 1fr; 
          gap: 12px; 
          margin-top: 16px; 
        }
        @media (max-width: 600px) {
          .grid {
            grid-template-columns: 1fr;
          }
        }
        .card { 
          background: var(--panel); 
          border: 1px solid var(--border); 
          border-radius: 12px; 
          padding: 16px; 
        }
        .title { 
          font-weight: 600; 
          font-size: 14px; 
          margin-bottom: 12px;
          color: var(--text);
        }
        .muted { 
          color: var(--muted); 
          font-size: 12px;
          font-style: italic;
        }
        details { 
          background: transparent; 
          border: 1px solid var(--border); 
          border-radius: 8px; 
          padding: 8px 12px;
          margin-bottom: 8px;
        }
        details[open] { 
          padding-bottom: 12px; 
        }
        summary { 
          cursor: pointer; 
          font-weight: 600;
          font-size: 13px;
          padding: 4px 0;
        }
        summary:hover {
          color: var(--btn);
        }
        ul { 
          margin: 8px 0 0; 
          padding: 0 0 0 16px; 
          list-style-type: disc;
        }
        .mcp-item, .feed-item, .hist {
          margin: 4px 0;
          font-size: 13px;
        }
        .hist {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          cursor: pointer;
          padding: 4px 8px;
          border-radius: 4px;
        }
        .hist:hover {
          background: var(--border);
        }
        .actions {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .actions button { 
          width: 100%;
          text-align: left;
          justify-content: flex-start;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .input-group {
          display: flex;
          gap: 8px;
          margin-top: 8px;
        }
        .input-group input {
          flex: 1;
        }
        .feed {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
        }
        a {
          color: var(--vscode-textLink-foreground, #60a5fa);
          text-decoration: none;
        }
        a:hover {
          text-decoration: underline;
        }
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="row">
          <span class="chip">Model</span>
          <select id="model">
            ${['gpt-4o', 'gpt-4o-mini', 'claude-3-5-sonnet', 'gemini-1.5-pro'].map(m =>
            `<option value="${m}" ${m === model ? 'selected' : ''}>${m}</option>`
        ).join('')}
          </select>
          ${signInButton}
          <span class="chip">JIRA: <span class="${jiraConnected ? 'pill ok' : 'pill off'}">${jiraConnected ? 'Connected' : 'Connect'}</span></span>
          <button id="cfgJira" class="small">${jiraConnected ? 'Refresh' : 'Connect'}</button>
          <span class="chip">GitHub: <span class="${githubConnected ? 'pill ok' : 'pill off'}">${githubConnected ? 'Connected' : 'Connect'}</span></span>
          <button id="cfgGh" class="small">${githubConnected ? 'Refresh' : 'Connect'}</button>
        </div>

        <div class="grid">
          <div class="card">
            <div class="title">📋 Today for you</div>
            <div class="feed">
              <div>
                <div class="title muted" style="margin-top:6px; margin-bottom: 8px;">JIRA — Assigned</div>
                <ul>${issueList}</ul>
              </div>
              <div>
                <div class="title muted" style="margin-top:6px; margin-bottom: 8px;">GitHub — Open PRs</div>
                <ul>${prList}</ul>
              </div>
            </div>

            <div class="title" style="margin-top:16px;">🔌 MCP Servers</div>
            <details open>
              <summary>Configured Servers</summary>
              <ul id="mcpList">${mcpItems}</ul>
            </details>
            <div class="input-group">
              <input id="mcpName" placeholder="e.g. Local MCP Server" />
              <button id="addMcp">Add</button>
            </div>
            <div class="muted" style="margin-top: 8px;">
              MCP servers run locally or remote. AEP will auto-discover available tools and schemas.
            </div>
          </div>
          
          <div class="card">
            <div class="title">🚀 Quick Actions</div>
            <div class="actions">
              <button data-cmd="aep.reviewFile">
                <span>🔍</span>
                <span>Review File</span>
              </button>
              <button data-cmd="aep.debugIssue">
                <span>🪲</span>
                <span>Debug Issue</span>
              </button>
              <button data-cmd="aep.explainCode">
                <span>💡</span>
                <span>Explain Code</span>
              </button>
              <button data-cmd="aep.generateTests">
                <span>🧪</span>
                <span>Generate Tests</span>
              </button>
            </div>

            <div class="title" style="margin-top:16px;">💬 Recent Sessions</div>
            <ul id="histList">${sessionList}</ul>
          </div>
        </div>
      </div>

      <script>
        const vscode = acquireVsCodeApi();
        
        // Notify extension that webview is ready
        vscode.postMessage({ type: 'ready' });

        // Sign in handler
        const signinBtn = document.getElementById('signin');
        if (signinBtn) {
          signinBtn.onclick = () => vscode.postMessage({ type:'signin' });
        }
        
        // Model selection handler
        document.getElementById('model').onchange = (e) => {
          vscode.postMessage({ type:'selectModel', value: e.target.value });
        };
        
        // Action button handlers
        document.querySelectorAll('button[data-cmd]').forEach(button => {
          button.onclick = () => {
            const command = button.dataset.cmd;
            vscode.postMessage({ type:'action', command: command });
          };
        });
        
        // MCP add handler
        document.getElementById('addMcp').onclick = () => {
          const input = document.getElementById('mcpName');
          const value = input.value.trim();
          if (value) {
            vscode.postMessage({ type:'addMcp', value: value });
            input.value = '';
          }
        };

        // Handle Enter key in MCP input
        document.getElementById('mcpName').onkeypress = (e) => {
          if (e.key === 'Enter') {
            document.getElementById('addMcp').click();
          }
        };

        // Connection handlers
        document.getElementById('cfgJira').onclick = () => {
          vscode.postMessage({ type: 'connectJira' });
        };
        document.getElementById('cfgGh').onclick = () => {
          vscode.postMessage({ type: 'connectGithub' });
        };

        // History handlers
        document.querySelectorAll('.hist').forEach(el => {
          el.onclick = () => {
            const id = el.getAttribute('data-id');
            if (id) {
              vscode.postMessage({ type: 'openSession', id: id });
            }
          };
        });
        
        // Listen for messages from extension
        window.addEventListener('message', event => {
          const { type, value, model, mcp, sessions } = event.data || {};
          
          if (type === 'mcpList') {
            const list = document.getElementById('mcpList');
            if (value && value.length > 0) {
              list.innerHTML = value.map(name => 
                '<li class="mcp-item">' + escapeHtml(name) + '</li>'
              ).join('');
            } else {
              list.innerHTML = '<li class="muted">No MCP servers configured</li>';
            }
          }
          
          if (type === 'init') {
            // Update UI with initial state
            if (model) {
              document.getElementById('model').value = model;
            }
            if (mcp) {
              const list = document.getElementById('mcpList');
              if (mcp.length > 0) {
                list.innerHTML = mcp.map(name => 
                  '<li class="mcp-item">' + escapeHtml(name) + '</li>'
                ).join('');
              }
            }
            if (sessions) {
              updateHistoryList(sessions);
            }
          }

          if (type === 'historyData') {
            updateHistoryList(value);
          }
        });

        function updateHistoryList(sessions) {
          const list = document.getElementById('histList');
          if (sessions && sessions.length > 0) {
            list.innerHTML = sessions.map(s => 
              '<li class="hist" data-id="' + s.id + '"><span>' + escapeHtml(s.title) + '</span><span class="muted">' + timeAgo(s.updatedAt) + '</span></li>'
            ).join('');
            // Re-attach click handlers
            list.querySelectorAll('.hist').forEach(el => {
              el.onclick = () => {
                const id = el.getAttribute('data-id');
                if (id) {
                  vscode.postMessage({ type: 'openSession', id: id });
                }
              };
            });
          } else {
            list.innerHTML = '<li class="muted">No history yet</li>';
          }
        }

        function escapeHtml(str) {
          const div = document.createElement('div');
          div.textContent = str;
          return div.innerHTML;
        }

        function timeAgo(ts) {
          const d = Date.now() - ts;
          const m = Math.round(d / 60000);
          if (m < 60) return m + 'm';
          const h = Math.round(m / 60);
          if (h < 24) return h + 'h';
          return Math.round(h / 24) + 'd';
        }
      </script>
    </body>
    </html>`;
    }

    private escapeHtml(str: string): string {
        return (str || '').replace(/[&<>"']/g, (m) => {
            const map: Record<string, string> = {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;'
            };
            return map[m] || m;
        });
    }

    private timeAgo(ts: number): string {
        const d = Date.now() - ts;
        const m = Math.round(d / 60000);
        if (m < 60) return m + 'm';
        const h = Math.round(m / 60);
        if (h < 24) return h + 'h';
        return Math.round(h / 24) + 'd';
    }
}