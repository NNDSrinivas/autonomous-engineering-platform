"use strict";
/**
 * VS Code Extension Integration Guide
 *
 * This file shows how to integrate the EnhancedChatPanel with your existing VS Code extension
 */
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
        if (jiraKey) {
            // Open enhanced chat and automatically start the workflow
            EnhancedChatPanel_1.EnhancedChatPanel.createOrShow(context.extensionUri);
            // The panel will handle the JIRA task selection
        }
    });
    // Add commands to subscriptions
    context.subscriptions.push(enhancedChatCommand, legacyChatCommand, startAutonomousCoding);
    // Show welcome message on first activation
    const hasShownWelcome = context.globalState.get('aep.hasShownEnhancedWelcome', false);
    if (!hasShownWelcome) {
        showEnhancedWelcomeMessage();
        context.globalState.update('aep.hasShownEnhancedWelcome', true);
    }
    console.log('✅ AEP Enhanced Extension Activated');
}
async function showEnhancedWelcomeMessage() {
    const action = await vscode.window.showInformationMessage('🎉 AEP Enhanced is now available! Experience next-level autonomous coding with enterprise intelligence.', 'Open Enhanced Chat', 'Learn More');
    switch (action) {
        case 'Open Enhanced Chat':
            vscode.commands.executeCommand('aep.openEnhancedChat');
            break;
        case 'Learn More':
            vscode.env.openExternal(vscode.Uri.parse('https://github.com/your-repo/aep-docs'));
            break;
    }
}
function deactivate() {
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
//# sourceMappingURL=enhanced-extension.js.map