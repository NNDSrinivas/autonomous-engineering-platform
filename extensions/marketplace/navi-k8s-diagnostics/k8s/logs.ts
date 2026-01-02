/**
 * Kubernetes Logs Inspector Module
 * 
 * Retrieves and analyzes container logs for error patterns and diagnostic information.
 * Implements safe log collection with size limits and pattern matching.
 */

import { ExtensionContext, LogOptions } from '../types';

export async function getPodLogs(
    ctx: ExtensionContext,
    podName: string,
    namespace: string,
    options: LogOptions = {}
): Promise<{
    logs: string;
    truncated: boolean;
    containerLogs: Record<string, string>;
}> {
    try {
        const tailLines = Math.min(options.tailLines || 100, 1000); // Safety limit
        const containerLogs: Record<string, string> = {};

        let allLogs = '';
        let truncated = false;

        if (options.container) {
            // Get logs for specific container
            const logs = await getContainerLogs(podName, namespace, options.container, tailLines);
            containerLogs[options.container] = logs;
            allLogs = logs;
        } else {
            // Get logs for all containers in pod
            const containers = await getPodContainers(podName, namespace);

            for (const containerName of containers) {
                try {
                    const logs = await getContainerLogs(podName, namespace, containerName, tailLines);
                    containerLogs[containerName] = logs;
                    allLogs += `\\n\\n=== Container: ${containerName} ===\\n${logs}`;

                    // Check if we're getting too much data
                    if (allLogs.length > 50000) { // 50KB limit
                        truncated = true;
                        break;
                    }
                } catch (error) {
                    console.error(`Failed to get logs for container ${containerName}:`, error);
                    containerLogs[containerName] = `Error retrieving logs: ${error}`;
                }
            }
        }

        return {
            logs: allLogs,
            truncated,
            containerLogs
        };

    } catch (error) {
        console.error(`Failed to get pod logs for ${podName}:`, error);
        return {
            logs: `Error retrieving logs: ${error}`,
            truncated: false,
            containerLogs: {}
        };
    }
}

export function analyzeLogPatterns(logs: string): {
    errorCount: number;
    warningCount: number;
    commonErrors: Array<{ pattern: string; count: number }>;
    severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
    summary: string;
} {
    const lines = logs.split('\\n');
    let errorCount = 0;
    let warningCount = 0;
    const errorPatterns: Record<string, number> = {};

    // Common error patterns to look for
    const patterns = {
        error: [
            /error/gi,
            /exception/gi,
            /failed/gi,
            /fatal/gi,
            /panic/gi,
            /crash/gi
        ],
        warning: [
            /warn/gi,
            /warning/gi,
            /deprecated/gi,
            /retry/gi
        ],
        critical: [
            /segmentation fault/gi,
            /out of memory/gi,
            /killed/gi,
            /signal/gi,
            /core dump/gi
        ],
        network: [
            /connection refused/gi,
            /timeout/gi,
            /unreachable/gi,
            /dns/gi
        ],
        database: [
            /connection pool/gi,
            /deadlock/gi,
            /constraint/gi,
            /transaction/gi
        ],
        auth: [
            /unauthorized/gi,
            /forbidden/gi,
            /authentication/gi,
            /token/gi
        ]
    };

    for (const line of lines) {
        // Count errors and warnings
        for (const errorPattern of patterns.error) {
            if (errorPattern.test(line)) {
                errorCount++;
                break;
            }
        }

        for (const warningPattern of patterns.warning) {
            if (warningPattern.test(line)) {
                warningCount++;
                break;
            }
        }

        // Extract specific error messages
        const errorMatch = line.match(/error:?\s*(.+?)$/i);
        if (errorMatch && errorMatch[1]) {
            const errorMsg = errorMatch[1].slice(0, 100); // Truncate long messages
            errorPatterns[errorMsg] = (errorPatterns[errorMsg] || 0) + 1;
        }

        const exceptionMatch = line.match(/exception:?\s*(.+?)$/i);
        if (exceptionMatch && exceptionMatch[1]) {
            const exceptionMsg = exceptionMatch[1].slice(0, 100);
            errorPatterns[exceptionMsg] = (errorPatterns[exceptionMsg] || 0) + 1;
        }
    }

    // Determine severity
    let severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' = 'LOW';

    if (errorCount > 50 || patterns.critical.some(p => p.test(logs))) {
        severity = 'CRITICAL';
    } else if (errorCount > 10) {
        severity = 'HIGH';
    } else if (errorCount > 0 || warningCount > 20) {
        severity = 'MEDIUM';
    }

    // Get most common errors
    const commonErrors = Object.entries(errorPatterns)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 5)
        .map(([pattern, count]) => ({ pattern, count }));

    // Generate summary
    const totalLines = lines.length;
    const errorRate = totalLines > 0 ? Math.round((errorCount / totalLines) * 100) : 0;

    const summary = `${totalLines} log lines analyzed. ` +
        `${errorCount} errors (${errorRate}%), ${warningCount} warnings. ` +
        `Severity: ${severity}`;

    return {
        errorCount,
        warningCount,
        commonErrors,
        severity,
        summary
    };
}

export function extractStackTraces(logs: string): Array<{
    error: string;
    stackTrace: string[];
    language: 'java' | 'python' | 'nodejs' | 'go' | 'unknown';
}> {
    const stackTraces = [];
    const lines = logs.split('\\n');

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (!line) continue;

        // Java stack traces
        if (line.includes('Exception') && line.includes(' at ')) {
            const stackTrace = [];
            const error = line.trim();

            // Collect stack trace lines
            for (let j = i + 1; j < lines.length && j < i + 20; j++) {
                const traceLine = lines[j];
                if (!traceLine) continue;

                if (traceLine.trim().startsWith('at ')) {
                    stackTrace.push(traceLine.trim());
                } else if (traceLine.trim().startsWith('Caused by:')) {
                    stackTrace.push(traceLine.trim());
                } else if (stackTrace.length > 0) {
                    break;
                }
            }

            if (stackTrace.length > 0) {
                stackTraces.push({
                    error,
                    stackTrace,
                    language: 'java' as const
                });
            }
        }

        // Python stack traces
        else if (line.includes('Traceback (most recent call last):')) {
            const stackTrace = [];
            const errorLine = findPythonError(lines, i);

            for (let j = i + 1; j < lines.length && j < i + 20; j++) {
                const traceLine = lines[j];
                if (!traceLine) continue;

                const trimmedLine = traceLine.trim();
                if (trimmedLine.startsWith('File ') || trimmedLine.includes('line ')) {
                    stackTrace.push(trimmedLine);
                } else if (stackTrace.length > 0 && !trimmedLine) {
                    break;
                }
            }

            if (stackTrace.length > 0) {
                stackTraces.push({
                    error: errorLine,
                    stackTrace,
                    language: 'python' as const
                });
            }
        }

        // Node.js stack traces  
        else if (line.includes('Error:') && lines[i + 1]?.trim().startsWith('at ')) {
            const stackTrace = [];
            const error = line.trim();

            for (let j = i + 1; j < lines.length && j < i + 15; j++) {
                const traceLine = lines[j];
                if (!traceLine) continue;

                if (traceLine.trim().startsWith('at ')) {
                    stackTrace.push(traceLine.trim());
                } else if (stackTrace.length > 0) {
                    break;
                }
            }

            if (stackTrace.length > 0) {
                stackTraces.push({
                    error,
                    stackTrace,
                    language: 'nodejs' as const
                });
            }
        }
    }

    return stackTraces;
}

function findPythonError(lines: string[], startIndex: number): string {
    // Look for the actual error line in Python traceback
    for (let i = startIndex; i < Math.min(startIndex + 20, lines.length); i++) {
        const line = lines[i];
        if (!line) continue;

        const trimmedLine = line.trim();
        if (trimmedLine && !trimmedLine.startsWith('File ') && !trimmedLine.includes('Traceback') &&
            (trimmedLine.includes('Error:') || trimmedLine.includes('Exception:'))) {
            return trimmedLine;
        }
    }
    return 'Python exception (error details not found)';
}

async function getContainerLogs(
    podName: string,
    namespace: string,
    containerName: string,
    tailLines: number
): Promise<string> {
    const args = [
        'logs', podName,
        '-n', namespace,
        '-c', containerName,
        '--tail', tailLines.toString()
    ];

    return await executeKubectl(args);
}

async function getPodContainers(podName: string, namespace: string): Promise<string[]> {
    try {
        const args = [
            'get', 'pod', podName,
            '-n', namespace,
            '-o', 'jsonpath={.spec.containers[*].name}'
        ];

        const output = await executeKubectl(args);
        return output.trim().split(/\\s+/).filter(name => name);
    } catch (error) {
        console.error(`Failed to get containers for pod ${podName}:`, error);
        return ['app']; // Default container name
    }
}

// Security: Execute kubectl with validation
async function executeKubectl(args: string[]): Promise<string> {
    const allowedCommands = ['logs', 'get'];

    if (!args.length || !args[0] || !allowedCommands.includes(args[0])) {
        throw new Error(`kubectl command not allowed: ${args[0]}`);
    }

    const unsafeChars = /[;&|`$(){}[\]]/;
    for (const arg of args) {
        if (unsafeChars.test(arg)) {
            throw new Error(`Unsafe kubectl argument: ${arg}`);
        }
    }

    try {
        const result = await executeSecureCommand('kubectl', args, {
            timeout: 30000,
            workingDirectory: process.cwd()
        });

        return result.stdout;
    } catch (error: any) {
        throw new Error(`kubectl execution failed: ${error.message}`);
    }
}

// Mock implementation
async function executeSecureCommand(
    command: string,
    args: string[],
    options: { timeout: number; workingDirectory: string }
): Promise<{ stdout: string; stderr: string; exitCode: number }> {
    console.log(`Would execute: ${command} ${args.join(' ')}`);

    // Mock log response with realistic application errors
    if (args[0] === 'logs') {
        return {
            stdout: `2024-12-25T17:30:00Z INFO Starting payments service v1.2.3
2024-12-25T17:30:01Z INFO Connecting to database at postgres://***@db:5432/payments
2024-12-25T17:30:02Z ERROR Failed to connect to database: connection refused
2024-12-25T17:30:02Z ERROR Database connection pool exhausted
2024-12-25T17:30:03Z WARN Retrying database connection (attempt 1/5)
2024-12-25T17:30:05Z ERROR Connection timeout after 2s
2024-12-25T17:30:05Z WARN Retrying database connection (attempt 2/5)
2024-12-25T17:30:08Z ERROR Connection timeout after 3s
2024-12-25T17:30:08Z FATAL Unable to establish database connection after 5 attempts
2024-12-25T17:30:08Z ERROR panic: runtime error: invalid memory address or nil pointer dereference
2024-12-25T17:30:08Z ERROR [signal SIGSEGV: segmentation violation code=0x1 addr=0x0 pc=0x123456]
2024-12-25T17:30:08Z INFO Shutting down gracefully...`,
            stderr: '',
            exitCode: 0
        };
    }

    // Mock container names
    if (args[0] === 'get' && args[1] === 'pod' && args.includes('-o') && args.includes('jsonpath')) {
        return {
            stdout: 'payments sidecar-proxy',
            stderr: '',
            exitCode: 0
        };
    }

    return {
        stdout: 'Mock response',
        stderr: '',
        exitCode: 0
    };
}