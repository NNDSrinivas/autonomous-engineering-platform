/**
 * VS Code Extension Integration Guide
 * 
 * This file shows how to integrate the EnhancedChatPanel with your existing VS Code extension
 */

import * as vscode from 'vscode';
import { EnhancedChatPanel } from './panels/EnhancedChatPanel';
import { ChatPanel } from './panels/ChatPanel'; // Existing panel

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

        if (jiraKey) {
            // Open enhanced chat and automatically start the workflow
            EnhancedChatPanel.createOrShow(context.extensionUri);
            // The panel will handle the JIRA task selection
        }
    });

    // Add commands to subscriptions
    context.subscriptions.push(
        enhancedChatCommand,
        legacyChatCommand,
        startAutonomousCoding
    );

    // Show welcome message on first activation
    const hasShownWelcome = context.globalState.get('aep.hasShownEnhancedWelcome', false);
    if (!hasShownWelcome) {
        showEnhancedWelcomeMessage();
        context.globalState.update('aep.hasShownEnhancedWelcome', true);
    }

    console.log('✅ AEP Enhanced Extension Activated');
}

async function showEnhancedWelcomeMessage() {
    const action = await vscode.window.showInformationMessage(
        '🎉 AEP Enhanced is now available! Experience next-level autonomous coding with enterprise intelligence.',
        'Open Enhanced Chat',
        'Learn More'
    );

    switch (action) {
        case 'Open Enhanced Chat':
            vscode.commands.executeCommand('aep.openEnhancedChat');
            break;
        case 'Learn More':
            vscode.env.openExternal(vscode.Uri.parse('https://github.com/your-repo/aep-docs'));
            break;
    }
}

export function deactivate() {
    console.log('AEP Enhanced Extension Deactivated');
}

// Add to package.json contributions:
/*
{
  "contributes": {
    "commands": [
      {
        "command": "aep.openEnhancedChat",
        "title": "AEP: Open Enhanced Chat",
        "icon": "$(robot)"
      },
      {
        "command": "aep.startAutonomousCoding",
        "title": "AEP: Start Autonomous Coding",
        "icon": "$(zap)"
      }
    ],
    "menus": {
      "explorer/context": [
        {
          "command": "aep.startAutonomousCoding",
          "when": "resourceExtname == .py || resourceExtname == .js || resourceExtname == .ts",
          "group": "aep"
        }
      ],
      "editor/context": [
        {
          "command": "aep.openEnhancedChat",
          "group": "aep"
        }
      ]
    },
    "keybindings": [
      {
        "command": "aep.openEnhancedChat",
        "key": "ctrl+shift+a",
        "mac": "cmd+shift+a"
      }
    ]
  }
}
*/