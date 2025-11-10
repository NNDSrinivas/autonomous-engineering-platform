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
        ['modern.css'],
        ['chat-modern.js']
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.output.appendLine(`ChatSidebar render failed: ${message}`);
      const fallback = `
        <div class="aep-container">
          <div class="aep-card aep-card--elevated">
            <div class="aep-card__header">
              <div>
                <h1 class="aep-card__title">Connection Error</h1>
                <p class="aep-card__subtitle">Unable to reach AEP workspace</p>
              </div>
              <div class="aep-status aep-status--offline">
                <span class="aep-status__dot"></span>
                Offline
              </div>
            </div>
            
            <div class="aep-stack">
              <div class="aep-card">
                <p class="aep-text--sm">${this.escape(message)}</p>
              </div>
              
              <div class="aep-grid">
                <button class="aep-btn aep-btn--primary" data-command="refresh">
                  <span class="codicon codicon-refresh"></span>
                  Try Again
                </button>
                <button class="aep-btn aep-btn--secondary" data-command="openPortal">
                  <span class="codicon codicon-globe"></span>
                  Status Dashboard
                </button>
              </div>
            </div>
          </div>
        </div>`;
      this.view.webview.html = boilerplate(
        this.view.webview,
        this.ctx,
        fallback,
        ['modern.css'],
        ['chat-modern.js']
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
      : `<div class="aep-empty">
          <div class="aep-empty__icon">📋</div>
          <h3 class="aep-empty__title">No active issues</h3>
          <p class="aep-empty__description">Connect your Jira workspace or start a new conversation to begin.</p>
          <div class="aep-stack aep-stack--sm">
            <button class="aep-btn aep-btn--primary" data-command="refresh">
              <span class="codicon codicon-refresh"></span>
              Refresh Issues
            </button>
            <button class="aep-btn aep-btn--secondary" data-command="startSession">
              <span class="codicon codicon-comment-discussion"></span>
              Start New Session
            </button>
          </div>
        </div>`;

    return `
      <div class="aep-container">
        <div class="aep-stack">
          <!-- Header Section -->
          <div class="aep-card aep-card--elevated">
            <div class="aep-card__header">
              <div>
                <h1 class="aep-card__title">${this.escape(greeting)}, ${this.escape(displayName)}</h1>
                <p class="aep-card__subtitle">Connected as ${this.escape(email)}</p>
              </div>
              <div class="aep-status aep-status--online aep-connection-status">
                <span class="aep-status__dot"></span>
                Connected
              </div>
            </div>
            <div class="aep-grid aep-grid--cols-2">
              <button class="aep-btn aep-btn--primary" data-command="startSession">
                <span class="codicon codicon-rocket"></span>
                New Session
              </button>
              <button class="aep-btn aep-btn--secondary" data-command="openPortal">
                <span class="codicon codicon-globe"></span>
                Open Portal
              </button>
            </div>
          </div>

          <!-- Modern Chat Interface -->
          <div class="aep-card">
            <div class="aep-card__header">
              <h2 class="aep-card__title">Chat with AEP Agent</h2>
              <button class="aep-btn aep-btn--ghost aep-btn--sm" data-command="refresh" title="Refresh">
                <span class="codicon codicon-refresh"></span>
              </button>
            </div>
            
            <div class="aep-chat">
              <div class="aep-chat__header">
                <div class="aep-stack aep-stack--sm">
                  <span class="aep-text--bold">AEP Agent</span>
                  <span class="aep-text--sm aep-text--muted">Ready to help with code, planning, and architecture</span>
                </div>
                <div class="aep-status aep-status--online">
                  <span class="aep-status__dot"></span>
                  Online
                </div>
              </div>
              
              <div class="aep-chat__messages" id="chatMessages">
                <div class="aep-chat__message aep-chat__message--assistant">
                  <div class="aep-chat__message-bubble">
                    <p>👋 Hi! I'm your AEP Agent. I can help you:</p>
                    <ul>
                      <li><strong>Plan & execute</strong> development tasks</li>
                      <li><strong>Review & improve</strong> code quality</li>
                      <li><strong>Generate & apply</strong> code changes</li>
                      <li><strong>Analyze & optimize</strong> project architecture</li>
                    </ul>
                    <p>What would you like to work on today?</p>
                  </div>
                  <div class="aep-chat__message-meta">AEP Agent • ${new Date().toLocaleTimeString()}</div>
                </div>
              </div>
              
              <div class="aep-chat__input">
                <textarea 
                  id="chatInput" 
                  class="aep-chat__textarea" 
                  placeholder="Ask me anything about your codebase, request refactoring, or start a new task..."
                  rows="1"
                ></textarea>
                <button id="chatSend" class="aep-btn aep-btn--primary">
                  <span class="codicon codicon-send"></span>
                  Send
                </button>
              </div>
            </div>
          </div>

          <!-- Issues Section -->
          ${issues.length > 0 ? `
          <div class="aep-card">
            <div class="aep-card__header">
              <div>
                <h2 class="aep-card__title">Active Issues (${issues.length})</h2>
                <p class="aep-card__subtitle">Jira issues ready for AI-assisted development</p>
              </div>
              <button class="aep-btn aep-btn--ghost aep-btn--sm" data-command="refresh" title="Sync Issues">
                <span class="codicon codicon-sync"></span>
              </button>
            </div>
            <div class="aep-stack">
              ${issueCards}
            </div>
          </div>
          ` : `
          <div class="aep-card">
            ${issueCards}
          </div>
          `}

          <!-- Quick Actions -->
          <div class="aep-card">
            <div class="aep-card__header">
              <h2 class="aep-card__title">Quick Actions</h2>
              <p class="aep-card__subtitle">Common development workflows</p>
            </div>
            <div class="aep-grid">
              <button class="aep-btn aep-btn--secondary" data-command="startSession">
                <span class="codicon codicon-play"></span>
                Start Session
              </button>
              <button class="aep-btn aep-btn--secondary" data-command="refresh">
                <span class="codicon codicon-refresh"></span>
                Refresh Data
              </button>
            </div>
          </div>
        </div>
      </div>`;
  }

  private signedOutView(): string {
    return `
      <div class="aep-container">
        <div class="aep-stack">
          <!-- Hero Section -->
          <div class="aep-card aep-card--elevated">
            <div class="aep-card__header">
              <div>
                <h1 class="aep-card__title">AEP Agent for VS Code</h1>
                <p class="aep-card__subtitle">AI-powered development assistant for engineering teams</p>
              </div>
              <div class="aep-status aep-status--offline">
                <span class="aep-status__dot"></span>
                Sign In Required
              </div>
            </div>
            
            <div class="aep-stack">
              <p class="aep-text--md">
                Connect your workspace to unlock AI-assisted planning, code generation, 
                and automated patch application without leaving VS Code.
              </p>
              
              <div class="aep-grid">
                <button class="aep-btn aep-btn--primary" data-command="signIn">
                  <span class="codicon codicon-sign-in"></span>
                  Sign In to AEP
                </button>
                <button class="aep-btn aep-btn--secondary" data-command="openPortal">
                  <span class="codicon codicon-globe"></span>
                  Visit Portal
                </button>
              </div>
            </div>
          </div>

          <!-- Features Grid -->
          <div class="aep-card">
            <div class="aep-card__header">
              <h2 class="aep-card__title">What you get with AEP</h2>
              <p class="aep-card__subtitle">Professional AI development workflows</p>
            </div>
            
            <div class="aep-grid">
              <div class="aep-card">
                <div class="aep-card__header">
                  <span style="font-size: 24px;">🧠</span>
                </div>
                <h3 class="aep-text--lg aep-text--bold aep-mb--sm">Intelligent Planning</h3>
                <p class="aep-text--sm aep-text--muted">
                  Generate executable development plans from Jira issues with built-in approval workflows.
                </p>
              </div>

              <div class="aep-card">
                <div class="aep-card__header">
                  <span style="font-size: 24px;">⚡</span>
                </div>
                <h3 class="aep-text--lg aep-text--bold aep-mb--sm">Code Automation</h3>
                <p class="aep-text--sm aep-text--muted">
                  AI-generated code changes with diff previews, testing, and safety guardrails.
                </p>
              </div>

              <div class="aep-card">
                <div class="aep-card__header">
                  <span style="font-size: 24px;">�</span>
                </div>
                <h3 class="aep-text--lg aep-text--bold aep-mb--sm">Full Observability</h3>
                <p class="aep-text--sm aep-text--muted">
                  Track development velocity, code quality, and deployment success metrics.
                </p>
              </div>

              <div class="aep-card">
                <div class="aep-card__header">
                  <span style="font-size: 24px;">🛡️</span>
                </div>
                <h3 class="aep-text--lg aep-text--bold aep-mb--sm">Enterprise Security</h3>
                <p class="aep-text--sm aep-text--muted">
                  OAuth device flow, role-based access control, and audit logging.
                </p>
              </div>
            </div>
          </div>

          <!-- Getting Started -->
          <div class="aep-card">
            <div class="aep-card__header">
              <h2 class="aep-card__title">Getting Started</h2>
              <p class="aep-card__subtitle">Three steps to AI-powered development</p>
            </div>
            
            <div class="aep-stack">
              <div class="aep-card">
                <div class="aep-card__header">
                  <div class="aep-status aep-status--pending">
                    <span>01</span>
                  </div>
                </div>
                <h3 class="aep-text--lg aep-text--bold aep-mb--sm">Connect Workspace</h3>
                <p class="aep-text--sm aep-text--muted aep-mb--md">
                  Authenticate with your organization and link GitHub or Jira projects securely.
                </p>
                <button class="aep-btn aep-btn--secondary aep-btn--sm" data-command="signIn">
                  <span class="codicon codicon-arrow-right"></span>
                  Start Here
                </button>
              </div>

              <div class="aep-card">
                <div class="aep-card__header">
                  <div class="aep-status aep-status--pending">
                    <span>02</span>
                  </div>
                </div>
                <h3 class="aep-text--lg aep-text--bold aep-mb--sm">Chat & Plan</h3>
                <p class="aep-text--sm aep-text--muted">
                  Describe your development goals and receive AI-generated execution plans.
                </p>
              </div>

              <div class="aep-card">
                <div class="aep-card__header">
                  <div class="aep-status aep-status--pending">
                    <span>03</span>
                  </div>
                </div>
                <h3 class="aep-text--lg aep-text--bold aep-mb--sm">Review & Apply</h3>
                <p class="aep-text--sm aep-text--muted">
                  Approve AI-suggested code changes and apply patches with confidence.
                </p>
              </div>
            </div>
          </div>

          <!-- Call to Action -->
          <div class="aep-card aep-card--elevated">
            <div class="aep-stack aep-stack--sm">
              <h2 class="aep-text--xl aep-text--bold">Ready to accelerate your development?</h2>
              <p class="aep-text--muted">
                Join thousands of developers using AEP to ship faster and maintain higher code quality.
              </p>
              <div class="aep-grid">
                <button class="aep-btn aep-btn--primary" data-command="signIn">
                  <span class="codicon codicon-rocket"></span>
                  Get Started Now
                </button>
                <button class="aep-btn aep-btn--ghost" data-command="openPortal">
                  <span class="codicon codicon-question"></span>
                  Learn More
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>`;
  }

  private renderIssue(issue: JiraIssue): string {
    const status = issue.status ?? 'Pending';
    const statusClass = this.getStatusClass(status);
    return `
      <div class="aep-card">
        <div class="aep-card__header">
          <div>
            <span class="aep-text--mono aep-text--sm aep-text--bold">${this.escape(issue.key)}</span>
            <div class="aep-status ${statusClass}">
              <span class="aep-status__dot"></span>
              ${this.escape(status)}
            </div>
          </div>
        </div>
        <h3 class="aep-text--md aep-text--bold aep-mb--sm">${this.escape(issue.summary)}</h3>
        <div class="aep-grid">
          <button class="aep-btn aep-btn--primary aep-btn--sm" data-command="pickIssue" data-key="${this.escape(issue.key)}">
            <span class="codicon codicon-play"></span>
            Start Planning
          </button>
          <button class="aep-btn aep-btn--secondary aep-btn--sm" data-url="${issue.url ?? ''}">
            <span class="codicon codicon-link-external"></span>
            Open in Jira
          </button>
        </div>
      </div>`;
  }

  private getStatusClass(status: string): string {
    const lowerStatus = status.toLowerCase();
    if (lowerStatus.includes('done') || lowerStatus.includes('closed') || lowerStatus.includes('resolved')) {
      return 'aep-status--online';
    }
    if (lowerStatus.includes('progress') || lowerStatus.includes('active') || lowerStatus.includes('development')) {
      return 'aep-status--pending';
    }
    return 'aep-status--offline';
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
