import * as vscode from 'vscode';
import { AEPClient } from '../api/client';
import { Approvals } from './approvals';
import { boilerplate } from '../webview/view';

export class PlanPanelProvider implements vscode.WebviewViewProvider {
  private view?: vscode.WebviewView;
  private steps: any[] = [];
  private selectedIndex = 0;
  private selectedPatch: string | null = null;

  constructor(private ctx: vscode.ExtensionContext, private client: AEPClient, private approvals: Approvals){}

  resolveWebviewView(view: vscode.WebviewView){
    this.view = view;
    view.webview.options = { enableScripts: true };
    this.render();

    view.webview.onDidReceiveMessage(async message => {
      try {
        if (message.type === 'load-plan' && message.issue) {
          this.steps = await this.client.proposePlan(message.issue);
          this.selectedIndex = 0;
          this.selectedPatch = this.steps[0]?.patch || null;
          this.render();
          return;
        }

        if (message.type === 'load-demo-plan') {
          this.steps = this.demoPlan();
          this.selectedIndex = 0;
          this.selectedPatch = this.steps[0]?.patch || null;
          this.render();
          vscode.window.showInformationMessage('Demo plan loaded! 🚀');
          return;
        }

        if (message.type === 'select' && typeof message.index === 'number') {
          this.selectedIndex = message.index;
          this.selectedPatch = this.steps[message.index]?.patch || null;
          this.render();
          return;
        }

        if (message.type === 'approve') {
          await this.approvals.approve(this.steps[this.selectedIndex]);
          return;
        }

        if (message.type === 'reject') {
          await this.approvals.reject(this.steps[this.selectedIndex]);
          return;
        }

        if (message.type === 'applyPatch') {
          await vscode.commands.executeCommand('aep.applyPatch');
          return;
        }
      } catch (error) {
        this.showError(error);
      }
    });
  }

  refresh(){ if(this.view) this.render(); }

  async applySelectedPatch(){
    if(!this.selectedPatch){
      vscode.window.showWarningMessage('No patch selected');
      return;
    }
    try {
      const res = await this.client.applyPatch(this.selectedPatch);
      vscode.window.showInformationMessage(res.applied ? 'Patch applied' : 'Patch failed');
    } catch (error: any) {
      vscode.window.showErrorMessage(`Unable to apply patch: ${error?.message ?? error}`);
    }
  }

  private render(){
    if (!this.view) {
      return;
    }

    try {
      if (this.steps.length === 0) {
        const body = `
          <div class="plan-placeholder">
            <div class="card">
              <div class="h">Plan &amp; Act</div>
              <p class="lead">Select an issue from the Agent view to generate an execution plan.</p>
              <vscode-button id="demo-plan" appearance="secondary">🧪 Load Demo Plan</vscode-button>
            </div>
            <ul class="how-it-works">
              <li>Pick a JIRA issue from the Agent tab</li>
              <li>AEP drafts a reviewable plan</li>
              <li>Approve or reject each step</li>
              <li>Apply AI-generated patches with one click</li>
            </ul>
          </div>`;
        this.view.webview.html = boilerplate(this.view.webview, this.ctx, body, ['base.css', 'plan.css'], ['plan.js']);
        return;
      }

      const body = `
        <div class="wrap">
          <div class="card"><div class="h">Plan &amp; Act</div></div>
          <div class="steps">
            <ul>
              ${this.steps.map((s, i) => `<li class="${i === this.selectedIndex ? 'sel' : ''}" data-i="${i}">${this.escape(s.kind)}: ${this.escape(s.title)}</li>`).join('')}
            </ul>
          </div>
          <div class="details">
            ${this.selectedPatch ? `<pre>${this.escape(this.selectedPatch)}</pre>` : '<em>Select a step to inspect details</em>'}
          </div>
          <div class="actions">
            <vscode-button id="approve">Approve</vscode-button>
            <vscode-button appearance="secondary" id="reject">Reject</vscode-button>
            <vscode-button id="apply">Apply Patch</vscode-button>
          </div>
        </div>`;
      this.view.webview.html = boilerplate(this.view.webview, this.ctx, body, ['base.css', 'plan.css'], ['plan.js']);
    } catch (error) {
      this.showError(error);
    }
  }

  private escape(text: string): string {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  private demoPlan() {
    return [
      { kind: 'Setup', title: 'Analyze requirements and create project structure', description: 'Analyze requirements and create project structure', status: 'pending', patch: '// Demo patch 1\n+ Create new component\n- Remove old file' },
      { kind: 'Implement', title: 'Implement core functionality', description: 'Implement core functionality', status: 'pending', patch: '// Demo patch 2\n+ Add main logic\n+ Update tests' },
      { kind: 'Validate', title: 'Add error handling and validation', description: 'Add error handling and validation', status: 'pending', patch: '// Demo patch 3\n+ Try-catch blocks\n+ Input validation' }
    ];
  }

  private showError(error: unknown) {
    if (!this.view) {
      return;
    }
    const message = error instanceof Error ? error.message : String(error);
    const body = `
      <div class="card error">
        <div class="h">We hit a snag</div>
        <p>${this.escape(message)}</p>
        <vscode-button id="demo-plan" appearance="secondary">Try Demo Plan</vscode-button>
      </div>`;
    this.view.webview.html = boilerplate(this.view.webview, this.ctx, body, ['base.css', 'plan.css'], ['plan.js']);
  }
}
