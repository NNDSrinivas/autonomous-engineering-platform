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
    console.log('🔧 PlanPanelProvider resolveWebviewView called');
    try {
      this.view = view; 
      view.webview.options = { enableScripts: true }; 
      this.render();
      console.log('✅ PlanPanelProvider webview resolved successfully');
    } catch (error) {
      console.error('❌ PlanPanelProvider resolveWebviewView failed:', error);
    }
    view.webview.onDidReceiveMessage(async (m)=>{
      if(m.type==='load-plan' && m.issue){
        this.steps = await this.client.proposePlan(m.issue);
        this.selectedIndex = 0; this.selectedPatch = this.steps[0]?.patch || null; this.render();
      }
      if(m.type==='load-demo-plan'){
        // Load demo plan for testing
        this.steps = [
          { description: 'Analyze requirements and create project structure', status: 'pending', patch: '// Demo patch 1\n+ Create new component\n- Remove old file' },
          { description: 'Implement core functionality', status: 'pending', patch: '// Demo patch 2\n+ Add main logic\n+ Update tests' },
          { description: 'Add error handling and validation', status: 'pending', patch: '// Demo patch 3\n+ Try-catch blocks\n+ Input validation' }
        ];
        this.selectedIndex = 0; 
        this.selectedPatch = this.steps[0]?.patch || null; 
        this.render();
        vscode.window.showInformationMessage('Demo plan loaded! 🚀');
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
    console.log('🎨 PlanPanelProvider render() called with steps:', this.steps.length);
    
    // Show default content if no steps are loaded
    if (this.steps.length === 0) {
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
    .placeholder { text-align: center; padding: 40px 20px; border: 2px dashed var(--vscode-contrastBorder); border-radius: 8px; background: var(--vscode-textBlockQuote-background); }
    .placeholder h3 { margin-bottom: 16px; color: var(--vscode-foreground); }
    .sample-issue { background: var(--vscode-list-hoverBackground); padding: 12px; margin: 8px 0; border-radius: 4px; cursor: pointer; border: 1px solid var(--vscode-contrastBorder); }
    .sample-issue:hover { background: var(--vscode-list-activeSelectionBackground); }
    button { padding: 8px 16px; background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; border-radius: 4px; cursor: pointer; margin: 4px; }
    button:hover { background: var(--vscode-button-hoverBackground); }
  </style>
</head>
<body>
<div class="wrap">
  <h2>📋 Plan & Act</h2>
  <div class="placeholder">
    <h3>🚀 Ready to Plan!</h3>
    <p>Select a JIRA issue from the Agent tab to generate an execution plan.</p>
    <div style="margin-top: 20px;">
      <p><strong>How it works:</strong></p>
      <ol style="text-align: left; display: inline-block;">
        <li>Choose a JIRA issue in the Agent tab</li>
        <li>AI generates a step-by-step plan</li>
        <li>Review and approve each step</li>
        <li>Apply code changes automatically</li>
      </ol>
    </div>
    <div style="margin-top: 20px;">
      <button id="demo-plan">🧪 Load Demo Plan</button>
    </div>
  </div>
</div>
<script>
  const vscode = acquireVsCodeApi();
  document.getElementById('demo-plan')?.addEventListener('click', () => {
    vscode.postMessage({ type: 'load-demo-plan' });
  });
</script>
</body>
</html>`;
      this.view!.webview.html = html;
      return;
    }
    
    // Show actual plan content
    const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body { font-family: var(--vscode-font-family); color: var(--vscode-foreground); background: var(--vscode-editor-background); margin: 16px; }
    .wrap { max-width: 500px; }
    h2 { color: var(--vscode-foreground); margin-bottom: 16px; }
    .steps { list-style: none; padding: 0; }
    .step { background: var(--vscode-list-hoverBackground); padding: 12px; margin: 8px 0; border-radius: 4px; cursor: pointer; border: 1px solid var(--vscode-contrastBorder); }
    .step.selected { background: var(--vscode-list-activeSelectionBackground); border-color: var(--vscode-focusBorder); }
    .step:hover { background: var(--vscode-list-activeSelectionBackground); }
    .actions { margin-top: 16px; display: flex; gap: 8px; flex-wrap: wrap; }
    button { padding: 8px 16px; background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; border-radius: 4px; cursor: pointer; }
    button:hover { background: var(--vscode-button-hoverBackground); }
    button.approve { background: var(--vscode-testing-iconPassed); }
    button.reject { background: var(--vscode-testing-iconFailed); }
    .patch { margin-top: 16px; padding: 12px; background: var(--vscode-textCodeBlock-background); border-radius: 4px; font-family: monospace; font-size: 12px; max-height: 200px; overflow-y: auto; border: 1px solid var(--vscode-contrastBorder); }
  </style>
</head>
<body>
<div class="wrap">
  <h2>📋 Execution Plan (${this.steps.length} steps)</h2>
  <ol class="steps">
    ${this.steps.map((step, i) => `
      <li class="step ${i === this.selectedIndex ? 'selected' : ''}" data-index="${i}">
        <strong>Step ${i + 1}:</strong> ${step.description || step.task || 'Untitled step'}
        ${step.status ? `<span style="float: right; color: var(--vscode-descriptionForeground);">${step.status}</span>` : ''}
      </li>
    `).join('')}
  </ol>
  <div class="actions">
    <button class="approve" id="approve">✅ Approve Step</button>
    <button class="reject" id="reject">❌ Reject Step</button>
    ${this.selectedPatch ? '<button id="apply-patch">🔧 Apply Patch</button>' : ''}
  </div>
  ${this.selectedPatch ? `<div class="patch"><strong>Selected Patch:</strong><br><pre>${this.selectedPatch.substring(0, 500)}${this.selectedPatch.length > 500 ? '...' : ''}</pre></div>` : ''}
</div>
<script>
  const vscode = acquireVsCodeApi();
  document.querySelectorAll('.step').forEach((step, index) => {
    step.addEventListener('click', () => {
      vscode.postMessage({ type: 'select', index });
    });
  });
  document.getElementById('approve')?.addEventListener('click', () => {
    vscode.postMessage({ type: 'approve' });
  });
  document.getElementById('reject')?.addEventListener('click', () => {
    vscode.postMessage({ type: 'reject' });
  });
  document.getElementById('apply-patch')?.addEventListener('click', () => {
    vscode.postMessage({ type: 'applyPatch' });
  });
</script>
</body>
</html>`;
    this.view!.webview.html = html;
  }
}