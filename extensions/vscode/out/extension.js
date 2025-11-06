"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const EnhancedChatPanel_1 = require("./panels/EnhancedChatPanel");
function activate(context) {
    console.log('🚀 AEP Enhanced Extension Activating...');
    // Register enhanced commands
    const enhancedChatCommand = vscode.commands.registerCommand('aep.openEnhancedChat', () => {
        EnhancedChatPanel_1.EnhancedChatPanel.createOrShow(context.extensionUri);
    });
    // Register legacy chat command for backward compatibility
    const legacyChatCommand = vscode.commands.registerCommand('aep.openChat', () => {
        // For now, redirect to enhanced chat
        EnhancedChatPanel_1.EnhancedChatPanel.createOrShow(context.extensionUri);
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
        const panel = EnhancedChatPanel_1.EnhancedChatPanel.createOrShow(context.extensionUri);
        await panel.startAutonomousCoding(jiraKey);
    });
    // Register the plan and act command
    const planAndAct = vscode.commands.registerCommand('aep.planAndAct', () => {
        EnhancedChatPanel_1.EnhancedChatPanel.createOrShow(context.extensionUri);
        vscode.window.showInformationMessage('Opening plan & act mode');
    });
    // Register agent commands
    const openAgent = vscode.commands.registerCommand('aep.openAgent', () => {
        EnhancedChatPanel_1.EnhancedChatPanel.createOrShow(context.extensionUri);
    });
    const morningBrief = vscode.commands.registerCommand('aep.morningBrief', () => {
        EnhancedChatPanel_1.EnhancedChatPanel.createOrShow(context.extensionUri);
        vscode.window.showInformationMessage('Good morning! Opening your briefing...');
    });
    // Register Jira related commands
    const pickJiraTask = vscode.commands.registerCommand('aep.pickJiraTask', async () => {
        EnhancedChatPanel_1.EnhancedChatPanel.createOrShow(context.extensionUri);
        vscode.window.showInformationMessage('Opening JIRA task picker...');
    });
    const showPlan = vscode.commands.registerCommand('aep.showPlan', () => {
        EnhancedChatPanel_1.EnhancedChatPanel.createOrShow(context.extensionUri);
        vscode.window.showInformationMessage('Showing current plan...');
    });
    // Authentication command
    const authenticate = vscode.commands.registerCommand('aep.authenticate', async () => {
        try {
            // Get base URL from configuration
            const config = vscode.workspace.getConfiguration('aep');
            const baseUrl = config.get('baseUrl', 'http://localhost:8000');
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
            const selection = await vscode.window.showInformationMessage(`Please visit ${deviceData.verification_uri} and enter code: ${deviceData.user_code}`, 'Open Browser', 'Cancel');
            if (selection === 'Open Browser') {
                vscode.env.openExternal(vscode.Uri.parse(deviceData.verification_uri));
            }
            // Poll for authorization (simplified for demo)
            vscode.window.showInformationMessage('Authentication initiated. Please complete in browser.');
        }
        catch (error) {
            vscode.window.showErrorMessage(`Authentication failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    });
    // Add all commands to subscriptions
    context.subscriptions.push(enhancedChatCommand, legacyChatCommand, startAutonomousCoding, planAndAct, openAgent, morningBrief, pickJiraTask, showPlan, authenticate);
    console.log('✅ AEP Enhanced Extension Activated!');
}
function deactivate() {
    console.log('🛑 AEP Enhanced Extension Deactivated');
}
//# sourceMappingURL=extension.js.map