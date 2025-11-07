import * as vscode from 'vscode';
import { EnhancedChatPanel } from './panels/EnhancedChatPanel';
import { makeHttpRequest } from './utils/http';

// API Response Interfaces
interface DeviceCodeResponse {
    verification_uri: string;
    user_code: string;
    device_code: string;
    expires_in?: number;
    interval?: number;
}

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
            const baseUrl = config.get<string>('coreApi', 'http://localhost:8002');

            // Start OAuth device flow
            const response = await makeHttpRequest(`${baseUrl}/oauth/device/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    client_id: 'vscode-extension',
                    scope: 'read write'
                })
            });

            if (!response.ok) {
                // Provide user-friendly error messages based on status code
                let errorMessage: string;
                if (response.status >= 500) {
                    // Server errors (5xx)
                    errorMessage = 'Authentication service is temporarily unavailable. Please try again later.';
                } else if (response.status >= 400) {
                    // Client errors (4xx)
                    if (response.status === 404) {
                        errorMessage = 'Authentication endpoint not found. Please check your API configuration.';
                    } else if (response.status === 401 || response.status === 403) {
                        errorMessage = 'Authentication request was rejected. Please check your credentials.';
                    } else {
                        errorMessage = 'Please check your network connection and API configuration.';
                    }
                } else {
                    // Other errors
                    errorMessage = 'An unexpected error occurred during authentication.';
                }
                throw new Error(`${errorMessage} (Status: ${response.status})`);
            }

            const deviceData = await response.json() as DeviceCodeResponse;

            // Validate response structure with detailed error reporting
            const missing = [];
            if (!deviceData.verification_uri) missing.push('verification_uri');
            if (!deviceData.user_code) missing.push('user_code');
            if (!deviceData.device_code) missing.push('device_code');

            if (missing.length > 0) {
                throw new Error(`Invalid response from authentication server: missing required fields: ${missing.join(', ')}`);
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