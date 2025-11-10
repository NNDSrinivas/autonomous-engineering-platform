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
      this.view.webview.html = boilerplate(this.view.webview, this.ctx, body, ['base.css', 'landing.css'], ['chat.js']);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.output.appendLine(`ChatSidebar render failed: ${message}`);
      const fallback = `
        <div class="landing-container">
          <div class="hero-section">
            <div class="logo-area">
              <div class="logo">⚠️</div>
              <h1>AEP Agent</h1>
              <p class="tagline">We couldn't load your workspace right now.</p>
            </div>
            <p style="color: var(--vscode-descriptionForeground);">${this.escape(message)}</p>
            <vscode-button appearance="secondary" id="retry">Retry</vscode-button>
          </div>
        </div>`;
      this.view.webview.html = boilerplate(this.view.webview, this.ctx, fallback, ['base.css', 'landing.css'], ['chat.js']);
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
    const issueCards = issues.length
      ? issues.map(issue => this.renderIssue(issue)).join('')
      : `<div class="empty">No issues found. Check your Jira integration.</div>`;

    return `
      <div class="card">
        <div class="row"><span class="h">${greeting}, welcome to AEP Agent</span></div>
        <div class="row mono">Signed in as ${this.escape(email)}</div>
        <div class="row" style="gap:8px;margin-top:8px;">
          <vscode-button id="start" appearance="primary">Start Session</vscode-button>
          <vscode-button id="refresh" appearance="secondary">Refresh</vscode-button>
        </div>
      </div>
      ${issueCards}`;
  }

  private signedOutView(): string {
    return `
      <div class="landing-container">
        <div class="hero-section">
          <div class="logo-area">
            <div class="logo">🤖</div>
            <h1>AEP Agent</h1>
            <p class="tagline">Your AI-powered development assistant</p>
            <div class="status-indicator status-disconnected">
              ⚠️ Not connected - Authentication required
            </div>
          </div>

          <div class="auth-section">
            <vscode-button appearance="primary" id="signIn">
              🔐 Sign In with Auth0
            </vscode-button>
            <vscode-button appearance="secondary" id="getStarted">
              🧪 Demo Mode
            </vscode-button>
            <p style="margin-top: 1rem; font-size: 0.85em; color: var(--vscode-descriptionForeground); text-align: center;">
              ℹ️ Requires AEP backend server for authentication
            </p>
          </div>
        </div>

        <div class="features-grid">
          <div class="feature-card">
            <div class="feature-icon">💻</div>
            <h3>Code Analysis</h3>
            <p>Get instant AI-powered code reviews and suggestions</p>
          </div>

          <div class="feature-card">
            <div class="feature-icon">📋</div>
            <h3>Task Planning</h3>
            <p>Break down JIRA issues into actionable steps</p>
          </div>

          <div class="feature-card">
            <div class="feature-icon">🔧</div>
            <h3>Auto Patches</h3>
            <p>Apply AI-generated code changes with confidence</p>
          </div>

          <div class="feature-card">
            <div class="feature-icon">👥</div>
            <h3>Team Collaboration</h3>
            <p>Share insights and collaborate with your team</p>
          </div>
        </div>

        <div class="quick-start">
          <h3>Quick Start</h3>
          <div class="quick-actions">
            <button class="action-btn" id="tryDemo">
              <span class="action-icon">🎯</span>
              <div>
                <div class="action-title">Try Demo</div>
                <div class="action-desc">Explore features without signing in</div>
              </div>
            </button>

            <button class="action-btn" id="loadSample">
              <span class="action-icon">📝</span>
              <div>
                <div class="action-title">Load Sample Tasks</div>
                <div class="action-desc">See how AEP handles real projects</div>
              </div>
            </button>
          </div>
        </div>

        <div class="demo-chat" id="demoChat" style="display: none;">
          <div class="chat-header">
            <h3>💬 Chat with AEP Agent</h3>
            <button class="close-btn" id="closeDemo">×</button>
          </div>
          <div class="chat-messages" id="chatMessages"></div>
          <div class="chat-input-area">
            <textarea id="chatInput" placeholder="Ask me anything about your code..."></textarea>
            <button id="sendMessage" class="send-btn">Send</button>
          </div>
        </div>
      </div>`;
  }

  private renderIssue(issue: JiraIssue): string {
    return `
      <div class="card">
        <div class="row"><b>${this.escape(issue.key)}</b> — ${this.escape(issue.summary)} <span class="chip">${
          this.escape(issue.status)
        }</span></div>
        <div class="row">
          <vscode-button appearance="secondary" data-url="${issue.url ?? ''}" class="open">Open in Jira</vscode-button>
          <vscode-button class="plan">Plan</vscode-button>
        </div>
      </div>`;
  }

  private escape(text: string | null | undefined): string {
    return String(text ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
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
