/**
 * Kubernetes Events Inspector Module
 * 
 * Retrieves and analyzes Kubernetes events to understand cluster activity,
 * warnings, and error conditions across resources.
 */

import { Event, ExtensionContext } from '../types';

export async function getClusterEvents(
    ctx: ExtensionContext,
    namespace?: string,
    lastMinutes: number = 30
): Promise<Event[]> {
    try {
        const args = ['get', 'events', '--sort-by', '.firstTimestamp'];

        if (namespace) {
            args.push('-n', namespace);
        } else {
            args.push('--all-namespaces');
        }

        // Filter events from last N minutes
        const sinceTime = new Date(Date.now() - (lastMinutes * 60 * 1000)).toISOString();
        args.push('--field-selector', `firstTimestamp>${sinceTime}`);
        args.push('-o', 'json');

        const output = await executeKubectl(args);
        const eventList = JSON.parse(output);

        return eventList.items.map((event: any) => transformEvent(event));
    } catch (error) {
        console.error('Failed to get cluster events:', error);
        return [];
    }
}

export async function getResourceEvents(
    ctx: ExtensionContext,
    resourceKind: string,
    resourceName: string,
    namespace: string
): Promise<Event[]> {
    try {
        const args = [
            'get', 'events',
            '-n', namespace,
            '--field-selector', `involvedObject.kind=${resourceKind},involvedObject.name=${resourceName}`,
            '--sort-by', '.firstTimestamp',
            '-o', 'json'
        ];

        const output = await executeKubectl(args);
        const eventList = JSON.parse(output);

        return eventList.items.map((event: any) => transformEvent(event));
    } catch (error) {
        console.error(`Failed to get events for ${resourceKind}/${resourceName}:`, error);
        return [];
    }
}

export function filterCriticalEvents(events: Event[]): Event[] {
    return events.filter(event => {
        // Warning events
        if (event.type === 'Warning') {
            return true;
        }

        // High-frequency events (may indicate problems)
        if (event.count > 10) {
            return true;
        }

        // Common critical event reasons
        const criticalReasons = [
            'Failed',
            'FailedCreate',
            'FailedMount',
            'FailedScheduling',
            'FailedSync',
            'Unhealthy',
            'BackOff',
            'FailedPostStartHook',
            'FailedPreStopHook',
            'NetworkNotReady',
            'NodeNotReady'
        ];

        return criticalReasons.some(reason => event.reason.includes(reason));
    });
}

export function categorizeEvents(events: Event[]): {
    scheduling: Event[];
    networking: Event[];
    storage: Event[];
    security: Event[];
    application: Event[];
    infrastructure: Event[];
    other: Event[];
} {
    const categories = {
        scheduling: [] as Event[],
        networking: [] as Event[],
        storage: [] as Event[],
        security: [] as Event[],
        application: [] as Event[],
        infrastructure: [] as Event[],
        other: [] as Event[]
    };

    for (const event of events) {
        const reason = event.reason.toLowerCase();
        const message = event.message.toLowerCase();

        if (reason.includes('schedul') || reason.includes('preempt') || message.includes('schedule')) {
            categories.scheduling.push(event);
        } else if (reason.includes('network') || reason.includes('dns') || message.includes('network')) {
            categories.networking.push(event);
        } else if (reason.includes('mount') || reason.includes('volume') || message.includes('storage')) {
            categories.storage.push(event);
        } else if (reason.includes('forbid') || reason.includes('unauthoriz') || message.includes('rbac')) {
            categories.security.push(event);
        } else if (reason.includes('back') || reason.includes('crash') || reason.includes('restart')) {
            categories.application.push(event);
        } else if (reason.includes('node') || reason.includes('kubelet') || message.includes('node')) {
            categories.infrastructure.push(event);
        } else {
            categories.other.push(event);
        }
    }

    return categories;
}

export function analyzeEventPatterns(events: Event[]): {
    trends: Array<{ pattern: string; count: number; severity: 'HIGH' | 'MEDIUM' | 'LOW' }>;
    summary: string;
} {
    const reasonCounts: Record<string, number> = {};
    const messageCounts: Record<string, number> = {};

    // Count event reasons and common message patterns
    for (const event of events) {
        reasonCounts[event.reason] = (reasonCounts[event.reason] || 0) + 1;

        // Extract common patterns from messages
        const patterns = extractMessagePatterns(event.message);
        for (const pattern of patterns) {
            messageCounts[pattern] = (messageCounts[pattern] || 0) + 1;
        }
    }

    // Identify trends
    const trends = [];

    // High-frequency reason patterns
    for (const [reason, count] of Object.entries(reasonCounts)) {
        if (count >= 5) {
            let severity: 'HIGH' | 'MEDIUM' | 'LOW' = 'LOW';

            if (reason.includes('Failed') || reason.includes('Error')) {
                severity = 'HIGH';
            } else if (count >= 10) {
                severity = 'MEDIUM';
            }

            trends.push({
                pattern: `Repeated ${reason} events`,
                count,
                severity
            });
        }
    }

    // High-frequency message patterns
    for (const [pattern, count] of Object.entries(messageCounts)) {
        if (count >= 3) {
            trends.push({
                pattern: `Pattern: ${pattern}`,
                count,
                severity: 'MEDIUM' as 'HIGH' | 'MEDIUM' | 'LOW'
            });
        }
    }

    // Generate summary
    const warningCount = events.filter(e => e.type === 'Warning').length;
    const totalEvents = events.length;
    const topReasons = Object.entries(reasonCounts)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 3)
        .map(([reason, count]) => `${reason} (${count})`);

    const summary = `${totalEvents} events analyzed, ${warningCount} warnings. ` +
        `Top reasons: ${topReasons.join(', ')}.`;

    return { trends, summary };
}

function extractMessagePatterns(message: string): string[] {
    const patterns = [];

    // Extract common error patterns
    const errorPatterns = [
        /failed to (\w+)/gi,
        /unable to (\w+)/gi,
        /error (\w+)/gi,
        /timeout (\w+)/gi,
        /connection refused/gi,
        /no such file/gi,
        /permission denied/gi
    ];

    for (const pattern of errorPatterns) {
        const matches = message.match(pattern);
        if (matches) {
            patterns.push(...matches);
        }
    }

    return patterns;
}

function transformEvent(k8sEvent: any): Event {
    return {
        metadata: {
            name: k8sEvent.metadata.name,
            namespace: k8sEvent.metadata.namespace
        },
        involvedObject: {
            kind: k8sEvent.involvedObject.kind,
            name: k8sEvent.involvedObject.name,
            namespace: k8sEvent.involvedObject.namespace
        },
        reason: k8sEvent.reason,
        message: k8sEvent.message,
        type: k8sEvent.type,
        firstTimestamp: k8sEvent.firstTimestamp,
        lastTimestamp: k8sEvent.lastTimestamp,
        count: k8sEvent.count || 1
    };
}

// Security: Execute kubectl with validation
async function executeKubectl(args: string[]): Promise<string> {
    const allowedCommands = ['get'];

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

    // Mock events response
    if (args[0] === 'get' && args[1] === 'events') {
        return {
            stdout: JSON.stringify({
                items: [
                    {
                        metadata: {
                            name: 'payments-deployment-6c8f7b9d4.17abc123',
                            namespace: 'default'
                        },
                        involvedObject: {
                            kind: 'Pod',
                            name: 'payments-deployment-6c8f7b9d4-abc123',
                            namespace: 'default'
                        },
                        reason: 'BackOff',
                        message: 'Back-off restarting failed container payments in pod payments-deployment-6c8f7b9d4-abc123_default(12345678-1234-1234-1234-123456789abc)',
                        type: 'Warning',
                        firstTimestamp: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
                        lastTimestamp: new Date(Date.now() - 1 * 60 * 1000).toISOString(),
                        count: 25
                    },
                    {
                        metadata: {
                            name: 'payments-deployment-6c8f7b9d4.17abc124',
                            namespace: 'default'
                        },
                        involvedObject: {
                            kind: 'Pod',
                            name: 'payments-deployment-6c8f7b9d4-abc123',
                            namespace: 'default'
                        },
                        reason: 'Failed',
                        message: 'Failed to pull image "payments:v1.2.3": rpc error: code = Unknown desc = Error response from daemon: pull access denied for payments, repository does not exist or may require docker login',
                        type: 'Warning',
                        firstTimestamp: new Date(Date.now() - 20 * 60 * 1000).toISOString(),
                        lastTimestamp: new Date(Date.now() - 18 * 60 * 1000).toISOString(),
                        count: 5
                    },
                    {
                        metadata: {
                            name: 'api-deployment-abc123.17abc125',
                            namespace: 'default'
                        },
                        involvedObject: {
                            kind: 'Pod',
                            name: 'api-deployment-abc123-xyz456',
                            namespace: 'default'
                        },
                        reason: 'Started',
                        message: 'Started container api',
                        type: 'Normal',
                        firstTimestamp: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
                        lastTimestamp: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
                        count: 1
                    }
                ]
            }),
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