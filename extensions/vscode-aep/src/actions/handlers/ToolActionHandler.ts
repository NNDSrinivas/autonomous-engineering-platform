/**
 * Tool Installation Action Handler
 * Handles actions related to installing missing development tools
 */

import * as vscode from 'vscode';
import { exec } from 'child_process';
import { promisify } from 'util';
import { BaseActionHandler, ActionContext, ActionResult } from '../ActionRegistry';

const execAsync = promisify(exec);

export class ToolActionHandler extends BaseActionHandler {
    constructor() {
        super('tool-installation', 85); // High priority for tool installations
    }

    canHandle(action: any): boolean {
        const type = action.type?.toLowerCase();
        return type === 'installtool' || type === 'checktool' || type === 'install_tool';
    }

    async execute(action: any, context: ActionContext): Promise<ActionResult> {
        const type = action.type?.toLowerCase();
        const tool = action.tool;
        const command = action.command;

        if (!tool && !command) {
            return {
                success: false,
                error: new Error('No tool or command specified'),
                message: 'Tool installation requires a tool name or command'
            };
        }

        try {
            switch (type) {
                case 'checktool':
                    return await this.checkTool(tool, context);
                case 'installtool':
                case 'install_tool':
                    return await this.installTool(tool, command, action.alternatives, context);
                default:
                    return {
                        success: false,
                        error: new Error(`Unknown tool action type: ${type}`)
                    };
            }
        } catch (error: any) {
            return {
                success: false,
                error: error,
                message: `Tool operation failed: ${error.message}`
            };
        }
    }

    private async checkTool(tool: string, context: ActionContext): Promise<ActionResult> {
        const isInstalled = await this.isToolInstalled(tool);

        if (context.postMessage) {
            context.postMessage({
                type: 'tool.status',
                tool,
                installed: isInstalled
            });
        }

        return {
            success: true,
            message: isInstalled
                ? `${tool} is installed`
                : `${tool} is not installed`,
            data: { tool, installed: isInstalled }
        };
    }

    private async installTool(
        tool: string,
        command: string,
        alternatives: string[] = [],
        context: ActionContext
    ): Promise<ActionResult> {
        // First check if already installed
        if (await this.isToolInstalled(tool)) {
            return {
                success: true,
                message: `${tool} is already installed`
            };
        }

        // Confirm with user before installing
        const installOptions = [command, ...alternatives].filter(Boolean);
        const optionLabels = installOptions.map((cmd, i) =>
            i === 0 ? `Install with: ${cmd}` : `Alternative: ${cmd}`
        );

        const choice = await vscode.window.showQuickPick(
            [...optionLabels, 'Cancel'],
            {
                placeHolder: `Install ${tool}?`,
                title: `NAVI: Install Missing Tool - ${tool}`
            }
        );

        if (!choice || choice === 'Cancel') {
            return {
                success: false,
                message: 'Installation cancelled by user'
            };
        }

        const selectedIndex = optionLabels.indexOf(choice);
        const selectedCommand = installOptions[selectedIndex];

        // Notify UI that installation started
        if (context.postMessage) {
            context.postMessage({
                type: 'tool.installing',
                tool,
                command: selectedCommand
            });
        }

        // Show progress notification
        return await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: `Installing ${tool}...`,
                cancellable: false
            },
            async (progress) => {
                try {
                    progress.report({ message: 'Running installation command...' });

                    // Determine if we need a terminal for interactive installations
                    const needsTerminal = this.needsInteractiveTerminal(selectedCommand);

                    if (needsTerminal) {
                        // Use integrated terminal for interactive installations
                        const terminal = vscode.window.createTerminal({
                            name: `Install ${tool}`,
                            cwd: context.workspaceRoot
                        });
                        terminal.show();
                        terminal.sendText(selectedCommand);

                        // Wait a bit and check if installed
                        await new Promise(resolve => setTimeout(resolve, 5000));

                        if (context.postMessage) {
                            context.postMessage({
                                type: 'tool.install_started',
                                tool,
                                terminal: true,
                                message: 'Installation started in terminal. Please follow any prompts.'
                            });
                        }

                        return {
                            success: true,
                            message: `Installation of ${tool} started in terminal. Please follow any prompts and restart your terminal when done.`,
                            data: { tool, terminal: true }
                        };
                    }

                    // Non-interactive installation
                    const { stdout, stderr } = await execAsync(selectedCommand, {
                        timeout: 300000, // 5 minute timeout
                        cwd: context.workspaceRoot
                    });

                    progress.report({ message: 'Verifying installation...' });

                    // Verify installation
                    const isInstalled = await this.isToolInstalled(tool);

                    if (context.postMessage) {
                        context.postMessage({
                            type: 'tool.installed',
                            tool,
                            success: isInstalled,
                            output: stdout + stderr
                        });
                    }

                    if (isInstalled) {
                        vscode.window.showInformationMessage(`Successfully installed ${tool}`);
                        return {
                            success: true,
                            message: `Successfully installed ${tool}`,
                            data: { tool, output: stdout }
                        };
                    } else {
                        return {
                            success: false,
                            message: `Installation completed but ${tool} not found in PATH. You may need to restart your terminal.`,
                            data: { tool, output: stdout + stderr }
                        };
                    }
                } catch (error: any) {
                    if (context.postMessage) {
                        context.postMessage({
                            type: 'tool.install_failed',
                            tool,
                            error: error.message
                        });
                    }

                    // Offer alternatives if main installation failed
                    if (alternatives.length > 0) {
                        const tryAlternative = await vscode.window.showErrorMessage(
                            `Failed to install ${tool}: ${error.message}`,
                            'Try Alternative Method',
                            'Cancel'
                        );

                        if (tryAlternative === 'Try Alternative Method') {
                            return await this.installTool(tool, alternatives[0], alternatives.slice(1), context);
                        }
                    }

                    return {
                        success: false,
                        error: error,
                        message: `Failed to install ${tool}: ${error.message}`
                    };
                }
            }
        );
    }

    private async isToolInstalled(tool: string): Promise<boolean> {
        try {
            const platform = process.platform;
            const command = platform === 'win32' ? `where ${tool}` : `which ${tool}`;
            await execAsync(command);
            return true;
        } catch {
            return false;
        }
    }

    private needsInteractiveTerminal(command: string): boolean {
        // Commands that typically need user interaction
        const interactivePatterns = [
            'rustup',
            'sh -c',
            '| sh',
            '| bash',
            'curl.*install',
            'xcode-select',
            'sudo'
        ];

        return interactivePatterns.some(pattern =>
            new RegExp(pattern, 'i').test(command)
        );
    }
}
