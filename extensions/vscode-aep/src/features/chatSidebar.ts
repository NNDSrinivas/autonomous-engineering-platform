import * as vscode from 'vscode';
import { AEPClient } from '../api/client';
import { boilerplate } from '../webview/view';
import type { JiraIssue } from '../api/types';

export class ChatSidebarProvider implements vscode.WebviewViewProvider {
  private view: vscode.WebviewView | undefined;

  constructor(
    private readonly ctx: vscode.ExtensionContext,
    private readonly client: AEPClient,
    private readonly output: vscode.OutputChannel
  ) {}

  resolveWebviewView(view: vscode.WebviewView) {
    this.view = view;
    view.webview.options = { enableScripts: true };
    this.render();

    view.webview.onDidReceiveMessage(async message => {
      try {
        switch (message.type) {
          case 'openExternal':
            if (message.url) {
              vscode.env.openExternal(vscode.Uri.parse(message.url));
            }
            break;
          case 'openPortal':
            await vscode.commands.executeCommand('aep.openPortal');
            break;
          case 'pickIssue':
          case 'startSession':
            await vscode.commands.executeCommand('aep.startSession');
            break;
          case 'signIn':
            await vscode.commands.executeCommand('aep.signIn');
            setTimeout(() => this.render(), 2000);
            break;
          case 'refresh':
            await this.render();
            break;
          case 'chat':
            if (message.message) {
              await this.handleChatMessage(message.message);
            }
            break;
          default:
            this.output.appendLine(`Unknown chat message type: ${message.type}`);
        }
      } catch (error) {
        const text = error instanceof Error ? error.message : String(error);
        this.output.appendLine(`ChatSidebar message handling failed: ${text}`);
        vscode.window.showErrorMessage(`AEP Agent chat error: ${text}`);
      }
    });
  }

  refresh() {
    if (this.view) {
      this.render();
    }
  }

  async render() {
    if (!this.view) {
      return;
    }

    try {
      const [me, issues] = await Promise.all([
        this.client.me().catch(() => ({} as any)),
        this.client.listMyJiraIssues().catch(() => [])
      ]);

      const greeting = this.resolveGreeting();
      const body = me?.email ? this.signedInView(greeting, me.email, issues) : this.signedOutView();
      this.view.webview.html = boilerplate(
        this.view.webview,
        this.ctx,
        body,
        ['base.css', 'aurora.css', 'landing.css'],
        ['chat.js']
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.output.appendLine(`ChatSidebar render failed: ${message}`);
      const fallback = `
        <div class="aep-shell">
          <section class="panel aurora error">
            <div class="panel-header">
              <span class="badge badge-alert">Connectivity issue</span>
              <h1>We couldn't reach your workspace</h1>
              <p class="lead">${this.escape(message)}</p>
            </div>
            <div class="panel-actions">
              <vscode-button appearance="primary" id="retry" data-command="refresh">Try again</vscode-button>
              <vscode-button appearance="secondary" id="openPortal" data-command="openPortal">Open status dashboard</vscode-button>
            </div>
          </section>
        </div>`;
      this.view.webview.html = boilerplate(
        this.view.webview,
        this.ctx,
        fallback,
        ['base.css', 'aurora.css', 'landing.css'],
        ['chat.js']
      );
    }
  }

  private resolveGreeting(): string {
    const hour = new Date().getHours();
    if (hour < 12) {
      return 'Good morning';
    }
    if (hour < 18) {
      return 'Good afternoon';
    }
    return 'Good evening';
  }

  private signedInView(greeting: string, email: string, issues: JiraIssue[]): string {
    const displayName = this.formatName(email);
    const issueCards = issues.length
      ? issues.map(issue => this.renderIssue(issue)).join('')
      : `<div class="empty-state">
          <h3>No Jira issues detected</h3>
          <p>Connect a project in the Agent tab or load a demo to explore AEP workflows.</p>
          <div class="empty-actions">
          <vscode-button appearance="secondary" id="action-refresh" data-command="refresh">Refresh data</vscode-button>
          <vscode-button appearance="secondary" id="action-start" data-command="startSession">Open command session</vscode-button>
          </div>
        </div>`;

    return `
      <div class="aep-shell">
        <section class="panel aurora hero">
          <div class="panel-header">
            <span class="badge badge-success">Workspace connected</span>
            <h1>${this.escape(greeting)}, ${this.escape(displayName)}.</h1>
            <p class="lead">You're authenticated as ${this.escape(email)}. Launch a session or pick a Jira issue to begin shipping.</p>
          </div>
          <div class="panel-actions">
            <vscode-button id="action-start" data-command="startSession" appearance="primary">Launch agent session</vscode-button>
            <vscode-button id="action-refresh" data-command="refresh" appearance="secondary">Refresh workspace</vscode-button>
            <vscode-button id="action-portal" data-command="openPortal" appearance="secondary">Open Portal</vscode-button>
          </div>
          <div class="panel-metrics">
            <div class="metric">
              <span class="metric-value">${issues.length}</span>
              <span class="metric-label">Active Jira issues</span>
            </div>
            <div class="metric">
              <span class="metric-value">Realtime</span>
              <span class="metric-label">AEP sync</span>
            </div>
            <div class="metric">
              <span class="metric-value">Secured</span>
              <span class="metric-label">Auth0 login</span>
            </div>
          </div>
        </section>

        <section class="grid">
          <article class="module issues">
            <header>
              <div>
                <h2>Priority work</h2>
                <p>Assign AEP to break down tasks, draft plans, and prepare patches.</p>
              </div>
              <vscode-button appearance="secondary" id="action-refresh-secondary" data-command="refresh">Sync now</vscode-button>
            </header>
            <div class="issue-grid">${issueCards}</div>
          </article>

          <article class="module conversation">
            <header>
              <div>
                <h2>Chat with AEP</h2>
                <p>Ask for refactors, tests, deployment steps, or architecture reviews.</p>
              </div>
            </header>
            <div class="chat-log" id="chatMessages">
              <div class="chat-placeholder">
                <span>💬</span>
                <div>
                  <strong>Ready for your next request</strong>
                  <p>Summarize a pull request, draft a remediation plan, or generate a hotfix.</p>
                </div>
              </div>
            </div>
            <div class="chat-compose">
              <textarea id="chatInput" placeholder="Ask AEP to analyze a file, reason about tests, or prepare a plan..."></textarea>
              <vscode-button id="chatSend" appearance="primary">Send</vscode-button>
            </div>
          </article>
        </section>

        <section class="grid tertiary">
          <article class="module quick-actions">
            <header>
              <div>
                <h2>Quick actions</h2>
                <p>Drive the workflow without leaving VS Code.</p>
              </div>
            </header>
            <div class="quick-actions-grid">
              <button class="quick-action" data-command="startSession">
                <span class="icon">⚡</span>
                <div>
                  <strong>Start an execution session</strong>
                  <p>Open the Agent palette to create or resume tasks.</p>
                </div>
              </button>
              <button class="quick-action" data-command="refresh">
                <span class="icon">🔄</span>
                <div>
                  <strong>Resync integrations</strong>
                  <p>Force refresh Jira issues and workspace metadata.</p>
                </div>
              </button>
              <button class="quick-action" data-command="openPortal">
                <span class="icon">🌐</span>
                <div>
                  <strong>Review insights in Portal</strong>
                  <p>Jump to the AEP Portal for analytics and approvals.</p>
                </div>
              </button>
            </div>
          </article>
        </section>
      </div>`;
  }

  private signedOutView(): string {
    return `
      <div class="aep-shell">
        <section class="panel aurora hero">
          <div class="panel-header">
            <span class="badge badge-offline">Authentication required</span>
            <h1>Build with AEP Agent for engineering teams</h1>
            <p class="lead">Securely connect your workspace, orchestrate AI-assisted plans, and apply production-ready patches without leaving VS Code.</p>
          </div>
          <div class="panel-actions">
            <vscode-button id="cta-signin" data-command="signIn" appearance="primary">Sign in to AEP</vscode-button>
            <vscode-button id="cta-demo" appearance="secondary">Explore the interactive demo</vscode-button>
            <vscode-button id="cta-portal" data-command="openPortal" appearance="secondary">Visit Portal</vscode-button>
          </div>
          <div class="panel-metrics">
            <div class="metric">
              <span class="metric-value">Planning</span>
              <span class="metric-label">Generate AI-driven execution plans</span>
            </div>
            <div class="metric">
              <span class="metric-value">Shipping</span>
              <span class="metric-label">Apply validated patches in seconds</span>
            </div>
            <div class="metric">
              <span class="metric-value">Security</span>
              <span class="metric-label">Device-code login backed by Auth0</span>
            </div>
          </div>
        </section>

        <section class="grid">
          <article class="module">
            <header>
              <div>
                <h2>What you get with AEP</h2>
                <p>Purpose-built workflows that keep engineers in flow.</p>
              </div>
            </header>
            <div class="feature-grid">
              <div class="feature-card">
                <span class="icon">🧠</span>
                <h3>Full-context planning</h3>
                <p>Draft executable plans from Jira issues with approvals woven in.</p>
              </div>
              <div class="feature-card">
                <span class="icon">🛠️</span>
                <h3>Code change automation</h3>
                <p>Generate, review, and apply patches with guardrails and diff previews.</p>
              </div>
              <div class="feature-card">
                <span class="icon">📊</span>
                <h3>Operations visibility</h3>
                <p>Track session health, rollout risk, and completions from the Portal.</p>
              </div>
            </div>
          </article>

          <article class="module demo" data-visible="false" aria-hidden="true">
            <header>
              <div>
                <h2>Interactive showcase</h2>
                <p>Try a simulated conversation before authenticating.</p>
              </div>
              <button id="demo-close" class="ghost" aria-label="Close demo">×</button>
            </header>
            <div class="demo-log" id="demoLog">
              <div class="demo-message assistant">
                <strong>AEP Agent</strong>
                <p>Hi! I can help plan your sprint, triage bugs, and prep code changes. Ask me about your project.</p>
              </div>
            </div>
            <div class="demo-compose">
              <textarea id="demoInput" placeholder="Try: Generate a rollout plan for the onboarding flow"></textarea>
              <vscode-button id="demoSend" appearance="primary">Send</vscode-button>
            </div>
          </article>
        </section>

        <section class="grid tertiary">
          <article class="module timeline">
            <header>
              <div>
                <h2>How teams ship with AEP</h2>
              </div>
            </header>
            <ol class="timeline-steps">
              <li>
                <span class="step">01</span>
                <div>
                  <strong>Connect your workspace</strong>
                  <p>Authenticate with your organization and link Jira or GitHub projects.</p>
                </div>
              </li>
              <li>
                <span class="step">02</span>
                <div>
                  <strong>Generate plans</strong>
                  <p>Send an issue to the Agent panel to receive a review-ready execution plan.</p>
                </div>
              </li>
              <li>
                <span class="step">03</span>
                <div>
                  <strong>Approve and apply</strong>
                  <p>Review AI-suggested patches, approve changes, and merge with confidence.</p>
                </div>
              </li>
            </ol>
          </article>
        </section>
      </div>`;
  }

  private renderIssue(issue: JiraIssue): string {
    const status = issue.status ?? 'Pending';
    return `
      <div class="issue-card">
        <header>
          <span class="issue-key">${this.escape(issue.key)}</span>
          <span class="status-pill">${this.escape(status)}</span>
        </header>
        <p>${this.escape(issue.summary)}</p>
        <footer>
          <vscode-button appearance="primary" data-command="pickIssue" data-key="${this.escape(issue.key)}">Plan in Agent</vscode-button>
          <vscode-button appearance="secondary" data-url="${issue.url ?? ''}">Open in Jira</vscode-button>
        </footer>
      </div>`;
  }

  private escape(text: string | null | undefined): string {
    return String(text ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  private formatName(email: string): string {
    const name = email.split('@')[0] ?? email;
    return name
      .split(/[._-]+/)
      .filter(Boolean)
      .map(part => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ');
  }

  private async handleChatMessage(message: string) {
    if (!this.view) {
      return;
    }

    try {
      this.showChatMessage('user', message);
      this.showChatMessage('system', '🤔 Thinking...');

      const response = await this.client.chat(message);
      const answer = response.response || response.message || 'I received your message but had trouble generating a response.';
      this.showChatMessage('assistant', answer);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      this.output.appendLine(`Chat error: ${text}`);
      this.showChatMessage(
        'assistant',
        'I encountered an error processing your message. Please check your connection and try again.'
      );
    }
  }

  private showChatMessage(role: 'user' | 'assistant' | 'system', content: string) {
    if (this.view) {
      this.view.webview.postMessage({
        type: 'chatMessage',
        role,
        content,
        timestamp: new Date().toLocaleTimeString()
      });
    }
  }
}
