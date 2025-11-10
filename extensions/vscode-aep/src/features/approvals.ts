import * as vscode from 'vscode';
import type { AEPClient } from '../api/client';
import type { ProposedStep } from '../api/types';

export class Approvals {
  private selected: ProposedStep | null = null;

  constructor(
    private readonly _ctx: vscode.ExtensionContext,
    private readonly _client: AEPClient,
    private readonly output: vscode.OutputChannel
  ) {}

  set(step: ProposedStep | null) {
    this.selected = step;
  }

  async approve(step: ProposedStep) {
    this.selected = step;
    await vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title: `Approving “${step.title}”…` },
      async progress => {
        progress.report({ increment: 33, message: 'Syncing with AEP…' });
        await vscode.env.clipboard.writeText(step.patch ?? step.details ?? step.description ?? step.title);
        this.output.appendLine(`Approved step ${step.id ?? step.title}`);
        progress.report({ increment: 66, message: 'Ready for execution' });
      }
    );
    vscode.window.showInformationMessage('Step approved and copied to clipboard for quick application.');
  }

  async reject(step: ProposedStep) {
    this.selected = step;
    const detail = step.details || step.description || step.title;
    this.output.appendLine(`Rejected step ${step.id ?? step.title}: ${detail}`);
    vscode.window.showWarningMessage(`Rejected plan step: ${step.title}`);
  }

  async approveSelected() {
    if (this.selected) {
      await this.approve(this.selected);
    } else {
      vscode.window.showInformationMessage('Select a plan step to approve.');
    }
  }

  async rejectSelected() {
    if (this.selected) {
      await this.reject(this.selected);
    } else {
      vscode.window.showInformationMessage('Select a plan step to reject.');
    }
  }
}
