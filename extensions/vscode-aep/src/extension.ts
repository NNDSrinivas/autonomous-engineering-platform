import * as vscode from 'vscode';
import { ensureAuth } from './auth/deviceCode';
import { ChatSidebarProvider } from './features/chatSidebar';
import { PlanPanelProvider } from './features/planPanel';
import { Approvals } from './features/approvals';
import { AEPClient } from './api/client';
import { getConfig } from './config';

export async function activate(context: vscode.ExtensionContext) {
  console.log('🚀 AEP Extension activating...');
  
  try {
    // Show activation in VS Code
    vscode.window.showInformationMessage('AEP Extension activated successfully!');
    
    const cfg = getConfig();
    console.log('📊 Extension config:', { baseUrl: cfg.baseUrl, orgId: cfg.orgId });
    
    const client = new AEPClient(context, cfg.baseUrl, cfg.orgId);
    const approvals = new Approvals(context, client);

    const chat = new ChatSidebarProvider(context, client);
    const plan = new PlanPanelProvider(context, client, approvals);

    console.log('🔧 Registering webview providers...');
    
    const chatProvider = vscode.window.registerWebviewViewProvider('aep.chatView', chat);
    const planProvider = vscode.window.registerWebviewViewProvider('aep.planView', plan);
    
    console.log('📋 Registered providers:', {
      chatView: 'aep.chatView',
      planView: 'aep.planView'
    });
    
    context.subscriptions.push(
      chatProvider,
      planProvider,

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
    
    console.log('✅ AEP Extension activated successfully');
    console.log('Setting up vscode host providers...');
    vscode.window.showInformationMessage('AEP Extension loaded! Check the Activity Bar for AEP icon.');
  } catch (error) {
    console.error('❌ AEP Extension activation failed:', error);
    vscode.window.showErrorMessage(`AEP Extension failed to activate: ${error}`);
  }
}

export function deactivate() {
  console.log('🛑 AEP Extension deactivating...');
}