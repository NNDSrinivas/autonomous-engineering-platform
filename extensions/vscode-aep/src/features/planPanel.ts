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
    console.log('🔧 PlanPanelProvider resolveWebviewView called');
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
    <h3>📋 Plan & Act - Connection Test</h3>
    <p>This is a test to verify the webview is working properly.</p>
    <button onclick="testDemo()">Load Demo Plan</button>
  </div>
  <script>
    const vscode = acquireVsCodeApi();
    function testDemo() {
      vscode.postMessage({ type: 'load-demo-plan' });
    }
  </script>
</body>
</html>`;
      
      console.log('✅ PlanPanelProvider webview HTML set successfully');
      
      // Then call the full render
      setTimeout(() => {
        this.render();
      }, 1000);
      
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
          { kind: 'setup', title: 'Analyze requirements and create project structure', description: 'Analyze requirements and create project structure', status: 'pending', patch: '// Demo patch 1\n+ Create new component\n- Remove old file' },
          { kind: 'implement', title: 'Implement core functionality', description: 'Implement core functionality', status: 'pending', patch: '// Demo patch 2\n+ Add main logic\n+ Update tests' },
          { kind: 'validate', title: 'Add error handling and validation', description: 'Add error handling and validation', status: 'pending', patch: '// Demo patch 3\n+ Try-catch blocks\n+ Input validation' }
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
    
    // Show actual plan content using new boilerplate
    const body = `
      <div class="wrap">
        <div class="card"><div class="h">Plan & Act</div></div>
        <div class="steps">
          <ul>
            ${this.steps.map((s,i)=>`<li class="${i===this.selectedIndex?'sel':''}" data-i="${i}">${s.kind}: ${s.title}</li>`).join('')}
          </ul>
        </div>
        <div class="details">
          ${this.selectedPatch? `<pre>${this.escape(this.selectedPatch)}</pre>` : '<em>Select a step</em>'}
        </div>
        <div class="actions">
          <vscode-button id="approve">Approve</vscode-button>
          <vscode-button appearance="secondary" id="reject">Reject</vscode-button>
          <vscode-button id="apply">Apply Patch</vscode-button>
        </div>
      </div>`;
    
    this.view!.webview.html = boilerplate(this.view!.webview, this.ctx, body, ['base.css', 'plan.css'], ['plan.js']);
  }

  private escape(text: string): string {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
}