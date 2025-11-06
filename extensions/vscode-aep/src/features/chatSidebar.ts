import * as vscode from 'vscode';
import { AEPClient } from '../api/client';
import { greeting } from '../util/time';
import { boilerplate } from '../webview/view';

export class ChatSidebarProvider implements vscode.WebviewViewProvider {
  private view?: vscode.WebviewView;
  constructor(private ctx: vscode.ExtensionContext, private client: AEPClient){}

  resolveWebviewView(view: vscode.WebviewView){
    this.view = view; 
    view.webview.options = { enableScripts: true };
    this.render();
    view.webview.onDidReceiveMessage(async (m)=>{
      console.log('ChatSidebar received message:', m);
      
      if(m.type==='openExternal') {
        vscode.env.openExternal(vscode.Uri.parse(m.url));
      }
      else if(m.type==='openPortal') {
        vscode.commands.executeCommand('aep.openPortal');
      }
      else if(m.type==='pickIssue') {
        vscode.commands.executeCommand('aep.startSession');
      }
      else if(m.type==='signIn') {
        vscode.commands.executeCommand('aep.signIn');
        // Refresh after sign in attempt
        setTimeout(() => this.render(), 2000);
      }
      else if(m.type==='startSession') {
        vscode.commands.executeCommand('aep.startSession');
      }
      else if(m.type==='refresh') {
        await this.render();
      }
      else if(m.type==='chat' && m.message) {
        await this.handleChatMessage(m.message);
      }
    });
  }

  refresh(){ 
    if(this.view) this.render(); 
  }

  async sendHello(){
    const issues = await this.client.listMyJiraIssues();
    this.post({ type: 'hello', issues });
  }

  private post(message: any) {
    if (this.view) {
      this.view.webview.postMessage(message);
    }
  }

  async render(){
    // For now, always show the landing page until we implement proper auth
    
    // Modern AI assistant landing page
    const body = `
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
            <vscode-button id="getStarted">
              🚀 Get Started
            </vscode-button>
            <vscode-button appearance="secondary" id="signIn">
              🔐 Sign In
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
            <h3>� Chat with AEP Agent</h3>
            <button class="close-btn" id="closeDemo">×</button>
          </div>
          <div class="chat-messages" id="chatMessages"></div>
          <div class="chat-input-area">
            <textarea id="chatInput" placeholder="Ask me anything about your code..."></textarea>
            <button id="sendMessage" class="send-btn">Send</button>
          </div>
        </div>
      </div>`;
    
    this.view!.webview.html = boilerplate(this.view!.webview, this.ctx, body, ['base.css', 'landing.css'], ['chat.js']);
  }

  private async handleChatMessage(message: string) {
    try {
      // Show user message immediately
      this.showChatMessage('user', message);
      
      // Show typing indicator
      this.showChatMessage('system', '🤔 Thinking...');
      
      // Send to AI backend
      const response = await fetch(`${this.client['baseUrl']}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, type: 'question' })
      });
      
      if (response.ok) {
        const result = await response.json() as any;
        this.showChatMessage('assistant', result.response || result.message || 'I received your message but had trouble generating a response.');
      } else {
        this.showChatMessage('assistant', 'Sorry, I\'m having trouble connecting right now. Please try again later.');
      }
    } catch (error) {
      console.error('Chat error:', error);
      this.showChatMessage('assistant', 'I encountered an error processing your message. Please check your connection and try again.');
    }
  }
  
  private showChatMessage(role: 'user' | 'assistant' | 'system', content: string) {
    // Send message to webview for display
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
