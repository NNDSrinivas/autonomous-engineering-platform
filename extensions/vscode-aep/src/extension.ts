import * as vscode from 'vscode';
import { ensureAuth } from './auth/deviceCode';
import { ChatSidebarProvider } from './features/chatSidebar';
import { PlanPanelProvider } from './features/planPanel';
import { Approvals } from './features/approvals';
import { AuthPanel } from './features/authPanel';
import { AEPClient } from './api/client';
import { getConfig } from './config';

export async function activate(context: vscode.ExtensionContext) {
  console.log('🚀 AEP Extension activating...');
  console.log('🔍 Extension context:', { 
    globalState: Object.keys(context.globalState.keys()), 
    workspaceState: Object.keys(context.workspaceState.keys()),
    subscriptions: context.subscriptions.length 
  });
  
  // Show immediate activation confirmation
  vscode.window.showInformationMessage('🚀 AEP Extension is ACTIVATING...', 'Show Console').then(selection => {
    if (selection === 'Show Console') {
      vscode.commands.executeCommand('workbench.action.toggleDevTools');
    }
  });
  
  try {
    // Show activation in VS Code
    vscode.window.showInformationMessage('AEP Extension activated successfully!');
    
    const cfg = getConfig();
    console.log('📊 Extension config:', { baseUrl: cfg.baseUrl, orgId: cfg.orgId });
    
    const client = new AEPClient(context, cfg.baseUrl, cfg.orgId);
    const approvals = new Approvals(context, client);

    const chat = new ChatSidebarProvider(context, client);
    const plan = new PlanPanelProvider(context, client, approvals);
    const auth = new AuthPanel(context, client, cfg.portalUrl);

    console.log('🔧 Registering webview providers...');
    console.log('🎯 About to register:', { 
      chatProviderInstance: !!chat, 
      planProviderInstance: !!plan,
      vscodeWindow: !!vscode.window 
    });
    
    const chatProvider = vscode.window.registerWebviewViewProvider('aep.chatView', chat);
    const planProvider = vscode.window.registerWebviewViewProvider('aep.planView', plan);
    const authProvider = vscode.window.registerWebviewViewProvider('aep.authView', auth);
    
    console.log('📋 Registered providers:', {
      chatView: 'aep.chatView',
      planView: 'aep.planView',
      chatDisposable: !!chatProvider,
      planDisposable: !!planProvider
    });
    
    context.subscriptions.push(
      chatProvider,
      planProvider,
      authProvider,

      vscode.commands.registerCommand('aep.signIn', async () => {
        await ensureAuth(context, client);
        vscode.window.showInformationMessage('AEP: Signed in');
        chat.refresh(); plan.refresh();
      }),

      vscode.commands.registerCommand('aep.startSession', async () => {
        await ensureAuth(context, client);
        await chat.sendHello();
      }),

      vscode.commands.registerCommand('aep.openPortal', async () => {
        const portal = cfg.portalUrl || 'https://portal.aep.navra.ai';
        vscode.env.openExternal(vscode.Uri.parse(portal));
      }),

      vscode.commands.registerCommand('aep.plan.approve', async () => approvals.approveSelected()),
      vscode.commands.registerCommand('aep.plan.reject', async () => approvals.rejectSelected()),
      vscode.commands.registerCommand('aep.applyPatch', async () => plan.applySelectedPatch()),
      
      // Debug command to test webview providers
      vscode.commands.registerCommand('aep.debug.testWebviews', async () => {
        console.log('🧪 Testing webview providers...');
        vscode.window.showInformationMessage('Testing webview providers - check console');
        
        // Force refresh webviews
        chat.refresh();
        plan.refresh();
        
        // Try to focus on the AEP views
        await vscode.commands.executeCommand('workbench.view.extension.aep');
      })
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