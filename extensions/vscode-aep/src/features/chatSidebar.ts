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
    view.webview.onDidReceiveMessage((m)=>{
      if(m.type==='openExternal') vscode.env.openExternal(vscode.Uri.parse(m.url));
      if(m.type==='pickIssue') vscode.commands.executeCommand('aep.startSession');
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
    try {
      const issues = await this.client.listMyJiraIssues();
      const now = greeting();
      const makeIssue = (i:any)=> `
        <div class="card">
          <div class="row">
            <span class="badge gray">${i.status}</span>
            <span class="h">${i.key}</span>
          </div>
          <div>${i.summary}</div>
          <div class="row" style="margin-top:8px;">
            ${i.url ? `<a class="link" data-url="${i.url}">Open in Jira</a>`:''}
            <vscode-button data-key="${i.key}" appearance="secondary">Plan</vscode-button>
          </div>
        </div>`;

      const body = `
        <div class="card">
          <div class="row"><span class="badge green">●</span><span class="h">${now}, welcome to AEP Agent</span></div>
          <div>Ask about your project, request code analysis, or pick a Jira issue to start planning.</div>
          <div class="row" style="margin-top:8px;">
            <vscode-button id="signIn">Sign In</vscode-button>
            <vscode-button id="start" appearance="secondary">Start Session</vscode-button>
          </div>
        </div>
        ${issues.length? issues.map(makeIssue).join('') : `<div class="empty">No issues found. Sign in to load your Jira issues.</div>`}`;

      this.view!.webview.html = boilerplate(this.view!.webview, this.ctx, body, ['base.css'], ['chat.js']);
    } catch (error) {
      // Show error state
      const body = `
        <div class="card">
          <div class="h">Welcome to AEP Agent</div>
          <div>Please sign in to connect your IDE with AEP.</div>
          <div class="row" style="margin-top:8px;">
            <vscode-button id="signIn">Sign In</vscode-button>
          </div>
        </div>`;
      this.view!.webview.html = boilerplate(this.view!.webview, this.ctx, body, ['base.css'], ['chat.js']);
    }
  }
}
