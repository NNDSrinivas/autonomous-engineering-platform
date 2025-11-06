import * as vscode from 'vscode';
import { AEPClient } from '../api/client';
import { greeting } from '../util/time';

export class ChatSidebarProvider implements vscode.WebviewViewProvider {
  constructor(private ctx: vscode.ExtensionContext, private client: AEPClient){}
  private view?: vscode.WebviewView;
  resolveWebviewView(view: vscode.WebviewView){
    console.log('🔧 ChatSidebarProvider resolveWebviewView called');
    try {
      this.view = view;
      view.webview.options = { enableScripts: true };
      this.render();
      console.log('✅ ChatSidebarProvider webview resolved successfully');
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
  <style>
    body { font-family: var(--vscode-font-family); color: var(--vscode-foreground); background: var(--vscode-editor-background); margin: 16px; }
    .wrap { max-width: 400px; }
    h2 { color: var(--vscode-foreground); margin-bottom: 16px; }
    p { color: var(--vscode-descriptionForeground); margin-bottom: 16px; }
    .issues { list-style: none; padding: 0; margin: 16px 0; }
    .issues li { background: var(--vscode-list-hoverBackground); padding: 12px; margin: 8px 0; border-radius: 4px; cursor: pointer; border: 1px solid var(--vscode-contrastBorder); }
    .issues li:hover { background: var(--vscode-list-activeSelectionBackground); }
    .ask { margin-top: 16px; display: flex; gap: 8px; }
    .ask input { flex: 1; padding: 8px; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border); border-radius: 4px; }
    .ask button { padding: 8px 16px; background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; border-radius: 4px; cursor: pointer; }
    .st { float: right; font-size: 0.8em; opacity: 0.7; }
  </style>
</head>
<body>
<div class="wrap">
  <h2>${now}! 👋</h2>
  <p>Select a Jira task to begin, or ask a question.</p>
  <ul class="issues">
    ${issues.map(i=>`<li data-key="${i.key}"><b>${i.key}</b> – ${i.summary} <span class="st">${i.status}</span></li>`).join('')}
  </ul>
  <div class="ask">
    <input id="q" placeholder="Ask the agent about your project…" />
    <button id="ask">Ask</button>
  </div>
</div>
<script>
  const vscode = acquireVsCodeApi();
  document.getElementById('ask')?.addEventListener('click', () => {
    const input = document.getElementById('q');
    const question = input.value.trim();
    if (question) {
      vscode.postMessage({ type: 'ask', question });
      input.value = '';
    }
  });
  document.querySelectorAll('.issues li').forEach(li => {
    li.addEventListener('click', () => {
      const key = li.getAttribute('data-key');
      vscode.postMessage({ type: 'selectIssue', key });
    });
  });
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