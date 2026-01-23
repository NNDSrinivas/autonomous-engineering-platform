/**
 * Terminal Output Capture
 * 
 * Captures and analyzes terminal output during command execution.
 * Integrates with existing ActionRegistry and FailureAnalyzer.
 */

import * as vscode from 'vscode';
import * as cp from 'child_process';

export interface CommandResult {
    success: boolean;
    exitCode: number | null;
    stdout: string;
    stderr: string;
    duration: number;
    errors: string[];
}

export interface TerminalOutputEvent {
    type: 'stdout' | 'stderr' | 'exit' | 'error';
    content: string;
    timestamp: Date;
}

export type OutputCallback = (event: TerminalOutputEvent) => void;

/**
 * Executes commands and captures output for autonomous workflows
 */
export class TerminalOutputCapture {
    /**
     * Execute a command and capture all output
     */
    async executeCommand(
        command: string,
        options: {
            cwd?: string;
            timeout?: number;
            onOutput?: OutputCallback;
        } = {}
    ): Promise<CommandResult> {
        const { cwd, timeout = 60000, onOutput } = options;
        const startTime = Date.now();

        return new Promise((resolve) => {
            let stdout = '';
            let stderr = '';
            const errors: string[] = [];

            const process = cp.spawn(command, [], {
                shell: true,
                cwd: cwd || vscode.workspace.workspaceFolders?.[0]?.uri.fsPath,
            });

            const timeoutId = setTimeout(() => {
                process.kill();
                errors.push('Command timed out');
            }, timeout);

            process.stdout?.on('data', (data: Buffer) => {
                const text = data.toString();
                stdout += text;

                onOutput?.({
                    type: 'stdout',
                    content: text,
                    timestamp: new Date(),
                });

                // Detect errors in stdout
                const detectedErrors = this.detectErrors(text);
                errors.push(...detectedErrors);
            });

            process.stderr?.on('data', (data: Buffer) => {
                const text = data.toString();
                stderr += text;

                onOutput?.({
                    type: 'stderr',
                    content: text,
                    timestamp: new Date(),
                });

                errors.push(...this.detectErrors(text));
            });

            process.on('close', (code: number | null) => {
                clearTimeout(timeoutId);

                onOutput?.({
                    type: 'exit',
                    content: `Process exited with code ${code}`,
                    timestamp: new Date(),
                });

                resolve({
                    success: code === 0 && errors.length === 0,
                    exitCode: code,
                    stdout,
                    stderr,
                    duration: Date.now() - startTime,
                    errors,
                });
            });

            process.on('error', (err: Error) => {
                clearTimeout(timeoutId);
                errors.push(err.message);

                onOutput?.({
                    type: 'error',
                    content: err.message,
                    timestamp: new Date(),
                });

                resolve({
                    success: false,
                    exitCode: null,
                    stdout,
                    stderr,
                    duration: Date.now() - startTime,
                    errors,
                });
            });
        });
    }

    /**
     * Detect error patterns in output
     */
    private detectErrors(output: string): string[] {
        const errorPatterns = [
            /error:/i,
            /ERROR/,
            /failed/i,
            /FAILED/,
            /exception/i,
            /Cannot find module/,
            /Module not found/,
            /TS\d{4,5}:/,
            /npm ERR!/,
            /FAIL\s+/,
            /fatal:/,
            /CONFLICT/,
        ];

        const successPatterns = [
            /Successfully/i,
            /success/i,
            /✓|✔/,
            /PASS\s+/,
            /npm WARN/,
        ];

        const errors: string[] = [];
        const lines = output.split('\n');

        for (const line of lines) {
            // Check if line matches error pattern
            for (const pattern of errorPatterns) {
                if (pattern.test(line)) {
                    // Make sure it's not actually a success message
                    const isSuccess = successPatterns.some(sp => sp.test(line));
                    if (!isSuccess) {
                        errors.push(line.trim());
                        break;
                    }
                }
            }
        }

        return errors;
    }
}
