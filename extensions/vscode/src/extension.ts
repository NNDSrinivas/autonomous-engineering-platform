import * as vscode from 'vscode';
import { EnhancedChatPanel } from './panels/EnhancedChatPanel';
export function activate(context: vscode.ExtensionContext) {
    console.log('🚀 AEP Enhanced Extension Activating...');

    // Register enhanced commands
    const enhancedChatCommand = vscode.commands.registerCommand('aep.openEnhancedChat', () => {
        EnhancedChatPanel.createOrShow(context.extensionUri);
    });

    // Register legacy chat command for backward compatibility
    const legacyChatCommand = vscode.commands.registerCommand('aep.openChat', () => {
        // For now, redirect to enhanced chat
        EnhancedChatPanel.createOrShow(context.extensionUri);
    });

    // Register autonomous coding commands
    const startAutonomousCoding = vscode.commands.registerCommand('aep.startAutonomousCoding', async () => {
        const jiraKey = await vscode.window.showInputBox({
            prompt: 'Enter JIRA ticket key (e.g., ENG-123)',
            placeHolder: 'ENG-123'
        });

        if (!jiraKey) {
            return;
        }

        // Create or show enhanced chat panel with autonomous coding mode
        const panel = EnhancedChatPanel.createOrShow(context.extensionUri);
        await panel.startAutonomousCoding(jiraKey);
    });

    // Register the plan and act command
    const planAndAct = vscode.commands.registerCommand('aep.planAndAct', () => {
        EnhancedChatPanel.createOrShow(context.extensionUri);
        vscode.window.showInformationMessage('Opening plan & act mode');
    });

    // Register agent commands
    const openAgent = vscode.commands.registerCommand('aep.openAgent', () => {
        EnhancedChatPanel.createOrShow(context.extensionUri);
    });

    const morningBrief = vscode.commands.registerCommand('aep.morningBrief', () => {
        EnhancedChatPanel.createOrShow(context.extensionUri);
        vscode.window.showInformationMessage('Good morning! Opening your briefing...');
    });

    // Register Jira related commands
    const pickJiraTask = vscode.commands.registerCommand('aep.pickJiraTask', async () => {
        EnhancedChatPanel.createOrShow(context.extensionUri);
        vscode.window.showInformationMessage('Opening JIRA task picker...');
    });

    const showPlan = vscode.commands.registerCommand('aep.showPlan', () => {
        EnhancedChatPanel.createOrShow(context.extensionUri);
        vscode.window.showInformationMessage('Showing current plan...');
    });

    // Authentication command
    const authenticate = vscode.commands.registerCommand('aep.authenticate', async () => {
        try {
            // Get base URL from configuration
            const config = vscode.workspace.getConfiguration('aep');
            const baseUrl = config.get<string>('baseUrl', 'http://localhost:8000');
            
            // Start OAuth device flow
            const response = await fetch(`${baseUrl}/oauth/device/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    client_id: 'vscode-extension',
                    scope: 'read write'
                })
            });

            if (!response.ok) {
                throw new Error(`Authentication server error: ${response.status}`);
            }

            const deviceData = await response.json();
            
            // Validate response structure with detailed error reporting
            const requiredFields = ['verification_uri', 'user_code', 'device_code'];
            const missingFields = requiredFields.filter(field => !deviceData || !deviceData[field]);
            
            if (missingFields.length > 0) {
                throw new Error(`Invalid response from authentication server: missing required fields: ${missingFields.join(', ')}`);
            }
            
            // Show user code and open browser
            const selection = await vscode.window.showInformationMessage(
                `Please visit ${deviceData.verification_uri} and enter code: ${deviceData.user_code}`,
                'Open Browser',
                'Cancel'
            );

            if (selection === 'Open Browser') {
                vscode.env.openExternal(vscode.Uri.parse(deviceData.verification_uri));
            }

            // Poll for authorization (simplified for demo)
            vscode.window.showInformationMessage('Authentication initiated. Please complete in browser.');
        } catch (error) {
            vscode.window.showErrorMessage(`Authentication failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    });

    // Add all commands to subscriptions
    context.subscriptions.push(
        enhancedChatCommand,
        legacyChatCommand,
        startAutonomousCoding,
        planAndAct,
        openAgent,
        morningBrief,
        pickJiraTask,
        showPlan,
        authenticate
    );

    console.log('✅ AEP Enhanced Extension Activated!');
}

export function deactivate() {
    console.log('🛑 AEP Enhanced Extension Deactivated');
}