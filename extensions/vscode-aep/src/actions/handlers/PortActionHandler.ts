/**
 * Port Action Handler
 * Handles actions related to port management: checking ports, killing processes on ports
 *
 * All port values are configurable via VS Code settings or environment variables.
 * NO HARDCODED PORT VALUES - uses NaviPortConfig for all defaults.
 */

import * as vscode from 'vscode';
import { exec } from 'child_process';
import { promisify } from 'util';
import { BaseActionHandler, ActionContext, ActionResult } from '../ActionRegistry';

const execAsync = promisify(exec);

/**
 * Centralized port configuration - NO HARDCODING.
 * Values can be overridden via VS Code settings or environment variables.
 */
class NaviPortConfig {
    // Get port configuration from VS Code settings or environment
    static get PORT_RANGE_START(): number {
        const config = vscode.workspace.getConfiguration('navi');
        return config.get<number>('portRangeStart') ||
               parseInt(process.env.NAVI_PORT_RANGE_START || '3000', 10);
    }

    static get PORT_RANGE_END(): number {
        const config = vscode.workspace.getConfiguration('navi');
        return config.get<number>('portRangeEnd') ||
               parseInt(process.env.NAVI_PORT_RANGE_END || '3100', 10);
    }

    static get COMMON_DEV_PORTS(): number[] {
        const config = vscode.workspace.getConfiguration('navi');
        const configPorts = config.get<number[]>('commonDevPorts');
        if (configPorts && configPorts.length > 0) {
            return configPorts;
        }

        const envPorts = process.env.NAVI_COMMON_PORTS;
        if (envPorts) {
            return envPorts.split(',').map(p => parseInt(p.trim(), 10)).filter(p => !isNaN(p));
        }

        // Default common development ports
        return [3000, 3001, 3002, 3003, 3004, 3005, 4000, 5000, 5173, 5174, 8000, 8080, 8081];
    }
}

interface PortStatus {
    port: number;
    isAvailable: boolean;
    processName?: string;
    processPid?: number;
    processCommand?: string;
}

export class PortActionHandler extends BaseActionHandler {
    constructor() {
        super('port-management', 95); // High priority - port operations need to happen before commands
    }

    canHandle(action: any): boolean {
        const type = action.type?.toLowerCase();
        return type === 'checkport' || type === 'killport' || type === 'findport';
    }

    async execute(action: any, context: ActionContext): Promise<ActionResult> {
        const type = action.type?.toLowerCase();
        const port = parseInt(action.port, 10);

        if (isNaN(port)) {
            return {
                success: false,
                error: new Error('Invalid port number'),
                message: 'Port must be a valid number'
            };
        }

        try {
            switch (type) {
                case 'checkport':
                    return await this.checkPort(port, context);
                case 'killport':
                    return await this.killPort(port, context);
                case 'findport':
                    return await this.findAvailablePort(port, context);
                default:
                    return {
                        success: false,
                        error: new Error(`Unknown port action type: ${type}`)
                    };
            }
        } catch (error: any) {
            return {
                success: false,
                error: error,
                message: `Port operation failed: ${error.message}`
            };
        }
    }

    private async checkPort(port: number, context: ActionContext): Promise<ActionResult> {
        const status = await this.getPortStatus(port);

        // Notify UI about port status
        if (context.postMessage) {
            context.postMessage({
                type: 'port.status',
                port,
                status: status.isAvailable ? 'available' : 'in_use',
                processInfo: status.isAvailable ? null : {
                    name: status.processName,
                    pid: status.processPid,
                    command: status.processCommand
                }
            });
        }

        return {
            success: true,
            message: status.isAvailable
                ? `Port ${port} is available`
                : `Port ${port} is in use by ${status.processName || 'unknown process'} (PID: ${status.processPid || 'unknown'})`,
            data: status
        };
    }

    private async killPort(port: number, context: ActionContext): Promise<ActionResult> {
        const status = await this.getPortStatus(port);

        if (status.isAvailable) {
            return {
                success: true,
                message: `Port ${port} is already free`
            };
        }

        if (!status.processPid) {
            return {
                success: false,
                error: new Error(`Could not find process ID for port ${port}`),
                message: `Cannot kill process on port ${port}: unable to identify the process`
            };
        }

        // Confirm with user before killing
        const processDesc = status.processName
            ? `${status.processName} (PID: ${status.processPid})`
            : `PID ${status.processPid}`;

        const confirmed = await vscode.window.showWarningMessage(
            `Stop the process on port ${port}?\n\nProcess: ${processDesc}\n${status.processCommand ? `Command: ${status.processCommand}` : ''}`,
            { modal: true },
            'Stop Process',
            'Cancel'
        );

        if (confirmed !== 'Stop Process') {
            return {
                success: false,
                message: 'User cancelled the operation'
            };
        }

        // Kill the process
        try {
            const platform = process.platform;
            if (platform === 'win32') {
                await execAsync(`taskkill /F /PID ${status.processPid}`);
            } else {
                // Try graceful termination first, then force kill
                try {
                    await execAsync(`kill ${status.processPid}`);
                    // Wait a bit for graceful shutdown
                    await new Promise(resolve => setTimeout(resolve, 500));
                    // Check if still running
                    const stillRunning = await this.isProcessRunning(status.processPid);
                    if (stillRunning) {
                        await execAsync(`kill -9 ${status.processPid}`);
                    }
                } catch {
                    // If graceful kill fails, force kill
                    await execAsync(`kill -9 ${status.processPid}`);
                }
            }

            // Verify port is now free
            await new Promise(resolve => setTimeout(resolve, 500));
            const newStatus = await this.getPortStatus(port);

            if (context.postMessage) {
                context.postMessage({
                    type: 'port.killed',
                    port,
                    success: newStatus.isAvailable,
                    previousProcess: {
                        name: status.processName,
                        pid: status.processPid
                    }
                });
            }

            if (newStatus.isAvailable) {
                return {
                    success: true,
                    message: `Successfully stopped process on port ${port}`
                };
            } else {
                return {
                    success: false,
                    message: `Process was signaled but port ${port} is still in use`
                };
            }
        } catch (error: any) {
            return {
                success: false,
                error: error,
                message: `Failed to stop process on port ${port}: ${error.message}`
            };
        }
    }

    private async findAvailablePort(preferredPort: number, context: ActionContext): Promise<ActionResult> {
        // Use NaviPortConfig instead of hardcoded values
        const commonPorts = NaviPortConfig.COMMON_DEV_PORTS;
        const portRangeStart = NaviPortConfig.PORT_RANGE_START;
        const portRangeEnd = NaviPortConfig.PORT_RANGE_END;

        // Try preferred port first
        let status = await this.getPortStatus(preferredPort);
        if (status.isAvailable) {
            return {
                success: true,
                message: `Port ${preferredPort} is available`,
                data: { port: preferredPort }
            };
        }

        // Try common ports from config
        for (const port of commonPorts) {
            if (port !== preferredPort) {
                status = await this.getPortStatus(port);
                if (status.isAvailable) {
                    if (context.postMessage) {
                        context.postMessage({
                            type: 'port.found',
                            preferredPort,
                            availablePort: port
                        });
                    }
                    return {
                        success: true,
                        message: `Found available port: ${port}`,
                        data: { port, wasPreferred: false, preferredPort }
                    };
                }
            }
        }

        // Try port range from config
        for (let port = portRangeStart; port < portRangeEnd; port++) {
            status = await this.getPortStatus(port);
            if (status.isAvailable) {
                return {
                    success: true,
                    message: `Found available port: ${port}`,
                    data: { port, wasPreferred: false, preferredPort }
                };
            }
        }

        return {
            success: false,
            error: new Error('No available ports found'),
            message: `Could not find any available port in the range ${portRangeStart}-${portRangeEnd}`
        };
    }

    private async getPortStatus(port: number): Promise<PortStatus> {
        const platform = process.platform;

        try {
            if (platform === 'darwin' || platform === 'linux') {
                // Use lsof to find process on port
                try {
                    const { stdout } = await execAsync(`lsof -i :${port} -t 2>/dev/null`);
                    const pid = parseInt(stdout.trim().split('\n')[0], 10);

                    if (!isNaN(pid)) {
                        // Get process info
                        try {
                            const { stdout: psOutput } = await execAsync(`ps -p ${pid} -o comm=,args= 2>/dev/null`);
                            const parts = psOutput.trim().split(/\s+/);
                            const name = parts[0] || 'unknown';
                            const command = parts.slice(1).join(' ') || name;

                            return {
                                port,
                                isAvailable: false,
                                processName: name,
                                processPid: pid,
                                processCommand: command.substring(0, 100)
                            };
                        } catch {
                            return {
                                port,
                                isAvailable: false,
                                processPid: pid,
                                processName: 'unknown'
                            };
                        }
                    }
                } catch {
                    // lsof failed or returned empty - port is likely available
                }

                return { port, isAvailable: true };

            } else if (platform === 'win32') {
                // Use netstat on Windows
                try {
                    const { stdout } = await execAsync(`netstat -ano | findstr :${port}`);
                    const lines = stdout.trim().split('\n');
                    for (const line of lines) {
                        if (line.includes('LISTENING')) {
                            const parts = line.trim().split(/\s+/);
                            const pid = parseInt(parts[parts.length - 1], 10);
                            if (!isNaN(pid)) {
                                return {
                                    port,
                                    isAvailable: false,
                                    processPid: pid,
                                    processName: 'unknown'
                                };
                            }
                        }
                    }
                } catch {
                    // netstat failed - port is likely available
                }

                return { port, isAvailable: true };
            }
        } catch {
            // If all checks fail, assume port is available
        }

        return { port, isAvailable: true };
    }

    private async isProcessRunning(pid: number): Promise<boolean> {
        try {
            if (process.platform === 'win32') {
                await execAsync(`tasklist /FI "PID eq ${pid}" | findstr ${pid}`);
                return true;
            } else {
                await execAsync(`kill -0 ${pid}`);
                return true;
            }
        } catch {
            return false;
        }
    }
}
