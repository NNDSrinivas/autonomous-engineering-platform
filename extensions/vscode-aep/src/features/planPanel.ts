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
          case 'start-session':
            await vscode.commands.executeCommand('aep.startSession');
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
          <div class="plan-shell">
            <section class="panel aurora plan-hero">
              <div class="panel-header">
                <span class="badge badge-offline">Awaiting selection</span>
                <h1>Plan &amp; Act with AEP</h1>
                <p class="lead">Send an issue from the Agent sidebar or explore the demo workflow to see how AEP turns requests into execution plans.</p>
              </div>
              <div class="panel-actions">
                <vscode-button id="plan-start" data-command="start-session" appearance="primary">Choose an issue</vscode-button>
                <vscode-button id="demo-plan" appearance="secondary">Load demo plan</vscode-button>
              </div>
            </section>

            <section class="module walkthrough">
              <header>
                <div>
                  <h2>Your plan pipeline</h2>
                  <p>Every plan runs through approvals, patch previews, and one-click application.</p>
                </div>
              </header>
              <ol class="timeline-steps">
                <li>
                  <span class="step">01</span>
                  <div>
                    <strong>Select a Jira issue</strong>
                    <p>Pick a task from the Agent panel or search from the command palette.</p>
                  </div>
                </li>
                <li>
                  <span class="step">02</span>
                  <div>
                    <strong>Review AI-generated steps</strong>
                    <p>Assess the proposed milestones and request revisions where needed.</p>
                  </div>
                </li>
                <li>
                  <span class="step">03</span>
                  <div>
                    <strong>Apply curated patches</strong>
                    <p>Approve confident steps and apply the suggested code changes.</p>
                  </div>
                </li>
              </ol>
            </section>
          </div>`;
        this.view.webview.html = boilerplate(
          this.view.webview,
          this.ctx,
          body,
          ['base.css', 'aurora.css', 'plan.css'],
          ['plan.js']
        );
        return;
      }

      const current = this.steps[this.selectedIndex];
      const subtitle = current?.details || current?.description || '';
      const body = `
        <div class="plan-shell">
          <section class="panel aurora plan-hero">
            <div class="panel-header">
              <span class="badge badge-success">Execution plan ready</span>
              <h1>Plan &amp; Act</h1>
              <p class="lead">${this.steps.length} structured steps are ready for review. Approve, request changes, or apply the generated patch.</p>
            </div>
            <div class="panel-actions">
              <vscode-button id="plan-approve" appearance="primary">Approve step</vscode-button>
              <vscode-button id="plan-reject" appearance="secondary">Request revision</vscode-button>
              <vscode-button id="plan-apply" appearance="secondary">Apply patch</vscode-button>
            </div>
          </section>

          <div class="plan-layout">
            <aside class="plan-steps">
              <ul>
                ${this.steps
                  .map((step, index) => this.renderStep(step, index === this.selectedIndex, index))
                  .join('')}
              </ul>
            </aside>
            <section class="plan-detail">
              <header>
                <div>
                  <h2>${this.escape(current?.title ?? 'Select a step')}</h2>
                  <p>${this.escape(subtitle)}</p>
                </div>
                ${current?.status ? `<span class="status-pill">${this.escape(current.status)}</span>` : ''}
              </header>
              <div class="plan-detail-body">
                ${
                  this.selectedPatch
                    ? `<pre class="code-block">${this.escape(this.selectedPatch)}</pre>`
                    : '<div class="empty-state">Select a step from the list to inspect patch details.</div>'
                }
              </div>
            </section>
          </div>
        </div>`;

      this.view.webview.html = boilerplate(
        this.view.webview,
        this.ctx,
        body,
        ['base.css', 'aurora.css', 'plan.css'],
        ['plan.js']
      );
    } catch (error) {
      this.showError(error);
    }
  }

  private renderStep(step: ProposedStep, isSelected: boolean, index: number): string {
    const classes = ['plan-step'];
    if (isSelected) {
      classes.push('active');
    }
    if (step.status) {
      classes.push(`status-${this.slugify(step.status)}`);
    }
    const subtitle = step.details || step.description || '';
    return `
      <li class="${classes.join(' ')}" data-i="${index}">
        <span class="step-index">${(index + 1).toString().padStart(2, '0')}</span>
        <div class="step-copy">
          <strong>${this.escape(step.kind)} · ${this.escape(step.title)}</strong>
          ${subtitle ? `<p>${this.escape(subtitle)}</p>` : ''}
        </div>
        ${step.status ? `<span class="status-pill">${this.escape(step.status)}</span>` : ''}
      </li>`;
  }

  private escape(text: string | null | undefined): string {
    return String(text ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  private slugify(text: string): string {
    return text
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
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
      <div class="plan-shell">
        <section class="panel aurora error">
          <div class="panel-header">
            <span class="badge badge-alert">Plan failed</span>
            <h1>We hit a snag preparing your plan</h1>
            <p class="lead">${this.escape(message)}</p>
          </div>
          <div class="panel-actions">
            <vscode-button id="demo-plan" appearance="secondary">Load demo plan</vscode-button>
            <vscode-button id="plan-start" data-command="start-session" appearance="secondary">Choose another issue</vscode-button>
          </div>
        </section>
      </div>`;

    this.view.webview.html = boilerplate(
      this.view.webview,
      this.ctx,
      body,
      ['base.css', 'aurora.css', 'plan.css'],
      ['plan.js']
    );
  }
}
