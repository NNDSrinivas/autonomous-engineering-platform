import * as vscode from 'vscode';
import { AEPClient } from '../api/client';
import { greeting } from '../util/time';

export class ChatSidebarProvider implements vscode.WebviewViewProvider {
  constructor(private ctx: vscode.ExtensionContext, private client: AEPClient){}
  private view?: vscode.WebviewView;
  resolveWebviewView(view: vscode.WebviewView){
    console.log('🔧 ChatSidebarProvider resolveWebviewView called');
    console.log('🔍 Webview details:', { 
      viewType: view.viewType, 
      title: view.title,
      description: view.description 
    });
    try {
      this.view = view;
      view.webview.options = { enableScripts: true };
      
      // Immediately set simple HTML to test
      view.webview.html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body { 
      font-family: var(--vscode-font-family); 
      color: var(--vscode-foreground); 
      background: var(--vscode-editor-background); 
      margin: 16px; 
      padding: 16px;
    }
    .test-message { 
      background: var(--vscode-textBlockQuote-background); 
      padding: 16px; 
      border-radius: 8px; 
      border-left: 4px solid var(--vscode-focusBorder);
      margin-bottom: 16px;
    }
    button { 
      padding: 8px 16px; 
      background: var(--vscode-button-background); 
      color: var(--vscode-button-foreground); 
      border: none; 
      border-radius: 4px; 
      cursor: pointer; 
    }
  </style>
</head>
<body>
  <div class="test-message">
    <h3>🚀 AEP Agent - Connection Test</h3>
    <p>This is a test to verify the webview is working properly.</p>
    <button onclick="testMessage()">Test Message</button>
  </div>
  <script>
    const vscode = acquireVsCodeApi();
    function testMessage() {
      vscode.postMessage({ type: 'test', message: 'Hello from webview!' });
    }
  </script>
</body>
</html>`;
      
      console.log('✅ ChatSidebarProvider webview HTML set successfully');
      
      // Then call the full render
      setTimeout(() => {
        this.render();
      }, 1000);
      
    } catch (error) {
      console.error('❌ ChatSidebarProvider resolveWebviewView failed:', error);
    }
  }
  refresh(){ if(this.view) this.render(); }

  async sendHello(){
    const issues = await this.client.listMyJiraIssues();
    this.post({ type: 'hello', issues });
  }

  private post(message: any) {
    if (this.view) {
      this.view.webview.postMessage(message);
    }
  }

  private async render(){
    const now = greeting();
    
    console.log('🎨 ChatSidebarProvider render() called');
    
    try {
      console.log('🔍 Attempting to fetch JIRA issues...');
      const issues = await this.client.listMyJiraIssues();
      console.log('✅ Successfully fetched issues:', issues.length);
      
      const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AEP Agent</title>
  <style>
    :root {
      --vscode-button-primary-background: #0e639c;
      --vscode-button-primary-foreground: #ffffff;
      --vscode-button-primary-hoverBackground: #1177bb;
      --border-radius: 6px;
      --spacing-xs: 4px;
      --spacing-sm: 8px;
      --spacing-md: 12px;
      --spacing-lg: 16px;
      --spacing-xl: 24px;
    }
    
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    
    body {
      font-family: var(--vscode-font-family);
      color: var(--vscode-foreground);
      background: var(--vscode-editor-background);
      line-height: 1.4;
      font-size: 13px;
    }
    
    .container {
      padding: var(--spacing-lg);
      height: 100vh;
      display: flex;
      flex-direction: column;
    }
    
    .header {
      margin-bottom: var(--spacing-xl);
    }
    
    .welcome-section {
      background: var(--vscode-textBlockQuote-background);
      border-left: 3px solid var(--vscode-focusBorder);
      padding: var(--spacing-lg);
      border-radius: var(--border-radius);
      margin-bottom: var(--spacing-xl);
    }
    
    .welcome-title {
      font-size: 16px;
      font-weight: 600;
      margin-bottom: var(--spacing-sm);
      display: flex;
      align-items: center;
      gap: var(--spacing-sm);
    }
    
    .status-indicator {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #22c55e;
      animation: pulse 2s infinite;
    }
    
    .welcome-subtitle {
      color: var(--vscode-descriptionForeground);
      font-size: 12px;
      margin-bottom: var(--spacing-md);
    }
    
    .quick-actions {
      display: flex;
      gap: var(--spacing-sm);
      flex-wrap: wrap;
    }
    
    .btn {
      padding: var(--spacing-sm) var(--spacing-md);
      border: none;
      border-radius: var(--border-radius);
      cursor: pointer;
      font-size: 12px;
      font-weight: 500;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      gap: var(--spacing-xs);
    }
    
    .btn-primary {
      background: var(--vscode-button-primary-background);
      color: var(--vscode-button-primary-foreground);
    }
    
    .btn-primary:hover {
      background: var(--vscode-button-primary-hoverBackground);
    }
    
    .btn-secondary {
      background: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
      border: 1px solid var(--vscode-contrastBorder);
    }
    
    .btn-secondary:hover {
      background: var(--vscode-button-secondaryHoverBackground);
    }
    
    .section {
      margin-bottom: var(--spacing-xl);
    }
    
    .section-title {
      font-size: 14px;
      font-weight: 600;
      margin-bottom: var(--spacing-md);
      display: flex;
      align-items: center;
      gap: var(--spacing-sm);
    }
    
    .issues-container {
      flex: 1;
      overflow-y: auto;
    }
    
    .issues-list {
      list-style: none;
      gap: var(--spacing-sm);
      display: flex;
      flex-direction: column;
    }
    
    .issue-item {
      background: var(--vscode-list-hoverBackground);
      border: 1px solid var(--vscode-contrastBorder);
      border-radius: var(--border-radius);
      padding: var(--spacing-md);
      cursor: pointer;
      transition: all 0.2s ease;
      position: relative;
    }
    
    .issue-item:hover {
      background: var(--vscode-list-activeSelectionBackground);
      border-color: var(--vscode-focusBorder);
      transform: translateY(-1px);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }
    
    .issue-header {
      display: flex;
      justify-content: between;
      align-items: flex-start;
      gap: var(--spacing-sm);
      margin-bottom: var(--spacing-xs);
    }
    
    .issue-key {
      background: var(--vscode-badge-background);
      color: var(--vscode-badge-foreground);
      padding: 2px 6px;
      border-radius: 3px;
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.5px;
    }
    
    .issue-status {
      background: var(--vscode-statusBar-background);
      color: var(--vscode-statusBar-foreground);
      padding: 2px 6px;
      border-radius: 3px;
      font-size: 10px;
      margin-left: auto;
    }
    
    .issue-title {
      font-weight: 500;
      font-size: 13px;
      line-height: 1.3;
      margin-bottom: var(--spacing-xs);
    }
    
    .issue-meta {
      display: flex;
      align-items: center;
      gap: var(--spacing-md);
      font-size: 11px;
      color: var(--vscode-descriptionForeground);
    }
    
    .chat-input-section {
      margin-top: auto;
      padding-top: var(--spacing-lg);
      border-top: 1px solid var(--vscode-contrastBorder);
    }
    
    .input-container {
      display: flex;
      gap: var(--spacing-sm);
      align-items: flex-end;
    }
    
    .chat-input {
      flex: 1;
      background: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border);
      border-radius: var(--border-radius);
      padding: var(--spacing-md);
      font-family: inherit;
      font-size: 13px;
      resize: vertical;
      min-height: 40px;
      max-height: 120px;
    }
    
    .chat-input:focus {
      outline: none;
      border-color: var(--vscode-focusBorder);
      box-shadow: 0 0 0 1px var(--vscode-focusBorder);
    }
    
    .chat-input::placeholder {
      color: var(--vscode-input-placeholderForeground);
    }
    
    .send-btn {
      background: var(--vscode-button-primary-background);
      color: var(--vscode-button-primary-foreground);
      border: none;
      border-radius: var(--border-radius);
      padding: var(--spacing-md);
      cursor: pointer;
      transition: all 0.2s ease;
      min-width: 40px;
      height: 40px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    
    .send-btn:hover:not(:disabled) {
      background: var(--vscode-button-primary-hoverBackground);
    }
    
    .send-btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    
    .empty-state {
      text-align: center;
      padding: var(--spacing-xl);
      color: var(--vscode-descriptionForeground);
    }
    
    .empty-state-icon {
      font-size: 32px;
      margin-bottom: var(--spacing-md);
      opacity: 0.5;
    }
    
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.5; }
    }
    
    .tooltip {
      position: relative;
    }
    
    .tooltip:hover::after {
      content: attr(data-tooltip);
      position: absolute;
      bottom: 100%;
      left: 50%;
      transform: translateX(-50%);
      background: var(--vscode-editorHoverWidget-background);
      color: var(--vscode-editorHoverWidget-foreground);
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 11px;
      white-space: nowrap;
      z-index: 1000;
      border: 1px solid var(--vscode-contrastBorder);
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="welcome-section">
        <div class="welcome-title">
          <span class="status-indicator"></span>
          ${now}! Welcome to AEP Agent
        </div>
        <div class="welcome-subtitle">
          Your AI-powered development assistant is ready to help
        </div>
        <div class="quick-actions">
          <button class="btn btn-primary" onclick="signIn()">
            🔑 Sign In
          </button>
          <button class="btn btn-secondary" onclick="startSession()">
            🚀 Start Session
          </button>
        </div>
      </div>
    </div>
    
    <div class="section">
      <div class="section-title">
        📋 Available Issues (${issues.length})
      </div>
      <div class="issues-container">
        ${issues.length > 0 ? `
          <ul class="issues-list">
            ${issues.map(issue => `
              <li class="issue-item" data-key="${issue.key}" onclick="selectIssue('${issue.key}')">
                <div class="issue-header">
                  <span class="issue-key">${issue.key}</span>
                  <span class="issue-status">${issue.status}</span>
                </div>
                <div class="issue-title">${issue.summary}</div>
                <div class="issue-meta">
                  <span>🔗 ID: ${issue.id}</span>
                  <span>📋 Status: ${issue.status}</span>
                </div>
              </li>
            `).join('')}
          </ul>
        ` : `
          <div class="empty-state">
            <div class="empty-state-icon">📝</div>
            <div>No issues found. Sign in to load your JIRA issues.</div>
          </div>
        `}
      </div>
    </div>
    
    <div class="chat-input-section">
      <div class="input-container">
        <textarea 
          class="chat-input" 
          id="chatInput"
          placeholder="Ask the agent about your project, request code analysis, or get help with implementation..."
          rows="2"
        ></textarea>
        <button class="send-btn tooltip" data-tooltip="Send message" onclick="sendMessage()" id="sendBtn">
          ➤
        </button>
      </div>
    </div>
  </div>

  <script>
    const vscode = acquireVsCodeApi();
    
    function signIn() {
      vscode.postMessage({ type: 'signin' });
    }
    
    function startSession() {
      vscode.postMessage({ type: 'start-session' });
    }
    
    function selectIssue(key) {
      vscode.postMessage({ type: 'selectIssue', key });
      
      // Visual feedback
      document.querySelectorAll('.issue-item').forEach(item => {
        item.style.background = 'var(--vscode-list-hoverBackground)';
      });
      event.target.closest('.issue-item').style.background = 'var(--vscode-list-activeSelectionBackground)';
    }
    
    function sendMessage() {
      const input = document.getElementById('chatInput');
      const message = input.value.trim();
      
      if (message) {
        vscode.postMessage({ type: 'ask', question: message });
        input.value = '';
        input.style.height = '40px'; // Reset height
        updateSendButton();
      }
    }
    
    function updateSendButton() {
      const input = document.getElementById('chatInput');
      const sendBtn = document.getElementById('sendBtn');
      sendBtn.disabled = !input.value.trim();
    }
    
    // Auto-resize textarea
    document.getElementById('chatInput').addEventListener('input', function() {
      this.style.height = '40px';
      this.style.height = Math.min(this.scrollHeight, 120) + 'px';
      updateSendButton();
    });
    
    // Enter to send (Shift+Enter for new line)
    document.getElementById('chatInput').addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
    
    // Initialize
    updateSendButton();
  </script>
</body>
</html>`;
      this.view!.webview.html = html;
    } catch (error) {
      console.warn('⚠️ Could not fetch issues, showing sign-in UI:', error);
      // Show sign-in UI when not authenticated or backend not available
      const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body { font-family: var(--vscode-font-family); color: var(--vscode-foreground); background: var(--vscode-editor-background); margin: 16px; }
    .wrap { max-width: 400px; }
    h2 { color: var(--vscode-foreground); margin-bottom: 16px; }
    p { color: var(--vscode-descriptionForeground); margin-bottom: 16px; }
    .signin button { padding: 12px 24px; background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
    .signin button:hover { background: var(--vscode-button-hoverBackground); }
    .status { margin-top: 16px; padding: 12px; background: var(--vscode-textBlockQuote-background); border-left: 4px solid var(--vscode-textBlockQuote-border); border-radius: 4px; }
    .error { color: var(--vscode-errorForeground); font-family: monospace; font-size: 12px; margin-top: 8px; }
  </style>
</head>
<body>
<div class="wrap">
  <h2>${now}! 👋</h2>
  <p>Welcome to AEP Agent! Please sign in to get started.</p>
  <div class="signin">
    <button id="signin">🔑 Sign In to AEP</button>
  </div>
  <div class="status">
    <p><strong>Status:</strong> <span id="status">Not authenticated</span></p>
    <div class="error">Error: ${error instanceof Error ? error.message : String(error)}</div>
  </div>
  <div style="margin-top: 20px;">
    <p><strong>Getting Started:</strong></p>
    <ol>
      <li>Click "Sign In to AEP" above</li>
      <li>Complete the OAuth flow</li>
      <li>Start working with JIRA issues</li>
    </ol>
  </div>
</div>
<script>
  const vscode = acquireVsCodeApi();
  document.getElementById('signin')?.addEventListener('click', () => {
    vscode.postMessage({ type: 'signin' });
  });
</script>
</body>
</html>`;
      this.view!.webview.html = html;
    }
    
    // Set up message handling
    this.view!.webview.onDidReceiveMessage(async (m)=>{
      console.log('📨 ChatSidebar received message:', m);
      if(m.type==='selectIssue'){
        vscode.commands.executeCommand('workbench.view.extension.aep');
        vscode.window.showInformationMessage(`Selected issue: ${m.key}`);
      }
      if(m.type==='ask'){ 
        vscode.window.showInformationMessage(`Question: ${m.question}`); 
      }
      if(m.type==='signin'){ 
        vscode.commands.executeCommand('aep.signIn');
      }
      if(m.type==='test'){ 
        vscode.window.showInformationMessage(`✅ Webview test successful: ${m.message}`);
      }
    });
  }

  private cssUri(name:string){ return this.view!.webview.asWebviewUri(vscode.Uri.file(`${this.ctx.extensionPath}/media/${name}`)); }
  private script(name:string){
    // inline minimal script for MVP
    if(name==='chat.js') return `(() => {
      const vscode = acquireVsCodeApi();
      const ul = document.querySelector('.issues');
      ul?.addEventListener('click', (e)=>{
        const li = (e.target as HTMLElement).closest('li');
        if(!li) return; vscode.postMessage({ type:'pick-issue', key: li.getAttribute('data-key') });
      });
      document.getElementById('ask')?.addEventListener('click', ()=>{
        const v = (document.getElementById('q') as HTMLInputElement).value;
        vscode.postMessage({ type:'ask', q: v });
      });
    })();`;
    return '';
  }
}