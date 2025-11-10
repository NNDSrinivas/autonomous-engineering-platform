import * as vscode from 'vscode';
import { AEPClient } from '../api/client';
import { Approvals } from './approvals';
import { boilerplate } from '../webview/view';
import type { ProposedStep } from '../api/types';

export class PlanPanelProvider implements vscode.WebviewViewProvider {
  private view: vscode.WebviewView | undefined;
  private steps: ProposedStep[] = [];
  private selectedIndex = 0;
  private selectedPatch: string | null = null;

  constructor(
    private readonly ctx: vscode.ExtensionContext,
    private readonly client: AEPClient,
    private readonly approvals: Approvals,
    private readonly output: vscode.OutputChannel
  ) {}

  resolveWebviewView(view: vscode.WebviewView) {
    this.view = view;
    view.webview.options = { enableScripts: true };
    this.render();

    view.webview.onDidReceiveMessage(async message => {
      try {
        switch (message.type) {
          case 'load-plan':
            if (message.issue) {
              await this.loadPlan(message.issue);
            }
            break;
          case 'load-demo-plan':
            this.loadDemoPlan();
            break;
          case 'select':
            if (typeof message.index === 'number') {
              this.selectStep(message.index);
            }
            break;
          case 'approve':
            await this.approveSelected();
            break;
          case 'reject':
            await this.rejectSelected();
            break;
          case 'applyPatch':
            await vscode.commands.executeCommand('aep.applyPatch');
            break;
          default:
            this.output.appendLine(`Unknown plan message type: ${message.type}`);
        }
      } catch (error) {
        this.showError(error);
      }
    });
  }

  refresh() {
    if (this.view) {
      this.render();
    }
  }

  async applySelectedPatch() {
    if (!this.selectedPatch) {
      vscode.window.showWarningMessage('No patch selected');
      return;
    }

    try {
      const result = await this.client.applyPatch(this.selectedPatch);
      vscode.window.showInformationMessage(result.applied ? 'Patch applied' : 'Patch failed');
    } catch (error: any) {
      this.output.appendLine(`Unable to apply patch: ${error?.message ?? error}`);
      vscode.window.showErrorMessage(`Unable to apply patch: ${error?.message ?? error}`);
    }
  }

  private async loadPlan(issueKey: string) {
    this.output.appendLine(`Loading plan for ${issueKey}`);
    const steps = await this.client.proposePlan(issueKey);
    this.steps = steps;
    this.selectStep(0);
  }

  private loadDemoPlan() {
    this.steps = this.demoPlan();
    this.selectStep(0);
    vscode.window.showInformationMessage('Demo plan loaded! 🚀');
  }

  private selectStep(index: number) {
    this.selectedIndex = Math.max(0, Math.min(index, this.steps.length - 1));
    const step = this.steps[this.selectedIndex];
    this.selectedPatch = step?.patch || null;
    this.approvals.set(step ?? null);
    this.render();
  }

  private async approveSelected() {
    const step = this.steps[this.selectedIndex];
    if (step) {
      await this.approvals.approve(step);
    }
  }

  private async rejectSelected() {
    const step = this.steps[this.selectedIndex];
    if (step) {
      await this.approvals.reject(step);
    }
  }

  private render() {
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
              ${this.steps
                .map((step, index) => this.renderStep(step, index === this.selectedIndex, index))
                .join('')}
            </ul>
          </div>
          <div class="details">
            ${
              this.selectedPatch
                ? `<pre>${this.escape(this.selectedPatch)}</pre>`
                : '<em>Select a step to inspect details</em>'
            }
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

  private renderStep(step: ProposedStep, isSelected: boolean, index: number): string {
    const classes = isSelected ? 'sel' : '';
    const subtitle = step.details || step.description || '';
    const subtitleHtml = subtitle ? ` <span class="hint">${this.escape(subtitle)}</span>` : '';
    return `<li class="${classes}" data-i="${index}">${this.escape(step.kind)}: ${this.escape(step.title)}${subtitleHtml}</li>`;
  }

  private escape(text: string | null | undefined): string {
    return String(text ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  private demoPlan(): ProposedStep[] {
    return [
      {
        id: 'demo-1',
        kind: 'Setup',
        title: 'Analyze requirements and create project structure',
        description: 'Analyze requirements and create project structure',
        status: 'pending',
        patch: '// Demo patch 1\n+ Create new component\n- Remove old file'
      },
      {
        id: 'demo-2',
        kind: 'Implement',
        title: 'Implement core functionality',
        description: 'Implement core functionality',
        status: 'pending',
        patch: '// Demo patch 2\n+ Add main logic\n+ Update tests'
      },
      {
        id: 'demo-3',
        kind: 'Validate',
        title: 'Add error handling and validation',
        description: 'Add error handling and validation',
        status: 'pending',
        patch: '// Demo patch 3\n+ Try-catch blocks\n+ Input validation'
      }
    ];
  }

  private showError(error: unknown) {
    if (!this.view) {
      return;
    }

    const message = error instanceof Error ? error.message : String(error);
    this.output.appendLine(`Plan panel error: ${message}`);

    const body = `
      <div class="card error">
        <div class="h">We hit a snag</div>
        <p>${this.escape(message)}</p>
        <vscode-button id="demo-plan" appearance="secondary">Try Demo Plan</vscode-button>
      </div>`;

    this.view.webview.html = boilerplate(this.view.webview, this.ctx, body, ['base.css', 'plan.css'], ['plan.js']);
  }
}
