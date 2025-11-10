import * as vscode from 'vscode';
import { ChatSidebarProvider } from './features/chatSidebar';
import { PlanPanelProvider } from './features/planPanel';
import { Approvals } from './features/approvals';
import { AuthPanel } from './features/authPanel';
import { AEPClient } from './api/client';
import { getConfig } from './config';
import { pollDeviceCode } from './deviceFlow';

const OUTPUT_CHANNEL = 'AEP Agent';
let outputChannel: vscode.OutputChannel | undefined;

export async function activate(context: vscode.ExtensionContext) {
  outputChannel = vscode.window.createOutputChannel(OUTPUT_CHANNEL);
  const output = outputChannel;
  output.appendLine('Activating AEP Agent extension…');

  try {
    const cfg = getConfig();
    output.appendLine(`Using backend ${cfg.baseUrl} for org ${cfg.orgId}`);

    const client = new AEPClient(context, cfg.baseUrl, cfg.orgId);
    const approvals = new Approvals(context, client, output);
    const chat = new ChatSidebarProvider(context, client, output);
    const plan = new PlanPanelProvider(context, client, approvals, output);
    const auth = new AuthPanel(context, client, cfg.portalUrl, output);

    const disposables: vscode.Disposable[] = [
      vscode.window.registerWebviewViewProvider('aep.chatView', chat, {
        webviewOptions: { retainContextWhenHidden: true }
      }),
      vscode.window.registerWebviewViewProvider('aep.planView', plan, {
        webviewOptions: { retainContextWhenHidden: true }
      }),
      vscode.window.registerWebviewViewProvider('aep.authView', auth, {
        webviewOptions: { retainContextWhenHidden: true }
      }),

      vscode.commands.registerCommand('aep.signIn', () => startDeviceFlow(client, chat, output)),
      vscode.commands.registerCommand('aep.startSession', () => {
        vscode.window.showInformationMessage('Starting an AEP planning session…');
      }),
      vscode.commands.registerCommand('aep.openPortal', () => {
        const portal = cfg.portalUrl || 'https://portal.aep.navra.ai';
        vscode.env.openExternal(vscode.Uri.parse(portal));
      }),
      vscode.commands.registerCommand('aep.plan.approve', () => approvals.approveSelected()),
      vscode.commands.registerCommand('aep.plan.reject', () => approvals.rejectSelected()),
      vscode.commands.registerCommand('aep.applyPatch', () => plan.applySelectedPatch())
    ];

    context.subscriptions.push(...disposables, output);
    output.appendLine('AEP Agent extension activated successfully.');
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    output.appendLine(`Activation failed: ${message}`);
    vscode.window.showErrorMessage(
      'AEP Agent extension failed to activate. Check the AEP Agent output channel for details.'
    );
    throw error;
  }
}

async function startDeviceFlow(
  client: AEPClient,
  chat: ChatSidebarProvider,
  output: vscode.OutputChannel
) {
  try {
    const flow = await client.startDeviceCode();
    output.appendLine('Device flow started. Opening browser for verification.');

    const verificationUrl = flow.verification_uri_complete || flow.verification_uri;
    const codeLabel = flow.user_code ? ` (code: ${flow.user_code})` : '';

    vscode.window
      .showInformationMessage(`Open the browser to complete sign-in${codeLabel}`, 'Open Browser')
      .then(selection => {
        if (selection === 'Open Browser' && verificationUrl) {
          vscode.env.openExternal(vscode.Uri.parse(verificationUrl));
        }
      });

    if (!flow.device_code) {
      throw new Error('Device authorization response was missing a device code.');
    }

    await pollDeviceCode(client, flow.device_code, output);
    vscode.window.showInformationMessage('Signed in to AEP successfully.');
    chat.refresh();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    output.appendLine(`Sign-in failed: ${message}`);
    vscode.window.showErrorMessage(`AEP sign-in failed: ${message}`);
  }
}

export function deactivate() {
  outputChannel?.appendLine('AEP Agent extension deactivated.');
}
