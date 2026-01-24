/**
 * Command Action Handler
 * Handles actions that involve executing shell commands or VS Code commands
 */

import * as vscode from 'vscode';
import { spawn } from 'child_process';
import { BaseActionHandler, ActionContext, ActionResult } from '../ActionRegistry';

export class CommandActionHandler extends BaseActionHandler {
    constructor() {
        super('command-execution', 90); // High priority
    }

    canHandle(action: any): boolean {
        // Can handle if action has command field
        return !!(action.command && typeof action.command === 'string');
    }

    async execute(action: any, context: ActionContext): Promise<ActionResult> {
        const command = action.command;
        const args = action.args || [];
        const cwd = action.cwd || context.workspaceRoot;

        // Determine if this is a VS Code command or shell command
        // VS Code commands typically start with vscode. or are registered commands
        const isVSCodeCommand = this.isVSCodeCommand(command, action);

        try {
            if (isVSCodeCommand) {
                return await this.executeVSCodeCommand(command, args, context);
            } else {
                return await this.executeShellCommand(command, cwd, context, action);
            }
        } catch (error: any) {
            return {
                success: false,
                error: error,
                message: `Command execution failed: ${error.message}`
            };
        }
    }

    private isVSCodeCommand(command: string, action: any): boolean {
        // Explicitly marked as VS Code command
        if (action.type === 'vscode_command' || action.commandType === 'vscode') {
            return true;
        }

        // Shell commands almost always contain whitespace (e.g., "git diff file.ts")
        if (/\s/.test(command)) {
            return false;
        }

        // Only treat known VS Code command namespaces as VS Code commands
        const vscodePrefixes = [
            'vscode.',
            'workbench.',
            'editor.',
            'terminal.',
            'debug.',
            'extensions.',
            'git.',
            'testing.',
            'views.',
        ];
        return vscodePrefixes.some((prefix) => command.startsWith(prefix));
    }

    private async executeVSCodeCommand(
        command: string,
        args: any[],
        context: ActionContext
    ): Promise<ActionResult> {
        console.log(`[CommandHandler] Executing VS Code command: ${command} with args:`, args);

        try {
            // Special handling for commands that require URI objects
            if (command === 'vscode.openFolder' && args.length > 0 && typeof args[0] === 'string') {
                const folderPath = args[0];
                const uri = vscode.Uri.file(folderPath);
                const result = await vscode.commands.executeCommand(command, uri);

                return {
                    success: true,
                    message: `Opened folder: ${folderPath}`,
                    data: result
                };
            }

            // vscode.open requires a URI object for file paths
            if (command === 'vscode.open' && args.length > 0 && typeof args[0] === 'string') {
                const filePath = args[0];
                const uri = vscode.Uri.file(filePath);
                const result = await vscode.commands.executeCommand(command, uri);

                return {
                    success: true,
                    message: `Opened file: ${filePath}`,
                    data: result
                };
            }

            // workbench.action.openRecent and similar also may need URI handling
            if ((command === 'workbench.action.openRecent' ||
                 command === 'vscode.openWith' ||
                 command === 'vscode.diff') &&
                args.length > 0 && typeof args[0] === 'string') {
                // Convert string paths to URIs
                const convertedArgs = args.map((arg, index) => {
                    if (typeof arg === 'string' && (arg.startsWith('/') || arg.match(/^[A-Za-z]:\\/))) {
                        return vscode.Uri.file(arg);
                    }
                    return arg;
                });
                const result = await vscode.commands.executeCommand(command, ...convertedArgs);

                return {
                    success: true,
                    message: `VS Code command executed: ${command}`,
                    data: result
                };
            }

            const result = await vscode.commands.executeCommand(command, ...args);

            return {
                success: true,
                message: `VS Code command executed: ${command}`,
                data: result
            };
        } catch (error: any) {
            throw new Error(`Failed to execute VS Code command '${command}': ${error.message}`);
        }
    }

    private async executeShellCommand(
        command: string,
        cwd: string | undefined,
        context: ActionContext,
        action: any
    ): Promise<ActionResult> {
        // Security: Sanitize and show command for confirmation
        const sanitizedCommand = command.replace(/[\r\n]/g, ' ').substring(0, 200);
        const displayCommand = command.length > 200 ? sanitizedCommand + '...' : sanitizedCommand;

        // Skip confirmation if approved via chat
        if (!context.approvedViaChat) {
            const confirmed = await vscode.window.showWarningMessage(
                `Execute command:\n\n${displayCommand}\n\nAre you sure?`,
                { modal: true },
                'Run Command'
            );

            if (confirmed !== 'Run Command') {
                return {
                    success: false,
                    message: 'Command execution cancelled by user'
                };
            }
        }

        const workspaceRoot = cwd || context.workspaceRoot || process.cwd();
        const commandId = `cmd-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

        // Notify UI that command started
        if (context.postMessage) {
            context.postMessage({
                type: 'command.start',
                commandId,
                command,
                cwd: workspaceRoot,
                meta: action.meta,
            });
        }

        return new Promise((resolve) => {
            const started = Date.now();
            let stdout = '';
            let stderr = '';

            const child = spawn(command, {
                cwd: workspaceRoot,
                shell: true,
                env: process.env,
            });

            child.stdout?.on('data', (data: Buffer) => {
                const text = data.toString();
                stdout += text;

                if (context.postMessage) {
                    context.postMessage({
                        type: 'command.output',
                        commandId,
                        stream: 'stdout',
                        text,
                    });
                }
            });

            child.stderr?.on('data', (data: Buffer) => {
                const text = data.toString();
                stderr += text;

                if (context.postMessage) {
                    context.postMessage({
                        type: 'command.output',
                        commandId,
                        stream: 'stderr',
                        text,
                    });
                }
            });

            child.on('close', (exitCode) => {
                const durationMs = Date.now() - started;

                if (context.postMessage) {
                    context.postMessage({
                        type: 'command.done',
                        commandId,
                        exitCode,
                        durationMs,
                        stdout,
                        stderr,
                    });
                }

                const exitError = exitCode === 0
                    ? undefined
                    : new Error(`Command failed with exit code ${exitCode}: ${command}`);

                resolve({
                    success: exitCode === 0,
                    message: exitCode === 0
                        ? `Command executed successfully: ${command}`
                        : `Command failed with exit code ${exitCode}: ${command}`,
                    error: exitError,
                    data: {
                        command,
                        cwd: workspaceRoot,
                        exitCode,
                        stdout,
                        stderr,
                        durationMs,
                    }
                });
            });

            child.on('error', (error) => {
                if (context.postMessage) {
                    context.postMessage({
                        type: 'command.error',
                        commandId,
                        error: error.message,
                    });
                }

                resolve({
                    success: false,
                    error: error,
                    message: `Command execution error: ${error.message}`
                });
            });
        });
    }
}
