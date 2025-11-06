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
        EnhancedChatPanel.createOrShow(context.extensionUri);
        vscode.window.showInformationMessage(`Starting autonomous coding for task: ${jiraKey}`);
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
        vscode.window.showInformationMessage('Authentication flow would be initiated here');
        // TODO: Implement authentication flow
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