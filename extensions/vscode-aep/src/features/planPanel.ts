import * as vscode from 'vscode';
import { AEPClient } from '../api/client';
import { Approvals } from './approvals';

export class PlanPanelProvider implements vscode.WebviewViewProvider {
  private view?: vscode.WebviewView;
  private steps: any[] = [];
  private selectedIndex = 0;
  private selectedPatch: string | null = null;

  constructor(private ctx: vscode.ExtensionContext, private client: AEPClient, private approvals: Approvals){}

  resolveWebviewView(view: vscode.WebviewView){
    this.view = view; view.webview.options = { enableScripts: true }; this.render();
    view.webview.onDidReceiveMessage(async (m)=>{
      if(m.type==='load-plan' && m.issue){
        this.steps = await this.client.proposePlan(m.issue);
        this.selectedIndex = 0; this.selectedPatch = this.steps[0]?.patch || null; this.render();
      }
      if(m.type==='select' && typeof m.index==='number'){
        this.selectedIndex = m.index; this.selectedPatch = this.steps[m.index]?.patch || null; this.render();
      }
      if(m.type==='approve'){ this.approvals.approve(this.steps[this.selectedIndex]); }
      if(m.type==='reject'){ this.approvals.reject(this.steps[this.selectedIndex]); }
      if(m.type==='applyPatch'){ vscode.commands.executeCommand('aep.applyPatch'); }
    });
  }

  refresh(){ if(this.view) this.render(); }

  async applySelectedPatch(){
    if(!this.selectedPatch){ vscode.window.showWarningMessage('No patch selected'); return; }
    const res = await this.client.applyPatch(this.selectedPatch);
    vscode.window.showInformationMessage(res.applied ? 'Patch applied' : 'Patch failed');
  }

  private render(){
    const html = `
      <link rel="stylesheet" href="${this.css('plan.css')}">
      <div class="wrap">
        <h3>Plan & Act</h3>
        ${this.steps.length > 0 ? `
        <div class="steps">
          <ul>
            ${this.steps.map((s,i)=>`<li class="${i===this.selectedIndex?'sel':''}" data-i="${i}">${s.kind}: ${s.title}</li>`).join('')}
          </ul>
        </div>
        <div class="details">
          ${this.selectedPatch? `<pre>${this.escape(this.selectedPatch)}</pre>` : '<em>Select a step</em>'}
        </div>
        <div class="actions">
          <button id="approve">Approve</button>
          <button id="reject">Reject</button>
          <button id="apply">Apply Patch</button>
        </div>
        ` : `
        <div class="empty">
          <p>Select a JIRA task from the Agent panel to generate a plan.</p>
          <p><small>Plans break down tasks into reviewable steps with code patches.</small></p>
        </div>
        `}
      </div>
      <script>${this.script('plan.js')}</script>
    `;
    this.view!.webview.html = html;
  }

  private css(name:string){ return this.view!.webview.asWebviewUri(vscode.Uri.file(`${this.ctx.extensionPath}/media/${name}`)); }
  private escape(s:string){ return s.replace(/[&<>]/g, c=>({ '&':'&amp;','<':'&lt;','>':'&gt;' } as any)[c]); }
  private script(name:string){ if(name==='plan.js') return `(() => {
    const vscode = acquireVsCodeApi();
    const ul = document.querySelector('.steps ul');
    ul?.addEventListener('click', (e)=>{ const li = (e.target as HTMLElement).closest('li'); if(!li) return; const i = Number(li.getAttribute('data-i')); vscode.postMessage({type:'select', index:i}); });
    document.getElementById('approve')?.addEventListener('click', ()=> vscode.postMessage({type:'approve'}));
    document.getElementById('reject')?.addEventListener('click', ()=> vscode.postMessage({type:'reject'}));
    document.getElementById('apply')?.addEventListener('click', ()=> vscode.postMessage({type:'applyPatch'}));
  })();`; return ''; }
}