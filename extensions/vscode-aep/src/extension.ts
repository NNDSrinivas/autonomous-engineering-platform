import * as vscode from 'vscode';
import { ensureAuth } from './auth/deviceCode';
import { ChatSidebarProvider } from './features/chatSidebar';
import { PlanPanelProvider } from './features/planPanel';
import { Approvals } from './features/approvals';
import { AEPClient } from './api/client';
import { getConfig } from './config';

export async function activate(context: vscode.ExtensionContext) {
  console.log('AEP Extension activating...');
  
  const cfg = getConfig();
  const client = new AEPClient(context, cfg.baseUrl, cfg.orgId);
  const approvals = new Approvals(context, client);

  const chat = new ChatSidebarProvider(context, client);
  const plan = new PlanPanelProvider(context, client, approvals);

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('aep.chatView', chat),
    vscode.window.registerWebviewViewProvider('aep.planView', plan),

    vscode.commands.registerCommand('aep.signIn', async () => {
      await ensureAuth(context, client);
      vscode.window.showInformationMessage('AEP: Signed in');
      chat.refresh(); plan.refresh();
    }),

    vscode.commands.registerCommand('aep.startSession', async () => {
      await ensureAuth(context, client);
      await chat.sendHello();
    }),

    vscode.commands.registerCommand('aep.plan.approve', async () => approvals.approveSelected()),
    vscode.commands.registerCommand('aep.plan.reject', async () => approvals.rejectSelected()),
    vscode.commands.registerCommand('aep.applyPatch', async () => plan.applySelectedPatch())
  );
  
  console.log('AEP Extension activated successfully');
  vscode.window.showInformationMessage('AEP Extension loaded! Check the Activity Bar for AEP icon.');
}

export function deactivate() {}