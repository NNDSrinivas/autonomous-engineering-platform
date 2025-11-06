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
    
    try {
      const issues = await this.client.listMyJiraIssues();
      const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="stylesheet" href="${this.cssUri('chat.css')}">
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
<script>${this.script('chat.js')}</script>
</body>
</html>`;
      this.view!.webview.html = html;
    } catch (error) {
      // Show sign-in UI when not authenticated or backend not available
      const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="stylesheet" href="${this.cssUri('chat.css')}">
</head>
<body>
<div class="wrap">
  <h2>${now}! 👋</h2>
  <p>Welcome to AEP Agent! Please sign in to get started.</p>
  <div class="signin">
    <button id="signin">🔑 Sign In to AEP</button>
  </div>
  <div class="status">
    <p><small>Backend: <span id="status">Checking...</span></small></p>
  </div>
</div>
<script>
  const vscode = acquireVsCodeApi();
  document.getElementById('signin')?.addEventListener('click', () => {
    vscode.postMessage({ type: 'signin' });
  });
  
  // Check backend status
  fetch('http://localhost:8000/health').then(r => r.ok ? 'Connected' : 'Error').catch(() => 'Not running')
    .then(status => document.getElementById('status').textContent = status);
</script>
</body>
</html>`;
      this.view!.webview.html = html;
    }
    this.view!.webview.onDidReceiveMessage(async (m)=>{
      if(m.type==='pick-issue'){
        vscode.commands.executeCommand('revealView', 'aep.planView');
        vscode.commands.executeCommand('aep.startSession');
      }
      if(m.type==='ask'){ vscode.window.showInformationMessage('Question sent (wire to backend Q&A endpoint)'); }
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