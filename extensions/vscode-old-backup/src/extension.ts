import * as vscode from 'vscode';
import { AgentPanel } from './panels/AgentPanel';
import { PlanActPanel } from './panels/PlanActPanel';
import { AuthManager } from './auth/AuthManager';
import { AEPApiClient } from './api/AEPApiClient';

/**
 * AEP VS Code Extension - Production Ready
 * 
 * Provides Cline-like capabilities with enterprise intelligence:
 * - Morning briefings with Jira task context
 * - Step-by-step plan & act workflow with approvals
 * - Cross-source memory with citations
 * - OAuth device flow authentication
 * - Real-time collaboration awareness
 */

let agentPanel: AgentPanel | undefined;
let planActPanel: PlanActPanel | undefined;
let authManager: AuthManager;
let apiClient: AEPApiClient;

export async function activate(context: vscode.ExtensionContext) {
    console.log('AEP Autonomous Agent activating...');

    // Initialize core services
    authManager = new AuthManager(context);
    apiClient = new AEPApiClient(authManager);

    // Register authentication status
    await updateAuthenticationContext();

    // Register all commands
    registerCommands(context);

    // Auto-greeting on startup if configured
    const config = vscode.workspace.getConfiguration('aep');
    if (config.get('autoGreeting') && await authManager.isAuthenticated()) {
        setTimeout(() => {
            vscode.commands.executeCommand('aep.morningBrief');
        }, 2000); // Delay to let VS Code finish loading
    }

    console.log('AEP Autonomous Agent activated successfully!');
}

function registerCommands(context: vscode.ExtensionContext) {
    // Authentication command
    const authenticate = vscode.commands.registerCommand('aep.authenticate', async () => {
        try {
            const success = await authManager.authenticate();
            if (success) {
                await updateAuthenticationContext();
                vscode.window.showInformationMessage('Successfully authenticated with AEP!');
                
                // Auto-show morning brief after authentication
                setTimeout(() => {
                    vscode.commands.executeCommand('aep.morningBrief');
                }, 1000);
            }
        } catch (error) {
            vscode.window.showErrorMessage(`Authentication failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    });

    // Open Agent Panel command
    const openAgent = vscode.commands.registerCommand('aep.openAgent', async () => {
        if (!await authManager.isAuthenticated()) {
            const result = await vscode.window.showInformationMessage(
                'Please authenticate with AEP first.',
                'Authenticate'
            );
            if (result === 'Authenticate') {
                vscode.commands.executeCommand('aep.authenticate');
            }
            return;
        }

        agentPanel = AgentPanel.createOrShow(context.extensionUri, apiClient);
    });

    // Morning Brief command
    const morningBrief = vscode.commands.registerCommand('aep.morningBrief', async () => {
        if (!await authManager.isAuthenticated()) {
            vscode.commands.executeCommand('aep.authenticate');
            return;
        }

        try {
            // Show morning brief in agent panel
            agentPanel = AgentPanel.createOrShow(context.extensionUri, apiClient);
            agentPanel.showMorningBrief();
            
            // Also show notification with quick stats
            const briefData = await apiClient.getMorningBrief();
            const taskCount = briefData.jiraTasks?.length || 0;
            const message = `Good morning! You have ${taskCount} Jira task${taskCount !== 1 ? 's' : ''} assigned.`;
            
            const result = await vscode.window.showInformationMessage(
                message,
                'View Tasks',
                'Pick Task',
                'Open Chat'
            );

            switch (result) {
                case 'View Tasks':
                    agentPanel.focusOnTasks();
                    break;
                case 'Pick Task':
                    vscode.commands.executeCommand('aep.pickJiraTask');
                    break;
                case 'Open Chat':
                    vscode.window.showInformationMessage('Chat panel coming soon!');
                    break;
            }
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to load morning brief: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    });

    // Pick Jira Task command
    const pickJiraTask = vscode.commands.registerCommand('aep.pickJiraTask', async () => {
        if (!await authManager.isAuthenticated()) {
            vscode.commands.executeCommand('aep.authenticate');
            return;
        }

        try {
            const tasks = await apiClient.getJiraTasks();
            
            if (!tasks || tasks.length === 0) {
                vscode.window.showInformationMessage('No Jira tasks assigned to you.');
                return;
            }

            // Show quick pick for task selection
            const items = tasks.map(task => ({
                label: task.key,
                description: task.summary,
                detail: `${task.status} • ${task.priority} • ${task.assignee}`,
                task
            }));

            const selected = await vscode.window.showQuickPick(items, {
                placeHolder: 'Select a Jira task to work on',
                matchOnDescription: true,
                matchOnDetail: true
            });

            if (selected) {
                // Start task-centric workflow
                planActPanel = PlanActPanel.createOrShow(context.extensionUri, apiClient);
                planActPanel.startTaskWorkflow(selected.task);
            }
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to load Jira tasks: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    });

    // Plan & Act command
    const planAndAct = vscode.commands.registerCommand('aep.planAndAct', async () => {
        if (!await authManager.isAuthenticated()) {
            vscode.commands.executeCommand('aep.authenticate');
            return;
        }

        planActPanel = PlanActPanel.createOrShow(context.extensionUri, apiClient);
    });

    // Show Plan command
    const showPlan = vscode.commands.registerCommand('aep.showPlan', async () => {
        if (!await authManager.isAuthenticated()) {
            vscode.commands.executeCommand('aep.authenticate');
            return;
        }

        if (planActPanel) {
            planActPanel.reveal();
        } else {
            vscode.commands.executeCommand('aep.planAndAct');
        }
    });

    // Register all commands
    context.subscriptions.push(
        authenticate,
        openAgent,
        morningBrief,
        pickJiraTask,
        planAndAct,
        showPlan
    );
}

async function updateAuthenticationContext() {
    const isAuthenticated = await authManager.isAuthenticated();
    vscode.commands.executeCommand('setContext', 'aep.authenticated', isAuthenticated);
}

export function deactivate() {
    // Clean up resources
    agentPanel?.dispose();
    planActPanel?.dispose();
    authManager?.dispose();
}